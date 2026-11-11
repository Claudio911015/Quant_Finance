"""Pricers de QuantLib con Hull-White para cap/floor y swaption.

Solo para el entorno de QuantLib (Python 3.12). Cada pricer tiene la firma `pricer(case, ctx) -> float`
(PV en la moneda y con el signo de `pv_desk`); `ctx` es el de `run_quantlib.build_context`.

El modelo es `ql.HullWhite` ajustado a la misma curva de descuento que usa el desk, con la `a` y la
`sigma` que el desk aplicó a cada caso (`case["inputs"]["hw_a"]`, `["hw_sigma"]`). La curva no se
vuelve a interpolar: es la reconstruida en `ql_curves` desde los DF del desk.
"""
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))

import QuantLib as ql  # noqa: E402

METHODS = {
    "cap_floor": (
        "ql.Cap / ql.Floor sobre una pierna ql.IborLeg (NullCalendar, ACT/360, sin rezago de fijación, "
        "fechas today + i·period_days) con ql.AnalyticCapFloorEngine y ql.HullWhite(a, sigma) ajustado a la "
        "curva del desk. El primer caplet fija hoy y vale su intrínseco, como en el desk."
    ),
    "swaption": (
        "ql.Swaption europea (ejercicio en today + round(expiry_years·365) días) sobre un ql.VanillaSwap "
        "(fija y flotante con fechas expiración + i·period_days, NullCalendar, ACT/360, spread 0) con "
        "ql.JamshidianSwaptionEngine y ql.HullWhite(a, sigma) ajustado a la curva del desk."
    ),
}


def _dates(start: ql.Date, step_days: int, count: int) -> List[ql.Date]:
    """count + 1 fechas start, start + step, ... start + count·step (días calendario)."""
    return [start + i * step_days for i in range(count + 1)]


def _schedule(dates: List[ql.Date]) -> ql.Schedule:
    return ql.Schedule(dates, ql.NullCalendar(), ql.Unadjusted)


def _index(name: str, period_days: int, currency: ql.Currency, handle: ql.YieldTermStructureHandle) -> ql.IborIndex:
    """Índice de tasa a `period_days` días, ACT/360, sin calendario ni ajuste de fechas."""
    return ql.IborIndex(
        name, ql.Period(period_days, ql.Days), 0, currency, ql.NullCalendar(), ql.Unadjusted, False,
        ql.Actual360(), handle,
    )


def price_cap_floor(case: dict, ctx: dict) -> float:
    params, inputs = case["params"], case["inputs"]
    curve = params["curve"]
    handle = ctx["curves"][curve]
    period_days = int(inputs["period_days"])
    index = _index("%s-%dD" % (curve, period_days), period_days, ctx["currencies"][curve], handle)

    schedule = _schedule(_dates(ctx["today"], period_days, int(params["periods"])))
    leg = ql.IborLeg([float(params["notional"])], schedule, index, ql.Actual360(), ql.Unadjusted, [0])
    strike = [float(params["strike"])]
    instrument = ql.Cap(leg, strike) if params["cap_type"] == "cap" else ql.Floor(leg, strike)

    model = ql.HullWhite(handle, float(inputs["hw_a"]), float(inputs["hw_sigma"]))
    instrument.setPricingEngine(ql.AnalyticCapFloorEngine(model, handle))
    return instrument.NPV()


def price_swaption(case: dict, ctx: dict) -> float:
    params, inputs = case["params"], case["inputs"]
    curve = params["curve"]
    handle = ctx["curves"][curve]
    period_days = int(inputs["period_days"])
    index = _index("%s-%dD" % (curve, period_days), period_days, ctx["currencies"][curve], handle)

    expiry = ctx["today"] + int(round(float(params["expiry_years"]) * 365))
    schedule = _schedule(_dates(expiry, period_days, int(inputs["payments"])))
    swap_type = ql.Swap.Payer if params["swaption_type"] == "payer" else ql.Swap.Receiver
    swap = ql.VanillaSwap(
        swap_type, float(params["notional"]), schedule, float(params["strike"]), ql.Actual360(),
        schedule, index, 0.0, ql.Actual360(),
    )
    swaption = ql.Swaption(swap, ql.EuropeanExercise(expiry))

    model = ql.HullWhite(handle, float(inputs["hw_a"]), float(inputs["hw_sigma"]))
    swaption.setPricingEngine(ql.JamshidianSwaptionEngine(model, handle))
    return swaption.NPV()


PRICERS = {"cap_floor": price_cap_floor, "swaption": price_swaption}
