"""Medición de un periodo de cobertura y sus asientos (D4 y D5 del diseño del corte 4, con C2–C5).

Aquí no hay fórmulas de valuación: el instrumento y el derivado hipotético se valúan con
`valuation.value_trade`, lo liquidado sale de `settlement.settled_flows`, y este módulo solo resta,
reparte entre ORI y resultados, y arma los asientos. Todo en MXN. `F` es la fracción designada.

Regla del menor (C3, IFRS 9 6.5.11(a)): se aplica sobre los acumulados *desde la designación* que
incluyen lo liquidado (`inst_total`, `hypo_total`), no sobre el PV limpio. El reciclaje es la parte
efectiva de lo liquidado en el periodo y la reserva es `effective_cum − Σ reciclaje`.

Asientos (C4): los importes de las cuentas de balance son la diferencia entre el saldo redondeado a
centavos de hoy y lo ya asentado en periodos anteriores, así el acumulado coincide al centavo con el
saldo; el descuadre por redondeo se absorbe en la cuenta de resultados principal del tipo.
"""
import json
import math
import sqlite3
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Tuple

from desk.api import fixings as fixing_store
from desk.api import hedges, lifecycle, market, portfolio, settlement
from desk.api import valuation as trade_valuation
from desk.api.errors import ApiError
from desk.api.market import MarketContext
from desk.api.validation import choice, ensure_finite, number, text

_CENT = Decimal("0.01")
_HALF_CENT = 0.005
_MEMO_DERIVATIVE = "Cambio de valor razonable del derivado (fracción designada)"
_MEMO_CASH = "Liquidación del derivado en el periodo"
_MEMO_ROUNDING = "Residuo de redondeo"
_MEMO_RELEASE_ORI = "Liberación de la reserva de cobertura congelada"
_MEMO_RELEASE_TO = {
    "flow_occurred": "Reciclaje de la reserva congelada: el flujo cubierto ocurrió",
    "flow_no_longer_expected": "Reserva a resultados: el flujo cubierto ya no se espera",
}
_RELEASE_TARGET = {"flow_occurred": hedges.ACC_RECYCLING, "flow_no_longer_expected": hedges.ACC_INEFFECTIVENESS}
_HINT_CLOSE = "desdesigna la relación"
_HINT_DEDESIGNATE = "usa el snapshot del último cierre (o de la designación) o uno dentro de su vigencia"


def _since(rel: Dict[str, Any]) -> Tuple[date, str]:
    """Fecha desde la que se mide (último cierre o designación) y cómo nombrarla en un mensaje."""
    last = hedges.last_close(rel)
    if last is not None:
        return last, "el último cierre"
    return rel["designation_date"], "la designación"


def _previous(rel: Dict[str, Any]) -> Dict[str, Any]:
    """Punto de partida del periodo: el último cierre o, si no hay, la designación (acumulados en 0)."""
    d = rel["designation"]
    prev = {
        "snapshot": d["snapshot"], "as_of": date.fromisoformat(d["as_of"]),
        "inst_cum": 0.0, "hypo_cum": 0.0, "oci": 0.0, "inst_total": 0.0, "hypo_total": 0.0, "effective_cum": 0.0,
        "settled_cum": 0.0, "hypo_settled_cum": 0.0,
    }  # type: Dict[str, Any]
    if rel["periods"]:
        last = rel["periods"][-1]
        r = last["result"]
        prev.update(
            snapshot=last["snapshot_id"], as_of=last["as_of"], inst_cum=r["inst_cum"], hypo_cum=r["hypo_cum"],
            oci=r["oci"], inst_total=r["inst_total"], hypo_total=r["hypo_total"], effective_cum=r["effective_cum"],
            settled_cum=sum(p["result"]["settled_period"] for p in rel["periods"]),
            hypo_settled_cum=sum(p["result"]["hypo_settled_period"] for p in rel["periods"]),
        )
    return prev


def measure(
    rel: Dict[str, Any],
    trade: Dict[str, Any],
    mkt: MarketContext,
    fixings: Dict[str, Dict[date, float]],
) -> Dict[str, Any]:
    """`result` del periodo al `as_of` de `mkt`, sin escribir nada.

    Es el `result` del contrato sin `data_quality` (la calidad de datos es del snapshot y la añade
    `_close`, que es quien lo lee de la base).
    """
    prev = _previous(rel)
    design = rel["designation"]
    fraction = float(rel["fraction"])
    hypo_trade = hedges.hypothetical_trade(rel)
    v_inst = trade_valuation.value_trade(trade, mkt, fixings)
    v_hypo = trade_valuation.value_trade(hypo_trade, mkt, fixings)
    pv_inst, pv_hypo = float(v_inst["pv_mxn"]), float(v_hypo["pv_mxn"])
    inst_cum = fraction * (pv_inst - design["pv_inst"])
    hypo_cum = pv_hypo - design["pv_hypo"]
    d_inst_cum = inst_cum - prev["inst_cum"]
    d_hypo_cum = hypo_cum - prev["hypo_cum"]
    flows, flow_warnings = settlement.settled_flows(trade, fixings, prev["as_of"], mkt.as_of, mkt.spot, mkt)
    hypo_flows, hypo_warnings = settlement.settled_flows(
        hypo_trade, fixings, prev["as_of"], mkt.as_of, mkt.spot, mkt
    )
    settled_period = fraction * sum((f["amount_mxn"] for f in flows), 0.0)
    hypo_settled_period = sum((f["amount_mxn"] for f in hypo_flows), 0.0)
    settled_cum = prev["settled_cum"] + settled_period
    inst_total = inst_cum + settled_cum
    hypo_total = hypo_cum + prev["hypo_settled_cum"] + hypo_settled_period

    if rel["hedge_type"] == "cash_flow":
        if inst_total * hypo_total > 0:
            effective_cum = math.copysign(min(abs(inst_total), abs(hypo_total)), inst_total)
        else:
            effective_cum = 0.0
        ineffectiveness = (inst_total - prev["inst_total"]) - (effective_cum - prev["effective_cum"])
        if settled_period * hypo_settled_period > 0:
            recycled = math.copysign(min(abs(settled_period), abs(hypo_settled_period)), settled_period)
        else:
            recycled = 0.0
        recycled_before = prev["effective_cum"] - prev["oci"]  # Σ reciclaje de los periodos anteriores
        if v_inst["status"] == "vencida":  # cierre final: la reserva queda exactamente en 0
            recycled = effective_cum - recycled_before
        oci = effective_cum - (recycled_before + recycled)
        d_oci = oci - prev["oci"]
        item_adjustment = 0.0
        fv_result = 0.0
        identity_residual = (d_inst_cum + settled_period) - (d_oci + recycled + ineffectiveness)
    else:  # fair_value (solo `fixed_loan`): sin reserva
        effective_cum = oci = d_oci = recycled = 0.0
        item_adjustment = -d_hypo_cum
        ineffectiveness = d_inst_cum + item_adjustment
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
        "inst_total": inst_total,
        "hypo_total": hypo_total,
        "effective_cum": effective_cum,
        "settled_period": settled_period,
        "hypo_settled_period": hypo_settled_period,
        "settled_flows": flows,
        "oci": oci,
        "d_oci": d_oci,
        "ineffectiveness": ineffectiveness,
        "recycled": recycled,
        "item_adjustment": item_adjustment,
        "fv_result": fv_result,
        "instrument_pnl": d_inst_cum + settled_period,
        "identity_residual": identity_residual,
        "warnings": settlement.merge_warnings(v_inst["warnings"], v_hypo["warnings"], flow_warnings, hypo_warnings),
    }
    balances = {  # saldo con signo (+ = cargo) de las cuentas de balance al cierre
        hedges.ACC_DERIVATIVE: inst_cum,
        hedges.ACC_OCI: -oci,
        hedges.ACC_CASH: settled_cum,
        hedges.ACC_ITEM_ADJ: -hypo_cum,
    }
    result["entries"] = journal(rel["hedge_type"], result, balances, _booked(rel))
    return result


def _cents(amount: float) -> int:
    return int((Decimal(repr(amount)).quantize(_CENT, ROUND_HALF_UP) * 100).to_integral_value())


def _entry(account: str, cents: int, memo: str) -> Dict[str, Any]:
    return {"account": account, "debit": max(cents, 0) / 100.0, "credit": max(-cents, 0) / 100.0, "memo": memo}


def _booked(rel: Dict[str, Any]) -> Dict[str, int]:
    """Centavos con signo (+ = cargo) ya asentados por cuenta: cierres de periodo y liberaciones de reserva."""
    blocks = [p["result"]["entries"] for p in rel["periods"]]
    blocks += [e["data"]["entries"] for e in rel["events"] if e["type"] == "reserve_release"]
    totals = {}  # type: Dict[str, int]
    for entries in blocks:
        for e in entries:
            totals[e["account"]] = totals.get(e["account"], 0) + int(round(e["debit"] * 100)) - int(round(e["credit"] * 100))
    return totals


def journal(
    hedge_type: str, figures: Dict[str, Any], balances: Dict[str, float], booked: Optional[Dict[str, int]] = None
) -> List[Dict[str, Any]]:
    """Asientos `{"account","debit","credit","memo"}` del periodo.

    `balances` es el saldo con signo (`+` = cargo) de `Derivado`, `ORI`, `Efectivo` y, en valor
    razonable, `Partida cubierta` al cierre; `booked`, los centavos con signo ya asentados por
    cuenta (C4). El importe de una cuenta de balance es `centavos(saldo) − asentado`. Los de
    resultados salen de `figures` (flujo de efectivo) o son la contrapartida exacta de las líneas de
    balance (valor razonable). Las líneas en 0 se omiten y el descuadre por redondeo se absorbe en la
    última línea de la cuenta de resultados principal del tipo (se crea si no hay), así
    `Σcargos == Σabonos` al centavo.
    """
    booked = booked or {}

    def move(account: str) -> int:
        return _cents(balances[account]) - booked.get(account, 0)

    if hedge_type == "cash_flow":
        raw = [
            (hedges.ACC_DERIVATIVE, move(hedges.ACC_DERIVATIVE), _MEMO_DERIVATIVE),
            (hedges.ACC_OCI, move(hedges.ACC_OCI), "Porción efectiva a la reserva de cobertura"),
            (hedges.ACC_INEFFECTIVENESS, _cents(-figures["ineffectiveness"]), "Inefectividad del periodo"),
            (hedges.ACC_CASH, move(hedges.ACC_CASH), _MEMO_CASH),
            (hedges.ACC_RECYCLING, _cents(-figures["recycled"]), "Reciclaje: flujo cubierto ocurrido en el periodo"),
        ]
    else:
        derivative, item, cash = (move(a) for a in (hedges.ACC_DERIVATIVE, hedges.ACC_ITEM_ADJ, hedges.ACC_CASH))
        raw = [
            (hedges.ACC_DERIVATIVE, derivative, _MEMO_DERIVATIVE),
            (hedges.ACC_FV_RESULT, -derivative, "Cambio del derivado a resultados"),
            (hedges.ACC_ITEM_ADJ, item, "Ajuste de valor razonable de la partida cubierta"),
            (hedges.ACC_FV_RESULT, -item, "Ajuste de la partida contra resultados"),
            (hedges.ACC_CASH, cash, _MEMO_CASH),
            (hedges.ACC_FV_RESULT, -cash, "Liquidación del derivado a resultados"),
        ]
    lines = [[account, cents, memo] for account, cents, memo in raw if cents != 0]
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
    return [_entry(account, cents, memo) for account, cents, memo in lines]


def _close(conn: sqlite3.Connection, rel: Dict[str, Any], snapshot_id: str, mkt: MarketContext, hint: str) -> Dict[str, Any]:
    """Cierra el periodo de `rel` al `as_of` de `mkt` (sin `commit`) y devuelve el periodo interno.

    `hint` completa el mensaje cuando la operación ya no está viva. Quien llama comprueba antes que
    la relación siga activa.
    """
    since, label = _since(rel)
    if mkt.as_of <= since:
        raise ApiError(
            409,
            "El snapshot (%s) debe ser posterior a %s, %s de la cobertura" % (mkt.as_of.isoformat(), since.isoformat(), label),
            "snapshot",
        )
    if rel["periods"] and rel["periods"][-1]["result"]["trade_status"] == "vencida":
        raise ApiError(
            409, "El último cierre ya fue el final (la operación venció): no hay más periodos que cerrar", "snapshot"
        )
    trade = portfolio.get_trade(conn, rel["trade_id"])
    status = lifecycle.state(trade, trade["events"], mkt.as_of)["status"]
    if status not in ("viva", "vencida"):
        raise ApiError(409, "La operación ya no está viva al %s: %s" % (mkt.as_of.isoformat(), hint), "snapshot")
    result = measure(rel, trade, mkt, fixing_store.load_all(conn))
    row = conn.execute("SELECT data FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
    result["data_quality"] = market.data_quality(market.sources_of(json.loads(row["data"])))
    ensure_finite(result)  # la tabla es solo de inserción: nada no finito entra
    period = hedges.insert_period(conn, rel["id"], snapshot_id, mkt.as_of, result)
    hedges.insert_event(
        conn, rel["id"], "period_close", mkt.as_of,
        {"period_id": period["id"], "snapshot": snapshot_id, "as_of": mkt.as_of.isoformat()},
    )
    return period


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
    return hedges.public_period(_close(conn, rel, snapshot_id, mkt, _HINT_CLOSE))


def dedesignate(conn: sqlite3.Connection, hedge_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Desdesignación (`POST /api/hedges/<id>/dedesignate {snapshot, reason, cause}`, C2).

    La fecha es el `as_of` del snapshot. Si es posterior al último cierre (o a la designación), antes
    se cierra el periodo con ese snapshot —con las mismas reglas de `close_period`— y la reserva
    congelada (`frozen_oci`) es la de ese cierre; si coincide con él, no se mide de nuevo. Quien
    llama hace `commit`; si algo falla no se escribe nada. La relación deja de contar su fracción y
    ya no admite cierres.

    Hueco de la especificación (resuelto de forma conservadora): si el snapshot es posterior al
    último cierre pero la operación ya terminó o se ejerció, o el último cierre ya fue el final,
    el cierre previo es imposible y se responde 409 `snapshot` en vez de congelar un saldo sin medir
    hasta esa fecha; siempre se puede desdesignar con el snapshot del último cierre.
    """
    rel = hedges.load_relationship(conn, hedge_id)
    snapshot_id = text(body, "snapshot")
    reason = text(body, "reason")
    cause = choice(body, "cause", hedges.DEDESIGNATION_CAUSES)
    mkt = market.load_context(conn, snapshot_id)
    if hedges.status(rel) == hedges.STATUS_DEDESIGNATED:
        raise ApiError(409, "La cobertura ya está desdesignada", "id")
    since, label = _since(rel)
    if mkt.as_of < since:
        raise ApiError(
            409,
            "El snapshot (%s) no puede ser anterior a %s, %s de la cobertura" % (mkt.as_of.isoformat(), since.isoformat(), label),
            "snapshot",
        )
    if mkt.as_of > since:
        _close(conn, rel, snapshot_id, mkt, _HINT_DEDESIGNATE)
        rel = hedges.load_relationship(conn, hedge_id)
    hedges.insert_event(
        conn, hedge_id, "dedesignation", mkt.as_of,
        {"reason": reason, "cause": cause, "snapshot": snapshot_id, "frozen_oci": hedges.oci_balance(rel)},
    )
    return hedges.public_relationship(hedges.load_relationship(conn, hedge_id))


def release_reserve(conn: sqlite3.Connection, hedge_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Liberación de la reserva congelada (`POST /api/hedges/<id>/release {snapshot, amount?, cause}`, C5).

    Solo en relaciones desdesignadas con reserva distinta de 0. `amount` va con el signo del saldo
    (`oci_balance`; por omisión, todo): no puede tener el signo contrario ni exceder el saldo (409
    `amount`, con media centésima de tolerancia para el monto tecleado a centavos). El asiento lleva
    `ORI` contra `Resultados — partida cubierta (reciclaje)` (`flow_occurred`) o contra
    `Resultados — inefectividad de cobertura` (`flow_no_longer_expected`). La fecha es el `as_of` del
    snapshot y no puede ser anterior al último evento (409 `snapshot`). Quien llama hace `commit`.
    """
    rel = hedges.load_relationship(conn, hedge_id)
    snapshot_id = text(body, "snapshot")
    cause = choice(body, "cause", hedges.RELEASE_CAUSES)
    amount = number(body, "amount", required=False)
    mkt = market.load_context(conn, snapshot_id)
    if hedges.status(rel) != hedges.STATUS_DEDESIGNATED:
        raise ApiError(409, "Solo se libera la reserva de una cobertura desdesignada", "id")
    balance = hedges.oci_balance(rel)
    if abs(balance) < _HALF_CENT:
        raise ApiError(409, "La cobertura no tiene reserva que liberar", "id")
    latest = hedges.last_event_date(rel)
    if mkt.as_of < latest:
        raise ApiError(
            409,
            "El snapshot (%s) no puede ser anterior al último evento de la cobertura (%s)"
            % (mkt.as_of.isoformat(), latest.isoformat()),
            "snapshot",
        )
    if amount is not None:
        if abs(amount) < _HALF_CENT:
            raise ApiError(400, "'amount' debe ser de al menos un centavo", "amount")
        if amount * balance < 0:
            raise ApiError(409, "El monto no puede tener signo contrario al saldo de la reserva (%.2f)" % balance, "amount")
        if abs(amount) - abs(balance) > _HALF_CENT:
            raise ApiError(409, "El monto excede el saldo de la reserva (%.2f)" % balance, "amount")
    if amount is None or abs(abs(balance) - abs(amount)) <= _HALF_CENT:
        # Todo el saldo (también un monto tecleado a centavos que lo iguala): el asiento deja `ORI` en 0.00 exacto.
        amount, released_cents, reserve_after = balance, -_booked(rel).get(hedges.ACC_OCI, 0), 0.0
    else:
        released_cents, reserve_after = _cents(amount), balance - amount
    entries = [
        _entry(hedges.ACC_OCI, released_cents, _MEMO_RELEASE_ORI),
        _entry(_RELEASE_TARGET[cause], -released_cents, _MEMO_RELEASE_TO[cause]),
    ]
    hedges.insert_event(
        conn, hedge_id, "reserve_release", mkt.as_of,
        {
            "snapshot": snapshot_id, "cause": cause, "amount": amount, "reserve_before": balance,
            "reserve_after": reserve_after, "entries": entries,
        },
    )
    return hedges.public_relationship(hedges.load_relationship(conn, hedge_id))
