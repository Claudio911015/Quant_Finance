"""Fijaciones traídas de la fuente: NY Fed (SOFR) y Banxico SIE (TIIE-F, USDMXN).

Todo o nada: primero se descarga y se valida todo; solo entonces se escribe. Una fijación ya guardada
nunca se sobrescribe: si el valor de la fuente coincide (tolerancia 1e-9) se cuenta como igual y si no
se lista como conflicto, sin abortar el resto. El token de Banxico se lee solo de `BANXICO_TOKEN` y
nunca entra en una respuesta, un mensaje de error ni la base.
"""
import http.client
import os
import sqlite3
import urllib.error
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from desk.api import banxico, fixings, nyfed
from desk.api.errors import ApiError
from desk.api.validation import body_object, choice, iso_date

MAX_RANGE_DAYS = 366
TOLERANCE = 1e-9

SOURCE_NYFED = "Fed de Nueva York"
SOURCE_BANXICO = "Banxico (SIE)"
SOURCE_OF = {"TIIE-F": SOURCE_BANXICO, "SOFR": SOURCE_NYFED, "USDMXN": SOURCE_BANXICO}
WHO = {"TIIE-F": "Banxico", "SOFR": "La Fed de Nueva York", "USDMXN": "Banxico"}  # sujeto de los mensajes 502
BANXICO_SERIES = {"TIIE-F": banxico.TIIE_F_SERIES, "USDMXN": banxico.FIX_SERIES}

TOKEN_MISSING = "Falta el token de Banxico (variable BANXICO_TOKEN)"
TOKEN_REJECTED = "Banxico rechazó el token (BANXICO_TOKEN)"
TOKEN_REJECTED_CODES = (400, 401, 403)  # el SIE responde 400 (no 401) con token inválido


def _token() -> Optional[str]:
    return os.environ.get("BANXICO_TOKEN") or None


def _why(e: BaseException) -> str:
    """Motivo legible de un fallo de red o de formato (ninguno incluye el token)."""
    if isinstance(e, urllib.error.URLError) and not isinstance(e, urllib.error.HTTPError):
        return str(e.reason)
    return str(e) or type(e).__name__


def _download(index: str, start: date, end: date) -> List[Tuple[str, float]]:
    """Observaciones `(fecha ISO, valor en la unidad de la tabla)` de la fuente del índice; 409/502."""
    token = None
    if index != "SOFR":
        token = _token()
        if token is None:
            raise ApiError(409, TOKEN_MISSING, code="banxico_token_missing")
    try:
        if index == "SOFR":
            return nyfed.fetch_sofr(start.isoformat(), end.isoformat())
        return banxico.fetch_series(BANXICO_SERIES[index], start.isoformat(), end.isoformat(), token)
    except urllib.error.HTTPError as e:  # antes que OSError: HTTPError es URLError es OSError
        if index != "SOFR" and e.code in TOKEN_REJECTED_CODES:
            raise ApiError(502, TOKEN_REJECTED, code="banxico_token_rejected")
        raise ApiError(502, "%s no respondió: %s" % (WHO[index], _why(e)))
    except (OSError, ValueError, http.client.HTTPException) as e:  # URLError y timeout son OSError
        raise ApiError(502, "%s no respondió: %s" % (WHO[index], _why(e)))


def _request_range(body: Dict[str, Any]) -> Tuple[str, date, date]:
    index = choice(body, "index", fixings.INDICES)
    start = iso_date(body, "from")
    end = iso_date(body, "to")
    if start > end:
        raise ApiError(400, "'from' no puede ser posterior a 'to'", "from")
    if (end - start).days > MAX_RANGE_DAYS:
        raise ApiError(400, "El rango no puede pasar de %d días" % MAX_RANGE_DAYS, "to")
    return index, start, end


def fetch_fixings(conn: sqlite3.Connection, body: Dict[str, Any]) -> Dict[str, Any]:
    """Trae las fijaciones del rango y guarda las nuevas; el commit lo hace la ruta."""
    index, start, end = _request_range(body)
    observations = _download(index, start, end)  # todo antes de escribir

    valid = []  # type: List[Tuple[str, float]]
    for day, value in observations:
        try:
            fixings._validate({"index": index, "date": day, "value": value})
        except ApiError as e:
            raise ApiError(502, "%s devolvió un valor inválido (%s): %s" % (WHO[index], day, e.error))
        valid.append((day, value))

    stored = {}  # type: Dict[str, float]
    if valid:
        rows = fixings.list_fixings(
            conn, index, date.fromisoformat(valid[0][0]), date.fromisoformat(valid[-1][0])
        )
        stored = {r["date"]: r["value"] for r in rows}

    to_insert = []  # type: List[Tuple[str, str, float]]
    conflicts = []  # type: List[Dict[str, Any]]
    unchanged = 0
    for day, value in valid:
        if day not in stored:
            to_insert.append((index, day, value))
        elif abs(value - stored[day]) <= TOLERANCE:
            unchanged += 1
        else:
            conflicts.append({"date": day, "stored": stored[day], "source": value})
    conn.executemany(
        "INSERT INTO fixings (index_name, fixing_date, value) VALUES (?, ?, ?)", to_insert
    )
    return {
        "index": index,
        "source": SOURCE_OF[index],
        "from": start.isoformat(),
        "to": end.isoformat(),
        "fetched": len(to_insert) + unchanged + len(conflicts),
        "inserted": len(to_insert),
        "unchanged": unchanged,
        "conflicts": conflicts,
    }


def list_sources(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Fuente de cada índice (en el orden de `INDICES`), si se puede usar ahora y su última fijación."""
    last = {
        r["index_name"]: r["last_date"]
        for r in conn.execute(
            "SELECT index_name, MAX(fixing_date) AS last_date FROM fixings GROUP BY index_name"
        )
    }
    has_token = _token() is not None
    out = []
    for index in fixings.INDICES:
        available = index == "SOFR" or has_token
        out.append(
            {
                "index": index,
                "source": SOURCE_OF[index],
                "available": available,
                "reason": None if available else TOKEN_MISSING,
                "last_date": last.get(index),
            }
        )
    return {"sources": out}
