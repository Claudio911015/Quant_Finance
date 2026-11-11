"""Pricer del cross currency swap USDMXN (`xccy_swap`).

Solo valida, arma el `qfpy.XccySwap` de la operación recién pactada (inicio hoy, cupones de 28 días en
ambas patas) y serializa; la matemática vive en C++ y el armado del instrumento en `desk/api/xccy.py`.
El PV va en MXN y descuenta la pata MXN con `MXN-USD` (o `TIIE-F` si el snapshot no trae esa curva).
"""
from datetime import date, timedelta
from typing import Any, Dict, Tuple

from desk.api import xccy as engine
from desk.api.market import CSA_CURVE, CSA_PERIOD_DAYS, MarketContext
from desk.api.pricing.base import MAX_PERIODS, Product
from desk.api.qf import qfpy
from desk.api.validation import MAX_AMOUNT, MAX_PRICE, MAX_RATE, MIN_RATE, choice, integer, number

SIDES = ("pay_usd", "pay_mxn")
EXCHANGES = ("both", "initial", "final", "none")


def _validate(d: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "side": choice(d, "side", SIDES),
        "notional_usd": number(d, "notional_usd", gt=0, le=MAX_AMOUNT),
        "periods": integer(d, "periods", ge=1, le=MAX_PERIODS),
        "fx_rate": number(d, "fx_rate", gt=0, le=MAX_PRICE, required=False),
        "spread": number(d, "spread", ge=MIN_RATE, le=MAX_RATE, required=False),
        "exchange": choice(d, "exchange", EXCHANGES, default="both"),
    }


def _swap(p: Dict[str, Any], mkt: MarketContext) -> Tuple["qfpy.XccySwap", Dict[str, Any]]:
    """`(instrumento, términos con fx_rate y spread completos)` de la operación pactada en `mkt.as_of`."""
    trade = {
        "start_date": mkt.as_of,
        "maturity_date": mkt.as_of + timedelta(days=p["periods"] * CSA_PERIOD_DAYS),
    }
    terms = engine.resolve(trade, p, mkt, {})
    return engine.aged_xccy(trade, terms, mkt, {}, []), terms


def _pv_mxn(p: Dict[str, Any], mkt: MarketContext) -> float:
    return float(_swap(p, mkt)[0].npv(mkt.env))


def _dv01(swap: "qfpy.XccySwap", mkt: MarketContext, curve: str) -> float:
    """`PV(base) − PV(curva +1 pb)` en MXN, con el mismo instrumento (mismo diferencial) en ambos lados."""
    return float(swap.npv(mkt.env) - swap.npv(mkt.shifted(curve=curve, parallel_bp=1.0).env))


def _price(p: Dict[str, Any], mkt: MarketContext) -> Dict[str, Any]:
    swap, terms = _swap(p, mkt)
    pv = float(swap.npv(mkt.env))
    cashflows = [
        {
            "date": (mkt.as_of + timedelta(days=cf.pay_days)).isoformat(),
            "days": int(cf.pay_days),
            "leg": cf.leg,
            "kind": cf.kind,
            "amount": cf.amount,
            "df": cf.discount_factor,
            "pv": cf.present_value,
            "pv_mxn": cf.present_value_mxn,
        }
        for cf in swap.cash_flows(mkt.env)
    ]
    return {
        "product": "xccy_swap",
        "currency": "MXN",
        "pv": pv,
        "pv_mxn": pv,
        "risk": {
            "par_spread": float(swap.par_spread(mkt.env)),
            # sin la curva MXN-USD no hay sensibilidad a ella: el descuento es TIIE-F (ver `details`)
            "dv01_mxn_usd": _dv01(swap, mkt, CSA_CURVE) if mkt.csa_available else 0.0,
            "dv01_tiie": _dv01(swap, mkt, "TIIE-F"),  # recalibra MXN-USD con los puntos y la base fijos
            "dv01_sofr": _dv01(swap, mkt, "SOFR"),
        },
        "cashflows": cashflows,
        "details": {
            "fx_rate": terms["fx_rate"],
            "spread": terms["spread"],
            "notional_mxn": float(swap.notional_mxn()),
            "discount_curve": engine.discount_curve(mkt),
        },
    }


def _describe(p: Dict[str, Any], as_of: date) -> Dict[str, Any]:
    return {
        "notional": p["notional_usd"],
        "currency": "USD",
        "maturity": (as_of + timedelta(days=p["periods"] * CSA_PERIOD_DAYS)).isoformat(),
    }


PRODUCTS: Dict[str, Product] = {
    "xccy_swap": Product("xccy_swap", _validate, _price, _pv_mxn, _describe),
}
