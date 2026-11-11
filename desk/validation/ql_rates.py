"""Pricers de QuantLib para swaps OIS y bonos a tasa fija (irs, bond).

Solo para el entorno de QuantLib (Python 3.12); el backend nunca importa este módulo.

Cada pricer tiene la firma `pricer(case: dict, ctx: dict) -> float` y devuelve el PV en la moneda y con el
signo de `pv_desk`. QuantLib calcula el PV (instrumento + motor); aquí solo se arma el calendario de pagos
con las mismas fechas enteras que usa el desk.
"""
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))

import QuantLib as ql  # noqa: E402


def _schedule(today: ql.Date, offsets: List[int]) -> ql.Schedule:
    """Calendario explícito [hoy] + [hoy + d], sin calendario de feriados ni ajuste de fechas."""
    dates = [today] + [today + int(d) for d in offsets]
    return ql.Schedule(dates, ql.NullCalendar(), ql.Unadjusted)


def price_irs(case: dict, ctx: dict) -> float:
    """Swap OIS: OvernightIndexedSwap con valor telescópico y DiscountingSwapEngine sobre la misma curva."""
    params = case["params"]
    handle = ctx["curves"][params["curve"]]
    index = ql.OvernightIndex(
        "Fondeo-" + params["curve"], 0, ctx["currencies"][params["curve"]], ql.NullCalendar(), ql.Actual360(), handle
    )
    side = ql.Swap.Payer if params["side"] == "payer" else ql.Swap.Receiver
    swap = ql.OvernightIndexedSwap(
        side,
        float(params["notional"]),
        _schedule(ctx["today"], case["inputs"]["payment_days"]),
        float(params["fixed_rate"]),
        ql.Actual360(),
        index,
        0.0,
        0,
        ql.Unadjusted,
        ql.NullCalendar(),
        True,
    )
    swap.setPricingEngine(ql.DiscountingSwapEngine(handle))
    return swap.NPV()


def price_bond(case: dict, ctx: dict) -> float:
    """Bono a tasa fija: FixedRateBond ACT/365 con pagos en hoy + round(i·365/frecuencia) días, DiscountingBondEngine."""
    params = case["params"]
    handle = ctx["curves"][params["curve"]]
    # El desk paga en t = i/frecuencia años; QuantLib solo admite fechas enteras (redondeo de Python al entero par).
    offsets = [round(i * 365.0 / float(params["frequency"])) for i in range(1, int(params["periods"]) + 1)]
    bond = ql.FixedRateBond(
        0,
        float(params["face"]),
        _schedule(ctx["today"], offsets),
        [float(params["coupon_rate"])],
        ql.Actual365Fixed(),
        ql.Unadjusted,
        100.0,
        ql.Date(),
        ql.NullCalendar(),
    )
    bond.setPricingEngine(ql.DiscountingBondEngine(handle))
    return bond.NPV()


PRICERS = {"irs": price_irs, "bond": price_bond}

METHODS = {
    "irs": (
        "OvernightIndexedSwap (valor telescópico) + DiscountingSwapEngine sobre la curva del desk; "
        "calendario explícito de fechas enteras con NullCalendar y Unadjusted, fija y flotante ACT/360, "
        "sin rezago de pago ni fijaciones"
    ),
    "bond": (
        "FixedRateBond ACT/365 + DiscountingBondEngine sobre la curva del desk; fechas de pago en "
        "hoy + round(i·365/frecuencia) días (calendario explícito, NullCalendar, Unadjusted), "
        "principal al vencimiento"
    ),
}
