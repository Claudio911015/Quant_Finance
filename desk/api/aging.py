"""Valuación y flujos envejecidos del bono y del cap/floor (gancho del corte 3).

Corte 3, T4: aquí vive, movido tal cual, el comportamiento que ya tenían (plazo acortado con
`valuation.shortened`, bono sin liquidación derivada, calendario proyectado del pricer). T9 lo
reemplaza por la valuación exacta; hasta entonces ningún resultado cambia.
"""
from datetime import date
from typing import Any, Dict, List, Optional

from desk.api.market import MarketContext
from desk.api.pricing import PRODUCTS

# `valuation` y `settlement` importan este módulo: sus funciones se importan dentro de cada
# función de aquí para no crear un ciclo de importación.


def bond_pv_mxn(trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext) -> float:
    """PV en MXN del bono con el plazo acortado a lo que falta."""
    from desk.api import valuation

    days = (trade["maturity_date"] - mkt.as_of).days
    return float(PRODUCTS["bond"].pv_mxn(valuation.shortened("bond", terms, days), mkt))


def cap_floor_pv_mxn(trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext) -> float:
    """PV en MXN del cap/floor con los periodos acortados a lo que falta."""
    from desk.api import valuation

    days = (trade["maturity_date"] - mkt.as_of).days
    return float(PRODUCTS["cap_floor"].pv_mxn(valuation.shortened("cap_floor", terms, days), mkt))


def bond_settled(
    trade: Dict[str, Any],
    fixings: Dict[str, Dict[date, float]],
    d0: date,
    d1: date,
    fallback_spot: float,
    flows: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]],
) -> None:
    """Flujos liquidados del bono en `(d0, d1]`: hoy ninguno, solo el aviso `no_settlement`."""
    from desk.api import settlement

    settlement._no_settlement(trade, d0, d1, warnings)


def projected_bond(trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext) -> List[Dict[str, Any]]:
    """Flujos del bono acortado a lo que falta (el mismo que `bond_pv_mxn`), según su pricer."""
    from desk.api import valuation

    shortened = valuation.shortened("bond", terms, (trade["maturity_date"] - mkt.as_of).days)
    priced = PRODUCTS["bond"].price(shortened, mkt)
    return [
        {
            "date": cf["date"],
            "kind": "coupon",
            "status": "projected",
            "amount": cf["amount"],
            "currency": priced["currency"],
            "df": cf["df"],
            "pv": cf["pv"],
        }
        for cf in priced["cashflows"]
    ]


def bond_quote(trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext) -> Optional[Dict[str, Any]]:
    """`{"dirty", "clean", "accrued", "currency"}` del bono vivo; hoy `None` (lo implementa T9)."""
    return None
