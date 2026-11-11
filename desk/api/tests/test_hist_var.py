"""Corte 6, T5: VaR histórico (`POST /api/risk/var` con `method: historical`)."""
import json
import math
import random
import sqlite3
from datetime import date, timedelta

import pytest

from desk.api import db
from desk.api.risk import factor_history, hist_var, var
from desk.api.seed_market import demo_data

FACTORS = demo_data()["factors"]
BODY = {"snapshot": "MX-DEMO", "horizon_days": 1, "confidence": 0.99, "method": "historical"}


def _hist(client, **over):
    body = dict(BODY)
    body.update(over)
    return client.post("/api/risk/var", json=body)


def _ok(client, **over):
    r = _hist(client, **over)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _correlated_days(n, seed=7):
    """`n` días hábiles previos a MX-DEMO con normales correlacionadas (vols y correlaciones de MX-DEMO)."""
    corr, vols = FACTORS["correlations"], FACTORS["daily_vols"]
    low = [[0.0] * 3 for _ in range(3)]
    for i in range(3):
        for j in range(i + 1):
            s = sum(low[i][k] * low[j][k] for k in range(j))
            low[i][j] = math.sqrt(corr[i][i] - s) if i == j else (corr[i][j] - s) / low[j][j]
    rng = random.Random(seed)
    days, day = [], date(2026, 11, 9)
    while len(days) < n:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    days.reverse()
    rows = []
    for d in days:
        z = [rng.gauss(0, 1) for _ in range(3)]
        for i, name in enumerate(FACTORS["names"]):
            rows.append((name, d.isoformat(), vols[i] * sum(low[i][k] * z[k] for k in range(i + 1))))
    return rows


def _load_csv(client, rows):
    text = "factor,date,value\n" + "\n".join("%s,%s,%r" % r for r in rows)
    r = client.post("/api/factor-history/csv", json={"csv": text})
    assert r.status_code == 200, r.get_json()


def _series(client, source, as_of, n):
    conn = db.connect(client.application.config["DESK_DB"])
    try:
        return factor_history.window(conn, source, as_of, n)
    finally:
        conn.close()


# ------------------------------------------------------------------------------ contrato

def test_default_is_synthetic_250_days_with_contract_shape(client):
    body = _ok(client)
    assert set(body) == {"snapshot", "method", "var_mxn", "es_mxn", "horizon_days", "confidence", "window_days",
                         "worst_day", "history", "factors", "errors"}
    assert body["method"] == "historical" and body["snapshot"] == "MX-DEMO"
    assert body["window_days"] == 250 and body["horizon_days"] == 1.0 and body["confidence"] == 0.99
    assert body["errors"] == []
    h = body["history"]
    assert h["source"] == "synthetic" and h["label"] == factor_history.SOURCE_LABEL["synthetic"]
    assert h["observations"] == 250 and h["by_source"] == {"synthetic": 750}
    dates, _, _ = _series(client, "synthetic", "2026-11-10", 250)
    assert h["from"] == dates[0] and h["to"] == dates[-1] == "2026-11-09"
    assert [(f["factor"], f["unit"]) for f in body["factors"]] == [("TIIE-F", "bp"), ("SOFR", "bp"), ("USDMXN", "ret")]
    assert all(set(f) == {"factor", "unit", "exposure_mxn"} for f in body["factors"])
    assert set(body["worst_day"]) == {"date", "pnl_mxn"}
    assert body["var_mxn"] > 0


def test_exposures_are_the_parametric_ones(client):
    parametric = client.post("/api/risk/var", json={k: v for k, v in BODY.items() if k != "method"}).get_json()
    hist = _ok(client)
    for p, h in zip(parametric["factors"], hist["factors"]):
        assert (p["factor"], p["unit"], p["exposure_mxn"]) == (h["factor"], h["unit"], h["exposure_mxn"])


def test_es_is_at_least_var(client):
    for conf in (0.9, 0.95, 0.99, 0.5):
        body = _ok(client, confidence=conf)
        assert body["es_mxn"] >= body["var_mxn"]
    assert _ok(client, confidence=0.9)["es_mxn"] > _ok(client, confidence=0.9)["var_mxn"]


def test_percentile_and_es_follow_the_definition(client):
    body = _ok(client, window_days=100, confidence=0.95)
    dates, series, _ = _series(client, "synthetic", "2026-11-10", 100)
    expo = {f["factor"]: f["exposure_mxn"] for f in body["factors"]}
    pnl = [sum(expo[f] * series[f][t] for f in expo) for t in range(100)]
    losses = sorted((-p for p in pnl), reverse=True)
    assert body["var_mxn"] == pytest.approx(losses[4], rel=1e-12)  # k = ceil(100 * 0.05) = 5
    assert body["es_mxn"] == pytest.approx(sum(losses[:5]) / 5, rel=1e-12)


def test_worst_day_is_the_date_of_the_largest_loss(client):
    body = _ok(client, window_days=250)
    dates, series, _ = _series(client, "synthetic", "2026-11-10", 250)
    expo = {f["factor"]: f["exposure_mxn"] for f in body["factors"]}
    pnl = [sum(expo[f] * series[f][t] for f in expo) for t in range(250)]
    t = min(range(250), key=lambda i: pnl[i])
    assert body["worst_day"]["date"] == dates[t]
    assert body["worst_day"]["pnl_mxn"] == pytest.approx(pnl[t], rel=1e-12)
    assert body["worst_day"]["pnl_mxn"] < 0  # P&L de 1 día, sin escalar


def test_horizon_scales_with_square_root(client):
    one, four = _ok(client, horizon_days=1), _ok(client, horizon_days=4)
    assert four["var_mxn"] == pytest.approx(2 * one["var_mxn"], rel=1e-9)
    assert four["es_mxn"] == pytest.approx(2 * one["es_mxn"], rel=1e-9)
    assert four["horizon_days"] == 4.0
    assert four["worst_day"] == one["worst_day"]  # el peor día no se escala


def test_window_size_is_used(client):
    body = _ok(client, window_days=60)
    assert body["window_days"] == 60 and body["history"]["observations"] == 60
    assert body["history"]["by_source"] == {"synthetic": 180}
    dates, _, _ = _series(client, "synthetic", "2026-11-10", 60)
    assert (body["history"]["from"], body["history"]["to"]) == (dates[0], dates[-1])


def test_empty_portfolio_has_zero_var(client):
    from desk.api.tests.conftest import empty_portfolio
    empty_portfolio(client)
    body = _ok(client)
    assert body["var_mxn"] == 0.0 and body["es_mxn"] == 0.0
    assert all(f["exposure_mxn"] == 0.0 for f in body["factors"])


# ------------------------------------------------------------------------------ R3 y paramétrico

def test_r3_historical_matches_parametric_on_normal_history(client):
    _load_csv(client, _correlated_days(5000))
    parametric = client.post("/api/risk/var", json={"snapshot": "MX-DEMO", "horizon_days": 1, "confidence": 0.99})
    param = parametric.get_json()["var_mxn"]
    body = _ok(client, history_source="observed", window_days=5000)
    assert body["history"]["source"] == "observed"
    assert body["history"]["label"] == hist_var.OBSERVED_LABEL
    assert body["history"]["observations"] == 5000 and body["history"]["by_source"] == {"csv": 15000}
    assert abs(body["var_mxn"] / param - 1) < 0.10
    assert body["es_mxn"] >= body["var_mxn"]


def test_without_method_the_json_is_the_parametric_one(client):
    direct = None
    conn = db.connect(client.application.config["DESK_DB"])
    try:
        direct = var.compute_var(conn, "MX-DEMO", {"horizon_days": 10, "confidence": 0.99})
    finally:
        conn.close()
    plain = {"snapshot": "MX-DEMO", "horizon_days": 10, "confidence": 0.99}
    for extra in ({}, {"method": "parametric"}):
        body = client.post("/api/risk/var", json=dict(plain, **extra)).get_json()
        assert "method" not in body
        assert body["var_mxn"] == pytest.approx(direct["var_mxn"], rel=1e-12)
        assert json.dumps(body, sort_keys=True) == json.dumps(direct, sort_keys=True)


# ------------------------------------------------------------------------------ errores

def test_not_enough_history_is_409_window_days(client):
    r = _hist(client, window_days=6000)
    assert r.status_code == 409
    body = r.get_json()
    assert body["field"] == "window_days"
    assert body["error"] == "Historia insuficiente: hay 500 días con los tres factores hasta el 2026-11-10 (se piden 6000)"


def test_observed_without_data_is_409(client):
    r = _hist(client, history_source="observed")
    assert r.status_code == 409
    assert r.get_json()["field"] == "window_days" and "hay 0 días" in r.get_json()["error"]


def test_observed_ignores_the_synthetic_series(client):
    _load_csv(client, _correlated_days(100))
    assert _hist(client, history_source="observed", window_days=101).status_code == 409
    assert _hist(client, history_source="observed", window_days=100).status_code == 200


@pytest.mark.parametrize("over,field", [
    ({"window_days": 59}, "window_days"),
    ({"window_days": 10001}, "window_days"),
    ({"window_days": 250.5}, "window_days"),
    ({"window_days": "250"}, "window_days"),
    ({"window_days": True}, "window_days"),
    ({"history_source": "otra"}, "history_source"),
    ({"history_source": 3}, "history_source"),
    ({"horizon_days": 0}, "horizon_days"),
    ({"horizon_days": "x"}, "horizon_days"),
    ({"confidence": 1}, "confidence"),
    ({"confidence": 0}, "confidence"),
])
def test_validation_is_400_with_field(client, over, field):
    r = _hist(client, **over)
    assert r.status_code == 400 and r.get_json()["field"] == field


def test_validation_order_precedes_missing_snapshot(client):
    # horizon, confidence, window_days, history_source y luego 404 del snapshot
    assert _hist(client, snapshot="NOPE", horizon_days=0).get_json()["field"] == "horizon_days"
    assert _hist(client, snapshot="NOPE", confidence=2).get_json()["field"] == "confidence"
    assert _hist(client, snapshot="NOPE", window_days=1).get_json()["field"] == "window_days"
    assert _hist(client, snapshot="NOPE", history_source="x").get_json()["field"] == "history_source"
    r = _hist(client, snapshot="NOPE")
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"


def test_missing_required_fields_are_400(client):
    assert client.post("/api/risk/var", json={"snapshot": "MX-DEMO", "method": "historical"}).status_code == 400
    assert client.post("/api/risk/var", json={"snapshot": "MX-DEMO", "method": "historical",
                                              "horizon_days": 1}).get_json()["field"] == "confidence"


# ------------------------------------------------------------------------------ fuente por omisión

def _insert_live_snapshot(client, snapshot_id="LIVE-T"):
    """Copia de MX-DEMO con todas las fuentes marcadas `live` (calidad "live")."""
    conn = sqlite3.connect(client.application.config["DESK_DB"])
    try:
        row = conn.execute("SELECT as_of, data FROM snapshots WHERE id = 'MX-DEMO'").fetchone()
        data = json.loads(row[1])
        data["sources"] = {k: {"kind": "live", "label": "x", "as_of": row[0]} for k in
                           ("TIIE-F", "SOFR", "USDMXN", "vol_surface", "hw", "factors", "fx")}
        conn.execute("INSERT INTO snapshots (id, label, synthetic, as_of, data) VALUES (?, 'vivo', 0, ?, ?)",
                     (snapshot_id, row[0], json.dumps(data)))
        conn.commit()
    finally:
        conn.close()


def test_non_synthetic_snapshot_defaults_to_observed(client):
    _insert_live_snapshot(client)
    r = _hist(client, snapshot="LIVE-T")
    assert r.status_code == 409 and r.get_json()["field"] == "window_days"  # sin historia observada
    _load_csv(client, _correlated_days(250))
    body = _ok(client, snapshot="LIVE-T")
    assert body["history"]["source"] == "observed" and body["history"]["by_source"] == {"csv": 750}
    forced = _ok(client, snapshot="LIVE-T", history_source="synthetic")
    assert forced["history"]["source"] == "synthetic"


def test_null_values_use_defaults(client):
    body = _ok(client, window_days=None, history_source=None)
    assert body["window_days"] == 250 and body["history"]["source"] == "synthetic"
