"""Flujos liquidados y calendario de flujos de la ficha. Se implementa en T9."""
import sqlite3
from datetime import date
from typing import Any, Dict, List, Tuple


def settled_flows(
    trade: Dict[str, Any],
    fixings: Dict[str, Dict[date, float]],
    d0: date,
    d1: date,
    fallback_spot: float,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """`(flujos, avisos)` liquidados con fecha en `(d0, d1]`."""
    raise NotImplementedError("settlement.settled_flows se implementa en T9")


def trade_flows(conn: sqlite3.Connection, trade_id: int, snapshot_id: str) -> Dict[str, Any]:
    """Cuerpo de `GET /api/trades/<id>/flows`: liquidados y proyectados, con avisos."""
    raise NotImplementedError("settlement.trade_flows se implementa en T9")
