"""Valuación y flujos envejecidos exactos del bono y del cap/floor (corte 3, T9).

Antes (corte 2) se acortaba el plazo a periodos enteros; aquí se arma el instrumento con el
calendario que de verdad queda a la fecha de valuación (`qfpy.Bond` y `qfpy.CapFloor` con calendario
explícito) y la matemática sigue en C++.

* Bono: pagos `i = 1..periods` en el día `start_date + round(i / frequency × 365)` (el mismo redondeo
  que fija `maturity_date`); quedan los que caen después del `as_of`. Tiempos exactos
  `i / frequency − elapsed / 365`; el cupón corrido sale de `prevCouponTime`. El PV es el precio
  **sucio**. Un cupón con fecha igual al `as_of` ya está liquidado y no entra.
* Cap/floor: fronteras `k × period_days` días desde `start_date`. Entran los caplets cuyo inicio
  `(k − 1) × period_days` es `>= elapsed`; el caplet ya fijado (inicio anterior al `as_of`) no entra
  al valor y tampoco se liquida (decisión declarada en Metodología).
* Descuento: si la curva de la operación es `TIIE-F`, con `mkt.mxn_discount` (`MXN-USD` bajo colateral
  USD); `SOFR` siempre con SOFR. El cap/floor proyecta con su curva y descuenta con `price_dual`.
"""
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from desk.api.market import CURVES, MarketContext
from desk.api.qf import qfpy

# `valuation` y `settlement` importan este módulo: sus funciones se importan dentro de cada
# función de aquí para no crear un ciclo de importación.

_DAYS_PER_YEAR = 365.0


def _discount_key(curve: str, mkt: MarketContext) -> str:
    """Curva de descuento de un producto de la curva `curve` (solo `TIIE-F` cambia con el colateral)."""
    return getattr(mkt, "mxn_discount", "TIIE-F") if curve == "TIIE-F" else curve


def _to_mxn(pv: float, curve: str, mkt: MarketContext) -> float:
    return pv * mkt.spot if CURVES[curve]["currency"] == "USD" else pv


def _pay_day(i: int, frequency: float) -> int:
    """Día (desde `start_date`) del pago `i` del bono; igual que el vencimiento de `portfolio._tenor_days`."""
    return int(round(i / frequency * _DAYS_PER_YEAR))


# ------------------------------------------------------------------------------- bono

def _remaining_payments(
    trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext
) -> Tuple[int, List[Tuple[int, int]]]:
    """`(elapsed, [(i, día del pago i)])` de los pagos que quedan después del `as_of`."""
    frequency = float(terms["frequency"])
    elapsed = (mkt.as_of - trade["start_date"]).days
    remaining = []  # type: List[Tuple[int, int]]
    for i in range(1, int(terms["periods"]) + 1):
        day = _pay_day(i, frequency)
        if day > elapsed:
            remaining.append((i, day))
    return elapsed, remaining


def aged_bond(trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext) -> "qfpy.Bond":
    """Bono con los pagos que quedan a `mkt.as_of`, con cupón corrido.

    El día del pacto (`elapsed = 0`) es el mismo bono de `/api/price`. Con inicio futuro
    (`elapsed < 0`) los tiempos se alargan en `|elapsed| / 365` y el cupón corrido es 0.

    @raise ValueError si ya no queda ningún pago (el bono está vencido).
    """
    frequency = float(terms["frequency"])
    elapsed, remaining = _remaining_payments(trade, terms, mkt)
    if not remaining:
        raise ValueError("El bono ya pagó su último cupón: no hay flujos por valuar")
    offset = elapsed / _DAYS_PER_YEAR
    pay_times = [i / frequency - offset for i, _ in remaining]
    # `round` de los días puede dejar el cupón anterior hasta medio día DESPUÉS del as_of en tiempo
    # exacto; C++ exige `prevCouponTime <= 0`, así que se recorta a 0 (cupón corrido nulo).
    previous = min(0.0, (remaining[0][0] - 1) / frequency - offset)
    return qfpy.Bond(float(terms["face"]), float(terms["coupon_rate"]), frequency, pay_times, previous)


def _bond_curve(terms: Dict[str, Any], mkt: MarketContext) -> "qfpy.YieldCurve":
    return mkt.curves[_discount_key(terms["curve"], mkt)]


def bond_pv_mxn(trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext) -> float:
    """PV en MXN (precio sucio) del bono envejecido, descontado con la curva del colateral."""
    pv = aged_bond(trade, terms, mkt).price(_bond_curve(terms, mkt))
    return float(_to_mxn(pv, terms["curve"], mkt))


def bond_quote(trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext) -> Optional[Dict[str, Any]]:
    """`{"dirty", "clean", "accrued", "currency"}` del bono (moneda de su curva); `dirty − clean = accrued`."""
    bond = aged_bond(trade, terms, mkt)
    curve = _bond_curve(terms, mkt)
    return {
        "dirty": bond.price(curve),
        "clean": bond.clean_price(curve),
        "accrued": bond.accrued_interest(),
        "currency": CURVES[terms["curve"]]["currency"],
    }


def _coupon_amount(face: float, coupon_rate: float, frequency: float) -> float:
    """Cupón por periodo con la misma convención del constructor de `qfpy.Bond` (viene de C++)."""
    return float(qfpy.Bond(face, coupon_rate, 2, frequency).cash_flow_schedule()[0][1])


def bond_settled(
    trade: Dict[str, Any],
    fixings: Dict[str, Dict[date, float]],
    d0: date,
    d1: date,
    fallback_spot: float,
    flows: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]],
) -> None:
    """Cupones (`coupon`) y amortización (`redemption`, en el último pago) del bono en `(d0, d1]`.

    Un pago con fecha `P` cuenta si la operación seguía `viva` el día `P − 1` (igual que los cupones del
    `irs`). Los flujos en USD (curva SOFR) se convierten a MXN con el FIX `USDMXN` de su fecha o, si
    falta, con `fallback_spot` (aviso `fx_fallback`).
    """
    from desk.api import lifecycle, settlement, valuation

    _, params = valuation.normalized(trade)
    currency = CURVES[params["curve"]]["currency"]
    frequency, periods = float(params["frequency"]), int(params["periods"])
    start, events = trade["start_date"], trade["events"]
    fallback_days = []  # type: List[date]
    for i in range(1, periods + 1):
        day = start + timedelta(days=_pay_day(i, frequency))
        if day > d1:
            break
        if day <= d0 or lifecycle.state(trade, events, day - timedelta(days=1))["status"] != "viva":
            continue
        terms = lifecycle.state(trade, events, day)["terms"]  # nocional y cupón vigentes al pago
        fix = settlement._fix(fixings, day, fallback_spot, fallback_days) if currency == "USD" else 1.0
        coupon = _coupon_amount(float(terms["face"]), float(terms["coupon_rate"]), frequency)
        flows.append(settlement._flow(day, "coupon", coupon, currency, coupon * fix))
        if i == periods:
            face = float(terms["face"])
            flows.append(settlement._flow(day, "redemption", face, currency, face * fix))
    if fallback_days:
        warnings.append(settlement._fx_fallback(fallback_days))


def projected_bond(trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext) -> List[Dict[str, Any]]:
    """Flujos por cobrar del bono envejecido (los mismos que valúa `bond_pv_mxn`), con `df` y `pv`.

    Un flujo por pago; el último trae el principal dentro de `amount`. La fecha es la del calendario del
    bono (`start_date + round(i / frequency × 365)`), la misma de los flujos liquidados.
    """
    bond = aged_bond(trade, terms, mkt)
    curve = _bond_curve(terms, mkt)
    currency = CURVES[terms["curve"]]["currency"]
    _, remaining = _remaining_payments(trade, terms, mkt)
    out = []
    for (_, day), (t, amount) in zip(remaining, bond.cash_flow_schedule()):
        df = curve.discount_factor(t)
        out.append(
            {
                "date": (trade["start_date"] + timedelta(days=day)).isoformat(),
                "kind": "coupon",
                "status": "projected",
                "amount": amount,
                "currency": currency,
                "df": df,
                "pv": amount * df,
            }
        )
    return out


# ------------------------------------------------------------------------- cap/floor

def aged_cap_floor(
    trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext
) -> Optional["qfpy.CapFloor"]:
    """Cap/floor con los caplets que no han fijado a `mkt.as_of`, o `None` si no queda ninguno.

    Fronteras en `k × period_days` días desde `start_date`; entra el caplet `k` si `(k − 1) × period_days
    >= elapsed` (uno que fija hoy entra con su valor intrínseco). El caplet ya fijado no entra. Con
    `elapsed <= 0` es el instrumento de `/api/price`.
    """
    period_days = CURVES[terms["curve"]]["period_days"]
    periods = int(terms["periods"])
    elapsed = (mkt.as_of - trade["start_date"]).days
    first = max(1, -(-elapsed // period_days) + 1)  # menor k con (k − 1) × period_days >= elapsed
    if first > periods:
        return None
    boundaries = [(k * period_days - elapsed) / _DAYS_PER_YEAR for k in range(first - 1, periods + 1)]
    kind = qfpy.CapFloorType.Cap if terms["cap_type"] == "cap" else qfpy.CapFloorType.Floor
    hw = mkt.hw[terms["curve"]]
    return qfpy.CapFloor(
        kind,
        float(terms["notional"]),
        float(terms["strike"]),
        boundaries,
        hw["a"],
        hw["sigma"],
        qfpy.DayCountConvention.ACT_360,
    )


def cap_floor_pv_mxn(trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext) -> float:
    """PV en MXN del cap/floor envejecido; 0 si ya fijaron todos sus caplets."""
    cap = aged_cap_floor(trade, terms, mkt)
    if cap is None:
        return 0.0
    curve = terms["curve"]
    discount = _discount_key(curve, mkt)
    if discount != curve:  # colateral USD: se proyecta con TIIE-F y se descuenta con MXN-USD
        pv = cap.price_dual(mkt.curves[curve], mkt.curves[discount])
    else:
        pv = cap.price(mkt.curves[curve])
    return float(_to_mxn(pv, curve, mkt))
