"""Conexión SQLite y esquema."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from flask import current_app, g

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "desk.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (id TEXT PRIMARY KEY, label TEXT NOT NULL, synthetic INTEGER NOT NULL, as_of TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS counterparties (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, product TEXT NOT NULL,
  counterparty_id INTEGER NOT NULL REFERENCES counterparties(id), trade_date TEXT NOT NULL, start_date TEXT NOT NULL,
  maturity_date TEXT NOT NULL, terms TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS trade_events (id INTEGER PRIMARY KEY AUTOINCREMENT, trade_id INTEGER NOT NULL REFERENCES trades(id),
  type TEXT NOT NULL, event_date TEXT NOT NULL, data TEXT NOT NULL, prev_event_id INTEGER REFERENCES trade_events(id), created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS trade_events_no_update BEFORE UPDATE ON trade_events BEGIN SELECT RAISE(ABORT, 'trade_events es solo de inserción'); END;
CREATE TRIGGER IF NOT EXISTS trade_events_no_delete BEFORE DELETE ON trade_events BEGIN SELECT RAISE(ABORT, 'trade_events es solo de inserción'); END;
CREATE TABLE IF NOT EXISTS fixings (index_name TEXT NOT NULL, fixing_date TEXT NOT NULL, value REAL NOT NULL, PRIMARY KEY (index_name, fixing_date));
CREATE TABLE IF NOT EXISTS hedge_relationships (id INTEGER PRIMARY KEY AUTOINCREMENT,
  trade_id INTEGER NOT NULL REFERENCES trades(id), fraction REAL NOT NULL, hedge_type TEXT NOT NULL,
  item_kind TEXT NOT NULL, item_terms TEXT NOT NULL, hedge_ratio REAL NOT NULL, designation_date TEXT NOT NULL,
  designation_snapshot TEXT NOT NULL, documentation TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS hedge_relationships_no_update BEFORE UPDATE ON hedge_relationships BEGIN SELECT RAISE(ABORT, 'hedge_relationships no se modifica'); END;
CREATE TRIGGER IF NOT EXISTS hedge_relationships_no_delete BEFORE DELETE ON hedge_relationships BEGIN SELECT RAISE(ABORT, 'hedge_relationships no se modifica'); END;
CREATE TABLE IF NOT EXISTS hedge_events (id INTEGER PRIMARY KEY AUTOINCREMENT,
  relationship_id INTEGER NOT NULL REFERENCES hedge_relationships(id), type TEXT NOT NULL, event_date TEXT NOT NULL,
  data TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS hedge_events_no_update BEFORE UPDATE ON hedge_events BEGIN SELECT RAISE(ABORT, 'hedge_events es solo de inserción'); END;
CREATE TRIGGER IF NOT EXISTS hedge_events_no_delete BEFORE DELETE ON hedge_events BEGIN SELECT RAISE(ABORT, 'hedge_events es solo de inserción'); END;
CREATE TABLE IF NOT EXISTS hedge_periods (id INTEGER PRIMARY KEY AUTOINCREMENT,
  relationship_id INTEGER NOT NULL REFERENCES hedge_relationships(id), snapshot_id TEXT NOT NULL, as_of TEXT NOT NULL,
  result TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE (relationship_id, as_of));
CREATE TRIGGER IF NOT EXISTS hedge_periods_no_update BEFORE UPDATE ON hedge_periods BEGIN SELECT RAISE(ABORT, 'hedge_periods es solo de inserción'); END;
CREATE TRIGGER IF NOT EXISTS hedge_periods_no_delete BEFORE DELETE ON hedge_periods BEGIN SELECT RAISE(ABORT, 'hedge_periods es solo de inserción'); END;
-- --- corte 6: riesgo avanzado (historia de factores, límites, crédito, conjuntos de escenarios) ---
CREATE TABLE IF NOT EXISTS factor_history (factor TEXT NOT NULL, source TEXT NOT NULL, date TEXT NOT NULL,
  value REAL NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (factor, source, date));
CREATE TRIGGER IF NOT EXISTS factor_history_no_update BEFORE UPDATE ON factor_history BEGIN SELECT RAISE(ABORT, 'factor_history es solo de inserción'); END;
CREATE TRIGGER IF NOT EXISTS factor_history_no_delete BEFORE DELETE ON factor_history BEGIN SELECT RAISE(ABORT, 'factor_history es solo de inserción'); END;
CREATE TABLE IF NOT EXISTS limits (id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL, key TEXT NOT NULL,
  metric TEXT NOT NULL, amount REAL NOT NULL, created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS limits_no_update BEFORE UPDATE ON limits BEGIN SELECT RAISE(ABORT, 'limits es solo de inserción'); END;
CREATE TRIGGER IF NOT EXISTS limits_no_delete BEFORE DELETE ON limits BEGIN SELECT RAISE(ABORT, 'limits es solo de inserción'); END;
CREATE TABLE IF NOT EXISTS limit_events (id INTEGER PRIMARY KEY AUTOINCREMENT, limit_id INTEGER NOT NULL REFERENCES limits(id),
  type TEXT NOT NULL, amount REAL, reason TEXT, created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS limit_events_no_update BEFORE UPDATE ON limit_events BEGIN SELECT RAISE(ABORT, 'limit_events es solo de inserción'); END;
CREATE TRIGGER IF NOT EXISTS limit_events_no_delete BEFORE DELETE ON limit_events BEGIN SELECT RAISE(ABORT, 'limit_events es solo de inserción'); END;
CREATE TABLE IF NOT EXISTS limit_breaches (id INTEGER PRIMARY KEY AUTOINCREMENT, limit_id INTEGER NOT NULL REFERENCES limits(id),
  snapshot_id TEXT NOT NULL, as_of TEXT NOT NULL, amount REAL NOT NULL, usage REAL NOT NULL, pct REAL NOT NULL,
  created_at TEXT NOT NULL, UNIQUE (limit_id, as_of));
CREATE TRIGGER IF NOT EXISTS limit_breaches_no_update BEFORE UPDATE ON limit_breaches BEGIN SELECT RAISE(ABORT, 'limit_breaches es solo de inserción'); END;
CREATE TRIGGER IF NOT EXISTS limit_breaches_no_delete BEFORE DELETE ON limit_breaches BEGIN SELECT RAISE(ABORT, 'limit_breaches es solo de inserción'); END;
CREATE TABLE IF NOT EXISTS counterparty_credit (id INTEGER PRIMARY KEY AUTOINCREMENT,
  counterparty_id INTEGER NOT NULL REFERENCES counterparties(id), hazard_rate REAL NOT NULL, recovery REAL NOT NULL,
  as_of TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS counterparty_credit_no_update BEFORE UPDATE ON counterparty_credit BEGIN SELECT RAISE(ABORT, 'counterparty_credit es solo de inserción'); END;
CREATE TRIGGER IF NOT EXISTS counterparty_credit_no_delete BEFORE DELETE ON counterparty_credit BEGIN SELECT RAISE(ABORT, 'counterparty_credit es solo de inserción'); END;
CREATE TABLE IF NOT EXISTS scenario_sets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
  description TEXT, scenarios TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS scenario_sets_no_update BEFORE UPDATE ON scenario_sets BEGIN SELECT RAISE(ABORT, 'scenario_sets es solo de inserción'); END;
CREATE TRIGGER IF NOT EXISTS scenario_sets_no_delete BEFORE DELETE ON scenario_sets BEGIN SELECT RAISE(ABORT, 'scenario_sets es solo de inserción'); END;
CREATE TABLE IF NOT EXISTS scenario_set_events (id INTEGER PRIMARY KEY AUTOINCREMENT,
  set_id INTEGER NOT NULL REFERENCES scenario_sets(id), type TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS scenario_set_events_no_update BEFORE UPDATE ON scenario_set_events BEGIN SELECT RAISE(ABORT, 'scenario_set_events es solo de inserción'); END;
CREATE TRIGGER IF NOT EXISTS scenario_set_events_no_delete BEFORE DELETE ON scenario_set_events BEGIN SELECT RAISE(ABORT, 'scenario_set_events es solo de inserción'); END;
-- --- fin corte 6 ---
"""


def connect(db_path: Union[str, Path]) -> sqlite3.Connection:
    """Abre (creando el directorio si hace falta) la base con `row_factory=sqlite3.Row`."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def now_iso() -> str:
    """Marca de tiempo UTC ISO 8601 sin microsegundos (`created_at` de operaciones y eventos)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def init_schema(conn: sqlite3.Connection) -> None:
    """Crea las tablas si no existen; una base del corte 1 se migra antes (idempotente)."""
    from desk.api import migrate  # import tardío: migrate usa portfolio, que usa este módulo

    if migrate.is_v1(conn):
        migrate.migrate_v1(conn)
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
