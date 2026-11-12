"""Corte 5, T1: esquema, ajustes, referencias, exclusión de confirmaciones y registro de rutas."""
import sqlite3
from datetime import date

import pytest

from desk.api import market
from desk.api.app import create_app
from desk.api.db import connect
from desk.api.tests.hedge_fixture import roll
from desk.api.tests.ops_fixture import confirm_raw, own_pv
from desk.api.tests.original_book import drop_xva_trades

AS_OF = date(2026, 11, 10)
DEFAULT_NAME = "Empresa sin nombre (configurar en la confirmación)"
OPS_TABLES = ("settings", "trade_refs", "reconciliations", "reconciliation_rows")


def _sql(app, sql, params=()):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def _insert_run(app):
    """Una corrida y una fila insertadas por SQL; devuelve el id de la corrida."""
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        cur = conn.execute(
            "INSERT INTO reconciliations (snapshot_id, as_of, counterparty, tolerance, csv, summary, created_at)"
            " VALUES ('MX-DEMO', '2026-11-10', 'Banco Alfa (sintético)', 0.0001, 'x', '{}', 'ahora')"
        )
        conn.execute(
            "INSERT INTO reconciliation_rows (reconciliation_id, kind, trade_id, result)"
            " VALUES (?, 'matched', 1, '{}')",
            (cur.lastrowid,),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ------------------------------------------------------------------ solo inserción

@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE reconciliations SET tolerance = 0.5",
        "DELETE FROM reconciliations",
        "UPDATE reconciliation_rows SET kind = 'bank_only'",
        "DELETE FROM reconciliation_rows",
    ],
)
def test_reconciliation_tables_are_insert_only(app, sql):
    _insert_run(app)
    with pytest.raises(sqlite3.DatabaseError, match="solo de inserción"):
        _sql(app, sql)


def test_reconciliation_rows_survive_a_rejected_change(app):
    run_id = _insert_run(app)
    with pytest.raises(sqlite3.DatabaseError):
        _sql(app, "DELETE FROM reconciliations")
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        assert conn.execute("SELECT COUNT(*) FROM reconciliations WHERE id = ?", (run_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM reconciliation_rows").fetchone()[0] == 1
    finally:
        conn.close()


def test_settings_and_refs_are_editable_configuration(app):
    _sql(app, "INSERT INTO settings (key, value, updated_at) VALUES ('company_name', 'A', 'x')")
    _sql(app, "UPDATE settings SET value = 'B'")
    _sql(app, "INSERT INTO trade_refs (trade_id, ref, updated_at) VALUES (1, 'R', 'x')")
    _sql(app, "UPDATE trade_refs SET ref = 'S'")
    _sql(app, "DELETE FROM trade_refs")
    _sql(app, "DELETE FROM settings")


# ------------------------------------------------------- bases existentes sin las tablas

def test_existing_database_without_the_new_tables_recovers_them(tmp_path):
    path = tmp_path / "old.db"
    app = create_app(db_path=path)
    drop_xva_trades(app)  # una base anterior al corte 9: solo las 7 originales
    conn = sqlite3.connect(str(path))
    try:
        before = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        assert before == 7
        for table in ("reconciliation_rows", "reconciliations", "trade_refs", "settings"):
            conn.execute("DROP TABLE %s" % table)  # el DROP arrastra sus disparadores
        conn.commit()
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
        assert not names & set(OPS_TABLES)
        assert not [n for n in names if n.startswith("reconciliation")]
    finally:
        conn.close()
    app2 = create_app(db_path=path)  # el arranque recrea lo que falta
    conn = sqlite3.connect(str(path))
    try:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
        assert set(OPS_TABLES) <= names
        assert {
            "reconciliations_no_update", "reconciliations_no_delete",
            "reconciliation_rows_no_update", "reconciliation_rows_no_delete",
        } <= names
        # no resembró las 7; el arranque solo añade las 9 del corte 9 (borrar `settings` borró su marca)
        assert conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == before + 9
    finally:
        conn.close()
    assert app2.test_client().get("/api/settings").get_json() == {"company_name": DEFAULT_NAME}
    _insert_run(app2)
    with pytest.raises(sqlite3.DatabaseError):
        _sql(app2, "DELETE FROM reconciliation_rows")


def test_second_startup_on_the_same_database_is_idempotent(tmp_path):
    path = tmp_path / "twice.db"
    create_app(db_path=path)
    create_app(db_path=path)


# ------------------------------------------------------------------------- ajustes

def test_settings_default(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert r.get_json() == {"company_name": DEFAULT_NAME}


def test_settings_put_trims_and_persists(client):
    r = client.put("/api/settings", json={"company_name": "  Tesorería X  "})
    assert r.status_code == 200
    assert r.get_json() == {"company_name": "Tesorería X"}
    assert client.get("/api/settings").get_json() == {"company_name": "Tesorería X"}
    client.put("/api/settings", json={"company_name": "Otra, S.A."})  # reemplaza, no duplica
    assert client.get("/api/settings").get_json() == {"company_name": "Otra, S.A."}


def test_settings_empty_body_changes_nothing(client):
    client.put("/api/settings", json={"company_name": "Tesorería X"})
    r = client.put("/api/settings", json={})
    assert r.status_code == 200
    assert r.get_json() == {"company_name": "Tesorería X"}


def test_settings_unknown_key_is_400_with_that_key_and_writes_nothing(client):
    r = client.put("/api/settings", json={"company_name": "Nueva", "foo": 1})
    assert r.status_code == 400
    assert r.get_json()["field"] == "foo"
    assert client.get("/api/settings").get_json() == {"company_name": DEFAULT_NAME}


def test_settings_company_name_limits(client):
    assert client.put("/api/settings", json={"company_name": "x" * 200}).status_code == 200
    r = client.put("/api/settings", json={"company_name": "x" * 201})
    assert r.status_code == 400 and r.get_json()["field"] == "company_name"
    r = client.put("/api/settings", json={"company_name": "x" * 195 + "      "})  # recortado: cabe
    assert r.status_code == 200
    for bad in ("   ", 5, ["a"]):
        r = client.put("/api/settings", json={"company_name": bad})
        assert r.status_code == 400 and r.get_json()["field"] == "company_name"


def test_settings_body_must_be_an_object(client):
    assert client.put("/api/settings", json=[1]).status_code == 400


# ----------------------------------------------------------------------- referencias

def test_ref_defaults_to_null_and_round_trips(client):
    assert client.get("/api/trades/1/ref").get_json() == {"trade_id": 1, "ref": None}
    r = client.put("/api/trades/1/ref", json={"ref": "BA-2026-0042"})
    assert r.status_code == 200
    assert r.get_json() == {"trade_id": 1, "ref": "BA-2026-0042"}
    assert client.get("/api/trades/1/ref").get_json() == {"trade_id": 1, "ref": "BA-2026-0042"}
    assert client.put("/api/trades/1/ref", json={"ref": "BA-2026-0042"}).status_code == 200  # misma operación


def test_ref_is_unique_per_counterparty_not_global(client):
    client.put("/api/trades/1/ref", json={"ref": "BA-1"})
    r = client.put("/api/trades/4/ref", json={"ref": "BA-1"})  # 4 también es Banco Alfa
    assert r.status_code == 409 and r.get_json()["field"] == "ref"
    assert client.get("/api/trades/4/ref").get_json()["ref"] is None
    r = client.put("/api/trades/2/ref", json={"ref": "BA-1"})  # 2 es Banco Beta
    assert r.status_code == 200 and r.get_json()["ref"] == "BA-1"


def test_ref_blank_or_null_deletes_and_frees_it(client):
    client.put("/api/trades/1/ref", json={"ref": "BA-1"})
    assert client.put("/api/trades/1/ref", json={"ref": ""}).get_json() == {"trade_id": 1, "ref": None}
    assert client.get("/api/trades/1/ref").get_json()["ref"] is None
    assert client.put("/api/trades/4/ref", json={"ref": "BA-1"}).status_code == 200  # ya libre
    assert client.put("/api/trades/4/ref", json={"ref": None}).get_json() == {"trade_id": 4, "ref": None}
    assert client.put("/api/trades/4/ref", json={"ref": "   "}).get_json() == {"trade_id": 4, "ref": None}


def test_ref_is_trimmed_and_limited(client):
    assert client.put("/api/trades/1/ref", json={"ref": "  X1  "}).get_json()["ref"] == "X1"
    assert client.put("/api/trades/1/ref", json={"ref": "r" * 64}).status_code == 200
    r = client.put("/api/trades/1/ref", json={"ref": "r" * 65})
    assert r.status_code == 400 and r.get_json()["field"] == "ref"
    for bad in (123, True, ["a"]):
        r = client.put("/api/trades/1/ref", json={"ref": bad})
        assert r.status_code == 400 and r.get_json()["field"] == "ref"
    r = client.put("/api/trades/1/ref", json={})  # sin la clave no se borra nada por descuido
    assert r.status_code == 400 and r.get_json()["field"] == "ref"


def test_ref_error_order_404_then_400_then_409(client):
    client.put("/api/trades/1/ref", json={"ref": "BA-1"})
    assert client.put("/api/trades/999/ref", json={"ref": 5}).status_code == 404  # 404 antes que 400
    assert client.put("/api/trades/999/ref", data="no es json").status_code == 404  # y antes de leer el cuerpo
    r = client.put("/api/trades/4/ref", json={"ref": 5})
    assert r.status_code == 400 and r.get_json()["field"] == "ref"
    assert client.put("/api/trades/4/ref", json={"ref": "BA-1"}).status_code == 409


@pytest.mark.parametrize("method", ["get", "put"])
@pytest.mark.parametrize("raw", ["abc", "999", "99999999999999999999"])
def test_ref_unknown_trade_is_404_id(client, method, raw):
    r = getattr(client, method)("/api/trades/%s/ref" % raw, **({"json": {"ref": "x"}} if method == "put" else {}))
    assert r.status_code == 404 and r.get_json()["field"] == "id"


# ------------------------------------------------- las confirmaciones no tocan el P&L

def test_confirmation_does_not_change_pnl_or_flows(app, client):
    roll(client, "MX-DEMO", "D1", 35)
    pnl_url, flows_url = "/api/pnl?from=MX-DEMO&to=D1", "/api/trades/1/flows?snapshot=D1"
    pnl_before, flows_before = client.get(pnl_url).get_json(), client.get(flows_url).get_json()
    coupon = date(2026, 12, 8)  # primer cupón del swap 1 (28 días tras el inicio), ya liquidado al 2026-12-15
    assert [f["date"] for f in flows_before["flows"] if f["status"] == "settled"] == [coupon.isoformat()]

    confirm_raw(app, 1, coupon, 123.0)
    events = client.get("/api/trades/1").get_json()["events"]
    assert [e["data"].get("kind") for e in events if e["type"] == "transfer"] == ["settlement_confirmed"]

    pnl_after, flows_after = client.get(pnl_url).get_json(), client.get(flows_url).get_json()
    assert flows_after == flows_before
    assert pnl_after == pnl_before
    row_before = {r["id"]: r for r in pnl_before["rows"]}[1]
    row_after = {r["id"]: r for r in pnl_after["rows"]}[1]
    for name in ("pv_from", "pv_to", "settled", "pnl"):
        assert row_after[name] == pytest.approx(row_before[name], abs=1e-12)
    assert pnl_after["total_mxn"] == pytest.approx(pnl_before["total_mxn"], abs=1e-12)


def test_other_transfers_still_count(app, client):
    """Solo se ignora `settlement_confirmed`: el resto de los `transfer` sigue siendo un flujo."""
    roll(client, "MX-DEMO", "D1", 35)
    flows_url = "/api/trades/1/flows?snapshot=D1"
    before = client.get(flows_url).get_json()["flows"]
    r = client.post(
        "/api/trades/1/events",
        json={"type": "termination", "event_date": "2026-12-14", "data": {"amount": 1000.0}},
    )
    assert r.status_code == 201, r.get_json()
    after = client.get(flows_url).get_json()["flows"]
    assert [f for f in after if f["kind"] == "transfer"][0]["amount"] == 1000.0
    assert len(after) != len(before)


# --------------------------------------------------------------- piezas reales de T1

def test_business_day_skips_weekends():
    from desk.api.ops_recon import business_day

    assert business_day(date(2026, 11, 13), 1) == date(2026, 11, 16)  # viernes -> lunes
    assert business_day(date(2026, 11, 16), -1) == date(2026, 11, 13)  # lunes -> viernes
    assert business_day(date(2026, 11, 10), 1) == date(2026, 11, 11)
    assert business_day(date(2026, 11, 14), 1) == date(2026, 11, 16)  # sábado -> lunes
    assert business_day(date(2026, 11, 15), -1) == date(2026, 11, 13)  # domingo -> viernes


def test_context_at_keeps_the_market_and_changes_only_the_date(app):
    from desk.api.ops_recon import context_at

    conn = connect(app.config["DESK_DB"])
    try:
        mkt = market.load_context(conn, "MX-DEMO")
    finally:
        conn.close()
    other = context_at(mkt, date(2026, 11, 11))
    assert other.as_of == date(2026, 11, 11) and mkt.as_of == AS_OF
    assert other.snapshot_id == mkt.snapshot_id and other.spot == mkt.spot
    assert other.curves is mkt.curves and other.surface is mkt.surface and other.pillars is mkt.pillars
    assert own_pv(app, 4, mkt_fn=lambda m: context_at(m, AS_OF)) == pytest.approx(own_pv(app, 4), abs=1e-9)


def test_confirmations_maps_only_settlement_confirmations_by_date_and_currency(app):
    from desk.api import portfolio
    from desk.api.ops_cashflows import confirmations
    from desk.api.ops_settlements import is_confirmation

    confirm_raw(app, 1, date(2026, 12, 8), 10.0)
    conn = connect(app.config["DESK_DB"])
    try:
        trade = portfolio.get_trade(conn, 1)
    finally:
        conn.close()
    found = confirmations(trade)
    key = (date(2026, 12, 8), "MXN")
    assert list(found) == [key] and found[key]["amount"] == 10.0
    assert [is_confirmation(e) for e in trade["events"]] == [False, True]
    assert confirmations({"events": [e for e in trade["events"] if e["type"] == "execution"]}) == {}


# ---------------------------------------------------------------- registro de rutas

ROUTES = [
    ("GET", "/api/settings"),
    ("PUT", "/api/settings"),
    ("GET", "/api/trades/<trade_id>/ref"),
    ("PUT", "/api/trades/<trade_id>/ref"),
    ("GET", "/api/cashflows"),
    ("POST", "/api/trades/<trade_id>/settlements"),
    ("GET", "/api/trades/<trade_id>/confirmation"),
    ("GET", "/api/trades/<trade_id>/fpml"),
    ("POST", "/api/trades/fpml"),
    ("POST", "/api/reconciliations"),
    ("GET", "/api/reconciliations"),
    ("GET", "/api/reconciliations/<run_id>"),
]


@pytest.mark.parametrize("method,rule", ROUTES)
def test_route_is_registered(app, method, rule):
    assert any(r.rule == rule and method in r.methods for r in app.url_map.iter_rules())


def test_fpml_import_rule_wins_over_the_trade_id_rule(app):
    adapter = app.url_map.bind("localhost")
    assert adapter.match("/api/trades/fpml", method="POST")[0] == "ops.import_fpml"
    assert adapter.match("/api/trades/7/fpml", method="GET")[0] == "ops.export_fpml"


def test_cashflows_format_is_checked_by_the_route(client):
    r = client.get("/api/cashflows?snapshot=MX-DEMO&format=xml")
    assert r.status_code == 400 and r.get_json()["field"] == "format"


@pytest.mark.parametrize("raw", ["abc", "99999999999999999999"])
def test_reconciliation_id_that_cannot_exist_is_404_id(client, raw):
    r = client.get("/api/reconciliations/%s" % raw)
    assert r.status_code == 404 and r.get_json()["field"] == "id"


# --------------------------------------- armado de respuestas de las rutas (con módulos simulados)
# Las rutas quedan cerradas tras T1: estas pruebas fijan sus cabeceras, códigos y commits
# sin depender de que los módulos de T2-T6 estén implementados.

def test_cashflows_csv_response_headers(client, monkeypatch):
    from desk.api import ops_cashflows

    monkeypatch.setattr(ops_cashflows, "cashflows", lambda conn, args: {"snapshot": "MX-DEMO", "rows": []})
    monkeypatch.setattr(ops_cashflows, "cashflows_csv", lambda payload: "date,trade_id\n")
    r = client.get("/api/cashflows?snapshot=MX-DEMO&format=csv")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "text/csv; charset=utf-8"
    assert r.headers["Content-Disposition"] == 'attachment; filename="flujos-MX-DEMO.csv"'
    assert r.get_data(as_text=True) == "date,trade_id\n"
    assert client.get("/api/cashflows?snapshot=MX-DEMO").get_json() == {"snapshot": "MX-DEMO", "rows": []}


def test_json_responses_refuse_non_finite_numbers(client, monkeypatch):
    from desk.api import ops_cashflows

    monkeypatch.setattr(ops_cashflows, "cashflows", lambda conn, args: {"snapshot": "S", "x": float("nan")})
    assert client.get("/api/cashflows?snapshot=S").status_code == 400


def test_fpml_export_and_import_responses(client, monkeypatch):
    from desk.api import fpml

    seen = {}
    monkeypatch.setattr(fpml, "export_trade", lambda conn, tid: "<?xml version='1.0' encoding='utf-8'?><a>é</a>")

    def fake_import(conn, raw):
        seen["raw"] = raw
        return {"trade": {"id": 1}, "warnings": []}

    monkeypatch.setattr(fpml, "import_trade", fake_import)
    r = client.get("/api/trades/4/fpml")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "application/xml; charset=utf-8"
    assert r.headers["Content-Disposition"] == 'attachment; filename="operacion-4.fpml.xml"'
    assert r.get_data().decode("utf-8").endswith("<a>é</a>")
    assert client.get("/api/trades/abc/fpml").status_code == 404
    r = client.post("/api/trades/fpml", data="<x>é</x>".encode("utf-8"), content_type="text/plain")
    assert r.status_code == 201 and r.get_json() == {"trade": {"id": 1}, "warnings": []}
    assert seen["raw"] == "<x>é</x>".encode("utf-8")  # cuerpo crudo en bytes, sin pasar por JSON


def test_writing_routes_commit_only_on_success(app, client, monkeypatch):
    from desk.api import ops_recon, ops_settlements
    from desk.api.errors import ApiError

    def write(conn, *args):
        conn.execute("INSERT INTO settings (key, value, updated_at) VALUES ('probe', 'v', 'x')")
        return {"ok": True}

    monkeypatch.setattr(ops_settlements, "confirm_settlement", write)
    monkeypatch.setattr(ops_recon, "create_run", write)

    def count():
        conn = sqlite3.connect(app.config["DESK_DB"])
        try:
            return conn.execute("SELECT COUNT(*) FROM settings WHERE key = 'probe'").fetchone()[0]
        finally:
            conn.close()

    r = client.post("/api/trades/1/settlements", json={})
    assert r.status_code == 201 and r.get_json() == {"ok": True} and count() == 1
    _sql(app, "DELETE FROM settings")

    def write_then_fail(conn, *args):
        write(conn)
        raise ApiError(409, "no", "date")

    monkeypatch.setattr(ops_recon, "create_run", write_then_fail)
    assert client.post("/api/reconciliations", json={}).status_code == 409
    assert count() == 0  # una 4xx no deja nada escrito


def test_reconciliation_routes_responses(client, monkeypatch):
    from desk.api import ops_recon

    calls = []
    monkeypatch.setattr(ops_recon, "list_runs", lambda conn, cp=None: calls.append(cp) or [])
    monkeypatch.setattr(ops_recon, "get_run", lambda conn, rid: {"id": rid})
    monkeypatch.setattr(ops_recon, "run_csv", lambda run: "section\n")
    assert client.get("/api/reconciliations").get_json() == {"reconciliations": []}
    client.get("/api/reconciliations?counterparty=Banco%20Alfa")
    assert calls == [None, "Banco Alfa"]
    assert client.get("/api/reconciliations/3").get_json() == {"id": 3}
    r = client.get("/api/reconciliations/3?format=csv")
    assert r.headers["Content-Type"] == "text/csv; charset=utf-8"
    assert r.headers["Content-Disposition"] == 'attachment; filename="conciliacion-3.csv"'
    r = client.get("/api/reconciliations/3?format=xml")
    assert r.status_code == 400 and r.get_json()["field"] == "format"
