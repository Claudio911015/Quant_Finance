from flask import Blueprint, jsonify, request

from desk.api import events, lifecycle, portfolio, settlement
from desk.api.db import get_conn
from desk.api.errors import ApiError
from desk.api.validation import body_object, ensure_finite, iso_date

bp = Blueprint("trades", __name__)


def _trade_id(raw: str) -> int:
    """Id numérico de la ruta; 404 `field: "id"` si no puede existir."""
    try:
        tid = int(raw)
        if abs(tid) >= 2 ** 63:  # fuera del rango de enteros de SQLite: no puede existir
            raise ValueError(raw)
    except ValueError:
        raise ApiError(404, "Operación inexistente", "id")
    return tid


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


@bp.get("/api/trades/<trade_id>")
def get_trade(trade_id):
    trade = portfolio.get_trade(get_conn(), _trade_id(trade_id))
    return jsonify(
        {**portfolio.public_trade(trade), "events": [events.public_event(e) for e in trade["events"]]}
    )


@bp.get("/api/trades/<trade_id>/state")
def trade_state(trade_id):
    trade = portfolio.get_trade(get_conn(), _trade_id(trade_id))
    on = iso_date(request.args, "date")
    st = lifecycle.state(trade, trade["events"], on)
    return jsonify(ensure_finite({"id": trade["id"], "date": on.isoformat(), **st}))


@bp.post("/api/trades/<trade_id>/events")
def post_event(trade_id):
    conn = get_conn()
    tid = portfolio.get_trade(conn, _trade_id(trade_id))["id"]  # 404 antes de leer el cuerpo
    created = events.post_event(conn, tid, body_object())
    conn.commit()
    return jsonify({"events": [events.public_event(e) for e in created]}), 201


@bp.get("/api/trades/<trade_id>/flows")
def trade_flows(trade_id):
    conn = get_conn()
    tid = portfolio.get_trade(conn, _trade_id(trade_id))["id"]
    snapshot_id = request.args.get("snapshot", "").strip()
    if not snapshot_id:
        raise ApiError(400, "Falta el parámetro 'snapshot'", "snapshot")
    return jsonify(ensure_finite(settlement.trade_flows(conn, tid, snapshot_id)))


@bp.delete("/api/trades/<trade_id>")
def delete_trade(trade_id):
    portfolio.get_trade(get_conn(), _trade_id(trade_id))  # 404 si no existe
    raise ApiError(409, "Una operación no se borra: termínala", "id")


@bp.get("/api/portfolio/valuation")
def valuation():
    snapshot_id = request.args.get("snapshot", "").strip()
    if not snapshot_id:
        raise ApiError(400, "Falta el parámetro 'snapshot'", "snapshot")
    return jsonify(ensure_finite(portfolio.valuation(get_conn(), snapshot_id)))
