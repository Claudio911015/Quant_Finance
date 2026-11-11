import math
import sqlite3
import statistics

import pytest

from desk.api.qf import qfpy

FWD = {"side": "buy", "notional_usd": 1_000_000.0, "strike": 19.0, "days": 91}
IRS = {"curve": "TIIE-F", "side": "payer", "notional": 100e6, "periods": 13, "fixed_rate": 0.07}
EQ = {
    "option_type": "call", "spot": 55.0, "strike": 55.0, "volatility": 0.25,
    "rate": 0.07, "dividend_yield": 0.02, "maturity_years": 1.0, "quantity": 1000.0,
}


def _only(client, *trades):
    """Vacía el portafolio sembrado y deja solo `(producto, params)`."""
    for t in client.get("/api/trades").get_json()["trades"]:
        assert client.delete("/api/trades/%d" % t["id"]).status_code == 204
    for product, params in trades:
        r = client.post(
            "/api/trades",
            json={"product": product, "counterparty": "Banco Test", "params": params},
        )
        assert r.status_code == 201, r.get_json()


def _var(client, **over):
    body = {"snapshot": "MX-DEMO", "horizon_days": 1, "confidence": 0.99}
    body.update(over)
    return client.post("/api/risk/var", json=body)


def _ok(client, **over):
    r = _var(client, **over)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _factor(body, name):
    return next(f for f in body["factors"] if f["factor"] == name)


def _rel(a, b):
    return abs(a - b) / max(abs(b), 1e-300)


def test_single_fx_forward_matches_closed_form(client):
    _only(client, ("fx_forward", FWD))
    snap = client.get("/api/market/snapshots/MX-DEMO").get_json()
    spot = snap["fx"]["spot"]
    sigma = snap["factors"]["daily_vols"][snap["factors"]["names"].index("USDMXN")]
    delta = client.post(
        "/api/price/fx_forward", json=dict(FWD, snapshot="MX-DEMO")
    ).get_json()["risk"]["delta"]
    conf, h = 0.975, 10
    expected = abs(delta) * spot * sigma * statistics.NormalDist().inv_cdf(conf) * math.sqrt(h)

    body = _ok(client, confidence=conf, horizon_days=h)
    assert body["errors"] == []
    assert _rel(_factor(body, "USDMXN")["var_mxn"], expected) < 1e-6

    # sin vol en las curvas, el total es solo el factor FX
    flat = _ok(client, confidence=conf, horizon_days=h, factor_vols={"TIIE-F": 0, "SOFR": 0})
    assert _rel(flat["var_mxn"], expected) < 1e-6
    assert _factor(flat, "TIIE-F")["var_mxn"] == 0.0


def test_response_shape_and_factor_order(client):
    body = _ok(client, horizon_days=5, confidence=0.95)
    assert set(body) == {"snapshot", "var_mxn", "horizon_days", "confidence", "factors", "errors"}
    assert body["snapshot"] == "MX-DEMO"
    assert body["horizon_days"] == 5 and body["confidence"] == 0.95
    assert [f["factor"] for f in body["factors"]] == ["TIIE-F", "SOFR", "USDMXN"]
    assert [f["unit"] for f in body["factors"]] == ["bp", "bp", "ret"]
    assert all(
        set(f) == {"factor", "unit", "exposure_mxn", "daily_vol", "var_mxn"}
        for f in body["factors"]
    )
    snap = client.get("/api/market/snapshots/MX-DEMO").get_json()
    assert [f["daily_vol"] for f in body["factors"]] == snap["factors"]["daily_vols"]
    assert body["errors"] == []


def test_total_and_per_factor_vars_are_consistent_with_qfpy(client):
    body = _ok(client, horizon_days=3, confidence=0.99)
    snap = client.get("/api/market/snapshots/MX-DEMO").get_json()
    exposures = [f["exposure_mxn"] for f in body["factors"]]
    vols = [f["daily_vol"] for f in body["factors"]]
    total = qfpy.delta_normal_var(exposures, vols, snap["factors"]["correlations"], 0.99, 3)
    assert _rel(body["var_mxn"], total) < 1e-12
    z = statistics.NormalDist().inv_cdf(0.99)
    for f in body["factors"]:
        assert _rel(f["var_mxn"], abs(f["exposure_mxn"]) * f["daily_vol"] * z * math.sqrt(3)) < 1e-9
    assert body["var_mxn"] > 0


def test_rate_exposure_is_minus_parallel_dv01(client):
    _only(client, ("irs", IRS))
    dv01 = client.post(
        "/api/price/irs", json=dict(IRS, snapshot="MX-DEMO")
    ).get_json()["risk"]["dv01"]
    body = _ok(client)
    assert _rel(_factor(body, "TIIE-F")["exposure_mxn"], -dv01) < 1e-9
    assert _factor(body, "TIIE-F")["exposure_mxn"] > 0  # payer fijo gana si suben las tasas
    assert _factor(body, "SOFR")["exposure_mxn"] == 0.0
    assert _factor(body, "USDMXN")["exposure_mxn"] == 0.0


def test_equity_option_alone_has_zero_var(client):
    _only(client, ("equity_option", EQ))
    body = _ok(client)
    assert body["var_mxn"] == 0.0
    assert all(f["exposure_mxn"] == 0.0 and f["var_mxn"] == 0.0 for f in body["factors"])


def test_empty_portfolio_has_zero_var(client):
    _only(client)
    body = _ok(client)
    assert body["var_mxn"] == 0.0 and body["errors"] == []


def test_factor_vols_override_is_partial_and_per_request(client):
    base = _ok(client)
    over = _ok(client, factor_vols={"USDMXN": 0.02})
    assert _factor(over, "USDMXN")["daily_vol"] == 0.02
    assert _factor(over, "TIIE-F")["daily_vol"] == _factor(base, "TIIE-F")["daily_vol"]
    # no persiste en el snapshot
    again = _ok(client)
    assert _factor(again, "USDMXN")["daily_vol"] == _factor(base, "USDMXN")["daily_vol"]
    # factor_vols nulo equivale a ausente
    assert _ok(client, factor_vols=None)["var_mxn"] == base["var_mxn"]


def test_var_scales_with_sqrt_horizon(client):
    one = _ok(client, horizon_days=1)["var_mxn"]
    four = _ok(client, horizon_days=4)["var_mxn"]
    assert _rel(four, 2 * one) < 1e-9


def test_corrupt_trade_is_reported_and_excluded(app, client):
    _only(client, ("fx_forward", FWD))
    clean = _ok(client)
    conn = sqlite3.connect(app.config["DESK_DB"])
    cur = conn.execute(
        "INSERT INTO trades (product, counterparty, params, created_at) "
        "VALUES ('irs', 'Raw', '{no es json', 'x')"
    )
    corrupt_id = cur.lastrowid
    conn.commit()
    conn.close()
    body = _ok(client)
    assert [e["id"] for e in body["errors"]] == [corrupt_id]
    assert body["errors"][0]["error"]
    assert body["var_mxn"] == clean["var_mxn"]


@pytest.mark.parametrize(
    "over, field",
    [
        ({"horizon_days": 0}, "horizon_days"),
        ({"horizon_days": -1}, "horizon_days"),
        ({"horizon_days": "10"}, "horizon_days"),
        ({"horizon_days": True}, "horizon_days"),
        ({"horizon_days": None}, "horizon_days"),
        ({"confidence": 0}, "confidence"),
        ({"confidence": 1}, "confidence"),
        ({"confidence": 1.5}, "confidence"),
        ({"confidence": -0.1}, "confidence"),
        ({"confidence": "0.99"}, "confidence"),
        ({"confidence": False}, "confidence"),
        ({"factor_vols": [1, 2]}, "factor_vols"),
        ({"factor_vols": "TIIE-F"}, "factor_vols"),
        ({"factor_vols": {"EURMXN": 0.01}}, "factor_vols"),
        ({"factor_vols": {"TIIE-F": -1}}, "factor_vols"),
        ({"factor_vols": {"TIIE-F": "4"}}, "factor_vols"),
        ({"factor_vols": {"SOFR": True}}, "factor_vols"),
        ({"factor_vols": {"USDMXN": None}}, "factor_vols"),
    ],
)
def test_invalid_inputs_are_400_with_field(client, over, field):
    r = _var(client, **over)
    assert r.status_code == 400
    assert r.get_json()["field"] == field


def test_nan_and_inf_are_rejected(client):
    for bad in ("NaN", "Infinity"):
        raw = '{"snapshot": "MX-DEMO", "horizon_days": %s, "confidence": 0.99}' % bad
        r = client.post("/api/risk/var", data=raw, content_type="application/json")
        assert r.status_code == 400 and r.get_json()["field"] == "horizon_days"
        raw = (
            '{"snapshot": "MX-DEMO", "horizon_days": 1, "confidence": 0.99,'
            ' "factor_vols": {"TIIE-F": %s}}' % bad
        )
        r = client.post("/api/risk/var", data=raw, content_type="application/json")
        assert r.status_code == 400 and r.get_json()["field"] == "factor_vols"


def test_missing_required_fields_and_bad_snapshot(client):
    for body, status, field in [
        ({"horizon_days": 1, "confidence": 0.99}, 400, "snapshot"),
        ({"snapshot": "MX-DEMO", "confidence": 0.99}, 400, "horizon_days"),
        ({"snapshot": "MX-DEMO", "horizon_days": 1}, 400, "confidence"),
        ({"snapshot": "NOPE", "horizon_days": 1, "confidence": 0.99}, 404, "snapshot"),
    ]:
        r = client.post("/api/risk/var", json=body)
        assert r.status_code == status, body
        assert r.get_json()["field"] == field
    assert client.post("/api/risk/var", json=[]).status_code == 400
    assert client.post("/api/risk/var", data="{", content_type="application/json").status_code == 400
