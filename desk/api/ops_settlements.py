"""Confirmación de liquidaciones (corte 5): registro del monto que de verdad se liquidó.

Una confirmación es un evento `transfer` con `data.kind == CONFIRMED_KIND`. Es solo registro:
no cambia estado, PV ni P&L (`settlement.settled_flows` la ignora) y no cuenta para el orden
cronológico de `events.post_event`.
"""
import sqlite3
from datetime import timedelta
from typing import Any, Dict

from desk.api import events, fixings, market, portfolio, settlement
from desk.api.errors import ApiError
from desk.api.validation import MAX_AMOUNT, choice, iso_date, number, text

CONFIRMED_KIND = "settlement_confirmed"
CURRENCIES = ("MXN", "USD")
_CONFIRMABLE = ("coupon", "settlement")  # un `transfer` de terminación o ejercicio no se confirma


def is_confirmation(event: Dict[str, Any]) -> bool:
    """True si el evento es la confirmación de una liquidación."""
    return event["type"] == "transfer" and event["data"].get("kind") == CONFIRMED_KIND


def _snapshot_id(conn: sqlite3.Connection, body: Dict[str, Any]) -> str:
    """`snapshot` del cuerpo o, si falta, el de mayor `as_of` (empate: el de mayor `id`)."""
    given = text(body, "snapshot", required=False)
    if given is not None:
        return given
    snapshots = market.list_snapshots(conn)
    if not snapshots:
        raise ApiError(404, "No hay snapshots de mercado", "snapshot")
    return max(snapshots, key=lambda s: (s["as_of"], s["id"]))["id"]


def confirm_settlement(conn: sqlite3.Connection, trade_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Cuerpo 201 de `POST /api/trades/<id>/settlements` (sin commit).

    Registra el monto que el banco liquidó de verdad en un flujo ya derivado (`coupon` o
    `settlement`). No cambia PV ni P&L; `data.computed_amount` guarda lo calculado al confirmar.

    @param body `{"date", "amount", "currency", "snapshot"?}`; sin `snapshot`, el de mayor `as_of`.
    @raise ApiError 404 (`id`, `snapshot`), 400 (`date`, `amount`, `currency`) o 409 (`date`: el flujo
        aún no ocurre, no existe o ya está confirmado; `currency`: no es la del flujo).
    """
    trade = portfolio.get_trade(conn, trade_id)
    day = iso_date(body, "date")
    amount = number(body, "amount", ge=-MAX_AMOUNT, le=MAX_AMOUNT)
    currency = choice(body, "currency", CURRENCIES)
    mkt = market.load_context(conn, _snapshot_id(conn, body))
    if day > mkt.as_of:
        raise ApiError(
            409, "El flujo del %s aún no ocurre al %s" % (day.isoformat(), mkt.as_of.isoformat()), "date"
        )
    flows, _ = settlement.settled_flows(
        trade, fixings.load_all(conn), trade["trade_date"] - timedelta(days=1), mkt.as_of, mkt.spot, mkt
    )
    flow = next((f for f in flows if f["date"] == day.isoformat() and f["kind"] in _CONFIRMABLE), None)
    if flow is None:
        raise ApiError(409, "No hay flujo derivado el %s" % day.isoformat(), "date")
    if currency != flow["currency"]:
        raise ApiError(
            409,
            "El flujo del %s es en %s, no en %s" % (day.isoformat(), flow["currency"], currency),
            "currency",
        )
    # Se recorren los eventos (no `ops_cashflows.confirmations`): ese módulo importa a este.
    if any(is_confirmation(e) and e["event_date"] == day for e in trade["events"]):
        raise ApiError(409, "Ese flujo ya está confirmado", "date")
    event = events.insert_event(
        conn,
        trade_id,
        "transfer",
        day,
        {
            "kind": CONFIRMED_KIND,
            "amount": amount,
            "currency": currency,
            "flow_kind": flow["kind"],
            "computed_amount": flow["amount"],
        },
    )
    return {
        "event": events.public_event(event),
        "flow": {
            "date": flow["date"],
            "kind": flow["kind"],
            "amount": flow["amount"],
            "currency": flow["currency"],
        },
        "difference": amount - flow["amount"],
    }
