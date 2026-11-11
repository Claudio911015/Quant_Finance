"""Eventos por la API (`POST /api/trades/<id>/events`) y estado (`GET /api/trades/<id>/state`)."""
import sqlite3
from datetime import date, timedelta

import pytest

from desk.api import events, lifecycle, portfolio
from desk.api.db import connect

FWD = {"side": "buy", "notional_usd": 1e6, "days": 91, "strike": 19.0}
IRS = {"curve": "TIIE-F", "side": "payer", "notional": 1e6, "periods": 13, "fixed_rate": 0.07}
BOND = {"curve": "TIIE-F", "face": 1e6, "coupon_rate": 0.08, "periods": 10, "frequency": 4.0}
OPTIONS = {
    "fx_option": {"side": "buy", "option_type": "call", "notional_usd": 1e6, "days": 91, "strike": 19.0},
    "swaption": {"curve": "TIIE-F", "swaption_type": "payer", "notional": 1e6, "strike": 0.07,
                 "expiry_years": 0.25, "swap_tenor_years": 2.0},
    "equity_option": {"option_type": "call", "spot": 55.0, "strike": 55.0, "volatility": 0.25, "rate": 0.07,
                      "dividend_yield": 0.02, "maturity_years": 1.0, "quantity": 100.0},
}
NOT_FINITE_RAW = '{"type": "%s", "event_date": "2026-11-12", "data": {"%s": %s}}'


def new_trade(client, product="fx_forward", params=None, **extra):
    body = {"product": product, "counterparty": "Banco Test", "params": dict(params or FWD), **extra}
    r = client.post("/api/trades", json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def post(client, trade_id, type, event_date, data=None):
    body = {"type": type, "event_date": event_date}
    if data is not None:
        body["data"] = data
    return client.post("/api/trades/%d/events" % trade_id, json=body)


def get_state(client, trade_id, on):
    r = client.get("/api/trades/%d/state?date=%s" % (trade_id, on))
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def event_rows(app, trade_id):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        return conn.execute(
            "SELECT id, type, event_date, data, prev_event_id FROM trade_events WHERE trade_id = ? ORDER BY id",
            (trade_id,),
        ).fetchall()
    finally:
        conn.close()


def iso(d):
    return d.isoformat()


# ----------------------------------------------------------------------------------- R1

@pytest.mark.parametrize("kind", ["novation", "", "QUANTITY_CHANGE", 5, ["termination"], None])
def test_type_outside_the_catalog_is_400(client, kind):
    t = new_trade(client)
    r = client.post("/api/trades/%d/events" % t["id"], json={"type": kind, "event_date": "2026-11-12", "data": {}})
    assert r.status_code == 400 and r.get_json()["field"] == "type", r.get_json()


@pytest.mark.parametrize("kind", ["execution", "reset", "transfer"])
def test_catalog_types_the_api_does_not_accept_are_400(app, client, kind):
    t = new_trade(client)
    r = post(client, t["id"], kind, "2026-11-12", {"amount": 1.0})
    assert r.status_code == 400 and r.get_json()["field"] == "type"
    assert [row[1] for row in event_rows(app, t["id"])] == ["execution"]


def test_missing_type_is_400(client):
    t = new_trade(client)
    r = client.post("/api/trades/%d/events" % t["id"], json={"event_date": "2026-11-12"})
    assert r.status_code == 400 and r.get_json()["field"] == "type"


def test_unknown_trade_is_404_on_id(client):
    r = post(client, 9999, "termination", "2026-11-12", {"amount": 1.0})
    assert r.status_code == 404 and r.get_json()["field"] == "id"
    r = client.get("/api/trades/9999/state?date=2026-11-10")
    assert r.status_code == 404 and r.get_json()["field"] == "id"


def test_delete_is_always_409(client):
    t = new_trade(client)
    r = client.delete("/api/trades/%d" % t["id"])
    assert r.status_code == 409 and r.get_json()["field"] == "id"
    assert client.get("/api/trades/%d" % t["id"]).status_code == 200


# --------------------------------------------------------------------------- event_date

@pytest.mark.parametrize("bad", [None, "2026-13-01", "12/11/2026", "2026-11-1", 20261112, ""])
def test_event_date_invalid_is_400(client, bad):
    t = new_trade(client)
    body = {"type": "termination", "data": {"amount": 1.0}}
    if bad is not None:
        body["event_date"] = bad
    r = client.post("/api/trades/%d/events" % t["id"], json=body)
    assert r.status_code == 400 and r.get_json()["field"] == "event_date"


def test_event_date_before_trade_date_is_400(app, client):
    t = new_trade(client, trade_date="2026-11-10")
    r = post(client, t["id"], "termination", "2026-11-09", {"amount": 1.0})
    assert r.status_code == 400 and r.get_json()["field"] == "event_date"
    assert len(event_rows(app, t["id"])) == 1


def test_event_on_or_after_maturity_is_409_vencida(app, client):
    t = new_trade(client)
    for on in (t["maturity_date"], iso(date.fromisoformat(t["maturity_date"]) + timedelta(days=5))):
        r = post(client, t["id"], "termination", on, {"amount": 1.0})
        assert r.status_code == 409 and r.get_json()["field"] == "id"
        assert "vencida" in r.get_json()["error"]
    assert len(event_rows(app, t["id"])) == 1


# -------------------------------------------------------------------------------- data

def test_data_must_be_an_object(client):
    t = new_trade(client)
    r = client.post("/api/trades/%d/events" % t["id"],
                    json={"type": "termination", "event_date": "2026-11-12", "data": [1]})
    assert r.status_code == 400 and r.get_json()["field"] == "data"


@pytest.mark.parametrize("data", [None, {}, {"amount": "1"}, {"amount": True}, {"amount": None}, {"amount": 1e14}])
def test_termination_amount_invalid_is_400(app, client, data):
    t = new_trade(client)
    r = post(client, t["id"], "termination", "2026-11-12", data)
    assert r.status_code == 400 and r.get_json()["field"] == "amount"
    assert len(event_rows(app, t["id"])) == 1


@pytest.mark.parametrize("data", [None, {}, {"notional": 0}, {"notional": -5}, {"notional": "9"},
                                  {"notional": False}, {"notional": 1e14}])
def test_quantity_change_notional_invalid_is_400(app, client, data):
    t = new_trade(client)
    r = post(client, t["id"], "quantity_change", "2026-11-12", data)
    assert r.status_code == 400 and r.get_json()["field"] == "notional"
    assert len(event_rows(app, t["id"])) == 1


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e999"])
@pytest.mark.parametrize("kind, key", [("termination", "amount"), ("exercise", "amount"),
                                       ("quantity_change", "notional")])
def test_non_finite_numbers_are_400(app, client, literal, kind, key):
    product = "fx_option" if kind == "exercise" else "fx_forward"
    t = new_trade(client, product, OPTIONS.get(product))
    r = client.post("/api/trades/%d/events" % t["id"], data=NOT_FINITE_RAW % (kind, key, literal),
                    content_type="application/json")
    assert r.status_code == 400 and r.get_json()["field"] == key, r.get_json()
    assert len(event_rows(app, t["id"])) == 1


# ---------------------------------------------------------------------------------- R5

def test_termination_inserts_event_and_chained_transfer(app, client):
    t = new_trade(client)
    r = post(client, t["id"], "termination", "2026-11-20", {"amount": -12500.5})
    assert r.status_code == 201, r.get_json()
    evs = r.get_json()["events"]
    assert [e["type"] for e in evs] == ["termination", "transfer"]
    term, transfer = evs
    assert term["data"] == {"amount": -12500.5} and term["event_date"] == "2026-11-20"
    assert transfer["data"] == {"amount": -12500.5, "currency": "MXN", "cause_event_id": term["id"]}
    assert transfer["event_date"] == "2026-11-20" and transfer["trade_id"] == t["id"]
    execution_id = event_rows(app, t["id"])[0][0]
    assert term["prev_event_id"] == execution_id and transfer["prev_event_id"] == term["id"]
    assert [row[1] for row in event_rows(app, t["id"])] == ["execution", "termination", "transfer"]
    assert get_state(client, t["id"], "2026-11-19")["status"] == "viva"
    assert get_state(client, t["id"], "2026-11-20")["status"] == "terminada"
    assert get_state(client, t["id"], t["maturity_date"])["status"] == "terminada"


def test_any_event_after_a_termination_is_409_and_inserts_nothing(app, client):
    t = new_trade(client)
    assert post(client, t["id"], "termination", "2026-11-20", {"amount": 5.0}).status_code == 201
    before = len(event_rows(app, t["id"]))
    for kind, on, data in [("termination", "2026-11-20", {"amount": 1.0}),
                           ("quantity_change", "2026-11-25", {"notional": 5e5}),
                           ("terms_change", "2026-12-01", {"terms": {"strike": 19.5}})]:
        r = post(client, t["id"], kind, on, data)
        assert r.status_code == 409 and r.get_json()["field"] == "id", (kind, r.get_json())
        assert "terminada" in r.get_json()["error"]
    assert len(event_rows(app, t["id"])) == before


@pytest.mark.parametrize("product", sorted(OPTIONS))
def test_exercise_on_options_inserts_exercise_and_transfer(app, client, product):
    t = new_trade(client, product, OPTIONS[product])
    r = post(client, t["id"], "exercise", "2026-11-25", {"amount": 8000.0})
    assert r.status_code == 201, r.get_json()
    ex, transfer = r.get_json()["events"]
    assert (ex["type"], transfer["type"]) == ("exercise", "transfer")
    assert transfer["data"] == {"amount": 8000.0, "currency": "MXN", "cause_event_id": ex["id"]}
    assert transfer["prev_event_id"] == ex["id"]
    assert get_state(client, t["id"], "2026-11-24")["status"] == "viva"
    assert get_state(client, t["id"], "2026-11-25")["status"] == "ejercida"
    assert post(client, t["id"], "termination", "2026-12-01", {"amount": 1.0}).status_code == 409


@pytest.mark.parametrize("product", sorted(OPTIONS))
def test_exercise_on_the_maturity_date_is_accepted_and_the_state_is_ejercida(app, client, product):
    t = new_trade(client, product, OPTIONS[product])
    maturity = date.fromisoformat(t["maturity_date"])
    r = post(client, t["id"], "exercise", iso(maturity), {"amount": 8000.0})
    assert r.status_code == 201, r.get_json()
    assert [e["type"] for e in r.get_json()["events"]] == ["exercise", "transfer"]
    assert [row[1] for row in event_rows(app, t["id"])] == ["execution", "exercise", "transfer"]
    assert get_state(client, t["id"], iso(maturity - timedelta(days=1)))["status"] == "viva"
    assert get_state(client, t["id"], iso(maturity))["status"] == "ejercida"
    assert get_state(client, t["id"], iso(maturity + timedelta(days=1)))["status"] == "ejercida"


def test_exercise_after_the_maturity_date_is_409_vencida(app, client):
    t = new_trade(client, "fx_option", OPTIONS["fx_option"])
    after = iso(date.fromisoformat(t["maturity_date"]) + timedelta(days=1))
    r = post(client, t["id"], "exercise", after, {"amount": 8000.0})
    assert r.status_code == 409 and r.get_json()["field"] == "id"
    assert "vencida" in r.get_json()["error"]
    assert len(event_rows(app, t["id"])) == 1


def test_exercise_on_the_maturity_date_of_an_already_closed_trade_is_409(app, client):
    t = new_trade(client, "fx_option", OPTIONS["fx_option"])
    maturity = date.fromisoformat(t["maturity_date"])
    assert post(client, t["id"], "exercise", iso(maturity), {"amount": 8000.0}).status_code == 201
    r = post(client, t["id"], "exercise", iso(maturity), {"amount": 1.0})
    assert r.status_code == 409 and r.get_json()["field"] == "id" and "ejercida" in r.get_json()["error"]
    assert len(event_rows(app, t["id"])) == 3

    u = new_trade(client, "fx_option", OPTIONS["fx_option"])
    assert post(client, u["id"], "termination", iso(maturity - timedelta(days=1)), {"amount": 5.0}).status_code == 201
    r = post(client, u["id"], "exercise", iso(maturity), {"amount": 1.0})
    assert r.status_code == 409 and "terminada" in r.get_json()["error"]
    assert len(event_rows(app, u["id"])) == 3


@pytest.mark.parametrize("product, params", [("irs", IRS), ("fx_forward", FWD), ("bond", BOND),
                                             ("cap_floor", {"curve": "TIIE-F", "cap_type": "cap",
                                                            "notional": 1e6, "periods": 13, "strike": 0.07})])
def test_exercise_on_a_non_option_is_400_on_type(app, client, product, params):
    t = new_trade(client, product, params)
    r = post(client, t["id"], "exercise", "2026-11-20", {"amount": 1.0})
    assert r.status_code == 400 and r.get_json()["field"] == "type"
    assert len(event_rows(app, t["id"])) == 1


# ---------------------------------------------------------------------------------- R6

def test_quantity_change_changes_the_state_only_from_its_date(app, client):
    t = new_trade(client)
    r = post(client, t["id"], "quantity_change", "2026-11-20", {"notional": 4e5})
    assert r.status_code == 201
    (e,) = r.get_json()["events"]
    assert e["type"] == "quantity_change" and e["data"] == {"notional": 4e5}
    before = get_state(client, t["id"], "2026-11-19")
    after = get_state(client, t["id"], "2026-11-20")
    assert (before["status"], before["notional"], before["terms"]["notional_usd"]) == ("viva", 1e6, 1e6)
    assert (after["status"], after["notional"], after["terms"]["notional_usd"]) == ("viva", 4e5, 4e5)
    assert after["id"] == t["id"] and after["date"] == "2026-11-20"
    # la operación de origen no cambia
    assert client.get("/api/trades/%d" % t["id"]).get_json()["params"]["notional_usd"] == 1e6


@pytest.mark.parametrize("product, params, key, value", [
    ("fx_forward", FWD, "strike", 19.4),
    ("fx_option", OPTIONS["fx_option"], "strike", 19.4),
    ("irs", IRS, "fixed_rate", 0.0725),
    ("cap_floor", {"curve": "TIIE-F", "cap_type": "cap", "notional": 1e6, "periods": 13, "strike": 0.07},
     "strike", 0.08),
    ("swaption", OPTIONS["swaption"], "strike", 0.075),
    ("equity_option", OPTIONS["equity_option"], "strike", 56.0),
])
def test_terms_change_updates_the_price_field_from_its_date(client, product, params, key, value):
    t = new_trade(client, product, params)
    r = post(client, t["id"], "terms_change", "2026-11-20", {"terms": {key: value}})
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["events"][0]["data"] == {"terms": {key: value}}
    assert get_state(client, t["id"], "2026-11-19")["terms"][key] == params[key]
    st = get_state(client, t["id"], "2026-11-20")
    assert st["terms"][key] == value
    assert {k: v for k, v in st["terms"].items() if k != key} == {k: v for k, v in params.items() if k != key}


@pytest.mark.parametrize("product, params, terms", [
    ("fx_forward", FWD, {"notional_usd": 5e5}),
    ("fx_forward", FWD, {"days": 30}),
    ("fx_forward", FWD, {"strike": 19.1, "notional_usd": 5e5}),
    ("fx_forward", FWD, {"fixed_rate": 0.07}),
    ("irs", IRS, {"strike": 0.07}),
    ("irs", IRS, {"periods": 5}),
    ("irs", IRS, {}),
    ("irs", IRS, {"fixed_rate": None}),
    ("irs", IRS, {"fixed_rate": "0.07"}),
    ("irs", IRS, {"fixed_rate": 11.0}),
    ("fx_forward", FWD, {"strike": -1.0}),
    ("fx_forward", FWD, {"strike": 0}),
    ("fx_forward", FWD, {"strike": float("nan")}),
    ("bond", BOND, {"coupon_rate": 0.09}),
    ("bond", BOND, {"strike": 1.0}),
])
def test_terms_change_with_other_keys_or_invalid_values_is_400_on_terms(app, client, product, params, terms):
    t = new_trade(client, product, params)
    r = post(client, t["id"], "terms_change", "2026-11-20", {"terms": terms})
    assert r.status_code == 400 and r.get_json()["field"] == "terms", r.get_json()
    assert len(event_rows(app, t["id"])) == 1


@pytest.mark.parametrize("data", [None, {}, {"terms": None}, {"terms": [1]}, {"terms": "strike"}])
def test_terms_change_without_a_terms_object_is_400_on_terms(client, data):
    t = new_trade(client)
    r = post(client, t["id"], "terms_change", "2026-11-20", data)
    assert r.status_code == 400 and r.get_json()["field"] == "terms"


# ------------------------------------------------------------------ orden cronológico

@pytest.mark.parametrize("kind, data", [("quantity_change", {"notional": 5e5}),
                                        ("terms_change", {"terms": {"strike": 19.5}}),
                                        ("termination", {"amount": 1.0})])
def test_event_dated_before_the_last_stored_event_is_409_on_event_date(app, client, kind, data):
    t = new_trade(client)
    assert post(client, t["id"], "quantity_change", "2026-11-25", {"notional": 8e5}).status_code == 201
    before = event_rows(app, t["id"])
    r = post(client, t["id"], kind, "2026-11-24", data)
    assert r.status_code == 409 and r.get_json()["field"] == "event_date", r.get_json()
    assert "cronológico" in r.get_json()["error"]
    assert event_rows(app, t["id"]) == before


def test_event_on_the_same_date_as_the_last_stored_event_is_accepted(app, client):
    t = new_trade(client)
    assert post(client, t["id"], "quantity_change", "2026-11-25", {"notional": 8e5}).status_code == 201
    assert post(client, t["id"], "terms_change", "2026-11-25", {"terms": {"strike": 19.5}}).status_code == 201
    assert len(event_rows(app, t["id"])) == 3


# ----------------------------------------------------------------------- orden y lectura

def test_events_listing_is_ordered_by_event_date_then_id(client):
    t = new_trade(client)
    post(client, t["id"], "quantity_change", "2026-11-20", {"notional": 8e5})
    post(client, t["id"], "quantity_change", "2026-11-20", {"notional": 7e5})
    post(client, t["id"], "quantity_change", "2026-12-01", {"notional": 5e5})
    got = client.get("/api/trades/%d" % t["id"]).get_json()["events"]
    assert [(e["type"], e["event_date"], e["data"].get("notional")) for e in got] == [
        ("execution", "2026-11-10", None),
        ("quantity_change", "2026-11-20", 8e5),
        ("quantity_change", "2026-11-20", 7e5),
        ("quantity_change", "2026-12-01", 5e5),
    ]
    assert [e["id"] for e in got[1:3]] == sorted(e["id"] for e in got[1:3])


def test_same_date_events_the_highest_id_wins(client):
    t = new_trade(client)
    post(client, t["id"], "quantity_change", "2026-11-20", {"notional": 8e5})
    post(client, t["id"], "quantity_change", "2026-11-20", {"notional": 7e5})
    post(client, t["id"], "quantity_change", "2026-12-01", {"notional": 5e5})
    assert get_state(client, t["id"], "2026-11-19")["notional"] == 1e6
    assert get_state(client, t["id"], "2026-11-20")["notional"] == 7e5
    assert get_state(client, t["id"], "2026-11-30")["notional"] == 7e5
    assert get_state(client, t["id"], "2026-12-01")["notional"] == 5e5


def test_state_date_param_is_validated(client):
    t = new_trade(client)
    for url in ("/api/trades/%d/state", "/api/trades/%d/state?date=", "/api/trades/%d/state?date=2026-02-30"):
        r = client.get(url % t["id"])
        assert r.status_code == 400 and r.get_json()["field"] == "date"


def test_state_before_trade_date_is_no_pactada(client):
    t = new_trade(client, trade_date="2026-11-20", start_date="2026-11-20")
    st = get_state(client, t["id"], "2026-11-19")
    assert st["status"] == "no_pactada" and st["notional"] == 1e6
    assert get_state(client, t["id"], "2026-11-20")["status"] == "viva"


# ---------------------------------------------------------------------------------- R2

def _build_trades(client):
    """Siete de la semilla (solo `execution`) más tres con eventos; devuelve los ids de las tres."""
    a = new_trade(client, trade_date="2026-11-10", maturity_date="2027-03-10")
    post(client, a["id"], "quantity_change", "2026-11-15", {"notional": 8e5})
    post(client, a["id"], "quantity_change", "2026-11-25", {"notional": 3e5})
    b = new_trade(client, trade_date="2026-11-10", maturity_date="2027-03-10")
    post(client, b["id"], "quantity_change", "2026-11-15", {"notional": 2e6})
    assert post(client, b["id"], "termination", "2026-11-25", {"amount": -1500.0}).status_code == 201
    c = new_trade(client, "fx_option", OPTIONS["fx_option"], trade_date="2026-11-10", maturity_date="2027-03-10")
    post(client, c["id"], "quantity_change", "2026-11-20", {"notional": 8e5})
    post(client, c["id"], "quantity_change", "2026-11-20", {"notional": 7e5})
    post(client, c["id"], "quantity_change", "2026-12-01", {"notional": 5e5})
    post(client, c["id"], "terms_change", "2026-12-10", {"terms": {"strike": 19.6}})
    return [a["id"], b["id"], c["id"]]


def _five_dates(trade, evs):
    days = sorted({e["event_date"] for e in evs if e["type"] != "execution"})
    start, maturity = trade["start_date"], trade["maturity_date"]
    if len(days) >= 2:
        between = days[0] + (days[-1] - days[0]) // 2
    else:
        between = start + (maturity - start) // 2
    after_last = (days[-1] if days else start) + timedelta(days=1)
    return [start - timedelta(days=1), start, between, after_last, maturity]


def test_state_recomputed_from_stored_events_matches_the_endpoint(app, client):
    created = _build_trades(client)
    conn = connect(app.config["DESK_DB"])
    try:
        trades = portfolio.load_trades(conn)
        assert len(trades) == 10 and set(created) <= {t["id"] for t in trades}
        distinct_by_trade = {}
        for t in trades:
            evs = events.load_events(conn, t["id"])
            seen = []
            for d in _five_dates(t, evs):
                want = lifecycle.state(t, evs, d)
                r = client.get("/api/trades/%d/state?date=%s" % (t["id"], d.isoformat()))
                assert r.status_code == 200, r.get_json()
                got = r.get_json()
                assert got == {"id": t["id"], "date": d.isoformat(), **want}, (t["id"], d)
                seen.append((got["status"], got["notional"], tuple(sorted(got["terms"].items()))))
            distinct_by_trade[t["id"]] = len(set(seen))
    finally:
        conn.close()
    # los tres con eventos recorren estados o nocionales distintos; no es una igualdad trivial
    assert all(distinct_by_trade[i] >= 3 for i in created), distinct_by_trade


def test_concrete_values_of_the_created_trades(client):
    a, b, c = _build_trades(client)
    assert [get_state(client, a, d)["notional"] for d in
            ("2026-11-14", "2026-11-15", "2026-11-24", "2026-11-25", "2027-03-09")] == [1e6, 8e5, 8e5, 3e5, 3e5]
    assert get_state(client, a, "2027-03-10")["status"] == "vencida"
    assert [get_state(client, b, d)["status"] for d in ("2026-11-24", "2026-11-25", "2027-03-10")] == \
        ["viva", "terminada", "terminada"]
    assert get_state(client, b, "2026-11-25")["notional"] == 2e6
    assert [get_state(client, c, d)["notional"] for d in
            ("2026-11-19", "2026-11-20", "2026-11-30", "2026-12-01")] == [1e6, 7e5, 7e5, 5e5]
    assert get_state(client, c, "2026-12-09")["terms"]["strike"] == 19.0
    assert get_state(client, c, "2026-12-10")["terms"]["strike"] == 19.6


def test_seed_trades_report_origin_state_at_their_dates(client):
    for t in client.get("/api/trades").get_json()["trades"][:7]:
        before = (date.fromisoformat(t["trade_date"]) - timedelta(days=1)).isoformat()
        assert get_state(client, t["id"], before)["status"] == "no_pactada"
        live = get_state(client, t["id"], t["trade_date"])
        assert live["status"] == "viva" and live["terms"] == t["params"]
        assert get_state(client, t["id"], t["maturity_date"])["status"] == "vencida"
