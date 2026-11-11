"""VaR y déficit esperado históricos del portafolio (corte 6, D3).

Contrato fijado por T3: constantes reales; `compute_hist_var` lo implementa T5.
"""
import sqlite3
from typing import Any, Dict

DEFAULT_WINDOW, MIN_WINDOW, MAX_WINDOW = 250, 60, 10000
HISTORY_SOURCES = ("synthetic", "observed")


def compute_hist_var(conn: sqlite3.Connection, snapshot_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Cuerpo de `POST /api/risk/var` con `method: historical`. Stub de T3: lo implementa T5."""
    raise NotImplementedError("compute_hist_var")
