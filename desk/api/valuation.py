"""Valuación de una operación a la fecha de un snapshot (envejecimiento).

Cada operación se valúa en el `as_of` del snapshot con su estado vigente (`lifecycle.state`).
Aquí no hay matemática financiera: se arma el instrumento envejecido y lo valúa `qfpy`.

* `irs`: constructor envejecido de `OisSwap` (calendario por fechas, periodo en curso con el
  factor acumulado de las fijaciones diarias).
* `fx_forward`, `fx_option`, `equity_option`, `swaption`: se acorta el plazo a lo que falta.
* `cap_floor` y `bond` (aproximación declarada, sin C++ nuevo): se acortan los periodos con
  `ceil`; el caplet o cupón en curso ya fijado se omite. Viven en `aging.py`.
* `xccy_swap`: lo valúa `xccy.pv_mxn` (gancho del corte 3).

Colateral (corte 3): `value_trade` valúa con el colateral que la contraparte tiene en el `as_of`
(`collateral.currency_on`). Con colateral USD y la curva `MXN-USD` en el snapshot, el lado MXN se
descuenta con `MXN-USD` (`MarketContext.mxn_discount`); sin la curva avisa `no_csa_curve` y descuenta
con `TIIE-F`. Con colateral MXN nada cambia.
"""
import math
from bisect import bisect_left
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from desk.api import aging, calendars, collateral, lifecycle, xccy
from desk.api.market import CURVES, MarketContext
from desk.api.pricing import PRODUCTS
from desk.api.pricing.base import Product
from desk.api.qf import qfpy

_DAYS_PER_YEAR = 365.0
_OPTIONS = ("fx_option", "swaption", "equity_option")
_PV_IN_MXN = ("fx_forward", "fx_option", "equity_option", "xccy_swap")  # D6: `pv` ya viene en MXN
_MXN_RATE_PRODUCTS = ("irs", "cap_floor", "swaption", "bond")  # sensibles al colateral si su curva es TIIE-F
NO_CSA_CURVE_MESSAGE = (
    "La contraparte tiene colateral en USD pero el snapshot no trae la curva MXN-USD: "
    "se descontó con TIIE-F"
)

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


def accrued_factor(
    index: str,
    first_day: date,
    on: date,
    fixings: Fixings,
    mkt: MarketContext,
    warnings: List[Dict[str, Any]],
) -> float:
    """Factor acumulado de las fijaciones diarias de `[first_day, on)` (1 si el rango es vacío).

    Las tasas a un día solo se publican en días hábiles: la del viernes devenga también sábado y
    domingo (3 días), así que un día inhábil sin fijación no se espera ni se avisa, y se agrupa
    con el día anterior. Inhábil = sábado, domingo o feriado del calendario del índice
    (`calendars.INDEX_CALENDAR`: México para TIIE-F, EE. UU. para SOFR). Una fijación cargada en un
    día inhábil se usa tal cual, como un día más. Un día hábil sin fijación usa la última publicada
    anterior del índice y, si no hay, la tasa a un día de la curva del snapshot, y todos esos días
    se reportan en un aviso `missing_fixing`.
    """
    published = fixings.get(index, {})
    ordered = sorted(published)
    overnight = (1.0 / mkt.curves[index].discount_factor(1.0 / _DAYS_PER_YEAR) - 1.0) * 360.0

    def carried(d: date) -> float:  # última publicada anterior a `d`, o la tasa a un día de la curva
        j = bisect_left(ordered, d)  # ordered[:j] son las fijaciones anteriores a `d`
        return published[ordered[j - 1]] if j else overnight

    calendar = calendars.INDEX_CALENDAR.get(index)

    def business(d: date) -> bool:  # sin calendario conocido solo se distingue el fin de semana
        return d.weekday() < 5 if calendar is None else calendars.is_business_day(calendar, d)

    missing = []  # type: List[date]
    entries = []  # type: List[List[float]]  # [tasa, días que devenga]
    for i in range((on - first_day).days):
        d = first_day + timedelta(days=i)
        if d in published:
            entries.append([published[d], 1])
        elif not business(d) and entries:  # inhábil sin publicar: sigue la tasa anterior
            entries[-1][1] += 1
        else:
            if business(d):
                missing.append(d)
            entries.append([carried(d), 1])
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
    return qfpy.compound_overnight([e[0] for e in entries], [int(e[1]) for e in entries], 360.0)


def aged_swap_terms(
    trade: Dict[str, Any],
    terms: Dict[str, Any],
    mkt: MarketContext,
    fixings: Fixings,
    warnings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Los términos del swap envejecido a `mkt.as_of`, tal como los recibe `qfpy.OisSwap` (y el motor de XVA):
    `{notional, fixed_rate, start_days, pay_days, accrued_factor, side, curve, discount}`.

    Calendario por fechas desde `start_date` y periodo en curso con el factor acumulado de las fijaciones
    diarias (los avisos de fijaciones faltantes se añaden a `warnings`). `side` es el texto de los términos
    (`"payer"`/`"receiver"`) y `discount` la curva de descuento (solo TIIE-F cambia con el colateral).

    @raise ValueError si falta `fixed_rate` o `mkt.as_of` es posterior al último pago.
    """
    curve = terms["curve"]
    if terms["fixed_rate"] is None:
        raise ValueError("Falta el parámetro 'fixed_rate'")
    # corte 3: solo TIIE-F cambia de curva de descuento con el colateral de la contraparte (`mkt.mxn_discount`)
    discount = getattr(mkt, "mxn_discount", "TIIE-F") if curve == "TIIE-F" else curve
    start, on = trade["start_date"], mkt.as_of
    pay = qfpy.ois_payment_days((trade["maturity_date"] - start).days, CURVES[curve]["period_days"])
    elapsed = (on - start).days  # negativo si la operación aún no empieza
    first = next((i for i, k in enumerate(pay) if k > elapsed), None)  # el periodo en curso en `on`
    if first is None:
        raise ValueError("El swap ya no tiene pagos pendientes al %s" % on.isoformat())
    period_start = pay[first - 1] if first else 0
    factor = 1.0
    if period_start < elapsed:
        factor = accrued_factor(curve, start + timedelta(days=period_start), on, fixings, mkt, warnings)
    return {
        "notional": terms["notional"],
        "fixed_rate": terms["fixed_rate"],
        "start_days": period_start - elapsed,
        "pay_days": [k - elapsed for k in pay[first:]],
        "accrued_factor": factor,
        "side": terms["side"],
        "curve": curve,
        "discount": discount,
    }


def aged_swap(
    trade: Dict[str, Any],
    terms: Dict[str, Any],
    mkt: MarketContext,
    fixings: Fixings,
    warnings: List[Dict[str, Any]],
) -> "qfpy.OisSwap":
    """El swap de la operación envejecido a `mkt.as_of` (ver `aged_swap_terms`).

    Es el instrumento que valúa `value_trade` y cuyos flujos proyecta la ficha. `terms` son los
    términos vigentes (`lifecycle.state`); los avisos de fijaciones faltantes se añaden a `warnings`.

    @raise ValueError si falta `fixed_rate` o `mkt.as_of` es posterior al último pago.
    """
    a = aged_swap_terms(trade, terms, mkt, fixings, warnings)
    side = qfpy.SwapType.Payer if a["side"] == "payer" else qfpy.SwapType.Receiver
    return qfpy.OisSwap(
        a["notional"],
        a["fixed_rate"],
        a["start_days"],
        a["pay_days"],
        a["accrued_factor"],
        side,
        a["curve"],
        discount_curve_key="" if a["discount"] == a["curve"] else a["discount"],
    )


def _irs_pv(
    trade: Dict[str, Any],
    terms: Dict[str, Any],
    mkt: MarketContext,
    fixings: Fixings,
    warnings: List[Dict[str, Any]],
) -> float:
    """PV (moneda de la curva) del swap envejecido a `mkt.as_of`."""
    return float(aged_swap(trade, terms, mkt, fixings, warnings).npv(mkt.env))


def shortened(product: str, terms: Dict[str, Any], days: int) -> Dict[str, Any]:
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


def _sensitive_to_mxn_discount(product: str, terms: Dict[str, Any]) -> bool:
    """True si el PV de la operación depende de la curva con la que se descuenta el lado MXN:
    `fx_forward`, `fx_option` y los productos de tasas con curva `TIIE-F` (SOFR no cambia con el colateral)."""
    if product in ("fx_forward", "fx_option"):
        return True
    return product in _MXN_RATE_PRODUCTS and terms.get("curve") == "TIIE-F"


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
        # corte 3 (D5): todo el pricing usa `vm`, el contexto con el colateral que la contraparte tiene en
        # el `as_of`; un `mkt` que ya traiga otro colateral se ignora (manda el historial de la operación)
        vm = mkt.with_collateral(collateral.currency_on(trade, mkt.as_of))
        if vm.csa_missing and _sensitive_to_mxn_discount(name, terms):
            warnings.append(_warning("no_csa_curve", None, [], NO_CSA_CURVE_MESSAGE))
        if name == "irs":
            pv = _irs_pv(trade, terms, vm, fixings or {}, warnings)
            pv_mxn = pv * vm.spot if CURVES[terms["curve"]]["currency"] == "USD" else pv
        elif name == "xccy_swap":
            pv_mxn = pv = float(xccy.pv_mxn(trade, terms, vm, fixings or {}, warnings))
        else:
            if name == "bond":
                pv_mxn = aging.bond_pv_mxn(trade, terms, vm)
            elif name == "cap_floor":
                pv_mxn = aging.cap_floor_pv_mxn(trade, terms, vm)
            else:
                days = (trade["maturity_date"] - mkt.as_of).days
                pv_mxn = float(product.pv_mxn(shortened(name, terms, days), vm))
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
