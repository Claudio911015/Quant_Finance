"""Portafolio: operaciones guardadas en SQLite y su valuación contra un snapshot.

Aquí no hay matemática financiera: cada operación se valúa con el `Product` de su
producto (que llama a `qfpy`). Las operaciones guardadas llevan en `terms` los `params`
ya normalizados por `Product.validate` (la forma de origen, plazo incluido), más las tres
fechas del contrato (`trade_date`, `start_date`, `maturity_date`) y sus eventos.
"""
import json
import sqlite3
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from desk.api import db, events, market
from desk.api import fixings as fixing_store
from desk.api import valuation as trade_valuation
from desk.api.errors import ApiError
from desk.api.market import CURVES, MarketContext
from desk.api.pricing import PRODUCTS
from desk.api.seed_market import SNAPSHOT_ID
from desk.api.validation import NON_FINITE_MESSAGE, choice, has_non_finite, iso_date, text

_NO_DESCRIPTION = {"notional": None, "currency": None, "maturity": None}


def _snapshot_as_of(conn: sqlite3.Connection, snapshot_id: str) -> date:
    """`as_of` del snapshot; 404 `field: "snapshot"` si no existe."""
    row = conn.execute("SELECT as_of FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
    if row is None:
        raise ApiError(404, "Snapshot no encontrado: %s" % snapshot_id, "snapshot")
    return date.fromisoformat(row["as_of"])


# ------------------------------------------------------------------ plazo <-> fechas

_DAYS_PER_YEAR = 365.0


def _tenor_days(product: str, p: Dict[str, Any]) -> int:
    """Días naturales del plazo de los términos (hasta el fin del contrato; swaption: la expiración)."""
    if product in ("irs", "cap_floor"):
        return p["periods"] * CURVES[p["curve"]]["period_days"]
    if product in ("fx_forward", "fx_option"):
        return p["days"]
    if product == "bond":
        return int(round(p["periods"] / p["frequency"] * _DAYS_PER_YEAR))
    # swaption / equity_option: el 1 mínimo evita un vencimiento igual al inicio con plazos diminutos.
    years = p["expiry_years"] if product == "swaption" else p["maturity_years"]
    return max(1, int(round(years * _DAYS_PER_YEAR)))


def _add_days(start: date, days: int) -> date:
    try:
        return start + timedelta(days=days)
    except OverflowError:
        raise ApiError(400, "El vencimiento excede el calendario admitido", "maturity_date")


def default_maturity(product: str, params: Dict[str, Any], start: date) -> date:
    """Vencimiento cuando la petición no trae `maturity_date`: `start_date` + plazo de los términos."""
    return _add_days(start, _tenor_days(product, params))


def fit_to_maturity(
    product: str, params: Dict[str, Any], start: date, maturity: date
) -> Tuple[Dict[str, Any], date]:
    """Con `maturity_date` en la petición manda la fecha: reescribe el plazo de los términos.

    `irs`, `cap_floor` y `bond` redondean a periodos enteros y devuelven el vencimiento ajustado.
    Lanza 400 `field: "maturity_date"` si los términos reescritos salen de las cotas del producto.
    """
    days = (maturity - start).days
    q = dict(params)
    if product in ("irs", "cap_floor"):
        q["periods"] = max(1, int(round(days / CURVES[q["curve"]]["period_days"])))
    elif product in ("fx_forward", "fx_option"):
        q["days"] = days
    elif product == "bond":
        q["periods"] = max(1, int(round(days * q["frequency"] / _DAYS_PER_YEAR)))
    elif product == "swaption":
        q["expiry_years"] = days / _DAYS_PER_YEAR
    else:  # equity_option
        q["maturity_years"] = days / _DAYS_PER_YEAR
    try:
        q = PRODUCTS[product].validate(q)
    except ApiError as e:
        raise ApiError(400, "'maturity_date' fuera de rango: %s" % e.error, "maturity_date")
    return q, _add_days(start, _tenor_days(product, q))


# --------------------------------------------------------------------------- lectura

_SELECT_TRADES = (
    "SELECT t.id, t.product, c.name AS counterparty, t.trade_date, t.start_date, t.maturity_date,"
    " t.terms, t.created_at FROM trades t JOIN counterparties c ON c.id = t.counterparty_id"
)


def _decode(row: sqlite3.Row, trade_events: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        params = json.loads(row["terms"])
    except ValueError:
        params = None  # fila corrupta: se reporta al valuarla, no rompe el listado
    return {
        "id": row["id"],
        "product": row["product"],
        "counterparty": row["counterparty"],
        "trade_date": date.fromisoformat(row["trade_date"]),
        "start_date": date.fromisoformat(row["start_date"]),
        "maturity_date": date.fromisoformat(row["maturity_date"]),
        "params": params,
        "created_at": row["created_at"],
        "events": trade_events,
    }


def _describe(trade: Dict[str, Any], as_of: date) -> Dict[str, Any]:
    """`notional`/`currency`/`maturity` de la operación; todo `None` si está corrupta."""
    try:
        product, params = trade_valuation.normalized(trade)
        return product.describe(params, as_of)
    except Exception:
        return dict(_NO_DESCRIPTION)


def public_trade(trade: Dict[str, Any]) -> Dict[str, Any]:
    """Forma HTTP de una operación (sin `events`): fechas ISO, `notional`/`currency` de origen."""
    described = _describe(trade, trade["start_date"])
    return {
        "id": trade["id"],
        "product": trade["product"],
        "counterparty": trade["counterparty"],
        "trade_date": trade["trade_date"].isoformat(),
        "start_date": trade["start_date"].isoformat(),
        "maturity_date": trade["maturity_date"].isoformat(),
        "params": trade["params"],
        "notional": described["notional"],
        "currency": described["currency"],
        "maturity": trade["maturity_date"].isoformat(),
        "created_at": trade["created_at"],
    }


def load_trades(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Operaciones ordenadas por id: fechas como `date`, `params` decodificado (`None` si el
    JSON está corrupto) y `events` en orden `(event_date, id)`."""
    all_events = events.load_all_events(conn)
    rows = conn.execute(_SELECT_TRADES + " ORDER BY t.id").fetchall()
    return [_decode(r, all_events.get(r["id"], [])) for r in rows]


def get_trade(conn: sqlite3.Connection, trade_id: int) -> Dict[str, Any]:
    """Una operación como en `load_trades`; 404 `field: "id"` si no existe."""
    row = conn.execute(_SELECT_TRADES + " WHERE t.id = ?", (trade_id,)).fetchone()
    if row is None:
        raise ApiError(404, "Operación inexistente: %s" % trade_id, "id")
    return _decode(row, events.load_events(conn, trade_id))


def trade_pv_mxn(
    trade: Dict[str, Any],
    mkt: MarketContext,
    fixings: Optional[Dict[str, Dict[date, float]]] = None,
) -> float:
    """PV en MXN de una operación de `load_trades` en `mkt.as_of` (0.0 si no está `viva`).

    Lanza (`ValueError`, `ApiError`, error de `qfpy`...) si la operación no se puede valuar;
    quien recorre el portafolio debe atrapar y reportar esa operación sin detener el resto.
    Sin `fixings` no hay fijaciones publicadas (ver `valuation.value_trade`).
    """
    return float(trade_valuation.value_trade(trade, mkt, fixings)["pv_mxn"])


def list_trades(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Operaciones ordenadas por id en su forma HTTP."""
    return [public_trade(t) for t in load_trades(conn)]


def counterparty_id(conn: sqlite3.Connection, name: str) -> int:
    """Id de la contraparte; la da de alta si es nueva."""
    conn.execute("INSERT OR IGNORE INTO counterparties (name) VALUES (?)", (name,))
    return conn.execute("SELECT id FROM counterparties WHERE name = ?", (name,)).fetchone()[0]


def insert_trade(
    conn: sqlite3.Connection,
    product: str,
    counterparty: str,
    trade_date: date,
    start_date: date,
    maturity_date: date,
    params: Dict[str, Any],
    created_at: str,
    trade_id: Optional[int] = None,
) -> int:
    """Inserta la operación y su evento `execution` (sin commit); devuelve el id.

    No valida: lo hacen `create_trade` y la migración. `trade_id` fija el id (migración).
    """
    cur = conn.execute(
        "INSERT INTO trades (id, product, counterparty_id, trade_date, start_date, maturity_date,"
        " terms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            trade_id,
            product,
            counterparty_id(conn, counterparty),
            trade_date.isoformat(),
            start_date.isoformat(),
            maturity_date.isoformat(),
            json.dumps(params),
            created_at,
        ),
    )
    events.insert_event(conn, cur.lastrowid, "execution", trade_date, {})
    return cur.lastrowid


def _dates_from_body(conn: sqlite3.Connection, body: Dict[str, Any]) -> Tuple[date, date, Optional[date]]:
    """`(trade_date, start_date, maturity_date | None)` de la petición con sus defaults y reglas."""
    trade = iso_date(body, "trade_date", required=False)
    start = iso_date(body, "start_date", required=False)
    maturity = iso_date(body, "maturity_date", required=False)
    snapshot = text(body, "snapshot", required=False)
    as_of = None
    if snapshot is not None or trade is None:
        as_of = _snapshot_as_of(conn, snapshot or SNAPSHOT_ID)
    if trade is None:
        trade = as_of
    if start is None:
        start = trade
    if start < trade:
        raise ApiError(400, "'start_date' no puede ser anterior a 'trade_date'", "start_date")
    if maturity is not None and maturity <= start:
        raise ApiError(400, "'maturity_date' debe ser posterior a 'start_date'", "maturity_date")
    return trade, start, maturity


def create_trade(conn: sqlite3.Connection, body: Dict[str, Any]) -> Dict[str, Any]:
    """Valida el cuerpo del contrato, guarda la operación con su `execution` y la devuelve."""
    name = choice(body, "product", tuple(PRODUCTS))
    counterparty = text(body, "counterparty")
    raw = body.get("params")
    if not isinstance(raw, dict):
        raise ApiError(400, "'params' debe ser un objeto con los parámetros del producto", "params")
    params = PRODUCTS[name].validate(raw)
    if name == "irs" and params["fixed_rate"] is None:
        raise ApiError(400, "Falta el parámetro 'fixed_rate'", "fixed_rate")
    trade_date, start_date, maturity = _dates_from_body(conn, body)
    if maturity is None:
        maturity = default_maturity(name, params, start_date)
    else:
        params, maturity = fit_to_maturity(name, params, start_date, maturity)
    created_at = db.now_iso()
    trade_id = insert_trade(
        conn, name, counterparty, trade_date, start_date, maturity, params, created_at
    )
    return public_trade(
        {
            "id": trade_id,
            "product": name,
            "counterparty": counterparty,
            "trade_date": trade_date,
            "start_date": start_date,
            "maturity_date": maturity,
            "params": params,
            "created_at": created_at,
        }
    )


def valuation(conn: sqlite3.Connection, snapshot_id: str) -> Dict[str, Any]:
    """Valuación del portafolio contra el snapshot; una operación que falla no detiene el resto."""
    mkt = market.load_context(conn, snapshot_id)
    fixings = fixing_store.load_all(conn)
    rows = []
    total = 0.0
    for trade in load_trades(conn):
        row = {
            "id": trade["id"],
            "product": trade["product"],
            "counterparty": trade["counterparty"],
            "trade_date": trade["trade_date"].isoformat(),
            "start_date": trade["start_date"].isoformat(),
            "maturity_date": trade["maturity_date"].isoformat(),
            "status": None,
            "notional": None,
            "currency": None,
            "maturity": trade["maturity_date"].isoformat(),
            "pv": None,
            "pv_mxn": None,
            "warnings": [],
            "error": None,
        }
        try:
            v = trade_valuation.value_trade(trade, mkt, fixings)
            if has_non_finite((v["pv"], v["pv_mxn"])):
                raise ValueError(NON_FINITE_MESSAGE)
            row.update(
                status=v["status"],
                notional=v["notional"],
                currency=v["currency"],
                pv=v["pv"],
                pv_mxn=v["pv_mxn"],
                warnings=v["warnings"],
            )
            total += v["pv_mxn"]
        except Exception as e:  # nunca propaga: la fila lleva el error
            row["error"] = str(e)
        rows.append(row)
    return {
        "snapshot": snapshot_id,
        "as_of": mkt.as_of.isoformat(),
        "total_mxn": total,
        "rows": rows,
    }
