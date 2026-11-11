"""Biblioteca de conjuntos de escenarios: de fábrica y guardados (corte 6, D6).

Contrato fijado por T3: `BUILTIN_SETS` real; las funciones las implementa T8. Los escenarios
combinados (`type: "combined"`) los admite `scenarios._validate` cuando T8 lo extiende.
"""
import copy
import sqlite3
from typing import Any, Dict, List

from desk.api.risk import scenarios

SET_EVENT_TYPES = ("retire",)
MAX_NAME = 80


def _historical(name: str, fx_pct: float, tiie_bp: float, sofr_bp: float, summary: str) -> Dict[str, Any]:
    """Conjunto de fábrica de un solo escenario combinado (aproximación histórica)."""
    return {
        "name": name,
        "approximation": True,
        "description": "Aproximación histórica: %s a la vez" % summary,
        "scenarios": [
            {
                "name": name,
                "type": "combined",
                "shocks": [
                    {"type": "fx_spot", "pct": fx_pct},
                    {"type": "parallel", "curve": "TIIE-F", "bp": tiie_bp},
                    {"type": "parallel", "curve": "SOFR", "bp": sofr_bp},
                ],
            }
        ],
    }


# Conjuntos de fábrica: viven en código (sin id, no se dan de baja). Quien los entregue debe copiarlos.
BUILTIN_SETS = [
    {
        "name": "Por omisión",
        "approximation": False,
        "description": "Los ocho escenarios de la pantalla de Sensibilidades",
        "scenarios": copy.deepcopy(scenarios.DEFAULT_SCENARIOS),
    },
    _historical("Depreciación 2008", 35.0, 100.0, -200.0, "USDMXN +35 %, TIIE-F +100 pb y SOFR −200 pb"),
    _historical("2016 elecciones EE. UU.", 12.0, 75.0, 25.0, "USDMXN +12 %, TIIE-F +75 pb y SOFR +25 pb"),
    _historical("Marzo 2020", 25.0, -100.0, -150.0, "USDMXN +25 %, TIIE-F −100 pb y SOFR −150 pb"),
]  # type: List[Dict[str, Any]]


def list_sets(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Los de fábrica y luego los activos por `id`. Stub de T3: lo implementa T8."""
    raise NotImplementedError("list_sets")


def create_set(conn: sqlite3.Connection, body: Dict[str, Any]) -> Dict[str, Any]:
    """Alta de un conjunto guardado. Stub de T3: lo implementa T8."""
    raise NotImplementedError("create_set")


def retire_set(conn: sqlite3.Connection, set_id: int) -> Dict[str, Any]:
    """Baja lógica (evento `retire`). Stub de T3: lo implementa T8."""
    raise NotImplementedError("retire_set")


def resolve(conn: sqlite3.Connection, name: str) -> List[Dict[str, Any]]:
    """Escenarios del conjunto activo `name` (404 `set` si no existe o está de baja). Stub de T3: lo implementa T8."""
    raise NotImplementedError("resolve")
