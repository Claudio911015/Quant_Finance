import json
import sqlite3

import pytest

IRS_PAYER = {"curve": "TIIE-F", "side": "payer", "notional": 100e6, "periods": 26, "fixed_rate": 0.068}
IRS_RECEIVER = {"curve": "TIIE-F", "side": "receiver", "notional": 50e6, "periods": 65, "fixed_rate": 0.0695}
FWD = {"side": "buy", "notional_usd": 1e6, "days": 91, "strike": 19.0}
EQ = {"option_type": "call", "spot": 55.0, "strike": 55.0, "volatility": 0.25, "rate": 0.07,
      "dividend_yield": 0.02, "maturity_years": 1.0, "quantity": 1000.0}


def _clear(client):
    for t in client.get("/api/trades").get_json()["trades"]:
        assert client.delete("/api/trades/%d" % t["id"]).status_code == 204


def _add(client, product, params):
    r = client.post("/api/trades", json={"product": product, "counterparty": "Banco Test", "params": params})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["id"]


def _dv01(client, snapshot="MX-DEMO"):
    r = client.post("/api/risk/dv01", json={"snapshot": snapshot})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _scenarios(client, scenarios, snapshot="MX-DEMO"):
    r = client.post("/api/risk/scenarios", json={"snapshot": snapshot, "scenarios": scenarios})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["scenarios"]


def _insert_raw(app, product, params_text):
    conn = sqlite3.connect(app.config["DESK_DB"])
    conn.execute(
        "INSERT INTO trades (product, counterparty, params, created_at) VALUES (?, 'Raw', ?, 'x')",
        (product, params_text),
    )
    conn.commit()
    conn.close()


@pytest.fixture
def irs_client(client):
    """Portafolio de solo `irs` TIIE-F."""
    _clear(client)
    _add(client, "irs", IRS_PAYER)
    _add(client, "irs", IRS_RECEIVER)
    return client


# ----------------------------------------------------------------------------- DV01

def test_dv01_shape_on_seed_portfolio(client):
    d = _dv01(client)
    assert set(d) == {"snapshot", "total_mxn", "parallel_mxn", "curves", "errors"}
    assert d["snapshot"] == "MX-DEMO" and d["errors"] == []
    assert set(d["curves"]) == {"TIIE-F", "SOFR"}
    snap = client.get("/api/market/snapshots/MX-DEMO").get_json()
    for name, c in d["curves"].items():
        assert set(c) == {"parallel_mxn", "points"}
        assert [(p["label"], p["days"]) for p in c["points"]] == [
            (q["label"], q["days"]) for q in snap["quotes"] if q["curve"] == name
        ]
        assert all(set(p) == {"label", "days", "dv01_mxn"} for p in c["points"])
    points = [p["dv01_mxn"] for c in d["curves"].values() for p in c["points"]]
    assert d["total_mxn"] == pytest.approx(sum(points))
    assert d["parallel_mxn"] == pytest.approx(sum(c["parallel_mxn"] for c in d["curves"].values()))
    assert d["curves"]["TIIE-F"]["parallel_mxn"] != 0 and d["curves"]["SOFR"]["parallel_mxn"] != 0


def test_key_rates_add_up_to_parallel(irs_client):
    d = _dv01(irs_client)
    parallel = d["curves"]["TIIE-F"]["parallel_mxn"]
    key_rates = sum(p["dv01_mxn"] for p in d["curves"]["TIIE-F"]["points"])
    assert parallel != 0
    assert abs(key_rates - parallel) < 0.02 * abs(parallel)
    assert d["parallel_mxn"] == pytest.approx(parallel)
    assert all(p["dv01_mxn"] == 0 for p in d["curves"]["SOFR"]["points"])


def test_dv01_sign_convention_payer_loses_when_rates_fall(client):
    _clear(client)
    _add(client, "irs", IRS_PAYER)
    assert _dv01(client)["curves"]["TIIE-F"]["parallel_mxn"] < 0  # paga fija: PV baja si bajan las tasas
    _clear(client)
    _add(client, "irs", IRS_RECEIVER)
    assert _dv01(client)["curves"]["TIIE-F"]["parallel_mxn"] > 0


def test_equity_option_contributes_zero(irs_client):
    before = _dv01(irs_client)
    pnl_before = _scenarios(irs_client, [{"name": "p", "type": "parallel", "curve": "TIIE-F", "bp": 25}])
    eq_id = _add(irs_client, "equity_option", EQ)
    assert _dv01(irs_client) == before
    after = _scenarios(irs_client, [{"name": "p", "type": "parallel", "curve": "TIIE-F", "bp": 25}])
    eq_row = next(r for r in after[0]["trades"] if r["id"] == eq_id)
    assert eq_row["pnl_mxn"] == pytest.approx(0, abs=1e-9) and eq_row["error"] is None
    assert after[0]["total_mxn"] == pytest.approx(pnl_before[0]["total_mxn"])


def test_empty_portfolio_gives_zeros(client):
    _clear(client)
    d = _dv01(client)
    assert d["total_mxn"] == 0 and d["parallel_mxn"] == 0 and d["errors"] == []
    assert all(p["dv01_mxn"] == 0 for c in d["curves"].values() for p in c["points"])


def test_dv01_corrupt_rows_are_reported_and_excluded(app, client):
    clean = _dv01(client)
    _insert_raw(app, "irs", json.dumps({"curve": "TIIE-F"}))  # faltan campos
    _insert_raw(app, "irs", "{no es json")
    d = _dv01(client)
    assert [e["id"] for e in d["errors"]] == [8, 9]
    assert all(e["error"] for e in d["errors"])
    assert d["total_mxn"] == pytest.approx(clean["total_mxn"])
    assert d["curves"] == clean["curves"]


# ----------------------------------------------------------------------------- escenarios

def test_parallel_one_bp_matches_dv01(irs_client):
    d = _dv01(irs_client)
    s = _scenarios(irs_client, [{"name": "TIIE-F +1 pb", "type": "parallel", "curve": "TIIE-F", "bp": 1}])
    assert s[0]["name"] == "TIIE-F +1 pb"
    assert s[0]["total_mxn"] == pytest.approx(sum(r["pnl_mxn"] for r in s[0]["trades"]))
    assert abs(-s[0]["total_mxn"] - d["total_mxn"]) < 0.02 * abs(d["total_mxn"])


def test_steepener_follows_linear_ramp_of_key_rates(irs_client):
    d = _dv01(irs_client)
    pts = d["curves"]["TIIE-F"]["points"]
    n = len(pts)
    ramp = [-1.0 + 2.0 * i / (n - 1) for i in range(n)]  # -1 pb en el primer pilar, +1 pb en el último
    expected = -sum(w * p["dv01_mxn"] for w, p in zip(ramp, pts))
    scale = sum(abs(w * p["dv01_mxn"]) for w, p in zip(ramp, pts))
    s = _scenarios(irs_client, [{"name": "st", "type": "steepener", "curve": "TIIE-F", "bp": 1}])
    assert s[0]["total_mxn"] != 0
    assert abs(s[0]["total_mxn"] - expected) < 0.02 * scale


def test_steepener_is_not_a_parallel_shock(irs_client):
    s = _scenarios(irs_client, [
        {"name": "up", "type": "parallel", "curve": "TIIE-F", "bp": 50},
        {"name": "steep", "type": "steepener", "curve": "TIIE-F", "bp": 50},
    ])
    assert s[0]["total_mxn"] != pytest.approx(s[1]["total_mxn"], rel=0.05)


def test_spot_shock_moves_only_fx_and_sofr_trades(client):
    s = _scenarios(client, [{"name": "USDMXN +10 %", "type": "fx_spot", "pct": 10}])[0]
    by_id = {r["id"]: r["pnl_mxn"] for r in s["trades"]}
    products = {t["id"]: t["product"] for t in client.get("/api/trades").get_json()["trades"]}
    assert len(by_id) == 7 and all(r["error"] is None for r in s["trades"])
    for tid, pnl in by_id.items():
        if tid in (1, 2, 7):  # irs TIIE-F y cap TIIE-F: MXN puro
            assert pnl == pytest.approx(0, abs=1e-6), products[tid]
        else:  # irs SOFR (USD), forwards y opción FX
            assert abs(pnl) > 1.0, products[tid]
    assert s["total_mxn"] == pytest.approx(sum(by_id.values()))


def test_scenarios_do_not_alter_the_base_market(client):
    before = client.get("/api/portfolio/valuation?snapshot=MX-DEMO").get_json()
    _scenarios(client, [
        {"name": "a", "type": "parallel", "curve": "SOFR", "bp": 100},
        {"name": "b", "type": "steepener", "curve": "TIIE-F", "bp": 100},
        {"name": "c", "type": "fx_spot", "pct": -20},
    ])
    assert client.get("/api/portfolio/valuation?snapshot=MX-DEMO").get_json() == before


def test_scenario_corrupt_rows_report_error_and_rest_is_valued(app, client):
    clean = _scenarios(client, [{"name": "p", "type": "parallel", "curve": "TIIE-F", "bp": 10}])[0]
    _insert_raw(app, "irs", "{no es json")
    s = _scenarios(client, [{"name": "p", "type": "parallel", "curve": "TIIE-F", "bp": 10}])[0]
    assert len(s["trades"]) == 8
    bad = s["trades"][7]
    assert bad["id"] == 8 and bad["pnl_mxn"] is None and bad["error"]
    assert s["trades"][:7] == clean["trades"]
    assert s["total_mxn"] == pytest.approx(clean["total_mxn"])


# ----------------------------------------------------------------------------- entradas inválidas

OK_SCN = {"name": "x", "type": "parallel", "curve": "TIIE-F", "bp": 10}


@pytest.mark.parametrize("path", ["dv01", "scenarios"])
def test_unknown_snapshot_is_404(client, path):
    r = client.post("/api/risk/" + path, json={"snapshot": "NOPE", "scenarios": [OK_SCN]})
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"


@pytest.mark.parametrize("path", ["dv01", "scenarios"])
def test_missing_snapshot_is_400(client, path):
    r = client.post("/api/risk/" + path, json={"scenarios": [OK_SCN]})
    assert r.status_code == 400 and r.get_json()["field"] == "snapshot"


@pytest.mark.parametrize("scenarios", [
    None,
    [],
    "parallel",
    {"name": "x"},
    ["parallel"],
    [{**OK_SCN, "name": ""}],
    [{k: v for k, v in OK_SCN.items() if k != "name"}],
    [{**OK_SCN, "type": "flattener"}],
    [{k: v for k, v in OK_SCN.items() if k != "type"}],
    [{**OK_SCN, "curve": "CETES"}],
    [{k: v for k, v in OK_SCN.items() if k != "curve"}],
    [{**OK_SCN, "bp": "10"}],
    [{**OK_SCN, "bp": True}],
    [{**OK_SCN, "bp": None}],
    [{k: v for k, v in OK_SCN.items() if k != "bp"}],
    [{**OK_SCN, "type": "steepener", "bp": float("nan")}],
    [{"name": "fx", "type": "fx_spot"}],
    [{"name": "fx", "type": "fx_spot", "pct": "10"}],
    [{"name": "fx", "type": "fx_spot", "pct": -100}],
    [{"name": "fx", "type": "fx_spot", "pct": -250}],
    [OK_SCN, {"name": "fx", "type": "fx_spot", "pct": float("inf")}],
])
def test_invalid_scenarios_are_400_on_field_scenarios(client, scenarios):
    body = {"snapshot": "MX-DEMO"}
    if scenarios is not None:
        body["scenarios"] = scenarios
    r = client.post("/api/risk/scenarios", data=json.dumps(body), content_type="application/json")
    assert r.status_code == 400, r.get_json()
    assert r.get_json()["field"] == "scenarios" and r.get_json()["error"]
