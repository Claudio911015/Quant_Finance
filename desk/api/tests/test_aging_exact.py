"""Bono y cap/floor envejecidos exactos y liquidación del bono (corte 3, T9; R9)."""
from datetime import timedelta

import pytest

from desk.api import aging, lifecycle, market, portfolio, settlement
from desk.api import fixings as fixing_store
from desk.api.db import connect
from desk.api.qf import qfpy
from desk.api.tests.test_flows import _flows, _split
from desk.api.tests.test_pnl import _assert_adds_up, _pnl
from desk.api.tests.test_valuation_aged import (
    AS_OF, _book, _context, _csv, _iso, _price, _roll, _rows,
)

BOND = {"curve": "TIIE-F", "face": 100.0, "coupon_rate": 0.08, "periods": 12, "frequency": 4.0}
CAP = {"curve": "TIIE-F", "cap_type": "cap", "notional": 1e8, "strike": 0.0675, "periods": 13}


def _pay_days(periods, frequency):
    """Día del pago i (desde el inicio), calculado aparte de `aging`."""
    return [int(round(i * 365.0 / frequency)) for i in range(1, periods + 1)]


def _live(app, trade_id, snap_id):
    """`(trade, terms, mkt)` de la operación en el snapshot, como los ve `aging`."""
    conn = connect(app.config["DESK_DB"])
    try:
        trade = portfolio.get_trade(conn, trade_id)
        mkt = market.load_context(conn, snap_id)
    finally:
        conn.close()
    return trade, lifecycle.state(trade, trade["events"], mkt.as_of)["terms"], mkt


# ------------------------------------------------- el día del pacto = /api/price

@pytest.mark.parametrize(
    "product, params",
    [
        ("bond", BOND),
        ("bond", {**BOND, "frequency": 2.0, "periods": 3}),  # 547.5 días: el redondeo del vencimiento
        ("bond", {**BOND, "frequency": 12.0, "periods": 24}),
        ("bond", {**BOND, "curve": "SOFR", "frequency": 1.0, "periods": 5}),
        ("cap_floor", CAP),
        ("cap_floor", {**CAP, "cap_type": "floor", "strike": 0.08}),
        ("cap_floor", {**CAP, "curve": "SOFR", "strike": 0.04, "periods": 4}),
    ],
    ids=["bond-q", "bond-547.5d", "bond-monthly", "bond-sofr", "cap", "floor", "cap-sofr"],
)
def test_on_the_trade_date_the_aged_value_is_the_price(client, product, params):
    tid = _book(client, product, params)
    row = _rows(client, "MX-DEMO")[tid]
    expected = _price(client, product, "MX-DEMO", params)
    assert row["status"] == "viva" and row["error"] is None and row["warnings"] == []
    assert row["pv"] == pytest.approx(expected["pv"], rel=1e-9)
    assert row["pv_mxn"] == pytest.approx(expected["pv_mxn"], rel=1e-9)


# ----------------------------------------------------------- bono día a día (+1..+200)

def test_bond_rolled_day_by_day_has_no_step_and_dirty_clean_accrued_add_up(app, client):
    tid = _book(client, "bond", BOND)  # cupón de 2.0 cada 91/92 días
    coupon = 100.0 * 0.08 / 4.0
    coupon_days = {d for d in _pay_days(12, 4.0) if d <= 200}
    assert coupon_days == {91, 182}  # round(182.5) = 182 (mitad al par)
    pv = {0: _rows(client, "MX-DEMO")[tid]["pv_mxn"]}
    for d in range(1, 201):
        snap = _roll(client, "R%d" % d, d)
        row = _rows(client, snap)[tid]
        assert row["status"] == "viva" and row["error"] is None and row["warnings"] == []
        pv[d] = row["pv_mxn"]
        quote = _flows(client, tid, snap)["bond"]
        assert quote["currency"] == "MXN"
        assert quote["dirty"] == pytest.approx(row["pv"], rel=1e-12)
        assert quote["dirty"] - quote["clean"] - quote["accrued"] == pytest.approx(0.0, abs=1e-9)
        assert 0.0 <= quote["accrued"] <= coupon * (1.0 + 1e-9)
    for d in range(1, 201):
        step = pv[d] - pv[d - 1]
        if d in coupon_days:  # el cupón sale del valor: PV(d−1) ≈ PV(d) + cupón
            assert abs((pv[d - 1] - pv[d]) - coupon) < 0.02 * coupon, d
        else:  # sin escalón: solo el devengo de un día
            assert abs(step) < 0.05 * coupon, d


def test_bond_accrued_interest_grows_linearly_between_coupons(app, client):
    tid = _book(client, "bond", BOND)
    _roll(client, "A10", 10)
    _roll(client, "A20", 20)
    a10 = _flows(client, tid, "A10")["bond"]["accrued"]
    a20 = _flows(client, tid, "A20")["bond"]["accrued"]
    assert a10 == pytest.approx(2.0 * 10.0 / 365.0 * 4.0, rel=1e-9)  # cupón × (10/365) / (1/4)
    assert a20 == pytest.approx(2.0 * a10, rel=1e-9)


def test_bond_quote_is_none_until_it_is_alive_and_after_it_matures(client):
    tid = _book(client, "bond", {**BOND, "periods": 2, "frequency": 12.0})  # vence el día 61
    _roll(client, "B70", 70)
    assert _flows(client, tid, "B70")["bond"] is None
    assert _flows(client, tid, "MX-DEMO")["bond"]["currency"] == "MXN"


# ------------------------------------------------------------------ flujos del bono

def test_bond_flows_settle_coupons_and_then_the_redemption(client):
    params = {**BOND, "periods": 2, "frequency": 12.0}  # cupones los días 30 y 61 (vencimiento)
    tid = _book(client, "bond", params)
    coupon = 100.0 * 0.08 / 12.0
    _roll(client, "F40", 40)
    settled, projected = _split(_flows(client, tid, "F40"))
    assert [(f["date"], f["kind"]) for f in settled] == [(_iso(30), "coupon")]
    assert settled[0]["amount"] == pytest.approx(coupon, rel=1e-12)
    assert settled[0]["currency"] == "MXN"
    assert [f["date"] for f in projected] == [_iso(61)]
    assert projected[0]["amount"] == pytest.approx(coupon + 100.0, rel=1e-12)

    _roll(client, "F70", 70)
    body = _flows(client, tid, "F70")
    settled, projected = _split(body)
    assert [(f["date"], f["kind"]) for f in settled] == [
        (_iso(30), "coupon"), (_iso(61), "coupon"), (_iso(61), "redemption")
    ]
    assert settled[2]["amount"] == 100.0
    assert projected == [] and body["bond"] is None
    assert "no_settlement" not in [w["code"] for w in body["warnings"]]


def test_bond_coupon_dated_on_the_snapshot_is_settled_and_not_in_the_value(client):
    params = {**BOND, "periods": 2, "frequency": 12.0}
    tid = _book(client, "bond", params)
    _roll(client, "G30", 30)
    settled, projected = _split(_flows(client, tid, "G30"))
    assert [f["date"] for f in settled] == [_iso(30)]
    assert [f["date"] for f in projected] == [_iso(61)]


def _settled_in_mxn(app, trade_id, snap_id):
    """`(flujos, avisos)` de `settlement.settled_flows` (traen `amount_mxn`) hasta el `as_of` del snapshot."""
    conn = connect(app.config["DESK_DB"])
    try:
        trade = portfolio.get_trade(conn, trade_id)
        mkt = market.load_context(conn, snap_id)
        fixings = fixing_store.load_all(conn)
    finally:
        conn.close()
    return settlement.settled_flows(
        trade, fixings, trade["trade_date"] - timedelta(days=1), mkt.as_of, mkt.spot, mkt
    )


def test_usd_bond_converts_its_flows_with_the_fix_or_the_spot(app, client):
    params = {"curve": "SOFR", "face": 100.0, "coupon_rate": 0.05, "periods": 4, "frequency": 12.0}
    tid = _book(client, "bond", params)
    _roll(client, "U40", 40)
    coupon = 100.0 * 0.05 / 12.0
    body = _flows(client, tid, "U40")
    settled, projected = _split(body)
    assert len(settled) == 1 and settled[0]["currency"] == "USD"
    assert settled[0]["amount"] == pytest.approx(coupon, rel=1e-12)
    assert [w["code"] for w in body["warnings"]] == ["fx_fallback"]
    assert all(f["currency"] == "USD" for f in projected) and len(projected) == 3
    assert body["bond"]["currency"] == "USD"
    flows, warnings = _settled_in_mxn(app, tid, "U40")  # sin FIX: spot del snapshot
    assert flows[0]["amount_mxn"] == pytest.approx(coupon * _context(app, "U40").spot, rel=1e-12)
    assert [w["code"] for w in warnings] == ["fx_fallback"]
    _csv(client, "USDMXN", [19.5] * 40)  # con FIX publicado se usa el de la fecha del cupón
    flows, warnings = _settled_in_mxn(app, tid, "U40")
    assert warnings == []
    assert flows[0]["amount_mxn"] == pytest.approx(coupon * 19.5, rel=1e-12)
    assert _flows(client, tid, "U40")["warnings"] == []


# ------------------------------------------------------------------------------ P&L

def test_bond_pnl_over_200_days_is_the_value_change_plus_the_settled_coupons(client):
    tid = _book(client, "bond", BOND)
    _roll(client, "P200", 200)
    body, rows = _pnl(client, "MX-DEMO", "P200")
    row = rows[tid]
    assert row["warnings"] == []
    assert row["settled"] == pytest.approx(2 * 2.0, rel=1e-12)  # cupones de los días 91 y 182
    assert row["pnl"] == pytest.approx(row["pv_to"] - row["pv_from"] + row["settled"], abs=1e-9)
    _assert_adds_up(body)


def test_bond_pnl_across_its_maturity_includes_the_redemption(client):
    tid = _book(client, "bond", {**BOND, "periods": 2})  # cupones los días 91 y 182 (vencimiento)
    _roll(client, "P200", 200)
    body, rows = _pnl(client, "MX-DEMO", "P200")
    row = rows[tid]
    assert row["status_to"] == "vencida" and row["pv_to"] == 0 and row["warnings"] == []
    assert row["settled"] == pytest.approx(2.0 + 2.0 + 100.0, rel=1e-12)
    assert row["pnl"] == pytest.approx(row["settled"] - row["pv_from"], abs=1e-9)
    _assert_adds_up(body)


def test_cap_still_has_no_settlement(client):
    tid = _book(client, "cap_floor", {**CAP, "periods": 1})
    _roll(client, "C40", 40)
    body = _flows(client, tid, "C40")
    assert body["flows"] == [] and body["bond"] is None
    assert [w["code"] for w in body["warnings"]] == ["no_settlement"]


# --------------------------------------------------------------------- cap/floor exacto

def _hand_cap(ctx, params, starts_days, elapsed):
    """Cap armado a mano con los caplets que quedan: `starts_days` son las fronteras en días desde el inicio."""
    hw = ctx.hw[params["curve"]]
    kind = qfpy.CapFloorType.Cap if params["cap_type"] == "cap" else qfpy.CapFloorType.Floor
    times = [(d - elapsed) / 365.0 for d in starts_days]
    return qfpy.CapFloor(
        kind, params["notional"], params["strike"], times, hw["a"], hw["sigma"],
        qfpy.DayCountConvention.ACT_360,
    )


def test_cap_aged_30_days_values_only_the_caplets_that_have_not_fixed(app, client):
    tid = _book(client, "cap_floor", CAP)  # caplets sobre [28(k−1), 28k], k = 1..13
    snap = _roll(client, "K30", 30)
    ctx = _context(app, snap)
    # a +30 el caplet 1 ya se pagó y el 2 (inicio día 28) ya fijó: quedan k = 3..13
    expected = _hand_cap(ctx, CAP, [28 * k for k in range(2, 14)], 30).price(ctx.curves["TIIE-F"])
    row = _rows(client, snap)[tid]
    assert row["status"] == "viva" and row["error"] is None
    assert row["pv_mxn"] == pytest.approx(expected, rel=1e-9)
    full = _price(client, "cap_floor", snap, CAP)["pv_mxn"]
    assert row["pv_mxn"] < full


def test_cap_whose_caplet_fixes_on_the_snapshot_date_keeps_it_at_intrinsic_value(app, client):
    tid = _book(client, "cap_floor", {**CAP, "strike": 0.01})  # muy dentro del dinero
    snap = _roll(client, "K28", 28)
    ctx = _context(app, snap)
    params = {**CAP, "strike": 0.01}
    expected = _hand_cap(ctx, params, [28 * k for k in range(1, 14)], 28).price(ctx.curves["TIIE-F"])
    assert _rows(client, snap)[tid]["pv_mxn"] == pytest.approx(expected, rel=1e-9)


def test_sofr_cap_ages_with_annual_periods_and_values_in_mxn(app, client):
    params = {"curve": "SOFR", "cap_type": "cap", "notional": 1e6, "strike": 0.03, "periods": 5}
    tid = _book(client, "cap_floor", params)
    snap = _roll(client, "K400", 400)  # caplet 2 (inicio 365) ya fijó: quedan k = 3..5
    ctx = _context(app, snap)
    usd = _hand_cap(ctx, params, [365 * k for k in range(2, 6)], 400).price(ctx.curves["SOFR"])
    row = _rows(client, snap)[tid]
    assert row["pv"] == pytest.approx(usd, rel=1e-9)
    assert row["pv_mxn"] == pytest.approx(usd * ctx.spot, rel=1e-9)


def test_cap_with_every_caplet_already_fixed_is_alive_but_worth_nothing(app, client):
    tid = _book(client, "cap_floor", {**CAP, "periods": 2})  # vence el día 56; el caplet 2 fija el día 28
    snap = _roll(client, "K30", 30)
    row = _rows(client, snap)[tid]
    assert row["status"] == "viva" and row["error"] is None
    assert row["pv"] == 0.0 and row["pv_mxn"] == 0.0
    trade, terms, mkt = _live(app, tid, snap)
    assert aging.aged_cap_floor(trade, terms, mkt) is None
    assert aging.cap_floor_pv_mxn(trade, terms, mkt) == 0.0


# --------------------------------------------------------------- colateral y curva

def test_usd_collateral_discounts_a_tiie_bond_and_cap_with_the_csa_curve(app, client):
    bond = _book(client, "bond", BOND)
    cap = _book(client, "cap_floor", CAP)
    snap = _roll(client, "S40", 40)
    trade, terms, mkt = _live(app, bond, snap)
    usd = mkt.with_collateral("USD")
    assert usd.mxn_discount == "MXN-USD"
    csa, tiie = usd.curves["MXN-USD"], usd.curves["TIIE-F"]
    # bono a mano con los pagos que quedan a +40 (cupones de los días 91, 182, ...)
    pay = [i / 4.0 - 40 / 365.0 for i in range(1, 13)]  # a +40 siguen los 12 pagos (el 1.º es el día 91)
    expected = qfpy.Bond(100.0, 0.08, 4.0, pay, -40 / 365.0).price(csa)
    assert aging.bond_pv_mxn(trade, terms, usd) == pytest.approx(expected, rel=1e-12)
    assert aging.bond_pv_mxn(trade, terms, mkt) != aging.bond_pv_mxn(trade, terms, usd)
    quote = aging.bond_quote(trade, terms, usd)
    assert quote["dirty"] == pytest.approx(expected, rel=1e-12)
    assert quote["dirty"] - quote["clean"] - quote["accrued"] == pytest.approx(0.0, abs=1e-9)

    trade, terms, mkt = _live(app, cap, snap)
    usd = mkt.with_collateral("USD")
    hand = _hand_cap(usd, CAP, [28 * k for k in range(2, 14)], 40)
    assert aging.cap_floor_pv_mxn(trade, terms, usd) == pytest.approx(
        hand.price_dual(tiie, csa), rel=1e-12
    )


def test_sofr_products_ignore_the_collateral_curve(app, client):
    params = {"curve": "SOFR", "face": 100.0, "coupon_rate": 0.05, "periods": 4, "frequency": 1.0}
    tid = _book(client, "bond", params)
    snap = _roll(client, "S10", 10)
    trade, terms, mkt = _live(app, tid, snap)
    assert aging.bond_pv_mxn(trade, terms, mkt.with_collateral("USD")) == aging.bond_pv_mxn(trade, terms, mkt)


# ------------------------------------------------------------------ inicio futuro

def test_bond_that_starts_in_the_future_keeps_its_calendar_and_has_no_accrued(app, client):
    tid = _book(client, "bond", {**BOND, "periods": 4}, start_date=_iso(14))
    row = _rows(client, "MX-DEMO")[tid]
    ctx = _context(app, "MX-DEMO")
    # a +14 días del inicio los pagos caen en i/4 años + 14/365 años desde el as_of
    pay = [i / 4.0 + 14 / 365.0 for i in range(1, 5)]
    expected = qfpy.Bond(100.0, 0.08, 4.0, pay, 0.0).price(ctx.curves["TIIE-F"])
    assert row["status"] == "viva" and row["error"] is None
    assert row["pv_mxn"] == pytest.approx(expected, rel=1e-9)
    assert _flows(client, tid, "MX-DEMO")["bond"]["accrued"] == 0.0


def test_bond_pay_days_match_the_maturity_date_for_any_frequency():
    for frequency in (0.5, 1.0, 2.0, 3.0, 4.0, 6.0, 10.0, 12.0, 52.0, 365.0):
        for periods in (1, 3, 7, 24):
            maturity = portfolio._tenor_days("bond", {"periods": periods, "frequency": frequency})
            assert aging._pay_day(periods, frequency) == maturity
