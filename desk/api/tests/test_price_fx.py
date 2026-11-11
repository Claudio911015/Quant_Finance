import math
from datetime import date

import pytest

from desk.api import db, market
from desk.api.pricing import PRODUCTS
from desk.api.qf import qfpy

FWD = {"side": "buy", "notional_usd": 1_000_000.0, "strike": 19.0, "days": 91}
OPT = dict(FWD, option_type="call")
EQ = {
    "option_type": "call",
    "spot": 55.0,
    "strike": 55.0,
    "volatility": 0.25,
    "rate": 0.07,
    "dividend_yield": 0.02,
    "maturity_years": 1.0,
    "quantity": 1000.0,
}


@pytest.fixture
def ctx(app, tmp_path):
    conn = db.connect(tmp_path / "t.db")
    try:
        yield market.load_context(conn, "MX-DEMO")
    finally:
        conn.close()


def _price(client, product, params, snapshot="MX-DEMO"):
    return client.post("/api/price/%s" % product, json=dict(params, snapshot=snapshot))


def _ok(client, product, params):
    resp = _price(client, product, params)
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


def _bad(client, product, params, field):
    resp = _price(client, product, params)
    assert resp.status_code == 400
    body = resp.get_json()
    assert set(body) == {"error", "field"}
    assert body["error"]
    assert body["field"] == field


def _rel(a, b):
    return abs(a - b) / max(abs(b), 1e-12)


# ----------------------------------------------------------------------------- fx_forward


def test_fx_forward_matches_interest_parity(client, ctx):
    body = _ok(client, "fx_forward", FWD)
    t = FWD["days"] / 365
    df_usd = ctx.curves["SOFR"].discount_factor(t)
    df_mxn = ctx.curves["TIIE-F"].discount_factor(t)
    expected = FWD["notional_usd"] * (ctx.spot * df_usd - FWD["strike"] * df_mxn)
    assert _rel(body["pv"], expected) < 1e-8
    assert body["product"] == "fx_forward"
    assert body["currency"] == "MXN"
    assert body["pv_mxn"] == body["pv"]
    assert set(body["risk"]) == {"delta", "forward"}
    assert _rel(body["risk"]["forward"], ctx.spot * df_usd / df_mxn) < 1e-8
    assert _rel(body["risk"]["delta"], FWD["notional_usd"] * df_usd) < 1e-8
    assert body["cashflows"] is None
    assert body["details"] == {}


def test_fx_forward_sell_is_minus_buy(client):
    buy = _ok(client, "fx_forward", FWD)
    sell = _ok(client, "fx_forward", dict(FWD, side="sell"))
    assert _rel(sell["pv"], -buy["pv"]) < 1e-12
    assert _rel(sell["risk"]["delta"], -buy["risk"]["delta"]) < 1e-12
    assert sell["risk"]["forward"] == buy["risk"]["forward"]


@pytest.mark.parametrize(
    "mutation, field",
    [
        ({"side": None}, "side"),
        ({"side": "long"}, "side"),
        ({"notional_usd": None}, "notional_usd"),
        ({"notional_usd": -5}, "notional_usd"),
        ({"notional_usd": 0}, "notional_usd"),
        ({"strike": None}, "strike"),
        ({"strike": -19}, "strike"),
        ({"days": None}, "days"),
        ({"days": 0}, "days"),
        ({"days": 91.5}, "days"),
        ({"days": True}, "days"),
    ],
)
def test_fx_forward_validation(client, mutation, field):
    params = dict(FWD)
    for k, v in mutation.items():
        if v is None:
            params.pop(k)
        else:
            params[k] = v
    _bad(client, "fx_forward", params, field)


def test_fx_forward_unknown_snapshot_is_404(client):
    resp = _price(client, "fx_forward", FWD, snapshot="NOPE")
    assert resp.status_code == 404
    assert resp.get_json()["field"] == "snapshot"


# ----------------------------------------------------------------------------- fx_option


def test_fx_option_put_call_parity_against_forward(client):
    call = _ok(client, "fx_option", dict(OPT, option_type="call"))
    put = _ok(client, "fx_option", dict(OPT, option_type="put"))
    fwd = _ok(client, "fx_forward", FWD)
    assert _rel(call["pv"] - put["pv"], fwd["pv"]) < 1e-8
    assert call["pv"] > 0 and put["pv"] > 0


def test_fx_option_response_shape(client):
    body = _ok(client, "fx_option", OPT)
    assert body["product"] == "fx_option"
    assert body["currency"] == "MXN"
    assert body["pv_mxn"] == body["pv"]
    assert set(body["risk"]) == {"delta", "gamma", "vega", "forward", "vol"}
    assert body["risk"]["vol"] > 0
    assert body["cashflows"] is None


def test_fx_option_sell_is_minus_buy(client):
    buy = _ok(client, "fx_option", OPT)
    sell = _ok(client, "fx_option", dict(OPT, side="sell"))
    assert _rel(sell["pv"], -buy["pv"]) < 1e-12
    for k in ("delta", "gamma", "vega"):
        assert _rel(sell["risk"][k], -buy["risk"][k]) < 1e-12
    assert sell["risk"]["forward"] == buy["risk"]["forward"]
    assert sell["risk"]["vol"] == buy["risk"]["vol"]


@pytest.mark.parametrize(
    "mutation, field",
    [
        ({"side": None}, "side"),
        ({"option_type": None}, "option_type"),
        ({"option_type": "straddle"}, "option_type"),
        ({"notional_usd": None}, "notional_usd"),
        ({"notional_usd": -1}, "notional_usd"),
        ({"strike": None}, "strike"),
        ({"strike": 0}, "strike"),
        ({"days": None}, "days"),
        ({"days": -3}, "days"),
    ],
)
def test_fx_option_validation(client, mutation, field):
    params = dict(OPT)
    for k, v in mutation.items():
        if v is None:
            params.pop(k)
        else:
            params[k] = v
    _bad(client, "fx_option", params, field)


# ----------------------------------------------------------------------------- equity_option


def test_equity_option_matches_black_scholes_times_quantity(client):
    body = _ok(client, "equity_option", EQ)
    p = qfpy.OptionParams()
    p.spot, p.strike, p.volatility = EQ["spot"], EQ["strike"], EQ["volatility"]
    p.riskFreeRate, p.dividendYield, p.maturity = EQ["rate"], EQ["dividend_yield"], 1.0
    p.type = qfpy.OptionType.Call
    p.exercise = qfpy.ExerciseType.European
    bs = qfpy.black_scholes(p)
    q = EQ["quantity"]
    assert body["product"] == "equity_option"
    assert body["currency"] == "MXN"
    assert _rel(body["pv"], q * bs["price"]) < 1e-12
    assert body["pv_mxn"] == body["pv"]
    assert set(body["risk"]) == {"delta", "gamma", "vega", "theta", "rho"}
    for k in body["risk"]:
        assert _rel(body["risk"][k], q * bs[k]) < 1e-12
    assert body["cashflows"] is None


def test_equity_option_quantity_defaults_to_one(client):
    params = {k: v for k, v in EQ.items() if k != "quantity"}
    one = _ok(client, "equity_option", params)
    many = _ok(client, "equity_option", dict(params, quantity=10))
    assert _rel(many["pv"], 10 * one["pv"]) < 1e-12


def test_equity_option_does_not_depend_on_market(client):
    base = _ok(client, "equity_option", EQ)
    moved = client.put("/api/market/snapshots/MX-DEMO", json={"spot": 25.0})
    assert moved.status_code == 200
    assert _ok(client, "equity_option", EQ)["pv"] == base["pv"]


@pytest.mark.parametrize(
    "mutation, field",
    [
        ({"option_type": None}, "option_type"),
        ({"option_type": "binary"}, "option_type"),
        ({"spot": None}, "spot"),
        ({"spot": -1}, "spot"),
        ({"strike": None}, "strike"),
        ({"strike": 0}, "strike"),
        ({"volatility": None}, "volatility"),
        ({"volatility": 0}, "volatility"),
        ({"rate": None}, "rate"),
        ({"rate": "7%"}, "rate"),
        ({"dividend_yield": None}, "dividend_yield"),
        ({"dividend_yield": -0.01}, "dividend_yield"),
        ({"maturity_years": None}, "maturity_years"),
        ({"maturity_years": 0}, "maturity_years"),
        ({"quantity": 0}, "quantity"),
        ({"quantity": -5}, "quantity"),
    ],
)
def test_equity_option_validation(client, mutation, field):
    params = dict(EQ)
    for k, v in mutation.items():
        if v is None:
            params.pop(k)
        else:
            params[k] = v
    _bad(client, "equity_option", params, field)


# ----------------------------------------------------------------------------- registro, pv_mxn y describe


def test_registered_in_products():
    assert {"fx_forward", "fx_option", "equity_option"} <= set(PRODUCTS)


def test_pv_mxn_matches_price(client, ctx):
    for name, params in (("fx_forward", FWD), ("fx_option", OPT), ("equity_option", EQ)):
        prod = PRODUCTS[name]
        norm = prod.validate(params)
        assert math.isclose(prod.pv_mxn(norm, ctx), prod.price(norm, ctx)["pv_mxn"], rel_tol=1e-12)


def test_describe():
    as_of = date(2026, 11, 10)
    fwd = PRODUCTS["fx_forward"].describe(PRODUCTS["fx_forward"].validate(FWD), as_of)
    assert fwd == {"notional": 1_000_000.0, "currency": "USD", "maturity": "2027-02-09"}
    opt = PRODUCTS["fx_option"].describe(PRODUCTS["fx_option"].validate(OPT), as_of)
    assert opt == fwd
    eq = PRODUCTS["equity_option"].describe(PRODUCTS["equity_option"].validate(EQ), as_of)
    assert eq == {"notional": 55_000.0, "currency": "MXN", "maturity": "2027-11-10"}
