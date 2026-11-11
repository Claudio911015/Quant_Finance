"""Pricers de QuantLib para forwards y opciones USDMXN y opciones sobre acción (fx_forward, fx_option, equity_option).

Solo para el entorno de QuantLib (Python 3.12); el backend nunca importa este módulo.

Cada pricer tiene la firma `pricer(case: dict, ctx: dict) -> float` y devuelve el PV en la moneda y con el
signo de `pv_desk` (MXN en los tres productos). QuantLib calcula el PV (instrumento + motor); aquí solo se
arman los insumos que el desk ya fijó: spot, volatilidad de la superficie en (K, T) y fechas enteras.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import QuantLib as ql  # noqa: E402


def _sign(side: str) -> float:
    """+1 si se compra, −1 si se vende (mismo signo que el desk)."""
    return 1.0 if side == "buy" else -1.0


def _flat_vol(today: ql.Date, vol: float) -> ql.BlackVolTermStructureHandle:
    """Volatilidad plana, base Actual365Fixed (T = días/365 como el desk)."""
    return ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, ql.NullCalendar(), float(vol), ql.Actual365Fixed()))


def price_fx_forward(case: dict, ctx: dict) -> float:
    """Forward USDMXN: FxForward con DiscountingFxForwardEngine (USD descontado con SOFR, MXN con TIIE-F)."""
    params = case["params"]
    # Comprar USD = recibir USD (moneda origen) y pagar MXN al strike; vender USD = pagar la moneda origen.
    pay_source = params["side"] == "sell"
    forward = ql.FxForward(
        float(params["notional_usd"]),
        ql.USDCurrency(),
        ql.MXNCurrency(),
        float(params["strike"]),
        ctx["today"] + int(params["days"]),
        pay_source,
        0,  # sin rezago de liquidación: se paga exactamente en hoy + días
        ql.NullCalendar(),
    )
    spot = ql.QuoteHandle(ql.SimpleQuote(float(ctx["spot"])))  # MXN por USD
    forward.setPricingEngine(ql.DiscountingFxForwardEngine(ctx["curves"]["SOFR"], ctx["curves"]["TIIE-F"], spot))
    # El forward justo de QuantLib debe ser el que usó el desk; si no, el sentido de spot/monedas está invertido.
    fair = float(forward.fairForwardRate())  # en QuantLib 1.44 devuelve el número, no un ExchangeRate
    expected = float(case["inputs"]["forward"])
    if abs(fair - expected) > 1e-10 * max(1.0, abs(expected)):
        raise ValueError("forward justo de QuantLib %.12g distinto del del desk %.12g" % (fair, expected))
    # NPV() viene en la moneda origen (USD); el PV del desk va en MXN (moneda destino).
    return forward.npvTargetCurrency()


def price_fx_option(case: dict, ctx: dict) -> float:
    """Opción europea USDMXN: GarmanKohlagenProcess (USD = tasa foránea, MXN = doméstica) + AnalyticEuropeanEngine."""
    params = case["params"]
    process = ql.GarmanKohlagenProcess(
        ql.QuoteHandle(ql.SimpleQuote(float(ctx["spot"]))),
        ctx["curves"]["SOFR"],
        ctx["curves"]["TIIE-F"],
        _flat_vol(ctx["today"], case["inputs"]["vol"]),  # la σ que el desk leyó de su superficie en (K, T)
    )
    kind = ql.Option.Call if params["option_type"] == "call" else ql.Option.Put
    option = ql.VanillaOption(
        ql.PlainVanillaPayoff(kind, float(params["strike"])),
        ql.EuropeanExercise(ctx["today"] + int(params["days"])),
    )
    option.setPricingEngine(ql.AnalyticEuropeanEngine(process))
    return _sign(params["side"]) * float(params["notional_usd"]) * option.NPV()


def price_equity_option(case: dict, ctx: dict) -> float:
    """Opción europea sobre acción: BlackScholesMertonProcess con tasa y dividendo continuos + AnalyticEuropeanEngine."""
    params = case["params"]
    today = ctx["today"]
    day_count = ql.Actual365Fixed()
    dividend = ql.YieldTermStructureHandle(ql.FlatForward(today, float(params["dividend_yield"]), day_count, ql.Continuous))
    risk_free = ql.YieldTermStructureHandle(ql.FlatForward(today, float(params["rate"]), day_count, ql.Continuous))
    process = ql.BlackScholesMertonProcess(
        ql.QuoteHandle(ql.SimpleQuote(float(params["spot"]))),
        dividend,
        risk_free,
        _flat_vol(today, params["volatility"]),
    )
    kind = ql.Option.Call if params["option_type"] == "call" else ql.Option.Put
    option = ql.VanillaOption(
        ql.PlainVanillaPayoff(kind, float(params["strike"])),
        ql.EuropeanExercise(today + int(case["inputs"]["days"])),
    )
    option.setPricingEngine(ql.AnalyticEuropeanEngine(process))
    return float(params["quantity"]) * option.NPV()


PRICERS = {"fx_forward": price_fx_forward, "fx_option": price_fx_option, "equity_option": price_equity_option}

METHODS = {
    "fx_forward": (
        "FxForward (USD origen, MXN destino, strike como tasa pactada, pago en hoy + días sin rezago, NullCalendar) + "
        "DiscountingFxForwardEngine con la curva SOFR para USD, la TIIE-F para MXN y el spot del snapshot; PV en MXN "
        "(npvTargetCurrency); el forward justo de QuantLib se comprueba contra el del desk"
    ),
    "fx_option": (
        "VanillaOption europea (PlainVanillaPayoff, vencimiento hoy + días) + GarmanKohlagenProcess (SOFR foránea, "
        "TIIE-F doméstica) + AnalyticEuropeanEngine; volatilidad plana (BlackConstantVol, Actual365Fixed) igual a la "
        "σ que el desk leyó de su superficie en (K, T), por lo que se valida la fórmula y no la interpolación de la "
        "superficie; PV = ±nocional USD × NPV"
    ),
    "equity_option": (
        "VanillaOption europea + BlackScholesMertonProcess con FlatForward continuo (Actual365Fixed) para tasa y "
        "dividendo, BlackConstantVol y spot propios del caso, vencimiento hoy + días + AnalyticEuropeanEngine; "
        "PV = cantidad × NPV (no depende de las curvas del snapshot)"
    ),
}
