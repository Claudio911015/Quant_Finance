"""Flujos liquidados y calendario de flujos de la ficha.

Los flujos ya fijados no se guardan: se derivan de términos + fijaciones + eventos (D3).

* `irs`: un cupón neto por cada pago en la ventana; fijo `N·K·τ` (ACT/360) y flotante
  `N·(factor − 1)` con el factor de las fijaciones diarias del periodo (`qfpy.compound_overnight`).
* `fx_forward`: al vencimiento, `notional_usd × (FIX − strike)` en MXN con el FIX `USDMXN`.
* `transfer` (terminación o ejercicio): su importe en MXN.
* `bond`: lo despacha a `aging.bond_settled`, que emite los cupones (`coupon`) y la amortización
  (`redemption`) en `(d0, d1]` con la misma regla de «viva el día anterior» que el `irs`.
* `cap_floor`, `swaption`: sin flujo derivado, solo el aviso `no_settlement`.
* `xccy_swap`: lo despacha a `xccy.settled` (gancho del corte 3).

Un pago con fecha `P` está liquidado si la operación seguía `viva` el día `P − 1`: así el último
cupón (fecha de vencimiento, en que el estado ya es `vencida`) y el cupón del día de una
terminación cuentan, y el P&L entre dos snapshots no pierde el cupón que sale del PV.
"""
import sqlite3
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from desk.api import fixings as fixing_store
from desk.api import aging, calendars, collateral, lifecycle, market, portfolio, valuation, xccy
from desk.api.market import CURVES, MarketContext
from desk.api.qf import qfpy

Fixings = Dict[str, Dict[date, float]]
Flows = List[Dict[str, Any]]
Warnings = List[Dict[str, Any]]

_DAY = timedelta(days=1)
_ACT_360 = 360.0  # convención de devengo de `OisSwap` (ACT/360)
_NO_SETTLEMENT = ("cap_floor", "swaption")  # el bono liquida por `aging.bond_settled`
_MISSING_FIXING = (
    "Faltan fijaciones de %s en %d día(s): se usó la última publicada anterior o, "
    "si no hay, la tasa a un día de la curva"
)


def _flow(day: date, kind: str, amount: float, currency: str, amount_mxn: float) -> Dict[str, Any]:
    return {
        "date": day.isoformat(),
        "kind": kind,
        "amount": amount,
        "currency": currency,
        "amount_mxn": amount_mxn,
    }


def _merged(warnings: Warnings) -> Warnings:
    """Un solo aviso por `(code, index)`: fechas sin repetir y ordenadas, en orden de aparición."""
    merged = {}  # type: Dict[Tuple[str, Optional[str]], Dict[str, Any]]
    for w in warnings:
        key = (w["code"], w["index"])
        if key not in merged:
            merged[key] = {"code": w["code"], "index": w["index"], "dates": set(), "message": w["message"]}
        merged[key]["dates"].update(w["dates"])
    out = []
    for (code, index), w in merged.items():
        dates = sorted(w["dates"])
        message = _MISSING_FIXING % (index, len(dates)) if code == "missing_fixing" else w["message"]
        out.append({"code": code, "index": index, "dates": dates, "message": message})
    return out


def merge_warnings(*groups: Warnings) -> Warnings:
    """Avisos de varias fuentes en una sola lista, un aviso por `(code, index)`."""
    return _merged([w for g in groups for w in g])


def _fx_fallback(days: List[date]) -> Dict[str, Any]:
    return {
        "code": "fx_fallback",
        "index": "USDMXN",
        "dates": [d.isoformat() for d in days],
        "message": "Sin FIX USDMXN en esas fechas: el flujo en USD se convirtió al spot del snapshot final",
    }


def _fix(fixings: Fixings, day: date, fallback_spot: float, fallback_days: List[date]) -> float:
    """FIX de `day`; si falta, el spot de respaldo y la fecha queda anotada en `fallback_days`.

    En un día inhábil de México (fin de semana o feriado) no se publica FIX: se usa el último
    publicado, sin aviso, siempre que entre ese FIX y `day` no haya un día hábil sin FIX (un hueco
    real de datos sigue avisando `fx_fallback`, no se arrastra un FIX viejo en silencio). En un día
    hábil sin FIX, o sin ningún FIX anterior, se usa el spot de respaldo como siempre.
    """
    published = fixings.get("USDMXN", {})
    value = published.get(day)
    if value is not None:
        return value
    if not calendars.is_business_day("MX", day):
        last = max((d for d in published if d < day), default=None)
        if last is not None:
            probe = day - _DAY
            while probe > last and not calendars.is_business_day("MX", probe):
                probe -= _DAY
            if probe == last:
                return published[last]
    fallback_days.append(day)
    return fallback_spot


def _irs_coupons(
    trade: Dict[str, Any],
    fixings: Fixings,
    d0: date,
    d1: date,
    fallback_spot: float,
    mkt: Optional[MarketContext],
    flows: Flows,
    warnings: Warnings,
) -> None:
    _, params = valuation.normalized(trade)
    curve = params["curve"]
    if params["fixed_rate"] is None:
        raise ValueError("Falta el parámetro 'fixed_rate'")
    if mkt is None:
        raise ValueError("Los cupones de un irs necesitan el contexto de mercado (fijaciones faltantes)")
    currency = CURVES[curve]["currency"]
    start, events = trade["start_date"], trade["events"]
    pay = qfpy.ois_payment_days((trade["maturity_date"] - start).days, CURVES[curve]["period_days"])
    fallback_days = []  # type: List[date]
    previous = 0
    for k in pay:
        first, previous = previous, k
        day = start + timedelta(days=k)
        if day > d1:
            break
        if day <= d0 or lifecycle.state(trade, events, day - _DAY)["status"] != "viva":
            continue
        terms = lifecycle.state(trade, events, day)["terms"]  # nocional y precio vigentes al pago
        factor = valuation.accrued_factor(
            curve, start + timedelta(days=first), day, fixings, mkt, warnings
        )
        tau = (k - first) / _ACT_360
        fixed = terms["notional"] * terms["fixed_rate"] * tau
        floating = terms["notional"] * (factor - 1.0)
        amount = floating - fixed if terms["side"] == "payer" else fixed - floating
        fix = _fix(fixings, day, fallback_spot, fallback_days) if currency == "USD" else 1.0
        flows.append(_flow(day, "coupon", amount, currency, amount * fix))
    if fallback_days:
        warnings.append(_fx_fallback(fallback_days))


def _forward_settlement(
    trade: Dict[str, Any],
    fixings: Fixings,
    d0: date,
    d1: date,
    fallback_spot: float,
    flows: Flows,
    warnings: Warnings,
) -> None:
    maturity = trade["maturity_date"]
    if not d0 < maturity <= d1:
        return
    st = lifecycle.state(trade, trade["events"], maturity - _DAY)
    if st["status"] != "viva":
        return
    terms = st["terms"]
    fallback_days = []  # type: List[date]
    fix = _fix(fixings, maturity, fallback_spot, fallback_days)
    amount = terms["notional_usd"] * (fix - terms["strike"]) * (1.0 if terms["side"] == "buy" else -1.0)
    flows.append(_flow(maturity, "settlement", amount, "MXN", amount))
    if fallback_days:
        warnings.append(_fx_fallback(fallback_days))


def _no_settlement(trade: Dict[str, Any], d0: date, d1: date, warnings: Warnings) -> None:
    maturity = trade["maturity_date"]
    if d0 < maturity <= d1 and lifecycle.state(trade, trade["events"], maturity - _DAY)["status"] == "viva":
        warnings.append(
            {
                "code": "no_settlement",
                "index": None,
                "dates": [maturity.isoformat()],
                "message": "Venció %s sin liquidación derivada (fuera de alcance): su flujo no entra al P&L"
                % trade["product"],
            }
        )


def settled_flows(
    trade: Dict[str, Any],
    fixings: Fixings,
    d0: date,
    d1: date,
    fallback_spot: float,
    mkt: Optional[MarketContext] = None,
) -> Tuple[Flows, Warnings]:
    """`(flujos, avisos)` liquidados con fecha en `(d0, d1]`, ordenados por fecha.

    Cada flujo es `{"date" (ISO), "kind": "coupon" | "settlement" | "transfer" | "exchange" |
    "redemption", "amount", "currency", "amount_mxn"}` (el del `xccy_swap` añade `"leg"`). Los
    flujos en USD se convierten con el FIX `USDMXN` de su fecha o,
    si falta, con `fallback_spot` (aviso `fx_fallback`). `mkt` (el contexto del snapshot final) es
    necesario para los `irs`: da la tasa a un día de la curva cuando falta toda fijación anterior.

    @param trade operación de `portfolio.load_trades` (fechas como `date`, con `events`).
    @param fixings fijaciones de `fixings.load_all`.
    @param d0 fecha excluida del inicio de la ventana.
    @param d1 fecha incluida del fin de la ventana.
    @param fallback_spot USDMXN con que se convierte un flujo USD sin FIX.
    @param mkt contexto de mercado del snapshot final (obligatorio si la operación es un `irs`).
    @raise ValueError si la operación es ilegible, un `irs` sin `fixed_rate` o sin `mkt`.
    """
    flows = []  # type: Flows
    warnings = []  # type: Warnings
    name = trade["product"]
    if name == "irs":
        _irs_coupons(trade, fixings, d0, d1, fallback_spot, mkt, flows, warnings)
    elif name == "fx_forward":
        _forward_settlement(trade, fixings, d0, d1, fallback_spot, flows, warnings)
    elif name == "xccy_swap":
        xccy.settled(trade, fixings, d0, d1, fallback_spot, mkt, flows, warnings)
    elif name == "bond":
        aging.bond_settled(trade, fixings, d0, d1, fallback_spot, flows, warnings)
    elif name in _NO_SETTLEMENT:
        _no_settlement(trade, d0, d1, warnings)
    for e in trade["events"]:
        # --- corte 5 --- una confirmación de liquidación es registro, no un flujo nuevo
        if e["type"] == "transfer" and e["data"].get("kind") == "settlement_confirmed":
            continue
        # --- fin corte 5 ---
        if e["type"] == "transfer" and d0 < e["event_date"] <= d1:
            amount = float(e["data"]["amount"])
            flows.append(_flow(e["event_date"], "transfer", amount, "MXN", amount))
    flows.sort(key=lambda f: f["date"])
    return flows, _merged(warnings)


# ------------------------------------------------------------------- calendario proyectado

def _projected_irs(
    trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext, fixings: Fixings, warnings: Warnings
) -> Flows:
    """Cupones futuros del swap envejecido a `mkt.as_of` (el mismo instrumento que `value_trade`)."""
    curve, on = terms["curve"], mkt.as_of
    swap = valuation.aged_swap(trade, terms, mkt, fixings, warnings)
    currency = CURVES[curve]["currency"]
    return [
        {
            "date": (on + timedelta(days=cf.pay_days)).isoformat(),
            "kind": "coupon",
            "status": "projected",
            "amount": cf.net_amount,
            "currency": currency,
            "df": cf.discount_factor,
            "pv": cf.present_value,
        }
        for cf in swap.cash_flows(mkt.env)
    ]


def _with_collateral(trade: Dict[str, Any], mkt: MarketContext) -> MarketContext:
    """`mkt` con el colateral vigente de la contraparte, como lo hace `valuation.value_trade`."""
    return mkt.with_collateral(collateral.currency_on(trade, mkt.as_of))


def projected_flows(
    trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext, fixings: Fixings, warnings: Warnings
) -> Flows:
    """Flujos futuros de una operación viva a `mkt.as_of`, con `df` y `pv` (solo `irs`, `xccy_swap` y `bond`).

    Es el despacho que comparten la ficha (`trade_flows`) y el calendario del portafolio, para que sus
    `df`/`pv` sumen el PV del portafolio. Descuenta con el colateral de la contraparte (el `xccy_swap`
    ya descuenta siempre con `MXN-USD`); los demás productos devuelven `[]`.
    """
    vm = _with_collateral(trade, mkt)
    product = trade["product"]
    if product == "irs":
        return _projected_irs(trade, terms, vm, fixings, warnings)
    if product == "xccy_swap":
        return xccy.projected(trade, terms, mkt, fixings, warnings)
    if product == "bond":
        return aging.projected_bond(trade, terms, vm)
    return []


def trade_flows(conn: sqlite3.Connection, trade_id: int, snapshot_id: str) -> Dict[str, Any]:
    """Cuerpo de `GET /api/trades/<id>/flows`: liquidados y proyectados, con avisos.

    Liquidados: `settled_flows` desde el día anterior al pacto hasta el `as_of` del snapshot (sin
    `df` ni `pv`). Proyectados: los flujos que el pricer valúa a esa fecha (`projected_flows`, y solo si
    la operación está `viva`), con su `df` y `pv`. Orden por fecha.
    """
    trade = portfolio.get_trade(conn, trade_id)
    mkt = market.load_context(conn, snapshot_id)
    fixings = fixing_store.load_all(conn)
    settled, warnings = settled_flows(
        trade, fixings, trade["trade_date"] - _DAY, mkt.as_of, mkt.spot, mkt
    )
    flows = [
        {
            "date": f["date"],
            "kind": f["kind"],
            "status": "settled",
            "amount": f["amount"],
            "currency": f["currency"],
            "df": None,
            "pv": None,
            "leg": f.get("leg"),
        }
        for f in settled
    ]
    st = lifecycle.state(trade, trade["events"], mkt.as_of)
    projection_warnings = []  # type: Warnings
    bond = None
    if st["status"] == "viva":
        flows += projected_flows(trade, st["terms"], mkt, fixings, projection_warnings)
        if trade["product"] == "bond":
            bond = aging.bond_quote(trade, st["terms"], _with_collateral(trade, mkt))
    for f in flows:
        f.setdefault("leg", None)  # solo el cross currency swap distingue la pata
    flows.sort(key=lambda f: f["date"])
    return {
        "id": trade["id"],
        "snapshot": snapshot_id,
        "as_of": mkt.as_of.isoformat(),
        "flows": flows,
        "bond": bond,
        "warnings": merge_warnings(warnings, projection_warnings),
    }
