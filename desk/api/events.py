"""Eventos de una operación: tabla `trade_events`, solo de inserción.

Forma de un evento: `{"id", "trade_id", "type", "event_date" (date), "data" (dict),
"prev_event_id", "created_at"}`. `public_event` lo deja listo para JSON (`event_date` ISO).
"""
import json
import sqlite3
from datetime import date
from typing import Any, Dict, List

from desk.api.db import now_iso
from desk.api.lifecycle import EVENT_TYPES

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


def post_event(conn: sqlite3.Connection, trade_id: int, body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Valida y registra un evento por la API; devuelve los eventos insertados (uno o dos).

    Responde 400/404/409 según el contrato. Se implementa en T4.
    """
    raise NotImplementedError("events.post_event se implementa en T4")
