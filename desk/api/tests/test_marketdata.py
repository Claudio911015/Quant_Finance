import sqlite3
from datetime import date, timedelta

import pytest

from desk.api import marketdata
from desk.api.errors import ApiError
from desk.api.tests.mdf_fixture import REAL_2026_11_10, make_mdf_db


def _history(n, end="2026-11-10", start_rate=4.0):
    """`n` observaciones 5Y consecutivas (en %) que terminan en `end`, ascendentes."""
    last = date.fromisoformat(end)
    return [
        ((last - timedelta(days=n - 1 - i)).isoformat(), round(start_rate + 0.01 * i, 4))
        for i in range(n)
    ]


def _conflict(excinfo, needle):
    assert excinfo.value.status == 409
    assert excinfo.value.field is None
    assert needle in excinfo.value.error


def test_constants():
    assert marketdata.TENORS == ["1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y"]
    assert marketdata.MAX_CHANGES == 250
    assert marketdata.MIN_CHANGES == 60


def test_latest_treasury_curve_is_complete_and_decimal(tmp_path):
    db = make_mdf_db(tmp_path / "mdf.db")
    curve = marketdata.latest_treasury_curve(db)
    assert curve["date"] == "2026-11-10"
    assert list(curve["yields"]) == marketdata.TENORS  # sin 2M, 4M, 20Y ni 30Y
    assert curve["yields"]["1M"] == pytest.approx(0.0405)
    assert curve["yields"]["10Y"] == pytest.approx(0.0498)
    for tenor in marketdata.TENORS:
        assert curve["yields"][tenor] == pytest.approx(REAL_2026_11_10[tenor] / 100.0)


def test_latest_treasury_curve_uses_max_date(tmp_path):
    db = make_mdf_db(tmp_path / "mdf.db")
    conn = sqlite3.connect(str(db))
    conn.executemany(
        "INSERT INTO treasury_yields (effective_date, tenor, rate) VALUES ('2026-11-06', ?, 9.99)",
        [(t,) for t in marketdata.TENORS],
    )
    conn.commit()
    conn.close()
    curve = marketdata.latest_treasury_curve(db)
    assert curve["date"] == "2026-11-10"
    assert curve["yields"]["5Y"] == pytest.approx(0.0481)


def test_latest_treasury_curve_missing_tenor_is_409(tmp_path):
    db = make_mdf_db(tmp_path / "mdf.db", drop_tenor="3M")
    with pytest.raises(ApiError) as e:
        marketdata.latest_treasury_curve(db)
    _conflict(e, "3M")


def test_latest_date_incomplete_does_not_fall_back_to_older_date(tmp_path):
    db = make_mdf_db(tmp_path / "mdf.db", curve_date="2026-11-06")
    conn = sqlite3.connect(str(db))
    conn.execute(
        "INSERT INTO treasury_yields (effective_date, tenor, rate) VALUES ('2026-11-10', '1M', 4.0)"
    )
    conn.commit()
    conn.close()
    with pytest.raises(ApiError) as e:
        marketdata.latest_treasury_curve(db)
    _conflict(e, "2026-11-10")


def test_missing_database_is_409(tmp_path):
    for fn in (marketdata.latest_treasury_curve, marketdata.latest_sofr, marketdata.treasury_5y_history):
        with pytest.raises(ApiError) as e:
            fn(tmp_path / "no_existe.db")
        _conflict(e, "no encontrada")


def test_empty_database_is_409(tmp_path):
    db = make_mdf_db(tmp_path / "mdf.db", empty=True)
    for fn in (marketdata.latest_treasury_curve, marketdata.latest_sofr):
        with pytest.raises(ApiError) as e:
            fn(db)
        assert e.value.status == 409
    with pytest.raises(ApiError) as e:
        marketdata.treasury_5y_history(db)
    _conflict(e, "Historia insuficiente")


def test_database_without_tables_is_409(tmp_path):
    path = tmp_path / "vacia.db"
    sqlite3.connect(str(path)).close()
    for fn in (marketdata.latest_treasury_curve, marketdata.latest_sofr, marketdata.treasury_5y_history):
        with pytest.raises(ApiError) as e:
            fn(path)
        _conflict(e, "inutilizable")


def test_not_a_sqlite_file_is_409(tmp_path):
    path = tmp_path / "texto.db"
    path.write_text("esto no es sqlite " * 100)
    with pytest.raises(ApiError) as e:
        marketdata.latest_treasury_curve(path)
    _conflict(e, "inutilizable")


def test_reads_never_modify_the_database(tmp_path):
    db = make_mdf_db(tmp_path / "mdf.db", history_5y=_history(100))
    before = db.read_bytes()
    marketdata.latest_treasury_curve(db)
    marketdata.latest_sofr(db)
    marketdata.treasury_5y_history(db)
    assert db.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["mdf.db"]


def test_latest_sofr(tmp_path):
    db = make_mdf_db(tmp_path / "mdf.db", sofr=(("2026-11-06", 3.90), ("2026-11-09", 3.88)))
    sofr = marketdata.latest_sofr(db)
    assert sofr["date"] == "2026-11-09"
    assert sofr["rate"] == pytest.approx(0.0388)


def test_latest_sofr_without_rows_is_409(tmp_path):
    db = make_mdf_db(tmp_path / "mdf.db", sofr=())
    with pytest.raises(ApiError) as e:
        marketdata.latest_sofr(db)
    assert e.value.status == 409


def test_history_300_returns_last_251_ascending_in_decimal(tmp_path):
    hist = _history(300)
    db = make_mdf_db(tmp_path / "mdf.db", history_5y=hist)
    out = marketdata.treasury_5y_history(db)
    assert len(out) == 251
    assert [d for d, _ in out] == [d for d, _ in hist[-251:]]
    assert [d for d, _ in out] == sorted(d for d, _ in out)
    assert [r for _, r in out] == pytest.approx([r / 100.0 for _, r in hist[-251:]])
    assert out[-1][0] == "2026-11-10"


@pytest.mark.parametrize("n", [100, 61])
def test_history_below_the_window_returns_all(tmp_path, n):
    # La curva del 2026-11-10 aporta su propia 5Y: el historial termina un día antes y suma n - 1 filas.
    hist = _history(n - 1, end="2026-11-09")
    db = make_mdf_db(tmp_path / "mdf.db", history_5y=hist)
    out = marketdata.treasury_5y_history(db)
    assert len(out) == n
    assert out[-1] == ("2026-11-10", pytest.approx(0.0481))
    assert out[0][0] == hist[0][0]


def test_history_with_60_observations_is_409(tmp_path):
    db = make_mdf_db(tmp_path / "mdf.db", history_5y=_history(60))
    with pytest.raises(ApiError) as e:
        marketdata.treasury_5y_history(db)
    _conflict(e, "Historia insuficiente: 59 cambios diarios de 5Y (mínimo 60)")


def test_history_with_a_single_observation_is_409(tmp_path):
    db = make_mdf_db(tmp_path / "mdf.db")
    with pytest.raises(ApiError) as e:
        marketdata.treasury_5y_history(db)
    _conflict(e, "Historia insuficiente: 0 cambios diarios de 5Y (mínimo 60)")
