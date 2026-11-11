from flask import Blueprint, jsonify, request

from desk.api import calendars
from desk.api.errors import ApiError
from desk.api.validation import ensure_finite, iso_date

bp = Blueprint("calendars", __name__)

_MAX_DAYS = 3660


@bp.get("/api/calendars/holidays")
def holidays():
    d0 = iso_date(request.args, "from")
    d1 = iso_date(request.args, "to")
    if d1 < d0:
        raise ApiError(400, "'to' no puede ser anterior a 'from'", "to")
    for name, d in (("from", d0), ("to", d1)):
        if not calendars.FIRST_YEAR <= d.year <= calendars.LAST_YEAR:
            raise ApiError(
                400,
                "'%s' debe estar entre los años %d y %d" % (name, calendars.FIRST_YEAR, calendars.LAST_YEAR),
                name,
            )
    if (d1 - d0).days > _MAX_DAYS:
        raise ApiError(400, "El rango no puede exceder %d días" % _MAX_DAYS, "to")
    body = {cal: calendars.holidays_between(cal, d0, d1) for cal in calendars.CALENDARS}
    return jsonify(
        ensure_finite({"from": d0.isoformat(), "to": d1.isoformat(), "holidays": body})
    )
