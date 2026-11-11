from flask import Blueprint, jsonify, request

from desk.api import fixings, fixings_fetch  # corte 8: fixings_fetch
from desk.api.db import get_conn
from desk.api.errors import ApiError
from desk.api.validation import body_object, ensure_finite, iso_date

bp = Blueprint("fixings", __name__)


@bp.get("/api/fixings")
def list_fixings():
    start = iso_date(request.args, "from", required=False)
    end = iso_date(request.args, "to", required=False)
    rows = fixings.list_fixings(get_conn(), request.args.get("index"), start, end)
    return jsonify(ensure_finite({"fixings": rows}))


@bp.post("/api/fixings")
def add_fixing():
    body = body_object()
    conn = get_conn()
    fixing, created = fixings.add_fixing(conn, body)
    conn.commit()
    return jsonify({"fixing": fixing, "created": created}), (201 if created else 200)


@bp.post("/api/fixings/csv")
def import_csv():
    body = body_object()
    if not isinstance(body.get("csv"), str):
        raise ApiError(400, "'csv' debe ser texto", "csv")
    conn = get_conn()
    result = fixings.import_csv(conn, body["csv"])
    conn.commit()
    return jsonify(result)


# corte 8
@bp.post("/api/fixings/fetch")
def fetch_from_source():
    body = body_object()
    conn = get_conn()
    result = fixings_fetch.fetch_fixings(conn, body)
    conn.commit()
    return jsonify(ensure_finite(result))


@bp.get("/api/fixings/sources")
def fixing_sources():
    return jsonify(fixings_fetch.list_sources(get_conn()))
# fin corte 8
