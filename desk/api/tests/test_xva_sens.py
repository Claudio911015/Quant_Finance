"""Corte 12, T4: `GET /api/xva/sensitivities`, las sensibilidades del XVA por diferenciación adjunta (AAD).

Forma del JSON y coherencia con `GET /api/xva`; las derivadas contra choque y reprecio con las mismas trayectorias
(un insumo de cada clase, por la API); y los errores (404, 400, 501, contraparte sin operaciones cubiertas).
"""
import pytest

from desk.api import db, market
from desk.api import fixings as fixing_store
from desk.api.risk import credit_curves, xva, xva_sens
from desk.api.tests.csa_fixture import strip_csa, trade_with

qfxva = xva._qfxva()
pytestmark = pytest.mark.skipif(not getattr(qfxva, "HAS_XAD", False), reason="qf se compiló sin XAD")

SNAP = "MX-DEMO"
ALFA = "Banco Alfa (sintético)"
DELTA = "Banco Delta (prueba)"
KEYS = {"cva", "dva", "fva", "total"}
TOP_KEYS = {
    "snapshot", "as_of", "counterparty", "notice", "method", "cds_jacobian", "params", "paths", "seed", "elapsed_s",
    "valuation_elapsed_s", "n_inputs", "bump_cost_estimate_s", "xva", "curves", "fx", "vols", "credit",
    "funding", "empty_reason", "assumptions", "warnings",
}


def _put_paths(client, n_paths):
    assert client.put("/api/xva/params", json={"n_paths": n_paths}).status_code == 200


def _sens(client, name=ALFA, snapshot=SNAP):
    r = client.get("/api/xva/sensitivities", query_string={"snapshot": snapshot, "counterparty": name})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


@pytest.fixture(scope="module")
def alfa200(tmp_path_factory):
    """Una sola respuesta (200 trayectorias) para las pruebas de forma, y el XVA de `GET /api/xva` con los mismos
    parámetros."""
    from desk.api.app import create_app

    app = create_app(db_path=tmp_path_factory.mktemp("sens") / "t.db")
    client = app.test_client()
    _put_paths(client, 200)
    cps = client.get("/api/xva?snapshot=%s" % SNAP).get_json()["counterparties"]
    return _sens(client), {c["counterparty"]: c for c in cps}[ALFA]


def test_shape_lengths_and_totals(alfa200):
    body, _ = alfa200
    assert set(body) == TOP_KEYS
    assert (body["snapshot"], body["counterparty"], body["paths"], body["seed"]) == (SNAP, ALFA, 200, 42)
    assert [(c["curve"], len(c["pillars"])) for c in body["curves"]] == [("TIIE-F", 10), ("SOFR", 10), ("MXN-USD", 9)]
    assert [v["param"] for v in body["vols"]] == ["fx_vol", "sigma_mxn", "a_mxn", "sigma_usd", "a_usd"]
    for side in ("counterparty", "own"):
        block = body["credit"][side]
        assert block["kind"] == "curve" and [c["tenor"] for c in block["cds"]] == ["1Y", "2Y", "3Y", "5Y", "7Y", "10Y"]
        assert block["hazards"] == []  # con cotizaciones de CDS no se repite la intensidad por tramo
    assert body["n_inputs"] == 10 + 10 + 9 + 1 + 5 + 6 + 6 + 1
    assert body["bump_cost_estimate_s"] == pytest.approx(2 * body["n_inputs"] * body["valuation_elapsed_s"])
    assert body["elapsed_s"] > 0 and body["valuation_elapsed_s"] > 0
    rows = [p for c in body["curves"] for p in c["pillars"]] + [body["fx"], body["funding"]] + body["vols"]
    rows += [r for side in body["credit"].values() for r in side["cds"]]
    for row in rows:
        assert KEYS <= set(row)
        assert row["total"] == pytest.approx(row["cva"] - row["dva"] + row["fva"], rel=1e-12, abs=1e-12)
    # La total (MXN-USD recalibrada) está en TIIE-F, SOFR y el spot; en MXN-USD, que es lo que se recalibra, no.
    with_total = [p for c in body["curves"][:2] for p in c["pillars"]] + [body["fx"]]
    for row in with_total:
        assert set(row["recalibrated"]) == KEYS
        assert row["recalibrated"]["total"] == pytest.approx(
            row["recalibrated"]["cva"] - row["recalibrated"]["dva"] + row["recalibrated"]["fva"], rel=1e-12, abs=1e-12
        )
    assert not any("recalibrated" in p for p in body["curves"][2]["pillars"] + body["vols"])
    assert any(abs(r["recalibrated"]["cva"] - r["cva"]) > 1.0 for r in with_total)  # la recalibración sí importa


def test_xva_is_exactly_the_one_of_get_xva_and_dv01_sums_the_pillars(alfa200):
    body, reference = alfa200
    assert body["xva"] == {k: reference[k] for k in ("cva_mxn", "dva_mxn", "fva_mxn", "total_mxn")}
    for curve in body["curves"]:
        for k in KEYS:
            assert curve["dv01"][k] == pytest.approx(sum(p[k] for p in curve["pillars"]), rel=1e-12)
            if "recalibrated" in curve["dv01"]:
                assert curve["dv01"]["recalibrated"][k] == pytest.approx(
                    sum(p["recalibrated"][k] for p in curve["pillars"]), rel=1e-12
                )
    # Una contraparte con deuda a tasa fija pagada (Alfa paga fija en TIIE-F): el DV01 del CVA no es cero.
    assert any(abs(c["dv01"]["cva"]) > 0 for c in body["curves"])
    assert [n in body["assumptions"] for n in (xva_sens.PARTIAL_NOTE, xva_sens.COST_NOTE)] == [True, True]
    assert body["notice"] == xva.NOTICE


# ---------------------------------------------------------------- AAD contra choque y reprecio

def _bump_world(app, name):
    """Todo lo que `xva_sens.compute` arma, pero para repreciar a mano: devuelve `valuate(...)`, que acepta el
    insumo movido y da (cva, dva, fva) de las mismas trayectorias, y los objetos base."""
    conn = db.connect(app.config["DESK_DB"])
    try:
        mkt = market.load_context(conn, SNAP)
        params = xva.load_params(conn)
        model, model_json, _ = xva.model_from_snapshot(mkt)
        trades = xva.live_by_counterparty(conn, mkt)[name]
        spec, included, _, _ = xva.build_set(trades, mkt, fixing_store.load_all(conn))
        report = xva.report_days(mkt.as_of, xva._last_maturity(trades, included))
        cp_curve, cp_recovery, _ = xva.credit_for(conn, name, mkt)
        own_curve, own_recovery, _ = xva.own_credit(conn, mkt)
        quotes_row = credit_curves.current(conn)[name]
    finally:
        conn.close()
    days = xva.integration_days(report, spec)
    profile = xva.engine(mkt, model, params, days).simulate([spec])[0]

    def credit(cp=cp_curve, funding=params["funding_spread"]):  # el perfil no depende del crédito ni del fondeo
        x = qfxva.compute_xva(profile, cp, 1.0 - cp_recovery, own_curve, 1.0 - own_recovery, funding)
        return x.cva, x.dva, x.fva

    def exposure(curves=None, spot=None, fx_vol=None):
        mk = qfxva.ExposureMarket(
            (curves or {}).get("TIIE-F", mkt.curves["TIIE-F"]), (curves or {}).get("SOFR", mkt.curves["SOFR"]),
            spot or mkt.spot, (curves or {}).get(market.CSA_CURVE, mkt.curves[market.CSA_CURVE]),
        )
        hw, rho = model_json["hw"], model_json["correlations"]
        md = qfxva.ExposureModel(
            a_mxn=hw["TIIE-F"]["a"], sigma_mxn=hw["TIIE-F"]["sigma"], a_usd=hw["SOFR"]["a"],
            sigma_usd=hw["SOFR"]["sigma"], fx_vol=fx_vol or model_json["fx_vol"], rho_mxn_usd=rho["mxn_usd"],
            rho_mxn_fx=rho["mxn_fx"], rho_usd_fx=rho["usd_fx"],
        )
        config = qfxva.SimConfig(
            n_paths=params["n_paths"], seed=params["seed"], pfe_quantile=params["pfe_quantile"], report_days=days
        )
        p = qfxva.ExposureEngine(mk, md, config).simulate([spec])[0]
        x = qfxva.compute_xva(p, cp_curve, 1.0 - cp_recovery, own_curve, 1.0 - own_recovery, params["funding_spread"])
        return x.cva, x.dva, x.fva

    return mkt, params, model_json["fx_vol"], credit, exposure, quotes_row


def _central(plus, minus, width):
    """(cva, dva, fva, total) de la diferencia central; `width` es el ancho del intervalo en la unidad del reporte."""
    d = [(a - b) / width for a, b in zip(plus, minus)]
    return {"cva": d[0], "dva": d[1], "fva": d[2], "total": d[0] - d[1] + d[2]}


def _agree(row, expected, what):
    """Tolerancia de la decisión de Fable: max(1 %, 1e-4 MXN por pb); la derivada es la parcial de las mismas
    trayectorias, así que la diferencia es solo el error de la diferencia central."""
    for k in KEYS:
        assert abs(row[k] - expected[k]) <= max(0.01 * abs(expected[k]), 1e-4), (what, k, row[k], expected[k])


def test_aad_matches_bump_and_reprice_for_one_input_of_each_class(app, client):
    _put_paths(client, 500)
    body = _sens(client)
    mkt, params, fx_vol, credit, exposure, quotes_row = _bump_world(app, ALFA)
    spot = mkt.spot
    biggest = lambda rows: max(range(len(rows)), key=lambda i: abs(rows[i]["total"]))  # noqa: E731

    for curve in body["curves"]:                      # un pilar de cada curva: el de mayor sensibilidad; ±0.1 pb
        i = biggest(curve["pillars"])
        base = mkt.curves[curve["curve"]]
        moved = lambda bp: {curve["curve"]: base.bumped(i, bp)}  # noqa: E731
        _agree(curve["pillars"][i], _central(exposure(moved(0.1)), exposure(moved(-0.1)), 0.2), (curve["curve"], i))
    assert body["fx"]["total"] != 0.0                 # spot ± 0.01 MXN, por 1 % del spot (0.01 * spot MXN)
    _agree(body["fx"], _central(exposure(spot=spot + 0.01), exposure(spot=spot - 0.01), 0.02 / (0.01 * spot)), "spot")
    vol = body["vols"][0]                             # volatilidad USDMXN ± 1e-4, por 0.01
    _agree(vol, _central(exposure(fx_vol=fx_vol + 1e-4), exposure(fx_vol=fx_vol - 1e-4), 2e-4 / 0.01), "fx_vol")
    funding = params["funding_spread"]                # fondeo ± 1e-6, por pb
    _agree(body["funding"], _central(credit(funding=funding + 1e-6), credit(funding=funding - 1e-6), 2e-6 / 1e-4),
           "funding")

    quotes = quotes_row["quotes"]                     # la cotización de CDS de mayor sensibilidad ± 1e-6, por pb
    cds_rows = body["credit"]["counterparty"]["cds"]  # (Alfa vence antes de 5 años: los plazos largos dan cero)
    k = biggest(cds_rows)

    def shifted(bump):
        moved = [dict(q, spread=q["spread"] + (bump if j == k else 0.0)) for j, q in enumerate(quotes)]
        return credit_curves.build_curve(qfxva, dict(quotes_row, quotes=moved), mkt)

    assert cds_rows[k]["cva"] != 0.0
    _agree(cds_rows[k], _central(credit(cp=shifted(1e-6)), credit(cp=shifted(-1e-6)), 2e-6 / 1e-4), "CDS %s" % k)


def test_total_matches_bump_recalibrate_and_reprice(app, client):
    """La total (MXN-USD recalibrada con sus puntos forward y base fijos) contra choque del insumo, recalibración
    con `MarketContext.shifted` y reprecio completo con las mismas trayectorias: un pilar de TIIE-F, uno de SOFR y
    el spot. Tolerancia max(1 %, 1 MXN por pb); el crédito no se recalibra (el perfil no lo usa)."""
    _put_paths(client, 500)
    body = _sens(client)
    mkt, _, _, _, exposure, _ = _bump_world(app, ALFA)

    def reprice(recalibrate, **move):
        ctx = mkt.shifted(**move)
        keep = {} if recalibrate else {market.CSA_CURVE: mkt.curves[market.CSA_CURVE]}
        return exposure(curves=dict(ctx.curves, **keep), spot=ctx.spot)

    def agree(row, plus, minus, width, what):
        total, partial = (_central(reprice(r, **plus), reprice(r, **minus), width) for r in (True, False))
        for k in KEYS:
            assert abs(row["recalibrated"][k] - total[k]) <= max(0.01 * abs(total[k]), 1.0), (what, k)
            gap = total[k] - partial[k]  # lo que aporta la recalibración: es lo que delataría un jacobiano mal escalado
            assert abs(row["recalibrated"][k] - row[k] - gap) <= max(0.02 * abs(gap), 0.05), (what, k, gap)
        return total

    gaps = []
    for curve in body["curves"][:2]:                  # TIIE-F y SOFR: el pilar de mayor sensibilidad total; ± 0.1 pb
        rows = curve["pillars"]
        i = max(range(len(rows)), key=lambda j: abs(rows[j]["recalibrated"]["total"]))
        shift = lambda s: {"curve": curve["curve"], "pillar_shifts_bp": [s * 0.1 * (j == i) for j in range(len(rows))]}  # noqa: E731
        agree(rows[i], shift(1), shift(-1), 0.2, (curve["curve"], i))
        gaps.append(abs(rows[i]["recalibrated"]["cva"] - rows[i]["cva"]))
    total = agree(body["fx"], {"spot_pct": 0.05}, {"spot_pct": -0.05}, 0.1, "spot")  # por 1 % del spot
    gaps.append(abs(body["fx"]["recalibrated"]["cva"] - body["fx"]["cva"]))
    assert all(g > 1.0 for g in gaps) and total["cva"] != 0.0  # la recalibración mueve el resultado: no es vacía


# ---------------------------------------------------------------- errores y casos límite

def test_unknown_counterparty_is_404_and_missing_parameters_are_400(client):
    r = client.get("/api/xva/sensitivities", query_string={"snapshot": SNAP, "counterparty": "Nadie"})
    assert r.status_code == 404 and r.get_json() == {"error": "Contraparte inexistente: Nadie", "field": "counterparty"}
    r = client.get("/api/xva/sensitivities", query_string={"snapshot": "NO-EXISTE", "counterparty": ALFA})
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"
    for query, field in (({"counterparty": ALFA}, "snapshot"), ({"snapshot": SNAP}, "counterparty")):
        r = client.get("/api/xva/sensitivities", query_string=query)
        assert r.status_code == 400 and r.get_json()["field"] == field


def test_without_xad_the_route_answers_501(client, monkeypatch):
    monkeypatch.setattr(qfxva, "HAS_XAD", False)
    r = client.get("/api/xva/sensitivities", query_string={"snapshot": SNAP, "counterparty": ALFA})
    assert r.status_code == 501 and "QF_WITH_XAD=OFF" in r.get_json()["error"]


def test_counterparty_without_covered_trades_has_empty_sensitivities(client):
    _put_paths(client, 100)
    trade_with(client, "fx_forward", DELTA, {"side": "buy", "notional_usd": 1e6, "days": 91, "strike": 18.9})
    body = _sens(client, DELTA)
    assert body["empty_reason"] and body["curves"] == [] and body["vols"] == []
    assert body["credit"]["counterparty"]["cds"] == [] and body["credit"]["counterparty"]["hazards"] == []
    assert body["xva"] == {"cva_mxn": 0.0, "dva_mxn": 0.0, "fva_mxn": 0.0, "total_mxn": 0.0}
    assert body["fx"]["total"] == 0.0 and body["funding"]["total"] == 0.0 and body["n_inputs"] == 0


def test_without_the_mxn_usd_curve_it_does_not_appear(app, client):
    _put_paths(client, 100)
    strip_csa(app, SNAP)
    body = _sens(client)
    assert [c["curve"] for c in body["curves"]] == ["TIIE-F", "SOFR"]
    assert body["n_inputs"] == 10 + 10 + 1 + 5 + 6 + 6 + 1
    for row in body["curves"][0]["pillars"] + body["curves"][1]["pillars"] + [body["fx"]]:
        assert row["recalibrated"] == {k: row[k] for k in KEYS}  # sin MXN-USD no hay nada que recalibrar


def test_assumptions_carry_the_same_notes_as_get_xva(app, client):
    """MXN-USD ausente, fondeo por omisión, crédito propio supuesto y crédito supuesto de la contraparte: las
    mismas líneas, en el mismo orden, que `GET /api/xva` (una sola función de `xva.py` las escribe)."""
    _put_paths(client, 100)
    strip_csa(app, SNAP)
    trade_with(client, "irs", DELTA, {"curve": "TIIE-F", "side": "payer", "notional": 1e8, "periods": 13, "fixed_rate": 0.07})
    conn = db.connect(app.config["DESK_DB"])
    try:
        conn.execute("DROP TRIGGER credit_curves_no_delete")
        conn.execute("DELETE FROM credit_curves WHERE entity = 'propia'")
        conn.commit()
    finally:
        conn.close()
    reference = client.get("/api/xva", query_string={"snapshot": SNAP}).get_json()["assumptions"]
    notes = [a for a in reference if "curva MXN-USD" in a or "Spread de fondeo" in a or a.startswith(("Crédito propio", DELTA))]
    assert len(notes) == 4  # las cuatro existen en el caso armado: la prueba no puede pasar vacía
    assert _sens(client, DELTA)["assumptions"] == reference + [xva_sens.PARTIAL_NOTE, xva_sens.COST_NOTE]
