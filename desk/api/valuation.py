"""Valuación de una operación a la fecha de un snapshot (envejecimiento). Se implementa en T7."""
from datetime import date
from typing import Any, Dict

from desk.api.market import MarketContext


def value_trade(trade: Dict[str, Any], mkt: MarketContext, fixings: Dict[str, Dict[date, float]]) -> Dict[str, Any]:
    """`{"status", "notional", "currency", "pv", "pv_mxn", "warnings"}` de la operación en `mkt.as_of`."""
    raise NotImplementedError("valuation.value_trade se implementa en T7")


def is_live(trade: Dict[str, Any], on: date) -> bool:
    """True si la operación está `viva` en la fecha `on`."""
    raise NotImplementedError("valuation.is_live se implementa en T7")
