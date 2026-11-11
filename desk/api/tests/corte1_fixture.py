"""Base del corte 1 congelada para probar la migración (T3): esquema viejo + PV dorado."""
import json
import sqlite3
from pathlib import Path
from typing import Dict

from desk.api.seed_market import seed_market

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "corte1_trades.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def build_corte1_db(path) -> Path:
    """Crea una base con el esquema del corte 1, mercado MX-DEMO y las operaciones congeladas."""
    path = Path(path)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            "CREATE TABLE snapshots (id TEXT PRIMARY KEY, label TEXT NOT NULL, synthetic INTEGER NOT NULL, as_of TEXT NOT NULL, data TEXT NOT NULL);"
            "CREATE TABLE trades (id INTEGER PRIMARY KEY AUTOINCREMENT, product TEXT NOT NULL, counterparty TEXT NOT NULL, params TEXT NOT NULL, created_at TEXT NOT NULL);"
        )
        seed_market(conn)
        for t in _load()["trades"]:
            conn.execute(
                "INSERT INTO trades (id, product, counterparty, params, created_at) VALUES (?, ?, ?, ?, ?)",
                (t["id"], t["product"], t["counterparty"], t["params"], t["created_at"]),
            )
        conn.commit()
    finally:
        conn.close()
    return path


def golden_pv() -> Dict[int, float]:
    """PV en MXN de cada operación del corte 1 con MX-DEMO, según el código del corte 1."""
    return {t["id"]: t["pv_mxn"] for t in _load()["trades"]}
