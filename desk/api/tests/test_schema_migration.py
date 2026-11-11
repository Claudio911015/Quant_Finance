"""Migración del esquema del corte 1 al del corte 2 (T3): ids, eventos, PV y atomicidad."""
import json
import sqlite3

import pytest

from desk.api import events
from desk.api.app import create_app
from desk.api.tests.corte1_fixture import FIXTURE, build_corte1_db, golden_pv

AS_OF = "2026-11-10"


def _rows(path, sql):
    conn = sqlite3.connect(str(path))
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def _snapshot_v1(path):
    """Todo lo que identifica a una base del corte 1: tablas y filas de `trades`."""
    return (
        _rows(path, "SELECT name FROM sqlite_master ORDER BY name"),
        _rows(path, "SELECT * FROM trades ORDER BY id"),
    )


def _add_corrupt(path, product, params_text):
    conn = sqlite3.connect(str(path))
    conn.execute(
        "INSERT INTO trades (id, product, counterparty, params, created_at) VALUES (8, ?, 'Raw', ?, 'x')",
        (product, params_text),
    )
    conn.commit()
    conn.close()


@pytest.fixture
def migrated(tmp_path):
    path = build_corte1_db(tmp_path / "corte1.db")
    return path, create_app(db_path=path)


def test_migration_keeps_ids_and_gives_each_trade_one_execution(migrated):
    path, app = migrated
    trades = app.test_client().get("/api/trades").get_json()["trades"]
    assert [t["id"] for t in trades] == list(range(1, 8))
    evs = _rows(path, "SELECT trade_id, type, event_date, data, prev_event_id FROM trade_events ORDER BY id")
    assert evs == [(i, "execution", AS_OF, "{}", None) for i in range(1, 8)]
    for t in trades:
        assert t["trade_date"] == t["start_date"] == AS_OF
        assert t["maturity_date"] == t["maturity"] > AS_OF


def test_migration_preserves_created_at_terms_and_counterparties(migrated):
    path, _ = migrated
    expected = {t["id"]: t for t in json.loads(FIXTURE.read_text(encoding="utf-8"))["trades"]}
    rows = _rows(
        path,
        "SELECT t.id, t.product, c.name, t.terms, t.created_at FROM trades t"
        " JOIN counterparties c ON c.id = t.counterparty_id ORDER BY t.id",
    )
    assert len(rows) == 7
    for tid, product, name, terms, created_at in rows:
        assert (product, name, created_at) == (
            expected[tid]["product"], expected[tid]["counterparty"], expected[tid]["created_at"]
        )
        assert json.loads(terms) == json.loads(expected[tid]["params"])
    assert _rows(path, "SELECT COUNT(*) FROM counterparties") == [(3,)]
    assert "trades_v1" not in [r[0] for r in _rows(path, "SELECT name FROM sqlite_master")]


def test_migrated_pv_equals_corte1_golden(migrated):
    _, app = migrated
    v = app.test_client().get("/api/portfolio/valuation?snapshot=MX-DEMO").get_json()
    golden = golden_pv()
    assert [r["id"] for r in v["rows"]] == sorted(golden)
    for r in v["rows"]:
        assert r["error"] is None
        assert r["pv_mxn"] == pytest.approx(golden[r["id"]], rel=1e-8), r["id"]


def test_migration_is_idempotent(migrated, tmp_path):
    path, _ = migrated
    before = {
        "trades": _rows(path, "SELECT * FROM trades ORDER BY id"),
        "events": _rows(path, "SELECT * FROM trade_events ORDER BY id"),
        "counterparties": _rows(path, "SELECT * FROM counterparties ORDER BY id"),
    }
    again = create_app(db_path=path)
    assert again.test_client().get("/api/trades").status_code == 200
    after = {
        "trades": _rows(path, "SELECT * FROM trades ORDER BY id"),
        "events": _rows(path, "SELECT * FROM trade_events ORDER BY id"),
        "counterparties": _rows(path, "SELECT * FROM counterparties ORDER BY id"),
    }
    assert after == before


def test_fresh_seed_equals_migration(migrated, tmp_path):
    path, _ = migrated
    fresh = tmp_path / "fresh.db"
    create_app(db_path=fresh)
    sql = (
        "SELECT t.id, t.product, c.name, t.trade_date, t.start_date, t.maturity_date, t.terms"
        " FROM trades t JOIN counterparties c ON c.id = t.counterparty_id ORDER BY t.id"
    )
    norm = lambda rows: [r[:6] + (json.loads(r[6]),) for r in rows]  # noqa: E731
    assert norm(_rows(fresh, sql)) == norm(_rows(path, sql))
    assert _rows(fresh, "SELECT trade_id, type, event_date FROM trade_events ORDER BY id") == [
        (i, "execution", AS_OF) for i in range(1, 8)
    ]


@pytest.mark.parametrize(
    "product, params_text, reason",
    [
        ("irs", "{no es json", "JSON"),
        ("irs", json.dumps({"curve": "TIIE-F"}), "inválidos"),
        ("bono_raro", "{}", "producto desconocido"),
        ("irs", "[1, 2]", "objeto"),
    ],
)
def test_corrupt_row_aborts_startup_and_leaves_database_untouched(tmp_path, product, params_text, reason):
    path = build_corte1_db(tmp_path / "corte1.db")
    _add_corrupt(path, product, params_text)
    before = _snapshot_v1(path)
    with pytest.raises(RuntimeError) as exc:
        create_app(db_path=path)
    assert "operación 8" in str(exc.value) and reason in str(exc.value)
    assert _snapshot_v1(path) == before  # esquema viejo y mismas filas, sin migración parcial
    assert {r[1] for r in _rows(path, "PRAGMA table_info(trades)")} >= {"params", "counterparty"}


def test_failure_while_writing_rolls_everything_back(tmp_path, monkeypatch):
    path = build_corte1_db(tmp_path / "corte1.db")
    before = _snapshot_v1(path)
    real = events.insert_event
    calls = []

    def flaky(*args, **kwargs):
        calls.append(1)
        if len(calls) == 4:
            raise RuntimeError("falla simulada a mitad de la migración")
        return real(*args, **kwargs)

    monkeypatch.setattr(events, "insert_event", flaky)
    with pytest.raises(RuntimeError, match="falla simulada"):
        create_app(db_path=path)
    assert len(calls) == 4
    assert _snapshot_v1(path) == before


def test_trade_events_are_insert_only(tmp_path):
    path = tmp_path / "t.db"
    create_app(db_path=path)
    conn = sqlite3.connect(str(path))
    try:
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("UPDATE trade_events SET type = 'x'")
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("DELETE FROM trade_events")
        assert conn.execute("SELECT COUNT(*) FROM trade_events").fetchone()[0] == 7
    finally:
        conn.close()
