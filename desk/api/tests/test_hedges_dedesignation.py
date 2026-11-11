"""Coberturas, T5 + C2: `POST /api/hedges/<id>/dedesignate {snapshot, reason, cause}` (R8 de desdesignación y R1: fracciones activas tras desdesignar)."""
import json
import sqlite3
from datetime import date, timedelta

from desk.api.tests.hedge_fixture import designate, load_fixings, market_forward, par_irs, roll

D0 = date(2026, 11, 10)
LOAN_END = D0 + timedelta(days=364)
FWD_END = D0 + timedelta(days=20)
NOTIONAL = 500e6
TIIE = 0.07  # por encima de la tasa par: el swap que paga fija gana y la reserva no es cero


def _loan():
    return {
        "index": "TIIE-F", "notional": NOTIONAL, "start_date": D0.isoformat(),
        "maturity_date": LOAN_END.isoformat(), "side": "pays_floating",
    }


def _hedge(client, **over):
    """`par_irs` + designación de un crédito variable; devuelve `(operación, id de la cobertura)`."""
    trade = par_irs(client, "TIIE-F", NOTIONAL, D0, LOAN_END)
    r = designate(client, trade["id"], "floating_loan", _loan(), **over)
    assert r.status_code == 201, r.get_json()
    return trade, r.get_json()["id"]


def _snapshot(client, days):
    """Rueda MX-DEMO `days` días (snapshot `D<days>`), carga TIIE-F hasta ahí y devuelve su id."""
    sid = "D%d" % days
    as_of = date.fromisoformat(roll(client, "MX-DEMO", sid, days))
    load_fixings(client, "TIIE-F", D0, as_of, TIIE)
    return sid


def _close(client, hid, days):
    """Cierra el periodo con el snapshot `D<days>` y devuelve el periodo."""
    r = client.post("/api/hedges/%d/periods" % hid, json={"snapshot": _snapshot(client, days)})
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _dedesignate(client, hid, snapshot, reason="Prepago del crédito", cause="instrument_ended"):
    return client.post("/api/hedges/%d/dedesignate" % hid, json={"snapshot": snapshot, "reason": reason, "cause": cause})


def _detail(client, hid):
    return client.get("/api/hedges/%d" % hid).get_json()


def _events(client, hid):
    return _detail(client, hid)["events"]


def _counts(app):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        return [conn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in ("hedge_events", "hedge_periods")]
    finally:
        conn.close()


# ------------------------------------------------------------------------- C2: mide hasta la fecha de la desdesignación

def test_dedesignating_with_a_later_snapshot_closes_a_period_first_and_freezes_that_reserve(client):
    _, hid = _hedge(client)
    first = _close(client, hid, 35)
    sid = _snapshot(client, 40)

    r = _dedesignate(client, hid, sid)

    assert r.status_code == 201, r.get_json()
    detail = r.get_json()
    assert [p["snapshot"] for p in detail["periods"]] == ["D35", "D40"]
    last = detail["periods"][-1]
    assert last["oci"] != first["oci"] and last["prev_snapshot"] == "D35"  # cerró el tramo entre los dos snapshots
    when = (D0 + timedelta(days=40)).isoformat()
    assert detail["status"] == "desdesignada"
    assert detail["dedesignation"] == {
        "date": when, "reason": "Prepago del crédito", "cause": "instrument_ended", "snapshot": sid,
        "frozen_oci": last["oci"],
    }
    assert detail["oci_balance"] == last["oci"] and detail["last_close"] == when
    assert [e["type"] for e in detail["events"]] == ["designation", "period_close", "period_close", "dedesignation"]
    event = detail["events"][-1]
    assert event["event_date"] == when
    assert event["data"] == {"reason": "Prepago del crédito", "cause": "instrument_ended", "snapshot": sid, "frozen_oci": last["oci"]}
    assert _detail(client, hid) == detail


def test_dedesignating_with_the_snapshot_of_the_last_close_does_not_measure_again(app, client):
    _, hid = _hedge(client)
    period = _close(client, hid, 35)
    before = _counts(app)

    r = _dedesignate(client, hid, "D35", reason="  Prepago del crédito  ", cause="criteria_not_met")

    assert r.status_code == 201, r.get_json()
    detail = r.get_json()
    assert _counts(app) == [before[0] + 1, before[1]]
    assert [p["id"] for p in detail["periods"]] == [period["id"]]
    assert detail["dedesignation"]["reason"] == "Prepago del crédito"
    assert detail["dedesignation"]["cause"] == "criteria_not_met" and detail["dedesignation"]["frozen_oci"] == period["oci"]


def test_dedesignating_at_the_designation_snapshot_without_closes_freezes_zero(client):
    _, hid = _hedge(client)

    r = _dedesignate(client, hid, "MX-DEMO", cause="risk_objective_changed")

    assert r.status_code == 201, r.get_json()
    detail = r.get_json()
    assert detail["status"] == "desdesignada" and detail["periods"] == []
    assert detail["dedesignation"] == {
        "date": D0.isoformat(), "reason": "Prepago del crédito", "cause": "risk_objective_changed",
        "snapshot": "MX-DEMO", "frozen_oci": 0.0,
    }
    assert detail["oci_balance"] == 0.0 and detail["last_close"] is None


def test_dedesignating_with_a_later_snapshot_and_no_closes_makes_the_first_close(client):
    _, hid = _hedge(client)
    sid = _snapshot(client, 35)

    detail = _dedesignate(client, hid, sid).get_json()

    assert [p["snapshot"] for p in detail["periods"]] == [sid]
    assert detail["periods"][0]["prev_snapshot"] == "MX-DEMO" and detail["periods"][0]["oci"] != 0
    assert detail["dedesignation"]["frozen_oci"] == detail["periods"][0]["oci"]


def test_the_closing_done_by_the_dedesignation_follows_the_close_rules(app, client):
    trade, hid = _hedge(client)
    sid = _snapshot(client, 35)
    r = client.post(
        "/api/trades/%d/events" % trade["id"],
        json={"type": "termination", "event_date": "2026-12-01", "data": {"amount": 0.0}},
    )
    assert r.status_code == 201, r.get_json()
    before = _counts(app)

    r = _dedesignate(client, hid, sid)

    assert r.status_code == 409 and r.get_json()["field"] == "snapshot"
    assert "ya no está viva" in r.get_json()["error"] and "snapshot del último cierre" in r.get_json()["error"]
    assert _counts(app) == before and _detail(client, hid)["status"] == "activa"
    # Siempre queda el camino de desdesignar con el snapshot de la designación (o del último cierre).
    assert _dedesignate(client, hid, "MX-DEMO").status_code == 201


def test_a_later_snapshot_after_the_final_close_cannot_close_again(app, client):
    trade = market_forward(client, "buy", 10e6, FWD_END)
    r = designate(client, trade["id"], "forecast_fx", {"amount_usd": 10e6, "date": FWD_END.isoformat(), "side": "buy_usd"})
    assert r.status_code == 201, r.get_json()
    hid = r.get_json()["id"]
    roll(client, "MX-DEMO", "F1", 25)  # ya vencido: cierre final
    roll(client, "MX-DEMO", "F2", 40)
    assert client.post("/api/hedges/%d/periods" % hid, json={"snapshot": "F1"}).status_code == 201
    before = _counts(app)

    r = _dedesignate(client, hid, "F2")
    assert r.status_code == 409 and r.get_json()["field"] == "snapshot"
    assert _counts(app) == before

    detail = _dedesignate(client, hid, "F1").get_json()  # con el snapshot del cierre final sí
    assert detail["status"] == "desdesignada" and detail["dedesignation"]["frozen_oci"] == 0.0


# ------------------------------------------------------------------------- estados y errores

def test_closing_a_period_after_dedesignation_is_409_on_id(client):
    _, hid = _hedge(client)
    _close(client, hid, 35)
    assert _dedesignate(client, hid, "D35").status_code == 201
    sid = _snapshot(client, 70)

    r = client.post("/api/hedges/%d/periods" % hid, json={"snapshot": sid})

    assert r.status_code == 409 and r.get_json()["field"] == "id"
    assert len(_detail(client, hid)["periods"]) == 1


def test_second_dedesignation_is_409_on_id_and_keeps_the_first(client):
    _, hid = _hedge(client)
    first = _dedesignate(client, hid, "MX-DEMO", reason="Primera").get_json()
    sid = _snapshot(client, 9)

    r = _dedesignate(client, hid, sid, reason="Segunda")

    assert r.status_code == 409 and r.get_json()["field"] == "id"
    assert _detail(client, hid) == first


def test_snapshot_before_the_last_close_is_409_on_snapshot_and_writes_nothing(app, client):
    _, hid = _hedge(client)
    _close(client, hid, 35)
    early = _snapshot(client, 20)
    before = _counts(app)

    r = _dedesignate(client, hid, early)

    assert r.status_code == 409 and r.get_json()["field"] == "snapshot"
    assert r.get_json()["error"].endswith(", el último cierre de la cobertura")
    assert _counts(app) == before and _detail(client, hid)["status"] == "activa"


def test_snapshot_before_the_designation_is_409_on_snapshot(app, client):
    _, hid = _hedge(client)
    roll(client, "MX-DEMO", "BEFORE", -3)
    before = _counts(app)

    r = _dedesignate(client, hid, "BEFORE")

    assert r.status_code == 409 and r.get_json()["field"] == "snapshot"
    assert r.get_json()["error"].endswith(", la designación de la cobertura")
    assert _counts(app) == before


def test_invalid_body_is_400_with_its_field_and_writes_nothing(app, client):
    _, hid = _hedge(client)
    base = {"snapshot": "MX-DEMO", "reason": "x", "cause": "instrument_ended"}
    cases = [
        ({**base, "reason": ""}, "reason"),
        ({**base, "reason": "   "}, "reason"),
        ({k: v for k, v in base.items() if k != "reason"}, "reason"),
        ({**base, "reason": 5}, "reason"),
        ({k: v for k, v in base.items() if k != "snapshot"}, "snapshot"),
        ({**base, "snapshot": ""}, "snapshot"),
        ({k: v for k, v in base.items() if k != "cause"}, "cause"),
        ({**base, "cause": "porque sí"}, "cause"),
        ({**base, "cause": 3}, "cause"),
    ]
    before = _counts(app)
    for body, field in cases:
        r = client.post("/api/hedges/%d/dedesignate" % hid, json=body)
        assert r.status_code == 400 and r.get_json()["field"] == field, (body, r.get_json())
    assert client.post("/api/hedges/%d/dedesignate" % hid, json=[]).status_code == 400
    r = client.post("/api/hedges/%d/dedesignate" % hid, json={**base, "snapshot": "NO-EXISTE"})
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"
    assert _counts(app) == before and _detail(client, hid)["status"] == "activa"


def test_the_old_date_field_is_no_longer_the_way_to_dedesignate(client):
    _, hid = _hedge(client)

    r = client.post("/api/hedges/%d/dedesignate" % hid, json={"date": D0.isoformat(), "reason": "x"})

    assert r.status_code == 400 and r.get_json()["field"] == "snapshot"


def test_unknown_or_malformed_id_is_404_on_id(client):
    for path in ("/api/hedges/999/dedesignate", "/api/hedges/abc/dedesignate"):
        r = client.post(path, json={"snapshot": "MX-DEMO", "reason": "x", "cause": "instrument_ended"})
        assert r.status_code == 404 and r.get_json()["field"] == "id"


# ------------------------------------------------------------------------- R1: fracciones tras desdesignar

def test_dedesignating_the_full_fraction_frees_the_trade_for_a_new_designation(client):
    trade, hid = _hedge(client)
    blocked = designate(client, trade["id"], "floating_loan", _loan(), fraction=0.5)
    assert blocked.status_code == 409 and blocked.get_json()["field"] == "fraction"

    assert _dedesignate(client, hid, "MX-DEMO").status_code == 201

    again = designate(client, trade["id"], "floating_loan", _loan(), fraction=1.0)
    assert again.status_code == 201, again.get_json()
    assert again.get_json()["id"] != hid


def test_dedesignating_part_of_the_fraction_frees_only_that_part(client):
    trade = par_irs(client, "TIIE-F", NOTIONAL, D0, LOAN_END)
    ids = []
    for fraction in (0.6, 0.4):
        r = designate(client, trade["id"], "floating_loan", _loan(), fraction=fraction)
        assert r.status_code == 201, r.get_json()
        ids.append(r.get_json()["id"])

    assert _dedesignate(client, ids[0], "MX-DEMO").status_code == 201

    assert designate(client, trade["id"], "floating_loan", _loan(), fraction=0.7).status_code == 409
    assert designate(client, trade["id"], "floating_loan", _loan(), fraction=0.6).status_code == 201


def test_list_reflects_the_dedesignated_status(client):
    _, hid = _hedge(client)
    period = _close(client, hid, 35)
    active = client.get("/api/hedges").get_json()["hedges"][0]
    assert active["status"] == "activa" and active["periods_count"] == 1

    assert _dedesignate(client, hid, "D35").status_code == 201

    row = client.get("/api/hedges").get_json()["hedges"][0]
    assert row["id"] == hid and row["status"] == "desdesignada"
    assert row["oci_balance"] == period["oci"] and row["periods_count"] == 1


def test_a_legacy_dedesignation_event_without_cause_still_reads(app, client):
    """Un evento guardado antes de C2 (sin causa ni snapshot) se muestra sin romper el detalle."""
    _, hid = _hedge(client)
    conn = sqlite3.connect(app.config["DESK_DB"])
    conn.execute(
        "INSERT INTO hedge_events (relationship_id, type, event_date, data, created_at)"
        " VALUES (?, 'dedesignation', '2026-11-20', ?, 'x')",
        (hid, json.dumps({"reason": "Prepago", "frozen_oci": 0.0})),
    )
    conn.commit()
    conn.close()

    detail = _detail(client, hid)

    assert detail["status"] == "desdesignada"
    assert detail["dedesignation"]["cause"] is None and detail["dedesignation"]["snapshot"] is None
