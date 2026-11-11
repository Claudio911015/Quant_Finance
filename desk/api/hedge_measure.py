"""Medición de un periodo de cobertura y sus asientos (D4 y D5 del diseño del corte 4).

Aquí no hay fórmulas de valuación: el instrumento y el derivado hipotético se valúan con
`valuation.value_trade`, lo liquidado sale de `settlement.settled_flows`, y este módulo solo resta,
reparte entre ORI y resultados, y arma los asientos. Todo en MXN. `F` es la fracción designada.
"""
import json
import math
import sqlite3
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List

from desk.api import fixings as fixing_store
from desk.api import hedges, lifecycle, market, portfolio, settlement
from desk.api import valuation as trade_valuation
from desk.api.errors import ApiError
from desk.api.market import MarketContext
from desk.api.validation import ensure_finite, text

_CENT = Decimal("0.01")
_MEMO_DERIVATIVE = "Cambio de valor razonable del derivado (fracción designada)"
_MEMO_CASH = "Liquidación del derivado en el periodo"
_MEMO_ROUNDING = "Residuo de redondeo"


def _previous(rel: Dict[str, Any]) -> Dict[str, Any]:
    """Punto de partida del periodo: el último cierre o, si no hay, la designación (acumulados en 0)."""
    if rel["periods"]:
        last = rel["periods"][-1]
        r = last["result"]
        return {
            "snapshot": last["snapshot_id"], "as_of": last["as_of"],
            "inst_cum": r["inst_cum"], "hypo_cum": r["hypo_cum"], "oci": r["oci"],
        }
    d = rel["designation"]
    return {
        "snapshot": d["snapshot"], "as_of": date.fromisoformat(d["as_of"]),
        "inst_cum": 0.0, "hypo_cum": 0.0, "oci": 0.0,
    }


def measure(
    rel: Dict[str, Any],
    trade: Dict[str, Any],
    mkt: MarketContext,
    fixings: Dict[str, Dict[date, float]],
) -> Dict[str, Any]:
    """`result` del periodo al `as_of` de `mkt`, sin escribir nada.

    Es el `result` del contrato sin `data_quality` (la calidad de datos es del snapshot y la añade
    `close_period`, que es quien lo lee de la base).
    """
    prev = _previous(rel)
    design = rel["designation"]
    fraction = float(rel["fraction"])
    v_inst = trade_valuation.value_trade(trade, mkt, fixings)
    v_hypo = trade_valuation.value_trade(hedges.hypothetical_trade(rel), mkt, fixings)
    pv_inst, pv_hypo = float(v_inst["pv_mxn"]), float(v_hypo["pv_mxn"])
    inst_cum = fraction * (pv_inst - design["pv_inst"])
    hypo_cum = pv_hypo - design["pv_hypo"]
    d_inst_cum = inst_cum - prev["inst_cum"]
    d_hypo_cum = hypo_cum - prev["hypo_cum"]
    flows, flow_warnings = settlement.settled_flows(trade, fixings, prev["as_of"], mkt.as_of, mkt.spot, mkt)
    settled_period = fraction * sum((f["amount_mxn"] for f in flows), 0.0)

    if rel["hedge_type"] == "cash_flow":
        if inst_cum * hypo_cum > 0:
            oci = math.copysign(min(abs(inst_cum), abs(hypo_cum)), inst_cum)
        else:
            oci = 0.0
        d_oci = oci - prev["oci"]
        ineffectiveness = d_inst_cum - d_oci
        recycled = settled_period
        item_adjustment = 0.0
        fv_result = 0.0
        identity_residual = (d_inst_cum + settled_period) - (d_oci + ineffectiveness + recycled)
    else:  # fair_value (solo `fixed_loan`)
        oci = d_oci = 0.0
        item_adjustment = -d_hypo_cum
        ineffectiveness = d_inst_cum + item_adjustment
        recycled = 0.0
        fv_result = d_inst_cum + item_adjustment + settled_period
        identity_residual = (d_inst_cum + settled_period) - (ineffectiveness - item_adjustment + settled_period)

    result = {
        "prev_snapshot": prev["snapshot"],
        "prev_as_of": prev["as_of"].isoformat(),
        "trade_status": v_inst["status"],
        "hedge_type": rel["hedge_type"],
        "fraction": fraction,
        "pv_inst": pv_inst,
        "pv_hypo": pv_hypo,
        "inst_cum": inst_cum,
        "hypo_cum": hypo_cum,
        "d_inst_cum": d_inst_cum,
        "d_hypo_cum": d_hypo_cum,
        "settled_period": settled_period,
        "settled_flows": flows,
        "oci": oci,
        "d_oci": d_oci,
        "ineffectiveness": ineffectiveness,
        "recycled": recycled,
        "item_adjustment": item_adjustment,
        "fv_result": fv_result,
        "instrument_pnl": d_inst_cum + settled_period,
        "identity_residual": identity_residual,
        "warnings": settlement.merge_warnings(v_inst["warnings"], v_hypo["warnings"], flow_warnings),
    }
    result["entries"] = journal(rel["hedge_type"], result)
    return result


def _cents(amount: float) -> int:
    return int((Decimal(repr(amount)).quantize(_CENT, ROUND_HALF_UP) * 100).to_integral_value())


def journal(hedge_type: str, figures: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Asientos `{"account","debit","credit","memo"}` del periodo a partir de sus cifras.

    Cada línea nace como un importe con signo (`+` = cargo), se redondea a centavos y se omite si
    queda en 0. El descuadre por redondeo se absorbe en la última línea de la cuenta de resultados
    principal del tipo de cobertura (se crea si no hay ninguna), así `Σcargos == Σabonos` al centavo.
    """
    if hedge_type == "cash_flow":
        raw = [
            (hedges.ACC_DERIVATIVE, figures["d_inst_cum"], _MEMO_DERIVATIVE),
            (hedges.ACC_OCI, -figures["d_oci"], "Porción efectiva a la reserva de cobertura"),
            (hedges.ACC_INEFFECTIVENESS, -figures["ineffectiveness"], "Inefectividad del periodo"),
            (hedges.ACC_CASH, figures["settled_period"], _MEMO_CASH),
            (hedges.ACC_RECYCLING, -figures["recycled"], "Reciclaje: flujo cubierto ocurrido en el periodo"),
        ]
    else:
        raw = [
            (hedges.ACC_DERIVATIVE, figures["d_inst_cum"], _MEMO_DERIVATIVE),
            (hedges.ACC_FV_RESULT, -figures["d_inst_cum"], "Cambio del derivado a resultados"),
            (hedges.ACC_ITEM_ADJ, figures["item_adjustment"], "Ajuste de valor razonable de la partida cubierta"),
            (hedges.ACC_FV_RESULT, -figures["item_adjustment"], "Ajuste de la partida contra resultados"),
            (hedges.ACC_CASH, figures["settled_period"], _MEMO_CASH),
            (hedges.ACC_FV_RESULT, -figures["settled_period"], "Liquidación del derivado a resultados"),
        ]
    lines = [[account, _cents(amount), memo] for account, amount, memo in raw]
    lines = [line for line in lines if line[1] != 0]
    residual = sum(line[1] for line in lines)
    if residual:
        main = hedges.MAIN_RESULT_ACCOUNT[hedge_type]
        idx = [i for i, line in enumerate(lines) if line[0] == main]
        if idx:
            lines[idx[-1]][1] -= residual
            if lines[idx[-1]][1] == 0:
                del lines[idx[-1]]
        else:
            lines.append([main, -residual, _MEMO_ROUNDING])
    return [
        {
            "account": account,
            "debit": max(cents, 0) / 100.0,
            "credit": max(-cents, 0) / 100.0,
            "memo": memo,
        }
        for account, cents, memo in lines
    ]


def close_period(conn: sqlite3.Connection, hedge_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Cierra un periodo (`POST /api/hedges/<id>/periods`): mide, asienta y devuelve el periodo público.

    Guarda el cierre y el evento `period_close` sin hacer `commit` (lo hace la ruta); si algo
    falla antes, no se escribe nada.
    """
    rel = hedges.load_relationship(conn, hedge_id)
    snapshot_id = text(body, "snapshot")
    mkt = market.load_context(conn, snapshot_id)
    if hedges.status(rel) == hedges.STATUS_DEDESIGNATED:
        raise ApiError(409, "La cobertura está desdesignada: ya no admite cierres de periodo", "id")
    last = hedges.last_close(rel)
    since = last if last is not None else rel["designation_date"]
    if mkt.as_of <= since:
        raise ApiError(
            409,
            "El snapshot (%s) debe ser posterior a %s, la %s de la cobertura"
            % (mkt.as_of.isoformat(), since.isoformat(), "último cierre" if last is not None else "designación"),
            "snapshot",
        )
    if rel["periods"] and rel["periods"][-1]["result"]["trade_status"] == "vencida":
        raise ApiError(
            409, "El último cierre ya fue el final (la operación venció): no hay más periodos que cerrar", "snapshot"
        )
    trade = portfolio.get_trade(conn, rel["trade_id"])
    status = lifecycle.state(trade, trade["events"], mkt.as_of)["status"]
    if status not in ("viva", "vencida"):
        raise ApiError(
            409, "La operación ya no está viva al %s: desdesigna la relación" % mkt.as_of.isoformat(), "snapshot"
        )
    result = measure(rel, trade, mkt, fixing_store.load_all(conn))
    row = conn.execute("SELECT data FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
    result["data_quality"] = market.data_quality(market.sources_of(json.loads(row["data"])))
    ensure_finite(result)  # la tabla es solo de inserción: nada no finito entra
    period = hedges.insert_period(conn, hedge_id, snapshot_id, mkt.as_of, result)
    hedges.insert_event(
        conn, hedge_id, "period_close", mkt.as_of,
        {"period_id": period["id"], "snapshot": snapshot_id, "as_of": mkt.as_of.isoformat()},
    )
    return hedges.public_period(period)
