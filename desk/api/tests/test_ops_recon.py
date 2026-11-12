"""Conciliación con el banco (corte 5, T6): `POST/GET /api/reconciliations`, descomposición y CSV (R5)."""
import csv
import io
import sqlite3

import pytest

from desk.api import fixings, market, ops_recon, portfolio, valuation
from desk.api.db import connect
from desk.api.tests import hedge_fixture
from desk.api.tests.conftest import insert_raw_trade
from desk.api.tests.ops_fixture import ALFA, fx_trade, irs_trade, own_pv
from desk.api.tests.original_book import original_book  # noqa: F401  (fixture)

# corte 9: la conciliación se prueba sobre el portafolio original de siete operaciones (ids 1 a 7)
pytestmark = pytest.mark.usefixtures("original_book")

BETA = "Banco Beta (sintético)"
HEADER = "trade_id,bank_pv,currency,bank_ref\n"
CSV_HEADER = (
    "section,line,trade_id,bank_ref,product,status,own_pv_mxn,bank_pv,bank_currency,bank_pv_mxn,"
    "difference_mxn,difference_rel,date_attributed,curve_bp,fx_spot,terms_flag,reason"
)


def _csv(*rows):
    """CSV con el encabezado estándar; cada fila es `(trade_id, bank_pv, currency, bank_ref)` (`None` = vacío)."""
    lines = [HEADER.strip()]
    for r in rows:
        trade_id, pv, currency, ref = (list(r) + [None] * 4)[:4]
        lines.append("%s,%r,%s,%s" % ("" if trade_id is None else trade_id, pv, currency or "MXN", ref or ""))
    return "\n".join(lines) + "\n"


def _post(client, csv_text, counterparty=ALFA, **extra):
    body = {"snapshot": "MX-DEMO", "counterparty": counterparty, "csv": csv_text}
    body.update(extra)
    return client.post("/api/reconciliations", json=body)


def _run(client, csv_text, counterparty=ALFA, **extra):
    r = _post(client, csv_text, counterparty, **extra)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _count(app, table="reconciliations"):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        return conn.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
    finally:
        conn.close()


def _row(run, trade_id):
    return next(r for r in run["rows"] if r["trade_id"] == trade_id)


def _spot(app):
    conn = connect(app.config["DESK_DB"])
    try:
        return market.load_context(conn, "MX-DEMO").spot
    finally:
        conn.close()


def _off_market(client):
    """`irs` payer a 3 % contra una curva de ~7 %: PV muy lejos de cero."""
    return irs_trade(client, fixed_rate=0.03, notional=100e6, periods=52)


def _dv01(app, trade_id):
    return own_pv(app, trade_id, mkt_fn=lambda m: m.shifted(curve="TIIE-F", parallel_bp=1)) - own_pv(app, trade_id)


# ------------------------------------------------------------------------ (a) exacto

def test_exact_own_pv_is_conciliada_for_every_trade(app, client):
    off = _off_market(client)
    ids = [1, 4, 7, off["id"]]
    run = _run(client, _csv(*[(i, own_pv(app, i)) for i in ids]))
    assert [r["trade_id"] for r in run["rows"]] == ids
    assert {r["status"] for r in run["rows"]} == {"conciliada"}
    assert run["own_only"] == [] and run["bank_only"] == []
    assert run["summary"]["matched"] == 4 and run["summary"]["conciliada"] == 4
    assert run["summary"]["explicable"] == run["summary"]["revisar"] == 0
    assert run["summary"]["difference_mxn"] == pytest.approx(0.0, abs=1e-6)
    assert all(r["terms_flag"] is False and r["error"] is None for r in run["rows"])
    # La descomposición se calcula también en las conciliadas.
    assert _row(run, 1)["decomposition"]["curve"]["bp"] == pytest.approx(0.0, abs=1e-6)


def test_row_shape_and_roles(app, client):
    run = _run(client, _csv((1, own_pv(app, 1) + 100.0, "MXN", "X-1")))
    assert run["snapshot"] == "MX-DEMO" and run["as_of"] == "2026-11-10"
    assert run["counterparty"] == ALFA and run["tolerance"] == ops_recon.DEFAULT_TOLERANCE
    assert run["disclaimer"] == ops_recon.DISCLAIMER
    r = run["rows"][0]
    assert set(r) == {  # jsonify ordena las claves: se compara el conjunto
        "line", "trade_id", "bank_ref", "product", "currency", "notional_mxn", "own_pv_mxn", "bank_pv",
        "bank_currency", "bank_pv_mxn", "difference_mxn", "difference_rel", "status", "decomposition",
        "terms_flag", "error",
    }
    assert r["line"] == 2 and r["product"] == "irs" and r["currency"] == "MXN" and r["bank_ref"] == "X-1"
    assert r["notional_mxn"] == 500e6
    assert r["difference_mxn"] == pytest.approx(-100.0, abs=1e-6)  # propio − banco
    assert r["difference_rel"] == pytest.approx(-100.0 / 500e6)
    dec = r["decomposition"]
    assert set(dec) == {"date", "curve", "fx"} and dec["fx"] is None
    assert dec["curve"]["curve"] == "TIIE-F"
    assert dec["date"]["prev_date"] == "2026-11-09" and dec["date"]["next_date"] == "2026-11-11"


# ------------------------------------------------------------------- (b) curva y tipo de cambio

def test_curve_shift_is_explicable_and_recovers_the_basis_points(app, client):
    bank = own_pv(app, 1, mkt_fn=lambda m: m.shifted(curve="TIIE-F", parallel_bp=5))
    run = _run(client, _csv((1, bank)))
    r = run["rows"][0]
    assert r["status"] == "explicable" and r["terms_flag"] is False
    assert r["decomposition"]["curve"]["curve"] == "TIIE-F"
    assert r["decomposition"]["curve"]["bp"] == pytest.approx(5.0, abs=0.1)
    assert r["decomposition"]["fx"] is None


def test_spot_shift_is_explicable_and_recovers_the_percentage(app, client):
    bank = own_pv(app, 4, mkt_fn=lambda m: m.shifted(spot_pct=0.5))
    run = _run(client, _csv((4, bank)))
    r = run["rows"][0]
    assert r["status"] == "explicable" and r["terms_flag"] is False
    assert r["decomposition"]["fx"]["pct"] == pytest.approx(0.5, abs=0.01)
    assert r["decomposition"]["fx"]["spot"] == pytest.approx(_spot(app) * 1.005, rel=1e-4)
    assert r["decomposition"]["curve"] is None


def test_fx_option_spot_shift_also_converges(app, client):
    bank = own_pv(app, 6, mkt_fn=lambda m: m.shifted(spot_pct=-0.4))
    r = _run(client, _csv((6, bank)), counterparty="Banco Gamma (sintético)")["rows"][0]
    assert r["status"] == "explicable"
    assert r["decomposition"]["fx"]["pct"] == pytest.approx(-0.4, abs=0.01)


# ----------------------------------------------------------------------------- (c) fecha

def test_pv_one_business_day_later_is_attributed_to_the_date(app, client):
    off = _off_market(client)
    tid = off["id"]
    assert abs(own_pv(app, tid)) > 30 * abs(_dv01(app, tid))  # precondición: bien fuera de mercado
    bank = own_pv(app, tid, mkt_fn=lambda m: ops_recon.context_at(m, ops_recon.business_day(m.as_of, 1)))
    assert bank != pytest.approx(own_pv(app, tid), abs=1e-6)
    # Tolerancia mínima: el cambio de un día debe superarla para que el estado no sea `conciliada`.
    r = _run(client, _csv((tid, bank)), tolerance=1e-6)["rows"][0]
    assert r["decomposition"]["date"]["attributed"] is True
    assert r["decomposition"]["date"]["pv_next"] == pytest.approx(bank)
    assert r["status"] == "explicable"


def test_a_day_when_the_trade_is_not_alive_does_not_widen_the_date_range(app, client):
    # Operación pactada en el `as_of`: el día hábil anterior aún no existe y su PV es 0 por definición, no
    # por mercado. Si entrara al rango, cualquier PV del banco entre 0 y el propio sería "atribuible a la fecha".
    tid = _off_market(client)["id"]
    own = own_pv(app, tid)
    run = _run(client, _csv((tid, own * 0.5)))
    r = run["rows"][0]
    date = r["decomposition"]["date"]
    assert date["pv_prev"] == 0.0 and date["attributed"] is False
    assert abs(r["decomposition"]["curve"]["bp"]) > ops_recon.EXPLAIN_CURVE_BP
    assert r["status"] == "revisar"


# -------------------------------------------------------------------------- (d) nocional

def test_notional_times_one_and_a_half_is_revisar_with_terms_flag(app, client):
    off = _off_market(client)
    tid = off["id"]
    conn = connect(app.config["DESK_DB"])
    try:
        trade = portfolio.get_trade(conn, tid)
        mkt = market.load_context(conn, "MX-DEMO")
        bigger = dict(trade, params=dict(trade["params"], notional=trade["params"]["notional"] * 1.5))
        bank = valuation.value_trade(bigger, mkt, fixings.load_all(conn))["pv_mxn"]
    finally:
        conn.close()
    r = _run(client, _csv((tid, bank)))["rows"][0]
    assert r["status"] == "revisar" and r["terms_flag"] is True
    assert r["decomposition"]["date"]["attributed"] is False
    bp = r["decomposition"]["curve"]["bp"]
    assert bp is None or abs(bp) > ops_recon.TERMS_CURVE_BP


def test_unreachable_bank_pv_leaves_the_factors_null_and_flags_the_terms(app, client):
    r = _run(client, _csv((1, 9e12)))["rows"][0]
    assert r["status"] == "revisar" and r["terms_flag"] is True
    assert r["decomposition"]["curve"] == {"curve": "TIIE-F", "bp": None}
    r = _run(client, _csv((4, 9e12)))["rows"][0]
    assert r["decomposition"]["fx"] == {"spot": None, "pct": None} and r["terms_flag"] is True


def test_a_matured_trade_has_zero_slope_and_is_not_an_own_only(app, client):
    hedge_fixture.roll(client, "MX-DEMO", "D1", 400)  # op. 4 (forward a 120 días) ya venció
    r = client.post(
        "/api/reconciliations", json={"snapshot": "D1", "counterparty": ALFA, "csv": _csv((4, 500000.0))}
    )
    assert r.status_code == 201, r.get_json()
    run = r.get_json()
    row = run["rows"][0]
    assert row["own_pv_mxn"] == 0.0 and row["status"] == "revisar"
    assert row["decomposition"]["fx"] == {"spot": None, "pct": None}
    assert 4 not in [o["trade_id"] for o in run["own_only"]]


# ---------------------------------------------------------------- (e) emparejamiento y huérfanas

def test_pairing_by_id_and_by_registered_reference(app, client):
    assert client.put("/api/trades/4/ref", json={"ref": "BA-2026-0042"}).status_code == 200
    csv_text = _csv(
        (1, own_pv(app, 1)),
        (999, 1000.0),
        (2, 1000.0),
        (None, 2500.0, "MXN", "NO-EXISTE"),
        (None, own_pv(app, 4), "MXN", "BA-2026-0042"),
    )
    run = _run(client, csv_text)
    assert [r["trade_id"] for r in run["rows"]] == [1, 4]
    by_ref = _row(run, 4)
    assert by_ref["bank_ref"] == "BA-2026-0042" and by_ref["line"] == 6 and by_ref["status"] == "conciliada"
    reasons = {b["line"]: (b["trade_id"], b["bank_ref"], b["reason"]) for b in run["bank_only"]}
    assert reasons == {
        3: (999, None, "Operación inexistente"),
        4: (2, None, "La operación es de otra contraparte"),
        5: (None, "NO-EXISTE", "Referencia no encontrada"),
    }
    assert run["bank_only"][0]["bank_pv"] == 1000.0 and run["bank_only"][0]["currency"] == "MXN"
    assert run["summary"]["bank_only"] == 3 and run["summary"]["matched"] == 2


def test_trade_id_wins_over_the_reference(app, client):
    client.put("/api/trades/4/ref", json={"ref": "BA-9"})
    run = _run(client, _csv((1, own_pv(app, 1), "MXN", "BA-9")))
    assert [r["trade_id"] for r in run["rows"]] == [1] and run["rows"][0]["bank_ref"] == "BA-9"


def test_reference_of_another_counterparty_is_not_found(app, client):
    client.put("/api/trades/2/ref", json={"ref": "BB-1"})  # Banco Beta
    run = _run(client, _csv((None, 10.0, "MXN", "BB-1")))
    assert run["rows"] == [] and run["bank_only"][0]["reason"] == "Referencia no encontrada"


def test_trades_the_csv_omits_are_own_only_but_only_if_alive(app, client):
    r = client.post(
        "/api/trades/7/events",
        json={"type": "termination", "event_date": "2026-11-10", "data": {"amount": 0.0}},
    )
    assert r.status_code == 201, r.get_json()
    run = _run(client, _csv((1, own_pv(app, 1))))
    assert [o["trade_id"] for o in run["own_only"]] == [4]  # la 7 está terminada
    assert run["own_only"][0]["product"] == "fx_forward"
    assert run["own_only"][0]["own_pv_mxn"] == pytest.approx(own_pv(app, 4))
    assert run["summary"]["own_only"] == 1


def test_omitting_trade_7_lists_it_as_own_only(app, client):
    run = _run(client, _csv((1, own_pv(app, 1)), (4, own_pv(app, 4))))
    assert run["own_only"] == [
        {"trade_id": 7, "product": "cap_floor", "own_pv_mxn": pytest.approx(own_pv(app, 7))}
    ]


# --------------------------------------------------------------------------- USD y errores de valuación

def test_usd_bank_pv_is_converted_with_the_snapshot_spot(app, client):
    spot = _spot(app)
    run = _run(client, _csv((3, own_pv(app, 3) / spot, "USD")), counterparty="Banco Gamma (sintético)")
    r = run["rows"][0]
    assert r["bank_currency"] == "USD" and r["currency"] == "USD"
    assert r["bank_pv_mxn"] == pytest.approx(r["bank_pv"] * spot)
    assert r["bank_pv_mxn"] == pytest.approx(own_pv(app, 3), rel=1e-12)
    assert r["status"] == "conciliada"
    assert r["notional_mxn"] == pytest.approx(20e6 * spot)
    assert run["summary"]["bank_pv_mxn"] == pytest.approx(r["bank_pv_mxn"])


def test_unvaluable_trade_is_a_revisar_row_with_error_and_no_decomposition(app, client):
    good = insert_raw_trade(app, "irs", '{"curve": "TIIE-F"}')  # le faltan parámetros
    bad = insert_raw_trade(app, "irs", "no es json")
    run = _run(client, _csv((good, 100.0), (bad, 100.0)), counterparty="Raw")
    for r in run["rows"]:
        assert r["status"] == "revisar" and r["error"]
        assert r["decomposition"] is None and r["terms_flag"] is False
        assert r["own_pv_mxn"] is None and r["difference_mxn"] is None and r["difference_rel"] is None
        assert r["bank_pv_mxn"] == 100.0
    assert run["summary"]["matched"] == 2 and run["summary"]["revisar"] == 2
    assert run["summary"]["own_pv_mxn"] == run["summary"]["bank_pv_mxn"] == run["summary"]["difference_mxn"] == 0
    # También en `own_only`: se lista con PV nulo en vez de tumbar la corrida.
    run = _run(client, _csv((good, 100.0)), counterparty="Raw")
    assert run["own_only"] == [{"trade_id": bad, "product": "irs", "own_pv_mxn": None}]


# ----------------------------------------------------------------------------- validación

def test_tolerance_out_of_range_is_400(app, client):
    for bad in (0.5, -0.1, "x", True):
        r = _post(client, _csv((1, 1.0)), tolerance=bad)
        assert r.status_code == 400 and r.get_json()["field"] == "tolerance", bad
    assert _count(app) == 0


def test_tolerance_is_stored_and_changes_the_status(app, client):
    bank = own_pv(app, 1) + 1000.0  # 1000 MXN sobre 500e6
    assert _run(client, _csv((1, bank)))["rows"][0]["status"] == "conciliada"  # 0.0001 × 500e6 = 50 000
    run = _run(client, _csv((1, bank)), tolerance=0)
    assert run["tolerance"] == 0 and run["rows"][0]["status"] != "conciliada"


@pytest.mark.parametrize("body, status, field", [
    ({"counterparty": ALFA, "csv": "x"}, 400, "snapshot"),
    ({"snapshot": "", "counterparty": ALFA, "csv": "x"}, 400, "snapshot"),
    ({"snapshot": "NOPE", "counterparty": ALFA, "csv": "x"}, 404, "snapshot"),
    ({"snapshot": "MX-DEMO", "csv": "x"}, 400, "counterparty"),
    ({"snapshot": "MX-DEMO", "counterparty": "Nadie, S.A.", "csv": "x"}, 404, "counterparty"),
    ({"snapshot": "MX-DEMO", "counterparty": ALFA}, 400, "csv"),
    ({"snapshot": "MX-DEMO", "counterparty": ALFA, "csv": "  \n"}, 400, "csv"),
    ({"snapshot": "MX-DEMO", "counterparty": ALFA, "csv": 5}, 400, "csv"),
])
def test_body_validation_order_and_fields(app, client, body, status, field):
    r = client.post("/api/reconciliations", json=body)
    assert r.status_code == status and r.get_json()["field"] == field, r.get_json()
    assert _count(app) == 0


def test_validation_order_snapshot_before_counterparty_before_tolerance_before_csv(app, client):
    r = client.post("/api/reconciliations", json={"snapshot": "NOPE", "counterparty": "Nadie", "tolerance": 9})
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"
    r = client.post("/api/reconciliations", json={"snapshot": "MX-DEMO", "counterparty": "Nadie", "tolerance": 9})
    assert r.status_code == 404 and r.get_json()["field"] == "counterparty"
    r = client.post("/api/reconciliations", json={"snapshot": "MX-DEMO", "counterparty": ALFA, "tolerance": 9})
    assert r.status_code == 400 and r.get_json()["field"] == "tolerance"


def test_body_must_be_a_json_object(client):
    assert client.post("/api/reconciliations", json=[1]).status_code == 400
    assert client.post("/api/reconciliations", data="no json").status_code == 400


@pytest.mark.parametrize("csv_text, expected", [
    ("trade_id,currency\n1,MXN\n", "Falta la columna 'bank_pv'"),
    ("bank_pv,currency\n1,MXN\n", "Falta la columna 'trade_id'"),
    ("trade_id,bank_pv\n1,5\n", "Falta la columna 'currency'"),
    (HEADER, "no trae filas"),
    (HEADER + "\n,,,\n", "no trae filas"),
    (HEADER + "1,abc,MXN,\n", "Línea 2: bank_pv"),
    (HEADER + "1,nan,MXN,\n", "Línea 2: bank_pv"),
    (HEADER + "1,inf,MXN,\n", "Línea 2: bank_pv"),
    (HEADER + "1,1_0,MXN,\n", "Línea 2: bank_pv"),
    (HEADER + "1,,MXN,\n", "Línea 2: bank_pv"),
    (HEADER + "1,2e13,MXN,\n", "Línea 2: bank_pv"),
    (HEADER + "1,5,EUR,\n", "Línea 2: currency"),
    (HEADER + "1,5,,\n", "Línea 2: currency"),
    (HEADER + "1.5,5,MXN,\n", "Línea 2: trade_id"),
    (HEADER + "-1,5,MXN,\n", "Línea 2: trade_id"),
    (HEADER + "abc,5,MXN,\n", "Línea 2: trade_id"),
    (HEADER + ",5,MXN,\n", "Línea 2: falta trade_id o bank_ref"),
    (HEADER + "1,5,MXN,\n1,6,MXN,\n", "Línea 3: la operación 1 ya viene en la línea 2"),
    (HEADER + "1,5,MXN,\n\n\n1,6,USD,\n", "Línea 5: la operación 1 ya viene en la línea 2"),
    (HEADER + "1,5,MXN,\n2,6,MXN,\n7,x,MXN,\n", "Línea 4: bank_pv"),
    ("currency,trade_id,bank_pv\n\nMXN,1,abc\n", "Línea 3: bank_pv"),
])
def test_csv_errors_are_400_csv_with_the_line_and_write_nothing(app, client, csv_text, expected):
    r = _post(client, csv_text)
    assert r.status_code == 400 and r.get_json()["field"] == "csv", r.get_json()
    assert expected in r.get_json()["error"]
    assert _count(app) == 0 and _count(app, "reconciliation_rows") == 0


def test_same_trade_by_id_and_by_resolved_reference_is_a_duplicate(app, client):
    client.put("/api/trades/1/ref", json={"ref": "R-1"})
    r = _post(client, _csv((1, 5.0), (None, 6.0, "MXN", "R-1")))
    assert r.status_code == 400 and "Línea 3: la operación 1 ya viene en la línea 2" in r.get_json()["error"]


def test_too_many_rows_is_400(app, client, monkeypatch):
    monkeypatch.setattr(ops_recon, "MAX_CSV_ROWS", 2)
    assert _post(client, _csv((1, 5.0), (2, 5.0))).status_code == 201
    r = _post(client, _csv((1, 5.0), (2, 5.0), (3, 5.0)))
    assert r.status_code == 400 and r.get_json()["field"] == "csv" and "pasa de 2" in r.get_json()["error"]


def test_csv_is_lenient_with_order_blank_lines_spaces_and_missing_optional_column(app, client):
    text = " currency , trade_id,bank_pv\n\n MXN ,1, %r \n,,\nUSD,4,%r\n" % (
        own_pv(app, 1), own_pv(app, 4) / _spot(app)
    )
    run = _run(client, text)
    assert [(r["trade_id"], r["line"], r["status"], r["bank_ref"]) for r in run["rows"]] == [
        (1, 3, "conciliada", None), (4, 5, "conciliada", None),
    ]


# ------------------------------------------------------------------------- persistencia

def test_get_returns_exactly_what_post_returned_and_the_csv_is_stored_raw(app, client):
    text = _csv((1, own_pv(app, 1) + 123.0), (999, 5.0), (None, 7.0, "MXN", "X"))
    run = _run(client, text)
    r = client.get("/api/reconciliations/%d" % run["id"])
    assert r.status_code == 200 and r.get_json() == run
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        stored = conn.execute("SELECT csv, snapshot_id, as_of FROM reconciliations").fetchall()
        kinds = conn.execute("SELECT kind, trade_id FROM reconciliation_rows ORDER BY id").fetchall()
    finally:
        conn.close()
    assert stored == [(text, "MX-DEMO", "2026-11-10")]
    assert kinds == [("matched", 1), ("bank_only", 999), ("bank_only", None), ("own_only", 4), ("own_only", 7)]


def test_list_runs_newest_first_with_counterparty_filter(app, client):
    first = _run(client, _csv((1, 1.0)))
    second = _run(client, _csv((2, 1.0)), counterparty=BETA)
    third = _run(client, _csv((1, 2.0)), tolerance=0.01)
    listing = client.get("/api/reconciliations").get_json()["reconciliations"]
    assert [x["id"] for x in listing] == [third["id"], second["id"], first["id"]]
    head = listing[0]
    assert set(head) == {"id", "snapshot", "as_of", "counterparty", "tolerance", "created_at", "summary"}
    assert head["tolerance"] == 0.01 and head["summary"] == third["summary"] and head["counterparty"] == ALFA
    only_beta = client.get("/api/reconciliations?counterparty=" + BETA).get_json()["reconciliations"]
    assert [x["id"] for x in only_beta] == [second["id"]]
    assert client.get("/api/reconciliations?counterparty=Nadie").get_json() == {"reconciliations": []}
    assert client.get("/api/reconciliations").status_code == 200


def test_empty_listing(client):
    assert client.get("/api/reconciliations").get_json() == {"reconciliations": []}


@pytest.mark.parametrize("sql", [
    "UPDATE reconciliations SET tolerance = 1",
    "DELETE FROM reconciliations",
    "UPDATE reconciliation_rows SET kind = 'matched'",
    "DELETE FROM reconciliation_rows",
])
def test_both_tables_are_insert_only(app, client, sql):
    _run(client, _csv((1, 1.0)))
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute(sql)
    finally:
        conn.close()


def test_get_unknown_or_malformed_id_is_404_and_format_is_validated(client):
    for raw in ("999", "abc", "0", "-1", "1.5"):
        r = client.get("/api/reconciliations/" + raw)
        assert r.status_code == 404 and r.get_json()["field"] == "id", raw
    run = _run(client, _csv((1, 1.0)))
    r = client.get("/api/reconciliations/%d?format=xml" % run["id"])
    assert r.status_code == 400 and r.get_json()["field"] == "format"
    assert client.get("/api/reconciliations/%d?format=json" % run["id"]).get_json() == run


def test_a_4xx_or_a_failure_while_computing_leaves_nothing_stored(app, client, monkeypatch):
    def boom(*a, **k):
        raise KeyError("boom")

    monkeypatch.setattr(ops_recon, "reconcile_trade", boom)
    r = client.post(
        "/api/reconciliations", json={"snapshot": "MX-DEMO", "counterparty": ALFA, "csv": _csv((1, 1.0))}
    )
    assert r.status_code == 500
    assert _count(app) == 0 and _count(app, "reconciliation_rows") == 0


# --------------------------------------------------------------------------------- CSV

def test_csv_download_has_the_exact_header_and_one_row_per_element(app, client):
    client.put("/api/trades/4/ref", json={"ref": "BA-4"})
    bank = own_pv(app, 1, mkt_fn=lambda m: m.shifted(curve="TIIE-F", parallel_bp=5))
    run = _run(client, _csv((1, bank), (None, own_pv(app, 4), "MXN", "BA-4"), (999, 12.5), (None, 3.0, "USD", "ZZ")))
    r = client.get("/api/reconciliations/%d?format=csv" % run["id"])
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "text/csv; charset=utf-8"
    assert r.headers["Content-Disposition"] == 'attachment; filename="conciliacion-%d.csv"' % run["id"]
    lines = r.get_data(as_text=True).splitlines()
    assert lines[0] == CSV_HEADER == ",".join(ops_recon.CSV_COLUMNS)
    rows = list(csv.DictReader(io.StringIO(r.get_data(as_text=True))))
    assert [x["section"] for x in rows] == ["conciliacion", "conciliacion", "solo_banco", "solo_banco", "solo_propia"]
    assert len(rows) == len(run["rows"]) + len(run["bank_only"]) + len(run["own_only"])

    first = rows[0]
    assert first["line"] == "2" and first["trade_id"] == "1" and first["product"] == "irs"
    assert first["status"] == "explicable" and first["bank_ref"] == ""
    assert first["own_pv_mxn"] == "%.2f" % run["rows"][0]["own_pv_mxn"]
    assert first["bank_pv"] == "%.2f" % bank and first["bank_currency"] == "MXN"
    assert first["difference_rel"] == "%.10f" % run["rows"][0]["difference_rel"]
    assert first["curve_bp"] == "%.4f" % run["rows"][0]["decomposition"]["curve"]["bp"]
    assert first["fx_spot"] == "" and first["terms_flag"] == "no" and first["reason"] == ""
    assert first["date_attributed"] in ("si", "no")

    second = rows[1]
    assert second["trade_id"] == "4" and second["bank_ref"] == "BA-4" and second["curve_bp"] == ""
    assert second["fx_spot"] == "%.6f" % run["rows"][1]["decomposition"]["fx"]["spot"]

    gone, unknown = rows[2], rows[3]
    assert (gone["line"], gone["trade_id"], gone["reason"]) == ("4", "999", "Operación inexistente")
    assert gone["bank_pv"] == "12.50" and gone["bank_currency"] == "MXN"
    assert gone["product"] == gone["status"] == gone["own_pv_mxn"] == gone["terms_flag"] == ""
    assert (unknown["trade_id"], unknown["bank_ref"], unknown["bank_currency"]) == ("", "ZZ", "USD")

    own = rows[4]
    assert (own["line"], own["trade_id"], own["product"]) == ("", "7", "cap_floor")
    assert own["own_pv_mxn"] == "%.2f" % run["own_only"][0]["own_pv_mxn"]
    assert own["bank_pv"] == own["reason"] == ""


def test_csv_of_an_error_row_carries_the_message_in_reason(app, client):
    tid = insert_raw_trade(app, "irs", "no es json")
    run = _run(client, _csv((tid, 100.0)), counterparty="Raw")
    rows = list(csv.DictReader(io.StringIO(ops_recon.run_csv(run))))
    assert rows[0]["section"] == "conciliacion" and rows[0]["status"] == "revisar"
    assert rows[0]["reason"] == run["rows"][0]["error"] != ""
    assert rows[0]["own_pv_mxn"] == rows[0]["curve_bp"] == rows[0]["date_attributed"] == ""
    assert rows[0]["terms_flag"] == "no"


# --------------------------------------------------------------------------- utilidades

def test_business_day_skips_weekends():
    from datetime import date

    assert ops_recon.business_day(date(2026, 11, 13), 1) == date(2026, 11, 16)  # viernes → lunes
    assert ops_recon.business_day(date(2026, 11, 16), -1) == date(2026, 11, 13)  # lunes → viernes
    assert ops_recon.business_day(date(2026, 11, 14), 1) == date(2026, 11, 16)  # sábado → lunes
    assert ops_recon.business_day(date(2026, 11, 10), 2) == date(2026, 11, 12)


def test_reconcile_trade_directly_returns_the_row_without_line_or_bank_fields(app):
    conn = connect(app.config["DESK_DB"])
    try:
        trade = portfolio.get_trade(conn, 1)
        mkt = market.load_context(conn, "MX-DEMO")
        fx = fixings.load_all(conn)
        own = valuation.value_trade(trade, mkt, fx)["pv_mxn"]
        row = ops_recon.reconcile_trade(trade, own, mkt, fx, ops_recon.DEFAULT_TOLERANCE)
    finally:
        conn.close()
    assert set(row) == {
        "trade_id", "product", "currency", "notional_mxn", "own_pv_mxn", "difference_mxn", "difference_rel",
        "status", "decomposition", "terms_flag", "error",
    }
    assert row["status"] == "conciliada" and row["difference_mxn"] == 0.0
