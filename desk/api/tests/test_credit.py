"""Corte 6, T7 (parámetros) y corte 9, T8 (exposición): EE/PFE, CVA informativo y parámetros de crédito.

La exposición de `GET /api/credit/exposure` sale del motor multimoneda de `risk/xva.py` (el de `GET /api/xva`);
las pruebas del motor anterior (conjunto por curva y por moneda, EE escalada con el spot, tasa fija efectiva,
CVA como suma de conjuntos, escalón en el primer mes) se reescribieron para el contrato de P5: un solo conjunto
`multimoneda`, `credit_source`, `hazard_rate` = −ln S(5)/5 de la curva usada y ningún escalón. Las de parámetros
(`/api/credit/params`) no cambian.
"""
import calendar
import math
import os
import re
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

import pytest

from desk.api import db, market, valuation
from desk.api import fixings as fixing_store
from desk.api.risk import credit, xva
from desk.api.tests.conftest import empty_portfolio, insert_raw_trade
from desk.api.tests.csa_fixture import set_collateral, trade_with

ALFA, BETA, GAMMA = "Banco Alfa (sintético)", "Banco Beta (sintético)", "Banco Gamma (sintético)"
DELTA = "Banco Delta (prueba)"
AS_OF = date(2026, 11, 10)  # as_of de MX-DEMO
FWD = {"side": "buy", "notional_usd": 1e6, "days": 91, "strike": 19.0}
IRS = {"curve": "TIIE-F", "side": "payer", "notional": 1e8, "periods": 13, "fixed_rate": 0.07}
ASSUMED = "Supuesto: probabilidad de incumplimiento 1 % anual y recuperación 40 % (sin parámetros capturados)"
NOT_COVERED = "El XVA solo cubre swaps de tasa y cross currency swaps: %s se excluye"
# ids sembrados (7 originales + 9 del corte 9): operaciones cubiertas y excluidas por contraparte
COVERED = {ALFA: [1, 8, 9, 10], BETA: [2, 11, 12, 13], GAMMA: [3, 14, 15, 16]}
EXCLUDED = {ALFA: {4: "fx_forward", 7: "cap_floor"}, BETA: {5: "fx_forward"}, GAMMA: {6: "fx_option"}}
CP_KEYS = {
    "counterparty", "hazard_rate", "recovery", "assumed", "assumed_note", "credit_source", "pv_mxn", "cva_mxn",
    "netting_sets", "profile", "excluded",
}
TOP_KEYS = {"snapshot", "as_of", "n_paths", "seed", "pfe_quantile", "notice", "counterparties", "excluded", "warnings"}


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


def _fast(client, n_paths=200):
    """Pocas trayectorias: las pruebas de relaciones exactas entre corridas no necesitan precisión de Monte Carlo."""
    assert client.put("/api/xva/params", json={"n_paths": n_paths}).status_code == 200


def _covered_pv(client, name):
    """Σ PV (MXN) de las operaciones cubiertas vivas de la contraparte según `GET /api/portfolio/valuation`."""
    rows = client.get("/api/portfolio/valuation?snapshot=MX-DEMO").get_json()["rows"]
    return sum(
        r["pv_mxn"] for r in rows
        if r["counterparty"] == name and r["product"] in xva.COVERED_PRODUCTS and r["status"] == "viva"
    )


def _curve(client, entity):
    body = client.get("/api/credit/curves?snapshot=MX-DEMO").get_json()
    return {c["entity"]: c for c in body["curves"]}[entity]


def _put_curve(client, entity, recovery, quotes):
    r = client.put("/api/credit/curves/%s" % quote(entity, safe=""), json={"recovery": recovery, "quotes": quotes})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _survival(curve, years):
    """S(años) = exp(−∫ h) con las intensidades por tramos de `GET /api/credit/curves` (independiente del motor)."""
    total = sum(h["hazard"] * max(0.0, min(years, h["to_years"]) - h["from_years"]) for h in curve["hazards"])
    return math.exp(-total)


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


# ------------------------------------------------------------------------ exposición (motor multimoneda)

def test_contract_shape_and_constants(client):
    body = _exposure(client)
    assert set(body) == TOP_KEYS
    assert body["snapshot"] == "MX-DEMO" and body["as_of"] == "2026-11-10"
    assert (body["n_paths"], body["seed"], body["pfe_quantile"]) == (2000, 42, 0.95)  # los de /api/xva/params
    assert body["notice"] == "CVA informativo: no entra al PV ni a la contabilidad de coberturas"
    assert [c["counterparty"] for c in body["counterparties"]] == [ALFA, BETA, GAMMA]
    assert body["warnings"] == client.get("/api/xva?snapshot=MX-DEMO").get_json()["warnings"]
    for cp in body["counterparties"]:
        assert set(cp) == CP_KEYS, cp["counterparty"]
        assert (cp["credit_source"], cp["assumed"], cp["assumed_note"]) == ("curve", False, None)
        assert cp["recovery"] == 0.4 and 0.0 < cp["hazard_rate"] < 0.05
        # un solo conjunto de compensación, multimoneda, con las operaciones cubiertas de la contraparte
        assert cp["netting_sets"] == [
            {"curve": "multimoneda", "trades": COVERED[cp["counterparty"]], "pv_mxn": cp["pv_mxn"], "cva_mxn": cp["cva_mxn"]}
        ]
        assert cp["profile"] and set(cp["profile"][0]) == {"date", "t", "ee_mxn", "pfe_mxn"}
        assert "currency" not in cp["netting_sets"][0]


def test_simulation_parameters_are_the_xva_params(client):
    assert client.put("/api/xva/params", json={"n_paths": 150, "seed": 7, "pfe_quantile": 0.9}).status_code == 200
    body = _exposure(client)
    assert (body["n_paths"], body["seed"], body["pfe_quantile"]) == (150, 7, 0.9)
    xva_body = client.get("/api/xva?snapshot=MX-DEMO").get_json()
    for cp in body["counterparties"]:  # mismo motor, mismas trayectorias: la exposición es la de /api/xva
        other = {c["counterparty"]: c for c in xva_body["counterparties"]}[cp["counterparty"]]
        assert cp["cva_mxn"] == other["cva_mxn"] and cp["pv_mxn"] == other["pv_mxn"]
        assert [(p["date"], p["ee_mxn"], p["pfe_mxn"]) for p in cp["profile"]] == [
            (p["date"], p["epe_mxn"], p["pfe_mxn"]) for p in other["profile"]
        ]


def test_ee_and_pfe_are_non_negative_and_pfe_starts_at_ee(client):
    _fast(client)
    for cp in _exposure(client)["counterparties"]:
        assert cp["profile"], cp["counterparty"]
        assert cp["profile"][0]["pfe_mxn"] == pytest.approx(cp["profile"][0]["ee_mxn"], rel=1e-9)  # hoy no hay incertidumbre
        for p in cp["profile"]:
            assert p["ee_mxn"] >= 0.0 and p["pfe_mxn"] >= 0.0


def test_ee_at_zero_is_max_pv_of_the_covered_trades_valued_by_the_desk(client):
    _fast(client)
    body = _exposure(client)
    for name in (ALFA, BETA, GAMMA):
        cp = _by_name(body)[name]
        pv = _covered_pv(client, name)
        assert cp["pv_mxn"] == pytest.approx(pv, rel=1e-9)
        first = cp["profile"][0]
        assert first["date"] == "2026-11-10" and first["t"] == 0.0
        assert first["ee_mxn"] == pytest.approx(max(pv, 0.0), rel=1e-9)
        assert pv < 0.0 and first["ee_mxn"] == 0.0  # las tres sembradas están en contra: sin exposición hoy


def test_ee_at_zero_is_the_pv_when_the_counterparty_owes_us(client):
    _fast(client)
    trade_with(client, "irs", DELTA, dict(IRS, side="receiver", fixed_rate=0.10))  # recibe 10 % con TIIE-F ~7 %: PV > 0
    cp = _by_name(_exposure(client))[DELTA]
    pv = _covered_pv(client, DELTA)
    assert pv > 1e6
    first = cp["profile"][0]
    assert first["ee_mxn"] == pytest.approx(pv, rel=1e-9) and first["pfe_mxn"] == pytest.approx(pv, rel=1e-9)
    assert cp["profile"][1]["ee_mxn"] > 0.0  # y el siguiente punto mensual parte de ahí, no de cero


def test_cva_and_pv_are_the_ones_of_the_xva_endpoint(client):
    _fast(client)
    xva_body = {c["counterparty"]: c for c in client.get("/api/xva?snapshot=MX-DEMO").get_json()["counterparties"]}
    for cp in _exposure(client)["counterparties"]:
        other = xva_body[cp["counterparty"]]
        assert cp["cva_mxn"] == other["cva_mxn"] > 0.0
        assert cp["pv_mxn"] == other["pv_mxn"]
        assert cp["excluded"] == other["excluded"]


def test_grid_is_monthly_and_reaches_the_last_maturity(client):
    _fast(client)
    body = _exposure(client)
    trades = {t["id"]: t for t in client.get("/api/trades").get_json()["trades"]}
    for name, trade_ids in COVERED.items():
        cp = _by_name(body)[name]
        dates = [p["date"] for p in cp["profile"][1:]]
        last_maturity = max(date.fromisoformat(trades[i]["maturity_date"]) for i in trade_ids)
        for k, (iso, p) in enumerate(zip(dates, cp["profile"][1:]), start=1):
            d = date.fromisoformat(iso)
            assert d == _plus_months(AS_OF, k)
            assert p["t"] == pytest.approx((d - AS_OF).days / 365.0, abs=1e-12)
        assert date.fromisoformat(dates[-1]) >= last_maturity
        assert date.fromisoformat(dates[-2]) < last_maturity  # la primera fecha que alcanza el vencimiento


def test_hazard_rate_is_the_five_year_average_of_the_curve_used(client):
    _fast(client)
    body = _exposure(client)
    for name in (ALFA, BETA, GAMMA):
        curve = _curve(client, name)
        cp = _by_name(body)[name]
        assert cp["hazard_rate"] == pytest.approx(-math.log(_survival(curve, 5.0)) / 5.0, rel=1e-9)
        assert cp["recovery"] == curve["recovery"]
    # el más débil (Beta, 150-300 pb) tiene más intensidad media que el de grado de inversión (Alfa)
    assert _by_name(body)[BETA]["hazard_rate"] > _by_name(body)[ALFA]["hazard_rate"]


def test_editing_the_curve_moves_the_cva_and_the_hazard_but_not_the_exposure(client):
    _fast(client)
    before = _by_name(_exposure(client))[ALFA]
    quotes = [{"tenor_years": q["tenor_years"], "spread": q["spread"] * 2.0} for q in _curve(client, ALFA)["quotes"]]
    _put_curve(client, ALFA, 0.25, quotes)
    after = _by_name(_exposure(client))[ALFA]
    assert after["recovery"] == 0.25 and after["credit_source"] == "curve"
    assert after["hazard_rate"] > before["hazard_rate"] * 1.5
    assert after["hazard_rate"] == pytest.approx(-math.log(_survival(_curve(client, ALFA), 5.0)) / 5.0, rel=1e-9)
    assert after["cva_mxn"] > before["cva_mxn"]
    assert after["profile"] == before["profile"] and after["pv_mxn"] == before["pv_mxn"]  # el crédito no mueve EE ni PFE


def test_a_curve_wins_over_the_flat_parameters(client):
    _fast(client)
    before = _by_name(_exposure(client))[ALFA]
    _set_params(client, ALFA, 0.5, 0.1)
    after = _by_name(_exposure(client))[ALFA]
    assert after == before and after["credit_source"] == "curve"


# ----------------------------------------------- sin curva: respaldo plano y supuesto

def test_counterparty_without_a_curve_uses_the_assumed_values(client):
    _fast(client)
    trade_with(client, "irs", DELTA, IRS)
    cp = _by_name(_exposure(client))[DELTA]
    assert (cp["credit_source"], cp["assumed"], cp["assumed_note"]) == ("flat", True, ASSUMED)
    assert cp["hazard_rate"] == pytest.approx(0.01, rel=1e-12) and cp["recovery"] == 0.4
    assert cp["cva_mxn"] > 0.0


def test_counterparty_without_a_curve_uses_its_flat_parameters(client):
    _fast(client)
    trade_with(client, "irs", DELTA, IRS)
    _set_params(client, DELTA, 0.02, 0.35)
    cp = _by_name(_exposure(client))[DELTA]
    assert (cp["credit_source"], cp["assumed"], cp["assumed_note"]) == ("flat", False, None)
    assert cp["hazard_rate"] == pytest.approx(0.02, rel=1e-12) and cp["recovery"] == 0.35


def test_zero_hazard_gives_exactly_zero_cva(client):
    _fast(client)
    trade_with(client, "irs", DELTA, IRS)
    _set_params(client, DELTA, 0.0, 0.4)
    delta = _by_name(_exposure(client))[DELTA]
    assert delta["cva_mxn"] == 0.0 and delta["hazard_rate"] == 0.0
    assert [ns["cva_mxn"] for ns in delta["netting_sets"]] == [0.0]
    assert delta["assumed"] is False and delta["assumed_note"] is None


def test_cva_grows_with_hazard_and_leaves_the_exposure_profile_alone(client):
    _fast(client)
    trade_with(client, "irs", DELTA, IRS)
    _set_params(client, DELTA, 0.01, 0.4)
    low = _by_name(_exposure(client))[DELTA]
    _set_params(client, DELTA, 0.05, 0.4)
    high = _by_name(_exposure(client))[DELTA]
    assert 0.0 < low["cva_mxn"] < high["cva_mxn"]
    assert high["profile"] == low["profile"]  # el riesgo de crédito no mueve EE ni PFE
    assert (high["hazard_rate"], high["assumed"]) == (pytest.approx(0.05, rel=1e-12), False)
    _set_params(client, DELTA, 0.05, 0.1)  # menos recuperación = más pérdida
    assert _by_name(_exposure(client))[DELTA]["cva_mxn"] > high["cva_mxn"]


# ----------------------------------------------- exclusiones y casos vacíos

def test_products_without_simulated_exposure_are_listed_as_excluded_with_the_xva_text(client):
    _fast(client)
    body = _exposure(client)
    expected = {i: p for per_cp in EXCLUDED.values() for i, p in per_cp.items()}
    top = {x["id"]: x for x in body["excluded"]}
    assert set(top) == set(expected)
    label = {"fx_forward": "Forward FX", "fx_option": "Opción FX", "cap_floor": "Cap / Floor"}
    for trade_id, product in expected.items():
        assert top[trade_id]["product"] == product and top[trade_id]["reason"] == NOT_COVERED % label[product]
        assert not re.search(r"\b(irs|fx_forward|fx_option|cap_floor)\b", top[trade_id]["reason"])  # sin códigos internos
    assert top[4]["counterparty"] == ALFA and top[7]["counterparty"] == ALFA and top[6]["counterparty"] == GAMMA
    by = _by_name(body)
    assert [x["id"] for x in by[ALFA]["excluded"]] == [4, 7]
    assert by[ALFA]["excluded"][0] == {"id": 4, "product": "fx_forward", "reason": top[4]["reason"]}
    assert [x["id"] for x in by[BETA]["excluded"]] == [5]
    assert [x["id"] for x in by[GAMMA]["excluded"]] == [6]


def test_cross_currency_swaps_are_covered_now(client):
    _fast(client)
    body = _exposure(client)
    for name, xccy_id in ((ALFA, 10), (BETA, 12), (GAMMA, 16)):
        cp = _by_name(body)[name]
        assert xccy_id in cp["netting_sets"][0]["trades"]
        assert xccy_id not in [x["id"] for x in cp["excluded"]]


def test_counterparty_without_covered_trades_has_an_empty_profile(client):
    _fast(client)
    trade_with(client, "fx_forward", DELTA, FWD)
    delta = _by_name(_exposure(client))[DELTA]
    assert (delta["netting_sets"], delta["profile"], delta["pv_mxn"], delta["cva_mxn"]) == ([], [], 0.0, 0.0)
    assert [x["product"] for x in delta["excluded"]] == ["fx_forward"]
    assert delta["assumed"] is True  # aunque no se simule nada, se le muestran los supuestos


def test_terminated_swap_leaves_the_counterparty_with_only_its_excluded_trades(client):
    _fast(client)
    swap = trade_with(client, "irs", DELTA, IRS)["id"]
    trade_with(client, "fx_forward", DELTA, FWD)
    r = client.post(
        "/api/trades/%d/events" % swap, json={"type": "termination", "event_date": "2026-11-10", "data": {"amount": 1000.0}}
    )
    assert r.status_code == 201, r.get_json()
    delta = _by_name(_exposure(client))[DELTA]
    assert delta["netting_sets"] == [] and delta["profile"] == [] and delta["pv_mxn"] == 0.0
    assert [x["product"] for x in delta["excluded"]] == ["fx_forward"]  # el swap terminado no es ni cubierto ni excluido


def test_counterparties_without_live_trades_do_not_appear(client):
    empty_portfolio(client)
    body = _exposure(client)
    assert body["counterparties"] == [] and body["excluded"] == [] and body["warnings"] == []


def test_unreadable_swap_is_excluded_with_its_reason_and_does_not_stop_the_rest(app, client):
    _fast(client)
    insert_raw_trade(app, "irs", "no es json")
    body = _exposure(client)
    raw = _by_name(body)["Raw"]
    assert raw["netting_sets"] == [] and raw["profile"] == []
    assert len(raw["excluded"]) == 1 and raw["excluded"][0]["product"] == "irs"
    assert raw["excluded"][0]["reason"].startswith("No se pudo valuar: ")
    assert _by_name(body)[BETA]["profile"]  # las demás se calculan igual


# ----------------------------------------------- compensación entre monedas y sin escalón

def test_cross_currency_netting_costs_less_than_the_parts(client):
    """Un mismo conjunto con un swap MXN y uno USD (pagador de TIIE-F y receptor de SOFR, correlacionadas) tiene
    menos CVA que los dos swaps en contrapartes separadas con el mismo crédito: las mismas trayectorias, así que
    es subaditividad exacta de max(·, 0), no una cuestión de ruido."""
    _fast(client)
    mxn = dict(IRS)
    usd = {"curve": "SOFR", "side": "receiver", "notional": 5.4e6, "periods": 13, "fixed_rate": 0.04}
    trade_with(client, "irs", "Banco Eco (prueba)", mxn)
    trade_with(client, "irs", "Banco Foxtrot (prueba)", usd)
    trade_with(client, "irs", DELTA, mxn)
    trade_with(client, "irs", DELTA, usd)
    by = _by_name(_exposure(client))
    joint, parts = by[DELTA]["cva_mxn"], by["Banco Eco (prueba)"]["cva_mxn"] + by["Banco Foxtrot (prueba)"]["cva_mxn"]
    assert 0.0 < joint < parts
    assert by[DELTA]["netting_sets"][0]["curve"] == "multimoneda" and len(by[DELTA]["netting_sets"][0]["trades"]) == 2


def test_no_step_after_the_first_day_when_there_is_no_volatility(app):
    """Auditoría del corte 6: el motor anterior valía el PV del desk en t = 0 y caía de golpe hasta un cupón diario
    un instante después (−86 mil MXN en Alfa, 0.017 % de su nocional de 500 M). Con volatilidad cero el motor nuevo
    es determinista y el valor del primer día difiere del de t = 0 solo por el acarreo de un día: aquí queda en
    ≈ 0.00005 % del nocional (783 MXN en Alfa), y la cota de 0.001 % deja fuera al escalón anterior."""
    from desk.api.qf import qfpy  # noqa: F401  (debe cargarse antes que qfxva)
    import qfxva

    conn = db.connect(app.config["DESK_DB"])
    try:
        mkt = market.load_context(conn, "MX-DEMO")
        fixings = fixing_store.load_all(conn)
        model = qfxva.ExposureModel(
            a_mxn=0.05, sigma_mxn=0.0, a_usd=0.03, sigma_usd=0.0, fx_vol=0.0, rho_mxn_usd=0.0, rho_mxn_fx=0.0, rho_usd_fx=0.0
        )
        by_name = xva.live_by_counterparty(conn, mkt)
        assert sorted(by_name) == [ALFA, BETA, GAMMA]
        for name, trades in by_name.items():
            spec, included, _, _ = xva.build_set(trades, mkt, fixings)
            ids = {i["id"] for i in included}
            notional_mxn = 0.0
            for trade in trades:
                if trade["id"] in ids:
                    v = valuation.value_trade(trade, mkt, fixings)
                    notional_mxn += v["notional"] * (mkt.spot if v["currency"] == "USD" else 1.0)
            profile = xva.engine(mkt, model, dict(xva.DEFAULTS, n_paths=100), [0, 1]).simulate([spec])[0]
            assert profile.value_at_zero == pytest.approx(sum(i["pv_mxn"] for i in included), rel=1e-9)  # arranca en el PV del desk
            step = abs(profile.expected_value[1] - profile.expected_value[0])
            assert step < 1e-5 * notional_mxn, (name, step, notional_mxn)
    finally:
        conn.close()


# ----------------------------------------------- estructura

def test_same_response_on_two_calls(client):
    _fast(client)
    assert _exposure(client) == _exposure(client)  # semilla fija


def test_snapshot_is_required_and_must_exist(client):
    r = client.get("/api/credit/exposure")
    assert r.status_code == 400 and r.get_json()["field"] == "snapshot"
    r = client.get("/api/credit/exposure?snapshot=NOPE")
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"


def test_the_motor_anterior_is_gone_from_the_desk():
    root = Path(credit.__file__).resolve().parents[1]
    for name in ("_effective_fixed_rate", "_MODEL_FREQUENCY", "_netting_set", "_model_maturity", "N_PATHS", "COVERED_PRODUCTS"):
        assert not hasattr(credit, name), name
    for path in root.rglob("*.py"):
        if "tests" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        assert "CVACalculator" not in source and "_effective_fixed_rate" not in source, path
        assert not re.search(r"\bNettingSet\b", source), path  # NettingSetSpec (el motor nuevo) sí


@pytest.mark.parametrize("module", ["desk.api.risk.credit", "desk.api.risk.xva"])
def test_each_module_imports_alone_without_a_cycle(module):
    root = Path(__file__).resolve().parents[3]
    r = subprocess.run(
        [sys.executable, "-c", "import %s" % module], cwd=str(root), env=dict(os.environ, PYTHONPATH=str(root)),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
    )
    assert r.returncode == 0, r.stderr


def test_grid_helper_clips_to_the_last_day_of_the_month():
    assert credit._add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert credit._add_months(date(2026, 1, 31), 2) == date(2026, 3, 31)  # desde `as_of`, sin acumular el recorte
    assert credit._add_months(date(2026, 11, 30), 3) == date(2027, 2, 28)
    assert credit._add_months(date(2027, 11, 30), 3) == date(2028, 2, 29)
    assert credit._add_months(date(2026, 11, 10), 14) == date(2028, 1, 10)
