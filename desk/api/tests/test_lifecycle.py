"""`lifecycle.state`: estado derivado de la operación y sus eventos (función pura, sin DB)."""
import random
from datetime import date, timedelta

import pytest

from desk.api.lifecycle import NOTIONAL_FIELD, STATUSES, state

TRADE_DATE = date(2026, 11, 10)
MATURITY = date(2027, 2, 9)

PARAMS = {
    "irs": {"curve": "TIIE-F", "side": "payer", "notional": 1e6, "periods": 13, "fixed_rate": 0.07},
    "cap_floor": {"curve": "TIIE-F", "cap_type": "cap", "notional": 1e6, "periods": 13, "strike": 0.07},
    "swaption": {"curve": "TIIE-F", "swaption_type": "payer", "notional": 1e6, "strike": 0.07,
                 "expiry_years": 0.25, "swap_tenor_years": 2.0},
    "fx_forward": {"side": "buy", "notional_usd": 1e6, "days": 91, "strike": 19.0},
    "fx_option": {"side": "buy", "option_type": "call", "notional_usd": 1e6, "days": 91, "strike": 19.0},
    "bond": {"curve": "TIIE-F", "face": 1e6, "coupon_rate": 0.08, "periods": 10, "frequency": 4.0},
    "equity_option": {"option_type": "call", "spot": 55.0, "strike": 55.0, "volatility": 0.25, "rate": 0.07,
                      "dividend_yield": 0.02, "maturity_years": 1.0, "quantity": 100.0},
}


def make_trade(product="fx_forward", params=None, trade_date=TRADE_DATE, maturity=MATURITY):
    return {
        "id": 1,
        "product": product,
        "counterparty": "Banco Test",
        "trade_date": trade_date,
        "start_date": trade_date,
        "maturity_date": maturity,
        "params": dict(PARAMS[product] if params is None else params),
        "created_at": "x",
        "events": [],
    }


def ev(event_id, type, on, data=None):
    return {"id": event_id, "trade_id": 1, "type": type, "event_date": on, "data": data or {},
            "prev_event_id": None, "created_at": "x"}


def day(n):
    return TRADE_DATE + timedelta(days=n)


EXECUTION = ev(1, "execution", TRADE_DATE)


# ------------------------------------------------------------------------------ estados

@pytest.mark.parametrize(
    "on, status",
    [
        (day(-30), "no_pactada"),
        (day(-1), "no_pactada"),
        (day(0), "viva"),
        (day(1), "viva"),
        (MATURITY - timedelta(days=1), "viva"),
        (MATURITY, "vencida"),
        (MATURITY + timedelta(days=400), "vencida"),
    ],
)
def test_status_without_events_beyond_execution(on, status):
    st = state(make_trade(), [EXECUTION], on)
    assert st["status"] == status
    assert st["terms"] == PARAMS["fx_forward"] and st["notional"] == 1e6


def test_status_is_one_of_the_catalog():
    assert set(STATUSES) == {"no_pactada", "viva", "vencida", "terminada", "ejercida"}
    assert state(make_trade(), [], day(5))["status"] in STATUSES


def test_state_works_without_any_event():
    assert state(make_trade(), [], day(5))["status"] == "viva"


def test_not_agreed_yet_keeps_origin_terms():
    st = state(make_trade(), [EXECUTION], day(-1))
    assert st == {"status": "no_pactada", "terms": PARAMS["fx_forward"], "notional": 1e6}


# ------------------------------------------------------------------------ quantity_change

def test_quantity_change_applies_only_from_its_date():
    events = [EXECUTION, ev(2, "quantity_change", day(10), {"notional": 4e5})]
    assert state(make_trade(), events, day(9))["notional"] == 1e6
    assert state(make_trade(), events, day(10))["notional"] == 4e5
    assert state(make_trade(), events, day(50))["notional"] == 4e5
    # el nocional vive también en los términos vigentes, bajo el campo del producto
    assert state(make_trade(), events, day(10))["terms"]["notional_usd"] == 4e5
    assert state(make_trade(), events, day(9))["terms"]["notional_usd"] == 1e6


def test_two_quantity_changes_apply_in_order():
    events = [EXECUTION, ev(2, "quantity_change", day(10), {"notional": 4e5}),
              ev(3, "quantity_change", day(20), {"notional": 2e5})]
    got = [state(make_trade(), events, day(n))["notional"] for n in (5, 10, 15, 20, 60)]
    assert got == [1e6, 4e5, 4e5, 2e5, 2e5]


def test_same_date_events_the_highest_id_wins():
    events = [ev(2, "quantity_change", day(10), {"notional": 4e5}),
              ev(3, "quantity_change", day(10), {"notional": 7e5})]
    assert state(make_trade(), events, day(10))["notional"] == 7e5
    assert state(make_trade(), list(reversed(events)), day(10))["notional"] == 7e5


def test_events_in_any_order_give_the_same_state():
    events = [EXECUTION,
              ev(2, "quantity_change", day(30), {"notional": 5e5}),
              ev(3, "quantity_change", day(10), {"notional": 8e5}),
              ev(4, "quantity_change", day(10), {"notional": 7e5}),
              ev(5, "terms_change", day(20), {"terms": {"strike": 19.5}})]
    rng = random.Random(7)
    for n in (5, 10, 25, 30, 90):
        want = state(make_trade(), events, day(n))
        for _ in range(5):
            shuffled = events[:]
            rng.shuffle(shuffled)
            assert state(make_trade(), shuffled, day(n)) == want
    assert state(make_trade(), events, day(25)) == {
        "status": "viva", "terms": {**PARAMS["fx_forward"], "notional_usd": 7e5, "strike": 19.5},
        "notional": 7e5}


@pytest.mark.parametrize("product", sorted(PARAMS))
def test_quantity_change_writes_the_products_notional_field(product):
    field = NOTIONAL_FIELD[product]
    events = [ev(2, "quantity_change", day(3), {"notional": 123.0})]
    before = state(make_trade(product), events, day(2))
    after = state(make_trade(product), events, day(3))
    assert before["notional"] == PARAMS[product][field]
    assert after["notional"] == 123.0 and after["terms"][field] == 123.0
    assert {k: v for k, v in after["terms"].items() if k != field} == \
        {k: v for k, v in PARAMS[product].items() if k != field}


# ------------------------------------------------------------------------------ cierres

def test_termination_makes_it_terminada_from_its_date_and_never_vencida():
    events = [EXECUTION, ev(2, "termination", day(20), {"amount": 100.0}),
              ev(3, "transfer", day(20), {"amount": 100.0, "currency": "MXN", "cause_event_id": 2})]
    assert state(make_trade(), events, day(19))["status"] == "viva"
    assert state(make_trade(), events, day(20))["status"] == "terminada"
    assert state(make_trade(), events, day(21))["status"] == "terminada"
    assert state(make_trade(), events, MATURITY)["status"] == "terminada"
    assert state(make_trade(), events, MATURITY + timedelta(days=30))["status"] == "terminada"


def test_exercise_makes_it_ejercida_and_never_vencida():
    events = [EXECUTION, ev(2, "exercise", day(40), {"amount": -50.0})]
    assert state(make_trade("fx_option"), events, day(39))["status"] == "viva"
    assert state(make_trade("fx_option"), events, day(40))["status"] == "ejercida"
    assert state(make_trade("fx_option"), events, MATURITY + timedelta(days=1))["status"] == "ejercida"


def test_termination_wins_over_exercise_when_both_are_in_force():
    events = [ev(2, "exercise", day(10), {"amount": 1.0}), ev(3, "termination", day(5), {"amount": 1.0})]
    assert state(make_trade("fx_option"), events, day(7))["status"] == "terminada"
    assert state(make_trade("fx_option"), events, day(4))["status"] == "viva"
    assert state(make_trade("fx_option"), events, day(12))["status"] == "terminada"


def test_not_agreed_wins_over_everything_else():
    # un cierre con fecha anterior al pacto no puede existir por la API, pero la precedencia es fija
    events = [ev(2, "termination", day(-3), {"amount": 1.0})]
    assert state(make_trade(), events, day(-3))["status"] == "no_pactada"


def test_execution_reset_and_transfer_do_not_change_the_state():
    events = [EXECUTION, ev(2, "reset", day(3), {}), ev(3, "transfer", day(4), {"amount": 9.0})]
    assert state(make_trade(), events, day(10)) == state(make_trade(), [], day(10))


# ----------------------------------------------------------------------------- terms_change

def test_terms_change_strike_from_its_date():
    events = [ev(2, "terms_change", day(15), {"terms": {"strike": 19.8}})]
    assert state(make_trade(), events, day(14))["terms"]["strike"] == 19.0
    got = state(make_trade(), events, day(15))
    assert got["terms"] == {**PARAMS["fx_forward"], "strike": 19.8} and got["notional"] == 1e6


def test_terms_change_fixed_rate_of_an_irs():
    events = [ev(2, "terms_change", day(15), {"terms": {"fixed_rate": 0.0725}})]
    got = state(make_trade("irs"), events, day(16))
    assert got["terms"]["fixed_rate"] == 0.0725
    assert {k: v for k, v in got["terms"].items() if k != "fixed_rate"} == \
        {k: v for k, v in PARAMS["irs"].items() if k != "fixed_rate"}


def test_terms_change_and_quantity_change_stack():
    events = [ev(2, "quantity_change", day(5), {"notional": 3e5}),
              ev(3, "terms_change", day(6), {"terms": {"strike": 20.0}}),
              ev(4, "quantity_change", day(7), {"notional": 2e5})]
    got = state(make_trade("fx_option"), events, day(8))
    assert got["terms"] == {**PARAMS["fx_option"], "notional_usd": 2e5, "strike": 20.0}
    assert state(make_trade("fx_option"), events, day(6))["terms"]["notional_usd"] == 3e5


def test_terms_change_is_revalidated_with_the_product():
    from desk.api.errors import ApiError

    events = [ev(2, "terms_change", day(5), {"terms": {"strike": -1.0}})]
    with pytest.raises(ApiError):
        state(make_trade(), events, day(6))


# ------------------------------------------------------------------------------- pureza

def test_state_does_not_mutate_its_inputs():
    trade = make_trade()
    events = [EXECUTION, ev(2, "quantity_change", day(3), {"notional": 5.0}),
              ev(3, "terms_change", day(4), {"terms": {"strike": 20.0}})]
    snapshot_events = [dict(e) for e in events]
    got = state(trade, events, day(10))
    got["terms"]["strike"] = 999.0
    assert trade["params"] == PARAMS["fx_forward"]
    assert events == snapshot_events


def test_unreadable_params_raise_value_error():
    trade = make_trade()
    trade["params"] = None
    with pytest.raises(ValueError):
        state(trade, [], day(1))
