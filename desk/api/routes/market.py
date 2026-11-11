from flask import Blueprint, current_app, jsonify

from desk.api import market, refresh
from desk.api.db import get_conn
from desk.api.validation import body_object, ensure_finite

bp = Blueprint("market", __name__, url_prefix="/api/market")


@bp.get("/snapshots")
def snapshots():
    return jsonify({"snapshots": market.list_snapshots(get_conn())})


@bp.get("/snapshots/<snapshot_id>")
def snapshot(snapshot_id):
    return jsonify(market.snapshot_payload(get_conn(), snapshot_id))


@bp.put("/snapshots/<snapshot_id>")
def update_snapshot(snapshot_id):
    conn = get_conn()
    # MKT-LIVE nunca se edita: su 409 (o el 404 si no existe) sale antes de mirar el cuerpo.
    body = {} if snapshot_id == market.LIVE_ID else body_object()
    payload = market.update_snapshot(conn, snapshot_id, body)
    conn.commit()
    return jsonify(payload)


@bp.post("/<snapshot_id>/roll")
def roll_snapshot(snapshot_id):
    conn = get_conn()
    payload = market.roll_snapshot(conn, snapshot_id, body_object())
    conn.commit()
    return jsonify(payload), 201


@bp.post("/refresh")
def refresh_market():
    return jsonify(ensure_finite(refresh.run_refresh(get_conn(), current_app.config)))
