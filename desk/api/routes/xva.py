"""Rutas del corte 9: XVA por contraparte y sus parámetros. Cada ruta valida lo que es suyo, delega en
`desk/api/risk/xva.py`, hace `commit` si escribe y responde con `ensure_finite`."""
from flask import Blueprint, jsonify, request

from desk.api.db import get_conn
from desk.api.errors import ApiError
from desk.api.risk import xva
from desk.api.validation import body_object, ensure_finite

bp = Blueprint("xva", __name__)


def _arg(name: str) -> str:
    """Parámetro de consulta obligatorio (400 con `field` si falta), como en `routes/risk_adv.py`."""
    value = request.args.get(name, "").strip()
    if not value:
        raise ApiError(400, "Falta el parámetro '%s'" % name, name)
    return value


@bp.get("/api/xva")
def xva_get():
    return jsonify(ensure_finite(xva.compute(get_conn(), _arg("snapshot"))))


@bp.get("/api/xva/params")
def xva_params_get():
    return jsonify(ensure_finite(xva.params_response(get_conn())))


@bp.put("/api/xva/params")
def xva_params_put():
    body = body_object()
    conn = get_conn()
    saved = xva.put_params(conn, body)
    conn.commit()
    return jsonify(ensure_finite(saved))
