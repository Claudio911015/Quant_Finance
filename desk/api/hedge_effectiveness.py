"""Efectividad prospectiva de una relación de cobertura: términos críticos y escenarios (T4).

Compara el instrumento (la fracción designada de la operación) con la partida cubierta, que se
representa por el derivado hipotético guardado al designar. No hay fórmulas nuevas: los cambios de
valor salen de `valuation.value_trade` bajo los choques de `risk.scenarios.DEFAULT_SCENARIOS`.
"""
import sqlite3
from datetime import date
from typing import Any, Dict, List, Optional

from desk.api import fixings as fixing_store
from desk.api import hedges, lifecycle, market, portfolio, settlement
from desk.api import valuation as trade_valuation
from desk.api.errors import ApiError
from desk.api.risk import scenarios

REFERENCE_RANGE = (0.8, 1.25)
REFERENCE_NOTE = "IFRS 9 no fija un umbral de efectividad: el rango 80 %–125 % se informa solo como referencia"

_TERM_LABEL = {
    "notional": "Nocional",
    "index": "Índice",
    "currency": "Moneda",
    "start_date": "Inicio",
    "maturity_date": "Vencimiento",
    "side": "Sentido",
}
_FORWARD_SIDE_FOR = {"buy_usd": "buy", "sell_usd": "sell"}
# Lado del swap que compensa cada deuda (el mismo del derivado hipotético): quien paga variable paga fija.
_SWAP_SIDE_FOR = {"pays_floating": "payer", "receives_floating": "receiver", "pays_fixed": "receiver", "receives_fixed": "payer"}
_TOLERANCE = 1e-9  # relativa para montos y para decidir que el hipotético no se movió


def _same_amount(a: float, b: float) -> bool:
    return abs(a - b) <= _TOLERANCE * max(abs(a), abs(b), 1.0)


def _term(term: str, instrument: Any, item: Any, match: Optional[bool] = None) -> Dict[str, Any]:
    if match is None:
        match = instrument == item
    return {
        "term": term,
        "label": _TERM_LABEL[term],
        "instrument": instrument,
        "item": item,
        "result": "match" if match else "mismatch",
    }


def critical_terms(rel: Dict[str, Any], trade: Dict[str, Any], on: date) -> List[Dict[str, Any]]:
    """Comparación de términos críticos instrumento contra partida cubierta, con la operación vigente a `on`.

    Nocional: `fraction × nocional vigente` contra `hedge_ratio × nocional de la partida`. Un
    `quantity_change` posterior a la designación no tiene tratamiento especial (se usa el vigente).
    """
    state = lifecycle.state(trade, trade["events"], on)
    terms = rel["item_terms"]
    inst_notional = rel["fraction"] * state["notional"]
    if rel["item_kind"] == "forecast_fx":
        item_notional = rel["hedge_ratio"] * terms["amount_usd"]
        forward_side = state["terms"]["side"]
        return [
            _term("notional", inst_notional, item_notional, _same_amount(inst_notional, item_notional)),
            _term("currency", "USD", "USD"),
            _term("maturity_date", trade["maturity_date"].isoformat(), terms["date"].isoformat()),
            _term("side", forward_side, terms["side"], forward_side == _FORWARD_SIDE_FOR[terms["side"]]),
        ]
    item_notional = rel["hedge_ratio"] * terms["notional"]
    swap_side = state["terms"]["side"]
    return [
        _term("notional", inst_notional, item_notional, _same_amount(inst_notional, item_notional)),
        _term("index", state["terms"]["curve"], terms["index"]),
        _term("start_date", trade["start_date"].isoformat(), terms["start_date"].isoformat()),
        _term("maturity_date", trade["maturity_date"].isoformat(), terms["maturity_date"].isoformat()),
        # Un swap del lado contrario coincide en los otros cuatro términos y solo lo delata la razón negativa.
        _term("side", swap_side, terms["side"], swap_side == _SWAP_SIDE_FOR[terms["side"]]),
    ]


def _require_live(who: str, obj: Dict[str, Any], on: date) -> None:
    status = lifecycle.state(obj, obj["events"], on)["status"]
    if status != "viva":
        raise ApiError(
            409, "%s no está viva al %s (estado: %s): usa un snapshot dentro de su vigencia" % (who, on.isoformat(), status),
            "snapshot",
        )


def _pv(obj: Dict[str, Any], mkt: Any, fixings: Any) -> float:
    return float(trade_valuation.value_trade(obj, mkt, fixings)["pv_mxn"])


def assess(rel: Dict[str, Any], trade: Dict[str, Any], mkt: Any, fixings: Any) -> Dict[str, Any]:
    """Prueba prospectiva de `rel` al `as_of` de `mkt`: lo que devuelve `effectiveness` sin `id` ni `snapshot`.

    `rel` puede ser una relación aún sin guardar: solo se leen `fraction`, `hedge_ratio`, `item_kind`,
    `item_terms` y `designation["hypothetical"]`.

    @raise ApiError 409 `snapshot` si la operación o el derivado hipotético no están vivos al `as_of`.
    """
    hypothetical = hedges.hypothetical_trade(rel)
    _require_live("La operación de cobertura", trade, mkt.as_of)
    _require_live("La partida cubierta (derivado hipotético)", hypothetical, mkt.as_of)

    fraction = rel["fraction"]
    terms = rel["item_terms"]
    item_notional = terms["amount_usd"] if rel["item_kind"] == "forecast_fx" else terms["notional"]
    base_inst = trade_valuation.value_trade(trade, mkt, fixings)
    base_hypo = trade_valuation.value_trade(hypothetical, mkt, fixings)

    rows = []  # type: List[Dict[str, Any]]
    for spec in scenarios.DEFAULT_SCENARIOS:
        shocked = scenarios.shock(mkt, spec)
        d_inst = fraction * (_pv(trade, shocked, fixings) - base_inst["pv_mxn"])
        d_hypo = _pv(hypothetical, shocked, fixings) - base_hypo["pv_mxn"]
        moved = abs(d_hypo) > _TOLERANCE * max(1.0, item_notional)
        rows.append({"name": spec["name"], "d_inst": d_inst, "d_hypo": d_hypo, "ratio": d_inst / d_hypo if moved else None})

    ratios = [r["ratio"] for r in rows if r["ratio"] is not None]
    low, high = REFERENCE_RANGE
    return {
        "as_of": mkt.as_of.isoformat(),
        "critical_terms": critical_terms(rel, trade, mkt.as_of),
        "scenarios": rows,
        "economic_relationship": bool(ratios) and all(r > 0 for r in ratios),
        "in_reference_range": sum(1 for r in ratios if low <= r <= high),
        "scenarios_counted": len(ratios),
        "reference_note": REFERENCE_NOTE,
        "warnings": settlement.merge_warnings(base_inst["warnings"], base_hypo["warnings"]),
    }


def effectiveness(conn: sqlite3.Connection, hedge_id: int, snapshot_id: str) -> Dict[str, Any]:
    """Respuesta de `GET /api/hedges/<id>/effectiveness?snapshot=<id>`.

    @raise ApiError 404 `id` o `snapshot`; 409 `snapshot` si la operación o el derivado hipotético
    no están vivos al `as_of` del snapshot.
    """
    rel = hedges.load_relationship(conn, hedge_id)
    mkt = market.load_context(conn, snapshot_id)
    trade = portfolio.get_trade(conn, rel["trade_id"])
    return {"id": rel["id"], "snapshot": snapshot_id, **assess(rel, trade, mkt, fixing_store.load_all(conn))}
