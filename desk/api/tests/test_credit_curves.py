"""Corte 9, T6: curvas de crédito sintéticas por CDS (tabla de solo inserción, siembra, GET y PUT)."""
import json
import sqlite3
from urllib.parse import quote as urlquote

import pytest

from desk.api import db
from desk.api.app import create_app
from desk.api.risk import credit_curves

SNAP = "MX-DEMO"
ALFA, BETA, GAMMA = "Banco Alfa (sintético)", "Banco Beta (sintético)", "Banco Gamma (sintético)"
TENORS = [1, 2, 3, 5, 7, 10]
SPREADS_PB = {
    ALFA: [60, 70, 80, 95, 105, 120],
    BETA: [150, 180, 210, 250, 275, 300],
    GAMMA: [95, 97, 98, 100, 100, 101],
    "propia": [70, 80, 90, 105, 115, 125],
}
CURVE_KEYS = {
    "entity", "label", "kind", "id", "as_of", "recovery", "quotes", "hazards", "grid", "history", "error",
}


def _get(client, snapshot=SNAP):
    return client.get("/api/credit/curves?snapshot=%s" % snapshot)


def _curves(client):
    resp = _get(client)
    assert resp.status_code == 200, resp.get_json()
    return {c["entity"]: c for c in resp.get_json()["curves"]}


def _put(client, entity, body):
    return client.put("/api/credit/curves/%s" % urlquote(entity, safe=""), json=body)


def _rows(app, sql="SELECT * FROM credit_curves ORDER BY id"):
    conn = sqlite3.connect(app.config["DESK_DB"])
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql)]
    finally:
        conn.close()


def _valid_body(**over):
    body = {"recovery": 0.4, "quotes": [{"tenor_years": 1, "spread": 0.006}, {"tenor_years": 3, "spread": 0.009}]}
    body.update(over)
    return body


# ---------------------------------------------------------------- siembra

def test_seed_inserts_four_synthetic_entities_once(app):
    rows = _rows(app)
    assert [r["entity"] for r in rows] == [ALFA, BETA, GAMMA, "propia"]
    assert [r["id"] for r in rows] == [1, 2, 3, 4]
    for r in rows:
        assert r["source"] == "synthetic"
        assert r["recovery"] == 0.4
        assert r["as_of"] == "2026-11-10"  # el del snapshot MX-DEMO, no la fecha UTC de hoy
        quotes = json.loads(r["quotes"])
        assert [q["tenor_years"] for q in quotes] == TENORS
        assert [round(q["spread"] * 1e4) for q in quotes] == SPREADS_PB[r["entity"]]
    assert _rows(app, "SELECT value FROM settings WHERE key = 'seed.credit_curves_v1'") == [{"value": "1"}]


def test_seed_as_of_is_the_snapshot_date_whatever_the_clock_says(tmp_path, monkeypatch):
    monkeypatch.setattr(credit_curves, "now_iso", lambda: "2031-05-06T07:08:09+00:00")
    seeded = create_app(db_path=tmp_path / "reloj.db")
    rows = _rows(seeded)
    assert len(rows) == 4
    for r in rows:
        assert r["as_of"] == "2026-11-10" and r["created_at"].startswith("2031-05-06")


def test_restart_does_not_reseed(app):
    path = app.config["DESK_DB"]
    create_app(db_path=path)  # segundo arranque sobre la misma base
    assert len(_rows(app)) == 4


def test_seed_runs_only_with_seed_flag(tmp_path):
    path = tmp_path / "noseed.db"
    create_app(db_path=path, seed=False)
    conn = sqlite3.connect(str(path))
    try:
        assert conn.execute("SELECT COUNT(*) FROM credit_curves").fetchone()[0] == 0
    finally:
        conn.close()


@pytest.mark.parametrize("sql", ["UPDATE credit_curves SET recovery = 0.5", "DELETE FROM credit_curves"])
def test_table_is_insert_only(app, sql):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        with pytest.raises(sqlite3.DatabaseError, match="credit_curves es solo de inserción"):
            conn.execute(sql)
    finally:
        conn.close()


# ---------------------------------------------------------------- GET

def test_get_shape_and_order(client):
    resp = _get(client)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["snapshot"] == SNAP
    assert data["as_of"] == "2026-11-10"
    assert data["discount_curve"] == "TIIE-F"
    assert data["source"] == {"kind": "synthetic", "label": "Sintética (inventada para demostración)"}
    assert [c["entity"] for c in data["curves"]] == ["propia", ALFA, BETA, GAMMA]
    propia, alfa = data["curves"][0], data["curves"][1]
    assert set(propia) == CURVE_KEYS and set(alfa) == CURVE_KEYS
    assert propia["label"] == "Propia (el desk)" and propia["kind"] == "own" and propia["id"] == 4
    assert alfa["label"] == ALFA and alfa["kind"] == "counterparty" and alfa["id"] == 1
    assert alfa["recovery"] == 0.4 and alfa["error"] is None
    assert [q["tenor_years"] for q in alfa["quotes"]] == TENORS
    assert alfa["quotes"][0] == {"tenor_years": 1, "spread": pytest.approx(0.006)}
    assert [set(h) for h in alfa["history"]] == [{"id", "as_of", "created_at"}]
    assert alfa["history"][0]["id"] == 1


@pytest.mark.parametrize("entity", ["propia", ALFA, BETA, GAMMA])
def test_grid_is_a_ten_year_survival_table(client, entity):
    curve = _curves(client)[entity]
    grid = curve["grid"]
    assert [g["year"] for g in grid] == list(range(1, 11))
    survivals = [g["survival"] for g in grid]
    assert all(0 < s < 1 for s in survivals)
    assert all(a > b for a, b in zip(survivals, survivals[1:]))
    prev = 1.0
    for g in grid:
        assert g["cumulative_pd"] == pytest.approx(1.0 - g["survival"], abs=1e-12)
        assert g["marginal_pd"] == pytest.approx(prev - g["survival"], abs=1e-12)
        prev = g["survival"]


@pytest.mark.parametrize("entity", ["propia", ALFA, BETA, GAMMA])
def test_hazards_are_positive_and_follow_the_quote_tenors(client, entity):
    hazards = _curves(client)[entity]["hazards"]
    assert [(h["from_years"], h["to_years"]) for h in hazards] == list(zip([0] + TENORS[:-1], TENORS))
    assert all(h["hazard"] > 0 for h in hazards)
    # el crédito más débil tiene más intensidad: Beta supera a Alfa en cada tramo
    beta = _curves(client)[BETA]["hazards"]
    alfa = _curves(client)[ALFA]["hazards"]
    assert all(b["hazard"] > a["hazard"] for a, b in zip(alfa, beta))


@pytest.mark.parametrize("entity", ["propia", ALFA, BETA, GAMMA])
def test_each_seeded_quote_reprices_to_zero_with_the_cpp_cds_value(app, entity):
    from desk.api import market
    from desk.api.qf import qfpy  # noqa: F401  (debe cargarse antes que qfxva)
    import qfxva

    conn = db.connect(app.config["DESK_DB"])
    try:
        mkt = market.load_context(conn, SNAP)
        row = credit_curves.current(conn)[entity]
    finally:
        conn.close()
    curve = credit_curves.build_curve(qfxva, row, mkt)
    assert len(row["quotes"]) == 6
    for q in row["quotes"]:
        value = qfxva.cds_value(
            qfxva.CdsQuote(q["tenor_years"], q["spread"]), row["recovery"], curve, mkt.curves["TIIE-F"]
        )
        assert abs(value) <= 1e-8, (entity, q, value)


def test_current_returns_the_latest_row_per_entity(app):
    conn = db.connect(app.config["DESK_DB"])
    try:
        cur = credit_curves.current(conn)
    finally:
        conn.close()
    assert set(cur) == {"propia", ALFA, BETA, GAMMA}
    assert cur[ALFA]["id"] == 1 and cur[ALFA]["recovery"] == 0.4
    assert cur[ALFA]["quotes"][0] == {"tenor_years": 1, "spread": pytest.approx(0.006)}


def test_get_requires_an_existing_snapshot(client):
    missing = client.get("/api/credit/curves")
    assert missing.status_code == 400 and missing.get_json()["field"] == "snapshot"
    unknown = _get(client, "NO-EXISTE")
    assert unknown.status_code == 404 and unknown.get_json()["field"] == "snapshot"


def test_counterparty_without_curve_is_listed_with_nulls(app, client):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        conn.execute("INSERT INTO counterparties (name) VALUES ('Banco Delta')")
        conn.commit()
    finally:
        conn.close()
    curves = _get(client).get_json()["curves"]
    by_name = {c["entity"]: c for c in curves}
    delta = by_name["Banco Delta"]
    assert delta["id"] is None and delta["as_of"] is None and delta["recovery"] is None
    assert delta["quotes"] == [] and delta["history"] == [] and delta["error"] is None
    assert "hazards" not in delta and "grid" not in delta
    # orden: propia primero y luego las contrapartes por nombre
    assert [c["entity"] for c in curves] == ["propia"] + sorted(c["entity"] for c in curves if c["entity"] != "propia")


def test_a_curve_that_fails_to_bootstrap_is_listed_with_error(app, client):
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:  # fila inválida metida por SQL (el PUT no la deja pasar)
        conn.execute(
            "INSERT INTO credit_curves (entity, as_of, recovery, quotes, source, created_at)"
            " VALUES (?, '2026-11-11', 0.4, ?, 'synthetic', 'x')",
            (BETA, json.dumps([{"tenor_years": 1, "spread": 0.05}, {"tenor_years": 2, "spread": 0.001}])),
        )
        conn.commit()
    finally:
        conn.close()
    curves = _curves(client)
    beta = curves[BETA]
    assert "negativa" in beta["error"] and "2 años" in beta["error"]
    assert "hazards" not in beta and "grid" not in beta
    assert beta["id"] == 5 and [h["id"] for h in beta["history"]] == [5, 2]
    assert curves[ALFA]["error"] is None and curves[ALFA]["grid"]  # las demás siguen


# ---------------------------------------------------------------- PUT

def test_put_valid_inserts_a_second_row_and_returns_the_element(app, client):
    body = _valid_body(recovery=0.35)
    resp = _put(client, ALFA, body)
    assert resp.status_code == 200, resp.get_json()
    element = resp.get_json()
    assert set(element) == CURVE_KEYS
    assert element["entity"] == ALFA and element["id"] == 5 and element["recovery"] == 0.35
    assert [q["tenor_years"] for q in element["quotes"]] == [1, 3]
    assert [h["id"] for h in element["history"]] == [5, 1]  # la vigente es la última
    assert [g["year"] for g in element["grid"]] == list(range(1, 11))
    rows = [r for r in _rows(app) if r["entity"] == ALFA]
    assert [r["id"] for r in rows] == [1, 5] and rows[1]["source"] == "synthetic"
    assert rows[1]["as_of"] == "2026-11-10"  # el del snapshot de la petición (MX-DEMO por omisión)
    assert element["history"][0]["as_of"] == "2026-11-10"
    assert _curves(client)[ALFA] == element
    # sus otras curvas no cambian
    assert len(_rows(app)) == 5


def test_put_as_of_is_the_as_of_of_the_requested_snapshot_not_the_clock(app, client, monkeypatch):
    monkeypatch.setattr(credit_curves, "now_iso", lambda: "2031-05-06T07:08:09+00:00")
    rolled = client.post("/api/market/MX-DEMO/roll", json={"id": "ROLL-CC", "as_of": "2026-12-31"})
    assert rolled.status_code in (200, 201), rolled.get_json()
    resp = _put(client, BETA, _valid_body(snapshot="ROLL-CC"))
    assert resp.status_code == 200, resp.get_json()
    assert [r["as_of"] for r in _rows(app, "SELECT as_of FROM credit_curves WHERE id = 5")] == ["2026-12-31"]
    assert resp.get_json()["history"][0]["as_of"] == "2026-12-31"
    assert _rows(app, "SELECT created_at FROM credit_curves WHERE id = 5")[0]["created_at"].startswith("2031-05-06")


def test_put_accepts_propia_and_an_explicit_snapshot(client):
    resp = _put(client, "propia", _valid_body(snapshot=SNAP))
    assert resp.status_code == 200 and resp.get_json()["entity"] == "propia"
    assert resp.get_json()["kind"] == "own"


def test_put_negative_intensity_is_400_on_quotes_and_does_not_insert(app, client):
    body = _valid_body(quotes=[{"tenor_years": 1, "spread": 0.05}, {"tenor_years": 2, "spread": 0.001}])
    resp = _put(client, ALFA, body)
    assert resp.status_code == 400
    err = resp.get_json()
    assert err["field"] == "quotes"
    assert err["error"] == "Las cotizaciones implican una intensidad de incumplimiento negativa en el tramo de 2 años"
    assert len(_rows(app)) == 4


@pytest.mark.parametrize("recovery", [1, 1.0, -0.1, "0.4", None, True])
def test_put_rejects_a_bad_recovery(app, client, recovery):
    resp = _put(client, ALFA, _valid_body(recovery=recovery))
    assert resp.status_code == 400 and resp.get_json()["field"] == "recovery"
    assert len(_rows(app)) == 4


def test_put_accepts_zero_recovery(client):
    assert _put(client, ALFA, _valid_body(recovery=0)).status_code == 200


@pytest.mark.parametrize(
    "quotes",
    [
        "no es lista",
        None,
        [],
        [{"tenor_years": t, "spread": 0.01} for t in range(1, 14)],            # 13 cotizaciones
        ["x"],
        [{"tenor_years": 1}],                                                    # falta spread
        [{"spread": 0.01}],                                                      # falta plazo
        [{"tenor_years": 0, "spread": 0.01}],
        [{"tenor_years": -1, "spread": 0.01}],
        [{"tenor_years": 31, "spread": 0.01}],
        [{"tenor_years": "1", "spread": 0.01}],
        [{"tenor_years": 2, "spread": 0.01}, {"tenor_years": 1, "spread": 0.01}],  # decreciente
        [{"tenor_years": 1, "spread": 0.01}, {"tenor_years": 1, "spread": 0.02}],  # repetido
        [{"tenor_years": 1, "spread": 0}],
        [{"tenor_years": 1, "spread": -0.01}],
        [{"tenor_years": 1, "spread": 0.51}],
        [{"tenor_years": 1, "spread": True}],
    ],
)
def test_put_rejects_malformed_quotes(app, client, quotes):
    resp = _put(client, ALFA, _valid_body(quotes=quotes))
    assert resp.status_code == 400 and resp.get_json()["field"] == "quotes", resp.get_json()
    assert len(_rows(app)) == 4


def test_put_accepts_the_boundaries(client):
    for tenor, spread in ((30, 0.5), (12, 0.0001)):
        resp = _put(client, ALFA, _valid_body(quotes=[{"tenor_years": tenor, "spread": spread}]))
        assert resp.status_code == 200, resp.get_json()
        assert resp.get_json()["hazards"][0]["to_years"] == tenor


def test_hazards_report_the_quote_tenor_even_when_not_a_whole_year(client):
    quotes = [{"tenor_years": 0.5, "spread": 0.01}, {"tenor_years": 1.3, "spread": 0.012}]
    element = _put(client, ALFA, _valid_body(quotes=quotes)).get_json()
    assert [(h["from_years"], h["to_years"]) for h in element["hazards"]] == [(0, 0.5), (0.5, 1.3)]
    assert [g["year"] for g in element["grid"]] == list(range(1, 11))


def test_put_unknown_entity_is_404(app, client):
    resp = _put(client, "Banco Fantasma", _valid_body())
    assert resp.status_code == 404 and resp.get_json()["field"] == "entity"
    assert len(_rows(app)) == 4


def test_put_unknown_snapshot_is_404(app, client):
    resp = _put(client, ALFA, _valid_body(snapshot="NO-EXISTE"))
    assert resp.status_code == 404 and resp.get_json()["field"] == "snapshot"
    assert len(_rows(app)) == 4


def test_put_body_must_be_an_object(client):
    resp = client.put("/api/credit/curves/propia", json=[1, 2])
    assert resp.status_code == 400
