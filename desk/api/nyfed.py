"""Descarga y parseo de SOFR desde la API pública de la Fed de Nueva York.

Un solo intento y sin cabeceras propias. `URLError`, `HTTPError`, `socket.timeout` y `ValueError`
se propagan tal cual: quien llama los vuelve 502. La petición solo lleva las dos fechas.
"""
import json
import math
import urllib.request
from datetime import date
from typing import Dict, List, Tuple

SOFR_URL = "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json"
TIMEOUT_S = 20


def parse_sofr(text: str) -> List[Tuple[str, float]]:
    """Observaciones SOFR `(fecha ISO, tasa decimal)` en orden ascendente.

    La fuente publica `percentRate` en por ciento y en orden descendente; aquí se convierte a
    decimal (`round(percentRate / 100, 10)`). Se descartan filas sin `effectiveDate` ISO o sin
    `percentRate` numérico finito, y las de `type` distinto de `SOFR`; si una fecha se repite
    gana la última fila. Un cuerpo que no es JSON, o sin la lista `refRates`, lanza `ValueError`;
    una lista vacía es válida (no hay datos en el rango).
    """
    try:
        body = json.loads(text)
    except ValueError:  # JSONDecodeError es ValueError
        raise ValueError("SOFR: la respuesta de la Fed de Nueva York no es JSON")
    rows = body.get("refRates") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        raise ValueError("SOFR: la respuesta de la Fed de Nueva York no trae 'refRates'")
    found: Dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("type") != "SOFR":
            continue
        day, pct = row.get("effectiveDate"), row.get("percentRate")
        if not isinstance(day, str) or isinstance(pct, bool) or not isinstance(pct, (int, float)):
            continue
        try:
            date.fromisoformat(day)
        except ValueError:
            continue
        if math.isfinite(pct):
            found[day] = round(pct / 100, 10)
    return sorted(found.items())


def fetch_sofr(start: str, end: str) -> List[Tuple[str, float]]:
    """SOFR entre `start` y `end` (fechas ISO `YYYY-MM-DD`, ambas incluidas), vía `parse_sofr`."""
    url = "%s?startDate=%s&endDate=%s" % (
        SOFR_URL,
        date.fromisoformat(start).isoformat(),
        date.fromisoformat(end).isoformat(),
    )
    with urllib.request.urlopen(url, timeout=TIMEOUT_S) as resp:
        text = resp.read().decode("utf-8")
    return parse_sofr(text)
