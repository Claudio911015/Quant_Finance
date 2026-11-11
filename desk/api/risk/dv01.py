"""DV01 por curva y pilar del portafolio completo.

Convención del desk: `DV01 = PV(base) − PV(curva +1 pb)`, positivo si el PV sube cuando bajan
las tasas. La revaluación la hace cada `Product` (vía `portfolio.trade_pv_mxn`); aquí solo se
arman los choques, se restan PV y se agregan.

El paralelo sigue esa convención (coincide con `/api/price`, la exposición del VaR y el escenario
+1 pb). El DV01 por pilar usa en cambio la diferencia central `(PV(−1 pb) − PV(+1 pb)) / 2`: un
cap/floor es convexo y un choque en un solo pilar mueve las tasas forward varios pb (la rampa de
tasa cero se amplifica por T/Δpilar), así que la diferencia unilateral de cada pilar arrastra un
término de segundo orden que no suma al del paralelo (la escalera de un cap quedaba 4.0 % lejos
del paralelo). La central lo cancela y las rampas suman exactamente un desplazamiento paralelo.

Corte 3: las curvas son las de `mkt.curve_names()`; si el snapshot trae la curva dependiente `MXN-USD`
también se choca (sus pilares) y los choques a TIIE-F y SOFR la recalibran vía `MarketContext.shifted`.
"""
import sqlite3
from typing import Any, Dict, List

from desk.api import fixings as fixing_store, market, portfolio, valuation
from desk.api.market import MarketContext


def _shocked_contexts(mkt: MarketContext) -> Dict[str, Dict[str, Any]]:
    """Por curva: el contexto con +1 pb paralelo y, por pilar, el par (−1 pb, +1 pb) solo en ese pilar."""
    shocked = {}
    for curve in mkt.curve_names():
        n = len(mkt.pillars[curve])

        def at_pillar(i: int, bp: float) -> MarketContext:
            return mkt.shifted(curve=curve, pillar_shifts_bp=[bp if j == i else 0.0 for j in range(n)])

        shocked[curve] = {
            "parallel": mkt.shifted(curve=curve, parallel_bp=1.0),
            "pillars": [(at_pillar(i, -1.0), at_pillar(i, 1.0)) for i in range(n)],
        }
    return shocked


def compute_dv01(conn: sqlite3.Connection, snapshot_id: str) -> Dict[str, Any]:
    """Cuerpo de `POST /api/risk/dv01`; 404 `field: "snapshot"` si no existe.

    Solo entran las operaciones `viva` en el `as_of` del snapshot. Una operación que no se puede
    valuar (base o cualquier choque) se reporta en `errors` y no aporta a ningún total.
    """
    mkt = market.load_context(conn, snapshot_id)
    fixings = fixing_store.load_all(conn)
    shocked = _shocked_contexts(mkt)
    curves = {
        c: {
            "parallel_mxn": 0.0,
            "points": [
                {"label": p["label"], "days": p["days"], "dv01_mxn": 0.0} for p in mkt.pillars[c]
            ],
        }
        for c in mkt.curve_names()
    }
    errors: List[Dict[str, Any]] = []

    for trade in portfolio.load_trades(conn):
        if not valuation.is_live(trade, mkt.as_of):
            continue
        try:
            base = portfolio.trade_pv_mxn(trade, mkt, fixings)
            contrib = {
                c: {
                    "parallel": base - portfolio.trade_pv_mxn(trade, s["parallel"], fixings),
                    "points": [
                        (
                            portfolio.trade_pv_mxn(trade, down, fixings)
                            - portfolio.trade_pv_mxn(trade, up, fixings)
                        )
                        / 2.0
                        for down, up in s["pillars"]
                    ],
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
