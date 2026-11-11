"""P&L explicado por cascada entre dos snapshots (corte 6, D1).

Contrato fijado por T3: aquí solo viven los pasos de la cascada; `explain_pnl` lo implementa T4.
"""
import sqlite3
from typing import Any, Dict

from desk.api import market

# "TIIE-F" primero y luego las demás curvas de `market.CURVES` en orden alfabético.
_CURVE_ORDER = ["TIIE-F"] + sorted(c for c in market.CURVES if c != "TIIE-F")

STEPS = (
    [("carry", "Paso del tiempo y liquidaciones")]
    + [("curve:%s" % c, "Tasas %s" % c) for c in _CURVE_ORDER]
    + [
        ("fx", "Tipo de cambio"),
        ("vol", "Volatilidad"),
        ("new_trades", "Operaciones nuevas"),
        ("events", "Eventos"),
        ("residual", "Residuo"),
    ]
)


def explain_pnl(conn: sqlite3.Connection, from_id: str, to_id: str) -> Dict[str, Any]:
    """Cuerpo de `GET /api/pnl/explain`. Stub de T3: lo implementa T4."""
    raise NotImplementedError("explain_pnl")
