"""Portafolio: operaciones guardadas en SQLite y su valuación contra un snapshot.

Aquí no hay matemática financiera: cada operación se valúa con el `Product` de su
producto (que llama a `qfpy`). Las operaciones guardadas llevan los `params` ya
normalizados por `Product.validate`.
"""
import json
import sqlite3
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from desk.api import market
from desk.api.errors import ApiError
from desk.api.market import MarketContext
from desk.api.pricing import PRODUCTS
from desk.api.pricing.base import Product
from desk.api.seed_market import SNAPSHOT_ID
from desk.api.validation import NON_FINITE_MESSAGE, choice, has_non_finite, text

_NO_DESCRIPTION = {"notional": None, "currency": None, "maturity": None}


def _reference_as_of(conn: sqlite3.Connection) -> date:
    """Fecha de valor con la que se derivan vencimientos (la del snapshot `MX-DEMO`)."""
    row = conn.execute(
        "SELECT as_of FROM snapshots WHERE id = ?", (SNAPSHOT_ID,)
    ).fetchone()
    if row is None:
        raise ApiError(404, "Snapshot no encontrado: %s" % SNAPSHOT_ID, "snapshot")
    return date.fromisoformat(row["as_of"])


def _decode(row: sqlite3.Row) -> Dict[str, Any]:
    try:
        params = json.loads(row["params"])
    except ValueError:
        params = None  # fila corrupta: se reporta al valuarla, no rompe el listado
    return {
        "id": row["id"],
        "product": row["product"],
        "counterparty": row["counterparty"],
        "params": params,
        "created_at": row["created_at"],
    }


def _normalized(trade: Dict[str, Any]) -> Tuple[Product, Dict[str, Any]]:
    """Producto y `params` revalidados; lanza si la operación guardada no es valuable."""
    product = PRODUCTS.get(trade["product"])
    if product is None:
        raise ValueError("Producto desconocido: %s" % trade["product"])
    if not isinstance(trade["params"], dict):
        raise ValueError("Los parámetros guardados de la operación son ilegibles")
    return product, product.validate(trade["params"])


def _describe(trade: Dict[str, Any], as_of: date) -> Dict[str, Any]:
    """`notional`/`currency`/`maturity` de la operación; todo `None` si está corrupta."""
    try:
        product, params = _normalized(trade)
        return product.describe(params, as_of)
    except Exception:
        return dict(_NO_DESCRIPTION)


def _public(trade: Dict[str, Any], as_of: date) -> Dict[str, Any]:
    return {**trade, **_describe(trade, as_of)}


def load_trades(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Operaciones ordenadas por id con `params` decodificado (`None` si el JSON está corrupto)."""
    rows = conn.execute(
        "SELECT id, product, counterparty, params, created_at FROM trades ORDER BY id"
    ).fetchall()
    return [_decode(r) for r in rows]


def trade_pv_mxn(trade: Dict[str, Any], mkt: MarketContext) -> float:
    """PV en MXN de una operación de `load_trades` contra un contexto de mercado.

    Lanza (`ValueError`, `ApiError`, error de `qfpy`...) si la operación no se puede valuar;
    quien recorre el portafolio debe atrapar y reportar esa operación sin detener el resto.
    """
    product, params = _normalized(trade)
    return float(product.pv_mxn(params, mkt))


def list_trades(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Operaciones ordenadas por id, con notional/currency/maturity derivados."""
    as_of = _reference_as_of(conn)
    return [_public(t, as_of) for t in load_trades(conn)]


def create_trade(conn: sqlite3.Connection, body: Dict[str, Any]) -> Dict[str, Any]:
    """Valida `product`, `counterparty` y `params`; guarda y devuelve la operación."""
    name = choice(body, "product", tuple(PRODUCTS))
    counterparty = text(body, "counterparty")
    raw = body.get("params")
    if not isinstance(raw, dict):
        raise ApiError(400, "'params' debe ser un objeto con los parámetros del producto", "params")
    params = PRODUCTS[name].validate(raw)
    if name == "irs" and params["fixed_rate"] is None:
        raise ApiError(400, "Falta el parámetro 'fixed_rate'", "fixed_rate")
    as_of = _reference_as_of(conn)
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    cur = conn.execute(
        "INSERT INTO trades (product, counterparty, params, created_at) VALUES (?, ?, ?, ?)",
        (name, counterparty, json.dumps(params), created_at),
    )
    trade = {
        "id": cur.lastrowid,
        "product": name,
        "counterparty": counterparty,
        "params": params,
        "created_at": created_at,
    }
    return _public(trade, as_of)


def delete_trade(conn: sqlite3.Connection, trade_id: int) -> None:
    """Borra la operación; 404 `field: "id"` si no existe."""
    cur = conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    if cur.rowcount == 0:
        raise ApiError(404, "Operación inexistente: %s" % trade_id, "id")


def valuation(conn: sqlite3.Connection, snapshot_id: str) -> Dict[str, Any]:
    """Valuación del portafolio contra el snapshot; una operación que falla no detiene el resto."""
    mkt = market.load_context(conn, snapshot_id)
    rows = []
    total = 0.0
    for trade in load_trades(conn):
        row = {
            "id": trade["id"],
            "product": trade["product"],
            "counterparty": trade["counterparty"],
            **_describe(trade, mkt.as_of),
            "pv": None,
            "pv_mxn": None,
            "error": None,
        }
        try:
            pv_mxn = trade_pv_mxn(trade, mkt)
            # `pv` va en la moneda de la fila (USD = PV en MXN ÷ spot, inverso de la conversión).
            pv = pv_mxn / mkt.spot if row["currency"] == "USD" else pv_mxn
            if has_non_finite((pv, pv_mxn)):
                raise ValueError(NON_FINITE_MESSAGE)
            row["pv"] = pv
            row["pv_mxn"] = pv_mxn
            total += pv_mxn
        except Exception as e:  # nunca propaga: la fila lleva el error
            row["error"] = str(e)
        rows.append(row)
    return {
        "snapshot": snapshot_id,
        "as_of": mkt.as_of.isoformat(),
        "total_mxn": total,
        "rows": rows,
    }
