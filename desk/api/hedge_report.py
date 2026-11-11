"""Reporte de documentación y asientos de una cobertura (T6).

Solo reúne lo que ya está guardado (designación, periodos, liberaciones de reserva y sus asientos) y la prueba prospectiva
de `hedge_effectiveness`: no mide ni valúa nada nuevo. Los totales se suman en centavos enteros
para que cargos y abonos cuadren exactamente.
"""
import csv
import io
import sqlite3
from typing import Any, Dict, List, Optional

from desk.api import hedge_effectiveness, hedges, portfolio
from desk.api.db import now_iso
from desk.api.errors import ApiError

CSV_HEADER = ["period_id", "as_of", "snapshot", "account", "debit", "credit", "memo"]
_PERIOD_FIGURES = (
    "inst_cum", "hypo_cum", "oci", "d_oci", "ineffectiveness", "recycled", "item_adjustment", "fv_result",
    "settled_period",
)


def _cents(amount: float) -> int:
    return int(round(amount * 100))


def _entries_total(blocks: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Cargos y abonos de todos los bloques de asientos por cuenta, en el orden de `ACCOUNTS`, sin cuentas vacías."""
    debit = {}  # type: Dict[str, int]
    credit = {}  # type: Dict[str, int]
    for entries in blocks:
        for entry in entries:
            debit[entry["account"]] = debit.get(entry["account"], 0) + _cents(entry["debit"])
            credit[entry["account"]] = credit.get(entry["account"], 0) + _cents(entry["credit"])
    return [
        {"account": account, "debit": debit[account] / 100.0, "credit": credit[account] / 100.0}
        for account in hedges.ACCOUNTS
        if debit.get(account) or credit.get(account)
    ]


def _releases(rel: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Liberaciones de la reserva congelada (C5) en orden de fecha."""
    return [
        {
            "id": e["id"], "snapshot": e["data"]["snapshot"], "as_of": e["event_date"].isoformat(),
            "cause": e["data"]["cause"], "amount": e["data"]["amount"], "reserve_after": e["data"]["reserve_after"],
            "entries": e["data"]["entries"],
        }
        for e in rel["events"]
        if e["type"] == "reserve_release"
    ]


def _prospective(conn: sqlite3.Connection, hedge_id: int, snapshot_id: str) -> Dict[str, Any]:
    """La efectividad prospectiva; si la operación ya no está viva en ese snapshot, `{"error": mensaje}`."""
    try:
        return hedge_effectiveness.effectiveness(conn, hedge_id, snapshot_id)
    except ApiError as exc:
        if exc.status != 409:
            raise
        return {"error": exc.error}


def build_report(
    conn: sqlite3.Connection, hedge_id: int, snapshot_id: Optional[str] = None
) -> Dict[str, Any]:
    """Cuerpo de `GET /api/hedges/<id>/report`; la prueba prospectiva usa `snapshot_id` o el de designación.

    @raise ApiError 404 `id` o `snapshot`.
    """
    rel = hedges.load_relationship(conn, hedge_id)
    trade = portfolio.public_trade(portfolio.get_trade(conn, rel["trade_id"]))
    detail = hedges.public_relationship(rel)
    designation = rel["designation"]
    periods = rel["periods"]
    frozen = hedges.status(rel) == hedges.STATUS_DEDESIGNATED
    releases = _releases(rel)
    balance = hedges.oci_balance(rel)

    return {
        "id": rel["id"],
        "generated_at": now_iso(),
        "notice": hedges.NOTICE,
        "relationship": {k: v for k, v in detail.items() if k not in ("events", "periods")},
        "documentation": {
            "risk_management_objective": rel["documentation"]["risk_management_objective"],
            "hedged_risk": rel["documentation"]["hedged_risk"],
            "hedged_item": {"item_kind": rel["item_kind"], "item_terms": detail["item_terms"]},
            "hedging_instrument": {
                "trade_id": rel["trade_id"],
                "product": rel["product"],
                "counterparty": rel["counterparty"],
                "fraction": rel["fraction"],
                "notional": trade["notional"],
                "currency": trade["currency"],
                "start_date": trade["start_date"],
                "maturity_date": trade["maturity_date"],
            },
            "hedge_ratio": rel["hedge_ratio"],
            "effectiveness_method": rel["documentation"]["effectiveness_method"],
            "ineffectiveness_sources": rel["documentation"]["ineffectiveness_sources"],
        },
        "prospective": _prospective(conn, hedge_id, snapshot_id or rel["designation_snapshot"]),
        "periods": [
            {
                "id": p["id"],
                "snapshot": p["snapshot_id"],
                "as_of": p["as_of"].isoformat(),
                "data_quality": p["result"]["data_quality"],
                **{k: p["result"][k] for k in _PERIOD_FIGURES},
            }
            for p in periods
        ],
        "entries_by_period": [
            {"period_id": p["id"], "as_of": p["as_of"].isoformat(), "entries": p["result"]["entries"]}
            for p in periods
        ],
        "reserve_releases": releases,
        "entries_total": _entries_total([p["result"]["entries"] for p in periods] + [r["entries"] for r in releases]),
        "fair_value_hierarchy": {
            "level": hedges.FAIR_VALUE_LEVEL,
            "basis": hedges.FAIR_VALUE_BASIS,
            "snapshots": [
                {
                    "role": "designation",
                    "snapshot": rel["designation_snapshot"],
                    "as_of": designation["as_of"],
                    "data_quality": designation["data_quality"],
                }
            ]
            + [
                {
                    "role": "period",
                    "snapshot": p["snapshot_id"],
                    "as_of": p["as_of"].isoformat(),
                    "data_quality": p["result"]["data_quality"],
                }
                for p in periods
            ],
        },
        "reserve": {
            "balance": balance,
            "frozen": frozen,
            "note": hedges.FROZEN_NOTE if frozen and abs(balance) >= 0.005 else None,
            "released": sum((r["amount"] for r in releases), 0.0),
        },
    }


def report_csv(report: Dict[str, Any]) -> str:
    """Asientos del reporte como CSV `period_id,as_of,snapshot,account,debit,credit,memo`.

    Primero los de los periodos; después los de las liberaciones de reserva, con `period_id` vacío.
    """
    snapshot_of = {p["id"]: p["snapshot"] for p in report["periods"]}
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_HEADER)
    for block in report["entries_by_period"]:
        for e in block["entries"]:
            writer.writerow(
                [
                    block["period_id"], block["as_of"], snapshot_of[block["period_id"]], e["account"],
                    "%.2f" % e["debit"], "%.2f" % e["credit"], e["memo"],
                ]
            )
    for release in report["reserve_releases"]:
        for e in release["entries"]:
            writer.writerow(
                ["", release["as_of"], release["snapshot"], e["account"], "%.2f" % e["debit"], "%.2f" % e["credit"], e["memo"]]
            )
    return out.getvalue()
