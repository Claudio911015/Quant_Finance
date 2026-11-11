"""P&L entre dos snapshots. Se implementa en T9."""
import sqlite3
from typing import Any, Dict


def compute_pnl(conn: sqlite3.Connection, from_id: str, to_id: str) -> Dict[str, Any]:
    """Cuerpo de `GET /api/pnl` (forma del contrato)."""
    raise NotImplementedError("pnl.compute_pnl se implementa en T9")
