"""Corte 6, T5: historia de factores (semilla sintética, CSV, derivación y lectura)."""
import math
import sqlite3
import statistics
from datetime import date, timedelta

from desk.api import db
from desk.api.app import create_app
from desk.api.risk import factor_history
from desk.api.seed_market import demo_data
from desk.api.tests.mdf_fixture import make_fred_csv, make_mdf_db

VOLS = dict(zip(*[demo_data()["factors"][k] for k in ("names", "daily_vols")]))


def _rows(path, source=None):
    conn = sqlite3.connect(str(path))
    try:
        sql = "SELECT factor, source, date, value FROM factor_history"
        if source:
            return conn.execute(sql + " WHERE source = ? ORDER BY factor, date", (source,)).fetchall()
        return conn.execute(sql + " ORDER BY factor, source, date").fetchall()
    finally:
        conn.close()


def _csv(client, text):
    return client.post("/api/factor-history/csv", json={"csv": text})


def _weekdays(start, n):
    out, day = [], start
    while len(out) < n:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


def _fixings(client, index, pairs):
    lines = ["index,date,value"] + ["%s,%s,%r" % (index, d, v) for d, v in pairs]
    r = client.post("/api/fixings/csv", json={"csv": "\n".join(lines)})
    assert r.status_code == 200, r.get_json()


# ------------------------------------------------------------------------------ semilla

def test_seed_creates_500_rows_per_factor_once(tmp_path):
    path = tmp_path / "t.db"
    create_app(db_path=path)
    first = _rows(path, "synthetic")
    assert {f: sum(1 for r in first if r[0] == f) for f in ("TIIE-F", "SOFR", "USDMXN")} == {
        "TIIE-F": 500, "SOFR": 500, "USDMXN": 500}
    create_app(db_path=path)  # segundo arranque sobre la misma base: no resiembra
    assert _rows(path, "synthetic") == first


def test_seed_dates_are_the_500_weekdays_before_the_demo_as_of(tmp_path):
    path = tmp_path / "t.db"
    create_app(db_path=path)
    days = sorted({r[2] for r in _rows(path, "synthetic")})
    assert len(days) == 500
    assert days[-1] == "2026-11-09"  # lunes anterior al as_of (martes 2026-11-10)
    assert all(date.fromisoformat(d).weekday() < 5 for d in days)


def test_seed_is_reproducible_across_databases(tmp_path):
    create_app(db_path=tmp_path / "a.db")
    create_app(db_path=tmp_path / "b.db")
    a = _rows(tmp_path / "a.db", "synthetic")
    assert a == _rows(tmp_path / "b.db", "synthetic")
    assert len({r[3] for r in a}) > 1400  # no es una serie constante ni repetida


def test_seed_sample_std_is_within_15_percent_of_demo_vols(tmp_path):
    path = tmp_path / "t.db"
    create_app(db_path=path)
    for factor, vol in VOLS.items():
        xs = [r[3] for r in _rows(path, "synthetic") if r[0] == factor]
        assert abs(statistics.stdev(xs) / vol - 1) < 0.15, factor


def test_seed_correlations_follow_the_demo_matrix(tmp_path):
    path = tmp_path / "t.db"
    create_app(db_path=path)
    series = {f: [r[3] for r in _rows(path, "synthetic") if r[0] == f] for f in VOLS}

    def corr(a, b):
        ma, mb = statistics.mean(series[a]), statistics.mean(series[b])
        cov = sum((x - ma) * (y - mb) for x, y in zip(series[a], series[b])) / (len(series[a]) - 1)
        return cov / (statistics.stdev(series[a]) * statistics.stdev(series[b]))

    assert abs(corr("TIIE-F", "SOFR") - 0.35) < 0.12
    assert abs(corr("TIIE-F", "USDMXN") - 0.30) < 0.12


def test_seed_without_seed_flag_or_demo_inserts_nothing(tmp_path):
    create_app(db_path=tmp_path / "t.db", seed=False)
    assert _rows(tmp_path / "t.db") == []
    conn = db.connect(tmp_path / "t.db")
    try:
        assert factor_history.seed_synthetic(conn) == 0  # sin MX-DEMO no hay semilla
    finally:
        conn.close()


# ------------------------------------------------------------------------------ CSV

def test_csv_inserts_then_reload_is_unchanged(client):
    text = "factor,date,value\nTIIE-F,2026-11-09,1.5\nUSDMXN,2026-11-09,-0.004"
    r = _csv(client, text)
    assert r.status_code == 200 and r.get_json() == {"inserted": 2, "unchanged": 0}
    r = _csv(client, text)
    assert r.get_json() == {"inserted": 0, "unchanged": 2}
    assert len(_rows(client.application.config["DESK_DB"], "csv")) == 2


def test_csv_accepts_bom_and_crlf(client):
    r = _csv(client, "﻿factor,date,value\r\nSOFR,2026-11-09,-2.5\r\n\r\n")
    assert r.status_code == 200 and r.get_json() == {"inserted": 1, "unchanged": 0}


def test_csv_bad_header_is_400_csv(client):
    for text in ("index,date,value\nSOFR,2026-11-09,1", "", "factor,date\nSOFR,2026-11-09"):
        r = _csv(client, text)
        assert r.status_code == 400 and r.get_json()["field"] == "csv", text
        assert r.get_json()["error"].startswith("Fila 1")


def test_csv_row_errors_name_the_row_and_insert_nothing(client):
    path = client.application.config["DESK_DB"]
    good = "TIIE-F,2026-11-09,1.5"
    bad = {
        "XYZ,2026-11-09,1": "Fila 3",  # factor desconocido
        "SOFR,2026-13-09,1": "Fila 3",  # fecha inválida
        "SOFR,2026-11-9,1": "Fila 3",  # fecha no ISO
        "SOFR,2026-11-09,abc": "Fila 3",  # no numérico
        "SOFR,2026-11-09,nan": "Fila 3",
        "SOFR,2026-11-09,inf": "Fila 3",
        "SOFR,2026-11-09,1000.5": "Fila 3",  # |valor| > 1000 pb
        "SOFR,2026-11-09,-1001": "Fila 3",
        "USDMXN,2026-11-09,1.5": "Fila 3",  # |valor| > 1 en rendimiento
        "SOFR,2026-11-09": "Fila 3",  # faltan columnas
    }
    for row, where in bad.items():
        r = _csv(client, "factor,date,value\n%s\n%s" % (good, row))
        assert r.status_code == 400, row
        body = r.get_json()
        assert body["field"] == "csv" and body["error"].startswith(where), (row, body)
    assert _rows(path, "csv") == []  # todo o nada


def test_csv_bounds_are_inclusive(client):
    r = _csv(client, "factor,date,value\nSOFR,2026-11-09,1000\nSOFR,2026-11-06,-1000\nUSDMXN,2026-11-09,1")
    assert r.status_code == 200 and r.get_json()["inserted"] == 3


def test_csv_same_day_other_value_is_409_and_inserts_nothing(client):
    path = client.application.config["DESK_DB"]
    assert _csv(client, "factor,date,value\nTIIE-F,2026-11-09,1.5").status_code == 200
    r = _csv(client, "factor,date,value\nSOFR,2026-11-09,3\nTIIE-F,2026-11-09,1.6")
    assert r.status_code == 409 and r.get_json()["field"] == "csv"
    assert "Fila 3" in r.get_json()["error"]
    assert len(_rows(path, "csv")) == 1  # el SOFR del mismo archivo tampoco se guardó


def test_csv_same_key_twice_in_file(client):
    same = _csv(client, "factor,date,value\nSOFR,2026-11-09,3\nSOFR,2026-11-09,3")
    assert same.get_json() == {"inserted": 1, "unchanged": 1}
    other = _csv(client, "factor,date,value\nSOFR,2026-11-06,3\nSOFR,2026-11-06,4")
    assert other.status_code == 409


def test_csv_must_be_text(client):
    for body in ({"csv": 5}, {}):
        r = client.post("/api/factor-history/csv", json=body)
        assert r.status_code == 400 and r.get_json()["field"] == "csv"


def test_csv_does_not_touch_other_sources(client):
    path = client.application.config["DESK_DB"]
    before = _rows(path, "synthetic")
    # el mismo (factor, fecha) que una fila sintética no choca: la clave incluye la fuente
    day = before[0][2]
    assert _csv(client, "factor,date,value\n%s,%s,0.5" % (before[0][0], day)).status_code == 200
    assert _rows(path, "synthetic") == before


# ------------------------------------------------------------------------------ derive

def test_derive_rejects_unknown_source(client):
    for body in ({"source": "csv"}, {"source": "x"}, {}):
        r = client.post("/api/factor-history/derive", json=body)
        assert r.status_code == 400 and r.get_json()["field"] == "source", body


def test_derive_fixings_converts_rates_to_bp_and_skips_gaps(client):
    _fixings(client, "TIIE-F", [("2026-11-02", 0.07), ("2026-11-03", 0.071), ("2026-11-11", 0.072)])
    _fixings(client, "USDMXN", [("2026-11-02", 18.0), ("2026-11-03", 18.18)])
    r = client.post("/api/factor-history/derive", json={"source": "fixings"})
    assert r.status_code == 200
    assert r.get_json() == {"source": "fixings", "inserted": 2, "unchanged": 0, "skipped_gaps": 1}
    got = {(x[0], x[2]): x[3] for x in _rows(client.application.config["DESK_DB"], "fixings")}
    assert set(got) == {("TIIE-F", "2026-11-03"), ("USDMXN", "2026-11-03")}  # fechada en el segundo dato
    assert math.isclose(got[("TIIE-F", "2026-11-03")], 10.0, abs_tol=1e-9)
    assert math.isclose(got[("USDMXN", "2026-11-03")], math.log(18.18 / 18.0), rel_tol=1e-12)
    again = client.post("/api/factor-history/derive", json={"source": "fixings"}).get_json()
    assert again == {"source": "fixings", "inserted": 0, "unchanged": 2, "skipped_gaps": 1}


def test_derive_fixings_weekend_is_not_a_gap(client):
    _fixings(client, "SOFR", [("2026-11-06", 0.04), ("2026-11-09", 0.0395)])  # viernes -> lunes
    r = client.post("/api/factor-history/derive", json={"source": "fixings"}).get_json()
    assert r["inserted"] == 1 and r["skipped_gaps"] == 0
    (row,) = _rows(client.application.config["DESK_DB"], "fixings")
    assert math.isclose(row[3], -5.0, abs_tol=1e-9)


def test_derive_fixings_without_fixings_is_a_noop(client):
    r = client.post("/api/factor-history/derive", json={"source": "fixings"})
    assert r.status_code == 200
    assert r.get_json() == {"source": "fixings", "inserted": 0, "unchanged": 0, "skipped_gaps": 0}


def test_derive_fixings_conflict_is_409_and_inserts_nothing(client):
    path = client.application.config["DESK_DB"]
    _fixings(client, "TIIE-F", [("2026-11-02", 0.07), ("2026-11-04", 0.072)])
    assert client.post("/api/factor-history/derive", json={"source": "fixings"}).get_json()["inserted"] == 1
    _fixings(client, "TIIE-F", [("2026-11-03", 0.071)])  # parte el cambio del 4 en dos: 20 pb -> 10 + 10
    r = client.post("/api/factor-history/derive", json={"source": "fixings"})
    assert r.status_code == 409 and r.get_json()["field"] == "source"
    assert [x[2] for x in _rows(path, "fixings")] == ["2026-11-04"]


def test_derive_fixings_out_of_range_change_is_409(client):
    _fixings(client, "SOFR", [("2026-11-02", 0.01), ("2026-11-03", 0.5)])  # 49 000 pb
    r = client.post("/api/factor-history/derive", json={"source": "fixings"})
    assert r.status_code == 409 and r.get_json()["field"] == "source"
    assert _rows(client.application.config["DESK_DB"], "fixings") == []


def _live_sources(tmp_path, app, n=70):
    days = _weekdays(date(2026, 8, 3), n)
    sofr = [(d.isoformat(), 4.0 + 0.01 * i) for i, d in enumerate(days)]
    mdf = make_mdf_db(tmp_path / "sofr.db", curve_date=days[-1].isoformat(), history_5y=sofr)
    fx = make_fred_csv(tmp_path / "fred.csv", [(d.isoformat(), 18.0 + 0.01 * i) for i, d in enumerate(days)])
    app.config["MDF_DB"] = str(mdf)
    app.config["FRED_DEXMXUS_URL"] = fx.as_uri()
    return days


def test_derive_live_inserts_sofr_and_usdmxn(client, tmp_path):
    days = _live_sources(tmp_path, client.application)
    r = client.post("/api/factor-history/derive", json={"source": "live"})
    assert r.status_code == 200, r.get_json()
    # 70 observaciones -> 69 cambios por factor (los fines de semana son 3 días, no hueco)
    assert r.get_json() == {"source": "live", "inserted": 138, "unchanged": 0, "skipped_gaps": 0}
    rows = _rows(client.application.config["DESK_DB"], "live")
    assert {x[0] for x in rows} == {"SOFR", "USDMXN"}
    sofr = {x[2]: x[3] for x in rows if x[0] == "SOFR"}
    fx = {x[2]: x[3] for x in rows if x[0] == "USDMXN"}
    d1 = days[1].isoformat()
    assert math.isclose(sofr[d1], 1.0, abs_tol=1e-6)  # +1 pb diario
    assert math.isclose(fx[d1], math.log(18.01 / 18.0), rel_tol=1e-9)
    again = client.post("/api/factor-history/derive", json={"source": "live"}).get_json()
    assert again["inserted"] == 0 and again["unchanged"] == 138


def test_derive_live_read_errors(client, tmp_path):
    app = client.application
    r = client.post("/api/factor-history/derive", json={"source": "live"})  # MarketDataFeed no existe
    assert r.status_code == 502 and r.get_json()["field"] == "source"
    _live_sources(tmp_path, app)
    app.config["FRED_DEXMXUS_URL"] = (tmp_path / "no-hay.csv").as_uri()
    r = client.post("/api/factor-history/derive", json={"source": "live"})
    assert r.status_code == 502 and "FRED" in r.get_json()["error"]
    assert _rows(app.config["DESK_DB"], "live") == []


def test_derive_live_short_history_stays_409(client, tmp_path):
    app = client.application
    app.config["MDF_DB"] = str(make_mdf_db(tmp_path / "sofr.db"))  # solo la curva del día: sin historia
    r = client.post("/api/factor-history/derive", json={"source": "live"})
    assert r.status_code == 409 and r.get_json()["error"].startswith("Historia insuficiente")


# ------------------------------------------------------------------------------ resumen y ventana

def test_summary_has_the_contract_shape(client):
    assert _csv(client, "factor,date,value\nTIIE-F,2026-11-09,1.5\nTIIE-F,2026-11-06,2").status_code == 200
    body = client.get("/api/factor-history").get_json()
    assert [f["factor"] for f in body["factors"]] == ["TIIE-F", "SOFR", "USDMXN"]
    assert [f["unit"] for f in body["factors"]] == ["bp", "bp", "ret"]
    tiie = body["factors"][0]["sources"]
    assert [s["source"] for s in tiie] == ["synthetic", "csv"]  # orden de SOURCES
    assert tiie[0] == {"source": "synthetic", "label": factor_history.SOURCE_LABEL["synthetic"],
                       "count": 500, "first": "2024-12-10", "last": "2026-11-09"}
    assert tiie[1] == {"source": "csv", "label": "CSV cargado", "count": 2,
                       "first": "2026-11-06", "last": "2026-11-09"}
    assert [s["source"] for s in body["factors"][1]["sources"]] == ["synthetic"]


def test_summary_without_seed_lists_the_three_factors_empty(tmp_path):
    client = create_app(db_path=tmp_path / "t.db", seed=False).test_client()
    body = client.get("/api/factor-history").get_json()
    assert [(f["factor"], f["sources"]) for f in body["factors"]] == [
        ("TIIE-F", []), ("SOFR", []), ("USDMXN", [])]


def test_window_synthetic_takes_last_n_complete_dates(client):
    conn = db.connect(client.application.config["DESK_DB"])
    try:
        dates, series, by_source = factor_history.window(conn, "synthetic", "2026-11-10", 60)
        assert len(dates) == 60 and dates == sorted(dates) and dates[-1] == "2026-11-09"
        assert set(series) == {"TIIE-F", "SOFR", "USDMXN"} and all(len(v) == 60 for v in series.values())
        assert by_source == {"synthetic": 180}
        early, _, _ = factor_history.window(conn, "synthetic", "2025-01-01", 60)
        assert early[-1] <= "2025-01-01"
        all_dates, _, _ = factor_history.window(conn, "synthetic", "2026-11-10", 10000)
        assert len(all_dates) == 500  # menos de las pedidas: devuelve las que hay
    finally:
        conn.close()


def test_window_observed_priority_and_complete_dates_only(client):
    conn = db.connect(client.application.config["DESK_DB"])
    try:
        rows = [
            ("TIIE-F", "csv", "2027-01-05", 1.0), ("TIIE-F", "fixings", "2027-01-05", 9.0),
            ("SOFR", "fixings", "2027-01-05", 2.0), ("SOFR", "live", "2027-01-05", 8.0),
            ("USDMXN", "live", "2027-01-05", 0.001),
            ("TIIE-F", "csv", "2027-01-06", 1.0),  # incompleta: faltan SOFR y USDMXN
            ("SOFR", "synthetic", "2027-01-06", 5.0),  # el sintético no cuenta en observed
        ]
        conn.executemany(
            "INSERT INTO factor_history (factor, source, date, value, created_at) VALUES (?, ?, ?, ?, 'x')", rows)
        dates, series, by_source = factor_history.window(conn, "observed", "2027-01-10", 5)
        assert dates == ["2027-01-05"]
        assert series == {"TIIE-F": [1.0], "SOFR": [8.0], "USDMXN": [0.001]}  # csv > live > fixings
        assert by_source == {"csv": 1, "live": 2}
    finally:
        conn.close()
