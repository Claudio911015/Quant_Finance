"""Corte 6, T8: biblioteca de conjuntos de escenarios y escenarios combinados (`type: "combined"`)."""
import copy
import sqlite3

import pytest

from desk.api.risk import scenario_sets, scenarios
from desk.api.tests.conftest import empty_portfolio

BUILTIN_NAMES = ["Por omisión", "Depreciación 2008", "2016 elecciones EE. UU.", "Marzo 2020"]

TIIE_50 = {"type": "parallel", "curve": "TIIE-F", "bp": 50.0}
SOFR_M100 = {"type": "parallel", "curve": "SOFR", "bp": -100.0}
FX_10 = {"type": "fx_spot", "pct": 10.0}
STEEP = {"type": "steepener", "curve": "TIIE-F", "bp": 25.0}

MARCH_2020 = {"name": "Marzo 2020", "type": "combined", "shocks": [
    {"type": "fx_spot", "pct": 25.0},
    {"type": "parallel", "curve": "TIIE-F", "bp": -100.0},
    {"type": "parallel", "curve": "SOFR", "bp": -150.0},
]}


def _simple(name, shock):
    return dict(shock, name=name)


def _create(client, name="Choque Banxico", scenarios_=None, **extra):
    body = {"name": name, "scenarios": scenarios_ if scenarios_ is not None else [_simple("TIIE-F +100", dict(TIIE_50, bp=100.0))]}
    body.update(extra)
    return client.post("/api/scenario-sets", json=body)


def _list(client):
    r = client.get("/api/scenario-sets")
    assert r.status_code == 200, r.get_json()
    return r.get_json()["sets"]


def _run_inline(client, specs, snapshot="MX-DEMO"):
    r = client.post("/api/risk/scenarios", json={"snapshot": snapshot, "scenarios": specs})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _run_set(client, name, snapshot="MX-DEMO"):
    r = client.post("/api/risk/scenarios", json={"snapshot": snapshot, "set": name})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _count(app, table):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        return conn.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
    finally:
        conn.close()


def _assert_same_scenarios(a, b, tol=1e-12, names=True):
    if names:
        assert [s["name"] for s in a] == [s["name"] for s in b]
    for sa, sb in zip(a, b):
        assert sa["total_mxn"] == pytest.approx(sb["total_mxn"], abs=tol, rel=tol)
        assert [t["id"] for t in sa["trades"]] == [t["id"] for t in sb["trades"]]
        for ta, tb in zip(sa["trades"], sb["trades"]):
            assert ta["error"] == tb["error"]
            if ta["pnl_mxn"] is None:
                assert tb["pnl_mxn"] is None
            else:
                assert ta["pnl_mxn"] == pytest.approx(tb["pnl_mxn"], abs=tol, rel=tol)


# ----------------------------------------------------------------------------- biblioteca

def test_list_has_the_four_builtin_sets_first_and_in_order(client):
    sets = _list(client)
    assert [s["name"] for s in sets] == BUILTIN_NAMES
    for s in sets:
        assert s["id"] is None and s["builtin"] is True and s["status"] == "activo"
        assert s["created_at"] is None and s["scenarios"] and s["description"]
    assert [s["approximation"] for s in sets] == [False, True, True, True]


def test_builtin_march_2020_matches_the_contract_shape(client):
    march = _list(client)[3]
    assert march["description"] == "Aproximación histórica: USDMXN +25 %, TIIE-F −100 pb y SOFR −150 pb a la vez"
    assert march["scenarios"] == [MARCH_2020]


def test_builtin_default_set_is_the_eight_default_scenarios(client):
    assert _list(client)[0]["scenarios"] == scenarios.DEFAULT_SCENARIOS
    assert len(_list(client)[0]["scenarios"]) == 8


def test_builtin_historical_sets_have_one_combined_scenario_with_the_documented_shocks(client):
    by_name = {s["name"]: s for s in _list(client)}
    expected = {
        "Depreciación 2008": (35.0, 100.0, -200.0),
        "2016 elecciones EE. UU.": (12.0, 75.0, 25.0),
        "Marzo 2020": (25.0, -100.0, -150.0),
    }
    for name, (fx, tiie, sofr) in expected.items():
        (scn,) = by_name[name]["scenarios"]
        assert scn["name"] == name and scn["type"] == "combined"
        assert scn["shocks"] == [
            {"type": "fx_spot", "pct": fx},
            {"type": "parallel", "curve": "TIIE-F", "bp": tiie},
            {"type": "parallel", "curve": "SOFR", "bp": sofr},
        ]


def test_list_and_resolve_hand_out_copies_of_the_builtin_sets(app):
    conn = sqlite3.connect(app.config["DESK_DB"])
    conn.row_factory = sqlite3.Row
    try:
        before = copy.deepcopy(scenario_sets.BUILTIN_SETS)
        scenario_sets.list_sets(conn)[1]["scenarios"][0]["shocks"].clear()
        scenario_sets.resolve(conn, "Marzo 2020")[0]["shocks"].clear()
        scenario_sets.list_sets(conn)[0]["scenarios"].clear()
        assert scenario_sets.BUILTIN_SETS == before
    finally:
        conn.close()


def test_create_returns_201_with_the_saved_set(client):
    r = _create(client, "  Choque Banxico  ", description="  Sube la tasa  ")
    assert r.status_code == 201, r.get_json()
    s = r.get_json()
    assert isinstance(s["id"], int)
    assert s["name"] == "Choque Banxico"
    assert (s["builtin"], s["approximation"], s["status"]) == (False, False, "activo")
    assert s["description"] == "Sube la tasa"
    assert s["scenarios"] == [{"name": "TIIE-F +100", "type": "parallel", "curve": "TIIE-F", "bp": 100.0}]
    assert s["created_at"] and s["created_at"].endswith("+00:00")


def test_saved_sets_come_after_the_builtin_ones_by_id(client):
    first = _create(client, "Uno").get_json()
    second = _create(client, "Dos").get_json()
    sets = _list(client)
    assert [s["name"] for s in sets] == BUILTIN_NAMES + ["Uno", "Dos"]
    assert sets[4] == first and sets[5] == second  # lo que devuelve el alta es lo que lista


def test_description_is_null_when_omitted_or_blank(client):
    assert _create(client, "Uno").get_json()["description"] is None
    assert _create(client, "Dos", description="   ").get_json()["description"] is None
    assert _create(client, "Tres", description=None).get_json()["description"] is None


def test_create_normalizes_scenarios_like_the_inline_validator(client):
    r = _create(client, "N", [
        {"name": "  p  ", "type": "parallel", "curve": "SOFR", "bp": 5, "extra": "se descarta"},
        {"name": "f", "type": "fx_spot", "pct": 3},
    ])
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["scenarios"] == [
        {"name": "p", "type": "parallel", "curve": "SOFR", "bp": 5.0},
        {"name": "f", "type": "fx_spot", "pct": 3.0},
    ]


def test_create_accepts_a_combined_scenario_and_drops_the_shock_names(client):
    combined = {"name": "Mixto", "type": "combined", "shocks": [
        dict(TIIE_50, name="se descarta"), FX_10, {"type": "steepener", "curve": "SOFR", "bp": 10, "otro": 1}]}
    r = _create(client, "Con combinado", [combined])
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["scenarios"] == [{"name": "Mixto", "type": "combined", "shocks": [
        TIIE_50, FX_10, {"type": "steepener", "curve": "SOFR", "bp": 10.0}]}]


def test_duplicate_name_is_409_on_field_name(client, app):
    assert _create(client, "Repetido").status_code == 201
    r = _create(client, "Repetido")
    assert r.status_code == 409
    assert r.get_json()["field"] == "name" and r.get_json()["error"]
    assert _create(client, "  Repetido ").status_code == 409  # se compara ya recortado
    assert _count(app, "scenario_sets") == 1


def test_name_comparison_is_exact(client):
    assert _create(client, "Repetido").status_code == 201
    assert _create(client, "repetido").status_code == 201


@pytest.mark.parametrize("name", BUILTIN_NAMES)
def test_name_of_a_builtin_set_is_409(client, app, name):
    r = _create(client, name)
    assert r.status_code == 409 and r.get_json()["field"] == "name"
    assert _count(app, "scenario_sets") == 0


def test_retire_removes_it_from_the_list_and_a_repeat_is_409(client, app):
    sid = _create(client, "Temporal").get_json()["id"]
    r = client.post("/api/scenario-sets/%d/retire" % sid)
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["status"] == "baja" and r.get_json()["id"] == sid and r.get_json()["name"] == "Temporal"
    assert "Temporal" not in [s["name"] for s in _list(client)]
    again = client.post("/api/scenario-sets/%d/retire" % sid)
    assert again.status_code == 409 and again.get_json()["field"] == "id"
    assert _count(app, "scenario_set_events") == 1  # el segundo intento no insertó nada
    assert _count(app, "scenario_sets") == 1  # la fila sigue (solo inserción)


def test_retire_unknown_id_is_404(client):
    r = client.post("/api/scenario-sets/9999/retire")
    assert r.status_code == 404 and r.get_json()["field"] == "id"


@pytest.mark.parametrize("raw", ["abc", "1.5", "99999999999999999999"])
def test_retire_non_integer_id_is_404(client, raw):
    r = client.post("/api/scenario-sets/%s/retire" % raw)
    assert r.status_code == 404 and r.get_json()["field"] == "id"


def test_name_of_a_retired_set_can_be_reused(client):
    old = _create(client, "Reusable", [_simple("a", TIIE_50)]).get_json()
    assert client.post("/api/scenario-sets/%d/retire" % old["id"]).status_code == 200
    new = _create(client, "Reusable", [_simple("b", FX_10)])
    assert new.status_code == 201, new.get_json()
    assert new.get_json()["id"] != old["id"]
    listed = [s for s in _list(client) if s["name"] == "Reusable"]
    assert [s["id"] for s in listed] == [new.get_json()["id"]]
    # correr por nombre usa el activo, no el de baja
    assert [s["name"] for s in _run_set(client, "Reusable")["scenarios"]] == ["b"]


# ----------------------------------------------------------------------------- validación del alta

@pytest.mark.parametrize("body", [
    {"scenarios": [_simple("a", TIIE_50)]},
    {"name": "", "scenarios": [_simple("a", TIIE_50)]},
    {"name": "   ", "scenarios": [_simple("a", TIIE_50)]},
    {"name": 5, "scenarios": [_simple("a", TIIE_50)]},
    {"name": None, "scenarios": [_simple("a", TIIE_50)]},
    {"name": "x" * (scenario_sets.MAX_NAME + 1), "scenarios": [_simple("a", TIIE_50)]},
])
def test_invalid_name_is_400_on_field_name(client, app, body):
    r = client.post("/api/scenario-sets", json=body)
    assert r.status_code == 400 and r.get_json()["field"] == "name"
    assert _count(app, "scenario_sets") == 0


def test_name_of_exactly_max_length_is_accepted(client):
    assert _create(client, "x" * scenario_sets.MAX_NAME).status_code == 201


def test_non_text_description_is_400_on_field_description(client, app):
    r = _create(client, "D", description=5)
    assert r.status_code == 400 and r.get_json()["field"] == "description"
    assert _count(app, "scenario_sets") == 0


@pytest.mark.parametrize("scenarios_", [
    None,
    [],
    "no es lista",
    [5],
    [{"name": "a", "type": "otro"}],
    [{"name": "", "type": "fx_spot", "pct": 1}],
    [{"name": "a", "type": "fx_spot", "pct": -90}],
    [{"name": "a", "type": "parallel", "curve": "X", "bp": 1}],
])
def test_invalid_scenarios_are_400_on_field_scenarios(client, app, scenarios_):
    body = {"name": "S"}
    if scenarios_ is not None:
        body["scenarios"] = scenarios_
    r = client.post("/api/scenario-sets", json=body)
    assert r.status_code == 400 and r.get_json()["field"] == "scenarios"
    assert _count(app, "scenario_sets") == 0


@pytest.mark.parametrize("body", [[], "texto", 5])
def test_body_must_be_an_object(client, body):
    assert client.post("/api/scenario-sets", json=body).status_code == 400


# ----------------------------------------------------------------------------- escenarios combinados (validación)

def _combined(shocks, name="C"):
    return {"name": name, "type": "combined", "shocks": shocks}


def _err(client, specs):
    r = client.post("/api/risk/scenarios", json={"snapshot": "MX-DEMO", "scenarios": specs})
    assert r.status_code == 400, r.get_json()
    assert r.get_json()["field"] == "scenarios"
    return r.get_json()["error"]


@pytest.mark.parametrize("shocks", [
    [],
    None,
    "no es lista",
    [dict(FX_10)] * 9,
    [5],
    [{"type": "combined", "shocks": [dict(FX_10)]}],
    [{"type": "otro"}],
    [{"type": "fx_spot", "pct": -90}],
    [{"type": "fx_spot"}],
    [{"type": "parallel", "curve": "X", "bp": 1}],
    [{"type": "parallel", "curve": "TIIE-F", "bp": 5000}],
])
def test_invalid_combined_shocks_are_400(client, shocks):
    spec = {"name": "C", "type": "combined"}
    if shocks is not None:
        spec["shocks"] = shocks
    assert _err(client, [spec]).startswith("Escenario 1: ")


@pytest.mark.parametrize("name", [None, "", "  ", 5])
def test_combined_needs_a_name(client, name):
    spec = {"type": "combined", "shocks": [dict(FX_10)]}
    if name is not None:
        spec["name"] = name
    assert _err(client, [spec]) == "Escenario 1: 'name' debe ser texto no vacío"


def test_combined_accepts_between_one_and_eight_shocks(client):
    one = _run_inline(client, [_combined([FX_10])])["scenarios"]
    eight = _run_inline(client, [_combined([dict(FX_10, pct=1.0)] * 8)])["scenarios"]
    assert len(one) == 1 and len(eight) == 1


def test_combined_cannot_be_nested(client):
    msg = _err(client, [_combined([{"type": "combined", "name": "x", "shocks": [dict(FX_10)]}])])
    assert "no se anida" in msg


def test_error_index_points_at_the_offending_scenario(client):
    ok = _simple("ok", TIIE_50)
    assert _err(client, [ok, _combined([FX_10]), {"name": "x", "type": "otro"}]).startswith("Escenario 3: 'type'")
    assert _err(client, [ok, _combined([{"type": "otro"}])]).startswith("Escenario 2: choque 1: 'type'")
    assert _err(client, [ok, _combined([FX_10, dict(FX_10, pct="x")])]).startswith("Escenario 2: choque 2: 'pct'")
    assert _err(client, [ok, ok, 5]) == "Escenario 3: debe ser un objeto"
    assert _err(client, [ok, ok, {"name": " ", "type": "fx_spot", "pct": 1}]) == "Escenario 3: 'name' debe ser texto no vacío"


def test_existing_error_messages_for_simple_scenarios_are_unchanged(client):
    assert _err(client, [{"name": "a", "type": "otro"}]) == (
        "Escenario 1: 'type' debe ser uno de: parallel, steepener, fx_spot")
    assert _err(client, []) == "'scenarios' debe ser una lista no vacía de escenarios"
    assert _err(client, [{"name": "a", "type": "fx_spot", "pct": -90}]) == (
        "Escenario 1: 'pct' debe ser mayor que -90 y no mayor que 500")


# ----------------------------------------------------------------------------- R5: correr un conjunto == mandarlo en línea

def test_running_a_saved_set_equals_sending_it_inline(client):
    specs = [_simple("TIIE-F +50", TIIE_50), _simple("steep", STEEP), _simple("USDMXN +10", FX_10),
             _combined([TIIE_50, SOFR_M100, FX_10], "Mixto")]
    saved = _create(client, "Guardado", specs)
    assert saved.status_code == 201, saved.get_json()
    from_set = _run_set(client, "Guardado")
    inline = _run_inline(client, specs)
    assert from_set["set"] == "Guardado" and from_set["snapshot"] == "MX-DEMO"
    _assert_same_scenarios(from_set["scenarios"], inline["scenarios"])
    assert {k: v for k, v in from_set.items() if k != "set"}.keys() == inline.keys()


def test_running_a_historical_set_equals_its_combined_scenario_inline(client):
    from_set = _run_set(client, "Marzo 2020")
    inline = _run_inline(client, [MARCH_2020])
    assert from_set["set"] == "Marzo 2020"
    assert [s["name"] for s in from_set["scenarios"]] == ["Marzo 2020"]
    _assert_same_scenarios(from_set["scenarios"], inline["scenarios"])
    assert from_set["scenarios"][0]["total_mxn"] != 0.0


@pytest.mark.parametrize("name", ["Depreciación 2008", "2016 elecciones EE. UU."])
def test_other_historical_sets_run_and_move_the_portfolio(client, name):
    result = _run_set(client, name)
    assert [s["name"] for s in result["scenarios"]] == [name]
    assert result["scenarios"][0]["total_mxn"] != 0.0
    assert all(t["error"] is None for t in result["scenarios"][0]["trades"])


def test_default_set_equals_the_eight_default_scenarios_inline(client):
    from_set = _run_set(client, "Por omisión")
    inline = _run_inline(client, scenarios.DEFAULT_SCENARIOS)
    assert len(from_set["scenarios"]) == 8
    _assert_same_scenarios(from_set["scenarios"], inline["scenarios"])


def test_running_a_set_does_not_change_the_response_without_set(client):
    inline = _run_inline(client, [_simple("p", TIIE_50)])
    assert "set" not in inline


def test_set_unknown_or_retired_is_404_on_field_set(client):
    r = client.post("/api/risk/scenarios", json={"snapshot": "MX-DEMO", "set": "No existe"})
    assert r.status_code == 404 and r.get_json()["field"] == "set"
    sid = _create(client, "Se va").get_json()["id"]
    assert client.post("/api/scenario-sets/%d/retire" % sid).status_code == 200
    r = client.post("/api/risk/scenarios", json={"snapshot": "MX-DEMO", "set": "Se va"})
    assert r.status_code == 404 and r.get_json()["field"] == "set"


def test_set_and_scenarios_together_are_400_on_field_set(client):
    r = client.post("/api/risk/scenarios", json={
        "snapshot": "MX-DEMO", "set": "Marzo 2020", "scenarios": [_simple("a", TIIE_50)]})
    assert r.status_code == 400 and r.get_json()["field"] == "set"


# ----------------------------------------------------------------------------- semántica del combinado

def test_combined_with_one_shock_equals_the_simple_scenario(client):
    for shock in (TIIE_50, STEEP, FX_10, SOFR_M100):
        simple, combined = _run_inline(client, [_simple("s", shock), _combined([shock], "s")])["scenarios"]
        _assert_same_scenarios([simple], [combined])


def test_combined_is_not_the_sum_of_its_shocks_because_of_interaction(client):
    tiie, fx, both = _run_inline(client, [
        _simple("t", TIIE_50), _simple("f", FX_10), _combined([TIIE_50, FX_10], "tf")])["scenarios"]
    by_trade = lambda s: {t["id"]: t["pnl_mxn"] for t in s["trades"]}
    t_pnl, f_pnl, b_pnl = by_trade(tiie), by_trade(fx), by_trade(both)
    # La opción FX (id 6) depende a la vez de la tasa MXN y del spot: el cruce no es cero.
    assert abs(b_pnl[6] - t_pnl[6] - f_pnl[6]) > 1.0
    assert abs(both["total_mxn"] - tiie["total_mxn"] - fx["total_mxn"]) > 1.0


def test_combined_on_a_pure_tiie_irs_equals_the_sum_of_its_shocks(client):
    # Un irs TIIE-F no ve el spot: sin interacción, el combinado es la suma (aquí además es exacto).
    tiie, fx, both = _run_inline(client, [
        _simple("t", TIIE_50), _simple("f", FX_10), _combined([TIIE_50, FX_10], "tf")])["scenarios"]
    by_trade = lambda s: {t["id"]: t["pnl_mxn"] for t in s["trades"]}
    for irs_id in (1, 2):  # los dos irs TIIE-F sembrados
        assert by_trade(fx)[irs_id] == 0.0
        assert by_trade(both)[irs_id] == pytest.approx(by_trade(tiie)[irs_id] + by_trade(fx)[irs_id], rel=1e-9, abs=1e-9)


def test_combined_shocks_are_chained_on_the_same_context(client):
    # Dos choques de spot se componen: (1 + 10 %)·(1 + 10 %) = +21 %, no +20 %.
    twice, plus21, plus20 = _run_inline(client, [
        _combined([FX_10, FX_10], "dos"), _simple("21", {"type": "fx_spot", "pct": 21.0}),
        _simple("20", {"type": "fx_spot", "pct": 20.0})])["scenarios"]
    _assert_same_scenarios([twice], [plus21], tol=1e-9, names=False)
    assert abs(twice["total_mxn"] - plus20["total_mxn"]) > 1.0


def test_combined_does_not_alter_the_base_market(client):
    before = _run_inline(client, [_simple("p", TIIE_50)])["scenarios"][0]
    _run_inline(client, [_combined([TIIE_50, SOFR_M100, FX_10], "c")])
    after = _run_inline(client, [_simple("p", TIIE_50)])["scenarios"][0]
    _assert_same_scenarios([before], [after], tol=0.0)


def test_shock_alias_handles_combined_for_hedge_effectiveness():
    assert scenarios.shock is scenarios._shock
    assert scenarios._validate_single is not scenarios._validate
    assert scenarios._shock_single is not scenarios._shock


def test_combined_on_an_empty_portfolio_is_zero(client):
    empty_portfolio(client)
    (result,) = _run_set(client, "Marzo 2020")["scenarios"]
    assert result["total_mxn"] == 0.0 and result["trades"] == []
