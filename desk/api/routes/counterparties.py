from flask import Blueprint, jsonify

from desk.api import collateral
from desk.api.db import get_conn
from desk.api.validation import body_object, ensure_finite

bp = Blueprint("counterparties", __name__)


@bp.get("/api/counterparties")
def list_counterparties():
    return jsonify(ensure_finite({"counterparties": collateral.list_counterparties(get_conn())}))


@bp.put("/api/counterparties/<counterparty_id>")
def change_collateral(counterparty_id):
    body = body_object()
    conn = get_conn()
    updated = collateral.change_collateral(conn, counterparty_id, body)
    conn.commit()
    return jsonify(ensure_finite(updated))
