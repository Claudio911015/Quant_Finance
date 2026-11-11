"""VaR delta-normal del portafolio sobre tres factores: TIIE-F, SOFR y USDMXN.

Las exposiciones salen de re-valuar cada operación con choques pequeños del mercado
(P&L en MXN); el VaR lo calcula `qfpy.delta_normal_var`. Aquí no hay fórmulas de VaR.
"""
import sqlite3
from typing import Any, Callable, Dict, List

from desk.api import market, portfolio
from desk.api.errors import ApiError
from desk.api.market import MarketContext
from desk.api.qf import qfpy
from desk.api.validation import finite_number, number

_FX_FACTOR = "USDMXN"
_FX_BUMP_PCT = 1.0  # el delta FX se toma por diferencia central de ±1 %


def _exposure_fns(mkt: MarketContext) -> List[Callable[[Dict[str, Any], float], float]]:
    """Una función `(operación, PV base) -> exposición MXN` por factor, en orden de `mkt.factors`."""
    fns = []
    for name in mkt.factors["names"]:
        if name in market.CURVES:
            bumped = mkt.shifted(curve=name, parallel_bp=1.0)
            fns.append(lambda t, base, b=bumped: portfolio.trade_pv_mxn(t, b) - base)
        elif name == _FX_FACTOR:
            up = mkt.shifted(spot_pct=_FX_BUMP_PCT)
            down = mkt.shifted(spot_pct=-_FX_BUMP_PCT)
            width = 2 * _FX_BUMP_PCT / 100.0
            fns.append(
                lambda t, base, u=up, d=down: (
                    portfolio.trade_pv_mxn(t, u) - portfolio.trade_pv_mxn(t, d)
                )
                / width
            )
        else:
            raise ValueError("Factor de riesgo desconocido: %s" % name)
    return fns


def _factor_vols(body: Dict[str, Any], names: List[str]) -> Dict[str, float]:
    """`factor_vols` opcional y parcial: {factor: vol diaria >= 0}; 400 `field: "factor_vols"`."""
    raw = body.get("factor_vols")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ApiError(400, "'factor_vols' debe ser un objeto {factor: vol diaria}", "factor_vols")
    out = {}
    for key, v in raw.items():
        if key not in names:
            raise ApiError(
                400,
                "Factor desconocido en 'factor_vols': %s (válidos: %s)" % (key, ", ".join(names)),
                "factor_vols",
            )
        if not finite_number(v) or v < 0:
            raise ApiError(
                400, "La vol de '%s' en 'factor_vols' debe ser un número >= 0" % key, "factor_vols"
            )
        out[key] = float(v)
    return out


def compute_var(
    conn: sqlite3.Connection, snapshot_id: str, body: Dict[str, Any]
) -> Dict[str, Any]:
    """Cuerpo de `POST /api/risk/var`; valida `horizon_days`, `confidence` y `factor_vols`."""
    horizon = number(body, "horizon_days", gt=0)
    confidence = number(body, "confidence", gt=0, lt=1)
    mkt = market.load_context(conn, snapshot_id)
    names = list(mkt.factors["names"])
    units = list(mkt.factors["units"])
    vols = list(mkt.factors["daily_vols"])
    overrides = _factor_vols(body, names)
    vols = [overrides.get(n, v) for n, v in zip(names, vols)]

    fns = _exposure_fns(mkt)
    exposures = [0.0] * len(names)
    errors = []
    for trade in portfolio.load_trades(conn):
        try:
            base = portfolio.trade_pv_mxn(trade, mkt)
            per_factor = [fn(trade, base) for fn in fns]
        except Exception as e:  # la operación se excluye de todos los factores
            errors.append({"id": trade["id"], "error": str(e)})
            continue
        exposures = [a + b for a, b in zip(exposures, per_factor)]

    total = qfpy.delta_normal_var(
        exposures, vols, mkt.factors["correlations"], confidence, horizon
    )
    factors = [
        {
            "factor": name,
            "unit": unit,
            "exposure_mxn": exposure,
            "daily_vol": vol,
            "var_mxn": qfpy.delta_normal_var([exposure], [vol], [[1.0]], confidence, horizon),
        }
        for name, unit, exposure, vol in zip(names, units, exposures, vols)
    ]
    return {
        "snapshot": snapshot_id,
        "var_mxn": total,
        "horizon_days": horizon,
        "confidence": confidence,
        "factors": factors,
        "errors": errors,
    }
