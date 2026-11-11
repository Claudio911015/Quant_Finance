"""Helpers de validación de cuerpos JSON. Todos lanzan `ApiError(400, msg, field=name)`."""
import math
from typing import Any, Dict, Optional, Sequence

from flask import request

from desk.api.errors import ApiError


def body_object() -> Dict[str, Any]:
    """Cuerpo de la petición como objeto JSON; 400 si falta, está mal formado o no es objeto."""
    data = request.get_json(force=True, silent=True)
    if data is None:
        raise ApiError(400, "El cuerpo no es JSON válido o está vacío")
    if not isinstance(data, dict):
        raise ApiError(400, "El cuerpo debe ser un objeto JSON")
    return data


def _missing(d: Dict[str, Any], name: str) -> bool:
    return name not in d or d[name] is None


def number(
    d: Dict[str, Any],
    name: str,
    *,
    gt: Optional[float] = None,
    ge: Optional[float] = None,
    lt: Optional[float] = None,
    required: bool = True,
    default: Optional[float] = None,
) -> Optional[float]:
    """Número finito (rechaza bool, NaN e inf) con cotas opcionales."""
    if _missing(d, name):
        if required:
            raise ApiError(400, "Falta el parámetro '%s'" % name, name)
        return default
    v = d[name]
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ApiError(400, "'%s' debe ser un número finito" % name, name)
    if gt is not None and not v > gt:
        raise ApiError(400, "'%s' debe ser mayor que %s" % (name, gt), name)
    if ge is not None and not v >= ge:
        raise ApiError(400, "'%s' debe ser mayor o igual que %s" % (name, ge), name)
    if lt is not None and not v < lt:
        raise ApiError(400, "'%s' debe ser menor que %s" % (name, lt), name)
    return float(v)


def integer(
    d: Dict[str, Any], name: str, *, ge: Optional[int] = None, required: bool = True
) -> Optional[int]:
    """Entero (rechaza bool y flotantes) con cota inferior opcional."""
    if _missing(d, name):
        if required:
            raise ApiError(400, "Falta el parámetro '%s'" % name, name)
        return None
    v = d[name]
    if isinstance(v, bool) or not isinstance(v, int):
        raise ApiError(400, "'%s' debe ser un entero" % name, name)
    if ge is not None and v < ge:
        raise ApiError(400, "'%s' debe ser mayor o igual que %s" % (name, ge), name)
    return v


def choice(
    d: Dict[str, Any], name: str, options: Sequence[str], default: Optional[str] = None
) -> str:
    """Una de `options`; si falta y hay `default`, lo devuelve."""
    if _missing(d, name):
        if default is not None:
            return default
        raise ApiError(400, "Falta el parámetro '%s'" % name, name)
    v = d[name]
    if not isinstance(v, str) or v not in options:
        raise ApiError(
            400, "'%s' debe ser uno de: %s" % (name, ", ".join(options)), name
        )
    return v


def text(d: Dict[str, Any], name: str, required: bool = True) -> Optional[str]:
    """Cadena no vacía (recortada). Si no es requerida y falta o queda vacía, `None`."""
    if _missing(d, name):
        if required:
            raise ApiError(400, "Falta el parámetro '%s'" % name, name)
        return None
    v = d[name]
    if not isinstance(v, str):
        raise ApiError(400, "'%s' debe ser texto" % name, name)
    v = v.strip()
    if not v:
        if required:
            raise ApiError(400, "'%s' no puede estar vacío" % name, name)
        return None
    return v
