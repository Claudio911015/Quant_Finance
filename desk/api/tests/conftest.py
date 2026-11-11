import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def app(tmp_path):
    from desk.api.app import create_app

    app = create_app(db_path=tmp_path / "t.db")
    # Ninguna prueba toca la base ni el ejecutable reales de MarketDataFeed, ni sale a internet.
    app.config["MDF_DB"] = str(tmp_path / "no-existe" / "sofr.db")
    app.config["MDF_FETCH"] = str(tmp_path / "no-existe" / "fetch_sofr")
    app.config["FRED_DEXMXUS_URL"] = (tmp_path / "no-existe" / "fred.csv").as_uri()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def empty_portfolio(client):
    """Vacía operaciones y eventos por SQL en la base de prueba.

    La API ya no borra operaciones (`DELETE` responde 409) y `trade_events` es solo de
    inserción, así que se quita el disparador de borrado de esta base desechable.
    """
    conn = sqlite3.connect(client.application.config["DESK_DB"])
    try:
        conn.executescript(
            "DROP TRIGGER IF EXISTS trade_events_no_delete;"
            "DELETE FROM trade_events; DELETE FROM trades;"
        )
    finally:
        conn.close()


def insert_raw_trade(app, product, terms_text):
    """Inserta por SQL una operación (posiblemente corrupta) de la contraparte 'Raw'; devuelve su id."""
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        conn.execute("INSERT OR IGNORE INTO counterparties (name) VALUES ('Raw')")
        cp = conn.execute("SELECT id FROM counterparties WHERE name = 'Raw'").fetchone()[0]
        cur = conn.execute(
            "INSERT INTO trades (product, counterparty_id, trade_date, start_date, maturity_date,"
            " terms, created_at) VALUES (?, ?, '2026-11-10', '2026-11-10', '2027-11-10', ?, 'x')",
            (product, cp, terms_text),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()
