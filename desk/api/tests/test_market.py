import math

import pytest

from desk.api import db, market
from desk.api.app import create_app
from desk.api.qf import qfpy

URL = "/api/market/snapshots/MX-DEMO"


def _error(resp, status, field):
    assert resp.status_code == status
    body = resp.get_json()
    assert set(body) == {"error", "field"}
    assert body["error"]
    assert body["field"] == field


def _dfs(payload, curve):
    return [p["df"] for p in payload["curves"][curve]["points"]]


@pytest.fixture
def ctx(app, tmp_path):
    conn = db.connect(tmp_path / "t.db")
    try:
        yield market.load_context(conn, "MX-DEMO")
    finally:
        conn.close()


def test_list_contains_demo(client):
    body = client.get("/api/market/snapshots").get_json()
    (item,) = body["snapshots"]
    # la procedencia (`data_quality`, `sources`) se prueba en test_market_sources.py
    assert {k: item[k] for k in ("id", "label", "synthetic", "as_of")} == {
        "id": "MX-DEMO",
        "label": "México demo (sintético)",
        "synthetic": True,
        "as_of": "2026-11-10",
    }
    assert set(item) == {"id", "label", "synthetic", "as_of", "data_quality", "sources"}


def test_get_snapshot_shape(client):
    s = client.get(URL).get_json()
    assert s["id"] == "MX-DEMO" and s["synthetic"] is True and s["as_of"] == "2026-11-10"
    assert len(s["quotes"]) == 20
    first = s["quotes"][0]
    assert first == {
        "id": "TIIE-F:1D", "curve": "TIIE-F", "label": "1D",
        "type": "deposit", "days": 1, "rate": 0.07,
    }
    q13 = next(q for q in s["quotes"] if q["id"] == "TIIE-F:13x28")
    assert (q13["type"], q13["days"], q13["rate"]) == ("ois", 364, 0.0675)
    for name, ccy, period in (("TIIE-F", "MXN", 28), ("SOFR", "USD", 365)):
        curve = s["curves"][name]
        assert (curve["currency"], curve["period_days"]) == (ccy, period)
        quotes = [q for q in s["quotes"] if q["curve"] == name]
        assert len(curve["points"]) == len(quotes)
        for p, q in zip(curve["points"], quotes):
            assert set(p) == {"label", "days", "t", "zero", "df", "forward"}
            assert (p["label"], p["days"]) == (q["label"], q["days"])
            assert p["t"] == pytest.approx(q["days"] / 365.0)
            assert p["df"] == pytest.approx(math.exp(-p["zero"] * p["t"]))
        dfs = [p["df"] for p in curve["points"]]
        assert dfs == sorted(dfs, reverse=True)
        assert curve["points"][0]["forward"] == pytest.approx(curve["points"][0]["zero"])
    assert s["fx"] == {"pair": "USDMXN", "spot": 18.6}
    vs = s["vol_surface"]
    assert vs["expiry_days"] == [30, 91, 182, 365]
    assert vs["strikes"] == [17.0 + 0.5 * i for i in range(8)]
    assert len(vs["vols"]) == 4 and all(len(r) == 8 for r in vs["vols"])
    k = math.log(17.0 / 18.60)
    assert vs["vols"][0][0] == pytest.approx(0.115 + 0.5 * k * k + 0.03 * k)
    assert s["hw"] == {
        "TIIE-F": {"a": 0.05, "sigma": 0.01},
        "SOFR": {"a": 0.03, "sigma": 0.008},
    }
    assert s["factors"]["names"] == ["TIIE-F", "SOFR", "USDMXN"]
    assert s["factors"]["units"] == ["bp", "bp", "ret"]
    assert s["factors"]["daily_vols"] == [4.0, 5.0, 0.0075]
    assert s["factors"]["correlations"][0] == [1.0, 0.35, 0.30]


def test_put_ten_bp_on_tiie_lowers_its_discount_factors_only(client):
    before = client.get(URL).get_json()
    quotes = [
        {"id": q["id"], "rate": q["rate"] + 0.0010}
        for q in before["quotes"]
        if q["curve"] == "TIIE-F"
    ]
    resp = client.put(URL, json={"quotes": quotes})
    assert resp.status_code == 200
    after = resp.get_json()
    for b, a in zip(before["curves"]["TIIE-F"]["points"], after["curves"]["TIIE-F"]["points"]):
        assert b["t"] > 0 and a["df"] < b["df"]
    assert _dfs(after, "SOFR") == _dfs(before, "SOFR")
    assert after["fx"] == before["fx"]
    assert client.get(URL).get_json() == after


def test_put_spot(client):
    resp = client.put(URL, json={"spot": 18.75})
    assert resp.status_code == 200
    assert resp.get_json()["fx"]["spot"] == 18.75
    assert len(resp.get_json()["quotes"]) == 20
    assert client.get(URL).get_json()["fx"]["spot"] == 18.75


def test_unknown_snapshot_is_404(client):
    _error(client.get("/api/market/snapshots/NOPE"), 404, "snapshot")
    _error(client.put("/api/market/snapshots/NOPE", json={"spot": 18.0}), 404, "snapshot")


@pytest.mark.parametrize(
    "quotes",
    [
        [{"id": "TIIE-F:99x28", "rate": 0.07}],
        [{"rate": 0.07}],
        [{"id": "TIIE-F:1D", "rate": "abc"}],
        [{"id": "TIIE-F:1D", "rate": True}],
        [{"id": "TIIE-F:1D"}],
        [{"id": "TIIE-F:1D", "rate": 1.0}],
        [{"id": "TIIE-F:1D", "rate": -0.05}],
        ["TIIE-F:1D"],
        [],
        "TIIE-F:1D",
    ],
)
def test_put_bad_quotes_is_400_on_quotes(client, quotes):
    _error(client.put(URL, json={"quotes": quotes}), 400, "quotes")


@pytest.mark.parametrize("spot", [0, -1.0, "abc", True])
def test_put_bad_spot_is_400_on_spot(client, spot):
    _error(client.put(URL, json={"spot": spot}), 400, "spot")


def test_put_empty_body_is_400(client):
    _error(client.put(URL, json={}), 400, None)


def test_rejected_put_changes_nothing(client):
    before = client.get(URL).get_json()
    bad = {"quotes": [{"id": "SOFR:1Y", "rate": 0.05}, {"id": "nope", "rate": 0.05}], "spot": 19.0}
    _error(client.put(URL, json=bad), 400, "quotes")
    assert client.get(URL).get_json() == before


def test_put_persists_across_app_instances(tmp_path):
    path = tmp_path / "p.db"
    c1 = create_app(db_path=path).test_client()
    resp = c1.put(URL, json={"quotes": [{"id": "SOFR:1Y", "rate": 0.045}], "spot": 19.2})
    assert resp.status_code == 200
    s = create_app(db_path=path).test_client().get(URL).get_json()
    assert s["fx"]["spot"] == 19.2
    assert next(q for q in s["quotes"] if q["id"] == "SOFR:1Y")["rate"] == 0.045
    assert len(s["quotes"]) == 20


def test_load_context_unknown_snapshot_is_404(app, tmp_path):
    conn = db.connect(tmp_path / "t.db")
    try:
        with pytest.raises(market.ApiError) as exc:
            market.load_context(conn, "NOPE")
    finally:
        conn.close()
    assert (exc.value.status, exc.value.field) == (404, "snapshot")


def test_context_attributes(ctx):
    assert ctx.snapshot_id == "MX-DEMO" and str(ctx.as_of) == "2026-11-10"
    assert set(market.CURVES) == {"TIIE-F", "SOFR"}
    assert set(ctx.curves) == set(market.CURVES) | {"MXN-USD"}  # corte 3: MX-DEMO trae cotizaciones de colateral USD
    assert ctx.spot == 18.6
    assert ctx.pillars["TIIE-F"][4] == {"label": "13x28", "days": 364}
    assert len(ctx.pillars["TIIE-F"]) == len(ctx.curves["TIIE-F"].maturities()) == 10
    assert len(ctx.pillars["SOFR"]) == len(ctx.curves["SOFR"].maturities()) == 10
    assert ctx.env.spot("USDMXN") == 18.6
    assert ctx.env.has_vol_surface("USDMXN")


def test_bootstrapped_curve_reprices_its_quote(ctx):
    swap = qfpy.OisSwap(1e6, 0.0675, 364, 28, qfpy.SwapType.Payer, "TIIE-F")
    assert swap.npv(ctx.env) == pytest.approx(0.0, abs=1e-2)


def test_env_with_default_points_to_requested_curve(ctx):
    for name in ("TIIE-F", "SOFR"):
        env = ctx.env_with_default(name)
        assert env.curve("default").zero_rate(1.0) == pytest.approx(
            ctx.curves[name].zero_rate(1.0)
        )
        assert env.curve("TIIE-F").zero_rate(1.0) == pytest.approx(
            ctx.curves["TIIE-F"].zero_rate(1.0)
        )
        assert env.spot("USDMXN") == ctx.spot
    with pytest.raises(ValueError):
        ctx.env_with_default("NOPE")


def test_shifted_parallel_moves_only_that_curve_and_leaves_original(ctx):
    z_tiie, z_sofr = (ctx.curves[c].zero_rate(2.0) for c in ("TIIE-F", "SOFR"))
    up = ctx.shifted(curve="TIIE-F", parallel_bp=1.0)
    assert up.curves["TIIE-F"].zero_rate(2.0) == pytest.approx(z_tiie + 1e-4)
    assert up.curves["SOFR"].zero_rate(2.0) == z_sofr
    assert up.env.curve("TIIE-F").zero_rate(2.0) == pytest.approx(z_tiie + 1e-4)
    assert ctx.curves["TIIE-F"].zero_rate(2.0) == z_tiie
    assert ctx.env.curve("TIIE-F").zero_rate(2.0) == z_tiie
    assert up.pillars == ctx.pillars


def test_shifted_single_pillar_and_combined(ctx):
    n = len(ctx.pillars["SOFR"])
    shifts = [0.0] * n
    shifts[4] = 5.0
    key = ctx.shifted(curve="SOFR", pillar_shifts_bp=shifts)
    base_r = ctx.curves["SOFR"].rates()
    new_r = key.curves["SOFR"].rates()
    for i in range(n):
        assert new_r[i] == pytest.approx(base_r[i] + (5e-4 if i == 4 else 0.0))
    both = ctx.shifted(curve="SOFR", pillar_shifts_bp=shifts, parallel_bp=1.0)
    for i in range(n):
        assert both.curves["SOFR"].rates()[i] == pytest.approx(
            base_r[i] + 1e-4 + (5e-4 if i == 4 else 0.0)
        )
    with pytest.raises(ValueError):
        ctx.shifted(curve="SOFR", pillar_shifts_bp=[1.0])
    with pytest.raises(ValueError):
        ctx.shifted(parallel_bp=1.0)


def test_shifted_spot(ctx):
    moved = ctx.shifted(spot_pct=10.0)
    assert moved.spot == pytest.approx(20.46)
    assert moved.env.spot("USDMXN") == pytest.approx(20.46)
    assert ctx.spot == 18.6
    assert moved.curves["TIIE-F"].zero_rate(1.0) == ctx.curves["TIIE-F"].zero_rate(1.0)
