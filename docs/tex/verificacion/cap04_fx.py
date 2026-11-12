"""Ejemplos verificables del capítulo 4 (derivados de FX y opción sobre acción).

Los insumos son los del texto: curvas de dos pilares y superficie de 2 x 3 construidas aquí, el snapshot
sintético MX-DEMO sembrado en una base temporal (nunca desk/data/desk.db) y la opción sobre acción del
pricer del backend. Cada valor se obtiene llamando al código del proyecto; las fórmulas del texto se
recalculan a mano solo para comprobar que el texto y el código dicen lo mismo.
"""
import math
import os
import tempfile

import comun  # primero: arregla sys.path
from desk.api import db, market, seed_market
from desk.api.pricing import PRODUCTS
from desk.api.qf import qfpy

LINEAL = qfpy.InterpolationMethod.Linear


def ncdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def entorno():
    """Entorno del texto: TIIE-F y SOFR de dos pilares (tasa cero continua), spot 18.60 y superficie 2 x 3."""
    env = qfpy.MarketEnvironment()
    env.add_curve("TIIE-F", qfpy.YieldCurve([0.5, 1.0], [0.0900, 0.0920], LINEAL))
    env.add_curve("SOFR", qfpy.YieldCurve([0.5, 1.0], [0.0420, 0.0410], LINEAL))
    env.set_spot("USDMXN", 18.60)
    env.set_vol_surface("USDMXN", superficie())
    return env


def superficie():
    return qfpy.VolSurface([0.25, 0.5], [18.0, 19.0, 20.0],
                           [[0.130, 0.120, 0.125], [0.135, 0.125, 0.130]], LINEAL)


def contexto_demo():
    """MarketContext de MX-DEMO (sintético) desde una base SQLite temporal."""
    with tempfile.TemporaryDirectory() as tmp:
        conn = db.connect(os.path.join(tmp, "cap04.db"))
        try:
            db.init_schema(conn)
            seed_market.seed_market(conn)
            conn.commit()
            return market.load_context(conn, "MX-DEMO")
        finally:
            conn.close()


env = entorno()

# --- forward: paridad cubierta con las curvas TIIE-F (MXN) y SOFR (USD) ---
fwd_1a = qfpy.FxForward(1e6, 19.0, 365, qfpy.FxSide.Buy)
mano = 18.60 * math.exp(-0.0410) / math.exp(-0.0920)
assert abs(fwd_1a.forward_rate(env) - mano) < 1e-12
comun.comprobar("cap04-fwd-1a", fwd_1a.forward_rate(env), 1e-9)

T = 273 / 365.0
zd, zf = 0.0900 + 0.0020 * (T - 0.5) / 0.5, 0.0420 - 0.0010 * (T - 0.5) / 0.5  # interpolación lineal del texto
mano = 1e6 * (18.60 * math.exp(-zf * T) - 19.0 * math.exp(-zd * T))
pv_273 = qfpy.FxForward(1e6, 19.0, 273, qfpy.FxSide.Buy).npv(env)
assert abs(pv_273 - mano) < 1e-6
comun.comprobar("cap04-fwd-pv-273", pv_273, 1e-3)

# --- superficie: suavizada en strike y varianza total lineal en plazo ---
vol = superficie().vol(18.5, 0.375)
mano = math.sqrt((0.125 ** 2 * 0.25 + 0.130 ** 2 * 0.5) / 2.0 / 0.375)
assert abs(vol - mano) < 1e-12
comun.comprobar("cap04-vol-superficie", vol, 1e-9)
# extrapolación: plana en strike, plana en volatilidad antes del primer plazo (ancla w = 0 en T = 0) y después del último
sup = superficie()
assert abs(sup.vol(18.5, 0.125) - 0.125) < 1e-15 and abs(sup.vol(18.5, 0.7) - 0.130) < 1e-15
assert abs(sup.vol(17.0, 0.5) - 0.135) < 1e-15 and abs(sup.vol(21.0, 0.25) - 0.125) < 1e-15

# --- opción FX: Garman-Kohlhagen con la sigma de la superficie en (K, T) ---
T = 182 / 365.0
opcion = qfpy.FxOption(1e6, 19.0, 182, qfpy.OptionType.Call, qfpy.FxSide.Buy).greeks(env)
sigma = env.volatility("USDMXN", 19.0, T)
d1 = (math.log(18.60 / 19.0) + (0.0900 - 0.0420 + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
d2 = d1 - sigma * math.sqrt(T)
prima = 18.60 * math.exp(-0.0420 * T) * ncdf(d1) - 19.0 * math.exp(-0.0900 * T) * ncdf(d2)
assert abs(opcion.price - 1e6 * prima) < 1e-6 and abs(opcion.vol - sigma) < 1e-15
comun.comprobar("cap04-gk-sigma", sigma, 1e-9)
comun.comprobar("cap04-gk-prima", opcion.price, 1e-3)
comun.comprobar("cap04-gk-vega", opcion.vega, 1e-3)
comun.comprobar("cap04-gk-delta", opcion.delta, 1e-3)

# --- opción sobre acción: Black-Scholes del pricer del backend (10 títulos, call) ---
acc = PRODUCTS["equity_option"]
res = acc.price(acc.validate({"option_type": "call", "spot": 100.0, "strike": 105.0, "volatility": 0.25,
                              "rate": 0.07, "dividend_yield": 0.02, "maturity_years": 0.5, "quantity": 10}), None)
comun.comprobar("cap04-bs-pv", res["pv"], 1e-9)
comun.comprobar("cap04-bs-delta", res["risk"]["delta"], 1e-9)

# --- MX-DEMO: forward implícito de MXN-USD y el mismo forward con colateral MXN o USD ---
demo = contexto_demo()
implicito = qfpy.FxForward(1.0, 1.0, 168, qfpy.FxSide.Buy, "USDMXN", "MXN-USD").forward_rate(demo.env)
comun.comprobar("cap04-fwd-implicito", implicito, 1e-7)  # spot 18.60 + puntos 0.2637 cotizados a 168 d
fwd = PRODUCTS["fx_forward"]
params = fwd.validate({"side": "buy", "notional_usd": 1e6, "strike": 19.0, "days": 182})
for lado, id_ in (("MXN", "mxn"), ("USD", "usd")):
    r = fwd.price(params, demo.with_collateral(lado))
    comun.comprobar("cap04-fwd-pv-" + id_, r["pv"], 1e-3)
    comun.comprobar("cap04-fwd-" + id_, r["risk"]["forward"], 1e-7)
comun.terminar()
