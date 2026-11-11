"""Historia diaria de factores de riesgo para el VaR histórico (corte 6, D2).

Tabla `factor_history (factor, source, date, value, created_at)`, solo de inserción. Valores:
`TIIE-F` y `SOFR` = cambio diario en pb; `USDMXN` = rendimiento logarítmico diario; cada fila va
fechada en el día del segundo dato. Fuentes: `synthetic` (semilla fija de MX-DEMO), `csv`, `live`
(FRED + MarketDataFeed) y `fixings` (derivada de las fijaciones cargadas).
"""
import json
import math
import random
import sqlite3
from datetime import date, timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from desk.api import fixings as fixing_store, fred, marketdata
from desk.api.db import now_iso
from desk.api.errors import ApiError
from desk.api.refresh import _why
from desk.api.seed_market import SNAPSHOT_ID as DEMO_ID
from desk.api.validation import finite_number

FACTORS = {"TIIE-F": "bp", "SOFR": "bp", "USDMXN": "ret"}
SOURCES = ("synthetic", "csv", "live", "fixings")
OBSERVED_PRIORITY = ("csv", "live", "fixings")  # en "observed", por (factor, fecha) gana el primero
SOURCE_LABEL = {
    "synthetic": "Sintético (semilla fija, vols y correlaciones de MX-DEMO)",
    "csv": "CSV cargado",
    "live": "FRED / MarketDataFeed",
    "fixings": "Fijaciones cargadas",
}
CSV_HEADER = "factor,date,value"
MAX_ABS = {"bp": 1000.0, "ret": 1.0}  # cota de |valor| por unidad (como var._MAX_FACTOR_VOL)
SYNTHETIC_SEED = 20261110
SYNTHETIC_DAYS = 500  # días hábiles (lun-vie) estrictamente anteriores al as_of de MX-DEMO
MAX_GAP_DAYS = 5  # al derivar: pares de observaciones a más de 5 días naturales se omiten

_LIVE_REJECT_PREFIX = "Historia insuficiente"  # el 409 de historia corta de `marketdata` se propaga tal cual
_INSERT = "INSERT INTO factor_history (factor, source, date, value, created_at) VALUES (?, ?, ?, ?, ?)"


# ------------------------------------------------------------------------------ semilla sintética

def _cholesky(m: Sequence[Sequence[float]]) -> List[List[float]]:
    """Factor de Cholesky inferior `L` (`L·Lᵀ = m`) de una matriz simétrica definida positiva."""
    n = len(m)
    low = [[0.0] * n for _ in range(n)]  # type: List[List[float]]
    for i in range(n):
        for j in range(i + 1):
            s = sum(low[i][k] * low[j][k] for k in range(j))
            if i == j:
                d = m[i][i] - s
                if d <= 0:
                    raise ValueError("La matriz de correlaciones no es definida positiva")
                low[i][j] = math.sqrt(d)
            else:
                low[i][j] = (m[i][j] - s) / low[j][j]
    return low


def _business_days_before(end: date, n: int) -> List[date]:
    """Los `n` días hábiles (lun-vie) estrictamente anteriores a `end`, en orden ascendente."""
    out = []  # type: List[date]
    day = end
    while len(out) < n:
        day -= timedelta(days=1)
        if day.weekday() < 5:
            out.append(day)
    out.reverse()
    return out


def seed_synthetic(conn: sqlite3.Connection) -> int:
    """Siembra la historia sintética de MX-DEMO; devuelve las filas insertadas (0 si no aplica).

    Solo si existe MX-DEMO y aún no hay filas `synthetic`. `random.Random(SYNTHETIC_SEED)` con
    normales correlacionadas (Cholesky de `factors["correlations"]`) escaladas por `daily_vols`:
    mismas cifras en cualquier base. Sin commit.
    """
    row = conn.execute("SELECT as_of, data FROM snapshots WHERE id = ?", (DEMO_ID,)).fetchone()
    if row is None:
        return 0
    if conn.execute("SELECT 1 FROM factor_history WHERE source = 'synthetic' LIMIT 1").fetchone():
        return 0
    spec = json.loads(row["data"]).get("factors") or {}
    names = list(spec.get("names", []))
    if sorted(names) != sorted(FACTORS):
        return 0
    low = _cholesky(spec["correlations"])
    vols = spec["daily_vols"]
    rng = random.Random(SYNTHETIC_SEED)
    created = now_iso()
    rows = []
    for day in _business_days_before(date.fromisoformat(row["as_of"]), SYNTHETIC_DAYS):
        z = [rng.gauss(0, 1) for _ in names]
        for i, name in enumerate(names):
            x = sum(low[i][k] * z[k] for k in range(i + 1))
            rows.append((name, "synthetic", day.isoformat(), vols[i] * x, created))
    conn.executemany(_INSERT, rows)
    return len(rows)


# ------------------------------------------------------------------------------ inserción idempotente

def _store(
    conn: sqlite3.Connection, source: str, rows: Sequence[Tuple[Optional[int], str, str, float]], field: str
) -> Tuple[int, int]:
    """Inserta `(fila, factor, fecha, valor)` de `source`; devuelve `(insertadas, sin cambio)`.

    Todo o nada: la misma clave `(factor, source, fecha)` con el mismo valor no cambia nada y con
    otro valor es 409 `field` sin insertar ninguna fila. `fila` (o `None`) solo rotula el mensaje.
    """
    stored = {
        (r["factor"], r["date"]): r["value"]
        for r in conn.execute("SELECT factor, date, value FROM factor_history WHERE source = ?", (source,))
    }
    pending = {}  # type: Dict[Tuple[str, str], float]
    unchanged = 0
    for n, factor, day, value in rows:
        key = (factor, day)
        old = pending.get(key, stored.get(key))
        if old is None:
            pending[key] = value
        elif old == value:
            unchanged += 1
        else:
            raise ApiError(
                409,
                "%s un dato de %s para %s con otro valor (%r)"
                % (("Fila %d: ya hay" % n) if n else "Ya hay", factor, day, old),
                field,
            )
    created = now_iso()
    conn.executemany(_INSERT, [(f, source, d, v, created) for (f, d), v in pending.items()])
    return len(pending), unchanged


def import_csv(conn: sqlite3.Connection, text: str) -> Dict[str, Any]:
    """Carga un CSV `factor,date,value` (fuente `csv`); devuelve `{"inserted", "unchanged"}`.

    Encabezado exacto; se admiten BOM y `\\r\\n`. Todo o nada: 400 `csv` con "Fila n: …" si algo
    no valida (encabezado = fila 1) y 409 `csv` si una clave existe con otro valor.
    """
    if text.startswith("﻿"):  # Excel guarda el CSV UTF-8 con BOM: no es parte del encabezado
        text = text[1:]
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines or lines[0] != CSV_HEADER:
        raise ApiError(400, "Fila 1: el encabezado debe ser exactamente '%s'" % CSV_HEADER, "csv")

    parsed = []  # type: List[Tuple[Optional[int], str, str, float]]
    for n, line in enumerate(lines[1:], start=2):
        cells = [c.strip() for c in line.split(",")]
        if len(cells) != 3:
            raise ApiError(400, "Fila %d: se esperaban 3 columnas (%s)" % (n, CSV_HEADER), "csv")
        factor, day, raw = cells
        if factor not in FACTORS:
            raise ApiError(
                400, "Fila %d: factor desconocido '%s' (válidos: %s)" % (n, factor, ", ".join(FACTORS)), "csv"
            )
        try:
            if len(day) != 10:
                raise ValueError(day)
            date.fromisoformat(day)
        except ValueError:
            raise ApiError(400, "Fila %d: la fecha debe ser AAAA-MM-DD" % n, "csv")
        try:
            value = float(raw)
        except ValueError:
            raise ApiError(400, "Fila %d: el valor debe ser un número" % n, "csv")
        cap = MAX_ABS[FACTORS[factor]]
        if not finite_number(value) or abs(value) > cap:
            raise ApiError(
                400, "Fila %d: el valor de %s debe ser finito y de magnitud <= %g" % (n, factor, cap), "csv"
            )
        parsed.append((n, factor, day, value))
    inserted, unchanged = _store(conn, "csv", parsed, "csv")
    return {"inserted": inserted, "unchanged": unchanged}


# ------------------------------------------------------------------------------ derivación

def _changes(
    factor: str, series: Sequence[Tuple[date, float]]
) -> Tuple[List[Tuple[Optional[int], str, str, float]], int]:
    """Cambios diarios de `factor` entre observaciones consecutivas y los pares omitidos por hueco.

    Tasas (decimal) -> pb; USDMXN -> rendimiento logarítmico. Un cambio fuera de la cota de
    `MAX_ABS` (dato de origen dudoso) detiene la derivación con 409 `source`: no se descarta en silencio.
    """
    unit = FACTORS[factor]
    rows = []  # type: List[Tuple[Optional[int], str, str, float]]
    skipped = 0
    for (d0, v0), (d1, v1) in zip(series, series[1:]):
        if (d1 - d0).days > MAX_GAP_DAYS:
            skipped += 1
            continue
        value = (v1 - v0) * 1e4 if unit == "bp" else math.log(v1 / v0)
        if not math.isfinite(value) or abs(value) > MAX_ABS[unit]:
            raise ApiError(
                409,
                "Cambio diario fuera de rango en %s el %s: revisa los datos de origen" % (factor, d1.isoformat()),
                "source",
            )
        rows.append((None, factor, d1.isoformat(), value))
    return rows, skipped


def _from_fixings(conn: sqlite3.Connection) -> Dict[str, List[Tuple[date, float]]]:
    loaded = fixing_store.load_all(conn)
    return {factor: sorted(loaded[factor].items()) for factor in FACTORS if factor in loaded}


def _from_live(config: Mapping[str, Any]) -> Dict[str, List[Tuple[date, float]]]:
    """SOFR = proxy 5Y de `MKT-LIVE` (MarketDataFeed) y USDMXN de FRED, ambos en la ventana de `MKT-LIVE`."""
    try:
        sofr = marketdata.treasury_5y_history(config["MDF_DB"])
    except ApiError as e:
        if e.error.startswith(_LIVE_REJECT_PREFIX):
            raise
        raise ApiError(502, e.error, "source")
    try:
        fx = fred.fetch_dexmxus(config["FRED_DEXMXUS_URL"])
    except (OSError, ValueError) as e:  # URLError y timeout son OSError
        raise ApiError(502, "FRED no respondió: %s" % _why(e), "source")
    fx = fx[-(marketdata.MAX_CHANGES + 1):]
    return {
        "SOFR": [(date.fromisoformat(d), v) for d, v in sofr],
        "USDMXN": [(date.fromisoformat(d), v) for d, v in fx],
    }


def derive(conn: sqlite3.Connection, source: str, config: Mapping[str, Any]) -> Dict[str, Any]:
    """Deriva historia de `fixings` o `live`; devuelve `{"source","inserted","unchanged","skipped_gaps"}`.

    400 `source` si no es una de las dos; 502 `source` si falla la lectura de origen; 409 `source`
    si una clave existe con otro valor (no se inserta nada).
    """
    if source not in ("fixings", "live"):
        raise ApiError(400, "'source' debe ser uno de: fixings, live", "source")
    series = _from_fixings(conn) if source == "fixings" else _from_live(config)
    rows = []  # type: List[Tuple[Optional[int], str, str, float]]
    skipped = 0
    for factor in FACTORS:
        if factor in series:
            factor_rows, gaps = _changes(factor, series[factor])
            rows.extend(factor_rows)
            skipped += gaps
    inserted, unchanged = _store(conn, source, rows, "source")
    return {"source": source, "inserted": inserted, "unchanged": unchanged, "skipped_gaps": skipped}


# ------------------------------------------------------------------------------ lectura

def summary(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Cuerpo de `GET /api/factor-history`: por factor, las fuentes con filas (en el orden de `SOURCES`)."""
    found = {}  # type: Dict[Tuple[str, str], Tuple[int, str, str]]
    for r in conn.execute(
        "SELECT factor, source, COUNT(*) AS n, MIN(date) AS first, MAX(date) AS last"
        " FROM factor_history GROUP BY factor, source"
    ):
        found[(r["factor"], r["source"])] = (r["n"], r["first"], r["last"])
    factors = []
    for factor, unit in FACTORS.items():
        sources = [
            {
                "source": s,
                "label": SOURCE_LABEL[s],
                "count": found[(factor, s)][0],
                "first": found[(factor, s)][1],
                "last": found[(factor, s)][2],
            }
            for s in SOURCES
            if (factor, s) in found
        ]
        factors.append({"factor": factor, "unit": unit, "sources": sources})
    return {"factors": factors}


def window(
    conn: sqlite3.Connection, history_source: str, as_of: str, n: int
) -> Tuple[List[str], Dict[str, List[float]], Dict[str, int]]:
    """`(fechas, {factor: [valores]}, by_source)` de las últimas `n` fechas `<= as_of` con los tres factores.

    `synthetic` usa solo filas `synthetic`; `observed` usa `OBSERVED_PRIORITY` (por factor y fecha
    gana la primera fuente). `by_source` cuenta las observaciones (factor-fecha) que aportó cada
    fuente dentro de esas fechas; si hay menos de `n` fechas devuelve las que haya.
    """
    if history_source == "synthetic":
        priority = ("synthetic",)
    elif history_source == "observed":
        priority = OBSERVED_PRIORITY
    else:
        raise ValueError("Fuente de historia desconocida: %s" % history_source)
    rank = {s: i for i, s in enumerate(priority)}
    best = {}  # type: Dict[Tuple[str, str], Tuple[int, float]]
    marks = ",".join("?" * len(priority))
    for r in conn.execute(
        "SELECT factor, source, date, value FROM factor_history WHERE date <= ? AND source IN (%s)" % marks,
        (as_of,) + priority,
    ):
        key = (r["factor"], r["date"])
        cand = (rank[r["source"]], r["value"])
        if key not in best or cand[0] < best[key][0]:
            best[key] = cand
    per_date = {}  # type: Dict[str, int]
    for _, day in best:
        per_date[day] = per_date.get(day, 0) + 1
    dates = sorted(d for d, c in per_date.items() if c == len(FACTORS))[-n:]
    series = {factor: [best[(factor, d)][1] for d in dates] for factor in FACTORS}
    by_source = {}  # type: Dict[str, int]
    for factor in FACTORS:
        for d in dates:
            name = priority[best[(factor, d)][0]]
            by_source[name] = by_source.get(name, 0) + 1
    return dates, series, {s: by_source[s] for s in priority if s in by_source}
