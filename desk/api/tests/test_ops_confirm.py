"""Corte 5, T4: `GET /api/trades/<id>/confirmation` para los siete productos."""
from datetime import date, timedelta

import pytest

from desk.api.market import CURVES
from desk.api.ops_confirm import NOTICES
from desk.api.qf import qfpy
from desk.api.tests.ops_fixture import ALFA, confirm_raw

COUNTERPARTY = ALFA
TERM_KEYS = {
    "irs": ["notional", "fixed_rate", "periods"],
    "fx_forward": ["notional_usd", "strike"],
    "fx_option": ["option_type", "notional_usd", "strike"],
    "cap_floor": ["cap_type", "notional", "strike", "periods"],
    "swaption": ["swaption_type", "notional", "strike", "expiry_years", "swap_tenor_years"],
    "bond": ["face", "coupon_rate", "periods", "frequency"],
    "equity_option": ["option_type", "quantity", "spot", "strike", "volatility", "rate",
                      "dividend_yield", "maturity_years"],
}
CONVENTION_KEYS = {
    "irs": ["index", "day_count", "payment_frequency", "compounding", "business_days"],
    "fx_forward": ["settlement", "business_days"],
    "fx_option": ["exercise", "settlement", "premium", "business_days"],
    "cap_floor": ["index", "day_count", "payment_frequency", "business_days"],
    "swaption": ["index", "exercise", "business_days"],
    "bond": ["day_count", "payment_frequency", "business_days"],
    "equity_option": ["exercise", "business_days"],
}
LABELS = {
    "irs": "Swap de tasa de interés (OIS)",
    "fx_forward": "Forward de tipo de cambio USD/MXN",
    "fx_option": "Opción de tipo de cambio USD/MXN",
    "cap_floor": "Cap / floor de tasa",
    "swaption": "Swaption europea",
    "bond": "Bono a tasa fija",
    "equity_option": "Opción de renta variable",
}
NEW_PARAMS = {
    "swaption": {"curve": "TIIE-F", "swaption_type": "payer", "notional": 100e6, "strike": 0.07,
                 "expiry_years": 1.0, "swap_tenor_years": 2.0},
    "bond": {"curve": "TIIE-F", "face": 1e8, "coupon_rate": 0.08, "periods": 6},
    "equity_option": {"option_type": "call", "spot": 100.0, "strike": 105.0, "volatility": 0.2,
                      "rate": 0.05, "dividend_yield": 0.01, "maturity_years": 1.0, "quantity": 10},
}


def _create(client, product, params):
    r = client.post("/api/trades", json={"product": product, "counterparty": COUNTERPARTY, "params": params})
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _confirmation(client, trade_id):
    r = client.get("/api/trades/%d/confirmation" % trade_id)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _trade_for(client, product):
    """Una operación de cada producto: las sembradas (1, 4, 6, 7) o una creada por POST."""
    seeded = {"irs": 1, "fx_forward": 4, "fx_option": 6, "cap_floor": 7}
    if product in seeded:
        return client.get("/api/trades/%d" % seeded[product]).get_json()
    return _create(client, product, NEW_PARAMS[product])


def _keys(rows):
    return [r["key"] for r in rows]


# ------------------------------------------------------------------------ forma común

@pytest.mark.parametrize("product", list(LABELS))
def test_every_product_has_the_contract_shape(client, product):
    trade = _trade_for(client, product)
    c = _confirmation(client, trade["id"])
    assert c["trade_id"] == trade["id"] and c["product"] == product
    assert c["product_label"] == LABELS[product]
    assert c["generated_at"]
    assert set(c["parties"]) == {"company", "counterparty", "company_role", "counterparty_role"}
    assert c["parties"]["counterparty"] == trade["counterparty"]
    assert c["bank_ref"] is None
    assert c["dates"] == {"trade_date": trade["trade_date"], "start_date": trade["start_date"],
                          "maturity_date": trade["maturity_date"]}
    assert _keys(c["terms"]) == TERM_KEYS[product]
    assert _keys(c["conventions"]) == CONVENTION_KEYS[product]
    assert c["schedule"], "el calendario no puede venir vacío"
    assert c["notices"] == list(NOTICES)
    assert c["events_note"] is None
    for row in c["terms"] + c["conventions"]:
        assert row["format"] in ("amount", "rate", "number", "text", "date")
        assert set(row) == {"key", "label", "value", "format", "currency"}
        assert row["label"]
    for step in c["schedule"]:
        assert set(step) == {"date", "description", "amount", "currency"}
        date.fromisoformat(step["date"])
        assert step["currency"] in ("MXN", "USD")


@pytest.mark.parametrize("product", list(LABELS))
def test_terms_are_the_agreed_params(client, product):
    trade = _trade_for(client, product)
    c = _confirmation(client, trade["id"])
    by_key = {r["key"]: r["value"] for r in c["terms"]}
    for key, value in trade["params"].items():
        if key in ("curve", "side", "days"):  # van en parties/conventions/dates, no en terms
            continue
        if key in ("option_type", "cap_type", "swaption_type"):
            assert isinstance(by_key[key], str)
        else:
            assert by_key[key] == value, key


def test_default_company_name_and_unknown_trade(client):
    c = _confirmation(client, 1)
    assert c["parties"]["company"] == "Empresa sin nombre (configurar en la confirmación)"
    r = client.get("/api/trades/999/confirmation")
    assert r.status_code == 404 and r.get_json()["field"] == "id"
    r = client.get("/api/trades/abc/confirmation")
    assert r.status_code == 404 and r.get_json()["field"] == "id"


def test_company_name_and_bank_ref_follow_their_settings(client):
    assert client.put("/api/settings", json={"company_name": "Tesorería Ejemplo, S.A. de C.V."}).status_code == 200
    assert client.put("/api/trades/1/ref", json={"ref": "BA-2026-0042"}).status_code == 200
    c = _confirmation(client, 1)
    assert c["parties"]["company"] == "Tesorería Ejemplo, S.A. de C.V."
    assert c["bank_ref"] == "BA-2026-0042"
    assert _confirmation(client, 2)["bank_ref"] is None  # la referencia es por operación
    assert client.put("/api/trades/1/ref", json={"ref": None}).status_code == 200
    assert _confirmation(client, 1)["bank_ref"] is None


# ------------------------------------------------------------------------------- irs

def _irs_tau(trade, pay):
    taus, previous = [], 0
    for k in pay:
        taus.append((k - previous) / 360.0)
        previous = k
    return taus


@pytest.mark.parametrize("trade_id, side_sign", [(1, -1), (2, 1), (3, -1)])
def test_irs_schedule_matches_payment_days_and_fixed_leg(client, trade_id, side_sign):
    trade = client.get("/api/trades/%d" % trade_id).get_json()
    p = trade["params"]
    c = _confirmation(client, trade_id)
    start = date.fromisoformat(trade["start_date"])
    pay = qfpy.ois_payment_days((date.fromisoformat(trade["maturity_date"]) - start).days,
                                CURVES[p["curve"]]["period_days"])
    assert len(c["schedule"]) == len(pay)
    assert [s["date"] for s in c["schedule"]] == [(start + timedelta(days=k)).isoformat() for k in pay]
    assert c["schedule"][-1]["date"] == trade["maturity_date"]
    currency = CURVES[p["curve"]]["currency"]
    assert {s["currency"] for s in c["schedule"]} == {currency}
    expected = side_sign * p["notional"] * p["fixed_rate"] * sum(_irs_tau(trade, pay))
    assert sum(s["amount"] for s in c["schedule"]) == pytest.approx(expected, rel=1e-12)
    assert c["schedule"][0]["description"] == "Cupón 1: pierna fija contra pierna variable"
    notional = c["terms"][0]
    assert notional["format"] == "amount" and notional["currency"] == currency
    assert c["terms"][1]["format"] == "rate" and c["terms"][1]["value"] == p["fixed_rate"]


def test_irs_roles_and_conventions_per_side(client):
    payer, receiver = _confirmation(client, 1), _confirmation(client, 2)
    assert (payer["parties"]["company_role"], payer["parties"]["counterparty_role"]) == (
        "Paga tasa fija", "Paga tasa variable")
    assert (receiver["parties"]["company_role"], receiver["parties"]["counterparty_role"]) == (
        "Paga tasa variable", "Paga tasa fija")
    conv = {r["key"]: r["value"] for r in payer["conventions"]}
    assert conv["index"] == "TIIE de Fondeo (TIIE-F)" and conv["day_count"] == "ACT/360"
    assert conv["payment_frequency"] == "Cada 28 días"
    assert "OIS" in conv["compounding"]
    sofr = {r["key"]: r["value"] for r in _confirmation(client, 3)["conventions"]}
    assert sofr["payment_frequency"] == "Cada 365 días" and "SOFR" in sofr["index"]


# --------------------------------------------------------------------------- forwards y opciones

@pytest.mark.parametrize("trade_id, roles", [(4, ("Compra", "Vende")), (5, ("Vende", "Compra")),
                                             (6, ("Compra", "Vende"))])
def test_fx_roles_and_single_settlement_row(client, trade_id, roles):
    trade = client.get("/api/trades/%d" % trade_id).get_json()
    c = _confirmation(client, trade_id)
    assert (c["parties"]["company_role"], c["parties"]["counterparty_role"]) == roles
    assert len(c["schedule"]) == 1
    step = c["schedule"][0]
    assert step["date"] == trade["maturity_date"] and step["amount"] is None and step["currency"] == "MXN"
    usd = [r for r in c["terms"] if r["key"] == "notional_usd"][0]
    assert usd["currency"] == "USD" and usd["format"] == "amount" and usd["label"] == "Nocional (USD)"


def test_fx_forward_and_option_specific_texts(client):
    fwd = _confirmation(client, 4)
    assert fwd["schedule"][0]["description"] == "Liquidación por diferencias: nocional × (FIX − strike)"
    conv = {r["key"]: r["value"] for r in fwd["conventions"]}
    assert conv["settlement"] == "Por diferencias en MXN con el FIX USD/MXN del vencimiento"
    assert [r["label"] for r in fwd["terms"]] == ["Nocional (USD)", "Tipo de cambio pactado"]
    opt = _confirmation(client, 6)
    conv = {r["key"]: r["value"] for r in opt["conventions"]}
    assert conv["exercise"] == "Europea" and conv["premium"] == "Prima no registrada en QF Desk"
    assert opt["terms"][0]["value"] == "Call" and opt["terms"][0]["label"] == "Tipo de opción"
    put = _create(client, "fx_option", {"side": "sell", "option_type": "put", "notional_usd": 1e6,
                                        "strike": 19.0, "days": 90})
    c = _confirmation(client, put["id"])
    assert c["terms"][0]["value"] == "Put"
    assert (c["parties"]["company_role"], c["parties"]["counterparty_role"]) == ("Vende", "Compra")


# ----------------------------------------------------------------------- cap/floor, swaption, bono, acción

def test_cap_floor_has_one_row_per_period(client):
    trade = client.get("/api/trades/7").get_json()
    p = trade["params"]
    c = _confirmation(client, 7)
    start = date.fromisoformat(trade["start_date"])
    assert len(c["schedule"]) == p["periods"]
    assert [s["date"] for s in c["schedule"]] == [
        (start + timedelta(days=k * 28)).isoformat() for k in range(1, p["periods"] + 1)]
    assert c["schedule"][-1]["date"] == trade["maturity_date"]
    assert all(s["amount"] is None for s in c["schedule"])
    assert c["terms"][0]["value"] == ("Cap" if p["cap_type"] == "cap" else "Floor")
    assert c["terms"][2]["format"] == "rate"
    conv = {r["key"]: r["value"] for r in c["conventions"]}
    assert conv["day_count"] == "ACT/360" and conv["payment_frequency"] == "Cada 28 días"
    assert (c["parties"]["company_role"], c["parties"]["counterparty_role"]) == ("Compra", "Vende")


def test_floor_describes_the_floor_condition(client):
    floor = _create(client, "cap_floor", {"curve": "TIIE-F", "cap_type": "floor", "notional": 1e8,
                                          "strike": 0.05, "periods": 3})
    c = _confirmation(client, floor["id"])
    assert c["terms"][0]["value"] == "Floor"
    assert len(c["schedule"]) == 3 and "por debajo" in c["schedule"][0]["description"]


def test_swaption_expires_on_maturity_date(client):
    trade = _create(client, "swaption", NEW_PARAMS["swaption"])
    c = _confirmation(client, trade["id"])
    assert len(c["schedule"]) == 1
    assert c["schedule"][0]["date"] == trade["maturity_date"] and c["schedule"][0]["amount"] is None
    assert c["terms"][0]["value"] == "Pagadora"
    assert [r["label"] for r in c["terms"]][3:] == ["Expiración (años)", "Plazo del swap (años)"]
    assert {r["key"]: r["value"] for r in c["conventions"]}["exercise"] == "Europea"
    recv = _create(client, "swaption", {**NEW_PARAMS["swaption"], "swaption_type": "receiver"})
    assert _confirmation(client, recv["id"])["terms"][0]["value"] == "Receptora"


@pytest.mark.parametrize("frequency, expected", [(None, "2 veces al año"), (4.0, "4 veces al año"),
                                                 (0.5, "0.5 veces al año")])
def test_bond_schedule_pays_coupons_and_principal(client, frequency, expected):
    params = dict(NEW_PARAMS["bond"])
    if frequency is not None:
        params["frequency"] = frequency
    trade = _create(client, "bond", params)
    p = trade["params"]
    c = _confirmation(client, trade["id"])
    coupon = p["face"] * p["coupon_rate"] / p["frequency"]
    steps = c["schedule"]
    assert len(steps) == p["periods"]
    assert all(s["amount"] == pytest.approx(coupon, rel=1e-12) for s in steps[:-1])
    assert steps[-1]["amount"] == pytest.approx(coupon + p["face"], rel=1e-12)
    assert steps[-1]["date"] == trade["maturity_date"]
    dates = [s["date"] for s in steps]
    assert dates == sorted(dates)
    conv = {r["key"]: r["value"] for r in c["conventions"]}
    assert conv["payment_frequency"] == expected and conv["day_count"] == "ACT/365"
    assert (c["parties"]["company_role"], c["parties"]["counterparty_role"]) == ("Tenedor", "Emisor")
    assert c["terms"][0]["currency"] == "MXN" and c["terms"][1]["format"] == "rate"


def test_equity_option_terms_labels_and_formats(client):
    trade = _create(client, "equity_option", NEW_PARAMS["equity_option"])
    c = _confirmation(client, trade["id"])
    assert [r["label"] for r in c["terms"]] == [
        "Tipo de opción", "Cantidad", "Spot", "Strike", "Volatilidad", "Tasa",
        "Rendimiento por dividendo", "Plazo (años)"]
    fmt = {r["key"]: r["format"] for r in c["terms"]}
    assert fmt["volatility"] == fmt["rate"] == fmt["dividend_yield"] == "rate"
    assert len(c["schedule"]) == 1 and c["schedule"][0]["date"] == trade["maturity_date"]
    assert (c["parties"]["company_role"], c["parties"]["counterparty_role"]) == ("Compra", "Vende")


# ------------------------------------------------------------------------------- eventos

def test_events_note_lists_post_agreement_events_in_spanish(client):
    t = _create(client, "fx_forward", {"side": "buy", "notional_usd": 1e6, "strike": 19.5, "days": 120})
    assert _confirmation(client, t["id"])["events_note"] is None
    r = client.post("/api/trades/%d/events" % t["id"], json={
        "type": "quantity_change", "event_date": "2026-11-20", "data": {"notional": 5e5}})
    assert r.status_code == 201, r.get_json()
    note = _confirmation(client, t["id"])["events_note"]
    assert note == ("La operación tiene eventos posteriores al pacto (cambio de nocional): "
                    "esta confirmación muestra los términos pactados.")


def test_settlement_confirmations_do_not_trigger_the_note(app, client):
    confirm_raw(app, 1, date(2026, 11, 8), 1000.0)
    assert _confirmation(client, 1)["events_note"] is None


def test_confirmation_shows_agreed_terms_not_current_ones(client):
    t = _create(client, "fx_forward", {"side": "buy", "notional_usd": 1e6, "strike": 19.5, "days": 120})
    client.post("/api/trades/%d/events" % t["id"], json={
        "type": "quantity_change", "event_date": "2026-11-20", "data": {"notional": 5e5}})
    c = _confirmation(client, t["id"])
    assert [r["value"] for r in c["terms"] if r["key"] == "notional_usd"] == [1e6]


def test_repeated_event_types_are_listed_once(client):
    t = _create(client, "fx_forward", {"side": "buy", "notional_usd": 1e6, "strike": 19.5, "days": 120})
    for day, n in (("2026-11-20", 8e5), ("2026-11-25", 6e5)):
        r = client.post("/api/trades/%d/events" % t["id"], json={
            "type": "quantity_change", "event_date": day, "data": {"notional": n}})
        assert r.status_code == 201, r.get_json()
    assert _confirmation(client, t["id"])["events_note"].count("cambio de nocional") == 1

