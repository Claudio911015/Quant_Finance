import json
import socket
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from desk.api import nyfed

FIXTURE = Path(__file__).parent / "fixtures" / "nyfed_sofr.json"
URL = (
    "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json"
    "?startDate=2026-10-27&endDate=2026-11-06"
)


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._payload


def _body(*rows):
    return json.dumps({"refRates": list(rows)})


def _row(day="2026-11-06", pct=3.89, kind="SOFR"):
    return {"effectiveDate": day, "type": kind, "percentRate": pct}


def test_constants():
    assert nyfed.SOFR_URL == "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json"
    assert nyfed.TIMEOUT_S == 20


def test_parse_real_fixture_is_ascending_decimal_and_rounded():
    rows = nyfed.parse_sofr(FIXTURE.read_text())
    assert len(rows) == 9
    assert rows[0] == ("2026-10-27", 0.0395)
    assert rows[-1] == ("2026-11-06", 0.0389)  # 3.89 % -> 0.0389 exacto
    assert [d for d, _ in rows] == sorted(d for d, _ in rows)
    assert dict(rows)["2026-11-03"] == 0.0397


def test_parse_discards_invalid_rows_and_other_types():
    text = _body(
        _row("2026-11-06", 3.89),
        _row("2026-11-05", 3.92, kind="BGCR"),
        _row("2026-11-04", None),
        _row("2026-11-03", "3.97"),
        _row("2026-11-02", True),
        _row("2026-11-01", float("nan")),
        _row("no-es-fecha", 3.9),
        {"type": "SOFR", "percentRate": 3.9},
        "no es un objeto",
        _row("2026-10-30", 3.95),
    )
    assert nyfed.parse_sofr(text) == [("2026-10-30", 0.0395), ("2026-11-06", 0.0389)]


def test_parse_repeated_date_keeps_the_last_row():
    text = _body(_row("2026-11-06", 3.89), _row("2026-11-06", 3.90))
    assert nyfed.parse_sofr(text) == [("2026-11-06", 0.039)]


def test_parse_empty_list_is_valid():
    assert nyfed.parse_sofr(_body()) == []


@pytest.mark.parametrize("text", ["", "no es json", "[]", "{}", '{"refRates": null}', '{"refRates": {}}'])
def test_parse_unreadable_body_raises(text):
    with pytest.raises(ValueError):
        nyfed.parse_sofr(text)


def test_fetch_builds_exact_url_with_only_the_dates_and_20s_timeout(monkeypatch):
    calls = []

    def fake_urlopen(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse(FIXTURE.read_bytes())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    rows = nyfed.fetch_sofr("2026-10-27", "2026-11-06")
    # La URL llega como cadena (sin Request ni cabeceras propias) y solo se fija el tiempo máximo.
    assert calls == [((URL,), {"timeout": 20})]
    assert len(rows) == 9 and rows[-1] == ("2026-11-06", 0.0389)


@pytest.mark.parametrize("start,end", [("27/10/2026", "2026-11-06"), ("2026-10-27&x=1", "2026-11-06"), ("2026-10-27", "")])
def test_fetch_rejects_non_iso_dates_before_any_request(monkeypatch, start, end):
    def fake_urlopen(*args, **kwargs):
        raise AssertionError("no debe haber petición")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ValueError):
        nyfed.fetch_sofr(start, end)


@pytest.mark.parametrize(
    "make_error",
    [
        lambda: urllib.error.HTTPError(URL, 500, "Internal Server Error", {}, None),
        lambda: urllib.error.URLError("sin ruta"),
        lambda: socket.timeout("timed out"),
    ],
    ids=["http-500", "urlerror", "timeout"],
)
def test_fetch_propagates_network_errors(monkeypatch, make_error):
    error = make_error()

    def fake_urlopen(*args, **kwargs):
        raise error

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(type(error)):
        nyfed.fetch_sofr("2026-10-27", "2026-11-06")


def test_fetch_unreadable_body_propagates_valueerror(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResponse(b"<html>caido</html>"))
    with pytest.raises(ValueError):
        nyfed.fetch_sofr("2026-10-27", "2026-11-06")
