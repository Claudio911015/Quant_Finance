"""Curvas de crédito por CDS (corte 9, R10a y R10c): tabla `credit_curves`, siembra sintética, lectura y alta.

Cada entidad (`"propia"` o el nombre de una contraparte) guarda cotizaciones de CDS (plazo en años y spread
decimal) y una recuperación. La intensidad de incumplimiento por tramos sale del bootstrap de C++
(`qfxva.bootstrap_cds_curve`) contra la curva TIIE-F del snapshot; aquí no hay fórmulas: Python valida,
persiste y da forma. `credit_curves` es solo de inserción: cambiar una curva es insertar otra fila y la vigente
es la de mayor `id` por entidad. Los datos sembrados son inventados (`SOURCE`), no cotizaciones de mercado.

`qfxva` se importa dentro de las funciones, después de `qfpy` (ambos registran tipos C++ compartidos), para que
el backend arranque aunque el módulo no esté compilado. Las escrituras no hacen commit: lo hace la ruta.
"""
import json
import re
import sqlite3
from typing import Any, Dict, List

from desk.api import market
from desk.api.db import now_iso
from desk.api.errors import ApiError
from desk.api.seed_market import SNAPSHOT_ID
from desk.api.seed_trades import _ALFA, _BETA, _GAMMA
from desk.api.validation import finite_number, number, text

OWN = "propia"
DISCOUNT_CURVE = "TIIE-F"
GRID_YEARS = 10
MAX_QUOTES, MAX_TENOR_YEARS, MAX_SPREAD = 12, 30, 0.5
SYNTHETIC = "synthetic"
SOURCE = {"kind": SYNTHETIC, "label": "Sintética (inventada para demostración)"}
SEED_KEY = "seed.credit_curves_v1"
SEED_RECOVERY = 0.40
SEED_TENORS = (1, 2, 3, 5, 7, 10)
# Spreads en puntos base por plazo de SEED_TENORS. El orden de inserción fija los ids: Alfa 1, Beta 2, Gamma 3, propia 4.
SEED = (
    (_ALFA, (60, 70, 80, 95, 105, 120)),
    (_BETA, (150, 180, 210, 250, 275, 300)),
    (_GAMMA, (95, 97, 98, 100, 100, 101)),
    (OWN, (70, 80, 90, 105, 115, 125)),
)

_NEGATIVE_HAZARD = re.compile(r"quote at (\S+?)y implies a negative hazard rate")


def _qfxva() -> Any:
    from desk.api.qf import qfpy  # noqa: F401  (debe cargarse antes que qfxva)
    import qfxva

    return qfxva


# ------------------------------------------------------------------ siembra y lectura de filas

def seed_synthetic(conn: sqlite3.Connection) -> None:
    """Siembra una vez las cuatro curvas sintéticas (idempotente con `settings["seed.credit_curves_v1"]`)."""
    if conn.execute("SELECT 1 FROM settings WHERE key = ?", (SEED_KEY,)).fetchone():
        return
    now = now_iso()
    for entity, spreads_pb in SEED:
        quotes = [{"tenor_years": t, "spread": pb / 1e4} for t, pb in zip(SEED_TENORS, spreads_pb)]
        conn.execute(
            "INSERT INTO credit_curves (entity, as_of, recovery, quotes, source, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (entity, now[:10], SEED_RECOVERY, json.dumps(quotes), SYNTHETIC, now),
        )
    conn.execute("INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)", (SEED_KEY, "1", now))


def _row(r: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": r["id"],
        "entity": r["entity"],
        "as_of": r["as_of"],
        "recovery": float(r["recovery"]),
        "quotes": json.loads(r["quotes"]),
        "source": r["source"],
        "created_at": r["created_at"],
    }


def _history(conn: sqlite3.Connection) -> Dict[str, List[Dict[str, Any]]]:
    """Todas las filas por entidad, de la más nueva a la más vieja."""
    out = {}  # type: Dict[str, List[Dict[str, Any]]]
    for r in conn.execute(
        "SELECT id, entity, as_of, recovery, quotes, source, created_at FROM credit_curves ORDER BY id DESC"
    ):
        out.setdefault(r["entity"], []).append(_row(r))
    return out


def current(conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
    """Fila vigente (mayor `id`) por entidad: `{id, entity, as_of, recovery, quotes, source, created_at}`."""
    return {entity: rows[0] for entity, rows in _history(conn).items()}


# ------------------------------------------------------------------ curva

def build_curve(qfxva: Any, row: Dict[str, Any], mkt: Any) -> Any:
    """`qfxva.PiecewiseHazardCurve` de la fila, ajustada contra la TIIE-F del snapshot (`ValueError` si no cuadra)."""
    quotes = [qfxva.CdsQuote(float(q["tenor_years"]), float(q["spread"])) for q in row["quotes"]]
    return qfxva.bootstrap_cds_curve(quotes, row["recovery"], mkt.curves[DISCOUNT_CURVE])


def _years(raw: str) -> str:
    try:
        return "%g" % float(raw)
    except ValueError:
        return raw


def _bootstrap_message(exc: Exception) -> str:
    found = _NEGATIVE_HAZARD.search(str(exc))
    if found:
        return (
            "Las cotizaciones implican una intensidad de incumplimiento negativa en el tramo de %s años"
            % _years(found.group(1))
        )
    return "No se pudo ajustar la curva con estas cotizaciones: %s" % exc


def _element(
    qfxva: Any, entity: str, label: str, kind: str, rows: List[Dict[str, Any]], mkt: Any
) -> Dict[str, Any]:
    """Elemento de `curves`. Sin filas: campos de curva en `null` y `quotes: []`. Con error de bootstrap: sin
    `hazards` ni `grid`. `hazards` usa los plazos de las cotizaciones (el vértice interno de C++ es la última fecha
    de pago del CDS: igual para años enteros)."""
    out = {
        "entity": entity, "label": label, "kind": kind, "id": None, "as_of": None, "recovery": None,
        "quotes": [], "history": [], "error": None,
    }  # type: Dict[str, Any]
    if not rows:
        return out
    cur = rows[0]
    out.update(
        id=cur["id"], as_of=cur["as_of"], recovery=cur["recovery"], quotes=cur["quotes"],
        history=[{"id": r["id"], "as_of": r["as_of"], "created_at": r["created_at"]} for r in rows],
    )
    try:
        curve = build_curve(qfxva, cur, mkt)
    except ValueError as exc:
        out["error"] = _bootstrap_message(exc)
        return out
    tenors = [q["tenor_years"] for q in cur["quotes"]]
    out["hazards"] = [
        {"from_years": lo, "to_years": hi, "hazard": h}
        for lo, hi, h in zip([0] + tenors[:-1], tenors, curve.hazards())
    ]
    grid = []  # type: List[Dict[str, float]]
    previous = 1.0
    for year in range(1, GRID_YEARS + 1):
        survival = curve.survival_probability(float(year))
        grid.append(
            {"year": year, "survival": survival, "cumulative_pd": 1.0 - survival, "marginal_pd": previous - survival}
        )
        previous = survival
    out["grid"] = grid
    return out


def _entities(conn: sqlite3.Connection) -> List[Any]:
    """`(entidad, rótulo, tipo)`: `propia` primero y luego todas las contrapartes por nombre."""
    out = [(OWN, "Propia (el desk)", "own")]
    out.extend((r["name"], r["name"], "counterparty") for r in conn.execute("SELECT name FROM counterparties ORDER BY name"))
    return out


def list_curves(conn: sqlite3.Connection, snapshot_id: str) -> Dict[str, Any]:
    """Contrato de `GET /api/credit/curves`. 404 `field: "snapshot"` si el snapshot no existe."""
    mkt = market.load_context(conn, snapshot_id)
    qfxva = _qfxva()
    history = _history(conn)
    return {
        "snapshot": mkt.snapshot_id,
        "as_of": mkt.as_of.isoformat(),
        "discount_curve": DISCOUNT_CURVE,
        "source": dict(SOURCE),
        "curves": [
            _element(qfxva, entity, label, kind, history.get(entity, []), mkt)
            for entity, label, kind in _entities(conn)
        ],
    }


# ------------------------------------------------------------------ alta

def _validated_quotes(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_QUOTES:
        raise ApiError(400, "'quotes' debe ser una lista de 1 a %d cotizaciones" % MAX_QUOTES, "quotes")
    out = []  # type: List[Dict[str, Any]]
    previous = 0.0
    for i, q in enumerate(raw, 1):
        if not isinstance(q, dict):
            raise ApiError(400, "Cotización %d: debe ser un objeto con 'tenor_years' y 'spread'" % i, "quotes")
        tenor, spread = q.get("tenor_years"), q.get("spread")
        if not finite_number(tenor) or not 0 < tenor <= MAX_TENOR_YEARS:
            raise ApiError(
                400, "Cotización %d: 'tenor_years' debe ser un número mayor que 0 y hasta %d años" % (i, MAX_TENOR_YEARS), "quotes"
            )
        if tenor <= previous:
            raise ApiError(400, "Cotización %d: los plazos deben ir en orden estrictamente creciente" % i, "quotes")
        if not finite_number(spread) or not 0 < spread <= MAX_SPREAD:
            raise ApiError(
                400, "Cotización %d: 'spread' debe ser un número decimal mayor que 0 y hasta %s" % (i, MAX_SPREAD), "quotes"
            )
        previous = tenor
        out.append({"tenor_years": tenor, "spread": spread})
    return out


def put_curve(conn: sqlite3.Connection, entity: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Valida, ajusta contra la TIIE-F del snapshot (omisión `MX-DEMO`), inserta y devuelve el elemento de `curves`.

    Orden de errores: entidad inexistente (404 `entity`), `recovery`, `quotes`, snapshot inexistente (404), y el
    bootstrap (400 `quotes`). Sin commit.
    """
    known = {e: (label, kind) for e, label, kind in _entities(conn)}
    if entity not in known:
        raise ApiError(404, "Entidad inexistente: %s" % entity, "entity")
    recovery = number(body, "recovery", ge=0, lt=1)
    quotes = _validated_quotes(body.get("quotes"))
    mkt = market.load_context(conn, text(body, "snapshot", required=False) or SNAPSHOT_ID)
    qfxva = _qfxva()
    candidate = {"quotes": quotes, "recovery": recovery}
    try:
        build_curve(qfxva, candidate, mkt)
    except ValueError as exc:
        raise ApiError(400, _bootstrap_message(exc), "quotes")
    now = now_iso()
    conn.execute(
        "INSERT INTO credit_curves (entity, as_of, recovery, quotes, source, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (entity, now[:10], recovery, json.dumps(quotes), SYNTHETIC, now),
    )
    label, kind = known[entity]
    return _element(qfxva, entity, label, kind, _history(conn).get(entity, []), mkt)
