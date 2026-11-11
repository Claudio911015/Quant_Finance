"""Datos de prueba de MarketDataFeed y FRED. Ninguna prueba toca la base ni la red reales."""
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence, Tuple

# Curva del Tesoro real del 2026-11-10 (los 13 tenores, en porcentaje como en la base).
REAL_2026_11_10 = {
    "1M": 4.05,
    "2M": 4.21,
    "3M": 4.30,
    "4M": 4.28,
    "6M": 4.38,
    "1Y": 4.56,
    "2Y": 4.73,
    "3Y": 4.74,
    "5Y": 4.81,
    "7Y": 4.89,
    "10Y": 4.98,
    "20Y": 5.39,
    "30Y": 5.35,
}

_DDL = """
CREATE TABLE sofr_rates (effective_date TEXT PRIMARY KEY, rate REAL NOT NULL, percentile_1 REAL, percentile_25 REAL, percentile_75 REAL, percentile_99 REAL, volume_billions REAL, fetched_at TEXT DEFAULT (datetime('now')));
CREATE TABLE sofr_averages (effective_date TEXT PRIMARY KEY, average_30d REAL, average_90d REAL, average_180d REAL, sofr_index REAL, fetched_at TEXT DEFAULT (datetime('now')));
CREATE TABLE treasury_yields (effective_date TEXT NOT NULL, tenor TEXT NOT NULL, rate REAL NOT NULL, fetched_at TEXT DEFAULT (datetime('now')), PRIMARY KEY (effective_date, tenor));
"""


def make_mdf_db(
    path,
    curve_date: str = "2026-11-10",
    curve: Dict[str, float] = REAL_2026_11_10,
    sofr: Iterable[Tuple[str, float]] = (("2026-11-09", 3.88),),
    history_5y: Optional[Sequence[Tuple[str, float]]] = None,
    drop_tenor: Optional[str] = None,
    empty: bool = False,
) -> Path:
    """Crea una base con el esquema real de MarketDataFeed (tasas en %) y devuelve su ruta.

    `curve` se inserta en `curve_date` salvo `drop_tenor`; `sofr` son pares `(fecha, %)`;
    `history_5y` son pares `(fecha, %)` de 5Y adicionales (reemplazan a la curva si coinciden en
    fecha). `empty=True` deja las tablas sin filas.
    """
    path = Path(path)
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(_DDL)
        if not empty:
            conn.executemany(
                "INSERT INTO treasury_yields (effective_date, tenor, rate) VALUES (?, ?, ?)",
                [(curve_date, t, r) for t, r in curve.items() if t != drop_tenor],
            )
            conn.executemany(
                "INSERT INTO sofr_rates (effective_date, rate) VALUES (?, ?)", list(sofr)
            )
            if history_5y:
                conn.executemany(
                    "INSERT OR REPLACE INTO treasury_yields (effective_date, tenor, rate) "
                    "VALUES (?, '5Y', ?)",
                    list(history_5y),
                )
        conn.commit()
    finally:
        conn.close()
    return path


def make_fred_csv(path, rows: Iterable[Tuple[str, Optional[float]]]) -> Path:
    """Escribe un CSV de FRED (`observation_date,DEXMXUS`); el valor `None` queda vacío."""
    path = Path(path)
    lines = ["observation_date,DEXMXUS"]
    for day, value in rows:
        lines.append("%s,%s" % (day, "" if value is None else repr(value)))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
