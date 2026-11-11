"""Ajustes de la empresa y referencia del banco por operación (corte 5).

`settings` y `trade_refs` son configuración editable (sin disparadores de solo inserción): el
nombre de la empresa sale en la confirmación y en FpML; la referencia de la contraparte sirve
para emparejar su estado de cuenta en la conciliación.
"""
import sqlite3
from typing import Any, Dict, Optional

from desk.api import portfolio
from desk.api.db import now_iso
from desk.api.errors import ApiError
from desk.api.validation import text

SETTING_KEYS = ("company_name",)
DEFAULT_COMPANY_NAME = "Empresa sin nombre (configurar en la confirmación)"
MAX_SETTING_LEN = 200
MAX_REF_LEN = 64

_DEFAULTS = {"company_name": DEFAULT_COMPANY_NAME}


def get_settings(conn: sqlite3.Connection) -> Dict[str, str]:
    """Todas las claves de `SETTING_KEYS`, con su valor por omisión si no hay fila."""
    stored = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")}
    return {key: stored.get(key, _DEFAULTS[key]) for key in SETTING_KEYS}


def put_settings(conn: sqlite3.Connection, body: Dict[str, Any]) -> Dict[str, str]:
    """Valida todo el cuerpo y luego inserta o reemplaza (sin commit); devuelve todas las claves.

    @raise ApiError 400 con `field` = la clave desconocida, o `company_name` vacío o de más de
        `MAX_SETTING_LEN` caracteres.
    """
    for key in body:
        if key not in SETTING_KEYS:
            raise ApiError(400, "Ajuste desconocido: %s" % key, key)
    values = {}  # type: Dict[str, str]
    if "company_name" in body:
        name = text(body, "company_name")
        if len(name) > MAX_SETTING_LEN:
            raise ApiError(
                400, "'company_name' no puede pasar de %d caracteres" % MAX_SETTING_LEN, "company_name"
            )
        values["company_name"] = name
    for key, value in values.items():
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, now_iso()),
        )
    return get_settings(conn)


def company_name(conn: sqlite3.Connection) -> str:
    """Nombre de la empresa guardado o `DEFAULT_COMPANY_NAME`."""
    return get_settings(conn)["company_name"]


def get_ref(conn: sqlite3.Connection, trade_id: int) -> Optional[str]:
    """Referencia del banco de la operación, o `None`. No valida que la operación exista."""
    row = conn.execute("SELECT ref FROM trade_refs WHERE trade_id = ?", (trade_id,)).fetchone()
    return None if row is None else row["ref"]


def put_ref(conn: sqlite3.Connection, trade_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Guarda o borra la referencia (sin commit); devuelve `{"trade_id", "ref"}`.

    `ref` `null` o vacío (tras recortar) la borra. Orden de errores: 404 `id`, 400 `ref`
    (falta la clave, no es texto o pasa de `MAX_REF_LEN`), 409 `ref` (otra operación de la misma
    contraparte ya la usa; la comparación es exacta, sensible a mayúsculas).
    """
    trade = portfolio.get_trade(conn, trade_id)
    if "ref" not in body:  # hueco del contrato: una clave ausente no es lo mismo que null
        raise ApiError(400, "Falta el parámetro 'ref'", "ref")
    ref = body["ref"]
    if ref is not None and not isinstance(ref, str):
        raise ApiError(400, "'ref' debe ser texto", "ref")
    ref = None if ref is None else ref.strip()
    if not ref:
        conn.execute("DELETE FROM trade_refs WHERE trade_id = ?", (trade_id,))
        return {"trade_id": trade_id, "ref": None}
    if len(ref) > MAX_REF_LEN:
        raise ApiError(400, "'ref' no puede pasar de %d caracteres" % MAX_REF_LEN, "ref")
    taken = conn.execute(
        "SELECT r.trade_id FROM trade_refs r JOIN trades t ON t.id = r.trade_id"
        " WHERE r.ref = ? AND r.trade_id != ? AND t.counterparty_id ="
        " (SELECT counterparty_id FROM trades WHERE id = ?)",
        (ref, trade_id, trade["id"]),
    ).fetchone()
    if taken is not None:
        raise ApiError(
            409, "La referencia ya la usa la operación %d de la misma contraparte" % taken["trade_id"], "ref"
        )
    conn.execute(
        "INSERT OR REPLACE INTO trade_refs (trade_id, ref, updated_at) VALUES (?, ?, ?)",
        (trade_id, ref, now_iso()),
    )
    return {"trade_id": trade_id, "ref": ref}


def refs_by_counterparty(conn: sqlite3.Connection, counterparty: str) -> Dict[str, int]:
    """Referencia → id de operación, de las operaciones de esa contraparte."""
    rows = conn.execute(
        "SELECT r.ref, r.trade_id FROM trade_refs r JOIN trades t ON t.id = r.trade_id"
        " JOIN counterparties c ON c.id = t.counterparty_id WHERE c.name = ?",
        (counterparty,),
    ).fetchall()
    return {r["ref"]: r["trade_id"] for r in rows}
