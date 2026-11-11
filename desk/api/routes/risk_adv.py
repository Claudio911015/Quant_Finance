"""Rutas del corte 6 (riesgo avanzado): P&L explicado, historia de factores, límites, crédito y
conjuntos de escenarios. Cada ruta valida lo que es suyo (parámetros de consulta, ids, texto del
CSV), delega en `desk/api/risk/*`, hace `commit` si escribe y responde con `ensure_finite`.
Los módulos que aún no existen responden 501 (`NotImplementedError`).
"""
from flask import Blueprint, current_app, jsonify, request

from desk.api.db import get_conn
from desk.api.errors import ApiError
from desk.api.risk import credit, explain, factor_history, limits, scenario_sets
from desk.api.validation import body_object, choice, ensure_finite

bp = Blueprint("risk_adv", __name__)


def _arg(name: str) -> str:
    """Parámetro de consulta obligatorio (400 con `field` si falta), como en `routes/pnl.py`."""
    value = request.args.get(name, "").strip()
    if not value:
        raise ApiError(400, "Falta el parámetro '%s'" % name, name)
    return value


def _int_id(raw: str, what: str) -> int:
    """Id numérico de la ruta; 404 `field: "id"` si no puede existir (patrón de `routes/trades.py`)."""
    try:
        value = int(raw)
        if abs(value) >= 2 ** 63:  # fuera del rango de enteros de SQLite: no puede existir
            raise ValueError(raw)
    except ValueError:
        raise ApiError(404, "%s inexistente" % what, "id")
    return value


# ------------------------------------------------------------------ P&L explicado

@bp.get("/api/pnl/explain")
def pnl_explain():
    from_id, to_id = _arg("from"), _arg("to")
    return jsonify(ensure_finite(explain.explain_pnl(get_conn(), from_id, to_id)))


# ------------------------------------------------------------------ historia de factores

@bp.get("/api/factor-history")
def factor_history_summary():
    return jsonify(ensure_finite(factor_history.summary(get_conn())))


@bp.post("/api/factor-history/csv")
def factor_history_csv():
    body = body_object()
    if not isinstance(body.get("csv"), str):
        raise ApiError(400, "'csv' debe ser texto", "csv")
    conn = get_conn()
    result = factor_history.import_csv(conn, body["csv"])
    conn.commit()
    return jsonify(ensure_finite(result))


@bp.post("/api/factor-history/derive")
def factor_history_derive():
    body = body_object()
    source = choice(body, "source", ("fixings", "live"))
    conn = get_conn()
    result = factor_history.derive(conn, source, current_app.config)
    conn.commit()
    return jsonify(ensure_finite(result))


# ------------------------------------------------------------------ límites

@bp.get("/api/limits")
def limits_list():
    return jsonify(ensure_finite({"limits": limits.list_limits(get_conn())}))


@bp.post("/api/limits")
def limits_create():
    body = body_object()
    conn = get_conn()
    created = limits.create_limit(conn, body)
    conn.commit()
    return jsonify(ensure_finite(created)), 201


@bp.post("/api/limits/<limit_id>/events")
def limits_event(limit_id):
    lid = _int_id(limit_id, "Límite")
    body = body_object()
    conn = get_conn()
    updated = limits.add_event(conn, lid, body)
    conn.commit()
    return jsonify(ensure_finite(updated)), 201


@bp.get("/api/limits/usage")
def limits_usage():
    return jsonify(ensure_finite(limits.usage(get_conn(), _arg("snapshot"))))


@bp.post("/api/limits/check")
def limits_check():
    snapshot_id = _arg("snapshot")
    conn = get_conn()
    result = limits.check(conn, snapshot_id)
    conn.commit()
    return jsonify(ensure_finite(result))


@bp.get("/api/limits/breaches")
def limits_breaches():
    return jsonify(ensure_finite({"breaches": limits.list_breaches(get_conn())}))


# ------------------------------------------------------------------ crédito

@bp.get("/api/credit/params")
def credit_params():
    return jsonify(ensure_finite({"params": credit.list_params(get_conn())}))


@bp.post("/api/credit/params")
def credit_set_params():
    body = body_object()
    conn = get_conn()
    saved = credit.set_params(conn, body)
    conn.commit()
    return jsonify(ensure_finite(saved)), 201


@bp.get("/api/credit/exposure")
def credit_exposure():
    return jsonify(ensure_finite(credit.exposure(get_conn(), _arg("snapshot"))))


# ------------------------------------------------------------------ conjuntos de escenarios

@bp.get("/api/scenario-sets")
def scenario_sets_list():
    return jsonify(ensure_finite({"sets": scenario_sets.list_sets(get_conn())}))


@bp.post("/api/scenario-sets")
def scenario_sets_create():
    body = body_object()
    conn = get_conn()
    created = scenario_sets.create_set(conn, body)
    conn.commit()
    return jsonify(ensure_finite(created)), 201


@bp.post("/api/scenario-sets/<set_id>/retire")
def scenario_sets_retire(set_id):
    sid = _int_id(set_id, "Conjunto")
    conn = get_conn()
    retired = scenario_sets.retire_set(conn, sid)
    conn.commit()
    return jsonify(ensure_finite(retired))
