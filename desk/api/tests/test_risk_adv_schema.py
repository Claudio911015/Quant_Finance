"""Corte 6, T3: esquema solo de inserción, recreación en bases existentes, despachos de `method` y `set`."""
import json
import sqlite3

import pytest

from desk.api import db
from desk.api.app import create_app
from desk.api.risk import explain, scenario_sets, var

TABLES = (
    "factor_history", "limits", "limit_events", "limit_breaches",
    "counterparty_credit", "scenario_sets", "scenario_set_events",
)
VAR_BODY = {"snapshot": "MX-DEMO", "horizon_days": 10, "confidence": 0.99}


def _insert_one_row_per_table(path):
    """Una fila por tabla, insertada por SQL (el orden respeta las claves foráneas)."""
    conn = sqlite3.connect(str(path))
    try:
        cp = conn.execute("SELECT id FROM counterparties ORDER BY id LIMIT 1").fetchone()[0]
        conn.execute("INSERT INTO factor_history VALUES ('TIIE-F', 'csv', '2026-11-09', 1.5, 'x')")
        conn.execute("INSERT INTO limits (scope, key, metric, amount, created_at)"
                     " VALUES ('portfolio', 'portfolio', 'var', 1000000, 'x')")
        conn.execute("INSERT INTO limit_events (limit_id, type, amount, reason, created_at)"
                     " VALUES (1, 'create', 1000000, NULL, 'x')")
        conn.execute("INSERT INTO limit_breaches (limit_id, snapshot_id, as_of, amount, usage, pct, created_at)"
                     " VALUES (1, 'MX-DEMO', '2026-11-10', 1000000, 2000000, 200, 'x')")
        conn.execute("INSERT INTO counterparty_credit (counterparty_id, hazard_rate, recovery, as_of, created_at)"
                     " VALUES (?, 0.02, 0.4, '2026-11-11', 'x')", (cp,))
        conn.execute("INSERT INTO scenario_sets (name, description, scenarios, created_at)"
                     " VALUES ('Mío', NULL, '[]', 'x')")
        conn.execute("INSERT INTO scenario_set_events (set_id, type, created_at) VALUES (1, 'retire', 'x')")
        conn.commit()
    finally:
        conn.close()


def _names(path, kind):
    conn = sqlite3.connect(str(path))
    try:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = ?", (kind,))}
    finally:
        conn.close()


# ------------------------------------------------------------------------- esquema

@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("sql", ["UPDATE {t} SET created_at = 'y'", "DELETE FROM {t}"])
def test_corte6_tables_reject_update_and_delete(app, table, sql):
    path = app.config["DESK_DB"]
    _insert_one_row_per_table(path)
    conn = sqlite3.connect(path)
    try:
        with pytest.raises(sqlite3.DatabaseError, match="%s es solo de inserción" % table):
            conn.execute(sql.format(t=table))
    finally:
        conn.close()


def test_corte6_schema_is_recreated_on_an_existing_database(app, client):
    path = app.config["DESK_DB"]
    trades_before = client.get("/api/trades").get_json()["trades"]
    assert trades_before
    conn = sqlite3.connect(path)
    try:
        for table in TABLES:
            conn.execute("DROP TRIGGER IF EXISTS %s_no_update" % table)
            conn.execute("DROP TRIGGER IF EXISTS %s_no_delete" % table)
            conn.execute("DROP TABLE %s" % table)
        conn.commit()
    finally:
        conn.close()
    assert not set(TABLES) & _names(path, "table")

    again = create_app(db_path=path)
    assert set(TABLES) <= _names(path, "table")
    expected = {"%s_%s" % (t, k) for t in TABLES for k in ("no_update", "no_delete")}
    assert len(expected) == 14 and expected <= _names(path, "trigger")
    assert again.test_client().get("/api/trades").get_json()["trades"] == trades_before


# ------------------------------------------------------------------------- constantes reales

def test_contract_constants():
    assert [k for k, _ in explain.STEPS] == [
        "carry", "curve:TIIE-F", "curve:SOFR", "fx", "vol", "new_trades", "events", "residual"]
    assert [s["name"] for s in scenario_sets.BUILTIN_SETS] == [
        "Por omisión", "Depreciación 2008", "2016 elecciones EE. UU.", "Marzo 2020"]
    assert len(scenario_sets.BUILTIN_SETS[0]["scenarios"]) == 8
    assert scenario_sets.BUILTIN_SETS[3]["scenarios"] == [{
        "name": "Marzo 2020", "type": "combined",
        "shocks": [{"type": "fx_spot", "pct": 25.0},
                   {"type": "parallel", "curve": "TIIE-F", "bp": -100.0},
                   {"type": "parallel", "curve": "SOFR", "bp": -150.0}]}]


# ------------------------------------------------------------------------- POST /api/risk/var

def test_var_without_method_or_parametric_is_unchanged(app, client):
    conn = db.connect(app.config["DESK_DB"])
    try:
        direct = json.loads(json.dumps(var.compute_var(conn, "MX-DEMO", dict(VAR_BODY))))
    finally:
        conn.close()
    plain = client.post("/api/risk/var", json=VAR_BODY)
    explicit = client.post("/api/risk/var", json=dict(VAR_BODY, method="parametric"))
    assert plain.status_code == explicit.status_code == 200
    assert plain.get_json() == direct
    assert explicit.get_json() == direct
    assert "method" not in direct


@pytest.mark.parametrize("method", ["x", "", 1, ["historical"]])  # null cuenta como ausente (como en todo `validation`)
def test_var_invalid_method_is_400(client, method):
    r = client.post("/api/risk/var", json=dict(VAR_BODY, method=method))
    assert r.status_code == 400
    assert r.get_json()["field"] == "method"


# ------------------------------------------------------------------------- POST /api/risk/scenarios

def test_scenarios_set_and_scenarios_together_is_400(client):
    inline = [{"name": "FX", "type": "fx_spot", "pct": 10}]
    r = client.post("/api/risk/scenarios", json={"snapshot": "MX-DEMO", "set": "Marzo 2020", "scenarios": inline})
    assert r.status_code == 400
    assert r.get_json()["field"] == "set"


@pytest.mark.parametrize("value", ["", "   ", 5, None, ["Marzo 2020"]])
def test_scenarios_set_must_be_non_empty_text(client, value):
    r = client.post("/api/risk/scenarios", json={"snapshot": "MX-DEMO", "set": value})
    assert r.status_code == 400
    assert r.get_json()["field"] == "set"


# ------------------------------------------------------------------------- ids de ruta

@pytest.mark.parametrize("path", [
    "/api/limits/abc/events",
    "/api/limits/9223372036854775808/events",
    "/api/scenario-sets/abc/retire",
])
def test_non_integer_route_ids_are_404(client, path):
    r = client.post(path, json={"type": "retire"})
    assert r.status_code == 404
    assert r.get_json()["field"] == "id"
