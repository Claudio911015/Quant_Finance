"""Coberturas, T3: `POST /api/hedges/<id>/periods` (medición D4 y asientos D5; R2, R3, R4, R5, R6 y R8 de cierre)."""
import json
import sqlite3
from datetime import date, timedelta

import pytest

from desk.api import hedge_measure, hedges
from desk.api.tests.hedge_fixture import designate, load_fixings, market_forward, par_irs, roll

D0 = date(2026, 11, 10)
LOAN_END = D0 + timedelta(days=364)  # 13 periodos de 28 días: el swap tiene exactamente las fechas del crédito
FIXED_END = D0 + timedelta(days=28 * 26)
FWD_END = D0 + timedelta(days=20)
FX_END = date(2027, 5, 11)
NOTIONAL = 500e6
TIIE = 0.07  # por encima de la tasa par de la designación: el swap que paga fija gana

SETTLEMENT_MEMO = "Liquidación del derivado a resultados"


def _loan(**over):
    return {
        "index": "TIIE-F", "notional": NOTIONAL, "start_date": D0.isoformat(),
        "maturity_date": LOAN_END.isoformat(), "side": "pays_floating", **over,
    }


def _fixed_loan(**over):
    return _loan(**{"notional": 300e6, "maturity_date": FIXED_END.isoformat(), "side": "pays_fixed", **over})


def _fx(**over):
    return {"amount_usd": 10e6, "date": FX_END.isoformat(), "side": "buy_usd", **over}


def _hedge(client, notional=NOTIONAL, irs_side="payer", **over):
    """`par_irs` + designación de un crédito variable de `NOTIONAL`; devuelve `(operación, id de la cobertura)`."""
    trade = par_irs(client, "TIIE-F", notional, D0, LOAN_END, side=irs_side)
    r = designate(client, trade["id"], "floating_loan", _loan(), **over)
    assert r.status_code == 201, r.get_json()
    return trade, r.get_json()["id"]


def _snapshots(client, *days):
    """Rueda MX-DEMO a `D1`, `D2`… (días desde la designación) y carga TIIE-F hasta el último; devuelve los ids."""
    ids = []
    as_of = D0
    for i, d in enumerate(days, 1):
        as_of = date.fromisoformat(roll(client, "MX-DEMO", "D%d" % i, d))
        ids.append("D%d" % i)
    load_fixings(client, "TIIE-F", D0, as_of, TIIE)
    return ids


def _close(client, hid, snapshot):
    return client.post("/api/hedges/%d/periods" % hid, json={"snapshot": snapshot})


def _closed(client, hid, snapshot):
    r = _close(client, hid, snapshot)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _cents(x):
    return int(round(x * 100))


def _net(entries, account, skip_memo=None):
    """Cargos menos abonos, en centavos, de las líneas de `account`."""
    return sum(
        _cents(e["debit"]) - _cents(e["credit"])
        for e in entries
        if e["account"] == account and e["memo"] != skip_memo
    )


def _balanced(entries):
    return sum(_cents(e["debit"]) for e in entries) == sum(_cents(e["credit"]) for e in entries)


def _accounts(entries):
    return {e["account"] for e in entries}


def _sql(app, sql, args=()):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        cur = conn.execute(sql, args)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _counts(app):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        return [
            conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
            for t in ("hedge_relationships", "hedge_events", "hedge_periods")
        ]
    finally:
        conn.close()


# ------------------------------------------------------------------------- R2: cobertura perfecta

def test_identical_swap_is_perfectly_effective_in_every_period(client):
    _, hid = _hedge(client)
    d1, d2 = _snapshots(client, 35, 70)
    for snapshot in (d1, d2):
        p = _closed(client, hid, snapshot)
        assert p["trade_status"] == "viva" and p["hedge_type"] == "cash_flow" and p["data_quality"] == "synthetic"
        assert abs(p["ineffectiveness"]) <= 1e-6 * NOTIONAL
        assert p["d_oci"] == pytest.approx(p["d_inst_cum"], abs=1e-6 * NOTIONAL)
        assert p["d_inst_cum"] != 0  # la prueba no es trivial: el swap se movió
    assert p["oci"] == pytest.approx(p["inst_cum"], abs=1e-6 * NOTIONAL)


def test_matching_forward_is_perfectly_effective_before_and_at_maturity(client):
    trade = market_forward(client, "buy", 10e6, FX_END)
    r = designate(client, trade["id"], "forecast_fx", _fx())
    assert r.status_code == 201, r.get_json()
    hid = r.get_json()["id"]
    roll(client, "MX-DEMO", "D1", 35)
    roll(client, "MX-DEMO", "D2", (FX_END - D0).days)  # el día del vencimiento
    load_fixings(client, "USDMXN", FX_END, FX_END + timedelta(days=1), trade["params"]["strike"] + 0.25)
    spot = client.get("/api/market/snapshots/MX-DEMO").get_json()["fx"]["spot"]
    tol = 1e-6 * 10e6 * spot
    before = _closed(client, hid, "D1")
    at_maturity = _closed(client, hid, "D2")
    assert before["trade_status"] == "viva" and at_maturity["trade_status"] == "vencida"
    for p in (before, at_maturity):
        assert abs(p["ineffectiveness"]) <= tol
        assert p["d_oci"] == pytest.approx(p["d_inst_cum"], abs=tol)
    assert before["d_inst_cum"] != 0


# ------------------------------------------------------------------------- R3: sobre y subcobertura

def test_over_hedge_books_only_the_hypothetical_change_to_oci(client):
    _, hid = _hedge(client, notional=1.2 * NOTIONAL, hedge_ratio=1.0)
    (d1,) = _snapshots(client, 35)  # D1 cruza el cupón del día 28
    p = _closed(client, hid, d1)
    assert abs(p["oci"]) == pytest.approx(abs(p["hypo_cum"]), abs=1e-9)
    # C3: lo liquidado entra a la regla del menor, así que el exceso del cupón también es inefectividad.
    assert p["ineffectiveness"] == pytest.approx(
        p["d_inst_cum"] + p["settled_period"] - p["d_oci"] - p["recycled"], abs=1e-9
    )
    assert p["ineffectiveness"] == pytest.approx(p["inst_total"] - p["hypo_total"], abs=1e-6)
    assert p["ineffectiveness"] != 0
    assert abs(p["inst_cum"]) > abs(p["hypo_cum"])


def test_under_hedge_books_the_whole_instrument_change_to_oci(client):
    _, hid = _hedge(client, notional=0.8 * NOTIONAL)
    d1, d2 = _snapshots(client, 35, 70)
    for snapshot in (d1, d2):
        p = _closed(client, hid, snapshot)
        assert abs(p["oci"]) == pytest.approx(abs(p["inst_cum"]), abs=1e-9)
        assert p["ineffectiveness"] == pytest.approx(0, abs=1e-6)
        assert abs(p["inst_cum"]) < abs(p["hypo_cum"])


def test_opposite_signs_leave_oci_at_zero_and_everything_in_profit_or_loss(client):
    _, hid = _hedge(client, irs_side="receiver")
    (d1,) = _snapshots(client, 35)
    p = _closed(client, hid, d1)
    assert p["inst_cum"] * p["hypo_cum"] < 0
    assert p["oci"] == 0 and p["d_oci"] == 0 and p["effective_cum"] == 0 and p["recycled"] == 0
    # Sin parte efectiva, todo lo que hizo el instrumento (cambio de valor y cupón) es inefectividad.
    assert p["ineffectiveness"] == pytest.approx(p["d_inst_cum"] + p["settled_period"], abs=1e-9)
    assert p["settled_period"] != 0
    assert _net(p["entries"], hedges.ACC_OCI) == 0 and hedges.ACC_RECYCLING not in _accounts(p["entries"])


# ------------------------------------------------------------------------- R4: fracción y cuadre

def test_fraction_half_balances_every_period_and_matches_half_the_trade_pnl(client):
    trade, hid = _hedge(client, fraction=0.5)
    d1, d2 = _snapshots(client, 35, 70)
    periods = [_closed(client, hid, s) for s in (d1, d2)]
    for p in periods:
        assert _balanced(p["entries"])
        assert abs(p["identity_residual"]) <= 1e-6
        assert p["fraction"] == 0.5
        pnl = client.get("/api/pnl?from=%s&to=%s" % (p["prev_snapshot"], p["snapshot"])).get_json()
        row = next(r for r in pnl["rows"] if r["id"] == trade["id"])
        assert p["d_inst_cum"] + p["settled_period"] == pytest.approx(0.5 * row["pnl"], abs=1e-6)
        assert p["instrument_pnl"] == pytest.approx(p["d_inst_cum"] + p["settled_period"], abs=1e-9)
    assert _balanced([e for p in periods for e in p["entries"]])


# ------------------------------------------------------------------------- R5: reciclaje

def test_a_coupon_in_the_period_is_settled_in_cash_and_recycled(client):
    _, hid = _hedge(client)
    d1, d2 = _snapshots(client, 35, 70)
    for snapshot in (d1, d2):
        p = _closed(client, hid, snapshot)
        assert len(p["settled_flows"]) == 1 and p["settled_flows"][0]["kind"] == "coupon"
        assert p["settled_period"] == pytest.approx(p["settled_flows"][0]["amount_mxn"], abs=1e-9)
        assert p["recycled"] == pytest.approx(p["settled_period"], abs=1e-6) and p["settled_period"] != 0
        assert p["hypo_settled_period"] == pytest.approx(p["settled_period"], abs=1e-6)
        assert _net(p["entries"], hedges.ACC_CASH) == _cents(round(p["settled_period"], 2))
        assert abs(_net(p["entries"], hedges.ACC_RECYCLING) + _cents(round(p["recycled"], 2))) <= 1
    assert hedges.ACC_INEFFECTIVENESS not in _accounts(p["entries"])  # cobertura perfecta: sin inefectividad


def test_forward_settlement_is_recycled_and_the_reserve_ends_at_zero(client):
    trade = market_forward(client, "buy", 10e6, FWD_END)
    r = designate(client, trade["id"], "forecast_fx", _fx(date=FWD_END.isoformat()))
    assert r.status_code == 201, r.get_json()
    hid = r.get_json()["id"]
    roll(client, "MX-DEMO", "D1", 10)
    roll(client, "MX-DEMO", "D2", 35)
    fix = trade["params"]["strike"] + 0.5
    load_fixings(client, "USDMXN", FWD_END, FWD_END + timedelta(days=1), fix)  # lunes: hábil
    first = _closed(client, hid, "D1")
    last = _closed(client, hid, "D2")
    assert first["trade_status"] == "viva" and last["trade_status"] == "vencida" and last["pv_inst"] == 0
    assert first["settled_period"] == 0 and first["oci"] != 0
    assert last["oci"] == pytest.approx(0, abs=1e-6)
    expected = 10e6 * (fix - trade["params"]["strike"])
    assert last["settled_period"] == pytest.approx(expected, abs=1e-6)
    total = sum(p["ineffectiveness"] + p["recycled"] for p in (first, last))
    assert total == pytest.approx(expected, abs=1e-6)
    assert _balanced(first["entries"]) and _balanced(last["entries"])


# ------------------------------------------------------------------------- C3: regla del menor sobre acumulados con lo liquidado

def test_over_hedge_with_coupons_recycles_only_what_the_hypothetical_settles(client):
    _, hid = _hedge(client, notional=1.2 * NOTIONAL, hedge_ratio=1.0)
    d1, d2 = _snapshots(client, 35, 70)
    periods = [_closed(client, hid, s) for s in (d1, d2)]
    for p in periods:
        assert abs(p["settled_period"]) > abs(p["hypo_settled_period"]) > 0
        assert p["settled_period"] == pytest.approx(1.2 * p["hypo_settled_period"], abs=1e-6)
        assert p["recycled"] == pytest.approx(p["hypo_settled_period"], abs=1e-9)  # no todo el cupón del swap
        assert p["effective_cum"] == pytest.approx(p["hypo_total"], abs=1e-9)
        assert abs(p["inst_total"]) > abs(p["hypo_total"])
        assert abs(p["identity_residual"]) <= 1e-6 and _balanced(p["entries"])
    # La reserva es lo efectivo acumulado menos lo reciclado, y el exceso del cupón sale por inefectividad.
    assert periods[1]["oci"] == pytest.approx(periods[1]["effective_cum"] - sum(p["recycled"] for p in periods), abs=1e-9)
    assert periods[1]["oci"] == pytest.approx(periods[1]["hypo_cum"], abs=1e-6)
    total_ineffectiveness = sum(p["ineffectiveness"] for p in periods)
    assert total_ineffectiveness == pytest.approx(periods[1]["inst_total"] - periods[1]["hypo_total"], abs=1e-6)
    assert _net(periods[0]["entries"], hedges.ACC_RECYCLING) == -_cents(round(periods[0]["hypo_settled_period"], 2))


def test_under_hedge_with_coupons_recycles_the_whole_instrument_settlement(client):
    _, hid = _hedge(client, notional=0.8 * NOTIONAL)
    d1, d2 = _snapshots(client, 35, 70)
    for snapshot in (d1, d2):
        p = _closed(client, hid, snapshot)
        assert abs(p["settled_period"]) < abs(p["hypo_settled_period"])
        assert p["recycled"] == pytest.approx(p["settled_period"], abs=1e-9)
        assert p["effective_cum"] == pytest.approx(p["inst_total"], abs=1e-9)
        assert abs(p["oci"]) == pytest.approx(abs(p["inst_cum"]), abs=1e-6)
        assert p["ineffectiveness"] == pytest.approx(0, abs=1e-6)


def test_the_final_close_leaves_the_reserve_and_the_booked_balances_at_exactly_zero(client):
    """C3/C4: cierre final con la operación `vencida` y un forward a mercado en tres cierres, con fracción 0.7."""
    trade = market_forward(client, "buy", 10e6, FWD_END)
    r = designate(client, trade["id"], "forecast_fx", _fx(date=FWD_END.isoformat()), fraction=0.7)
    assert r.status_code == 201, r.get_json()
    hid = r.get_json()["id"]
    for i, days in enumerate((5, 12, 35), 1):
        roll(client, "MX-DEMO", "F%d" % i, days)
    fix = trade["params"]["strike"] + 0.37
    load_fixings(client, "USDMXN", FWD_END, FWD_END + timedelta(days=1), fix)
    periods = [_closed(client, hid, "F%d" % i) for i in (1, 2, 3)]
    final = periods[-1]
    assert [p["trade_status"] for p in periods] == ["viva", "viva", "vencida"]
    assert final["oci"] == 0 and final["pv_inst"] == 0
    entries = [e for p in periods for e in p["entries"]]
    assert _net(entries, hedges.ACC_OCI) == 0 and _net(entries, hedges.ACC_DERIVATIVE) == 0
    expected = 0.7 * 10e6 * 0.37
    assert _net(entries, hedges.ACC_CASH) == _cents(round(expected, 2))
    assert sum(p["recycled"] for p in periods) == pytest.approx(expected, abs=1e-6)
    assert all(abs(p["identity_residual"]) <= 1e-6 and _balanced(p["entries"]) for p in periods)
    assert client.get("/api/hedges/%d" % hid).get_json()["oci_balance"] == 0


def test_the_final_close_zeroes_the_reserve_even_when_the_hypothetical_outlives_the_instrument(client):
    """El forward vence antes que la partida: la reserva no puede quedar para un cierre que ya no habrá."""
    trade = market_forward(client, "buy", 10e6, FWD_END)
    r = designate(client, trade["id"], "forecast_fx", _fx(date=(FWD_END + timedelta(days=30)).isoformat()))
    assert r.status_code == 201, r.get_json()
    hid = r.get_json()["id"]
    roll(client, "MX-DEMO", "F1", 10)
    roll(client, "MX-DEMO", "F2", 25)
    load_fixings(client, "USDMXN", FWD_END, FWD_END + timedelta(days=1), trade["params"]["strike"] + 0.25)
    first, final = _closed(client, hid, "F1"), _closed(client, hid, "F2")
    assert first["oci"] != 0 and final["trade_status"] == "vencida"
    assert final["oci"] == 0 and final["d_oci"] == pytest.approx(-first["oci"], abs=1e-9)
    assert abs(final["identity_residual"]) <= 1e-6 and _balanced(final["entries"])


# ------------------------------------------------------------------------- C4: el acumulado de asientos coincide con los saldos

def test_accumulated_entries_match_the_rounded_balances_after_several_closes(client):
    _, hid = _hedge(client)
    d1, d2, d3 = _snapshots(client, 35, 70, 105)
    periods = [_closed(client, hid, s) for s in (d1, d2, d3)]
    entries = [e for p in periods for e in p["entries"]]
    last = periods[-1]
    assert _net(entries, hedges.ACC_DERIVATIVE) == _cents(round(last["inst_cum"], 2))
    assert _net(entries, hedges.ACC_OCI) == -_cents(round(last["oci"], 2))
    cash = sum(p["settled_period"] for p in periods)
    assert _net(entries, hedges.ACC_CASH) == _cents(round(cash, 2))
    assert _balanced(entries)


# ------------------------------------------------------------------------- R6: valor razonable

def test_fair_value_hedge_of_a_fixed_loan_books_everything_to_profit_or_loss(client):
    trade = par_irs(client, "TIIE-F", 300e6, D0, FIXED_END, side="receiver")
    r = designate(client, trade["id"], "fixed_loan", _fixed_loan(), hedge_type="fair_value")
    assert r.status_code == 201, r.get_json()
    hid = r.get_json()["id"]
    d1, d2 = _snapshots(client, 35, 70)  # D1 cruza el cupón del día 28
    for snapshot in (d1, d2):
        p = _closed(client, hid, snapshot)
        assert p["hedge_type"] == "fair_value" and p["oci"] == 0 and p["d_oci"] == 0 and p["recycled"] == 0
        assert abs(p["ineffectiveness"]) <= 1e-6 * 300e6
        assert p["item_adjustment"] != 0 and p["settled_period"] != 0
        assert abs(p["identity_residual"]) <= 1e-6
        e = p["entries"]
        assert {hedges.ACC_DERIVATIVE, hedges.ACC_ITEM_ADJ, hedges.ACC_CASH, hedges.ACC_FV_RESULT} == _accounts(e)
        assert _balanced(e)
        # El neto de resultados sin la línea de liquidación es la inefectividad (abono = ganancia).
        net = -_net(e, hedges.ACC_FV_RESULT, skip_memo=SETTLEMENT_MEMO)
        assert net / 100 == pytest.approx(p["ineffectiveness"], abs=0.021)  # dos saldos redondeados
        assert p["fv_result"] == pytest.approx(p["ineffectiveness"] + p["settled_period"], abs=1e-9)


# ------------------------------------------------------------------------- asientos: redondeo (P5)

def test_rounding_residual_is_created_in_the_main_result_account_when_missing():
    entries = hedge_measure.journal(
        "cash_flow",
        {"ineffectiveness": 0.004, "recycled": 0.0},
        {hedges.ACC_DERIVATIVE: 0.016, hedges.ACC_OCI: -0.004, hedges.ACC_CASH: 0.0},
    )
    assert [(e["account"], e["debit"], e["credit"]) for e in entries] == [
        (hedges.ACC_DERIVATIVE, 0.02, 0.0),
        (hedges.ACC_INEFFECTIVENESS, 0.0, 0.02),
    ]
    assert entries[1]["memo"] == "Residuo de redondeo"


def test_rounding_residual_is_absorbed_by_the_last_main_result_line():
    figures = {"ineffectiveness": 0.014, "recycled": 0.0}
    entries = hedge_measure.journal(
        "cash_flow", figures, {hedges.ACC_DERIVATIVE: 0.026, hedges.ACC_OCI: -0.006, hedges.ACC_CASH: 0.0}
    )
    assert [(e["account"], e["debit"], e["credit"]) for e in entries] == [
        (hedges.ACC_DERIVATIVE, 0.03, 0.0),
        (hedges.ACC_OCI, 0.0, 0.01),
        (hedges.ACC_INEFFECTIVENESS, 0.0, 0.02),
    ]
    assert entries[2]["memo"] == "Inefectividad del periodo" and _balanced(entries)


def test_balance_accounts_book_the_difference_of_rounded_balances_so_nothing_drifts():
    """C4: tres periodos que suben 0.004 cada uno suman el saldo redondeado (0.01), no 3 × redondeo(0.004) = 0."""
    booked = {}
    for k in (1, 2, 3):
        balance = 0.004 * k
        entries = hedge_measure.journal(
            "cash_flow", {"ineffectiveness": 0.0, "recycled": 0.0},
            {hedges.ACC_DERIVATIVE: balance, hedges.ACC_OCI: -balance, hedges.ACC_CASH: 0.0}, booked,
        )
        for e in entries:
            booked[e["account"]] = booked.get(e["account"], 0) + _cents(e["debit"]) - _cents(e["credit"])
        assert _balanced(entries)
    assert booked[hedges.ACC_DERIVATIVE] == 1 and booked[hedges.ACC_OCI] == -1  # redondeo(0.012) = 0.01, sin deriva


def test_fair_value_counterparts_are_the_exact_negatives_of_the_balance_lines():
    entries = hedge_measure.journal(
        "fair_value", {},
        {hedges.ACC_DERIVATIVE: 0.026, hedges.ACC_ITEM_ADJ: -0.026, hedges.ACC_CASH: 0.014},
    )
    assert _balanced(entries)
    assert [(e["account"], e["debit"], e["credit"]) for e in entries] == [
        (hedges.ACC_DERIVATIVE, 0.03, 0.0), (hedges.ACC_FV_RESULT, 0.0, 0.03),
        (hedges.ACC_ITEM_ADJ, 0.0, 0.03), (hedges.ACC_FV_RESULT, 0.03, 0.0),
        (hedges.ACC_CASH, 0.01, 0.0), (hedges.ACC_FV_RESULT, 0.0, 0.01),
    ]


# ------------------------------------------------------------------------- persistencia

def test_closing_stores_the_period_and_the_event_and_updates_the_detail(app, client):
    _, hid = _hedge(client)
    (d1,) = _snapshots(client, 35)
    before = _counts(app)
    p = _closed(client, hid, d1)
    assert _counts(app) == [before[0], before[1] + 1, before[2] + 1]
    assert (p["snapshot"], p["as_of"], p["prev_snapshot"], p["prev_as_of"]) == (
        "D1", (D0 + timedelta(days=35)).isoformat(), "MX-DEMO", D0.isoformat(),
    )
    detail = client.get("/api/hedges/%d" % hid).get_json()
    assert detail["periods"] == [p]
    assert detail["last_close"] == p["as_of"] and detail["oci_balance"] == p["oci"]
    assert [e["type"] for e in detail["events"]] == ["designation", "period_close"]
    assert detail["events"][1]["data"] == {"period_id": p["id"], "snapshot": "D1", "as_of": p["as_of"]}
    assert detail["events"][1]["event_date"] == p["as_of"]
    assert client.get("/api/hedges?trade_id=%d" % detail["trade_id"]).get_json()["hedges"][0]["periods_count"] == 1


# ------------------------------------------------------------------------- R8: errores de cierre

def test_missing_and_unknown_inputs(app, client):
    _, hid = _hedge(client)
    snaps = _counts(app)
    r = client.post("/api/hedges/%d/periods" % hid, json={})
    assert r.status_code == 400 and r.get_json()["field"] == "snapshot"
    r = _close(client, hid, "NO-EXISTE")
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"
    r = _close(client, 999, "MX-DEMO")
    assert r.status_code == 404 and r.get_json()["field"] == "id"
    assert _counts(app) == snaps


def test_a_dedesignated_relationship_does_not_close_periods(app, client):
    _, hid = _hedge(client)
    (d1,) = _snapshots(client, 35)
    _sql(
        app,
        "INSERT INTO hedge_events (relationship_id, type, event_date, data, created_at)"
        " VALUES (?, 'dedesignation', '2026-11-20', ?, 'x')",
        (hid, json.dumps({"reason": "Prepago", "frozen_oci": 0.0})),
    )
    r = _close(client, hid, d1)
    assert r.status_code == 409 and r.get_json()["field"] == "id"


def test_a_snapshot_not_after_the_last_close_or_the_designation_is_409(app, client):
    _, hid = _hedge(client)
    d1, same_day, between = "D1", "SAME", "D5"
    roll(client, "MX-DEMO", d1, 35)
    roll(client, "MX-DEMO", same_day, 0)
    roll(client, "MX-DEMO", between, 5)
    roll(client, "MX-DEMO", "BEFORE", -3)
    load_fixings(client, "TIIE-F", D0, D0 + timedelta(days=35), TIIE)
    start = _counts(app)
    for snapshot in (same_day, "BEFORE"):  # la designación es de MX-DEMO (as_of = D0)
        r = _close(client, hid, snapshot)
        assert r.status_code == 409 and r.get_json()["field"] == "snapshot", snapshot
        assert r.get_json()["error"].endswith(", la designación de la cobertura")
    assert _counts(app) == start
    _closed(client, hid, d1)
    after_close = _counts(app)
    for snapshot in (d1, between):  # igual y anterior al último cierre
        r = _close(client, hid, snapshot)
        assert r.status_code == 409 and r.get_json()["field"] == "snapshot", snapshot
        assert r.get_json()["error"].endswith(", el último cierre de la cobertura")
    assert _counts(app) == after_close


def test_a_terminated_trade_cannot_close_a_period(app, client):
    trade, hid = _hedge(client)
    (d1,) = _snapshots(client, 35)
    r = client.post(
        "/api/trades/%d/events" % trade["id"],
        json={"type": "termination", "event_date": "2026-12-01", "data": {"amount": 0.0}},
    )
    assert r.status_code == 201, r.get_json()
    start = _counts(app)
    r = _close(client, hid, d1)
    assert r.status_code == 409 and r.get_json()["field"] == "snapshot"
    assert "desdesigna" in r.get_json()["error"]
    assert _counts(app) == start


def test_a_matured_forward_closes_once_with_zero_value_and_then_no_more(app, client):
    trade = market_forward(client, "buy", 10e6, FWD_END)
    r = designate(client, trade["id"], "forecast_fx", _fx(date=FWD_END.isoformat()))
    assert r.status_code == 201, r.get_json()
    hid = r.get_json()["id"]
    roll(client, "MX-DEMO", "D1", 35)
    roll(client, "MX-DEMO", "D2", 50)
    final = _closed(client, hid, "D1")
    assert final["pv_inst"] == 0 and final["trade_status"] == "vencida"
    start = _counts(app)
    r = _close(client, hid, "D2")
    assert r.status_code == 409 and r.get_json()["field"] == "snapshot"
    assert _counts(app) == start
