"""Confirmación de liquidaciones (corte 5, T3): `POST /api/trades/<id>/settlements` y el `transfer`
de confirmación por `POST /api/trades/<id>/events`. Son solo registro: PV, P&L y flujos no cambian."""
import sqlite3
from datetime import date, timedelta

import pytest

from desk.api import portfolio
from desk.api.db import connect
from desk.api.ops_cashflows import confirmations
from desk.api.tests.hedge_fixture import load_fixings, market_forward, roll
from desk.api.tests.ops_fixture import fx_trade

AS_OF = date(2026, 11, 10)
COUPON = AS_OF + timedelta(days=28)  # primer cupón de la operación 1 (inicio = AS_OF, periodo de 28 días)
D1_AS_OF = AS_OF + timedelta(days=35)
BANK = 31000.0


def iso(d):
    return d.isoformat()


@pytest.fixture
def rolled(client):
    """Snapshot `D1` a +35 días con fijaciones TIIE-F: el cupón de la operación 1 ya se liquidó."""
    roll(client, "MX-DEMO", "D1", 35)
    load_fixings(client, "TIIE-F", AS_OF, D1_AS_OF, 0.07)
    return client


def settle(client, trade_id=1, day=COUPON, amount=BANK, currency="MXN", **extra):
    body = {"date": iso(day), "amount": amount, "currency": currency, **extra}
    return client.post("/api/trades/%d/settlements" % trade_id, json=body)


def events_in_db(app, trade_id):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        return conn.execute(
            "SELECT id, type, event_date, data FROM trade_events WHERE trade_id = ? ORDER BY id", (trade_id,)
        ).fetchall()
    finally:
        conn.close()


def settled_coupon(client, trade_id=1, snapshot="D1"):
    flows = client.get("/api/trades/%d/flows?snapshot=%s" % (trade_id, snapshot)).get_json()["flows"]
    return [f for f in flows if f["status"] == "settled"]


# ------------------------------------------------------------------------------ el caso feliz

def test_confirms_the_coupon_and_returns_the_difference_against_the_computed_amount(app, rolled):
    computed = settled_coupon(rolled)[0]
    assert computed["date"] == iso(COUPON) and computed["kind"] == "coupon"
    r = settle(rolled)
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["flow"] == {
        "date": iso(COUPON), "kind": "coupon", "amount": computed["amount"], "currency": "MXN"
    }
    assert body["difference"] == pytest.approx(BANK - computed["amount"], abs=1e-9)
    event = body["event"]
    assert event["trade_id"] == 1 and event["type"] == "transfer" and event["event_date"] == iso(COUPON)
    assert event["data"] == {
        "kind": "settlement_confirmed", "amount": BANK, "currency": "MXN",
        "flow_kind": "coupon", "computed_amount": computed["amount"],
    }
    rows = events_in_db(app, 1)
    assert [row[1] for row in rows] == ["execution", "transfer"]
    assert event["id"] == rows[-1][0] and event["prev_event_id"] == rows[0][0]


def test_the_confirmation_is_listed_in_the_trade_and_seen_by_the_calendar_helper(app, rolled):
    assert settle(rolled).status_code == 201
    events = rolled.get("/api/trades/1").get_json()["events"]
    assert [e["data"].get("kind") for e in events if e["type"] == "transfer"] == ["settlement_confirmed"]
    conn = connect(app.config["DESK_DB"])
    try:
        found = confirmations(portfolio.get_trade(conn, 1))
    finally:
        conn.close()
    assert list(found) == [(COUPON, "MXN")] and found[(COUPON, "MXN")]["amount"] == BANK


def test_zero_and_negative_amounts_are_accepted(rolled):
    assert settle(rolled, amount=0).status_code == 201
    assert settle(rolled, day=COUPON + timedelta(days=28), amount=-5.0).status_code == 409  # aún no ocurre
    # Otra operación, otro monto negativo.
    assert settle(rolled, trade_id=2, amount=-120.5).status_code == 201


def test_a_forward_settlement_can_be_confirmed(rolled):
    fwd = market_forward(rolled, "buy", 5e6, AS_OF + timedelta(days=20))
    load_fixings(rolled, "USDMXN", AS_OF, D1_AS_OF, 19.9)
    maturity = date.fromisoformat(fwd["maturity_date"])
    computed = [f for f in settled_coupon(rolled, fwd["id"]) if f["kind"] == "settlement"]
    assert len(computed) == 1 and computed[0]["date"] == iso(maturity)
    r = settle(rolled, trade_id=fwd["id"], day=maturity, amount=computed[0]["amount"] + 50.0)
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["difference"] == pytest.approx(50.0, abs=1e-6)
    assert body["flow"]["kind"] == "settlement" and body["event"]["data"]["flow_kind"] == "settlement"


# ---------------------------------------------------------------------------- rechazos 409

def test_the_same_flow_cannot_be_confirmed_twice(app, rolled):
    assert settle(rolled).status_code == 201
    r = settle(rolled, amount=1.0)
    assert r.status_code == 409 and r.get_json()["field"] == "date"
    assert "ya está confirmado" in r.get_json()["error"]
    assert [row[1] for row in events_in_db(app, 1)] == ["execution", "transfer"]


def test_a_date_without_a_derived_flow_is_409(app, rolled):
    r = settle(rolled, day=AS_OF + timedelta(days=3))
    assert r.status_code == 409 and r.get_json()["field"] == "date"
    assert r.get_json()["error"] == "No hay flujo derivado el %s" % iso(AS_OF + timedelta(days=3))
    assert [row[1] for row in events_in_db(app, 1)] == ["execution"]


def test_a_date_after_the_snapshot_as_of_is_409(app, rolled):
    later = D1_AS_OF + timedelta(days=1)
    r = settle(rolled, day=later)
    assert r.status_code == 409 and r.get_json()["field"] == "date"
    assert r.get_json()["error"] == "El flujo del %s aún no ocurre al %s" % (iso(later), iso(D1_AS_OF))
    assert [row[1] for row in events_in_db(app, 1)] == ["execution"]


def test_the_same_date_is_not_a_flow_in_an_earlier_snapshot(app, rolled):
    """Con `snapshot` explícito se juzga contra ese snapshot: el cupón del día 28 no ocurre al 2026-11-10."""
    r = settle(rolled, snapshot="MX-DEMO")
    assert r.status_code == 409 and r.get_json()["field"] == "date"
    assert settle(rolled, snapshot="D1").status_code == 201


def test_the_default_snapshot_is_the_one_with_the_latest_as_of(rolled):
    # Solo D1 (as_of 2026-12-15) conoce el cupón del 2026-12-08: sin `snapshot` se usa D1.
    assert settle(rolled).status_code == 201


def test_a_currency_that_is_not_the_flows_is_409(app, rolled):
    r = settle(rolled, currency="USD")
    assert r.status_code == 409 and r.get_json()["field"] == "currency"
    assert [row[1] for row in events_in_db(app, 1)] == ["execution"]


def test_a_termination_transfer_is_not_a_confirmable_flow(app, rolled):
    t = rolled.post(
        "/api/trades/1/events",
        json={"type": "termination", "event_date": "2026-12-10", "data": {"amount": 1000.0}},
    )
    assert t.status_code == 201, t.get_json()
    before = events_in_db(app, 1)
    r = settle(rolled, day=date(2026, 12, 10), amount=1000.0)
    assert r.status_code == 409 and r.get_json()["field"] == "date"
    assert events_in_db(app, 1) == before


# ---------------------------------------------------------------------------- validación

def test_unknown_trade_is_404_id_even_with_an_unreadable_body(client):
    r = client.post("/api/trades/999/settlements", data="no es json")
    assert r.status_code == 404 and r.get_json()["field"] == "id"
    for raw in ("abc", "99999999999999999999"):
        r = client.post("/api/trades/%s/settlements" % raw, json={})
        assert r.status_code == 404 and r.get_json()["field"] == "id"


@pytest.mark.parametrize(
    "patch, field",
    [
        ({"date": None}, "date"),
        ({"date": "2026-13-45"}, "date"),
        ({"date": "08/12/2026"}, "date"),
        ({"date": 20261208}, "date"),
        ({"amount": "x"}, "amount"),
        ({"amount": None}, "amount"),
        ({"amount": True}, "amount"),
        ({"amount": [1]}, "amount"),
        ({"amount": 1e14}, "amount"),
        ({"amount": -1e14}, "amount"),
        ({"currency": "EUR"}, "currency"),
        ({"currency": "mxn"}, "currency"),
        ({"currency": None}, "currency"),
        ({"currency": 5}, "currency"),
        ({"snapshot": 5}, "snapshot"),
    ],
)
def test_invalid_fields_are_400_and_write_nothing(app, rolled, patch, field):
    body = {"date": iso(COUPON), "amount": BANK, "currency": "MXN", **patch}
    r = rolled.post("/api/trades/1/settlements", json=body)
    assert r.status_code == 400 and r.get_json()["field"] == field, r.get_json()
    assert [row[1] for row in events_in_db(app, 1)] == ["execution"]


def test_not_a_number_literal_is_400_amount(app, rolled):
    raw = '{"date": "%s", "amount": NaN, "currency": "MXN"}' % iso(COUPON)
    r = rolled.post("/api/trades/1/settlements", data=raw, content_type="application/json")
    assert r.status_code == 400 and r.get_json()["field"] == "amount"
    assert [row[1] for row in events_in_db(app, 1)] == ["execution"]


def test_unknown_snapshot_is_404_snapshot(app, rolled):
    r = settle(rolled, snapshot="NO-EXISTE")
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"
    assert [row[1] for row in events_in_db(app, 1)] == ["execution"]


def test_the_first_error_in_the_documented_order_wins(rolled):
    """date -> amount -> currency -> snapshot -> fecha futura -> sin flujo -> moneda -> duplicado."""
    body = {"date": "x", "amount": "x", "currency": "EUR", "snapshot": "NO-EXISTE"}
    post = lambda b: rolled.post("/api/trades/1/settlements", json=b)  # noqa: E731
    assert post(body).get_json()["field"] == "date"
    body["date"] = iso(D1_AS_OF + timedelta(days=1))
    assert post(body).get_json()["field"] == "amount"
    body["amount"] = 1.0
    assert post(body).get_json()["field"] == "currency"
    body["currency"] = "USD"
    r = post(body)
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"
    body["snapshot"] = "D1"
    r = post(body)
    assert r.status_code == 409 and "aún no ocurre" in r.get_json()["error"]
    body["date"] = iso(AS_OF + timedelta(days=3))
    assert "No hay flujo derivado" in post(body).get_json()["error"]
    body["date"] = iso(COUPON)
    r = post(body)
    assert r.status_code == 409 and r.get_json()["field"] == "currency"
    body["currency"] = "MXN"
    assert post(body).status_code == 201
    r = post(body)
    assert r.status_code == 409 and r.get_json()["field"] == "date" and "ya está confirmado" in r.get_json()["error"]


def test_an_unreadable_trade_is_a_400_and_writes_nothing(app, rolled):
    from desk.api.tests.conftest import insert_raw_trade

    tid = insert_raw_trade(app, "irs", "no es json")
    before = events_in_db(app, tid)
    r = settle(rolled, trade_id=tid)
    assert r.status_code == 400 and r.get_json()["error"].startswith("No se pudo valuar"), r.get_json()
    assert events_in_db(app, tid) == before


# ------------------------------------------------------------------ sin efecto en PV, P&L ni flujos

def test_a_confirmation_changes_neither_valuation_nor_pnl_nor_flows(rolled):
    val_url, pnl_url = "/api/portfolio/valuation?snapshot=D1", "/api/pnl?from=MX-DEMO&to=D1"
    flows_url = "/api/trades/1/flows?snapshot=D1"
    val_before, pnl_before = rolled.get(val_url).get_json(), rolled.get(pnl_url).get_json()
    flows_before = rolled.get(flows_url).get_json()
    state_before = rolled.get("/api/trades/1/state?date=%s" % iso(D1_AS_OF)).get_json()

    assert settle(rolled, amount=BANK + 12345.0).status_code == 201

    val_after, pnl_after = rolled.get(val_url).get_json(), rolled.get(pnl_url).get_json()
    flows_after = rolled.get(flows_url).get_json()
    assert flows_after == flows_before
    assert [f for f in flows_after["flows"] if f["kind"] == "transfer"] == []
    assert rolled.get("/api/trades/1/state?date=%s" % iso(D1_AS_OF)).get_json() == state_before

    rows_before = {r["id"]: r for r in val_before["rows"]}
    rows_after = {r["id"]: r for r in val_after["rows"]}
    assert rows_before.keys() == rows_after.keys()
    for tid, row in rows_before.items():
        for name in ("pv", "pv_mxn"):
            assert rows_after[tid][name] == pytest.approx(row[name], abs=1e-12)
    assert val_after["total_mxn"] == pytest.approx(val_before["total_mxn"], abs=1e-12)

    p_before = {r["id"]: r for r in pnl_before["rows"]}
    p_after = {r["id"]: r for r in pnl_after["rows"]}
    assert p_before.keys() == p_after.keys()
    for tid, row in p_before.items():
        for name in ("pv_from", "pv_to", "settled", "pnl"):
            assert p_after[tid][name] == pytest.approx(row[name], abs=1e-12)
    assert pnl_after["total_mxn"] == pytest.approx(pnl_before["total_mxn"], abs=1e-12)


# --------------------------------------------------------------- por `POST /api/trades/<id>/events`

def confirmation_event(day=COUPON, **data):
    data = {"kind": "settlement_confirmed", "amount": BANK, "currency": "MXN", **data}
    return {"type": "transfer", "event_date": iso(day), "data": data}


def test_events_route_registers_the_confirmation_and_wraps_the_event(app, rolled):
    r = rolled.post("/api/trades/1/events", json=confirmation_event())
    assert r.status_code == 201, r.get_json()
    events = r.get_json()["events"]
    assert len(events) == 1
    e = events[0]
    assert e["type"] == "transfer" and e["event_date"] == iso(COUPON) and e["trade_id"] == 1
    computed = settled_coupon(rolled)[0]["amount"]
    assert e["data"] == {
        "kind": "settlement_confirmed", "amount": BANK, "currency": "MXN",
        "flow_kind": "coupon", "computed_amount": computed,
    }
    assert [row[1] for row in events_in_db(app, 1)] == ["execution", "transfer"]


def test_events_route_applies_the_same_validation_as_settlements(app, rolled):
    post = lambda b: rolled.post("/api/trades/1/events", json=b)  # noqa: E731
    # La fecha va en `event_date` en este cuerpo.
    r = post({"type": "transfer", "data": {"kind": "settlement_confirmed", "amount": 1.0, "currency": "MXN"}})
    assert r.status_code == 400 and r.get_json()["field"] == "event_date"
    assert post(confirmation_event(amount="x")).get_json()["field"] == "amount"
    assert post(confirmation_event(currency="EUR")).get_json()["field"] == "currency"
    assert post(confirmation_event(snapshot="NO-EXISTE")).status_code == 404
    r = post(confirmation_event(day=AS_OF + timedelta(days=3)))
    assert r.status_code == 409 and r.get_json()["field"] == "event_date"
    assert post(confirmation_event(currency="USD")).get_json()["field"] == "currency"
    assert [row[1] for row in events_in_db(app, 1)] == ["execution"]
    assert post(confirmation_event()).status_code == 201
    r = post(confirmation_event())
    assert r.status_code == 409 and r.get_json()["field"] == "event_date"
    assert [row[1] for row in events_in_db(app, 1)] == ["execution", "transfer"]


@pytest.mark.parametrize(
    "data", [{"amount": 1.0}, {"kind": "otro", "amount": 1.0}, {"kind": None}, {}, "settlement_confirmed", None]
)
def test_any_other_transfer_stays_a_400_type(app, rolled, data):
    body = {"type": "transfer", "event_date": iso(COUPON)}
    if data is not None:
        body["data"] = data
    r = rolled.post("/api/trades/1/events", json=body)
    assert r.status_code == 400 and r.get_json()["field"] == "type"
    assert [row[1] for row in events_in_db(app, 1)] == ["execution"]


def test_a_later_confirmation_does_not_block_an_earlier_lifecycle_event(app, rolled):
    assert settle(rolled).status_code == 201  # confirmación con fecha 2026-12-08
    qc = {"type": "quantity_change", "event_date": "2026-11-20", "data": {"notional": 400e6}}
    r = rolled.post("/api/trades/1/events", json=qc)
    assert r.status_code == 201, r.get_json()
    assert [row[1] for row in events_in_db(app, 1)] == ["execution", "transfer", "quantity_change"]


def test_an_earlier_confirmation_is_accepted_after_a_later_lifecycle_event(app, rolled):
    qc = {"type": "quantity_change", "event_date": "2026-12-10", "data": {"notional": 400e6}}
    assert rolled.post("/api/trades/1/events", json=qc).status_code == 201
    # La confirmación es del 2026-12-08, anterior al último evento (2026-12-10).
    r = settle(rolled)
    assert r.status_code == 201, r.get_json()
    assert [row[1] for row in events_in_db(app, 1)] == ["execution", "quantity_change", "transfer"]
    # Y el orden cronológico de los demás eventos sigue exigiéndose contra el último evento real.
    early = {"type": "quantity_change", "event_date": "2026-12-09", "data": {"notional": 300e6}}
    r = rolled.post("/api/trades/1/events", json=early)
    assert r.status_code == 409 and r.get_json()["field"] == "event_date"


def test_the_chronological_rule_still_holds_without_confirmations(client):
    t = fx_trade(client, "fx_forward", days=60)
    first = {"type": "quantity_change", "event_date": "2026-11-20", "data": {"notional": 4e6}}
    assert client.post("/api/trades/%d/events" % t["id"], json=first).status_code == 201
    back = {"type": "quantity_change", "event_date": "2026-11-15", "data": {"notional": 3e6}}
    r = client.post("/api/trades/%d/events" % t["id"], json=back)
    assert r.status_code == 409 and r.get_json()["field"] == "event_date"


# ------------------------------------------------- las confirmaciones no entran en la cadena del ciclo de vida

def test_confirmations_do_not_enter_the_lifecycle_prev_event_chain(app, rolled):
    """Auditoría corte 5: una terminación posterior apuntaba a la confirmación (de fecha anterior)."""
    execution_id = events_in_db(app, 1)[0][0]
    first = settle(rolled).get_json()["event"]
    assert first["prev_event_id"] == execution_id
    term = rolled.post("/api/trades/1/events", json={
        "type": "termination", "event_date": iso(D1_AS_OF), "data": {"amount": 10.0},
    })
    assert term.status_code == 201, term.get_json()
    termination, transfer = term.get_json()["events"]
    assert termination["prev_event_id"] == execution_id
    assert transfer["prev_event_id"] == termination["id"]
