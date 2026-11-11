"""Fijaciones traídas de la fuente (NY Fed y Banxico) con `urlopen` simulado: sin red en la suite."""
import json
import socket
import urllib.error
import urllib.request
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
TOKEN = "tok-secreto-0123456789abcdef"
NYFED_URL = (
    "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json"
    "?startDate=2026-10-27&endDate=2026-11-06"
)
RANGE = {"from": "2026-10-27", "to": "2026-11-06"}
TOKEN_MISSING = "Falta el token de Banxico (variable BANXICO_TOKEN)"
TOKEN_REJECTED = "Banxico rechazó el token (BANXICO_TOKEN)"


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._payload


@pytest.fixture(autouse=True)
def no_real_token(monkeypatch):
    monkeypatch.delenv("BANXICO_TOKEN", raising=False)


@pytest.fixture
def served(monkeypatch):
    """Instala un `urlopen` simulado; devuelve la lista de peticiones `(url, token)` recibidas."""
    calls = []

    def serve(payload=None, error=None):
        def fake_urlopen(req, timeout=None):
            if isinstance(req, str):
                calls.append((req, None, timeout))
            else:
                calls.append((req.full_url, req.get_header("Bmx-token"), timeout))
            if error is not None:
                raise error
            return FakeResponse(payload)

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        return calls

    return serve


def fixture_bytes(name):
    return (FIXTURES / name).read_bytes()


def post(client, **body):
    return client.post("/api/fixings/fetch", json=body)


def stored(client, index=None):
    url = "/api/fixings" + ("?index=%s" % index if index else "")
    return client.get(url).get_json()["fixings"]


def http_error(code, msg="x"):
    return urllib.error.HTTPError("https://example.invalid/", code, msg, {}, None)


# ---- errores: el cuerpo existente no cambia y `code` solo aparece si se dio --------------------

def test_error_without_code_keeps_exact_body(client):
    resp = client.get("/api/fixings?index=NOPE")
    assert resp.status_code == 400
    assert set(resp.get_json()) == {"error", "field"}


def test_error_with_code_adds_code(client, served):
    served()
    resp = post(client, index="USDMXN", **RANGE)
    assert resp.status_code == 409
    assert set(resp.get_json()) == {"error", "field", "code"}


# ---- SOFR (Fed de Nueva York) --------------------------------------------------------------------

def test_sofr_fetch_inserts_in_decimal_and_asks_only_dates(client, served):
    calls = served(fixture_bytes("nyfed_sofr.json"))
    resp = post(client, index="SOFR", **RANGE)
    assert resp.status_code == 200
    assert resp.get_json() == {
        "index": "SOFR",
        "source": "Fed de Nueva York",
        "from": "2026-10-27",
        "to": "2026-11-06",
        "fetched": 9,
        "inserted": 9,
        "unchanged": 0,
        "conflicts": [],
    }
    assert calls == [(NYFED_URL, None, 20)]
    rows = stored(client, "SOFR")
    assert len(rows) == 9
    assert rows[0] == {"index": "SOFR", "date": "2026-10-27", "value": 0.0395}
    assert rows[-1] == {"index": "SOFR", "date": "2026-11-06", "value": 0.0389}


def test_repeating_the_fetch_inserts_nothing_and_changes_nothing(client, served):
    served(fixture_bytes("nyfed_sofr.json"))
    post(client, index="SOFR", **RANGE)
    before = stored(client)
    resp = post(client, index="SOFR", **RANGE)
    assert resp.status_code == 200
    body = resp.get_json()
    assert (body["fetched"], body["inserted"], body["unchanged"], body["conflicts"]) == (9, 0, 9, [])
    assert stored(client) == before


def test_manual_fixing_equal_within_tolerance_is_unchanged(client, served):
    served(fixture_bytes("nyfed_sofr.json"))
    client.post("/api/fixings", json={"index": "SOFR", "date": "2026-11-06", "value": 0.0389})
    client.post("/api/fixings", json={"index": "SOFR", "date": "2026-11-05", "value": 0.0392 + 5e-10})
    body = post(client, index="SOFR", **RANGE).get_json()
    assert (body["fetched"], body["inserted"], body["unchanged"], body["conflicts"]) == (9, 7, 2, [])
    assert next(r for r in stored(client) if r["date"] == "2026-11-05")["value"] == 0.0392 + 5e-10


def test_different_value_is_a_conflict_and_is_not_overwritten(client, served):
    served(fixture_bytes("nyfed_sofr.json"))
    client.post("/api/fixings", json={"index": "SOFR", "date": "2026-11-06", "value": 0.05})
    resp = post(client, index="SOFR", **RANGE)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["conflicts"] == [{"date": "2026-11-06", "stored": 0.05, "source": 0.0389}]
    assert (body["fetched"], body["inserted"], body["unchanged"]) == (9, 8, 0)
    assert body["fetched"] == body["inserted"] + body["unchanged"] + len(body["conflicts"])
    assert next(r for r in stored(client) if r["date"] == "2026-11-06")["value"] == 0.05
    assert len(stored(client)) == 9  # lo nuevo sí entró pese al conflicto


def test_tolerance_boundary_is_one_nano(client, served):
    served(fixture_bytes("nyfed_sofr.json"))
    client.post("/api/fixings", json={"index": "SOFR", "date": "2026-11-06", "value": 0.0389 + 2e-9})
    body = post(client, index="SOFR", **RANGE).get_json()
    assert len(body["conflicts"]) == 1 and body["unchanged"] == 0


def test_range_without_data_is_not_an_error(client, served):
    served(json.dumps({"refRates": []}).encode())
    body = post(client, index="SOFR", **RANGE).get_json()
    assert (body["fetched"], body["inserted"], body["unchanged"], body["conflicts"]) == (0, 0, 0, [])
    assert stored(client) == []


# ---- validación del cuerpo (400) -----------------------------------------------------------------

@pytest.mark.parametrize(
    "body,field",
    [
        ({"index": "SOFR", "from": "2026-11-06", "to": "2026-10-27"}, "from"),
        ({"index": "SOFR", "from": "2025-11-05", "to": "2026-11-07"}, "to"),  # 367 días
        ({"index": "EURUSD", **RANGE}, "index"),
        ({"from": "2026-10-27", "to": "2026-11-06"}, "index"),
        ({"index": "SOFR", "from": "27/10/2026", "to": "2026-11-06"}, "from"),
        ({"index": "SOFR", "from": "2026-10-27"}, "to"),
    ],
    ids=["invertido", "mas-de-366", "indice-malo", "sin-indice", "fecha-no-iso", "sin-to"],
)
def test_bad_request_is_400_with_field_and_no_request(client, served, body, field):
    calls = served(fixture_bytes("nyfed_sofr.json"))
    resp = client.post("/api/fixings/fetch", json=body)
    assert resp.status_code == 400
    assert resp.get_json()["field"] == field
    assert calls == []
    assert stored(client) == []


def test_non_object_body_is_400(client):
    assert client.post("/api/fixings/fetch", json=[1]).status_code == 400


def test_exactly_366_days_is_allowed(client, served):
    served(fixture_bytes("nyfed_sofr.json"))
    resp = post(client, index="SOFR", **{"from": "2026-01-01", "to": "2027-01-02"})
    assert resp.status_code == 200


# ---- fallos de la fuente (502, nada insertado) ---------------------------------------------------

@pytest.mark.parametrize(
    "error",
    [urllib.error.URLError("sin ruta"), http_error(500, "Internal Server Error"), socket.timeout("timed out")],
    ids=["urlerror", "http-500", "timeout"],
)
def test_sofr_network_failure_is_502_and_writes_nothing(client, served, error):
    served(error=error)
    resp = post(client, index="SOFR", **RANGE)
    assert resp.status_code == 502
    assert resp.get_json()["error"].startswith("La Fed de Nueva York no respondió: ")
    assert resp.get_json()["field"] is None and "code" not in resp.get_json()
    assert stored(client) == []


def test_sofr_unreadable_body_is_502_and_writes_nothing(client, served):
    served(b"<html>caido</html>")
    resp = post(client, index="SOFR", **RANGE)
    assert resp.status_code == 502
    assert stored(client) == []


def test_invalid_value_from_source_is_502_and_nothing_is_written(client, served):
    rows = [
        {"effectiveDate": "2026-11-05", "type": "SOFR", "percentRate": 3.92},
        {"effectiveDate": "2026-11-06", "type": "SOFR", "percentRate": 5000.0},  # 50 en decimal > MAX_RATE
    ]
    served(json.dumps({"refRates": rows}).encode())
    resp = post(client, index="SOFR", **RANGE)
    assert resp.status_code == 502
    assert "2026-11-06" in resp.get_json()["error"]
    assert stored(client) == []


# ---- Banxico (TIIE-F, USDMXN) --------------------------------------------------------------------

def test_tiie_f_fetch_with_token_converts_to_decimal_and_skips_ne(client, served, monkeypatch):
    monkeypatch.setenv("BANXICO_TOKEN", TOKEN)
    calls = served(fixture_bytes("banxico_tiie_f.json"))
    resp = post(client, index="TIIE-F", **RANGE)
    assert resp.status_code == 200
    assert resp.get_json() == {
        "index": "TIIE-F",
        "source": "Banxico (SIE)",
        "from": "2026-10-27",
        "to": "2026-11-06",
        "fetched": 8,  # 9 filas, una "N/E"
        "inserted": 8,
        "unchanged": 0,
        "conflicts": [],
    }
    assert TOKEN not in resp.get_data(as_text=True)
    assert calls == [
        (
            "https://www.banxico.org.mx/SieAPIRest/service/v1/series/SF331451/datos/2026-10-27/2026-11-06",
            TOKEN,
            20,
        )
    ]
    rows = stored(client, "TIIE-F")
    assert len(rows) == 8 and "2026-11-02" not in {r["date"] for r in rows}
    assert rows[0]["value"] == 0.0691 and rows[-1]["value"] == 0.0688


def test_usdmxn_fetch_keeps_value_and_reports_conflict(client, served, monkeypatch):
    monkeypatch.setenv("BANXICO_TOKEN", TOKEN)
    calls = served(fixture_bytes("banxico_fix.json"))
    client.post("/api/fixings", json={"index": "USDMXN", "date": "2026-10-28", "value": 18.0})
    resp = post(client, index="USDMXN", **RANGE)
    body = resp.get_json()
    assert resp.status_code == 200 and body["source"] == "Banxico (SIE)"
    assert body["conflicts"] == [{"date": "2026-10-28", "stored": 18.0, "source": 18.4567}]
    assert (body["fetched"], body["inserted"], body["unchanged"]) == (8, 7, 0)
    assert "/series/SF43718/datos/" in calls[0][0]
    assert next(r for r in stored(client, "USDMXN") if r["date"] == "2026-10-28")["value"] == 18.0
    assert TOKEN not in resp.get_data(as_text=True)


def test_banxico_series_without_data_is_not_an_error(client, served, monkeypatch):
    monkeypatch.setenv("BANXICO_TOKEN", TOKEN)
    served(fixture_bytes("banxico_sin_datos.json"))
    body = post(client, index="USDMXN", **RANGE).get_json()
    assert (body["fetched"], body["inserted"], body["conflicts"]) == (0, 0, [])


@pytest.mark.parametrize("env", [None, ""], ids=["ausente", "vacio"])
@pytest.mark.parametrize("index", ["TIIE-F", "USDMXN"])
def test_missing_token_is_409_with_code_and_no_request(client, served, monkeypatch, env, index):
    if env is not None:
        monkeypatch.setenv("BANXICO_TOKEN", env)
    calls = served(fixture_bytes("banxico_tiie_f.json"))
    resp = post(client, index=index, **RANGE)
    assert resp.status_code == 409
    assert resp.get_json() == {"error": TOKEN_MISSING, "field": None, "code": "banxico_token_missing"}
    assert calls == []
    assert stored(client) == []


@pytest.mark.parametrize("code", [400, 401, 403])
def test_banxico_rejecting_the_token_is_502_with_code(client, served, monkeypatch, code):
    monkeypatch.setenv("BANXICO_TOKEN", TOKEN)
    served(error=http_error(code))
    resp = post(client, index="TIIE-F", **RANGE)
    assert resp.status_code == 502
    assert resp.get_json() == {"error": TOKEN_REJECTED, "field": None, "code": "banxico_token_rejected"}
    assert TOKEN not in resp.get_data(as_text=True)
    assert stored(client) == []


@pytest.mark.parametrize(
    "error",
    [http_error(500, "Server Error"), http_error(404, "Not Found"), urllib.error.URLError("sin ruta")],
    ids=["http-500", "http-404", "urlerror"],
)
def test_other_banxico_failures_are_502_without_code(client, served, monkeypatch, error):
    monkeypatch.setenv("BANXICO_TOKEN", TOKEN)
    served(error=error)
    resp = post(client, index="USDMXN", **RANGE)
    assert resp.status_code == 502
    assert resp.get_json()["error"].startswith("Banxico no respondió: ")
    assert "code" not in resp.get_json()
    assert TOKEN not in resp.get_data(as_text=True)
    assert stored(client) == []


def test_banxico_unreadable_body_is_502(client, served, monkeypatch):
    monkeypatch.setenv("BANXICO_TOKEN", TOKEN)
    served(b"no es json")
    resp = post(client, index="TIIE-F", **RANGE)
    assert resp.status_code == 502
    assert TOKEN not in resp.get_data(as_text=True)
    assert stored(client) == []


def test_sofr_does_not_need_the_banxico_token(client, served):
    served(fixture_bytes("nyfed_sofr.json"))
    assert post(client, index="SOFR", **RANGE).status_code == 200


# ---- GET /api/fixings/sources --------------------------------------------------------------------

def test_sources_without_token(client):
    resp = client.get("/api/fixings/sources")
    assert resp.status_code == 200
    assert resp.get_json() == {
        "sources": [
            {"index": "TIIE-F", "source": "Banxico (SIE)", "available": False, "reason": TOKEN_MISSING, "last_date": None},
            {"index": "SOFR", "source": "Fed de Nueva York", "available": True, "reason": None, "last_date": None},
            {"index": "USDMXN", "source": "Banxico (SIE)", "available": False, "reason": TOKEN_MISSING, "last_date": None},
        ]
    }


def test_sources_with_token_and_last_date(client, served, monkeypatch):
    monkeypatch.setenv("BANXICO_TOKEN", TOKEN)
    served(fixture_bytes("nyfed_sofr.json"))
    post(client, index="SOFR", **RANGE)
    client.post("/api/fixings", json={"index": "TIIE-F", "date": "2026-11-03", "value": 0.07})
    client.post("/api/fixings", json={"index": "TIIE-F", "date": "2026-11-05", "value": 0.07})
    resp = client.get("/api/fixings/sources")
    assert TOKEN not in resp.get_data(as_text=True)
    assert resp.get_json() == {
        "sources": [
            {"index": "TIIE-F", "source": "Banxico (SIE)", "available": True, "reason": None, "last_date": "2026-11-05"},
            {"index": "SOFR", "source": "Fed de Nueva York", "available": True, "reason": None, "last_date": "2026-11-06"},
            {"index": "USDMXN", "source": "Banxico (SIE)", "available": True, "reason": None, "last_date": None},
        ]
    }
