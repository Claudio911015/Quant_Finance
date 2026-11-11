from typing import Optional

from flask import Blueprint, Response, jsonify, request

from desk.api import hedge_effectiveness, hedge_measure, hedge_report, hedges
from desk.api.db import get_conn
from desk.api.errors import ApiError
from desk.api.validation import body_object, ensure_finite

bp = Blueprint("hedges", __name__)


def _hedge_id(raw: str) -> int:
    """Id numérico de la ruta; 404 `field: "id"` si no puede existir."""
    try:
        hid = int(raw)
        if abs(hid) >= 2 ** 63:  # fuera del rango de enteros de SQLite: no puede existir
            raise ValueError(raw)
    except ValueError:
        raise ApiError(404, "Cobertura inexistente", "id")
    return hid


def _snapshot_arg(required: bool) -> Optional[str]:
    snapshot_id = request.args.get("snapshot", "").strip()
    if not snapshot_id:
        if required:
            raise ApiError(400, "Falta el parámetro 'snapshot'", "snapshot")
        return None
    return snapshot_id


@bp.post("/api/hedges")
def create_hedge():
    conn = get_conn()
    detail = hedges.create_hedge(conn, body_object())
    conn.commit()
    return jsonify(ensure_finite(detail)), 201


@bp.get("/api/hedges")
def list_hedges():
    raw = request.args.get("trade_id")
    trade_id = None
    if raw is not None:
        try:
            trade_id = int(raw)
            if abs(trade_id) >= 2 ** 63:
                raise ValueError(raw)
        except ValueError:
            raise ApiError(400, "'trade_id' debe ser un entero", "trade_id")
    rels = hedges.load_relationships(get_conn(), trade_id)
    return jsonify(ensure_finite({"hedges": [hedges.public_summary(r) for r in rels]}))


@bp.get("/api/hedges/<hedge_id>")
def get_hedge(hedge_id):
    rel = hedges.load_relationship(get_conn(), _hedge_id(hedge_id))
    return jsonify(ensure_finite(hedges.public_relationship(rel)))


@bp.post("/api/hedges/<hedge_id>/periods")
def close_period(hedge_id):
    hid = _hedge_id(hedge_id)
    conn = get_conn()
    period = hedge_measure.close_period(conn, hid, body_object())
    conn.commit()
    return jsonify(ensure_finite(period)), 201


@bp.post("/api/hedges/<hedge_id>/dedesignate")
def dedesignate(hedge_id):
    hid = _hedge_id(hedge_id)
    conn = get_conn()
    detail = hedges.dedesignate(conn, hid, body_object())
    conn.commit()
    return jsonify(ensure_finite(detail)), 201


@bp.get("/api/hedges/<hedge_id>/effectiveness")
def effectiveness(hedge_id):
    hid = _hedge_id(hedge_id)
    snapshot_id = _snapshot_arg(required=True)
    return jsonify(ensure_finite(hedge_effectiveness.effectiveness(get_conn(), hid, snapshot_id)))


@bp.get("/api/hedges/<hedge_id>/report")
def report(hedge_id):
    hid = _hedge_id(hedge_id)
    fmt = request.args.get("format", "json")
    if fmt not in ("json", "csv"):
        raise ApiError(400, "'format' debe ser uno de: json, csv", "format")
    built = ensure_finite(hedge_report.build_report(get_conn(), hid, _snapshot_arg(required=False)))
    if fmt == "json":
        return jsonify(built)
    resp = Response(hedge_report.report_csv(built), mimetype="text/csv")
    resp.headers["Content-Disposition"] = 'attachment; filename="cobertura-%d-asientos.csv"' % hid
    return resp
