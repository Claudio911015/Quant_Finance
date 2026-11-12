"""Cross currency swap USDMXN (`xccy_swap`) en el backend (corte 3, T8).

Aquí no hay matemática financiera: se arma el `qfpy.XccySwap` envejecido a la fecha del snapshot y lo
valúa C++. Convenciones del desk: ambas patas pagan cada 28 días (`market.CSA_PERIOD_DAYS`), pata USD
SOFR plana y pata MXN TIIE-F más diferencial, ACT/360, nocional constante con intercambio inicial y/o
final según `exchange`. El descuento de la pata MXN es siempre `MXN-USD` (colateral USD, como cotiza el
mercado); sin esa curva en el snapshot se usa `TIIE-F` y se avisa `no_csa_curve`.

* `aged_xccy`: el instrumento a `mkt.as_of`, con el periodo en curso y los factores acumulados de las
  fijaciones diarias de SOFR y TIIE-F (`valuation.accrued_factor`).
* `settled`: cupones de ambas patas e intercambios de nocional liquidados en `(d0, d1]` (el intercambio
  inicial, en `d0 <= start < d1`: ver `settled`).
* `projected`: flujos futuros de la ficha, los de `cash_flows` del instrumento envejecido.
* `resolve`/`at_par`: completan `fx_rate` (spot) y `spread` (diferencial par) cuando faltan.

`valuation`, `settlement`, `lifecycle` y `pricing` se importan dentro de las funciones: ellos importan
este módulo (directa o indirectamente) y un import al inicio cerraría el ciclo.
"""
import sqlite3
from datetime import date, timedelta
from typing import Any, Dict, List

from desk.api import market
from desk.api.errors import ApiError
from desk.api.market import CSA_PERIOD_DAYS, MarketContext
from desk.api.qf import qfpy
from desk.api.seed_market import SNAPSHOT_ID
from desk.api.validation import text

Fixings = Dict[str, Dict[date, float]]
Warnings = List[Dict[str, Any]]

_DAY = timedelta(days=1)
_ACT_360 = 360.0
_NO_CSA_MESSAGE = "El snapshot no trae la curva MXN-USD: el cross currency swap se descontó con TIIE-F"


def discount_curve(mkt: MarketContext) -> str:
    """Curva con que el cross currency swap descuenta su pata MXN: `MXN-USD` o, sin ella, `TIIE-F`."""
    return mkt.with_collateral("USD").mxn_discount


def aged_xccy_terms(
    trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext, fixings: Fixings, warnings: Warnings
) -> Dict[str, Any]:
    """Los términos del cross currency swap envejecido a `mkt.as_of`, tal como los recibe `qfpy.XccySwap`
    (y el motor de XVA): `{notional_usd, fx_rate, spread, start_days, pay_days, accrued_factor_usd,
    accrued_factor_mxn, side, initial_exchange, final_exchange, discount, csa_discount}`.

    Calendario `ois_payment_days((vencimiento − inicio).days, 28)` desde `start_date`; el periodo en curso
    lleva el factor acumulado de SOFR (pata USD) y de TIIE-F (pata MXN). El intercambio inicial solo
    entra si `start_date >= as_of` (y `exchange` lo pide); el final, si `exchange` lo pide. Los avisos de
    fijaciones faltantes y `no_csa_curve` se añaden a `warnings`. `discount` es la curva de la pata MXN
    y `csa_discount` es `discount == "MXN-USD"`.

    @raise ValueError si falta `fx_rate` o `spread` (ver `resolve`) o `mkt.as_of` es posterior al último pago.
    """
    from desk.api import valuation

    for name in ("fx_rate", "spread"):
        if terms.get(name) is None:
            raise ValueError("Falta el parámetro '%s'" % name)
    start, on = trade["start_date"], mkt.as_of
    pay = qfpy.ois_payment_days((trade["maturity_date"] - start).days, CSA_PERIOD_DAYS)
    elapsed = (on - start).days  # negativo si la operación aún no empieza
    first = next((i for i, k in enumerate(pay) if k > elapsed), None)  # el periodo en curso en `on`
    if first is None:
        raise ValueError("El cross currency swap ya no tiene pagos pendientes al %s" % on.isoformat())
    period_start = pay[first - 1] if first else 0
    usd = mxn = 1.0
    if period_start < elapsed:
        since = start + timedelta(days=period_start)
        usd = valuation.accrued_factor("SOFR", since, on, fixings, mkt, warnings)
        mxn = valuation.accrued_factor("TIIE-F", since, on, fixings, mkt, warnings)
    vm = mkt.with_collateral("USD")
    if vm.csa_missing:
        warnings.append(valuation._warning("no_csa_curve", None, [], _NO_CSA_MESSAGE))
    return {
        "notional_usd": terms["notional_usd"],
        "fx_rate": terms["fx_rate"],
        "spread": terms["spread"],
        "start_days": period_start - elapsed,
        "pay_days": [k - elapsed for k in pay[first:]],
        "accrued_factor_usd": usd,
        "accrued_factor_mxn": mxn,
        "side": terms["side"],
        "initial_exchange": terms["exchange"] in ("both", "initial") and start >= on,
        "final_exchange": terms["exchange"] in ("both", "final"),
        "discount": vm.mxn_discount,
        "csa_discount": vm.mxn_discount == "MXN-USD",
    }


def aged_xccy(
    trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext, fixings: Fixings, warnings: Warnings
) -> "qfpy.XccySwap":
    """El cross currency swap de la operación envejecido a `mkt.as_of` (ver `aged_xccy_terms`).

    @raise ValueError si falta `fx_rate` o `spread` (ver `resolve`) o `mkt.as_of` es posterior al último pago.
    """
    a = aged_xccy_terms(trade, terms, mkt, fixings, warnings)
    side = qfpy.XccySide.PayUsd if a["side"] == "pay_usd" else qfpy.XccySide.PayMxn
    return qfpy.XccySwap(
        a["notional_usd"],
        a["fx_rate"],
        a["spread"],
        a["start_days"],
        a["pay_days"],
        a["accrued_factor_usd"],
        a["accrued_factor_mxn"],
        side,
        a["initial_exchange"],
        a["final_exchange"],
        "SOFR",
        "TIIE-F",
        a["discount"],
    )


def resolve(trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext, fixings: Fixings) -> Dict[str, Any]:
    """`terms` con `fx_rate` (el spot del snapshot) y `spread` (el diferencial par del instrumento con
    sus fechas, en ese snapshot) completados cuando vienen vacíos; lo ya dado no se toca."""
    out = dict(terms)
    if out.get("fx_rate") is None:
        out["fx_rate"] = mkt.spot
    if out.get("spread") is None:
        probe = aged_xccy(trade, {**out, "spread": 0.0}, mkt, fixings, [])
        out["spread"] = float(probe.par_spread(mkt.env))
    return out


def pv_mxn(
    trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext, fixings: Fixings, warnings: Warnings
) -> float:
    """PV en MXN de la operación a `mkt.as_of` (descuento `MXN-USD`), desde la perspectiva de `side`."""
    return float(aged_xccy(trade, terms, mkt, fixings, warnings).npv(mkt.env))


def settled(
    trade: Dict[str, Any],
    fixings: Fixings,
    d0: date,
    d1: date,
    fallback_spot: float,
    mkt: MarketContext,
    flows: List[Dict[str, Any]],
    warnings: Warnings,
) -> None:
    """Añade a `flows` los flujos liquidados con fecha en `(d0, d1]`: el cupón de cada pata en cada pago
    (compuesto con las fijaciones diarias como un `irs`) y los intercambios de nocional (`kind: "exchange"`
    en `start_date` y `maturity_date` según `exchange`). Cada flujo lleva `leg` ("USD" o "MXN"); los USD se
    convierten a MXN con el FIX de su fecha o, si falta, con `fallback_spot` (aviso `fx_fallback`). Como en
    los demás productos, un flujo cuenta si la operación seguía `viva` el día anterior a su fecha.

    Excepción, el intercambio inicial: sigue en el PV hasta `start_date` incluido, así que se liquida en la
    ventana en que sale del PV, `d0 <= start_date < d1`, si la operación está `viva` en `start_date` (también
    la pactada ese mismo día). Cada ventana consecutiva lo cuenta una sola vez y el P&L no da un salto de
    N·(spot − fx_rate) cuando el tipo de cambio inicial no es el spot.

    @raise ValueError si falta `fx_rate`/`spread` o `mkt`.
    """
    from desk.api import lifecycle, settlement, valuation

    _, params = valuation.normalized(trade)
    for name in ("fx_rate", "spread"):
        if params[name] is None:
            raise ValueError("Falta el parámetro '%s'" % name)
    if mkt is None:
        raise ValueError("Los cupones de un cross currency swap necesitan el contexto de mercado (fijaciones faltantes)")
    start, maturity, events = trade["start_date"], trade["maturity_date"], trade["events"]
    sign = 1.0 if params["side"] == "pay_usd" else -1.0  # +1: recibe MXN y paga USD
    fallback_days = []  # type: List[date]

    def counts(day: date) -> bool:
        return d0 < day <= d1 and lifecycle.state(trade, events, day - _DAY)["status"] == "viva"

    def add(day: date, kind: str, leg: str, amount: float) -> None:
        fix = settlement._fix(fixings, day, fallback_spot, fallback_days) if leg == "USD" else 1.0
        flows.append({**settlement._flow(day, kind, amount, leg, amount * fix), "leg": leg})

    def exchange(day: date, direction: float) -> None:
        """`direction` −1 al inicio, +1 al final, vistos desde quien recibe la pata USD."""
        terms = lifecycle.state(trade, events, day)["terms"]
        n_usd = terms["notional_usd"]
        add(day, "exchange", "USD", -sign * direction * n_usd)
        add(day, "exchange", "MXN", sign * direction * n_usd * terms["fx_rate"])

    # El intercambio inicial sigue en el PV hasta `start_date` incluido (`aged_xccy`: `start >= as_of`, así el
    # pricer lo valúa al pacto y el diferencial par lo cuenta). Sale del PV en el primer snapshot posterior a
    # `start_date`, y ahí debe liquidarse para que `pnl = pv_to − pv_from + settled` no pierda N·(spot − fx_rate):
    # ventana `d0 <= start < d1` (no `(d0, d1]` como los demás flujos), y se exige que la operación viva el día
    # de inicio mismo (no el anterior: una operación pactada ese día no existía la víspera).
    if (
        params["exchange"] in ("both", "initial")
        and d0 <= start < d1
        and lifecycle.state(trade, events, start)["status"] == "viva"
    ):
        exchange(start, -1.0)
    pay = qfpy.ois_payment_days((maturity - start).days, CSA_PERIOD_DAYS)
    previous = 0
    for k in pay:
        first, previous = previous, k
        day = start + timedelta(days=k)
        if day > d1:
            break
        if not counts(day):
            continue
        terms = lifecycle.state(trade, events, day)["terms"]
        since = start + timedelta(days=first)
        tau = (k - first) / _ACT_360
        n_usd = terms["notional_usd"]
        n_mxn = n_usd * terms["fx_rate"]
        usd_leg = n_usd * (valuation.accrued_factor("SOFR", since, day, fixings, mkt, warnings) - 1.0)
        mxn_leg = n_mxn * (valuation.accrued_factor("TIIE-F", since, day, fixings, mkt, warnings) - 1.0)
        mxn_leg += n_mxn * terms["spread"] * tau
        add(day, "coupon", "USD", -sign * usd_leg)
        add(day, "coupon", "MXN", sign * mxn_leg)
    if params["exchange"] in ("both", "final") and counts(maturity):
        exchange(maturity, 1.0)
    if fallback_days:
        warnings.append(settlement._fx_fallback(fallback_days))


def projected(
    trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext, fixings: Fixings, warnings: Warnings
) -> List[Dict[str, Any]]:
    """Flujos futuros de la ficha: los de `cash_flows` del instrumento envejecido (el mismo que valúa
    `pv_mxn`), cada uno en la moneda de su pata con su factor de descuento y valor presente."""
    swap = aged_xccy(trade, terms, mkt, fixings, warnings)
    return [
        {
            "date": (mkt.as_of + timedelta(days=cf.pay_days)).isoformat(),
            "kind": cf.kind,
            "status": "projected",
            "amount": cf.amount,
            "currency": cf.leg,
            "df": cf.discount_factor,
            "pv": cf.present_value,
            "leg": cf.leg,
        }
        for cf in swap.cash_flows(mkt.env)
    ]


def at_par(
    conn: sqlite3.Connection, body: Dict[str, Any], params: Dict[str, Any], start: date, maturity: date
) -> Dict[str, Any]:
    """`params` con `fx_rate` (el spot) y `spread` (el diferencial par con las fechas finales) completados
    en el snapshot de la petición (o `MX-DEMO`): la operación nace a la par y queda guardada con ambos.
    Es el mismo instrumento que luego valúa `aged_xccy`.

    El diferencial par solo tiene sentido en la fecha de inicio: con `start` anterior al `as_of` del snapshot
    la operación ya devengó (sin fijaciones) y el diferencial que la deja en cero hoy no es el de su pacto, así
    que, si falta el diferencial, se exige capturarlo (400 `spread`)."""
    from desk.api.pricing import PRODUCTS

    mkt = market.load_context(conn, text(body, "snapshot", required=False) or SNAPSHOT_ID)
    if params.get("spread") is None and start < mkt.as_of:
        raise ApiError(
            400,
            "Para una operación que ya empezó capture el diferencial pactado: el diferencial par solo se calcula "
            "en la fecha de inicio",
            "spread",
        )
    try:
        filled = resolve({"start_date": start, "maturity_date": maturity}, params, mkt, {})
        return PRODUCTS["xccy_swap"].validate(filled)
    except ValueError as e:
        raise ApiError(400, "No se pudo fijar el diferencial par: %s" % e, "spread")
    except ApiError as e:
        raise ApiError(400, "No se pudo fijar el diferencial par: %s" % e.error, "spread")
