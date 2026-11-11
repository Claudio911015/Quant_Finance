"""Pricers de tasas: irs, cap_floor, swaption, bond.

Aquí solo se validan parámetros, se arman objetos de `qfpy` y se leen sus resultados;
toda la matemática (bootstrap, descuento, Hull-White, par rate) vive en C++.
"""
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional

from desk.api.errors import ApiError
from desk.api.market import CURVES, MarketContext
from desk.api.pricing.base import MAX_BOND_YEARS, MAX_PERIODS, MAX_YEARS, Product
from desk.api.qf import qfpy
from desk.api.validation import MAX_AMOUNT, MAX_FREQUENCY, MAX_RATE, MIN_RATE, choice, integer, number

_CURVE_NAMES = tuple(CURVES)
_DAYS_PER_YEAR = 365.0


def _curve(d: Dict[str, Any], default: Optional[str] = None) -> str:
    return choice(d, "curve", _CURVE_NAMES, default)


def _currency(curve: str) -> str:
    return CURVES[curve]["currency"]


def _to_mxn(pv: float, curve: str, mkt: MarketContext) -> float:
    return pv * mkt.spot if _currency(curve) == "USD" else pv


def _discount(curve: str, mkt: MarketContext) -> str:
    """Curva con la que se descuenta un producto de la curva `curve` (corte 3, colateral).

    Solo `TIIE-F` cambia: descuenta con `mkt.mxn_discount` (`MXN-USD` si la contraparte tiene colateral
    en USD y el snapshot trae la curva, si no `TIIE-F`). `SOFR` descuenta con SOFR con cualquier colateral.
    """
    return getattr(mkt, "mxn_discount", "TIIE-F") if curve == "TIIE-F" else curve


def _dv01(pv_fn: Callable[[MarketContext], float], curve: str, mkt: MarketContext) -> float:
    """DV01 = PV(base) − PV(curva +1 pb): positivo si el PV sube cuando bajan las tasas."""
    return pv_fn(mkt) - pv_fn(mkt.shifted(curve=curve, parallel_bp=1.0))


def _maturity(as_of: date, days: float) -> str:
    return (as_of + timedelta(days=int(round(days)))).isoformat()


def _response(
    product: str,
    p: Dict[str, Any],
    mkt: MarketContext,
    pv: float,
    risk: Dict[str, float],
    cashflows: Optional[List[Dict[str, Any]]] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "product": product,
        "currency": _currency(p["curve"]),
        "pv": pv,
        "pv_mxn": _to_mxn(pv, p["curve"], mkt),
        "risk": risk,
        "cashflows": cashflows,
        "details": details or {},
    }


# --------------------------------------------------------------------------- irs

def _irs_validate(d: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "curve": _curve(d),
        "side": choice(d, "side", ("payer", "receiver")),
        "notional": number(d, "notional", gt=0, le=MAX_AMOUNT),
        "periods": integer(d, "periods", ge=1, le=MAX_PERIODS),
        "fixed_rate": number(d, "fixed_rate", ge=MIN_RATE, le=MAX_RATE, required=False),
    }


def _irs_swap(p: Dict[str, Any], fixed_rate: float, discount: str = "") -> "qfpy.OisSwap":
    """El swap del pricer; `discount` es la curva de descuento ("" = la misma de proyección)."""
    period_days = CURVES[p["curve"]]["period_days"]
    side = qfpy.SwapType.Payer if p["side"] == "payer" else qfpy.SwapType.Receiver
    return qfpy.OisSwap(
        p["notional"],
        fixed_rate,
        p["periods"] * period_days,
        period_days,
        side,
        p["curve"],
        discount_curve_key="" if discount == p["curve"] else discount,
    )


def _irs_par(p: Dict[str, Any], mkt: MarketContext) -> float:
    return _irs_swap(p, 0.0, _discount(p["curve"], mkt)).par_rate(mkt.env)


def _irs_fixed(p: Dict[str, Any], mkt: MarketContext) -> float:
    return p["fixed_rate"] if p["fixed_rate"] is not None else _irs_par(p, mkt)


def _irs_pv(p: Dict[str, Any], mkt: MarketContext) -> float:
    return _irs_swap(p, _irs_fixed(p, mkt), _discount(p["curve"], mkt)).npv(mkt.env)


def _irs_price(p: Dict[str, Any], mkt: MarketContext) -> Dict[str, Any]:
    par = _irs_par(p, mkt)
    fixed = p["fixed_rate"] if p["fixed_rate"] is not None else par
    swap = _irs_swap(p, fixed, _discount(p["curve"], mkt))  # la misma tasa fija para la base y para el choque
    pv = swap.npv(mkt.env)
    bumped = swap.npv(mkt.shifted(curve=p["curve"], parallel_bp=1.0).env)
    cashflows = [
        {
            "date": _maturity(mkt.as_of, cf.pay_days),
            "days": int(cf.pay_days),
            "amount": cf.net_amount,
            "df": cf.discount_factor,
            "pv": cf.present_value,
        }
        for cf in swap.cash_flows(mkt.env)
    ]
    return _response(
        "irs",
        p,
        mkt,
        pv,
        {"dv01": pv - bumped, "par_rate": par},
        cashflows,
        {"fixed_rate": fixed},
    )


def _irs_describe(p: Dict[str, Any], as_of: date) -> Dict[str, Any]:
    days = p["periods"] * CURVES[p["curve"]]["period_days"]
    return {
        "notional": p["notional"],
        "currency": _currency(p["curve"]),
        "maturity": _maturity(as_of, days),
    }


# ------------------------------------------------------------------------ cap_floor

def _cap_floor_validate(d: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "curve": _curve(d),
        "cap_type": choice(d, "cap_type", ("cap", "floor")),
        "notional": number(d, "notional", gt=0, le=MAX_AMOUNT),
        "strike": number(d, "strike", gt=0, le=MAX_RATE),  # el strike de un cap/floor es una tasa
        "periods": integer(d, "periods", ge=1, le=MAX_PERIODS),
    }


def _cap_floor_instrument(p: Dict[str, Any], mkt: MarketContext) -> "qfpy.CapFloor":
    period_days = CURVES[p["curve"]]["period_days"]
    kind = qfpy.CapFloorType.Cap if p["cap_type"] == "cap" else qfpy.CapFloorType.Floor
    hw = mkt.hw[p["curve"]]
    return qfpy.CapFloor(
        kind,
        p["notional"],
        p["strike"],
        p["periods"] * period_days / _DAYS_PER_YEAR,
        _DAYS_PER_YEAR / period_days,
        hw["a"],
        hw["sigma"],
        qfpy.DayCountConvention.ACT_360,
    )


def _cap_floor_pv(p: Dict[str, Any], mkt: MarketContext) -> float:
    discount = _discount(p["curve"], mkt)
    if discount != p["curve"]:  # colateral USD: se proyecta con TIIE-F y se descuenta con MXN-USD
        return _cap_floor_instrument(p, mkt).price_dual(mkt.curves[p["curve"]], mkt.curves[discount])
    return _cap_floor_instrument(p, mkt).pv(mkt.env_with_default(p["curve"]))


def _cap_floor_price(p: Dict[str, Any], mkt: MarketContext) -> Dict[str, Any]:
    pv = _cap_floor_pv(p, mkt)
    hw = mkt.hw[p["curve"]]
    return _response(
        "cap_floor",
        p,
        mkt,
        pv,
        {"dv01": _dv01(lambda m: _cap_floor_pv(p, m), p["curve"], mkt)},
        details={"hw_a": hw["a"], "hw_sigma": hw["sigma"]},
    )


def _cap_floor_describe(p: Dict[str, Any], as_of: date) -> Dict[str, Any]:
    return _irs_describe(p, as_of)


# -------------------------------------------------------------------------- swaption

def _swaption_validate(d: Dict[str, Any]) -> Dict[str, Any]:
    p = {
        "curve": _curve(d),
        "swaption_type": choice(d, "swaption_type", ("payer", "receiver")),
        "notional": number(d, "notional", gt=0, le=MAX_AMOUNT),
        "strike": number(d, "strike", gt=0, le=MAX_RATE),  # el strike de una swaption es una tasa
        "expiry_years": number(d, "expiry_years", gt=0, le=MAX_YEARS),
        "swap_tenor_years": number(d, "swap_tenor_years", gt=0, le=MAX_YEARS),
    }
    # `Swaption::price` redondea tenor × frecuencia al número de pagos; con 0 pagos escribe
    # fuera de rango y tumba el proceso (segfault), así que se exige al menos un pago.
    frequency = _DAYS_PER_YEAR / CURVES[p["curve"]]["period_days"]
    if p["swap_tenor_years"] * frequency < 0.5:
        raise ApiError(
            400,
            "'swap_tenor_years' debe cubrir al menos medio periodo de pago (%.4f años)" % (0.5 / frequency),
            "swap_tenor_years",
        )
    return p


def _swaption_instrument(p: Dict[str, Any], mkt: MarketContext) -> "qfpy.Swaption":
    period_days = CURVES[p["curve"]]["period_days"]
    kind = (
        qfpy.SwaptionType.Payer
        if p["swaption_type"] == "payer"
        else qfpy.SwaptionType.Receiver
    )
    hw = mkt.hw[p["curve"]]
    return qfpy.Swaption(
        kind,
        p["notional"],
        p["strike"],
        p["expiry_years"],
        p["swap_tenor_years"],
        _DAYS_PER_YEAR / period_days,
        hw["a"],
        hw["sigma"],
        qfpy.DayCountConvention.ACT_360,
    )


def _swaption_pv(p: Dict[str, Any], mkt: MarketContext) -> float:
    discount = _discount(p["curve"], mkt)
    if discount != p["curve"]:  # colateral USD: se proyecta con TIIE-F y se descuenta con MXN-USD
        return _swaption_instrument(p, mkt).price_dual(mkt.curves[p["curve"]], mkt.curves[discount])
    return _swaption_instrument(p, mkt).pv(mkt.env_with_default(p["curve"]))


def _swaption_price(p: Dict[str, Any], mkt: MarketContext) -> Dict[str, Any]:
    pv = _swaption_pv(p, mkt)
    hw = mkt.hw[p["curve"]]
    return _response(
        "swaption",
        p,
        mkt,
        pv,
        {"dv01": _dv01(lambda m: _swaption_pv(p, m), p["curve"], mkt)},
        details={"hw_a": hw["a"], "hw_sigma": hw["sigma"]},
    )


def _swaption_describe(p: Dict[str, Any], as_of: date) -> Dict[str, Any]:
    days = (p["expiry_years"] + p["swap_tenor_years"]) * _DAYS_PER_YEAR
    return {
        "notional": p["notional"],
        "currency": _currency(p["curve"]),
        "maturity": _maturity(as_of, days),
    }


# ----------------------------------------------------------------------------- bond

def _bond_validate(d: Dict[str, Any]) -> Dict[str, Any]:
    p = {
        "curve": _curve(d, default="TIIE-F"),
        "face": number(d, "face", gt=0, le=MAX_AMOUNT),
        "coupon_rate": number(d, "coupon_rate", ge=0, le=MAX_RATE),
        "periods": integer(d, "periods", ge=1, le=MAX_PERIODS),
        "frequency": number(d, "frequency", gt=0, le=MAX_FREQUENCY, required=False, default=2.0),
    }
    if p["periods"] / p["frequency"] > MAX_BOND_YEARS:
        raise ApiError(
            400,
            "'frequency' es demasiado baja: el bono duraría más de %d años (periods / frequency)"
            % MAX_BOND_YEARS,
            "frequency",
        )
    return p


def _bond_instrument(p: Dict[str, Any]) -> "qfpy.Bond":
    return qfpy.Bond(p["face"], p["coupon_rate"], p["periods"], p["frequency"])


def _bond_pv(p: Dict[str, Any], mkt: MarketContext) -> float:
    return _bond_instrument(p).pv(mkt.env_with_default(_discount(p["curve"], mkt)))


def _bond_price(p: Dict[str, Any], mkt: MarketContext) -> Dict[str, Any]:
    bond = _bond_instrument(p)
    discount = _discount(p["curve"], mkt)
    curve = mkt.curves[discount]
    pv = bond.pv(mkt.env_with_default(discount))
    cashflows = []
    for t, amount in bond.cash_flow_schedule():
        days = int(round(t * _DAYS_PER_YEAR))
        df = curve.discount_factor(t)
        cashflows.append(
            {
                "date": _maturity(mkt.as_of, days),
                "days": days,
                "amount": amount,
                "df": df,
                "pv": amount * df,
            }
        )
    risk = {
        "dv01": _dv01(lambda m: _bond_pv(p, m), p["curve"], mkt),
        "duration": bond.duration(curve),
        "convexity": bond.convexity(curve),
    }
    return _response("bond", p, mkt, pv, risk, cashflows)


def _bond_describe(p: Dict[str, Any], as_of: date) -> Dict[str, Any]:
    last = _bond_instrument(p).cash_flow_schedule()[-1][0]
    return {
        "notional": p["face"],
        "currency": _currency(p["curve"]),
        "maturity": _maturity(as_of, last * _DAYS_PER_YEAR),
    }


# ---------------------------------------------------------------------------- registro

def _product(name, validate, price, pv_fn, describe) -> Product:
    return Product(
        name,
        validate,
        price,
        lambda p, mkt: _to_mxn(pv_fn(p, mkt), p["curve"], mkt),
        describe,
    )


PRODUCTS: Dict[str, Product] = {
    "irs": _product("irs", _irs_validate, _irs_price, _irs_pv, _irs_describe),
    "cap_floor": _product(
        "cap_floor", _cap_floor_validate, _cap_floor_price, _cap_floor_pv, _cap_floor_describe
    ),
    "swaption": _product(
        "swaption", _swaption_validate, _swaption_price, _swaption_pv, _swaption_describe
    ),
    "bond": _product("bond", _bond_validate, _bond_price, _bond_pv, _bond_describe),
}
