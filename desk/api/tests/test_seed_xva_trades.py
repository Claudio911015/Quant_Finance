"""Corte 9: las 9 operaciones nuevas que dan al XVA compensación real por contraparte."""
import sqlite3

from desk.api import db, market, portfolio, valuation
from desk.api import fixings as fixing_store
from desk.api.app import create_app
from desk.api.seed_trades import XVA_TRADES, ensure_xva_trades

_ALFA = "Banco Alfa (sintético)"
_BETA = "Banco Beta (sintético)"
_GAMMA = "Banco Gamma (sintético)"
_KEY = "seed.xva_trades_v1"

# (id, producto, contraparte, trade_date) en el orden de la tabla del plan.
_TABLE = [
    (8, "irs", _ALFA, "2025-11-10"),
    (9, "irs", _ALFA, "2026-02-03"),
    (10, "xccy_swap", _ALFA, "2026-05-12"),
    (11, "irs", _BETA, "2026-08-17"),
    (12, "xccy_swap", _BETA, "2026-11-10"),
    (13, "irs", _BETA, "2026-11-10"),
    (14, "irs", _GAMMA, "2025-08-01"),
    (15, "irs", _GAMMA, "2026-11-10"),
    (16, "xccy_swap", _GAMMA, "2025-02-14"),
]


def _conn(app):
    return db.connect(app.config["DESK_DB"])


def _load(app):
    conn = _conn(app)
    try:
        return portfolio.load_trades(conn)
    finally:
        conn.close()


def _drop_new_ones(path):
    """Deja la base como estaba antes del corte 9: solo las 7 originales y sin la marca."""
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            "DROP TRIGGER IF EXISTS trade_events_no_delete;"
            "DELETE FROM trade_events WHERE trade_id > 7;"
            "DELETE FROM trades WHERE id > 7;"
            "DELETE FROM settings WHERE key = '%s';" % _KEY
        )
        conn.commit()
    finally:
        conn.close()


def test_new_base_has_sixteen_trades_with_the_table_dates(app):
    trades = _load(app)
    assert len(trades) == 16
    new = [t for t in trades if t["id"] >= 8]
    assert [(t["id"], t["product"], t["counterparty"], t["trade_date"].isoformat()) for t in new] == _TABLE
    assert len(XVA_TRADES) == 9


def test_every_counterparty_has_an_irs_and_an_xccy(app):
    trades = _load(app)
    for name in (_ALFA, _BETA, _GAMMA):
        products = {t["product"] for t in trades if t["counterparty"] == name}
        assert {"irs", "xccy_swap"} <= products, name


def test_new_trades_keep_the_explicit_terms_of_the_table(app):
    by_id = {t["id"]: t for t in _load(app)}
    assert by_id[8]["params"]["fixed_rate"] == 0.0710 and by_id[8]["params"]["periods"] == 39
    assert by_id[8]["params"]["side"] == "receiver" and by_id[8]["params"]["curve"] == "TIIE-F"
    assert by_id[9]["params"]["curve"] == "SOFR" and by_id[9]["params"]["fixed_rate"] == 0.0375
    assert by_id[10]["params"]["side"] == "pay_usd" and by_id[10]["params"]["fx_rate"] == 18.20
    assert by_id[10]["params"]["spread"] == 0.0005 and by_id[10]["params"]["exchange"] == "both"
    assert by_id[12]["params"]["side"] == "pay_mxn" and by_id[12]["params"]["notional_usd"] == 10e6
    assert by_id[16]["params"]["exchange"] == "final" and by_id[16]["params"]["spread"] == 0.0
    assert by_id[16]["params"]["periods"] == 52


def test_restarting_create_app_does_not_duplicate(tmp_path):
    path = tmp_path / "x.db"
    create_app(db_path=path)
    app = create_app(db_path=path)
    assert len(_load(app)) == 16
    conn = _conn(app)
    try:
        assert conn.execute("SELECT value FROM settings WHERE key = ?", (_KEY,)).fetchone() is not None
    finally:
        conn.close()


def test_settings_key_marks_the_step(app):
    conn = _conn(app)
    try:
        assert conn.execute("SELECT COUNT(*) FROM settings WHERE key = ?", (_KEY,)).fetchone()[0] == 1
    finally:
        conn.close()


def test_base_with_only_the_original_seven_receives_the_nine_and_keeps_the_seven(tmp_path):
    path = tmp_path / "old.db"
    app = create_app(db_path=path)
    before = [t for t in _load(app) if t["id"] <= 7]
    _drop_new_ones(path)
    assert len(_load(app)) == 7

    app = create_app(db_path=path)
    trades = _load(app)
    assert len(trades) == 16
    assert [t for t in trades if t["id"] <= 7] == before  # mismos params y fechas
    # los ids siguen la secuencia AUTOINCREMENT tras el borrado por SQL: se compara sin id
    assert [(t["product"], t["counterparty"], t["trade_date"].isoformat())
            for t in trades if t["id"] > 7] == [row[1:] for row in _TABLE]


def test_step_is_not_repeated_once_marked(tmp_path):
    """Si alguien vacía el portafolio después de la marca, no se resiembra."""
    path = tmp_path / "e.db"
    app = create_app(db_path=path)
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            "DROP TRIGGER IF EXISTS trade_events_no_delete;"
            "DELETE FROM trade_events; DELETE FROM trades;"
        )
        conn.commit()
    finally:
        conn.close()
    app = create_app(db_path=path)
    assert _load(app) == []


def test_ensure_without_snapshot_does_nothing(tmp_path):
    conn = db.connect(tmp_path / "vacia.db")
    try:
        db.init_schema(conn)
        ensure_xva_trades(conn)
        assert conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM settings WHERE key = ?", (_KEY,)).fetchone()[0] == 0
    finally:
        conn.close()


def test_seed_false_does_not_add_the_nine(tmp_path):
    app = create_app(db_path=tmp_path / "s.db", seed=False)
    assert _load(app) == []


def test_all_sixteen_value_without_error(app):
    conn = _conn(app)
    try:
        mkt = market.load_context(conn, "MX-DEMO")
        fixings = fixing_store.load_all(conn)
        for t in portfolio.load_trades(conn):
            v = valuation.value_trade(t, mkt, fixings)
            assert v["status"] is not None, t["id"]
            assert v["pv_mxn"] is not None and v["pv_mxn"] == v["pv_mxn"], t["id"]
    finally:
        conn.close()
