"""Valuación a fecha (T7): envejecimiento, estados de la vida y fijaciones (R3, R5-R10)."""
import json
import math
from datetime import date, timedelta

import pytest

from desk.api import market, valuation
from desk.api.app import create_app
from desk.api.db import connect
from desk.api.qf import qfpy
from desk.api.tests.conftest import insert_raw_trade
from desk.api.tests.corte1_fixture import build_corte1_db, golden_pv

AS_OF = date(2026, 11, 10)  # as_of de MX-DEMO
VALUATION = "/api/portfolio/valuation?snapshot=%s"


# ------------------------------------------------------------------------ ayudas

def _iso(days):
    return (AS_OF + timedelta(days=days)).isoformat()


def _roll(client, snap_id, days):
    r = client.post("/api/market/MX-DEMO/roll", json={"id": snap_id, "as_of": _iso(days)})
    assert r.status_code == 201, r.get_json()
    return snap_id


def _rows(client, snap_id):
    r = client.get(VALUATION % snap_id)
    assert r.status_code == 200, r.get_json()
    return {row["id"]: row for row in r.get_json()["rows"]}


def _book(client, product, params, **dates):
    r = client.post(
        "/api/trades",
        json={"product": product, "counterparty": "Banco T", "params": params, **dates},
    )
    assert r.status_code == 201, r.get_json()
    return r.get_json()["id"]


def _event(client, trade_id, kind, day, data):
    r = client.post(
        "/api/trades/%d/events" % trade_id,
        json={"type": kind, "event_date": day, "data": data},
    )
    assert r.status_code == 201, r.get_json()


def _csv(client, index, values):
    """Carga fijaciones diarias `values` de `index` desde AS_OF (una por día)."""
    lines = ["index,date,value"] + [
        "%s,%s,%r" % (index, _iso(i), v) for i, v in enumerate(values)
    ]
    r = client.post("/api/fixings/csv", json={"csv": "\n".join(lines)})
    assert r.status_code == 200, r.get_json()


def _price(client, product, snap_id, params):
    r = client.post("/api/price/%s" % product, json={**params, "snapshot": snap_id})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _context(app, snap_id):
    conn = connect(app.config["DESK_DB"])
    try:
        return market.load_context(conn, snap_id)
    finally:
        conn.close()


IRS = {"curve": "TIIE-F", "side": "payer", "notional": 1e8, "periods": 13, "fixed_rate": 0.07}
FWD = {"side": "buy", "notional_usd": 1e6, "strike": 19.0, "days": 30}
OPT = {"side": "buy", "option_type": "call", "notional_usd": 1e6, "strike": 19.0, "days": 30}


# ------------------------------------------------------------------------ R9, R10

def test_r9_migrated_book_values_through_value_trade_unchanged(tmp_path):
    from desk.api import portfolio

    app = create_app(db_path=build_corte1_db(tmp_path / "corte1.db"))
    conn = connect(app.config["DESK_DB"])
    try:
        mkt = market.load_context(conn, "MX-DEMO")
        golden = golden_pv()
        for trade in portfolio.load_trades(conn):
            v = valuation.value_trade(trade, mkt, {})
            assert v["status"] == "viva" and v["warnings"] == []
            assert v["pv_mxn"] == pytest.approx(golden[trade["id"]], rel=1e-8)
            assert portfolio.trade_pv_mxn(trade, mkt) == v["pv_mxn"]
    finally:
        conn.close()
    rows = _rows(app.test_client(), "MX-DEMO")
    for tid, pv in golden.items():
        assert rows[tid]["pv_mxn"] == pytest.approx(pv, rel=1e-8)


@pytest.mark.parametrize("trade_id, product", [(4, "fx_forward"), (5, "fx_forward"), (6, "fx_option")])
def test_r10_fx_rows_carry_pv_in_mxn_equal_to_price(client, trade_id, product):
    trade = client.get("/api/trades/%d" % trade_id).get_json()
    row = _rows(client, "MX-DEMO")[trade_id]
    price = _price(client, product, "MX-DEMO", trade["params"])
    assert row["pv"] == pytest.approx(price["pv"], rel=1e-8)
    assert row["pv"] == row["pv_mxn"]
    assert row["currency"] == "USD"  # moneda del nocional; el pv de FX va en MXN


# ---------------------------------------------------------- envejecer cada producto

AGED_CASES = [
    ("fx_forward", FWD, {"days": 30 - 10}),
    ("fx_option", OPT, {"days": 30 - 10}),
    (
        "swaption",
        {"curve": "TIIE-F", "swaption_type": "payer", "notional": 1e8, "strike": 0.0675,
         "expiry_years": 1.0, "swap_tenor_years": 2.0},
        {"expiry_years": (365 - 10) / 365.0},
    ),
    (
        "equity_option",
        {"option_type": "call", "spot": 100.0, "strike": 100.0, "volatility": 0.2, "rate": 0.05,
         "dividend_yield": 0.0, "maturity_years": 1.0, "quantity": 10},
        {"maturity_years": (365 - 10) / 365.0},
    ),
    # Aproximación declarada: periods = ceil(días / period_days) y ceil((días − 0.5) × frecuencia / 365).
    (
        "cap_floor",
        {"curve": "TIIE-F", "cap_type": "cap", "notional": 1e8, "strike": 0.0675, "periods": 13},
        {"periods": math.ceil((13 * 28 - 40) / 28.0)},
    ),
    (
        "bond",
        {"curve": "TIIE-F", "face": 100.0, "coupon_rate": 0.08, "periods": 24, "frequency": 12.0},
        {"periods": math.ceil((730 - 40 - 0.5) * 12.0 / 365.0)},
    ),
]


@pytest.mark.parametrize("product, params, shortened", AGED_CASES, ids=[c[0] for c in AGED_CASES])
def test_aged_value_is_the_price_of_the_shortened_term(client, product, params, shortened):
    days = 40 if product in ("cap_floor", "bond") else 10
    tid = _book(client, product, params)
    snap = _roll(client, "AGED", days)
    row = _rows(client, snap)[tid]
    assert row["status"] == "viva" and row["error"] is None and row["warnings"] == []
    expected = _price(client, product, snap, {**params, **shortened})
    assert math.isfinite(row["pv_mxn"])
    assert row["pv_mxn"] == pytest.approx(expected["pv_mxn"], rel=1e-9)
    # el PV va en la moneda de /api/price (MXN en FX/acción, la de la curva en el resto)
    assert row["pv"] == pytest.approx(expected["pv"], rel=1e-9)


def test_cap_and_bond_ceil_changes_the_period_count():
    # Los casos de arriba deben ejercitar el ceil: con 40 días menos cambia el número de periodos.
    assert math.ceil((13 * 28 - 40) / 28.0) == 12 != 13
    assert math.ceil((730 - 40 - 0.5) * 12.0 / 365.0) == 23 != 24


def test_bond_valued_on_its_trade_date_is_the_price_even_when_maturity_rounded_half_a_day(client):
    # periods=3, frequency=2: 3/2 × 365 = 547.5 días, que `maturity_date` redondea a 548; con
    # ceil(548 × 2 / 365) = 4 el bono saldría con un periodo de más el mismo día del pacto.
    params = {"curve": "TIIE-F", "face": 100.0, "coupon_rate": 0.08, "periods": 3, "frequency": 2.0}
    tid = _book(client, "bond", params)
    row = _rows(client, "MX-DEMO")[tid]
    assert row["maturity_date"] == _iso(548)
    assert math.ceil(548 * 2.0 / 365.0) == 4  # la fórmula anterior se pasaba
    expected = _price(client, "bond", "MX-DEMO", params)
    assert row["status"] == "viva" and row["error"] is None
    assert row["pv_mxn"] == pytest.approx(expected["pv_mxn"], rel=1e-9)
    assert row["pv"] == pytest.approx(expected["pv"], rel=1e-9)


def test_future_start_forward_uses_total_term_from_as_of(client):
    tid = _book(client, "fx_forward", FWD, start_date=_iso(14))  # vence en start + 30
    row = _rows(client, "MX-DEMO")[tid]
    assert row["status"] == "viva" and row["maturity_date"] == _iso(44)
    expected = _price(client, "fx_forward", "MX-DEMO", {**FWD, "days": 44})
    assert row["pv_mxn"] == pytest.approx(expected["pv_mxn"], rel=1e-9)


def test_future_start_irs_uses_start_days_and_unit_factor(client, app):
    tid = _book(client, "irs", IRS, start_date=_iso(14))
    row = _rows(client, "MX-DEMO")[tid]
    assert row["status"] == "viva" and row["warnings"] == []  # sin fijaciones debidas
    mkt = _context(app, "MX-DEMO")
    swap = qfpy.OisSwap(
        1e8, 0.07, 14, [14 + k for k in qfpy.ois_payment_days(13 * 28, 28)], 1.0,
        qfpy.SwapType.Payer, "TIIE-F",
    )
    assert row["pv_mxn"] == pytest.approx(swap.npv(mkt.env), rel=1e-12)
    spot_id = _book(client, "irs", IRS)
    spot_start = _rows(client, "MX-DEMO")[spot_id]["pv_mxn"]
    assert row["pv_mxn"] != pytest.approx(spot_start, rel=1e-6)


# ------------------------------------------------------------------ R8, no_pactada

def test_r8_forward_is_expired_from_its_maturity_on(client):
    tid = _book(client, "fx_forward", FWD)  # vence AS_OF + 30
    _roll(client, "D29", 29)
    _roll(client, "D30", 30)
    _roll(client, "D31", 31)
    live = _rows(client, "D29")[tid]
    assert live["status"] == "viva" and live["pv_mxn"] != 0
    for snap in ("D30", "D31"):
        row = _rows(client, snap)[tid]
        assert row["status"] == "vencida" and row["pv"] == row["pv_mxn"] == 0
        assert row["warnings"] == [] and row["error"] is None  # un forward no es opción


def test_r8_unexercised_option_expires_with_warning(client):
    tid = _book(client, "fx_option", OPT)
    _roll(client, "D30", 30)
    _roll(client, "D31", 31)
    for snap in ("D30", "D31"):
        row = _rows(client, snap)[tid]
        assert row["status"] == "vencida" and row["pv"] == row["pv_mxn"] == 0
        assert [w["code"] for w in row["warnings"]] == ["expired_unexercised"]
        w = row["warnings"][0]
        assert w["index"] is None and w["dates"] == [_iso(30)] and w["message"]


def test_exercised_option_is_not_flagged_as_expired_unexercised(client):
    tid = _book(client, "fx_option", OPT)
    _event(client, tid, "exercise", _iso(30), {"amount": 5000.0})
    _roll(client, "D31", 31)
    row = _rows(client, "D31")[tid]
    assert row["status"] == "ejercida" and row["pv_mxn"] == 0 and row["warnings"] == []


def test_not_yet_agreed_trades_are_worth_zero(client):
    _book(client, "fx_forward", FWD, trade_date=_iso(3), start_date=_iso(3))
    _roll(client, "BEFORE", -5)
    v = client.get(VALUATION % "BEFORE").get_json()
    assert len(v["rows"]) == 8
    assert all(r["status"] == "no_pactada" for r in v["rows"])
    assert all(r["pv"] == r["pv_mxn"] == 0 and r["error"] is None for r in v["rows"])
    assert v["total_mxn"] == 0
    _roll(client, "BEFORE_PACT", 1)  # el último pacta el día 3
    pact = _rows(client, "BEFORE_PACT")
    assert pact[8]["status"] == "no_pactada" and pact[1]["status"] == "viva"


# --------------------------------------------------------------------- R5, R6

def test_r5_termination_zeroes_pv_from_its_date_on(client):
    _roll(client, "BEFORE", 5)
    _roll(client, "ON", 10)
    _roll(client, "AFTER", 15)
    before = {s: _rows(client, s) for s in ("BEFORE", "ON", "AFTER")}
    _event(client, 1, "termination", _iso(10), {"amount": 1000.0})
    _event(client, 4, "termination", _iso(10), {"amount": -250.0})
    after = {s: _rows(client, s) for s in ("BEFORE", "ON", "AFTER")}
    for tid in (1, 4):
        assert after["BEFORE"][tid]["pv_mxn"] == before["BEFORE"][tid]["pv_mxn"] != 0
        assert after["BEFORE"][tid]["status"] == "viva"
        for snap in ("ON", "AFTER"):
            assert before[snap][tid]["pv_mxn"] != 0
            row = after[snap][tid]
            assert row["status"] == "terminada" and row["pv"] == row["pv_mxn"] == 0
    total = client.get(VALUATION % "AFTER").get_json()["total_mxn"]
    assert total == pytest.approx(sum(r["pv_mxn"] for r in after["AFTER"].values()))


def test_r6_quantity_change_scales_pv_from_its_date_on(client):
    _roll(client, "BEFORE", 5)
    _roll(client, "ON", 10)
    _roll(client, "AFTER", 15)
    before = {s: _rows(client, s) for s in ("BEFORE", "ON", "AFTER")}
    changes = {1: 1000e6, 4: 20e6}  # irs 500e6 -> x2; forward 10e6 -> x2
    for tid, notional in changes.items():
        _event(client, tid, "quantity_change", _iso(10), {"notional": notional})
    after = {s: _rows(client, s) for s in ("BEFORE", "ON", "AFTER")}
    for tid, notional in changes.items():
        assert after["BEFORE"][tid]["pv_mxn"] == before["BEFORE"][tid]["pv_mxn"]
        assert after["BEFORE"][tid]["notional"] == before["BEFORE"][tid]["notional"]
        for snap in ("ON", "AFTER"):
            assert after[snap][tid]["pv_mxn"] == pytest.approx(2 * before[snap][tid]["pv_mxn"], rel=1e-10)
            assert after[snap][tid]["notional"] == notional


# ----------------------------------------------------------------------- R7

def test_r7_missing_fixings_warn_and_loaded_fixings_clear_the_warning(client):
    _roll(client, "D10", 10)
    row = _rows(client, "D10")[1]  # irs TIIE-F pactado en MX-DEMO
    assert row["error"] is None and row["status"] == "viva"
    assert [w["code"] for w in row["warnings"]] == ["missing_fixing"]
    w = row["warnings"][0]
    assert w["index"] == "TIIE-F" and w["dates"] == [_iso(i) for i in range(10)] and w["message"]
    sofr = _rows(client, "D10")[3]  # irs SOFR: aviso del otro índice, valuado en MXN
    assert sofr["warnings"][0]["index"] == "SOFR" and len(sofr["warnings"][0]["dates"]) == 10
    assert sofr["pv_mxn"] == pytest.approx(sofr["pv"] * 18.60, rel=1e-12)

    _csv(client, "TIIE-F", [0.0701 + 0.0001 * i for i in range(10)])
    cleared = _rows(client, "D10")[1]
    assert cleared["warnings"] == [] and cleared["error"] is None
    assert cleared["pv_mxn"] != pytest.approx(row["pv_mxn"], rel=1e-9)  # las fijaciones se usan


def test_missing_day_takes_last_published_before_it(client):
    _roll(client, "D10", 10)
    _csv(client, "TIIE-F", [0.0705])  # solo el día 0 está publicado
    row = _rows(client, "D10")[1]
    assert row["warnings"][0]["dates"] == [_iso(i) for i in range(1, 10)]
    pv_carried = row["pv_mxn"]
    _csv(client, "TIIE-F", [0.0705] * 10)  # los días 1-9 con la misma tasa (día 0 ya existe igual)
    full = _rows(client, "D10")[1]
    assert full["warnings"] == []
    assert pv_carried == pytest.approx(full["pv_mxn"], rel=1e-12)


def test_missing_day_without_any_fixing_uses_the_curve_overnight_rate(client, app):
    _roll(client, "D10", 10)
    row = _rows(client, "D10")[1]
    curve = _context(app, "D10").curves["TIIE-F"]
    overnight = (1.0 / curve.discount_factor(1.0 / 365.0) - 1.0) * 360.0
    _csv(client, "TIIE-F", [overnight] * 10)
    full = _rows(client, "D10")[1]
    assert full["warnings"] == []
    assert row["pv_mxn"] == pytest.approx(full["pv_mxn"], rel=1e-12)


def test_irs_without_fixed_rate_is_a_row_error(app, client):
    params = {"curve": "TIIE-F", "side": "payer", "notional": 1e6, "periods": 13}
    tid = insert_raw_trade(app, "irs", json.dumps(params))
    row = _rows(client, "MX-DEMO")[tid]
    assert "fixed_rate" in row["error"] and row["pv"] is None and row["status"] is None


# ----------------------------------------------------------------------- R3

def _aged_irs_check(client, app, fixed_rate):
    """irs de 26 periodos TIIE-F: su valor 14 días después, con la curva desplazada y fijaciones
    forward, es el valor de hoy reexpresado en la nueva fecha (PV_D0 / DF0(14/365))."""
    tau, notional = 14, 500e6
    params = {"curve": "TIIE-F", "side": "payer", "notional": notional, "periods": 26}
    if fixed_rate is None:  # a la par
        fixed_rate = _price(client, "irs", "MX-DEMO", params)["risk"]["par_rate"]
    tid = _book(client, "irs", {**params, "fixed_rate": fixed_rate})
    pv0 = _rows(client, "MX-DEMO")[tid]["pv_mxn"]

    conn = connect(app.config["DESK_DB"])
    try:
        c0 = market.load_context(conn, "MX-DEMO").curves["TIIE-F"]
        row = conn.execute("SELECT label, synthetic, data FROM snapshots WHERE id = 'MX-DEMO'").fetchone()
        data = json.loads(row["data"])
        pay0 = qfpy.ois_payment_days(26 * 28, 28)
        mats, zeros = [], []
        for d in pay0:  # curva desplazada tau días, como en tests/test_ois_aged_py.py
            t1 = (d - tau) / 365.0
            mats.append(t1)
            zeros.append((c0.zero_rate(d / 365.0) * d / 365.0 - c0.zero_rate(tau / 365.0) * tau / 365.0) / t1)
        env = qfpy.MarketEnvironment()
        env.add_curve("TIIE-F", qfpy.YieldCurve(mats, zeros, qfpy.InterpolationMethod.Linear))
        quotes = []
        for i, d in enumerate(pay0):  # una cotización en cada pago restante
            days = d - tau
            par = qfpy.OisSwap(1e6, 0.0, days, 28, qfpy.SwapType.Payer, "TIIE-F").par_rate(env)
            quotes.append({"id": "TIIE-F:%dD" % days, "curve": "TIIE-F", "label": "%dD" % days,
                           "type": "deposit" if i == 0 else "ois", "days": days, "rate": par})
        data["quotes"] = quotes + [q for q in data["quotes"] if q["curve"] == "SOFR"]
        conn.execute(
            "INSERT INTO snapshots (id, label, synthetic, as_of, data) VALUES ('D1', 'desplazado', ?, ?, ?)",
            (row["synthetic"], _iso(tau), json.dumps(data)),
        )
        conn.commit()
        df0 = lambda d: 1.0 if d == 0 else c0.discount_factor(d / 365.0)  # noqa: E731
        fixings = [(df0(d) / df0(d + 1) - 1.0) * 360.0 for d in range(tau)]
        df_tau = df0(tau)
    finally:
        conn.close()
    _csv(client, "TIIE-F", fixings)

    aged = _rows(client, "D1")[tid]
    assert aged["status"] == "viva" and aged["error"] is None and aged["warnings"] == []
    assert aged["pv_mxn"] == pytest.approx(pv0 / df_tau, abs=1e-6 * notional)
    return pv0, aged["pv_mxn"]


def test_r3_par_swap_aged_on_shifted_curve_stays_at_par(client, app):
    pv0, pv1 = _aged_irs_check(client, app, None)
    assert abs(pv0) < 1e-6 * 500e6 and abs(pv1) < 1e-6 * 500e6


def test_r3_off_par_swap_aged_on_shifted_curve_is_rebased(client, app):
    pv0, pv1 = _aged_irs_check(client, app, 0.0690)
    assert abs(pv0) > 1e5  # no trivial: la comparación no se cumple por ser ambos ~0


# ----------------------------------------------------------------- is_live

def test_is_live_follows_the_state_and_treats_unreadable_trades_as_live(app):
    from desk.api import portfolio

    conn = connect(app.config["DESK_DB"])
    try:
        trade = portfolio.get_trade(conn, 4)  # forward de 182 días
        assert valuation.is_live(trade, AS_OF)
        assert not valuation.is_live(trade, AS_OF - timedelta(days=1))  # no pactada
        assert not valuation.is_live(trade, trade["maturity_date"])  # vencida
        broken = dict(trade, params=None)
        assert valuation.is_live(broken, AS_OF)  # se intenta valuar y la fila reporta el error
    finally:
        conn.close()
