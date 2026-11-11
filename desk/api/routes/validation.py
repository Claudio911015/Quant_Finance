import json
from pathlib import Path

from flask import Blueprint, current_app, jsonify

from desk.api.errors import ApiError
from desk.api.validation import ensure_finite
from desk.validation import common

bp = Blueprint("validation", __name__, url_prefix="/api/validation")


@bp.get("/report")
def get_report():
    path = Path(current_app.config.get("VALIDATION_REPORT") or common.REPORT_PATH)
    if not path.is_file():
        raise ApiError(404, "Aún no hay reporte de validación: genera uno con desk/validation/make_report.sh")
    report = json.loads(path.read_text(encoding="utf-8"))
    # El commit se recalcula en cada petición para avisar si la valuación cambió tras generar el reporte.
    current = common.desk_commit()
    report["current_commit"] = current
    report["commit_matches"] = None if current is None else current == report.get("desk_commit")
    return jsonify(ensure_finite(report))
