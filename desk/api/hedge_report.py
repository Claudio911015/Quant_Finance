"""Reporte de documentación y asientos de una cobertura (T6). Por ahora, firmas del contrato."""
import sqlite3
from typing import Any, Dict, Optional


def build_report(
    conn: sqlite3.Connection, hedge_id: int, snapshot_id: Optional[str] = None
) -> Dict[str, Any]:
    """Cuerpo de `GET /api/hedges/<id>/report`; la prueba prospectiva usa `snapshot_id` o el de designación."""
    raise NotImplementedError("build_report")


def report_csv(report: Dict[str, Any]) -> str:
    """Asientos del reporte como CSV `period_id,as_of,snapshot,account,debit,credit,memo`."""
    raise NotImplementedError("report_csv")
