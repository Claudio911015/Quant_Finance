"""Ciclo de vida de una operación: estado derivado de sus eventos (función pura, sin DB).

Nada guarda el estado: `state` lo recalcula siempre desde la operación y sus eventos.
"""
from datetime import date
from typing import Any, Dict, List

from desk.api.pricing import PRODUCTS

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
    "xccy_swap": "notional_usd",
}


def state(trade: Dict[str, Any], events: List[Dict[str, Any]], on: date) -> Dict[str, Any]:
    """Estado a la fecha `on`: `{"status", "terms", "notional"}`.

    Aplica en orden `(event_date, id)` los eventos con fecha <= `on`: `quantity_change` cambia el
    campo de nocional del producto, `terms_change` mezcla el precio y revalida con el producto,
    `termination` y `exercise` cierran la operación. El estado sale, por precedencia, de:
    `no_pactada` (`on < trade_date`), `terminada`, `ejercida`, `vencida` (`on >= maturity_date`)
    o `viva`.

    @param trade operación de `portfolio.load_trades` (fechas como `date`).
    @param events eventos de la operación (con `event_date` como `date`), en cualquier orden.
    @param on fecha de consulta.
    @return estado vigente en `on`; `terms` son los términos vigentes y `notional` su campo de nocional.
    @raise ValueError si los parámetros guardados de la operación son ilegibles.
    """
    product = trade["product"]
    params = trade["params"]
    if product not in NOTIONAL_FIELD or not isinstance(params, dict):
        raise ValueError("Los parámetros guardados de la operación son ilegibles")
    field = NOTIONAL_FIELD[product]
    terms = dict(params)
    terminated = exercised = False
    if on >= trade["trade_date"]:
        for e in sorted(events, key=lambda ev: (ev["event_date"], ev["id"])):
            if e["event_date"] > on:
                break
            kind = e["type"]
            if kind == "quantity_change":
                terms[field] = float(e["data"]["notional"])
            elif kind == "terms_change":
                terms = PRODUCTS[product].validate({**terms, **e["data"]["terms"]})
            elif kind == "termination":
                terminated = True
            elif kind == "exercise":
                exercised = True
    if on < trade["trade_date"]:
        status = "no_pactada"
    elif terminated:
        status = "terminada"
    elif exercised:
        status = "ejercida"
    elif on >= trade["maturity_date"]:
        status = "vencida"
    else:
        status = "viva"
    return {"status": status, "terms": terms, "notional": float(terms[field])}
