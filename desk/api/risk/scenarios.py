"""Escenarios de choque paralelo, steepener y spot sobre el portafolio completo.

P&L por operación = `pv_mxn(choque) − pv_mxn(base)`; la revaluación la hace cada `Product`
(vía `portfolio.trade_pv_mxn`). Aquí solo se validan los escenarios, se arman los choques
y se suma.
"""
import sqlite3
from typing import Any, Dict, List

from desk.api import fixings as fixing_store, market, portfolio, valuation
from desk.api.errors import ApiError
from desk.api.market import MarketContext
from desk.api.validation import finite_number


_MAX_BP = 1000.0  # |bp| máximo de un choque de curva
_MIN_PCT = -90.0  # exclusivo
_MAX_PCT = 500.0  # inclusivo


def _bad(index: int, msg: str) -> ApiError:
    return ApiError(400, "Escenario %d: %s" % (index + 1, msg), "scenarios")


def _finite(spec: Dict[str, Any], key: str, index: int) -> float:
    v = spec.get(key)
    if not finite_number(v):
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
            if not isinstance(curve, str) or curve not in market.CURVES:
                raise _bad(i, "'curve' debe ser una de: %s" % ", ".join(market.CURVES))
            bp = _finite(spec, "bp", i)
            if abs(bp) > _MAX_BP:
                raise _bad(i, "'bp' debe estar entre -%g y %g" % (_MAX_BP, _MAX_BP))
            out.append({"name": name.strip(), "type": kind, "curve": curve, "bp": bp})
        elif kind == "fx_spot":
            pct = _finite(spec, "pct", i)
            if not _MIN_PCT < pct <= _MAX_PCT:
                raise _bad(i, "'pct' debe ser mayor que %g y no mayor que %g" % (_MIN_PCT, _MAX_PCT))
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


shock = _shock  # pública: la usa la efectividad prospectiva de coberturas

# Los ocho escenarios fijos de RiskScreen.tsx (mismo orden y mismos nombres): la efectividad
# prospectiva de una cobertura mide la razón de cambios sobre este mismo set.
DEFAULT_SCENARIOS = [
    {"name": "TIIE-F +50 pb", "type": "parallel", "curve": "TIIE-F", "bp": 50.0},
    {"name": "TIIE-F -50 pb", "type": "parallel", "curve": "TIIE-F", "bp": -50.0},
    {"name": "SOFR +50 pb", "type": "parallel", "curve": "SOFR", "bp": 50.0},
    {"name": "SOFR -50 pb", "type": "parallel", "curve": "SOFR", "bp": -50.0},
    {"name": "TIIE-F steepener 25 pb", "type": "steepener", "curve": "TIIE-F", "bp": 25.0},
    {"name": "SOFR steepener 25 pb", "type": "steepener", "curve": "SOFR", "bp": 25.0},
    {"name": "USDMXN +10 %", "type": "fx_spot", "pct": 10.0},
    {"name": "USDMXN -10 %", "type": "fx_spot", "pct": -10.0},
]  # type: List[Dict[str, Any]]


def run_scenarios(
    conn: sqlite3.Connection, snapshot_id: str, body: Dict[str, Any]
) -> Dict[str, Any]:
    """Cuerpo de `POST /api/risk/scenarios`; valida `body["scenarios"]` (400 `field: "scenarios"`).

    Solo entran las operaciones `viva` en el `as_of` del snapshot. Una operación que no se puede
    valuar se reporta en su fila (`error`, `pnl_mxn` nulo) y no suma al total del escenario.
    """
    specs = _validate(body)
    mkt = market.load_context(conn, snapshot_id)
    fixings = fixing_store.load_all(conn)
    trades = [t for t in portfolio.load_trades(conn) if valuation.is_live(t, mkt.as_of)]

    base: Dict[int, Any] = {}
    for t in trades:
        try:
            base[t["id"]] = portfolio.trade_pv_mxn(t, mkt, fixings)
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
                row["pnl_mxn"] = portfolio.trade_pv_mxn(t, shocked, fixings) - base[t["id"]]
                total += row["pnl_mxn"]
            except Exception as e:
                row["error"] = str(e)
            rows.append(row)
        results.append({"name": spec["name"], "total_mxn": total, "trades": rows})
    return {"snapshot": snapshot_id, "scenarios": results}
