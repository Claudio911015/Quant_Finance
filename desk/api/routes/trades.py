from flask import Blueprint, jsonify, request

from desk.api import portfolio
from desk.api.db import get_conn
from desk.api.errors import ApiError
from desk.api.validation import body_object

bp = Blueprint("trades", __name__)


@bp.post("/api/trades")
def create_trade():
    body = body_object()
    conn = get_conn()
    trade = portfolio.create_trade(conn, body)
    conn.commit()
    return jsonify(trade), 201


@bp.get("/api/trades")
def list_trades():
    return jsonify({"trades": portfolio.list_trades(get_conn())})


@bp.delete("/api/trades/<trade_id>")
def delete_trade(trade_id):
    try:
        tid = int(trade_id)
    except ValueError:
        raise ApiError(404, "Operación inexistente", "id")
    conn = get_conn()
    portfolio.delete_trade(conn, tid)
    conn.commit()
    return "", 204


@bp.get("/api/portfolio/valuation")
def valuation():
    snapshot_id = request.args.get("snapshot", "").strip()
    if not snapshot_id:
        raise ApiError(400, "Falta el parámetro 'snapshot'", "snapshot")
    return jsonify(portfolio.valuation(get_conn(), snapshot_id))
