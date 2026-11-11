from flask import Blueprint, jsonify

from desk.api.db import get_conn
from desk.api.risk import dv01, scenarios, var
from desk.api.validation import body_object, ensure_finite, text

# --- corte 6: VaR histórico y conjuntos de escenarios ---
from desk.api.errors import ApiError
from desk.api.risk import hist_var, scenario_sets
from desk.api.validation import choice
# --- fin corte 6 ---

bp = Blueprint("risk", __name__, url_prefix="/api/risk")


@bp.post("/dv01")
def risk_dv01():
    snapshot_id = text(body_object(), "snapshot")
    return jsonify(ensure_finite(dv01.compute_dv01(get_conn(), snapshot_id)))


@bp.post("/scenarios")
def risk_scenarios():
    body = body_object()
    snapshot_id = text(body, "snapshot")
    # --- corte 6: correr un conjunto guardado en lugar de escenarios en línea ---
    if "set" in body:
        if "scenarios" in body:
            raise ApiError(400, "Manda 'set' o 'scenarios', no ambos", "set")
        set_name = text(body, "set")
        conn = get_conn()
        specs = scenario_sets.resolve(conn, set_name)
        result = scenarios.run_scenarios(conn, snapshot_id, {"scenarios": specs})
        return jsonify(ensure_finite({**result, "set": set_name}))
    # --- fin corte 6 ---
    return jsonify(ensure_finite(scenarios.run_scenarios(get_conn(), snapshot_id, body)))


@bp.post("/var")
def risk_var():
    body = body_object()
    snapshot_id = text(body, "snapshot")
    # --- corte 6: método histórico (sin 'method' o 'parametric' nada cambia) ---
    method = choice(body, "method", ("parametric", "historical"), default="parametric")
    if method == "historical":
        return jsonify(ensure_finite(hist_var.compute_hist_var(get_conn(), snapshot_id, body)))
    # --- fin corte 6 ---
    return jsonify(ensure_finite(var.compute_var(get_conn(), snapshot_id, body)))
