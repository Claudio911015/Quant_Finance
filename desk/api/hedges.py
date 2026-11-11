"""Coberturas contables (IFRS 9): relaciones de cobertura, sus eventos y sus periodos en SQLite.

Una relación designa una fracción de una operación existente como instrumento de cobertura de una
partida cubierta (crédito o flujo pronosticado en USD). Aquí no hay matemática financiera: la
medición la hace `hedge_measure` con el motor de valuación existente. Las tres tablas son solo de
inserción (disparadores en `db.SCHEMA`): `hedge_relationships` no se modifica, `hedge_events` y
`hedge_periods` solo crecen.

Forma interna de una relación (`load_relationship`): las columnas de `hedge_relationships` con
`designation_date` y las fechas de `item_terms` (`start_date`, `maturity_date`, `date`) como `date`,
`item_terms`/`documentation` como dict, más `product`/`counterparty` de la operación,
`events` (`{"id","relationship_id","type","event_date" (date),"data" (dict),"created_at"}` en orden
`(event_date, id)`), `periods` (`{"id","relationship_id","snapshot_id","as_of" (date),"result"
(dict),"created_at"}` por `as_of`) y `designation` (el `data` del evento `designation`).
"""
import json
import sqlite3
from datetime import date
from typing import Any, Dict, List, Optional

from desk.api import fixings as fixing_store
from desk.api import lifecycle, market, portfolio
from desk.api import valuation as trade_valuation
from desk.api.db import now_iso
from desk.api.errors import ApiError
from desk.api.market import CURVES
from desk.api.pricing import PRODUCTS
from desk.api.validation import MAX_AMOUNT, choice, integer, iso_date, number, text

HEDGE_TYPES = ("cash_flow", "fair_value")
ITEM_KINDS = ("floating_loan", "fixed_loan", "forecast_fx")
INSTRUMENT_FOR = {"floating_loan": "irs", "fixed_loan": "irs", "forecast_fx": "fx_forward"}
VALID_COMBINATIONS = {"cash_flow": ("floating_loan", "forecast_fx"), "fair_value": ("fixed_loan",)}
LOAN_INDICES = ("TIIE-F", "SOFR")
LOAN_SIDES = ("pays_floating", "receives_floating")
FIXED_LOAN_SIDES = ("pays_fixed", "receives_fixed")
FX_SIDES = ("buy_usd", "sell_usd")
HEDGE_EVENT_TYPES = ("designation", "period_close", "dedesignation")
STATUS_ACTIVE, STATUS_DEDESIGNATED = "activa", "desdesignada"
DOC_FIELDS = ("risk_management_objective", "hedged_risk", "effectiveness_method", "ineffectiveness_sources")
NOTICE = "Asientos sugeridos. Metodología pendiente de revisión por un contador con experiencia en IFRS 9"
ACC_DERIVATIVE = "Derivado (valor razonable)"
ACC_OCI = "ORI — reserva de cobertura"
ACC_INEFFECTIVENESS = "Resultados — inefectividad de cobertura"
ACC_RECYCLING = "Resultados — partida cubierta (reciclaje)"
ACC_CASH = "Efectivo"
ACC_ITEM_ADJ = "Partida cubierta — ajuste de valor razonable"
ACC_FV_RESULT = "Resultados — cobertura de valor razonable"
ACCOUNTS = (ACC_DERIVATIVE, ACC_OCI, ACC_INEFFECTIVENESS, ACC_RECYCLING, ACC_FV_RESULT, ACC_CASH, ACC_ITEM_ADJ)  # orden de presentación
MAIN_RESULT_ACCOUNT = {"cash_flow": ACC_INEFFECTIVENESS, "fair_value": ACC_FV_RESULT}  # recibe el residuo de redondeo (P5)
FAIR_VALUE_LEVEL = 2
FAIR_VALUE_BASIS = "Nivel 2: insumos observables (curvas, tipo de cambio y volatilidades del snapshot)"
FROZEN_NOTE = "Reserva congelada al desdesignar: se reciclará a resultados cuando ocurra el flujo cubierto"

_TERM_DATE_KEYS = ("start_date", "maturity_date", "date")

# ------------------------------------------------------------------------------ lectura

_SELECT_RELATIONSHIPS = (
    "SELECT h.id, h.trade_id, t.product, c.name AS counterparty, h.fraction, h.hedge_type, h.item_kind,"
    " h.item_terms, h.hedge_ratio, h.designation_date, h.designation_snapshot, h.documentation,"
    " h.created_at FROM hedge_relationships h JOIN trades t ON t.id = h.trade_id"
    " JOIN counterparties c ON c.id = t.counterparty_id"
)


def _terms_in(terms: Dict[str, Any]) -> Dict[str, Any]:
    return {k: date.fromisoformat(v) if k in _TERM_DATE_KEYS else v for k, v in terms.items()}


def _terms_out(terms: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v.isoformat() if isinstance(v, date) else v for k, v in terms.items()}


def _event(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "relationship_id": row["relationship_id"],
        "type": row["type"],
        "event_date": date.fromisoformat(row["event_date"]),
        "data": json.loads(row["data"]),
        "created_at": row["created_at"],
    }


def _period(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "relationship_id": row["relationship_id"],
        "snapshot_id": row["snapshot_id"],
        "as_of": date.fromisoformat(row["as_of"]),
        "result": json.loads(row["result"]),
        "created_at": row["created_at"],
    }


def _decode(conn: sqlite3.Connection, row: sqlite3.Row) -> Dict[str, Any]:
    events = [
        _event(r)
        for r in conn.execute(
            "SELECT id, relationship_id, type, event_date, data, created_at FROM hedge_events"
            " WHERE relationship_id = ? ORDER BY event_date, id",
            (row["id"],),
        )
    ]
    periods = [
        _period(r)
        for r in conn.execute(
            "SELECT id, relationship_id, snapshot_id, as_of, result, created_at FROM hedge_periods"
            " WHERE relationship_id = ? ORDER BY as_of, id",
            (row["id"],),
        )
    ]
    return {
        "id": row["id"],
        "trade_id": row["trade_id"],
        "product": row["product"],
        "counterparty": row["counterparty"],
        "fraction": row["fraction"],
        "hedge_type": row["hedge_type"],
        "item_kind": row["item_kind"],
        "item_terms": _terms_in(json.loads(row["item_terms"])),
        "hedge_ratio": row["hedge_ratio"],
        "designation_date": date.fromisoformat(row["designation_date"]),
        "designation_snapshot": row["designation_snapshot"],
        "documentation": json.loads(row["documentation"]),
        "created_at": row["created_at"],
        "events": events,
        "periods": periods,
        "designation": next(e["data"] for e in events if e["type"] == "designation"),
    }


def load_relationship(conn: sqlite3.Connection, hedge_id: int) -> Dict[str, Any]:
    """Una relación en su forma interna; 404 `field: "id"` si no existe."""
    row = conn.execute(_SELECT_RELATIONSHIPS + " WHERE h.id = ?", (hedge_id,)).fetchone()
    if row is None:
        raise ApiError(404, "Cobertura inexistente: %s" % hedge_id, "id")
    return _decode(conn, row)


def load_relationships(conn: sqlite3.Connection, trade_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Relaciones por id (las de `trade_id` si se da) en su forma interna."""
    if trade_id is None:
        rows = conn.execute(_SELECT_RELATIONSHIPS + " ORDER BY h.id").fetchall()
    else:
        rows = conn.execute(_SELECT_RELATIONSHIPS + " WHERE h.trade_id = ? ORDER BY h.id", (trade_id,)).fetchall()
    return [_decode(conn, r) for r in rows]


def status(rel: Dict[str, Any]) -> str:
    """`desdesignada` si existe un evento `dedesignation`, si no `activa`."""
    if any(e["type"] == "dedesignation" for e in rel["events"]):
        return STATUS_DEDESIGNATED
    return STATUS_ACTIVE


def oci_balance(rel: Dict[str, Any]) -> float:
    """Reserva de cobertura: el `oci` del último periodo (0 si no hay periodos)."""
    return float(rel["periods"][-1]["result"]["oci"]) if rel["periods"] else 0.0


def last_close(rel: Dict[str, Any]) -> Optional[date]:
    """`as_of` del último cierre de periodo, o `None` si no hay."""
    return rel["periods"][-1]["as_of"] if rel["periods"] else None


# ------------------------------------------------------------------------------ forma HTTP

def public_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """El evento con la fecha en ISO, listo para `jsonify`."""
    return {**event, "event_date": event["event_date"].isoformat()}


def public_period(period: Dict[str, Any]) -> Dict[str, Any]:
    """`{"id","snapshot","as_of","created_at"}` y, a continuación, todo el `result` del periodo."""
    return {
        "id": period["id"],
        "snapshot": period["snapshot_id"],
        "as_of": period["as_of"].isoformat(),
        "created_at": period["created_at"],
        **period["result"],
    }


def public_relationship(rel: Dict[str, Any]) -> Dict[str, Any]:
    """Detalle de relación del contrato HTTP."""
    designation = rel["designation"]
    closed = [e for e in rel["events"] if e["type"] == "dedesignation"]
    closing = closed[-1] if closed else None
    last = last_close(rel)
    return {
        "id": rel["id"],
        "trade_id": rel["trade_id"],
        "product": rel["product"],
        "counterparty": rel["counterparty"],
        "fraction": rel["fraction"],
        "hedge_type": rel["hedge_type"],
        "item_kind": rel["item_kind"],
        "item_terms": _terms_out(rel["item_terms"]),
        "hedge_ratio": rel["hedge_ratio"],
        "designation_date": rel["designation_date"].isoformat(),
        "designation_snapshot": rel["designation_snapshot"],
        "documentation": rel["documentation"],
        "hypothetical": designation["hypothetical"],
        "designation": {
            k: designation[k] for k in ("snapshot", "as_of", "data_quality", "pv_inst", "pv_hypo")
        },
        "status": status(rel),
        "dedesignation": None
        if closing is None
        else {
            "date": closing["event_date"].isoformat(),
            "reason": closing["data"]["reason"],
            "frozen_oci": closing["data"]["frozen_oci"],
        },
        "oci_balance": oci_balance(rel),
        "last_close": last.isoformat() if last else None,
        "events": [public_event(e) for e in rel["events"]],
        "periods": [public_period(p) for p in rel["periods"]],
        "created_at": rel["created_at"],
    }


def public_summary(rel: Dict[str, Any]) -> Dict[str, Any]:
    """Resumen de relación para el listado."""
    last = last_close(rel)
    return {
        "id": rel["id"],
        "trade_id": rel["trade_id"],
        "product": rel["product"],
        "counterparty": rel["counterparty"],
        "hedge_type": rel["hedge_type"],
        "item_kind": rel["item_kind"],
        "fraction": rel["fraction"],
        "hedge_ratio": rel["hedge_ratio"],
        "designation_date": rel["designation_date"].isoformat(),
        "status": status(rel),
        "oci_balance": oci_balance(rel),
        "last_close": last.isoformat() if last else None,
        "periods_count": len(rel["periods"]),
    }


# ------------------------------------------------------------------------------ escritura

def insert_event(
    conn: sqlite3.Connection, hedge_id: int, type: str, event_date: date, data: Dict[str, Any]
) -> Dict[str, Any]:
    """Inserta un evento de la relación (sin commit); lo devuelve con `event_date` como `date`."""
    if type not in HEDGE_EVENT_TYPES:
        raise ValueError("Tipo de evento de cobertura desconocido: %s" % type)
    created_at = now_iso()
    cur = conn.execute(
        "INSERT INTO hedge_events (relationship_id, type, event_date, data, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (hedge_id, type, event_date.isoformat(), json.dumps(data), created_at),
    )
    return {
        "id": cur.lastrowid,
        "relationship_id": hedge_id,
        "type": type,
        "event_date": event_date,
        "data": data,
        "created_at": created_at,
    }


def insert_period(
    conn: sqlite3.Connection, hedge_id: int, snapshot_id: str, as_of: date, result: Dict[str, Any]
) -> Dict[str, Any]:
    """Inserta un cierre de periodo (sin commit); lo devuelve en la forma interna.

    Un segundo cierre con el mismo `as_of` viola `UNIQUE (relationship_id, as_of)`: quien llama
    valida antes con 409.
    """
    created_at = now_iso()
    cur = conn.execute(
        "INSERT INTO hedge_periods (relationship_id, snapshot_id, as_of, result, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (hedge_id, snapshot_id, as_of.isoformat(), json.dumps(result), created_at),
    )
    return {
        "id": cur.lastrowid,
        "relationship_id": hedge_id,
        "snapshot_id": snapshot_id,
        "as_of": as_of,
        "result": result,
        "created_at": created_at,
    }


def hypothetical_trade(rel: Dict[str, Any]) -> Dict[str, Any]:
    """Derivado hipotético de la designación como operación en memoria (nunca vive en `trades`)."""
    h = rel["designation"]["hypothetical"]
    return {
        "id": None,
        "product": h["product"],
        "counterparty": "Hipotético",
        "trade_date": date.fromisoformat(h["trade_date"]),
        "start_date": date.fromisoformat(h["start_date"]),
        "maturity_date": date.fromisoformat(h["maturity_date"]),
        "params": dict(h["params"]),
        "created_at": None,
        "events": [],
    }


# ------------------------------------------------------------------------------ designación

_MAX_ID = 2 ** 63 - 1  # mayor entero de SQLite


def build_hypothetical(
    item_kind: str, item_terms: Dict[str, Any], designation_date: date, mkt: Any, fixings: Any
) -> Dict[str, Any]:
    """Derivado hipotético `{"product","trade_date","start_date","maturity_date" (ISO),"params"}`
    a la par en el snapshot de designación.

    `item_terms` en su forma interna (fechas como `date`). Un crédito usa sus fechas tal cual y la
    tasa par del swap con ellas; un flujo pronosticado, el forward de mercado a su fecha.
    """
    if item_kind == "forecast_fx":
        forward_product = PRODUCTS["fx_forward"]
        quote = forward_product.validate(
            {
                "side": "buy" if item_terms["side"] == "buy_usd" else "sell",
                "notional_usd": item_terms["amount_usd"],
                "strike": 1.0,
                "days": (item_terms["date"] - designation_date).days,
            }
        )
        forward = forward_product.price(quote, mkt)["risk"]["forward"]
        return {
            "product": "fx_forward",
            "trade_date": designation_date.isoformat(),
            "start_date": designation_date.isoformat(),
            "maturity_date": item_terms["date"].isoformat(),
            "params": forward_product.validate({**quote, "strike": float(forward)}),
        }
    start, maturity = item_terms["start_date"], item_terms["maturity_date"]
    if item_kind == "floating_loan":
        side = "payer" if item_terms["side"] == "pays_floating" else "receiver"
    else:  # fixed_loan: el derivado hipotético recibe la fija que la deuda paga
        side = "receiver" if item_terms["side"] == "pays_fixed" else "payer"
    index = item_terms["index"]
    params = {
        "curve": index,
        "side": side,
        "notional": item_terms["notional"],
        "periods": max(1, int(round((maturity - start).days / CURVES[index]["period_days"]))),
        "fixed_rate": 0.0,
    }
    hypothetical = {
        "id": None, "product": "irs", "counterparty": "Hipotético", "trade_date": designation_date,
        "start_date": start, "maturity_date": maturity, "params": params, "created_at": None, "events": [],
    }
    swap = trade_valuation.aged_swap(hypothetical, params, mkt, fixings, [])
    try:
        params = PRODUCTS["irs"].validate({**params, "fixed_rate": float(swap.par_rate(mkt.env))})
    except ApiError as e:
        raise ApiError(400, "'maturity_date' fuera de rango: %s" % e.error, "maturity_date")
    return {
        "product": "irs",
        "trade_date": designation_date.isoformat(),
        "start_date": start.isoformat(),
        "maturity_date": maturity.isoformat(),
        "params": params,
    }


def _item_terms(item_kind: str, raw: Any, designation_date: date) -> Dict[str, Any]:
    """Términos de la partida cubierta normalizados (fechas como `date`); claves desconocidas se ignoran."""
    if not isinstance(raw, dict):
        raise ApiError(400, "'item_terms' debe ser un objeto con los términos de la partida cubierta", "item_terms")
    if item_kind == "forecast_fx":
        amount = number(raw, "amount_usd", gt=0, le=MAX_AMOUNT)
        day = iso_date(raw, "date")
        if day <= designation_date:
            raise ApiError(400, "'date' debe ser posterior a la fecha de designación", "date")
        return {"amount_usd": amount, "date": day, "side": choice(raw, "side", FX_SIDES)}
    index = choice(raw, "index", LOAN_INDICES)
    notional = number(raw, "notional", gt=0, le=MAX_AMOUNT)
    start = iso_date(raw, "start_date")
    maturity = iso_date(raw, "maturity_date")
    if maturity <= start:
        raise ApiError(400, "'maturity_date' debe ser posterior a 'start_date'", "maturity_date")
    if maturity <= designation_date:
        raise ApiError(400, "'maturity_date' debe ser posterior a la fecha de designación", "maturity_date")
    side = choice(raw, "side", LOAN_SIDES if item_kind == "floating_loan" else FIXED_LOAN_SIDES)
    return {"index": index, "notional": notional, "start_date": start, "maturity_date": maturity, "side": side}


def _documentation(raw: Any) -> Dict[str, str]:
    if not isinstance(raw, dict):
        raise ApiError(400, "'documentation' debe ser un objeto con %s" % ", ".join(DOC_FIELDS), "documentation")
    return {name: text(raw, name) for name in DOC_FIELDS}


def create_hedge(conn: sqlite3.Connection, body: Dict[str, Any]) -> Dict[str, Any]:
    """Valida el cuerpo de `POST /api/hedges` en el orden del contrato, guarda la relación y el
    evento `designation` (con el derivado hipotético de D3) y devuelve el detalle.

    Quien llama hace `commit`; nada se inserta si algo falla.
    """
    trade_id = integer(body, "trade_id", ge=1, le=_MAX_ID)
    try:
        trade = portfolio.get_trade(conn, trade_id)
    except ApiError:
        raise ApiError(404, "Operación inexistente: %s" % trade_id, "trade_id")
    snapshot_id = text(body, "snapshot")
    mkt = market.load_context(conn, snapshot_id)
    designation_date = iso_date(body, "designation_date", required=False)
    if designation_date is None:
        designation_date = mkt.as_of
    elif designation_date != mkt.as_of:
        raise ApiError(
            400, "'designation_date' debe ser el as_of del snapshot (%s)" % mkt.as_of.isoformat(), "designation_date"
        )
    hedge_type = choice(body, "hedge_type", HEDGE_TYPES)
    item_kind = choice(body, "item_kind", ITEM_KINDS)
    item_terms = _item_terms(item_kind, body.get("item_terms"), designation_date)
    if item_kind not in VALID_COMBINATIONS[hedge_type]:
        raise ApiError(
            400, "Una cobertura de %s no admite la partida %s" % (hedge_type, item_kind), "hedge_type"
        )
    if trade["product"] != INSTRUMENT_FOR[item_kind]:
        raise ApiError(
            400, "La partida %s se cubre con un %s, no con un %s" % (item_kind, INSTRUMENT_FOR[item_kind], trade["product"]),
            "item_kind",
        )
    if item_kind != "forecast_fx" and (trade["params"] or {}).get("curve") != item_terms["index"]:
        raise ApiError(400, "La curva de la operación no coincide con el índice de la partida cubierta", "index")
    fraction = number(body, "fraction", gt=0, le=1)
    hedge_ratio = number(body, "hedge_ratio", gt=0, le=MAX_AMOUNT, required=False, default=1.0)
    documentation = _documentation(body.get("documentation"))
    state = lifecycle.state(trade, trade["events"], designation_date)["status"]
    if state != "viva":
        raise ApiError(
            409, "La operación no está viva al %s (estado: %s)" % (designation_date.isoformat(), state), "trade_id"
        )
    committed = sum(r["fraction"] for r in load_relationships(conn, trade_id) if status(r) == STATUS_ACTIVE)
    if committed + fraction > 1 + 1e-12:
        raise ApiError(
            409, "La operación ya tiene designado %s de su nocional: la nueva fracción excede 1" % committed, "fraction"
        )

    fixings = fixing_store.load_all(conn)
    hypothetical = build_hypothetical(item_kind, item_terms, designation_date, mkt, fixings)
    pv_inst = float(trade_valuation.value_trade(trade, mkt, fixings)["pv_mxn"])
    pv_hypo = float(
        trade_valuation.value_trade(hypothetical_trade({"designation": {"hypothetical": hypothetical}}), mkt, fixings)[
            "pv_mxn"
        ]
    )
    snapshot_row = conn.execute("SELECT data FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
    sources = market.sources_of(json.loads(snapshot_row["data"]))
    cur = conn.execute(
        "INSERT INTO hedge_relationships (trade_id, fraction, hedge_type, item_kind, item_terms, hedge_ratio,"
        " designation_date, designation_snapshot, documentation, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            trade_id, fraction, hedge_type, item_kind, json.dumps(_terms_out(item_terms)), hedge_ratio,
            designation_date.isoformat(), snapshot_id, json.dumps(documentation), now_iso(),
        ),
    )
    insert_event(
        conn,
        cur.lastrowid,
        "designation",
        designation_date,
        {
            "snapshot": snapshot_id,
            "as_of": mkt.as_of.isoformat(),
            "data_quality": market.data_quality(sources),
            "pv_inst": pv_inst,
            "pv_hypo": pv_hypo,
            "hypothetical": hypothetical,
        },
    )
    return public_relationship(load_relationship(conn, cur.lastrowid))


# ------------------------------------------------------------------------------ stubs

def dedesignate(conn: sqlite3.Connection, hedge_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Desdesignación: evento `dedesignation` con `frozen_oci`; devuelve el detalle (T5)."""
    raise NotImplementedError("dedesignate")
