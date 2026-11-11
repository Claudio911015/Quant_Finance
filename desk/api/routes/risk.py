from flask import Blueprint, jsonify

from desk.api.db import get_conn
from desk.api.risk import dv01, scenarios, var
from desk.api.validation import body_object, text

bp = Blueprint("risk", __name__, url_prefix="/api/risk")


@bp.post("/dv01")
def risk_dv01():
    snapshot_id = text(body_object(), "snapshot")
    return jsonify(dv01.compute_dv01(get_conn(), snapshot_id))


@bp.post("/scenarios")
def risk_scenarios():
    body = body_object()
    snapshot_id = text(body, "snapshot")
    return jsonify(scenarios.run_scenarios(get_conn(), snapshot_id, body))


@bp.post("/var")
def risk_var():
    body = body_object()
    snapshot_id = text(body, "snapshot")
    return jsonify(var.compute_var(get_conn(), snapshot_id, body))
