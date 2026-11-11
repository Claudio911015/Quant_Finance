"""Coberturas, T1: esquema solo de inserción, migración, lecturas y rutas registradas (R1, base de R1-R9, R12)."""
import json
import sqlite3
from datetime import date

import pytest

from desk.api import hedge_report, hedges
from desk.api.app import create_app
from desk.api.tests.hedge_fixture import DOC
from desk.api.tests.hedge_fixture import frozen_clock  # noqa: F401  (autouse: reloj fijo)

TABLES = ("hedge_relationships", "hedge_events", "hedge_periods")
ITEM = {
    "index": "TIIE-F", "notional": 500000000.0, "start_date": "2026-11-10",
    "maturity_date": "2027-11-09", "side": "pays_floating",
}
HYPO = {
    "product": "irs", "trade_date": "2026-11-10", "start_date": "2026-11-10", "maturity_date": "2027-11-09",
    "params": {"curve": "TIIE-F", "side": "payer", "notional": 500000000.0, "periods": 13, "fixed_rate": 0.0712},
}
DESIGNATION = {
    "snapshot": "MX-DEMO", "as_of": "2026-11-10", "data_quality": "synthetic",
    "pv_inst": 0.0, "pv_hypo": 0.0, "hypothetical": HYPO,
}


def _sql(app, sql, args=()):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        cur = conn.execute(sql, args)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _hedge_by_sql(app, trade_id):
    """Relación y evento `designation` insertados por SQL; devuelve el id de la relación."""
    hid = _sql(
        app,
        "INSERT INTO hedge_relationships (trade_id, fraction, hedge_type, item_kind, item_terms, hedge_ratio,"
        " designation_date, designation_snapshot, documentation, created_at)"
        " VALUES (?, 1.0, 'cash_flow', 'floating_loan', ?, 1.0, '2026-11-10', 'MX-DEMO', ?, 'x')",
        (trade_id, json.dumps(ITEM), json.dumps(DOC)),
    )
    _sql(
        app,
        "INSERT INTO hedge_events (relationship_id, type, event_date, data, created_at)"
        " VALUES (?, 'designation', '2026-11-10', ?, 'x')",
        (hid, json.dumps(DESIGNATION)),
    )
    return hid


def _trade_ids(client):
    return [t["id"] for t in client.get("/api/trades").get_json()["trades"]]


def _db(app):
    conn = sqlite3.connect(app.config["DESK_DB"])
    conn.row_factory = sqlite3.Row
    return conn


# ------------------------------------------------------------------------- esquema

@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("sql", ["UPDATE {t} SET created_at = 'y'", "DELETE FROM {t}"])
def test_hedge_tables_reject_update_and_delete(app, client, table, sql):
    hid = _hedge_by_sql(app, _trade_ids(client)[0])
    _sql(
        app,
        "INSERT INTO hedge_periods (relationship_id, snapshot_id, as_of, result, created_at)"
        " VALUES (?, 'D1', '2026-12-15', '{}', 'x')",
        (hid,),
    )
    with pytest.raises(sqlite3.DatabaseError):
        _sql(app, sql.format(t=table))


def test_a_corte2_database_recovers_the_three_tables_without_losing_trades(tmp_path):
    path = tmp_path / "corte2.db"
    create_app(db_path=path)
    conn = sqlite3.connect(str(path))
    trades = conn.execute("SELECT * FROM trades ORDER BY id").fetchall()
    for table in TABLES:
        conn.execute("DROP TRIGGER IF EXISTS %s_no_update" % table)
        conn.execute("DROP TRIGGER IF EXISTS %s_no_delete" % table)
        conn.execute("DROP TABLE %s" % table)
    conn.commit()
    assert not conn.execute("SELECT name FROM sqlite_master WHERE name LIKE 'hedge_%'").fetchall()
    conn.close()

    create_app(db_path=path)

    conn = sqlite3.connect(str(path))
    try:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE name LIKE 'hedge_%'")}
        assert names == set(TABLES) | {"%s_no_%s" % (t, k) for t in TABLES for k in ("update", "delete")}
        assert conn.execute("SELECT * FROM trades ORDER BY id").fetchall() == trades
    finally:
        conn.close()


# ------------------------------------------------------------------------- lecturas

def test_list_is_empty_without_relationships(client):
    r = client.get("/api/hedges")
    assert (r.status_code, r.get_json()) == (200, {"hedges": []})


def test_detail_of_a_relationship_inserted_by_sql(app, client):
    trade_id, other_id = _trade_ids(client)[:2]
    hid = _hedge_by_sql(app, trade_id)
    trade = client.get("/api/trades/%d" % trade_id).get_json()

    r = client.get("/api/hedges/%d" % hid)
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["status"] == "activa" and d["oci_balance"] == 0 and d["last_close"] is None
    assert d["dedesignation"] is None and d["periods"] == [] and d["warnings"] == []
    assert (d["id"], d["trade_id"], d["product"], d["counterparty"]) == (
        hid, trade_id, trade["product"], trade["counterparty"],
    )
    assert (d["fraction"], d["hedge_ratio"], d["hedge_type"], d["item_kind"]) == (1.0, 1.0, "cash_flow", "floating_loan")
    assert d["item_terms"] == ITEM
    assert (d["designation_date"], d["designation_snapshot"], d["documentation"]) == ("2026-11-10", "MX-DEMO", DOC)
    assert d["hypothetical"] == HYPO
    assert d["designation"] == {k: v for k, v in DESIGNATION.items() if k != "hypothetical"}
    assert [(e["type"], e["event_date"], e["relationship_id"]) for e in d["events"]] == [
        ("designation", "2026-11-10", hid)
    ]
    assert d["events"][0]["data"] == DESIGNATION

    listed = client.get("/api/hedges?trade_id=%d" % trade_id).get_json()["hedges"]
    assert listed == [
        {
            "id": hid, "trade_id": trade_id, "product": trade["product"], "counterparty": trade["counterparty"],
            "hedge_type": "cash_flow", "item_kind": "floating_loan", "fraction": 1.0, "hedge_ratio": 1.0,
            "designation_date": "2026-11-10", "status": "activa", "oci_balance": 0.0, "last_close": None,
            "periods_count": 0,
        }
    ]
    assert client.get("/api/hedges?trade_id=%d" % other_id).get_json() == {"hedges": []}
    assert [h["id"] for h in client.get("/api/hedges").get_json()["hedges"]] == [hid]


def test_periods_and_dedesignation_show_up_in_the_detail_and_the_summary(app, client):
    hid = _hedge_by_sql(app, _trade_ids(client)[0])
    conn = _db(app)
    try:
        hedges.insert_period(conn, hid, "D2", date(2027, 1, 12), {"oci": -300.0, "trade_status": "viva"})
        hedges.insert_period(conn, hid, "D1", date(2026, 12, 15), {"oci": -125.0, "trade_status": "viva"})
        hedges.insert_event(conn, hid, "period_close", date(2026, 12, 15), {"snapshot": "D1"})
        hedges.insert_event(conn, hid, "dedesignation", date(2027, 1, 20), {"reason": "Prepago", "frozen_oci": -300.0})
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):  # UNIQUE (relationship_id, as_of)
            hedges.insert_period(conn, hid, "D1b", date(2026, 12, 15), {"oci": 0.0})
        with pytest.raises(ValueError):
            hedges.insert_event(conn, hid, "otro", date(2027, 1, 20), {})
    finally:
        conn.close()

    d = client.get("/api/hedges/%d" % hid).get_json()
    assert [p["as_of"] for p in d["periods"]] == ["2026-12-15", "2027-01-12"]  # por as_of, no por inserción
    first = d["periods"][0]
    assert (first["snapshot"], first["oci"], first["trade_status"]) == ("D1", -125.0, "viva")
    assert set(first) == {"id", "snapshot", "as_of", "created_at", "oci", "trade_status"}
    assert [e["type"] for e in d["events"]] == ["designation", "period_close", "dedesignation"]
    assert d["status"] == "desdesignada"
    # Una desdesignación guardada antes de C2 no trae causa ni snapshot: el detalle los muestra vacíos.
    assert d["dedesignation"] == {
        "date": "2027-01-20", "reason": "Prepago", "cause": None, "snapshot": None, "frozen_oci": -300.0,
    }
    assert (d["oci_balance"], d["last_close"]) == (-300.0, "2027-01-12")

    summary = client.get("/api/hedges").get_json()["hedges"][0]
    assert (summary["status"], summary["oci_balance"], summary["last_close"], summary["periods_count"]) == (
        "desdesignada", -300.0, "2027-01-12", 2,
    )


def test_hypothetical_trade_is_an_in_memory_trade_that_never_reaches_the_trades_table(app, client):
    trade_id = _trade_ids(client)[0]
    before = len(_trade_ids(client))
    conn = _db(app)
    try:
        rel = hedges.load_relationship(conn, _hedge_by_sql(app, trade_id))
    finally:
        conn.close()
    hyp = hedges.hypothetical_trade(rel)
    assert hyp == {
        "id": None, "product": "irs", "counterparty": "Hipotético", "trade_date": date(2026, 11, 10),
        "start_date": date(2026, 11, 10), "maturity_date": date(2027, 11, 9), "params": HYPO["params"],
        "created_at": None, "events": [],
    }
    assert len(_trade_ids(client)) == before


@pytest.mark.parametrize("path", ["/api/hedges/abc", "/api/hedges/99999999999999999999", "/api/hedges/7"])
def test_unknown_id_is_404_on_the_id_field(client, path):
    r = client.get(path)
    assert r.status_code == 404 and r.get_json()["field"] == "id"


# ------------------------------------------------------------------------- rutas

def test_trade_id_filter_must_be_an_integer(client):
    for bad in ("abc", "1.5", "99999999999999999999"):
        r = client.get("/api/hedges?trade_id=%s" % bad)
        assert r.status_code == 400 and r.get_json()["field"] == "trade_id"


def test_effectiveness_requires_the_snapshot_parameter(client):
    for path in ("/api/hedges/1/effectiveness", "/api/hedges/1/effectiveness?snapshot=%20"):
        r = client.get(path)
        assert r.status_code == 400 and r.get_json()["field"] == "snapshot"


def test_route_ids_that_cannot_exist_are_404_before_anything_else(client):
    for verb, path in (
        ("post", "/api/hedges/abc/periods"), ("post", "/api/hedges/abc/dedesignate"),
        ("get", "/api/hedges/abc/effectiveness"), ("get", "/api/hedges/abc/report?format=xml"),
    ):
        r = getattr(client, verb)(path, json={})
        assert r.status_code == 404 and r.get_json()["field"] == "id", path


def test_report_format_must_be_json_or_csv(client):
    r = client.get("/api/hedges/1/report?format=xml")
    assert r.status_code == 400 and r.get_json()["field"] == "format"


def test_report_route_hands_the_snapshot_and_format_to_the_builder(client, monkeypatch):
    seen = []

    def build(conn, hedge_id, snapshot_id=None):
        seen.append((hedge_id, snapshot_id))
        return {"id": hedge_id}

    monkeypatch.setattr(hedge_report, "build_report", build)
    monkeypatch.setattr(hedge_report, "report_csv", lambda report: "period_id,as_of\n1,2026-12-15\n")

    r = client.get("/api/hedges/3/report")
    assert (r.status_code, r.get_json()) == (200, {"id": 3})
    r = client.get("/api/hedges/3/report?snapshot=D1&format=json")
    assert r.status_code == 200
    assert seen == [(3, None), (3, "D1")]

    r = client.get("/api/hedges/3/report?format=csv")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "text/csv; charset=utf-8"
    assert r.headers["Content-Disposition"] == 'attachment; filename="cobertura-3-asientos.csv"'
    assert r.get_data(as_text=True) == "period_id,as_of\n1,2026-12-15\n"
