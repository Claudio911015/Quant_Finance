"""Fijaciones diarias de índices (TIIE-F, SOFR, USDMXN). Se implementa en T5."""
import sqlite3
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

INDICES = ("TIIE-F", "SOFR", "USDMXN")


def add_fixing(conn: sqlite3.Connection, body: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Alta de una fijación; devuelve `(fijación, creada)`. 409 si la clave existe con otro valor."""
    raise NotImplementedError("fixings.add_fixing se implementa en T5")


def import_csv(conn: sqlite3.Connection, text: str) -> Dict[str, int]:
    """Alta atómica desde CSV; devuelve `{"inserted", "unchanged"}`."""
    raise NotImplementedError("fixings.import_csv se implementa en T5")


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
    raise NotImplementedError("fixings.list_fixings se implementa en T5")


def load_all(conn: sqlite3.Connection) -> Dict[str, Dict[date, float]]:
    """Todas las fijaciones como `{índice: {fecha: valor}}`."""
    raise NotImplementedError("fixings.load_all se implementa en T5")
