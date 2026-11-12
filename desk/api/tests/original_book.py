"""Deja la base de prueba con solo las 7 operaciones originales de la semilla.

El corte 9 siembra 9 operaciones más (ids 8 a 16, `seed_trades.XVA_TRADES`). Las pruebas escritas contra
el portafolio de siete (calendario de flujos, conciliación, colateral, crédito del motor anterior) enumeran
ids, productos y avisos de ese portafolio; con este fixture siguen probando exactamente lo mismo en vez de
tener que reescribir cada enumeración. Los conteos que sí dependen del número de operaciones se actualizan
en su propia prueba.
"""
import sqlite3

import pytest


def drop_xva_trades(app):
    """Borra por SQL las operaciones con id > 7 y sus eventos, y rebobina las secuencias AUTOINCREMENT.

    Los disparadores de solo inserción se quitan y se vuelven a crear tal cual para no cambiar el esquema.
    La marca `seed.xva_trades_v1` queda puesta: reabrir la base con `create_app` no las vuelve a sembrar.
    """
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        triggers = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' AND tbl_name IN ('trades', 'trade_events')"
        ).fetchall()
        for name, _ in triggers:
            conn.execute("DROP TRIGGER %s" % name)
        conn.execute("DELETE FROM trade_events WHERE trade_id > 7")
        conn.execute("DELETE FROM trades WHERE id > 7")
        for table in ("trades", "trade_events"):
            conn.execute(
                "UPDATE sqlite_sequence SET seq = (SELECT COALESCE(MAX(id), 0) FROM %s) WHERE name = '%s'"
                % (table, table)
            )
        for _, sql in triggers:
            conn.execute(sql)
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def original_book(app):
    drop_xva_trades(app)
