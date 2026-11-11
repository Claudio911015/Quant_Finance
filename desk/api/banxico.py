"""Descarga y parseo de series del SIE (API REST) de Banxico: TIIE de Fondeo a un día y FIX.

El token (`Bmx-Token`) lo recibe quien llama y solo viaja en la cabecera de la petición: ningún
mensaje de excepción de este módulo lo incluye. `URLError`, `HTTPError` (Banxico responde 400 con
token inválido), `socket.timeout` y `ValueError` se propagan tal cual.
"""
import json
import math
import urllib.request
from datetime import date, datetime
from typing import Dict, List, Tuple

BASE_URL = "https://www.banxico.org.mx/SieAPIRest/service/v1/series"
TIMEOUT_S = 20

# Verificados el 2026-11-11 contra el catálogo público del SIE (no pide token):
#   GET https://www.banxico.org.mx/SieAPIRest/service/v1/cat/series/SF331451
#   -> "TIIE de Fondeo a Un Día Hábil Bancario, Mediana ponderada por volumen" (diaria, porcentajes)
TIIE_F_SERIES = "SF331451"
#   GET https://www.banxico.org.mx/SieAPIRest/service/v1/cat/series/SF43718
#   -> "Tipo de cambio Pesos por dólar E.U.A. ... Fecha de determinación (FIX)" (diaria, pesos por dólar)
#   (también listada en https://www.banxico.org.mx/SieAPIRest/service/v1/doc/catalogoSeries)
FIX_SERIES = "SF43718"


def parse_series(text: str) -> List[Tuple[str, float]]:
    """Observaciones `(fecha ISO, valor)` en orden ascendente de la primera serie del cuerpo SIE.

    Formato: `{"bmx": {"series": [{"idSerie", "datos": [{"fecha": "dd/mm/aaaa", "dato": "18.45"}]}]}}`.
    Qué conversión aplicar lo decide el `idSerie` del cuerpo: `TIIE_F_SERIES` llega en por ciento
    y sale en decimal (`round(dato / 100, 10)`); `FIX_SERIES` sale tal cual. Se omiten los datos
    faltantes (`"N/E"`) y las filas ilegibles o no finitas; si una fecha se repite gana la última.
    Una serie sin `datos` es válida (no hay datos en el rango). Un cuerpo que no es JSON, sin
    `bmx.series` o con una serie desconocida lanza `ValueError`.
    """
    try:
        body = json.loads(text)
    except ValueError:
        raise ValueError("Banxico: la respuesta del SIE no es JSON")
    series = body.get("bmx", {}).get("series") if isinstance(body, dict) else None
    if isinstance(series, list) and series:
        series = series[0]
    if not isinstance(series, dict):
        raise ValueError("Banxico: la respuesta del SIE no trae 'bmx.series'")
    id_serie = series.get("idSerie")
    if id_serie not in (TIIE_F_SERIES, FIX_SERIES):
        raise ValueError("Banxico: serie desconocida en la respuesta del SIE (%r)" % (id_serie,))
    scale = 100.0 if id_serie == TIIE_F_SERIES else 1.0
    datos = series.get("datos", [])
    if not isinstance(datos, list):
        raise ValueError("Banxico: 'datos' de la respuesta del SIE no es una lista")
    found: Dict[str, float] = {}
    for row in datos:
        if not isinstance(row, dict):
            continue
        try:
            day = datetime.strptime(row["fecha"], "%d/%m/%Y").date().isoformat()
            value = float(row["dato"])  # "N/E" no se puede convertir
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(value):
            found[day] = round(value / scale, 10) if scale != 1.0 else value
    return sorted(found.items())


def fetch_series(series_id: str, start: str, end: str, token: str) -> List[Tuple[str, float]]:
    """Serie `series_id` entre `start` y `end` (fechas ISO, ambas incluidas), vía `parse_series`."""
    if not token:
        raise ValueError("Banxico: falta el token del SIE")
    url = "%s/%s/datos/%s/%s" % (
        BASE_URL,
        series_id,
        date.fromisoformat(start).isoformat(),
        date.fromisoformat(end).isoformat(),
    )
    request = urllib.request.Request(url, headers={"Bmx-Token": token})
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as resp:
        text = resp.read().decode("utf-8")
    return parse_series(text)
