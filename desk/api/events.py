"""Eventos de una operación: tabla `trade_events`, solo de inserción.

Forma de un evento: `{"id", "trade_id", "type", "event_date" (date), "data" (dict),
"prev_event_id", "created_at"}`. `public_event` lo deja listo para JSON (`event_date` ISO).
"""
import json
import sqlite3
from datetime import date
from typing import Any, Dict, List

from desk.api import lifecycle
from desk.api.db import now_iso
from desk.api.errors import ApiError
from desk.api.lifecycle import EVENT_TYPES
from desk.api.pricing import PRODUCTS
from desk.api.validation import MAX_AMOUNT, finite_number, iso_date, number

_COLUMNS = "id, trade_id, type, event_date, data, prev_event_id, created_at"


def _decode(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "trade_id": row["trade_id"],
        "type": row["type"],
        "event_date": date.fromisoformat(row["event_date"]),
        "data": json.loads(row["data"]),
        "prev_event_id": row["prev_event_id"],
        "created_at": row["created_at"],
    }


def public_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """El evento con la fecha en ISO, listo para `jsonify`."""
    return {**event, "event_date": event["event_date"].isoformat()}


def load_events(conn: sqlite3.Connection, trade_id: int) -> List[Dict[str, Any]]:
    """Eventos de la operación en orden `(event_date, id)`."""
    rows = conn.execute(
        "SELECT %s FROM trade_events WHERE trade_id = ? ORDER BY event_date, id" % _COLUMNS,
        (trade_id,),
    ).fetchall()
    return [_decode(r) for r in rows]


def load_all_events(conn: sqlite3.Connection) -> Dict[int, List[Dict[str, Any]]]:
    """Eventos de todas las operaciones por `trade_id`, cada lista en orden `(event_date, id)`."""
    out = {}  # type: Dict[int, List[Dict[str, Any]]]
    rows = conn.execute(
        "SELECT %s FROM trade_events ORDER BY event_date, id" % _COLUMNS
    ).fetchall()
    for r in rows:
        out.setdefault(r["trade_id"], []).append(_decode(r))
    return out


def insert_event(
    conn: sqlite3.Connection, trade_id: int, type: str, event_date: date, data: Dict[str, Any]
) -> Dict[str, Any]:
    """Inserta un evento (sin commit) encadenado al último insertado de la operación.

    No valida `data` ni el estado de la operación: eso lo hace `post_event`.

    @return el evento insertado, con `event_date` como `date`.
    """
    if type not in EVENT_TYPES:
        raise ValueError("Tipo de evento desconocido: %s" % type)
    prev = conn.execute(
        "SELECT MAX(id) FROM trade_events WHERE trade_id = ?", (trade_id,)
    ).fetchone()[0]
    created_at = now_iso()
    cur = conn.execute(
        "INSERT INTO trade_events (trade_id, type, event_date, data, prev_event_id, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (trade_id, type, event_date.isoformat(), json.dumps(data), prev, created_at),
    )
    return {
        "id": cur.lastrowid,
        "trade_id": trade_id,
        "type": type,
        "event_date": event_date,
        "data": data,
        "prev_event_id": prev,
        "created_at": created_at,
    }


# Tipos que la API acepta; `execution` lo crea el alta de la operación y `reset`/`transfer` no se registran a mano.
API_EVENT_TYPES = ("quantity_change", "terms_change", "exercise", "termination")
_OPTIONS = ("fx_option", "swaption", "equity_option")
_PRICE_FIELD = {"irs": "fixed_rate", "fx_forward": "strike", "fx_option": "strike",
                "cap_floor": "strike", "swaption": "strike", "equity_option": "strike"}


def _terms_data(trade: Dict[str, Any], event_date: date, data: Dict[str, Any]) -> Dict[str, Any]:
    """`data` de un `terms_change`: solo el campo de precio del producto, revalidado sobre los términos vigentes."""
    partial = data.get("terms")
    price = _PRICE_FIELD.get(trade["product"])
    if price is None:
        raise ApiError(400, "Esta operación no admite cambio de términos", "terms")
    if not isinstance(partial, dict) or set(partial) != {price}:
        raise ApiError(400, "'terms' solo admite el campo '%s'" % price, "terms")
    if not finite_number(partial[price]):
        raise ApiError(400, "'%s' debe ser un número finito" % price, "terms")
    current = lifecycle.state(trade, trade["events"], event_date)["terms"]
    try:
        merged = PRODUCTS[trade["product"]].validate({**current, price: partial[price]})
    except ApiError as e:
        raise ApiError(400, e.error, "terms")
    return {"terms": {price: merged[price]}}


def post_event(conn: sqlite3.Connection, trade_id: int, body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Valida y registra un evento por la API; devuelve los eventos insertados (uno o dos).

    `termination` y `exercise` insertan además un `transfer` en MXN con `cause_event_id`.
    No hace commit: todo queda en la transacción de la petición.

    @param body `{"type", "event_date", "data"}` con `data` según el tipo.
    @return eventos insertados con `event_date` como `date`.
    @raise ApiError 404 (operación), 400 (tipo, fecha o `data`) o 409 (la operación no está viva en `event_date`).
    """
    from desk.api import portfolio  # import tardío: portfolio importa este módulo

    trade = portfolio.get_trade(conn, trade_id)
    kind = body.get("type")
    if not isinstance(kind, str) or kind not in EVENT_TYPES:
        raise ApiError(400, "Tipo de evento desconocido: %s" % (kind,), "type")
    if kind not in API_EVENT_TYPES:
        raise ApiError(400, "El tipo '%s' no se registra por la API" % kind, "type")
    if kind == "exercise" and trade["product"] not in _OPTIONS:
        raise ApiError(400, "Solo se ejercen opciones: no aplica a '%s'" % trade["product"], "type")
    event_date = iso_date(body, "event_date")
    if event_date < trade["trade_date"]:
        raise ApiError(400, "'event_date' no puede ser anterior a 'trade_date'", "event_date")
    data = body.get("data")
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ApiError(400, "'data' debe ser un objeto", "data")
    if kind == "quantity_change":
        data = {"notional": number(data, "notional", gt=0, le=MAX_AMOUNT)}
    elif kind == "terms_change":
        data = _terms_data(trade, event_date, data)
    else:  # termination / exercise
        data = {"amount": number(data, "amount", ge=-MAX_AMOUNT, le=MAX_AMOUNT)}
    status = lifecycle.state(trade, trade["events"], event_date)["status"]
    if status != "viva":
        raise ApiError(
            409, "La operación no está viva el %s (estado: %s)" % (event_date.isoformat(), status), "id"
        )
    created = [insert_event(conn, trade_id, kind, event_date, data)]
    if kind in ("termination", "exercise"):
        created.append(
            insert_event(
                conn, trade_id, "transfer", event_date,
                {"amount": data["amount"], "currency": "MXN", "cause_event_id": created[0]["id"]},
            )
        )
    return created
