"""FpML 5.12 (vista de confirmación) de `irs`, `fx_forward` y `fx_option` (corte 5).

Solo biblioteca estándar (`xml.etree.ElementTree`).
"""
import sqlite3
from typing import Any, Dict

FPML_NS = "http://www.fpml.org/FpML-5/confirmation"
FPML_VERSION = "5-12"
FPML_PRODUCTS = ("irs", "fx_forward", "fx_option")
MAX_FPML_BYTES = 1000000
INDEX_TO_FPML = {"TIIE-F": "MXN-TIIE-ON-OIS Compound", "SOFR": "USD-SOFR-OIS Compound"}
TRADE_ID_SCHEME = "urn:qf-desk:trade-id"


def export_trade(conn: sqlite3.Connection, trade_id: int) -> str:
    """XML (con declaración) de la operación para `GET /api/trades/<id>/fpml`. Lo implementa T5."""
    raise NotImplementedError("export_trade: pendiente (T5)")


def import_trade(conn: sqlite3.Connection, raw: bytes) -> Dict[str, Any]:
    """`{"trade", "warnings"}` de un FpML crudo (sin commit). Lo implementa T5."""
    raise NotImplementedError("import_trade: pendiente (T5)")
