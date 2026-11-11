"""Coberturas, C5: `POST /api/hedges/<id>/release {snapshot, amount?, cause}` (liberación de la reserva congelada)."""
import sqlite3
from datetime import date, timedelta

import pytest

from desk.api import hedges
from desk.api.tests.hedge_fixture import designate, load_fixings, market_forward, par_irs, roll
from desk.api.tests.hedge_fixture import frozen_clock  # noqa: F401  (autouse: reloj fijo)

D0 = date(2026, 11, 10)
LOAN_END = D0 + timedelta(days=364)
FWD_END = D0 + timedelta(days=20)
NOTIONAL = 500e6
TIIE = 0.07


def _cents(x):
    return int(round(x * 100))


def _loan():
    return {
        "index": "TIIE-F", "notional": NOTIONAL, "start_date": D0.isoformat(),
        "maturity_date": LOAN_END.isoformat(), "side": "pays_floating",
    }


def _dedesignate(client, hid, snapshot):
    r = client.post(
        "/api/hedges/%d/dedesignate" % hid, json={"snapshot": snapshot, "reason": "Prepago", "cause": "criteria_not_met"}
    )
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _positive_reserve(client):
    """Swap idéntico, un cierre a +35 días y desdesignación con ese snapshot: reserva congelada positiva."""
    trade = par_irs(client, "TIIE-F", NOTIONAL, D0, LOAN_END)
    r = designate(client, trade["id"], "floating_loan", _loan())
    assert r.status_code == 201, r.get_json()
    hid = r.get_json()["id"]
    as_of = date.fromisoformat(roll(client, "MX-DEMO", "D35", 35))
    load_fixings(client, "TIIE-F", D0, as_of, TIIE)
    detail = _dedesignate_after_close(client, hid, "D35")
    assert detail["oci_balance"] > 1000
    return hid, detail


def _negative_reserve(client):
    """Forward de compra a mercado cerrado antes de vencer (el USD baja): reserva congelada negativa."""
    trade = market_forward(client, "buy", 10e6, FWD_END)
    terms = {"amount_usd": 10e6, "date": FWD_END.isoformat(), "side": "buy_usd"}
    r = designate(client, trade["id"], "forecast_fx", terms)
    assert r.status_code == 201, r.get_json()
    hid = r.get_json()["id"]
    roll(client, "MX-DEMO", "F1", 5)
    roll(client, "MX-DEMO", "F2", 25)  # después del vencimiento del forward y del flujo cubierto: ya puede ocurrir
    detail = _dedesignate(client, hid, "F1")
    assert detail["oci_balance"] < -1000
    return hid, detail


def _dedesignate_after_close(client, hid, snapshot):
    assert client.post("/api/hedges/%d/periods" % hid, json={"snapshot": snapshot}).status_code == 201
    return _dedesignate(client, hid, snapshot)


def _release(client, hid, snapshot="D35", cause="flow_occurred", **extra):
    return client.post("/api/hedges/%d/release" % hid, json={"snapshot": snapshot, "cause": cause, **extra})


def _released(client, hid, snapshot="D35", cause="flow_occurred", **extra):
    r = _release(client, hid, snapshot, cause, **extra)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _ori_cents(detail):
    """Centavos con signo (+ = cargo) que lleva `ORI` entre los cierres y las liberaciones."""
    blocks = [p["entries"] for p in detail["periods"]]
    blocks += [e["data"]["entries"] for e in detail["events"] if e["type"] == "reserve_release"]
    return sum(_cents(e["debit"]) - _cents(e["credit"]) for b in blocks for e in b if e["account"] == hedges.ACC_OCI)


def _counts(app):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        return [conn.execute("SELECT COUNT(*) FROM hedge_events").fetchone()[0]]
    finally:
        conn.close()


# ------------------------------------------------------------------------- liberación total

def test_full_release_moves_the_reserve_to_the_recycling_account_and_zeroes_oci_exactly(client):
    hid, frozen = _positive_reserve(client)
    balance = frozen["oci_balance"]
    assert _ori_cents(frozen) == -_cents(balance)  # la reserva asentada es el saldo, redondeado

    detail = _released(client, hid)

    event = detail["events"][-1]
    assert event["type"] == "reserve_release" and event["event_date"] == (D0 + timedelta(days=35)).isoformat()
    data = event["data"]
    assert (data["snapshot"], data["cause"], data["amount"]) == ("D35", "flow_occurred", balance)
    assert (data["reserve_before"], data["reserve_after"]) == (balance, 0.0)
    cents = _cents(balance)
    assert [(e["account"], _cents(e["debit"]), _cents(e["credit"])) for e in data["entries"]] == [
        (hedges.ACC_OCI, cents, 0), (hedges.ACC_RECYCLING, 0, cents),
    ]
    assert _ori_cents(detail) == 0  # el acumulado de asientos de ORI queda en 0.00 exacto
    assert detail["oci_balance"] == 0.0 and detail["status"] == "desdesignada"
    assert detail["dedesignation"]["frozen_oci"] == balance  # lo congelado no cambia: el vigente es congelado − liberado
    assert client.get("/api/hedges").get_json()["hedges"][0]["oci_balance"] == 0.0
    assert client.get("/api/hedges/%d" % hid).get_json() == detail


def test_the_cause_chooses_the_counterpart_account(client):
    hid, _ = _positive_reserve(client)

    detail = _released(client, hid, cause="flow_no_longer_expected")

    accounts = [e["account"] for e in detail["events"][-1]["data"]["entries"]]
    assert accounts == [hedges.ACC_OCI, hedges.ACC_INEFFECTIVENESS]
    assert detail["events"][-1]["data"]["cause"] == "flow_no_longer_expected"


def test_a_release_on_a_later_snapshot_is_dated_there(client):
    hid, _ = _positive_reserve(client)
    roll(client, "MX-DEMO", "D50", 50)

    detail = _released(client, hid, "D50")

    assert detail["events"][-1]["event_date"] == (D0 + timedelta(days=50)).isoformat()
    assert detail["oci_balance"] == 0.0


# ------------------------------------------------------------------------- liberación parcial

def test_partial_releases_leave_the_rest_and_the_last_one_zeroes_oci(client):
    hid, frozen = _positive_reserve(client)
    balance = frozen["oci_balance"]
    part = round(balance * 0.4, 2)

    first = _released(client, hid, amount=part)
    assert first["oci_balance"] == pytest.approx(balance - part, abs=1e-9)
    assert first["events"][-1]["data"]["reserve_before"] == balance
    assert _ori_cents(first) == -_cents(balance) + _cents(part)
    assert first["dedesignation"]["frozen_oci"] == balance
    assert client.get("/api/hedges").get_json()["hedges"][0]["oci_balance"] == first["oci_balance"]

    second = _released(client, hid, cause="flow_no_longer_expected")  # el resto, a otra cuenta
    assert second["events"][-1]["data"]["amount"] == pytest.approx(balance - part, abs=1e-9)
    assert second["oci_balance"] == 0.0 and _ori_cents(second) == 0
    results = [
        sum(_cents(e["credit"]) - _cents(e["debit"]) for e in ev["data"]["entries"] if e["account"] != hedges.ACC_OCI)
        for ev in second["events"]
        if ev["type"] == "reserve_release"
    ]
    assert sum(results) == _cents(balance)  # a resultados se llevó todo el saldo, a centavos


def test_an_amount_typed_in_cents_that_equals_the_balance_counts_as_the_whole_release(client):
    hid, frozen = _positive_reserve(client)

    detail = _released(client, hid, amount=round(frozen["oci_balance"], 2))

    assert detail["oci_balance"] == 0.0 and _ori_cents(detail) == 0


# ------------------------------------------------------------------------- reserva negativa

def test_a_negative_reserve_is_released_with_a_negative_amount(client):
    hid, frozen = _negative_reserve(client)
    balance = frozen["oci_balance"]
    part = round(balance / 2, 2)

    first = _released(client, hid, "F2", amount=part)
    ori, target = first["events"][-1]["data"]["entries"]
    assert ori["account"] == hedges.ACC_OCI and ori["credit"] == -part and ori["debit"] == 0.0  # ORI tenía saldo deudor
    assert target["account"] == hedges.ACC_RECYCLING and target["debit"] == -part and target["credit"] == 0.0
    assert first["oci_balance"] == pytest.approx(balance - part, abs=1e-9)

    last = _released(client, hid, "F2")
    assert last["oci_balance"] == 0.0 and _ori_cents(last) == 0


def test_a_positive_amount_against_a_negative_reserve_changes_its_sign(app, client):
    hid, _ = _negative_reserve(client)
    before = _counts(app)

    r = _release(client, hid, "F2", amount=1000.0)

    assert r.status_code == 409 and r.get_json()["field"] == "amount"
    assert "signo" in r.get_json()["error"] and _counts(app) == before


# ------------------------------------------------------------------------- errores

def test_an_amount_beyond_the_balance_or_against_its_sign_is_409_on_amount(app, client):
    hid, frozen = _positive_reserve(client)
    balance = frozen["oci_balance"]
    before = _counts(app)

    r = _release(client, hid, amount=balance + 1.0)
    assert r.status_code == 409 and r.get_json()["field"] == "amount" and "excede" in r.get_json()["error"]
    r = _release(client, hid, amount=-balance)
    assert r.status_code == 409 and r.get_json()["field"] == "amount" and "signo" in r.get_json()["error"]
    r = _release(client, hid, amount=-1.0)
    assert r.status_code == 409 and r.get_json()["field"] == "amount"
    assert _counts(app) == before and client.get("/api/hedges/%d" % hid).get_json()["oci_balance"] == balance


def test_the_amount_must_be_a_real_number_of_at_least_a_cent(client):
    hid, _ = _positive_reserve(client)
    for bad in (0, 0.001, "x", True, [1]):
        r = _release(client, hid, amount=bad)
        assert r.status_code == 400 and r.get_json()["field"] == "amount", bad


def test_only_a_dedesignated_relationship_with_a_reserve_can_release(app, client):
    trade = par_irs(client, "TIIE-F", NOTIONAL, D0, LOAN_END)
    hid = designate(client, trade["id"], "floating_loan", _loan()).get_json()["id"]
    before = _counts(app)

    r = _release(client, hid, "MX-DEMO")  # sigue activa
    assert r.status_code == 409 and r.get_json()["field"] == "id"

    _dedesignate(client, hid, "MX-DEMO")  # desdesignada sin cierres: reserva 0
    r = _release(client, hid, "MX-DEMO")
    assert r.status_code == 409 and r.get_json()["field"] == "id" and "reserva" in r.get_json()["error"]
    assert _counts(app) == [before[0] + 1]  # solo la desdesignación


def test_after_a_full_release_there_is_nothing_left_to_release(client):
    hid, _ = _positive_reserve(client)
    _released(client, hid)

    r = _release(client, hid)

    assert r.status_code == 409 and r.get_json()["field"] == "id"


def test_the_date_cannot_be_before_the_last_event(app, client):
    hid, _ = _positive_reserve(client)  # último evento: la desdesignación del día 35
    before = _counts(app)

    r = _release(client, hid, "MX-DEMO")

    assert r.status_code == 409 and r.get_json()["field"] == "snapshot"
    assert _counts(app) == before


def test_after_a_release_an_earlier_snapshot_than_it_is_also_rejected(client):
    hid, _ = _positive_reserve(client)
    roll(client, "MX-DEMO", "D50", 50)
    _released(client, hid, "D50", amount=1000.0)

    r = _release(client, hid, "D35", amount=1000.0)

    assert r.status_code == 409 and r.get_json()["field"] == "snapshot"


def test_invalid_inputs_keep_their_field_and_write_nothing(app, client):
    hid, _ = _positive_reserve(client)
    before = _counts(app)
    cases = [
        ({"cause": "flow_occurred"}, 400, "snapshot"),
        ({"snapshot": "D35"}, 400, "cause"),
        ({"snapshot": "D35", "cause": "porque sí"}, 400, "cause"),
        ({"snapshot": "NO-EXISTE", "cause": "flow_occurred"}, 404, "snapshot"),
    ]
    for body, status, field in cases:
        r = client.post("/api/hedges/%d/release" % hid, json=body)
        assert (r.status_code, r.get_json()["field"]) == (status, field), body
    assert client.post("/api/hedges/%d/release" % hid, json=[]).status_code == 400
    for path in ("/api/hedges/999/release", "/api/hedges/abc/release"):
        r = client.post(path, json={"snapshot": "D35", "cause": "flow_occurred"})
        assert r.status_code == 404 and r.get_json()["field"] == "id"
    assert _counts(app) == before


def test_a_release_event_inserted_by_sql_sets_the_current_reserve(app, client):
    """`oci_balance` lee `reserve_after` del último `reserve_release`: sin residuo de punto flotante."""
    hid, frozen = _positive_reserve(client)
    conn = sqlite3.connect(app.config["DESK_DB"])
    conn.execute(
        "INSERT INTO hedge_events (relationship_id, type, event_date, data, created_at)"
        " VALUES (?, 'reserve_release', '2026-12-20', ?, 'x')",
        (hid, '{"snapshot": "D35", "cause": "flow_occurred", "amount": 1.0, "reserve_before": 2.0,'
              ' "reserve_after": 0.25, "entries": []}'),
    )
    conn.commit()
    conn.close()

    detail = client.get("/api/hedges/%d" % hid).get_json()

    assert detail["oci_balance"] == 0.25 and detail["dedesignation"]["frozen_oci"] == frozen["oci_balance"]


# ------------------------------------------------------------------------- F4: causas contrastadas con la partida

def test_flow_occurred_cannot_be_dated_before_the_first_date_of_the_hedged_item(app, client):
    hid, _ = _negative_reserve(client)  # el flujo pronosticado es FWD_END (+20 días); la reserva se congeló en F1 (+5)
    before = _counts(app)

    r = _release(client, hid, "F1", cause="flow_occurred")

    assert r.status_code == 409 and r.get_json()["field"] == "cause"
    assert FWD_END.isoformat() in r.get_json()["error"] and "ya no se espera" in r.get_json()["error"]
    assert _counts(app) == before and client.get("/api/hedges/%d" % hid).get_json()["oci_balance"] < 0
    roll(client, "MX-DEMO", "ON", 20)  # el día del flujo ya cuenta como ocurrido
    assert _release(client, hid, "ON", cause="flow_occurred", amount=-1000.0).status_code == 201


def test_flow_no_longer_expected_has_no_date_restriction(client):
    hid, _ = _negative_reserve(client)

    detail = _released(client, hid, "F1", cause="flow_no_longer_expected")

    assert detail["oci_balance"] == 0.0 and _ori_cents(detail) == 0
    assert detail["events"][-1]["data"]["entries"][1]["account"] == hedges.ACC_INEFFECTIVENESS


def test_a_loan_hedge_can_only_release_as_occurred_from_the_start_of_the_credit(client):
    trade = par_irs(client, "TIIE-F", NOTIONAL, D0, LOAN_END)
    later = D0 + timedelta(days=60)
    terms = {**_loan(), "start_date": later.isoformat()}  # crédito que arranca dentro de dos meses
    hid = designate(client, trade["id"], "floating_loan", terms).get_json()["id"]
    as_of = date.fromisoformat(roll(client, "MX-DEMO", "D35", 35))
    load_fixings(client, "TIIE-F", D0, as_of, TIIE)
    assert client.post("/api/hedges/%d/periods" % hid, json={"snapshot": "D35"}).status_code == 201
    assert _dedesignate(client, hid, "D35")["oci_balance"] != 0

    r = _release(client, hid, "D35", cause="flow_occurred")
    assert r.status_code == 409 and r.get_json()["field"] == "cause" and later.isoformat() in r.get_json()["error"]
