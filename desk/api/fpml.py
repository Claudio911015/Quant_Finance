"""FpML 5.12 (vista de confirmación) de `irs`, `fx_forward` y `fx_option` (corte 5).

Solo biblioteca estándar (`xml.etree.ElementTree`): ni red ni archivos. Exporta un
`dataDocument` con la empresa como `party1` y la contraparte como `party2`; importa
exactamente los elementos que exporta y rechaza lo que no puede representar fielmente.
La importación no es una validación contra el esquema XSD.
"""
import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any, Dict, List, Tuple

from desk.api import ops_settings, ops_settlements, portfolio
from desk.api.errors import ApiError
from desk.api.market import CURVES
from desk.api.validation import finite_number, iso_date

FPML_NS = "http://www.fpml.org/FpML-5/confirmation"
FPML_VERSION = "5-12"
FPML_PRODUCTS = ("irs", "fx_forward", "fx_option")
MAX_FPML_BYTES = 1000000
INDEX_TO_FPML = {"TIIE-F": "MXN-TIIE-ON-OIS Compound", "SOFR": "USD-SOFR-OIS Compound"}
TRADE_ID_SCHEME = "urn:qf-desk:trade-id"

FPML_TO_INDEX = {v: k for k, v in INDEX_TO_FPML.items()}
_COMPANY = "party1"
_COUNTERPARTY = "party2"
_DAY_COUNT = "ACT/360"
_PARTY_REFS = ("partyReference", "payerPartyReference", "receiverPartyReference",
               "buyerPartyReference", "sellerPartyReference")

ET.register_namespace("", FPML_NS)  # el documento sale con xmlns por omisión, sin prefijos


def _q(name: str) -> str:
    return "{%s}%s" % (FPML_NS, name)


def _qpath(path: str) -> str:
    return "/".join(_q(part) for part in path.split("/"))


def _frequency(curve: str) -> Tuple[int, str]:
    """`(multiplicador, periodo)` de pago de la curva: TIIE-F `28 D`, SOFR `1 Y`."""
    days = CURVES[curve]["period_days"]
    return (1, "Y") if days == 365 else (days, "D")


# =============================================================================== exportar

def _sub(parent: ET.Element, name: str, value: Any = None, **attrs: str) -> ET.Element:
    el = ET.SubElement(parent, _q(name), attrs)
    if value is not None:
        el.text = value
    return el


def _ref(parent: ET.Element, name: str, party: str) -> ET.Element:
    return _sub(parent, name, href=party)


def _num(value: float) -> str:
    return repr(float(value))  # ida y vuelta exacta


def _unadjusted(parent: ET.Element, name: str, day: date) -> None:
    el = _sub(parent, name)
    _sub(el, "unadjustedDate", day.isoformat())
    _sub(_sub(el, "dateAdjustments"), "businessDayConvention", "NONE")


def _indent(el: ET.Element, level: int = 0) -> None:
    """Sangría de dos espacios (`ET.indent` no existe en Python 3.8)."""
    children = list(el)
    if not children:
        return
    pad = "\n" + "  " * (level + 1)
    el.text = pad
    for child in children:
        _indent(child, level + 1)
        child.tail = pad
    children[-1].tail = "\n" + "  " * level


def _swap_stream(swap: ET.Element, kind: str, payer: str, receiver: str,
                 trade: Dict[str, Any]) -> None:
    p = trade["params"]
    mult, unit = _frequency(p["curve"])
    stream = _sub(swap, "swapStream", id=kind + "Leg")
    _ref(stream, "payerPartyReference", payer)
    _ref(stream, "receiverPartyReference", receiver)
    dates = _sub(stream, "calculationPeriodDates", id=kind + "LegCalcDates")
    _unadjusted(dates, "effectiveDate", trade["start_date"])
    _unadjusted(dates, "terminationDate", trade["maturity_date"])
    freq = _sub(dates, "calculationPeriodFrequency")
    _sub(freq, "periodMultiplier", str(mult))
    _sub(freq, "period", unit)
    _sub(freq, "rollConvention", "NONE")
    paying = _sub(stream, "paymentDates")
    _ref(paying, "calculationPeriodDatesReference", kind + "LegCalcDates")
    pay_freq = _sub(paying, "paymentFrequency")
    _sub(pay_freq, "periodMultiplier", str(mult))
    _sub(pay_freq, "period", unit)
    _sub(paying, "payRelativeTo", "CalculationPeriodEndDate")
    calc = _sub(_sub(stream, "calculationPeriodAmount"), "calculation")
    step = _sub(_sub(calc, "notionalSchedule"), "notionalStepSchedule")
    _sub(step, "initialValue", _num(p["notional"]))
    _sub(step, "currency", CURVES[p["curve"]]["currency"])
    if kind == "fixed":
        _sub(_sub(calc, "fixedRateSchedule"), "initialValue", _num(p["fixed_rate"]))
    else:
        _sub(_sub(calc, "floatingRateCalculation"), "floatingRateIndex", INDEX_TO_FPML[p["curve"]])
    _sub(calc, "dayCountFraction", _DAY_COUNT)


def _export_irs(trade_el: ET.Element, trade: Dict[str, Any]) -> None:
    p = trade["params"]
    if p.get("fixed_rate") is None:
        raise ApiError(409, "La operación no tiene tasa fija: FpML no puede exportarla", "id")
    swap = _sub(trade_el, "swap")
    _sub(swap, "productType", "InterestRate:IRSwap:OIS")
    fixed_payer, fixed_receiver = (
        (_COMPANY, _COUNTERPARTY) if p["side"] == "payer" else (_COUNTERPARTY, _COMPANY)
    )
    _swap_stream(swap, "fixed", fixed_payer, fixed_receiver, trade)
    _swap_stream(swap, "floating", fixed_receiver, fixed_payer, trade)


def _amount(parent: ET.Element, name: str, currency: str, amount: float) -> None:
    el = _sub(parent, name)
    _sub(el, "currency", currency)
    _sub(el, "amount", _num(amount))


def _export_fx_forward(trade_el: ET.Element, trade: Dict[str, Any]) -> None:
    p = trade["params"]
    usd_receiver, usd_payer = (
        (_COMPANY, _COUNTERPARTY) if p["side"] == "buy" else (_COUNTERPARTY, _COMPANY)
    )
    fx = _sub(trade_el, "fxSingleLeg")
    _sub(fx, "productType", "ForeignExchange:Forward")
    usd = _sub(fx, "exchangedCurrency1")
    _ref(usd, "payerPartyReference", usd_payer)
    _ref(usd, "receiverPartyReference", usd_receiver)
    _amount(usd, "paymentAmount", "USD", p["notional_usd"])
    mxn = _sub(fx, "exchangedCurrency2")
    _ref(mxn, "payerPartyReference", usd_receiver)
    _ref(mxn, "receiverPartyReference", usd_payer)
    _amount(mxn, "paymentAmount", "MXN", p["notional_usd"] * p["strike"])  # informativo
    _sub(fx, "valueDate", trade["maturity_date"].isoformat())
    rate = _sub(fx, "exchangeRate")
    pair = _sub(rate, "quotedCurrencyPair")
    _sub(pair, "currency1", "USD")
    _sub(pair, "currency2", "MXN")
    _sub(pair, "quoteBasis", "Currency2PerCurrency1")
    _sub(rate, "rate", _num(p["strike"]))
    _sub(_sub(fx, "nonDeliverableSettlement"), "settlementCurrency", "MXN")


def _export_fx_option(trade_el: ET.Element, trade: Dict[str, Any]) -> None:
    p = trade["params"]
    buyer, seller = (
        (_COMPANY, _COUNTERPARTY) if p["side"] == "buy" else (_COUNTERPARTY, _COMPANY)
    )
    is_call = p["option_type"] == "call"
    opt = _sub(trade_el, "fxOption")
    _sub(opt, "productType", "ForeignExchange:VanillaOption")
    _ref(opt, "buyerPartyReference", buyer)
    _ref(opt, "sellerPartyReference", seller)
    maturity = trade["maturity_date"].isoformat()
    exercise = _sub(opt, "europeanExercise")
    _sub(exercise, "expiryDate", maturity)
    expiry_time = _sub(exercise, "expiryTime")
    _sub(expiry_time, "hourMinuteTime", "12:00:00")
    _sub(expiry_time, "businessCenter", "MXMC")
    _sub(exercise, "valueDate", maturity)
    mxn_amount = p["notional_usd"] * p["strike"]
    # Call de USD = compra USD con MXN (put MXN); put de USD al revés.
    _amount(opt, "putCurrencyAmount", "MXN" if is_call else "USD", mxn_amount if is_call else p["notional_usd"])
    _amount(opt, "callCurrencyAmount", "USD" if is_call else "MXN", p["notional_usd"] if is_call else mxn_amount)
    strike = _sub(opt, "strike")
    _sub(strike, "rate", _num(p["strike"]))
    _sub(strike, "strikeQuoteBasis", "PutCurrencyPerCallCurrency" if is_call else "CallCurrencyPerPutCurrency")


_EXPORTERS = {"irs": _export_irs, "fx_forward": _export_fx_forward, "fx_option": _export_fx_option}


def export_trade(conn: sqlite3.Connection, trade_id: int) -> str:
    """XML (con declaración) de la operación para `GET /api/trades/<id>/fpml`.

    @raise ApiError 404 `id` (no existe), 400 `product` (fuera de `FPML_PRODUCTS`), 409 `id`
        (eventos posteriores al pacto, o FX con `start_date` distinto de `trade_date`).
    """
    trade = portfolio.get_trade(conn, trade_id)
    if trade["product"] not in FPML_PRODUCTS:
        raise ApiError(400, "FpML solo soporta: %s" % ", ".join(FPML_PRODUCTS), "product")
    if any(e["type"] != "execution" and not ops_settlements.is_confirmation(e) for e in trade["events"]):
        raise ApiError(409, "FpML exporta solo operaciones sin eventos posteriores al pacto", "id")
    if trade["product"] != "irs" and trade["start_date"] != trade["trade_date"]:
        raise ApiError(409, "FpML no lleva fecha de inicio distinta de la fecha de pacto en FX", "id")
    if not isinstance(trade["params"], dict):
        raise ApiError(409, "Los términos guardados de la operación son ilegibles", "id")

    root = ET.Element(_q("dataDocument"), {"fpmlVersion": FPML_VERSION})
    trade_el = _sub(root, "trade")
    header = _sub(trade_el, "tradeHeader")
    ident = _sub(header, "partyTradeIdentifier")
    _ref(ident, "partyReference", _COMPANY)
    _sub(ident, "tradeId", str(trade["id"]), tradeIdScheme=TRADE_ID_SCHEME)
    _sub(header, "tradeDate", trade["trade_date"].isoformat())
    _EXPORTERS[trade["product"]](trade_el, trade)
    _sub(_sub(root, "party", id=_COMPANY), "partyName", ops_settings.company_name(conn))
    _sub(_sub(root, "party", id=_COUNTERPARTY), "partyName", trade["counterparty"])
    _indent(root)
    return "<?xml version='1.0' encoding='utf-8'?>\n" + ET.tostring(root, encoding="unicode") + "\n"


# =============================================================================== importar

_DTD = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)", re.IGNORECASE)
# Decimal con exponente opcional (`repr(float)` puede emitir `1e-05`); rechaza `nan`, `inf`, `1_0`.
_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")


def _bad(message: str) -> ApiError:
    return ApiError(400, message, "fpml")


def _parse(raw: bytes) -> ET.Element:
    """Raíz del documento. Tamaño, UTF-8, DTD/entidades y buena formación, en ese orden."""
    if not raw or not raw.strip():
        raise _bad("El cuerpo está vacío")
    if len(raw) > MAX_FPML_BYTES:
        raise _bad("El FpML excede %d bytes" % MAX_FPML_BYTES)
    try:
        doc = raw.decode("utf-8-sig")  # UTF-16 y similares esconderían el DOCTYPE a la búsqueda
    except UnicodeDecodeError:
        raise _bad("El FpML debe estar codificado en UTF-8")
    if _DTD.search(doc):
        raise _bad("FpML con DTD o entidades no se acepta")
    try:
        root = ET.fromstring(doc)
    except ET.ParseError as e:
        raise _bad("XML mal formado: %s" % e)
    if root.tag != _q("dataDocument"):
        raise _bad("La raíz debe ser <dataDocument> de FpML (%s)" % FPML_NS)
    return root


def _req(parent: ET.Element, path: str) -> ET.Element:
    node = parent.find(_qpath(path))
    if node is None:
        raise _bad("Falta el elemento <%s>" % path)
    return node


def _text(parent: ET.Element, path: str) -> str:
    value = (_req(parent, path).text or "").strip()
    if not value:
        raise _bad("El elemento <%s> está vacío" % path)
    return value


def _number(parent: ET.Element, path: str) -> float:
    value = _text(parent, path)
    if not _NUMBER.fullmatch(value) or not finite_number(float(value)):
        raise _bad("El elemento <%s> no es un número finito: %s" % (path, value))
    return float(value)


def _date(parent: ET.Element, path: str) -> date:
    value = _text(parent, path)
    try:
        return iso_date({"d": value}, "d")
    except ApiError:
        raise _bad("El elemento <%s> no es una fecha AAAA-MM-DD: %s" % (path, value))


def _expect(parent: ET.Element, path: str, expected: str) -> None:
    value = _text(parent, path)
    if value != expected:
        raise _bad("El elemento <%s> debe ser %s, no %s" % (path, expected, value))


def _party(parent: ET.Element, path: str) -> str:
    return _req(parent, path).get("href")  # ya validado contra las `party` declaradas


def _parties(root: ET.Element) -> Dict[str, str]:
    """`{id: partyName}` de exactamente dos `party`."""
    parties = {}  # type: Dict[str, str]
    for el in root.findall(_q("party")):
        pid = el.get("id")
        if not pid:
            raise _bad("Falta el atributo id de <party>")
        if pid in parties:
            raise _bad("La <party> %s está repetida" % pid)
        parties[pid] = _text(el, "partyName")
    if len(parties) != 2:
        raise _bad("Se esperan exactamente dos <party>, hay %d" % len(parties))
    return parties


def _check_party_refs(trade: ET.Element, parties: Dict[str, str]) -> None:
    refs = {_q(name) for name in _PARTY_REFS}
    for el in trade.iter():
        if el.tag in refs and el.get("href") not in parties:
            raise _bad("<%s href=%s> no corresponde a ninguna <party>"
                       % (el.tag.rsplit("}", 1)[-1], el.get("href")))


def _swap_body(swap: ET.Element, company: str) -> Dict[str, Any]:
    """`curve`, `side`, `notional`, `fixed_rate`, `start`/`maturity` y `periods` inicial de un swap OIS."""
    streams = swap.findall(_q("swapStream"))
    if len(streams) != 2:
        raise _bad("El swap debe tener exactamente dos <swapStream>")
    fixed, floating = [], []
    for stream in streams:
        calc = _req(stream, "calculationPeriodAmount/calculation")
        if calc.find(_q("floatingRateCalculation")) is not None:
            floating.append(stream)
        elif calc.find(_q("fixedRateSchedule")) is not None:
            fixed.append(stream)
        else:
            raise _bad("Falta <fixedRateSchedule> o <floatingRateCalculation> en <swapStream>")
    if len(fixed) != 1 or len(floating) != 1:
        raise _bad("El swap debe tener exactamente una pierna fija y una variable")
    fixed_leg, floating_leg = fixed[0], floating[0]

    index = _text(floating_leg, "calculationPeriodAmount/calculation/floatingRateCalculation/floatingRateIndex")
    if index not in FPML_TO_INDEX:
        raise _bad("Índice de tasa no soportado: %s" % index)
    curve = FPML_TO_INDEX[index]
    mult, unit = _frequency(curve)
    notional_path = "calculationPeriodAmount/calculation/notionalSchedule/notionalStepSchedule/"

    legs = []
    for stream in (fixed_leg, floating_leg):
        _expect(stream, "calculationPeriodDates/calculationPeriodFrequency/periodMultiplier", str(mult))
        _expect(stream, "calculationPeriodDates/calculationPeriodFrequency/period", unit)
        _expect(stream, "calculationPeriodAmount/calculation/dayCountFraction", _DAY_COUNT)
        _expect(stream, notional_path + "currency", CURVES[curve]["currency"])
        payer, receiver = _party(stream, "payerPartyReference"), _party(stream, "receiverPartyReference")
        if payer == receiver:
            raise _bad("El pagador y el receptor de una pierna no pueden ser la misma parte")
        legs.append({
            "payer": payer,
            "receiver": receiver,
            "start": _date(stream, "calculationPeriodDates/effectiveDate/unadjustedDate"),
            "end": _date(stream, "calculationPeriodDates/terminationDate/unadjustedDate"),
            "notional": _number(stream, notional_path + "initialValue"),
        })
    fixed_data, floating_data = legs
    if (fixed_data["payer"], fixed_data["receiver"]) != (floating_data["receiver"], floating_data["payer"]):
        raise _bad("Las dos piernas del swap deben tener pagadores opuestos")
    for key in ("start", "end", "notional"):
        if fixed_data[key] != floating_data[key]:
            raise _bad("Las dos piernas del swap deben coincidir en fechas y nocional")
    return {
        "params": {
            "curve": curve,
            "side": "payer" if fixed_data["payer"] == company else "receiver",
            "notional": fixed_data["notional"],
            "periods": 1,  # `fit_to_maturity` lo reescribe con el vencimiento
            "fixed_rate": _number(fixed_leg, "calculationPeriodAmount/calculation/fixedRateSchedule/initialValue"),
        },
        "start_date": fixed_data["start"],
        "maturity_date": fixed_data["end"],
    }


def _fx_leg(fx: ET.Element, name: str) -> Dict[str, Any]:
    return {
        "payer": _party(fx, name + "/payerPartyReference"),
        "receiver": _party(fx, name + "/receiverPartyReference"),
        "currency": _text(fx, name + "/paymentAmount/currency"),
        "amount": _number(fx, name + "/paymentAmount/amount"),
    }


def _fx_forward_body(fx: ET.Element, company: str, trade_date: date) -> Dict[str, Any]:
    legs = [_fx_leg(fx, "exchangedCurrency1"), _fx_leg(fx, "exchangedCurrency2")]
    usd = [leg for leg in legs if leg["currency"] == "USD"]
    mxn = [leg for leg in legs if leg["currency"] == "MXN"]
    if len(usd) != 1 or len(mxn) != 1:
        raise _bad("Se esperan dos montos intercambiados: uno en USD y otro en MXN")
    usd_leg, mxn_leg = usd[0], mxn[0]
    if usd_leg["payer"] == usd_leg["receiver"] or (mxn_leg["payer"], mxn_leg["receiver"]) != (
        usd_leg["receiver"], usd_leg["payer"]
    ):
        raise _bad("Los dos montos intercambiados deben tener pagadores opuestos")
    _expect(fx, "exchangeRate/quotedCurrencyPair/currency1", "USD")
    _expect(fx, "exchangeRate/quotedCurrencyPair/currency2", "MXN")
    _expect(fx, "exchangeRate/quotedCurrencyPair/quoteBasis", "Currency2PerCurrency1")
    _expect(fx, "nonDeliverableSettlement/settlementCurrency", "MXN")
    return {
        "params": {
            "side": "buy" if usd_leg["receiver"] == company else "sell",
            "notional_usd": usd_leg["amount"],
            "strike": _number(fx, "exchangeRate/rate"),  # el monto MXN es informativo
            "days": 1,  # `fit_to_maturity` lo reescribe con el vencimiento
        },
        "start_date": trade_date,
        "maturity_date": _date(fx, "valueDate"),
    }


def _fx_option_body(opt: ET.Element, company: str, trade_date: date) -> Dict[str, Any]:
    buyer, seller = _party(opt, "buyerPartyReference"), _party(opt, "sellerPartyReference")
    if buyer == seller:
        raise _bad("El comprador y el vendedor de la opción no pueden ser la misma parte")
    put_ccy, call_ccy = _text(opt, "putCurrencyAmount/currency"), _text(opt, "callCurrencyAmount/currency")
    put_amount, call_amount = _number(opt, "putCurrencyAmount/amount"), _number(opt, "callCurrencyAmount/amount")
    if (call_ccy, put_ccy) == ("USD", "MXN"):
        option_type, usd_amount, basis = "call", call_amount, "PutCurrencyPerCallCurrency"
    elif (call_ccy, put_ccy) == ("MXN", "USD"):
        option_type, usd_amount, basis = "put", put_amount, "CallCurrencyPerPutCurrency"
    else:
        raise _bad("Se esperan montos de la opción en USD y MXN")
    _expect(opt, "strike/strikeQuoteBasis", basis)
    return {
        "params": {
            "side": "buy" if buyer == company else "sell",
            "option_type": option_type,
            "notional_usd": usd_amount,
            "strike": _number(opt, "strike/rate"),
            "days": 1,  # `fit_to_maturity` lo reescribe con el vencimiento
        },
        "start_date": trade_date,
        "maturity_date": _date(opt, "europeanExercise/expiryDate"),
    }


def import_trade(conn: sqlite3.Connection, raw: bytes) -> Dict[str, Any]:
    """`{"trade", "warnings"}` de un FpML crudo, con la operación ya creada (sin commit).

    Cualquier 400 ocurre antes de escribir. La empresa es la `party` cuyo nombre coincide con
    `company_name`; si ninguna, la primera (`party_assumed`). No guarda el `tradeId` externo.
    Igual que `POST /api/trades`, el vencimiento de un `irs` se ajusta a periodos enteros.
    """
    root = _parse(raw)
    trades = root.findall(_q("trade"))
    if not trades:
        raise _bad("Falta el elemento <trade>")
    if len(trades) > 1:
        raise _bad("El FpML trae más de una <trade>; solo se importa una operación por documento")
    trade_el = trades[0]
    product_el = next((c for c in trade_el if c.tag != _q("tradeHeader")), None)
    if product_el is None:
        raise _bad("Falta el producto dentro de <trade>")
    if product_el.tag not in (_q("swap"), _q("fxSingleLeg"), _q("fxOption")):
        raise _bad("Producto FpML no soportado: %s" % product_el.tag.rsplit("}", 1)[-1])

    parties = _parties(root)
    _check_party_refs(trade_el, parties)
    name = ops_settings.company_name(conn)
    warnings = []  # type: List[Dict[str, str]]
    company = next((pid for pid, party_name in parties.items() if party_name == name), None)
    if company is None:
        company = next(iter(parties))
        warnings.append({
            "code": "party_assumed",
            "message": "Ninguna parte coincide con el nombre de la empresa: se tomó %s como la empresa" % company,
        })
    counterparty = next(party_name for pid, party_name in parties.items() if pid != company)

    trade_date = _date(trade_el, "tradeHeader/tradeDate")
    if product_el.tag == _q("swap"):
        product, parts = "irs", _swap_body(product_el, company)
    elif product_el.tag == _q("fxSingleLeg"):
        product, parts = "fx_forward", _fx_forward_body(product_el, company, trade_date)
    else:
        product, parts = "fx_option", _fx_option_body(product_el, company, trade_date)
    trade = portfolio.create_trade(conn, {
        "product": product,
        "counterparty": counterparty,
        "trade_date": trade_date.isoformat(),
        "start_date": parts["start_date"].isoformat(),
        "maturity_date": parts["maturity_date"].isoformat(),
        "params": parts["params"],
    })
    return {"trade": trade, "warnings": warnings}
