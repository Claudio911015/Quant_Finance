"""Curva MXN-USD en el contexto de mercado, el snapshot y el DV01 (corte 3, T6).

R1 (la curva reprecia sus cotizaciones), R2 (con paridad y base 0 coincide con TIIE-F), R7 (estructura)
y R10 (procedencia en el payload). La valuación con colateral es de T7; aquí solo el mercado.
"""
import json
import math
import sqlite3

import pytest

from desk.api import db, market, seed_market
from desk.api.qf import qfpy
from desk.api.tests.csa_fixture import strip_csa

URL = "/api/market/snapshots/MX-DEMO"
CSA = "MXN-USD"
NO_CURVE_MESSAGE = (
    "El snapshot no trae puntos forward ni base de cross currency swaps: "
    "la curva MXN-USD no existe y todo se descuenta con TIIE-F"
)


# ----------------------------------------------------------------------------- ayudas

def _sql(app, sql, args=()):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        rows = conn.execute(sql, args).fetchall()
        conn.commit()
        return rows
    finally:
        conn.close()


def _data(app, snapshot_id="MX-DEMO"):
    return json.loads(_sql(app, "SELECT data FROM snapshots WHERE id = ?", (snapshot_id,))[0][0])


def _set_data(app, data, snapshot_id="MX-DEMO"):
    _sql(app, "UPDATE snapshots SET data = ? WHERE id = ?", (json.dumps(data), snapshot_id))


def _context(app, snapshot_id="MX-DEMO"):
    conn = db.connect(app.config["DESK_DB"])
    try:
        return market.load_context(conn, snapshot_id)
    finally:
        conn.close()


def _roll(client, new_id, source="MX-DEMO", as_of="2026-12-15"):
    r = client.post("/api/market/%s/roll" % source, json={"id": new_id, "as_of": as_of})
    assert r.status_code == 201 or r.status_code == 200, r.get_json()
    return r.get_json()


def _dfs(ctx, name, days):
    return [ctx.curves[name].discount_factor(d / 365.0) for d in days]


def _zeros(ctx, name):
    return [ctx.curves[name].zero_rate(p["days"] / 365.0) for p in ctx.pillars[name]]


def _parity_snapshot(app):
    """MX-DEMO con puntos forward de paridad TIIE-F/SOFR y base 0 en los días de TIIE-F (R2)."""
    base = _context(app)
    data = _data(app)
    forwards = []
    for q in data["fx_forwards"]:
        parity = qfpy.FxForward(1.0, 1.0, q["days"], qfpy.FxSide.Buy, "USDMXN", "TIIE-F").forward_rate(base.env)
        forwards.append({"days": q["days"], "points": parity - base.spot, "label": q["label"]})
    data["fx_forwards"] = forwards
    data["xccy_basis"] = [{"days": q["days"], "spread": 0.0, "label": q["label"]} for q in data["xccy_basis"]]
    _set_data(app, data)
    return _context(app)


# ----------------------------------------------------------------------------- payload

def test_demo_payload_has_dependent_curve_with_nine_points(client):
    s = client.get(URL).get_json()
    curve = s["curves"][CSA]
    assert (curve["currency"], curve["period_days"], curve["dependent"]) == ("MXN", 28, True)
    assert [(p["label"], p["days"]) for p in curve["points"]] == [
        ("1M", 28), ("3M", 84), ("6M", 168), ("1Y", 364),
        ("2Y", 728), ("3Y", 1092), ("5Y", 1820), ("7Y", 2548), ("10Y", 3640),
    ]
    for p in curve["points"]:
        assert set(p) == {"label", "days", "t", "zero", "df", "forward"}
        assert p["df"] == pytest.approx(math.exp(-p["zero"] * p["t"]))
    # TIIE-F y SOFR conservan su forma y no se mezclan con la dependiente
    assert "dependent" not in s["curves"]["TIIE-F"] and "dependent" not in s["curves"]["SOFR"]
    assert set(s["curves"]) == {"TIIE-F", "SOFR", CSA}


def test_demo_payload_lists_normalized_quotes(client):
    s = client.get(URL).get_json()
    assert s["fx_forwards"] == [
        {"days": 28, "points": 0.0438, "label": "1M"},
        {"days": 84, "points": 0.1317, "label": "3M"},
        {"days": 168, "points": 0.2637, "label": "6M"},
        {"days": 364, "points": 0.5745, "label": "1Y"},
    ]
    assert s["xccy_basis"] == [
        {"days": 728, "spread": -0.0010, "label": "2Y"},
        {"days": 1092, "spread": -0.0012, "label": "3Y"},
        {"days": 1820, "spread": -0.0015, "label": "5Y"},
        {"days": 2548, "spread": -0.0017, "label": "7Y"},
        {"days": 3640, "spread": -0.0020, "label": "10Y"},
    ]


def test_demo_csa_block_is_synthetic_and_available(client):
    csa = client.get(URL).get_json()["csa"]
    assert set(csa) == {"available", "curve", "source", "message", "implied_vs_quoted"}
    assert csa["available"] is True and csa["curve"] == CSA and csa["message"] is None
    assert csa["source"] == {
        "kind": "synthetic", "label": "Sintético (inventado para demostración)", "as_of": None,
    }
    rows = csa["implied_vs_quoted"]
    assert [r["label"] for r in rows] == ["1M", "3M", "6M", "1Y"]
    assert set(rows[0]) == {
        "label", "days", "quoted_points", "quoted_forward", "implied_forward", "parity_forward", "diff",
    }
    assert rows[0]["quoted_forward"] == pytest.approx(18.6 + 0.0438)
    # base negativa: el forward cotizado queda por debajo del de paridad TIIE-F/SOFR
    assert all(r["quoted_forward"] < r["parity_forward"] for r in rows)


def test_provenance_keys_do_not_include_the_dependent_curve(client):
    s = client.get(URL).get_json()
    assert set(s["sources"]) == set(market.SOURCE_KEYS)
    assert not any(CSA in key for key in s["sources"])
    assert s["data_quality"] == "synthetic"
    listing = client.get("/api/market/snapshots").get_json()["snapshots"][0]
    assert set(listing["sources"]) == set(market.SOURCE_KEYS)


def test_csa_source_in_data_replaces_the_default(app, client):
    data = _data(app)
    data["csa_source"] = {"kind": "proxy", "label": "Banxico (prueba)", "as_of": "2026-11-09"}
    _set_data(app, data)
    assert client.get(URL).get_json()["csa"]["source"] == data["csa_source"]


# ----------------------------------------------------------------------------- R1

def test_r1_implied_forwards_match_quoted(client):
    rows = client.get(URL).get_json()["csa"]["implied_vs_quoted"]
    assert len(rows) == 4
    for r in rows:
        assert abs(r["diff"]) <= 1e-8
        assert r["implied_forward"] == pytest.approx(r["quoted_forward"], abs=1e-8)


def test_r1_each_basis_swap_reprices_to_zero(app, client):
    mkt = _context(app)
    basis = client.get(URL).get_json()["xccy_basis"]
    assert len(basis) == 5
    n_mxn = 1.0 * mkt.spot
    for q in basis:
        swap = qfpy.XccySwap(
            1.0, mkt.spot, q["spread"], 0, qfpy.ois_payment_days(q["days"], 28), 1.0, 1.0,
            qfpy.XccySide.PayUsd, True, True,
        )
        assert abs(swap.npv(mkt.env)) <= 1e-8 * n_mxn, q


def test_env_carries_the_curve_for_forward_pricing(app):
    mkt = _context(app)
    implied = qfpy.FxForward(1.0, 1.0, 28, qfpy.FxSide.Buy, "USDMXN", CSA).forward_rate(mkt.env)
    assert implied == pytest.approx(mkt.spot + 0.0438, abs=1e-8)


# ----------------------------------------------------------------------------- sin curva

def test_snapshot_without_lists_has_no_curve(app, client):
    strip_csa(app, "MX-DEMO")
    s = client.get(URL).get_json()
    assert CSA not in s["curves"] and set(s["curves"]) == {"TIIE-F", "SOFR"}
    assert s["fx_forwards"] is None and s["xccy_basis"] is None
    assert s["csa"] == {
        "available": False, "curve": CSA, "source": None, "message": NO_CURVE_MESSAGE, "implied_vs_quoted": [],
    }
    mkt = _context(app)
    assert not mkt.csa_available and mkt.curve_names() == ["TIIE-F", "SOFR"] and CSA not in mkt.pillars


def test_simulated_live_snapshot_has_no_curve(app, client):
    data = seed_market.demo_data()  # MKT-LIVE parte de demo_data(): sin cotizaciones de colateral
    assert "fx_forwards" not in data and "xccy_basis" not in data
    _sql(
        app,
        "INSERT INTO snapshots (id, label, synthetic, as_of, data) VALUES (?, ?, 0, ?, ?)",
        (market.LIVE_ID, "Mercado vivo", "2026-11-10", json.dumps(data)),
    )
    s = client.get("/api/market/snapshots/%s" % market.LIVE_ID).get_json()
    assert s["csa"]["available"] is False and s["csa"]["message"] == NO_CURVE_MESSAGE
    assert CSA not in s["curves"] and s["fx_forwards"] is None and s["xccy_basis"] is None


def test_a_single_quote_is_not_enough_for_a_curve(app, client):
    data = _data(app)
    data["fx_forwards"] = data["fx_forwards"][:1]
    data.pop("xccy_basis")
    _set_data(app, data)
    s = client.get(URL).get_json()
    assert CSA not in s["curves"] and s["csa"]["available"] is False
    assert s["fx_forwards"] == [{"days": 28, "points": 0.0438, "label": "1M"}] and s["xccy_basis"] is None


def test_default_labels_when_a_quote_has_none(app, client):
    data = _data(app)
    for q in data["fx_forwards"] + data["xccy_basis"]:
        del q["label"]
    _set_data(app, data)
    s = client.get(URL).get_json()
    assert [q["label"] for q in s["fx_forwards"]] == ["28d", "84d", "168d", "364d"]
    assert [p["label"] for p in s["curves"][CSA]["points"]][:2] == ["28d", "84d"]


def test_with_collateral_usd_without_curve_falls_back_to_tiie(app):
    strip_csa(app, "MX-DEMO")
    mkt = _context(app)
    usd = mkt.with_collateral("USD")
    assert (usd.collateral, usd.mxn_discount, usd.csa_missing) == ("USD", "TIIE-F", True)
    mxn = mkt.with_collateral("MXN")
    assert (mxn.collateral, mxn.mxn_discount, mxn.csa_missing) == ("MXN", "TIIE-F", False)


# ----------------------------------------------------------------------------- contexto

def test_context_defaults_and_with_collateral(app):
    mkt = _context(app)
    assert mkt.csa_available and mkt.curve_names() == ["TIIE-F", "SOFR", CSA]
    assert (mkt.collateral, mkt.mxn_discount, mkt.csa_missing) == ("MXN", "TIIE-F", False)
    assert len(mkt.pillars[CSA]) == len(mkt.curves[CSA].maturities()) == 9
    usd = mkt.with_collateral("USD")
    assert (usd.collateral, usd.mxn_discount, usd.csa_missing) == ("USD", CSA, False)
    assert usd.curves[CSA] is mkt.curves[CSA]  # misma curva: no recalibra
    assert (mkt.collateral, mkt.mxn_discount) == ("MXN", "TIIE-F")  # el original no cambia
    back = usd.with_collateral("MXN")
    assert (back.collateral, back.mxn_discount, back.csa_missing) == ("MXN", "TIIE-F", False)
    with pytest.raises(ValueError):
        mkt.with_collateral("EUR")


def test_shifted_keeps_collateral_attributes(app):
    usd = _context(app).with_collateral("USD")
    for moved in (
        usd.shifted(curve="TIIE-F", parallel_bp=1.0),
        usd.shifted(curve=CSA, parallel_bp=1.0),
        usd.shifted(spot_pct=1.0),
    ):
        assert (moved.collateral, moved.mxn_discount, moved.csa_missing) == ("USD", CSA, False)
    strip_csa(app, "MX-DEMO")
    missing = _context(app).with_collateral("USD").shifted(curve="SOFR", parallel_bp=1.0)
    assert (missing.collateral, missing.mxn_discount, missing.csa_missing) == ("USD", "TIIE-F", True)


# ----------------------------------------------------------------------------- R2

def test_r2_parity_forwards_and_zero_basis_equal_tiie(app):
    mkt = _parity_snapshot(app)
    pillar_days = [p["days"] for p in mkt.pillars[CSA]]
    intermediate = list(range(28, 3641, 7))
    for days in pillar_days + intermediate:
        assert _dfs(mkt, CSA, [days])[0] == pytest.approx(_dfs(mkt, "TIIE-F", [days])[0], abs=1e-8, rel=0)


def test_r2_through_the_api_the_payload_dfs_match_tiie(app, client):
    _parity_snapshot(app)
    s = client.get(URL).get_json()
    tiie = {p["days"]: p["df"] for p in s["curves"]["TIIE-F"]["points"]}
    for p in s["curves"][CSA]["points"]:
        assert p["df"] == pytest.approx(tiie[p["days"]], abs=1e-8, rel=0)
    assert all(abs(r["diff"]) <= 1e-8 for r in s["csa"]["implied_vs_quoted"])
    assert all(r["implied_forward"] == pytest.approx(r["parity_forward"], abs=1e-8) for r in s["csa"]["implied_vs_quoted"])


# ----------------------------------------------------------------------------- choques (D6)

FORWARD_DAYS = (28, 84, 168, 364)


def _moved(base, other):
    """Días de pilar de `MXN-USD` cuyo DF cambió entre dos contextos (tolerancia 1e-12)."""
    days = [p["days"] for p in base.pillars[CSA]]
    return [
        d for d, a, b in zip(days, _dfs(base, CSA, days), _dfs(other, CSA, days)) if abs(a - b) > 1e-12
    ]


def test_tiie_shock_moves_basis_pillars_only(app):
    mkt = _context(app)
    moved = _moved(mkt, mkt.shifted(curve="TIIE-F", parallel_bp=10.0))
    assert moved and all(d not in FORWARD_DAYS for d in moved)
    assert set(moved) == {728, 1092, 1820, 2548, 3640}


def test_tiie_single_pillar_shock_also_recalibrates(app):
    mkt = _context(app)
    n = len(mkt.pillars["TIIE-F"])
    shifts = [0.0] * n
    shifts[-1] = 25.0  # solo el pilar de 10 años
    moved = _moved(mkt, mkt.shifted(curve="TIIE-F", pillar_shifts_bp=shifts))
    assert 3640 in moved and not set(moved) & set(FORWARD_DAYS)


def test_sofr_and_spot_shocks_move_the_forward_pillars(app):
    mkt = _context(app)
    sofr = _moved(mkt, mkt.shifted(curve="SOFR", parallel_bp=10.0))
    assert set(FORWARD_DAYS) <= set(sofr)
    spot = _moved(mkt, mkt.shifted(spot_pct=1.0))
    assert set(FORWARD_DAYS) <= set(spot)
    # los puntos forward se fijan en pesos: con el spot ×1.01 el forward implícito sigue a spot + puntos
    up = mkt.shifted(spot_pct=1.0)
    implied = qfpy.FxForward(1.0, 1.0, 28, qfpy.FxSide.Buy, "USDMXN", CSA).forward_rate(up.env)
    assert implied == pytest.approx(up.spot + 0.0438, abs=1e-8)


def test_csa_shock_leaves_tiie_and_sofr_alone(app):
    mkt = _context(app)
    n = len(mkt.pillars[CSA])
    shifts = [0.0] * n
    shifts[5] = 7.0
    moved = mkt.shifted(curve=CSA, pillar_shifts_bp=shifts)
    assert _zeros(moved, "TIIE-F") == _zeros(mkt, "TIIE-F")
    assert _zeros(moved, "SOFR") == _zeros(mkt, "SOFR")
    assert moved.spot == mkt.spot
    before, after = _zeros(mkt, CSA), _zeros(moved, CSA)
    assert after[5] == pytest.approx(before[5] + 0.0007, abs=1e-9)
    assert [a for i, a in enumerate(after) if i != 5] == [b for i, b in enumerate(before) if i != 5]
    par = mkt.shifted(curve=CSA, parallel_bp=1.0)
    assert _zeros(par, "TIIE-F") == _zeros(mkt, "TIIE-F") and _zeros(par, "SOFR") == _zeros(mkt, "SOFR")
    assert all(a == pytest.approx(b + 0.0001, abs=1e-9) for a, b in zip(_zeros(par, CSA), _zeros(mkt, CSA)))


def test_csa_shock_with_spot_applies_over_the_recalibrated_curve(app):
    mkt = _context(app)
    spot_only = mkt.shifted(spot_pct=1.0)
    both = mkt.shifted(curve=CSA, parallel_bp=1.0, spot_pct=1.0)
    assert all(
        a == pytest.approx(b + 0.0001, abs=1e-9) for a, b in zip(_zeros(both, CSA), _zeros(spot_only, CSA))
    )


def test_shifted_does_not_change_the_original_or_the_pillars(app):
    mkt = _context(app)
    before = _zeros(mkt, CSA)
    pillars = [dict(p) for p in mkt.pillars[CSA]]
    mkt.shifted(curve="TIIE-F", parallel_bp=50.0)
    mkt.shifted(curve=CSA, parallel_bp=50.0)
    assert _zeros(mkt, CSA) == before and mkt.pillars[CSA] == pillars


def test_shifted_errors_keep_their_messages(app):
    mkt = _context(app)
    with pytest.raises(ValueError, match="curva desconocida"):
        mkt.shifted(curve="EUR", parallel_bp=1.0)
    with pytest.raises(ValueError, match="se esperaban 9 desplazamientos para MXN-USD"):
        mkt.shifted(curve=CSA, pillar_shifts_bp=[0.0])
    strip_csa(app, "MX-DEMO")
    with pytest.raises(ValueError, match="curva desconocida: MXN-USD"):
        _context(app).shifted(curve=CSA, parallel_bp=1.0)


def test_put_spot_recalibrates_the_curve(client):
    before = client.get(URL).get_json()
    s = client.put(URL, json={"spot": 19.5}).get_json()
    assert s["curves"][CSA]["points"][0]["df"] != before["curves"][CSA]["points"][0]["df"]
    assert all(abs(r["diff"]) <= 1e-8 for r in s["csa"]["implied_vs_quoted"])
    assert s["csa"]["implied_vs_quoted"][0]["quoted_forward"] == pytest.approx(19.5 + 0.0438)


# ----------------------------------------------------------------------------- validación

def _bad(app, mutate):
    data = _data(app)
    mutate(data)
    _set_data(app, data)


@pytest.mark.parametrize(
    "mutate, fragment",
    [
        (lambda d: d["fx_forwards"][0].update(days=0), "'days' debe ser un entero mayor que 0"),
        (lambda d: d["fx_forwards"][0].update(days=-28), "'days' debe ser un entero mayor que 0"),
        (lambda d: d["fx_forwards"][0].update(days=28.5), "'days' debe ser un entero mayor que 0"),
        (lambda d: d["fx_forwards"][0].update(days=True), "'days' debe ser un entero mayor que 0"),
        (lambda d: d["fx_forwards"][0].update(days="28"), "'days' debe ser un entero mayor que 0"),
        (lambda d: d["fx_forwards"][1].update(days=28), "orden estrictamente creciente"),
        (lambda d: d["xccy_basis"][2].update(days=1092), "orden estrictamente creciente"),
        (lambda d: d["xccy_basis"][0].update(days=364), "después del último punto forward"),
        (lambda d: d["fx_forwards"][0].update(points=float("nan")), "'points' debe ser un número finito"),
        (lambda d: d["fx_forwards"][0].update(points=float("inf")), "'points' debe ser un número finito"),
        (lambda d: d["fx_forwards"][0].update(points="0.04"), "'points' debe ser un número finito"),
        (lambda d: d["fx_forwards"][0].pop("points"), "'points' debe ser un número finito"),
        (lambda d: d["xccy_basis"][0].update(spread=float("nan")), "'spread' debe ser un número finito"),
        (lambda d: d["xccy_basis"][0].update(spread=None), "'spread' debe ser un número finito"),
        (lambda d: d["fx_forwards"][0].update(label=""), "'label' debe ser un texto"),
        (lambda d: d["fx_forwards"][0].update(label=3), "'label' debe ser un texto"),
        (lambda d: d.update(fx_forwards="1M"), "debe ser una lista"),
        (lambda d: d["xccy_basis"].__setitem__(0, 5), "debe ser un objeto"),
    ],
)
def test_invalid_lists_raise_runtime_error_in_spanish(app, client, mutate, fragment):
    _bad(app, mutate)
    with pytest.raises(RuntimeError, match="snapshot") as exc:
        _context(app)
    assert fragment in str(exc.value)
    # por la API: el snapshot no se puede valuar y la respuesta es 400 con el mensaje
    r = client.get(URL)
    assert r.status_code == 400 and fragment in r.get_json()["error"]


def test_unsolvable_calibration_is_a_spanish_runtime_error(app):
    _bad(app, lambda d: d["xccy_basis"][0].update(spread=5.0))
    with pytest.raises(RuntimeError, match="No se pudo calibrar la curva MXN-USD"):
        _context(app)


def test_forwards_that_break_parity_beyond_repair_fail_the_snapshot(app):
    _bad(app, lambda d: d["fx_forwards"][0].update(points=-1000.0))  # spot + puntos < 0
    with pytest.raises(RuntimeError, match="No se pudo calibrar la curva MXN-USD"):
        _context(app)


# ----------------------------------------------------------------------------- ensure_csa_quotes

def _conn(app):
    conn = db.connect(app.config["DESK_DB"])
    return conn


def test_seeded_demo_carries_the_lists_and_ensure_is_a_noop(app):
    before = _sql(app, "SELECT data FROM snapshots ORDER BY id")
    conn = _conn(app)
    try:
        seed_market.ensure_csa_quotes(conn)
        conn.commit()
    finally:
        conn.close()
    assert _sql(app, "SELECT data FROM snapshots ORDER BY id") == before
    assert set(_data(app)) >= {"fx_forwards", "xccy_basis"}


def test_ensure_adds_the_lists_to_an_already_seeded_demo_idempotently(app):
    expected = seed_market.csa_quotes_data()
    strip_csa(app, "MX-DEMO")
    assert "fx_forwards" not in _data(app)
    conn = _conn(app)
    try:
        seed_market.ensure_csa_quotes(conn)
        conn.commit()
        once = conn.execute("SELECT data FROM snapshots WHERE id = 'MX-DEMO'").fetchone()[0]
        seed_market.ensure_csa_quotes(conn)
        conn.commit()
        twice = conn.execute("SELECT data FROM snapshots WHERE id = 'MX-DEMO'").fetchone()[0]
    finally:
        conn.close()
    assert once == twice
    data = json.loads(once)
    assert data["fx_forwards"] == expected["fx_forwards"] and data["xccy_basis"] == expected["xccy_basis"]


def test_ensure_runs_at_startup(app):
    from desk.api.app import create_app

    strip_csa(app, "MX-DEMO")
    again = create_app(db_path=app.config["DESK_DB"])
    s = again.test_client().get(URL).get_json()
    assert s["csa"]["available"] is True and len(s["curves"][CSA]["points"]) == 9


def test_ensure_does_not_touch_other_snapshots_or_a_demo_with_some_list(app, client):
    _roll(client, "SIN-LISTAS")
    strip_csa(app, "SIN-LISTAS")
    rolled_before = _sql(app, "SELECT data FROM snapshots WHERE id = 'SIN-LISTAS'")
    # MX-DEMO con solo una lista: no se completa ni se pisa
    data = _data(app)
    data.pop("xccy_basis")
    data["fx_forwards"] = data["fx_forwards"][:2]
    _set_data(app, data)
    demo_before = _sql(app, "SELECT data FROM snapshots WHERE id = 'MX-DEMO'")
    conn = _conn(app)
    try:
        seed_market.ensure_csa_quotes(conn)
        conn.commit()
    finally:
        conn.close()
    assert _sql(app, "SELECT data FROM snapshots WHERE id = 'SIN-LISTAS'") == rolled_before
    assert _sql(app, "SELECT data FROM snapshots WHERE id = 'MX-DEMO'") == demo_before
    assert "fx_forwards" not in _data(app, "SIN-LISTAS")


def test_ensure_without_demo_snapshot_does_nothing(app):
    _sql(app, "DELETE FROM snapshots WHERE id = 'MX-DEMO'")
    conn = _conn(app)
    try:
        seed_market.ensure_csa_quotes(conn)
    finally:
        conn.close()
    assert _sql(app, "SELECT COUNT(*) FROM snapshots") == [(0,)]


def test_rolling_the_demo_copies_the_lists(app, client):
    rolled = _roll(client, "D1")
    assert rolled["fx_forwards"] == client.get(URL).get_json()["fx_forwards"]
    assert rolled["xccy_basis"] == client.get(URL).get_json()["xccy_basis"]
    assert len(rolled["curves"][CSA]["points"]) == 9 and rolled["csa"]["available"] is True
    assert _data(app, "D1")["fx_forwards"] == _data(app)["fx_forwards"]


# ----------------------------------------------------------------------------- DV01

def _dv01(client, snapshot="MX-DEMO"):
    r = client.post("/api/risk/dv01", json={"snapshot": snapshot})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def test_dv01_includes_the_dependent_curve_with_zeros_for_the_mxn_portfolio(client):
    d = _dv01(client)
    assert d["errors"] == []
    csa = d["curves"][CSA]
    assert [(p["label"], p["days"]) for p in csa["points"]][:2] == [("1M", 28), ("3M", 84)]
    assert len(csa["points"]) == 9
    assert all(p["dv01_mxn"] == 0 for p in csa["points"]) and csa["parallel_mxn"] == 0


def test_dv01_of_tiie_and_sofr_is_unchanged_by_the_dependent_curve(app, client):
    with_curve = _dv01(client)
    _roll(client, "SIN-LISTAS", as_of="2026-11-10")
    strip_csa(app, "SIN-LISTAS")
    without = _dv01(client, "SIN-LISTAS")
    assert set(without["curves"]) == {"TIIE-F", "SOFR"}
    for name in ("TIIE-F", "SOFR"):
        a, b = with_curve["curves"][name], without["curves"][name]
        assert a["parallel_mxn"] == pytest.approx(b["parallel_mxn"], rel=1e-8, abs=1e-8)
        assert [p["label"] for p in a["points"]] == [p["label"] for p in b["points"]]
        for pa, pb in zip(a["points"], b["points"]):
            assert pa["dv01_mxn"] == pytest.approx(pb["dv01_mxn"], rel=1e-8, abs=1e-8)
    assert with_curve["total_mxn"] == pytest.approx(without["total_mxn"], rel=1e-8)
    assert with_curve["parallel_mxn"] == pytest.approx(without["parallel_mxn"], rel=1e-8)


def test_dv01_without_curve_is_todays_response(app, client):
    strip_csa(app, "MX-DEMO")
    d = _dv01(client)
    assert set(d["curves"]) == {"TIIE-F", "SOFR"}
