"""Mercado: snapshots, curvas y contexto de valuación (lo llena T7).

Stub con las firmas fijas del plan; las rutas ya delegan aquí.
"""
import sqlite3
from datetime import date
from typing import Any, Dict, List, Optional

from desk.api.qf import qfpy

CURVES = {
    "TIIE-F": {"currency": "MXN", "period_days": 28},
    "SOFR": {"currency": "USD", "period_days": 365},
}


class MarketContext:
    """Estado de mercado listo para valuar.

    Atributos: snapshot_id, as_of (date), curves (Dict[str, qfpy.YieldCurve]),
    pillars (Dict[str, List[dict]] con "label" y "days"), spot (float),
    surface (qfpy.VolSurface), hw (dict), factors (dict),
    env (qfpy.MarketEnvironment con curvas "TIIE-F" y "SOFR", spot y superficie "USDMXN").
    """

    def env_with_default(self, curve: str) -> "qfpy.MarketEnvironment":
        """`env` más la curva "default" apuntando a `curve`."""
        raise NotImplementedError

    def shifted(
        self,
        curve: Optional[str] = None,
        pillar_shifts_bp: Optional[List[float]] = None,
        parallel_bp: Optional[float] = None,
        spot_pct: float = 0.0,
    ) -> "MarketContext":
        """Copia con la curva desplazada y/o el spot × (1 + spot_pct/100)."""
        raise NotImplementedError


def load_context(conn: sqlite3.Connection, snapshot_id: str) -> MarketContext:
    """Contexto del snapshot; 404 `field: "snapshot"` si no existe."""
    raise NotImplementedError


def list_snapshots(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Resumen `{"id","label","synthetic","as_of"}` de cada snapshot."""
    raise NotImplementedError


def snapshot_payload(conn: sqlite3.Connection, snapshot_id: str) -> Dict[str, Any]:
    """Cuerpo completo de `GET /api/market/snapshots/<id>`; 404 `field: "snapshot"` si no existe."""
    raise NotImplementedError


def update_snapshot(
    conn: sqlite3.Connection, snapshot_id: str, body: Dict[str, Any]
) -> Dict[str, Any]:
    """Valida y persiste `quotes`/`spot` del cuerpo; devuelve el payload recalculado."""
    raise NotImplementedError
