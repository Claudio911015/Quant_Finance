"""Alta de operaciones con fechas, `execution`, DELETE y rutas nuevas del corte 2 (T3)."""
import sqlite3
from datetime import date, timedelta

import pytest

from desk.api import events
from desk.api.db import connect

AS_OF = date(2026, 11, 10)
FWD = {"side": "buy", "notional_usd": 1e6, "days": 91, "strike": 19.0}
IRS = {"curve": "TIIE-F", "side": "payer", "notional": 1e6, "periods": 13, "fixed_rate": 0.07}
IRS_SOFR = {**IRS, "curve": "SOFR", "periods": 5}
CAP = {"curve": "TIIE-F", "cap_type": "cap", "notional": 1e6, "periods": 13, "strike": 0.07}
SWAPTION = {"curve": "TIIE-F", "swaption_type": "payer", "notional": 1e6, "strike": 0.07,
            "expiry_years": 0.25, "swap_tenor_years": 2.0}
BOND = {"curve": "TIIE-F", "face": 1e6, "coupon_rate": 0.08, "periods": 10, "frequency": 4.0}
EQ = {"option_type": "call", "spot": 55.0, "strike": 55.0, "volatility": 0.25, "rate": 0.07,
      "dividend_yield": 0.02, "maturity_years": 1.0, "quantity": 100.0}
FX_OPT = {"side": "buy", "option_type": "call", "notional_usd": 1e6, "days": 91, "strike": 19.0}


def _body(product="fx_forward", params=None, counterparty="Banco Test", **extra):
    return {"product": product, "counterparty": counterparty, "params": dict(params or FWD), **extra}


def _post(client, body):
    return client.post("/api/trades", json=body)


def _iso(d):
    return d.isoformat()


def _sql(app, query, args=()):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        return conn.execute(query, args).fetchall()
    finally:
        conn.close()


# ------------------------------------------------------------------------ alta con fechas

def test_create_with_dates_stores_three_dates_and_one_execution(app, client):
    r = _post(client, _body(trade_date="2026-11-01", start_date="2026-11-05", maturity_date="2027-02-05"))
    assert r.status_code == 201, r.get_json()
    t = r.get_json()
    assert (t["trade_date"], t["start_date"], t["maturity_date"]) == ("2026-11-01", "2026-11-05", "2027-02-05")
    assert t["maturity"] == t["maturity_date"] and t["params"]["days"] == 92
    rows = _sql(app, "SELECT type, event_date, data, prev_event_id FROM trade_events WHERE trade_id = ?", (t["id"],))
    assert rows == [("execution", "2026-11-01", "{}", None)]
    got = client.get("/api/trades/%d" % t["id"]).get_json()
    assert [e["type"] for e in got["events"]] == ["execution"]
    assert got["events"][0]["event_date"] == "2026-11-01" and got["events"][0]["trade_id"] == t["id"]
    assert {k: got[k] for k in t} == t


def test_defaults_come_from_mx_demo_as_of(client):
    t = _post(client, _body()).get_json()
    assert t["trade_date"] == t["start_date"] == _iso(AS_OF)
    assert t["maturity_date"] == _iso(AS_OF + timedelta(days=91))


def test_snapshot_in_body_sets_the_defaults(app, client):
    conn = sqlite3.connect(app.config["DESK_DB"])
    conn.execute(
        "INSERT INTO snapshots SELECT 'D1', label, synthetic, '2026-12-08', data FROM snapshots WHERE id = 'MX-DEMO'"
    )
    conn.commit()
    conn.close()
    t = _post(client, _body(snapshot="D1")).get_json()
    assert t["trade_date"] == t["start_date"] == "2026-12-08"
    assert t["maturity_date"] == _iso(date(2026, 12, 8) + timedelta(days=91))
    r = _post(client, _body(snapshot="NO-EXISTE"))
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"


def test_start_defaults_to_trade_date_and_trade_defaults_to_as_of(client):
    t = _post(client, _body(trade_date="2026-12-01")).get_json()
    assert t["trade_date"] == t["start_date"] == "2026-12-01"
    t = _post(client, _body(start_date="2026-12-01")).get_json()
    assert (t["trade_date"], t["start_date"]) == (_iso(AS_OF), "2026-12-01")


@pytest.mark.parametrize(
    "dates, field",
    [
        ({"trade_date": "2026-11-05", "start_date": "2026-11-04"}, "start_date"),
        ({"start_date": "2026-11-09"}, "start_date"),  # trade_date por defecto = 2026-11-10
        ({"start_date": "2026-11-20", "maturity_date": "2026-11-20"}, "maturity_date"),
        ({"start_date": "2026-11-20", "maturity_date": "2026-11-19"}, "maturity_date"),
        ({"maturity_date": "2026-11-10"}, "maturity_date"),
        ({"trade_date": "2026-11-05", "start_date": "2026-11-04", "maturity_date": "2026-11-01"}, "start_date"),
    ],
)
def test_date_order_rules_name_the_offending_field(client, dates, field):
    r = _post(client, _body(**dates))
    assert r.status_code == 400 and r.get_json()["field"] == field, r.get_json()


@pytest.mark.parametrize("field", ["trade_date", "start_date", "maturity_date"])
@pytest.mark.parametrize("bad", ["2026/11/10", "20261110", "2026-13-01", "2026-02-30", "10-11-2026", "", " 2026-11-10", 20261110, True, []])
def test_non_iso_dates_are_400_with_their_field(client, field, bad):
    r = _post(client, _body(**{field: bad}))
    assert r.status_code == 400 and r.get_json()["field"] == field, (field, bad, r.get_json())


def test_maturity_beyond_the_calendar_is_400_not_500(client):
    r = _post(client, _body(trade_date="9999-12-01", start_date="9999-12-01"))
    assert r.status_code == 400 and r.get_json()["field"] == "maturity_date"


def test_repeated_counterparty_reuses_its_id(app, client):
    before = _sql(app, "SELECT COUNT(*) FROM counterparties")[0][0]
    _post(client, _body(counterparty="Banco Nuevo"))
    _post(client, _body(counterparty="  Banco Nuevo  "))
    _post(client, _body(counterparty="Banco Alfa (sintético)"))  # ya sembrada
    assert _sql(app, "SELECT COUNT(*) FROM counterparties")[0][0] == before + 1
    assert _sql(app, "SELECT COUNT(DISTINCT counterparty_id) FROM trades WHERE id > 7")[0][0] == 2


# ------------------------------------------------------------------ plazo <-> fechas

def _mat(days):
    return _iso(AS_OF + timedelta(days=days))


def test_maturity_date_overrides_fx_tenor(client):
    for product, params in (("fx_forward", FWD), ("fx_option", FX_OPT)):
        t = _post(client, _body(product, params, maturity_date=_mat(100))).get_json()
        assert t["params"]["days"] == 100 and t["maturity_date"] == _mat(100)


def test_maturity_date_overrides_irs_and_is_adjusted_to_whole_periods(client):
    t = _post(client, _body("irs", IRS, maturity_date=_mat(100))).get_json()
    assert t["params"]["periods"] == 4 and t["maturity_date"] == _mat(112) == t["maturity"]
    t = _post(client, _body("irs", IRS_SOFR, maturity_date=_mat(400))).get_json()
    assert t["params"]["periods"] == 1 and t["maturity_date"] == _mat(365)
    t = _post(client, _body("irs", IRS, maturity_date=_mat(3))).get_json()  # nunca 0 periodos
    assert t["params"]["periods"] == 1 and t["maturity_date"] == _mat(28)


def test_maturity_date_overrides_cap_floor_like_irs(client):
    t = _post(client, _body("cap_floor", CAP, maturity_date=_mat(100))).get_json()
    assert t["params"]["periods"] == 4 and t["maturity_date"] == _mat(112)


def test_maturity_date_overrides_bond_and_is_adjusted(client):
    t = _post(client, _body("bond", BOND, maturity_date=_mat(400))).get_json()
    assert t["params"]["periods"] == 4 and t["maturity_date"] == _mat(365)  # round(400 × 4 / 365) = 4


def test_swaption_maturity_is_the_option_expiry(client):
    t = _post(client, _body("swaption", SWAPTION)).get_json()
    assert t["maturity_date"] == _mat(round(0.25 * 365)) and t["params"]["swap_tenor_years"] == 2.0
    t = _post(client, _body("swaption", SWAPTION, maturity_date=_mat(73))).get_json()
    assert t["params"]["expiry_years"] == pytest.approx(73 / 365) and t["maturity_date"] == _mat(73)
    assert t["params"]["swap_tenor_years"] == 2.0


def test_equity_option_maturity(client):
    t = _post(client, _body("equity_option", EQ)).get_json()
    assert t["maturity_date"] == _mat(365)
    t = _post(client, _body("equity_option", EQ, maturity_date=_mat(73))).get_json()
    assert t["params"]["maturity_years"] == pytest.approx(0.2) and t["maturity_date"] == _mat(73)


def test_tenor_that_leaves_the_product_bounds_is_400_on_maturity_date(client):
    r = _post(client, _body(maturity_date=_iso(AS_OF + timedelta(days=18251))))  # > MAX_DAYS
    assert r.status_code == 400 and r.get_json()["field"] == "maturity_date"
    r = _post(client, _body("equity_option", EQ, maturity_date=_iso(AS_OF + timedelta(days=365 * 51))))
    assert r.status_code == 400 and r.get_json()["field"] == "maturity_date"


def test_list_and_get_agree_and_expose_dates(client):
    t = _post(client, _body("irs", IRS, maturity_date=_mat(100))).get_json()
    listed = next(x for x in client.get("/api/trades").get_json()["trades"] if x["id"] == t["id"])
    assert listed == t
    r = client.get("/api/trades/%d" % t["id"])
    assert r.status_code == 200 and r.get_json()["maturity_date"] == _mat(112)


# ---------------------------------------------------------------------- eventos (insert_event)

def test_insert_event_chains_prev_event_id_and_loads_in_date_order(app, client):
    tid = _post(client, _body()).get_json()["id"]
    conn = connect(app.config["DESK_DB"])
    try:
        first = events.insert_event(conn, tid, "quantity_change", date(2026, 12, 1), {"notional": 2e6})
        second = events.insert_event(conn, tid, "quantity_change", date(2026, 11, 20), {"notional": 3e6})
        conn.commit()
        execution = events.load_events(conn, tid)[0]
        assert execution["type"] == "execution" and execution["prev_event_id"] is None
        assert first["prev_event_id"] == execution["id"] and second["prev_event_id"] == first["id"]
        loaded = events.load_events(conn, tid)
        assert [e["id"] for e in loaded] == [execution["id"], second["id"], first["id"]]  # (event_date, id)
        assert isinstance(loaded[1]["event_date"], date) and loaded[1]["data"] == {"notional": 3e6}
        assert [e["id"] for e in events.load_all_events(conn)[tid]] == [e["id"] for e in loaded]
        with pytest.raises(ValueError):
            events.insert_event(conn, tid, "novation", date(2026, 12, 1), {})
    finally:
        conn.close()
    got = client.get("/api/trades/%d" % tid).get_json()["events"]
    assert [e["event_date"] for e in got] == ["2026-11-10", "2026-11-20", "2026-12-01"]


# --------------------------------------------------------------------------------- DELETE

def test_delete_is_always_409_and_missing_is_404(client):
    r = client.delete("/api/trades/1")
    assert r.status_code == 409 and r.get_json() == {"error": "Una operación no se borra: termínala", "field": "id"}
    assert len(client.get("/api/trades").get_json()["trades"]) == 7
    r = client.delete("/api/trades/999")
    assert r.status_code == 404 and r.get_json()["field"] == "id"


# ----------------------------------------------------------------- rutas nuevas y sus 501

# Cada tarea posterior borra de aquí las rutas que implementa (T4: state y events; T5: fixings;
# T6: roll; T9: flows y pnl).
STUB_ROUTES = [
    ("T4", "get", "/api/trades/1/state?date=2026-11-10", None),
    ("T4", "post", "/api/trades/1/events",
     {"type": "quantity_change", "event_date": "2026-11-11", "data": {"notional": 1e6}}),
    ("T5", "get", "/api/fixings", None),
    ("T5", "post", "/api/fixings", {"index": "SOFR", "date": "2026-11-10", "value": 0.04}),
    ("T5", "post", "/api/fixings/csv", {"csv": "index,date,value\n"}),
    ("T6", "post", "/api/market/MX-DEMO/roll", {"id": "D1", "as_of": "2026-12-08"}),
    ("T9", "get", "/api/trades/1/flows?snapshot=MX-DEMO", None),
    ("T9", "get", "/api/pnl?from=MX-DEMO&to=MX-DEMO", None),
]


@pytest.mark.parametrize("task, method, url, body", STUB_ROUTES, ids=[r[2] for r in STUB_ROUTES])
def test_unimplemented_routes_answer_501_json(client, task, method, url, body):
    r = getattr(client, method)(url, json=body) if body is not None else getattr(client, method)(url)
    assert r.status_code == 501, (task, r.get_json())
    assert r.get_json() == {"error": "No implementado", "field": None}


@pytest.mark.parametrize(
    "method, url, body, status, field",
    [
        ("get", "/api/trades/999", None, 404, "id"),
        ("get", "/api/trades/abc", None, 404, "id"),
        ("get", "/api/trades/999/state?date=2026-11-10", None, 404, "id"),
        ("get", "/api/trades/1/state", None, 400, "date"),
        ("get", "/api/trades/1/state?date=", None, 400, "date"),
        ("get", "/api/trades/1/state?date=2026-13-01", None, 400, "date"),
        ("post", "/api/trades/999/events", {"type": "termination"}, 404, "id"),
        ("post", "/api/trades/1/events", None, 400, None),  # cuerpo vacío
        ("get", "/api/trades/999/flows?snapshot=MX-DEMO", None, 404, "id"),
        ("get", "/api/trades/1/flows", None, 400, "snapshot"),
        ("get", "/api/trades/1/flows?snapshot=%20", None, 400, "snapshot"),
        ("get", "/api/fixings?from=nope", None, 400, "from"),
        ("get", "/api/fixings?to=2026-02-30", None, 400, "to"),
        ("post", "/api/fixings/csv", {"csv": 5}, 400, "csv"),
        ("post", "/api/fixings/csv", {}, 400, "csv"),
        ("get", "/api/pnl", None, 400, "from"),
        ("get", "/api/pnl?from=MX-DEMO", None, 400, "to"),
        ("get", "/api/pnl?to=MX-DEMO", None, 400, "from"),
    ],
)
def test_new_routes_validate_before_delegating(client, method, url, body, status, field):
    send = getattr(client, method)
    r = send(url, json=body) if body is not None else send(url)
    assert r.status_code == status, r.get_json()
    assert r.get_json()["field"] == field
