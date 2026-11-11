"""P&L entre dos snapshots: `pnl = pv_to − pv_from + settled`, todo en MXN.

`settled` son los flujos liquidados en `(from.as_of, to.as_of]` (ver `settlement.settled_flows`),
incluidos los `transfer` de terminación y ejercicio. No se modela prima ni pago inicial: una
operación pactada dentro de la ventana entra con `pv_from = 0` (`no_pactada`). Única excepción, el
intercambio inicial de nocional del `xccy_swap`, que se liquida al salir del PV (ver `xccy.settled`).
"""
import sqlite3
from typing import Any, Dict

from desk.api import fixings as fixing_store
from desk.api import market, portfolio, settlement, valuation
from desk.api.errors import ApiError
from desk.api.validation import NON_FINITE_MESSAGE, has_non_finite

_FIGURES = ("pv_from", "pv_to", "settled", "pnl")


def _row(trade: Dict[str, Any], mkt_from, mkt_to, fixings) -> Dict[str, Any]:
    row = {
        "id": trade["id"],
        "product": trade["product"],
        "counterparty": trade["counterparty"],
        "status_from": None,
        "status_to": None,
        "pv_from": None,
        "pv_to": None,
        "settled": None,
        "pnl": None,
        "error": None,
        "warnings": [],
    }  # type: Dict[str, Any]
    try:
        v_from = valuation.value_trade(trade, mkt_from, fixings)
        v_to = valuation.value_trade(trade, mkt_to, fixings)
        flows, flow_warnings = settlement.settled_flows(
            trade, fixings, mkt_from.as_of, mkt_to.as_of, mkt_to.spot, mkt_to
        )
        settled = sum((f["amount_mxn"] for f in flows), 0.0)
        pnl = v_to["pv_mxn"] - v_from["pv_mxn"] + settled
        if has_non_finite((v_from["pv_mxn"], v_to["pv_mxn"], settled, pnl)):
            raise ValueError(NON_FINITE_MESSAGE)
    except Exception as e:  # nunca propaga: la fila lleva el error y no suma
        row["error"] = str(e)
        return row
    row.update(
        status_from=v_from["status"],
        status_to=v_to["status"],
        pv_from=v_from["pv_mxn"],
        pv_to=v_to["pv_mxn"],
        settled=settled,
        pnl=pnl,
        warnings=settlement.merge_warnings(v_from["warnings"], v_to["warnings"], flow_warnings),
    )
    return row


def compute_pnl(conn: sqlite3.Connection, from_id: str, to_id: str) -> Dict[str, Any]:
    """Cuerpo de `GET /api/pnl`: filas por operación y totales que cuadran con ellas.

    @raise ApiError 404 `field: "snapshot"` si un snapshot no existe; 400 `field: "to"` si el
        `as_of` de `from` es posterior al de `to`.
    """
    mkt_from = market.load_context(conn, from_id)
    mkt_to = market.load_context(conn, to_id)
    if mkt_from.as_of > mkt_to.as_of:
        raise ApiError(400, "'from' no puede ser posterior a 'to'", "to")
    fixings = fixing_store.load_all(conn)
    rows = [_row(t, mkt_from, mkt_to, fixings) for t in portfolio.load_trades(conn)]
    totals = {name: 0.0 for name in _FIGURES}
    for row in rows:
        if row["error"] is None:
            for name in _FIGURES:
                totals[name] += row[name]
    return {
        "from": {"snapshot": from_id, "as_of": mkt_from.as_of.isoformat()},
        "to": {"snapshot": to_id, "as_of": mkt_to.as_of.isoformat()},
        "total_mxn": totals["pnl"],
        "totals": totals,
        "rows": rows,
    }
