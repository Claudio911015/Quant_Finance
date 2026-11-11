"""Calendario de flujos del portafolio (corte 5): liquidados, confirmados y proyectados."""
import sqlite3
from datetime import date
from typing import Any, Dict

from desk.api import ops_settlements

FLOW_STATUSES = ("settled", "confirmed", "projected")
CSV_COLUMNS = ("date", "trade_id", "counterparty", "product", "kind", "status", "currency",
               "amount", "amount_mxn", "confirmed_amount", "difference")


def confirmations(trade: Dict[str, Any]) -> Dict[date, Dict[str, Any]]:
    """Fecha → `data` de la confirmación de liquidación de la operación en esa fecha.

    Si hubiera dos en la misma fecha (la ruta de T3 lo impide) vale la última insertada.
    """
    return {
        e["event_date"]: e["data"] for e in trade["events"] if ops_settlements.is_confirmation(e)
    }


def cashflows(conn: sqlite3.Connection, args: Any) -> Dict[str, Any]:
    """Cuerpo de `GET /api/cashflows`; `args` es `request.args`. Lo implementa T2."""
    raise NotImplementedError("cashflows: pendiente (T2)")


def cashflows_csv(payload: Dict[str, Any]) -> str:
    """Texto CSV del cuerpo de `cashflows` (encabezado `CSV_COLUMNS`). Lo implementa T2."""
    raise NotImplementedError("cashflows_csv: pendiente (T2)")
