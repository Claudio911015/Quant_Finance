"""Confirmación de liquidaciones (corte 5): registro del monto que de verdad se liquidó.

Una confirmación es un evento `transfer` con `data.kind == CONFIRMED_KIND`. Es solo registro:
no cambia estado, PV ni P&L (`settlement.settled_flows` la ignora) y no cuenta para el orden
cronológico de `events.post_event`.
"""
import sqlite3
from typing import Any, Dict

CONFIRMED_KIND = "settlement_confirmed"
CURRENCIES = ("MXN", "USD")


def is_confirmation(event: Dict[str, Any]) -> bool:
    """True si el evento es la confirmación de una liquidación."""
    return event["type"] == "transfer" and event["data"].get("kind") == CONFIRMED_KIND


def confirm_settlement(conn: sqlite3.Connection, trade_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Cuerpo 201 de `POST /api/trades/<id>/settlements` (sin commit). Lo implementa T3."""
    raise NotImplementedError("confirm_settlement: pendiente (T3)")
