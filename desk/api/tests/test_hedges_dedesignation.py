"""Coberturas, T5: `POST /api/hedges/<id>/dedesignate` (R8 de desdesignación y R1: fracciones activas tras desdesignar)."""
from datetime import date, timedelta

from desk.api.tests.hedge_fixture import designate, load_fixings, par_irs, roll

D0 = date(2026, 11, 10)
LOAN_END = D0 + timedelta(days=364)
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


def _close(client, hid, days):
    """Rueda MX-DEMO `days` días, carga TIIE-F hasta ahí, cierra el periodo y devuelve el periodo."""
    sid = "D%d" % days
    as_of = date.fromisoformat(roll(client, "MX-DEMO", sid, days))
    load_fixings(client, "TIIE-F", D0, as_of, TIIE)
    r = client.post("/api/hedges/%d/periods" % hid, json={"snapshot": sid})
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _dedesignate(client, hid, when, reason="Prepago del crédito"):
    return client.post("/api/hedges/%d/dedesignate" % hid, json={"date": when, "reason": reason})


def _events(client, hid):
    return client.get("/api/hedges/%d" % hid).get_json()["events"]


def test_dedesignation_after_a_close_freezes_the_reserve(client):
    _, hid = _hedge(client)
    period = _close(client, hid, 35)
    assert period["oci"] != 0  # la prueba tiene sentido solo con una reserva que congelar
    when = (D0 + timedelta(days=40)).isoformat()

    r = _dedesignate(client, hid, when)

    assert r.status_code == 201, r.get_json()
    detail = r.get_json()
    assert detail["status"] == "desdesignada"
    assert detail["dedesignation"] == {"date": when, "reason": "Prepago del crédito", "frozen_oci": period["oci"]}
    assert detail["oci_balance"] == period["oci"]
    assert detail["last_close"] == period["as_of"]
    event = detail["events"][-1]
    assert event["type"] == "dedesignation" and event["event_date"] == when
    assert event["data"] == {"reason": "Prepago del crédito", "frozen_oci": period["oci"]}
    assert [e["type"] for e in detail["events"]] == ["designation", "period_close", "dedesignation"]
    assert client.get("/api/hedges/%d" % hid).get_json() == detail


def test_dedesignation_on_the_last_close_date_is_allowed_and_reason_is_trimmed(client):
    _, hid = _hedge(client)
    period = _close(client, hid, 35)

    r = _dedesignate(client, hid, period["as_of"], reason="  Prepago del crédito  ")

    assert r.status_code == 201, r.get_json()
    assert r.get_json()["dedesignation"]["reason"] == "Prepago del crédito"


def test_dedesignation_without_closes_freezes_zero(client):
    _, hid = _hedge(client)

    r = _dedesignate(client, hid, D0.isoformat())

    assert r.status_code == 201, r.get_json()
    detail = r.get_json()
    assert detail["status"] == "desdesignada"
    assert detail["dedesignation"]["frozen_oci"] == 0.0
    assert detail["oci_balance"] == 0.0 and detail["last_close"] is None


def test_closing_a_period_after_dedesignation_is_409_on_id(client):
    _, hid = _hedge(client)
    _close(client, hid, 35)
    assert _dedesignate(client, hid, (D0 + timedelta(days=40)).isoformat()).status_code == 201
    as_of = date.fromisoformat(roll(client, "MX-DEMO", "D70", 70))
    load_fixings(client, "TIIE-F", D0, as_of, TIIE)

    r = client.post("/api/hedges/%d/periods" % hid, json={"snapshot": "D70"})

    assert r.status_code == 409 and r.get_json()["field"] == "id"
    assert len(client.get("/api/hedges/%d" % hid).get_json()["periods"]) == 1


def test_second_dedesignation_is_409_on_id_and_keeps_the_first(client):
    _, hid = _hedge(client)
    first = _dedesignate(client, hid, (D0 + timedelta(days=5)).isoformat(), reason="Primera").get_json()

    r = _dedesignate(client, hid, (D0 + timedelta(days=9)).isoformat(), reason="Segunda")

    assert r.status_code == 409 and r.get_json()["field"] == "id"
    assert client.get("/api/hedges/%d" % hid).get_json() == first


def test_date_before_the_last_close_is_409_on_date_and_writes_nothing(client):
    _, hid = _hedge(client)
    period = _close(client, hid, 35)
    before = _events(client, hid)

    r = _dedesignate(client, hid, (date.fromisoformat(period["as_of"]) - timedelta(days=1)).isoformat())

    assert r.status_code == 409 and r.get_json()["field"] == "date"
    assert _events(client, hid) == before
    assert client.get("/api/hedges/%d" % hid).get_json()["status"] == "activa"


def test_date_before_the_designation_is_409_on_date(client):
    _, hid = _hedge(client)

    r = _dedesignate(client, hid, (D0 - timedelta(days=1)).isoformat())

    assert r.status_code == 409 and r.get_json()["field"] == "date"
    assert len(_events(client, hid)) == 1


def test_invalid_body_is_400_with_its_field_and_writes_nothing(client):
    _, hid = _hedge(client)
    when = (D0 + timedelta(days=5)).isoformat()
    cases = [
        ({"date": when, "reason": ""}, "reason"),
        ({"date": when, "reason": "   "}, "reason"),
        ({"date": when}, "reason"),
        ({"date": when, "reason": 5}, "reason"),
        ({"reason": "x"}, "date"),
        ({"date": "10/12/2026", "reason": "x"}, "date"),
        ({"date": "2026-02-30", "reason": "x"}, "date"),
    ]
    for body, field in cases:
        r = client.post("/api/hedges/%d/dedesignate" % hid, json=body)
        assert r.status_code == 400 and r.get_json()["field"] == field, (body, r.get_json())
    assert client.post("/api/hedges/%d/dedesignate" % hid, json=[]).status_code == 400
    assert len(_events(client, hid)) == 1
    assert client.get("/api/hedges/%d" % hid).get_json()["status"] == "activa"


def test_unknown_or_malformed_id_is_404_on_id(client):
    for path in ("/api/hedges/999/dedesignate", "/api/hedges/abc/dedesignate"):
        r = client.post(path, json={"date": D0.isoformat(), "reason": "x"})
        assert r.status_code == 404 and r.get_json()["field"] == "id"


def test_dedesignating_the_full_fraction_frees_the_trade_for_a_new_designation(client):
    trade, hid = _hedge(client)
    blocked = designate(client, trade["id"], "floating_loan", _loan(), fraction=0.5)
    assert blocked.status_code == 409 and blocked.get_json()["field"] == "fraction"

    assert _dedesignate(client, hid, D0.isoformat()).status_code == 201

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

    assert _dedesignate(client, ids[0], D0.isoformat()).status_code == 201

    assert designate(client, trade["id"], "floating_loan", _loan(), fraction=0.7).status_code == 409
    assert designate(client, trade["id"], "floating_loan", _loan(), fraction=0.6).status_code == 201


def test_list_reflects_the_dedesignated_status(client):
    _, hid = _hedge(client)
    period = _close(client, hid, 35)
    active = client.get("/api/hedges").get_json()["hedges"][0]
    assert active["status"] == "activa" and active["periods_count"] == 1

    assert _dedesignate(client, hid, (D0 + timedelta(days=40)).isoformat()).status_code == 201

    row = client.get("/api/hedges").get_json()["hedges"][0]
    assert row["id"] == hid and row["status"] == "desdesignada"
    assert row["oci_balance"] == period["oci"] and row["periods_count"] == 1
