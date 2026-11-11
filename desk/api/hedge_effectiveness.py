"""Efectividad prospectiva: términos críticos y escenarios con derivado hipotético (T4). Por ahora, firmas del contrato."""
import sqlite3
from datetime import date
from typing import Any, Dict, List


def effectiveness(conn: sqlite3.Connection, hedge_id: int, snapshot_id: str) -> Dict[str, Any]:
    """Respuesta de `GET /api/hedges/<id>/effectiveness?snapshot=<id>`."""
    raise NotImplementedError("effectiveness")


def critical_terms(rel: Dict[str, Any], trade: Dict[str, Any], on: date) -> List[Dict[str, Any]]:
    """Comparación de términos críticos instrumento contra partida cubierta, con la operación vigente a `on`."""
    raise NotImplementedError("critical_terms")
