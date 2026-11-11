"""Fijaciones diarias de índices (TIIE-F, SOFR, USDMXN).

Tabla `fixings (index_name, fixing_date, value)`, clave `(index_name, fixing_date)`. Las tasas
(`TIIE-F`, `SOFR`) van en decimal; `USDMXN` es el FIX (MXN por USD). Una fijación ya guardada
no se sobrescribe: repetirla igual es un no-op y con otro valor es un conflicto (409).
"""
import sqlite3
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from desk.api.errors import ApiError
from desk.api.validation import MAX_PRICE, MAX_RATE, MIN_RATE, choice, iso_date, number

INDICES = ("TIIE-F", "SOFR", "USDMXN")

CSV_HEADER = "index,date,value"


def _validate(body: Dict[str, Any]) -> Tuple[str, date, float]:
    """`(índice, fecha, valor)` de un cuerpo `{"index", "date", "value"}`; 400 con el campo culpable."""
    index = choice(body, "index", INDICES)
    day = iso_date(body, "date")
    if index == "USDMXN":
        value = number(body, "value", gt=0, le=MAX_PRICE)
    else:
        value = number(body, "value", ge=MIN_RATE, le=MAX_RATE)
    return index, day, value


def _public(index: str, day: date, value: float) -> Dict[str, Any]:
    return {"index": index, "date": day.isoformat(), "value": value}


def add_fixing(conn: sqlite3.Connection, body: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Alta de una fijación; devuelve `(fijación, creada)`. 409 si la clave existe con otro valor."""
    index, day, value = _validate(body)
    cur = conn.execute(
        "INSERT OR IGNORE INTO fixings (index_name, fixing_date, value) VALUES (?, ?, ?)",
        (index, day.isoformat(), value),
    )
    if cur.rowcount == 1:
        return _public(index, day, value), True
    stored = conn.execute(
        "SELECT value FROM fixings WHERE index_name = ? AND fixing_date = ?",
        (index, day.isoformat()),
    ).fetchone()["value"]
    if stored != value:
        raise ApiError(
            409, "Ya hay una fijación de %s para %s con otro valor (%r)" % (index, day.isoformat(), stored), "value"
        )
    return _public(index, day, value), False


def import_csv(conn: sqlite3.Connection, text: str) -> Dict[str, int]:
    """Alta atómica desde CSV; devuelve `{"inserted", "unchanged"}`.

    Encabezado exacto `index,date,value`; se tolera un BOM UTF-8 al inicio y el fin de línea CRLF, y
    las líneas vacías al final se ignoran. Primero se valida todo el archivo (400 `field: "csv"` con
    "Fila <n>: <motivo>", encabezado = fila 1) y después se buscan conflictos (409), y solo si no hay
    ninguno se inserta: un archivo malo no guarda nada.
    """
    if text.startswith("\ufeff"):  # Excel guarda el CSV UTF-8 con BOM: no es parte del encabezado
        text = text[1:]
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines or lines[0] != CSV_HEADER:
        raise ApiError(400, "Fila 1: el encabezado debe ser exactamente '%s'" % CSV_HEADER, "csv")

    parsed = []  # type: List[Tuple[int, str, date, float]]
    for n, line in enumerate(lines[1:], start=2):
        cells = [c.strip() for c in line.split(",")]
        if len(cells) != 3:
            raise ApiError(400, "Fila %d: se esperaban 3 columnas (index,date,value)" % n, "csv")
        try:
            value = float(cells[2])  # type: Any
        except ValueError:
            value = cells[2]  # texto: `_validate` lo rechaza como no numérico
        try:
            index, day, value = _validate({"index": cells[0], "date": cells[1], "value": value})
        except ApiError as e:
            raise ApiError(400, "Fila %d: %s" % (n, e.error), "csv")
        parsed.append((n, index, day, value))

    inserted = 0
    unchanged = 0
    to_insert = {}  # type: Dict[Tuple[str, str], float]
    for n, index, day, value in parsed:
        key = (index, day.isoformat())
        if key in to_insert:
            stored = to_insert[key]
        else:
            row = conn.execute(
                "SELECT value FROM fixings WHERE index_name = ? AND fixing_date = ?", key
            ).fetchone()
            stored = row["value"] if row is not None else None
        if stored is None:
            to_insert[key] = value
            inserted += 1
        elif stored == value:
            unchanged += 1
        else:
            raise ApiError(
                409, "Fila %d: ya hay una fijación de %s para %s con otro valor (%r)" % (n, index, key[1], stored), "csv"
            )
    conn.executemany(
        "INSERT INTO fixings (index_name, fixing_date, value) VALUES (?, ?, ?)",
        [(i, d, v) for (i, d), v in to_insert.items()],
    )
    return {"inserted": inserted, "unchanged": unchanged}


def list_fixings(
    conn: sqlite3.Connection,
    index: Optional[str] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Fijaciones ordenadas por `(index, date)`.

    @param index nombre crudo del índice (esta función lo valida: 400 `field: "index"`) o `None`.
    @param start, end `date` ya validadas por la ruta, o `None`.
    """
    clauses = []  # type: List[str]
    args = []  # type: List[str]
    if index is not None:
        if index not in INDICES:
            raise ApiError(400, "'index' debe ser uno de: %s" % ", ".join(INDICES), "index")
        clauses.append("index_name = ?")
        args.append(index)
    if start is not None:
        clauses.append("fixing_date >= ?")
        args.append(start.isoformat())
    if end is not None:
        clauses.append("fixing_date <= ?")
        args.append(end.isoformat())
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        "SELECT index_name, fixing_date, value FROM fixings%s ORDER BY index_name, fixing_date" % where,
        args,
    ).fetchall()
    return [
        {"index": r["index_name"], "date": r["fixing_date"], "value": r["value"]} for r in rows
    ]


def load_all(conn: sqlite3.Connection) -> Dict[str, Dict[date, float]]:
    """Todas las fijaciones como `{índice: {fecha: valor}}` (los tres índices siempre presentes)."""
    out = {i: {} for i in INDICES}  # type: Dict[str, Dict[date, float]]
    for r in conn.execute("SELECT index_name, fixing_date, value FROM fixings"):
        if r["index_name"] in out:
            out[r["index_name"]][date.fromisoformat(r["fixing_date"])] = r["value"]
    return out
