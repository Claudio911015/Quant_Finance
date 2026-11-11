import json
import socket
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from desk.api import banxico

FIXTURES = Path(__file__).parent / "fixtures"
TOKEN = "TOKEN-SECRETO-0123456789"
URL = "https://www.banxico.org.mx/SieAPIRest/service/v1/series/SF331451/datos/2026-10-27/2026-11-06"


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._payload


def _text(name):
    return (FIXTURES / name).read_text()


def _body(id_serie, *datos):
    return json.dumps({"bmx": {"series": [{"idSerie": id_serie, "datos": list(datos)}]}})


def test_constants():
    assert banxico.TIIE_F_SERIES == "SF331451"
    assert banxico.FIX_SERIES == "SF43718"
    assert banxico.BASE_URL == "https://www.banxico.org.mx/SieAPIRest/service/v1/series"
    assert banxico.TIMEOUT_S == 20


def test_parse_tiie_f_to_decimal_ascending_and_skips_missing():
    rows = banxico.parse_series(_text("banxico_tiie_f.json"))
    assert len(rows) == 8  # el N/E del 02/11 se omite
    assert rows[0] == ("2026-10-27", 0.0691)
    assert rows[-1] == ("2026-11-06", 0.0688)
    assert "2026-11-02" not in dict(rows)
    assert [d for d, _ in rows] == sorted(d for d, _ in rows)
    assert dict(rows)["2026-11-04"] == 0.068875  # 6.8875 % redondeado a 10 decimales, exacto


def test_parse_fix_as_is_and_converts_date_format():
    rows = banxico.parse_series(_text("banxico_fix.json"))
    assert len(rows) == 8
    assert rows[0] == ("2026-10-27", 18.4123)
    assert rows[-1] == ("2026-11-06", 18.6226)


def test_parse_sorts_descending_input_and_keeps_last_of_a_repeated_date():
    text = _body(
        banxico.FIX_SERIES,
        {"fecha": "06/11/2026", "dato": "18.7"},
        {"fecha": "05/11/2026", "dato": "18.5"},
        {"fecha": "06/11/2026", "dato": "18.6"},
    )
    assert banxico.parse_series(text) == [("2026-11-05", 18.5), ("2026-11-06", 18.6)]


def test_parse_discards_unreadable_rows():
    text = _body(
        banxico.FIX_SERIES,
        {"fecha": "2026-11-06", "dato": "18.7"},
        {"fecha": "31/02/2026", "dato": "18.7"},
        {"fecha": "05/11/2026", "dato": "nan"},
        {"fecha": "04/11/2026", "dato": None},
        {"fecha": "03/11/2026"},
        "no es un objeto",
        {"fecha": "02/11/2026", "dato": "N/E"},
        {"fecha": "30/10/2026", "dato": "18.4"},
    )
    assert banxico.parse_series(text) == [("2026-10-30", 18.4)]


def test_parse_series_without_datos_is_valid_and_empty():
    assert banxico.parse_series(_text("banxico_sin_datos.json")) == []


@pytest.mark.parametrize(
    "text",
    [
        "",
        "no es json",
        "[]",
        "{}",
        '{"bmx": {}}',
        '{"bmx": {"series": []}}',
        '{"bmx": {"series": [{"idSerie": "SF999", "datos": []}]}}',
        '{"bmx": {"series": [{"datos": []}]}}',
        '{"bmx": {"series": [{"idSerie": "SF43718", "datos": {}}]}}',
        '{"error": {"mensaje": "Token inválido"}}',
    ],
)
def test_parse_unreadable_body_raises(text):
    with pytest.raises(ValueError):
        banxico.parse_series(text)


def test_fetch_sends_token_header_exact_url_and_20s_timeout(monkeypatch):
    calls = []

    def fake_urlopen(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse(_text("banxico_tiie_f.json").encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    rows = banxico.fetch_series(banxico.TIIE_F_SERIES, "2026-10-27", "2026-11-06", TOKEN)
    (args, kwargs), = calls
    request = args[0]
    assert kwargs == {"timeout": 20}
    assert request.full_url == URL
    assert request.get_header("Bmx-token") == TOKEN
    assert rows[-1] == ("2026-11-06", 0.0688)


def test_fetch_fix_url(monkeypatch):
    seen = []
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda request, timeout: seen.append(request.full_url) or FakeResponse(_text("banxico_fix.json").encode()),
    )
    rows = banxico.fetch_series(banxico.FIX_SERIES, "2026-10-27", "2026-11-06", TOKEN)
    assert seen == ["https://www.banxico.org.mx/SieAPIRest/service/v1/series/SF43718/datos/2026-10-27/2026-11-06"]
    assert rows[0] == ("2026-10-27", 18.4123)


@pytest.mark.parametrize("start,end", [("27/10/2026", "2026-11-06"), ("2026-10-27/../x", "2026-11-06"), ("2026-10-27", "")])
def test_fetch_rejects_non_iso_dates_before_any_request(monkeypatch, start, end):
    def fake_urlopen(*args, **kwargs):
        raise AssertionError("no debe haber petición")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ValueError) as info:
        banxico.fetch_series(banxico.FIX_SERIES, start, end, TOKEN)
    assert TOKEN not in str(info.value)


@pytest.mark.parametrize("token", ["", None])
def test_fetch_without_token_raises_before_any_request(monkeypatch, token):
    def fake_urlopen(*args, **kwargs):
        raise AssertionError("no debe haber petición")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ValueError):
        banxico.fetch_series(banxico.FIX_SERIES, "2026-10-27", "2026-11-06", token)


@pytest.mark.parametrize(
    "make_error",
    [
        lambda: urllib.error.HTTPError(URL, 400, "Bad Request", {}, None),
        lambda: urllib.error.HTTPError(URL, 403, "Forbidden", {}, None),
        lambda: urllib.error.URLError("sin ruta"),
        lambda: socket.timeout("timed out"),
    ],
    ids=["http-400", "http-403", "urlerror", "timeout"],
)
def test_fetch_propagates_network_errors_without_leaking_the_token(monkeypatch, make_error):
    error = make_error()

    def fake_urlopen(*args, **kwargs):
        raise error

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(type(error)) as info:
        banxico.fetch_series(banxico.FIX_SERIES, "2026-10-27", "2026-11-06", TOKEN)
    assert TOKEN not in str(info.value)
    if isinstance(error, urllib.error.HTTPError):
        assert info.value.code == error.code  # quien llama distingue 400/401/403 por `.code`


@pytest.mark.parametrize("payload", [b"<html>caido</html>", b'{"error": {"mensaje": "Token inv\\u00e1lido"}}'])
def test_fetch_unreadable_body_raises_valueerror_without_the_token(monkeypatch, payload):
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResponse(payload))
    with pytest.raises(ValueError) as info:
        banxico.fetch_series(banxico.FIX_SERIES, "2026-10-27", "2026-11-06", TOKEN)
    assert TOKEN not in str(info.value)
