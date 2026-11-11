"""Confirmación imprimible de una operación (corte 5): términos pactados, no los vigentes."""
import sqlite3
from typing import Any, Dict

NOTICES = ("Documento informativo; no sustituye la confirmación ISDA ni el contrato marco firmado por las partes.",
           "Generado por QF Desk con los términos registrados; los montos variables dependen de fijaciones futuras.")


def confirmation(conn: sqlite3.Connection, trade_id: int) -> Dict[str, Any]:
    """Cuerpo de `GET /api/trades/<id>/confirmation`. Lo implementa T4."""
    raise NotImplementedError("confirmation: pendiente (T4)")
