"""Construcción de `MKT-LIVE` a partir de MarketDataFeed (SOFR y Tesoro) y FRED (USDMXN).

Solo se leen datos, se convierten cotizaciones con la fórmula del diseño, se miden desviaciones
estándar de series históricas y se arma el JSON del snapshot. La curva SOFR es una aproximación:
rendimientos par del Tesoro en convención OIS, sin spread de swap. Nada de pricing ni de
interpolación vive aquí.
"""
import copy
import json
import math
import sqlite3
import statistics
from typing import Any, Dict, List, Optional, Sequence, Tuple

from desk.api import marketdata, seed_market
from desk.api.errors import ApiError
from desk.api.market import LIVE_ID, _build_context

LIVE_LABEL = "Mercado vivo (SOFR aproximada)"

# (etiqueta, días, tenor del Tesoro). `1D` viene de `sofr_rates`, no del Tesoro.
SOFR_PILLARS = (
    ("1D", 1, None),
    ("1M", 30, "1M"),
    ("3M", 91, "3M"),
    ("6M", 182, "6M"),
    ("1Y", 365, "1Y"),
    ("2Y", 730, "2Y"),
    ("3Y", 1095, "3Y"),
    ("5Y", 1825, "5Y"),
    ("7Y", 2555, "7Y"),
    ("10Y", 3650, "10Y"),
)


def treasury_to_ois(y: float, days: int) -> float:
    """Rendimiento par del Tesoro `y` (decimal) en la convención de las cotizaciones OIS.

    Plazos de hasta 1 año: `y × 360/365`; más largos: `((1 + y/2)² − 1) × 360/365`.
    """
    if days <= 365:
        return y * 360.0 / 365.0
    return ((1.0 + y / 2.0) ** 2 - 1.0) * 360.0 / 365.0


def window(values: Sequence[float], what: str = "serie") -> List[float]:
    """Últimas `MAX_CHANGES + 1` observaciones; con menos de `MIN_CHANGES + 1`, 409."""
    changes = max(len(values) - 1, 0)
    if changes < marketdata.MIN_CHANGES:
        raise ApiError(
            409,
            "Historia insuficiente: %d cambios diarios de %s (mínimo %d)"
            % (changes, what, marketdata.MIN_CHANGES),
        )
    return list(values[-(marketdata.MAX_CHANGES + 1):])


def sample_std(xs: Sequence[float]) -> float:
    """Desviación estándar muestral (ddof = 1)."""
    return statistics.stdev(xs)


def daily_vol_bp(yields_decimal: Sequence[float]) -> Tuple[float, int]:
    """`(desviación estándar del cambio diario en pb, N de cambios usados)`."""
    obs = window(yields_decimal, "5Y")
    return sample_std([(b - a) * 10000.0 for a, b in zip(obs, obs[1:])]), len(obs) - 1


def daily_vol_logret(spots: Sequence[Optional[float]]) -> Tuple[float, int]:
    """`(desviación estándar del rendimiento logarítmico diario, N de cambios usados)`.

    Las observaciones faltantes (`None`, no finitas o ≤ 0) se descartan antes de tomar la
    ventana, de modo que el rendimiento une a las válidas vecinas.
    """
    valid = [s for s in spots if s is not None and math.isfinite(s) and s > 0]
    obs = window(valid, "USDMXN")
    return sample_std([math.log(b / a) for a, b in zip(obs, obs[1:])]), len(obs) - 1


def _sources(
    treasury_date: str, fx_date: str, n_sofr: int, n_fx: int
) -> Dict[str, Dict[str, Any]]:
    def synthetic(label: str) -> Dict[str, Any]:
        return {"kind": "synthetic", "label": label, "as_of": None}

    return {
        "curve:TIIE-F": synthetic("Sintética: sin datos libres (Banxico exige token)"),
        "curve:SOFR": {
            "kind": "proxy",
            "label": "Aproximada: 1D = SOFR overnight (FRBNY); resto = Treasuries par "
            "(Treasury.gov) en convención OIS, sin spread de swap",
            "as_of": treasury_date,
        },
        "spot": {
            "kind": "live",
            "label": "FRED DEXMXUS (mediodía de Nueva York; no es el FIX de Banxico)",
            "as_of": fx_date,
        },
        "surface": synthetic("Sintética: sin datos libres de volatilidad USDMXN"),
        "hw": synthetic("Sintéticos (heredados de MX-DEMO)"),
        "factor_vols": {
            "kind": "mixed",
            "label": "SOFR (%d cambios diarios) y USDMXN (%d cambios diarios) medidas; "
            "TIIE-F sintética" % (n_sofr, n_fx),
            "as_of": treasury_date,
        },
        "factor_corr": synthetic("Sintéticas (heredadas de MX-DEMO)"),
    }


def build_live_data(
    curve: Dict[str, Any],
    sofr: Dict[str, Any],
    history_5y: Sequence[Tuple[str, float]],
    fx_series: Sequence[Tuple[str, float]],
) -> Tuple[str, Dict[str, Any]]:
    """`(as_of, data)` de `MKT-LIVE`; parte de `seed_market.demo_data()` (no de la fila `MX-DEMO`).

    `curve`, `sofr` y `history_5y` tienen la forma de `marketdata`; `fx_series` es la de
    `fred.parse_dexmxus` (ascendente, solo observaciones válidas). Función pura.
    """
    vol_sofr_bp, n_sofr = daily_vol_bp([y for _, y in history_5y])
    vol_fx, n_fx = daily_vol_logret([s for _, s in fx_series])
    fx_date, spot = fx_series[-1]

    data = copy.deepcopy(seed_market.demo_data())
    rates = {}
    for label, days, tenor in SOFR_PILLARS:
        if tenor is None:
            rates["SOFR:%s" % label] = sofr["rate"]
        else:
            rates["SOFR:%s" % label] = treasury_to_ois(curve["yields"][tenor], days)
    for quote in data["quotes"]:
        if quote["id"] in rates:
            quote["rate"] = round(rates[quote["id"]], 6)
    data["fx"]["spot"] = spot
    names = data["factors"]["names"]
    data["factors"]["daily_vols"][names.index("SOFR")] = vol_sofr_bp
    data["factors"]["daily_vols"][names.index("USDMXN")] = vol_fx
    data["sources"] = _sources(curve["date"], fx_date, n_sofr, n_fx)
    return curve["date"], data


def save_live(conn: sqlite3.Connection, as_of: str, data: Dict[str, Any]) -> None:
    """Guarda `MKT-LIVE` con una sola sentencia, tras serializar y armar el bootstrap.

    Si algo falla antes (JSON no finito, bootstrap) no se escribe nada. Sin commit.
    """
    payload = json.dumps(data, allow_nan=False)
    _build_context(LIVE_ID, as_of, data)
    conn.execute(
        "INSERT OR REPLACE INTO snapshots (id, label, synthetic, as_of, data) "
        "VALUES (?, ?, 1, ?, ?)",
        (LIVE_ID, LIVE_LABEL, as_of, payload),
    )


def rebuild_live(
    conn: sqlite3.Connection, mdf_db: Any, fx_series: Sequence[Tuple[str, float]]
) -> Dict[str, Any]:
    """Lee MarketDataFeed, arma y guarda `MKT-LIVE`; sin commit.

    Devuelve `treasury_latest`, `sofr_latest`, `fred_latest`, `as_of` y `created` (`MKT-LIVE` no
    existía). Los `ApiError(409)` de la lectura y de las ventanas se propagan.
    """
    curve = marketdata.latest_treasury_curve(mdf_db)
    sofr = marketdata.latest_sofr(mdf_db)
    history = marketdata.treasury_5y_history(mdf_db)
    as_of, data = build_live_data(curve, sofr, history, fx_series)
    created = (
        conn.execute("SELECT 1 FROM snapshots WHERE id = ?", (LIVE_ID,)).fetchone() is None
    )
    save_live(conn, as_of, data)
    return {
        "treasury_latest": curve["date"],
        "sofr_latest": sofr["date"],
        "fred_latest": fx_series[-1][0],
        "as_of": as_of,
        "created": created,
    }
