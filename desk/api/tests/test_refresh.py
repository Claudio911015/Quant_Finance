"""`POST /api/market/refresh` (R5, R11). Scripts falsos y `file://`: ni red, ni la base real, ni el
ejecutable real de MarketDataFeed."""
import http.client
import math
import re
import socket
import sqlite3
import urllib.error
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from desk.api import db, fred, live_market, market, refresh
from desk.api.app import create_app
from desk.api.tests.mdf_fixture import REAL_2026_11_10, make_fred_csv, make_mdf_db

URL = "/api/market/refresh"
LIVE = "/api/market/snapshots/MKT-LIVE"
LOCK_MSG = "Ya hay una actualización de datos en curso"
LIVE_PUT_MSG = "Mercado vivo se reconstruye en cada actualización; no se edita"
KEYS = {"ran_at", "mdf_exit_code", "treasury_latest", "sofr_latest", "fred_latest", "snapshot"}


# ------------------------------------------------------------------------------- datos de prueba

def _hist5(n):
    """`n` observaciones 5Y `(fecha, %)` que terminan el 2026-11-10 en 4.81."""
    ys = [4.0 + 0.4 * math.sin(i / 7.0) + 0.04 * math.sin(i * 1.3) for i in range(n)]
    ys[-1] = REAL_2026_11_10["5Y"]
    return [
        ((date(2026, 11, 10) - timedelta(days=n - 1 - i)).isoformat(), y)
        for i, y in enumerate(ys)
    ]


def _fx_rows(n):
    """`n` observaciones válidas de DEXMXUS que terminan el 2026-11-06 en 18.6226."""
    vals = [18.0 + 0.8 * math.sin(i / 9.0) + 0.05 * math.sin(i * 1.7) for i in range(n)]
    vals[-1] = 18.6226
    return [((date(2026, 11, 6) - timedelta(days=n - 1 - i)).isoformat(), v) for i, v in enumerate(vals)]


def _script(folder, body, name="fetch.sh"):
    path = folder / name
    path.write_text("#!/bin/sh\n%s\n" % body)
    path.chmod(0o755)
    return path


def _arm(app, tmp_path, tag="ok", script="exit 0", n5=300, nfx=300, sofr=3.88, drop_tenor=None,
         fred_rows=None):
    """Apunta la app a una base, un ejecutable y un CSV de FRED falsos en `tmp_path/<tag>`."""
    folder = tmp_path / tag
    folder.mkdir(exist_ok=True)
    mdf = make_mdf_db(
        folder / "sofr.db", history_5y=_hist5(n5), sofr=(("2026-11-09", sofr),),
        drop_tenor=drop_tenor,
    )
    csv = make_fred_csv(folder / "fred.csv", _fx_rows(nfx) if fred_rows is None else fred_rows)
    app.config["MDF_DB"] = str(mdf)
    app.config["MDF_FETCH"] = str(_script(folder, script))
    app.config["FRED_DEXMXUS_URL"] = csv.as_uri()
    return mdf


def _live_row(app):
    conn = db.connect(app.config["DESK_DB"])
    try:
        row = conn.execute("SELECT * FROM snapshots WHERE id = 'MKT-LIVE'").fetchone()
        return None if row is None else tuple(row)
    finally:
        conn.close()


def _post_ok(client):
    r = client.post(URL)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


@pytest.fixture(autouse=True)
def lock_is_free_around_each_test():
    assert not refresh._LOCK.locked()
    yield
    assert not refresh._LOCK.locked()


# --------------------------------------------------------------------------------------- éxito

def test_success_returns_the_contract(app, client, tmp_path):
    args_file = tmp_path / "args.txt"
    mdf = _arm(app, tmp_path, script='printf "%%s\\n" "$@" > %s\nexit 0' % args_file)

    body = _post_ok(client)

    assert set(body) == KEYS
    assert body["mdf_exit_code"] == 0
    assert (body["treasury_latest"], body["sofr_latest"], body["fred_latest"]) == (
        "2026-11-10", "2026-11-09", "2026-11-06",
    )
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00", body["ran_at"])
    assert datetime.fromisoformat(body["ran_at"]).utcoffset() == timedelta(0)
    snap = body["snapshot"]
    assert snap["id"] == "MKT-LIVE"
    assert snap["read_only"] is True
    assert snap["data_quality"] == "mixed"
    assert snap["as_of"] == "2026-11-10"
    assert snap["fx"]["spot"] == 18.6226
    # El ejecutable recibe exactamente estos argumentos, en este orden.
    assert args_file.read_text().split("\n")[:-1] == ["--latest", "--treasury", "--db", str(mdf)]


def test_snapshot_equals_get_and_appears_in_the_list(app, client, tmp_path):
    _arm(app, tmp_path)
    assert "MKT-LIVE" not in [s["id"] for s in client.get("/api/market/snapshots").get_json()["snapshots"]]

    body = _post_ok(client)

    assert body["snapshot"] == client.get(LIVE).get_json()
    listed = client.get("/api/market/snapshots").get_json()["snapshots"]
    assert [s["id"] for s in listed] == ["MKT-LIVE", "MX-DEMO"]
    assert next(s for s in listed if s["id"] == "MKT-LIVE")["data_quality"] == "mixed"


def test_second_refresh_replaces_the_row_with_new_data(app, client, tmp_path):
    _arm(app, tmp_path, tag="a", sofr=3.88)
    _post_ok(client)
    before = _live_row(app)
    _arm(app, tmp_path, tag="b", sofr=3.50)

    body = _post_ok(client)

    assert _live_row(app) != before
    assert next(q for q in body["snapshot"]["quotes"] if q["id"] == "SOFR:1D")["rate"] == 0.035


def test_fred_is_requested_once_per_refresh(app, client, tmp_path, monkeypatch):
    _arm(app, tmp_path)
    calls = []
    real = fred.fetch_dexmxus
    monkeypatch.setattr(
        fred, "fetch_dexmxus", lambda url: calls.append(url) or real(url)
    )

    _post_ok(client)

    assert calls == [app.config["FRED_DEXMXUS_URL"]]


def test_body_is_ignored(app, client, tmp_path):
    _arm(app, tmp_path)
    assert client.post(URL, data="esto no es json", content_type="application/json").status_code == 200


# -------------------------------------------------------------------- fallos: 502 y fila intacta

def _exit3(app, tmp_path):
    _arm(app, tmp_path, tag="bad", script="echo falla-del-ejecutable >&2\nexit 3", sofr=3.50)
    return "código 3: falla-del-ejecutable"


def _no_exe(app, tmp_path):
    _arm(app, tmp_path, tag="bad", sofr=3.50)
    app.config["MDF_FETCH"] = str(tmp_path / "bad" / "no-existe")
    return "No se pudo ejecutar MarketDataFeed"


def _not_executable(app, tmp_path):
    _arm(app, tmp_path, tag="bad", sofr=3.50)
    Path(app.config["MDF_FETCH"]).chmod(0o644)
    return "No se pudo ejecutar MarketDataFeed"


def _timeout(app, tmp_path):
    _arm(app, tmp_path, tag="bad", script="exec sleep 5", sofr=3.50)
    return "no terminó en 1 s"


def _fred_missing(app, tmp_path):
    _arm(app, tmp_path, tag="bad", sofr=3.50)
    app.config["FRED_DEXMXUS_URL"] = (tmp_path / "bad" / "no-existe.csv").as_uri()
    return "FRED no respondió"


def _fred_no_valid_rows(app, tmp_path):
    _arm(app, tmp_path, tag="bad", sofr=3.50, fred_rows=[("2026-11-05", None), ("2026-11-06", None)])
    return "FRED no respondió: DEXMXUS sin observaciones válidas"


def _fred_short_history(app, tmp_path):
    _arm(app, tmp_path, tag="bad", sofr=3.50, nfx=50)
    return "Historia insuficiente: 49 cambios diarios de USDMXN (mínimo 60)"


def _mdf_missing_tenor(app, tmp_path):
    _arm(app, tmp_path, tag="bad", sofr=3.50, drop_tenor="7Y")
    return "faltan 7Y"


def _mdf_short_history(app, tmp_path):
    _arm(app, tmp_path, tag="bad", sofr=3.50, n5=50)
    return "Historia insuficiente: 49 cambios diarios de 5Y (mínimo 60)"


def _mdf_db_missing(app, tmp_path):
    _arm(app, tmp_path, tag="bad", sofr=3.50)
    Path(app.config["MDF_DB"]).unlink()
    return "Base de MarketDataFeed no encontrada"


def _mdf_db_not_sqlite(app, tmp_path):
    _arm(app, tmp_path, tag="bad", sofr=3.50)
    Path(app.config["MDF_DB"]).write_text("esto no es sqlite " * 50)
    return "Base de MarketDataFeed inutilizable"


FAILURES = [
    _exit3, _no_exe, _not_executable, _timeout, _fred_missing, _fred_no_valid_rows,
    _fred_short_history, _mdf_missing_tenor, _mdf_short_history, _mdf_db_missing,
    _mdf_db_not_sqlite,
]


@pytest.mark.parametrize("arm", FAILURES, ids=lambda f: f.__name__.lstrip("_"))
def test_failure_is_502_keeps_live_row_and_frees_the_lock(app, client, tmp_path, monkeypatch, arm):
    monkeypatch.setattr(refresh, "FETCH_TIMEOUT_S", 1)
    _arm(app, tmp_path, tag="seed")
    _post_ok(client)
    before = _live_row(app)
    expected = arm(app, tmp_path)

    r = client.post(URL)

    assert r.status_code == 502  # nunca 409 ni 500
    body = r.get_json()
    assert body["field"] is None
    assert expected in body["error"], body["error"]
    assert _live_row(app) == before
    assert not refresh._LOCK.locked()
    # El candado quedó libre: un refresco bueno posterior responde 200.
    _arm(app, tmp_path, tag="good", sofr=3.50)
    assert client.post(URL).status_code == 200


@pytest.mark.parametrize("arm", [_exit3, _fred_missing, _mdf_missing_tenor], ids=lambda f: f.__name__.lstrip("_"))
def test_failure_without_a_previous_live_creates_nothing(app, client, tmp_path, arm):
    arm(app, tmp_path)

    assert client.post(URL).status_code == 502

    assert _live_row(app) is None
    assert [s["id"] for s in client.get("/api/market/snapshots").get_json()["snapshots"]] == ["MX-DEMO"]


def test_fixture_app_points_at_nonexistent_paths_and_answers_502(app, client, tmp_path):
    for key in ("MDF_DB", "MDF_FETCH"):
        assert not Path(app.config[key]).exists()
        assert str(tmp_path) in app.config[key]
    r = client.post(URL)
    assert r.status_code == 502
    assert "No se pudo ejecutar MarketDataFeed" in r.get_json()["error"]


def test_stderr_is_trimmed_to_its_last_300_characters(app, client, tmp_path):
    _arm(app, tmp_path, script="head -c 1000 /dev/zero | tr '\\0' x >&2\nprintf END >&2\nexit 4")

    r = client.post(URL)

    assert r.status_code == 502
    msg = r.get_json()["error"]
    assert "código 4" in msg
    assert msg.endswith("x" * 297 + "END")
    assert "x" * 298 + "END" not in msg


def test_exit_code_without_stderr_has_no_dangling_colon(app, client, tmp_path):
    _arm(app, tmp_path, script="exit 7")
    assert client.post(URL).get_json()["error"] == "MarketDataFeed terminó con código 7"


@pytest.mark.parametrize(
    "exc",
    [
        urllib.error.URLError("sin ruta al servidor"),
        urllib.error.HTTPError("http://x", 503, "Service Unavailable", {}, None),
        socket.timeout("timed out"),
        ConnectionResetError("reinicio de conexión"),
        http.client.IncompleteRead(b"abc"),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "byte inválido"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_any_fred_network_error_is_502(app, client, tmp_path, monkeypatch, exc):
    _arm(app, tmp_path, tag="seed")
    _post_ok(client)
    before = _live_row(app)

    def boom(url):
        raise exc

    monkeypatch.setattr(fred, "fetch_dexmxus", boom)
    r = client.post(URL)

    assert r.status_code == 502
    assert r.get_json()["error"].startswith("FRED no respondió: ")
    assert _live_row(app) == before


def test_construction_failure_is_502_and_rolls_back(app, client, tmp_path, monkeypatch):
    """El INSERT ya se hizo cuando falla la lectura del payload: el rollback deja la fila anterior."""
    _arm(app, tmp_path, tag="seed", sofr=3.88)
    _post_ok(client)
    before = _live_row(app)
    _arm(app, tmp_path, tag="new", sofr=3.50)

    def boom(conn, snapshot_id):
        assert conn.execute("SELECT data FROM snapshots WHERE id = 'MKT-LIVE'").fetchone()[0] != before[4]
        raise sqlite3.OperationalError("disco lleno")

    monkeypatch.setattr(market, "snapshot_payload", boom)
    r = client.post(URL)

    assert r.status_code == 502
    assert r.get_json() == {"error": "No se pudo construir Mercado vivo: disco lleno", "field": None}
    assert _live_row(app) == before


def test_bootstrap_failure_is_502_and_keeps_the_row(app, client, tmp_path, monkeypatch):
    _arm(app, tmp_path, tag="seed", sofr=3.88)
    _post_ok(client)
    before = _live_row(app)
    _arm(app, tmp_path, tag="new", sofr=3.50)

    def boom(*a, **k):
        raise RuntimeError("el bootstrap no converge")

    monkeypatch.setattr(live_market, "_build_context", boom)
    r = client.post(URL)

    assert r.status_code == 502
    assert "el bootstrap no converge" in r.get_json()["error"]
    assert _live_row(app) == before


# ------------------------------------------------------------------------------------ candado

def test_concurrent_refresh_is_409_and_does_not_release_the_other_lock(app, client, tmp_path):
    _arm(app, tmp_path)
    assert refresh._LOCK.acquire(blocking=False)
    try:
        r = client.post(URL)
        assert r.status_code == 409
        assert r.get_json() == {"error": LOCK_MSG, "field": None}
        assert refresh._LOCK.locked()  # el candado ajeno sigue tomado
        assert _live_row(app) is None
    finally:
        refresh._LOCK.release()
    assert client.post(URL).status_code == 200


# ------------------------------------------------------------ PUT sobre MKT-LIVE (nota de T2)

@pytest.mark.parametrize(
    "kwargs",
    [
        {"data": b""},
        {"json": [1, 2]},
        {"data": "esto no es json", "content_type": "application/json"},
        {"json": {"spot": 19.0}},
        {"json": {}},
    ],
    ids=["vacio", "lista", "no-json", "objeto-valido", "objeto-vacio"],
)
def test_put_live_is_409_with_any_body(app, client, tmp_path, kwargs):
    _arm(app, tmp_path)
    _post_ok(client)
    before = _live_row(app)

    r = client.put(LIVE, **kwargs)

    assert r.status_code == 409
    assert r.get_json() == {"error": LIVE_PUT_MSG, "field": None}
    assert _live_row(app) == before


def test_put_live_missing_is_404_with_a_non_object_body(client):
    r = client.put(LIVE, json=[1, 2])
    assert r.status_code == 404
    assert r.get_json()["field"] == "snapshot"


def test_put_on_other_snapshots_still_validates_the_body(client):
    assert client.put("/api/market/snapshots/MX-DEMO", json=[1, 2]).status_code == 400
    assert client.put("/api/market/snapshots/MX-DEMO", data=b"").status_code == 400
    assert client.put("/api/market/snapshots/MX-DEMO", json={"spot": 19.5}).status_code == 200


# --------------------------------------------------------------------------- configuración

def test_config_defaults(tmp_path, monkeypatch):
    monkeypatch.delenv("MDF_DB", raising=False)
    monkeypatch.delenv("MDF_FETCH", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "casa"))
    app = create_app(db_path=tmp_path / "t.db")
    mdf = tmp_path / "casa" / "Git" / "MarketDataFeed" / "build"
    assert app.config["MDF_DB"] == str(mdf / "sofr.db")
    assert app.config["MDF_FETCH"] == str(mdf / "examples" / "fetch_sofr")
    assert app.config["FRED_DEXMXUS_URL"] == fred.DEXMXUS_URL == (
        "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXMXUS"
    )


def test_config_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("MDF_DB", "/datos/mdf/sofr.db")
    monkeypatch.delenv("MDF_FETCH", raising=False)
    app = create_app(db_path=tmp_path / "t.db")
    assert app.config["MDF_DB"] == "/datos/mdf/sofr.db"
    assert app.config["MDF_FETCH"] == "/datos/mdf/examples/fetch_sofr"

    monkeypatch.setenv("MDF_FETCH", "/usr/local/bin/mi_fetch")
    app = create_app(db_path=tmp_path / "t2.db")
    assert app.config["MDF_FETCH"] == "/usr/local/bin/mi_fetch"
