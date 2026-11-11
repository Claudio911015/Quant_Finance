"""Historia diaria de factores de riesgo para el VaR histórico (corte 6, D2).

Contrato fijado por T3: constantes reales y firmas; T5 implementa las funciones.
`seed_synthetic` es la excepción: devuelve 0 sin lanzar porque `create_app` la llama al arrancar.
"""
import sqlite3
from typing import Any, Dict, List, Mapping, Tuple

FACTORS = {"TIIE-F": "bp", "SOFR": "bp", "USDMXN": "ret"}
SOURCES = ("synthetic", "csv", "live", "fixings")
OBSERVED_PRIORITY = ("csv", "live", "fixings")  # en "observed", por (factor, fecha) gana el primero
SOURCE_LABEL = {
    "synthetic": "Sintético (semilla fija, vols y correlaciones de MX-DEMO)",
    "csv": "CSV cargado",
    "live": "FRED / MarketDataFeed",
    "fixings": "Fijaciones cargadas",
}
CSV_HEADER = "factor,date,value"
MAX_ABS = {"bp": 1000.0, "ret": 1.0}  # cota de |valor| por unidad (como var._MAX_FACTOR_VOL)
SYNTHETIC_SEED = 20261110
SYNTHETIC_DAYS = 500  # días hábiles (lun-vie) estrictamente anteriores al as_of de MX-DEMO
MAX_GAP_DAYS = 5  # al derivar: pares de observaciones a más de 5 días naturales se omiten


def seed_synthetic(conn: sqlite3.Connection) -> int:
    """Siembra la historia sintética de MX-DEMO; devuelve las filas insertadas. Stub de T3: 0."""
    return 0


def import_csv(conn: sqlite3.Connection, text: str) -> Dict[str, Any]:
    """`{"inserted", "unchanged"}` tras cargar un CSV `factor,date,value`. Stub de T3: lo implementa T5."""
    raise NotImplementedError("import_csv")


def derive(conn: sqlite3.Connection, source: str, config: Mapping[str, Any]) -> Dict[str, Any]:
    """Deriva historia de `fixings` o `live`. Stub de T3: lo implementa T5."""
    raise NotImplementedError("derive")


def summary(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Cuerpo de `GET /api/factor-history`. Stub de T3: lo implementa T5."""
    raise NotImplementedError("summary")


def window(
    conn: sqlite3.Connection, history_source: str, as_of: str, n: int
) -> Tuple[List[str], Dict[str, List[float]], Dict[str, int]]:
    """`(fechas, {factor: valores}, by_source)` de las últimas `n` fechas. Stub de T3: lo implementa T5."""
    raise NotImplementedError("window")
