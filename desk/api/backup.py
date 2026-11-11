"""Respaldo y restauración de la base del desk (corte 8, R4).

    python -m desk.api.backup <destino_dir> [--keep N]
    python -m desk.api.backup --restore <archivo> [--force]

Siempre trabaja sobre `db.DEFAULT_DB_PATH`. El respaldo usa la API en línea de `sqlite3`, así que
es consistente con el servidor encendido. Restaurar sí exige el servidor apagado (no se detecta).
Las funciones reciben las rutas para poder probarlas con bases temporales.
"""
import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

from desk.api import db

PREFIX = "qfdesk-"
SUFFIX = ".sqlite"
PathLike = Union[str, Path]


class BackupError(Exception):
    """Fallo esperado (archivo ausente, copia dañada, destino existente): el CLI lo imprime y sale con 1."""


def _stamp(now: Optional[datetime]) -> str:
    return (now or datetime.now()).strftime("%Y%m%d-%H%M%S")


def _open_ro(path: Path) -> sqlite3.Connection:
    """Abre solo lectura: `sqlite3.connect` a secas crearía un archivo vacío si la ruta no existe."""
    return sqlite3.connect("{}?mode=ro".format(path.resolve().as_uri()), uri=True)


def _copy(source: Path, target: Path) -> None:
    """Copia consistente `source` -> `target` con la API de respaldo (sobrescribe el contenido de `target`)."""
    src = _open_ro(source)
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def _integrity(path: Path) -> str:
    """Resultado de `PRAGMA integrity_check` ("ok" si está sana); un archivo que no es SQLite lo reporta como texto."""
    try:
        conn = _open_ro(path)
        try:
            return str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        finally:
            conn.close()
    except sqlite3.DatabaseError as e:
        return str(e)


def backup(db_path: PathLike, dest_dir: PathLike, keep: Optional[int] = None,
           now: Optional[datetime] = None) -> Path:
    """Respalda `db_path` en `dest_dir/qfdesk-YYYYMMDD-HHMMSS.sqlite` y devuelve la ruta de la copia.

    Escribe a un archivo provisional y solo lo renombra si `integrity_check` da `ok`, de modo que
    nunca queda en el directorio una copia dañada con nombre de respaldo. Con `keep`, borra después
    las `qfdesk-*.sqlite` más viejas (por nombre, que lleva la marca de tiempo) que excedan `keep`.
    """
    if keep is not None and keep < 1:
        raise ValueError("keep debe ser >= 1")
    source = Path(db_path)
    if not source.is_file():
        raise BackupError("No existe la base a respaldar: {}".format(source))
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    final = dest / "{}{}{}".format(PREFIX, _stamp(now), SUFFIX)
    partial = final.with_name(final.name + ".parcial")
    try:
        _copy(source, partial)
        verdict = _integrity(partial)
        if verdict != "ok":
            raise BackupError("La copia no pasó integrity_check: {}".format(verdict))
        os.replace(str(partial), str(final))
    finally:
        if partial.exists():
            partial.unlink()
    if keep is not None:
        copies: List[Path] = sorted(dest.glob("{}*{}".format(PREFIX, SUFFIX)))
        for old in copies[:-keep]:
            old.unlink()
    return final


def restore(archive: PathLike, db_path: PathLike, force: bool = False,
            now: Optional[datetime] = None) -> Optional[Path]:
    """Restaura `archive` en `db_path`; devuelve la copia previa de la base reemplazada (o None si no había).

    Si `db_path` existe y no hay `force`, no toca nada. Con `force`, antes de pisarla guarda la actual
    como `<base>.antes-de-restaurar-YYYYMMDD-HHMMSS` junto a ella. El archivo origen se verifica
    con `integrity_check` antes de cualquier cambio.
    """
    source = Path(archive)
    target = Path(db_path)
    if not source.is_file():
        raise BackupError("No existe el archivo de respaldo: {}".format(source))
    verdict = _integrity(source)
    if verdict != "ok":
        raise BackupError("El respaldo no pasó integrity_check: {}".format(verdict))
    previous: Optional[Path] = None
    if target.exists():
        if not force:
            raise BackupError("La base {} ya existe; usa --force para reemplazarla "
                              "(se guarda antes una copia de la actual)".format(target))
        previous = target.with_name("{}.antes-de-restaurar-{}".format(target.name, _stamp(now)))
        try:
            _copy(target, previous)
        except sqlite3.DatabaseError:
            # Base dañada, justo el caso de restaurar: se conserva byte a byte y se retira para
            # que el respaldo no tenga que escribirse encima de un archivo ilegible.
            shutil.copy2(str(target), str(previous))
            target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    _copy(source, target)
    return previous


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m desk.api.backup",
        description="Respalda o restaura la base del desk ({}).".format(db.DEFAULT_DB_PATH),
    )
    parser.add_argument("destino_dir", nargs="?", help="directorio donde se crea qfdesk-YYYYMMDD-HHMMSS.sqlite")
    parser.add_argument("--keep", type=int, metavar="N",
                        help="tras respaldar, conserva solo las N copias qfdesk-*.sqlite más recientes")
    parser.add_argument("--restore", metavar="ARCHIVO", help="restaura la base desde este respaldo (servidor apagado)")
    parser.add_argument("--force", action="store_true",
                        help="con --restore: reemplaza una base existente, guardando antes copia de la actual")
    args = parser.parse_args(argv)
    if (args.destino_dir is None) == (args.restore is None):
        parser.error("indica destino_dir (respaldar) o --restore ARCHIVO (restaurar), no ambos ni ninguno")
    if args.keep is not None and args.keep < 1:
        parser.error("--keep debe ser >= 1")
    try:
        if args.restore is not None:
            previous = restore(args.restore, db.DEFAULT_DB_PATH, force=args.force)
            print("Base restaurada en {}".format(db.DEFAULT_DB_PATH))
            if previous is not None:
                print("Copia de la base anterior: {}".format(previous))
        else:
            print("Respaldo creado: {}".format(backup(db.DEFAULT_DB_PATH, args.destino_dir, keep=args.keep)))
    except (BackupError, sqlite3.Error, OSError) as e:
        print("Error: {}".format(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
