"""Curvas de descuento en QuantLib reconstruidas desde los factores de descuento del desk.

Para el entorno de QuantLib (Python 3.12) y, con `build_curve`, para los exóticos de FX del backend (`desk/api/pricing/fx_exotics.py`).

El desk interpola linealmente la tasa cero continua con t = días/365 y extrapola plana la tasa cero
fuera de [primer pilar, último pilar]. QuantLib lo reproduce con un `ZeroCurve` lineal en cero continua
y Actual365Fixed, con un nodo en el día 0 (cero del primer pilar) y otro en el día `FAR_DAYS`
(cero del último pilar).
"""
import math
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

import QuantLib as ql  # noqa: E402

import common  # noqa: E402

INTERPOLATION = (
    "ZeroCurve lineal en tasa cero continua, Actual365Fixed, plana fuera de los pilares "
    "(nodos en el día 0 y en el día %d)" % common.FAR_DAYS
)


def setup(as_of_iso: str) -> ql.Date:
    """Fija la fecha de evaluación de QuantLib a `as_of_iso` (AAAA-MM-DD) y la devuelve."""
    year, month, day = (int(part) for part in as_of_iso.split("-"))
    today = ql.Date(day, month, year)
    ql.Settings.instance().evaluationDate = today
    return today


def _zero(df: float, days: int) -> float:
    """Tasa cero continua con t = días/365, como la del desk."""
    return -math.log(df) / (days / 365.0)


def build_curve(spec: dict, today: ql.Date) -> ql.YieldTermStructureHandle:
    """Curva de descuento de QuantLib que reproduce los DF de los pilares del desk (`spec` = cases["curves"][c])."""
    pillars = spec["pillars"]
    zeros = [_zero(p["df"], p["days"]) for p in pillars]
    dates = [today] + [today + int(p["days"]) for p in pillars] + [today + common.FAR_DAYS]
    nodes = [zeros[0]] + zeros + [zeros[-1]]
    curve = ql.ZeroCurve(dates, nodes, ql.Actual365Fixed(), ql.NullCalendar(), ql.Linear(), ql.Continuous)
    curve.enableExtrapolation()
    return ql.YieldTermStructureHandle(curve)


def curve_report(spec: dict, handle: ql.YieldTermStructureHandle, today: ql.Date) -> dict:
    """DF de QuantLib en los pilares y en las fechas intermedias de `spec` (mismos días que el desk)."""

    def measure(rows: List[dict]) -> List[Dict[str, float]]:
        return [{"days": int(r["days"]), "df_ref": float(handle.discount(today + int(r["days"])))} for r in rows]

    return {
        "interpolation": INTERPOLATION,
        "pillars": measure(spec["pillars"]),
        "checks": measure(spec["checks"]),
    }
