"""DV01 por curva y pilar (lo llena T11)."""
import sqlite3
from typing import Any, Dict


def compute_dv01(conn: sqlite3.Connection, snapshot_id: str) -> Dict[str, Any]:
    """Cuerpo de `POST /api/risk/dv01`; 404 `field: "snapshot"` si no existe."""
    raise NotImplementedError
