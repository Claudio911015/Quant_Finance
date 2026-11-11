"""Colateral por contraparte: historial de la moneda de colateral (CSA) y su API.

No hay columna en `counterparties`: la moneda vigente en una fecha `d` es la del último evento
`collateral_change` de `counterparty_events` (orden `(effective_date, id)`) con
`effective_date <= d`; sin eventos, `"MXN"`. La tabla es solo de inserción, así que el historial
completo queda y una valuación a una fecha pasada usa el colateral que regía entonces.
"""
import json
import re
import sqlite3
from datetime import date
from typing import Any, Dict, List, Optional

from desk.api import db
from desk.api.errors import ApiError
from desk.api.validation import choice, iso_date

CURRENCIES = ("MXN", "USD")
DEFAULT_CURRENCY = "MXN"

_EVENT_TYPE = "collateral_change"
_ID = re.compile(r"[0-9]{1,18}")  # cabe en el entero de SQLite; "1_0" o " 1" no son ids


def _currency_of(raw: str) -> Optional[str]:
    """Moneda de un evento guardado; `None` si el JSON es ilegible o la moneda no es válida."""
    try:
        value = json.loads(raw).get("collateral_currency")
    except (ValueError, AttributeError):
        return None
    return value if value in CURRENCIES else None


def history(conn: sqlite3.Connection) -> Dict[str, List[Dict[str, Any]]]:
    """Historial de colateral por nombre de contraparte: `[{"effective_date": date, "currency"}]`.

    Cada contraparte aparece (lista vacía si nunca cambió), ordenada por `(effective_date, id)`.
    Un evento con datos ilegibles se ignora: no rompe la lectura de todo el portafolio.
    """
    out = {}  # type: Dict[str, List[Dict[str, Any]]]
    for r in conn.execute("SELECT name FROM counterparties ORDER BY name"):
        out[r["name"]] = []
    rows = conn.execute(
        "SELECT c.name, e.effective_date, e.data FROM counterparty_events e"
        " JOIN counterparties c ON c.id = e.counterparty_id WHERE e.type = ?"
        " ORDER BY e.effective_date, e.id",
        (_EVENT_TYPE,),
    )
    for r in rows:
        currency = _currency_of(r["data"])
        if currency is not None:
            out[r["name"]].append(
                {"effective_date": date.fromisoformat(r["effective_date"]), "currency": currency}
            )
    return out


def currency_on(trade: Dict[str, Any], on: date) -> str:
    """Moneda de colateral de la operación en la fecha `on` (`"MXN"` si no hay historial).

    Usa `trade.get("collateral", [])`: un dict en memoria sin la clave (hipotéticos de coberturas,
    pruebas) es colateral MXN. Gana el último evento con `effective_date <= on`; a igual fecha,
    el que va después en la lista.
    """
    currency = DEFAULT_CURRENCY
    best = None
    for e in trade.get("collateral", []):
        if e["effective_date"] <= on and (best is None or e["effective_date"] >= best):
            best, currency = e["effective_date"], e["currency"]
    return currency


def _public(row: sqlite3.Row, trades: int, events: List[Dict[str, Any]]) -> Dict[str, Any]:
    last = events[-1] if events else None
    return {
        "id": row["id"],
        "name": row["name"],
        "collateral_currency": last["collateral_currency"] if last else DEFAULT_CURRENCY,
        "effective_date": last["effective_date"] if last else None,
        "trades": trades,
        "history": events,
    }


def _events_by_counterparty(conn: sqlite3.Connection) -> Dict[int, List[Dict[str, Any]]]:
    out = {}  # type: Dict[int, List[Dict[str, Any]]]
    rows = conn.execute(
        "SELECT id, counterparty_id, effective_date, data, created_at FROM counterparty_events"
        " WHERE type = ? ORDER BY effective_date, id",
        (_EVENT_TYPE,),
    )
    for r in rows:
        currency = _currency_of(r["data"])
        if currency is not None:
            out.setdefault(r["counterparty_id"], []).append(
                {
                    "id": r["id"],
                    "collateral_currency": currency,
                    "effective_date": r["effective_date"],
                    "created_at": r["created_at"],
                }
            )
    return out


def _trade_counts(conn: sqlite3.Connection) -> Dict[int, int]:
    rows = conn.execute("SELECT counterparty_id, COUNT(*) AS n FROM trades GROUP BY counterparty_id")
    return {r["counterparty_id"]: r["n"] for r in rows}


def list_counterparties(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Contrapartes por nombre en su forma pública.

    `{"id", "name", "collateral_currency", "effective_date", "trades", "history"}`: la moneda y la
    fecha son las del último evento registrado (`"MXN"` y `None` si no hay), aunque su fecha efectiva
    sea posterior a la fecha de valuación; el colateral que rige en una fecha lo da `history` (la
    interfaz lo lee de ahí, como `currency_on`). `trades` cuenta las operaciones de la contraparte e
    `history` son sus eventos por `(effective_date, id)`.
    """
    events = _events_by_counterparty(conn)
    counts = _trade_counts(conn)
    rows = conn.execute("SELECT id, name FROM counterparties ORDER BY name").fetchall()
    return [_public(r, counts.get(r["id"], 0), events.get(r["id"], [])) for r in rows]


def change_collateral(
    conn: sqlite3.Connection, counterparty_id_raw: str, body: Dict[str, Any]
) -> Dict[str, Any]:
    """Valida y registra (sin commit) un cambio de moneda de colateral; devuelve la contraparte.

    Orden de las validaciones: id no entero o inexistente, 404 `id`; `collateral_currency` fuera
    de `CURRENCIES` o `effective_date` ausente o no ISO, 400; `effective_date` anterior al último
    evento, 409 `effective_date`; moneda igual a la vigente tras el último evento, 409
    `collateral_currency`.
    """
    if not isinstance(counterparty_id_raw, str) or not _ID.fullmatch(counterparty_id_raw):
        raise ApiError(404, "Contraparte inexistente", "id")
    row = conn.execute(
        "SELECT id, name FROM counterparties WHERE id = ?", (int(counterparty_id_raw),)
    ).fetchone()
    if row is None:
        raise ApiError(404, "Contraparte inexistente", "id")
    currency = choice(body, "collateral_currency", CURRENCIES)
    effective = iso_date(body, "effective_date")
    events = _events_by_counterparty(conn).get(row["id"], [])
    if events:
        last = events[-1]
        if effective.isoformat() < last["effective_date"]:
            raise ApiError(
                409,
                "'effective_date' no puede ser anterior al último cambio de colateral (%s)"
                % last["effective_date"],
                "effective_date",
            )
    current = events[-1]["collateral_currency"] if events else DEFAULT_CURRENCY
    if currency == current:
        raise ApiError(409, "La contraparte ya tiene colateral en %s" % currency, "collateral_currency")
    conn.execute(
        "INSERT INTO counterparty_events (counterparty_id, type, effective_date, data, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (
            row["id"],
            _EVENT_TYPE,
            effective.isoformat(),
            json.dumps({"collateral_currency": currency}),
            db.now_iso(),
        ),
    )
    events = _events_by_counterparty(conn).get(row["id"], [])
    return _public(row, _trade_counts(conn).get(row["id"], 0), events)
