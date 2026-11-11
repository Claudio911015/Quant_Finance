"""VaR y déficit esperado históricos del portafolio (corte 6, D3).

Las exposiciones son las mismas del VaR paramétrico (`var._exposure_fns`); aquí solo se arma el
P&L diario `Σ exposición·cambio del factor` sobre la historia de `factor_history` y se toma el
percentil empírico. No hay fórmulas de pricing.
"""
import json
import math
import sqlite3
from typing import Any, Dict, List

from desk.api import fixings as fixing_store, market, portfolio, valuation
from desk.api.errors import ApiError
from desk.api.risk import factor_history, var
from desk.api.validation import MAX_HORIZON_DAYS, choice, integer, number

DEFAULT_WINDOW, MIN_WINDOW, MAX_WINDOW = 250, 60, 10000
HISTORY_SOURCES = ("synthetic", "observed")
OBSERVED_LABEL = "Observada: CSV cargado, FRED / MarketDataFeed y fijaciones (en ese orden de prioridad)"


def _history_label(source: str) -> str:
    return factor_history.SOURCE_LABEL["synthetic"] if source == "synthetic" else OBSERVED_LABEL


def compute_hist_var(conn: sqlite3.Connection, snapshot_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Cuerpo de `POST /api/risk/var` con `method: historical`.

    Valida `horizon_days`, `confidence`, `window_days` y `history_source` (en ese orden) y luego 404
    `snapshot`. Sin `history_source`: `synthetic` si el snapshot es todo sintético, si no `observed`.
    409 `window_days` si la historia tiene menos fechas completas que `window_days`.
    """
    horizon = number(body, "horizon_days", gt=0, le=MAX_HORIZON_DAYS)
    confidence = number(body, "confidence", gt=0, lt=1)
    window_days = integer(body, "window_days", ge=MIN_WINDOW, le=MAX_WINDOW, required=False) or DEFAULT_WINDOW
    explicit = choice(body, "history_source", HISTORY_SOURCES) if body.get("history_source") is not None else None

    row = market._fetch(conn, snapshot_id)
    data = json.loads(row["data"])
    mkt = market._build_context(row["id"], row["as_of"], data)
    if explicit is not None:
        history_source = explicit
    elif market.data_quality(market.sources_of(data)) == "synthetic":
        history_source = "synthetic"
    else:
        history_source = "observed"

    names = list(mkt.factors["names"])
    units = list(mkt.factors["units"])
    unknown = [n for n in names if n not in factor_history.FACTORS]
    if unknown:
        raise ApiError(409, "No hay historia para el factor: %s" % ", ".join(unknown), "snapshot")

    # Exposiciones: mismo recorrido que `var.compute_var` (operaciones vivas; las que fallan van a `errors`).
    fixings = fixing_store.load_all(conn)
    fns = var._exposure_fns(mkt, fixings)
    exposures = [0.0] * len(names)
    errors = []  # type: List[Dict[str, Any]]
    for trade in portfolio.load_trades(conn):
        if not valuation.is_live(trade, mkt.as_of):
            continue
        try:
            base = portfolio.trade_pv_mxn(trade, mkt, fixings)
            per_factor = [fn(trade, base) for fn in fns]
        except Exception as e:  # la operación se excluye de todos los factores
            errors.append({"id": trade["id"], "error": str(e)})
            continue
        exposures = [a + b for a, b in zip(exposures, per_factor)]

    as_of = mkt.as_of.isoformat()
    dates, series, by_source = factor_history.window(conn, history_source, as_of, window_days)
    if len(dates) < window_days:
        raise ApiError(
            409,
            "Historia insuficiente: hay %d días con los tres factores hasta el %s (se piden %d)"
            % (len(dates), as_of, window_days),
            "window_days",
        )

    # P&L diario (sin escalar) y pérdidas ordenadas de mayor a menor.
    pnl = [sum(e * series[n][t] for e, n in zip(exposures, names)) for t in range(window_days)]
    losses = sorted((0.0 - p for p in pnl), reverse=True)  # `0.0 - p` evita el -0.0
    k = max(1, math.ceil(round(window_days * (1.0 - confidence), 9)))
    scale = math.sqrt(horizon)
    var_mxn = losses[k - 1] * scale
    es_mxn = max(sum(losses[:k]) / k * scale, var_mxn)  # el máximo evita que el redondeo ponga ES bajo VaR
    worst = max(range(window_days), key=lambda t: -pnl[t])  # primera fecha de la mayor pérdida
    return {
        "snapshot": snapshot_id,
        "method": "historical",
        "var_mxn": var_mxn,
        "es_mxn": es_mxn,
        "horizon_days": horizon,
        "confidence": confidence,
        "window_days": window_days,
        "worst_day": {"date": dates[worst], "pnl_mxn": pnl[worst]},
        "history": {
            "source": history_source,
            "label": _history_label(history_source),
            "from": dates[0],
            "to": dates[-1],
            "observations": window_days,
            "by_source": by_source,
        },
        "factors": [
            {"factor": n, "unit": u, "exposure_mxn": e} for n, u, e in zip(names, units, exposures)
        ],
        "errors": errors,
    }
