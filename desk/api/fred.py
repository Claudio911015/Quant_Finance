"""Descarga y parseo de la serie DEXMXUS (pesos por dólar, mediodía de Nueva York) de FRED.

Un solo intento, sin cabeceras propias (FRED deja colgadas las peticiones con un User-Agent
inventado). `URLError`, `socket.timeout` y `ValueError` se propagan: el refresco los vuelve 502.
"""
import csv
import io
import math
import urllib.request
from datetime import date
from typing import List, Tuple

DEXMXUS_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXMXUS"
TIMEOUT_S = 20


def parse_dexmxus(text: str) -> List[Tuple[str, float]]:
    """Observaciones válidas `(fecha ISO, MXN por USD)` en orden ascendente.

    Columna 0 = fecha, columna 1 = valor; la primera fila es la cabecera y su nombre no importa.
    Se descartan faltantes (`""`, `"."`), valores no finitos o ≤ 0 y fechas no ISO. Sin
    observaciones válidas lanza `ValueError`.
    """
    rows = []
    reader = csv.reader(io.StringIO(text))
    next(reader, None)
    for row in reader:
        if len(row) < 2:
            continue
        day, raw = row[0].strip(), row[1].strip()
        if raw in ("", "."):
            continue
        try:
            date.fromisoformat(day)
            value = float(raw)
        except ValueError:
            continue
        if math.isfinite(value) and value > 0:
            rows.append((day, value))
    if not rows:
        raise ValueError("DEXMXUS sin observaciones válidas")
    rows.sort(key=lambda r: r[0])
    return rows


def fetch_dexmxus(url: str) -> List[Tuple[str, float]]:
    """Descarga `url` (admite `file://`) y la parsea con `parse_dexmxus`."""
    with urllib.request.urlopen(url, timeout=TIMEOUT_S) as resp:
        text = resp.read().decode("utf-8")
    return parse_dexmxus(text)
