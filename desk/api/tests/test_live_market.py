"""Construcción de `MKT-LIVE` (R2, R3, R4, R6). Solo fixtures: ni red ni la base real de MarketDataFeed."""
import json
import math
from datetime import date, timedelta

import pytest

from desk.api import db, fred, live_market, market, marketdata, seed_market
from desk.api.errors import ApiError
from desk.api.pricing import PRODUCTS
from desk.api.qf import qfpy
from desk.api.tests.conftest import empty_portfolio
from desk.api.tests.mdf_fixture import REAL_2026_11_10, make_fred_csv, make_mdf_db

LIVE = "/api/market/snapshots/MKT-LIVE"
SOFR_LABEL = (
    "Aproximada: 1D = SOFR overnight (FRBNY); resto = Treasuries par (Treasury.gov) en "
    "convención OIS, sin spread de swap"
)


# ---------------------------------------------------------------------------- series a mano

def _indep_std(xs):
    """Desviación estándar muestral (ddof = 1) escrita aparte de la implementación."""
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _yields(n):
    """`n` rendimientos decimales; los primeros 40 se mueven mucho más que el resto."""
    return [
        0.04 + 0.004 * math.sin(i / 7.0) + (0.003 if i < 40 else 0.0004) * math.sin(i * 1.3)
        for i in range(n)
    ]


def _spots(n):
    return [18.0 + 0.8 * math.sin(i / 9.0) + (0.5 if i < 40 else 0.05) * math.sin(i * 1.7)
            for i in range(n)]


def _end_at(last_day, n):
    return [last_day - timedelta(days=n - 1 - i) for i in range(n)]


def _history_pct(n):
    """`(fecha, %)` de 5Y que terminan el 2026-11-10 en 4.81, como la curva del fixture."""
    ys = [round(y * 100.0, 6) for y in _yields(n)]
    ys[-1] = REAL_2026_11_10["5Y"]
    return [(d.isoformat(), y) for d, y in zip(_end_at(date(2026, 11, 10), n), ys)]


def _fx_rows(n_valid, gap_every=11):
    """Filas de FRED: `n_valid` válidas que terminan el 2026-11-06 = 18.6226, con un faltante
    tras cada `gap_every` válidas y dos faltantes al final (09 y 10 de noviembre)."""
    values = _spots(n_valid)
    values[-1] = 18.6226
    cells = []
    for i, v in enumerate(values):
        cells.append(v)
        if i % gap_every == gap_every - 1 and i < n_valid - 1:
            cells.append(None)
    days = _end_at(date(2026, 11, 6), len(cells))
    rows = [(d.isoformat(), v) for d, v in zip(days, cells)]
    return rows + [("2026-11-09", None), ("2026-11-10", None)], values


def _fx_series(tmp_path, n_valid=300):
    rows, values = _fx_rows(n_valid)
    csv_path = make_fred_csv(tmp_path / "fred.csv", rows)
    series = fred.parse_dexmxus(csv_path.read_text(encoding="utf-8"))
    assert [v for _, v in series] == values  # el fixture no pierde ni inventa observaciones
    return series


def _mdf(tmp_path, n=300, name="mdf.db", **kw):
    return make_mdf_db(tmp_path / name, history_5y=_history_pct(n), **kw)


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "desk.db")
    db.init_schema(c)
    yield c
    c.close()


def _live_row(c):
    return c.execute("SELECT id, label, synthetic, as_of, data FROM snapshots WHERE id = 'MKT-LIVE'").fetchone()


def _live_data(c):
    return json.loads(_live_row(c)["data"])


def _quote(data, qid):
    return next(q for q in data["quotes"] if q["id"] == qid)


# ------------------------------------------------------------------------ conversión (R2)

def test_conversion_reference_values():
    assert live_market.treasury_to_ois(0.0405, 30) == pytest.approx(0.039945, abs=1e-6)
    assert live_market.treasury_to_ois(0.0498, 3650) == pytest.approx(0.049729, abs=1e-6)


def test_conversion_switches_to_semiannual_compounding_after_one_year():
    y = 0.0456
    assert live_market.treasury_to_ois(y, 365) == pytest.approx(y * 360 / 365, abs=1e-12)
    assert live_market.treasury_to_ois(y, 366) == pytest.approx(
        ((1 + y / 2) ** 2 - 1) * 360 / 365, abs=1e-12
    )


def test_pillar_table_matches_the_template_quotes():
    template = [q for q in seed_market.demo_data()["quotes"] if q["curve"] == "SOFR"]
    assert [("SOFR:" + label, days) for label, days, _ in live_market.SOFR_PILLARS] == [
        (q["id"], q["days"]) for q in template
    ]


# ------------------------------------------------------------------- ventanas y vols (R3)

@pytest.mark.parametrize("n,changes", [(300, 250), (251, 250), (100, 99), (61, 60)])
def test_daily_vol_bp_uses_the_last_changes(n, changes):
    ys = _yields(n)
    vol, used = live_market.daily_vol_bp(ys)
    obs = ys[-(changes + 1):]
    expected = _indep_std([(b - a) * 10000.0 for a, b in zip(obs, obs[1:])])
    assert used == changes
    assert vol == pytest.approx(expected, rel=0, abs=1e-9)


def test_daily_vol_bp_window_matters():
    ys = _yields(300)
    vol, _ = live_market.daily_vol_bp(ys)
    all_changes = _indep_std([(b - a) * 10000.0 for a, b in zip(ys, ys[1:])])
    assert abs(vol - all_changes) > 1e-3


@pytest.mark.parametrize("n", [0, 1, 59, 60])
def test_daily_vol_bp_too_short_is_409(n):
    with pytest.raises(ApiError) as e:
        live_market.daily_vol_bp(_yields(n))
    assert e.value.status == 409 and e.value.error.startswith("Historia insuficiente")


@pytest.mark.parametrize("n,changes", [(300, 250), (100, 99), (61, 60)])
def test_daily_vol_logret_uses_the_last_changes(n, changes):
    s = _spots(n)
    vol, used = live_market.daily_vol_logret(s)
    obs = s[-(changes + 1):]
    expected = _indep_std([math.log(b / a) for a, b in zip(obs, obs[1:])])
    assert used == changes
    assert vol == pytest.approx(expected, rel=0, abs=1e-9)


def test_daily_vol_logret_skips_missing_and_joins_valid_neighbours():
    valid = _spots(300)
    junk = [None, float("nan"), 0.0, -3.0]
    mixed = []
    for i, v in enumerate(valid):
        mixed.append(v)
        if i % 7 == 3:
            mixed.append(junk[(i // 7) % 4])
    vol, used = live_market.daily_vol_logret(mixed)
    obs = valid[-251:]
    expected = _indep_std([math.log(b / a) for a, b in zip(obs, obs[1:])])
    assert used == 250
    assert vol == pytest.approx(expected, rel=0, abs=1e-9)


def test_missing_observations_do_not_count_towards_the_minimum():
    padded = lambda n_valid: _spots(n_valid) + [None] * 20  # noqa: E731
    assert live_market.daily_vol_logret(padded(61))[1] == 60
    with pytest.raises(ApiError) as e:
        live_market.daily_vol_logret(padded(60))
    assert e.value.status == 409 and e.value.error.startswith("Historia insuficiente")


# ------------------------------------------------------------------- construcción (R2, R3)

def test_rebuild_converts_the_real_curve(tmp_path, conn):
    out = live_market.rebuild_live(conn, _mdf(tmp_path), _fx_series(tmp_path))
    data = _live_data(conn)
    assert _quote(data, "SOFR:1M")["rate"] == pytest.approx(0.039945, abs=1e-6)
    assert _quote(data, "SOFR:10Y")["rate"] == pytest.approx(0.049729, abs=1e-6)
    assert _quote(data, "SOFR:1D")["rate"] == pytest.approx(0.0388, abs=1e-12)
    for label, days, tenor in live_market.SOFR_PILLARS[1:]:
        y = REAL_2026_11_10[tenor] / 100.0
        expected = y * 360 / 365 if days <= 365 else ((1 + y / 2) ** 2 - 1) * 360 / 365
        assert _quote(data, "SOFR:" + label)["rate"] == pytest.approx(expected, abs=1e-6)
    assert out == {
        "treasury_latest": "2026-11-10",
        "sofr_latest": "2026-11-09",
        "fred_latest": "2026-11-06",
        "as_of": "2026-11-10",
        "created": True,
    }


def test_rebuild_keeps_quote_format_of_the_template(tmp_path, conn):
    live_market.rebuild_live(conn, _mdf(tmp_path), _fx_series(tmp_path))
    live = [q for q in _live_data(conn)["quotes"] if q["curve"] == "SOFR"]
    template = [q for q in seed_market.demo_data()["quotes"] if q["curve"] == "SOFR"]
    assert [q["type"] for q in live] == ["deposit"] + ["ois"] * 9
    for q, t in zip(live, template):
        assert {k: q[k] for k in ("id", "curve", "label", "type", "days")} == {
            k: t[k] for k in ("id", "curve", "label", "type", "days")
        }
        assert q["rate"] == round(q["rate"], 6)


def test_rebuild_row_metadata(tmp_path, conn):
    live_market.rebuild_live(conn, _mdf(tmp_path), _fx_series(tmp_path))
    row = _live_row(conn)
    assert row["label"] == "Mercado vivo (SOFR aproximada)"
    assert row["synthetic"] == 1
    assert row["as_of"] == "2026-11-10"


def test_save_does_not_commit(tmp_path, conn):
    live_market.rebuild_live(conn, _mdf(tmp_path), _fx_series(tmp_path))
    conn.rollback()
    assert _live_row(conn) is None


def test_spot_is_the_last_valid_observation(tmp_path, conn):
    text = (
        "observation_date,DEXMXUS\n"
        + "".join("%s,%r\n" % (d.isoformat(), v)
                  for d, v in zip(_end_at(date(2026, 11, 3), 80), _spots(80)))
        + "2026-11-04,18.5\n2026-11-05,18.6226\n2026-11-06,.\n2026-11-09,\n2026-11-10,.\n"
    )
    series = fred.parse_dexmxus(text)
    live_market.rebuild_live(conn, _mdf(tmp_path), series)
    data = _live_data(conn)
    assert data["fx"] == {"pair": "USDMXN", "spot": 18.6226}
    assert data["sources"]["spot"]["as_of"] == "2026-11-05"


def test_spot_with_missing_tail_from_fred_fixture(tmp_path, conn):
    live_market.rebuild_live(conn, _mdf(tmp_path), _fx_series(tmp_path))
    data = _live_data(conn)
    assert data["fx"]["spot"] == 18.6226
    assert data["sources"]["spot"]["as_of"] == "2026-11-06"


def test_factor_vols_are_measured_from_history(tmp_path, conn):
    live_market.rebuild_live(conn, _mdf(tmp_path), _fx_series(tmp_path))
    vols = _live_data(conn)["factors"]["daily_vols"]
    ys = [p / 100.0 for _, p in _history_pct(300)][-251:]
    expected_sofr = _indep_std([(b - a) * 10000.0 for a, b in zip(ys, ys[1:])])
    spots = _fx_rows(300)[1][-251:]
    expected_fx = _indep_std([math.log(b / a) for a, b in zip(spots, spots[1:])])
    assert vols[1] == pytest.approx(expected_sofr, rel=0, abs=1e-9)
    assert vols[2] == pytest.approx(expected_fx, rel=0, abs=1e-9)
    assert vols[0] == seed_market.demo_data()["factors"]["daily_vols"][0]


def test_factor_vols_label_carries_both_n(tmp_path, conn):
    live_market.rebuild_live(conn, _mdf(tmp_path), _fx_series(tmp_path))
    assert _live_data(conn)["sources"]["factor_vols"]["label"] == (
        "SOFR (250 cambios diarios) y USDMXN (250 cambios diarios) medidas; TIIE-F sintética"
    )
    live_market.rebuild_live(
        conn, _mdf(tmp_path, n=100, name="short.db"), _fx_series(tmp_path, n_valid=61)
    )
    assert _live_data(conn)["sources"]["factor_vols"]["label"] == (
        "SOFR (99 cambios diarios) y USDMXN (60 cambios diarios) medidas; TIIE-F sintética"
    )


def test_short_history_is_409_and_writes_nothing(tmp_path, conn):
    with pytest.raises(ApiError) as e:
        live_market.rebuild_live(conn, _mdf(tmp_path, n=60), _fx_series(tmp_path))
    assert e.value.status == 409 and "5Y" in e.value.error
    with pytest.raises(ApiError) as e:
        live_market.rebuild_live(
            conn, _mdf(tmp_path, name="ok.db"), _fx_series(tmp_path, n_valid=60)
        )
    assert e.value.status == 409 and "USDMXN" in e.value.error
    assert _live_row(conn) is None


# ------------------------------------------------- herencia de la plantilla, no de MX-DEMO

def test_inherits_the_constant_template_even_if_mx_demo_was_edited(app, client, tmp_path):
    edit = client.put(
        "/api/market/snapshots/MX-DEMO",
        json={"quotes": [{"id": "TIIE-F:1D", "rate": 0.0999}, {"id": "SOFR:1M", "rate": 0.0123}],
              "spot": 25.0},
    )
    assert edit.status_code == 200
    c = db.connect(app.config["DESK_DB"])
    try:
        live_market.rebuild_live(c, _mdf(tmp_path), _fx_series(tmp_path))
        c.commit()
        data = _live_data(c)
    finally:
        c.close()
    demo = seed_market.demo_data()
    assert set(data) == {"quotes", "fx", "vol_surface", "hw", "factors", "sources"}
    assert [q for q in data["quotes"] if q["curve"] == "TIIE-F"] == [
        q for q in demo["quotes"] if q["curve"] == "TIIE-F"
    ]
    assert data["vol_surface"] == demo["vol_surface"]
    assert data["hw"] == demo["hw"]
    assert data["factors"]["names"] == demo["factors"]["names"]
    assert data["factors"]["units"] == demo["factors"]["units"]
    assert data["factors"]["correlations"] == demo["factors"]["correlations"]
    assert data["factors"]["daily_vols"][0] == demo["factors"]["daily_vols"][0]
    assert data["fx"]["pair"] == "USDMXN" and data["fx"]["spot"] == 18.6226
    # y MX-DEMO conserva su edición
    assert client.get("/api/market/snapshots/MX-DEMO").get_json()["fx"]["spot"] == 25.0


# ------------------------------------------------------------------------ procedencia (R4)

def test_sources_of_live(tmp_path, conn):
    live_market.rebuild_live(conn, _mdf(tmp_path), _fx_series(tmp_path))
    s = _live_data(conn)["sources"]
    assert list(s) and set(s) == set(market.SOURCE_KEYS)
    assert {k: v["kind"] for k, v in s.items()} == {
        "curve:TIIE-F": "synthetic",
        "curve:SOFR": "proxy",
        "spot": "live",
        "surface": "synthetic",
        "hw": "synthetic",
        "factor_vols": "mixed",
        "factor_corr": "synthetic",
    }
    assert s["curve:TIIE-F"]["label"] == "Sintética: sin datos libres (Banxico exige token)"
    assert s["curve:SOFR"]["label"] == SOFR_LABEL
    assert s["spot"]["label"] == "FRED DEXMXUS (mediodía de Nueva York; no es el FIX de Banxico)"
    assert s["surface"]["label"] == "Sintética: sin datos libres de volatilidad USDMXN"
    assert s["hw"]["label"] == "Sintéticos (heredados de MX-DEMO)"
    assert s["factor_corr"]["label"] == "Sintéticas (heredadas de MX-DEMO)"
    assert {k: v["as_of"] for k, v in s.items()} == {
        "curve:TIIE-F": None,
        "curve:SOFR": "2026-11-10",
        "spot": "2026-11-06",
        "surface": None,
        "hw": None,
        "factor_vols": "2026-11-10",
        "factor_corr": None,
    }


def test_live_snapshot_over_http(app, client, tmp_path):
    c = db.connect(app.config["DESK_DB"])
    try:
        live_market.rebuild_live(c, _mdf(tmp_path), _fx_series(tmp_path))
        c.commit()
    finally:
        c.close()
    detail = client.get(LIVE).get_json()
    assert detail["data_quality"] == "mixed"
    assert detail["read_only"] is True
    assert detail["synthetic"] is True
    assert detail["as_of"] == "2026-11-10"
    assert detail["label"] == "Mercado vivo (SOFR aproximada)"
    assert detail["sources"]["curve:SOFR"]["kind"] == "proxy"
    summary = next(
        s for s in client.get("/api/market/snapshots").get_json()["snapshots"] if s["id"] == "MKT-LIVE"
    )
    assert summary["data_quality"] == "mixed" and "read_only" not in summary


# --------------------------------------------------------- reescritura y fallos atómicos

def _mdf_newer(tmp_path):
    """Base con una curva un día más reciente (2026-11-11)."""
    hist = [
        (d.isoformat(), p)
        for d, (_, p) in zip(_end_at(date(2026, 11, 11), 300), _history_pct(300))
    ]
    return make_mdf_db(tmp_path / "newer.db", curve_date="2026-11-11", history_5y=hist)


def test_rebuild_replaces_the_row_and_reports_created(tmp_path, conn):
    first = live_market.rebuild_live(conn, _mdf(tmp_path), _fx_series(tmp_path))
    again = live_market.rebuild_live(conn, _mdf_newer(tmp_path), _fx_series(tmp_path))
    assert first["created"] is True and again["created"] is False
    assert conn.execute("SELECT COUNT(*) FROM snapshots WHERE id = 'MKT-LIVE'").fetchone()[0] == 1
    assert _live_row(conn)["as_of"] == "2026-11-11"


def test_failure_midway_leaves_the_previous_row_intact(tmp_path, conn):
    live_market.rebuild_live(conn, _mdf(tmp_path), _fx_series(tmp_path))
    before = tuple(_live_row(conn))
    broken = _mdf(tmp_path, name="broken.db", drop_tenor="7Y")
    with pytest.raises(ApiError) as e:
        live_market.rebuild_live(conn, broken, _fx_series(tmp_path))
    assert e.value.status == 409 and "7Y" in e.value.error
    assert tuple(_live_row(conn)) == before


def test_non_finite_data_is_not_written(tmp_path, conn):
    mdf = _mdf(tmp_path)
    live_market.rebuild_live(conn, mdf, _fx_series(tmp_path))
    before = tuple(_live_row(conn))
    as_of, data = live_market.build_live_data(
        marketdata.latest_treasury_curve(mdf),
        marketdata.latest_sofr(mdf),
        marketdata.treasury_5y_history(mdf),
        _fx_series(tmp_path),
    )
    data["fx"]["spot"] = float("nan")
    with pytest.raises(ValueError):
        live_market.save_live(conn, as_of, data)
    assert tuple(_live_row(conn)) == before


def test_bootstrap_failure_is_not_written(tmp_path, conn, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("bootstrap roto")

    monkeypatch.setattr(live_market, "_build_context", boom)
    with pytest.raises(RuntimeError):
        live_market.rebuild_live(conn, _mdf(tmp_path), _fx_series(tmp_path))
    assert _live_row(conn) is None


# ------------------------------------------------------- valuación y riesgo sobre MKT-LIVE (R6)

PRICER_CASES = {
    "irs": {"curve": "SOFR", "side": "payer", "notional": 1e8, "periods": 13},
    "cap_floor": {"curve": "TIIE-F", "cap_type": "cap", "notional": 1e8, "strike": 0.075, "periods": 39},
    "swaption": {"curve": "TIIE-F", "swaption_type": "payer", "notional": 1e8, "strike": 0.07,
                 "expiry_years": 1, "swap_tenor_years": 5},
    "bond": {"curve": "TIIE-F", "face": 100, "coupon_rate": 0.08, "periods": 20, "frequency": 2},
    "equity_option": {"option_type": "call", "spot": 55, "strike": 55, "volatility": 0.25,
                      "rate": 0.07, "dividend_yield": 0.02, "maturity_years": 1, "quantity": 1000},
    "fx_forward": {"side": "buy", "notional_usd": 1e6, "strike": 18.9, "days": 91},
    "fx_option": {"side": "buy", "option_type": "call", "notional_usd": 1e6, "strike": 19, "days": 91},
}


def _all_finite(obj):
    if isinstance(obj, float):
        return math.isfinite(obj)
    if isinstance(obj, dict):
        return all(_all_finite(v) for v in obj.values())
    if isinstance(obj, list):
        return all(_all_finite(v) for v in obj)
    return True


@pytest.fixture
def live_client(app, client, tmp_path):
    c = db.connect(app.config["DESK_DB"])
    try:
        live_market.rebuild_live(c, _mdf(tmp_path), _fx_series(tmp_path))
        c.commit()
    finally:
        c.close()
    return client


def _post(client, path, **body):
    body.setdefault("snapshot", "MKT-LIVE")
    r = client.post(path, json=body)
    assert r.status_code == 200, r.get_json()
    out = r.get_json()
    assert _all_finite(out)
    return out


def test_pricer_cases_cover_every_product():
    assert set(PRICER_CASES) == set(PRODUCTS)


@pytest.mark.parametrize("product", sorted(PRICER_CASES))
def test_default_pricer_cases_respond_200_on_live(live_client, product):
    out = _post(live_client, "/api/price/" + product, **PRICER_CASES[product])
    assert math.isfinite(out["pv"])


@pytest.mark.parametrize("side", ["payer", "receiver"])
@pytest.mark.parametrize("periods", [1, 5, 10, 13])
def test_sofr_par_irs_has_zero_pv_on_live(live_client, side, periods):
    notional = 1e8
    out = _post(live_client, "/api/price/irs", curve="SOFR", side=side, notional=notional, periods=periods)
    assert abs(out["pv"]) < 1e-6 * notional


def test_portfolio_valuation_on_live_has_no_errors(live_client):
    v = live_client.get("/api/portfolio/valuation?snapshot=MKT-LIVE").get_json()
    assert len(v["rows"]) == 7
    assert all(r["error"] is None and r["pv_mxn"] is not None for r in v["rows"])
    assert math.isfinite(v["total_mxn"]) and _all_finite(v)
    demo = live_client.get("/api/portfolio/valuation?snapshot=MX-DEMO").get_json()
    assert v["total_mxn"] != demo["total_mxn"]  # la curva real sí cambia el valor


def test_risk_endpoints_on_live(live_client):
    dv01 = _post(live_client, "/api/risk/dv01")
    assert dv01["errors"] == [] and dv01["snapshot"] == "MKT-LIVE"
    scn = _post(
        live_client,
        "/api/risk/scenarios",
        scenarios=[
            {"name": "SOFR +25", "type": "parallel", "curve": "SOFR", "bp": 25},
            {"name": "TIIE-F steepener", "type": "steepener", "curve": "TIIE-F", "bp": 50},
            {"name": "USDMXN +5%", "type": "fx_spot", "pct": 5},
        ],
    )
    assert len(scn["scenarios"]) == 3
    var = _post(live_client, "/api/risk/var", horizon_days=1, confidence=0.99)
    assert var["errors"] == [] and var["var_mxn"] > 0
    live = live_client.get(LIVE).get_json()
    measured = {f["factor"]: f["daily_vol"] for f in var["factors"]}
    names = live["factors"]["names"]
    for name, vol in zip(names, live["factors"]["daily_vols"]):
        assert measured[name] == vol


def _assert_key_rates_add_up(dv01):
    checked = 0
    for name, curve in dv01["curves"].items():
        parallel = curve["parallel_mxn"]
        if parallel == 0:
            continue
        key_rates = sum(p["dv01_mxn"] for p in curve["points"])
        assert abs(key_rates - parallel) < 0.02 * abs(parallel), (name, key_rates, parallel)
        checked += 1
    return checked


def test_key_rates_add_up_to_parallel_on_live(live_client):
    assert _assert_key_rates_add_up(_post(live_client, "/api/risk/dv01")) >= 1


def test_sofr_key_rates_add_up_to_parallel_on_live(live_client):
    empty_portfolio(live_client)
    for side, periods, fixed in (("payer", 5, 0.045), ("receiver", 10, 0.049)):
        r = live_client.post(
            "/api/trades",
            json={"product": "irs", "counterparty": "Banco Test",
                  "params": {"curve": "SOFR", "side": side, "notional": 50e6,
                             "periods": periods, "fixed_rate": fixed}},
        )
        assert r.status_code == 201, r.get_json()
    dv01 = _post(live_client, "/api/risk/dv01")
    assert dv01["curves"]["SOFR"]["parallel_mxn"] != 0
    assert _assert_key_rates_add_up(dv01) >= 1


def test_bootstrap_reprices_every_sofr_quote(app, live_client):
    c = db.connect(app.config["DESK_DB"])
    try:
        ctx = market.load_context(c, "MKT-LIVE")
        quotes = [q for q in _live_data(c)["quotes"] if q["curve"] == "SOFR" and q["type"] == "ois"]
    finally:
        c.close()
    assert len(quotes) == 9
    notional = 1e6
    for q in quotes:
        swap = qfpy.OisSwap(notional, q["rate"], q["days"], 365, qfpy.SwapType.Payer, "SOFR")
        assert abs(swap.npv(ctx.env)) < 1e-6 * notional, q["id"]
