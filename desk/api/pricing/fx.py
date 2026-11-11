"""Pricers FX y renta variable: fx_forward, fx_option, equity_option.

Toda la matemática vive en C++ (`qfpy`); aquí solo se valida, se arma el instrumento y se
serializa. Forward y opción FX valúan sobre `mkt.env` (curvas TIIE-F/SOFR, spot y
superficie USDMXN) y ya están en MXN; la opción sobre acción es Black-Scholes y no depende
del mercado.
"""
from datetime import date, timedelta
from typing import Any, Dict

from desk.api.pricing.base import MAX_DAYS, MAX_YEARS, Product
from desk.api.qf import qfpy
from desk.api.validation import choice, integer, number

_SIDE = {"buy": qfpy.FxSide.Buy, "sell": qfpy.FxSide.Sell}
_OPTION_TYPE = {"call": qfpy.OptionType.Call, "put": qfpy.OptionType.Put}


def _iso(as_of: date, days: int) -> str:
    return (as_of + timedelta(days=days)).isoformat()


def _fx_params(d: Dict[str, Any], with_option_type: bool) -> Dict[str, Any]:
    out = {"side": choice(d, "side", ["buy", "sell"])}
    if with_option_type:
        out["option_type"] = choice(d, "option_type", ["call", "put"])
    out["notional_usd"] = number(d, "notional_usd", gt=0)
    out["strike"] = number(d, "strike", gt=0)
    out["days"] = integer(d, "days", ge=1, le=MAX_DAYS)
    return out


def _fx_describe(params: Dict[str, Any], as_of: date) -> Dict[str, Any]:
    return {
        "notional": params["notional_usd"],
        "currency": "USD",
        "maturity": _iso(as_of, params["days"]),
    }


# ----------------------------------------------------------------------------- fx_forward


def _fx_forward(params: Dict[str, Any]):
    return qfpy.FxForward(
        params["notional_usd"], params["strike"], params["days"], _SIDE[params["side"]]
    )


def _fx_forward_validate(params: Dict[str, Any]) -> Dict[str, Any]:
    return _fx_params(params, with_option_type=False)


def _fx_forward_pv_mxn(params: Dict[str, Any], mkt) -> float:
    return float(_fx_forward(params).npv(mkt.env))


def _fx_forward_price(params: Dict[str, Any], mkt) -> Dict[str, Any]:
    inst = _fx_forward(params)
    pv = float(inst.npv(mkt.env))
    return {
        "product": "fx_forward",
        "currency": "MXN",
        "pv": pv,
        "pv_mxn": pv,
        "risk": {
            "delta": float(inst.delta(mkt.env)),
            "forward": float(inst.forward_rate(mkt.env)),
        },
        "cashflows": None,
        "details": {},
    }


# ----------------------------------------------------------------------------- fx_option


def _fx_option(params: Dict[str, Any]):
    return qfpy.FxOption(
        params["notional_usd"],
        params["strike"],
        params["days"],
        _OPTION_TYPE[params["option_type"]],
        _SIDE[params["side"]],
    )


def _fx_option_validate(params: Dict[str, Any]) -> Dict[str, Any]:
    return _fx_params(params, with_option_type=True)


def _fx_option_pv_mxn(params: Dict[str, Any], mkt) -> float:
    return float(_fx_option(params).npv(mkt.env))


def _fx_option_price(params: Dict[str, Any], mkt) -> Dict[str, Any]:
    g = _fx_option(params).greeks(mkt.env)
    return {
        "product": "fx_option",
        "currency": "MXN",
        "pv": float(g.price),
        "pv_mxn": float(g.price),
        "risk": {
            "delta": float(g.delta),
            "gamma": float(g.gamma),
            "vega": float(g.vega),
            "forward": float(g.forward),
            "vol": float(g.vol),
        },
        "cashflows": None,
        "details": {},
    }


# ----------------------------------------------------------------------------- equity_option


def _equity_validate(params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "option_type": choice(params, "option_type", ["call", "put"]),
        "spot": number(params, "spot", gt=0),
        "strike": number(params, "strike", gt=0),
        "volatility": number(params, "volatility", gt=0),
        "rate": number(params, "rate"),
        "dividend_yield": number(params, "dividend_yield", ge=0),
        "maturity_years": number(params, "maturity_years", gt=0, le=MAX_YEARS),
        "quantity": number(params, "quantity", gt=0, required=False, default=1.0),
    }


def _equity_bs(params: Dict[str, Any]) -> Dict[str, float]:
    p = qfpy.OptionParams()
    p.spot = params["spot"]
    p.strike = params["strike"]
    p.riskFreeRate = params["rate"]
    p.dividendYield = params["dividend_yield"]
    p.volatility = params["volatility"]
    p.maturity = params["maturity_years"]
    p.type = _OPTION_TYPE[params["option_type"]]
    p.exercise = qfpy.ExerciseType.European
    return qfpy.black_scholes(p)


def _equity_pv_mxn(params: Dict[str, Any], mkt) -> float:
    return params["quantity"] * float(_equity_bs(params)["price"])


def _equity_price(params: Dict[str, Any], mkt) -> Dict[str, Any]:
    bs = _equity_bs(params)
    q = params["quantity"]
    pv = q * float(bs["price"])
    return {
        "product": "equity_option",
        "currency": "MXN",
        "pv": pv,
        "pv_mxn": pv,
        "risk": {k: q * float(bs[k]) for k in ("delta", "gamma", "vega", "theta", "rho")},
        "cashflows": None,
        "details": {},
    }


def _equity_describe(params: Dict[str, Any], as_of: date) -> Dict[str, Any]:
    return {
        "notional": params["quantity"] * params["spot"],
        "currency": "MXN",
        "maturity": _iso(as_of, int(round(params["maturity_years"] * 365))),
    }


PRODUCTS: Dict[str, Product] = {
    "fx_forward": Product(
        "fx_forward",
        _fx_forward_validate,
        _fx_forward_price,
        _fx_forward_pv_mxn,
        _fx_describe,
    ),
    "fx_option": Product(
        "fx_option",
        _fx_option_validate,
        _fx_option_price,
        _fx_option_pv_mxn,
        _fx_describe,
    ),
    "equity_option": Product(
        "equity_option",
        _equity_validate,
        _equity_price,
        _equity_pv_mxn,
        _equity_describe,
    ),
}
