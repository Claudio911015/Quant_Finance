"""Rutas de operaciones (corte 5): ajustes, referencias, calendario de flujos, confirmaciones,
FpML y conciliación.

Las rutas solo parsean el id, validan el formato de salida, delegan en los módulos
(`ops_*`, `fpml`), hacen `commit` al final de las escrituras y arman las respuestas CSV/XML.
Toda validación de parámetros de negocio vive en los módulos.
"""
from flask import Blueprint, Response, jsonify, request

from desk.api import fpml, ops_cashflows, ops_confirm, ops_recon, ops_settings, ops_settlements, portfolio
from desk.api.db import get_conn
from desk.api.errors import ApiError
from desk.api.routes.trades import _trade_id
from desk.api.validation import body_object, choice, ensure_finite

bp = Blueprint("ops", __name__)

_FORMATS = ("json", "csv")


def _run_id(raw: str) -> int:
    """Id numérico de una conciliación; 404 `field: "id"` si no puede existir."""
    try:
        rid = int(raw)
        if abs(rid) >= 2 ** 63:  # fuera del rango de enteros de SQLite: no puede existir
            raise ValueError(raw)
    except ValueError:
        raise ApiError(404, "Conciliación inexistente", "id")
    return rid


def _format() -> str:
    """`format` de la consulta: `json` (por omisión) o `csv`; 400 `format` si es otro."""
    return choice(request.args, "format", _FORMATS, default="json")


def _csv_response(body: str, filename: str) -> Response:
    return Response(
        body,
        content_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="%s"' % filename},
    )


# --------------------------------------------------------------------------- ajustes

@bp.get("/api/settings")
def get_settings():
    return jsonify(ops_settings.get_settings(get_conn()))


@bp.put("/api/settings")
def put_settings():
    conn = get_conn()
    settings = ops_settings.put_settings(conn, body_object())
    conn.commit()
    return jsonify(settings)


# ------------------------------------------------------------- referencia del banco

@bp.get("/api/trades/<trade_id>/ref")
def get_ref(trade_id):
    conn = get_conn()
    tid = portfolio.get_trade(conn, _trade_id(trade_id))["id"]
    return jsonify({"trade_id": tid, "ref": ops_settings.get_ref(conn, tid)})


@bp.put("/api/trades/<trade_id>/ref")
def put_ref(trade_id):
    conn = get_conn()
    tid = portfolio.get_trade(conn, _trade_id(trade_id))["id"]  # 404 antes de leer el cuerpo
    result = ops_settings.put_ref(conn, tid, body_object())
    conn.commit()
    return jsonify(result)


# ------------------------------------------------------------------------ flujos

@bp.get("/api/cashflows")
def cashflows():
    fmt = _format()
    payload = ensure_finite(ops_cashflows.cashflows(get_conn(), request.args))
    if fmt == "csv":
        return _csv_response(
            ops_cashflows.cashflows_csv(payload), "flujos-%s.csv" % payload["snapshot"]
        )
    return jsonify(payload)


@bp.post("/api/trades/<trade_id>/settlements")
def confirm_settlement(trade_id):
    conn = get_conn()
    tid = portfolio.get_trade(conn, _trade_id(trade_id))["id"]  # 404 antes de leer el cuerpo
    result = ops_settlements.confirm_settlement(conn, tid, body_object())
    conn.commit()
    return jsonify(ensure_finite(result)), 201


# ------------------------------------------------------------------ confirmación

@bp.get("/api/trades/<trade_id>/confirmation")
def confirmation(trade_id):
    result = ops_confirm.confirmation(get_conn(), _trade_id(trade_id))
    return jsonify(ensure_finite(result))


# --------------------------------------------------------------------------- FpML

@bp.get("/api/trades/<trade_id>/fpml")
def export_fpml(trade_id):
    tid = _trade_id(trade_id)
    xml = fpml.export_trade(get_conn(), tid)
    return Response(
        xml,
        content_type="application/xml; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="operacion-%d.fpml.xml"' % tid},
    )


@bp.post("/api/trades/fpml")
def import_fpml():
    conn = get_conn()
    result = fpml.import_trade(conn, request.get_data())  # cuerpo XML crudo, no JSON
    conn.commit()
    return jsonify(ensure_finite(result)), 201


# ------------------------------------------------------------------- conciliación

@bp.post("/api/reconciliations")
def create_reconciliation():
    conn = get_conn()
    run = ops_recon.create_run(conn, body_object())
    conn.commit()
    return jsonify(ensure_finite(run)), 201


@bp.get("/api/reconciliations")
def list_reconciliations():
    counterparty = request.args.get("counterparty", "").strip() or None
    return jsonify(ensure_finite({"reconciliations": ops_recon.list_runs(get_conn(), counterparty)}))


@bp.get("/api/reconciliations/<run_id>")
def get_reconciliation(run_id):
    run = ops_recon.get_run(get_conn(), _run_id(run_id))
    if _format() == "csv":
        return _csv_response(ops_recon.run_csv(run), "conciliacion-%d.csv" % run["id"])
    return jsonify(ensure_finite(run))
