import sys
import types
import math
import pytest
from unittest.mock import MagicMock, patch

# ── Stub qfpy antes de importar market_feed ──────────────────────────────────
# market_feed importa qfpy (C++ extension) al nivel de módulo.
# Creamos un stub mínimo para que los tests corran sin compilar C++.

_qfpy_stub = types.ModuleType("qfpy")


class _YieldCurve:
    def __init__(self, maturities, rates, interp=None):
        self.maturities = maturities
        self.rates = rates

    def zero_rate(self, T):
        # Interpolación lineal simple para tests
        if not self.maturities:
            return 0.05
        if T <= self.maturities[0]:
            return self.rates[0]
        if T >= self.maturities[-1]:
            return self.rates[-1]
        for i in range(len(self.maturities) - 1):
            t0, t1 = self.maturities[i], self.maturities[i + 1]
            if t0 <= T <= t1:
                frac = (T - t0) / (t1 - t0)
                return self.rates[i] + frac * (self.rates[i + 1] - self.rates[i])
        return self.rates[0]

    def discount_factor(self, T):
        return math.exp(-self.zero_rate(T) * T)


class _MarketEnvironment:
    def __init__(self):
        self._curves = {}
        self._spots = {}
        self._vols = {}

    def add_curve(self, name, curve):
        self._curves[name] = curve

    def set_spot(self, ticker, spot):
        self._spots[ticker] = spot

    def set_volatility(self, ticker, vol):
        self._vols[ticker] = vol

    def spot(self, ticker):
        return self._spots[ticker]

    def volatility(self, ticker):
        return self._vols[ticker]

    def curve(self, name):
        return self._curves[name]


_qfpy_stub.YieldCurve = _YieldCurve
_qfpy_stub.MarketEnvironment = _MarketEnvironment
_qfpy_stub.CubicSpline = "cubic"
_qfpy_stub.Linear = "linear"
sys.modules["qfpy"] = _qfpy_stub

# ── Stub yfinance y requests (no instalados en pyfinance) ────────────────────
_yf_stub = types.ModuleType("yfinance")
_yf_stub.download = MagicMock()
_yf_stub.Ticker = MagicMock()
sys.modules["yfinance"] = _yf_stub

_requests_stub = types.ModuleType("requests")
_requests_stub.get = MagicMock()
sys.modules["requests"] = _requests_stub

# Ahora importar el módulo bajo test
sys.path.insert(0, "/home/claudio/Git/Quant_Finance/python")
import market_feed  # noqa: E402
from market_feed import _yf_last_close  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_yf_df(value: float):
    """Fabricar un DataFrame mínimo que simula yf.download output."""
    import pandas as pd
    idx = pd.DatetimeIndex(["2026-06-05", "2026-06-06"])
    close = pd.DataFrame({"Close": [value - 1, value]}, index=idx)
    return close


# ─────────────────────────────────────────────────────────────────────────────
# Task 2: Tests para _yf_last_close
# ─────────────────────────────────────────────────────────────────────────────

def test_yf_last_close_returns_last_value():
    with patch("market_feed.yf.download", return_value=_make_yf_df(150.0)) as mock_dl:
        result = _yf_last_close("^TNX")
    assert result == pytest.approx(150.0)
    mock_dl.assert_called_once_with("^TNX", period="5d", progress=False, auto_adjust=True)


def test_yf_last_close_returns_none_on_empty():
    import pandas as pd
    with patch("market_feed.yf.download", return_value=pd.DataFrame()):
        result = _yf_last_close("^MISSING")
    assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Task 3: Tests para fetch_treasury_curve_yfinance
# ─────────────────────────────────────────────────────────────────────────────

from market_feed import fetch_treasury_curve_yfinance  # noqa: E402


def test_fetch_treasury_curve_yf_returns_yield_curve():
    def fake_download(ticker, **kwargs):
        return _make_yf_df(4.5)  # 4.5% yield para todos

    with patch("market_feed.yf.download", side_effect=fake_download):
        curve = fetch_treasury_curve_yfinance()

    assert isinstance(curve, _YieldCurve)
    assert len(curve.maturities) >= 2
    # rates deben ser decimales (~0.045), no porcentaje (~4.5)
    for r in curve.rates:
        assert r < 1.0, f"rate {r} parece estar en porcentaje, no decimal"


def test_fetch_treasury_curve_yf_raises_on_no_data():
    import pandas as pd
    with patch("market_feed.yf.download", return_value=pd.DataFrame()):
        with pytest.raises(RuntimeError, match="no se pudieron obtener"):
            fetch_treasury_curve_yfinance()


# ─────────────────────────────────────────────────────────────────────────────
# Task 4: Tests para fetch_treasury_curve_fred
# ─────────────────────────────────────────────────────────────────────────────

from market_feed import fetch_treasury_curve_fred  # noqa: E402


def _make_fred_response(rate_pct: float = 4.50) -> MagicMock:
    """Simula una respuesta CSV de FRED con una sola fila de datos."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.text = f"DATE,VALUE\n2026-06-06,{rate_pct}"
    return mock_resp


def test_fetch_treasury_curve_fred_returns_yield_curve():
    with patch("market_feed.requests.get", return_value=_make_fred_response(4.50)):
        curve = fetch_treasury_curve_fred()

    assert isinstance(curve, _YieldCurve)
    assert len(curve.maturities) >= 2
    # Tasas convertidas a continua: log(1 + 0.045) ≈ 0.0440
    for r in curve.rates:
        assert 0.0 < r < 0.15, f"rate {r} fuera de rango razonable"


def test_fetch_treasury_curve_fred_raises_on_no_data():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.text = "DATE,VALUE\n"

    with patch("market_feed.requests.get", return_value=mock_resp):
        with pytest.raises(RuntimeError, match="datos insuficientes"):
            fetch_treasury_curve_fred()


# ─────────────────────────────────────────────────────────────────────────────
# Task 5: Tests para MarketEnvironmentBuilder
# ─────────────────────────────────────────────────────────────────────────────

from market_feed import MarketEnvironmentBuilder  # noqa: E402


def test_builder_flat_curve_no_network():
    """Builder con curva plana y spots manuales — cero llamadas a red."""
    env = (
        MarketEnvironmentBuilder()
        .use_flat_curve(0.05)
        .set_spot("AAPL", 180.0)
        .set_vol("AAPL", 0.25)
        .build(verbose=False)
    )
    assert env.spot("AAPL") == pytest.approx(180.0)
    assert env.volatility("AAPL") == pytest.approx(0.25)


def test_builder_flat_curve_rate_is_correct():
    env = (
        MarketEnvironmentBuilder()
        .use_flat_curve(0.04)
        .build(verbose=False)
    )
    curve = env.curve("default")
    assert curve.zero_rate(1.0) == pytest.approx(0.04, abs=1e-6)
    assert curve.zero_rate(10.0) == pytest.approx(0.04, abs=1e-6)


def test_builder_add_equity_calls_fetch(monkeypatch):
    monkeypatch.setattr("market_feed.fetch_equity", lambda t: (200.0, 0.30))
    env = (
        MarketEnvironmentBuilder()
        .use_flat_curve(0.05)
        .add_equity("MSFT")
        .build(verbose=False)
    )
    assert env.spot("MSFT") == pytest.approx(200.0)
    assert env.volatility("MSFT") == pytest.approx(0.30)


def test_builder_manual_spot_overrides_fetched(monkeypatch):
    monkeypatch.setattr("market_feed.fetch_equity", lambda t: (200.0, 0.30))
    env = (
        MarketEnvironmentBuilder()
        .use_flat_curve(0.05)
        .add_equity("MSFT")
        .set_spot("MSFT", 999.0)
        .build(verbose=False)
    )
    assert env.spot("MSFT") == pytest.approx(999.0)
