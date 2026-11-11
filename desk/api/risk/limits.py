"""Límites de riesgo, uso y bitácora de excesos (corte 6, D4).

`limits`, `limit_events` y `limit_breaches` son solo de inserción: el monto vigente de un límite
sale de su último evento `create`/`change` y la baja es un evento `retire`. El uso se recalcula
con las rutas existentes (valuación, DV01 y VaR paramétrico a 1 día 99 %), una vez por petición.
Las escrituras no hacen commit: lo hace la ruta.
"""
import sqlite3
from typing import Any, Dict, List, Optional

from desk.api import market, portfolio
from desk.api.db import now_iso
from desk.api.errors import ApiError
from desk.api.risk import dv01, var
from desk.api.validation import MAX_AMOUNT, choice, number, text

SCOPES = ("counterparty", "factor", "portfolio")
METRICS = ("pv_exposure", "dv01", "fx_delta", "var")
METRICS_BY_SCOPE = {
    "counterparty": ("pv_exposure",),
    "factor": ("dv01", "fx_delta"),
    "portfolio": ("var",),
}
PORTFOLIO_KEY = "portfolio"
LIMIT_EVENT_TYPES = ("create", "change", "retire")
ALERT_PCT, BREACH_PCT = 80.0, 100.0
STATUS_OK, STATUS_ALERT, STATUS_BREACH = "ok", "alerta", "exceso"
LIMIT_ACTIVE, LIMIT_RETIRED = "activo", "baja"
VAR_LIMIT_PARAMS = {"horizon_days": 1, "confidence": 0.99}  # el límite de VaR es sobre el paramétrico a 1 día 99 %

_FX_KEY = market.PAIR  # el delta FX solo existe para USDMXN
_FX_PCT = 100.0  # `exposure_mxn` es MXN por unidad de rendimiento; el límite se mide por 1 % (÷ 100)
_PCT_DECIMALS = 9  # el porcentaje se redondea antes de comparar con los umbrales (80 y 100 exactos)


# ------------------------------------------------------------------ lectura de límites

def _event_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "type": row["type"],
        "amount": row["amount"],
        "reason": row["reason"],
        "created_at": row["created_at"],
    }


def _load(conn: sqlite3.Connection, limit_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Límites por `id` con sus eventos; `amount` es el vigente y `status` sale de los eventos."""
    where, args = ("WHERE id = ?", (limit_id,)) if limit_id is not None else ("", ())
    rows = conn.execute(
        "SELECT id, scope, key, metric, amount, created_at FROM limits %s ORDER BY id" % where, args
    ).fetchall()
    events: Dict[int, List[sqlite3.Row]] = {}
    for e in conn.execute(
        "SELECT id, limit_id, type, amount, reason, created_at FROM limit_events ORDER BY id"
    ):
        events.setdefault(e["limit_id"], []).append(e)
    out = []
    for r in rows:
        evs = events.get(r["id"], [])
        amount = r["amount"]  # monto de alta; si no hay eventos de monto, ese
        for e in evs:
            if e["type"] in ("create", "change") and e["amount"] is not None:
                amount = e["amount"]
        retired = any(e["type"] == "retire" for e in evs)
        out.append(
            {
                "id": r["id"],
                "scope": r["scope"],
                "key": r["key"],
                "metric": r["metric"],
                "amount": float(amount),
                "status": LIMIT_RETIRED if retired else LIMIT_ACTIVE,
                "created_at": r["created_at"],
                "events": [_event_dict(e) for e in evs],
            }
        )
    return out


def list_limits(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Límites (activos y de baja) por `id`."""
    return _load(conn)


# ------------------------------------------------------------------ alta y eventos

def _validated_key(conn: sqlite3.Connection, body: Dict[str, Any], scope: str, metric: str) -> str:
    if scope == "portfolio":
        if body.get("key") is None:
            return PORTFOLIO_KEY
        key = text(body, "key")
        if key != PORTFOLIO_KEY:
            raise ApiError(400, "La clave del límite de portafolio debe ser '%s'" % PORTFOLIO_KEY, "key")
        return key
    key = text(body, "key")
    if scope == "counterparty":
        if conn.execute("SELECT 1 FROM counterparties WHERE name = ?", (key,)).fetchone() is None:
            raise ApiError(400, "Contraparte inexistente: %s" % key, "key")
    elif metric == "dv01":
        if key not in market.CURVES:
            raise ApiError(
                400, "Curva desconocida: %s (válidas: %s)" % (key, ", ".join(market.CURVES)), "key"
            )
    elif key != _FX_KEY:  # fx_delta
        raise ApiError(400, "El delta de tipo de cambio solo existe para %s" % _FX_KEY, "key")
    return key


def create_limit(conn: sqlite3.Connection, body: Dict[str, Any]) -> Dict[str, Any]:
    """Alta de un límite con su evento `create`, en la misma transacción (sin commit)."""
    scope = choice(body, "scope", SCOPES)
    metric = choice(body, "metric", METRICS)
    if metric not in METRICS_BY_SCOPE[scope]:
        raise ApiError(
            400,
            "La métrica '%s' no aplica al alcance '%s' (válidas: %s)"
            % (metric, scope, ", ".join(METRICS_BY_SCOPE[scope])),
            "metric",
        )
    key = _validated_key(conn, body, scope, metric)
    amount = number(body, "amount", gt=0, le=MAX_AMOUNT)
    reason = text(body, "reason", required=False)
    for other in _load(conn):
        if (
            other["status"] == LIMIT_ACTIVE
            and (other["scope"], other["key"], other["metric"]) == (scope, key, metric)
        ):
            raise ApiError(409, "Ya hay un límite activo para %s / %s / %s" % (scope, key, metric), "key")
    now = now_iso()
    cur = conn.execute(
        "INSERT INTO limits (scope, key, metric, amount, created_at) VALUES (?, ?, ?, ?, ?)",
        (scope, key, metric, amount, now),
    )
    conn.execute(
        "INSERT INTO limit_events (limit_id, type, amount, reason, created_at) VALUES (?, 'create', ?, ?, ?)",
        (cur.lastrowid, amount, reason, now),
    )
    return _load(conn, cur.lastrowid)[0]


def add_event(conn: sqlite3.Connection, limit_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Evento `change` (nuevo monto) o `retire` (baja) de un límite (sin commit)."""
    found = _load(conn, limit_id)
    if not found:
        raise ApiError(404, "Límite inexistente", "id")
    etype = choice(body, "type", ("change", "retire"))
    amount = number(body, "amount", gt=0, le=MAX_AMOUNT) if etype == "change" else None
    reason = text(body, "reason", required=False)
    if found[0]["status"] == LIMIT_RETIRED:
        raise ApiError(409, "El límite ya está dado de baja", "id")
    conn.execute(
        "INSERT INTO limit_events (limit_id, type, amount, reason, created_at) VALUES (?, ?, ?, ?, ?)",
        (limit_id, etype, amount, reason, now_iso()),
    )
    return _load(conn, limit_id)[0]


# ------------------------------------------------------------------ uso

def _status(pct: float) -> str:
    if pct < ALERT_PCT:
        return STATUS_OK
    if pct <= BREACH_PCT:
        return STATUS_ALERT
    return STATUS_BREACH


def usage(conn: sqlite3.Connection, snapshot_id: str) -> Dict[str, Any]:
    """Cuerpo de `GET /api/limits/usage`: uso de los límites `activo` contra el snapshot.

    Cada cálculo (valuación, DV01, VaR) se hace una sola vez y solo si algún límite activo lo usa.
    """
    mkt = market.load_context(conn, snapshot_id)  # 404 `snapshot`
    active = [lim for lim in _load(conn) if lim["status"] == LIMIT_ACTIVE]
    errors: List[Dict[str, Any]] = []
    seen = set()

    def collect(items: List[Dict[str, Any]]) -> None:
        for item in items:
            if item["id"] not in seen:  # sin repetir id entre rutas
                seen.add(item["id"])
                errors.append(item)

    pv_by_cp: Optional[Dict[str, float]] = None
    if any(lim["metric"] == "pv_exposure" for lim in active):
        pv_by_cp = {}
        rows = portfolio.valuation(conn, snapshot_id)["rows"]
        collect([{"id": r["id"], "error": r["error"]} for r in rows if r["error"] is not None])
        for r in rows:
            if r["error"] is None:
                pv_by_cp[r["counterparty"]] = pv_by_cp.get(r["counterparty"], 0.0) + r["pv_mxn"]

    dv01_res = None
    if any(lim["metric"] == "dv01" for lim in active):
        dv01_res = dv01.compute_dv01(conn, snapshot_id)
        collect(dv01_res["errors"])

    var_res = None
    if any(lim["metric"] in ("fx_delta", "var") for lim in active):
        var_res = var.compute_var(conn, snapshot_id, dict(VAR_LIMIT_PARAMS))
        collect(var_res["errors"])

    rows_out = []
    for lim in active:
        metric = lim["metric"]
        if metric == "pv_exposure":
            used = max(pv_by_cp.get(lim["key"], 0.0), 0.0)
        elif metric == "dv01":
            used = abs(dv01_res["curves"][lim["key"]]["parallel_mxn"])
        elif metric == "fx_delta":
            fx = next(f for f in var_res["factors"] if f["factor"] == _FX_KEY)
            used = abs(fx["exposure_mxn"]) / _FX_PCT
        else:  # var
            used = var_res["var_mxn"]
        pct = round(used / lim["amount"] * 100.0, _PCT_DECIMALS)
        rows_out.append(
            {
                "limit_id": lim["id"],
                "scope": lim["scope"],
                "key": lim["key"],
                "metric": metric,
                "amount": lim["amount"],
                "usage": used,
                "pct": pct,
                "status": _status(pct),
            }
        )
    return {
        "snapshot": snapshot_id,
        "as_of": mkt.as_of.isoformat(),
        "thresholds": {"alert_pct": ALERT_PCT, "breach_pct": BREACH_PCT},
        "usage": rows_out,
        "errors": errors,
    }


# ------------------------------------------------------------------ excesos

_SELECT_BREACHES = (
    "SELECT b.id, b.limit_id, l.scope, l.key, l.metric, b.snapshot_id, b.as_of, b.amount, b.usage,"
    " b.pct, b.created_at FROM limit_breaches b JOIN limits l ON l.id = b.limit_id"
)


def _breach_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "limit_id": row["limit_id"],
        "scope": row["scope"],
        "key": row["key"],
        "metric": row["metric"],
        "snapshot": row["snapshot_id"],
        "as_of": row["as_of"],
        "amount": row["amount"],
        "usage": row["usage"],
        "pct": row["pct"],
        "created_at": row["created_at"],
    }


def check(conn: sqlite3.Connection, snapshot_id: str) -> Dict[str, Any]:
    """Uso más los excesos nuevos: una fila por límite en `exceso` cuya `(limit_id, as_of)` no exista."""
    result = usage(conn, snapshot_id)
    new_ids = []
    for row in result["usage"]:
        if row["status"] != STATUS_BREACH:
            continue
        exists = conn.execute(
            "SELECT 1 FROM limit_breaches WHERE limit_id = ? AND as_of = ?",
            (row["limit_id"], result["as_of"]),
        ).fetchone()
        if exists is not None:
            continue
        cur = conn.execute(
            "INSERT INTO limit_breaches (limit_id, snapshot_id, as_of, amount, usage, pct, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (row["limit_id"], snapshot_id, result["as_of"], row["amount"], row["usage"], row["pct"], now_iso()),
        )
        new_ids.append(cur.lastrowid)
    new = [
        _breach_dict(conn.execute(_SELECT_BREACHES + " WHERE b.id = ?", (i,)).fetchone()) for i in new_ids
    ]
    return dict(result, new_breaches=new)


def list_breaches(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Bitácora de excesos por `id` descendente."""
    return [_breach_dict(r) for r in conn.execute(_SELECT_BREACHES + " ORDER BY b.id DESC")]
