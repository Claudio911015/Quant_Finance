"""Fijaciones diarias: alta, CSV atómico, listado y carga (T5)."""
import sqlite3
from datetime import date

import pytest

from desk.api import fixings
from desk.api.db import connect

HEADER = "index,date,value"


def _post(client, index="SOFR", day="2026-11-10", value=0.04):
    return client.post("/api/fixings", json={"index": index, "date": day, "value": value})


def _csv(client, text):
    return client.post("/api/fixings/csv", json={"csv": text})


def _count(app):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        return conn.execute("SELECT COUNT(*) FROM fixings").fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------- alta

def test_add_fixing_returns_201_with_fixing(client, app):
    r = _post(client, "TIIE-F", "2026-11-10", 0.0701)
    assert r.status_code == 201
    assert r.get_json() == {
        "fixing": {"index": "TIIE-F", "date": "2026-11-10", "value": 0.0701},
        "created": True,
    }
    assert _count(app) == 1


def test_add_exact_duplicate_is_200_not_created_and_no_new_row(client, app):
    assert _post(client).status_code == 201
    r = _post(client)
    assert r.status_code == 200
    assert r.get_json() == {
        "fixing": {"index": "SOFR", "date": "2026-11-10", "value": 0.04},
        "created": False,
    }
    assert _count(app) == 1


def test_same_key_other_value_is_409_on_value_and_keeps_original(client, app):
    _post(client, value=0.04)
    r = _post(client, value=0.05)
    assert r.status_code == 409
    assert r.get_json()["field"] == "value"
    assert client.get("/api/fixings").get_json()["fixings"][0]["value"] == 0.04
    assert _count(app) == 1


def test_same_date_other_index_is_a_different_key(client):
    assert _post(client, "SOFR").status_code == 201
    assert _post(client, "TIIE-F").status_code == 201


@pytest.mark.parametrize("value", ["NaN", 1e309, 11, -1.5, True, None, "0.04", float("nan")])
def test_rate_value_out_of_range_or_not_a_number_is_400(client, value):
    r = _post(client, "SOFR", value=value)
    assert r.status_code == 400
    assert r.get_json()["field"] == "value"


def test_rate_bounds_are_inclusive(client):
    assert _post(client, "SOFR", "2026-11-10", -1).status_code == 201
    assert _post(client, "SOFR", "2026-11-11", 10).status_code == 201


@pytest.mark.parametrize("value", [0, -19.5, 1e6 + 1])
def test_usdmxn_must_be_positive_and_bounded(client, value):
    r = _post(client, "USDMXN", value=value)
    assert r.status_code == 400
    assert r.get_json()["field"] == "value"


def test_usdmxn_accepts_a_fix_above_the_rate_cap(client):
    r = _post(client, "USDMXN", value=19.4321)
    assert r.status_code == 201
    assert r.get_json()["fixing"]["value"] == 19.4321


def test_unknown_index_is_400_on_index(client):
    r = _post(client, "LIBOR")
    assert r.status_code == 400
    assert r.get_json()["field"] == "index"


@pytest.mark.parametrize("body, field", [
    ({"date": "2026-11-10", "value": 0.04}, "index"),
    ({"index": "SOFR", "value": 0.04}, "date"),
    ({"index": "SOFR", "date": "2026-11-10"}, "value"),
    ({"index": "SOFR", "date": "2026-02-30", "value": 0.04}, "date"),
    ({"index": "SOFR", "date": "10/11/2026", "value": 0.04}, "date"),
])
def test_missing_or_invalid_fields_name_the_key(client, body, field):
    r = client.post("/api/fixings", json=body)
    assert r.status_code == 400
    assert r.get_json()["field"] == field


# ---------------------------------------------------------------- CSV

def test_csv_three_valid_rows_then_reload_is_unchanged(client, app):
    text = "\n".join([HEADER, "TIIE-F,2026-11-10,0.0701", "SOFR,2026-11-10,0.0412", "USDMXN,2026-11-10,19.4"])
    r = _csv(client, text)
    assert r.status_code == 200
    assert r.get_json() == {"inserted": 3, "unchanged": 0}
    r = _csv(client, text)
    assert r.status_code == 200
    assert r.get_json() == {"inserted": 0, "unchanged": 3}
    assert _count(app) == 3


def test_csv_bad_row_on_line_3_names_the_row_and_saves_nothing(client, app):
    text = "\n".join([HEADER, "TIIE-F,2026-11-10,0.0701", "SOFR,2026-11-10,abc", "USDMXN,2026-11-10,19.4"])
    r = _csv(client, text)
    assert r.status_code == 400
    body = r.get_json()
    assert body["field"] == "csv"
    assert "Fila 3" in body["error"]
    assert _count(app) == 0


@pytest.mark.parametrize("row, fila", [
    ("LIBOR,2026-11-10,0.04", "Fila 2"),
    ("SOFR,2026-13-10,0.04", "Fila 2"),
    ("SOFR,2026-11-10,11", "Fila 2"),
    ("SOFR,2026-11-10,nan", "Fila 2"),
    ("SOFR,2026-11-10,", "Fila 2"),
    ("SOFR,2026-11-10", "Fila 2"),
    ("SOFR,2026-11-10,0.04,extra", "Fila 2"),
    ("", "Fila 2"),  # línea vacía en medio del archivo
])
def test_csv_malformed_rows_are_400_csv(client, app, row, fila):
    text = "\n".join([HEADER, row, "SOFR,2026-11-11,0.04"])
    r = _csv(client, text)
    assert r.status_code == 400
    assert r.get_json()["field"] == "csv"
    assert fila in r.get_json()["error"]
    assert _count(app) == 0


@pytest.mark.parametrize("text", ["", "\n", "Index,date,value\nSOFR,2026-11-10,0.04", "index,date\nSOFR,2026-11-10,0.04",
                                  "SOFR,2026-11-10,0.04"])
def test_csv_header_must_match_exactly(client, app, text):
    r = _csv(client, text)
    assert r.status_code == 400
    assert r.get_json()["field"] == "csv"
    assert "Fila 1" in r.get_json()["error"]
    assert _count(app) == 0


def test_csv_header_only_is_a_valid_empty_import(client):
    r = _csv(client, HEADER + "\n")
    assert r.status_code == 200
    assert r.get_json() == {"inserted": 0, "unchanged": 0}


def test_csv_trailing_blank_lines_and_crlf_are_ignored(client, app):
    text = HEADER + "\r\nSOFR,2026-11-10,0.04\r\nSOFR,2026-11-11,0.041\r\n\r\n   \r\n"
    r = _csv(client, text)
    assert r.status_code == 200
    assert r.get_json() == {"inserted": 2, "unchanged": 0}
    assert _count(app) == 2


def test_csv_conflict_with_stored_value_is_409_and_saves_nothing(client, app):
    _post(client, "SOFR", "2026-11-10", 0.04)
    text = "\n".join([HEADER, "TIIE-F,2026-11-10,0.07", "SOFR,2026-11-10,0.05"])
    r = _csv(client, text)
    assert r.status_code == 409
    body = r.get_json()
    assert body["field"] == "csv"
    assert "Fila 3" in body["error"]
    assert _count(app) == 1


def test_csv_malformed_row_wins_over_earlier_conflict(client, app):
    _post(client, "SOFR", "2026-11-10", 0.04)
    text = "\n".join([HEADER, "SOFR,2026-11-10,0.05", "SOFR,2026-11-11,xx"])
    r = _csv(client, text)
    assert r.status_code == 400
    assert "Fila 3" in r.get_json()["error"]
    assert _count(app) == 1


def test_csv_repeated_line_counts_once_inserted_once_unchanged(client, app):
    text = "\n".join([HEADER, "SOFR,2026-11-10,0.04", "SOFR,2026-11-10,0.04"])
    r = _csv(client, text)
    assert r.status_code == 200
    assert r.get_json() == {"inserted": 1, "unchanged": 1}
    assert _count(app) == 1


def test_csv_same_key_twice_with_other_value_is_409_and_saves_nothing(client, app):
    text = "\n".join([HEADER, "SOFR,2026-11-10,0.04", "SOFR,2026-11-10,0.05"])
    r = _csv(client, text)
    assert r.status_code == 409
    assert r.get_json()["field"] == "csv"
    assert "Fila 3" in r.get_json()["error"]
    assert _count(app) == 0


def test_csv_mixed_new_and_existing(client, app):
    _post(client, "SOFR", "2026-11-10", 0.04)
    text = "\n".join([HEADER, "SOFR,2026-11-10,0.04", "SOFR,2026-11-11,0.041"])
    r = _csv(client, text)
    assert r.get_json() == {"inserted": 1, "unchanged": 1}
    assert _count(app) == 2


# ---------------------------------------------------------------- listado

@pytest.fixture
def loaded(client):
    text = "\n".join([
        HEADER,
        "USDMXN,2026-11-10,19.4",
        "TIIE-F,2026-11-12,0.0703",
        "TIIE-F,2026-11-10,0.0701",
        "TIIE-F,2026-11-11,0.0702",
        "SOFR,2026-11-10,0.0412",
    ])
    assert _csv(client, text).status_code == 200
    return client


def _list(client, qs=""):
    r = client.get("/api/fixings" + qs)
    assert r.status_code == 200
    return r.get_json()["fixings"]


def test_list_all_is_ordered_by_index_then_date(loaded):
    rows = _list(loaded)
    assert [(r["index"], r["date"]) for r in rows] == [
        ("SOFR", "2026-11-10"),
        ("TIIE-F", "2026-11-10"),
        ("TIIE-F", "2026-11-11"),
        ("TIIE-F", "2026-11-12"),
        ("USDMXN", "2026-11-10"),
    ]
    assert rows[1] == {"index": "TIIE-F", "date": "2026-11-10", "value": 0.0701}


def test_list_filters_by_index(loaded):
    rows = _list(loaded, "?index=TIIE-F")
    assert [r["date"] for r in rows] == ["2026-11-10", "2026-11-11", "2026-11-12"]
    assert {r["index"] for r in rows} == {"TIIE-F"}


def test_list_date_range_is_inclusive(loaded):
    rows = _list(loaded, "?from=2026-11-11&to=2026-11-12")
    assert [(r["index"], r["date"]) for r in rows] == [("TIIE-F", "2026-11-11"), ("TIIE-F", "2026-11-12")]


def test_list_index_and_range_combined(loaded):
    rows = _list(loaded, "?index=TIIE-F&from=2026-11-11")
    assert [r["date"] for r in rows] == ["2026-11-11", "2026-11-12"]
    assert _list(loaded, "?index=SOFR&from=2026-11-11") == []


def test_list_empty_range_is_empty_not_error(loaded):
    assert _list(loaded, "?from=2026-12-01&to=2026-11-01") == []


@pytest.mark.parametrize("qs, field", [
    ("?index=LIBOR", "index"),
    ("?index=", "index"),
    ("?index=sofr", "index"),
    ("?from=nope", "from"),
    ("?to=2026-02-30", "to"),
])
def test_list_bad_filters_are_400(client, qs, field):
    r = client.get("/api/fixings" + qs)
    assert r.status_code == 400
    assert r.get_json()["field"] == field


def test_list_empty_table(client):
    assert _list(client) == []


# ---------------------------------------------------------------- load_all

def test_load_all_has_the_three_indices_even_when_empty(app):
    with app.app_context():
        conn = connect(app.config["DESK_DB"])
        try:
            assert fixings.load_all(conn) == {"TIIE-F": {}, "SOFR": {}, "USDMXN": {}}
        finally:
            conn.close()


def test_load_all_maps_dates_to_values(loaded, app):
    conn = connect(app.config["DESK_DB"])
    try:
        out = fixings.load_all(conn)
    finally:
        conn.close()
    assert set(out) == {"TIIE-F", "SOFR", "USDMXN"}
    assert out["TIIE-F"] == {
        date(2026, 11, 10): 0.0701,
        date(2026, 11, 11): 0.0702,
        date(2026, 11, 12): 0.0703,
    }
    assert out["SOFR"] == {date(2026, 11, 10): 0.0412}
    assert out["USDMXN"] == {date(2026, 11, 10): 19.4}
