"""Utilidades comunes de los ejemplos verificables de docs/tex (R3).

Uso en un script de capítulo (verificacion/capNN_<tema>.py):

    import comun                      # primero: arregla sys.path
    from desk.api.qf import qfpy
    comun.comprobar("cap03-tasa-par", valor_calculado, 1e-8)
    comun.terminar()

Solo stdlib. `impreso` lee el valor del propio .tex, de modo que el texto y el código no pueden divergir.
"""
import re
import sys
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
for _p in (str(RAIZ), str(RAIZ / "build" / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_CAPITULOS = RAIZ / "docs" / "tex" / "capitulos"
_VERIF = re.compile(r"\\verif\{([^}]*)\}\{([^}]*)\}")
_COMENTARIO = re.compile(r"(?<!\\)%.*")
_fallas = []


def _valor_texto(id):
    """Cadena del valor impreso en \\verif{id}{valor}; ValueError si hay 0 o más de 1 aparición."""
    hallados = []
    for tex in sorted(_CAPITULOS.glob("cap*.tex")):
        texto = _COMENTARIO.sub("", tex.read_text(encoding="utf-8"))
        hallados += [v.strip() for i, v in _VERIF.findall(texto) if i.strip() == id]
    if len(hallados) != 1:
        raise ValueError("\\verif{%s}: %d apariciones en capitulos/cap*.tex (se exige 1)" % (id, len(hallados)))
    return hallados[0]


def impreso(id):
    """Valor numérico impreso en el documento para el ejemplo `id`."""
    return float(_valor_texto(id))


def comprobar(id, calculado, tol):
    """Compara `calculado` con el valor impreso; imprime OK/FALLA y devuelve True/False."""
    try:
        texto = _valor_texto(id)
        imp = float(texto)
    except ValueError as exc:
        print("FALLA %s %s" % (id, exc))
        _fallas.append(id)
        return False
    media_unidad = Decimal(5) * Decimal(10) ** (Decimal(texto).as_tuple().exponent - 1)
    if Decimal(str(float(tol))) < media_unidad:
        print("AVISO %s: tol=%g < media unidad del ultimo digito impreso (%s)" % (id, tol, media_unidad),
              file=sys.stderr)
    bien = abs(calculado - imp) <= tol
    print("%s %s calculado=%r impreso=%r tol=%g" % ("OK" if bien else "FALLA", id, calculado, imp, tol))
    if not bien:
        _fallas.append(id)
    return bien


def terminar():
    """sys.exit(1) si hubo alguna FALLA; si no, sys.exit(0)."""
    sys.exit(1 if _fallas else 0)
