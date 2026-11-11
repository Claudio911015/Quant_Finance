"""P&L entre dos snapshots (T9): identidad, liquidaciones y avisos (R4, R8)."""
import json

import pytest

from desk.api import market
from desk.api.db import connect
from desk.api.qf import qfpy
from desk.api.tests.conftest import insert_raw_trade
from desk.api.tests.test_valuation_aged import AS_OF, FWD, IRS, _book, _csv, _event, _iso, _price, _roll, _rows

PNL = "/api/pnl?from=%s&to=%s"


def _pnl(client, src, dst):
    r = client.get(PNL % (src, dst))
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    return body, {row["id"]: row for row in body["rows"]}


def _assert_adds_up(body):
    rows = [r for r in body["rows"] if r["error"] is None]
    for r in rows:
        assert r["pnl"] == pytest.approx(r["pv_to"] - r["pv_from"] + r["settled"], abs=1e-6)
    for name in ("pv_from", "pv_to", "settled", "pnl"):
        assert body["totals"][name] == pytest.approx(sum(r[name] for r in rows), abs=1e-6)
    assert body["total_mxn"] == body["totals"]["pnl"]
    assert body["total_mxn"] == pytest.approx(sum(r["pnl"] for r in rows), abs=1e-6)


# ----------------------------------------------------------------------- R4

def test_r4_identity_holds_for_every_seed_trade_over_35_days(client):
    _roll(client, "D1", 35)
    body, rows = _pnl(client, "MX-DEMO", "D1")
    assert body["from"] == {"snapshot": "MX-DEMO", "as_of": AS_OF.isoformat()}
    assert body["to"] == {"snapshot": "D1", "as_of": _iso(35)}
    assert sorted(rows) == list(range(1, 8))
    assert all(r["error"] is None for r in rows.values())
    _assert_adds_up(body)
    valuation_from = _rows(client, "MX-DEMO")
    valuation_to = _rows(client, "D1")
    for tid, r in rows.items():
        assert r["pv_from"] == pytest.approx(valuation_from[tid]["pv_mxn"], rel=1e-12)
        assert r["pv_to"] == pytest.approx(valuation_to[tid]["pv_mxn"], rel=1e-12)
        assert (r["status_from"], r["status_to"]) == ("viva", "viva")
    # los dos swaps TIIE-F pagaron su cupón del día 28; el resto no liquidó nada
    assert rows[1]["settled"] != 0 and rows[2]["settled"] != 0
    assert all(rows[t]["settled"] == 0 for t in (3, 4, 5, 6, 7))
    assert body["totals"]["pv_from"] == pytest.approx(sum(v["pv_mxn"] for v in valuation_from.values()))


def test_r4_same_snapshot_gives_zero_pnl(client):
    body, rows = _pnl(client, "MX-DEMO", "MX-DEMO")
    assert body["total_mxn"] == 0 and all(r["pnl"] == 0 and r["settled"] == 0 for r in rows.values())
    _assert_adds_up(body)


def test_r4_par_swap_with_forward_fixings_and_shifted_curve_has_zero_pnl(client, app):
    """Un swap a la par, 28 días después con la curva desplazada y fijaciones = forwards: P&L ≈ 0."""
    tau, notional = 28, 500e6
    params = {"curve": "TIIE-F", "side": "payer", "notional": notional, "periods": 26}
    par = _price(client, "irs", "MX-DEMO", params)["risk"]["par_rate"]
    tid = _book(client, "irs", {**params, "fixed_rate": par})

    conn = connect(app.config["DESK_DB"])
    try:
        c0 = market.load_context(conn, "MX-DEMO").curves["TIIE-F"]
        row = conn.execute("SELECT synthetic, data FROM snapshots WHERE id = 'MX-DEMO'").fetchone()
        data = json.loads(row["data"])
        pay0 = [d for d in qfpy.ois_payment_days(26 * 28, 28) if d > tau]
        mats, zeros = [], []
        for d in pay0:  # curva desplazada tau días, como en test_valuation_aged
            t1 = (d - tau) / 365.0
            mats.append(t1)
            zeros.append((c0.zero_rate(d / 365.0) * d / 365.0 - c0.zero_rate(tau / 365.0) * tau / 365.0) / t1)
        env = qfpy.MarketEnvironment()
        env.add_curve("TIIE-F", qfpy.YieldCurve(mats, zeros, qfpy.InterpolationMethod.Linear))
        quotes = []
        for i, d in enumerate(pay0):  # una cotización en cada pago restante
            days = d - tau
            q = qfpy.OisSwap(1e6, 0.0, days, 28, qfpy.SwapType.Payer, "TIIE-F").par_rate(env)
            quotes.append({"id": "TIIE-F:%dD" % days, "curve": "TIIE-F", "label": "%dD" % days,
                           "type": "deposit" if i == 0 else "ois", "days": days, "rate": q})
        data["quotes"] = quotes + [q for q in data["quotes"] if q["curve"] == "SOFR"]
        conn.execute(
            "INSERT INTO snapshots (id, label, synthetic, as_of, data) VALUES ('D1', 'desplazado', ?, ?, ?)",
            (row["synthetic"], _iso(tau), json.dumps(data)),
        )
        conn.commit()
        df0 = lambda d: 1.0 if d == 0 else c0.discount_factor(d / 365.0)  # noqa: E731
        fixings = [(df0(d) / df0(d + 1) - 1.0) * 360.0 for d in range(tau)]
    finally:
        conn.close()
    _csv(client, "TIIE-F", fixings)

    body, rows = _pnl(client, "MX-DEMO", "D1")
    r = rows[tid]
    assert r["error"] is None and r["warnings"] == []
    assert abs(r["settled"]) > 1e-4 * notional  # pagó su cupón del día 28: no es trivial
    assert abs(r["pv_from"]) < 1e-6 * notional
    assert abs(r["pnl"]) < 1e-6 * notional
    _assert_adds_up(body)


def test_last_coupon_at_maturity_counts_as_settled(client):
    tid = _book(client, "irs", {**IRS, "periods": 1, "notional": 1e8})  # su único cupón cae en el vencimiento
    _roll(client, "D35", 35)
    rates = [0.0710] * 28
    _csv(client, "TIIE-F", rates)
    body, rows = _pnl(client, "MX-DEMO", "D35")
    r = rows[tid]
    factor = (1.0 + 0.0710 / 360.0) ** 28
    assert r["settled"] == pytest.approx(1e8 * (factor - 1.0) - 1e8 * 0.07 * 28 / 360.0, rel=1e-12)
    assert (r["status_from"], r["status_to"]) == ("viva", "vencida") and r["pv_to"] == 0
    _assert_adds_up(body)


# ----------------------------------------------------------------------- R8

def test_r8_forward_settles_with_the_fix_of_its_maturity(client):
    tid = _book(client, "fx_forward", {**FWD, "days": 20})
    _roll(client, "D35", 35)
    r = client.post("/api/fixings", json={"index": "USDMXN", "date": _iso(20), "value": 19.5})
    assert r.status_code == 201
    body, rows = _pnl(client, "MX-DEMO", "D35")
    row = rows[tid]
    assert row["settled"] == pytest.approx(1e6 * (19.5 - 19.0), rel=1e-12)
    assert (row["status_from"], row["status_to"]) == ("viva", "vencida")
    assert row["pv_to"] == 0 and row["warnings"] == []
    assert row["pnl"] == pytest.approx(row["settled"] - row["pv_from"], rel=1e-12)
    _assert_adds_up(body)


def test_r8_forward_without_fix_settles_at_the_spot_of_the_final_snapshot(client):
    tid = _book(client, "fx_forward", {**FWD, "side": "sell", "days": 20})
    _roll(client, "D35", 35)
    body, rows = _pnl(client, "MX-DEMO", "D35")
    row = rows[tid]
    assert row["settled"] == pytest.approx(-1e6 * (18.60 - 19.0), rel=1e-12)  # vende: signo contrario
    assert [(w["code"], w["index"], w["dates"]) for w in row["warnings"]] == [
        ("fx_fallback", "USDMXN", [_iso(20)])
    ]
    _assert_adds_up(body)


def test_sofr_coupon_converts_with_the_fix_of_its_payment_date(client):
    _roll(client, "D370", 370)
    spot = 18.60
    without = _pnl(client, "MX-DEMO", "D370")[1][3]
    assert [(w["code"], w["index"]) for w in without["warnings"]] == [
        ("missing_fixing", "SOFR"), ("fx_fallback", "USDMXN")
    ]
    assert without["warnings"][1]["dates"] == [_iso(365)]
    r = client.post("/api/fixings", json={"index": "USDMXN", "date": _iso(365), "value": 17.0})
    assert r.status_code == 201
    with_fix = _pnl(client, "MX-DEMO", "D370")[1][3]
    assert [w["code"] for w in with_fix["warnings"]] == ["missing_fixing"]
    assert with_fix["settled"] == pytest.approx(without["settled"] * 17.0 / spot, rel=1e-12)


# --------------------------------------------------------------- eventos y fechas

def test_termination_between_the_snapshots_adds_its_amount_to_settled(client):
    _event(client, 1, "termination", _iso(10), {"amount": 1234.5})
    _roll(client, "D15", 15)
    body, rows = _pnl(client, "MX-DEMO", "D15")
    row = rows[1]
    assert row["settled"] == pytest.approx(1234.5) and row["pv_to"] == 0
    assert (row["status_from"], row["status_to"]) == ("viva", "terminada")
    assert row["pnl"] == pytest.approx(1234.5 - row["pv_from"], rel=1e-12)
    _assert_adds_up(body)


def test_exercise_transfer_adds_to_settled(client):
    _event(client, 6, "exercise", _iso(10), {"amount": -80.0})
    _roll(client, "D15", 15)
    row = _pnl(client, "MX-DEMO", "D15")[1][6]
    assert row["settled"] == pytest.approx(-80.0) and row["status_to"] == "ejercida"


def test_trade_agreed_inside_the_window_enters_with_zero_pv_from(client):
    tid = _book(client, "fx_forward", FWD, trade_date=_iso(5), start_date=_iso(5))
    _roll(client, "D10", 10)
    body, rows = _pnl(client, "MX-DEMO", "D10")
    row = rows[tid]
    assert row["pv_from"] == 0 and row["status_from"] == "no_pactada" and row["status_to"] == "viva"
    assert row["settled"] == 0 and row["pnl"] == pytest.approx(row["pv_to"])
    _assert_adds_up(body)


def test_trade_agreed_after_the_final_snapshot_is_all_zero(client):
    tid = _book(client, "fx_forward", FWD, trade_date=_iso(20), start_date=_iso(20))
    _roll(client, "D10", 10)
    row = _pnl(client, "MX-DEMO", "D10")[1][tid]
    assert (row["status_from"], row["status_to"]) == ("no_pactada", "no_pactada")
    assert row["pv_from"] == row["pv_to"] == row["settled"] == row["pnl"] == 0


# --------------------------------------------------------------------- avisos

def test_cap_and_bond_maturing_in_the_window_warn_that_they_have_no_settlement(client):
    cap = _book(client, "cap_floor", {"curve": "TIIE-F", "cap_type": "cap", "notional": 1e8,
                                       "strike": 0.07, "periods": 1})
    bond = _book(client, "bond", {"curve": "TIIE-F", "face": 100.0, "coupon_rate": 0.08,
                                   "periods": 1, "frequency": 12.0})
    _roll(client, "D40", 40)
    body, rows = _pnl(client, "MX-DEMO", "D40")
    for tid, day in ((cap, 28), (bond, 30)):
        row = rows[tid]
        assert row["settled"] == 0 and row["status_to"] == "vencida" and row["pv_to"] == 0
        assert [(w["code"], w["dates"]) for w in row["warnings"]] == [("no_settlement", [_iso(day)])]
    _assert_adds_up(body)


def test_terminated_cap_does_not_report_a_missing_settlement(client):
    cap = _book(client, "cap_floor", {"curve": "TIIE-F", "cap_type": "cap", "notional": 1e8,
                                       "strike": 0.07, "periods": 1})
    _event(client, cap, "termination", _iso(10), {"amount": 10.0})
    _roll(client, "D40", 40)
    row = _pnl(client, "MX-DEMO", "D40")[1][cap]
    assert row["warnings"] == [] and row["settled"] == 10.0


def test_warnings_from_both_valuations_and_flows_are_merged_without_repeated_dates(client):
    _roll(client, "D35", 35)
    row = _pnl(client, "MX-DEMO", "D35")[1][1]
    assert [(w["code"], w["index"]) for w in row["warnings"]] == [("missing_fixing", "TIIE-F")]
    # 28 días del primer cupón + 7 del periodo en curso, cada fecha una sola vez
    assert row["warnings"][0]["dates"] == [_iso(i) for i in range(35)]
    assert "35" in row["warnings"][0]["message"]


# --------------------------------------------------------------------- errores

def test_row_with_an_error_has_null_figures_and_is_left_out_of_the_totals(app, client):
    params = {"curve": "TIIE-F", "side": "payer", "notional": 1e6, "periods": 13}
    bad = insert_raw_trade(app, "irs", json.dumps(params))  # sin fixed_rate
    _roll(client, "D35", 35)
    body, rows = _pnl(client, "MX-DEMO", "D35")
    row = rows[bad]
    assert "fixed_rate" in row["error"]
    assert all(row[k] is None for k in ("pv_from", "pv_to", "settled", "pnl", "status_from", "status_to"))
    assert row["warnings"] == []
    _assert_adds_up(body)
    assert len([r for r in body["rows"] if r["error"] is None]) == 7


def test_from_later_than_to_is_rejected_on_the_to_field(client):
    _roll(client, "D5", 5)
    r = client.get(PNL % ("D5", "MX-DEMO"))
    assert r.status_code == 400 and r.get_json()["field"] == "to"


@pytest.mark.parametrize("src, dst", [("NOPE", "MX-DEMO"), ("MX-DEMO", "NOPE")])
def test_unknown_snapshot_is_404_on_the_snapshot_field(client, src, dst):
    r = client.get(PNL % (src, dst))
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"
