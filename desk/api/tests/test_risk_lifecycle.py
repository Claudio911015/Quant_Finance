"""El riesgo (DV01, escenarios, VaR) solo mira operaciones `viva` en el `as_of` del snapshot."""
from datetime import date, timedelta

import pytest

from desk.api.tests.conftest import empty_portfolio

AS_OF = date(2026, 11, 10)  # as_of de MX-DEMO
SCENARIOS = [
    {"name": "TIIE +25", "type": "parallel", "curve": "TIIE-F", "bp": 25},
    {"name": "SOFR steepener", "type": "steepener", "curve": "SOFR", "bp": 10},
    {"name": "USDMXN +5 %", "type": "fx_spot", "pct": 5},
]
IRS_1 = {"curve": "TIIE-F", "fixed_rate": 0.068, "notional": 500000000.0, "periods": 26, "side": "payer"}


# ------------------------------------------------------------------------ ayudas

def _iso(days):
    return (AS_OF + timedelta(days=days)).isoformat()


def _roll(client, snap_id, days):
    r = client.post("/api/market/MX-DEMO/roll", json={"id": snap_id, "as_of": _iso(days)})
    assert r.status_code == 201, r.get_json()
    return snap_id


def _terminate(client, trade_id, days):
    r = client.post(
        "/api/trades/%d/events" % trade_id,
        json={"type": "termination", "event_date": _iso(days), "data": {"amount": 1000.0}},
    )
    assert r.status_code == 201, r.get_json()


def _dv01(client, snap="MX-DEMO"):
    r = client.post("/api/risk/dv01", json={"snapshot": snap})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _scenarios(client, snap="MX-DEMO"):
    r = client.post("/api/risk/scenarios", json={"snapshot": snap, "scenarios": SCENARIOS})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _var(client, snap="MX-DEMO"):
    r = client.post(
        "/api/risk/var", json={"snapshot": snap, "horizon_days": 10, "confidence": 0.99}
    )
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _all(client, snap="MX-DEMO"):
    return {"dv01": _dv01(client, snap), "scenarios": _scenarios(client, snap), "var": _var(client, snap)}


def _approx(x):
    """Copia de `x` con cada número envuelto en `pytest.approx` (1e-9 relativo, 1e-9 absoluto)."""
    if isinstance(x, dict):
        return {k: _approx(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_approx(v) for v in x]
    if isinstance(x, float):
        return pytest.approx(x, rel=1e-9, abs=1e-9)
    return x


def _scenario_ids(result):
    return [[t["id"] for t in s["trades"]] for s in result["scenarios"]]


def _csv(client, index, values):
    lines = ["index,date,value"] + [
        "%s,%s,%r" % (index, _iso(i), v) for i, v in enumerate(values)
    ]
    r = client.post("/api/fixings/csv", json={"csv": "\n".join(lines)})
    assert r.status_code == 200, r.get_json()


# ------------------------------------------------------------------------ R5

def test_r5_terminated_trade_leaves_dv01_by_exactly_its_prior_contribution(client):
    before = _dv01(client)
    _terminate(client, 1, 0)
    after = _dv01(client)
    assert after["errors"] == []

    # contribución previa de la operación 1, medida sola en un portafolio vacío
    empty_portfolio(client)
    r = client.post(
        "/api/trades", json={"product": "irs", "counterparty": "Banco T", "params": IRS_1}
    )
    assert r.status_code == 201, r.get_json()
    alone = _dv01(client)

    assert alone["parallel_mxn"] != 0.0
    assert before["total_mxn"] - after["total_mxn"] == pytest.approx(alone["total_mxn"], rel=1e-9)
    assert before["parallel_mxn"] - after["parallel_mxn"] == pytest.approx(
        alone["parallel_mxn"], rel=1e-9
    )
    for curve, c in before["curves"].items():
        assert c["parallel_mxn"] - after["curves"][curve]["parallel_mxn"] == pytest.approx(
            alone["curves"][curve]["parallel_mxn"], rel=1e-9, abs=1e-9
        )
        for p0, p1, pa in zip(c["points"], after["curves"][curve]["points"], alone["curves"][curve]["points"]):
            assert p0["dv01_mxn"] - p1["dv01_mxn"] == pytest.approx(pa["dv01_mxn"], rel=1e-9, abs=1e-9)


def test_r5_terminated_trade_leaves_scenarios_and_var(client):
    before = _all(client)
    row1 = {s["name"]: next(t for t in s["trades"] if t["id"] == 1) for s in before["scenarios"]["scenarios"]}
    _terminate(client, 1, 0)
    after = _all(client)

    assert all(1 not in ids for ids in _scenario_ids(after["scenarios"]))
    assert all(ids == [2, 3, 4, 5, 6, 7] for ids in _scenario_ids(after["scenarios"]))
    assert after["dv01"]["errors"] == [] and after["var"]["errors"] == []
    for b, a in zip(before["scenarios"]["scenarios"], after["scenarios"]["scenarios"]):
        assert a["total_mxn"] == pytest.approx(b["total_mxn"] - row1[b["name"]]["pnl_mxn"], rel=1e-9, abs=1e-6)
    assert after["var"]["var_mxn"] != before["var"]["var_mxn"]
    assert after["var"]["factors"][0]["exposure_mxn"] != before["var"]["factors"][0]["exposure_mxn"]


def test_snapshot_before_the_termination_is_unchanged(client):
    before = _all(client)
    _terminate(client, 1, 14)  # termina 14 días después del as_of de MX-DEMO
    assert _all(client) == _approx(before)
    # y en un snapshot rodado a esa fecha la operación ya no cuenta
    _roll(client, "T14", 14)
    assert all(1 not in ids for ids in _scenario_ids(_scenarios(client, "T14")))


# ------------------------------------------------------------------------ R8

def test_r8_expired_trades_are_out_of_risk(client):
    _roll(client, "V91", 91)  # los fx_forward/fx_option de 91 días (ids 5 y 6) vencen ese día
    scenarios = _scenarios(client, "V91")
    assert all(ids == [1, 2, 3, 4, 7] for ids in _scenario_ids(scenarios))
    assert _dv01(client, "V91")["errors"] == []
    assert _var(client, "V91")["errors"] == []


# ------------------------------------------------------------------------ no_pactada

def test_trades_not_yet_agreed_are_out_of_risk(client):
    _roll(client, "PAST", -5)  # antes del `trade_date` de toda la semilla
    d = _dv01(client, "PAST")
    assert d["errors"] == [] and d["total_mxn"] == 0.0 and d["parallel_mxn"] == 0.0
    for c in d["curves"].values():
        assert c["parallel_mxn"] == 0.0 and all(p["dv01_mxn"] == 0.0 for p in c["points"])

    s = _scenarios(client, "PAST")
    assert all(x["trades"] == [] and x["total_mxn"] == 0.0 for x in s["scenarios"])

    v = _var(client, "PAST")
    assert v["errors"] == [] and v["var_mxn"] == 0.0
    assert all(f["exposure_mxn"] == 0.0 for f in v["factors"])


# ------------------------------------------------------------------------ fijaciones

def test_risk_values_swaps_with_the_published_fixings(client):
    _roll(client, "AGED", 10)
    without = _dv01(client, "AGED")
    _csv(client, "TIIE-F", [0.10] * 10)  # muy por encima de la tasa a un día de la curva
    with_fixings = _dv01(client, "AGED")
    assert with_fixings["errors"] == []
    assert with_fixings["curves"]["TIIE-F"]["parallel_mxn"] != pytest.approx(
        without["curves"]["TIIE-F"]["parallel_mxn"], rel=1e-9
    )
