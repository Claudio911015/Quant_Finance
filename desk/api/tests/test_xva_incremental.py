"""Corte 9, T8: XVA incremental (`POST /api/xva/incremental`) con las mismas trayectorias antes y después.

R5(a): una candidata espejo de la única operación de una contraparte deja exposición cero. R5(b): guardar la
candidata y pedir `GET /api/xva` da el «después» (y el «antes» es el `GET` previo). R5(c): una candidata inválida
da el mismo error que `POST /api/trades`, sin insertar nada.
"""
import pytest

from desk.api.pricing import PRODUCT_LABEL
from desk.api.tests.csa_fixture import set_collateral, trade_with

SNAP = "MX-DEMO"
ALFA, BETA, GAMMA = "Banco Alfa (sintético)", "Banco Beta (sintético)", "Banco Gamma (sintético)"
DELTA = "Banco Delta (prueba)"
IRS = {"curve": "TIIE-F", "side": "payer", "notional": 1e8, "periods": 13, "fixed_rate": 0.07}
SOFR_IRS = {"curve": "SOFR", "side": "payer", "notional": 5e6, "periods": 5, "fixed_rate": 0.04}
XCCY = {"side": "pay_usd", "notional_usd": 5e6, "periods": 26, "fx_rate": 18.6, "spread": 0.001}
FORWARD = {"side": "buy", "notional_usd": 1e6, "days": 91, "strike": 18.9}
COMPONENTS = ("cva_mxn", "dva_mxn", "fva_mxn", "total_mxn")
SIDE_KEYS = {
    "pv_mxn", "cva_mxn", "cva_stderr_mxn", "dva_mxn", "fva_mxn", "total_mxn", "epe_max_mxn", "pfe_max_mxn",
}
TOP_KEYS = {
    "snapshot", "as_of", "counterparty", "notice", "candidate", "before", "after", "delta", "delta_bp", "profile",
    "warnings",
}
NOT_COVERED = "El XVA incremental solo cubre swaps de tasa y cross currency swaps: %s no"


# ---------------------------------------------------------------- ayudas

def _fast(client, n_paths=300):
    """Pocas trayectorias: lo que se prueba son relaciones exactas entre corridas, no precisión de Monte Carlo."""
    assert client.put("/api/xva/params", json={"n_paths": n_paths}).status_code == 200


def _body(counterparty, product="irs", params=IRS, **extra):
    return dict({"snapshot": SNAP, "counterparty": counterparty, "product": product, "params": params}, **extra)


def _incremental(client, body):
    return client.post("/api/xva/incremental", json=body)


def _ok(client, body):
    r = _incremental(client, body)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _xva(client):
    r = client.get("/api/xva?snapshot=%s" % SNAP)
    assert r.status_code == 200, r.get_json()
    return {c["counterparty"]: c for c in r.get_json()["counterparties"]}


def _counts(client):
    trades = client.get("/api/trades").get_json()["trades"]
    names = client.get("/api/counterparties").get_json()["counterparties"]
    return len(trades), sorted(c["name"] for c in names)


def _delta_with_forward(client):
    """Una contraparte sin curva de CDS ni operaciones cubiertas: solo un forward FX (excluido del XVA)."""
    return trade_with(client, "fx_forward", DELTA, FORWARD)


# ---------------------------------------------------------------- R5(a): el espejo deja exposición cero

@pytest.mark.parametrize(
    "product, params, mirror",
    [
        ("irs", IRS, {"side": "receiver"}),
        ("irs", SOFR_IRS, {"side": "receiver"}),
        ("xccy_swap", XCCY, {"side": "pay_mxn"}),
    ],
)
def test_mirror_of_the_only_trade_removes_all_the_xva_exactly(client, product, params, mirror):
    _fast(client)
    trade_with(client, product, DELTA, params)
    body = _ok(client, _body(DELTA, product, dict(params, **mirror)))
    before, after, delta = body["before"], body["after"], body["delta"]
    assert before["cva_mxn"] > 0.0 and before["dva_mxn"] > 0.0 and before["total_mxn"] != 0.0
    assert before["epe_max_mxn"] > 0.0 and before["pfe_max_mxn"] > 0.0
    for key in ("cva_mxn", "cva_stderr_mxn", "dva_mxn", "fva_mxn", "total_mxn", "epe_max_mxn", "pfe_max_mxn"):
        assert after[key] == 0.0, key
    for key in COMPONENTS:
        assert delta[key] == -before[key], key  # exacto, no aproximado
    assert after["pv_mxn"] == pytest.approx(0.0, abs=1e-3)
    assert all(p["epe_after_mxn"] == 0.0 and p["ene_after_mxn"] == 0.0 for p in body["profile"])
    assert any(p["epe_before_mxn"] > 0.0 for p in body["profile"]) and any(p["ene_before_mxn"] > 0.0 for p in body["profile"])


# ---------------------------------------------------------------- R5(b): guardar la candidata da el «después»

SAVED_CASES = [
    # (id, contraparte, producto, términos, extras de la petición)
    ("alfa-irs-par-longer-than-the-book", ALFA, "irs", {"curve": "TIIE-F", "side": "receiver", "notional": 2e8, "periods": 130}, {}),
    ("beta-xccy-par", BETA, "xccy_swap", {"side": "pay_usd", "notional_usd": 5e6, "periods": 26}, {}),
    ("gamma-sofr-aged", GAMMA, "irs", {"curve": "SOFR", "side": "payer", "notional": 8e6, "periods": 5, "fixed_rate": 0.04},
     {"trade_date": "2026-09-01"}),
    ("gamma-xccy-aged", GAMMA, "xccy_swap", {"side": "pay_mxn", "notional_usd": 4e6, "periods": 39, "fx_rate": 18.9, "spread": 0.001},
     {"trade_date": "2026-06-01"}),
    ("delta-only-excluded-trades", DELTA, "irs", IRS, {}),
]


@pytest.mark.parametrize("name, product, params, extra", [c[1:] for c in SAVED_CASES], ids=[c[0] for c in SAVED_CASES])
def test_saving_the_candidate_gives_the_after_state_and_the_before_is_the_previous_get(client, name, product, params, extra):
    _fast(client)
    if name == DELTA:
        _delta_with_forward(client)
    previous = _xva(client)[name]
    request = _body(name, product, params, **extra)
    body = _ok(client, request)

    # el «antes» es el XVA que ya daba GET /api/xva, aunque la candidata alargue la malla de reporte
    for key in SIDE_KEYS:
        assert body["before"][key] == pytest.approx(previous[key], rel=1e-9, abs=1e-6), key
    assert body["before"]["pv_mxn"] == pytest.approx(previous["pv_mxn"], rel=1e-9, abs=1e-6)

    saved = client.post("/api/trades", json=request)
    assert saved.status_code == 201, saved.get_json()
    current = _xva(client)[name]
    for key in SIDE_KEYS:
        assert body["after"][key] == pytest.approx(current[key], rel=1e-6, abs=1e-6), key
    assert body["candidate"]["params"] == saved.get_json()["params"]  # los términos resueltos (a la par)
    assert body["candidate"]["pv_mxn"] == pytest.approx(current["pv_mxn"] - previous["pv_mxn"], rel=1e-9, abs=1e-6)

    # los perfiles «después» son el perfil sin descontar de GET; los «antes», el previo en las fechas comunes
    after = {p["date"]: p for p in current["profile"]}
    assert [p["date"] for p in body["profile"]] == [p["date"] for p in current["profile"]]
    for p in body["profile"]:
        assert p["epe_after_mxn"] == pytest.approx(after[p["date"]]["epe_mxn"], rel=1e-9, abs=1e-6)
        assert p["ene_after_mxn"] == pytest.approx(after[p["date"]]["ene_mxn"], rel=1e-9, abs=1e-6)
    prior = {p["date"]: p for p in previous["profile"]}
    for p in body["profile"]:
        if p["date"] in prior:
            assert p["epe_before_mxn"] == pytest.approx(prior[p["date"]]["epe_mxn"], rel=1e-9, abs=1e-6)
            assert p["ene_before_mxn"] == pytest.approx(prior[p["date"]]["ene_mxn"], rel=1e-9, abs=1e-6)
        else:
            assert p["epe_before_mxn"] == 0.0 and p["ene_before_mxn"] == 0.0  # pasado el último vencimiento


def test_saving_the_candidate_matches_with_usd_collateral(client):
    _fast(client)
    assert set_collateral(client, ALFA, "USD", "2026-01-01").status_code == 200
    previous = _xva(client)[ALFA]
    request = _body(ALFA, "irs", {"curve": "TIIE-F", "side": "payer", "notional": 1.5e8, "periods": 26, "fixed_rate": 0.0705})
    body = _ok(client, request)
    assert client.post("/api/trades", json=request).status_code == 201
    current = _xva(client)[ALFA]
    for key in SIDE_KEYS:
        assert body["after"][key] == pytest.approx(current[key], rel=1e-6, abs=1e-6), key
    assert body["before"]["total_mxn"] == pytest.approx(previous["total_mxn"], rel=1e-9)


# ---------------------------------------------------------------- forma, números y economía

def test_response_shape_and_candidate_block(client):
    _fast(client)
    body = _ok(client, _body(ALFA, "irs", dict(IRS, side="receiver")))
    assert set(body) == TOP_KEYS
    assert body["snapshot"] == SNAP and body["as_of"] == "2026-11-10" and body["counterparty"] == ALFA
    assert body["notice"] == "XVA informativo: no entra al PV ni a la contabilidad"
    assert set(body["before"]) == SIDE_KEYS == set(body["after"])
    assert set(body["delta"]) == set(COMPONENTS) and set(body["delta_bp"]) == {"cva", "dva", "fva", "total"}
    cand = body["candidate"]
    assert set(cand) == {
        "product", "label", "params", "trade_date", "start_date", "maturity_date", "notional", "currency",
        "notional_mxn", "pv_mxn",
    }
    assert (cand["product"], cand["label"]) == ("irs", PRODUCT_LABEL["irs"])
    assert (cand["notional"], cand["currency"], cand["notional_mxn"]) == (1e8, "MXN", 1e8)
    assert cand["trade_date"] == cand["start_date"] == "2026-11-10"
    assert set(body["profile"][0]) == {"date", "t", "epe_before_mxn", "ene_before_mxn", "epe_after_mxn", "ene_after_mxn"}
    assert body["profile"][0]["date"] == "2026-11-10" and body["profile"][0]["t"] == 0.0
    assert body["after"]["pv_mxn"] == pytest.approx(body["before"]["pv_mxn"] + cand["pv_mxn"], rel=1e-12)
    for key in COMPONENTS:
        assert body["delta"][key] == body["after"][key] - body["before"][key], key
    assert body["delta"]["total_mxn"] == pytest.approx(
        body["delta"]["cva_mxn"] - body["delta"]["dva_mxn"] + body["delta"]["fva_mxn"], rel=1e-9, abs=1e-6
    )
    assert body["after"]["total_mxn"] == pytest.approx(
        body["after"]["cva_mxn"] - body["after"]["dva_mxn"] + body["after"]["fva_mxn"], rel=1e-9, abs=1e-6
    )


@pytest.mark.parametrize(
    "product, params, currency, in_usd",
    [("irs", IRS, "MXN", False), ("irs", SOFR_IRS, "USD", True), ("xccy_swap", XCCY, "USD", True)],
)
def test_notional_mxn_and_basis_points(client, product, params, currency, in_usd):
    _fast(client)
    spot = client.get("/api/market/snapshots/%s" % SNAP).get_json()["fx"]["spot"]
    body = _ok(client, _body(BETA, product, params))
    notional = params["notional_usd"] if product == "xccy_swap" else params["notional"]
    cand = body["candidate"]
    assert cand["currency"] == currency and cand["notional"] == notional
    assert cand["notional_mxn"] == pytest.approx(notional * (spot if in_usd else 1.0), rel=1e-12)
    for key in ("cva", "dva", "fva", "total"):
        assert body["delta_bp"][key] == pytest.approx(body["delta"][key + "_mxn"] / cand["notional_mxn"] * 1e4, rel=1e-12)
    assert body["delta_bp"]["total"] != 0.0


def test_candidate_pv_is_the_desk_valuation_of_the_saved_trade(client):
    _fast(client)
    request = _body(BETA, "xccy_swap", {"side": "pay_usd", "notional_usd": 3e6, "periods": 13}, trade_date="2026-08-17")
    body = _ok(client, request)
    created = client.post("/api/trades", json=request).get_json()
    rows = client.get("/api/portfolio/valuation?snapshot=%s" % SNAP).get_json()["rows"]
    pv = [r["pv_mxn"] for r in rows if r["id"] == created["id"]][0]
    assert body["candidate"]["pv_mxn"] == pytest.approx(pv, rel=1e-9)
    assert body["candidate"]["trade_date"] == "2026-08-17"
    assert body["candidate"]["params"] == created["params"]  # fx_rate y spread a la par, resueltos igual


def test_same_direction_adds_cva_and_the_opposite_direction_offsets_it(client):
    _fast(client)
    trade_with(client, "irs", DELTA, IRS)
    more = _ok(client, _body(DELTA, "irs", dict(IRS, notional=5e7)))
    offset = _ok(client, _body(DELTA, "irs", dict(IRS, notional=5e7, side="receiver")))
    assert more["delta"]["cva_mxn"] > 0.0 and more["after"]["epe_max_mxn"] > more["before"]["epe_max_mxn"]
    assert offset["delta"]["cva_mxn"] < 0.0 and offset["after"]["epe_max_mxn"] < offset["before"]["epe_max_mxn"]
    assert offset["delta_bp"]["cva"] < 0.0 < more["delta_bp"]["cva"]


def test_candidate_on_a_counterparty_without_covered_trades_starts_from_zero(client):
    _fast(client)
    _delta_with_forward(client)
    body = _ok(client, _body(DELTA))
    assert all(body["before"][k] == 0.0 for k in SIDE_KEYS)
    assert body["after"]["cva_mxn"] > 0.0 and body["delta"]["cva_mxn"] == body["after"]["cva_mxn"]
    assert all(p["epe_before_mxn"] == 0.0 and p["ene_before_mxn"] == 0.0 for p in body["profile"])


def test_same_response_on_two_calls_and_the_seed_is_shared_by_both_sides(client):
    _fast(client)
    request = _body(ALFA, "irs", dict(IRS, side="receiver"))
    assert _ok(client, request) == _ok(client, request)
    # otra semilla mueve las cifras, pero el espejo sigue dejando cero exacto: «antes» y «después» comparten trayectorias
    assert client.put("/api/xva/params", json={"seed": 7}).status_code == 200
    trade_with(client, "irs", DELTA, IRS)
    moved = _ok(client, _body(DELTA, "irs", dict(IRS, side="receiver")))
    assert moved["after"]["total_mxn"] == 0.0 and moved["delta"]["total_mxn"] == -moved["before"]["total_mxn"]


def test_a_negligible_candidate_moves_the_xva_by_a_negligible_amount(client):
    """Antes y después comparten trayectorias: sumar 1 000 MXN de nocional a un conjunto de miles de millones no
    puede mover el CVA más que su tamaño; con trayectorias distintas el ruido de Monte Carlo (~3 %) taparía el efecto."""
    _fast(client)
    body = _ok(client, _body(ALFA, "irs", dict(IRS, notional=1e3)))
    assert body["before"]["cva_mxn"] > 1e5
    assert abs(body["delta"]["cva_mxn"]) < 1e-5 * body["before"]["cva_mxn"]
    assert abs(body["delta"]["total_mxn"]) < 1e-5 * abs(body["before"]["total_mxn"])


def test_xva_params_apply_to_the_incremental(client):
    _fast(client)
    request = _body(ALFA)
    low = _ok(client, request)
    assert client.put("/api/xva/params", json={"funding_spread": 0.05}).status_code == 200
    high = _ok(client, request)
    assert high["before"]["cva_mxn"] == low["before"]["cva_mxn"] and high["before"]["fva_mxn"] != low["before"]["fva_mxn"]


def test_valuation_warnings_of_an_aged_candidate_are_reported(client):
    _fast(client)
    _delta_with_forward(client)
    fresh = _ok(client, _body(DELTA, "irs", dict(IRS, periods=26)))
    assert fresh["warnings"] == []
    aged = _ok(client, _body(DELTA, "irs", dict(IRS, periods=26), trade_date="2026-08-17"))
    assert "missing_fixing" in {w["code"] for w in aged["warnings"]}


def test_nothing_is_saved(client):
    _fast(client)
    _delta_with_forward(client)
    before = _counts(client)
    xva_before = _xva(client)
    _ok(client, _body(ALFA))
    _ok(client, _body(DELTA, "xccy_swap", XCCY))
    assert _counts(client) == before
    assert _xva(client) == xva_before


# ---------------------------------------------------------------- R5(c): errores

def _error(response):
    body = response.get_json()
    return response.status_code, body["error"], body.get("field")


INVALID = {
    "negative-notional": {"params": dict(IRS, notional=-1.0)},
    "zero-periods": {"params": dict(IRS, periods=0)},
    "unknown-curve": {"params": dict(IRS, curve="XXX")},
    "unknown-side": {"params": dict(IRS, side="largo")},
    "rate-out-of-range": {"params": dict(IRS, fixed_rate=11.0)},
    "params-missing": {"params": None},
    "params-not-an-object": {"params": [1, 2]},
    "maturity-before-start": {"start_date": "2026-11-10", "maturity_date": "2026-11-01"},
    "start-before-trade": {"trade_date": "2026-11-10", "start_date": "2026-11-01"},
    "bad-date-text": {"trade_date": "10/11/2026"},
    "impossible-date": {"maturity_date": "2027-02-30"},
    "maturity-out-of-range": {"start_date": "2026-11-10", "maturity_date": "2126-11-10"},
    "unknown-product": {"product": "swap_raro"},
    "blank-counterparty": {"counterparty": "   "},
    "counterparty-not-text": {"counterparty": 7},
    "xccy-bad-side": {"product": "xccy_swap", "params": dict(XCCY, side="x")},
    "xccy-negative-notional": {"product": "xccy_swap", "params": dict(XCCY, notional_usd=-5.0)},
}


@pytest.mark.parametrize("change", list(INVALID.values()), ids=list(INVALID))
def test_invalid_candidate_gives_the_same_error_as_post_trades_and_inserts_nothing(client, change):
    request = _body(ALFA)
    for key, value in change.items():
        if value is None:
            request.pop(key)
        else:
            request[key] = value
    before = _counts(client)
    reference = _error(client.post("/api/trades", json=request))
    assert reference[0] == 400 and reference[2], reference  # la petición es inválida de verdad
    assert _error(_incremental(client, request)) == reference
    assert _counts(client) == before


def test_post_trades_rejects_the_same_body_the_incremental_accepts_as_valid(client):
    """Contraste: lo que el incremental acepta, `POST /api/trades` lo guarda con 201."""
    _fast(client)
    request = _body(ALFA, "irs", dict(IRS, side="receiver"))
    assert _incremental(client, request).status_code == 200
    assert client.post("/api/trades", json=request).status_code == 201


@pytest.mark.parametrize(
    "product", ["fx_forward", "fx_option", "cap_floor", "bond", "swaption", "equity_option"]
)
def test_products_outside_the_scope_are_400_in_spanish_with_the_label(client, product):
    r = _incremental(client, _body(ALFA, product, {}))
    status, error, field = _error(r)
    assert (status, field) == (400, "product")
    assert error == NOT_COVERED % PRODUCT_LABEL[product]
    assert product not in error  # el rótulo, no el código interno


def test_unknown_counterparty_is_404_and_is_not_created(client):
    before = _counts(client)
    status, error, field = _error(_incremental(client, _body("Banco Fantasma")))
    assert (status, field, error) == (404, "counterparty", "Contraparte inexistente: Banco Fantasma")
    assert _counts(client) == before


def test_the_counterparty_is_checked_before_the_candidate_terms(client):
    status, _, field = _error(_incremental(client, _body("Banco Fantasma", "irs", dict(IRS, notional=-1.0))))
    assert (status, field) == (404, "counterparty")


def test_product_is_checked_before_the_counterparty(client):
    status, _, field = _error(_incremental(client, _body("Banco Fantasma", "bond", {})))
    assert (status, field) == (400, "product")


def test_snapshot_is_required_and_must_exist(client):
    request = _body(ALFA)
    request.pop("snapshot")
    assert _error(_incremental(client, request))[0::2] == (400, "snapshot")
    assert _error(_incremental(client, dict(request, snapshot="NOPE")))[0::2] == (404, "snapshot")
    assert _error(_incremental(client, dict(request, snapshot=5)))[0::2] == (400, "snapshot")


def test_body_must_be_an_object(client):
    assert _incremental(client, [1]).status_code == 400
    assert client.post("/api/xva/incremental", data="no es json", content_type="application/json").status_code == 400


@pytest.mark.parametrize(
    "extra",
    [
        {"trade_date": "2026-12-01"},  # aún no pactada al as_of del snapshot
        {"trade_date": "2025-01-01", "start_date": "2025-01-01", "maturity_date": "2025-06-01"},  # ya vencida
    ],
    ids=["not-yet-traded", "already-matured"],
)
def test_candidate_not_alive_at_the_snapshot_date_is_400_on_trade_date(client, extra):
    before = _counts(client)
    status, error, field = _error(_incremental(client, _body(ALFA, **extra)))
    assert (status, field) == (400, "trade_date")
    assert "no está viva" in error
    assert _counts(client) == before


def test_xva_response_and_credit_stay_unchanged_after_the_incremental(client):
    _fast(client)
    first = client.get("/api/credit/exposure?snapshot=%s" % SNAP).get_json()
    _ok(client, _body(ALFA))
    assert client.get("/api/credit/exposure?snapshot=%s" % SNAP).get_json() == first
