"""Corte 6, T4: P&L explicado por cascada (R1).

La suma de los componentes es el P&L de `/api/pnl` por fila y en total; con el mercado idéntico
rodado todo cae en `carry`; con el mercado movido cada bloque recibe su parte.
"""
from datetime import date, timedelta

import pytest

from desk.api.tests.hedge_fixture import load_fixings, roll
from desk.api.tests.test_valuation_aged import AS_OF, FWD, _book, _event, _iso

EXPLAIN = "/api/pnl/explain?from=%s&to=%s"
PNL = "/api/pnl?from=%s&to=%s"
KEYS = ["carry", "curve:TIIE-F", "curve:SOFR", "fx", "vol", "new_trades", "events", "residual"]
ZERO_KEYS = ["curve:TIIE-F", "curve:SOFR", "fx", "vol", "new_trades", "events"]


def _get(client, url, src, dst):
    r = client.get(url % (src, dst))
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _explain(client, src="MX-DEMO", dst="D1"):
    body = _get(client, EXPLAIN, src, dst)
    return body, {row["id"]: row for row in body["rows"]}


def _assert_identity(client, body, src="MX-DEMO", dst="D1"):
    """Σ componentes == P&L oficial de /api/pnl, por fila y en total, a 1e-6 MXN."""
    official = _get(client, PNL, src, dst)
    assert [r["id"] for r in body["rows"]] == [r["id"] for r in official["rows"]]
    assert body["totals"]["pnl"] == official["total_mxn"]
    for row, ref in zip(body["rows"], official["rows"]):
        assert row["pnl"] == ref["pnl"] and row["warnings"] == ref["warnings"]
        if ref["error"] is None:
            assert set(row["components"]) == set(KEYS)  # el JSON ordena las claves: el orden lo da `steps`
            assert sum(row["components"].values()) == pytest.approx(ref["pnl"], abs=1e-6)
        else:
            assert row["components"] is None and row["error"] == ref["error"]
    ok = [r for r in body["rows"] if r["error"] is None]
    for key in KEYS:
        assert body["totals"]["components"][key] == pytest.approx(sum(r["components"][key] for r in ok), abs=1e-6)
    assert sum(body["totals"]["components"].values()) == pytest.approx(official["total_mxn"], abs=1e-6)


def _gross_notional_mxn(client, snapshot):
    v = client.get("/api/portfolio/valuation?snapshot=%s" % snapshot).get_json()
    spot = client.get("/api/market/snapshots/%s" % snapshot).get_json()["fx"]["spot"]
    return sum(r["notional"] * (spot if r["currency"] == "USD" else 1.0) for r in v["rows"])


# ------------------------------------------------------------------------ forma


def test_response_shape_and_steps(client):
    roll(client, "MX-DEMO", "D1", 30)
    body, rows = _explain(client)
    assert body["from"] == {"snapshot": "MX-DEMO", "as_of": AS_OF.isoformat()}
    assert body["to"] == {"snapshot": "D1", "as_of": _iso(30)}
    assert [s["key"] for s in body["steps"]] == KEYS
    assert body["steps"][0] == {"key": "carry", "label": "Paso del tiempo y liquidaciones"}
    assert body["steps"][1] == {"key": "curve:TIIE-F", "label": "Tasas TIIE-F"}
    assert body["steps"][-1] == {"key": "residual", "label": "Residuo"}
    assert list(rows) == list(range(1, 8))
    assert set(body["totals"]) == {"pnl", "components"}
    assert set(rows[1]) == {"id", "product", "counterparty", "pnl", "components", "error", "explain_error", "warnings"}
    assert rows[1]["product"] == "irs" and rows[1]["counterparty"] == "Banco Alfa (sintético)"
    assert rows[1]["error"] is None and rows[1]["explain_error"] is None


# ----------------------------------------------------------------------- (a)


def test_rolled_identical_market_is_all_carry(client):
    due = AS_OF + timedelta(days=31)
    roll(client, "MX-DEMO", "D1", 30)
    load_fixings(client, "TIIE-F", AS_OF, due, 0.07)
    load_fixings(client, "SOFR", AS_OF, due, 0.04)
    body, rows = _explain(client)
    _assert_identity(client, body)
    for tid, row in rows.items():
        assert row["error"] is None and row["explain_error"] is None
        for key in ZERO_KEYS:
            assert row["components"][key] == 0.0, (tid, key)
        assert row["components"]["carry"] == pytest.approx(row["pnl"], abs=1e-6)
    for key in ZERO_KEYS:
        assert body["totals"]["components"][key] == 0.0
    # los swaps TIIE-F pagaron su cupón del día 28: carry no es trivial
    assert abs(rows[1]["components"]["carry"]) > 1.0 and abs(rows[2]["components"]["carry"]) > 1.0


def test_same_snapshot_is_all_zero(client):
    body, rows = _explain(client, "MX-DEMO", "MX-DEMO")
    _assert_identity(client, body, "MX-DEMO", "MX-DEMO")
    assert all(v == 0.0 for r in rows.values() for v in r["components"].values())


# ----------------------------------------------------------------------- (b)


def test_moved_market_splits_into_curves_and_fx(client):
    roll(client, "MX-DEMO", "D1", 30)
    snap = client.get("/api/market/snapshots/D1").get_json()
    quotes = [
        {"id": q["id"], "rate": q["rate"] + (0.0025 if q["curve"] == "TIIE-F" else -0.0025)} for q in snap["quotes"]
    ]
    r = client.put("/api/market/snapshots/D1", json={"quotes": quotes, "spot": snap["fx"]["spot"] * 1.03})
    assert r.status_code == 200, r.get_json()
    body, rows = _explain(client)
    _assert_identity(client, body)

    comps = body["totals"]["components"]
    gross = _gross_notional_mxn(client, "D1")
    assert abs(comps["residual"]) < max(0.02 * abs(body["totals"]["pnl"]), 1e-4 * gross)
    assert abs(comps["residual"]) < 1e-3  # telescopa: solo ruido numérico
    for tid, row in rows.items():
        assert abs(row["components"]["residual"]) < 1e-3, tid
        assert row["components"]["vol"] == 0.0 and row["components"]["new_trades"] == 0.0
        assert row["components"]["events"] == 0.0
    # swap Alfa pagador de TIIE-F: gana con tasas al alza; el receptor Beta pierde
    assert rows[1]["components"]["curve:TIIE-F"] > 0
    assert rows[2]["components"]["curve:TIIE-F"] < 0
    assert rows[1]["components"]["curve:SOFR"] == 0.0 and rows[1]["components"]["fx"] == 0.0
    # el swap Gamma (SOFR, USD) reacciona a SOFR y al tipo de cambio, no a TIIE-F
    assert rows[3]["components"]["curve:SOFR"] != 0.0 and rows[3]["components"]["curve:TIIE-F"] == 0.0
    assert rows[3]["components"]["fx"] != 0.0
    # el forward USD reacciona al tipo de cambio
    assert rows[4]["components"]["fx"] != 0.0


# ----------------------------------------------------------------------- (c)


def test_trade_agreed_inside_the_window_goes_whole_to_new_trades(client):
    roll(client, "MX-DEMO", "D1", 30)
    fwd = _book(client, "fx_forward", {**FWD, "days": 60}, trade_date=_iso(10), start_date=_iso(10))
    par = client.post(
        "/api/trades",
        json={
            "product": "irs",
            "counterparty": "Banco T",
            "params": {"curve": "TIIE-F", "side": "payer", "notional": 1e8, "periods": 13},
            "snapshot": "D1",
        },
    )
    assert par.status_code == 201, par.get_json()
    body, rows = _explain(client)
    _assert_identity(client, body)
    row = rows[fwd]
    assert row["pnl"] != 0.0
    assert row["components"]["new_trades"] == row["pnl"]
    assert all(v == 0.0 for k, v in row["components"].items() if k != "new_trades")
    new_irs = rows[par.get_json()["id"]]  # pactado en el snapshot D1: también es de la ventana
    assert new_irs["components"]["new_trades"] == new_irs["pnl"]
    assert all(v == 0.0 for k, v in new_irs["components"].items() if k != "new_trades")
    # las siete operaciones originales no tienen operaciones nuevas
    assert all(rows[t]["components"]["new_trades"] == 0.0 for t in range(1, 8))
    assert body["totals"]["components"]["new_trades"] == pytest.approx(row["pnl"] + new_irs["pnl"], abs=1e-6)


# ----------------------------------------------------------------------- (d)


def test_termination_inside_the_window_lands_in_events(client):
    roll(client, "MX-DEMO", "D1", 30)
    load_fixings(client, "TIIE-F", AS_OF, AS_OF + timedelta(days=31), 0.07)
    _event(client, 4, "termination", _iso(10), {"amount": -250000.0})
    body, rows = _explain(client)
    _assert_identity(client, body)
    row = rows[4]
    assert row["components"]["events"] != 0.0
    # sin mercado movido, todo lo demás de esa operación sigue siendo paso del tiempo (su valor sin evento)
    for key in ("curve:TIIE-F", "curve:SOFR", "fx", "vol", "new_trades"):
        assert row["components"][key] == 0.0
    # la terminación liquida -250 mil: eventos = (pv_to + settled) - (valor sin evento + liquidado sin evento)
    assert row["components"]["events"] + row["components"]["carry"] == pytest.approx(row["pnl"], abs=1e-6)
    # el resto no tiene eventos
    assert all(rows[t]["components"]["events"] == 0.0 for t in (1, 2, 3, 5, 6, 7))


# ----------------------------------------------------------------------- (e)


def test_errors(client):
    roll(client, "MX-DEMO", "D1", 30)
    r = client.get(EXPLAIN % ("D1", "MX-DEMO"))
    assert r.status_code == 400 and r.get_json()["field"] == "to"
    r = client.get("/api/pnl/explain?to=D1")
    assert r.status_code == 400 and r.get_json()["field"] == "from"
    r = client.get("/api/pnl/explain?from=MX-DEMO")
    assert r.status_code == 400 and r.get_json()["field"] == "to"
    for url in (EXPLAIN % ("NOPE", "D1"), EXPLAIN % ("MX-DEMO", "NOPE")):
        r = client.get(url)
        assert r.status_code == 404 and r.get_json()["field"] == "snapshot"


def test_unvaluable_trade_row_has_null_components_and_does_not_sum(client, app):
    from desk.api.tests.conftest import insert_raw_trade

    roll(client, "MX-DEMO", "D1", 30)
    raw = insert_raw_trade(app, "irs", "no es json")
    body, rows = _explain(client)
    _assert_identity(client, body)
    assert rows[raw]["error"] is not None and rows[raw]["pnl"] is None and rows[raw]["components"] is None
    assert rows[raw]["explain_error"] is None
    assert rows[1]["error"] is None


def test_cascade_failure_sends_the_pnl_to_residual(client, monkeypatch):
    from desk.api import valuation
    from desk.api.risk import explain

    roll(client, "MX-DEMO", "D1", 30)
    official = _get(client, PNL, "MX-DEMO", "D1")
    calls = {"n": 0}
    real = valuation.value_trade

    def flaky(trade, mkt, fixings=None):
        # compute_pnl valúa con los snapshots reales; solo los contextos híbridos ("from→to") de la cascada fallan
        if trade["id"] == 1 and "→" in mkt.snapshot_id:
            calls["n"] += 1
            raise ValueError("boom")
        return real(trade, mkt, fixings)

    monkeypatch.setattr(explain.valuation, "value_trade", flaky)
    body, rows = _explain(client)
    assert calls["n"] >= 1
    assert rows[1]["explain_error"] == "boom" and rows[1]["error"] is None
    ref = next(r for r in official["rows"] if r["id"] == 1)
    assert rows[1]["components"]["residual"] == ref["pnl"]
    assert all(v == 0.0 for k, v in rows[1]["components"].items() if k != "residual")
    assert sum(body["totals"]["components"].values()) == pytest.approx(official["total_mxn"], abs=1e-6)
