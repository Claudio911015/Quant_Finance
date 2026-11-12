"""Calendario de flujos del portafolio (corte 5, T2): `GET /api/cashflows` y su CSV (R1, R2)."""
import csv
import io
from datetime import date

import pytest

from desk.api import fixings, market, portfolio, valuation
from desk.api.db import connect
from desk.api.ops_cashflows import CSV_COLUMNS
from desk.api.tests import hedge_fixture
from desk.api.tests.conftest import insert_raw_trade
from desk.api.tests.ops_fixture import ALFA, confirm_raw
from desk.api.tests.original_book import original_book  # noqa: F401  (fixture)

# corte 9: el calendario se prueba sobre el portafolio original de siete operaciones (ids 1 a 7)
pytestmark = pytest.mark.usefixtures("original_book")

AS_OF = date(2026, 11, 10)
FIRST_COUPON = date(2026, 12, 8)  # día 28: primer cupón de las operaciones 1 y 2 (TIIE-F, 28 días)
URL = "/api/cashflows?snapshot=%s"


def _get(client, query="", snapshot="MX-DEMO"):
    r = client.get(URL % snapshot + query)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _roll_with_fixings(client, days=35):
    """Rueda a +`days` días y publica fijaciones TIIE-F y SOFR de todo el periodo: sin avisos."""
    as_of = hedge_fixture.roll(client, "MX-DEMO", "D1", days)
    end = date.fromisoformat(as_of)
    hedge_fixture.load_fixings(client, "TIIE-F", AS_OF, end, 0.0705)
    hedge_fixture.load_fixings(client, "SOFR", AS_OF, end, 0.0405)
    return as_of


def _pv(app, trade_id, snapshot="MX-DEMO"):
    """`pv` de `value_trade` (en la moneda de la curva para el resto de los productos)."""
    conn = connect(app.config["DESK_DB"])
    try:
        trade = portfolio.get_trade(conn, trade_id)
        mkt = market.load_context(conn, snapshot)
        return valuation.value_trade(trade, mkt, fixings.load_all(conn))["pv"]
    finally:
        conn.close()


def _new_bond(client):
    r = client.post(
        "/api/trades",
        json={
            "product": "bond",
            "counterparty": ALFA,
            "params": {"face": 1e8, "coupon_rate": 0.08, "periods": 6},
        },
    )
    assert r.status_code == 201, r.get_json()
    return r.get_json()["id"]


# ----------------------------------------------------------------------------- R1


@pytest.mark.parametrize("trade_id", [1, 2, 3, "bond"])
def test_projected_flows_discount_back_to_the_pv_of_the_trade(app, client, trade_id):
    if trade_id == "bond":
        trade_id = _new_bond(client)
    rows = [r for r in _get(client)["rows"] if r["trade_id"] == trade_id and r["status"] == "projected"]
    notional = portfolio.public_trade(_trade(app, trade_id))["notional"]
    assert rows
    assert sum(r["amount"] * r["df"] for r in rows) == pytest.approx(
        _pv(app, trade_id), abs=1e-6 * notional
    )
    assert all(r["pv"] == pytest.approx(r["amount"] * r["df"]) for r in rows)


def _trade(app, trade_id):
    conn = connect(app.config["DESK_DB"])
    try:
        return portfolio.get_trade(conn, trade_id)
    finally:
        conn.close()


def test_projected_flows_after_rolling_still_add_up_to_the_pv(app, client):
    _roll_with_fixings(client)
    body = _get(client, snapshot="D1")
    for trade_id in (1, 2):
        rows = [r for r in body["rows"] if r["trade_id"] == trade_id and r["status"] == "projected"]
        assert sum(r["amount"] * r["df"] for r in rows) == pytest.approx(
            _pv(app, trade_id, "D1"), abs=1e-6 * 500e6
        )


def test_only_irs_and_bonds_have_projected_rows_and_usd_rows_convert_at_the_spot(client):
    bond = _new_bond(client)
    body = _get(client)
    projected = [r for r in body["rows"] if r["status"] == "projected"]
    assert {r["trade_id"] for r in projected} == {1, 2, 3, bond}
    assert {r["product"] for r in body["rows"]} == {"irs", "bond"}
    usd = [r for r in body["rows"] if r["currency"] == "USD"]
    assert usd and {r["trade_id"] for r in usd} == {3}
    ratios = {round(r["amount_mxn"] / r["amount"], 9) for r in usd}
    assert len(ratios) == 1 and 15 < ratios.pop() < 30  # un solo tipo de cambio: el spot del snapshot
    mxn = [r for r in body["rows"] if r["currency"] == "MXN"]
    assert all(r["amount_mxn"] == r["amount"] for r in mxn)


# ------------------------------------------------------------------- filtros y orden


def test_window_is_inclusive_on_both_ends(client):
    full = _get(client)["rows"]
    only_first = _get(client, "&from=2026-12-08&to=2026-12-08")
    assert [r["date"] for r in only_first["rows"]] == ["2026-12-08", "2026-12-08"]
    assert {r["trade_id"] for r in only_first["rows"]} == {1, 2}
    assert only_first["from"] == only_first["to"] == "2026-12-08"
    after = _get(client, "&from=2027-01-05")["rows"]
    assert after and all(r["date"] >= "2027-01-05" for r in after)
    assert any(r["date"] == "2027-01-05" for r in after)  # el extremo incluido está
    before = _get(client, "&to=2027-01-05")["rows"]
    assert before and all(r["date"] <= "2027-01-05" for r in before)
    assert any(r["date"] == "2027-01-05" for r in before)
    assert len(after) + len(before) == len(full) + sum(1 for r in full if r["date"] == "2027-01-05")
    assert _get(client)["from"] is None and _get(client)["to"] is None


def test_counterparty_filter_is_exact_and_an_unknown_one_returns_no_rows(client):
    beta = _get(client, "&counterparty=Banco Beta (sintético)")
    assert beta["rows"] and {r["counterparty"] for r in beta["rows"]} == {"Banco Beta (sintético)"}
    assert {r["trade_id"] for r in beta["rows"]} == {2}
    assert beta["counterparty"] == "Banco Beta (sintético)"
    none = _get(client, "&counterparty=Banco Fantasma")
    assert none["rows"] == [] and none["errors"] == []
    assert none["totals"] == {"amount_mxn": 0.0, "by_date": [], "by_counterparty": [], "by_currency": []}


def test_currency_filter_keeps_only_that_currency(client):
    usd = _get(client, "&currency=USD")["rows"]
    assert usd and {r["trade_id"] for r in usd} == {3}  # las operaciones 4-6 no tienen proyectados
    assert all(r["currency"] == "USD" for r in usd)
    mxn = _get(client, "&currency=MXN")["rows"]
    assert mxn and all(r["currency"] == "MXN" for r in mxn) and 3 not in {r["trade_id"] for r in mxn}
    assert len(usd) + len(mxn) == len(_get(client)["rows"])
    assert _get(client, "&currency=USD")["currency"] == "USD"


def test_rows_are_sorted_by_date_trade_and_kind_and_have_the_contract_keys(client):
    body = _get(client)
    keys = [(r["date"], r["trade_id"], r["kind"]) for r in body["rows"]]
    assert keys == sorted(keys)
    assert set(body["rows"][0]) == {
        "date", "trade_id", "counterparty", "product", "kind", "status", "currency", "amount",
        "amount_mxn", "df", "pv", "confirmed_amount", "difference",
    }
    assert set(body) == {
        "snapshot", "as_of", "from", "to", "counterparty", "currency", "rows", "totals", "errors",
        "warnings",
    }
    assert body["as_of"] == AS_OF.isoformat() and body["snapshot"] == "MX-DEMO"


# ------------------------------------------------------------------------- totales


def test_totals_add_up_to_the_rows_and_each_group_to_its_own_rows(client):
    _new_bond(client)
    body = _get(client)
    rows, totals = body["rows"], body["totals"]
    assert totals["amount_mxn"] == pytest.approx(sum(r["amount_mxn"] for r in rows), abs=1e-9)

    def check(groups, key, with_amount):
        assert [g[key] for g in groups] == sorted({r[key] for r in rows})
        for g in groups:
            members = [r for r in rows if r[key] == g[key]]
            assert g["count"] == len(members)
            assert g["amount_mxn"] == pytest.approx(sum(r["amount_mxn"] for r in members), abs=1e-9)
            assert ("amount" in g) == with_amount
            if with_amount:
                assert g["amount"] == pytest.approx(sum(r["amount"] for r in members), abs=1e-9)
        assert sum(g["count"] for g in groups) == len(rows)

    check(totals["by_date"], "date", False)
    check(totals["by_counterparty"], "counterparty", False)
    check(totals["by_currency"], "currency", True)
    assert {g["currency"] for g in totals["by_currency"]} == {"MXN", "USD"}


def test_totals_follow_the_filters(client):
    body = _get(client, "&counterparty=Banco Gamma (sintético)&to=2027-12-31")
    assert body["rows"]
    assert body["totals"]["amount_mxn"] == pytest.approx(sum(r["amount_mxn"] for r in body["rows"]), abs=1e-9)
    assert [g["counterparty"] for g in body["totals"]["by_counterparty"]] == ["Banco Gamma (sintético)"]


# ----------------------------------------------------------------------------- CSV


def test_csv_has_the_same_rows_in_the_same_order_with_the_exact_header(client):
    body = _get(client, "&to=2027-03-31")
    r = client.get(URL % "MX-DEMO" + "&to=2027-03-31&format=csv")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "text/csv; charset=utf-8"
    assert r.headers["Content-Disposition"] == 'attachment; filename="flujos-MX-DEMO.csv"'
    table = list(csv.reader(io.StringIO(r.get_data(as_text=True))))
    assert tuple(table[0]) == CSV_COLUMNS
    assert table[0] == [
        "date", "trade_id", "counterparty", "product", "kind", "status", "currency", "amount",
        "amount_mxn", "confirmed_amount", "difference",
    ]
    data = table[1:]
    assert len(data) == len(body["rows"]) > 0
    for line, row in zip(data, body["rows"]):
        assert line[:7] == [
            row["date"], str(row["trade_id"]), row["counterparty"], row["product"], row["kind"],
            row["status"], row["currency"],
        ]
        assert line[7] == "%.2f" % row["amount"] and line[8] == "%.2f" % row["amount_mxn"]
        assert line[9] == "" and line[10] == ""  # nada confirmado: null -> vacío


def test_csv_of_a_confirmed_row_carries_the_confirmed_amount_and_the_difference(app, client):
    _roll_with_fixings(client)
    computed = _row(_get(client, snapshot="D1"), 1, FIRST_COUPON)["amount"]
    confirm_raw(app, 1, FIRST_COUPON, computed - 10.0)
    r = client.get(URL % "D1" + "&format=csv")
    lines = list(csv.reader(io.StringIO(r.get_data(as_text=True))))
    line = next(x for x in lines[1:] if x[0] == FIRST_COUPON.isoformat() and x[1] == "1")
    assert line[5] == "confirmed"
    assert line[9] == "%.2f" % (computed - 10.0) and line[10] == "-10.00"
    assert r.headers["Content-Disposition"] == 'attachment; filename="flujos-D1.csv"'


# --------------------------------------------------- liquidados y confirmados (R2)


def _row(body, trade_id, day, kind="coupon"):
    found = [
        r for r in body["rows"]
        if r["trade_id"] == trade_id and r["date"] == day.isoformat() and r["kind"] == kind
    ]
    assert len(found) == 1, found
    return found[0]


def test_coupons_before_the_as_of_come_out_settled_without_df_nor_pv(client):
    _roll_with_fixings(client)
    body = _get(client, snapshot="D1")
    assert body["warnings"] == [] and body["errors"] == []
    for trade_id in (1, 2):
        row = _row(body, trade_id, FIRST_COUPON)
        assert row["status"] == "settled" and row["currency"] == "MXN"
        assert row["df"] is None and row["pv"] is None
        assert row["confirmed_amount"] is None and row["difference"] is None
    settled = [r for r in body["rows"] if r["status"] != "projected"]
    assert {(r["trade_id"], r["date"]) for r in settled} == {(1, "2026-12-08"), (2, "2026-12-08")}
    assert all(r["date"] <= body["as_of"] for r in settled)
    assert all(r["date"] > body["as_of"] for r in body["rows"] if r["status"] == "projected")
    # payer y receiver del mismo tipo de cupón: signos opuestos y proporcionales al nocional
    payer, receiver = _row(body, 1, FIRST_COUPON), _row(body, 2, FIRST_COUPON)
    assert payer["amount"] * receiver["amount"] < 0


def test_a_confirmed_coupon_shows_the_bank_amount_and_the_difference(app, client):
    _roll_with_fixings(client)
    before = _get(client, snapshot="D1")
    computed = _row(before, 1, FIRST_COUPON)["amount"]
    confirm_raw(app, 1, FIRST_COUPON, computed + 123.0)
    after = _get(client, snapshot="D1")
    row = _row(after, 1, FIRST_COUPON)
    assert row["status"] == "confirmed"
    assert row["confirmed_amount"] == pytest.approx(computed + 123.0)
    assert row["difference"] == pytest.approx(row["confirmed_amount"] - row["amount"], abs=1e-9)
    assert row["difference"] == pytest.approx(123.0, abs=1e-6)
    # el monto calculado no cambia, ni el de la operación vecina
    assert row["amount"] == computed
    assert _row(after, 2, FIRST_COUPON)["status"] == "settled"


def test_the_confirmation_transfer_is_not_a_row_and_changes_no_figure(app, client):
    _roll_with_fixings(client)
    before = _get(client, snapshot="D1")
    confirm_raw(app, 1, FIRST_COUPON, 123.0)
    after = _get(client, snapshot="D1")
    assert len(after["rows"]) == len(before["rows"])
    assert "transfer" not in {r["kind"] for r in after["rows"]}
    assert after["totals"]["amount_mxn"] == pytest.approx(before["totals"]["amount_mxn"], abs=1e-9)
    assert after["totals"]["by_date"] == before["totals"]["by_date"]


def test_a_confirmation_on_a_date_without_a_flow_adds_no_row(app, client):
    _roll_with_fixings(client)
    before = _get(client, snapshot="D1")
    confirm_raw(app, 1, date(2026, 11, 20), 50.0)  # no hay cupón ese día
    after = _get(client, snapshot="D1")
    assert after["rows"] == before["rows"]


def test_a_real_transfer_stays_settled_and_is_not_marked_as_confirmed(client):
    _roll_with_fixings(client)
    r = client.post(
        "/api/trades/1/events",
        json={"type": "termination", "event_date": "2026-12-10", "data": {"amount": 500.0}},
    )
    assert r.status_code == 201, r.get_json()
    body = _get(client, snapshot="D1")
    transfer = _row(body, 1, date(2026, 12, 10), "transfer")
    assert transfer["status"] == "settled" and transfer["confirmed_amount"] is None
    assert transfer["amount"] == 500.0 and transfer["df"] is None
    assert not [r for r in body["rows"] if r["trade_id"] == 1 and r["status"] == "projected"]


def test_missing_fixings_give_one_merged_warning_per_index(client):
    hedge_fixture.roll(client, "MX-DEMO", "D1", 35)
    body = _get(client, snapshot="D1")
    assert [(w["code"], w["index"]) for w in body["warnings"]] == [
        ("missing_fixing", "TIIE-F"), ("missing_fixing", "SOFR"),
    ]
    assert all(len(w["dates"]) == len(set(w["dates"])) for w in body["warnings"])


# ------------------------------------------------------------------------- errores


def test_bad_query_parameters_are_400_on_their_own_field(client):
    cases = [
        ("/api/cashflows", "snapshot"),
        ("/api/cashflows?snapshot=", "snapshot"),
        (URL % "MX-DEMO" + "&from=ayer", "from"),
        (URL % "MX-DEMO" + "&to=2026-13-01", "to"),
        (URL % "MX-DEMO" + "&from=2027-01-02&to=2027-01-01", "to"),
        (URL % "MX-DEMO" + "&currency=EUR", "currency"),
        (URL % "MX-DEMO" + "&format=xlsx", "format"),
    ]
    for url, field in cases:
        r = client.get(url)
        assert r.status_code == 400, (url, r.get_json())
        assert r.get_json()["field"] == field, url


def test_unknown_snapshot_is_404_on_the_snapshot_field(client):
    r = client.get(URL % "NOPE")
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"
    r = client.get(URL % "NOPE" + "&format=csv")
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"


def test_a_corrupt_trade_goes_to_errors_and_the_rest_still_answers_200(app, client):
    clean = _get(client)
    bad = insert_raw_trade(app, "irs", "esto no es json")
    body = _get(client)
    assert [e["trade_id"] for e in body["errors"]] == [bad]
    assert body["errors"][0]["message"].startswith("No se pudo derivar sus flujos: ")
    assert body["rows"] == clean["rows"]
    assert body["totals"] == clean["totals"]
    csv_response = client.get(URL % "MX-DEMO" + "&format=csv")
    assert csv_response.status_code == 200
    assert len(list(csv.reader(io.StringIO(csv_response.get_data(as_text=True))))) == len(clean["rows"]) + 1


def test_a_corrupt_trade_of_another_counterparty_is_not_reported_under_a_filter(app, client):
    insert_raw_trade(app, "irs", "esto no es json")  # contraparte 'Raw'
    body = _get(client, "&counterparty=Banco Alfa (sintético)")
    assert body["errors"] == [] and body["rows"]
    assert _get(client, "&counterparty=Raw")["errors"] != []
