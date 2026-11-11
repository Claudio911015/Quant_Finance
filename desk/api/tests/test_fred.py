import urllib.error
import urllib.request

import pytest

from desk.api import fred
from desk.api.tests.mdf_fixture import make_fred_csv

CSV = (
    "observation_date,DEXMXUS\n"
    "2026-10-09,18.5\n"
    "2026-10-12,\n"
    "2026-10-13,.\n"
    "2026-10-14,18.7\n"
    "2026-11-06,18.6226\n"
)


def test_constants():
    assert fred.DEXMXUS_URL == "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXMXUS"
    assert fred.TIMEOUT_S == 20


def test_parse_discards_empty_and_dot_observations():
    assert fred.parse_dexmxus(CSV) == [
        ("2026-10-09", 18.5),
        ("2026-10-14", 18.7),
        ("2026-11-06", 18.6226),
    ]


def test_parse_discards_non_finite_non_positive_and_unparseable():
    text = (
        "observation_date,DEXMXUS\n"
        "2026-01-01,nan\n"
        "2026-01-02,inf\n"
        "2026-01-03,0\n"
        "2026-01-04,-3.2\n"
        "2026-01-05,abc\n"
        "no-es-fecha,19.0\n"
        "2026-01-06\n"
        "\n"
        "2026-01-07,19.25\n"
    )
    assert fred.parse_dexmxus(text) == [("2026-01-07", 19.25)]


def test_parse_is_ascending_and_ignores_header_name():
    text = "DATE,VALOR\n2026-03-02,19.0\n2026-03-01,18.0\n"
    assert fred.parse_dexmxus(text) == [("2026-03-01", 18.0), ("2026-03-02", 19.0)]


@pytest.mark.parametrize(
    "text",
    ["", "observation_date,DEXMXUS\n", "observation_date,DEXMXUS\n2026-10-12,\n2026-10-13,.\n"],
)
def test_parse_without_valid_observations_raises(text):
    with pytest.raises(ValueError):
        fred.parse_dexmxus(text)


def test_make_fred_csv_writes_header_and_blanks(tmp_path):
    path = make_fred_csv(tmp_path / "fred.csv", [("2026-10-09", 18.5), ("2026-10-12", None)])
    assert path.read_text() == "observation_date,DEXMXUS\n2026-10-09,18.5\n2026-10-12,\n"


def test_fetch_reads_a_file_url(tmp_path):
    path = make_fred_csv(
        tmp_path / "fred.csv", [("2026-10-09", 18.5), ("2026-10-12", None), ("2026-11-06", 18.6226)]
    )
    assert fred.fetch_dexmxus(path.as_uri()) == [("2026-10-09", 18.5), ("2026-11-06", 18.6226)]


def test_fetch_missing_file_propagates_urlerror(tmp_path):
    with pytest.raises(urllib.error.URLError):
        fred.fetch_dexmxus((tmp_path / "no_existe.csv").as_uri())


def test_fetch_without_valid_observations_propagates_valueerror(tmp_path):
    path = make_fred_csv(tmp_path / "fred.csv", [("2026-10-12", None)])
    with pytest.raises(ValueError):
        fred.fetch_dexmxus(path.as_uri())


def test_fetch_passes_url_as_is_with_20s_timeout_and_no_user_agent(monkeypatch):
    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return CSV.encode("utf-8")

    def fake_urlopen(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    rows = fred.fetch_dexmxus(fred.DEXMXUS_URL)
    # La URL llega como cadena (no como Request con cabeceras) y solo se fija el tiempo máximo.
    assert calls == [((fred.DEXMXUS_URL,), {"timeout": 20})]
    assert rows[-1] == ("2026-11-06", 18.6226)
