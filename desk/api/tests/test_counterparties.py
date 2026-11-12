"""Corte 3, T4: colateral por contraparte (historial solo de inserción), rutas y ganchos de contrato."""
import sqlite3
from datetime import date

import pytest

from desk.api import db, lifecycle, portfolio
from desk.api.app import create_app
from desk.api.collateral import currency_on
from desk.api.tests.csa_fixture import set_collateral, strip_csa, trade_with

ALFA = "Banco Alfa (sintético)"
BETA = "Banco Beta (sintético)"
GAMMA = "Banco Gamma (sintético)"


def _listing(client):
    r = client.get("/api/counterparties")
    assert r.status_code == 200, r.get_json()
    return {c["name"]: c for c in r.get_json()["counterparties"]}


def _conn(app):
    conn = db.connect(app.config["DESK_DB"])
    return conn


# ------------------------------------------------------------------------------ esquema

@pytest.mark.parametrize("sql", [
    "UPDATE counterparty_events SET type = 'x'",
    "DELETE FROM counterparty_events",
])
def test_counterparty_events_is_insert_only(app, client, sql):
    assert set_collateral(client, ALFA, "USD", "2026-11-10").status_code == 200
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        with pytest.raises(sqlite3.DatabaseError, match="solo de inserción"):
            conn.execute(sql)
    finally:
        conn.close()


def test_existing_base_without_the_table_recovers_it_when_the_app_is_recreated(tmp_path):
    path = tmp_path / "old.db"
    create_app(db_path=path)
    conn = sqlite3.connect(str(path))
    conn.executescript(
        "DROP TRIGGER counterparty_events_no_update; DROP TRIGGER counterparty_events_no_delete;"
        "DROP TABLE counterparty_events;"
    )
    conn.close()
    app = create_app(db_path=path)
    conn = sqlite3.connect(str(path))
    try:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
        assert {"counterparty_events", "counterparty_events_no_update", "counterparty_events_no_delete"} <= names
        assert conn.execute("SELECT COUNT(*) FROM counterparties").fetchone()[0] == 3  # no resembró nada
    finally:
        conn.close()
    assert app.test_client().get("/api/counterparties").status_code == 200


# ------------------------------------------------------------------------------ lectura

def test_listing_has_the_seed_counterparties_in_mxn_with_their_trade_counts(client):
    r = client.get("/api/counterparties")
    assert r.status_code == 200
    rows = r.get_json()["counterparties"]
    assert [c["name"] for c in rows] == [ALFA, BETA, GAMMA]  # por nombre
    # 7 originales (3, 2, 2) + 9 del corte 9 (3 por contraparte)
    assert {c["name"]: c["trades"] for c in rows} == {ALFA: 6, BETA: 5, GAMMA: 5}
    for c in rows:
        assert set(c) == {"id", "name", "collateral_currency", "effective_date", "trades", "history"}
        assert c["collateral_currency"] == "MXN" and c["effective_date"] is None and c["history"] == []


def test_listing_trades_count_follows_new_trades(client):
    trade_with(client, "fx_forward", ALFA, {"side": "buy", "notional_usd": 1e6, "days": 30, "strike": 19.0})
    assert _listing(client)[ALFA]["trades"] == 7  # 6 sembradas (corte 9 incluido) + la nueva


# ------------------------------------------------------------------------------ PUT

def test_valid_put_changes_the_collateral_and_records_one_event(client, monkeypatch):
    monkeypatch.setattr("desk.api.db.now_iso", lambda: "2026-11-11T18:00:00+00:00")
    r = set_collateral(client, ALFA, "USD", "2026-11-10")
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["name"] == ALFA and body["trades"] == 6  # 3 originales + 3 del corte 9
    assert body["collateral_currency"] == "USD" and body["effective_date"] == "2026-11-10"
    assert len(body["history"]) == 1
    assert set(body["history"][0]) == {"id", "collateral_currency", "effective_date", "created_at"}
    assert body["history"][0]["created_at"] == "2026-11-11T18:00:00+00:00"
    assert _listing(client)[ALFA] == body  # persistió (la ruta hizo commit)
    assert _listing(client)[BETA]["collateral_currency"] == "MXN"  # las demás no cambian


def test_second_put_back_to_mxn_with_a_later_date_is_accepted(client):
    assert set_collateral(client, ALFA, "USD", "2026-11-10").status_code == 200
    r = set_collateral(client, ALFA, "MXN", "2026-12-01")
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["collateral_currency"] == "MXN" and body["effective_date"] == "2026-12-01"
    assert [(h["collateral_currency"], h["effective_date"]) for h in body["history"]] == [
        ("USD", "2026-11-10"), ("MXN", "2026-12-01"),
    ]


def test_a_change_on_the_same_date_as_the_last_one_is_accepted_and_the_later_event_wins(app, client):
    assert set_collateral(client, ALFA, "USD", "2026-11-10").status_code == 200
    assert set_collateral(client, ALFA, "MXN", "2026-11-10").status_code == 200
    conn = _conn(app)
    try:
        trade = portfolio.get_trade(conn, 1)
    finally:
        conn.close()
    assert [e["currency"] for e in trade["collateral"]] == ["USD", "MXN"]
    assert currency_on(trade, date(2026, 11, 10)) == "MXN"


def _put(client, raw_id, body):
    return client.put("/api/counterparties/%s" % raw_id, json=body)


def _alfa_id(client):
    return _listing(client)[ALFA]["id"]


@pytest.mark.parametrize("raw_id", ["abc", "999", "-1", "1_0", "9" * 30, "1.5"])
def test_put_unknown_or_non_integer_id_is_404_on_id(client, raw_id):
    r = _put(client, raw_id, {"collateral_currency": "USD", "effective_date": "2026-11-10"})
    assert r.status_code == 404 and r.get_json()["field"] == "id"


def test_put_id_is_checked_before_the_body_fields(client):
    r = _put(client, "999", {"collateral_currency": "EUR"})
    assert r.status_code == 404 and r.get_json()["field"] == "id"


@pytest.mark.parametrize("body, field", [
    ({"effective_date": "2026-11-10"}, "collateral_currency"),
    ({"collateral_currency": "EUR", "effective_date": "2026-11-10"}, "collateral_currency"),
    ({"collateral_currency": "usd", "effective_date": "2026-11-10"}, "collateral_currency"),
    ({"collateral_currency": 1, "effective_date": "2026-11-10"}, "collateral_currency"),
    ({"collateral_currency": "USD"}, "effective_date"),
    ({"collateral_currency": "USD", "effective_date": "10/11/2026"}, "effective_date"),
    ({"collateral_currency": "USD", "effective_date": "2026-13-01"}, "effective_date"),
])
def test_put_invalid_body_is_400_on_its_field(client, body, field):
    r = _put(client, _alfa_id(client), body)
    assert r.status_code == 400 and r.get_json()["field"] == field


def test_put_without_a_json_object_is_400(client):
    r = client.put("/api/counterparties/%d" % _alfa_id(client), data="no es json")
    assert r.status_code == 400
    r = client.put("/api/counterparties/%d" % _alfa_id(client), json=[1])
    assert r.status_code == 400


def test_put_date_before_the_last_event_is_409_on_effective_date(client):
    assert set_collateral(client, ALFA, "USD", "2026-11-10").status_code == 200
    r = set_collateral(client, ALFA, "MXN", "2026-11-09")
    assert r.status_code == 409 and r.get_json()["field"] == "effective_date"
    assert len(_listing(client)[ALFA]["history"]) == 1  # no insertó


def test_put_same_currency_as_the_one_in_force_is_409_on_collateral_currency(client):
    assert set_collateral(client, ALFA, "USD", "2026-11-10").status_code == 200
    r = set_collateral(client, ALFA, "USD", "2026-11-11")
    assert r.status_code == 409 and r.get_json()["field"] == "collateral_currency"
    assert r.get_json()["error"] == "La contraparte ya tiene colateral en USD"
    r = set_collateral(client, BETA, "MXN", "2026-11-11")  # sin eventos rige MXN por omisión
    assert r.status_code == 409 and r.get_json()["error"] == "La contraparte ya tiene colateral en MXN"


def test_put_date_error_precedes_currency_error(client):
    assert set_collateral(client, ALFA, "USD", "2026-11-10").status_code == 200
    r = set_collateral(client, ALFA, "USD", "2026-11-09")
    assert r.status_code == 409 and r.get_json()["field"] == "effective_date"


# ------------------------------------------------------------------------------ currency_on

def test_currency_on_before_at_and_after_the_effective_date():
    trade = {"collateral": [
        {"effective_date": date(2026, 11, 10), "currency": "USD"},
        {"effective_date": date(2026, 12, 1), "currency": "MXN"},
    ]}
    assert currency_on(trade, date(2026, 11, 9)) == "MXN"
    assert currency_on(trade, date(2026, 11, 10)) == "USD"
    assert currency_on(trade, date(2026, 11, 30)) == "USD"
    assert currency_on(trade, date(2026, 12, 1)) == "MXN"
    assert currency_on(trade, date(2030, 1, 1)) == "MXN"


def test_currency_on_a_trade_without_collateral_is_mxn():
    assert currency_on({}, date(2026, 11, 10)) == "MXN"
    assert currency_on({"collateral": []}, date(2026, 11, 10)) == "MXN"


def test_trades_carry_the_collateral_history_of_their_counterparty(app, client):
    assert set_collateral(client, ALFA, "USD", "2026-11-10").status_code == 200
    conn = _conn(app)
    try:
        by_cp = {}
        for t in portfolio.load_trades(conn):
            by_cp.setdefault(t["counterparty"], []).append(t["collateral"])
        one = portfolio.get_trade(conn, 1)
    finally:
        conn.close()
    expected = [{"effective_date": date(2026, 11, 10), "currency": "USD"}]
    assert all(c == expected for c in by_cp[ALFA]) and len(by_cp[ALFA]) == 6  # 3 originales + 3 del corte 9
    assert all(c == [] for c in by_cp[BETA] + by_cp[GAMMA])
    assert one["counterparty"] == ALFA and one["collateral"] == expected
    assert "collateral" not in portfolio.public_trade(one)  # la forma HTTP no cambia


def test_new_trades_of_a_counterparty_inherit_its_history(app, client):
    assert set_collateral(client, BETA, "USD", "2026-11-10").status_code == 200
    created = trade_with(client, "fx_forward", BETA, {"side": "buy", "notional_usd": 1e6, "days": 30, "strike": 19.0})
    conn = _conn(app)
    try:
        trade = portfolio.get_trade(conn, created["id"])
    finally:
        conn.close()
    assert currency_on(trade, date(2026, 11, 10)) == "USD"


# ------------------------------------------------------------------------------ feriados

def test_holidays_route_answers_200_now_that_the_calendars_exist(client):
    r = client.get("/api/calendars/holidays?from=2026-01-01&to=2026-12-31")
    assert r.status_code == 200


@pytest.mark.parametrize("query, field", [
    ("to=2026-12-31", "from"),
    ("from=2026-01-01", "to"),
    ("from=01-01-2026&to=2026-12-31", "from"),
    ("from=2026-01-01&to=nada", "to"),
    ("from=2026-12-31&to=2026-01-01", "to"),
    ("from=2019-12-31&to=2020-01-31", "from"),
    ("from=2040-12-01&to=2041-01-01", "to"),
    ("from=2019-01-01&to=2030-01-01", "from"),  # el año fuera de rango se avisa antes que el tope de días
    ("from=2020-01-01&to=2030-12-31", "to"),  # más de 3660 días
])
def test_holidays_route_validates_its_range(client, query, field):
    r = client.get("/api/calendars/holidays?" + query)
    assert r.status_code == 400 and r.get_json()["field"] == field


def test_holidays_route_accepts_a_ten_year_range(client):
    r = client.get("/api/calendars/holidays?from=2020-01-01&to=2030-01-01")  # 3653 días: dentro del tope
    assert r.status_code != 400


# ------------------------------------------------------------------------------ ganchos

def test_xccy_swap_notional_field_is_registered():
    assert lifecycle.NOTIONAL_FIELD["xccy_swap"] == "notional_usd"


def test_flows_carry_leg_none_and_the_bond_key(client):
    bond = trade_with(client, "bond", ALFA, {"curve": "TIIE-F", "face": 1e6, "coupon_rate": 0.07, "periods": 4})
    swap = client.get("/api/trades/1/flows?snapshot=MX-DEMO").get_json()
    quote = client.get("/api/trades/%d/flows?snapshot=MX-DEMO" % bond["id"]).get_json()
    assert swap["flows"] and all(f["leg"] is None for f in swap["flows"])
    assert quote["flows"] and all(f["leg"] is None for f in quote["flows"])
    assert "bond" in swap and "bond" in quote  # T9 rellena la cotización; hasta entonces None


def test_fixture_helpers_create_trades_and_strip_the_csa_quotes(app, client):
    created = trade_with(client, "irs", GAMMA, {"curve": "SOFR", "side": "payer", "notional": 1e6, "periods": 4})
    assert created["counterparty"] == GAMMA and created["params"]["fixed_rate"] is not None
    strip_csa(app, "MX-DEMO")
    data = client.get("/api/market/snapshots/MX-DEMO").get_json()
    assert not data.get("fx_forwards") and not data.get("xccy_basis")
