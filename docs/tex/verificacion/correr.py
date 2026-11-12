"""Corre los ejemplos verificables docs/tex/verificacion/capNN_*.py (R3).

Uso: python docs/tex/verificacion/correr.py [--parcial]
Termina con 0 solo si: todos los scripts terminan con 0, cada \\verif{id} de capitulos/cap*.tex sale como
`OK id` en algun script y (sin --parcial) cada capitulo 02-12 tiene >= 2 \\verif con id `capNN-...`.
"""
import re
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CAPITULOS = AQUI.parent / "capitulos"
VERIF = re.compile(r"\\verif\{([^}]*)\}\{")
COMENTARIO = re.compile(r"(?<!\\)%.*")


def main(parcial):
    ok_ids, fallos = set(), []
    scripts = sorted(AQUI.glob("cap[0-9][0-9]_*.py"))
    for script in scripts:
        r = subprocess.run([sys.executable, script.name], cwd=str(AQUI), capture_output=True, text=True, timeout=900)
        ok_ids |= set(re.findall(r"^OK (\S+)", r.stdout, re.M))
        if r.returncode != 0:
            fallos.append("%s termino con codigo %d\n%s%s" % (script.name, r.returncode, r.stdout, r.stderr))
    en_texto = {}  # id -> archivo
    for tex in sorted(CAPITULOS.glob("cap[0-9][0-9]_*.tex")):
        for i in VERIF.findall(COMENTARIO.sub("", tex.read_text(encoding="utf-8"))):
            en_texto[i.strip()] = tex.name
    for i, archivo in sorted(en_texto.items()):
        if i not in ok_ids:
            fallos.append("\\verif{%s} (%s) no tiene un `OK %s` en ningun script" % (i, archivo, i))
        if not i.startswith(archivo[:5] + "-"):
            fallos.append("id `%s` debe empezar por `%s-` (esta en %s)" % (i, archivo[:5], archivo))
    if not parcial:
        for n in range(2, 13):
            cuantos = sum(1 for a in en_texto.values() if a.startswith("cap%02d_" % n))
            if cuantos < 2:
                fallos.append("FALTAN ejemplos verificables: cap%02d tiene %d (se exigen >= 2)" % (n, cuantos))
    print("%d scripts, %d valores verificados" % (len(scripts), len(ok_ids)))
    for f in fallos:
        print(f)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main("--parcial" in sys.argv))
