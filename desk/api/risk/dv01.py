"""DV01 por curva y pilar del portafolio completo.

Convención del desk: `DV01 = PV(base) − PV(curva +1 pb)`, positivo si el PV sube cuando bajan
las tasas. La revaluación la hace cada `Product` (vía `portfolio.trade_pv_mxn`); aquí solo se
arman los choques, se restan PV y se agregan.
"""
import sqlite3
from typing import Any, Dict, List

from desk.api import market, portfolio
from desk.api.market import MarketContext


def _shocked_contexts(mkt: MarketContext) -> Dict[str, Dict[str, Any]]:
    """Por curva: el contexto con +1 pb paralelo y uno por pilar con +1 pb solo en ese pilar."""
    shocked = {}
    for curve in market.CURVES:
        n = len(mkt.pillars[curve])
        shocked[curve] = {
            "parallel": mkt.shifted(curve=curve, parallel_bp=1.0),
            "pillars": [
                mkt.shifted(curve=curve, pillar_shifts_bp=[1.0 if j == i else 0.0 for j in range(n)])
                for i in range(n)
            ],
        }
    return shocked


def compute_dv01(conn: sqlite3.Connection, snapshot_id: str) -> Dict[str, Any]:
    """Cuerpo de `POST /api/risk/dv01`; 404 `field: "snapshot"` si no existe.

    Una operación que no se puede valuar (base o cualquier choque) se reporta en `errors`
    y no aporta a ningún total.
    """
    mkt = market.load_context(conn, snapshot_id)
    shocked = _shocked_contexts(mkt)
    curves = {
        c: {
            "parallel_mxn": 0.0,
            "points": [
                {"label": p["label"], "days": p["days"], "dv01_mxn": 0.0} for p in mkt.pillars[c]
            ],
        }
        for c in market.CURVES
    }
    errors: List[Dict[str, Any]] = []

    for trade in portfolio.load_trades(conn):
        try:
            base = portfolio.trade_pv_mxn(trade, mkt)
            contrib = {
                c: {
                    "parallel": base - portfolio.trade_pv_mxn(trade, s["parallel"]),
                    "points": [base - portfolio.trade_pv_mxn(trade, m) for m in s["pillars"]],
                }
                for c, s in shocked.items()
            }
        except Exception as e:
            errors.append({"id": trade["id"], "error": str(e)})
            continue
        for c, v in contrib.items():
            curves[c]["parallel_mxn"] += v["parallel"]
            for point, dv01 in zip(curves[c]["points"], v["points"]):
                point["dv01_mxn"] += dv01

    return {
        "snapshot": snapshot_id,
        "total_mxn": sum(p["dv01_mxn"] for c in curves.values() for p in c["points"]),
        "parallel_mxn": sum(c["parallel_mxn"] for c in curves.values()),
        "curves": curves,
        "errors": errors,
    }
