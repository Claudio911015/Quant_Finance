"""Corte 6, T7: exposición (EE/PFE), CVA informativo y parámetros de crédito por contraparte."""
import calendar
import re
import sqlite3
from datetime import date, datetime, timezone

import pytest

from desk.api import db, lifecycle, market, portfolio, valuation
from desk.api import fixings as fixing_store
from desk.api.qf import qfpy
from desk.api.risk import credit
from desk.api.tests.conftest import empty_portfolio, insert_raw_trade

ALFA, BETA, GAMMA = "Banco Alfa (sintético)", "Banco Beta (sintético)", "Banco Gamma (sintético)"
AS_OF = date(2026, 11, 10)  # as_of de MX-DEMO
FWD = {"side": "buy", "notional_usd": 1e6, "days": 91, "strike": 19.0}
ASSUMED = "Supuesto: probabilidad de incumplimiento 1 % anual y recuperación 40 % (sin parámetros capturados)"


# ------------------------------------------------------------------------ ayudas

def _exposure(client, snapshot="MX-DEMO"):
    r = client.get("/api/credit/exposure?snapshot=%s" % snapshot)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _by_name(body):
    return {c["counterparty"]: c for c in body["counterparties"]}


def _set_params(client, name, hazard, recovery):
    r = client.post("/api/credit/params", json={"counterparty": name, "hazard_rate": hazard, "recovery": recovery})
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _credit_rows(app):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        return conn.execute(
            "SELECT c.name, k.hazard_rate, k.recovery, k.as_of FROM counterparty_credit k"
            " JOIN counterparties c ON c.id = k.counterparty_id ORDER BY k.id"
        ).fetchall()
    finally:
        conn.close()


def _live_irs_pv(client, name):
    """Σ PV (MXN) de los `irs` vivos de la contraparte según `GET /api/portfolio/valuation`."""
    rows = client.get("/api/portfolio/valuation?snapshot=MX-DEMO").get_json()["rows"]
    return sum(r["pv_mxn"] for r in rows if r["counterparty"] == name and r["product"] == "irs" and r["status"] == "viva")


def _plus_months(start, k):
    month0 = start.month - 1 + k
    year, month = start.year + month0 // 12, month0 % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


# ------------------------------------------------------------------------ parámetros

def test_params_default_to_assumed_values_for_every_counterparty(client):
    r = client.get("/api/credit/params")
    assert r.status_code == 200
    params = r.get_json()["params"]
    assert [p["counterparty"] for p in params] == [ALFA, BETA, GAMMA]  # por nombre
    for p in params:
        assert (p["hazard_rate"], p["recovery"], p["as_of"], p["assumed"], p["history"]) == (0.01, 0.4, None, True, [])


def test_setting_params_twice_keeps_two_rows_and_the_last_is_current(app, client):
    day0 = datetime.now(timezone.utc).date().isoformat()
    first = _set_params(client, ALFA, 0.02, 0.35)
    assert first["counterparty"] == ALFA and first["assumed"] is False
    assert (first["hazard_rate"], first["recovery"]) == (0.02, 0.35)
    assert len(first["history"]) == 1
    second = _set_params(client, ALFA, 0.03, 0.5)
    assert (second["hazard_rate"], second["recovery"]) == (0.03, 0.5)
    assert [(h["hazard_rate"], h["recovery"]) for h in second["history"]] == [(0.03, 0.5), (0.02, 0.35)]  # nueva primero

    rows = _credit_rows(app)
    assert [(r[0], r[1], r[2]) for r in rows] == [(ALFA, 0.02, 0.35), (ALFA, 0.03, 0.5)]

    listed = {p["counterparty"]: p for p in client.get("/api/credit/params").get_json()["params"]}
    assert (listed[ALFA]["hazard_rate"], listed[ALFA]["recovery"], listed[ALFA]["assumed"]) == (0.03, 0.5, False)
    assert listed[BETA]["assumed"] is True and listed[BETA]["history"] == []  # las demás, intactas

    day1 = datetime.now(timezone.utc).date().isoformat()
    assert second["as_of"] == rows[-1][3] and second["as_of"] in (day0, day1)  # `as_of` = fecha UTC de hoy


def test_params_bounds_are_inclusive_on_hazard_and_exclusive_on_recovery(client):
    assert _set_params(client, BETA, 0.0, 0.0)["hazard_rate"] == 0.0
    assert _set_params(client, BETA, 1.0, 0.99)["hazard_rate"] == 1.0


@pytest.mark.parametrize(
    "body, field",
    [
        ({"counterparty": ALFA, "hazard_rate": 0.02, "recovery": 1}, "recovery"),
        ({"counterparty": ALFA, "hazard_rate": 0.02, "recovery": -0.1}, "recovery"),
        ({"counterparty": ALFA, "hazard_rate": 0.02}, "recovery"),
        ({"counterparty": ALFA, "hazard_rate": 1.0001, "recovery": 0.4}, "hazard_rate"),
        ({"counterparty": ALFA, "hazard_rate": -0.01, "recovery": 0.4}, "hazard_rate"),
        ({"counterparty": ALFA, "hazard_rate": "0.02", "recovery": 0.4}, "hazard_rate"),
        ({"counterparty": ALFA, "hazard_rate": True, "recovery": 0.4}, "hazard_rate"),
        ({"hazard_rate": 0.02, "recovery": 0.4}, "counterparty"),
        ({"counterparty": 7, "hazard_rate": 0.02, "recovery": 0.4}, "counterparty"),
    ],
)
def test_invalid_params_are_400_and_insert_nothing(app, client, body, field):
    r = client.post("/api/credit/params", json=body)
    assert r.status_code == 400 and r.get_json()["field"] == field, r.get_json()
    assert _credit_rows(app) == []


def test_unknown_counterparty_is_404(app, client):
    r = client.post("/api/credit/params", json={"counterparty": "Banco Fantasma", "hazard_rate": 0.02, "recovery": 0.4})
    assert r.status_code == 404 and r.get_json()["field"] == "counterparty"
    assert _credit_rows(app) == []


def test_params_body_must_be_an_object(client):
    assert client.post("/api/credit/params", json=[1]).status_code == 400


# ------------------------------------------------------------------------ exposición

def test_contract_shape_and_constants(client):
    body = _exposure(client)
    assert body["snapshot"] == "MX-DEMO" and body["as_of"] == "2026-11-10"
    assert (body["n_paths"], body["seed"], body["pfe_quantile"]) == (500, 42, 0.95)
    assert body["notice"] == "CVA informativo: no entra al PV ni a la contabilidad de coberturas"
    assert [c["counterparty"] for c in body["counterparties"]] == [ALFA, BETA, GAMMA]
    assert body["warnings"] == []
    alfa = _by_name(body)[ALFA]
    assert alfa["assumed"] is True and alfa["assumed_note"] == ASSUMED
    assert (alfa["hazard_rate"], alfa["recovery"]) == (0.01, 0.4)
    assert alfa["netting_sets"][0]["curve"] == "TIIE-F" and alfa["netting_sets"][0]["currency"] == "MXN"
    assert alfa["netting_sets"][0]["trades"] == [1]
    assert _by_name(body)[GAMMA]["netting_sets"][0]["currency"] == "USD"


def test_ee_and_pfe_are_non_negative_and_pfe_is_at_least_ee(client):
    for cp in _exposure(client)["counterparties"]:
        assert cp["profile"], cp["counterparty"]
        for p in cp["profile"]:
            assert p["ee_mxn"] >= 0.0
            assert p["pfe_mxn"] >= p["ee_mxn"]


def test_ee_at_zero_is_max_pv_of_the_live_swaps_valued_by_the_desk(client):
    body = _exposure(client)
    for name in (ALFA, BETA, GAMMA):
        cp = _by_name(body)[name]
        pv = _live_irs_pv(client, name)
        assert cp["pv_mxn"] == pytest.approx(pv, rel=1e-6)
        first = cp["profile"][0]
        assert first["date"] == "2026-11-10" and first["t"] == 0.0
        assert first["ee_mxn"] == pytest.approx(max(pv, 0.0), rel=1e-6)
        assert first["pfe_mxn"] == first["ee_mxn"]
    # el portafolio sembrado cubre los dos signos: Beta con PV positivo, Alfa y Gamma con PV negativo
    assert _by_name(body)[BETA]["profile"][0]["ee_mxn"] > 0.0
    assert _by_name(body)[ALFA]["profile"][0]["ee_mxn"] == 0.0


def test_grid_is_monthly_and_reaches_the_last_maturity(client):
    body = _exposure(client)
    trades = {t["id"]: t for t in client.get("/api/trades").get_json()["trades"]}
    for name, trade_ids in ((ALFA, [1]), (BETA, [2]), (GAMMA, [3])):
        cp = _by_name(body)[name]
        dates = [p["date"] for p in cp["profile"][1:]]
        last_maturity = max(date.fromisoformat(trades[i]["maturity_date"]) for i in trade_ids)
        for k, (iso, p) in enumerate(zip(dates, cp["profile"][1:]), start=1):
            d = date.fromisoformat(iso)
            assert d == _plus_months(AS_OF, k)
            assert p["t"] == pytest.approx((d - AS_OF).days / 365.0, abs=1e-12)
        assert date.fromisoformat(dates[-1]) >= last_maturity
        assert date.fromisoformat(dates[-2]) < last_maturity  # la primera fecha que alcanza el vencimiento


def test_usd_swap_is_converted_with_the_snapshot_spot(client):
    before = _exposure(client)
    spot = client.get("/api/market/snapshots/MX-DEMO").get_json()["fx"]["spot"]
    r = client.put("/api/market/snapshots/MX-DEMO", json={"spot": spot * 1.1})
    assert r.status_code == 200, r.get_json()
    after = _exposure(client)
    g0, g1 = _by_name(before)[GAMMA], _by_name(after)[GAMMA]
    for a, b in zip(g0["profile"][1:], g1["profile"][1:]):  # t > 0: la simulación en USD no depende del spot
        assert b["ee_mxn"] == pytest.approx(a["ee_mxn"] * 1.1, rel=1e-9)
        assert b["pfe_mxn"] == pytest.approx(a["pfe_mxn"] * 1.1, rel=1e-9)
    assert g1["cva_mxn"] == pytest.approx(g0["cva_mxn"] * 1.1, rel=1e-9)
    assert g1["pv_mxn"] == pytest.approx(g0["pv_mxn"] * 1.1, rel=1e-9)
    a0, a1 = _by_name(before)[ALFA], _by_name(after)[ALFA]  # un swap en MXN no cambia
    assert a1["profile"] == a0["profile"] and a1["cva_mxn"] == a0["cva_mxn"]


def test_zero_hazard_gives_exactly_zero_cva(client):
    _set_params(client, ALFA, 0.0, 0.4)
    alfa = _by_name(_exposure(client))[ALFA]
    assert alfa["cva_mxn"] == 0.0
    assert [ns["cva_mxn"] for ns in alfa["netting_sets"]] == [0.0]
    assert alfa["assumed"] is False and alfa["assumed_note"] is None


def test_cva_grows_with_hazard_and_leaves_the_exposure_profile_alone(client):
    _set_params(client, BETA, 0.01, 0.4)
    low = _by_name(_exposure(client))[BETA]
    _set_params(client, BETA, 0.05, 0.4)
    high = _by_name(_exposure(client))[BETA]
    assert 0.0 < low["cva_mxn"] < high["cva_mxn"]
    assert high["profile"] == low["profile"]  # el riesgo de crédito no mueve EE ni PFE
    assert (high["hazard_rate"], high["assumed"]) == (0.05, False)
    _set_params(client, BETA, 0.05, 0.1)  # menos recuperación = más pérdida
    assert _by_name(_exposure(client))[BETA]["cva_mxn"] > high["cva_mxn"]


def test_cva_of_the_counterparty_is_the_sum_of_its_netting_sets(client):
    for cp in _exposure(client)["counterparties"]:
        assert cp["cva_mxn"] == pytest.approx(sum(ns["cva_mxn"] for ns in cp["netting_sets"]), rel=1e-12)
        assert cp["cva_mxn"] > 0.0


def test_products_without_simulated_exposure_are_listed_as_excluded(client):
    body = _exposure(client)
    expected = {4: "fx_forward", 5: "fx_forward", 6: "fx_option", 7: "cap_floor"}
    top = {x["id"]: x for x in body["excluded"]}
    assert set(top) == set(expected)
    label = {"fx_forward": "Forward FX", "fx_option": "Opción FX", "cap_floor": "Cap / Floor"}
    for trade_id, product in expected.items():
        reason = "La exposición simulada solo cubre swaps de tasas (IRS): %s se excluye" % label[product]
        assert top[trade_id]["product"] == product and top[trade_id]["reason"] == reason
        # el aviso se lee en la interfaz: sin códigos internos de producto
        assert not re.search(r"\b(irs|fx_forward|fx_option|cap_floor)\b", top[trade_id]["reason"])
    assert top[4]["counterparty"] == ALFA and top[7]["counterparty"] == ALFA and top[6]["counterparty"] == GAMMA
    by = _by_name(body)
    assert [x["id"] for x in by[ALFA]["excluded"]] == [4, 7]
    assert by[ALFA]["excluded"][0] == {"id": 4, "product": "fx_forward", "reason": top[4]["reason"]}
    assert [x["id"] for x in by[BETA]["excluded"]] == [5]
    assert [x["id"] for x in by[GAMMA]["excluded"]] == [6]


def test_counterparty_without_covered_swaps_has_an_empty_profile(client):
    r = client.post("/api/trades", json={"product": "fx_forward", "counterparty": "Banco Delta", "params": FWD})
    assert r.status_code == 201, r.get_json()
    delta = _by_name(_exposure(client))["Banco Delta"]
    assert (delta["netting_sets"], delta["profile"], delta["pv_mxn"], delta["cva_mxn"]) == ([], [], 0.0, 0.0)
    assert [x["product"] for x in delta["excluded"]] == ["fx_forward"]
    assert delta["assumed"] is True  # aunque no se simule nada, se le muestran los supuestos


def test_terminated_swap_leaves_the_counterparty_with_only_its_excluded_trades(client):
    r = client.post(
        "/api/trades/2/events", json={"type": "termination", "event_date": "2026-11-10", "data": {"amount": 1000.0}}
    )
    assert r.status_code == 201, r.get_json()
    beta = _by_name(_exposure(client))[BETA]
    assert beta["netting_sets"] == [] and beta["profile"] == [] and beta["pv_mxn"] == 0.0
    assert [x["id"] for x in beta["excluded"]] == [5]  # el swap terminado no es ni cubierto ni excluido


def test_counterparties_without_live_trades_do_not_appear(client):
    empty_portfolio(client)
    body = _exposure(client)
    assert body["counterparties"] == [] and body["excluded"] == [] and body["warnings"] == []


def test_unreadable_swap_is_excluded_with_its_reason_and_does_not_stop_the_rest(app, client):
    insert_raw_trade(app, "irs", "no es json")
    body = _exposure(client)
    raw = _by_name(body)["Raw"]
    assert raw["netting_sets"] == [] and raw["profile"] == []
    assert len(raw["excluded"]) == 1 and raw["excluded"][0]["product"] == "irs"
    assert raw["excluded"][0]["reason"].startswith("No se pudo valuar: ")
    assert _by_name(body)[BETA]["profile"]  # las demás se calculan igual


def _alfa_with_sofr_swap(client, notional_usd):
    """Alfa recibe 4 % en SOFR pagando solo 1 % (PV positivo en USD) además de su swap TIIE-F (PV negativo)."""
    r = client.post(
        "/api/trades",
        json={
            "product": "irs",
            "counterparty": ALFA,
            "params": {"curve": "SOFR", "side": "payer", "notional": notional_usd, "periods": 3, "fixed_rate": 0.01},
        },
    )
    assert r.status_code == 201, r.get_json()
    return _by_name(_exposure(client))[ALFA]


@pytest.mark.parametrize("notional_usd, total_is_positive", [(5e6, True), (5e5, False)])
def test_ee_at_zero_nets_across_currencies_and_later_points_do_not(client, notional_usd, total_is_positive):
    alfa = _alfa_with_sofr_swap(client, notional_usd)
    assert [(ns["curve"], ns["currency"]) for ns in alfa["netting_sets"]] == [("TIIE-F", "MXN"), ("SOFR", "USD")]
    assert alfa["pv_mxn"] == pytest.approx(sum(ns["pv_mxn"] for ns in alfa["netting_sets"]), rel=1e-12)
    pv_tiie, pv_sofr = (ns["pv_mxn"] for ns in alfa["netting_sets"])
    assert pv_tiie < 0.0 < pv_sofr
    assert (alfa["pv_mxn"] > 0.0) is total_is_positive
    # R4: EE(0) = max(PV de la contraparte, 0): el valor de hoy compensa entre monedas...
    first = alfa["profile"][0]
    assert first["ee_mxn"] == pytest.approx(max(alfa["pv_mxn"], 0.0), rel=1e-12)
    assert first["pfe_mxn"] == first["ee_mxn"]
    # ...y es menor que la suma de los conjuntos (que es lo que sí suman los puntos mensuales: cota superior)
    assert first["ee_mxn"] < max(pv_tiie, 0.0) + max(pv_sofr, 0.0)
    assert all(p["pfe_mxn"] >= p["ee_mxn"] >= 0.0 for p in alfa["profile"])


def _model_swap_inputs(app):
    """Por cada `irs` vivo de MX-DEMO: (operación, PV del desk en la moneda de la curva, mercado, términos)."""
    conn = db.connect(app.config["DESK_DB"])
    try:
        mkt = market.load_context(conn, "MX-DEMO")
        fixings = fixing_store.load_all(conn)
        out = []
        for trade in portfolio.load_trades(conn):
            if trade["product"] != "irs" or not valuation.is_live(trade, mkt.as_of):
                continue
            terms = lifecycle.state(trade, trade["events"], mkt.as_of)["terms"]
            v = valuation.value_trade(trade, mkt, fixings)
            out.append((trade, v, mkt, terms))
        return out
    finally:
        conn.close()


def _side(terms):
    return qfpy.SwapType.Payer if terms["side"] == "payer" else qfpy.SwapType.Receiver


def test_model_swap_is_calibrated_to_the_desk_pv_at_zero(app):
    inputs = _model_swap_inputs(app)
    assert len(inputs) == 3
    for trade, v, mkt, terms in inputs:
        curve = mkt.curves[terms["curve"]]
        mat = credit._model_maturity(trade, mkt.as_of)
        rate = credit._effective_fixed_rate(qfpy, curve, _side(terms), v["notional"], mat, v["pv"])
        swap = qfpy.InterestRateSwap(v["notional"], rate, mat, credit._MODEL_FREQUENCY, _side(terms))
        assert swap.npv(qfpy.MarketEnvironment(curve)) == pytest.approx(v["pv"], rel=1e-9), trade["id"]
        # la tasa efectiva es la del contrato más la base de días y el calendario: del mismo orden
        assert rate == pytest.approx(terms["fixed_rate"], rel=0.05), trade["id"]


def test_calibration_without_coupons_is_an_error(app):
    trade, v, mkt, terms = _model_swap_inputs(app)[0]
    with pytest.raises(ValueError):
        credit._effective_fixed_rate(qfpy, mkt.curves[terms["curve"]], _side(terms), 1e6, 1e-6, 0.0)


def test_simulated_swap_starts_at_the_desk_pv_without_a_step_in_the_first_month(app):
    """Auditoría del corte 6: con los términos crudos el modelo valía +2.2 M (Alfa) y −0.36 M (Beta) en t ≈ 0
    frente a un PV del desk de −0.94 M y +1.60 M. Con volatilidad despreciable la simulación es el valor
    determinista del swap del modelo: debe arrancar en el PV del desk y no saltar al mes siguiente."""
    import qfxva

    for trade, v, mkt, terms in _model_swap_inputs(app):
        name = terms["curve"]
        hw = qfpy.HullWhite(a=mkt.hw[name]["a"], sigma=1e-7, curve=mkt.curves[name])
        rate = credit._effective_fixed_rate(
            qfpy, mkt.curves[name], _side(terms), v["notional"], credit._model_maturity(trade, mkt.as_of), v["pv"]
        )
        ns = credit._netting_set(
            qfxva, [{"notional": v["notional"], "model_rate": rate, "terms": terms, "maturity_date": trade["maturity_date"]}], mkt.as_of
        )
        sim = qfxva.SimParams(n_paths=2, monitor_dates=[1e-4, 1.0 / 12.0], seed=1)
        near, month = (p.epe - p.ene for p in qfxva.simulate_exposure(hw, ns, sim, pfe_quantile=0.95))
        tol = 5e-4 * v["notional"]  # 0.05 % del nocional: a lo más un cupón diario del modelo
        assert abs(near - v["pv"]) < tol, (trade["id"], near, v["pv"])
        assert near * v["pv"] > 0.0  # mismo signo (Alfa y Gamma negativos, Beta positivo)
        # un mes después solo cambia el acarreo (<= 0.12 % del nocional aquí); el escalón de antes era de 0.5 a 3 %
        assert abs(month - v["pv"]) < 2e-3 * v["notional"], (trade["id"], month, v["pv"])


def test_same_response_on_two_calls(client):
    assert _exposure(client) == _exposure(client)  # semilla fija


def test_snapshot_is_required_and_must_exist(client):
    r = client.get("/api/credit/exposure")
    assert r.status_code == 400 and r.get_json()["field"] == "snapshot"
    r = client.get("/api/credit/exposure?snapshot=NOPE")
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"


def test_grid_helper_clips_to_the_last_day_of_the_month():
    assert credit._add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert credit._add_months(date(2026, 1, 31), 2) == date(2026, 3, 31)  # desde `as_of`, sin acumular el recorte
    assert credit._add_months(date(2026, 11, 30), 3) == date(2027, 2, 28)
    assert credit._add_months(date(2027, 11, 30), 3) == date(2028, 2, 29)
    assert credit._add_months(date(2026, 11, 10), 14) == date(2028, 1, 10)
