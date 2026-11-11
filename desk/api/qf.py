"""Carga de `qfpy` (bindings de la biblioteca C++) para el resto del backend.

Uso: `from desk.api.qf import qfpy`.
"""
import sys
from pathlib import Path

_BUILD_SRC = Path(__file__).resolve().parents[2] / "build" / "src"

if str(_BUILD_SRC) not in sys.path:
    sys.path.insert(0, str(_BUILD_SRC))

try:
    import qfpy
except ImportError as exc:
    raise ImportError(
        "No se pudo cargar qfpy desde %s. Compilar con: "
        "cmake --build build --target qfpy (%s)" % (_BUILD_SRC, exc)
    ) from exc

__all__ = ["qfpy"]
