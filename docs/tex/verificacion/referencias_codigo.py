"""Comprueba las \\codigo{ruta}{simbolo} de docs/tex/**/*.tex (R4): la ruta existe y el simbolo esta DEFINIDO.
Uso: python docs/tex/verificacion/referencias_codigo.py [--min K]  (K=120). Omite .tex con `_` inicial y comentarios."""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
CODIGO = re.compile(r"\\codigo\{([^}]*)\}\{([^}]*)\}")
COMENTARIO = re.compile(r"(?<!\\)%.*")


def buscar(patron, texto):
    return re.search(patron, texto, re.M) is not None
def definido(ruta, sim, texto):
    e = re.escape
    ext = ruta.suffix
    if ext == ".py":
        if "." in sim:  # Clase.metodo
            clase, metodo = sim.split(".", 1)
            return buscar(r"^\s*class\s+%s\b" % e(clase), texto) and buscar(r"^\s*(async\s+)?def\s+%s\b" % e(metodo), texto)
        return buscar(r"^\s*(async\s+)?(def|class)\s+%s\b|^%s\s*(:|=)" % (e(sim), e(sim)), texto)
    if ext in (".hpp", ".cpp", ".h"):
        partes = sim.split("::")
        nombre = e(partes[-1])
        if len(partes) > 1:  # ns::Clase::metodo, Clase::metodo, ns::funcion
            if buscar(r"%s\s*\(" % e(sim), texto):
                return True
            return buscar(r"\b(class|struct|namespace)\s+(\w+::)*%s\b" % e(partes[-2]), texto) and buscar(r"\b%s\s*[(=]" % nombre, texto)
        # nombre simple (o literal "nombre" de un binding pybind11)
        return buscar(r"\b(class|struct|enum\s+class|enum|namespace|using)\s+%s\b|\b%s\s*[(=]|\"%s\"" % (nombre, nombre, nombre), texto)
    if ext in (".ts", ".tsx"):
        return buscar(r"\b(function|const|class|interface|type)\s+%s\b" % e(sim.split(".")[-1]), texto)
    return sim in texto  # .json, .md, .sh, .txt y demas


def main(minimo):
    n, fallos = 0, []
    for tex in sorted((RAIZ / "docs" / "tex").rglob("*.tex")):
        if tex.name.startswith("_"):
            continue
        for ruta_s, sim in CODIGO.findall(COMENTARIO.sub("", tex.read_text(encoding="utf-8"))):
            n += 1
            ruta, sim = RAIZ / ruta_s.strip(), sim.strip()
            if not ruta.is_file():
                fallos.append("%s: ruta inexistente o no es archivo: %s" % (tex.name, ruta_s))
            elif not definido(ruta, sim, ruta.read_text(encoding="utf-8", errors="replace")):
                fallos.append("%s: simbolo `%s` no definido en %s" % (tex.name, sim, ruta_s))
    for f in fallos:
        print(f)
    print("%d referencias, %d fallos" % (n, len(fallos)))
    return 0 if not fallos and n >= minimo else 1


if __name__ == "__main__":
    k = int(sys.argv[sys.argv.index("--min") + 1]) if "--min" in sys.argv else 120
    sys.exit(main(k))
