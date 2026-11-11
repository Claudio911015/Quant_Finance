"""Escenarios de choque paralelo, steepener y spot (los llena T11)."""
import sqlite3
from typing import Any, Dict


def run_scenarios(
    conn: sqlite3.Connection, snapshot_id: str, body: Dict[str, Any]
) -> Dict[str, Any]:
    """Cuerpo de `POST /api/risk/scenarios`; valida `body["scenarios"]` (400 `field: "scenarios"`)."""
    raise NotImplementedError
