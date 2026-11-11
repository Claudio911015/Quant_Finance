"""Constantes y utilidades comunes del arnés de validación independiente (desk vs QuantLib).

Solo stdlib y válido en Python 3.8 (backend) y 3.12 (QuantLib); no importa `desk.api`.
"""
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

PRODUCTS = ("irs", "fx_forward", "fx_option", "equity_option", "bond", "cap_floor", "swaption")
PRODUCT_LABELS = {
    "irs": "Swap OIS (TIIE de Fondeo y SOFR)",
    "fx_forward": "Forward USDMXN",
    "fx_option": "Opción USDMXN (Garman-Kohlhagen)",
    "equity_option": "Opción sobre acción (Black-Scholes)",
    "bond": "Bono a tasa fija",
    "cap_floor": "Cap/floor (Hull-White)",
    "swaption": "Swaption (Hull-White)",
}
# |PV_desk - PV_ref| / nocional
TOLERANCES = {
    "irs": 1e-6,
    "fx_forward": 1e-8,
    "fx_option": 1e-6,
    "equity_option": 1e-6,
    "bond": 1e-6,
    "cap_floor": 5e-4,
    "swaption": 5e-4,
}
PILLAR_TOLERANCE = 1e-12  # |DF_desk - DF_ql| en pilares
CHECK_TOLERANCE = 1e-8  # |DF_desk - DF_ql| en fechas intermedias
CHECK_COUNT = 10
MIN_CASES = 60
MIN_CASES_PER_PRODUCT = 5
VERDICTS = ("ok", "explained", "fail")
KNOWN_KINDS = ("convention", "interpolation", "defect")
SOURCES = ("portfolio", "battery")
SNAPSHOT_ID = "MX-DEMO"
FAR_DAYS = 36500  # nodo lejano para la extrapolación plana en QuantLib

VALIDATION_DIR = Path(__file__).resolve().parent
REPO_ROOT = VALIDATION_DIR.parents[1]
CASES_PATH = VALIDATION_DIR / "cases.json"
REFERENCE_PATH = VALIDATION_DIR / "reference.json"
KNOWN_PATH = VALIDATION_DIR / "known_differences.json"
REPORT_PATH = VALIDATION_DIR / "report.json"

# Código cuya última modificación define la versión de la valuación del desk.
VALUATION_PATHS = (
    "src",
    "include",
    "CMakeLists.txt",
    "desk/api/pricing",
    "desk/api/market.py",
    "desk/api/valuation.py",
    "desk/api/qf.py",
    "desk/api/seed_market.py",
    "desk/api/seed_trades.py",
    "desk/validation/export_cases.py",
)
BACKEND_PYTHON = "/home/claudio/anaconda3/bin/python"
QUANTLIB_PYTHON = "/home/claudio/anaconda3/envs/quantsuite-oracle/bin/python"
QUANTLIB_ENV = "quantsuite-oracle"
REPRODUCE_COMMAND = "desk/validation/make_report.sh"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _git(root: Path, *args: str) -> Optional[str]:
    """Salida de `git -C <root> <args>` o None si git no está o falla."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root)] + list(args),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def desk_commit(root: Path = REPO_ROOT) -> Optional[str]:
    """Último commit que tocó el código de valuación (`VALUATION_PATHS`); None si git falla o sale vacío."""
    out = _git(root, "log", "-1", "--format=%H", "--", *VALUATION_PATHS)
    out = (out or "").strip()
    return out or None


def desk_dirty(root: Path = REPO_ROOT) -> Optional[bool]:
    """True si hay cambios sin commit en `VALUATION_PATHS`; None si git falla."""
    out = _git(root, "status", "--porcelain", "--", *VALUATION_PATHS)
    if out is None:
        return None
    return bool(out.strip())


def check_days(pillar_days: List[int]) -> List[int]:
    """Días intermedios (CHECK_COUNT) estrictamente dentro de [primer pilar, último pilar]."""
    first, last = pillar_days[0], pillar_days[-1]
    return [int(round(first + (last - first) * (k + 0.5) / CHECK_COUNT)) for k in range(CHECK_COUNT)]


def diffs(pv_desk: float, pv_ref: Optional[float], notional: float) -> Tuple[Optional[float], Optional[float]]:
    """(|pv_desk - pv_ref|, |pv_desk - pv_ref| / notional); (None, None) si pv_ref es None o no finito."""
    if pv_ref is None or not math.isfinite(pv_ref):
        return None, None
    abs_diff = abs(pv_desk - pv_ref)
    return abs_diff, abs_diff / notional


def classify(rel_diff: Optional[float], tolerance: float, known: Optional[dict]) -> str:
    """"fail" sin diferencia; "ok" dentro de tolerancia; "explained" si una diferencia conocida la acota."""
    if rel_diff is None:
        return "fail"
    if rel_diff <= tolerance:
        return "ok"
    if known and rel_diff <= known["max_rel_diff"]:
        return "explained"
    return "fail"
