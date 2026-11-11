"""Calendario de flujos de la ficha (T9): liquidados y proyectados (R4, R8)."""
import json

import pytest

from desk.api.tests.conftest import insert_raw_trade
from desk.api.tests.test_valuation_aged import AS_OF, FWD, IRS, _book, _csv, _event, _iso, _roll, _rows

FLOWS = "/api/trades/%d/flows?snapshot=%s"


def _flows(client, trade_id, snap):
    r = client.get(FLOWS % (trade_id, snap))
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _split(body):
    settled = [f for f in body["flows"] if f["status"] == "settled"]
    projected = [f for f in body["flows"] if f["status"] == "projected"]
    return settled, projected


def _factor(rates):
    """Factor de capitalización diario ACT/360 calculado aparte de `qfpy`."""
    out = 1.0
    for r in rates:
        out *= 1.0 + r / 360.0
    return out


def test_irs_at_its_pact_date_lists_every_coupon_as_projected_and_they_add_up_to_the_pv(client):
    body = _flows(client, 1, "MX-DEMO")
    settled, projected = _split(body)
    assert body["id"] == 1 and body["snapshot"] == "MX-DEMO" and body["as_of"] == AS_OF.isoformat()
    assert settled == [] and body["warnings"] == []
    assert len(projected) == 26
    assert [f["date"] for f in projected] == [_iso(28 * (k + 1)) for k in range(26)]
    assert all(f["kind"] == "coupon" and f["currency"] == "MXN" for f in projected)
    assert all(0 < f["df"] <= 1 and f["pv"] == pytest.approx(f["amount"] * f["df"]) for f in projected)
    pv = _rows(client, "MX-DEMO")[1]["pv"]
    assert sum(f["pv"] for f in projected) == pytest.approx(pv, abs=1e-6)


def test_irs_valued_at_d1_lists_the_day_28_coupon_as_settled_and_the_rest_as_projected(client):
    _roll(client, "D1", 28)
    rates = [0.0700 + 0.0001 * i for i in range(28)]
    _csv(client, "TIIE-F", rates)
    body = _flows(client, 1, "D1")
    settled, projected = _split(body)
    assert body["warnings"] == []
    # cupón del día 28 de un payer 500e6 a 6.80 %: flotante - fijo, con τ = 28/360
    assert len(settled) == 1
    coupon = settled[0]
    assert coupon["date"] == _iso(28) and coupon["kind"] == "coupon" and coupon["currency"] == "MXN"
    expected = 500e6 * (_factor(rates) - 1.0) - 500e6 * 0.0680 * 28 / 360.0
    assert coupon["amount"] == pytest.approx(expected, rel=1e-12)
    assert coupon["df"] is None and coupon["pv"] is None
    assert len(projected) == 25 and projected[0]["date"] == _iso(56)
    assert all(f["df"] is not None and f["pv"] is not None for f in projected)
    assert body["flows"] == sorted(body["flows"], key=lambda f: f["date"])
    pv = _rows(client, "D1")[1]["pv"]
    assert sum(f["pv"] for f in projected) == pytest.approx(pv, abs=1e-6)


def test_missing_fixings_in_the_settled_period_warn_once_per_index(client):
    _roll(client, "D1", 28)
    body = _flows(client, 1, "D1")
    settled, _ = _split(body)
    assert len(settled) == 1
    assert [(w["code"], w["index"]) for w in body["warnings"]] == [("missing_fixing", "TIIE-F")]
    assert body["warnings"][0]["dates"] == [_iso(i) for i in range(28)]


def test_receiver_coupon_has_the_opposite_sign_of_the_payer(client):
    _roll(client, "D1", 28)
    rates = [0.0705] * 28
    _csv(client, "TIIE-F", rates)
    payer = _split(_flows(client, 1, "D1"))[0][0]["amount"]
    receiver_id = _book(client, "irs", {**IRS, "side": "receiver", "fixed_rate": 0.0680, "notional": 500e6})
    receiver = _split(_flows(client, receiver_id, "D1"))[0][0]["amount"]
    assert receiver == pytest.approx(-payer, rel=1e-12)


def test_quantity_change_mid_period_applies_the_new_notional_to_the_whole_coupon(client):
    _roll(client, "D1", 28)
    rates = [0.0702] * 28
    _csv(client, "TIIE-F", rates)
    _event(client, 1, "quantity_change", _iso(14), {"notional": 1000e6})
    coupon = _split(_flows(client, 1, "D1"))[0][0]
    expected = 1000e6 * (_factor(rates) - 1.0) - 1000e6 * 0.0680 * 28 / 360.0
    assert coupon["amount"] == pytest.approx(expected, rel=1e-12)


def test_last_coupon_at_maturity_is_settled_and_nothing_is_projected(client):
    tid = _book(client, "irs", {**IRS, "periods": 1, "notional": 1e8})  # vence el día 28
    _roll(client, "D29", 29)
    rates = [0.0710] * 28
    _csv(client, "TIIE-F", rates)
    settled, projected = _split(_flows(client, tid, "D29"))
    assert projected == [] and len(settled) == 1 and settled[0]["date"] == _iso(28)
    expected = 1e8 * (_factor(rates) - 1.0) - 1e8 * 0.07 * 28 / 360.0
    assert settled[0]["amount"] == pytest.approx(expected, rel=1e-12)


def test_terminated_swap_keeps_the_coupon_dated_on_the_termination_day_and_the_transfer(client):
    _roll(client, "D35", 35)
    _csv(client, "TIIE-F", [0.0705] * 28)
    _event(client, 1, "termination", _iso(28), {"amount": 1234.5})
    settled, projected = _split(_flows(client, 1, "D35"))
    assert projected == []  # terminada: nada por venir
    assert [(f["date"], f["kind"]) for f in settled] == [(_iso(28), "coupon"), (_iso(28), "transfer")]
    transfer = next(f for f in settled if f["kind"] == "transfer")
    assert transfer["amount"] == 1234.5 and transfer["currency"] == "MXN"


def test_termination_before_a_coupon_date_cancels_that_coupon(client):
    _roll(client, "D35", 35)
    _event(client, 1, "termination", _iso(10), {"amount": -500.0})
    settled, projected = _split(_flows(client, 1, "D35"))
    assert projected == []
    assert [(f["date"], f["kind"], f["amount"]) for f in settled] == [(_iso(10), "transfer", -500.0)]


def test_forward_settles_at_maturity_with_the_fix_and_has_no_projection(client):
    tid = _book(client, "fx_forward", {**FWD, "days": 20})
    _roll(client, "D35", 35)
    r = client.post("/api/fixings", json={"index": "USDMXN", "date": _iso(20), "value": 19.5})
    assert r.status_code == 201
    body = _flows(client, tid, "D35")
    settled, projected = _split(body)
    assert projected == [] and body["warnings"] == []
    assert settled == [
        {"date": _iso(20), "kind": "settlement", "status": "settled", "amount": pytest.approx(1e6 * (19.5 - 19.0)),
         "currency": "MXN", "df": None, "pv": None}
    ]


def test_forward_without_fix_settles_at_the_spot_with_a_warning(client):
    tid = _book(client, "fx_forward", {**FWD, "days": 20})
    _roll(client, "D35", 35)
    body = _flows(client, tid, "D35")
    settled, _ = _split(body)
    spot = client.get("/api/market/snapshots/D35").get_json()["fx"]["spot"]
    assert settled[0]["amount"] == pytest.approx(1e6 * (spot - 19.0))
    assert [(w["code"], w["index"], w["dates"]) for w in body["warnings"]] == [
        ("fx_fallback", "USDMXN", [_iso(20)])
    ]


def test_sofr_swap_coupon_is_listed_in_usd(client):
    _roll(client, "D370", 370)
    body = _flows(client, 3, "D370")  # irs SOFR de 5 periodos de 365 días
    settled, projected = _split(body)
    assert len(settled) == 1 and settled[0]["currency"] == "USD" and settled[0]["date"] == _iso(365)
    assert len(projected) == 4 and all(f["currency"] == "USD" for f in projected)
    assert "missing_fixing" in [w["code"] for w in body["warnings"]]


def test_bond_projected_flows_add_up_to_the_valuation_pv(client):
    params = {"curve": "TIIE-F", "face": 100.0, "coupon_rate": 0.08, "periods": 24, "frequency": 12.0}
    tid = _book(client, "bond", params)
    _roll(client, "D40", 40)
    body = _flows(client, tid, "D40")
    settled, projected = _split(body)
    assert settled == [] and len(projected) > 20
    assert all(f["kind"] == "coupon" and f["currency"] == "MXN" for f in projected)
    pv = _rows(client, "D40")[tid]["pv"]
    assert sum(f["pv"] for f in projected) == pytest.approx(pv, rel=1e-9)
    # bono a la fecha del pacto: lo que lista es lo que valúa
    at_pact = _flows(client, tid, "MX-DEMO")
    assert sum(f["pv"] for f in at_pact["flows"]) == pytest.approx(_rows(client, "MX-DEMO")[tid]["pv"], rel=1e-9)


@pytest.mark.parametrize("trade_id", [4, 6, 7])  # forward, opción FX y cap: sin calendario proyectado
def test_other_products_have_no_projected_flows(client, trade_id):
    body = _flows(client, trade_id, "MX-DEMO")
    assert body["flows"] == []


def test_cap_maturing_before_the_snapshot_warns_without_a_flow(client):
    tid = _book(client, "cap_floor", {"curve": "TIIE-F", "cap_type": "cap", "notional": 1e8,
                                       "strike": 0.07, "periods": 1})
    _roll(client, "D35", 35)
    body = _flows(client, tid, "D35")
    assert body["flows"] == []
    assert [(w["code"], w["index"], w["dates"]) for w in body["warnings"]] == [
        ("no_settlement", None, [_iso(28)])
    ]


def test_not_yet_agreed_trade_has_no_flows_of_any_kind(client):
    tid = _book(client, "irs", IRS, trade_date=_iso(20), start_date=_iso(20))
    body = _flows(client, tid, "MX-DEMO")
    assert body["flows"] == [] and body["warnings"] == []


def test_flows_reject_unknown_snapshot_and_trade(client):
    r = client.get(FLOWS % (1, "NOPE"))
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"
    r = client.get(FLOWS % (999, "MX-DEMO"))
    assert r.status_code == 404 and r.get_json()["field"] == "id"


def test_irs_without_fixed_rate_fails_clearly(app, client):
    params = {"curve": "TIIE-F", "side": "payer", "notional": 1e6, "periods": 13}
    tid = insert_raw_trade(app, "irs", json.dumps(params))
    r = client.get(FLOWS % (tid, "MX-DEMO"))
    assert r.status_code == 400 and "fixed_rate" in r.get_json()["error"]
