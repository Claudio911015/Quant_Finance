"""No touch y double no touch USDMXN: Monte Carlo contra los motores analíticos de QuantLib (R1-R6)."""
import copy
import json
import math
import sys
import threading
import time
from datetime import timedelta

import pytest
import QuantLib as ql

from desk.api import db, market
from desk.api.pricing import PRODUCT_LABEL, PRODUCTS, fx_exotics
from desk.api.pricing.base import MAX_DAYS
from desk.api.validation import MAX_AMOUNT, MAX_PRICE, has_non_finite

NT, DNT = "fx_no_touch", "fx_double_no_touch"
BASE = {"side": "buy", "payout_mxn": 1_000_000.0, "days": 91, "model": "flat"}
SPOT = 18.6


def _nt(days, barrier, kind, **kw):
    return dict(BASE, days=days, barrier=barrier, barrier_type=kind, **kw)


def _dnt(days, lower, upper, **kw):
    return dict(BASE, days=days, lower=lower, upper=upper, **kw)


# (días, barrera, tipo): cerca y lejos, arriba y abajo, de 7 a 730 días
NT_CASES = [
    (7, 18.9, "up"), (7, 18.3, "down"), (30, 19.2, "up"), (30, 18.0, "down"),
    (91, 19.0, "up"), (91, 19.5, "up"), (91, 17.8, "down"), (182, 20.5, "up"),
    (182, 17.0, "down"), (365, 19.8, "up"), (365, 17.5, "down"), (730, 21.0, "up"),
]
# (días, inferior, superior): corredores de 0.6 a 11 pesos
DNT_CASES = [
    (7, 18.3, 18.9), (7, 18.0, 19.2), (30, 18.1, 19.1), (30, 17.8, 19.5), (91, 18.0, 19.2),
    (91, 17.5, 19.8), (91, 16.5, 21.0), (182, 17.8, 19.6), (182, 17.0, 20.5), (365, 17.5, 19.8),
    (365, 16.0, 22.0), (730, 17.0, 20.5), (730, 15.0, 26.0),
]
R3_CASES = [pytest.param(NT, _nt(d, b, k), id="nt-%d-%s-%s" % (d, b, k)) for d, b, k in NT_CASES] + [
    pytest.param(DNT, _dnt(d, lo, hi), id="dnt-%d-%s-%s" % (d, lo, hi)) for d, lo, hi in DNT_CASES
]
MESH_CASES = [
    pytest.param(NT, _nt(30, 18.9, "up"), id="nt-near"),
    pytest.param(NT, _nt(182, 17.0, "down"), id="nt-far"),
    pytest.param(DNT, _dnt(30, 18.1, 19.1), id="dnt-narrow"),
    pytest.param(DNT, _dnt(365, 16.0, 22.0), id="dnt-wide"),
]


@pytest.fixture
def conn(app, tmp_path):
    c = db.connect(tmp_path / "t.db")
    try:
        yield c
    finally:
        c.close()


@pytest.fixture
def ctx(conn):
    return market.load_context(conn, "MX-DEMO")


@pytest.fixture
def flat(conn):
    """Fábrica de contextos de MX-DEMO con la superficie de volatilidad plana en `vol`."""
    row = conn.execute("SELECT as_of, data FROM snapshots WHERE id = 'MX-DEMO'").fetchone()

    def make(vol=0.12):
        data = json.loads(row["data"])
        surf = data["vol_surface"]
        surf["vols"] = [[vol] * len(surf["strikes"]) for _ in surf["expiry_days"]]
        return market._build_context("FLAT", row["as_of"], data)

    return make


def _res(name, params, mkt):
    """Resultado sin la gráfica (la parte que mide R6)."""
    return fx_exotics._result(fx_exotics.PRODUCTS[name].validate(params), mkt)


def _full(name, params, mkt):
    prod = fx_exotics.PRODUCTS[name]
    return prod.price(prod.validate(params), mkt)


def _post(client, name, params):
    return client.post("/api/price/%s" % name, json=dict(params, snapshot="MX-DEMO"))


def _se(r):
    return r["details"]["std_error"]


def _tol(*rs):
    return 3 * math.sqrt(sum(_se(r) ** 2 for r in rs))


# ----------------------------------------------------------------------------- R1: contrato y validación


@pytest.mark.parametrize("name,params", [(NT, _nt(91, 19.5, "up")), (DNT, _dnt(91, 17.5, 19.8))])
def test_contract_over_http(client, name, params):
    resp = _post(client, name, dict(params, model="smile"))
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert set(body) == {"product", "currency", "pv", "pv_mxn", "risk", "cashflows", "details"}
    assert body["product"] == name and body["currency"] == "MXN" and body["cashflows"] is None
    assert body["pv"] == body["pv_mxn"] > 0
    assert set(body["risk"]) == {"delta", "vega"}
    d = body["details"]
    assert set(d) == {
        "price_pct", "no_touch_probability", "std_error", "paths", "model", "method",
        "analytic_flat_pv", "chart",
    }
    assert (d["model"], d["method"], d["paths"]) == ("smile", "mc", fx_exotics.PATHS)
    assert d["price_pct"] == pytest.approx(100 * body["pv"] / 1_000_000.0)
    assert 0 < d["no_touch_probability"] < 1 and d["std_error"] > 0
    chart = d["chart"]
    assert set(chart) == {"strike", "barriers", "spots", "pnl"} and chart["strike"] is None
    assert chart["barriers"] == ([19.5] if name == NT else [17.5, 19.8])
    assert len(chart["spots"]) == len(chart["pnl"]) == fx_exotics.CHART_POINTS
    lo, hi = (SPOT ** 2 / 19.5, 19.5) if name == NT else (17.5, 19.8)  # del espejo del spot a la barrera
    assert chart["spots"][0] == pytest.approx(lo) and chart["spots"][-1] == pytest.approx(hi)
    assert chart["spots"] == sorted(chart["spots"])
    assert all(0 <= v <= 1_000_000 for v in chart["pnl"])
    assert not has_non_finite(body)


def test_defaults_are_smile_and_mc(client):
    d = _post(client, NT, {k: v for k, v in _nt(91, 19.5, "up").items() if k not in ("model",)}).get_json()["details"]
    assert (d["model"], d["method"]) == ("smile", "mc")


def test_labels_registered_and_not_tradable(client):
    assert PRODUCT_LABEL[NT] == "No touch USDMXN" and PRODUCT_LABEL[DNT] == "Double no touch USDMXN"
    assert NT not in PRODUCTS and DNT not in PRODUCTS
    body = {"product": NT, "counterparty": "X", "params": _nt(91, 19.5, "up")}
    resp = client.post("/api/trades", json=body)
    assert resp.status_code == 400 and resp.get_json()["field"] == "product"
    assert client.post("/api/price/fx_nope", json={"snapshot": "MX-DEMO"}).status_code == 404


def _drop(params, key):
    return {k: v for k, v in params.items() if k != key}


BAD = []
for _name, _ok in ((NT, _nt(91, 19.5, "up")), (DNT, _dnt(91, 17.5, 19.8))):
    for _k in ("side", "payout_mxn", "days") + (("barrier", "barrier_type") if _name == NT else ("lower", "upper")):
        BAD.append((_name, _drop(_ok, _k), _k))
    for _v in (0, -1, MAX_AMOUNT * 2):
        BAD.append((_name, dict(_ok, payout_mxn=_v), "payout_mxn"))
    for _v in (0, -5, MAX_DAYS + 1, 1.5):
        BAD.append((_name, dict(_ok, days=_v), "days"))
    for _k, _v in (("side", "x"), ("model", "x"), ("method", "x")):
        BAD.append((_name, dict(_ok, **{_k: _v}), _k))
    BAD.append((_name, dict(_ok, method="analytic", model="smile"), "method"))
    BAD.append((_name, _drop(dict(_ok, method="analytic"), "model"), "method"))
BAD += [
    (NT, _nt(91, 19.5, "x"), "barrier_type"),
    (NT, _nt(91, 19.0, "up", model="smile", method="analytic"), "method"),
    # barrera ya tocada (spot 18.6): arriba con spot >= B, abajo con spot <= B
    (NT, _nt(91, 18.6, "up"), "barrier"), (NT, _nt(91, 18.0, "up"), "barrier"),
    (NT, _nt(91, 18.6, "down"), "barrier"), (NT, _nt(91, 19.5, "down"), "barrier"),
    (DNT, _dnt(91, 18.6, 19.8), "lower"), (DNT, _dnt(91, 18.9, 19.8), "lower"),
    (DNT, _dnt(91, 17.5, 18.6), "upper"), (DNT, _dnt(91, 17.5, 18.0), "upper"),
    (DNT, _dnt(91, 19.0, 18.0), "upper"), (DNT, _dnt(91, 18.0, 18.0), "upper"),
]
for _v in (0, -1, MAX_PRICE * 2):
    BAD += [(NT, _nt(91, _v, "up"), "barrier"), (DNT, _dnt(91, _v, 19.8), "lower"), (DNT, _dnt(91, 17.5, _v), "upper")]


@pytest.mark.parametrize("name,params,field", BAD)
def test_invalid_request_is_400_with_field(client, name, params, field):
    resp = _post(client, name, params)
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["field"] == field and body["error"]


# ----------------------------------------------------------------------------- R3: contra QuantLib analítico


@pytest.mark.parametrize("name,params", R3_CASES)
def test_mc_matches_quantlib_analytic(ctx, name, params):
    r = _res(name, params, ctx)
    d = r["details"]
    assert abs(r["pv"] - d["analytic_flat_pv"]) <= 3 * d["std_error"] + 1e-9 * params["payout_mxn"]
    assert 0 < d["std_error"] <= 0.005 * params["payout_mxn"]


@pytest.mark.parametrize("name,params", MESH_CASES)
def test_result_does_not_depend_on_time_grid(ctx, monkeypatch, name, params):
    coarse = _res(name, params, ctx)
    monkeypatch.setattr(fx_exotics, "STEPS", 40)
    fine = _res(name, params, ctx)
    assert abs(coarse["pv"] - fine["pv"]) <= _tol(coarse, fine)


def test_analytic_method(ctx):
    for name, params in ((NT, _nt(91, 19.5, "up")), (DNT, _dnt(91, 17.5, 19.8))):
        r = _res(name, dict(params, method="analytic"), ctx)
        d = r["details"]
        assert (d["paths"], d["std_error"]) == (0, 0)
        assert r["pv"] == pytest.approx(d["analytic_flat_pv"], rel=1e-12)
        assert 0 < d["no_touch_probability"] < 1 and r["risk"]["vega"] < 0


# ----------------------------------------------------------------------------- R4: sonrisa


@pytest.mark.parametrize("name,params", [
    (NT, _nt(91, 19.5, "up")), (NT, _nt(365, 17.5, "down")),
    (DNT, _dnt(91, 17.5, 19.8)), (DNT, _dnt(730, 17.0, 20.5)),
])
def test_smile_on_flat_surface_reproduces_flat(flat, name, params):
    mkt = flat()
    a = _res(name, params, mkt)
    b = _res(name, dict(params, model="smile"), mkt)
    assert abs(a["pv"] - b["pv"]) <= _tol(a, b)


@pytest.mark.parametrize("name,params", [(NT, _nt(91, 19.5, "up")), (DNT, _dnt(182, 17.5, 19.8))])
def test_smile_on_demo_surface(ctx, name, params):
    r = _res(name, dict(params, model="smile"), ctx)
    d = r["details"]
    assert math.isfinite(r["pv"]) and 0 <= r["pv"] <= params["payout_mxn"]
    assert 0 <= d["no_touch_probability"] <= 1


# ----------------------------------------------------------------------------- R5: identidades


def test_value_is_between_zero_and_discounted_payout(ctx):
    for name, params in ((NT, _nt(91, 19.5, "up")), (NT, _nt(91, 17.8, "down")), (DNT, _dnt(91, 17.5, 19.8))):
        for model in ("flat", "smile"):
            r = _res(name, dict(params, model=model), ctx)
            df = r["pv"] / (params["payout_mxn"] * r["details"]["no_touch_probability"])
            assert 0 <= r["pv"] <= params["payout_mxn"] * df
            assert df == pytest.approx(ctx.curves["TIIE-F"].discount_factor(91 / 365.0), rel=1e-6)


@pytest.mark.parametrize("days", [91, 182, 3650])
@pytest.mark.parametrize("method", ["mc", "analytic"])
def test_barrier_that_cannot_be_touched_pays_the_payout_discounted_with_the_desk_curve(ctx, days, method):
    """R5(c): el pago descontado con la curva TIIE-F del desk, a 1e-6 relativo."""
    r = _res(NT, _nt(days, 900_000.0, "up", method=method), ctx)
    assert r["pv"] == pytest.approx(1_000_000.0 * ctx.curves["TIIE-F"].discount_factor(days / 365.0), rel=1e-6)


def test_quantlib_curves_give_the_discount_factors_of_the_desk_curves(ctx):
    """Pilares, entre pilares, antes del primero y más allá del último (30 años), en MXN y en USD."""
    dom, proc, *_ = fx_exotics._build({"days": 91, "model": "flat"}, ctx, ctx.spot, 0.0)
    today = ql.Settings.instance().evaluationDate
    for handle, name in ((dom, ctx.mxn_discount), (proc.dividendYield(), "SOFR")):
        pillars = [p["days"] for p in ctx.pillars[name]]
        mids = [(a + b) // 2 for a, b in zip(pillars, pillars[1:])]
        for d in pillars + mids + [1, 30 * 365]:
            ref = ctx.curves[name].discount_factor(d / 365.0)
            assert handle.discount(today + d) == pytest.approx(ref, abs=1e-9, rel=0), (name, d)


@pytest.mark.parametrize("model", ["flat", "smile"])
def test_farther_barrier_never_lowers_value(ctx, model):
    def pv(name, **kw):
        return _res(name, dict(BASE, model=model, **kw), ctx)["pv"]

    ups = [pv(NT, barrier=b, barrier_type="up") for b in (18.9, 19.5, 25.0)]
    downs = [pv(NT, barrier=b, barrier_type="down") for b in (18.3, 17.5, 12.0)]
    corridors = [pv(DNT, lower=lo, upper=hi) for lo, hi in ((18.3, 18.9), (18.0, 19.5), (14.0, 25.0))]
    for seq in (ups, downs, corridors):
        assert seq == sorted(seq) and seq[0] < seq[-1]


@pytest.mark.parametrize("model", ["flat", "smile"])
def test_far_barrier_tends_to_discounted_payout(ctx, model):
    for name, kw in ((NT, dict(barrier=1e6, barrier_type="up")), (NT, dict(barrier=0.01, barrier_type="down")),
                     (DNT, dict(lower=0.01, upper=1e6))):
        r = _res(name, dict(BASE, model=model, **kw), ctx)
        assert abs(r["details"]["no_touch_probability"] - 1) <= 1e-6
        assert r["details"]["std_error"] <= 1e-6 * 1_000_000


@pytest.mark.parametrize("name,params", [
    (NT, _nt(MAX_DAYS, 19.5, "up", model="smile")), (DNT, _dnt(MAX_DAYS, 17.5, 19.8, method="analytic")),
])
def test_longest_valid_maturity_is_priced(client, name, params):
    """Los pilares de las curvas llegan a ~10 años y el plazo válido a 50: la curva se extrapola."""
    resp = _post(client, name, params)
    assert resp.status_code == 200, resp.get_json()
    assert 0 <= resp.get_json()["pv"] < params["payout_mxn"]


@pytest.mark.parametrize("model", ["flat", "smile"])
def test_corridor_where_the_analytic_series_fails_is_still_priced_by_mc(client, model):
    """La serie analítica de QuantLib no converge con corredores muy anchos: el Monte Carlo sale normal, sin referencia."""
    resp = _post(client, DNT, _dnt(91, 0.01, 1e6, model=model))
    assert resp.status_code == 200, resp.get_json()
    d = resp.get_json()["details"]
    assert d["analytic_flat_pv"] is None
    assert abs(d["no_touch_probability"] - 1) <= 1e-6 and d["paths"] > 0


def test_analytic_method_where_the_series_fails_is_a_400_in_spanish(client):
    resp = _post(client, DNT, _dnt(91, 0.01, 1e6, method="analytic"))
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "La fórmula cerrada no converge con este corredor; use Monte Carlo", "field": "lower"}


@pytest.mark.parametrize("model", ["flat", "smile"])
def test_double_no_touch_is_at_most_each_single_no_touch(ctx, model):
    lo, hi = 17.5, 19.8
    both = _res(DNT, dict(BASE, model=model, lower=lo, upper=hi), ctx)["pv"]
    below = _res(NT, dict(BASE, model=model, barrier=lo, barrier_type="down"), ctx)["pv"]
    above = _res(NT, dict(BASE, model=model, barrier=hi, barrier_type="up"), ctx)["pv"]
    assert both <= below and both <= above and both > 0


@pytest.mark.parametrize("name,params", [
    (NT, _nt(91, 19.5, "up", model="smile")), (DNT, _dnt(91, 17.5, 19.8, model="smile")),
    (NT, _nt(91, 19.5, "up", method="analytic")),
])
def test_sell_is_minus_buy_and_runs_are_reproducible(ctx, name, params):
    buy = _res(name, params, ctx)
    sell = _res(name, dict(params, side="sell"), ctx)
    assert sell["pv"] == -buy["pv"] and sell["pv_mxn"] == -buy["pv_mxn"]
    assert sell["risk"] == {k: -v for k, v in buy["risk"].items()}
    assert sell["details"]["analytic_flat_pv"] == -buy["details"]["analytic_flat_pv"]
    assert sell["details"]["std_error"] == buy["details"]["std_error"] >= 0
    assert _res(name, params, ctx) == buy


def test_delta_and_vega_are_bumped_repricings(flat, monkeypatch):
    for name, params in ((NT, _nt(91, 19.5, "up")), (DNT, _dnt(91, 17.5, 19.8))):
        for method in ("mc", "analytic"):
            p = dict(params, method=method)
            base = _res(name, p, flat(0.12))
            vol_up = _res(name, p, flat(0.13))["pv"]
            assert base["risk"]["vega"] == pytest.approx(vol_up - base["pv"], rel=1e-9, abs=1e-6)
            up = flat(0.12)
            monkeypatch.setattr(up, "spot", SPOT * 1.01)
            spot_up = _res(name, p, up)["pv"]
            assert base["risk"]["delta"] == pytest.approx((spot_up - base["pv"]) / (0.01 * SPOT), rel=1e-9, abs=1e-6)
    ref = _res(NT, _nt(91, 19.5, "up", method="analytic"), flat(0.12))["risk"]
    assert ref["delta"] < 0 and ref["vega"] < 0  # comprador de no touch arriba: pierde si sube el spot o la vol


def test_flat_model_delta_keeps_the_volatility_of_the_unbumped_spot(ctx, flat):
    """La superficie del demo tiene sonrisa: la delta plana no debe leer otra vol en el spot chocado."""
    p = _nt(91, 19.5, "up", method="analytic")
    sigma = ctx.surface.vol(ctx.spot, 91 / 365.0)
    assert _res(NT, p, ctx)["risk"]["delta"] == pytest.approx(_res(NT, p, flat(sigma))["risk"]["delta"], rel=1e-9)


# ----------------------------------------------------------------------------- H23: nodo más allá de la barrera y choque de la delta


@pytest.mark.parametrize("model", ["flat", "smile"])
@pytest.mark.parametrize("sides,spot", [
    ([(18.5, 1)], 18.6), ([(18.6, 1)], 18.6), ([(18.7, -1)], 18.6), ([(18.6, -1)], 18.6),  # una barrera: más allá y encima
    ([(18.0, -1), (18.5, 1)], 18.6), ([(18.7, -1), (19.5, 1)], 18.6), ([(18.6, -1), (19.5, 1)], 18.6),  # dos barreras
])
def test_a_node_on_or_beyond_a_barrier_kills_the_path_even_if_every_node_is_on_the_dead_side(ctx, model, sides, spot):
    """El puente da probabilidad de cruce < 1 si los dos extremos de un paso están del mismo lado, también del muerto."""
    _, proc, sigma, ks, tab = fx_exotics._build({"days": 91, "model": model}, ctx, spot, 0.0)
    assert fx_exotics._mc(proc, sigma, ks, tab, sides, 91 / 365.0, 2000) == (0.0, 0.0)


def _distance(params):
    return min(abs(SPOT - params[k]) for k in ("barrier", "lower", "upper") if k in params)


NEAR = [pytest.param(NT, _nt(91, round(SPOT * (1 + sign * pct), 6), kind), id="nt-%s-%s" % (kind, pct))
        for pct in (0.001, 0.005, 0.02) for kind, sign in (("up", 1), ("down", -1))] + [
    pytest.param(DNT, _dnt(7, round(SPOT * 0.985, 6), round(SPOT * 1.005, 6)), id="dnt-narrow-spot-near-upper"),
    pytest.param(DNT, _dnt(7, round(SPOT * 0.995, 6), round(SPOT * 1.015, 6)), id="dnt-narrow-spot-near-lower"),
]


@pytest.mark.parametrize("name,params", NEAR)
def test_delta_with_a_barrier_near_the_spot_has_the_closed_form_sign_and_size(ctx, name, params):
    """El choque no cruza la barrera: la delta de Monte Carlo sigue a la de la forma cerrada con el mismo choque."""
    mc, an = _res(name, params, ctx), _res(name, dict(params, method="analytic"), ctx)
    h = min(0.01 * SPOT, _distance(params) / 2)
    assert mc["risk"]["delta"] * an["risk"]["delta"] > 0
    assert abs(mc["risk"]["delta"] - an["risk"]["delta"]) <= max(0.10 * abs(an["risk"]["delta"]), 3 * _se(mc) / h)


@pytest.mark.parametrize("name,params,h", [
    (NT, _nt(91, 18.62, "up", method="analytic"), 0.01), (NT, _nt(91, 18.5, "down", method="analytic"), 0.05),  # también si se aleja
    (DNT, _dnt(91, 18.59, 19.8, method="analytic"), 0.005), (NT, _nt(91, 19.5, "up", method="analytic"), 0.01 * SPOT),
])
def test_delta_bump_is_up_and_the_smaller_of_one_percent_and_half_the_distance_to_the_nearest_barrier(flat, monkeypatch, name, params, h):
    base = _res(name, params, flat(0.12))
    up = flat(0.12)
    monkeypatch.setattr(up, "spot", SPOT + h)
    assert base["risk"]["delta"] == pytest.approx((_res(name, params, up)["pv"] - base["pv"]) / h, rel=1e-9, abs=1e-6)


def test_prices_at_once_with_different_valuation_dates_equal_the_serial_ones(ctx):
    """La fecha de valuación de QuantLib es global: dos hilos con fechas distintas no deben pisarse."""
    other = copy.copy(ctx)
    other.as_of = ctx.as_of + timedelta(days=400)
    prod = fx_exotics.PRODUCTS[NT]
    p = prod.validate(_nt(91, 19.5, "up", method="analytic"))
    serial = [prod.price(p, m)["pv"] for m in (ctx, other)]
    out = [[], []]

    def work(i, m):
        out[i] = [prod.price(p, m)["pv"] for _ in range(5)]

    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        threads = [threading.Thread(target=work, args=(i, m)) for i, m in enumerate((ctx, other))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        sys.setswitchinterval(old)
    assert out == [[serial[0]] * 5, [serial[1]] * 5]


@pytest.mark.parametrize("name,params,field,label", [
    (NT, _nt(91, 18.0, "up"), "barrier", "la barrera"),
    (NT, _nt(91, 19.5, "down"), "barrier", "la barrera"),
    (DNT, _dnt(91, 18.9, 19.8), "lower", "la barrera inferior"),
    (DNT, _dnt(91, 17.5, 18.0), "upper", "la barrera superior"),
])
def test_touched_barrier_message_names_the_field_in_spanish(client, name, params, field, label):
    body = _post(client, name, params).get_json()
    assert body["field"] == field and body["error"].endswith("ya tocó " + label)


@pytest.mark.parametrize("name,params,bars", [
    (NT, _nt(91, 19.5, "up", model="smile"), [19.5]), (NT, _nt(91, 17.5, "down"), [17.5]),
    (NT, _nt(91, 40.0, "up"), [40.0]), (NT, _nt(91, 19.5, "up", method="analytic"), [19.5]),
    (DNT, _dnt(91, 17.5, 19.8, model="smile"), [17.5, 19.8]),
])
def test_chart_reaches_every_barrier_with_zero_value_and_contains_the_spot(ctx, name, params, bars):
    chart = _full(name, params, ctx)["details"]["chart"]
    assert chart["spots"][0] <= SPOT <= chart["spots"][-1]
    for b in bars:
        assert chart["pnl"][chart["spots"].index(b)] == 0


# ----------------------------------------------------------------------------- R6: eficiencia


@pytest.mark.parametrize("name,params", [(NT, _nt(91, 19.5, "up", model="smile")), (DNT, _dnt(91, 17.5, 19.8, model="smile"))])
def test_default_price_is_fast(ctx, client, name, params):
    t0 = time.perf_counter()
    r = _res(name, params, ctx)
    assert time.perf_counter() - t0 <= 4.5  # objetivo 1.5 s, margen 3x
    assert r["details"]["std_error"] <= 0.005 * params["payout_mxn"]
    t0 = time.perf_counter()
    assert _post(client, name, params).status_code == 200
    assert time.perf_counter() - t0 <= 15  # objetivo 5 s, margen 3x
