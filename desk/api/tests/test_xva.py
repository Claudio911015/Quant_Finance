"""Corte 9, T7: XVA por contraparte (`GET /api/xva`, `/api/xva/params`) sobre el motor multimoneda de `qfxva`.

R2(a) a nivel desk: el valor del motor en t = 0 de cada operación coincide con `valuation.value_trade`. El resto
verifica la forma del JSON, los respaldos de crédito, los supuestos declarados y los parámetros editables.
"""
import copy
import json
import math
import sqlite3
from datetime import date

import pytest

from desk.api import db, lifecycle, market, portfolio, valuation, xccy
from desk.api import fixings as fixing_store
from desk.api.risk import credit, xva
from desk.api.tests.csa_fixture import set_collateral, strip_csa, trade_with

SNAP = "MX-DEMO"
AS_OF = date(2026, 11, 10)
ALFA, BETA, GAMMA = "Banco Alfa (sintético)", "Banco Beta (sintético)", "Banco Gamma (sintético)"
DELTA = "Banco Delta (prueba)"
IRS = {"curve": "TIIE-F", "side": "payer", "notional": 1e8, "periods": 13, "fixed_rate": 0.07}
FORWARD = {"side": "buy", "notional_usd": 1e6, "days": 91, "strike": 18.9}
CP_KEYS = {
    "counterparty", "credit", "included", "excluded", "pv_mxn", "cva_mxn", "cva_stderr_mxn", "dva_mxn", "fva_mxn",
    "total_mxn", "epe_max_mxn", "pfe_max_mxn", "profile",
}
TOP_KEYS = {
    "snapshot", "as_of", "notice", "collateral_note", "params", "model", "assumptions", "own_credit",
    "counterparties", "warnings",
}


def _fast(client, n_paths=100):
    """Pocas trayectorias: las pruebas de forma no necesitan precisión de Monte Carlo."""
    assert client.put("/api/xva/params", json={"n_paths": n_paths}).status_code == 200


def _get(client, snapshot=SNAP):
    r = client.get("/api/xva?snapshot=%s" % snapshot)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _by_name(body):
    return {c["counterparty"]: c for c in body["counterparties"]}


def _sql(app, *statements):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        for sql in statements:
            conn.execute(*sql) if isinstance(sql, tuple) else conn.execute(sql)
        conn.commit()
    finally:
        conn.close()


def _edit_snapshot(app, edit):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        data = json.loads(conn.execute("SELECT data FROM snapshots WHERE id = ?", (SNAP,)).fetchone()[0])
        edit(data)
        conn.execute("UPDATE snapshots SET data = ? WHERE id = ?", (json.dumps(data), SNAP))
        conn.commit()
    finally:
        conn.close()


def _delta(client, product="irs", params=IRS):
    return trade_with(client, product, DELTA, params)


def _notional_mxn(trade, spot):
    p = trade["params"]
    if trade["product"] == "xccy_swap":
        return p["notional_usd"] * spot
    return p["notional"] * (spot if p["curve"] == "SOFR" else 1.0)


def _desk_vs_engine(app, snapshot=SNAP):
    """Compara, por operación viva, el valor del motor en t = 0 con `value_trade`; devuelve cuántas comparó."""
    conn = db.connect(app.config["DESK_DB"])
    try:
        mkt = market.load_context(conn, snapshot)
        fixings = fixing_store.load_all(conn)
        model, _, _ = xva.model_from_snapshot(mkt)
        compared = 0
        for name, trades in xva.live_by_counterparty(conn, mkt).items():
            spec, included, _, _ = xva.build_set(trades, mkt, fixings)
            values = xva.engine(mkt, model, xva.DEFAULTS, [0, 30]).trade_values_at_zero(spec)
            by_id = {t["id"]: t for t in trades}
            ordered = [i for i in included if i["product"] == "irs"] + [i for i in included if i["product"] == "xccy_swap"]
            assert len(values) == len(ordered) > 0, name
            for value, inc in zip(values, ordered):
                trade = by_id[inc["id"]]
                desk = valuation.value_trade(trade, mkt, fixings)["pv_mxn"]
                assert abs(value - desk) <= 1e-6 * _notional_mxn(trade, mkt.spot), (name, inc["id"], value, desk)
                compared += 1
        return compared
    finally:
        conn.close()


# ---------------------------------------------------------------- R2(a): el motor arranca en el PV del desk

def test_engine_value_at_zero_is_the_desk_pv_for_every_covered_trade(app):
    assert _desk_vs_engine(app) == 12  # 4 operaciones cubiertas por contraparte (irs MXN y USD, xccy)


def test_engine_matches_the_desk_with_usd_collateral_and_the_mxn_usd_discount(app, client):
    conn = db.connect(app.config["DESK_DB"])
    try:
        mkt = market.load_context(conn, SNAP)
        trade = [t for t in xva.live_by_counterparty(conn, mkt)[ALFA] if t["id"] == 1][0]
        before = valuation.value_trade(trade, mkt, {})["pv_mxn"]
    finally:
        conn.close()
    assert set_collateral(client, ALFA, "USD", "2026-01-01").status_code == 200
    _desk_vs_engine(app)
    conn = db.connect(app.config["DESK_DB"])
    try:
        alfa = [t for t in portfolio.load_trades(conn) if t["counterparty"] == ALFA]  # el colateral viaja en `trade["collateral"]`
        spec = xva.build_set(alfa, mkt, {})[0]
        assert [s.csa_discount for s in spec.swaps] == [True, True, False]  # los dos IRS TIIE-F (ids 1 y 8) con colateral USD; el SOFR (id 9) no
        assert [x.csa_discount for x in spec.xccys] == [True]
        assert valuation.value_trade(alfa[0], mkt, {})["pv_mxn"] != before  # el colateral sí cambia el PV
    finally:
        conn.close()


def test_engine_matches_the_desk_without_the_mxn_usd_curve(app):
    strip_csa(app, SNAP)
    assert _desk_vs_engine(app) == 12


def test_aged_terms_describe_the_instrument_the_desk_values(app):
    conn = db.connect(app.config["DESK_DB"])
    try:
        mkt = market.load_context(conn, SNAP)
        trades = {t["id"]: t for t in portfolio.load_trades(conn)}
        swap = trades[8]  # IRS TIIE-F pactado un año antes: periodo en curso con factor acumulado
        terms = lifecycle.state(swap, swap["events"], mkt.as_of)["terms"]
        a = valuation.aged_swap_terms(swap, terms, mkt, {}, [])
        assert set(a) == {"notional", "fixed_rate", "start_days", "pay_days", "accrued_factor", "side", "curve", "discount"}
        assert a["start_days"] < 0 < a["pay_days"][0] and a["accrued_factor"] > 1.0 and a["side"] == "receiver"
        assert a["pay_days"] == sorted(set(a["pay_days"]))
        cross = trades[10]
        terms = lifecycle.state(cross, cross["events"], mkt.as_of)["terms"]
        x = xccy.aged_xccy_terms(cross, terms, mkt, {}, [])
        assert x["side"] == "pay_usd" and x["csa_discount"] is True and x["discount"] == "MXN-USD"
        assert x["initial_exchange"] is False and x["final_exchange"] is True  # ya empezó; "both" pide el final
    finally:
        conn.close()


# ---------------------------------------------------------------- forma del JSON

def test_response_shape_and_totals(client):
    _fast(client)
    body = _get(client)
    assert set(body) == TOP_KEYS
    assert body["snapshot"] == SNAP and body["as_of"] == "2026-11-10"
    assert body["notice"] == "XVA informativo: no entra al PV ni a la contabilidad"
    assert body["collateral_note"].startswith("Exposición sin colateral ni margen")
    assert body["params"] == {"funding_spread": 0.005, "n_paths": 100, "seed": 42, "pfe_quantile": 0.95}
    assert [c["counterparty"] for c in body["counterparties"]] == [ALFA, BETA, GAMMA]
    for cp in body["counterparties"]:
        assert set(cp) == CP_KEYS
        assert cp["total_mxn"] == pytest.approx(cp["cva_mxn"] - cp["dva_mxn"] + cp["fva_mxn"], rel=1e-12)
        assert cp["pv_mxn"] == pytest.approx(sum(i["pv_mxn"] for i in cp["included"]))
        assert cp["cva_mxn"] > 0 and cp["dva_mxn"] > 0 and cp["cva_stderr_mxn"] > 0
        assert cp["epe_max_mxn"] == max(p["epe_mxn"] for p in cp["profile"])
        assert cp["pfe_max_mxn"] == max(p["pfe_mxn"] for p in cp["profile"])
        assert all(p["pfe_mxn"] >= p["epe_mxn"] >= 0 and p["ene_mxn"] >= 0 for p in cp["profile"])


def test_included_and_excluded_trades_are_listed_in_spanish(client):
    _fast(client)
    cps = _by_name(_get(client))
    assert [i["id"] for i in cps[ALFA]["included"]] == [1, 8, 9, 10]
    assert [i["id"] for i in cps[BETA]["included"]] == [2, 11, 12, 13]
    assert [i["id"] for i in cps[GAMMA]["included"]] == [3, 14, 15, 16]
    labels = {i["product"]: i["label"] for cp in cps.values() for i in cp["included"]}
    assert labels == {"irs": "Swap de tasas (IRS)", "xccy_swap": "Cross currency swap USDMXN"}
    assert cps[ALFA]["excluded"] == [
        {"id": 4, "product": "fx_forward", "reason": "El XVA solo cubre swaps de tasa y cross currency swaps: Forward FX se excluye"},
        {"id": 7, "product": "cap_floor", "reason": "El XVA solo cubre swaps de tasa y cross currency swaps: Cap / Floor se excluye"},
    ]
    assert [e["id"] for e in cps[BETA]["excluded"]] == [5] and [e["id"] for e in cps[GAMMA]["excluded"]] == [6]
    assert "Opción FX" in cps[GAMMA]["excluded"][0]["reason"]


def test_profile_starts_at_the_desk_pv_and_runs_monthly_past_the_last_maturity(app, client):
    _fast(client)
    cps = _by_name(_get(client))
    conn = db.connect(app.config["DESK_DB"])
    try:
        maturity = {t["id"]: t["maturity_date"] for t in portfolio.load_trades(conn)}
    finally:
        conn.close()
    for cp in cps.values():
        first, second = cp["profile"][0], cp["profile"][1]
        assert (first["date"], first["t"]) == ("2026-11-10", 0.0) and second["date"] == "2026-12-10"
        # V(0) neto del motor = PV del desk (cada operación a 1e-6 de su nocional: 1e3 MXN sobra para el conjunto)
        assert first["epe_mxn"] == pytest.approx(max(cp["pv_mxn"], 0.0), abs=1e3)
        assert first["ene_mxn"] == pytest.approx(max(-cp["pv_mxn"], 0.0), abs=1e3)
        last = max(maturity[i["id"]] for i in cp["included"]).isoformat()
        assert cp["profile"][-1]["date"] >= last > cp["profile"][-2]["date"]


def test_published_profile_is_the_undiscounted_one_and_cva_uses_the_chosen_credit(app, client):
    _fast(client, 200)
    quotes = [{"tenor_years": 1, "spread": 0.006}, {"tenor_years": 3, "spread": 0.009}]
    # recuperaciones distintas: la LGD de la contraparte (CVA) y la propia (DVA) no se pueden confundir
    assert client.put("/api/credit/curves/propia", json={"recovery": 0.25, "quotes": quotes}).status_code == 200
    assert client.put("/api/credit/curves/%s" % GAMMA.replace(" ", "%20"), json={"recovery": 0.5, "quotes": quotes}).status_code == 200
    body = _get(client)
    conn = db.connect(app.config["DESK_DB"])
    try:
        mkt = market.load_context(conn, SNAP)
        fixings = fixing_store.load_all(conn)
        model = xva.model_from_snapshot(mkt)[0]
        gamma = xva.live_by_counterparty(conn, mkt)[GAMMA]
        spec, included, _, _ = xva.build_set(gamma, mkt, fixings)
        last = max(t["maturity_date"] for t in gamma if t["id"] in {i["id"] for i in included})
        report = xva.report_days(AS_OF, last)
        profile = xva.engine(
            mkt, model, {"n_paths": 200, "seed": 42, "pfe_quantile": 0.95}, xva.integration_days(report, spec)
        ).simulate([spec])[0]
        curve, recovery, _ = xva.credit_for(conn, GAMMA, mkt)
        own, own_recovery, _ = xva.own_credit(conn, mkt)
        import qfxva

        expected = qfxva.compute_xva(profile, curve, 1 - recovery, own, 1 - own_recovery, 0.005)
    finally:
        conn.close()
    cp = _by_name(body)[GAMMA]
    assert (cp["credit"]["recovery"], body["own_credit"]["recovery"]) == (0.5, 0.25)
    # H21: el XVA se integra sobre la malla de integración (más fina) y el perfil publicado es su subconjunto mensual
    shown = [i for i, d in enumerate(profile.days) if d in set(report)]
    assert len(shown) == len(report) < len(profile.days)
    assert [p["epe_mxn"] for p in cp["profile"]] == [profile.epe[i] for i in shown]
    assert [p["ene_mxn"] for p in cp["profile"]] == [profile.ene[i] for i in shown]
    assert [p["pfe_mxn"] for p in cp["profile"]] == [profile.pfe[i] for i in shown]
    assert (cp["cva_mxn"], cp["dva_mxn"], cp["fva_mxn"]) == (expected.cva, expected.dva, expected.fva)
    assert cp["cva_stderr_mxn"] == expected.cva_stderr


def test_two_requests_give_identical_results(client):
    _fast(client)
    assert _get(client) == _get(client)


def test_warnings_report_the_missing_fixings_of_aged_trades(client):
    _fast(client)
    codes = {(w["code"], w["index"]) for w in _get(client)["warnings"]}
    assert ("missing_fixing", "TIIE-F") in codes and ("missing_fixing", "SOFR") in codes


def test_unknown_snapshot_and_missing_parameter(client):
    r = client.get("/api/xva")
    assert r.status_code == 400 and r.get_json()["field"] == "snapshot"
    r = client.get("/api/xva?snapshot=NO-EXISTE")
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"


def test_counterparty_with_only_uncovered_trades_is_listed_with_zeros(client):
    _fast(client)
    _delta(client, "fx_forward", FORWARD)
    cp = _by_name(_get(client))[DELTA]
    assert cp["included"] == [] and [e["product"] for e in cp["excluded"]] == ["fx_forward"]
    assert (cp["pv_mxn"], cp["cva_mxn"], cp["dva_mxn"], cp["fva_mxn"], cp["total_mxn"]) == (0.0,) * 5
    assert cp["profile"] == [] and cp["epe_max_mxn"] == 0.0 and cp["pfe_max_mxn"] == 0.0


# ---------------------------------------------------------------- crédito

def test_credit_comes_from_the_cds_curve_with_its_synthetic_source(client):
    _fast(client)
    body = _get(client)
    assert body["own_credit"] == {
        "entity": "propia", "kind": "curve", "recovery": 0.4, "assumed": False, "note": None,
        "source": {"kind": "synthetic", "label": "Sintética (inventada para demostración)"},
    }
    for cp in body["counterparties"]:
        assert cp["credit"] == {
            "kind": "curve", "recovery": 0.4, "assumed": False, "note": None,
            "source": {"kind": "synthetic", "label": "Sintética (inventada para demostración)"},
        }


def test_counterparty_without_a_curve_falls_back_to_the_flat_parameters_then_to_the_assumption(client):
    _fast(client)
    _delta(client)
    body = _get(client)
    assumed = _by_name(body)[DELTA]["credit"]
    assert assumed == {"kind": "assumed", "recovery": 0.4, "source": None, "assumed": True, "note": credit.ASSUMED_NOTE}
    assert "%s: %s" % (DELTA, credit.ASSUMED_NOTE) in body["assumptions"]
    saved = client.post("/api/credit/params", json={"counterparty": DELTA, "hazard_rate": 0.02, "recovery": 0.5})
    assert saved.status_code == 201
    flat = _by_name(_get(client))[DELTA]["credit"]
    assert (flat["kind"], flat["recovery"], flat["assumed"], flat["source"]) == ("flat", 0.5, False, None)
    assert "%s: %s" % (DELTA, credit.ASSUMED_NOTE) not in _get(client)["assumptions"]


def test_zero_flat_hazard_gives_exactly_zero_cva_and_dva_keeps_the_funding(client):
    _fast(client)
    _delta(client)
    client.post("/api/credit/params", json={"counterparty": DELTA, "hazard_rate": 0.0, "recovery": 0.4})
    cp = _by_name(_get(client))[DELTA]
    assert cp["cva_mxn"] == 0.0 and cp["cva_stderr_mxn"] == 0.0
    assert cp["total_mxn"] == pytest.approx(-cp["dva_mxn"] + cp["fva_mxn"])


def test_a_curve_that_does_not_fit_the_snapshot_is_declared_and_replaced_by_the_fallback(app, client):
    _fast(client)
    _delta(client)
    bad = json.dumps([{"tenor_years": 1, "spread": 0.03}, {"tenor_years": 2, "spread": 0.005}])
    _sql(app, ("INSERT INTO credit_curves (entity, as_of, recovery, quotes, source, created_at) VALUES (?, ?, ?, ?, ?, ?)",
               (DELTA, "2026-11-11", 0.4, bad, "synthetic", "2026-11-11T00:00:00+00:00")))
    credit_info = _by_name(_get(client))[DELTA]["credit"]
    assert credit_info["kind"] == "assumed" and credit_info["assumed"] is True
    assert "intensidad de incumplimiento negativa" in credit_info["note"] and credit_info["note"].endswith("se usó el respaldo")


def test_missing_own_curve_is_declared_as_an_assumption(app, client):
    _fast(client)
    _sql(app, "DROP TRIGGER credit_curves_no_delete", "DELETE FROM credit_curves WHERE entity = 'propia'")
    body = _get(client)
    assert body["own_credit"]["kind"] == "assumed" and body["own_credit"]["entity"] == "propia"
    assert "Crédito propio: %s" % credit.ASSUMED_NOTE in body["assumptions"]
    assert all(cp["dva_mxn"] > 0 for cp in body["counterparties"])


# ---------------------------------------------------------------- modelo y supuestos

def test_model_comes_from_the_snapshot(app, client):
    _fast(client)
    body = _get(client)
    conn = db.connect(app.config["DESK_DB"])
    try:
        mkt = market.load_context(conn, SNAP)
    finally:
        conn.close()
    assert body["model"] == {
        "hw": {"TIIE-F": {"a": 0.05, "sigma": 0.01}, "SOFR": {"a": 0.03, "sigma": 0.008}},
        "fx_vol": mkt.surface.vol(mkt.spot, 1.0),
        "fx_vol_source": "surface_atm_1y",
        "correlations": {"mxn_usd": 0.35, "mxn_fx": 0.30, "usd_fx": -0.10},
    }
    # con todo presente solo se declara la aproximación de las correlaciones, la malla de integración y el fondeo por omisión
    assert body["assumptions"] == [
        xva.CORRELATION_NOTE, xva.INTEGRATION_NOTE, "Spread de fondeo 0.50 %: valor por omisión, sin ajuste capturado"
    ]


def test_fx_vol_falls_back_to_the_daily_factor_vol_without_a_surface(app):
    conn = db.connect(app.config["DESK_DB"])
    try:
        mkt = copy.copy(market.load_context(conn, SNAP))
    finally:
        conn.close()
    mkt.surface = None
    _, model, assumptions = xva.model_from_snapshot(mkt)
    assert model["fx_vol_source"] == "factor_daily_vol"
    assert model["fx_vol"] == pytest.approx(0.0075 * math.sqrt(252))
    assert assumptions == [xva.CORRELATION_NOTE]


def test_missing_snapshot_data_uses_declared_defaults(app, client):
    _fast(client)

    def drop(data):
        data["hw"] = {"SOFR": {"a": 0.04, "sigma": 0.009}}
        data["factors"] = {}

    _edit_snapshot(app, drop)
    body = _get(client)
    assert body["model"]["hw"] == {"TIIE-F": {"a": 0.05, "sigma": 0.01}, "SOFR": {"a": 0.04, "sigma": 0.009}}
    assert body["model"]["correlations"] == {"mxn_usd": 0.0, "mxn_fx": 0.0, "usd_fx": 0.0}
    text = "\n".join(body["assumptions"])
    assert "parámetros Hull-White de TIIE-F" in text and "a = 0.05 y σ = 0.01" in text
    assert "Hull-White de SOFR" not in text
    assert "correlaciones de los factores" in text and xva.CORRELATION_NOTE not in body["assumptions"]


def test_snapshot_without_the_mxn_usd_curve_declares_it(app, client):
    _fast(client)
    strip_csa(app, SNAP)
    body = _get(client)
    assert any("curva MXN-USD" in a for a in body["assumptions"])
    assert "no_csa_curve" in {w["code"] for w in body["warnings"]}
    assert all(cp["cva_mxn"] > 0 for cp in body["counterparties"])


def test_correlations_that_are_not_positive_definite_are_rejected(app, client):
    def bad(data):
        data["factors"]["correlations"] = [[1.0, 0.9, 0.9], [0.9, 1.0, -0.9], [0.9, -0.9, 1.0]]

    _edit_snapshot(app, bad)
    r = client.get("/api/xva?snapshot=%s" % SNAP)
    assert r.status_code == 400 and "not positive definite" in r.get_json()["error"]


# ---------------------------------------------------------------- parámetros

def test_params_defaults_and_defaults_are_flagged_as_assumed(client):
    r = client.get("/api/xva/params")
    assert r.status_code == 200
    d = {"funding_spread": 0.005, "n_paths": 2000, "seed": 42, "pfe_quantile": 0.95}
    assert r.get_json() == dict(d, assumed={"funding_spread": True}, defaults=d)


def test_params_put_accepts_any_subset_persists_and_responds_like_the_get(app, client):
    r = client.put("/api/xva/params", json={"funding_spread": 0.01})
    assert r.status_code == 200
    d = r.get_json()
    assert d["funding_spread"] == 0.01 and d["n_paths"] == 2000 and d["assumed"] == {"funding_spread": False}
    assert d == client.get("/api/xva/params").get_json()
    r = client.put("/api/xva/params", json={"n_paths": 500, "seed": 7, "pfe_quantile": 0.99})
    assert (r.get_json()["n_paths"], r.get_json()["seed"], r.get_json()["pfe_quantile"]) == (500, 7, 0.99)
    assert r.get_json()["funding_spread"] == 0.01  # lo ya guardado se conserva
    rows = sqlite3.connect(app.config["DESK_DB"]).execute("SELECT key, value FROM settings WHERE key LIKE 'xva.%'").fetchall()
    assert dict(rows) == {"xva.funding_spread": "0.01", "xva.n_paths": "500", "xva.seed": "7", "xva.pfe_quantile": "0.99"}
    assert client.put("/api/xva/params", json={}).status_code == 200


@pytest.mark.parametrize(
    "key, value",
    [
        ("funding_spread", -0.001), ("funding_spread", 0.11), ("funding_spread", "x"), ("funding_spread", None),
        ("n_paths", 99), ("n_paths", 20001), ("n_paths", 100.5), ("n_paths", True), ("n_paths", "500"),
        ("seed", -1), ("seed", 2 ** 31), ("seed", 1.5),
        ("pfe_quantile", 0.49), ("pfe_quantile", 1.0), ("pfe_quantile", False),
    ],
)
def test_params_put_rejects_out_of_range_values_with_the_field(app, client, key, value):
    r = client.put("/api/xva/params", json={key: value})
    assert r.status_code == 400 and r.get_json()["field"] == key
    assert sqlite3.connect(app.config["DESK_DB"]).execute("SELECT COUNT(*) FROM settings WHERE key LIKE 'xva.%'").fetchone()[0] == 0


def test_params_put_edges_unknown_keys_and_atomicity(app, client):
    ok = {"funding_spread": 0.1, "n_paths": 20000, "seed": 2 ** 31 - 1, "pfe_quantile": 0.999}
    assert client.put("/api/xva/params", json=ok).status_code == 200
    low = {"funding_spread": 0.0, "n_paths": 100, "seed": 0, "pfe_quantile": 0.5}
    assert client.put("/api/xva/params", json=low).get_json()["n_paths"] == 100
    r = client.put("/api/xva/params", json={"hurdle": 1})
    assert r.status_code == 400 and r.get_json()["field"] == "hurdle"
    r = client.put("/api/xva/params", json={"funding_spread": 0.05, "seed": -1})  # nada se guarda si algo falla
    assert r.status_code == 400 and client.get("/api/xva/params").get_json()["funding_spread"] == 0.0
    assert client.put("/api/xva/params", json=[1]).status_code == 400


def test_params_drive_the_simulation(client):
    _fast(client)
    base = _by_name(_get(client))
    client.put("/api/xva/params", json={"funding_spread": 0.0})
    zero = _get(client)
    assert all(cp["fva_mxn"] == 0.0 for cp in zero["counterparties"])
    assert not any("Spread de fondeo" in a for a in zero["assumptions"])  # ya no es la omisión
    assert all(zero["counterparties"][k]["cva_mxn"] == base[cp["counterparty"]]["cva_mxn"] for k, cp in enumerate(zero["counterparties"]))
    client.put("/api/xva/params", json={"seed": 7})
    other = _by_name(_get(client))
    assert other[ALFA]["cva_mxn"] != base[ALFA]["cva_mxn"]
    client.put("/api/xva/params", json={"seed": 42, "n_paths": 300, "funding_spread": 0.005})
    more = _get(client)
    assert more["params"]["n_paths"] == 300 and more["params"]["funding_spread"] == 0.005
