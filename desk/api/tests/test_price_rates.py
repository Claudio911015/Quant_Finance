"""Pricers de tasas: irs, cap_floor, swaption, bond (R2, R5)."""
from datetime import date, timedelta

import pytest

from desk.api.db import get_conn
from desk.api.market import load_context
from desk.api.pricing import PRODUCTS

SNAP = "MX-DEMO"


def post(client, product, **body):
    body.setdefault("snapshot", SNAP)
    return client.post("/api/price/%s" % product, json=body)


def ok(client, product, **body):
    r = post(client, product, **body)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def assert_error(r, status, field):
    assert r.status_code == status, r.get_json()
    body = r.get_json()
    assert body["field"] == field
    assert isinstance(body["error"], str) and body["error"]


IRS = {"curve": "TIIE-F", "side": "payer", "notional": 1e8, "periods": 13}
CAP = {"curve": "TIIE-F", "cap_type": "cap", "notional": 1e8, "strike": 0.0675, "periods": 26}
SWPT = {
    "curve": "TIIE-F",
    "swaption_type": "payer",
    "notional": 1e8,
    "strike": 0.0675,
    "expiry_years": 1.0,
    "swap_tenor_years": 2.0,
}
BOND = {"curve": "TIIE-F", "face": 100.0, "coupon_rate": 0.08, "periods": 20, "frequency": 2}


# ------------------------------------------------------------------------------ irs

@pytest.mark.parametrize(
    "curve,periods,side",
    [("TIIE-F", 13, "payer"), ("TIIE-F", 26, "receiver"), ("SOFR", 5, "payer"), ("SOFR", 3, "receiver")],
)
def test_irs_at_par_rate_has_zero_pv(client, curve, periods, side):
    notional = 1e8
    out = ok(client, "irs", curve=curve, side=side, notional=notional, periods=periods)
    assert abs(out["pv"]) < 1e-6 * notional
    assert out["currency"] == ("MXN" if curve == "TIIE-F" else "USD")
    assert out["risk"]["par_rate"] == pytest.approx(out["details"]["fixed_rate"])


@pytest.mark.parametrize("curve,periods", [("TIIE-F", 13), ("SOFR", 5)])
def test_irs_explicit_par_rate_prices_to_zero(client, curve, periods):
    par = ok(client, "irs", curve=curve, side="payer", notional=1e6, periods=periods)[
        "risk"
    ]["par_rate"]
    out = ok(
        client, "irs", curve=curve, side="payer", notional=1e6, periods=periods, fixed_rate=par
    )
    assert abs(out["pv"]) < 1e-6 * 1e6
    out = ok(
        client, "irs", curve=curve, side="payer", notional=1e6, periods=periods, fixed_rate=None
    )
    assert abs(out["pv"]) < 1e-6 * 1e6


def test_irs_cashflows_sum_to_pv(client):
    out = ok(client, "irs", **IRS, fixed_rate=0.05)
    assert abs(out["pv"]) > 1.0
    cfs = out["cashflows"]
    assert len(cfs) == IRS["periods"]
    assert sum(c["pv"] for c in cfs) == pytest.approx(out["pv"], rel=1e-8)
    assert set(cfs[0]) == {"date", "days", "amount", "df", "pv"}
    assert cfs[0]["days"] == 28
    assert cfs[-1]["days"] == 13 * 28
    as_of = date.fromisoformat(client.get("/api/market/snapshots/%s" % SNAP).get_json()["as_of"])
    assert cfs[0]["date"] == (as_of + timedelta(days=28)).isoformat()


def test_irs_payer_is_minus_receiver(client):
    payer = ok(client, "irs", **IRS, fixed_rate=0.05)
    receiver = ok(client, "irs", **dict(IRS, side="receiver"), fixed_rate=0.05)
    assert payer["pv"] == pytest.approx(-receiver["pv"], rel=1e-9)
    assert payer["risk"]["dv01"] == pytest.approx(-receiver["risk"]["dv01"], rel=1e-9)
    # el payer que paga 5 % cuando la par es mayor recibe valor
    assert payer["pv"] > 0 > receiver["pv"]
    assert payer["cashflows"][0]["amount"] > 0


def test_irs_dv01_sign_follows_convention(client):
    # DV01 = PV(base) − PV(+1 pb): el receptor de fija gana cuando bajan las tasas.
    payer = ok(client, "irs", **IRS)
    receiver = ok(client, "irs", **dict(IRS, side="receiver"))
    assert payer["risk"]["dv01"] < 0 < receiver["risk"]["dv01"]


def test_irs_sofr_converts_to_mxn_with_spot(client):
    out = ok(client, "irs", curve="SOFR", side="payer", notional=1e6, periods=5, fixed_rate=0.03)
    spot = client.get("/api/market/snapshots/%s" % SNAP).get_json()["fx"]["spot"]
    assert out["pv_mxn"] == pytest.approx(out["pv"] * spot)
    assert out["currency"] == "USD"


def test_irs_response_shape(client):
    out = ok(client, "irs", **IRS)
    assert set(out) == {"product", "currency", "pv", "pv_mxn", "risk", "cashflows", "details"}
    assert out["product"] == "irs"
    assert set(out["risk"]) == {"dv01", "par_rate"}


# --------------------------------------------------------------------------- cap_floor

@pytest.mark.parametrize("cap_type", ["cap", "floor"])
def test_cap_floor_has_positive_pv(client, cap_type):
    out = ok(client, "cap_floor", **dict(CAP, cap_type=cap_type))
    assert out["pv"] > 0
    assert out["pv_mxn"] == pytest.approx(out["pv"])
    assert out["currency"] == "MXN"
    assert out["cashflows"] is None
    assert set(out["risk"]) == {"dv01"}
    assert out["product"] == "cap_floor"


def test_cap_dv01_negative_floor_positive(client):
    cap = ok(client, "cap_floor", **CAP)
    floor = ok(client, "cap_floor", **dict(CAP, cap_type="floor"))
    assert cap["risk"]["dv01"] < 0 < floor["risk"]["dv01"]


def test_cap_floor_sofr_in_usd(client):
    out = ok(client, "cap_floor", curve="SOFR", cap_type="cap", notional=1e6, strike=0.04, periods=3)
    spot = client.get("/api/market/snapshots/%s" % SNAP).get_json()["fx"]["spot"]
    assert out["currency"] == "USD"
    assert out["pv"] > 0
    assert out["pv_mxn"] == pytest.approx(out["pv"] * spot)


# ---------------------------------------------------------------------------- swaption

def test_swaption_response_keys(client):
    out = ok(client, "swaption", **SWPT)
    assert set(out) == {"product", "currency", "pv", "pv_mxn", "risk", "cashflows", "details"}
    assert out["product"] == "swaption"
    assert out["currency"] == "MXN"
    assert out["cashflows"] is None
    assert set(out["risk"]) == {"dv01"}
    assert out["pv"] > 0
    assert out["pv_mxn"] == pytest.approx(out["pv"])


def test_swaption_payer_dv01_negative_receiver_positive(client):
    payer = ok(client, "swaption", **SWPT)
    receiver = ok(client, "swaption", **dict(SWPT, swaption_type="receiver"))
    assert payer["risk"]["dv01"] < 0 < receiver["risk"]["dv01"]


# -------------------------------------------------------------------------------- bond

def test_bond_response_keys_and_cashflows(client):
    out = ok(client, "bond", **BOND)
    assert set(out) == {"product", "currency", "pv", "pv_mxn", "risk", "cashflows", "details"}
    assert out["product"] == "bond"
    assert set(out["risk"]) == {"dv01", "duration", "convexity"}
    assert out["risk"]["dv01"] > 0  # el PV del bono sube cuando bajan las tasas
    assert 0 < out["risk"]["duration"] < 10
    assert out["risk"]["convexity"] > 0
    cfs = out["cashflows"]
    assert len(cfs) == BOND["periods"]
    assert sum(c["pv"] for c in cfs) == pytest.approx(out["pv"], rel=1e-8)
    assert cfs[0]["days"] == round(0.5 * 365)
    assert cfs[0]["amount"] == pytest.approx(4.0)  # cupón 8 % semestral sobre 100
    assert cfs[-1]["amount"] == pytest.approx(104.0)  # último cupón + principal
    assert cfs[-1]["days"] == 3650


def test_bond_curve_defaults_to_tiie_and_frequency_to_two(client):
    explicit = ok(client, "bond", **BOND)
    implicit = ok(client, "bond", face=100.0, coupon_rate=0.08, periods=20)
    assert implicit["pv"] == pytest.approx(explicit["pv"])
    assert implicit["currency"] == "MXN"


def test_bond_sofr_converts_to_mxn(client):
    out = ok(client, "bond", **dict(BOND, curve="SOFR"))
    spot = client.get("/api/market/snapshots/%s" % SNAP).get_json()["fx"]["spot"]
    assert out["currency"] == "USD"
    assert out["pv_mxn"] == pytest.approx(out["pv"] * spot)


# ------------------------------------------------------------- pv_mxn y describe (portafolio)

@pytest.mark.parametrize(
    "product,params",
    [
        ("irs", dict(IRS, fixed_rate=0.05)),
        ("cap_floor", CAP),
        ("swaption", SWPT),
        ("bond", BOND),
        ("irs", {"curve": "SOFR", "side": "receiver", "notional": 1e6, "periods": 4, "fixed_rate": 0.04}),
        ("bond", dict(BOND, curve="SOFR")),
    ],
)
def test_pv_mxn_and_describe_match_price(app, client, product, params):
    out = ok(client, product, **params)
    p = PRODUCTS[product]
    norm = p.validate(dict(params))
    with app.app_context():
        mkt = load_context(get_conn(), SNAP)
    assert p.pv_mxn(norm, mkt) == pytest.approx(out["pv_mxn"], rel=1e-9)
    d = p.describe(norm, mkt.as_of)
    assert set(d) == {"notional", "currency", "maturity"}
    assert d["currency"] == out["currency"]
    assert d["notional"] > 0
    date.fromisoformat(d["maturity"])


def test_describe_maturities(app):
    with app.app_context():
        mkt = load_context(get_conn(), SNAP)
    as_of = mkt.as_of

    def maturity(product, params):
        p = PRODUCTS[product]
        return p.describe(p.validate(dict(params)), as_of)["maturity"]

    assert maturity("irs", IRS) == (as_of + timedelta(days=13 * 28)).isoformat()
    assert maturity("cap_floor", CAP) == (as_of + timedelta(days=26 * 28)).isoformat()
    assert maturity("swaption", SWPT) == (as_of + timedelta(days=3 * 365)).isoformat()
    assert maturity("bond", BOND) == (as_of + timedelta(days=10 * 365)).isoformat()
    sofr = dict(IRS, curve="SOFR", periods=5)
    assert maturity("irs", sofr) == (as_of + timedelta(days=5 * 365)).isoformat()


def test_validate_normalizes_params(app):
    p = PRODUCTS["irs"].validate({"curve": "SOFR", "side": "payer", "notional": 5, "periods": 2})
    assert p == {"curve": "SOFR", "side": "payer", "notional": 5.0, "periods": 2, "fixed_rate": None}
    b = PRODUCTS["bond"].validate({"face": 10, "coupon_rate": 0, "periods": 3})
    assert b["curve"] == "TIIE-F" and b["frequency"] == 2.0 and b["coupon_rate"] == 0.0


# ------------------------------------------------------------------------- validación

@pytest.mark.parametrize(
    "product,params",
    [("irs", IRS), ("cap_floor", CAP), ("swaption", SWPT), ("bond", BOND)],
)
def test_missing_notional_or_face(client, product, params):
    name = "face" if product == "bond" else "notional"
    body = {k: v for k, v in params.items() if k != name}
    assert_error(post(client, product, **body), 400, name)


@pytest.mark.parametrize(
    "product,params,field,bad",
    [
        ("irs", IRS, "notional", -1),
        ("irs", IRS, "notional", 0),
        ("irs", IRS, "periods", 0),
        ("irs", IRS, "periods", 1.5),
        ("irs", IRS, "periods", True),
        ("irs", IRS, "curve", "EURIBOR"),
        ("irs", IRS, "side", "buy"),
        ("irs", IRS, "fixed_rate", "alta"),
        ("irs", IRS, "notional", True),
        ("cap_floor", CAP, "strike", 0),
        ("cap_floor", CAP, "cap_type", "collar"),
        ("cap_floor", CAP, "periods", 0),
        ("cap_floor", CAP, "curve", "x"),
        ("swaption", SWPT, "expiry_years", 0),
        ("swaption", SWPT, "swap_tenor_years", -2),
        ("swaption", SWPT, "swaption_type", "call"),
        ("swaption", SWPT, "strike", -0.01),
        ("bond", BOND, "coupon_rate", -0.01),
        ("bond", BOND, "periods", 0),
        ("bond", BOND, "frequency", 0),
        ("bond", BOND, "curve", "x"),
        ("bond", BOND, "face", "cien"),
    ],
)
def test_invalid_parameter_gives_400_with_field(client, product, params, field, bad):
    assert_error(post(client, product, **dict(params, **{field: bad})), 400, field)


def test_missing_required_parameters(client):
    for product, params, field in [
        ("irs", IRS, "curve"),
        ("irs", IRS, "side"),
        ("irs", IRS, "periods"),
        ("cap_floor", CAP, "strike"),
        ("swaption", SWPT, "expiry_years"),
        ("bond", BOND, "periods"),
        ("bond", BOND, "coupon_rate"),
    ]:
        body = {k: v for k, v in params.items() if k != field}
        assert_error(post(client, product, **body), 400, field)


@pytest.mark.parametrize(
    "product,params",
    [("irs", IRS), ("cap_floor", CAP), ("swaption", SWPT), ("bond", BOND)],
)
def test_unknown_snapshot_is_404(client, product, params):
    assert_error(post(client, product, **dict(params, snapshot="NOPE")), 404, "snapshot")


def test_missing_snapshot_is_400(client):
    r = client.post("/api/price/irs", json=IRS)
    assert_error(r, 400, "snapshot")


def test_zero_coupon_bond_prices(client):
    out = ok(client, "bond", curve="TIIE-F", face=100.0, coupon_rate=0.0, periods=4, frequency=2)
    assert 0 < out["pv"] < 100.0
