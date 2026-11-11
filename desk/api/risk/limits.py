"""Límites de riesgo, uso y bitácora de excesos (corte 6, D4).

Contrato fijado por T3: constantes reales y firmas; T6 implementa las funciones.
Las escrituras no hacen commit: lo hace la ruta.
"""
import sqlite3
from typing import Any, Dict, List

SCOPES = ("counterparty", "factor", "portfolio")
METRICS = ("pv_exposure", "dv01", "fx_delta", "var")
METRICS_BY_SCOPE = {
    "counterparty": ("pv_exposure",),
    "factor": ("dv01", "fx_delta"),
    "portfolio": ("var",),
}
PORTFOLIO_KEY = "portfolio"
LIMIT_EVENT_TYPES = ("create", "change", "retire")
ALERT_PCT, BREACH_PCT = 80.0, 100.0
STATUS_OK, STATUS_ALERT, STATUS_BREACH = "ok", "alerta", "exceso"
LIMIT_ACTIVE, LIMIT_RETIRED = "activo", "baja"
VAR_LIMIT_PARAMS = {"horizon_days": 1, "confidence": 0.99}  # el límite de VaR es sobre el paramétrico a 1 día 99 %


def list_limits(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Límites (activos y de baja) por `id`. Stub de T3: lo implementa T6."""
    raise NotImplementedError("list_limits")


def create_limit(conn: sqlite3.Connection, body: Dict[str, Any]) -> Dict[str, Any]:
    """Alta de un límite con su evento `create`. Stub de T3: lo implementa T6."""
    raise NotImplementedError("create_limit")


def add_event(conn: sqlite3.Connection, limit_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Evento `change` o `retire` de un límite. Stub de T3: lo implementa T6."""
    raise NotImplementedError("add_event")


def usage(conn: sqlite3.Connection, snapshot_id: str) -> Dict[str, Any]:
    """Cuerpo de `GET /api/limits/usage`. Stub de T3: lo implementa T6."""
    raise NotImplementedError("usage")


def check(conn: sqlite3.Connection, snapshot_id: str) -> Dict[str, Any]:
    """Uso más los excesos nuevos de `POST /api/limits/check`. Stub de T3: lo implementa T6."""
    raise NotImplementedError("check")


def list_breaches(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Bitácora de excesos por `id` descendente. Stub de T3: lo implementa T6."""
    raise NotImplementedError("list_breaches")
