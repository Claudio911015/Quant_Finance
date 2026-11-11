from flask import Blueprint, jsonify, request

from desk.api import pnl
from desk.api.db import get_conn
from desk.api.errors import ApiError
from desk.api.validation import ensure_finite

bp = Blueprint("pnl", __name__)


@bp.get("/api/pnl")
def get_pnl():
    ids = {}
    for name in ("from", "to"):
        ids[name] = request.args.get(name, "").strip()
        if not ids[name]:
            raise ApiError(400, "Falta el parámetro '%s'" % name, name)
    return jsonify(ensure_finite(pnl.compute_pnl(get_conn(), ids["from"], ids["to"])))
