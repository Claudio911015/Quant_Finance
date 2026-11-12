"""Cross currency swap USDMXN de punta a punta (corte 3, T8): pricer, alta, valuación a fecha,
flujos liquidados y proyectados, riesgo y P&L (R5 desk, R6)."""
from datetime import date, timedelta

import pytest

from desk.api import market
from desk.api.db import connect
from desk.api.qf import qfpy
from desk.api.risk.scenarios import DEFAULT_SCENARIOS
from desk.api.tests.conftest import empty_portfolio
from desk.api.tests.csa_fixture import strip_csa, trade_with
from desk.api.tests.hedge_fixture import load_fixings, roll

CP = "Banco Alfa (sintético)"
AS_OF = date(2026, 11, 10)  # as_of de MX-DEMO (martes)
N = 10_000_000.0
FX = 18.6  # spot de MX-DEMO
BASE = {"side": "pay_usd", "notional_usd": N, "periods": 26}
NOTIONAL_MXN = N * FX


# ------------------------------------------------------------------------ ayudas

def _price(client, snapshot="MX-DEMO", **over):
    r = client.post("/api/price/xccy_swap", json={**BASE, "snapshot": snapshot, **over})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _book(client, params=None, **dates):
    return trade_with(client, "xccy_swap", CP, {**BASE, **(params or {})}, **dates)


def _rows(client, snapshot="MX-DEMO"):
    r = client.get("/api/portfolio/valuation?snapshot=%s" % snapshot)
    assert r.status_code == 200, r.get_json()
    return {row["id"]: row for row in r.get_json()["rows"]}


def _flows(client, trade_id, snapshot="MX-DEMO"):
    r = client.get("/api/trades/%d/flows?snapshot=%s" % (trade_id, snapshot))
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _context(app, snapshot):
    conn = connect(app.config["DESK_DB"])
    try:
        return market.load_context(conn, snapshot)
    finally:
        conn.close()


def _event(client, trade_id, kind, day, data):
    r = client.post(
        "/api/trades/%d/events" % trade_id, json={"type": kind, "event_date": day.isoformat(), "data": data}
    )
    assert r.status_code == 201, r.get_json()


def _compound(rate, first, last):
    """Factor de una tasa constante publicada cada lunes–viernes de `[first, last)`: el viernes devenga
    también sábado y domingo. Calculado aparte de `qfpy` (`first` debe ser día hábil)."""
    days = []
    day = first
    while day < last:
        if day.weekday() < 5:
            days.append(1)
        else:
            days[-1] += 1
        day += timedelta(days=1)
    out = 1.0
    for n in days:
        out *= 1.0 + rate * n / 360.0
    return out


def _load_market_fixings(client, end):
    """TIIE-F 7 %, SOFR 4 % y FIX 18.90 cada lunes–viernes de `[AS_OF, end)`."""
    load_fixings(client, "TIIE-F", AS_OF, end, 0.07)
    load_fixings(client, "SOFR", AS_OF, end, 0.04)
    load_fixings(client, "USDMXN", AS_OF, end, 18.90)


# ------------------------------------------------------------------------ pricer

def test_price_without_spread_is_par_and_matches_the_two_year_basis_quote(client):
    body = _price(client)
    assert body["product"] == "xccy_swap" and body["currency"] == "MXN"
    assert body["pv"] == body["pv_mxn"]
    assert abs(body["pv"]) <= 1e-6 * NOTIONAL_MXN
    assert body["risk"]["par_spread"] == pytest.approx(-0.0010, abs=1e-9)  # la cotización de 2 años de MX-DEMO
    assert set(body["risk"]) == {"par_spread", "dv01_mxn_usd", "dv01_tiie", "dv01_sofr"}
    d = body["details"]
    assert d["fx_rate"] == FX and d["notional_mxn"] == pytest.approx(NOTIONAL_MXN) and d["discount_curve"] == "MXN-USD"
    assert d["spread"] == pytest.approx(body["risk"]["par_spread"], abs=1e-12)
    cf = body["cashflows"]
    assert len(cf) == 2 * 26 + 4  # cupón por pata y periodo más dos intercambios por pata
    assert set(cf[0]) == {"date", "days", "leg", "kind", "amount", "df", "pv", "pv_mxn"}
    assert sum(f["pv_mxn"] for f in cf) == pytest.approx(body["pv"], abs=1e-6)
    exchanges = [f for f in cf if f["kind"] == "exchange"]
    assert [(f["leg"], f["days"], f["amount"]) for f in exchanges] == [
        ("USD", 0, N), ("MXN", 0, -NOTIONAL_MXN), ("USD", 728, -N), ("MXN", 728, NOTIONAL_MXN),
    ]
    coupons = {leg: [f for f in cf if f["kind"] == "coupon" and f["leg"] == leg] for leg in ("USD", "MXN")}
    assert all(f["amount"] < 0 for f in coupons["USD"]) and all(f["amount"] > 0 for f in coupons["MXN"])
    assert [f["days"] for f in coupons["USD"]] == [28 * (k + 1) for k in range(26)]
    assert coupons["MXN"][0]["date"] == (AS_OF + timedelta(days=28)).isoformat()


def test_price_risk_dv01s_match_a_manual_bump(client, app):
    body = _price(client, periods=30)  # fuera de las cotizaciones de base: sensible a las tres curvas
    mkt = _context(app, "MX-DEMO")
    swap = qfpy.XccySwap(
        N, FX, body["details"]["spread"], 0, qfpy.ois_payment_days(840, 28), 1.0, 1.0,
        qfpy.XccySide.PayUsd, True, True, "SOFR", "TIIE-F", "MXN-USD",
    )
    for key, curve in (("dv01_mxn_usd", "MXN-USD"), ("dv01_tiie", "TIIE-F"), ("dv01_sofr", "SOFR")):
        bumped = mkt.shifted(curve=curve, parallel_bp=1.0)
        assert body["risk"][key] == pytest.approx(swap.npv(mkt.env) - swap.npv(bumped.env), rel=1e-9, abs=1e-6)
        assert body["risk"][key] != 0.0


def test_pay_usd_and_pay_mxn_have_opposite_values(client):
    a = _price(client, side="pay_usd", spread=-0.0005)
    b = _price(client, side="pay_mxn", spread=-0.0005)
    assert a["pv"] != 0
    assert a["pv"] == pytest.approx(-b["pv"], rel=1e-12)
    assert a["risk"]["par_spread"] == pytest.approx(b["risk"]["par_spread"], abs=1e-12)  # mismo diferencial par
    assert a["cashflows"][0]["amount"] == -b["cashflows"][0]["amount"]


def test_explicit_spread_and_fx_rate_are_used_as_given(client):
    body = _price(client, spread=-0.0020, fx_rate=19.0)
    assert body["details"]["spread"] == -0.0020 and body["details"]["fx_rate"] == 19.0
    assert body["details"]["notional_mxn"] == pytest.approx(N * 19.0)
    assert abs(body["pv"]) > 1e-4 * NOTIONAL_MXN  # ya no está a la par


def test_exchange_option_changes_the_pv_and_the_initial_exchange_is_valued(client):
    spread = {"spread": -0.0005}
    both = _price(client, exchange="both", **spread)
    none = _price(client, exchange="none", **spread)
    initial = _price(client, exchange="initial", **spread)
    final = _price(client, exchange="final", **spread)
    assert both["pv"] != none["pv"]
    assert len(none["cashflows"]) == 52 and len(initial["cashflows"]) == 54 and len(final["cashflows"]) == 54
    # con el tipo de cambio inicial igual al spot el intercambio inicial vale 0; fuera del spot vale N·(S − fx_rate)
    assert both["pv"] == pytest.approx(final["pv"], abs=1e-6)
    off = {"spread": -0.0005, "fx_rate": 19.0}
    delta = _price(client, exchange="both", **off)["pv"] - _price(client, exchange="final", **off)["pv"]
    assert delta == pytest.approx(N * (FX - 19.0), rel=1e-12)


@pytest.mark.parametrize(
    "over, field",
    [
        ({"side": "x"}, "side"),
        ({"side": None}, "side"),
        ({"notional_usd": 0}, "notional_usd"),
        ({"notional_usd": -5}, "notional_usd"),
        ({"notional_usd": 1e14}, "notional_usd"),
        ({"periods": 0}, "periods"),
        ({"periods": 1201}, "periods"),
        ({"periods": 2.5}, "periods"),
        ({"fx_rate": 0}, "fx_rate"),
        ({"fx_rate": -18}, "fx_rate"),
        ({"fx_rate": 1e7}, "fx_rate"),
        ({"spread": 11}, "spread"),
        ({"spread": -1.5}, "spread"),
        ({"spread": "x"}, "spread"),
        ({"exchange": "x"}, "exchange"),
    ],
)
def test_price_validation_errors_name_the_field(client, over, field):
    r = client.post("/api/price/xccy_swap", json={**BASE, "snapshot": "MX-DEMO", **over})
    assert r.status_code == 400, r.get_json()
    assert r.get_json()["field"] == field


def test_price_without_the_csa_curve_discounts_with_tiie(client, app):
    strip_csa(app, "MX-DEMO")
    body = _price(client)
    assert body["details"]["discount_curve"] == "TIIE-F"
    assert abs(body["pv"]) <= 1e-6 * NOTIONAL_MXN  # a la par con esa misma curva
    assert body["risk"]["dv01_mxn_usd"] == 0.0 and body["risk"]["dv01_tiie"] != 0.0


def test_price_defaults_exchange_to_both(client):
    body = _price(client, exchange=None)
    assert len(body["cashflows"]) == 56


# ------------------------------------------------------------------------ alta (R6)

def test_r6_trade_without_spread_or_fx_rate_is_stored_at_par_with_both(client):
    trade = _book(client, {"periods": 30})
    price = _price(client, periods=30)
    assert trade["params"]["fx_rate"] == FX
    assert trade["params"]["spread"] == pytest.approx(price["risk"]["par_spread"], abs=1e-12)
    assert trade["params"]["exchange"] == "both" and trade["params"]["side"] == "pay_usd"
    assert (trade["currency"], trade["notional"]) == ("USD", N)
    assert trade["start_date"] == AS_OF.isoformat()
    assert trade["maturity_date"] == (AS_OF + timedelta(days=30 * 28)).isoformat()
    row = _rows(client)[trade["id"]]
    assert row["error"] is None and row["status"] == "viva" and row["warnings"] == []
    assert row["currency"] == "USD" and row["notional"] == N
    assert abs(row["pv_mxn"]) <= 1e-6 * NOTIONAL_MXN and row["pv"] == row["pv_mxn"]


# H15: igual que el irs, el diferencial par solo se calcula en la fecha de inicio.
SPREAD_MESSAGE = (
    "Para una operación que ya empezó capture el diferencial pactado: el diferencial par solo se calcula en la "
    "fecha de inicio"
)


@pytest.mark.parametrize("params", [{}, {"fx_rate": 18.2}], ids=["sin nada", "solo fx_rate"])
def test_r6_trade_that_already_started_needs_its_spread(client, params):
    body = {"product": "xccy_swap", "counterparty": CP, "params": {**BASE, **params}, "trade_date": "2026-10-12"}
    before = len(client.get("/api/trades").get_json()["trades"])
    r = client.post("/api/trades", json=body)
    assert r.status_code == 400
    assert r.get_json() == {"error": SPREAD_MESSAGE, "field": "spread"}
    assert len(client.get("/api/trades").get_json()["trades"]) == before


def test_r6_trade_that_already_started_keeps_the_terms_it_is_given(client):
    body = {"product": "xccy_swap", "counterparty": CP, "trade_date": "2026-10-12",
            "params": {**BASE, "fx_rate": 18.2, "spread": 0.0005}}
    r = client.post("/api/trades", json=body)
    assert r.status_code == 201, r.get_json()
    assert (r.get_json()["params"]["fx_rate"], r.get_json()["params"]["spread"]) == (18.2, 0.0005)


def test_r6_maturity_date_rewrites_the_periods_to_whole_28_day_coupons(client):
    trade = _book(client, maturity="2028-11-10")  # 731 días -> 26 periodos
    assert trade["params"]["periods"] == 26
    assert trade["maturity_date"] == (AS_OF + timedelta(days=728)).isoformat()


def test_r6_explicit_spread_and_fx_rate_are_kept(client):
    trade = _book(client, {"spread": -0.0005, "fx_rate": 18.0})
    assert trade["params"]["spread"] == -0.0005 and trade["params"]["fx_rate"] == 18.0


def test_r6_pv_at_the_pact_date_equals_the_pricer_with_the_stored_terms(client):
    trade = _book(client, {"spread": -0.0004, "fx_rate": 18.9, "exchange": "both"})
    price = _price(client, spread=-0.0004, fx_rate=18.9)
    row = _rows(client)[trade["id"]]
    assert price["pv"] != 0
    assert row["pv_mxn"] == pytest.approx(price["pv"], rel=1e-9)


def test_r6_forward_starting_trade_is_born_at_par_and_lists_its_initial_exchange_in_the_future(client):
    trade = _book(client, start="2026-11-24", maturity="2028-11-14")
    assert trade["start_date"] == "2026-11-24" and trade["params"]["periods"] == 26
    row = _rows(client)[trade["id"]]
    assert row["status"] == "viva" and abs(row["pv_mxn"]) <= 1e-6 * NOTIONAL_MXN
    body = _flows(client, trade["id"])
    assert len(body["flows"]) == 56 and body["flows"][0]["date"] == "2026-11-24"
    assert body["flows"][0]["kind"] == "exchange" and body["flows"][0]["status"] == "projected"


def test_r6_the_new_product_does_not_disturb_the_seed_portfolio(client):
    before = _rows(client)
    trade = _book(client)
    after = _rows(client)
    for tid, row in before.items():
        assert after[tid]["pv_mxn"] == row["pv_mxn"]
    assert after[trade["id"]]["product"] == "xccy_swap"
    listing = client.get("/api/trades").get_json()["trades"]
    assert [t["product"] for t in listing].count("xccy_swap") == 4  # 3 sembrados en el corte 9 + el nuevo


# ------------------------------------------------------------------------ flujos (R6)

def test_flows_at_the_pact_date_list_both_legs_and_the_exchanges_and_add_up_to_the_pv(client, app):
    trade = _book(client, {"spread": -0.0004})
    body = _flows(client, trade["id"])
    flows = body["flows"]
    assert body["warnings"] == [] and len(flows) == 56 and all(f["status"] == "projected" for f in flows)
    assert {f["leg"] for f in flows} == {"USD", "MXN"}
    assert {(f["leg"], f["currency"]) for f in flows} == {("USD", "USD"), ("MXN", "MXN")}
    assert [f["kind"] for f in flows if f["kind"] == "exchange"] == ["exchange"] * 4
    assert flows == sorted(flows, key=lambda f: f["date"])
    assert flows[-1]["date"] == flows[-2]["date"] == (AS_OF + timedelta(days=728)).isoformat()
    assert all(f["pv"] == pytest.approx(f["amount"] * f["df"]) for f in flows)
    spot = _context(app, "MX-DEMO").spot
    pv_mxn = sum(f["pv"] * (spot if f["leg"] == "USD" else 1.0) for f in flows)
    assert pv_mxn == pytest.approx(_rows(client)[trade["id"]]["pv_mxn"], abs=1e-6)


def test_flows_pay_mxn_side_has_the_opposite_signs(client):
    usd = _book(client, {"spread": -0.0004})
    mxn = _book(client, {"spread": -0.0004, "side": "pay_mxn"})
    a, b = _flows(client, usd["id"])["flows"], _flows(client, mxn["id"])["flows"]
    assert [f["amount"] for f in a] == pytest.approx([-f["amount"] for f in b], rel=1e-12)


def test_flows_without_the_csa_curve_warn_no_csa_curve(client, app):
    trade = _book(client)
    strip_csa(app, "MX-DEMO")
    body = _flows(client, trade["id"])
    assert [w["code"] for w in body["warnings"]] == ["no_csa_curve"]
    assert len(body["flows"]) == 56
    row = _rows(client)[trade["id"]]
    assert [w["code"] for w in row["warnings"]] == ["no_csa_curve"] and row["error"] is None
    price = _price(client, spread=trade["params"]["spread"])
    assert price["details"]["discount_curve"] == "TIIE-F"
    assert row["pv_mxn"] == pytest.approx(price["pv"], rel=1e-9, abs=1e-6)


def test_rolled_snapshot_settles_both_legs_with_fixings_and_values_the_aged_swap(client, app):
    trade = _book(client)
    spread = trade["params"]["spread"]
    d1 = roll(client, "MX-DEMO", "D1", 35)  # 2026-12-15: el primer cupón (día 28) ya se liquidó
    assert d1 == "2026-12-15"
    _load_market_fixings(client, date(2026, 12, 16))

    body = _flows(client, trade["id"], "D1")
    settled = [f for f in body["flows"] if f["status"] == "settled"]
    projected = [f for f in body["flows"] if f["status"] == "projected"]
    assert body["warnings"] == []
    first, paid = AS_OF, AS_OF + timedelta(days=28)
    usd = -N * (_compound(0.04, first, paid) - 1.0)
    mxn = NOTIONAL_MXN * (_compound(0.07, first, paid) - 1.0) + NOTIONAL_MXN * spread * 28 / 360.0
    # el intercambio inicial salió del PV al pasar `start_date` y se liquida (D1 de la auditoría)
    assert [(f["date"], f["kind"], f["leg"], f["currency"]) for f in settled] == [
        (AS_OF.isoformat(), "exchange", "USD", "USD"), (AS_OF.isoformat(), "exchange", "MXN", "MXN"),
        (paid.isoformat(), "coupon", "USD", "USD"), (paid.isoformat(), "coupon", "MXN", "MXN"),
    ]
    assert settled[0]["amount"] == N and settled[1]["amount"] == pytest.approx(-NOTIONAL_MXN)
    assert settled[2]["amount"] == pytest.approx(usd, rel=1e-12)
    assert settled[3]["amount"] == pytest.approx(mxn, rel=1e-12)
    assert settled[2]["df"] is None and settled[2]["pv"] is None
    assert len(projected) == 2 * 25 + 2 and projected[0]["date"] == (AS_OF + timedelta(days=56)).isoformat()
    # de los proyectados solo queda el intercambio final (el inicial ya está liquidado)
    assert [f["date"] for f in projected if f["kind"] == "exchange"] == [(AS_OF + timedelta(days=728)).isoformat()] * 2

    # el PV es el del instrumento envejecido armado aparte: periodo en curso desde el día 28 con el factor de 7 días
    mkt = _context(app, "D1")
    pay = qfpy.ois_payment_days(728, 28)
    swap = qfpy.XccySwap(
        N, FX, spread, 28 - 35, [k - 35 for k in pay[1:]],
        _compound(0.04, paid, date(2026, 12, 15)), _compound(0.07, paid, date(2026, 12, 15)),
        qfpy.XccySide.PayUsd, False, True, "SOFR", "TIIE-F", "MXN-USD",
    )
    row = _rows(client, "D1")[trade["id"]]
    assert row["warnings"] == [] and row["status"] == "viva"
    assert row["pv_mxn"] == pytest.approx(swap.npv(mkt.env), rel=1e-12)
    assert sum(f["pv"] * (mkt.spot if f["leg"] == "USD" else 1.0) for f in projected) == pytest.approx(
        row["pv_mxn"], abs=1e-6
    )


def test_rolled_snapshot_without_fixings_warns_for_both_indices(client):
    trade = _book(client)
    roll(client, "MX-DEMO", "D1", 35)
    row = _rows(client, "D1")[trade["id"]]
    assert row["error"] is None
    assert {w["index"] for w in row["warnings"] if w["code"] == "missing_fixing"} == {"TIIE-F", "SOFR"}


def test_pnl_identity_holds_and_settled_is_both_coupons_at_the_fix(client):
    trade = _book(client)
    spread = trade["params"]["spread"]
    roll(client, "MX-DEMO", "D1", 35)
    _load_market_fixings(client, date(2026, 12, 16))
    r = client.get("/api/pnl?from=MX-DEMO&to=D1")
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    row = {x["id"]: x for x in body["rows"]}[trade["id"]]
    assert row["error"] is None and row["warnings"] == []
    paid = AS_OF + timedelta(days=28)
    usd = -N * (_compound(0.04, AS_OF, paid) - 1.0)
    mxn = NOTIONAL_MXN * (_compound(0.07, AS_OF, paid) - 1.0) + NOTIONAL_MXN * spread * 28 / 360.0
    initial = N * 18.90 - NOTIONAL_MXN  # intercambio inicial al FIX del día de inicio (FIX 18.90 contra 18.60 de fx_rate)
    assert row["settled"] == pytest.approx(usd * 18.90 + mxn + initial, rel=1e-10)
    assert row["pnl"] == pytest.approx(row["pv_to"] - row["pv_from"] + row["settled"], abs=1e-6)
    assert row["pv_to"] == pytest.approx(_rows(client, "D1")[trade["id"]]["pv_mxn"], rel=1e-12)
    assert abs(row["pv_from"]) <= 1e-6 * NOTIONAL_MXN
    assert body["totals"]["pnl"] == pytest.approx(sum(x["pnl"] for x in body["rows"] if x["error"] is None), abs=1e-6)


def test_usd_flows_without_a_fix_fall_back_to_the_spot_with_a_warning(client):
    trade = _book(client)
    roll(client, "MX-DEMO", "D1", 35)
    load_fixings(client, "TIIE-F", AS_OF, date(2026, 12, 16), 0.07)
    load_fixings(client, "SOFR", AS_OF, date(2026, 12, 16), 0.04)
    body = client.get("/api/pnl?from=MX-DEMO&to=D1").get_json()
    row = {x["id"]: x for x in body["rows"]}[trade["id"]]
    assert [w["code"] for w in row["warnings"]] == ["fx_fallback"]
    # el intercambio inicial (día de inicio) y el primer cupón (día 28) son los dos flujos USD de la ventana
    assert row["warnings"][0]["dates"] == [AS_OF.isoformat(), (AS_OF + timedelta(days=28)).isoformat()]


def test_maturity_settles_the_last_coupons_and_the_final_exchange_and_the_swap_expires(client):
    trade = _book(client, {"periods": 1, "spread": -0.0010})  # un solo cupón: vence el día 28
    due = AS_OF + timedelta(days=28)
    roll(client, "MX-DEMO", "DUE", 28)
    roll(client, "MX-DEMO", "EARLY", 27)
    _load_market_fixings(client, date(2026, 12, 16))
    early = [f for f in _flows(client, trade["id"], "EARLY")["flows"] if f["status"] == "settled"]
    assert [(f["date"], f["kind"]) for f in early] == [(AS_OF.isoformat(), "exchange")] * 2  # solo el inicial
    body = _flows(client, trade["id"], "DUE")
    assert all(f["status"] == "settled" for f in body["flows"]) and body["warnings"] == []
    assert [(f["date"], f["kind"]) for f in body["flows"][:2]] == [(AS_OF.isoformat(), "exchange")] * 2
    settled = body["flows"][2:]  # lo que se liquida al vencer, tras el intercambio inicial
    assert [(f["kind"], f["leg"]) for f in settled] == [
        ("coupon", "USD"), ("coupon", "MXN"), ("exchange", "USD"), ("exchange", "MXN"),
    ]
    assert settled[2]["amount"] == -N and settled[3]["amount"] == pytest.approx(NOTIONAL_MXN)
    assert all(f["date"] == due.isoformat() for f in settled)
    row = _rows(client, "DUE")[trade["id"]]
    assert row["status"] == "vencida" and row["pv_mxn"] == 0.0
    pnl = {x["id"]: x for x in client.get("/api/pnl?from=MX-DEMO&to=DUE").get_json()["rows"]}[trade["id"]]
    expected = sum(f["amount"] * (18.90 if f["leg"] == "USD" else 1.0) for f in body["flows"])
    assert pnl["settled"] == pytest.approx(expected, rel=1e-10)
    assert pnl["pnl"] == pytest.approx(pnl["pv_to"] - pnl["pv_from"] + pnl["settled"], abs=1e-6)


# ------------------------------------------------------------------------ intercambio inicial (D1 de la auditoría)
# El intercambio inicial sigue en el PV hasta el día de inicio incluido (así el pricer lo valúa al pacto y el
# diferencial par lo cuenta); por eso se liquida en la ventana `d0 <= start < d1` en que sale del PV. Sin ello,
# un `fx_rate` distinto del spot da un salto fantasma de N·(spot − fx_rate) en el P&L.

OFF = {"fx_rate": 19.5, "spread": -0.001}  # fuera de mercado: el spot de MX-DEMO es 18.6
GAP = N * (FX - OFF["fx_rate"])  # lo que vale el intercambio inicial al spot (−9 M para quien paga USD)


def _pnl(client, a, b):
    r = client.get("/api/pnl?from=%s&to=%s" % (a, b))
    assert r.status_code == 200, r.get_json()
    return {x["id"]: x for x in r.get_json()["rows"]}


def _fix_at_spot(client, end):
    """Las tres fijaciones de `[AS_OF, end)`, con el FIX igual al spot de MX-DEMO (el intercambio inicial no gana ni pierde por FX)."""
    load_fixings(client, "TIIE-F", AS_OF, end, 0.07)
    load_fixings(client, "SOFR", AS_OF, end, 0.04)
    load_fixings(client, "USDMXN", AS_OF, end, FX)


def test_d1_off_market_initial_exchange_is_settled_when_it_leaves_the_pv(client):
    trade = _book(client, OFF)
    roll(client, "MX-DEMO", "D1", 1)
    _fix_at_spot(client, date(2026, 11, 12))
    # con los dos intercambios y el diferencial par, el PV al pacto es 0 cualquiera que sea `fx_rate`; al salir el
    # intercambio inicial del PV queda −GAP (el valor del resto) y solo la liquidación lo compensa
    assert _rows(client)[trade["id"]]["pv_mxn"] == pytest.approx(0.0, abs=1e-3)
    assert _rows(client, "D1")[trade["id"]]["pv_mxn"] == pytest.approx(-GAP, rel=0.02)
    row = _pnl(client, "MX-DEMO", "D1")[trade["id"]]
    assert row["error"] is None and row["warnings"] == []
    assert row["settled"] == pytest.approx(GAP, rel=1e-12)  # N·FIX − N·fx_rate, con FIX = spot
    assert row["pnl"] == pytest.approx(row["pv_to"] - row["pv_from"] + row["settled"], abs=1e-6)
    # sin liquidarlo el P&L de un día daba −GAP (9 M); ahora solo queda el devengo de un día
    assert abs(row["pnl"]) < 0.02 * abs(GAP)
    flows = [f for f in _flows(client, trade["id"], "D1")["flows"] if f["status"] == "settled"]
    assert [(f["date"], f["kind"], f["leg"]) for f in flows] == [
        (AS_OF.isoformat(), "exchange", "USD"), (AS_OF.isoformat(), "exchange", "MXN"),
    ]
    assert flows[0]["amount"] == N and flows[1]["amount"] == pytest.approx(-N * OFF["fx_rate"])


def test_d1_the_initial_exchange_is_settled_in_exactly_one_window(client):
    trade = _book(client, OFF)
    roll(client, "MX-DEMO", "D1", 1)
    roll(client, "MX-DEMO", "D2", 4)
    _fix_at_spot(client, date(2026, 11, 15))
    first, second = _pnl(client, "MX-DEMO", "D1")[trade["id"]], _pnl(client, "D1", "D2")[trade["id"]]
    whole = _pnl(client, "MX-DEMO", "D2")[trade["id"]]
    assert first["settled"] != 0 and second["settled"] == 0
    assert whole["settled"] == pytest.approx(first["settled"] + second["settled"], abs=1e-6)
    assert whole["pnl"] == pytest.approx(first["pnl"] + second["pnl"], abs=1e-6)
    assert abs(whole["pnl"]) < 0.02 * abs(GAP)


def test_d1_a_trade_booked_inside_the_window_settles_it_and_one_booked_on_its_end_does_not(client):
    roll(client, "MX-DEMO", "D1", 1)
    roll(client, "MX-DEMO", "D2", 4)
    _fix_at_spot(client, date(2026, 11, 15))
    trade = trade_with(client, "xccy_swap", CP, {**BASE, **OFF}, snapshot="D1")  # pacto e inicio el 2026-11-11
    booked_on_the_end = _pnl(client, "MX-DEMO", "D1")[trade["id"]]
    assert booked_on_the_end["pv_from"] == 0 and booked_on_the_end["settled"] == 0  # aún en el PV de D1
    inside = _pnl(client, "MX-DEMO", "D2")[trade["id"]]
    assert inside["pv_from"] == 0 and inside["settled"] != 0
    assert abs(inside["pnl"]) < 0.02 * abs(GAP)  # sin el intercambio daría el valor del resto, ~9 M
    after = _pnl(client, "D1", "D2")[trade["id"]]
    assert after["settled"] == inside["settled"]
    assert inside["pnl"] == pytest.approx(booked_on_the_end["pnl"] + after["pnl"], abs=1e-6)


def test_d1_a_forward_starting_swap_settles_the_exchange_when_it_passes_its_start(client):
    start = AS_OF + timedelta(days=10)
    trade = _book(client, OFF, start=start)
    roll(client, "MX-DEMO", "MID", 5)
    roll(client, "MX-DEMO", "ON", 10)  # el snapshot cae justo en `start_date`
    roll(client, "MX-DEMO", "LATE", 15)
    _fix_at_spot(client, date(2026, 11, 26))
    rows = [_pnl(client, a, b)[trade["id"]] for a, b in (("MX-DEMO", "MID"), ("MID", "ON"), ("ON", "LATE"))]
    # sale del PV al pasar `start_date`, así que se liquida en la ventana que empieza en él (no en la que termina en él)
    assert [r["settled"] != 0 for r in rows] == [False, False, True]
    assert abs(sum(r["pnl"] for r in rows)) < 0.02 * abs(GAP)
    projected = [f for f in _flows(client, trade["id"], "ON")["flows"] if f["kind"] == "exchange"]
    assert projected[0]["date"] == start.isoformat() and projected[0]["status"] == "projected"
    listed = [f for f in _flows(client, trade["id"], "LATE")["flows"] if f["kind"] == "exchange"]
    assert [(f["date"], f["status"]) for f in listed][:2] == [(start.isoformat(), "settled")] * 2


def test_d1_a_swap_terminated_before_its_start_never_settles_the_initial_exchange(client):
    start = AS_OF + timedelta(days=10)
    trade = _book(client, OFF, start=start)
    _event(client, trade["id"], "termination", AS_OF + timedelta(days=3), {"amount": 0.0})
    roll(client, "MX-DEMO", "LATE", 15)
    _fix_at_spot(client, date(2026, 11, 26))
    assert _pnl(client, "MX-DEMO", "LATE")[trade["id"]]["settled"] == 0


def test_d1_exchange_none_and_final_settle_no_initial_exchange(client):
    off = _book(client, {**OFF, "exchange": "none"})
    final = _book(client, {**OFF, "exchange": "final"})
    roll(client, "MX-DEMO", "D1", 1)
    _fix_at_spot(client, date(2026, 11, 12))
    rows = _pnl(client, "MX-DEMO", "D1")
    assert rows[off["id"]]["settled"] == 0 and rows[final["id"]]["settled"] == 0


# ------------------------------------------------------------------------ ciclo de vida

def test_termination_makes_the_trade_terminated_with_zero_pv_from_its_date_on(client):
    trade = _book(client, {"spread": -0.0004})
    roll(client, "MX-DEMO", "BEFORE", 5)
    roll(client, "MX-DEMO", "ON", 10)
    before = _rows(client, "BEFORE")[trade["id"]]
    _event(client, trade["id"], "termination", AS_OF + timedelta(days=10), {"amount": 1000.0})
    assert _rows(client, "BEFORE")[trade["id"]]["pv_mxn"] == before["pv_mxn"] != 0
    row = _rows(client, "ON")[trade["id"]]
    assert row["status"] == "terminada" and row["pv"] == row["pv_mxn"] == 0
    assert _flows(client, trade["id"], "ON")["flows"][-1]["kind"] == "transfer"


def test_quantity_change_scales_the_notional_and_the_pv(client):
    trade = _book(client, {"spread": -0.0004})
    roll(client, "MX-DEMO", "AFTER", 15)
    before = _rows(client, "AFTER")[trade["id"]]
    _event(client, trade["id"], "quantity_change", AS_OF + timedelta(days=10), {"notional": 2 * N})
    after = _rows(client, "AFTER")[trade["id"]]
    assert before["pv_mxn"] != 0
    assert after["notional"] == 2 * N and before["notional"] == N
    assert after["pv_mxn"] == pytest.approx(2 * before["pv_mxn"], rel=1e-10)
    assert _rows(client)[trade["id"]]["notional"] == N  # antes de la fecha del evento no cambia


# ------------------------------------------------------------------------ riesgo (R7)

def test_dv01_has_contributions_on_the_three_curves_and_pillars_add_up_to_the_parallel(client):
    empty_portfolio(client)
    trade = _book(client, {"periods": 30})
    body = client.post("/api/risk/dv01", json={"snapshot": "MX-DEMO"}).get_json()
    assert body["errors"] == []
    price = _price(client, periods=30, fx_rate=trade["params"]["fx_rate"], spread=trade["params"]["spread"])
    for curve, key in (("MXN-USD", "dv01_mxn_usd"), ("TIIE-F", "dv01_tiie"), ("SOFR", "dv01_sofr")):
        c = body["curves"][curve]
        assert c["parallel_mxn"] != 0
        assert abs(sum(p["dv01_mxn"] for p in c["points"]) - c["parallel_mxn"]) <= 0.02 * abs(c["parallel_mxn"])
        assert c["parallel_mxn"] == pytest.approx(price["risk"][key], rel=1e-9, abs=1e-6)
    assert body["curves"]["MXN-USD"]["points"].__len__() == 9


def test_scenarios_and_var_value_the_swap_without_errors(client):
    empty_portfolio(client)
    trade = _book(client, {"periods": 30})
    r = client.post("/api/risk/scenarios", json={"snapshot": "MX-DEMO", "scenarios": DEFAULT_SCENARIOS})
    assert r.status_code == 200, r.get_json()
    scenarios = r.get_json()["scenarios"]
    assert len(scenarios) == len(DEFAULT_SCENARIOS)
    for s in scenarios:
        assert [t["error"] for t in s["trades"]] == [None] and s["trades"][0]["id"] == trade["id"]
    assert any(abs(s["total_mxn"]) > 0 for s in scenarios)
    v = client.post("/api/risk/var", json={"snapshot": "MX-DEMO", "horizon_days": 1, "confidence": 0.99})
    assert v.status_code == 200, v.get_json()
    assert v.get_json()["errors"] == []
