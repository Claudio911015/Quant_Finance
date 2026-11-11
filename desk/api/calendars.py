"""Calendarios de días inhábiles de México (bancario) y de EE. UU. (publicación de SOFR, SIFMA).

Corte 3, T4: solo constantes y firmas; T5 implementa las reglas.
"""
from datetime import date
from typing import Dict, List

CALENDARS = ("MX", "US")
INDEX_CALENDAR = {"TIIE-F": "MX", "SOFR": "US", "USDMXN": "MX"}
CURRENCY_CALENDAR = {"MXN": "MX", "USD": "US"}
FIRST_YEAR, LAST_YEAR = 2020, 2040


def holidays(cal: str, year: int) -> Dict[date, str]:
    """`{fecha: nombre}` de los feriados del calendario en el año (nombres en español para MX).

    @raise ValueError si `year` está fuera de 2020–2040 o `cal` no es un calendario conocido.
    """
    raise NotImplementedError("calendars.holidays: lo implementa T5")


def is_holiday(cal: str, d: date) -> bool:
    """True si `d` es feriado del calendario (cualquier día de la semana); fuera de 2020–2040, False."""
    raise NotImplementedError("calendars.is_holiday: lo implementa T5")


def is_business_day(cal: str, d: date) -> bool:
    """True si `d` es de lunes a viernes y no es feriado del calendario."""
    raise NotImplementedError("calendars.is_business_day: lo implementa T5")


def holidays_between(cal: str, d0: date, d1: date) -> List[Dict[str, str]]:
    """`[{"date", "name"}]` de los feriados en `[d0, d1]`, ordenados por fecha."""
    raise NotImplementedError("calendars.holidays_between: lo implementa T5")
