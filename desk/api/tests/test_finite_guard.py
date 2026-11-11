"""Guarda contra no finitos (M1, B1, B2): ningún endpoint responde 200 con NaN/Infinity en el JSON.

Dos capas: las cotas de entrada (horizon_days, factor_vols, frequency) rechazan lo absurdo con su
`field`, y una guarda central en las respuestas de pricers, valuación, DV01, escenarios y VaR
convierte cualquier no finito que se cuele en un 400 con la forma habitual `{error, field}`.
La valuación del portafolio es la excepción: una fila no finita va a su propio `error`.
"""
import json
from typing import Any

import pytest

from desk.api import portfolio
from desk.api.pricing import PRODUCTS
from desk.api.risk import dv01, scenarios, var
from desk.api.tests.test_errors import SNAP, SPECS
from desk.api.validation import has_non_finite

NON_FINITE_BODY = {"error": "El cálculo produjo un valor no finito con esos parámetros", "field": None}

FWD = SPECS["fx_forward"]["base"]
EQ = SPECS["equity_option"]["base"]
BOND = SPECS["bond"]["base"]
VAR_OK = {"snapshot": SNAP, "horizon_days": 1, "confidence": 0.99}
SCN_OK = {"snapshot": SNAP, "scenarios": [{"name": "p", "type": "parallel", "curve": "TIIE-F", "bp": 10}]}


def _strict(resp) -> Any:
    """Decodifica el cuerpo crudo rechazando NaN/Infinity (un navegador no los parsea)."""
    text = resp.get_data(as_text=True)

    def reject(token):
        raise AssertionError("JSON inválido, contiene %s: %s" % (token, text[:200]))

    return json.loads(text, parse_constant=reject)


def _var(client, **over):
    return client.post("/api/risk/var", json={**VAR_OK, **over})


def _assert_400(resp, field: Any):
    assert resp.status_code == 400, resp.get_data(as_text=True)[:300]
    body = _strict(resp)
    assert set(body) == {"error", "field"} and body["error"], body
    assert body["field"] == field, body


def _assert_non_finite_400(resp):
    assert resp.status_code == 400, resp.get_data(as_text=True)[:300]
    assert _strict(resp) == NON_FINITE_BODY


# --------------------------------------------------------------------------- has_non_finite

@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_has_non_finite_encuentra_el_valor_a_cualquier_profundidad(bad):
    assert has_non_finite(bad)
    assert has_non_finite({"a": 1, "b": [{"c": (2, {"d": [bad]})}]})
    assert has_non_finite([[[[[bad]]]]])


@pytest.mark.parametrize(
    "ok",
    [0.0, -1e308, 1e308, 5, 10 ** 400, True, None, "NaN", "inf", [], {}, {"a": [1.5, {"b": None}]}],
)
def test_has_non_finite_no_confunde_valores_finitos(ok):
    assert not has_non_finite(ok)


# --------------------------------------------------------------------------- M1: cotas de /api/risk/var

def test_m1_reproduccion_del_informe_ahora_da_400_con_el_campo(client):
    """USDMXN=1e300 daba 200 con `var_mxn: Infinity` y `NaN`."""
    _assert_400(_var(client, factor_vols={"USDMXN": 1e300}), "factor_vols")


def test_m1_las_tres_vols_en_1e308_dan_400(client):
    _assert_400(_var(client, factor_vols={"TIIE-F": 1e308, "SOFR": 1e308, "USDMXN": 1e308}), "factor_vols")


@pytest.mark.parametrize("v", [1e300, 1e308, 10 ** 6, 3651])
def test_m1_horizon_days_absurdo_da_400_con_el_campo(client, v):
    _assert_400(_var(client, horizon_days=v), "horizon_days")


def test_horizon_days_en_la_cota_se_acepta_y_justo_arriba_no(client):
    r = _var(client, horizon_days=3650)
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    assert not has_non_finite(_strict(r))
    _assert_400(_var(client, horizon_days=3650 * (1 + 1e-9)), "horizon_days")
    _assert_400(_var(client, horizon_days=3650.5), "horizon_days")


# factor: (cota inclusiva). TIIE-F y SOFR están en puntos base; USDMXN es una fracción.
VOL_CAPS = [("TIIE-F", 1000.0), ("SOFR", 1000.0), ("USDMXN", 1.0)]


@pytest.mark.parametrize("factor,cap", VOL_CAPS)
def test_factor_vols_en_la_cota_se_acepta_y_justo_arriba_no(client, factor, cap):
    r = _var(client, factor_vols={factor: cap})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    assert not has_non_finite(_strict(r))
    for above in (cap * (1 + 1e-9), cap + 0.5, cap * 10):
        _assert_400(_var(client, factor_vols={factor: above}), "factor_vols")


def test_todas_las_cotas_a_la_vez_dan_200_con_json_finito(client):
    r = _var(client, horizon_days=3650, factor_vols=dict(VOL_CAPS))
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    body = _strict(r)
    assert not has_non_finite(body)
    assert body["var_mxn"] > 0


def test_una_vol_buena_y_una_fuera_de_cota_dan_400(client):
    _assert_400(_var(client, factor_vols={"TIIE-F": 4.0, "USDMXN": 1.5}), "factor_vols")


# --------------------------------------------------------------------------- B1: equity_option extremo

B1_CASES = {
    "spot y vol 1e-300": {"spot": 1e-300, "strike": 100, "volatility": 1e-300, "rate": 0.07,
                          "dividend_yield": 0, "maturity_years": 1},
    "vol y vencimiento 1e-300": {"spot": 55, "strike": 55, "volatility": 1e-300, "rate": 0.07,
                                 "dividend_yield": 0, "maturity_years": 1e-300},
}


@pytest.mark.parametrize("params", list(B1_CASES.values()), ids=list(B1_CASES))
def test_b1_equity_option_extremo_da_400_no_200_con_nan(client, params):
    r = client.post("/api/price/equity_option", json={"snapshot": SNAP, "option_type": "call", **params})
    _assert_non_finite_400(r)


def test_b1_el_mismo_caso_como_operacion_se_guarda_pero_la_valuacion_sigue_finita(client):
    """Guardar la operación es legítimo (los parámetros son válidos); la valuación no se rompe."""
    params = {"option_type": "call", **B1_CASES["spot y vol 1e-300"]}
    r = client.post("/api/trades", json={"product": "equity_option", "counterparty": "Banco Test",
                                          "params": params})
    assert r.status_code == 201, r.get_data(as_text=True)[:300]
    v = client.get("/api/portfolio/valuation?snapshot=%s" % SNAP)
    assert v.status_code == 200
    assert not has_non_finite(_strict(v))


# --------------------------------------------------------------------------- B2: bond.frequency

def test_b2_frequency_absurda_da_400_con_el_campo(client):
    for v in (1e300, 1e6, 366):
        r = client.post("/api/price/bond", json={"snapshot": SNAP, **BOND, "frequency": v})
        _assert_400(r, "frequency")


def test_b2_frequency_en_la_cota_valua_y_justo_arriba_no(client):
    r = client.post("/api/price/bond", json={"snapshot": SNAP, **BOND, "frequency": 365})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    assert not has_non_finite(_strict(r))
    r = client.post("/api/price/bond", json={"snapshot": SNAP, **BOND, "frequency": 365 * (1 + 1e-9)})
    _assert_400(r, "frequency")


def test_b2_la_cota_aplica_tambien_al_guardar_la_operacion(client):
    r = client.post("/api/trades", json={"product": "bond", "counterparty": "Banco Test",
                                          "params": {**BOND, "frequency": 1e300}})
    _assert_400(r, "frequency")


# --------------------------------------------------------------------------- guarda central: cableado

NASTY = [float("nan"), float("inf"), float("-inf")]


def _deep(bad: float) -> dict:
    return {"pv": 1.0, "details": {"filas": [{"ok": 1.0, "cola": (2.0, [bad])}]}}


def _patch_price(monkeypatch, payload):
    monkeypatch.setitem(PRODUCTS, "fx_forward", PRODUCTS["fx_forward"]._replace(price=lambda p, m: payload))
    return ("post", "/api/price/fx_forward", {"snapshot": SNAP, **FWD})


def _patch_valuation(monkeypatch, payload):
    monkeypatch.setattr(portfolio, "valuation", lambda conn, snap: payload)
    return ("get", "/api/portfolio/valuation?snapshot=%s" % SNAP, None)


def _patch_dv01(monkeypatch, payload):
    monkeypatch.setattr(dv01, "compute_dv01", lambda conn, snap: payload)
    return ("post", "/api/risk/dv01", {"snapshot": SNAP})


def _patch_scenarios(monkeypatch, payload):
    monkeypatch.setattr(scenarios, "run_scenarios", lambda conn, snap, body: payload)
    return ("post", "/api/risk/scenarios", SCN_OK)


def _patch_var(monkeypatch, payload):
    monkeypatch.setattr(var, "compute_var", lambda conn, snap, body: payload)
    return ("post", "/api/risk/var", VAR_OK)


ROUTES = [_patch_price, _patch_valuation, _patch_dv01, _patch_scenarios, _patch_var]


def _call(client, spec):
    method, url, body = spec
    return client.get(url) if method == "get" else client.post(url, json=body)


@pytest.mark.parametrize("bad", NASTY, ids=["nan", "inf", "-inf"])
@pytest.mark.parametrize("patch", ROUTES, ids=[p.__name__[7:] for p in ROUTES])
def test_la_guarda_central_convierte_un_no_finito_en_400_en_cada_respuesta(client, monkeypatch, patch, bad):
    spec = patch(monkeypatch, _deep(bad))
    _assert_non_finite_400(_call(client, spec))


@pytest.mark.parametrize("patch", ROUTES, ids=[p.__name__[7:] for p in ROUTES])
def test_la_guarda_central_deja_pasar_una_respuesta_finita_intacta(client, monkeypatch, patch):
    payload = _deep(1.5)
    r = _call(client, patch(monkeypatch, payload))
    assert r.status_code in (200, 201), r.get_data(as_text=True)[:300]
    assert _strict(r) == json.loads(json.dumps(payload))


# --------------------------------------------------------------------------- guarda central: de punta a punta

MARK = 123456.0  # notional_usd que identifica la operación que "desborda" en estas pruebas


def _poison_fx_forward(monkeypatch, bad: float):
    """`fx_forward` con notional MARK valúa a `bad`; el resto de operaciones valúa normal."""
    original = PRODUCTS["fx_forward"]

    def pv_mxn(params, mkt):
        return bad if params["notional_usd"] == MARK else original.pv_mxn(params, mkt)

    monkeypatch.setitem(PRODUCTS, "fx_forward", original._replace(pv_mxn=pv_mxn))


def _add_poisoned_trade(client):
    r = client.post("/api/trades", json={"product": "fx_forward", "counterparty": "Banco Test",
                                          "params": {**FWD, "notional_usd": MARK}})
    assert r.status_code == 201, r.get_data(as_text=True)[:300]
    return r.get_json()["id"]


@pytest.mark.parametrize("bad", NASTY, ids=["nan", "inf", "-inf"])
def test_valuacion_una_fila_no_finita_va_a_su_error_y_el_resto_se_valua(client, monkeypatch, bad):
    clean = _strict(client.get("/api/portfolio/valuation?snapshot=%s" % SNAP))
    trade_id = _add_poisoned_trade(client)
    _poison_fx_forward(monkeypatch, bad)

    r = client.get("/api/portfolio/valuation?snapshot=%s" % SNAP)
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    body = _strict(r)
    rows = {row["id"]: row for row in body["rows"]}
    assert len(rows) == len(clean["rows"]) + 1
    row = rows[trade_id]
    assert row["error"] == NON_FINITE_BODY["error"]
    assert row["pv"] is None and row["pv_mxn"] is None
    others = [x for i, x in rows.items() if i != trade_id]
    assert all(x["error"] is None and x["pv_mxn"] is not None for x in others)
    assert body["total_mxn"] == pytest.approx(clean["total_mxn"])
    assert body["total_mxn"] == pytest.approx(sum(x["pv_mxn"] for x in others))


@pytest.mark.parametrize("endpoint,body", [
    ("/api/risk/dv01", {"snapshot": SNAP}),
    ("/api/risk/scenarios", SCN_OK),
    ("/api/risk/var", VAR_OK),
])
@pytest.mark.parametrize("bad", [float("nan"), float("inf")], ids=["nan", "inf"])
def test_riesgo_una_valuacion_no_finita_da_400_y_no_json_invalido(client, monkeypatch, endpoint, body, bad):
    _add_poisoned_trade(client)
    _poison_fx_forward(monkeypatch, bad)
    _assert_non_finite_400(client.post(endpoint, json=body))


# --------------------------------------------------------------------------- lo razonable sigue dando 200

REASONABLE = [
    ("post", "/api/risk/var", VAR_OK),
    ("post", "/api/risk/var", {**VAR_OK, "horizon_days": 10, "confidence": 0.95,
                               "factor_vols": {"TIIE-F": 6.0, "SOFR": 5.0, "USDMXN": 0.01}}),
    ("post", "/api/risk/dv01", {"snapshot": SNAP}),
    ("post", "/api/risk/scenarios", SCN_OK),
    ("post", "/api/risk/scenarios", {"snapshot": SNAP, "scenarios": [
        {"name": "fx", "type": "fx_spot", "pct": 10}, {"name": "st", "type": "steepener", "curve": "SOFR", "bp": 25}]}),
    ("get", "/api/portfolio/valuation?snapshot=%s" % SNAP, None),
    ("post", "/api/price/equity_option", {"snapshot": SNAP, **EQ}),
    ("post", "/api/price/bond", {"snapshot": SNAP, **BOND}),
    ("post", "/api/price/bond", {"snapshot": SNAP, **BOND, "frequency": 4}),
    ("post", "/api/price/fx_option", {"snapshot": SNAP, **SPECS["fx_option"]["base"]}),
]


@pytest.mark.parametrize("method,url,body", REASONABLE, ids=["%s %s #%d" % (m, u.split("?")[0], i)
                                                             for i, (m, u, _) in enumerate(REASONABLE)])
def test_valores_razonables_siguen_dando_200_con_json_finito(client, method, url, body):
    r = _call(client, (method, url, body))
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    assert not has_non_finite(_strict(r))
