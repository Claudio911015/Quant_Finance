import json
import re
from collections import Counter

import pytest

from desk.api import market, portfolio, valuation
from desk.api.pricing import PRODUCTS
from desk.api.validation import has_non_finite
from desk.validation import common, export_cases

EXPECTED_COUNTS = {
    "irs": 12, "fx_forward": 8, "fx_option": 10, "equity_option": 8,
    "bond": 8, "cap_floor": 8, "swaption": 8,
}
ID_PATTERN = re.compile(r"^(%s)-\d\d$" % "|".join(common.PRODUCTS))
# Palabra en español que debe llevar el rótulo de cada producto (la de su plantilla), singular o plural.
LABEL_WORD = {
    "irs": r"periodos? de", "fx_forward": "días", "fx_option": "días", "equity_option": "días",
    "bond": r"cup(ón|ones) cada", "cap_floor": r"periodos?", "swaption": "días",
}


@pytest.fixture(scope="module")
def env():
    conn = export_cases.demo_conn()
    try:
        mkt = market.load_context(conn, common.SNAPSHOT_ID)
        cases = export_cases.build_cases(conn, mkt)
        trades = portfolio.load_trades(conn)
        return mkt, cases, trades
    finally:
        conn.close()


@pytest.fixture(scope="module")
def mkt(env):
    return env[0]


@pytest.fixture(scope="module")
def cases(env):
    return env[1]


@pytest.fixture(scope="module")
def by_id(cases):
    return {c["id"]: c for c in cases}


def test_hay_62_casos_con_ids_unicos_y_numerados_por_producto(cases):
    assert len(cases) == 62 >= common.MIN_CASES
    ids = [c["id"] for c in cases]
    assert len(set(ids)) == len(ids)
    assert all(ID_PATTERN.match(i) for i in ids)
    for product in common.PRODUCTS:
        mine = [c["id"] for c in cases if c["product"] == product]
        assert mine == ["%s-%02d" % (product, n) for n in range(1, len(mine) + 1)]


def test_conteo_por_producto_exacto(cases):
    counts = Counter(c["product"] for c in cases)
    assert dict(counts) == EXPECTED_COUNTS
    assert all(n >= common.MIN_CASES_PER_PRODUCT for n in counts.values())
    assert list(dict.fromkeys(c["product"] for c in cases)) == list(common.PRODUCTS)


def test_siete_casos_de_portafolio_con_trade_id_1_a_7_y_primeros_de_su_producto(env):
    mkt, cases, trades = env
    portfolio_cases = [c for c in cases if c["source"] == "portfolio"]
    assert sorted(c["trade_id"] for c in portfolio_cases) == list(range(1, 8))
    assert {c["id"]: c["trade_id"] for c in portfolio_cases} == {
        "irs-01": 1, "irs-02": 2, "irs-03": 3, "fx_forward-01": 4, "fx_forward-02": 5,
        "fx_option-01": 6, "cap_floor-01": 7,
    }
    for c in cases:
        if c["source"] == "battery":
            assert c["trade_id"] is None
    for trade in trades:
        case = next(c for c in portfolio_cases if c["trade_id"] == trade["id"])
        assert case["product"] == trade["product"]
        assert case["params"] == PRODUCTS[trade["product"]].validate(trade["params"])
        assert case["pv_desk"] == valuation.value_trade(trade, mkt)["pv"]


def test_pv_desk_coincide_con_el_pricer(cases, mkt):
    # Los de portafolio salen de `value_trade`: aquí se prueba que su camino y el del pricer coinciden.
    for c in cases:
        pv = PRODUCTS[c["product"]].price(c["params"], mkt)["pv"]
        assert abs(c["pv_desk"] - pv) <= 1e-9 * c["notional"], c["id"]


def test_irs_siempre_con_fixed_rate_numerico_y_a_la_par_en_04_y_10(by_id, cases, mkt):
    for c in cases:
        if c["product"] == "irs":
            assert isinstance(c["params"]["fixed_rate"], float), c["id"]
    for case_id in ("irs-04", "irs-10"):
        c = by_id[case_id]
        par = PRODUCTS["irs"].price(dict(c["params"], fixed_rate=None), mkt)["risk"]["par_rate"]
        assert c["params"]["fixed_rate"] == par
        assert c["label"].endswith("(a la par)")
        assert abs(c["pv_desk"]) <= 1e-9 * c["notional"]
    assert not any(c["label"].endswith("(a la par)") for c in cases if c["id"] not in ("irs-04", "irs-10"))


def test_nocional_y_moneda_segun_la_regla(cases, by_id, mkt):
    for c in cases:
        p, product = c["params"], c["product"]
        if product in ("irs", "cap_floor", "swaption"):
            assert (c["notional"], c["currency"]) == (p["notional"], market.CURVES[p["curve"]]["currency"])
        elif product == "bond":
            assert (c["notional"], c["currency"]) == (p["face"], market.CURVES[p["curve"]]["currency"])
        elif product in ("fx_forward", "fx_option"):
            assert (c["notional"], c["currency"]) == (p["notional_usd"] * mkt.spot, "MXN")
        else:
            assert (c["notional"], c["currency"]) == (p["quantity"] * p["spot"], "MXN")
        assert c["notional"] > 0
    assert (by_id["fx_forward-03"]["notional"], by_id["fx_forward-03"]["currency"]) == (5e6 * 18.6, "MXN")
    assert by_id["irs-09"]["currency"] == "USD"
    assert by_id["bond-05"]["currency"] == "USD" and by_id["bond-01"]["currency"] == "MXN"


def test_inputs_de_cada_producto(cases, mkt):
    for c in cases:
        i, p = c["inputs"], c["params"]
        if c["product"] == "irs":
            pd = market.CURVES[p["curve"]]["period_days"]
            assert i["period_days"] == pd
            assert i["payment_days"] == [pd * k for k in range(1, p["periods"] + 1)]
        elif c["product"] == "fx_forward":
            assert i["spot"] == mkt.spot and i["forward"] > 0
        elif c["product"] == "fx_option":
            assert i["spot"] == mkt.spot and i["forward"] > 0
            assert i["vol"] > 0, c["id"]
        elif c["product"] == "equity_option":
            assert i == {"days": round(p["maturity_years"] * 365)}
        elif c["product"] == "bond":
            assert len(i["schedule"]) == p["periods"]
            assert all(set(x) == {"t", "amount"} for x in i["schedule"])
            assert i["schedule"][-1]["amount"] >= p["face"]  # el principal va en el último flujo
        elif c["product"] == "cap_floor":
            hw = mkt.hw[p["curve"]]
            assert i == {"period_days": market.CURVES[p["curve"]]["period_days"],
                         "hw_a": hw["a"], "hw_sigma": hw["sigma"]}
        else:
            hw = mkt.hw[p["curve"]]
            pd = market.CURVES[p["curve"]]["period_days"]
            assert i == {"period_days": pd, "payments": round(p["swap_tenor_years"] * 365 / pd),
                         "hw_a": hw["a"], "hw_sigma": hw["sigma"]}


def test_la_bateria_transcribe_la_tabla(by_id, mkt):
    # Una muestra de la tabla fija del plan: si alguien la toca, esta prueba lo nota.
    assert by_id["bond-08"]["params"]["frequency"] == 2.0  # frecuencia por omisión del desk
    assert by_id["bond-02"]["params"]["frequency"] == 365.0 / 182
    assert by_id["bond-04"]["params"] == {
        "curve": "TIIE-F", "face": 10e6, "coupon_rate": 0.10, "periods": 13, "frequency": 365.0 / 28}
    assert by_id["equity_option-08"]["params"] == {
        "option_type": "put", "spot": 250.0, "strike": 262.5, "volatility": 0.18, "rate": 0.10,
        "dividend_yield": 0.0, "maturity_years": 365 / 365.0, "quantity": 50.0}
    assert by_id["swaption-08"]["params"] == {
        "curve": "SOFR", "swaption_type": "payer", "notional": 10e6, "strike": 0.040,
        "expiry_years": 1825 / 365.0, "swap_tenor_years": 5.0}
    assert by_id["fx_option-09"]["params"] == {
        "side": "sell", "option_type": "put", "notional_usd": 2e6, "days": 91, "strike": 18.85}
    assert by_id["fx_forward-08"]["params"] == {"side": "sell", "notional_usd": 3e6, "days": 7, "strike": 18.62}
    assert by_id["cap_floor-07"]["params"] == {
        "curve": "SOFR", "cap_type": "floor", "notional": 20e6, "periods": 3, "strike": 0.035}
    assert by_id["irs-12"]["params"] == {
        "curve": "SOFR", "side": "payer", "notional": 40e6, "periods": 10, "fixed_rate": 0.0420}


def test_ningun_caso_pasa_del_ultimo_pilar_de_su_curva(cases, mkt):
    for c in cases:
        p, i = c["params"], c["inputs"]
        if c["product"] in ("irs", "cap_floor", "bond", "swaption"):
            pd = market.CURVES[p["curve"]]["period_days"]
            if c["product"] == "bond":
                horizon = p["periods"] / p["frequency"] * 365
            elif c["product"] == "swaption":
                horizon = (p["expiry_years"] + p["swap_tenor_years"]) * 365
            else:
                horizon = p["periods"] * pd
            limit = mkt.pillars[p["curve"]][-1]["days"]
        elif c["product"] in ("fx_forward", "fx_option"):
            horizon, limit = p["days"], min(mkt.pillars[n][-1]["days"] for n in market.CURVES)
        else:
            continue  # la opción sobre acción no usa las curvas del desk
        assert horizon <= limit + 1e-6, c["id"]


def test_rotulos_no_vacios_y_en_espanol(cases):
    for c in cases:
        assert c["label"].strip(), c["id"]
        assert re.search(LABEL_WORD[c["product"]], c["label"]), c["id"]
        if c["source"] == "portfolio":
            assert c["label"].endswith(" · portafolio #%d" % c["trade_id"]), c["id"]
        else:
            assert "portafolio" not in c["label"], c["id"]
    labels = {c["id"]: c["label"] for c in cases}
    assert labels["irs-01"] == "Paga fija TIIE-F · 26 periodos de 28 días · fija 6.8000 % · portafolio #1"
    assert labels["fx_option-02"] == "Compra call USD 2,000,000 a 30 días · strike 18.6000"
    assert labels["bond-08"] == "Bono TIIE-F · cupón 7.50 % · 6 cupones cada 182.5 días"
    assert labels["bond-02"] == "Bono TIIE-F · cupón 7.00 % · 20 cupones cada 182 días"


def test_los_rotulos_concuerdan_en_numero_con_la_cantidad(cases):
    labels = {c["id"]: c["label"] for c in cases}
    # Cantidad 1 → singular (antes salía «1 periodos», «1 cupones», «1 años»).
    assert labels["irs-06"] == "Paga fija TIIE-F · 1 periodo de 28 días · fija 6.5000 %"
    assert labels["irs-09"] == "Recibe fija SOFR · 1 periodo de 365 días · fija 3.8000 %"
    assert labels["bond-03"] == "Bono TIIE-F · cupón 0.00 % · 1 cupón cada 365 días"
    assert labels["swaption-04"] == "Receptora TIIE-F · expira en 182 días · swap de 1 año · strike 6.50 %"
    # Cantidad > 1 → plural.
    assert labels["swaption-01"] == "Pagadora TIIE-F · expira en 365 días · swap de 2 años · strike 7.00 %"
    assert labels["cap_floor-02"] == "Cap TIIE-F · 13 periodos · strike 7.00 %"
    # Ningún rótulo conserva la concordancia errónea.
    for cid, label in labels.items():
        assert not re.search(r"(?<![\d.])1 (periodos|cupones|años)\b", label), cid


def test_el_documento_es_serializable_y_sin_no_finitos(cases):
    assert not has_non_finite(cases)
    assert json.loads(json.dumps(cases, allow_nan=False)) == cases


def test_build_incluye_los_62_casos_junto_a_las_curvas():
    doc = export_cases.build()
    assert len(doc["cases"]) == 62
    assert list(doc["curves"]) == ["TIIE-F", "SOFR"]
    assert not has_non_finite(doc)
