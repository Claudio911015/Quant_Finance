"""
example_live.py — Demostración del feed de datos reales + pricing con qfpy.

Descarga curva del Tesoro US (FRED) y datos de equity (AAPL, SPY)
y precio una call europea sobre AAPL con datos en vivo.

Uso:
    python3 python/example_live.py
"""

import sys
import os

_BUILD = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "build", "src"))
if _BUILD not in sys.path:
    sys.path.insert(0, _BUILD)

import qfpy
from market_feed import MarketEnvironmentBuilder, env_summary

# ── 1. Construir el MarketEnvironment con datos reales ────────────────────────

env = (MarketEnvironmentBuilder()
       .use_fred_curve()
       .add_equity("AAPL")
       .add_equity("SPY")
       .build(verbose=True))

env_summary(env, ["AAPL", "SPY"])

# ── 2. Precio una call AAPL ATM a 1 mes con Black-Scholes ────────────────────

spot = env.spot("AAPL")
iv   = env.volatility("AAPL")
r    = env.curve("default").zero_rate(1.0)   # tasa a 1Y como proxy r_f
T    = 30 / 365.0                             # ~1 mes

params = qfpy.OptionParams()
params.spot        = spot
params.strike      = round(spot, 0)           # ATM (strike redondeado)
params.riskFreeRate = r
params.dividendYield = 0.0
params.volatility  = iv
params.maturity    = T
params.type        = qfpy.OptionType.Call

result = qfpy.black_scholes(params)  # returns dict with price/delta/gamma/vega/theta/rho

print("── AAPL Call ATM 30d (Black-Scholes) ─────────────────────")
print(f"  Spot:      {spot:>10.2f}")
print(f"  Strike:    {params.strike:>10.2f}")
print(f"  IV:        {iv*100:>10.2f}%")
print(f"  r (1Y):    {r*100:>10.3f}%")
print(f"  T:         {T:>10.4f}  ({T*365:.0f} días)")
print(f"  Price:     {result['price']:>10.4f}")
print(f"  Delta:     {result['delta']:>10.4f}")
print(f"  Gamma:     {result['gamma']:>10.6f}")
print(f"  Vega:      {result['vega']:>10.4f}  (por 1% de vol)")
print(f"  Theta:     {result['theta']:>10.4f}  (por día calendario)")
print()

# ── 3. Engine-based: mismo resultado vía EngineFactory ───────────────────────

engine = qfpy.EngineFactory.make_equity_engine("BS", params, ticker="AAPL")
price_from_env = engine.price(env)
print(f"  Precio vía EngineFactory(env):      {price_from_env:.4f}")
print(f"  Diferencia vs resultado directo:    {abs(price_from_env - result['price']):.2e}")
print()
