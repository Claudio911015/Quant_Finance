"""Confirmación imprimible de una operación (corte 5): términos pactados, no los vigentes.

Solo presenta lo registrado: no hay fórmulas de pricing ni mercado. Los montos del calendario
son los conocidos sin fijaciones futuras (pierna fija de un `irs`, cupón de un `bond`); el resto
va con `amount = None` ("por determinar"). Las convenciones salen del código de los pricers
(`desk/api/pricing/`) y de `include/qf/`; donde difiere de la tabla del plan, manda el código.
"""
import sqlite3
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional

from desk.api import ops_settings, ops_settlements, portfolio
from desk.api.db import now_iso
from desk.api.errors import ApiError
from desk.api.market import CURVES
from desk.api.qf import qfpy

NOTICES = ("Documento informativo; no sustituye la confirmación ISDA ni el contrato marco firmado por las partes.",
           "Generado por QF Desk con los términos registrados; los montos variables dependen de fijaciones futuras.")

_ACT_360 = 360.0  # base de los cupones de `OisSwap` (igual que `settlement.py`)
_DAYS_PER_YEAR = 365.0  # base del calendario de `bond` (igual que `_bond_price`)

_INDEX_LABEL = {"TIIE-F": "TIIE de Fondeo (TIIE-F)", "SOFR": "SOFR (Secured Overnight Financing Rate)"}
_BUSINESS_DAYS = "Días naturales, sin ajuste por inhábiles"
_EUROPEAN = "Europea"
_FX_CASH_SETTLEMENT = "Por diferencias en MXN con el FIX USD/MXN del vencimiento"
_FX_OPTION_SETTLEMENT = (
    "Por diferencias en MXN con el FIX USD/MXN de la expiración, solo si la opción termina en el dinero"
)

_EVENT_LABEL = {
    "reset": "fijación",
    "transfer": "transferencia",
    "quantity_change": "cambio de nocional",
    "terms_change": "cambio de términos",
    "exercise": "ejercicio",
    "termination": "terminación anticipada",
}

Row = Dict[str, Any]


def _row(key: str, label: str, value: Any, fmt: str, currency: Optional[str] = None) -> Row:
    return {"key": key, "label": label, "value": value, "format": fmt, "currency": currency}


def _text(key: str, label: str, value: str) -> Row:
    return _row(key, label, value, "text")


def _step(description: str, day: date, amount: Optional[float], currency: str) -> Row:
    return {"date": day.isoformat(), "description": description, "amount": amount, "currency": currency}


def _index(curve: str) -> Row:
    return _text("index", "Índice variable", _INDEX_LABEL[curve])


def _period_frequency(curve: str) -> Row:
    return _text("payment_frequency", "Periodicidad de pago", "Cada %d días" % CURVES[curve]["period_days"])


def _business_days() -> Row:
    return _text("business_days", "Días hábiles", _BUSINESS_DAYS)


# ------------------------------------------------------------------------------ por producto
# Cada constructor recibe la operación y devuelve (etiqueta, roles, términos, convenciones, calendario).

def _irs(trade: Dict[str, Any]):
    p = trade["params"]
    curve, currency = p["curve"], CURVES[p["curve"]]["currency"]
    payer = p["side"] == "payer"
    terms = [
        _row("notional", "Nocional", p["notional"], "amount", currency),
        _row("fixed_rate", "Tasa fija", p["fixed_rate"], "rate"),
        _row("periods", "Periodos", p["periods"], "number"),
    ]
    conventions = [
        _index(curve),
        _text("day_count", "Base de días", "ACT/360"),
        _period_frequency(curve),
        _text("compounding", "Composición", "Capitalización diaria de la tasa a un día (OIS), sin spread"),
        _business_days(),
    ]
    start = trade["start_date"]
    pay = qfpy.ois_payment_days((trade["maturity_date"] - start).days, CURVES[curve]["period_days"])
    schedule = []  # type: List[Row]
    previous = 0
    for n, k in enumerate(pay, 1):
        fixed = p["notional"] * p["fixed_rate"] * (k - previous) / _ACT_360
        previous = k
        schedule.append(_step(
            "Cupón %d: pierna fija contra pierna variable" % n,
            start + timedelta(days=k),
            -fixed if payer else fixed,
            currency,
        ))
    roles = ("Paga tasa fija", "Paga tasa variable") if payer else ("Paga tasa variable", "Paga tasa fija")
    return "Swap de tasa de interés (OIS)", roles, terms, conventions, schedule


def _fx_forward(trade: Dict[str, Any]):
    p = trade["params"]
    terms = [
        _row("notional_usd", "Nocional (USD)", p["notional_usd"], "amount", "USD"),
        _row("strike", "Tipo de cambio pactado", p["strike"], "number"),
    ]
    conventions = [_text("settlement", "Liquidación", _FX_CASH_SETTLEMENT), _business_days()]
    schedule = [_step("Liquidación por diferencias: nocional × (FIX − strike)", trade["maturity_date"], None, "MXN")]
    return "Forward de tipo de cambio USD/MXN", _buy_sell(p), terms, conventions, schedule


def _fx_option(trade: Dict[str, Any]):
    p = trade["params"]
    terms = [
        _text("option_type", "Tipo de opción", _OPTION_TYPE[p["option_type"]]),
        _row("notional_usd", "Nocional (USD)", p["notional_usd"], "amount", "USD"),
        _row("strike", "Strike", p["strike"], "number"),
    ]
    conventions = [
        _text("exercise", "Ejercicio", _EUROPEAN),
        _text("settlement", "Liquidación", _FX_OPTION_SETTLEMENT),
        _text("premium", "Prima", "Prima no registrada en QF Desk"),
        _business_days(),
    ]
    schedule = [_step("Expiración de la opción", trade["maturity_date"], None, "MXN")]
    return "Opción de tipo de cambio USD/MXN", _buy_sell(p), terms, conventions, schedule


def _cap_floor(trade: Dict[str, Any]):
    p = trade["params"]
    curve, currency = p["curve"], CURVES[p["curve"]]["currency"]
    is_cap = p["cap_type"] == "cap"
    terms = [
        _text("cap_type", "Tipo", "Cap" if is_cap else "Floor"),
        _row("notional", "Nocional", p["notional"], "amount", currency),
        _row("strike", "Strike", p["strike"], "rate"),
        _row("periods", "Periodos", p["periods"], "number"),
    ]
    conventions = [
        _index(curve),
        _text("day_count", "Base de días", "ACT/360"),
        _period_frequency(curve),
        _business_days(),
    ]
    period_days = CURVES[curve]["period_days"]
    condition = "supera" if is_cap else "queda por debajo de"
    schedule = [
        _step(
            "Periodo %d: paga si la tasa variable %s el strike" % (k, condition),
            trade["start_date"] + timedelta(days=k * period_days),
            None,
            currency,
        )
        for k in range(1, p["periods"] + 1)
    ]
    return "Cap / floor de tasa", ("Compra", "Vende"), terms, conventions, schedule


def _swaption(trade: Dict[str, Any]):
    p = trade["params"]
    curve, currency = p["curve"], CURVES[p["curve"]]["currency"]
    terms = [
        _text("swaption_type", "Tipo", "Pagadora" if p["swaption_type"] == "payer" else "Receptora"),
        _row("notional", "Nocional", p["notional"], "amount", currency),
        _row("strike", "Strike", p["strike"], "rate"),
        _row("expiry_years", "Expiración (años)", p["expiry_years"], "number"),
        _row("swap_tenor_years", "Plazo del swap (años)", p["swap_tenor_years"], "number"),
    ]
    conventions = [_index(curve), _text("exercise", "Ejercicio", _EUROPEAN), _business_days()]
    schedule = [_step("Expiración: ejercicio de la swaption europea", trade["maturity_date"], None, currency)]
    return "Swaption europea", ("Compra", "Vende"), terms, conventions, schedule


def _bond(trade: Dict[str, Any]):
    p = trade["params"]
    currency = CURVES[p["curve"]]["currency"]
    frequency = p["frequency"]
    terms = [
        _row("face", "Valor nominal", p["face"], "amount", currency),
        _row("coupon_rate", "Tasa cupón", p["coupon_rate"], "rate"),
        _row("periods", "Periodos", p["periods"], "number"),
        _row("frequency", "Frecuencia", frequency, "number"),
    ]
    conventions = [
        _text("day_count", "Base de días", "ACT/365"),  # `qf::instruments::Bond` por omisión
        _text("payment_frequency", "Periodicidad de pago", "%g veces al año" % frequency),
        _business_days(),
    ]
    coupon = p["face"] * p["coupon_rate"] / frequency
    schedule = []  # type: List[Row]
    for k in range(1, p["periods"] + 1):
        last = k == p["periods"]
        # mismos días que `_bond_price`: round(t × 365) con t = k / frecuencia
        day = trade["start_date"] + timedelta(days=int(round((k / frequency) * _DAYS_PER_YEAR)))
        schedule.append(_step(
            "Cupón %d y principal" % k if last else "Cupón %d" % k,
            day,
            coupon + p["face"] if last else coupon,
            currency,
        ))
    return "Bono a tasa fija", ("Tenedor", "Emisor"), terms, conventions, schedule


def _equity_option(trade: Dict[str, Any]):
    p = trade["params"]
    terms = [
        _text("option_type", "Tipo de opción", _OPTION_TYPE[p["option_type"]]),
        _row("quantity", "Cantidad", p["quantity"], "number"),
        _row("spot", "Spot", p["spot"], "number"),
        _row("strike", "Strike", p["strike"], "number"),
        _row("volatility", "Volatilidad", p["volatility"], "rate"),
        _row("rate", "Tasa", p["rate"], "rate"),
        _row("dividend_yield", "Rendimiento por dividendo", p["dividend_yield"], "rate"),
        _row("maturity_years", "Plazo (años)", p["maturity_years"], "number"),
    ]
    conventions = [_text("exercise", "Ejercicio", _EUROPEAN), _business_days()]
    # la moneda del producto es MXN (`_equity_describe`)
    schedule = [_step("Vencimiento de la opción", trade["maturity_date"], None, "MXN")]
    return "Opción de renta variable", ("Compra", "Vende"), terms, conventions, schedule


_OPTION_TYPE = {"call": "Call", "put": "Put"}


def _buy_sell(params: Dict[str, Any]):
    return ("Compra", "Vende") if params["side"] == "buy" else ("Vende", "Compra")


_BUILDERS = {
    "irs": _irs,
    "fx_forward": _fx_forward,
    "fx_option": _fx_option,
    "cap_floor": _cap_floor,
    "swaption": _swaption,
    "bond": _bond,
    "equity_option": _equity_option,
}  # type: Dict[str, Callable[[Dict[str, Any]], Any]]


def _events_note(events: List[Dict[str, Any]]) -> Optional[str]:
    """`None` si solo hay `execution` y confirmaciones; si no, nombra los tipos (sin repetir)."""
    kinds = []  # type: List[str]
    for e in events:
        if e["type"] == "execution" or ops_settlements.is_confirmation(e):
            continue
        label = _EVENT_LABEL.get(e["type"], e["type"])
        if label not in kinds:
            kinds.append(label)
    if not kinds:
        return None
    return (
        "La operación tiene eventos posteriores al pacto (%s): esta confirmación muestra los términos pactados."
        % ", ".join(kinds)
    )


def confirmation(conn: sqlite3.Connection, trade_id: int) -> Dict[str, Any]:
    """Cuerpo de `GET /api/trades/<id>/confirmation`: términos pactados de la operación.

    @raise ApiError 404 `id` si no existe; 400 `product` si el producto no tiene confirmación.
    """
    trade = portfolio.get_trade(conn, trade_id)
    builder = _BUILDERS.get(trade["product"])
    if builder is None:
        raise ApiError(400, "El producto no tiene confirmación: %s" % trade["product"], "product")
    label, roles, terms, conventions, schedule = builder(trade)
    return {
        "trade_id": trade["id"],
        "product": trade["product"],
        "product_label": label,
        "generated_at": now_iso(),
        "parties": {
            "company": ops_settings.company_name(conn),
            "counterparty": trade["counterparty"],
            "company_role": roles[0],
            "counterparty_role": roles[1],
        },
        "bank_ref": ops_settings.get_ref(conn, trade["id"]),
        "dates": {
            "trade_date": trade["trade_date"].isoformat(),
            "start_date": trade["start_date"].isoformat(),
            "maturity_date": trade["maturity_date"].isoformat(),
        },
        "terms": terms,
        "conventions": conventions,
        "schedule": schedule,
        "events_note": _events_note(trade["events"]),
        "notices": list(NOTICES),
    }
