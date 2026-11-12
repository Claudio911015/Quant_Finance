"""Corte 3, T7: valuación por colateral de la contraparte (D5; R2, R3, R7 y R12).

Con colateral USD y la curva `MXN-USD` en el snapshot, el lado MXN se descuenta con ella; sin la curva se
descuenta con TIIE-F y se avisa `no_csa_curve`; con colateral MXN nada cambia.
"""
import json
import sqlite3
from datetime import date, timedelta

import pytest

from desk.api import db, market, portfolio, valuation
from desk.api.app import create_app
from desk.api.qf import qfpy
from desk.api.risk.scenarios import DEFAULT_SCENARIOS
from desk.api.tests.csa_fixture import set_collateral, strip_csa, trade_with
from desk.api.tests.hedge_fixture import designate, load_fixings, par_irs, roll
from desk.api.tests.hedge_fixture import frozen_clock  # noqa: F401  (autouse: reloj fijo de coberturas)
from desk.api.tests.original_book import original_book  # noqa: F401  (fixture)

AS_OF = date(2026, 11, 10)
X = "Banco X (prueba)"
Y = "Banco Y (prueba)"
NO_CSA_MESSAGE = (
    "La contraparte tiene colateral en USD pero el snapshot no trae la curva MXN-USD: "
    "se descontó con TIIE-F"
)

IRS = {"curve": "TIIE-F", "side": "receiver", "notional": 1e8, "periods": 26, "fixed_rate": 0.08}
BOND = {"curve": "TIIE-F", "face": 100e6, "coupon_rate": 0.08, "periods": 20, "frequency": 2}
CAP = {"curve": "TIIE-F", "cap_type": "cap", "notional": 1e8, "strike": 0.0675, "periods": 26}
SWPT = {
    "curve": "TIIE-F", "swaption_type": "payer", "notional": 1e8, "strike": 0.0675,
    "expiry_years": 1.0, "swap_tenor_years": 2.0,
}
FWD = {"side": "buy", "notional_usd": 5e6, "strike": 18.9, "days": 168}
OPT = {"side": "buy", "option_type": "call", "notional_usd": 5e6, "strike": 18.9, "days": 168}
SOFR_IRS = {"curve": "SOFR", "side": "payer", "notional": 1e7, "periods": 5, "fixed_rate": 0.04}

BOOK = (
    ("irs", IRS), ("bond", BOND), ("cap_floor", CAP), ("swaption", SWPT),
    ("fx_forward", FWD), ("fx_option", OPT),
)


# ----------------------------------------------------------------------------- ayudas

def _sql(app, sql, args=()):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        rows = conn.execute(sql, args).fetchall()
        conn.commit()
        return rows
    finally:
        conn.close()


def _context(app, snapshot_id="MX-DEMO"):
    conn = db.connect(app.config["DESK_DB"])
    try:
        return market.load_context(conn, snapshot_id)
    finally:
        conn.close()


def _parity_snapshot(app):
    """MX-DEMO con puntos forward de paridad TIIE-F/SOFR y base 0 (la curva MXN-USD coincide con TIIE-F)."""
    base = _context(app)
    data = json.loads(_sql(app, "SELECT data FROM snapshots WHERE id = 'MX-DEMO'")[0][0])
    forwards = []
    for q in data["fx_forwards"]:
        parity = qfpy.FxForward(1.0, 1.0, q["days"], qfpy.FxSide.Buy, "USDMXN", "TIIE-F").forward_rate(base.env)
        forwards.append({"days": q["days"], "points": parity - base.spot, "label": q["label"]})
    data["fx_forwards"] = forwards
    data["xccy_basis"] = [{"days": q["days"], "spread": 0.0, "label": q["label"]} for q in data["xccy_basis"]]
    _sql(app, "UPDATE snapshots SET data = ? WHERE id = 'MX-DEMO'", (json.dumps(data),))


def _rows(client, snapshot="MX-DEMO"):
    r = client.get("/api/portfolio/valuation?snapshot=%s" % snapshot)
    assert r.status_code == 200, r.get_json()
    return {row["id"]: row for row in r.get_json()["rows"]}


def _book(client, counterparty, items=BOOK, **kw):
    """Las mismas operaciones con `counterparty`; devuelve sus ids por producto."""
    return {p: trade_with(client, p, counterparty, params, **kw)["id"] for p, params in items}


def _usd(client, name=X, effective="2026-11-10"):
    r = set_collateral(client, name, "USD", effective)
    assert r.status_code == 200, r.get_json()


def _close(a, b, rel=1e-8):
    return a == pytest.approx(b, rel=rel, abs=1e-6)


# ----------------------------------------------------------------------------- R3: el colateral cambia el PV

def test_usd_collateral_changes_the_pv_of_every_mxn_product(client):
    x, y = _book(client, X), _book(client, Y)
    before = _rows(client)
    for p in x:  # nada cambia mientras el colateral es MXN
        assert before[x[p]]["pv"] == pytest.approx(before[y[p]]["pv"], rel=1e-12)
        assert before[x[p]]["collateral_currency"] == "MXN"
    _usd(client)
    after = _rows(client)
    for p in x:
        assert after[x[p]]["collateral_currency"] == "USD" and after[y[p]]["collateral_currency"] == "MXN"
        assert after[y[p]]["pv"] == before[y[p]]["pv"]  # la otra contraparte no se mueve
        assert after[x[p]]["pv"] != before[x[p]]["pv"], p
        assert after[x[p]]["warnings"] == []


def test_negative_basis_makes_a_positive_mxn_flow_worth_more_under_usd(client):
    bond = trade_with(client, "bond", X, BOND)["id"]
    mxn = _rows(client)[bond]["pv"]
    _usd(client)
    assert _rows(client)[bond]["pv"] > mxn  # DF(MXN-USD) > DF(TIIE-F) con la base de MX-DEMO


def test_irs_receiver_pv_matches_a_swap_built_by_hand(app, client):
    trade = trade_with(client, "irs", X, IRS)
    _usd(client)
    mkt = _context(app)
    swap = qfpy.OisSwap(IRS["notional"], IRS["fixed_rate"], 26 * 28, 28, qfpy.SwapType.Receiver, "TIIE-F",
                        discount_curve_key="MXN-USD")
    assert _rows(client)[trade["id"]]["pv"] == pytest.approx(swap.npv(mkt.env), rel=1e-9)
    plain = qfpy.OisSwap(IRS["notional"], IRS["fixed_rate"], 26 * 28, 28, qfpy.SwapType.Receiver, "TIIE-F")
    assert swap.npv(mkt.env) != pytest.approx(plain.npv(mkt.env), rel=1e-6)


def test_sofr_products_do_not_depend_on_the_collateral(client):
    sofr = trade_with(client, "irs", X, SOFR_IRS)["id"]
    equity = trade_with(client, "equity_option", X, {
        "option_type": "call", "spot": 100.0, "strike": 100.0, "volatility": 0.25, "rate": 0.05,
        "dividend_yield": 0.0, "maturity_years": 1.0})["id"]
    before = _rows(client)
    _usd(client)
    after = _rows(client)
    for t in (sofr, equity):
        assert after[t]["pv"] == before[t]["pv"] and after[t]["warnings"] == []


def test_collateral_dated_later_than_the_snapshot_does_not_apply_yet(client):
    """R3: la valuación a una fecha usa el colateral que regía entonces (historial con fecha efectiva)."""
    x = _book(client, X, (("irs", IRS), ("bond", BOND)))
    y = _book(client, Y, (("irs", IRS), ("bond", BOND)))
    d1 = roll(client, "MX-DEMO", "D1", 35)
    load_fixings(client, "TIIE-F", AS_OF, date.fromisoformat(d1), 0.07)
    _usd(client, effective="2026-11-10")
    usd_now = _rows(client)
    assert all(usd_now[x[p]]["pv"] != usd_now[y[p]]["pv"] for p in x)
    back = set_collateral(client, X, "MXN", d1)  # vuelve a MXN el día D1
    assert back.status_code == 200, back.get_json()
    again = _rows(client)  # MX-DEMO es anterior a D1: sigue en USD, idéntico a antes
    for p in x:
        assert again[x[p]]["pv"] == usd_now[x[p]]["pv"] and again[x[p]]["collateral_currency"] == "USD"
    at_d1 = _rows(client, "D1")  # en D1 rige MXN: igual que la contraparte que nunca cambió
    for p in x:
        assert at_d1[x[p]]["collateral_currency"] == "MXN"
        assert at_d1[x[p]]["pv"] == pytest.approx(at_d1[y[p]]["pv"], rel=1e-12)


# ----------------------------------------------------------------------------- sin curva: aviso y PV de MXN

def test_usd_collateral_without_the_curve_warns_and_values_like_mxn(app, client):
    x, y = _book(client, X), _book(client, Y)
    _usd(client)
    strip_csa(app, "MX-DEMO")
    rows = _rows(client)
    for p in x:
        assert rows[x[p]]["collateral_currency"] == "USD"
        assert rows[x[p]]["pv"] == pytest.approx(rows[y[p]]["pv"], rel=1e-12, abs=1e-12), p
        assert rows[x[p]]["warnings"] == [
            {"code": "no_csa_curve", "index": None, "dates": [], "message": NO_CSA_MESSAGE}
        ]
        assert rows[y[p]]["warnings"] == []


def test_no_csa_warning_only_for_products_that_depend_on_the_mxn_discount(app, client):
    sofr = trade_with(client, "irs", X, SOFR_IRS)["id"]
    equity = trade_with(client, "equity_option", X, {
        "option_type": "call", "spot": 100.0, "strike": 100.0, "volatility": 0.25, "rate": 0.05,
        "dividend_yield": 0.0, "maturity_years": 1.0})["id"]
    sofr_bond = trade_with(client, "bond", X, {**BOND, "curve": "SOFR"})["id"]
    mxn_bond = trade_with(client, "bond", X, BOND)["id"]
    _usd(client)
    strip_csa(app, "MX-DEMO")
    rows = _rows(client)
    assert [rows[t]["warnings"] for t in (sofr, equity, sofr_bond)] == [[], [], []]
    assert [w["code"] for w in rows[mxn_bond]["warnings"]] == ["no_csa_curve"]


def test_no_warning_when_the_collateral_is_mxn_even_without_the_curve(app, client):
    x = _book(client, X)
    strip_csa(app, "MX-DEMO")
    assert all(_rows(client)[t]["warnings"] == [] for t in x.values())


def test_terminated_trade_has_no_pv_and_no_warning(app, client):
    trade = trade_with(client, "irs", X, IRS)["id"]
    _usd(client)
    strip_csa(app, "MX-DEMO")
    r = client.post("/api/trades/%d/events" % trade, json={
        "type": "termination", "event_date": "2026-11-10", "data": {"amount": 0.0}})
    assert r.status_code == 201, r.get_json()
    row = _rows(client)[trade]
    assert row["status"] == "terminada" and row["pv"] == 0.0 and row["warnings"] == []


# ----------------------------------------------------------------------------- R2: paridad y base 0

def test_r2_parity_snapshot_gives_the_same_pv_under_either_collateral(app, client):
    _parity_snapshot(app)
    x, y = _book(client, X), _book(client, Y)
    _usd(client)
    rows = _rows(client)
    for p in x:
        assert rows[x[p]]["pv"] != 0.0
        assert _close(rows[x[p]]["pv"], rows[y[p]]["pv"]), p
        assert _close(rows[x[p]]["pv_mxn"], rows[y[p]]["pv_mxn"]), p


# ----------------------------------------------------------------------------- colateral MXN: nada cambia

@pytest.mark.usefixtures("original_book")
def test_mxn_collateral_values_the_seed_like_a_snapshot_without_the_lists(app, client):
    with_lists = _rows(client)
    assert len(with_lists) == 7 and all(r["collateral_currency"] == "MXN" for r in with_lists.values())
    strip_csa(app, "MX-DEMO")
    without = _rows(client)
    for t, row in with_lists.items():
        assert row["pv"] == pytest.approx(without[t]["pv"], rel=1e-10)
        assert row["pv_mxn"] == pytest.approx(without[t]["pv_mxn"], rel=1e-10)
        assert row["warnings"] == [] and without[t]["warnings"] == []


def test_every_row_carries_the_collateral_currency(client):
    trade = trade_with(client, "irs", X, IRS)["id"]
    _usd(client)
    rows = _rows(client)
    assert rows[trade]["collateral_currency"] == "USD"
    assert {r["collateral_currency"] for t, r in rows.items() if t != trade} == {"MXN"}


# ----------------------------------------------------------------------------- aged_swap y operaciones en memoria

def test_aged_swap_discounts_with_the_context_collateral(app, client):
    trade = _trade(app, trade_with(client, "irs", X, IRS)["id"])
    mkt = _context(app)
    terms = trade["params"]
    plain = valuation.aged_swap(trade, terms, mkt, {}, []).npv(mkt.env)
    usd = valuation.aged_swap(trade, terms, mkt.with_collateral("USD"), {}, []).npv(mkt.env)
    assert usd != pytest.approx(plain, rel=1e-6)
    _usd(client)
    trade = _trade(app, trade["id"])
    assert valuation.value_trade(trade, mkt, {})["pv"] == pytest.approx(usd, rel=1e-12)


def test_an_in_memory_trade_without_history_is_mxn_collateral(app, client):
    trade = _trade(app, trade_with(client, "irs", X, IRS)["id"])
    mkt = _context(app)
    hypothetical = {k: v for k, v in trade.items() if k != "collateral"}
    assert valuation.value_trade(hypothetical, mkt.with_collateral("USD"), {})["pv"] == pytest.approx(
        valuation.value_trade(trade, mkt, {})["pv"], rel=1e-12)


def _trade(app, trade_id):
    conn = db.connect(app.config["DESK_DB"])
    try:
        return portfolio.get_trade(conn, trade_id)
    finally:
        conn.close()


# ----------------------------------------------------------------------------- R7: riesgo con MXN-USD

def _dv01(client):
    r = client.post("/api/risk/dv01", json={"snapshot": "MX-DEMO"})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


# corte 9: los cross currency swaps sembrados descuentan siempre con MXN-USD (colateral USD) y no se pueden
# valuar "sin las listas"; estas dos pruebas son sobre el portafolio original de siete operaciones.
@pytest.mark.usefixtures("original_book")
def test_r7_dv01_with_usd_collateral_has_a_nonzero_dependent_curve_that_adds_up(client):
    for p in ("irs", "bond", "cap_floor"):
        trade_with(client, p, X, dict(BOOK)[p])
    flat = _dv01(client)["curves"]["MXN-USD"]
    assert flat["parallel_mxn"] == 0.0  # con colateral MXN la curva no mueve nada
    _usd(client)
    body = _dv01(client)
    assert body["errors"] == []
    assert body["curves"]["MXN-USD"]["parallel_mxn"] != 0.0
    for name, curve in body["curves"].items():
        total = sum(p["dv01_mxn"] for p in curve["points"])
        assert abs(total - curve["parallel_mxn"]) <= 0.02 * abs(curve["parallel_mxn"]), name


def test_r7_scenarios_and_var_answer_without_errors_under_usd_collateral(client):
    x = {p: trade_with(client, p, X, dict(BOOK)[p])["id"] for p in ("irs", "bond", "cap_floor")}
    y = {p: trade_with(client, p, Y, dict(BOOK)[p])["id"] for p in ("irs", "bond", "cap_floor")}
    _usd(client)
    r = client.post("/api/risk/scenarios", json={"snapshot": "MX-DEMO", "scenarios": DEFAULT_SCENARIOS})
    assert r.status_code == 200, r.get_json()
    scenarios = r.get_json()["scenarios"]
    assert len(scenarios) == len(DEFAULT_SCENARIOS)
    assert all(row["error"] is None for s in scenarios for row in s["trades"])
    tiie_up = {row["id"]: row["pnl_mxn"] for row in scenarios[0]["trades"]}  # "TIIE-F +50 pb"
    # el choque a TIIE-F recalibra MXN-USD: el bono con colateral USD no reacciona igual que el de MXN
    assert tiie_up[x["bond"]] != pytest.approx(tiie_up[y["bond"]], rel=1e-3)
    r = client.post("/api/risk/var", json={"snapshot": "MX-DEMO", "horizon_days": 1, "confidence": 0.99})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["errors"] == []


# ----------------------------------------------------------------------------- R12: coberturas y par

D0 = AS_OF
LOAN_END = D0 + timedelta(days=364)
NOTIONAL = 500e6
LOAN = {
    "index": "TIIE-F", "notional": NOTIONAL, "start_date": D0.isoformat(),
    "maturity_date": LOAN_END.isoformat(), "side": "pays_floating",
}


def _period(client, strip=None):
    """Cierra el periodo de una cobertura de flujo de efectivo en D1 (+35 días) y devuelve la respuesta."""
    trade = par_irs(client, "TIIE-F", NOTIONAL, D0, LOAN_END)
    r = designate(client, trade["id"], "floating_loan", LOAN)
    assert r.status_code == 201, r.get_json()
    as_of = roll(client, "MX-DEMO", "D1", 35)
    load_fixings(client, "TIIE-F", D0, date.fromisoformat(as_of), 0.07)
    closed = client.post("/api/hedges/%d/periods" % r.get_json()["id"], json={"snapshot": "D1"})
    assert closed.status_code == 201, closed.get_json()
    return closed.get_json()


def _numbers(node, path=""):
    if isinstance(node, dict):
        for k in sorted(node):
            for item in _numbers(node[k], path + "/" + k):
                yield item
    elif isinstance(node, list):
        for i, v in enumerate(node):
            for item in _numbers(v, "%s[%d]" % (path, i)):
                yield item
    elif isinstance(node, float):
        yield path, node


def test_r12_hedge_period_close_is_the_same_with_and_without_the_csa_lists(app, tmp_path):
    with_lists = _period(app.test_client())
    other = create_app(db_path=tmp_path / "sin-listas.db")
    strip_csa(other, "MX-DEMO")
    without = _period(other.test_client())
    a, b = dict(_numbers(with_lists)), dict(_numbers(without))
    assert a.keys() == b.keys() and a
    for path in a:
        assert a[path] == pytest.approx(b[path], rel=1e-8, abs=1e-6), path


def test_r12_a_par_irs_with_a_usd_counterparty_is_at_par_in_its_snapshot(client):
    mxn_par = trade_with(client, "irs", Y, {k: v for k, v in IRS.items() if k != "fixed_rate"})
    trade_with(client, "bond", X, BOND)  # da de alta a la contraparte X, que cambia a USD antes del swap a la par
    _usd(client)
    booked = trade_with(client, "irs", X, {k: v for k, v in IRS.items() if k != "fixed_rate"})
    assert booked["params"]["fixed_rate"] != pytest.approx(mxn_par["params"]["fixed_rate"], abs=1e-9)
    row = _rows(client)[booked["id"]]
    assert row["collateral_currency"] == "USD" and abs(row["pv"]) <= 1e-6 * IRS["notional"]
    assert abs(_rows(client)[mxn_par["id"]]["pv"]) <= 1e-6 * IRS["notional"]


def test_r12_a_par_irs_without_collateral_history_keeps_the_mxn_par(client):
    booked = trade_with(client, "irs", "Contraparte nueva", {k: v for k, v in IRS.items() if k != "fixed_rate"})
    assert abs(_rows(client)[booked["id"]]["pv"]) <= 1e-6 * IRS["notional"]
