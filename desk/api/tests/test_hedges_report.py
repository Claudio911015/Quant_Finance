"""Coberturas, T6: `GET /api/hedges/<id>/report` y su CSV de asientos (R9)."""
import csv
import io
from datetime import date, timedelta

import pytest

from desk.api import hedges
from desk.api.tests.hedge_fixture import designate, load_fixings, par_irs, roll

D0 = date(2026, 11, 10)
LOAN_END = D0 + timedelta(days=364)
FIXED_END = D0 + timedelta(days=28 * 26)
NOTIONAL = 500e6
TIIE = 0.07  # por encima de la tasa par: el swap que paga fija gana y hay reserva y liquidaciones

NOTICE = "Asientos sugeridos. Metodología pendiente de revisión por un contador con experiencia en IFRS 9"
REPORT_KEYS = {
    "id", "generated_at", "notice", "relationship", "documentation", "prospective", "periods",
    "entries_by_period", "reserve_releases", "entries_total", "fair_value_hierarchy", "reserve",
}
PERIOD_KEYS = {
    "id", "snapshot", "as_of", "data_quality", "inst_cum", "hypo_cum", "oci", "d_oci", "ineffectiveness",
    "recycled", "item_adjustment", "fv_result", "settled_period",
}
CSV_HEADER = "period_id,as_of,snapshot,account,debit,credit,memo"


def _loan():
    return {
        "index": "TIIE-F", "notional": NOTIONAL, "start_date": D0.isoformat(),
        "maturity_date": LOAN_END.isoformat(), "side": "pays_floating",
    }


def _hedge(client):
    """`par_irs` + designación de un crédito variable; devuelve `(operación, id de la cobertura)`."""
    trade = par_irs(client, "TIIE-F", NOTIONAL, D0, LOAN_END)
    r = designate(client, trade["id"], "floating_loan", _loan())
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


def _report(client, hid, query=""):
    r = client.get("/api/hedges/%d/report%s" % (hid, query))
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _cents(x):
    return int(round(x * 100))


def _csv_rows(client, hid):
    r = client.get("/api/hedges/%d/report?format=csv" % hid)
    assert r.status_code == 200
    rows = list(csv.reader(io.StringIO(r.get_data(as_text=True))))
    assert rows[0] == CSV_HEADER.split(",")
    return rows[1:]


def _two_closes(client):
    _, hid = _hedge(client)
    return hid, [_close(client, hid, 35), _close(client, hid, 70)]  # D1 cruza el cupón del día 28


def test_report_has_every_section_of_the_contract(client):
    hid, periods = _two_closes(client)
    detail = client.get("/api/hedges/%d" % hid).get_json()

    report = _report(client, hid)

    assert set(report) == REPORT_KEYS
    assert report["id"] == hid
    assert report["notice"] == NOTICE
    assert isinstance(report["generated_at"], str) and report["generated_at"]
    assert report["relationship"] == {k: v for k, v in detail.items() if k not in ("events", "periods")}

    doc = report["documentation"]
    assert doc["risk_management_objective"] == "Fijar el costo del crédito sindicado"
    assert doc["hedged_risk"] == "Variabilidad de los intereses por TIIE de Fondeo"
    assert doc["effectiveness_method"] == "Términos críticos y escenarios con derivado hipotético"
    assert doc["ineffectiveness_sources"].startswith("Diferencias de fechas y nocional")
    assert doc["hedged_item"] == {"item_kind": "floating_loan", "item_terms": detail["item_terms"]}
    assert doc["hedge_ratio"] == 1.0
    assert doc["hedging_instrument"] == {
        "trade_id": detail["trade_id"], "product": "irs", "counterparty": "Banco Alfa (sintético)",
        "fraction": 1.0, "notional": NOTIONAL, "currency": "MXN",
        "start_date": D0.isoformat(), "maturity_date": LOAN_END.isoformat(),
    }

    assert [p["id"] for p in report["periods"]] == [p["id"] for p in periods]
    for row, period in zip(report["periods"], periods):
        assert set(row) == PERIOD_KEYS
        assert row == {k: period[k] for k in PERIOD_KEYS}
    assert [b["period_id"] for b in report["entries_by_period"]] == [p["id"] for p in periods]
    for block, period in zip(report["entries_by_period"], periods):
        assert block == {"period_id": period["id"], "as_of": period["as_of"], "entries": period["entries"]}

    assert report["reserve"] == {"balance": periods[-1]["oci"], "frozen": False, "note": None, "released": 0}
    assert report["reserve_releases"] == []
    assert report["relationship"]["warnings"] == []
    assert periods[-1]["oci"] != 0


def test_prospective_test_uses_the_designation_snapshot_unless_another_is_given(client):
    hid, _ = _two_closes(client)

    default = _report(client, hid)["prospective"]
    other = _report(client, hid, "?snapshot=D35")["prospective"]

    assert default == client.get("/api/hedges/%d/effectiveness?snapshot=MX-DEMO" % hid).get_json()
    assert other == client.get("/api/hedges/%d/effectiveness?snapshot=D35" % hid).get_json()
    assert default["snapshot"] == "MX-DEMO" and other["snapshot"] == "D35"


def test_hierarchy_is_level_2_with_the_provenance_of_every_snapshot_used(client):
    hid, periods = _two_closes(client)
    quality = {s["id"]: s["data_quality"] for s in client.get("/api/market/snapshots").get_json()["snapshots"]}

    hierarchy = _report(client, hid)["fair_value_hierarchy"]

    assert hierarchy["level"] == 2 and hierarchy["basis"].startswith("Nivel 2: insumos observables")
    assert hierarchy["snapshots"] == [
        {"role": "designation", "snapshot": "MX-DEMO", "as_of": D0.isoformat(), "data_quality": quality["MX-DEMO"]},
        {"role": "period", "snapshot": "D35", "as_of": periods[0]["as_of"], "data_quality": quality["D35"]},
        {"role": "period", "snapshot": "D70", "as_of": periods[1]["as_of"], "data_quality": quality["D70"]},
    ]


def test_entries_total_adds_every_period_by_account_and_balances(client):
    hid, periods = _two_closes(client)

    total = _report(client, hid)["entries_total"]

    expected = {}
    for period in periods:
        for e in period["entries"]:
            d, c = expected.get(e["account"], (0, 0))
            expected[e["account"]] = (d + _cents(e["debit"]), c + _cents(e["credit"]))
    assert [t["account"] for t in total] == [a for a in hedges.ACCOUNTS if a in expected]
    for t in total:
        assert (_cents(t["debit"]), _cents(t["credit"])) == expected[t["account"]]
    assert sum(_cents(t["debit"]) for t in total) == sum(_cents(t["credit"]) for t in total)
    assert {hedges.ACC_DERIVATIVE, hedges.ACC_OCI, hedges.ACC_CASH, hedges.ACC_RECYCLING} <= set(expected)


def test_fair_value_report_totals_land_in_the_fair_value_result_account(client):
    trade = par_irs(client, "TIIE-F", 300e6, D0, FIXED_END, side="receiver")
    terms = {
        "index": "TIIE-F", "notional": 300e6, "start_date": D0.isoformat(),
        "maturity_date": FIXED_END.isoformat(), "side": "pays_fixed",
    }
    r = designate(client, trade["id"], "fixed_loan", terms, hedge_type="fair_value")
    assert r.status_code == 201, r.get_json()
    hid = r.get_json()["id"]
    _close(client, hid, 35)

    report = _report(client, hid)

    accounts = [t["account"] for t in report["entries_total"]]
    assert accounts == [a for a in hedges.ACCOUNTS if a in accounts]
    assert hedges.ACC_FV_RESULT in accounts and hedges.ACC_ITEM_ADJ in accounts
    assert hedges.ACC_OCI not in accounts and hedges.ACC_RECYCLING not in accounts
    assert report["relationship"]["hedge_type"] == "fair_value"
    assert report["documentation"]["hedged_item"]["item_kind"] == "fixed_loan"
    assert report["reserve"] == {"balance": 0.0, "frozen": False, "note": None, "released": 0}


def test_a_relationship_without_closes_reports_empty_sections(client):
    _, hid = _hedge(client)

    report = _report(client, hid)

    assert report["periods"] == [] and report["entries_by_period"] == [] and report["entries_total"] == []
    assert [s["role"] for s in report["fair_value_hierarchy"]["snapshots"]] == ["designation"]
    assert report["reserve"]["balance"] == 0.0
    assert "error" not in report["prospective"]
    assert _csv_rows(client, hid) == []


def test_csv_has_the_exact_header_and_one_row_per_entry(client):
    hid, periods = _two_closes(client)

    r = client.get("/api/hedges/%d/report?format=csv" % hid)

    assert r.headers["Content-Type"] == "text/csv; charset=utf-8"
    assert r.headers["Content-Disposition"] == 'attachment; filename="cobertura-%d-asientos.csv"' % hid
    text = r.get_data(as_text=True)
    assert text.splitlines()[0] == CSV_HEADER
    rows = _csv_rows(client, hid)
    expected = [
        [str(p["id"]), p["as_of"], p["snapshot"], e["account"], "%.2f" % e["debit"], "%.2f" % e["credit"], e["memo"]]
        for p in periods
        for e in p["entries"]
    ]
    assert rows == expected
    assert len(rows) == sum(len(p["entries"]) for p in periods)


def test_csv_debits_equal_credits_to_the_cent(client):
    hid, _ = _two_closes(client)

    rows = _csv_rows(client, hid)

    assert sum(_cents(float(r[4])) for r in rows) == sum(_cents(float(r[5])) for r in rows)
    assert any(float(r[4]) > 0 for r in rows) and any(float(r[5]) > 0 for r in rows)


def _dedesignate(client, hid, snapshot):
    r = client.post(
        "/api/hedges/%d/dedesignate" % hid, json={"snapshot": snapshot, "reason": "Prepago del crédito", "cause": "instrument_ended"}
    )
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def test_dedesignated_relationship_reports_the_frozen_reserve(client):
    hid, periods = _two_closes(client)
    _dedesignate(client, hid, "D70")

    report = _report(client, hid)

    assert report["reserve"] == {"balance": periods[-1]["oci"], "frozen": True, "note": hedges.FROZEN_NOTE, "released": 0}
    assert report["relationship"]["status"] == "desdesignada"
    dedesignation = report["relationship"]["dedesignation"]
    assert dedesignation["frozen_oci"] == periods[-1]["oci"] and dedesignation["cause"] == "instrument_ended"
    assert dedesignation["snapshot"] == "D70"


def test_reserve_releases_appear_in_the_report_the_totals_and_the_csv(client):
    hid, periods = _two_closes(client)
    detail = _dedesignate(client, hid, "D70")
    frozen = detail["oci_balance"]
    part = round(frozen / 4, 2)
    for body in ({"amount": part, "cause": "flow_occurred"}, {"cause": "flow_no_longer_expected"}):
        r = client.post("/api/hedges/%d/release" % hid, json={"snapshot": "D70", **body})
        assert r.status_code == 201, r.get_json()

    report = _report(client, hid)

    first, second = report["reserve_releases"]
    assert (first["snapshot"], first["as_of"], first["cause"], first["amount"]) == ("D70", periods[-1]["as_of"], "flow_occurred", part)
    assert second["cause"] == "flow_no_longer_expected" and second["reserve_after"] == 0.0
    assert second["amount"] == pytest.approx(frozen - part, abs=1e-9)
    assert report["reserve"] == {"balance": 0.0, "frozen": True, "note": None, "released": pytest.approx(frozen, abs=1e-9)}
    # Los totales por cuenta suman cierres y liberaciones: ORI queda en 0.00 y los asientos siguen cuadrando.
    total = {t["account"]: (_cents(t["debit"]), _cents(t["credit"])) for t in report["entries_total"]}
    assert total[hedges.ACC_OCI][0] == total[hedges.ACC_OCI][1]
    assert hedges.ACC_INEFFECTIVENESS in total
    assert sum(d for d, _ in total.values()) == sum(c for _, c in total.values())
    rows = _csv_rows(client, hid)
    release_rows = [r for r in rows if r[0] == ""]
    assert len(rows) == sum(len(p["entries"]) for p in periods) + 4 and len(release_rows) == 4
    assert {r[2] for r in release_rows} == {"D70"} and {r[1] for r in release_rows} == {periods[-1]["as_of"]}
    assert sum(_cents(float(r[4])) for r in rows) == sum(_cents(float(r[5])) for r in rows)
    ori = sum(_cents(float(r[4])) - _cents(float(r[5])) for r in rows if r[3] == hedges.ACC_OCI)
    assert ori == 0  # el acumulado de ORI en el CSV (cierres + liberaciones) es 0.00


def test_prospective_snapshot_after_maturity_is_reported_as_an_error_not_a_failure(client):
    _, hid = _hedge(client)
    roll(client, "MX-DEMO", "LATE", 400)  # el swap vence a los 364 días

    report = _report(client, hid, "?snapshot=LATE")

    assert set(report) == REPORT_KEYS
    assert set(report["prospective"]) == {"error"}
    assert report["prospective"]["error"].startswith("La operación de cobertura no está viva")


def test_errors_keep_their_status_and_field(client):
    _, hid = _hedge(client)

    r = client.get("/api/hedges/%d/report?format=xml" % hid)
    assert r.status_code == 400 and r.get_json()["field"] == "format"
    r = client.get("/api/hedges/%d/report?snapshot=NOPE" % hid)
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"
    r = client.get("/api/hedges/%d/report" % (hid + 99))
    assert r.status_code == 404 and r.get_json()["field"] == "id"
    r = client.get("/api/hedges/%d/report?format=csv&snapshot=NOPE" % hid)
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"
