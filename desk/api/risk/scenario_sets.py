"""Biblioteca de conjuntos de escenarios: de fábrica y guardados (corte 6, D6).

Los de fábrica viven en código (`BUILTIN_SETS`: sin id, no se dan de baja); los guardados, en
`scenario_sets` (solo inserción) y se dan de baja con un evento `retire` en `scenario_set_events`.
Los escenarios combinados (`type: "combined"`) los admite `scenarios._validate`. Las escrituras no
hacen commit: lo hace la ruta.
"""
import copy
import json
import sqlite3
from typing import Any, Dict, List, Optional

from desk.api.db import now_iso
from desk.api.errors import ApiError
from desk.api.risk import scenarios
from desk.api.validation import text

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


# Un conjunto guardado está activo mientras no tenga evento `retire`.
_ACTIVE = "NOT EXISTS (SELECT 1 FROM scenario_set_events e WHERE e.set_id = s.id AND e.type = 'retire')"
_COLUMNS = "s.id, s.name, s.description, s.scenarios, s.created_at"


def _builtin(spec: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": None,
        "name": spec["name"],
        "builtin": True,
        "approximation": spec["approximation"],
        "status": "activo",
        "description": spec["description"],
        "scenarios": copy.deepcopy(spec["scenarios"]),
        "created_at": None,
    }


def _saved(row: sqlite3.Row, status: str) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "builtin": False,
        "approximation": False,
        "status": status,
        "description": row["description"],
        "scenarios": json.loads(row["scenarios"]),
        "created_at": row["created_at"],
    }


def _builtin_named(name: str) -> Optional[Dict[str, Any]]:
    return next((b for b in BUILTIN_SETS if b["name"] == name), None)


def list_sets(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Los de fábrica (en el orden de `BUILTIN_SETS`) y luego los guardados activos por `id`."""
    rows = conn.execute(
        "SELECT %s FROM scenario_sets s WHERE %s ORDER BY s.id" % (_COLUMNS, _ACTIVE)
    ).fetchall()
    return [_builtin(b) for b in BUILTIN_SETS] + [_saved(r, "activo") for r in rows]


def create_set(conn: sqlite3.Connection, body: Dict[str, Any]) -> Dict[str, Any]:
    """Alta de un conjunto guardado: 400 `name`/`description`/`scenarios`, 409 `name` si el nombre ya existe."""
    name = text(body, "name")
    if len(name) > MAX_NAME:
        raise ApiError(400, "'name' no puede tener más de %d caracteres" % MAX_NAME, "name")
    description = body.get("description")
    if description is not None and not isinstance(description, str):
        raise ApiError(400, "'description' debe ser texto", "description")
    description = (description or "").strip() or None
    specs = scenarios._validate(body)  # `combined` incluido; 400 `scenarios`
    # Nombre único entre los de fábrica y los activos (comparación exacta, ya recortado); el de uno
    # dado de baja se puede reutilizar.
    taken = _builtin_named(name) is not None or conn.execute(
        "SELECT 1 FROM scenario_sets s WHERE s.name = ? AND %s" % _ACTIVE, (name,)
    ).fetchone() is not None
    if taken:
        raise ApiError(409, "Ya existe un conjunto de escenarios llamado '%s'" % name, "name")
    cur = conn.execute(
        "INSERT INTO scenario_sets (name, description, scenarios, created_at) VALUES (?, ?, ?, ?)",
        (name, description, json.dumps(specs, ensure_ascii=False), now_iso()),
    )
    return _saved(_fetch(conn, cur.lastrowid), "activo")


def _fetch(conn: sqlite3.Connection, set_id: int) -> sqlite3.Row:
    return conn.execute("SELECT %s FROM scenario_sets s WHERE s.id = ?" % _COLUMNS, (set_id,)).fetchone()


def retire_set(conn: sqlite3.Connection, set_id: int) -> Dict[str, Any]:
    """Baja lógica (evento `retire`): 404 `id` si no existe, 409 `id` si ya estaba de baja."""
    row = _fetch(conn, set_id)
    if row is None:
        raise ApiError(404, "Conjunto inexistente", "id")
    if conn.execute(
        "SELECT 1 FROM scenario_set_events WHERE set_id = ? AND type = 'retire'", (set_id,)
    ).fetchone():
        raise ApiError(409, "El conjunto '%s' ya está de baja" % row["name"], "id")
    conn.execute(
        "INSERT INTO scenario_set_events (set_id, type, created_at) VALUES (?, ?, ?)",
        (set_id, SET_EVENT_TYPES[0], now_iso()),
    )
    return _saved(row, "baja")


def resolve(conn: sqlite3.Connection, name: str) -> List[Dict[str, Any]]:
    """Escenarios del conjunto activo `name` (de fábrica o guardado); 404 `set` si no existe o está de baja."""
    builtin = _builtin_named(name)
    if builtin is not None:
        return copy.deepcopy(builtin["scenarios"])
    row = conn.execute(
        "SELECT %s FROM scenario_sets s WHERE s.name = ? AND %s ORDER BY s.id DESC LIMIT 1" % (_COLUMNS, _ACTIVE),
        (name,),
    ).fetchone()
    if row is None:
        raise ApiError(404, "Conjunto de escenarios inexistente o dado de baja: '%s'" % name, "set")
    return json.loads(row["scenarios"])
