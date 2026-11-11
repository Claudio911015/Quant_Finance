"""Respaldo y restauración de la base del desk (corte 8, R4). Solo bases temporales: nunca desk/data/desk.db."""
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from desk.api import backup, db, fixings
from desk.api.app import create_app

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def origen(tmp_path):
    """Base sembrada por `create_app` (operaciones y eventos) más tres fijaciones."""
    path = tmp_path / "origen.db"
    create_app(db_path=path)
    conn = db.connect(path)
    try:
        for day, value in (("2026-11-04", 0.0389), ("2026-11-05", 0.0391), ("2026-11-06", 0.0390)):
            fixings.add_fixing(conn, {"index": "SOFR", "date": day, "value": value})
        conn.commit()
    finally:
        conn.close()
    return path


def _counts(path):
    conn = sqlite3.connect(str(path))
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {t: conn.execute('SELECT COUNT(*) FROM "{}"'.format(t)).fetchone()[0] for t in tables}
    finally:
        conn.close()


def _triggers(path):
    conn = sqlite3.connect(str(path))
    try:
        return sorted(r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'"))
    finally:
        conn.close()


def test_respaldo_y_restauracion_conservan_tablas_y_disparadores(origen, tmp_path):
    copia = backup.backup(origen, tmp_path / "respaldos")
    assert re.fullmatch(r"qfdesk-\d{8}-\d{6}\.sqlite", copia.name)
    assert copia.parent == tmp_path / "respaldos"
    assert sqlite3.connect(str(copia)).execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    destino = tmp_path / "otra" / "restaurada.db"
    assert backup.restore(copia, destino) is None

    cuentas = _counts(origen)
    assert cuentas["trades"] > 0 and cuentas["trade_events"] > 0 and cuentas["fixings"] == 3
    assert _counts(destino) == cuentas
    assert _triggers(destino) == _triggers(origen) and "trade_events_no_update" in _triggers(destino)

    conn = sqlite3.connect(str(destino))
    try:
        with pytest.raises(sqlite3.DatabaseError, match="solo de inserción"):
            conn.execute("UPDATE trade_events SET type = type")
        with pytest.raises(sqlite3.DatabaseError, match="solo de inserción"):
            conn.execute("DELETE FROM trade_events")
    finally:
        conn.close()


def test_respaldo_sin_base_origen_falla_y_no_la_crea(tmp_path):
    ausente = tmp_path / "no-existe.db"
    with pytest.raises(backup.BackupError, match="No existe"):
        backup.backup(ausente, tmp_path / "respaldos")
    assert not ausente.exists()
    assert list((tmp_path / "respaldos").glob("*")) == []


def test_keep_conserva_las_n_mas_recientes(origen, tmp_path):
    dest = tmp_path / "respaldos"
    ajeno = dest / "notas.txt"
    for minuto in (1, 2, 3):
        backup.backup(origen, dest, now=datetime(2026, 11, 11, 10, minuto, 0))
    ajeno.write_text("no es un respaldo")
    assert len(list(dest.glob("qfdesk-*.sqlite"))) == 3  # sin --keep no se borra nada

    backup.backup(origen, dest, keep=2, now=datetime(2026, 11, 11, 10, 4, 0))
    assert sorted(p.name for p in dest.glob("qfdesk-*.sqlite")) == [
        "qfdesk-20261111-100300.sqlite",
        "qfdesk-20261111-100400.sqlite",
    ]
    assert ajeno.read_text() == "no es un respaldo"
    assert not list(dest.glob("*.parcial"))


def test_dos_respaldos_del_mismo_segundo_no_se_pisan(origen, tmp_path):
    dest = tmp_path / "respaldos"
    ahora = datetime(2026, 11, 11, 10, 0, 0)
    primera = backup.backup(origen, dest, now=ahora)
    conn = db.connect(origen)
    try:
        fixings.add_fixing(conn, {"index": "SOFR", "date": "2026-11-07", "value": 0.0388})
        conn.commit()
    finally:
        conn.close()
    segunda = backup.backup(origen, dest, now=ahora)
    tercera = backup.backup(origen, dest, now=ahora)
    assert [p.name for p in (primera, segunda, tercera)] == [
        "qfdesk-20261111-100000.sqlite",
        "qfdesk-20261111-100000-2.sqlite",
        "qfdesk-20261111-100000-3.sqlite",
    ]
    assert _counts(primera)["fixings"] == 3 and _counts(segunda)["fixings"] == 4  # la primera sigue intacta
    assert not list(dest.glob("*.parcial"))


def test_keep_solo_borra_nombres_del_patron_exacto_y_cuenta_los_sufijos_como_mas_recientes(origen, tmp_path):
    dest = tmp_path / "respaldos"
    dest.mkdir()
    ajenos = [
        "qfdesk-notas.sqlite",
        "qfdesk-20261111-100000.sqlite.bak",
        "qfdesk-20260101-000000.sqlite.parcial",
        "qfdesk-2026111-100000.sqlite",
        "qfdesk-20261111-100000-x.sqlite",
        "qfdesk-20261111-100000-.sqlite",
        "otro-20261111-100000.sqlite",
        "qfdesk-20260101-000000.sqlite~",
    ]
    for name in ajenos:
        (dest / name).write_text("no lo creó el desk")
    (dest / "qfdesk-20261111-090000.sqlite").mkdir()  # un directorio con nombre de respaldo tampoco se toca
    backup.backup(origen, dest, now=datetime(2026, 11, 11, 9, 59, 0))
    ahora = datetime(2026, 11, 11, 10, 0, 0)
    backup.backup(origen, dest, now=ahora)
    backup.backup(origen, dest, now=ahora)  # ...-2, más reciente que la sin sufijo aunque "-" ordene antes que "."
    backup.backup(origen, dest, keep=2, now=ahora)  # ...-3
    propias = sorted(p.name for p in dest.iterdir() if p.is_file() and p.name not in ajenos)
    assert propias == ["qfdesk-20261111-100000-2.sqlite", "qfdesk-20261111-100000-3.sqlite"]
    for name in ajenos:
        assert (dest / name).read_text() == "no lo creó el desk"
    assert (dest / "qfdesk-20261111-090000.sqlite").is_dir()


def test_keep_menor_que_uno_es_error_y_no_respalda(origen, tmp_path):
    with pytest.raises(ValueError):
        backup.backup(origen, tmp_path / "respaldos", keep=0)
    assert not (tmp_path / "respaldos").exists()


def test_restaurar_sobre_base_existente_sin_force_no_toca_nada(origen, tmp_path):
    copia = backup.backup(origen, tmp_path / "respaldos")
    destino = tmp_path / "desk.db"
    destino.write_bytes(b"contenido previo")
    with pytest.raises(backup.BackupError, match="--force"):
        backup.restore(copia, destino)
    assert destino.read_bytes() == b"contenido previo"
    assert sorted(p.name for p in tmp_path.iterdir() if p.name.startswith("desk.db")) == ["desk.db"]


def test_restaurar_con_force_deja_copia_previa(origen, tmp_path):
    copia = backup.backup(origen, tmp_path / "respaldos")
    destino = tmp_path / "desk.db"
    conn = sqlite3.connect(str(destino))
    conn.execute("CREATE TABLE marca (x INTEGER)")
    conn.execute("INSERT INTO marca VALUES (7)")
    conn.commit()
    conn.close()

    previa = backup.restore(copia, destino, force=True, now=datetime(2026, 11, 11, 15, 30, 0))
    assert previa == tmp_path / "desk.db.antes-de-restaurar-20261111-153000"
    assert _counts(previa) == {"marca": 1}
    assert _counts(destino) == _counts(origen)


def test_restaurar_con_force_sobre_base_danada_la_conserva_aparte(origen, tmp_path):
    copia = backup.backup(origen, tmp_path / "respaldos")
    destino = tmp_path / "desk.db"
    danada = b"esto no es sqlite " * 200
    destino.write_bytes(danada)

    previa = backup.restore(copia, destino, force=True, now=datetime(2026, 11, 11, 15, 30, 1))
    assert previa.read_bytes() == danada
    assert _counts(destino) == _counts(origen)


def test_restaurar_desde_archivo_danado_o_ausente_no_toca_el_destino(tmp_path):
    destino = tmp_path / "desk.db"
    destino.write_bytes(b"contenido previo")
    malo = tmp_path / "malo.sqlite"
    malo.write_bytes(b"esto no es sqlite " * 200)
    with pytest.raises(backup.BackupError, match="integrity_check"):
        backup.restore(malo, destino, force=True)
    with pytest.raises(backup.BackupError, match="No existe"):
        backup.restore(tmp_path / "ausente.sqlite", destino, force=True)
    assert destino.read_bytes() == b"contenido previo"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["desk.db", "malo.sqlite"]


def test_main_usa_la_base_por_omision_y_devuelve_codigos(origen, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", tmp_path / "desk.db")
    dest = str(tmp_path / "respaldos")

    assert backup.main([dest]) == 1  # la base por omisión no existe
    assert "No existe la base" in capsys.readouterr().err

    (tmp_path / "desk.db").write_bytes(origen.read_bytes())
    assert backup.main([dest, "--keep", "1"]) == 0
    copia = next((tmp_path / "respaldos").glob("qfdesk-*.sqlite"))
    assert str(copia) in capsys.readouterr().out

    assert backup.main(["--restore", str(copia)]) == 1  # la base existe y no hay --force
    assert "--force" in capsys.readouterr().err
    assert backup.main(["--restore", str(copia), "--force"]) == 0
    assert list(tmp_path.glob("desk.db.antes-de-restaurar-*"))


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "desk.api.backup"] + list(args), cwd=str(ROOT),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)


def test_cli_errores_de_uso_salen_con_2(tmp_path):
    dest = str(tmp_path / "respaldos")
    assert _cli().returncode == 2
    assert _cli(dest, "--keep", "0").returncode == 2
    assert _cli(dest, "--restore", "x").returncode == 2
    assert not (tmp_path / "respaldos").exists()


def test_cli_restaurar_archivo_ausente_sale_con_1(tmp_path):
    # Falla al validar el archivo, antes de mirar la base real: no la toca.
    r = _cli("--restore", str(tmp_path / "ausente.sqlite"), "--force")
    assert r.returncode == 1 and "No existe el archivo" in r.stderr


def test_cli_modulo_como_script_con_base_temporal(origen, tmp_path):
    """Ejecuta el bloque `__main__` real, con DEFAULT_DB_PATH apuntando a una base temporal."""
    codigo = (
        "import runpy, sys\n"
        "from pathlib import Path\n"
        "from desk.api import db\n"
        "db.DEFAULT_DB_PATH = Path(sys.argv[1])\n"
        "sys.argv = ['backup'] + sys.argv[2:]\n"
        "runpy.run_module('desk.api.backup', run_name='__main__')\n"
    )

    def correr(*args):
        return subprocess.run([sys.executable, "-c", codigo, str(origen)] + list(args), cwd=str(ROOT),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    ok = correr(str(tmp_path / "respaldos"))
    assert ok.returncode == 0, ok.stderr
    copia = next((tmp_path / "respaldos").glob("qfdesk-*.sqlite"))
    sin_force = correr("--restore", str(copia))
    assert sin_force.returncode == 1 and "--force" in sin_force.stderr
    assert correr("--restore", str(copia), "--force").returncode == 0
