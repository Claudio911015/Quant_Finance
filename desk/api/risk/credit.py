"""Exposición por contraparte (EE/PFE), CVA informativo y parámetros de crédito (corte 6, D5).

Contrato fijado por T3: constantes reales y firmas; T7 implementa las funciones. `qfxva` se importa
de forma perezosa dentro de las funciones (T7), para que el backend arranque sin él.
"""
import sqlite3
from typing import Any, Dict, List

DEFAULT_HAZARD, DEFAULT_RECOVERY = 0.01, 0.40
N_PATHS, SEED, PFE_QUANTILE = 500, 42, 0.95
COVERED_PRODUCTS = ("irs",)
CVA_NOTICE = "CVA informativo: no entra al PV ni a la contabilidad de coberturas"
ASSUMED_NOTE = "Supuesto: probabilidad de incumplimiento 1 % anual y recuperación 40 % (sin parámetros capturados)"


def list_params(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Parámetros vigentes por contraparte. Stub de T3: lo implementa T7."""
    raise NotImplementedError("list_params")


def set_params(conn: sqlite3.Connection, body: Dict[str, Any]) -> Dict[str, Any]:
    """Inserta parámetros nuevos de una contraparte. Stub de T3: lo implementa T7."""
    raise NotImplementedError("set_params")


def exposure(conn: sqlite3.Connection, snapshot_id: str) -> Dict[str, Any]:
    """Cuerpo de `GET /api/credit/exposure`. Stub de T3: lo implementa T7."""
    raise NotImplementedError("exposure")
