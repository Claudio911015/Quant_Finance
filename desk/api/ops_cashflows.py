"""Calendario de flujos del portafolio (corte 5): liquidados, confirmados y proyectados."""
import csv
import io
import sqlite3
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from desk.api import fixings as fixing_store
from desk.api import lifecycle, market, ops_settlements, portfolio, settlement
from desk.api.errors import ApiError
from desk.api.validation import choice, iso_date, text

FLOW_STATUSES = ("settled", "confirmed", "projected")
CSV_COLUMNS = ("date", "trade_id", "counterparty", "product", "kind", "status", "currency",
               "amount", "amount_mxn", "confirmed_amount", "difference")

_DAY = timedelta(days=1)
_CONFIRMABLE_KINDS = ("coupon", "settlement")  # un transfer (terminación, ejercicio) no se confirma


def confirmations(trade: Dict[str, Any]) -> Dict[Tuple[date, str], Dict[str, Any]]:
    """`(fecha, moneda)` → `data` de la confirmación de liquidación de la operación en esa fecha y moneda.

    La moneda distingue las dos patas de un `xccy_swap`, que liquidan el mismo día. Si hubiera dos
    con la misma clave (la ruta de T3 lo impide) vale la última insertada.
    """
    return {
        (e["event_date"], e["data"].get("currency")): e["data"]
        for e in trade["events"]
        if ops_settlements.is_confirmation(e)
    }


def _row(trade: Dict[str, Any], flow: Dict[str, Any], status: str) -> Dict[str, Any]:
    """Fila del calendario; `flow` trae `date`, `kind`, `amount`, `currency`, `amount_mxn` y a veces `df`/`pv`."""
    return {
        "date": flow["date"],
        "trade_id": trade["id"],
        "counterparty": trade["counterparty"],
        "product": trade["product"],
        "kind": flow["kind"],
        "status": status,
        "currency": flow["currency"],
        "amount": flow["amount"],
        "amount_mxn": flow["amount_mxn"],
        "df": flow.get("df"),
        "pv": flow.get("pv"),
        "confirmed_amount": None,
        "difference": None,
    }


def _trade_rows(trade: Dict[str, Any], mkt: Any, fixings: Any) -> Dict[str, Any]:
    """Filas y avisos de una operación (liquidada, confirmada y proyectada); lanza si no se puede derivar.

    Devuelve `{"rows", "warnings"}` con `warnings` como lista de grupos para `merge_warnings`.
    """
    settled, settled_warnings = settlement.settled_flows(
        trade, fixings, trade["trade_date"] - _DAY, mkt.as_of, mkt.spot, mkt
    )
    confirmed = confirmations(trade)
    rows = []  # type: List[Dict[str, Any]]
    for flow in settled:
        row = _row(trade, flow, "settled")
        data = None
        if flow["kind"] in _CONFIRMABLE_KINDS:
            data = confirmed.get((date.fromisoformat(flow["date"]), flow["currency"]))
        if data is not None:
            row["status"] = "confirmed"
            row["confirmed_amount"] = float(data["amount"])
            row["difference"] = row["confirmed_amount"] - flow["amount"]
        rows.append(row)
    state = lifecycle.state(trade, trade["events"], mkt.as_of)
    projection_warnings = []  # type: List[Dict[str, Any]]
    projected = []  # type: List[Dict[str, Any]]
    if state["status"] == "viva":
        projected = settlement.projected_flows(trade, state["terms"], mkt, fixings, projection_warnings)
    for flow in projected:
        in_mxn = flow["amount"] * mkt.spot if flow["currency"] == "USD" else flow["amount"]
        rows.append(_row(trade, {**flow, "amount_mxn": in_mxn}, "projected"))
    return {"rows": rows, "warnings": [settled_warnings, projection_warnings]}


def _grouped(rows: List[Dict[str, Any]], key: str, with_amount: bool = False) -> List[Dict[str, Any]]:
    """Totales por `key` en orden ascendente: `amount_mxn` y `count` (y `amount` en la moneda si `with_amount`)."""
    groups = {}  # type: Dict[str, Dict[str, Any]]
    for row in rows:
        g = groups.setdefault(row[key], {"amount": 0.0, "amount_mxn": 0.0, "count": 0})
        g["amount"] += row["amount"]
        g["amount_mxn"] += row["amount_mxn"]
        g["count"] += 1
    out = []
    for name in sorted(groups):
        g = groups[name]
        item = {key: name}  # type: Dict[str, Any]
        if with_amount:
            item["amount"] = g["amount"]
        item["amount_mxn"] = g["amount_mxn"]
        item["count"] = g["count"]
        out.append(item)
    return out


def cashflows(conn: sqlite3.Connection, args: Any) -> Dict[str, Any]:
    """Cuerpo de `GET /api/cashflows`; `args` es `request.args` (el `format` lo valida la ruta).

    Liquidados (`settled`, o `confirmed` si la operación tiene su confirmación) y proyectados de
    cada operación, filtrados por ventana inclusiva, contraparte y moneda, y ordenados por
    `(date, trade_id, kind)`. Una operación que no se puede derivar va a `errors` y no aporta filas.

    @raise ApiError 400 `snapshot`/`from`/`to`/`currency`; 404 `snapshot` si no existe.
    """
    snapshot = text(args, "snapshot")
    mkt = market.load_context(conn, snapshot)
    lo = iso_date(args, "from", required=False)
    hi = iso_date(args, "to", required=False)
    if lo is not None and hi is not None and lo > hi:
        raise ApiError(400, "'from' no puede ser posterior a 'to'", "to")
    counterparty = text(args, "counterparty", required=False)
    currency = choice(args, "currency", ops_settlements.CURRENCIES) if "currency" in args else None
    lo_iso = lo.isoformat() if lo is not None else None
    hi_iso = hi.isoformat() if hi is not None else None

    fixings = fixing_store.load_all(conn)
    rows = []  # type: List[Dict[str, Any]]
    errors = []  # type: List[Dict[str, Any]]
    warnings = []  # type: List[List[Dict[str, Any]]]
    for trade in portfolio.load_trades(conn):
        if counterparty is not None and trade["counterparty"] != counterparty:
            continue
        try:
            derived = _trade_rows(trade, mkt, fixings)
        except Exception as e:  # una operación ilegible no tumba el calendario de las demás
            errors.append({"trade_id": trade["id"], "message": "No se pudo derivar sus flujos: %s" % e})
            continue
        rows.extend(derived["rows"])
        warnings.extend(derived["warnings"])
    rows = [
        r for r in rows
        if (lo_iso is None or r["date"] >= lo_iso)
        and (hi_iso is None or r["date"] <= hi_iso)
        and (currency is None or r["currency"] == currency)
    ]
    rows.sort(key=lambda r: (r["date"], r["trade_id"], r["kind"]))
    return {
        "snapshot": snapshot,
        "as_of": mkt.as_of.isoformat(),
        "from": lo_iso,
        "to": hi_iso,
        "counterparty": counterparty,
        "currency": currency,
        "rows": rows,
        "totals": {
            "amount_mxn": sum((r["amount_mxn"] for r in rows), 0.0),
            "by_date": _grouped(rows, "date"),
            "by_counterparty": _grouped(rows, "counterparty"),
            "by_currency": _grouped(rows, "currency", with_amount=True),
        },
        "errors": errors,
        "warnings": settlement.merge_warnings(*warnings),
    }


def _money(v: Optional[float]) -> str:
    return "" if v is None else "%.2f" % v


def cashflows_csv(payload: Dict[str, Any]) -> str:
    """Texto CSV de `payload["rows"]`: encabezado `CSV_COLUMNS`, montos con dos decimales, sin totales."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    for r in payload["rows"]:
        writer.writerow([
            r["date"], r["trade_id"], r["counterparty"], r["product"], r["kind"], r["status"],
            r["currency"], _money(r["amount"]), _money(r["amount_mxn"]),
            _money(r["confirmed_amount"]), _money(r["difference"]),
        ])
    return out.getvalue()
