"""Lectura de solo lectura de la base de MarketDataFeed (SOFR y rendimientos del Tesoro).

Las rutas llegan como argumento (este módulo no lee `app.config`). En la base las tasas están en
porcentaje (4.05 = 4.05 %); aquí se devuelven en decimal. Nunca se devuelven datos parciales:
base inutilizable, tenor faltante o historia corta lanzan `ApiError(409, ...)`.
"""
import os
import sqlite3
from typing import Any, Dict, List, Tuple
from urllib.parse import quote

from desk.api.errors import ApiError

TENORS = ["1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y"]
MAX_CHANGES = 250  # cambios diarios que entran a la ventana de volatilidad
MIN_CHANGES = 60  # por debajo de esto no se mide volatilidad


def _query(db_path: Any, sql: str, params: tuple = ()) -> List[tuple]:
    """Ejecuta un SELECT con la base abierta en `mode=ro`; todo fallo de la base es 409."""
    path = str(db_path)
    if not os.path.isfile(path):
        raise ApiError(409, "Base de MarketDataFeed no encontrada: %s" % path)
    conn = None
    try:
        conn = sqlite3.connect("file:%s?mode=ro" % quote(path), uri=True)
        return conn.execute(sql, params).fetchall()
    except sqlite3.Error as e:
        raise ApiError(409, "Base de MarketDataFeed inutilizable: %s" % e)
    finally:
        if conn is not None:
            conn.close()


def latest_treasury_curve(db_path: Any) -> Dict[str, Any]:
    """Curva del Tesoro más reciente: `{"date": "YYYY-MM-DD", "yields": {tenor: decimal}}`."""
    rows = _query(db_path, "SELECT MAX(effective_date) FROM treasury_yields")
    date = rows[0][0] if rows else None
    if date is None:
        raise ApiError(409, "La base de MarketDataFeed no tiene rendimientos del Tesoro")
    found = dict(
        _query(db_path, "SELECT tenor, rate FROM treasury_yields WHERE effective_date = ?", (date,))
    )
    missing = [t for t in TENORS if t not in found]
    if missing:
        raise ApiError(
            409, "Curva del Tesoro incompleta al %s: faltan %s" % (date, ", ".join(missing))
        )
    return {"date": date, "yields": {t: found[t] / 100.0 for t in TENORS}}


def latest_sofr(db_path: Any) -> Dict[str, Any]:
    """SOFR overnight más reciente: `{"date": "YYYY-MM-DD", "rate": decimal}`."""
    rows = _query(
        db_path, "SELECT effective_date, rate FROM sofr_rates ORDER BY effective_date DESC LIMIT 1"
    )
    if not rows:
        raise ApiError(409, "La base de MarketDataFeed no tiene SOFR")
    return {"date": rows[0][0], "rate": rows[0][1] / 100.0}


def treasury_5y_history(db_path: Any) -> List[Tuple[str, float]]:
    """Últimas `MAX_CHANGES + 1` observaciones 5Y `(fecha, decimal)` en orden ascendente."""
    rows = _query(
        db_path,
        "SELECT effective_date, rate FROM treasury_yields WHERE tenor = '5Y' "
        "ORDER BY effective_date DESC LIMIT ?",
        (MAX_CHANGES + 1,),
    )
    changes = max(len(rows) - 1, 0)
    if changes < MIN_CHANGES:
        raise ApiError(
            409,
            "Historia insuficiente: %d cambios diarios de 5Y (mínimo %d)" % (changes, MIN_CHANGES),
        )
    return [(date, rate / 100.0) for date, rate in reversed(rows)]
