"""Barrido de errores por endpoint (R5): ninguna entrada inválida produce 500.

Cada caso envía una petición mal formada al endpoint y exige un 400/404 con cuerpo JSON
`{"error": str, "field": ...}`. Donde la causa es un parámetro concreto se exige además que
`field` sea su nombre. El barrido comparte una sola app: todo caso se rechaza antes de
escribir, así que no se contaminan entre sí.
"""
import json
from typing import Any, Dict, List, Optional

import pytest

from desk.api.pricing import PRODUCTS

SNAP = "MX-DEMO"
ANY = object()  # el caso no fija el nombre del campo culpable

# --------------------------------------------------------------------------- especificación

# Por producto: cuerpo válido (sin snapshot) y qué admite cada campo.
#   req   obligatorios para /api/price (faltar o ir en null → 400 con su nombre)
#   gt0   números > 0            ge0   números >= 0       free  números sin cota
#   int1  enteros >= 1           choice  cadenas de un conjunto
#   cap   cota superior inclusiva; el valor justo arriba se rechaza
SPECS: Dict[str, Dict[str, Any]] = {
    "irs": {
        "base": {"curve": "TIIE-F", "side": "payer", "notional": 1e8, "periods": 13, "fixed_rate": 0.07},
        "req": ["curve", "side", "notional", "periods"],
        "gt0": ["notional"], "ge0": [], "free": ["fixed_rate"], "int1": ["periods"],
        "choice": ["curve", "side"], "cap": {"periods": 1200},
    },
    "cap_floor": {
        "base": {"curve": "TIIE-F", "cap_type": "cap", "notional": 1e8, "strike": 0.07, "periods": 13},
        "req": ["curve", "cap_type", "notional", "strike", "periods"],
        "gt0": ["notional", "strike"], "ge0": [], "free": [], "int1": ["periods"],
        "choice": ["curve", "cap_type"], "cap": {"periods": 1200},
    },
    "swaption": {
        "base": {"curve": "TIIE-F", "swaption_type": "payer", "notional": 1e8, "strike": 0.07,
                 "expiry_years": 1.0, "swap_tenor_years": 2.0},
        "req": ["curve", "swaption_type", "notional", "strike", "expiry_years", "swap_tenor_years"],
        "gt0": ["notional", "strike", "expiry_years", "swap_tenor_years"], "ge0": [], "free": [],
        "int1": [], "choice": ["curve", "swaption_type"],
        "cap": {"expiry_years": 50, "swap_tenor_years": 50},
    },
    "bond": {
        "base": {"curve": "TIIE-F", "face": 1e6, "coupon_rate": 0.07, "periods": 10, "frequency": 2.0},
        "req": ["face", "coupon_rate", "periods"],
        "gt0": ["face", "frequency"], "ge0": ["coupon_rate"], "free": [], "int1": ["periods"],
        "choice": ["curve"], "cap": {"periods": 1200},
    },
    "fx_forward": {
        "base": {"side": "buy", "notional_usd": 1e6, "strike": 19.0, "days": 91},
        "req": ["side", "notional_usd", "strike", "days"],
        "gt0": ["notional_usd", "strike"], "ge0": [], "free": [], "int1": ["days"],
        "choice": ["side"], "cap": {"days": 18250},
    },
    "fx_option": {
        "base": {"side": "buy", "option_type": "call", "notional_usd": 1e6, "strike": 19.0, "days": 91},
        "req": ["side", "option_type", "notional_usd", "strike", "days"],
        "gt0": ["notional_usd", "strike"], "ge0": [], "free": [], "int1": ["days"],
        "choice": ["side", "option_type"], "cap": {"days": 18250},
    },
    "equity_option": {
        "base": {"option_type": "call", "spot": 55.0, "strike": 55.0, "volatility": 0.25, "rate": 0.07,
                 "dividend_yield": 0.02, "maturity_years": 1.0, "quantity": 1000.0},
        "req": ["option_type", "spot", "strike", "volatility", "rate", "dividend_yield", "maturity_years"],
        "gt0": ["spot", "strike", "volatility", "maturity_years", "quantity"],
        "ge0": ["dividend_yield"], "free": ["rate"], "int1": [], "choice": ["option_type"],
        "cap": {"maturity_years": 50},
    },
}

NOT_A_NUMBER = [
    ("str", "abc"), ("numstr", "5"), ("bool", True), ("nan", float("nan")),
    ("inf", float("inf")), ("list", []), ("dict", {}), ("bigint", 10 ** 400),
]
NOT_A_CHOICE = [("str", "nope"), ("num", 5), ("bool", True), ("list", []), ("empty", "")]
NOT_A_STRING = [("num", 5), ("bool", True), ("list", []), ("dict", {})]

# Cuerpos que no son un objeto JSON (cadena cruda): todos → 400 `field: null`.
BAD_BODIES = [
    ("empty", ""), ("garbage", "{no es json"), ("truncated", '{"snapshot": "MX-DEMO"'),
    ("list", "[]"), ("list_obj", '[{"snapshot": "MX-DEMO"}]'), ("string", '"texto"'),
    ("number", "5"), ("null", "null"), ("true", "true"),
]


def _drop(body: Dict[str, Any], key: str) -> Dict[str, Any]:
    return {k: v for k, v in body.items() if k != key}


def _case(method: str, url: str, body: Optional[str], field: Any, label: str):
    return pytest.param(method, url, body, field, id="%s %s %s" % (method, url, label))


def _raw(obj: Any) -> str:
    return json.dumps(obj)  # allow_nan: emite NaN/Infinity, que Flask sí acepta al leer


def _product_cases(product: str, wrap=None, url: Optional[str] = None, method: str = "POST") -> List:
    """Casos por campo de un producto. `wrap(params)` arma el cuerpo final (precio o trade)."""
    spec = SPECS[product]
    base = spec["base"]
    wrap = wrap or (lambda params: {"snapshot": SNAP, **params})
    url = url or "/api/price/%s" % product
    out = []

    def add(label: str, params: Dict[str, Any], field: Any):
        out.append(_case(method, url, _raw(wrap(params)), field, label))

    for name in spec["req"]:
        add("falta %s" % name, _drop(base, name), name)
        add("null %s" % name, {**base, name: None}, name)
    numeric = spec["gt0"] + spec["ge0"] + spec["free"] + spec["int1"]
    for name in numeric:
        for label, v in NOT_A_NUMBER:
            add("%s=%s" % (name, label), {**base, name: v}, name)
    for name in spec["gt0"]:
        for v in (0, -1):
            add("%s=%s" % (name, v), {**base, name: v}, name)
    for name in spec["ge0"]:
        add("%s=-1" % name, {**base, name: -1}, name)
    for name in spec["int1"]:
        for v in (0, -1, 1.5):
            add("%s=%s" % (name, v), {**base, name: v}, name)
    for name in spec["choice"]:
        for label, v in NOT_A_CHOICE:
            add("%s=%s" % (name, label), {**base, name: v}, name)
    for name, cap in spec["cap"].items():
        add("%s=%s (sobre la cota)" % (name, cap + 1), {**base, name: cap + 1}, name)
        add("%s=1e6" % name, {**base, name: 10 ** 6}, name)
    return out


# --------------------------------------------------------------------------- generadores por endpoint

def _structure_cases(method: str, url: str) -> List:
    return [_case(method, url, raw, None, "cuerpo %s" % label) for label, raw in BAD_BODIES]


def _snapshot_field_cases(url: str, body: Dict[str, Any]) -> List:
    """`snapshot` ausente, nulo, de tipo incorrecto, vacío; y snapshot inexistente → 404."""
    out = [
        _case("POST", url, _raw(_drop(body, "snapshot")), "snapshot", "falta snapshot"),
        _case("POST", url, _raw({**body, "snapshot": None}), "snapshot", "snapshot null"),
        _case("POST", url, _raw({**body, "snapshot": ""}), "snapshot", "snapshot vacío"),
        _case("POST", url, _raw({**body, "snapshot": "   "}), "snapshot", "snapshot en blanco"),
        _case("POST", url, _raw({**body, "snapshot": "NO-EXISTE"}), "snapshot", "snapshot inexistente"),
    ]
    for label, v in NOT_A_STRING:
        out.append(_case("POST", url, _raw({**body, "snapshot": v}), "snapshot", "snapshot=%s" % label))
    return out


def _price_cases() -> List:
    out = []
    for product in SPECS:
        url = "/api/price/%s" % product
        out += _structure_cases("POST", url)
        out.append(_case("POST", url, "{}", "snapshot", "objeto vacío"))
        out += _snapshot_field_cases(url, {"snapshot": SNAP, **SPECS[product]["base"]})
        out += _product_cases(product)
    bond, swn = SPECS["bond"]["base"], SPECS["swaption"]["base"]
    url_bond, url_swn = "/api/price/bond", "/api/price/swaption"
    for freq in (1e-9, 1e-300, 5e-324):  # vida del bono fuera del calendario: era 500 (OverflowError)
        out.append(_case("POST", url_bond, _raw({"snapshot": SNAP, **bond, "frequency": freq}),
                         "frequency", "bond frequency=%g" % freq))
    out.append(_case("POST", url_bond, _raw({"snapshot": SNAP, **bond, "periods": 1200, "frequency": 0.5}),
                     "frequency", "bond vida de 2400 años"))
    # Tenor de menos de medio periodo de pago: 0 pagos en C++ y segfault del proceso.
    for curve, tenor in (("TIIE-F", 1e-300), ("TIIE-F", 0.01), ("TIIE-F", 0.019), ("SOFR", 0.4), ("SOFR", 1e-9)):
        out.append(_case("POST", url_swn,
                         _raw({"snapshot": SNAP, **swn, "curve": curve, "swap_tenor_years": tenor}),
                         "swap_tenor_years", "swaption %s tenor=%g" % (curve, tenor)))
    out += [
        _case("POST", "/api/price/no_existe", _raw({"snapshot": SNAP}), "product", "producto inexistente"),
        _case("POST", "/api/price/no_existe", "", "product", "producto inexistente sin cuerpo"),
        _case("POST", "/api/price/IRS", _raw({"snapshot": SNAP}), "product", "producto en mayúsculas"),
    ]
    return out


def _trade_body(product: str):
    return lambda params: {"product": product, "counterparty": "Banco Test", "params": params}


def _trades_cases() -> List:
    url = "/api/trades"
    ok = {"product": "fx_forward", "counterparty": "Banco Test", "params": SPECS["fx_forward"]["base"]}
    out = _structure_cases("POST", url)
    out.append(_case("POST", url, "{}", ANY, "objeto vacío"))
    out += [
        _case("POST", url, _raw(_drop(ok, "product")), "product", "falta product"),
        _case("POST", url, _raw({**ok, "product": "no_existe"}), "product", "producto inexistente"),
        _case("POST", url, _raw(_drop(ok, "counterparty")), "counterparty", "falta counterparty"),
        _case("POST", url, _raw({**ok, "counterparty": ""}), "counterparty", "counterparty vacío"),
        _case("POST", url, _raw({**ok, "counterparty": "   "}), "counterparty", "counterparty en blanco"),
        _case("POST", url, _raw(_drop(ok, "params")), "params", "faltan params"),
        _case("POST", url, _raw({**ok, "params": None}), "params", "params null"),
    ]
    for label, v in NOT_A_CHOICE:
        out.append(_case("POST", url, _raw({**ok, "product": v}), "product", "product=%s" % label))
    for label, v in NOT_A_STRING:
        out.append(_case("POST", url, _raw({**ok, "counterparty": v}), "counterparty", "counterparty=%s" % label))
    for label, v in (("lista", []), ("texto", "x"), ("número", 5), ("bool", True)):
        out.append(_case("POST", url, _raw({**ok, "params": v}), "params", "params=%s" % label))
    # En el blotter irs exige tasa fija explícita (a diferencia del pricer).
    irs = SPECS["irs"]["base"]
    out.append(_case("POST", url, _raw(_trade_body("irs")(_drop(irs, "fixed_rate"))), "fixed_rate",
                     "irs sin fixed_rate"))
    out.append(_case("POST", url, _raw(_trade_body("irs")({**irs, "fixed_rate": None})), "fixed_rate",
                     "irs con fixed_rate null"))
    for product in SPECS:
        out += _product_cases(product, wrap=_trade_body(product), url=url)
    return out


def _delete_cases() -> List:
    ids = ["99999", "0", "-1", "abc", "1.5", "1e3", "%20", "9" * 30, "-" + "9" * 30]
    return [_case("DELETE", "/api/trades/%s" % i, None, "id", "id=%s" % i[:12]) for i in ids]


def _valuation_cases() -> List:
    base = "/api/portfolio/valuation"
    return [
        _case("GET", base, None, "snapshot", "sin snapshot"),
        _case("GET", base + "?snapshot=", None, "snapshot", "snapshot vacío"),
        _case("GET", base + "?snapshot=%20%20", None, "snapshot", "snapshot en blanco"),
        _case("GET", base + "?snapshot=NO-EXISTE", None, "snapshot", "snapshot inexistente"),
    ]


def _market_cases() -> List:
    snap = "/api/market/snapshots/%s" % SNAP
    out = [
        _case("GET", "/api/market/snapshots/NO-EXISTE", None, "snapshot", "GET inexistente"),
        _case("PUT", "/api/market/snapshots/NO-EXISTE", _raw({"spot": 18.5}), "snapshot", "PUT inexistente"),
        _case("PUT", snap, "{}", ANY, "PUT objeto vacío"),
        _case("PUT", snap, _raw({"spot": None}), ANY, "PUT spot null sin quotes"),
        _case("PUT", snap, _raw({"quotes": None}), ANY, "PUT quotes null sin spot"),
    ]
    out += _structure_cases("PUT", snap)
    good = {"id": "TIIE-F:13x28", "rate": 0.0685}
    for label, v in NOT_A_NUMBER:
        out.append(_case("PUT", snap, _raw({"spot": v}), "spot", "spot=%s" % label))
        out.append(_case("PUT", snap, _raw({"quotes": [{**good, "rate": v}]}), "quotes", "rate=%s" % label))
    for v in (0, -1, -18.5):
        out.append(_case("PUT", snap, _raw({"spot": v}), "spot", "spot=%s" % v))
    for v in (-0.05, -1, 1, 5, 100):
        out.append(_case("PUT", snap, _raw({"quotes": [{**good, "rate": v}]}), "quotes", "rate=%s" % v))
    for label, quotes in (
        ("quotes=texto", "TIIE-F"), ("quotes=número", 5), ("quotes=objeto", good), ("quotes=[]", []),
        ("quote=número", [5]), ("quote=texto", ["TIIE-F:13x28"]), ("quote=null", [None]),
        ("quote sin id", [{"rate": 0.07}]), ("quote sin rate", [{"id": good["id"]}]),
        ("id inexistente", [{"id": "NO:EXISTE", "rate": 0.07}]),
        ("id numérico", [{"id": 5, "rate": 0.07}]), ("id lista", [{"id": [], "rate": 0.07}]),
        ("id objeto", [{"id": {}, "rate": 0.07}]), ("una buena y una mala", [good, {"id": "X", "rate": 0.07}]),
    ):
        out.append(_case("PUT", snap, _raw({"quotes": quotes}), "quotes", label))
    return out


def _dv01_cases() -> List:
    url = "/api/risk/dv01"
    out = _structure_cases("POST", url)
    out.append(_case("POST", url, "{}", "snapshot", "objeto vacío"))
    out += _snapshot_field_cases(url, {"snapshot": SNAP})
    return out


OK_SCN = {"name": "p", "type": "parallel", "curve": "TIIE-F", "bp": 10}


def _scenarios_cases() -> List:
    url = "/api/risk/scenarios"
    ok = {"snapshot": SNAP, "scenarios": [OK_SCN]}
    out = _structure_cases("POST", url)
    out.append(_case("POST", url, "{}", "snapshot", "objeto vacío"))
    out += _snapshot_field_cases(url, ok)

    def scn(label: str, scenarios: Any, field: Any = "scenarios"):
        out.append(_case("POST", url, _raw({"snapshot": SNAP, "scenarios": scenarios}), field, label))

    out.append(_case("POST", url, _raw(_drop(ok, "scenarios")), "scenarios", "falta scenarios"))
    for label, v in (("null", None), ("lista vacía", []), ("texto", "x"), ("número", 5),
                     ("objeto", OK_SCN), ("bool", True)):
        scn("scenarios=%s" % label, v)
    for label, v in (("número", 5), ("texto", "x"), ("lista", []), ("null", None)):
        scn("escenario=%s" % label, [v])
    scn("escenario vacío", [{}])
    scn("uno bueno y uno malo", [OK_SCN, {"name": "x"}])
    for field_name in ("name", "type"):
        scn("falta %s" % field_name, [_drop(OK_SCN, field_name)])
        for label, v in (("null", None), ("vacío", ""), ("número", 5), ("lista", []), ("bool", True)):
            scn("%s=%s" % (field_name, label), [{**OK_SCN, field_name: v}])
    scn("name en blanco", [{**OK_SCN, "name": "   "}])
    scn("type desconocido", [{**OK_SCN, "type": "twist"}])
    scn("falta curve", [_drop(OK_SCN, "curve")])
    for label, v in (("null", None), ("vacía", ""), ("desconocida", "UDI"), ("número", 5), ("lista", [])):
        scn("curve=%s" % label, [{**OK_SCN, "curve": v}])
    for kind in ("parallel", "steepener"):
        base = {**OK_SCN, "type": kind}
        scn("%s falta bp" % kind, [_drop(base, "bp")])
        for label, v in NOT_A_NUMBER:
            scn("%s bp=%s" % (kind, label), [{**base, "bp": v}])
        for v in (1000.5, 1001, -1001, 10 ** 6, -(10 ** 6)):
            scn("%s bp=%s (fuera de ±1000)" % (kind, v), [{**base, "bp": v}])
    fx = {"name": "fx", "type": "fx_spot", "pct": 10}
    scn("fx_spot falta pct", [_drop(fx, "pct")])
    for label, v in NOT_A_NUMBER:
        scn("fx_spot pct=%s" % label, [{**fx, "pct": v}])
    for v in (-100, -95, -90, 500.5, 501, 10 ** 6, -(10 ** 6)):
        scn("fx_spot pct=%s (fuera de (-90, 500])" % v, [{**fx, "pct": v}])
    return out


def _var_cases() -> List:
    url = "/api/risk/var"
    ok = {"snapshot": SNAP, "horizon_days": 1, "confidence": 0.99}
    out = _structure_cases("POST", url)
    out.append(_case("POST", url, "{}", ANY, "objeto vacío"))
    out += _snapshot_field_cases(url, ok)
    for name, nonpositive in (("horizon_days", (0, -1)), ("confidence", (0, 1, -0.5, 1.5, 2))):
        out.append(_case("POST", url, _raw(_drop(ok, name)), name, "falta %s" % name))
        out.append(_case("POST", url, _raw({**ok, name: None}), name, "%s null" % name))
        for label, v in NOT_A_NUMBER:
            out.append(_case("POST", url, _raw({**ok, name: v}), name, "%s=%s" % (name, label)))
        for v in nonpositive:
            out.append(_case("POST", url, _raw({**ok, name: v}), name, "%s=%s" % (name, v)))
    for label, v in (("lista", []), ("texto", "x"), ("número", 5), ("bool", True)):
        out.append(_case("POST", url, _raw({**ok, "factor_vols": v}), "factor_vols", "factor_vols=%s" % label))
    for label, vols in (
        ("llave desconocida", {"UDI": 0.01}),
        ("una buena y una desconocida", {"TIIE-F": 4.0, "UDI": 0.01}),
        ("llave en minúsculas", {"usdmxn": 0.01}),
        ("negativa", {"TIIE-F": -1}),
        ("negativa FX", {"USDMXN": -0.0001}),
        ("texto", {"SOFR": "5"}),
        ("bool", {"SOFR": True}),
        ("null", {"SOFR": None}),
        ("NaN", {"SOFR": float("nan")}),
        ("infinito", {"SOFR": float("inf")}),
        ("lista", {"SOFR": []}),
        ("entero enorme", {"SOFR": 10 ** 400}),
    ):
        out.append(_case("POST", url, _raw({**ok, "factor_vols": vols}), "factor_vols", "factor_vols %s" % label))
    return out


ALL_CASES = (
    _price_cases()
    + _trades_cases()
    + _delete_cases()
    + _valuation_cases()
    + _market_cases()
    + _dv01_cases()
    + _scenarios_cases()
    + _var_cases()
)


# --------------------------------------------------------------------------- fixtures y barrido

@pytest.fixture(scope="module")
def sweep_client(tmp_path_factory):
    from desk.api.app import create_app

    return create_app(db_path=tmp_path_factory.mktemp("errors") / "t.db").test_client()


@pytest.mark.parametrize("method,url,body,field", ALL_CASES)
def test_entrada_invalida_nunca_es_500(sweep_client, method, url, body, field):
    kwargs = {} if body is None else {"data": body, "content_type": "application/json"}
    r = sweep_client.open(url, method=method, **kwargs)
    detail = r.get_data(as_text=True)[:300]
    assert r.status_code in (400, 404), "%s %s -> %d %s" % (method, url, r.status_code, detail)
    payload = r.get_json()
    assert isinstance(payload, dict) and set(payload) == {"error", "field"}, detail
    assert isinstance(payload["error"], str) and payload["error"], detail
    if field is not ANY:
        assert payload["field"] == field, detail


def test_el_barrido_cubre_los_endpoints_del_contrato():
    """Guarda contra olvidar un endpoint o un producto al ampliar la API."""
    assert set(SPECS) == set(PRODUCTS)
    urls = {c.values[1].split("?")[0] for c in ALL_CASES}
    expected = (
        {"/api/price/%s" % p for p in PRODUCTS}
        | {"/api/trades", "/api/portfolio/valuation", "/api/market/snapshots/NO-EXISTE",
           "/api/market/snapshots/%s" % SNAP, "/api/risk/dv01", "/api/risk/scenarios", "/api/risk/var"}
    )
    assert expected <= urls
    assert any(u.startswith("/api/trades/") for u in urls)


# --------------------------------------------------------------------------- cotas de entrada

def _capped_fields():
    return [(p, name, cap) for p, spec in SPECS.items() for name, cap in spec["cap"].items()]


@pytest.mark.parametrize("product,name,cap", _capped_fields())
def test_cota_exacta_es_aceptada_y_la_siguiente_no(product, name, cap):
    """La cota es inclusiva: el valor exacto valida y el siguiente se rechaza con su campo."""
    from desk.api.errors import ApiError

    validate = PRODUCTS[product].validate
    base = SPECS[product]["base"]
    validate({**base, name: cap})
    with pytest.raises(ApiError) as exc:
        validate({**base, name: cap + (1 if isinstance(cap, int) and name in SPECS[product]["int1"] else 0.5)})
    assert exc.value.status == 400 and exc.value.field == name


@pytest.mark.parametrize("product,name,cap", _capped_fields())
def test_valuar_en_la_cota_no_falla(client, product, name, cap):
    """El valor máximo permitido se puede valuar de punta a punta (200, PV finito)."""
    r = client.post(
        "/api/price/%s" % product,
        json={"snapshot": SNAP, **SPECS[product]["base"], name: cap},
    )
    assert r.status_code == 200, r.get_json()
    pv = r.get_json()["pv"]
    assert pv == pv and abs(pv) != float("inf")


@pytest.mark.parametrize(
    "product,params",
    [
        # vida del bono exactamente en la cota (1200 años) y swaptions con un solo pago
        ("bond", {"periods": 1200, "frequency": 1.0}),
        ("swaption", {"curve": "TIIE-F", "swap_tenor_years": 0.5 * 28 / 365}),
        ("swaption", {"curve": "SOFR", "swap_tenor_years": 0.5}),
    ],
)
def test_limites_que_tumbaban_el_proceso_ahora_valuan(client, product, params):
    r = client.post("/api/price/%s" % product, json={"snapshot": SNAP, **SPECS[product]["base"], **params})
    assert r.status_code == 200, r.get_json()


@pytest.mark.parametrize("curve", ["TIIE-F", "SOFR"])
def test_cotas_de_escenarios_son_inclusivas(client, curve):
    scenarios = [
        {"name": "up", "type": "parallel", "curve": curve, "bp": 1000},
        {"name": "down", "type": "parallel", "curve": curve, "bp": -1000},
        {"name": "steep", "type": "steepener", "curve": curve, "bp": 1000},
        {"name": "fx max", "type": "fx_spot", "pct": 500},
        {"name": "fx min", "type": "fx_spot", "pct": -89.9},
    ]
    r = client.post("/api/risk/scenarios", json={"snapshot": SNAP, "scenarios": scenarios})
    assert r.status_code == 200, r.get_json()
    assert len(r.get_json()["scenarios"]) == len(scenarios)
