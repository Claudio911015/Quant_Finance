"""Conciliación del PV propio contra el del banco (corte 5).

La descomposición de una diferencia (fecha, curva, tipo de cambio) es una ayuda de diagnóstico y
no hay fórmulas nuevas: todo PV sale de `valuation.value_trade`.
"""
import csv
import io
import json
import math
import re
import sqlite3
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from desk.api import fixings as fixings_store
from desk.api import lifecycle, market, ops_settings, portfolio, valuation
from desk.api.db import now_iso
from desk.api.errors import ApiError
from desk.api.market import MarketContext
from desk.api.validation import MAX_AMOUNT, number, text

DEFAULT_TOLERANCE = 0.0001        # fracción del nocional (= 0.01 %)
MAX_TOLERANCE = 0.1
EXPLAIN_CURVE_BP = 10.0           # |pb| ≤ 10 → explicable por curva
EXPLAIN_FX_PCT = 1.0              # |%| ≤ 1 → explicable por tipo de cambio
TERMS_CURVE_BP = 25.0             # sin explicación dentro de ±25 pb …
TERMS_FX_PCT = 2.0                # … o ±2 % de spot → bandera de términos
CURVE_PRODUCTS = ("irs", "cap_floor", "swaption", "bond")
FX_PRODUCTS = ("fx_forward", "fx_option")
RECON_STATUSES = ("conciliada", "explicable", "revisar")
MAX_CSV_ROWS = 5000
CURRENCIES = ("MXN", "USD")
CSV_COLUMNS = (
    "section", "line", "trade_id", "bank_ref", "product", "status", "own_pv_mxn", "bank_pv",
    "bank_currency", "bank_pv_mxn", "difference_mxn", "difference_rel", "date_attributed",
    "curve_bp", "fx_spot", "terms_flag", "reason",
)
_NEWTON_ITERATIONS = 20
_REQUIRED_COLUMNS = ("trade_id", "bank_pv", "currency")
_INTEGER = re.compile(r"[0-9]+")
_NUMBER = re.compile(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
DISCLAIMER = "La descomposición es una ayuda de diagnóstico, no una prueba: indica qué movimiento explicaría la diferencia, no que lo haya causado."


def context_at(mkt: MarketContext, on: date) -> MarketContext:
    """Mismo mercado (curvas, spot, superficie) con otra fecha de valuación."""
    return MarketContext(
        mkt.snapshot_id, on, mkt.curves, mkt.pillars, mkt.spot, mkt.surface, mkt.hw, mkt.factors
    )


def business_day(d: date, step: int) -> date:
    """`|step|` días hábiles (lunes a viernes, sin feriados) después (`step > 0`) o antes de `d`."""
    direction = 1 if step > 0 else -1
    out = d
    for _ in range(abs(step)):
        out += timedelta(days=direction)
        while out.weekday() >= 5:
            out += timedelta(days=direction)
    return out




# ------------------------------------------------------------------ una operación

def _newton(f: Callable[[float], float], step: float, limit: float, scale: float) -> Optional[float]:
    """Raíz de `f` por Newton desde 0 con pendiente por diferencia finita hacia adelante de `step`.

    Hasta `_NEWTON_ITERATIONS` iteraciones; converge si `|f| <= 1e-8 × scale`. `None` si la
    pendiente es ~0, si la solución sale de `±limit`, si `f` no es finita o lanza, o si no converge.
    """
    tol = 1e-8 * scale
    min_slope = 1e-12 * scale
    x = 0.0
    try:
        for i in range(_NEWTON_ITERATIONS + 1):
            fx = f(x)
            if not math.isfinite(fx):
                return None
            if abs(fx) <= tol:
                return x
            if i == _NEWTON_ITERATIONS:
                return None
            slope = (f(x + step) - fx) / step
            if not math.isfinite(slope) or abs(slope) < min_slope:
                return None
            x -= fx / slope
            if abs(x) > limit:
                return None
    except Exception:  # la valuación puede lanzar en un desplazamiento extremo
        return None
    return None


def _describe(trade: Dict[str, Any], mkt: MarketContext) -> Tuple[float, Optional[str], Dict[str, Any]]:
    """`(nocional en MXN, moneda de origen, términos vigentes)` en `mkt.as_of`; lanza si es ilegible.

    Usa el `notional` de `Product.describe` (el mismo que devuelve `value_trade`): es el campo de
    nocional de los términos vigentes y, en `equity_option`, `quantity × spot` en MXN.
    """
    product, _ = valuation.normalized(trade)
    terms = lifecycle.state(trade, trade["events"], mkt.as_of)["terms"]
    described = product.describe(terms, mkt.as_of)
    notional = abs(float(described["notional"]))
    if described["currency"] == "USD":
        notional *= mkt.spot
    return notional, described["currency"], terms


def _date_factor(
    trade: Dict[str, Any], own: float, bank: float, tol_abs: float, mkt: MarketContext, fixings: Dict[str, Dict[date, float]]
) -> Optional[Dict[str, Any]]:
    """PV propio un día hábil antes y después, y si el PV del banco cae en ese rango (± tolerancia)."""
    prev_date = business_day(mkt.as_of, -1)
    next_date = business_day(mkt.as_of, 1)
    try:
        val_prev = valuation.value_trade(trade, context_at(mkt, prev_date), fixings)
        val_next = valuation.value_trade(trade, context_at(mkt, next_date), fixings)
    except Exception:
        return None
    pv_prev, pv_next = val_prev["pv_mxn"], val_next["pv_mxn"]
    # corte 5 (T7): un día vecino en que la operación no está viva (aún no pactada o ya vencida) vale 0 por
    # definición, no por mercado; meterlo en el rango lo ensancharía hasta 0 y casi cualquier PV del banco de una
    # operación nueva saldría "atribuible a la fecha". Se muestra su PV, pero no cuenta para el rango.
    comparable = [own] + [v["pv_mxn"] for v in (val_prev, val_next) if v.get("status") == "viva"]
    low, high = min(comparable), max(comparable)
    return {
        "prev_date": prev_date.isoformat(),
        "next_date": next_date.isoformat(),
        "pv_prev": pv_prev,
        "pv_next": pv_next,
        "attributed": low - tol_abs <= bank <= high + tol_abs,
    }


def reconcile_trade(
    trade: Dict[str, Any],
    bank_pv_mxn: float,
    mkt: MarketContext,
    fixings: Dict[str, Dict[date, float]],
    tolerance: float,
) -> Dict[str, Any]:
    """Fila conciliada de una operación (sin `line` ni `bank_*`): PV propio, diferencia, estado y
    descomposición indicativa (fecha, curva o tipo de cambio). Si la valuación lanza, la fila es
    `revisar` con `error` y sin descomposición.
    """
    row = {
        "trade_id": trade["id"],
        "product": trade["product"],
        "currency": None,
        "notional_mxn": 0.0,
        "own_pv_mxn": None,
        "difference_mxn": None,
        "difference_rel": None,
        "status": "revisar",
        "decomposition": None,
        "terms_flag": False,  # Hueco: con error no se sabe si son los términos; no se levanta la bandera.
        "error": None,
    }  # type: Dict[str, Any]
    try:
        notional_mxn, currency, terms = _describe(trade, mkt)
        row["currency"], row["notional_mxn"] = currency, notional_mxn
    except Exception as exc:
        row["error"] = str(exc) or exc.__class__.__name__
        return row
    try:
        own = float(valuation.value_trade(trade, mkt, fixings)["pv_mxn"])
    except Exception as exc:
        row["error"] = str(exc) or exc.__class__.__name__
        return row

    diff = own - bank_pv_mxn
    tol_abs = tolerance * notional_mxn
    scale = max(notional_mxn, 1.0)
    name = trade["product"]

    def gap(shifted: Callable[[float], MarketContext]) -> Callable[[float], float]:
        """PV propio con el mercado desplazado `x` menos el del banco (en `x = 0` reusa el ya calculado)."""
        def f(x: float) -> float:
            if x == 0.0:
                return diff
            return valuation.value_trade(trade, shifted(x), fixings)["pv_mxn"] - bank_pv_mxn
        return f

    date_factor = _date_factor(trade, own, bank_pv_mxn, tol_abs, mkt, fixings)
    curve = fx = None  # type: Optional[Dict[str, Any]]
    bp = pct = None  # type: Optional[float]
    if name in CURVE_PRODUCTS:
        curve_name = terms.get("curve", "TIIE-F")
        bp = _newton(gap(lambda x: mkt.shifted(curve=curve_name, parallel_bp=x)), 1.0, 1000.0, scale)
        curve = {"curve": curve_name, "bp": bp}
    elif name in FX_PRODUCTS:
        pct = _newton(gap(lambda x: mkt.shifted(spot_pct=x)), 0.01, 50.0, scale)
        fx = {"spot": None if pct is None else mkt.spot * (1.0 + pct / 100.0), "pct": pct}

    attributed = bool(date_factor and date_factor["attributed"])
    if abs(diff) <= tol_abs:
        status = "conciliada"
    elif attributed or (bp is not None and abs(bp) <= EXPLAIN_CURVE_BP) or (
        pct is not None and abs(pct) <= EXPLAIN_FX_PCT
    ):
        status = "explicable"
    else:
        status = "revisar"
    row.update(
        own_pv_mxn=own,
        difference_mxn=diff,
        difference_rel=diff / notional_mxn if notional_mxn else None,
        status=status,
        decomposition={"date": date_factor, "curve": curve, "fx": fx},
        terms_flag=status == "revisar"
        and (bp is None or abs(bp) > TERMS_CURVE_BP)
        and (pct is None or abs(pct) > TERMS_FX_PCT),
    )
    return row


# ------------------------------------------------------------------------ el CSV

def _csv_error(line: int, message: str) -> ApiError:
    return ApiError(400, "Línea %d: %s" % (line, message), "csv")


def _read_csv(raw: str) -> Tuple[Dict[str, int], List[Tuple[int, List[str]]]]:
    """Posición de cada columna y las filas de datos `(línea, celdas)`; las vacías se ignoran.

    La línea es la física del texto (el encabezado suele ser la 1).
    """
    rows = []  # type: List[Tuple[int, List[str]]]
    header = None  # type: Optional[Dict[str, int]]
    reader = csv.reader(io.StringIO(raw))
    try:
        for cells in reader:
            if not any(c.strip() for c in cells):
                continue
            if header is None:
                names = [c.strip() for c in cells]
                for column in _REQUIRED_COLUMNS:
                    if column not in names:
                        raise ApiError(400, "Falta la columna '%s'" % column, "csv")
                header = {n: i for i, n in reversed(list(enumerate(names)))}  # la primera repetida gana
                continue
            rows.append((reader.line_num, cells))
            if len(rows) > MAX_CSV_ROWS:
                raise ApiError(400, "El CSV pasa de %d filas de datos" % MAX_CSV_ROWS, "csv")
    except csv.Error as exc:
        raise ApiError(400, "CSV ilegible: %s" % exc, "csv")
    if header is None:
        raise ApiError(400, "Falta la columna '%s'" % _REQUIRED_COLUMNS[0], "csv")
    if not rows:
        raise ApiError(400, "El CSV no trae filas de datos", "csv")
    return header, rows


def _parse_row(line: int, cells: List[str], header: Dict[str, int]) -> Dict[str, Any]:
    def cell(name: str) -> str:
        i = header.get(name)
        return cells[i].strip() if i is not None and i < len(cells) else ""

    raw_id, raw_pv, currency, bank_ref = cell("trade_id"), cell("bank_pv"), cell("currency"), cell("bank_ref") or None
    if raw_id and not _INTEGER.fullmatch(raw_id):
        raise _csv_error(line, "trade_id debe ser un entero o ir vacío")
    if not raw_id and bank_ref is None:
        raise _csv_error(line, "falta trade_id o bank_ref")
    pv = float(raw_pv) if _NUMBER.fullmatch(raw_pv) else float("nan")
    if not math.isfinite(pv):
        raise _csv_error(line, "bank_pv debe ser un número finito")
    if abs(pv) > MAX_AMOUNT:
        raise _csv_error(line, "bank_pv no puede pasar de %g en valor absoluto" % MAX_AMOUNT)
    if currency not in CURRENCIES:
        raise _csv_error(line, "currency debe ser %s" % " o ".join(CURRENCIES))
    return {
        "line": line,
        "trade_id": int(raw_id) if raw_id else None,
        "bank_pv": pv,
        "currency": currency,
        "bank_ref": bank_ref,
    }


# --------------------------------------------------------------------- la corrida

def _pair(
    entry: Dict[str, Any],
    counterparty: str,
    trades: Dict[int, Dict[str, Any]],
    refs: Dict[str, int],
) -> Tuple[Optional[int], Optional[Dict[str, Any]], Optional[str]]:
    """`(id efectivo, operación emparejada, motivo si no hay pareja)`: por `trade_id` si viene, si no
    por la referencia registrada entre las operaciones de la contraparte."""
    if entry["trade_id"] is not None:
        tid = entry["trade_id"]
        trade = trades.get(tid)
        if trade is None:
            return tid, None, "Operación inexistente"
        if trade["counterparty"] != counterparty:
            return tid, None, "La operación es de otra contraparte"
        return tid, trade, None
    tid = refs.get(entry["bank_ref"])
    if tid is None:
        return None, None, "Referencia no encontrada"
    return tid, trades[tid], None


def _summary(rows: List[Dict[str, Any]], bank_only: List[Any], own_only: List[Any]) -> Dict[str, Any]:
    valued = [r for r in rows if r["error"] is None]
    return {
        "matched": len(rows),
        "conciliada": sum(1 for r in rows if r["status"] == "conciliada"),
        "explicable": sum(1 for r in rows if r["status"] == "explicable"),
        "revisar": sum(1 for r in rows if r["status"] == "revisar"),
        "bank_only": len(bank_only),
        "own_only": len(own_only),
        "own_pv_mxn": sum(r["own_pv_mxn"] for r in valued),
        "bank_pv_mxn": sum(r["bank_pv_mxn"] for r in valued),
        "difference_mxn": sum(r["difference_mxn"] for r in valued),
    }


def create_run(conn: sqlite3.Connection, body: Dict[str, Any]) -> Dict[str, Any]:
    """Concilia el CSV del banco contra la valuación propia y guarda la corrida (sin commit).

    Devuelve lo mismo que `get_run` de la corrida creada. Toda validación ocurre antes de escribir.

    @raise ApiError 400 `snapshot`/`counterparty`/`tolerance`/`csv`; 404 `snapshot` o `counterparty`.
    """
    snapshot = text(body, "snapshot")
    mkt = market.load_context(conn, snapshot)
    counterparty = text(body, "counterparty")
    if conn.execute("SELECT 1 FROM counterparties WHERE name = ?", (counterparty,)).fetchone() is None:
        raise ApiError(404, "Contraparte inexistente: %s" % counterparty, "counterparty")
    tolerance = number(
        body, "tolerance", ge=0, le=MAX_TOLERANCE, required=False, default=DEFAULT_TOLERANCE
    )
    text(body, "csv")  # obligatorio y texto; se guarda crudo
    header, raw_rows = _read_csv(body["csv"])

    trades = {t["id"]: t for t in portfolio.load_trades(conn)}
    refs = ops_settings.refs_by_counterparty(conn, counterparty)
    fixings = fixings_store.load_all(conn)

    rows = []  # type: List[Dict[str, Any]]
    bank_only = []  # type: List[Dict[str, Any]]
    seen = {}  # type: Dict[int, int]  # id de operación → línea
    for line, cells in raw_rows:
        entry = _parse_row(line, cells, header)
        tid, trade, reason = _pair(entry, counterparty, trades, refs)
        if tid is not None:
            if tid in seen:
                raise _csv_error(line, "la operación %d ya viene en la línea %d" % (tid, seen[tid]))
            seen[tid] = line
        if trade is None:
            bank_only.append({
                "line": line,
                "trade_id": entry["trade_id"],
                "bank_ref": entry["bank_ref"],
                "bank_pv": entry["bank_pv"],
                "currency": entry["currency"],
                "reason": reason,
            })
            continue
        bank_mxn = entry["bank_pv"] * mkt.spot if entry["currency"] == "USD" else entry["bank_pv"]
        result = reconcile_trade(trade, bank_mxn, mkt, fixings, tolerance)
        rows.append({
            "line": line,
            "trade_id": result["trade_id"],
            "bank_ref": entry["bank_ref"],
            "product": result["product"],
            "currency": result["currency"],
            "notional_mxn": result["notional_mxn"],
            "own_pv_mxn": result["own_pv_mxn"],
            "bank_pv": entry["bank_pv"],
            "bank_currency": entry["currency"],
            "bank_pv_mxn": bank_mxn,
            "difference_mxn": result["difference_mxn"],
            "difference_rel": result["difference_rel"],
            "status": result["status"],
            "decomposition": result["decomposition"],
            "terms_flag": result["terms_flag"],
            "error": result["error"],
        })

    own_only = []  # type: List[Dict[str, Any]]
    for tid, trade in trades.items():  # por id
        if trade["counterparty"] != counterparty or tid in seen or not valuation.is_live(trade, mkt.as_of):
            continue
        try:
            pv = float(valuation.value_trade(trade, mkt, fixings)["pv_mxn"])
        except Exception:
            pv = None
        own_only.append({"trade_id": tid, "product": trade["product"], "own_pv_mxn": pv})

    cur = conn.execute(
        "INSERT INTO reconciliations (snapshot_id, as_of, counterparty, tolerance, csv, summary, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            mkt.snapshot_id,
            mkt.as_of.isoformat(),
            counterparty,
            tolerance,
            body["csv"],
            json.dumps(_summary(rows, bank_only, own_only)),
            now_iso(),
        ),
    )
    run_id = cur.lastrowid
    for kind, items in (("matched", rows), ("bank_only", bank_only), ("own_only", own_only)):
        for item in items:
            conn.execute(
                "INSERT INTO reconciliation_rows (reconciliation_id, kind, trade_id, result) VALUES (?, ?, ?, ?)",
                (run_id, kind, item["trade_id"], json.dumps(item)),
            )
    return get_run(conn, run_id)


def list_runs(conn: sqlite3.Connection, counterparty: Optional[str] = None) -> List[Dict[str, Any]]:
    """Corridas guardadas, de la más reciente a la más antigua, sin el detalle de filas."""
    sql = "SELECT id, snapshot_id, as_of, counterparty, tolerance, created_at, summary FROM reconciliations"
    params = ()  # type: Tuple[Any, ...]
    if counterparty is not None:
        sql += " WHERE counterparty = ?"
        params = (counterparty,)
    return [
        {
            "id": r["id"],
            "snapshot": r["snapshot_id"],
            "as_of": r["as_of"],
            "counterparty": r["counterparty"],
            "tolerance": r["tolerance"],
            "created_at": r["created_at"],
            "summary": json.loads(r["summary"]),
        }
        for r in conn.execute(sql + " ORDER BY id DESC", params)
    ]


def get_run(conn: sqlite3.Connection, run_id: int) -> Dict[str, Any]:
    """Detalle de una corrida reconstruido de lo guardado; 404 `id` si no existe."""
    head = conn.execute("SELECT * FROM reconciliations WHERE id = ?", (run_id,)).fetchone()
    if head is None:
        raise ApiError(404, "Conciliación inexistente: %s" % run_id, "id")
    groups = {"matched": [], "bank_only": [], "own_only": []}  # type: Dict[str, List[Any]]
    for r in conn.execute(
        "SELECT kind, result FROM reconciliation_rows WHERE reconciliation_id = ? ORDER BY id", (run_id,)
    ):
        groups[r["kind"]].append(json.loads(r["result"]))
    return {
        "id": head["id"],
        "snapshot": head["snapshot_id"],
        "as_of": head["as_of"],
        "counterparty": head["counterparty"],
        "tolerance": head["tolerance"],
        "created_at": head["created_at"],
        "disclaimer": DISCLAIMER,
        "summary": json.loads(head["summary"]),
        "rows": groups["matched"],
        "bank_only": groups["bank_only"],
        "own_only": groups["own_only"],
    }


# --------------------------------------------------------------------------- CSV

def _fmt(v: Optional[float], spec: str) -> str:
    return "" if v is None else spec % v


def _yes_no(v: Optional[bool]) -> str:
    return "" if v is None else ("si" if v else "no")


def run_csv(run: Dict[str, Any]) -> str:
    """Texto CSV del detalle: una fila por elemento, con su `section` (`conciliacion`, `solo_banco`,
    `solo_propia`); vacío lo que no aplica."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    for r in run["rows"]:
        deco = r["decomposition"] or {}
        date_factor, curve, fx = deco.get("date"), deco.get("curve"), deco.get("fx")
        writer.writerow([
            "conciliacion", r["line"], r["trade_id"], r["bank_ref"] or "", r["product"], r["status"],
            _fmt(r["own_pv_mxn"], "%.2f"), _fmt(r["bank_pv"], "%.2f"), r["bank_currency"],
            _fmt(r["bank_pv_mxn"], "%.2f"), _fmt(r["difference_mxn"], "%.2f"),
            _fmt(r["difference_rel"], "%.10f"),
            _yes_no(date_factor["attributed"] if date_factor else None),
            _fmt(curve["bp"] if curve else None, "%.4f"), _fmt(fx["spot"] if fx else None, "%.6f"),
            _yes_no(r["terms_flag"]), r["error"] or "",
        ])
    for b in run["bank_only"]:
        writer.writerow([
            "solo_banco", b["line"], "" if b["trade_id"] is None else b["trade_id"], b["bank_ref"] or "",
            "", "", "", _fmt(b["bank_pv"], "%.2f"), b["currency"], "", "", "", "", "", "", "", b["reason"],
        ])
    for o in run["own_only"]:
        writer.writerow([
            "solo_propia", "", o["trade_id"], "", o["product"], "", _fmt(o["own_pv_mxn"], "%.2f"),
            "", "", "", "", "", "", "", "", "", "",
        ])
    return out.getvalue()
