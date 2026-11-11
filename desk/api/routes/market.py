from flask import Blueprint, jsonify

from desk.api import market
from desk.api.db import get_conn
from desk.api.validation import body_object

bp = Blueprint("market", __name__, url_prefix="/api/market")


@bp.get("/snapshots")
def snapshots():
    return jsonify({"snapshots": market.list_snapshots(get_conn())})


@bp.get("/snapshots/<snapshot_id>")
def snapshot(snapshot_id):
    return jsonify(market.snapshot_payload(get_conn(), snapshot_id))


@bp.put("/snapshots/<snapshot_id>")
def update_snapshot(snapshot_id):
    body = body_object()
    conn = get_conn()
    payload = market.update_snapshot(conn, snapshot_id, body)
    conn.commit()
    return jsonify(payload)
