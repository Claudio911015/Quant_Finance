"""Conexión SQLite y esquema."""
import sqlite3
from pathlib import Path
from typing import Optional, Union

from flask import current_app, g

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "desk.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (id TEXT PRIMARY KEY, label TEXT NOT NULL, synthetic INTEGER NOT NULL, as_of TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, product TEXT NOT NULL, counterparty TEXT NOT NULL, params TEXT NOT NULL, created_at TEXT NOT NULL);
"""


def connect(db_path: Union[str, Path]) -> sqlite3.Connection:
    """Abre (creando el directorio si hace falta) la base con `row_factory=sqlite3.Row`."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Crea las tablas si no existen."""
    conn.executescript(SCHEMA)
    conn.commit()


def get_conn() -> sqlite3.Connection:
    """Conexión de la petición en curso (se cierra al terminar el contexto de la app)."""
    if "db" not in g:
        g.db = connect(current_app.config["DESK_DB"])
    return g.db


def close_conn(exc: Optional[BaseException] = None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()
