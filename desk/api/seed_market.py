"""Semilla del snapshot de mercado sintético `MX-DEMO` (todos los datos son inventados)."""
import json
import math
import sqlite3
from typing import Any, Dict, List

SNAPSHOT_ID = "MX-DEMO"
LABEL = "México demo (sintético)"
AS_OF = "2026-11-10"
SPOT = 18.60

# (etiqueta, días, tasa en %). La primera cotización de cada curva es el depósito a 1 día.
_TIIE_F = [
    ("1D", 1, 7.00),
    ("1x28", 1 * 28, 6.98),
    ("3x28", 3 * 28, 6.92),
    ("6x28", 6 * 28, 6.85),
    ("13x28", 13 * 28, 6.75),
    ("26x28", 26 * 28, 6.70),
    ("39x28", 39 * 28, 6.72),
    ("65x28", 65 * 28, 6.80),
    ("91x28", 91 * 28, 6.90),
    ("130x28", 130 * 28, 7.05),
]
_SOFR = [
    ("1D", 1, 3.90),
    ("1M", 30, 3.85),
    ("3M", 91, 3.80),
    ("6M", 182, 3.75),
    ("1Y", 365, 3.70),
    ("2Y", 730, 3.55),
    ("3Y", 1095, 3.50),
    ("5Y", 1825, 3.55),
    ("7Y", 2555, 3.65),
    ("10Y", 3650, 3.80),
]

_EXPIRY_DAYS = [30, 91, 182, 365]
_ATM_VOL = [0.115, 0.120, 0.125, 0.130]
_STRIKES = [17.0 + 0.5 * i for i in range(8)]  # 17.0, 17.5, ..., 20.5


def _quotes(curve: str, rows: List[tuple]) -> List[Dict[str, Any]]:
    return [
        {
            "id": "%s:%s" % (curve, label),
            "curve": curve,
            "label": label,
            "type": "deposit" if i == 0 else "ois",
            "days": days,
            "rate": round(pct / 100.0, 6),
        }
        for i, (label, days, pct) in enumerate(rows)
    ]


def _smile(atm: float, strike: float) -> float:
    k = math.log(strike / SPOT)
    return atm + 0.5 * k * k + 0.03 * k


def demo_data() -> Dict[str, Any]:
    """Cuerpo `data` (JSON) del snapshot `MX-DEMO`."""
    return {
        "quotes": _quotes("TIIE-F", _TIIE_F) + _quotes("SOFR", _SOFR),
        "fx": {"pair": "USDMXN", "spot": SPOT},
        "vol_surface": {
            "pair": "USDMXN",
            "expiry_days": _EXPIRY_DAYS,
            "strikes": _STRIKES,
            "vols": [[_smile(atm, k) for k in _STRIKES] for atm in _ATM_VOL],
        },
        "hw": {
            "TIIE-F": {"a": 0.05, "sigma": 0.01},
            "SOFR": {"a": 0.03, "sigma": 0.008},
        },
        "factors": {
            "names": ["TIIE-F", "SOFR", "USDMXN"],
            "units": ["bp", "bp", "ret"],
            "daily_vols": [4.0, 5.0, 0.0075],
            "correlations": [
                [1.0, 0.35, 0.30],
                [0.35, 1.0, -0.10],
                [0.30, -0.10, 1.0],
            ],
        },
    }


def seed_market(conn: sqlite3.Connection) -> None:
    """Inserta el snapshot `MX-DEMO` (sin commit: lo hace quien llama)."""
    conn.execute(
        "INSERT INTO snapshots (id, label, synthetic, as_of, data) VALUES (?, ?, 1, ?, ?)",
        (SNAPSHOT_ID, LABEL, AS_OF, json.dumps(demo_data())),
    )
