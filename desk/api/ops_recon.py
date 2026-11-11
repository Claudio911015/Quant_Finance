"""Conciliación del PV propio contra el del banco (corte 5).

La descomposición de una diferencia (fecha, curva, tipo de cambio) es una ayuda de diagnóstico y
no hay fórmulas nuevas: todo PV sale de `valuation.value_trade`.
"""
import sqlite3
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from desk.api.market import MarketContext

DEFAULT_TOLERANCE = 0.0001        # fracción del nocional (= 0.01 %)
MAX_TOLERANCE = 0.1
EXPLAIN_CURVE_BP = 10.0           # |pb| ≤ 10 → explicable por curva
EXPLAIN_FX_PCT = 1.0              # |%| ≤ 1 → explicable por tipo de cambio
TERMS_CURVE_BP = 25.0             # sin explicación dentro de ±25 pb …
TERMS_FX_PCT = 2.0                # … o ±2 % de spot → bandera de términos
CURVE_PRODUCTS = ("irs", "cap_floor", "swaption", "bond")
FX_PRODUCTS = ("fx_forward", "fx_option")
RECON_STATUSES = ("conciliada", "explicable", "revisar")
MAX_CSV_ROWS = 5000
DISCLAIMER = "La descomposición es una ayuda de diagnóstico, no una prueba: indica qué movimiento explicaría la diferencia, no que lo haya causado."


def context_at(mkt: MarketContext, on: date) -> MarketContext:
    """Mismo mercado (curvas, spot, superficie) con otra fecha de valuación."""
    return MarketContext(
        mkt.snapshot_id, on, mkt.curves, mkt.pillars, mkt.spot, mkt.surface, mkt.hw, mkt.factors
    )


def business_day(d: date, step: int) -> date:
    """`|step|` días hábiles (lunes a viernes, sin feriados) después (`step > 0`) o antes de `d`."""
    direction = 1 if step > 0 else -1
    out = d
    for _ in range(abs(step)):
        out += timedelta(days=direction)
        while out.weekday() >= 5:
            out += timedelta(days=direction)
    return out


def create_run(conn: sqlite3.Connection, body: Dict[str, Any]) -> Dict[str, Any]:
    """Detalle de la corrida creada por `POST /api/reconciliations` (sin commit). Lo implementa T6."""
    raise NotImplementedError("create_run: pendiente (T6)")


def list_runs(conn: sqlite3.Connection, counterparty: Optional[str] = None) -> List[Dict[str, Any]]:
    """Corridas guardadas, de la más reciente a la más antigua. Lo implementa T6."""
    raise NotImplementedError("list_runs: pendiente (T6)")


def get_run(conn: sqlite3.Connection, run_id: int) -> Dict[str, Any]:
    """Detalle de una corrida guardada; 404 `id` si no existe. Lo implementa T6."""
    raise NotImplementedError("get_run: pendiente (T6)")


def run_csv(run: Dict[str, Any]) -> str:
    """Texto CSV del detalle de una corrida. Lo implementa T6."""
    raise NotImplementedError("run_csv: pendiente (T6)")


def reconcile_trade(
    trade: Dict[str, Any],
    bank_pv_mxn: float,
    mkt: MarketContext,
    fixings: Dict[str, Dict[date, float]],
    tolerance: float,
) -> Dict[str, Any]:
    """Fila conciliada de una operación (sin `line` ni `bank_*`). Lo implementa T6."""
    raise NotImplementedError("reconcile_trade: pendiente (T6)")
