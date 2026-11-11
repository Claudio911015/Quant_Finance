"""Portafolio: operaciones y valuación (lo llena T10).

Stub con las firmas fijas del plan; las rutas ya delegan aquí.
"""
import sqlite3
from typing import Any, Dict, List


def list_trades(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Operaciones ordenadas por id, con notional/currency/maturity derivados."""
    raise NotImplementedError


def create_trade(conn: sqlite3.Connection, body: Dict[str, Any]) -> Dict[str, Any]:
    """Valida `product`, `counterparty` y `params`; guarda y devuelve la operación."""
    raise NotImplementedError


def delete_trade(conn: sqlite3.Connection, trade_id: int) -> None:
    """Borra la operación; 404 `field: "id"` si no existe."""
    raise NotImplementedError


def valuation(conn: sqlite3.Connection, snapshot_id: str) -> Dict[str, Any]:
    """Valuación del portafolio contra el snapshot."""
    raise NotImplementedError


def load_trades(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Operaciones con `params` ya decodificado."""
    raise NotImplementedError
