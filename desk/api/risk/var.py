"""VaR delta-normal (lo llena T12)."""
import sqlite3
from typing import Any, Dict


def compute_var(
    conn: sqlite3.Connection, snapshot_id: str, body: Dict[str, Any]
) -> Dict[str, Any]:
    """Cuerpo de `POST /api/risk/var`; valida `horizon_days`, `confidence` y `factor_vols`."""
    raise NotImplementedError
