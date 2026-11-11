"""Coberturas, T2: `POST /api/hedges` (designación) y el derivado hipotético a la par (R1, base de R2)."""
import sqlite3
from datetime import date, timedelta

import pytest

from desk.api.tests.hedge_fixture import CLOCK, DOC, designate, load_fixings, market_forward, par_irs, roll
from desk.api.tests.hedge_fixture import frozen_clock  # noqa: F401  (autouse: reloj fijo)

D0 = date(2026, 11, 10)
LOAN_END = D0 + timedelta(days=364)  # 13 periodos de 28 días: el swap tiene exactamente las fechas del crédito
FIXED_END = D0 + timedelta(days=28 * 26)
FX_END = date(2027, 5, 11)
TABLES = ("hedge_relationships", "hedge_events", "hedge_periods")


def _loan(**over):
    return {
        "index": "TIIE-F", "notional": 500e6, "start_date": D0.isoformat(),
        "maturity_date": LOAN_END.isoformat(), "side": "pays_floating", **over,
    }


def _fixed_loan(**over):
    return _loan(**{"notional": 300e6, "maturity_date": FIXED_END.isoformat(), "side": "pays_fixed", **over})


def _fx(**over):
    return {"amount_usd": 10e6, "date": FX_END.isoformat(), "side": "buy_usd", **over}


def _counts(app):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        return [conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in TABLES]
    finally:
        conn.close()


@pytest.fixture
def loan_trade(client):
    return par_irs(client, "TIIE-F", 500e6, D0, LOAN_END)


@pytest.fixture
def fx_trade(client):
    return market_forward(client, "buy", 10e6, FX_END)


# ------------------------------------------------------------------------- altas válidas

def test_floating_loan_designation_stores_the_par_hypothetical(app, client, loan_trade):
    r = designate(client, loan_trade["id"], "floating_loan", {**_loan(), "ignorada": 1}, hedge_ratio=0.95)
    assert r.status_code == 201, r.get_json()
    d = r.get_json()
    assert d["trade_id"] == loan_trade["id"] and d["status"] == "activa"
    assert d["item_terms"] == _loan()  # forma normalizada: la clave desconocida no se guarda
    assert (d["hedge_type"], d["item_kind"], d["fraction"], d["hedge_ratio"]) == ("cash_flow", "floating_loan", 1.0, 0.95)
    assert d["designation_date"] == D0.isoformat() and d["designation_snapshot"] == "MX-DEMO"
    assert d["documentation"] == DOC
    assert [e["type"] for e in d["events"]] == ["designation"] and d["periods"] == []
    assert d["events"][0]["event_date"] == D0.isoformat()
    h = d["hypothetical"]
    assert (h["product"], h["trade_date"], h["start_date"], h["maturity_date"]) == (
        "irs", D0.isoformat(), D0.isoformat(), LOAN_END.isoformat(),
    )
    assert h["params"]["side"] == "payer" and h["params"]["curve"] == "TIIE-F" and h["params"]["periods"] == 13
    assert h["params"]["notional"] == 500e6
    # el swap de la operación nace a la par con las mismas fechas: la tasa par del hipotético es la suya
    assert h["params"]["fixed_rate"] == pytest.approx(loan_trade["params"]["fixed_rate"], abs=1e-12)
    assert d["designation"]["data_quality"] == "synthetic" and d["designation"]["snapshot"] == "MX-DEMO"
    assert d["designation"]["as_of"] == D0.isoformat()
    assert abs(d["designation"]["pv_hypo"]) < 1e-6 * 500e6 and abs(d["designation"]["pv_inst"]) < 1e-6 * 500e6
    assert _counts(app) == [1, 1, 0]
    assert client.get("/api/hedges/%d" % d["id"]).get_json() == d  # GET devuelve el mismo detalle


def test_fixed_loan_fair_value_designation_has_a_receiver_hypothetical_at_par(client):
    trade = par_irs(client, "TIIE-F", 300e6, D0, FIXED_END, side="receiver")
    r = designate(client, trade["id"], "fixed_loan", _fixed_loan(), hedge_type="fair_value")
    assert r.status_code == 201, r.get_json()
    d = r.get_json()
    assert (d["hedge_type"], d["item_kind"]) == ("fair_value", "fixed_loan")
    assert d["hypothetical"]["params"]["side"] == "receiver"
    assert d["hypothetical"]["params"]["fixed_rate"] == pytest.approx(trade["params"]["fixed_rate"], abs=1e-12)
    assert abs(d["designation"]["pv_hypo"]) < 1e-6 * 300e6


def test_fixed_loan_that_receives_fixed_has_a_payer_hypothetical(client):
    trade = par_irs(client, "TIIE-F", 300e6, D0, FIXED_END, side="payer")
    r = designate(client, trade["id"], "fixed_loan", _fixed_loan(side="receives_fixed"), hedge_type="fair_value")
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["hypothetical"]["params"]["side"] == "payer"


def test_sofr_loan_designation_values_the_hypothetical_in_mxn(client):
    end = D0 + timedelta(days=365 * 3)
    trade = par_irs(client, "SOFR", 20e6, D0, end)
    terms = _loan(index="SOFR", notional=20e6, maturity_date=end.isoformat())
    r = designate(client, trade["id"], "floating_loan", terms)
    assert r.status_code == 201, r.get_json()
    d = r.get_json()
    assert d["hypothetical"]["params"]["curve"] == "SOFR" and d["hypothetical"]["params"]["periods"] == 3
    spot = client.get("/api/market/snapshots/MX-DEMO").get_json()["fx"]["spot"]
    assert abs(d["designation"]["pv_hypo"]) < 1e-6 * 20e6 * spot


@pytest.mark.parametrize("trade_side,item_side", [("buy", "buy_usd"), ("sell", "sell_usd")])
def test_forecast_fx_hypothetical_is_a_forward_at_the_market_forward(app, client, trade_side, item_side):
    trade = market_forward(client, trade_side, 10e6, FX_END)
    r = designate(client, trade["id"], "forecast_fx", _fx(side=item_side))
    assert r.status_code == 201, r.get_json()
    d = r.get_json()
    h = d["hypothetical"]
    assert (h["product"], h["trade_date"], h["start_date"], h["maturity_date"]) == (
        "fx_forward", D0.isoformat(), D0.isoformat(), FX_END.isoformat(),
    )
    assert h["params"]["side"] == trade_side and h["params"]["days"] == (FX_END - D0).days
    assert h["params"]["notional_usd"] == 10e6
    assert h["params"]["strike"] == pytest.approx(trade["params"]["strike"], rel=1e-12)  # strike = forward de mercado
    spot = client.get("/api/market/snapshots/MX-DEMO").get_json()["fx"]["spot"]
    assert abs(d["designation"]["pv_hypo"]) < 1e-6 * 10e6 * spot
    assert abs(d["designation"]["pv_inst"]) < 1e-6 * 10e6 * spot  # el forward de la operación también es de mercado


# ------------------------------------------------------------------------- combinaciones

@pytest.mark.parametrize(
    "hedge_type,item_kind,terms",
    [
        ("fair_value", "floating_loan", _loan()),
        ("fair_value", "forecast_fx", _fx()),
        ("cash_flow", "fixed_loan", _fixed_loan()),
    ],
)
def test_invalid_hedge_type_and_item_kind_combinations(app, client, loan_trade, hedge_type, item_kind, terms):
    r = designate(client, loan_trade["id"], item_kind, terms, hedge_type=hedge_type)
    assert r.status_code == 400 and r.get_json()["field"] == "hedge_type"
    assert _counts(app) == [0, 0, 0]


def test_fixed_loan_rejects_floating_sides(client, loan_trade):
    r = designate(client, loan_trade["id"], "fixed_loan", _fixed_loan(side="pays_floating"), hedge_type="fair_value")
    assert r.status_code == 400 and r.get_json()["field"] == "side"


def test_floating_loan_rejects_fixed_sides(client, loan_trade):
    r = designate(client, loan_trade["id"], "floating_loan", _loan(side="pays_fixed"))
    assert r.status_code == 400 and r.get_json()["field"] == "side"


# ------------------------------------------------------------------------- validación

def _body(tid, **over):
    body = {
        "trade_id": tid, "snapshot": "MX-DEMO", "hedge_type": "cash_flow", "item_kind": "floating_loan",
        "item_terms": _loan(), "fraction": 1.0, "documentation": DOC,
    }
    body.update(over)
    return body


@pytest.mark.parametrize(
    "over,status,field",
    [
        ({"trade_id": 0}, 400, "trade_id"),
        ({"trade_id": "x"}, 400, "trade_id"),
        ({"trade_id": None}, 400, "trade_id"),
        ({"trade_id": 99999}, 404, "trade_id"),
        ({"snapshot": None}, 400, "snapshot"),
        ({"snapshot": "NO-EXISTE"}, 404, "snapshot"),
        ({"designation_date": "10/11/2026"}, 400, "designation_date"),
        ({"designation_date": "2026-11-11"}, 400, "designation_date"),
        ({"hedge_type": "otra"}, 400, "hedge_type"),
        ({"hedge_type": None}, 400, "hedge_type"),
        ({"item_kind": "otra"}, 400, "item_kind"),
        ({"item_terms": "x"}, 400, "item_terms"),
        ({"item_terms": None}, 400, "item_terms"),
        ({"item_terms": _loan(index="CETES")}, 400, "index"),
        ({"item_terms": _loan(notional=0)}, 400, "notional"),
        ({"item_terms": _loan(notional="x")}, 400, "notional"),
        ({"item_terms": _loan(start_date="mañana")}, 400, "start_date"),
        ({"item_terms": _loan(maturity_date=D0.isoformat())}, 400, "maturity_date"),  # <= start_date
        ({"item_terms": _loan(start_date="2026-01-01", maturity_date=D0.isoformat())}, 400, "maturity_date"),  # <= designación
        ({"item_terms": _loan(side="otro")}, 400, "side"),
        ({"item_kind": "forecast_fx", "item_terms": _fx()}, 400, "item_kind"),  # un irs no cubre un flujo en USD
        ({"item_terms": _loan(index="SOFR")}, 400, "index"),  # curva del swap TIIE-F
        ({"fraction": 0}, 400, "fraction"),
        ({"fraction": 1.0001}, 400, "fraction"),
        ({"fraction": "x"}, 400, "fraction"),
        ({"hedge_ratio": 0}, 400, "hedge_ratio"),
        ({"documentation": "x"}, 400, "documentation"),
        ({"documentation": {k: v for k, v in DOC.items() if k != "hedged_risk"}}, 400, "hedged_risk"),
        ({"documentation": {**DOC, "effectiveness_method": "  "}}, 400, "effectiveness_method"),
    ],
)
def test_contract_errors_leave_no_trace(app, client, loan_trade, over, status, field):
    body = _body(loan_trade["id"], **over)
    if over.get("trade_id", 0) is None:
        del body["trade_id"]
    r = client.post("/api/hedges", json=body)
    assert r.status_code == status, r.get_json()
    assert r.get_json()["field"] == field
    assert _counts(app) == [0, 0, 0]


@pytest.mark.parametrize(
    "over,field",
    [
        ({"item_terms": _fx(amount_usd=0)}, "amount_usd"),
        ({"item_terms": _fx(date=D0.isoformat())}, "date"),  # no posterior a la designación
        ({"item_terms": _fx(date="no")}, "date"),
        ({"item_terms": _fx(side="buy")}, "side"),
    ],
)
def test_forecast_fx_term_errors(app, client, fx_trade, over, field):
    r = client.post("/api/hedges", json=_body(fx_trade["id"], item_kind="forecast_fx", **over))
    assert r.status_code == 400 and r.get_json()["field"] == field
    assert _counts(app) == [0, 0, 0]


def test_a_swap_cannot_hedge_the_forecast_flow_and_a_forward_cannot_hedge_a_loan(client, fx_trade):
    r = client.post("/api/hedges", json=_body(fx_trade["id"]))  # floating_loan contra un fx_forward
    assert r.status_code == 400 and r.get_json()["field"] == "item_kind"


def test_the_first_contract_error_wins(client, loan_trade):
    r = client.post(
        "/api/hedges", json=_body(loan_trade["id"], fraction=0, documentation="x", item_kind="otra")
    )
    assert r.get_json()["field"] == "item_kind"
    r = client.post("/api/hedges", json=_body(loan_trade["id"], fraction=0, documentation="x"))
    assert r.get_json()["field"] == "fraction"
    r = client.post("/api/hedges", json=_body(loan_trade["id"], snapshot="NO-EXISTE", hedge_type="otra"))
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"


# ------------------------------------------------------------------------- estado de la operación

def _book_at(client, trade_date, start, maturity):
    r = client.post(
        "/api/trades",
        json={
            "counterparty": "Banco Alfa (sintético)", "product": "irs", "snapshot": "MX-DEMO",
            "params": {"curve": "TIIE-F", "side": "payer", "notional": 500e6, "periods": 1, "fixed_rate": 0.07},
            "trade_date": trade_date, "start_date": start, "maturity_date": maturity,
        },
    )
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def test_a_trade_terminated_before_the_designation_is_rejected(app, client):
    trade = _book_at(client, "2026-10-01", "2026-10-01", "2027-09-30")
    r = client.post(
        "/api/trades/%d/events" % trade["id"],
        json={"type": "termination", "event_date": "2026-11-01", "data": {"amount": 0.0}},
    )
    assert r.status_code == 201, r.get_json()
    r = designate(client, trade["id"], "floating_loan", _loan(start_date="2026-10-01", maturity_date="2027-09-30"))
    assert r.status_code == 409 and r.get_json()["field"] == "trade_id"
    assert _counts(app) == [0, 0, 0]


def test_a_trade_dated_after_the_snapshot_as_of_is_rejected(app, client):
    trade = _book_at(client, "2026-12-01", "2026-12-01", "2027-11-30")
    r = designate(client, trade["id"], "floating_loan", _loan(start_date="2026-12-01", maturity_date="2027-11-30"))
    assert r.status_code == 409 and r.get_json()["field"] == "trade_id"
    assert _counts(app) == [0, 0, 0]


def test_a_matured_trade_is_not_designable(client):
    trade = _book_at(client, "2026-01-05", "2026-01-05", "2026-11-09")
    r = designate(client, trade["id"], "floating_loan", _loan(start_date="2026-01-05", maturity_date="2026-11-30"))
    assert r.status_code == 409 and r.get_json()["field"] == "trade_id"


# ------------------------------------------------------------------------- fracciones

def test_active_fractions_of_one_trade_cannot_exceed_one(app, client, loan_trade):
    first = designate(client, loan_trade["id"], "floating_loan", _loan(), fraction=0.6)
    assert first.status_code == 201, first.get_json()
    over = designate(client, loan_trade["id"], "floating_loan", _loan(), fraction=0.5)
    assert over.status_code == 409 and over.get_json()["field"] == "fraction"
    # La interfaz captura la fracción en %: el mensaje habla en % y no en decimales.
    assert "60 %" in over.get_json()["error"] and "100 %" in over.get_json()["error"]
    assert _counts(app) == [1, 1, 0]  # el rechazo no insertó nada
    rest = designate(client, loan_trade["id"], "floating_loan", _loan(), fraction=0.4)
    assert rest.status_code == 201, rest.get_json()
    assert _counts(app) == [2, 2, 0]
    assert [h["fraction"] for h in client.get("/api/hedges?trade_id=%d" % loan_trade["id"]).get_json()["hedges"]] == [0.6, 0.4]


# ------------------------------------------------------------------------- C1: designar en orden y sin solapar

def _later_snapshot(client, days=35):
    """Rueda MX-DEMO `days` días con TIIE-F cargada; devuelve el id del snapshot y su fecha."""
    sid = "D%d" % days
    as_of = date.fromisoformat(roll(client, "MX-DEMO", sid, days))
    load_fixings(client, "TIIE-F", D0, as_of, 0.07)
    return sid, as_of


def test_a_designation_dated_before_the_last_event_of_the_trade_is_409_on_snapshot(app, client, loan_trade):
    first = designate(client, loan_trade["id"], "floating_loan", _loan(), fraction=0.5)
    assert first.status_code == 201, first.get_json()
    sid, as_of = _later_snapshot(client)
    assert client.post("/api/hedges/%d/periods" % first.get_json()["id"], json={"snapshot": sid}).status_code == 201
    before = _counts(app)

    r = designate(client, loan_trade["id"], "floating_loan", _loan(), fraction=0.5)  # con MX-DEMO (2026-11-10)

    assert r.status_code == 409 and r.get_json()["field"] == "snapshot"
    assert as_of.isoformat() in r.get_json()["error"] and "#%d" % first.get_json()["id"] in r.get_json()["error"]
    assert _counts(app) == before
    # En la fecha del último evento sí se puede, y la fracción cuenta lo vigente ese día.
    ok = designate(client, loan_trade["id"], "floating_loan", _loan(), fraction=0.5, snapshot=sid)
    assert ok.status_code == 201, ok.get_json()
    assert ok.get_json()["designation_date"] == as_of.isoformat() and ok.get_json()["designation_snapshot"] == sid


def test_designating_again_with_an_old_snapshot_after_a_dedesignation_is_no_longer_a_150_percent_overlap(app, client, loan_trade):
    half = designate(client, loan_trade["id"], "floating_loan", _loan(), fraction=0.5).get_json()["id"]
    sid, _ = _later_snapshot(client)
    assert client.post("/api/hedges/%d/periods" % half, json={"snapshot": sid}).status_code == 201
    r = client.post(
        "/api/hedges/%d/dedesignate" % half, json={"snapshot": sid, "reason": "Prepago", "cause": "criteria_not_met"}
    )
    assert r.status_code == 201, r.get_json()
    before = _counts(app)

    retro = designate(client, loan_trade["id"], "floating_loan", _loan(), fraction=1.0)  # MX-DEMO es anterior a la desdesignación

    assert retro.status_code == 409 and retro.get_json()["field"] == "snapshot"
    assert _counts(app) == before
    same_day = designate(client, loan_trade["id"], "floating_loan", _loan(), fraction=1.0, snapshot=sid)
    assert same_day.status_code == 201, same_day.get_json()  # la desdesignada ese día ya no cuenta


def test_the_fraction_limit_counts_what_is_in_force_on_the_designation_date(client, loan_trade):
    first = designate(client, loan_trade["id"], "floating_loan", _loan(), fraction=0.5)
    assert first.status_code == 201, first.get_json()
    sid, _ = _later_snapshot(client)

    ok = designate(client, loan_trade["id"], "floating_loan", _loan(), fraction=0.5, snapshot=sid)
    over = designate(client, loan_trade["id"], "floating_loan", _loan(), fraction=0.1, snapshot=sid)

    assert ok.status_code == 201, ok.get_json()
    assert over.status_code == 409 and over.get_json()["field"] == "fraction"


def test_other_trades_do_not_constrain_the_designation_date(client, loan_trade):
    sid, _ = _later_snapshot(client)
    other = par_irs(client, "TIIE-F", 500e6, D0, LOAN_END)
    assert designate(client, other["id"], "floating_loan", _loan(), snapshot=sid).status_code == 201

    assert designate(client, loan_trade["id"], "floating_loan", _loan()).status_code == 201  # MX-DEMO, otra operación


# ------------------------------------------------------------------------- C6: avisos al designar

def _codes(body):
    return [w["code"] for w in body["warnings"]]


def test_a_clean_designation_has_no_warnings(client, loan_trade):
    r = designate(client, loan_trade["id"], "floating_loan", _loan())
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["created_at"] == CLOCK  # el reloj de las pruebas está fijado: el resultado no depende del día real
    assert r.get_json()["warnings"] == []
    assert r.get_json()["events"][0]["data"]["warnings"] == []


def test_a_relationship_without_economic_relationship_is_accepted_with_a_warning(client):
    trade = par_irs(client, "TIIE-F", 500e6, D0, LOAN_END, side="receiver")  # recibe fija: se mueve al revés que la deuda

    r = designate(client, trade["id"], "floating_loan", _loan(side="pays_floating"))

    assert r.status_code == 201, r.get_json()
    d = r.get_json()
    assert _codes(d) == ["no_economic_relationship"]
    assert set(d["warnings"][0]) == {"code", "message"} and "relación económica" in d["warnings"][0]["message"]
    assert d["events"][0]["data"]["warnings"] == d["warnings"]  # queda en el evento de designación
    assert client.get("/api/hedges/%d" % d["id"]).get_json()["warnings"] == d["warnings"]


def test_an_off_market_instrument_is_accepted_with_a_warning_that_states_its_value(client):
    trade = _book_at(client, D0.isoformat(), D0.isoformat(), LOAN_END.isoformat())  # fija 7 %, lejos de la par

    r = designate(client, trade["id"], "floating_loan", _loan())

    assert r.status_code == 201, r.get_json()
    d = r.get_json()
    assert _codes(d) == ["instrument_off_market"]
    assert abs(d["designation"]["pv_inst"]) > 1e-6 * 500e6
    assert "%.2f" % d["designation"]["pv_inst"] in d["warnings"][0]["message"]
    assert "inefectividad" in d["warnings"][0]["message"]


def test_a_forecast_flow_on_a_weekend_is_accepted_with_a_warning(client):
    saturday = date(2027, 5, 15)
    trade = market_forward(client, "buy", 10e6, saturday)

    r = designate(client, trade["id"], "forecast_fx", _fx(date=saturday.isoformat()))

    assert r.status_code == 201, r.get_json()
    assert _codes(r.get_json()) == ["forecast_date_weekend"]
    assert saturday.isoformat() in r.get_json()["warnings"][0]["message"]
    weekday = market_forward(client, "buy", 10e6, FX_END)  # martes
    assert designate(client, weekday["id"], "forecast_fx", _fx()).get_json()["warnings"] == []


def test_several_warnings_come_in_a_stable_order(client):
    saturday = date(2027, 5, 15)
    trade = market_forward(client, "sell", 10e6, saturday)  # vende USD: al revés de la compra pronosticada

    r = designate(client, trade["id"], "forecast_fx", _fx(date=saturday.isoformat(), side="buy_usd"))

    assert r.status_code == 201, r.get_json()
    assert _codes(r.get_json()) == ["no_economic_relationship", "forecast_date_weekend"]


# ------------------------------------------------------------------------- F5: documentación atrasada

def _clock(monkeypatch, iso):
    monkeypatch.setattr("desk.api.hedges.now_iso", lambda: iso)


def test_documenting_more_than_a_day_after_the_designation_date_warns_with_both_dates(monkeypatch, client, loan_trade):
    _clock(monkeypatch, "2026-11-13T09:30:00+00:00")  # tres días después del as_of de MX-DEMO

    r = designate(client, loan_trade["id"], "floating_loan", _loan())

    assert r.status_code == 201, r.get_json()
    d = r.get_json()
    assert _codes(d) == ["designation_backdated"]
    message = d["warnings"][0]["message"]
    assert "2026-11-13" in message and "2026-11-10" in message and "3 días" in message and "6.4.1(b)" in message
    assert d["created_at"] == "2026-11-13T09:30:00+00:00" and d["designation_date"] == "2026-11-10"
    assert d["events"][0]["data"]["warnings"] == d["warnings"]  # queda guardado con la designación
    assert client.get("/api/hedges/%d" % d["id"]).get_json()["warnings"] == d["warnings"]


def test_documenting_within_a_day_of_the_designation_date_does_not_warn(monkeypatch, client, loan_trade):
    _clock(monkeypatch, "2026-11-11T23:59:59+00:00")  # un día después: dentro de la holgura

    r = designate(client, loan_trade["id"], "floating_loan", _loan())

    assert r.status_code == 201, r.get_json()
    assert r.get_json()["warnings"] == []
    other = par_irs(client, "TIIE-F", 500e6, D0, LOAN_END)
    _clock(monkeypatch, "2026-11-12T00:00:00+00:00")  # dos días: ya avisa
    assert _codes(designate(client, other["id"], "floating_loan", _loan()).get_json()) == ["designation_backdated"]


def test_the_backdated_warning_goes_last_and_does_not_block(monkeypatch, client):
    saturday = date(2027, 5, 15)
    trade = market_forward(client, "sell", 10e6, saturday)
    _clock(monkeypatch, "2026-12-01T00:00:00+00:00")

    r = designate(client, trade["id"], "forecast_fx", _fx(date=saturday.isoformat(), side="buy_usd"))

    assert r.status_code == 201, r.get_json()
    assert _codes(r.get_json()) == ["no_economic_relationship", "forecast_date_weekend", "designation_backdated"]
