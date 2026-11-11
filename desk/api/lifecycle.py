"""Ciclo de vida de una operación: estado derivado de sus eventos (función pura, sin DB).

T3 solo deja las constantes del catálogo y el esqueleto de `state`; T4 lo implementa.
"""
from datetime import date
from typing import Any, Dict, List

EVENT_TYPES = (
    "execution", "reset", "transfer", "quantity_change", "terms_change", "exercise", "termination",
)
STATUSES = ("no_pactada", "viva", "vencida", "terminada", "ejercida")

# Campo de nocional de cada producto: lo que cambia un `quantity_change`.
NOTIONAL_FIELD = {
    "irs": "notional",
    "cap_floor": "notional",
    "swaption": "notional",
    "fx_forward": "notional_usd",
    "fx_option": "notional_usd",
    "bond": "face",
    "equity_option": "quantity",
}


def state(trade: Dict[str, Any], events: List[Dict[str, Any]], on: date) -> Dict[str, Any]:
    """Estado a la fecha `on`: `{"status", "terms", "notional"}`.

    @param trade operación de `portfolio.load_trades` (fechas como `date`).
    @param events eventos de la operación (con `event_date` como `date`), en cualquier orden.
    @param on fecha de consulta.
    @return estado vigente en `on`.
    """
    raise NotImplementedError("lifecycle.state se implementa en T4")
