"""Corte 6, T6: límites de riesgo, uso, estados en los umbrales y bitácora de excesos (solo de inserción)."""
import sqlite3

import pytest

from desk.api.tests.conftest import insert_raw_trade
from desk.api.tests.hedge_fixture import roll

SNAP = "MX-DEMO"
ALFA = "Banco Alfa (sintético)"
BETA = "Banco Beta (sintético)"
GAMMA = "Banco Gamma (sintético)"
VAR_BODY = {"snapshot": SNAP, "horizon_days": 1, "confidence": 0.99}


def _make(client, scope, metric, key=None, amount=1_000_000, reason=None):
    body = {"scope": scope, "metric": metric, "amount": amount}
    if key is not None:
        body["key"] = key
    if reason is not None:
        body["reason"] = reason
    return client.post("/api/limits", json=body)


def _usage(client, snapshot=SNAP):
    r = client.get("/api/limits/usage?snapshot=%s" % snapshot)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _row(client, limit_id, snapshot=SNAP):
    return next(u for u in _usage(client, snapshot)["usage"] if u["limit_id"] == limit_id)


def _change(client, limit_id, amount):
    r = client.post("/api/limits/%d/events" % limit_id, json={"type": "change", "amount": amount})
    assert r.status_code == 201, r.get_json()


def _sql(app, sql, args=()):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        rows = conn.execute(sql, args).fetchall()
        conn.commit()
        return rows
    finally:
        conn.close()


# ---------------------------------------------------------------- alta

VALID = [
    ("counterparty", "pv_exposure", ALFA),
    ("counterparty", "pv_exposure", GAMMA),
    ("factor", "dv01", "TIIE-F"),
    ("factor", "dv01", "SOFR"),
    ("factor", "fx_delta", "USDMXN"),
    ("portfolio", "var", "portfolio"),
]


@pytest.mark.parametrize("scope,metric,key", VALID)
def test_create_each_valid_combination(client, scope, metric, key):
    r = _make(client, scope, metric, key, 50_000_000, reason="Política 2026")
    assert r.status_code == 201, r.get_json()
    lim = r.get_json()
    assert (lim["scope"], lim["key"], lim["metric"]) == (scope, key, metric)
    assert lim["amount"] == 50_000_000.0
    assert lim["status"] == "activo"
    assert lim["created_at"]
    assert len(lim["events"]) == 1
    ev = lim["events"][0]
    assert (ev["type"], ev["amount"], ev["reason"]) == ("create", 50_000_000.0, "Política 2026")
    assert client.get("/api/limits").get_json()["limits"] == [lim]


def test_portfolio_key_is_optional(client):
    lim = _make(client, "portfolio", "var").get_json()
    assert lim["key"] == "portfolio"
    assert lim["events"][0]["reason"] is None


@pytest.mark.parametrize(
    "body,field",
    [
        ({"metric": "var", "amount": 1}, "scope"),
        ({"scope": "region", "metric": "var", "amount": 1}, "scope"),
        ({"scope": "portfolio", "amount": 1}, "metric"),
        ({"scope": "portfolio", "metric": "vega", "amount": 1}, "metric"),
        ({"scope": "portfolio", "metric": "dv01", "amount": 1}, "metric"),
        ({"scope": "counterparty", "metric": "var", "key": ALFA, "amount": 1}, "metric"),
        ({"scope": "factor", "metric": "pv_exposure", "key": "TIIE-F", "amount": 1}, "metric"),
        ({"scope": "counterparty", "metric": "pv_exposure", "amount": 1}, "key"),
        ({"scope": "counterparty", "metric": "pv_exposure", "key": "   ", "amount": 1}, "key"),
        ({"scope": "counterparty", "metric": "pv_exposure", "key": "Nadie", "amount": 1}, "key"),
        ({"scope": "factor", "metric": "dv01", "amount": 1}, "key"),
        ({"scope": "factor", "metric": "dv01", "key": "USDMXN", "amount": 1}, "key"),
        ({"scope": "factor", "metric": "dv01", "key": "EURMXN", "amount": 1}, "key"),
        ({"scope": "factor", "metric": "fx_delta", "key": "TIIE-F", "amount": 1}, "key"),
        ({"scope": "portfolio", "metric": "var", "key": "otro", "amount": 1}, "key"),
        ({"scope": "portfolio", "metric": "var", "key": "", "amount": 1}, "key"),
        ({"scope": "portfolio", "metric": "var"}, "amount"),
        ({"scope": "portfolio", "metric": "var", "amount": 0}, "amount"),
        ({"scope": "portfolio", "metric": "var", "amount": -5}, "amount"),
        ({"scope": "portfolio", "metric": "var", "amount": "10"}, "amount"),
        ({"scope": "portfolio", "metric": "var", "amount": True}, "amount"),
        ({"scope": "portfolio", "metric": "var", "amount": 1e13 * 10}, "amount"),
        ({"scope": "portfolio", "metric": "var", "amount": 1, "reason": 7}, "reason"),
    ],
)
def test_create_rejections(client, body, field):
    r = client.post("/api/limits", json=body)
    assert r.status_code == 400, r.get_json()
    assert r.get_json()["field"] == field
    assert client.get("/api/limits").get_json()["limits"] == []
    assert _sql(client.application, "SELECT COUNT(*) FROM limit_events") == [(0,)]


def test_validation_order_scope_then_metric_then_key_then_amount(client):
    bad = {"scope": "region", "metric": "vega", "key": "Nadie", "amount": -1}
    assert client.post("/api/limits", json=bad).get_json()["field"] == "scope"
    bad.update(scope="counterparty")
    assert client.post("/api/limits", json=bad).get_json()["field"] == "metric"
    bad.update(metric="pv_exposure")
    assert client.post("/api/limits", json=bad).get_json()["field"] == "key"
    bad.update(key=ALFA)
    assert client.post("/api/limits", json=bad).get_json()["field"] == "amount"
    bad.update(amount=1, reason=3)
    assert client.post("/api/limits", json=bad).get_json()["field"] == "reason"


def test_create_requires_json_object(client):
    r = client.post("/api/limits", data="no json", content_type="text/plain")
    assert r.status_code == 400


def test_duplicate_active_is_409_on_key(client):
    assert _make(client, "factor", "dv01", "TIIE-F").status_code == 201
    r = _make(client, "factor", "dv01", "TIIE-F", 5)
    assert r.status_code == 409 and r.get_json()["field"] == "key"
    # otra clave o métrica sobre el mismo factor sí se admite
    assert _make(client, "factor", "dv01", "SOFR").status_code == 201
    assert _make(client, "factor", "fx_delta", "USDMXN").status_code == 201
    assert len(client.get("/api/limits").get_json()["limits"]) == 3


def test_new_limit_allowed_after_retire(client):
    first = _make(client, "factor", "dv01", "TIIE-F").get_json()
    assert client.post("/api/limits/%d/events" % first["id"], json={"type": "retire"}).status_code == 201
    second = _make(client, "factor", "dv01", "TIIE-F", 2_000)
    assert second.status_code == 201
    limits = client.get("/api/limits").get_json()["limits"]
    assert [lim["id"] for lim in limits] == [first["id"], second.get_json()["id"]]
    assert [lim["status"] for lim in limits] == ["baja", "activo"]


# ---------------------------------------------------------------- eventos

def test_change_inserts_event_and_limits_row_stays(client):
    lim = _make(client, "factor", "dv01", "TIIE-F", 1_000, reason="alta").get_json()
    r = client.post(
        "/api/limits/%d/events" % lim["id"], json={"type": "change", "amount": 2_500, "reason": "Revisión"}
    )
    assert r.status_code == 201
    got = r.get_json()
    assert got["amount"] == 2_500.0 and got["status"] == "activo"
    assert [(e["type"], e["amount"], e["reason"]) for e in got["events"]] == [
        ("create", 1_000.0, "alta"),
        ("change", 2_500.0, "Revisión"),
    ]
    # la fila de `limits` conserva el monto de alta: el vigente sale de los eventos
    assert _sql(client.application, "SELECT amount FROM limits") == [(1_000.0,)]
    assert client.get("/api/limits").get_json()["limits"] == [got]
    _change(client, lim["id"], 3_000)
    assert client.get("/api/limits").get_json()["limits"][0]["amount"] == 3_000.0


def test_retire_marks_baja_and_leaves_usage(client):
    a = _make(client, "factor", "dv01", "TIIE-F").get_json()
    b = _make(client, "factor", "dv01", "SOFR").get_json()
    assert [u["limit_id"] for u in _usage(client)["usage"]] == [a["id"], b["id"]]
    r = client.post("/api/limits/%d/events" % a["id"], json={"type": "retire", "reason": "Ya no aplica"})
    assert r.status_code == 201
    got = r.get_json()
    assert got["status"] == "baja" and got["amount"] == 1_000_000.0
    assert [(e["type"], e["amount"], e["reason"]) for e in got["events"]][-1] == ("retire", None, "Ya no aplica")
    assert [u["limit_id"] for u in _usage(client)["usage"]] == [b["id"]]
    # sigue en el listado, de baja
    assert [lim["status"] for lim in client.get("/api/limits").get_json()["limits"]] == ["baja", "activo"]
    # cualquier evento posterior: 409 id, sin insertar
    for body in ({"type": "change", "amount": 5}, {"type": "retire"}):
        r = client.post("/api/limits/%d/events" % a["id"], json=body)
        assert r.status_code == 409 and r.get_json()["field"] == "id"
    assert _sql(client.application, "SELECT COUNT(*) FROM limit_events WHERE limit_id = ?", (a["id"],)) == [(2,)]


def test_event_rejections(client):
    lim = _make(client, "factor", "dv01", "TIIE-F").get_json()
    url = "/api/limits/%d/events" % lim["id"]
    for path in ("/api/limits/999/events", "/api/limits/abc/events", "/api/limits/%d/events" % (2 ** 63)):
        r = client.post(path, json={"type": "retire"})
        assert r.status_code == 404 and r.get_json()["field"] == "id"
    for body, field in [
        ({}, "type"),
        ({"type": "create", "amount": 5}, "type"),
        ({"type": "borrar"}, "type"),
        ({"type": "change"}, "amount"),
        ({"type": "change", "amount": 0}, "amount"),
        ({"type": "change", "amount": -1}, "amount"),
        ({"type": "change", "amount": "5"}, "amount"),
        ({"type": "change", "amount": 1e14}, "amount"),
        ({"type": "retire", "reason": 3}, "reason"),
    ]:
        r = client.post(url, json=body)
        assert r.status_code == 400, (body, r.get_json())
        assert r.get_json()["field"] == field
    assert _sql(client.application, "SELECT COUNT(*) FROM limit_events") == [(1,)]
    assert client.get("/api/limits").get_json()["limits"][0]["amount"] == 1_000_000.0


# ---------------------------------------------------------------- uso

def test_usage_validates_snapshot(client):
    assert client.get("/api/limits/usage").status_code == 400
    assert client.get("/api/limits/usage").get_json()["field"] == "snapshot"
    r = client.get("/api/limits/usage?snapshot=NOPE")
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"
    assert client.post("/api/limits/check").get_json()["field"] == "snapshot"
    assert client.post("/api/limits/check?snapshot=NOPE").status_code == 404


def test_usage_without_limits_is_empty(client):
    got = _usage(client)
    assert got == {
        "snapshot": SNAP,
        "as_of": "2026-11-10",
        "thresholds": {"alert_pct": 80.0, "breach_pct": 100.0},
        "usage": [],
        "errors": [],
    }


def test_usage_matches_existing_routes_for_the_four_metrics(client):
    valuation = client.get("/api/portfolio/valuation?snapshot=%s" % SNAP).get_json()
    dv01 = client.post("/api/risk/dv01", json={"snapshot": SNAP}).get_json()
    var = client.post("/api/risk/var", json=VAR_BODY).get_json()

    def raw_pv(name):
        return sum(r["pv_mxn"] for r in valuation["rows"] if r["counterparty"] == name and r["error"] is None)

    expected = {}
    ids = {}
    for scope, metric, key in [
        ("counterparty", "pv_exposure", ALFA),
        ("counterparty", "pv_exposure", BETA),
        ("counterparty", "pv_exposure", GAMMA),
        ("factor", "dv01", "TIIE-F"),
        ("factor", "dv01", "SOFR"),
        ("factor", "fx_delta", "USDMXN"),
        ("portfolio", "var", "portfolio"),
    ]:
        ids[(metric, key)] = _make(client, scope, metric, key, 1e9).get_json()["id"]
    fx = next(f for f in var["factors"] if f["factor"] == "USDMXN")
    expected[("pv_exposure", ALFA)] = max(raw_pv(ALFA), 0.0)
    expected[("pv_exposure", BETA)] = max(raw_pv(BETA), 0.0)
    expected[("pv_exposure", GAMMA)] = max(raw_pv(GAMMA), 0.0)
    expected[("dv01", "TIIE-F")] = abs(dv01["curves"]["TIIE-F"]["parallel_mxn"])
    expected[("dv01", "SOFR")] = abs(dv01["curves"]["SOFR"]["parallel_mxn"])
    expected[("fx_delta", "USDMXN")] = abs(fx["exposure_mxn"]) / 100.0
    expected[("var", "portfolio")] = var["var_mxn"]

    # el máximo con 0 se ejerce: al menos una contraparte tiene PV neto negativo y otra positivo
    assert min(raw_pv(n) for n in (ALFA, BETA, GAMMA)) < 0 < max(raw_pv(n) for n in (ALFA, BETA, GAMMA))
    got = _usage(client)
    assert len(got["usage"]) == 7 and got["errors"] == []
    for row in got["usage"]:
        want = expected[(row["metric"], row["key"])]
        assert row["usage"] == pytest.approx(want, abs=1e-6)
        assert row["amount"] == 1e9
        assert row["pct"] == pytest.approx(want / 1e9 * 100, abs=1e-6)
        assert row["status"] == "ok"
        assert row["limit_id"] == ids[(row["metric"], row["key"])]
    assert [u["limit_id"] for u in got["usage"]] == sorted(ids.values())
    # un uso positivo de verdad en las cuatro métricas
    assert all(v > 0 for k, v in expected.items() if k != ("pv_exposure", ALFA))


def test_usage_uses_the_current_amount(client):
    lim = _make(client, "factor", "dv01", "TIIE-F", 1e9).get_json()
    used = _row(client, lim["id"])["usage"]
    _change(client, lim["id"], used * 2)
    row = _row(client, lim["id"])
    assert row["amount"] == pytest.approx(used * 2)
    assert row["pct"] == pytest.approx(50.0, abs=1e-6)


def test_status_at_thresholds(client):
    lim = _make(client, "factor", "dv01", "TIIE-F", 1e9).get_json()
    used = _row(client, lim["id"])["usage"]
    assert used > 0
    for divisor, status in [(0.7999, "ok"), (0.8, "alerta"), (1.0, "alerta"), (1.0001, "exceso")]:
        _change(client, lim["id"], used / divisor)
        row = _row(client, lim["id"])
        assert row["status"] == status, (divisor, row)
        # el estado sale del porcentaje que se informa
        assert (row["pct"] < 80, 80 <= row["pct"] <= 100, row["pct"] > 100) == (
            status == "ok", status == "alerta", status == "exceso"
        )


def test_usage_errors_are_the_union_without_repeating_ids(client):
    bad = insert_raw_trade(client.application, "irs", "{no es json")
    _make(client, "counterparty", "pv_exposure", ALFA, 1e9)
    _make(client, "factor", "dv01", "TIIE-F", 1e9)
    _make(client, "portfolio", "var", None, 1e9)
    got = _usage(client)
    assert [e["id"] for e in got["errors"]] == [bad]
    assert got["errors"][0]["error"]
    assert len(got["usage"]) == 3


# ---------------------------------------------------------------- excesos

def test_check_inserts_one_breach_per_limit_and_is_idempotent(client):
    over = _make(client, "factor", "dv01", "TIIE-F", 1.0).get_json()
    under = _make(client, "factor", "dv01", "SOFR", 1e12).get_json()
    first = client.post("/api/limits/check?snapshot=%s" % SNAP)
    assert first.status_code == 200
    body = first.get_json()
    assert [u["limit_id"] for u in body["usage"]] == [over["id"], under["id"]]
    assert [b["limit_id"] for b in body["new_breaches"]] == [over["id"]]
    breach = body["new_breaches"][0]
    row = next(u for u in body["usage"] if u["limit_id"] == over["id"])
    assert row["status"] == "exceso"
    assert breach["scope"] == "factor" and breach["key"] == "TIIE-F" and breach["metric"] == "dv01"
    assert breach["snapshot"] == SNAP and breach["as_of"] == "2026-11-10"
    assert breach["amount"] == 1.0
    assert breach["usage"] == pytest.approx(row["usage"], abs=1e-6)
    assert breach["pct"] == pytest.approx(row["pct"], abs=1e-6)
    assert breach["created_at"] and breach["id"] >= 1

    again = client.post("/api/limits/check?snapshot=%s" % SNAP).get_json()
    assert again["new_breaches"] == []
    assert len(client.get("/api/limits/breaches").get_json()["breaches"]) == 1


def test_check_on_another_date_inserts_another_breach(client):
    lim = _make(client, "factor", "dv01", "TIIE-F", 1.0).get_json()
    client.post("/api/limits/check?snapshot=%s" % SNAP)
    as_of = roll(client, SNAP, "D1", 30)
    r = client.post("/api/limits/check?snapshot=D1").get_json()
    assert r["as_of"] == as_of
    assert [b["limit_id"] for b in r["new_breaches"]] == [lim["id"]]
    assert r["new_breaches"][0]["snapshot"] == "D1"
    breaches = client.get("/api/limits/breaches").get_json()["breaches"]
    assert [b["as_of"] for b in breaches] == [as_of, "2026-11-10"]
    assert [b["id"] for b in breaches] == sorted((b["id"] for b in breaches), reverse=True)


def test_check_ignores_alerts_and_retired_limits(client):
    alert = _make(client, "factor", "dv01", "TIIE-F", 1e9).get_json()
    used = _row(client, alert["id"])["usage"]
    _change(client, alert["id"], used / 0.9)  # alerta, no exceso
    gone = _make(client, "factor", "dv01", "SOFR", 1.0).get_json()
    client.post("/api/limits/%d/events" % gone["id"], json={"type": "retire"})
    r = client.post("/api/limits/check?snapshot=%s" % SNAP).get_json()
    assert [u["status"] for u in r["usage"]] == ["alerta"]
    assert r["new_breaches"] == []
    assert client.get("/api/limits/breaches").get_json() == {"breaches": []}


def test_breach_records_the_amount_in_force(client):
    lim = _make(client, "factor", "dv01", "TIIE-F", 1e12).get_json()
    _change(client, lim["id"], 10.0)
    b = client.post("/api/limits/check?snapshot=%s" % SNAP).get_json()["new_breaches"][0]
    assert b["amount"] == 10.0 and b["pct"] > 100


# ---------------------------------------------------------------- solo de inserción

def test_history_tables_are_insert_only(client):
    lim = _make(client, "factor", "dv01", "TIIE-F", 1.0).get_json()
    client.post("/api/limits/check?snapshot=%s" % SNAP)
    conn = sqlite3.connect(client.application.config["DESK_DB"])
    try:
        for table, update in [
            ("limits", "UPDATE limits SET amount = 5"),
            ("limit_events", "UPDATE limit_events SET amount = 5"),
            ("limit_breaches", "UPDATE limit_breaches SET pct = 1"),
        ]:
            with pytest.raises(sqlite3.DatabaseError, match="%s es solo de inserción" % table):
                conn.execute(update)
            with pytest.raises(sqlite3.DatabaseError, match="%s es solo de inserción" % table):
                conn.execute("DELETE FROM %s" % table)
        assert conn.execute("SELECT COUNT(*) FROM limit_breaches").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM limit_events WHERE limit_id = ?", (lim["id"],)).fetchone()[0] == 1
    finally:
        conn.close()
