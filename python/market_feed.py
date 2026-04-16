"""
market_feed.py — Feeds de datos reales hacia qf::core::MarketEnvironment.

Fuentes:
  - Equity spot + vol implícita: yfinance (Yahoo Finance, gratuito, EOD)
  - Curva de tasas US Treasuries: yfinance tickers ^IRX/^FVX/^TNX/^TYX
    o FRED API (gratuita, sin key para series públicas)

Uso básico:
    from market_feed import MarketEnvironmentBuilder
    env = MarketEnvironmentBuilder().add_equity("AAPL").add_equity("MSFT").build()

Uso con curva FRED:
    env = MarketEnvironmentBuilder().use_fred_curve().add_equity("SPY").build()
"""

import sys
import os
import warnings
from datetime import datetime, timedelta
from typing import Optional, Tuple

import numpy as np
import yfinance as yf
import requests

# -- Localiza qfpy.so (compilado en build/src/) --
_BUILD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "build", "src"))
if _BUILD not in sys.path:
    sys.path.insert(0, _BUILD)
import qfpy                                          # noqa: E402  (local C++ extension)


# ─────────────────────────────────────────────────────────────────────────────
# Curva de tasas
# ─────────────────────────────────────────────────────────────────────────────

# Tickers de Yahoo Finance para Treasury yields (en porcentaje anual)
_TREASURY_TICKERS = {
    0.25:  "^IRX",   # 13-week T-Bill
    2.0:   "^TYX",   # proxy; YF no tiene 2Y directamente
    5.0:   "^FVX",   # 5-year
    10.0:  "^TNX",   # 10-year
    30.0:  "^TYX",   # 30-year
}

# Maturities y series FRED para la curva del Tesoro US (tasas spot, base cc)
_FRED_SERIES = {
    0.25:  "DGS3MO",
    0.5:   "DGS6MO",
    1.0:   "DGS1",
    2.0:   "DGS2",
    3.0:   "DGS3",
    5.0:   "DGS5",
    7.0:   "DGS7",
    10.0:  "DGS10",
    20.0:  "DGS20",
    30.0:  "DGS30",
}


def _yf_last_close(ticker: str) -> Optional[float]:
    """Obtiene el último precio de cierre usando yfinance 1.x (MultiIndex DataFrame)."""
    hist = yf.download(ticker, period="5d", progress=False, auto_adjust=True)
    if hist.empty:
        return None
    close = hist["Close"]
    # yfinance 1.x: Close es DataFrame con columna (ticker,); extraer como Series
    if hasattr(close, "squeeze"):
        close = close.squeeze()
    vals = close.dropna()
    return float(vals.iloc[-1]) if not vals.empty else None


def fetch_treasury_curve_yfinance() -> qfpy.YieldCurve:
    """
    Descarga yields del Tesoro US vía Yahoo Finance y construye una YieldCurve.
    Tasas en formato Yahoo (porcentaje), convertidas a decimal.
    """
    maturities, rates = [], []
    for T, ticker in sorted(_TREASURY_TICKERS.items()):
        try:
            rate = _yf_last_close(ticker)
            if rate is None:
                continue
            maturities.append(T)
            rates.append(rate / 100.0)   # % → decimal
        except Exception as e:
            warnings.warn(f"Treasury ticker {ticker} (T={T}y): {e}")

    if len(maturities) < 2:
        raise RuntimeError("fetch_treasury_curve_yfinance: no se pudieron obtener tasas suficientes")

    # Dedup (30Y aparece dos veces en el dict)
    seen = {}
    for T, r in zip(maturities, rates):
        seen[T] = r
    maturities = sorted(seen.keys())
    rates = [seen[T] for T in maturities]

    return qfpy.YieldCurve(maturities, rates, qfpy.CubicSpline)


def fetch_treasury_curve_fred() -> qfpy.YieldCurve:
    """
    Descarga la curva del Tesoro US desde FRED (Federal Reserve Bank of St. Louis).
    No requiere API key para series públicas.
    Tasas en base anual continua (FRED reporta en base ACT/365 discreta;
    convertimos: r_cc = log(1 + r_discrete)).
    """
    base_url = "https://fred.stlouisfed.org/graph/fredgraph.csv"
    today = datetime.today().strftime("%Y-%m-%d")
    start = (datetime.today() - timedelta(days=10)).strftime("%Y-%m-%d")

    maturities, rates = [], []
    for T, series in sorted(_FRED_SERIES.items()):
        try:
            url = f"{base_url}?id={series}&vintage_date={today}"
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            lines = [l for l in resp.text.strip().split("\n") if not l.startswith("DATE")]
            if not lines:
                continue
            # Tomar el último valor no vacío
            for line in reversed(lines):
                parts = line.split(",")
                if len(parts) == 2 and parts[1].strip() not in (".", ""):
                    rate_pct = float(parts[1].strip())
                    rate_cc = np.log(1.0 + rate_pct / 100.0)  # discreta → continua
                    maturities.append(T)
                    rates.append(rate_cc)
                    break
        except Exception as e:
            warnings.warn(f"FRED series {series} (T={T}y): {e}")

    if len(maturities) < 2:
        raise RuntimeError("fetch_treasury_curve_fred: datos insuficientes de FRED")

    return qfpy.YieldCurve(maturities, rates, qfpy.CubicSpline)


# ─────────────────────────────────────────────────────────────────────────────
# Equity: spot + vol implícita ATM
# ─────────────────────────────────────────────────────────────────────────────

def fetch_equity(ticker: str,
                 target_expiry_days: int = 30
                 ) -> Tuple[float, float]:
    """
    Devuelve (spot, atm_iv) para el ticker dado.

    La vol implícita ATM se estima como la media de call y put ATM
    en el vencimiento más cercano a `target_expiry_days` días.
    Si el chain de opciones no está disponible, vol = None y se
    devuelve la volatilidad histórica de 30 días como fallback.

    Returns:
        (spot: float, iv: float)  — spot en USD, iv en decimal (0.25 = 25%)
    """
    tk = yf.Ticker(ticker)

    # Spot — fast_info.previous_close es robusto; fallback a download histórico
    info = tk.fast_info
    spot = getattr(info, "previous_close", None) or getattr(info, "regular_market_previous_close", None)
    if spot is None:
        spot = _yf_last_close(ticker)
    if spot is None:
        raise RuntimeError(f"fetch_equity: no se pudo obtener spot para {ticker}")

    # Vol implícita ATM — intento desde chain de opciones
    iv = None
    try:
        exps = tk.options                          # lista de fechas de expiración
        if exps:
            # Elegir el vencimiento más cercano al target
            today = datetime.today()
            best_exp = min(
                exps,
                key=lambda e: abs((datetime.strptime(e, "%Y-%m-%d") - today).days
                                  - target_expiry_days)
            )
            chain = tk.option_chain(best_exp)
            calls = chain.calls
            puts  = chain.puts

            # ATM = strike más cercano al spot
            atm_call = calls.iloc[(calls["strike"] - spot).abs().argsort()[:1]]
            atm_put  = puts.iloc[(puts["strike"] - spot).abs().argsort()[:1]]

            iv_c = float(atm_call["impliedVolatility"].values[0])
            iv_p = float(atm_put["impliedVolatility"].values[0])
            iv = (iv_c + iv_p) / 2.0
    except Exception as e:
        warnings.warn(f"{ticker}: no se pudo obtener IV de opciones ({e}), usando HV30")

    # Fallback: volatilidad histórica de 30 días
    if iv is None or iv <= 0.0:
        hist = yf.download(ticker, period="60d", progress=False, auto_adjust=True)
        close = hist["Close"].squeeze()   # yfinance 1.x MultiIndex → Series
        log_ret = np.log(close / close.shift(1)).dropna()
        iv = float(log_ret.std() * np.sqrt(252))

    return float(spot), float(iv)


# ─────────────────────────────────────────────────────────────────────────────
# Builder
# ─────────────────────────────────────────────────────────────────────────────

class MarketEnvironmentBuilder:
    """
    Construye un qfpy.MarketEnvironment listo para usar con los pricing engines.

    Ejemplo:
        env = (MarketEnvironmentBuilder()
               .use_fred_curve()
               .add_equity("AAPL")
               .add_equity("MSFT")
               .build())
        print(env.spot("AAPL"))

    Métodos encadenables:
        .use_yf_curve()     — Curva del Tesoro desde Yahoo Finance (default)
        .use_fred_curve()   — Curva del Tesoro desde FRED
        .use_flat_curve(r)  — Curva plana a tasa r (decimal)
        .add_equity(ticker) — Descarga spot + IV ATM vía yfinance
        .set_spot(t, s)     — Spot manual
        .set_vol(t, v)      — Vol manual
        .build()            — Devuelve el MarketEnvironment poblado
    """

    def __init__(self):
        self._curve_fn = self._build_yf_curve
        self._flat_rate: Optional[float] = None
        self._equities: list[str] = []
        self._manual_spots: dict[str, float] = {}
        self._manual_vols: dict[str, float] = {}

    def use_yf_curve(self) -> "MarketEnvironmentBuilder":
        self._curve_fn = self._build_yf_curve
        return self

    def use_fred_curve(self) -> "MarketEnvironmentBuilder":
        self._curve_fn = self._build_fred_curve
        return self

    def use_flat_curve(self, rate: float) -> "MarketEnvironmentBuilder":
        self._flat_rate = rate
        self._curve_fn = self._build_flat_curve
        return self

    def add_equity(self, ticker: str) -> "MarketEnvironmentBuilder":
        self._equities.append(ticker.upper())
        return self

    def set_spot(self, ticker: str, spot: float) -> "MarketEnvironmentBuilder":
        self._manual_spots[ticker.upper()] = spot
        return self

    def set_vol(self, ticker: str, vol: float) -> "MarketEnvironmentBuilder":
        self._manual_vols[ticker.upper()] = vol
        return self

    # -- internos --

    def _build_yf_curve(self) -> qfpy.YieldCurve:
        return fetch_treasury_curve_yfinance()

    def _build_fred_curve(self) -> qfpy.YieldCurve:
        return fetch_treasury_curve_fred()

    def _build_flat_curve(self) -> qfpy.YieldCurve:
        r = self._flat_rate
        ts = [0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
        return qfpy.YieldCurve(ts, [r] * len(ts), qfpy.Linear)

    def build(self, verbose: bool = True) -> qfpy.MarketEnvironment:
        """
        Descarga datos y devuelve el MarketEnvironment.

        Args:
            verbose: Si True, imprime un resumen de los datos cargados.
        """
        env = qfpy.MarketEnvironment()

        # Curva de tasas
        if verbose:
            print("Descargando curva de tasas...", end=" ", flush=True)
        curve = self._curve_fn()
        env.add_curve("default", curve)
        if verbose:
            rates_str = ", ".join(
                f"{T}Y={curve.zero_rate(T)*100:.2f}%"
                for T in [1.0, 5.0, 10.0]
                if True
            )
            print(f"OK ({rates_str})")

        # Equities desde yfinance
        for ticker in self._equities:
            if verbose:
                print(f"  {ticker}: descargando spot + IV...", end=" ", flush=True)
            try:
                spot, iv = fetch_equity(ticker)
                env.set_spot(ticker, spot)
                env.set_volatility(ticker, iv)
                if verbose:
                    print(f"spot={spot:.2f}  IV={iv*100:.1f}%")
            except Exception as e:
                warnings.warn(f"{ticker}: {e}")

        # Datos manuales (sobreescriben los de yfinance)
        for ticker, spot in self._manual_spots.items():
            env.set_spot(ticker, spot)
        for ticker, vol in self._manual_vols.items():
            env.set_volatility(ticker, vol)

        return env


# ─────────────────────────────────────────────────────────────────────────────
# Utilidad: snapshot del environment
# ─────────────────────────────────────────────────────────────────────────────

def env_summary(env: qfpy.MarketEnvironment,
                tickers: list,
                curve_tenors: Optional[list] = None) -> None:
    """Imprime un resumen tabular del MarketEnvironment."""
    if curve_tenors is None:
        curve_tenors = [0.25, 1.0, 2.0, 5.0, 10.0, 30.0]

    print("\n── Yield Curve (default) ──────────────────")
    for T in curve_tenors:
        try:
            r = env.curve("default").zero_rate(T)    # type: ignore[attr-defined]
            df = env.curve("default").discount_factor(T)  # type: ignore[attr-defined]
            print(f"  {T:5.2f}Y  r={r*100:6.3f}%  df={df:.6f}")
        except Exception:
            pass

    print("\n── Equities ───────────────────────────────")
    for t in tickers:
        try:
            s = env.spot(t)
            v = env.volatility(t)
            print(f"  {t:<8}  spot={s:>10.2f}  IV={v*100:6.2f}%")
        except Exception:
            print(f"  {t:<8}  (no disponible)")
    print()
