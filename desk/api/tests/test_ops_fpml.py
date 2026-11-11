"""FpML (corte 5, T5): ida y vuelta de `irs`, `fx_forward` y `fx_option`, e importación segura."""
import math
import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import date

import pytest

from desk.api import fpml
from desk.api.tests.ops_fixture import ALFA, confirm_raw, fx_trade, irs_trade, own_pv

GAMMA = "Banco Gamma (sintético)"
COMPANY = "Tesorería Ejemplo, S.A. de C.V."

VARIANTS = {
    "irs-tiie-payer": lambda c: irs_trade(c),
    "irs-tiie-receiver-start-later": lambda c: irs_trade(
        c, side="receiver", notional=250e6, periods=30, start="2026-12-01", fixed_rate=0.0712
    ),
    "irs-sofr-payer-other-maturity": lambda c: irs_trade(
        c, curve="SOFR", notional=20e6, periods=3, counterparty=GAMMA
    ),
    "fwd-buy": lambda c: fx_trade(c, "fx_forward"),
    "fwd-sell": lambda c: fx_trade(c, "fx_forward", side="sell", notional_usd=3e6, strike=19.123456, days=200),
    "fwd-other-strike-term": lambda c: fx_trade(c, "fx_forward", strike=21.25, days=45, counterparty=GAMMA),
    "opt-buy-call": lambda c: fx_trade(c, "fx_option"),
    "opt-sell-put": lambda c: fx_trade(c, "fx_option", side="sell", option_type="put", strike=18.75, days=90),
    "opt-buy-put": lambda c: fx_trade(c, "fx_option", option_type="put", notional_usd=2.5e6, strike=20.5, days=300),
}


def _count(app):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        return conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    finally:
        conn.close()


def _export(client, trade_id):
    r = client.get("/api/trades/%d/fpml" % trade_id)
    assert r.status_code == 200, r.get_json()
    return r


def _post(client, xml):
    data = xml.encode("utf-8") if isinstance(xml, str) else xml
    return client.post("/api/trades/fpml", data=data, content_type="application/xml")


def _set_company(client, name):
    assert client.put("/api/settings", json={"company_name": name}).status_code == 200


def _close(a, b):
    if isinstance(a, float) or isinstance(b, float):
        return math.isclose(a, b, rel_tol=1e-12)
    return a == b


def _assert_same_params(old, new):
    assert old.keys() == new.keys()
    for key in old:
        assert _close(old[key], new[key]), (key, old[key], new[key])


def _assert_rejected(app, client, payload, snippet=None, field="fpml"):
    before = _count(app)
    r = _post(client, payload)
    assert r.status_code == 400, r.get_data(as_text=True)[:300]
    body = r.get_json()
    assert body["field"] == field
    if snippet is not None:
        assert snippet in body["error"], body["error"]
    assert _count(app) == before  # sin efectos
    return body


# --------------------------------------------------------------------- ida y vuelta

@pytest.mark.parametrize("name", list(VARIANTS))
def test_round_trip_keeps_terms_dates_counterparty_and_pv(app, client, name):
    _set_company(client, COMPANY)
    old = VARIANTS[name](client)
    exported = _export(client, old["id"])
    assert exported.headers["Content-Type"] == "application/xml; charset=utf-8"
    assert exported.headers["Content-Disposition"] == 'attachment; filename="operacion-%d.fpml.xml"' % old["id"]

    r = _post(client, exported.get_data(as_text=True))
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["warnings"] == []  # party1 lleva el nombre de la empresa
    new = body["trade"]

    assert new["id"] != old["id"]
    assert new["product"] == old["product"]
    _assert_same_params(old["params"], new["params"])
    for key in ("trade_date", "start_date", "maturity_date", "counterparty", "notional", "currency"):
        assert new[key] == old[key], key
    pv_old, pv_new = own_pv(app, old["id"]), own_pv(app, new["id"])
    scale = abs(pv_old) if abs(pv_old) > 1e-6 * old["notional"] else old["notional"]
    assert abs(pv_new - pv_old) <= 1e-9 * scale


def test_exported_document_has_the_contract_shape(app, client):
    _set_company(client, COMPANY)
    t = irs_trade(client, fixed_rate=0.068)
    text = _export(client, t["id"]).get_data(as_text=True)
    assert text.startswith("<?xml version='1.0' encoding='utf-8'?>\n")
    assert 'xmlns="%s"' % fpml.FPML_NS in text and 'fpmlVersion="5-12"' in text
    assert "Tesorería Ejemplo" in text  # UTF-8 sin escapar
    root = ET.fromstring(text)
    assert root.tag == "{%s}dataDocument" % fpml.FPML_NS
    ns = {"f": fpml.FPML_NS}
    trade_id = root.find("f:trade/f:tradeHeader/f:partyTradeIdentifier/f:tradeId", ns)
    assert trade_id.text == str(t["id"]) and trade_id.get("tradeIdScheme") == fpml.TRADE_ID_SCHEME
    assert root.find("f:trade/f:tradeHeader/f:tradeDate", ns).text == t["trade_date"]
    streams = root.findall("f:trade/f:swap/f:swapStream", ns)
    assert [s.get("id") for s in streams] == ["fixedLeg", "floatingLeg"]
    # payer = la empresa (party1) paga la pierna fija
    assert streams[0].find("f:payerPartyReference", ns).get("href") == "party1"
    assert streams[1].find("f:payerPartyReference", ns).get("href") == "party2"
    assert streams[0].find(".//f:fixedRateSchedule/f:initialValue", ns).text == "0.068"
    assert streams[1].find(".//f:floatingRateIndex", ns).text == "MXN-TIIE-ON-OIS Compound"
    assert [(s.find(".//f:periodMultiplier", ns).text, s.find(".//f:period", ns).text) for s in streams] == [
        ("28", "D"), ("28", "D")]
    assert [p.find("f:partyName", ns).text for p in root.findall("f:party", ns)] == [COMPANY, ALFA]


def test_sofr_uses_a_yearly_frequency(client):
    t = irs_trade(client, curve="SOFR", notional=20e6, periods=2)
    root = ET.fromstring(_export(client, t["id"]).get_data(as_text=True))
    ns = {"f": fpml.FPML_NS}
    stream = root.find("f:trade/f:swap/f:swapStream", ns)
    assert (stream.find(".//f:periodMultiplier", ns).text, stream.find(".//f:period", ns).text) == ("1", "Y")
    assert root.find(".//f:floatingRateIndex", ns).text == "USD-SOFR-OIS Compound"
    assert root.find(".//f:notionalStepSchedule/f:currency", ns).text == "USD"


def test_fx_amounts_and_sides_in_the_exported_document(client):
    ns = {"f": fpml.FPML_NS}
    buy = fx_trade(client, "fx_forward", side="buy", notional_usd=1e6, strike=20.0)
    root = ET.fromstring(_export(client, buy["id"]).get_data(as_text=True))
    usd = root.find(".//f:exchangedCurrency1", ns)
    assert usd.find("f:receiverPartyReference", ns).get("href") == "party1"  # buy = la empresa recibe USD
    assert usd.find("f:paymentAmount/f:amount", ns).text == "1000000.0"
    assert root.find(".//f:exchangedCurrency2/f:paymentAmount/f:amount", ns).text == "20000000.0"
    assert root.find(".//f:exchangeRate/f:rate", ns).text == "20.0"

    put = fx_trade(client, "fx_option", side="sell", option_type="put", notional_usd=1e6, strike=20.0)
    root = ET.fromstring(_export(client, put["id"]).get_data(as_text=True))
    assert root.find(".//f:buyerPartyReference", ns).get("href") == "party2"
    assert root.find(".//f:putCurrencyAmount/f:currency", ns).text == "USD"
    assert root.find(".//f:callCurrencyAmount/f:currency", ns).text == "MXN"
    assert root.find(".//f:strikeQuoteBasis", ns).text == "CallCurrencyPerPutCurrency"


# --------------------------------------------------------- la empresa y la contraparte

def test_company_name_match_means_no_warning_and_other_name_warns(client):
    t = irs_trade(client, fixed_rate=0.07)
    xml = _export(client, t["id"]).get_data(as_text=True)  # party1 = nombre por omisión
    assert _post(client, xml).get_json()["warnings"] == []

    _set_company(client, "Otra Empresa, S.A.")
    r = _post(client, xml)
    assert r.status_code == 201
    body = r.get_json()
    assert [w["code"] for w in body["warnings"]] == ["party_assumed"]
    assert body["warnings"][0]["message"] == (
        "Ninguna parte coincide con el nombre de la empresa: se tomó party1 como la empresa")
    # se tomó party1 como la empresa: mismo lado y misma contraparte
    assert body["trade"]["params"]["side"] == t["params"]["side"]
    assert body["trade"]["counterparty"] == ALFA


def test_company_matched_as_party2_flips_the_side_and_the_counterparty(client):
    t = irs_trade(client, side="payer", fixed_rate=0.07)
    xml = _export(client, t["id"]).get_data(as_text=True)
    _set_company(client, ALFA)  # ahora la empresa es la que el documento llama party2
    body = _post(client, xml).get_json()
    assert body["warnings"] == []
    assert body["trade"]["params"]["side"] == "receiver"
    assert body["trade"]["counterparty"] != ALFA


@pytest.mark.parametrize("product", ["fx_forward", "fx_option"])
def test_company_matched_as_party2_flips_fx_side(client, product):
    t = fx_trade(client, product, side="buy")
    xml = _export(client, t["id"]).get_data(as_text=True)
    _set_company(client, ALFA)
    new = _post(client, xml).get_json()["trade"]
    assert new["params"]["side"] == "sell"


# ------------------------------------------------------------------------ exportar: rechazos

def test_export_unsupported_product_is_400_product(client):
    r = client.get("/api/trades/7/fpml")  # cap_floor de la siembra
    assert r.status_code == 400 and r.get_json()["field"] == "product"


@pytest.mark.parametrize("raw", ["999", "abc"])
def test_export_unknown_trade_is_404_id(client, raw):
    r = client.get("/api/trades/%s/fpml" % raw)
    assert r.status_code == 404 and r.get_json()["field"] == "id"


def test_export_with_a_lifecycle_event_is_409_id(client):
    t = irs_trade(client, fixed_rate=0.07)
    r = client.post(
        "/api/trades/%d/events" % t["id"],
        json={"type": "quantity_change", "event_date": "2026-11-12", "data": {"notional": 50e6}},
    )
    assert r.status_code == 201, r.get_json()
    r = client.get("/api/trades/%d/fpml" % t["id"])
    assert r.status_code == 409
    assert r.get_json()["field"] == "id"
    assert "eventos posteriores al pacto" in r.get_json()["error"]


def test_export_ignores_settlement_confirmations(app, client):
    t = irs_trade(client, fixed_rate=0.07)
    confirm_raw(app, t["id"], date(2026, 12, 8), 123.0)
    assert client.get("/api/trades/%d/fpml" % t["id"]).status_code == 200


@pytest.mark.parametrize("product, params", [
    ("fx_forward", {"side": "buy", "notional_usd": 1e6, "strike": 19.5, "days": 60}),
    ("fx_option", {"side": "buy", "option_type": "call", "notional_usd": 1e6, "strike": 19.5, "days": 60}),
])
def test_export_fx_with_start_after_trade_date_is_409_id(client, product, params):
    r = client.post("/api/trades", json={
        "product": product, "counterparty": ALFA, "params": params,
        "trade_date": "2026-11-10", "start_date": "2026-11-12",
    })
    assert r.status_code == 201, r.get_json()
    r = client.get("/api/trades/%d/fpml" % r.get_json()["id"])
    assert r.status_code == 409 and r.get_json()["field"] == "id"


# ------------------------------------------------------------------------ importar: rechazos

@pytest.fixture
def irs_xml(client):
    t = irs_trade(client, fixed_rate=0.068)
    return _export(client, t["id"]).get_data(as_text=True)


@pytest.fixture
def fwd_xml(client):
    return _export(client, fx_trade(client, "fx_forward")["id"]).get_data(as_text=True)


@pytest.fixture
def opt_xml(client):
    return _export(client, fx_trade(client, "fx_option")["id"]).get_data(as_text=True)


def test_import_empty_and_blank_body(app, client):
    _assert_rejected(app, client, b"", "vacío")
    _assert_rejected(app, client, b"  \n ", "vacío")


def test_import_oversize_body(app, client, irs_xml):
    big = irs_xml.replace("</dataDocument>", "<!-- " + "x" * fpml.MAX_FPML_BYTES + " --></dataDocument>")
    _assert_rejected(app, client, big, str(fpml.MAX_FPML_BYTES))


def test_import_truncated_xml(app, client, irs_xml):
    _assert_rejected(app, client, irs_xml[: len(irs_xml) // 2], "XML mal formado")


def test_import_not_utf8(app, client, irs_xml):
    _assert_rejected(app, client, irs_xml.encode("utf-16"), "UTF-8")
    _assert_rejected(app, client, b"<a>\xff\xfe</a>", "UTF-8")


def test_import_external_entity_is_rejected_before_parsing(app, client, irs_xml):
    evil = irs_xml.replace(
        "<dataDocument",
        '<!DOCTYPE dataDocument [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>\n<dataDocument',
        1,
    ).replace(">Banco Alfa", ">&xxe;Banco Alfa", 1)
    assert "&xxe;" in evil
    body = _assert_rejected(app, client, evil, "DTD o entidades")
    assert "root:" not in body["error"]


def test_import_internal_entity_billion_laughs(app, client, irs_xml):
    lolz = ['<!ENTITY lol0 "lol">']
    for i in range(1, 9):
        lolz.append('<!ENTITY lol%d "%s">' % (i, "&lol%d;" % (i - 1) * 10))
    evil = irs_xml.replace(
        "<dataDocument", "<!DOCTYPE lolz [%s]>\n<dataDocument" % "".join(lolz), 1
    ).replace(">Banco Alfa", ">&lol8;", 1)
    _assert_rejected(app, client, evil, "DTD o entidades")


@pytest.mark.parametrize("marker", ["<!doctype x>", "<!DoCtYpE x>", "<!ENTITY a 'b'>", "<! DOCTYPE x>"])
def test_import_dtd_markers_are_case_insensitive(app, client, irs_xml, marker):
    _assert_rejected(app, client, irs_xml.replace("<trade>", marker + "<trade>", 1), "DTD o entidades")


def test_import_foreign_root(app, client, irs_xml):
    _assert_rejected(app, client, irs_xml.replace("dataDocument", "otroDocumento"), "dataDocument")
    _assert_rejected(app, client, irs_xml.replace(fpml.FPML_NS, "http://example.com/otro"), "dataDocument")
    _assert_rejected(app, client, b"<dataDocument/>", "dataDocument")


def test_import_unsupported_product(app, client, irs_xml):
    bond = re.sub(r"<swap>.*</swap>", "<bond><productType>Bond</productType></bond>", irs_xml, flags=re.S)
    assert "<bond>" in bond
    _assert_rejected(app, client, bond, "Producto FpML no soportado: bond")


def test_import_missing_trade_and_product(app, client, irs_xml):
    no_trade = re.sub(r"<trade>.*</trade>", "", irs_xml, flags=re.S)
    _assert_rejected(app, client, no_trade, "<trade>")
    no_product = re.sub(r"<swap>.*</swap>", "", irs_xml, flags=re.S)
    _assert_rejected(app, client, no_product, "producto")


def test_import_more_than_one_trade(app, client, irs_xml):
    two = re.sub(r"(<trade>.*</trade>)", r"\1\1", irs_xml, count=1, flags=re.S)
    _assert_rejected(app, client, two, "más de una <trade>")


def test_import_missing_fixed_rate_schedule(app, client, irs_xml):
    broken = re.sub(r"<fixedRateSchedule>.*?</fixedRateSchedule>", "", irs_xml, flags=re.S)
    assert "fixedRateSchedule" not in broken
    _assert_rejected(app, client, broken, "fixedRateSchedule")


def test_import_unknown_index(app, client, irs_xml):
    _assert_rejected(
        app, client, irs_xml.replace("MXN-TIIE-ON-OIS Compound", "USD-LIBOR-BBA"),
        "Índice de tasa no soportado: USD-LIBOR-BBA",
    )


def test_import_two_fixed_legs(app, client, irs_xml):
    two_fixed = re.sub(
        r"<floatingRateCalculation>.*?</floatingRateCalculation>",
        "<fixedRateSchedule><initialValue>0.07</initialValue></fixedRateSchedule>", irs_xml, flags=re.S)
    _assert_rejected(app, client, two_fixed, "una pierna fija y una variable")


def test_import_negative_notional_passes_the_trade_validation(app, client, irs_xml):
    negative = re.sub(r"(<notionalStepSchedule>\s*<initialValue>)[^<]*", r"\g<1>-5.0", irs_xml)
    assert "<initialValue>-5.0</initialValue>" in negative
    _assert_rejected(app, client, negative, field="notional")


def test_import_maturity_before_start_passes_the_trade_validation(app, client, irs_xml):
    broken = re.sub(r"(<terminationDate>\s*<unadjustedDate>)[^<]*", r"\g<1>2020-01-01", irs_xml)
    _assert_rejected(app, client, broken, field="maturity_date")


def test_import_party_reference_to_an_undeclared_party(app, client, irs_xml):
    broken = irs_xml.replace('<payerPartyReference href="party1" />', '<payerPartyReference href="partyX" />', 1)
    assert "partyX" in broken
    _assert_rejected(app, client, broken, "partyX")


def test_import_needs_exactly_two_parties_with_names(app, client, irs_xml):
    _assert_rejected(app, client, re.sub(r'<party id="party2">.*?</party>', "", irs_xml, flags=re.S), "dos <party>")
    _assert_rejected(app, client, irs_xml.replace("<partyName>Banco Alfa (sintético)</partyName>", ""), "partyName")


def test_import_legs_must_agree(app, client, irs_xml):
    # El nocional de la pierna variable difiere del de la fija.
    first, second = [m.start() for m in re.finditer(r"<notionalStepSchedule>", irs_xml)]
    head, tail = irs_xml[:second], irs_xml[second:]
    tail = re.sub(r"<initialValue>[^<]*</initialValue>", "<initialValue>1.0</initialValue>", tail, count=1)
    _assert_rejected(app, client, head + tail, "fechas y nocional")
    # Las dos piernas las paga la misma parte.
    mid = irs_xml.index('<swapStream id="floatingLeg">')
    swapped = (irs_xml[:mid] + irs_xml[mid:]
               .replace('payerPartyReference href="party2"', 'payerPartyReference href="TMP"', 1)
               .replace('receiverPartyReference href="party1"', 'receiverPartyReference href="party2"', 1)
               .replace('payerPartyReference href="TMP"', 'payerPartyReference href="party1"', 1))
    _assert_rejected(app, client, swapped, "pagadores opuestos")
    # Una pierna con el mismo pagador y receptor.
    same_party = irs_xml.replace('<receiverPartyReference href="party2" />', '<receiverPartyReference href="party1" />', 1)
    _assert_rejected(app, client, same_party, "la misma parte")


def test_import_unsupported_frequency_and_day_count(app, client, irs_xml):
    _assert_rejected(app, client, irs_xml.replace("<periodMultiplier>28</periodMultiplier>", "<periodMultiplier>91</periodMultiplier>"), "periodMultiplier")
    _assert_rejected(app, client, irs_xml.replace("ACT/360", "30/360"), "dayCountFraction")


@pytest.mark.parametrize("bad", ["abc", "nan", "inf", "1_0", "", "1e999"])
def test_import_unreadable_numbers_name_the_element(app, client, irs_xml, bad):
    broken = irs_xml.replace("<initialValue>0.068</initialValue>", "<initialValue>%s</initialValue>" % bad)
    _assert_rejected(app, client, broken, "fixedRateSchedule/initialValue")


def test_import_bad_date_names_the_element(app, client, irs_xml):
    broken = re.sub(r"<tradeDate>[^<]*", "<tradeDate>10/11/2026", irs_xml)
    _assert_rejected(app, client, broken, "tradeDate")


def test_import_fx_forward_requires_its_elements(app, client, fwd_xml):
    _assert_rejected(app, client, re.sub(r"<exchangeRate>.*?</exchangeRate>", "", fwd_xml, flags=re.S), "exchangeRate")
    _assert_rejected(app, client, re.sub(r"<valueDate>.*?</valueDate>", "", fwd_xml, flags=re.S), "valueDate")
    _assert_rejected(app, client, fwd_xml.replace("Currency2PerCurrency1", "Currency1PerCurrency2"), "quoteBasis")
    _assert_rejected(app, client, fwd_xml.replace("<currency>MXN</currency>", "<currency>EUR</currency>"), "USD y otro en MXN")


def test_import_fx_option_requires_its_elements(app, client, opt_xml):
    _assert_rejected(app, client, re.sub(r"<europeanExercise>.*?</europeanExercise>", "", opt_xml, flags=re.S), "europeanExercise")
    _assert_rejected(app, client, opt_xml.replace("PutCurrencyPerCallCurrency", "CallCurrencyPerPutCurrency"), "strikeQuoteBasis")
    _assert_rejected(app, client, opt_xml.replace("<currency>MXN</currency>", "<currency>EUR</currency>"), "USD y MXN")


# ------------------------------------------------------------------------ importar: detalles

def test_forward_strike_comes_from_rate_not_from_the_mxn_amount(client):
    t = fx_trade(client, "fx_forward", notional_usd=1e6, strike=19.5)
    xml = _export(client, t["id"]).get_data(as_text=True)
    assert "<amount>19500000.0</amount>" in xml
    tampered = xml.replace("<amount>19500000.0</amount>", "<amount>1.0</amount>")
    new = _post(client, tampered).get_json()["trade"]
    assert new["params"]["strike"] == 19.5


def test_import_accepts_any_content_type_and_ignores_a_bom(client):
    t = fx_trade(client, "fx_forward")
    xml = _export(client, t["id"]).get_data()
    for content_type in ("application/xml", "text/plain", "application/json"):
        r = client.post("/api/trades/fpml", data=xml, content_type=content_type)
        assert r.status_code == 201, content_type
    r = client.post("/api/trades/fpml", data=b"\xef\xbb\xbf" + xml, content_type="text/xml")
    assert r.status_code == 201


def test_import_response_is_the_public_trade_and_it_is_persisted(client):
    t = irs_trade(client, fixed_rate=0.0705, periods=26)
    r = _post(client, _export(client, t["id"]).get_data(as_text=True))
    assert r.status_code == 201
    new = r.get_json()["trade"]
    assert set(new) == set(t)
    stored = client.get("/api/trades/%d" % new["id"]).get_json()
    assert stored["params"] == new["params"] and stored["counterparty"] == ALFA


def test_import_irs_maturity_is_fitted_to_whole_periods_like_the_trade_form(client):
    t = irs_trade(client, fixed_rate=0.07, periods=10)
    xml = _export(client, t["id"]).get_data(as_text=True)
    odd = re.sub(r"(<terminationDate>\s*<unadjustedDate>)[^<]*", r"\g<1>%s" % "2027-08-31", xml)
    new = _post(client, odd).get_json()["trade"]
    days = (date.fromisoformat(new["maturity_date"]) - date.fromisoformat(new["start_date"])).days
    assert days == new["params"]["periods"] * 28
