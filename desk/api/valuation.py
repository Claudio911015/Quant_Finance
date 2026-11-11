"""Valuación de una operación a la fecha de un snapshot (envejecimiento).

Cada operación se valúa en el `as_of` del snapshot con su estado vigente (`lifecycle.state`).
Aquí no hay matemática financiera: se arma el instrumento envejecido y lo valúa `qfpy`.

* `irs`: constructor envejecido de `OisSwap` (calendario por fechas, periodo en curso con el
  factor acumulado de las fijaciones diarias).
* `fx_forward`, `fx_option`, `equity_option`, `swaption`: se acorta el plazo a lo que falta.
* `cap_floor` y `bond` (aproximación declarada, sin C++ nuevo): se acortan los periodos con
  `ceil`; el caplet o cupón en curso ya fijado se omite.
"""
import math
from bisect import bisect_left
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from desk.api import lifecycle
from desk.api.market import CURVES, MarketContext
from desk.api.pricing import PRODUCTS
from desk.api.pricing.base import Product
from desk.api.qf import qfpy

_DAYS_PER_YEAR = 365.0
_OPTIONS = ("fx_option", "swaption", "equity_option")
_PV_IN_MXN = ("fx_forward", "fx_option", "equity_option")  # D6: `pv` ya viene en MXN

Fixings = Dict[str, Dict[date, float]]


def normalized(trade: Dict[str, Any]) -> Tuple[Product, Dict[str, Any]]:
    """Producto y `params` revalidados; lanza si la operación guardada no es valuable."""
    product = PRODUCTS.get(trade["product"])
    if product is None:
        raise ValueError("Producto desconocido: %s" % trade["product"])
    if not isinstance(trade["params"], dict):
        raise ValueError("Los parámetros guardados de la operación son ilegibles")
    return product, product.validate(trade["params"])


def _warning(code: str, index: Optional[str], dates: List[date], message: str) -> Dict[str, Any]:
    return {"code": code, "index": index, "dates": [d.isoformat() for d in dates], "message": message}


def _accrued_factor(
    index: str,
    first_day: date,
    on: date,
    fixings: Fixings,
    mkt: MarketContext,
    warnings: List[Dict[str, Any]],
) -> float:
    """Factor acumulado de las fijaciones diarias de `[first_day, on)` (1 si el rango es vacío).

    Un día sin fijación usa la última publicada anterior del índice y, si no hay, la tasa a un día
    de la curva del snapshot; todos los días así se reportan en un aviso `missing_fixing`.
    """
    published = fixings.get(index, {})
    days = [first_day + timedelta(days=i) for i in range((on - first_day).days)]
    missing = [d for d in days if d not in published]
    ordered = sorted(published) if missing else []
    overnight = (1.0 / mkt.curves[index].discount_factor(1.0 / _DAYS_PER_YEAR) - 1.0) * 360.0
    rates = []
    for d in days:
        if d in published:
            rates.append(published[d])
        else:
            j = bisect_left(ordered, d)  # ordered[:j] son las fijaciones anteriores a `d`
            rates.append(published[ordered[j - 1]] if j else overnight)
    if missing:
        warnings.append(
            _warning(
                "missing_fixing",
                index,
                missing,
                "Faltan fijaciones de %s en %d día(s): se usó la última publicada anterior o, "
                "si no hay, la tasa a un día de la curva" % (index, len(missing)),
            )
        )
    return qfpy.compound_overnight(rates, [1] * len(days), 360.0)


def _irs_pv(
    trade: Dict[str, Any],
    terms: Dict[str, Any],
    mkt: MarketContext,
    fixings: Fixings,
    warnings: List[Dict[str, Any]],
) -> float:
    """PV (moneda de la curva) del swap: calendario por fechas y periodo en curso con su factor."""
    curve = terms["curve"]
    if terms["fixed_rate"] is None:
        raise ValueError("Falta el parámetro 'fixed_rate'")
    start, on = trade["start_date"], mkt.as_of
    pay = qfpy.ois_payment_days((trade["maturity_date"] - start).days, CURVES[curve]["period_days"])
    elapsed = (on - start).days  # negativo si la operación aún no empieza
    first = next(i for i, k in enumerate(pay) if k > elapsed)  # el periodo en curso en `on`
    period_start = pay[first - 1] if first else 0
    factor = 1.0
    if period_start < elapsed:
        factor = _accrued_factor(
            curve, start + timedelta(days=period_start), on, fixings, mkt, warnings
        )
    side = qfpy.SwapType.Payer if terms["side"] == "payer" else qfpy.SwapType.Receiver
    swap = qfpy.OisSwap(
        terms["notional"],
        terms["fixed_rate"],
        period_start - elapsed,
        [k - elapsed for k in pay[first:]],
        factor,
        side,
        curve,
    )
    return float(swap.npv(mkt.env))


def _shortened(product: str, terms: Dict[str, Any], days: int) -> Dict[str, Any]:
    """Términos con el plazo reescrito a los `days` días que faltan hasta el vencimiento."""
    t = dict(terms)
    if product in ("fx_forward", "fx_option"):
        t["days"] = days
    elif product == "equity_option":
        t["maturity_years"] = days / _DAYS_PER_YEAR
    elif product == "swaption":  # `maturity_date` es la expiración; el tenor del swap no cambia
        t["expiry_years"] = days / _DAYS_PER_YEAR
    elif product == "cap_floor":
        t["periods"] = -(-days // CURVES[t["curve"]]["period_days"])
    else:  # bond
        # medio día menos: el día del pacto da `periods` exactos aunque `maturity_date` redondeó
        t["periods"] = int(math.ceil((days - 0.5) * t["frequency"] / _DAYS_PER_YEAR))
    return t


def value_trade(
    trade: Dict[str, Any], mkt: MarketContext, fixings: Optional[Fixings] = None
) -> Dict[str, Any]:
    """`{"status", "notional", "currency", "pv", "pv_mxn", "warnings"}` de la operación en `mkt.as_of`.

    `notional` y `currency` son los de los términos vigentes (como `Product.describe`: la moneda
    del nocional, USD en FX); `pv` va en la moneda de `/api/price` del producto (MXN para
    `fx_forward`, `fx_option` y `equity_option`, la de la curva en el resto) y `pv_mxn` en MXN.
    Si la operación no está `viva` el PV es 0; una opción vencida sin ejercicio añade el aviso
    `expired_unexercised`. Sin `fixings` no hay fijaciones publicadas.

    @raise ValueError, ApiError o error de `qfpy` si la operación no se puede valuar.
    """
    product, _ = normalized(trade)
    st = lifecycle.state(trade, trade["events"], mkt.as_of)
    terms, status = st["terms"], st["status"]
    described = product.describe(terms, mkt.as_of)
    warnings = []  # type: List[Dict[str, Any]]
    pv = pv_mxn = 0.0
    if status == "viva":
        name = trade["product"]
        if name == "irs":
            pv = _irs_pv(trade, terms, mkt, fixings or {}, warnings)
            pv_mxn = pv * mkt.spot if CURVES[terms["curve"]]["currency"] == "USD" else pv
        else:
            days = (trade["maturity_date"] - mkt.as_of).days
            pv_mxn = float(product.pv_mxn(_shortened(name, terms, days), mkt))
            usd = name not in _PV_IN_MXN and CURVES[terms["curve"]]["currency"] == "USD"
            pv = pv_mxn / mkt.spot if usd else pv_mxn
    elif status == "vencida" and trade["product"] in _OPTIONS:
        warnings.append(
            _warning(
                "expired_unexercised",
                None,
                [trade["maturity_date"]],
                "Opción vencida sin ejercicio registrado: se valúa en 0",
            )
        )
    return {
        "status": status,
        "notional": described["notional"],
        "currency": described["currency"],
        "pv": pv,
        "pv_mxn": pv_mxn,
        "warnings": warnings,
    }


def is_live(trade: Dict[str, Any], on: date) -> bool:
    """True si la operación está `viva` en la fecha `on`.

    Una operación cuyo estado no se puede derivar (parámetros ilegibles) cuenta como viva: así
    quien recorre el portafolio la intenta valuar y reporta su error, en vez de ocultarla.
    """
    try:
        return lifecycle.state(trade, trade["events"], on)["status"] == "viva"
    except Exception:
        return True
