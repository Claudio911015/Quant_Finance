"""Calendarios de días inhábiles de México (bancario) y de EE. UU. (publicación de SOFR, SIFMA).

Reglas fijas 2020–2040, sin dependencias. Sirven para decidir si una fijación sin publicar es
faltante o simplemente un día en que el índice no se publica, y para marcar fechas en la interfaz.
No ajustan fechas de pago.

* MX: inhábiles bancarios. Un feriado fijo en sábado o domingo no se traslada.
* US: calendario SIFMA (el de la publicación de SOFR). Un feriado fijo en domingo pasa al lunes
  siguiente y uno en sábado al viernes anterior, salvo el 1 de enero en sábado (no pasa al año anterior).
"""
from datetime import date, timedelta
from functools import lru_cache
from typing import Dict, List

CALENDARS = ("MX", "US")
INDEX_CALENDAR = {"TIIE-F": "MX", "SOFR": "US", "USDMXN": "MX"}
CURRENCY_CALENDAR = {"MXN": "MX", "USD": "US"}
FIRST_YEAR, LAST_YEAR = 2020, 2040

_MONDAY, _THURSDAY = 0, 3
_WEEKEND = 5  # weekday() >= 5 es sábado o domingo
_EXECUTIVE_HANDOVER_YEARS = (2024, 2030, 2036)  # 1 de octubre, cada sexenio


def _easter(year: int) -> date:
    """Domingo de Pascua (algoritmo gregoriano anónimo, Meeus/Jones/Butcher)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """El `n`-ésimo (1 = primero) día `weekday` del mes."""
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """El último día `weekday` del mes."""
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(d: date, is_new_year: bool = False) -> date:
    """Día en que se observa un feriado fijo de EE. UU.: domingo -> lunes, sábado -> viernes."""
    if d.weekday() == 6:
        return d + timedelta(days=1)
    if d.weekday() == 5 and not is_new_year:  # el 1 de enero en sábado no se traslada al año anterior
        return d - timedelta(days=1)
    return d


def _mexico(year: int) -> Dict[date, str]:
    easter = _easter(year)
    table = {
        date(year, 1, 1): "Año Nuevo",
        _nth_weekday(year, 2, _MONDAY, 1): "Día de la Constitución",
        _nth_weekday(year, 3, _MONDAY, 3): "Natalicio de Benito Juárez",
        easter - timedelta(days=3): "Jueves Santo",
        easter - timedelta(days=2): "Viernes Santo",
        date(year, 5, 1): "Día del Trabajo",
        date(year, 9, 16): "Día de la Independencia",
        date(year, 11, 2): "Día de Muertos",
        _nth_weekday(year, 11, _MONDAY, 3): "Día de la Revolución",
        date(year, 12, 12): "Día de la Virgen de Guadalupe",
        date(year, 12, 25): "Navidad",
    }
    if year in _EXECUTIVE_HANDOVER_YEARS:
        table[date(year, 10, 1)] = "Transmisión del Poder Ejecutivo"
    return table


def _united_states(year: int) -> Dict[date, str]:
    table = {
        _observed(date(year, 1, 1), is_new_year=True): "New Year's Day",
        _nth_weekday(year, 1, _MONDAY, 3): "Martin Luther King Jr.",
        _nth_weekday(year, 2, _MONDAY, 3): "Presidents Day",
        _easter(year) - timedelta(days=2): "Good Friday",
        _last_weekday(year, 5, _MONDAY): "Memorial Day",
        _observed(date(year, 7, 4)): "Independence Day",
        _nth_weekday(year, 9, _MONDAY, 1): "Labor Day",
        _nth_weekday(year, 10, _MONDAY, 2): "Columbus Day",
        _observed(date(year, 11, 11)): "Veterans Day",
        _nth_weekday(year, 11, _THURSDAY, 4): "Thanksgiving",
        _observed(date(year, 12, 25)): "Christmas",
    }
    if year >= 2022:
        table[_observed(date(year, 6, 19))] = "Juneteenth"
    return table


_RULES = {"MX": _mexico, "US": _united_states}


@lru_cache(maxsize=None)
def _table(cal: str, year: int) -> Dict[date, str]:
    return _RULES[cal](year)


def holidays(cal: str, year: int) -> Dict[date, str]:
    """`{fecha: nombre}` de los feriados del calendario en el año (nombres en español para MX).

    @raise ValueError si `year` está fuera de 2020–2040 o `cal` no es un calendario conocido.
    """
    if cal not in _RULES:
        raise ValueError("Calendario desconocido: %s" % cal)
    if not FIRST_YEAR <= year <= LAST_YEAR:
        raise ValueError("El año %d está fuera del alcance de los calendarios (%d–%d)" % (year, FIRST_YEAR, LAST_YEAR))
    return dict(_table(cal, year))


def is_holiday(cal: str, d: date) -> bool:
    """True si `d` es feriado del calendario (cualquier día de la semana); fuera de 2020–2040, False."""
    if cal not in _RULES:
        raise ValueError("Calendario desconocido: %s" % cal)
    return FIRST_YEAR <= d.year <= LAST_YEAR and d in _table(cal, d.year)


def is_business_day(cal: str, d: date) -> bool:
    """True si `d` es de lunes a viernes y no es feriado del calendario."""
    return d.weekday() < _WEEKEND and not is_holiday(cal, d)


def holidays_between(cal: str, d0: date, d1: date) -> List[Dict[str, str]]:
    """`[{"date", "name"}]` de los feriados en `[d0, d1]`, ordenados por fecha.

    Los años fuera de 2020–2040 no aportan feriados (igual que `is_holiday`); `d1 < d0` da `[]`.
    """
    if cal not in _RULES:
        raise ValueError("Calendario desconocido: %s" % cal)
    out = []  # type: List[Dict[str, str]]
    for year in range(max(d0.year, FIRST_YEAR), min(d1.year, LAST_YEAR) + 1):
        for day, name in _table(cal, year).items():
            if d0 <= day <= d1:
                out.append({"date": day.isoformat(), "name": name})
    return sorted(out, key=lambda h: h["date"])
