"""Escenarios de choque paralelo, steepener y spot sobre el portafolio completo.

P&L por operación = `pv_mxn(choque) − pv_mxn(base)`; la revaluación la hace cada `Product`
(vía `portfolio.trade_pv_mxn`). Aquí solo se validan los escenarios, se arman los choques
y se suma.
"""
import math
import sqlite3
from typing import Any, Dict, List

from desk.api import market, portfolio
from desk.api.errors import ApiError
from desk.api.market import MarketContext


def _bad(index: int, msg: str) -> ApiError:
    return ApiError(400, "Escenario %d: %s" % (index + 1, msg), "scenarios")


def _finite(spec: Dict[str, Any], key: str, index: int) -> float:
    v = spec.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise _bad(index, "'%s' debe ser un número finito" % key)
    return float(v)


def _validate(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Escenarios normalizados (`name`, `type` y `curve`/`bp` o `pct`); 400 `field: "scenarios"`."""
    raw = body.get("scenarios")
    if not isinstance(raw, list) or not raw:
        raise ApiError(400, "'scenarios' debe ser una lista no vacía de escenarios", "scenarios")
    out = []
    for i, spec in enumerate(raw):
        if not isinstance(spec, dict):
            raise _bad(i, "debe ser un objeto")
        name = spec.get("name")
        if not isinstance(name, str) or not name.strip():
            raise _bad(i, "'name' debe ser texto no vacío")
        kind = spec.get("type")
        if kind in ("parallel", "steepener"):
            curve = spec.get("curve")
            if curve not in market.CURVES:
                raise _bad(i, "'curve' debe ser una de: %s" % ", ".join(market.CURVES))
            out.append({"name": name.strip(), "type": kind, "curve": curve,
                        "bp": _finite(spec, "bp", i)})
        elif kind == "fx_spot":
            pct = _finite(spec, "pct", i)
            if not pct > -100:
                raise _bad(i, "'pct' debe ser mayor que -100")
            out.append({"name": name.strip(), "type": kind, "pct": pct})
        else:
            raise _bad(i, "'type' debe ser uno de: parallel, steepener, fx_spot")
    return out


def _shock(mkt: MarketContext, spec: Dict[str, Any]) -> MarketContext:
    if spec["type"] == "fx_spot":
        return mkt.shifted(spot_pct=spec["pct"])
    if spec["type"] == "parallel":
        return mkt.shifted(curve=spec["curve"], parallel_bp=spec["bp"])
    # steepener: rampa lineal de -bp (primer pilar) a +bp (último), como ScenarioEngine::steepener
    n = len(mkt.pillars[spec["curve"]])
    ramp = [-spec["bp"] + 2.0 * spec["bp"] * j / max(n - 1, 1) for j in range(n)]
    return mkt.shifted(curve=spec["curve"], pillar_shifts_bp=ramp)


def run_scenarios(
    conn: sqlite3.Connection, snapshot_id: str, body: Dict[str, Any]
) -> Dict[str, Any]:
    """Cuerpo de `POST /api/risk/scenarios`; valida `body["scenarios"]` (400 `field: "scenarios"`).

    Una operación que no se puede valuar se reporta en su fila (`error`, `pnl_mxn` nulo) y no
    suma al total del escenario.
    """
    specs = _validate(body)
    mkt = market.load_context(conn, snapshot_id)
    trades = portfolio.load_trades(conn)

    base: Dict[int, Any] = {}
    for t in trades:
        try:
            base[t["id"]] = portfolio.trade_pv_mxn(t, mkt)
        except Exception as e:
            base[t["id"]] = e

    results = []
    for spec in specs:
        shocked = _shock(mkt, spec)
        rows = []
        total = 0.0
        for t in trades:
            row = {"id": t["id"], "pnl_mxn": None, "error": None}
            try:
                if isinstance(base[t["id"]], Exception):
                    raise base[t["id"]]
                row["pnl_mxn"] = portfolio.trade_pv_mxn(t, shocked) - base[t["id"]]
                total += row["pnl_mxn"]
            except Exception as e:
                row["error"] = str(e)
            rows.append(row)
        results.append({"name": spec["name"], "total_mxn": total, "trades": rows})
    return {"snapshot": snapshot_id, "scenarios": results}
