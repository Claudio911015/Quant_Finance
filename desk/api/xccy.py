"""Gancho del cross currency swap USDMXN (`xccy_swap`) en el backend.

Corte 3, T4: solo las firmas que `valuation`, `settlement` y `portfolio` ya despachan; T8 las
implementa. Hasta entonces `xccy_swap` no está en `PRODUCTS`, así que nada las alcanza.
"""
import sqlite3
from datetime import date
from typing import Any, Dict, List

from desk.api.market import MarketContext
from desk.api.qf import qfpy

Fixings = Dict[str, Dict[date, float]]
Warnings = List[Dict[str, Any]]


def aged_xccy(
    trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext, fixings: Fixings, warnings: Warnings
) -> "qfpy.XccySwap":
    """El cross currency swap de la operación envejecido a `mkt.as_of`."""
    raise NotImplementedError("xccy.aged_xccy: lo implementa T8")


def pv_mxn(
    trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext, fixings: Fixings, warnings: Warnings
) -> float:
    """PV en MXN de la operación a `mkt.as_of` (descuento `MXN-USD`)."""
    raise NotImplementedError("xccy.pv_mxn: lo implementa T8")


def settled(
    trade: Dict[str, Any],
    fixings: Fixings,
    d0: date,
    d1: date,
    fallback_spot: float,
    mkt: MarketContext,
    flows: List[Dict[str, Any]],
    warnings: Warnings,
) -> None:
    """Añade a `flows` los flujos liquidados con fecha en `(d0, d1]` (cupones e intercambios)."""
    raise NotImplementedError("xccy.settled: lo implementa T8")


def projected(
    trade: Dict[str, Any], terms: Dict[str, Any], mkt: MarketContext, fixings: Fixings, warnings: Warnings
) -> List[Dict[str, Any]]:
    """Flujos futuros de la ficha: los de `cash_flows` del instrumento envejecido."""
    raise NotImplementedError("xccy.projected: lo implementa T8")


def at_par(
    conn: sqlite3.Connection, body: Dict[str, Any], params: Dict[str, Any], start: date, maturity: date
) -> Dict[str, Any]:
    """`params` con `fx_rate` (spot) y `spread` (el diferencial par) completados, como `_at_par`."""
    raise NotImplementedError("xccy.at_par: lo implementa T8")
