# Quant_Finance: Tests para market_feed.py

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `market_feed.py` (`python/market_feed.py`) tiene cero tests — sus funciones son nodos aislados en el grafo. Añadir tests con mocks de red para cubrir `fetch_treasury_curve_yfinance`, `fetch_treasury_curve_fred`, `fetch_equity` y `MarketEnvironmentBuilder`.

**Architecture:** Nuevo archivo `python/tests/test_market_feed.py`. Los tests mockean `yfinance` y `requests` con `unittest.mock`/`pytest-mock` para no depender de red ni de `qfpy.so` (que requiere compilar C++). El builder se testa con una curva plana que no llama a APIs externas.

**Tech Stack:** pytest, pytest-mock, unittest.mock; Python en env `pyfinance` (`conda activate pyfinance`).

---

### Task 1: Setup — crear directorio de tests y verificar entorno

**Files:**
- Create: `python/tests/__init__.py`
- Create: `python/tests/test_market_feed.py` (vacío por ahora)

- [ ] **Step 1: Crear estructura**

```bash
cd /home/claudio/Git/Quant_Finance
mkdir -p python/tests
touch python/tests/__init__.py python/tests/test_market_feed.py
```

- [ ] **Step 2: Verificar que pytest corre (sin tests)**

```bash
conda run -n pyfinance pytest python/tests/ -v
```

Esperado: `no tests ran` o `0 passed`.

- [ ] **Step 3: Commit**

```bash
git add python/tests/
git commit -m "test: create python/tests/ scaffold for market_feed tests"
```

---

### Task 2: Tests para `_yf_last_close`

**Files:**
- Modify: `python/tests/test_market_feed.py`

- [ ] **Step 1: Escribir tests**

```python
# python/tests/test_market_feed.py
import sys
import types
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
        return self.rates[0] if self.rates else 0.05
    def discount_factor(self, T):
        import math
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

# Ahora importar el módulo bajo test
sys.path.insert(0, "/home/claudio/Git/Quant_Finance/python")
from market_feed import _yf_last_close   # noqa: E402


def _make_yf_df(value: float):
    """Fabricar un DataFrame mínimo que simula yf.download output."""
    import pandas as pd
    import numpy as np
    idx = pd.DatetimeIndex(["2026-06-05", "2026-06-06"])
    close = pd.DataFrame({"Close": [value - 1, value]}, index=idx)
    return close


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
```

- [ ] **Step 2: Ejecutar**

```bash
conda run -n pyfinance pytest python/tests/test_market_feed.py::test_yf_last_close_returns_last_value python/tests/test_market_feed.py::test_yf_last_close_returns_none_on_empty -v
```

Esperado: 2 PASS.

- [ ] **Step 3: Commit**

```bash
git add python/tests/test_market_feed.py
git commit -m "test: _yf_last_close with yfinance mock"
```

---

### Task 3: Tests para `fetch_treasury_curve_yfinance`

**Files:**
- Modify: `python/tests/test_market_feed.py`

- [ ] **Step 1: Añadir tests al archivo existente**

```python
from market_feed import fetch_treasury_curve_yfinance


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
```

- [ ] **Step 2: Ejecutar**

```bash
conda run -n pyfinance pytest python/tests/test_market_feed.py -k "treasury_curve_yf" -v
```

Esperado: 2 PASS.

- [ ] **Step 3: Commit**

```bash
git add python/tests/test_market_feed.py
git commit -m "test: fetch_treasury_curve_yfinance with mocked yfinance"
```

---

### Task 4: Tests para `fetch_treasury_curve_fred`

**Files:**
- Modify: `python/tests/test_market_feed.py`

- [ ] **Step 1: Añadir tests**

```python
from market_feed import fetch_treasury_curve_fred


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
```

- [ ] **Step 2: Ejecutar**

```bash
conda run -n pyfinance pytest python/tests/test_market_feed.py -k "fred" -v
```

Esperado: 2 PASS.

- [ ] **Step 3: Commit**

```bash
git add python/tests/test_market_feed.py
git commit -m "test: fetch_treasury_curve_fred with mocked requests"
```

---

### Task 5: Tests para `MarketEnvironmentBuilder` con curva plana

**Files:**
- Modify: `python/tests/test_market_feed.py`

- [ ] **Step 1: Añadir tests**

```python
from market_feed import MarketEnvironmentBuilder


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
```

- [ ] **Step 2: Ejecutar todos los tests del archivo**

```bash
conda run -n pyfinance pytest python/tests/test_market_feed.py -v
```

Esperado: todos los tests pasan (mínimo 10).

- [ ] **Step 3: Commit + push**

```bash
git add python/tests/test_market_feed.py
git commit -m "test: MarketEnvironmentBuilder with flat curve and equity mocks"
git push
```
