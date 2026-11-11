"""Medición de un periodo de cobertura y sus asientos (T3). Por ahora, firmas del contrato."""
import sqlite3
from datetime import date
from typing import Any, Dict, List

from desk.api.market import MarketContext


def close_period(conn: sqlite3.Connection, hedge_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Cierra un periodo (`POST /api/hedges/<id>/periods`): mide, asienta y devuelve el periodo público."""
    raise NotImplementedError("close_period")


def measure(
    rel: Dict[str, Any],
    trade: Dict[str, Any],
    mkt: MarketContext,
    fixings: Dict[str, Dict[date, float]],
) -> Dict[str, Any]:
    """`result` del periodo al `as_of` de `mkt`, sin escribir nada."""
    raise NotImplementedError("measure")


def journal(hedge_type: str, figures: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Asientos `{"account","debit","credit","memo"}` del periodo a partir de sus cifras."""
    raise NotImplementedError("journal")
