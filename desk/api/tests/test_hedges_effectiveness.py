"""Coberturas, T4: efectividad prospectiva, términos críticos y razones por escenario (R7)."""
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from desk.api.risk import scenarios
from desk.api.tests.hedge_fixture import designate, market_forward, par_irs, roll
from desk.api.tests.hedge_fixture import frozen_clock  # noqa: F401  (autouse: reloj fijo)

D0 = date(2026, 11, 10)
LOAN_END = D0 + timedelta(days=364)  # 13 periodos de 28 días: el swap tiene exactamente las fechas del crédito
FIXED_END = D0 + timedelta(days=28 * 26)
FX_END = date(2027, 5, 11)
RISK_SCREEN = Path(__file__).resolve().parents[2] / "ui" / "src" / "screens" / "RiskScreen.tsx"


def _loan(**over):
    return {
        "index": "TIIE-F", "notional": 500e6, "start_date": D0.isoformat(),
        "maturity_date": LOAN_END.isoformat(), "side": "pays_floating", **over,
    }


def _fixed_loan(**over):
    return _loan(**{"notional": 300e6, "maturity_date": FIXED_END.isoformat(), "side": "pays_fixed", **over})


def _fx(**over):
    return {"amount_usd": 10e6, "date": FX_END.isoformat(), "side": "buy_usd", **over}


def _effectiveness(client, hedge_id, snapshot="MX-DEMO"):
    return client.get("/api/hedges/%d/effectiveness?snapshot=%s" % (hedge_id, snapshot))


def _ok(client, hedge_id, snapshot="MX-DEMO"):
    r = _effectiveness(client, hedge_id, snapshot)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _hedge(client, trade, item_kind, terms, **over):
    r = designate(client, trade["id"], item_kind, terms, **over)
    assert r.status_code == 201, r.get_json()
    return r.get_json()["id"]


def _results(body):
    return {t["term"]: t["result"] for t in body["critical_terms"]}


def _ratios(body):
    return {s["name"]: s["ratio"] for s in body["scenarios"]}


# ------------------------------------------------------------------------- hipotético idéntico

def test_identical_loan_swap_matches_every_term_and_every_ratio_is_one(client):
    trade = par_irs(client, "TIIE-F", 500e6, D0, LOAN_END)
    body = _ok(client, _hedge(client, trade, "floating_loan", _loan()))
    assert (body["snapshot"], body["as_of"]) == ("MX-DEMO", D0.isoformat())
    assert [t["term"] for t in body["critical_terms"]] == ["notional", "index", "start_date", "maturity_date", "side"]
    assert [t["label"] for t in body["critical_terms"]] == ["Nocional", "Índice", "Inicio", "Vencimiento", "Sentido"]
    assert set(_results(body).values()) == {"match"}
    notional = body["critical_terms"][0]
    assert (notional["instrument"], notional["item"]) == (500e6, 500e6)
    assert [(t["instrument"], t["item"]) for t in body["critical_terms"][1:]] == [
        ("TIIE-F", "TIIE-F"), (D0.isoformat(), D0.isoformat()), (LOAN_END.isoformat(), LOAN_END.isoformat()),
        ("payer", "pays_floating"),  # el swap que paga fija compensa al crédito que paga variable
    ]
    counted = [s for s in body["scenarios"] if s["ratio"] is not None]
    assert counted and body["scenarios_counted"] == len(counted)
    for s in counted:
        assert s["ratio"] == pytest.approx(1.0, abs=1e-6)
        assert s["d_inst"] == pytest.approx(s["d_hypo"], abs=1e-6 * 500e6)
    assert body["economic_relationship"] is True
    assert body["in_reference_range"] == body["scenarios_counted"]
    assert "80 %–125 %" in body["reference_note"] and "no fija" in body["reference_note"]
    assert isinstance(body["warnings"], list)


def test_scenarios_are_the_eight_of_the_risk_screen_in_order(client):
    trade = par_irs(client, "TIIE-F", 500e6, D0, LOAN_END)
    body = _ok(client, _hedge(client, trade, "floating_loan", _loan()))
    assert [s["name"] for s in body["scenarios"]] == [
        "TIIE-F +50 pb", "TIIE-F -50 pb", "SOFR +50 pb", "SOFR -50 pb",
        "TIIE-F steepener 25 pb", "SOFR steepener 25 pb", "USDMXN +10 %", "USDMXN -10 %",
    ]


def test_default_scenarios_mirror_the_risk_screen_source():
    """El set no se desvía de `RiskScreen.tsx` (mismo nombre, tipo, curva y magnitud, en el mismo orden)."""
    pattern = re.compile(
        r"\{ name: '([^']+)', type: '(\w+)'(?:, curve: '([^']+)', bp: (-?\d+))?(?:, pct: (-?\d+))? \}"
    )
    parsed = []
    for name, kind, curve, bp, pct in pattern.findall(RISK_SCREEN.read_text(encoding="utf-8")):
        spec = {"name": name, "type": kind}
        if kind == "fx_spot":
            spec["pct"] = float(pct)
        else:
            spec.update(curve=curve, bp=float(bp))
        parsed.append(spec)
    assert len(parsed) == 8
    assert scenarios.DEFAULT_SCENARIOS == parsed


def test_public_shock_is_the_private_one():
    assert scenarios.shock is scenarios._shock


def test_scenarios_that_do_not_move_the_item_have_a_null_ratio_and_are_not_counted(client):
    trade = par_irs(client, "TIIE-F", 500e6, D0, LOAN_END)
    body = _ok(client, _hedge(client, trade, "floating_loan", _loan()))
    ratios = _ratios(body)
    for name in ("SOFR +50 pb", "SOFR -50 pb", "SOFR steepener 25 pb", "USDMXN +10 %", "USDMXN -10 %"):
        assert ratios[name] is None
    for name in ("TIIE-F +50 pb", "TIIE-F -50 pb", "TIIE-F steepener 25 pb"):
        assert ratios[name] == pytest.approx(1.0, abs=1e-6)
    assert body["scenarios_counted"] == 3
    # un choque que no mueve la partida no cuenta: d_hypo es 0 y la razón no se inventa
    sofr = next(s for s in body["scenarios"] if s["name"] == "SOFR +50 pb")
    assert abs(sofr["d_hypo"]) < 1e-6 * 500e6


def test_identical_forward_matches_every_term_and_every_ratio_is_one(client):
    trade = market_forward(client, "buy", 10e6, FX_END)
    body = _ok(client, _hedge(client, trade, "forecast_fx", _fx()))
    assert [t["term"] for t in body["critical_terms"]] == ["notional", "currency", "maturity_date", "side"]
    assert [t["label"] for t in body["critical_terms"]] == ["Nocional", "Moneda", "Vencimiento", "Sentido"]
    assert set(_results(body).values()) == {"match"}
    side = body["critical_terms"][3]
    assert (side["instrument"], side["item"]) == ("buy", "buy_usd")
    assert (body["critical_terms"][1]["instrument"], body["critical_terms"][1]["item"]) == ("USD", "USD")
    ratios = _ratios(body)
    assert ratios["USDMXN +10 %"] == pytest.approx(1.0, abs=1e-6)
    assert ratios["USDMXN -10 %"] == pytest.approx(1.0, abs=1e-6)
    counted = [r for r in ratios.values() if r is not None]
    assert len(counted) == body["scenarios_counted"] >= 2
    for r in counted:
        assert r == pytest.approx(1.0, abs=1e-6)
    assert body["economic_relationship"] is True


def test_fixed_loan_with_an_identical_receiver_swap_matches_with_ratios_of_one(client):
    trade = par_irs(client, "TIIE-F", 300e6, D0, FIXED_END, side="receiver")
    body = _ok(client, _hedge(client, trade, "fixed_loan", _fixed_loan(), hedge_type="fair_value"))
    assert set(_results(body).values()) == {"match"}
    counted = [s["ratio"] for s in body["scenarios"] if s["ratio"] is not None]
    assert len(counted) == body["scenarios_counted"] == 3
    for r in counted:
        assert r == pytest.approx(1.0, abs=1e-6)
    assert body["economic_relationship"] is True


# ------------------------------------------------------------------------- desajustes

def test_a_loan_that_matures_after_the_swap_reports_a_maturity_mismatch(client):
    trade = par_irs(client, "TIIE-F", 500e6, D0, LOAN_END)
    later = LOAN_END + timedelta(days=28)
    body = _ok(client, _hedge(client, trade, "floating_loan", _loan(maturity_date=later.isoformat())))
    results = _results(body)
    assert results.pop("maturity_date") == "mismatch" and set(results.values()) == {"match"}
    term = next(t for t in body["critical_terms"] if t["term"] == "maturity_date")
    assert (term["instrument"], term["item"]) == (LOAN_END.isoformat(), later.isoformat())


def test_a_sell_forward_hedging_a_usd_purchase_has_a_side_mismatch_and_negative_ratios(client):
    trade = market_forward(client, "sell", 10e6, FX_END)
    body = _ok(client, _hedge(client, trade, "forecast_fx", _fx(side="buy_usd")))
    results = _results(body)
    assert results.pop("side") == "mismatch" and set(results.values()) == {"match"}
    side = next(t for t in body["critical_terms"] if t["term"] == "side")
    assert (side["instrument"], side["item"]) == ("sell", "buy_usd")
    counted = [s["ratio"] for s in body["scenarios"] if s["ratio"] is not None]
    assert counted and body["scenarios_counted"] == len(counted)
    assert all(r < 0 for r in counted)
    assert body["economic_relationship"] is False
    assert body["in_reference_range"] == 0


def test_a_buy_forward_hedging_a_usd_sale_is_also_a_side_mismatch(client):
    trade = market_forward(client, "buy", 10e6, FX_END)
    body = _ok(client, _hedge(client, trade, "forecast_fx", _fx(side="sell_usd")))
    assert _results(body)["side"] == "mismatch" and body["economic_relationship"] is False


def test_opposite_signs_mean_no_economic_relationship(client):
    trade = par_irs(client, "TIIE-F", 500e6, D0, LOAN_END, side="receiver")
    body = _ok(client, _hedge(client, trade, "floating_loan", _loan(side="pays_floating")))
    counted = [s["ratio"] for s in body["scenarios"] if s["ratio"] is not None]
    assert counted and all(r == pytest.approx(-1.0, abs=1e-6) for r in counted)
    assert body["economic_relationship"] is False
    assert body["in_reference_range"] == 0
    results = _results(body)  # C6 / D-4: el término `side` delata el swap del lado equivocado
    assert results.pop("side") == "mismatch" and set(results.values()) == {"match"}
    side = next(t for t in body["critical_terms"] if t["term"] == "side")
    assert (side["instrument"], side["item"]) == ("receiver", "pays_floating")


def test_a_half_fraction_of_a_double_notional_swap_matches_the_loan_notional(client):
    trade = par_irs(client, "TIIE-F", 1000e6, D0, LOAN_END)
    body = _ok(client, _hedge(client, trade, "floating_loan", _loan(), fraction=0.5))
    notional = body["critical_terms"][0]
    assert (notional["instrument"], notional["item"], notional["result"]) == (500e6, 500e6, "match")
    for s in body["scenarios"]:
        if s["ratio"] is not None:
            assert s["ratio"] == pytest.approx(1.0, abs=1e-6)
    assert body["economic_relationship"] is True


def test_hedge_ratio_enters_the_notional_comparison(client):
    trade = par_irs(client, "TIIE-F", 500e6, D0, LOAN_END)
    body = _ok(client, _hedge(client, trade, "floating_loan", _loan(), hedge_ratio=0.9))
    notional = body["critical_terms"][0]
    assert (notional["instrument"], notional["item"], notional["result"]) == (500e6, 450e6, "mismatch")


def test_a_notional_change_after_the_designation_has_no_special_treatment(client):
    """El nocional del instrumento es el vigente a la fecha de la consulta."""
    trade = par_irs(client, "TIIE-F", 500e6, D0, LOAN_END)
    hedge_id = _hedge(client, trade, "floating_loan", _loan())
    as_of = roll(client, "MX-DEMO", "D1", 35)
    r = client.post(
        "/api/trades/%d/events" % trade["id"],
        json={"type": "quantity_change", "event_date": as_of, "data": {"notional": 250e6}},
    )
    assert r.status_code == 201, r.get_json()
    body = _ok(client, hedge_id, "D1")
    notional = body["critical_terms"][0]
    assert (notional["instrument"], notional["item"], notional["result"]) == (250e6, 500e6, "mismatch")


# ------------------------------------------------------------------------- errores

def test_a_missing_snapshot_parameter_is_a_400(client):
    trade = par_irs(client, "TIIE-F", 500e6, D0, LOAN_END)
    hedge_id = _hedge(client, trade, "floating_loan", _loan())
    r = client.get("/api/hedges/%d/effectiveness" % hedge_id)
    assert r.status_code == 400 and r.get_json()["field"] == "snapshot"


def test_an_unknown_snapshot_is_a_404(client):
    trade = par_irs(client, "TIIE-F", 500e6, D0, LOAN_END)
    hedge_id = _hedge(client, trade, "floating_loan", _loan())
    r = _effectiveness(client, hedge_id, "NO-EXISTE")
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"


def test_an_unknown_hedge_is_a_404(client):
    r = _effectiveness(client, 999)
    assert r.status_code == 404 and r.get_json()["field"] == "id"


def test_a_snapshot_rolled_past_the_maturity_is_a_409(client):
    trade = par_irs(client, "TIIE-F", 500e6, D0, LOAN_END)
    hedge_id = _hedge(client, trade, "floating_loan", _loan())
    roll(client, "MX-DEMO", "TARDE", 400)
    r = _effectiveness(client, hedge_id, "TARDE")
    assert r.status_code == 409 and r.get_json()["field"] == "snapshot"


def test_a_swap_that_matured_before_the_loan_is_a_409_on_the_trade(client):
    trade = par_irs(client, "TIIE-F", 500e6, D0, LOAN_END)
    later = LOAN_END + timedelta(days=56)
    hedge_id = _hedge(client, trade, "floating_loan", _loan(maturity_date=later.isoformat()))
    roll(client, "MX-DEMO", "ENTRE", 380)  # el swap venció (364 días), el crédito aún no (420)
    r = _effectiveness(client, hedge_id, "ENTRE")
    assert r.status_code == 409 and r.get_json()["field"] == "snapshot"
    assert "operación" in r.get_json()["error"]


@pytest.mark.parametrize(
    "item_kind, loan_side, swap_side, expected",
    [
        ("floating_loan", "pays_floating", "payer", "match"),
        ("floating_loan", "receives_floating", "receiver", "match"),
        ("floating_loan", "receives_floating", "payer", "mismatch"),
        ("fixed_loan", "pays_fixed", "receiver", "match"),
        ("fixed_loan", "receives_fixed", "payer", "match"),
        ("fixed_loan", "pays_fixed", "payer", "mismatch"),
    ],
)
def test_the_side_term_compares_the_swap_with_the_side_that_offsets_the_loan(
    client, item_kind, loan_side, swap_side, expected
):
    fair = item_kind == "fixed_loan"
    trade = par_irs(client, "TIIE-F", 300e6, D0, FIXED_END, side=swap_side)
    terms = _fixed_loan(side=loan_side) if fair else _loan(notional=300e6, maturity_date=FIXED_END.isoformat(), side=loan_side)
    body = _ok(client, _hedge(client, trade, item_kind, terms, hedge_type="fair_value" if fair else "cash_flow"))
    side = next(t for t in body["critical_terms"] if t["term"] == "side")
    assert (side["instrument"], side["item"], side["result"]) == (swap_side, loan_side, expected)
