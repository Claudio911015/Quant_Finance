"""Ejemplos verificables del capítulo 7 (cross currency swap USDMXN).

Insumos del texto: tres curvas planas en tasa cero continua (SOFR 4.00 %, TIIE-F 7.00 %, MXN-USD 6.80 %),
spot 18.60, nocional 10 millones de USD y tipo de cambio pactado 18.50; y, para el cierre con la calibración,
el snapshot sintético MX-DEMO sembrado en una base temporal (nunca desk/data/desk.db). El valor sale de
`qfpy.XccySwap` y del pricer del backend; las fórmulas del texto se recalculan a mano solo como control.
"""
import math
import os
import tempfile

import comun  # primero: arregla sys.path
from desk.api import db, market, seed_market
from desk.api.pricing import PRODUCTS
from desk.api.qf import qfpy

NU, FX, SPOT = 10_000_000.0, 18.50, 18.60
NM = NU * FX
TAU = 28 / 360.0  # ACT/360 de un periodo de 28 días


def plana(z):
    return qfpy.YieldCurve([0.05, 2.0], [z, z], qfpy.InterpolationMethod.Linear)


def df(z, dias):
    return math.exp(-z * dias / 365.0)


env = qfpy.MarketEnvironment()
env.add_curve("SOFR", plana(0.04))
env.add_curve("TIIE-F", plana(0.07))
env.add_curve("MXN-USD", plana(0.068))
env.set_spot("USDMXN", SPOT)
PAGA_USD, PAGA_MXN = qfpy.XccySide.PayUsd, qfpy.XccySide.PayMxn


def swap(spread, inicio, pagos, fa_usd, fa_mxn, lado=PAGA_USD):
    """XccySwap con ambos intercambios de nocional; USD en SOFR, MXN proyectado en TIIE-F y descontado en MXN-USD."""
    return qfpy.XccySwap(NU, FX, spread, inicio, pagos, fa_usd, fa_mxn, lado, True, True)


# --- swap nuevo de tres periodos de 28 días ---
pagos = [28, 56, 84]
suma_pd = sum(df(0.068, d) for d in pagos)
nucleo = -1.0 + (math.exp(0.07 * 28 / 365.0) - 1.0) * suma_pd + df(0.068, 84)  # valor de la pata MXN con spread 0, por NM
par_mano = -nucleo / (TAU * suma_pd)
par = swap(0.0, 0, pagos, 1.0, 1.0).par_spread(env)
assert abs(par - par_mano) < 1e-12
comun.comprobar("cap07-spread-par", par, 1e-9)

s = -0.0010
con_spread = swap(s, 0, pagos, 1.0, 1.0)
assert abs(con_spread.npv(env) - NM * TAU * suma_pd * (s - par_mano)) < 1e-6  # lineal en el spread
comun.comprobar("cap07-pv-spread", con_spread.npv(env), 1e-3)
assert abs(con_spread.npv(env) + swap(s, 0, pagos, 1.0, 1.0, PAGA_MXN).npv(env)) < 1e-6  # lados opuestos
cupon_mxn = [c.amount for c in con_spread.cash_flows(env) if c.leg == "MXN" and c.kind == "coupon"][0]
assert abs(cupon_mxn - NM * (math.exp(0.07 * 28 / 365.0) - 1.0 + s * TAU)) < 1e-6
comun.comprobar("cap07-cupon-mxn", cupon_mxn, 1e-3)

# --- el mismo swap envejecido 10 días: periodo en curso con factores acumulados ---
au, am = 1.0 + 0.04 * 10 / 360.0, 1.0 + 0.07 * 10 / 360.0
dias = [18, 46, 74]
pp, pd = (lambda d: df(0.07, d)), (lambda d: df(0.068, d))
pata_mxn = ((am / pp(18) - 1.0) * pd(18) + (pp(18) / pp(46) - 1.0) * pd(46)
            + (pp(46) / pp(74) - 1.0) * pd(74) + pd(74) + s * TAU * sum(pd(d) for d in dias))
envejecido = swap(s, -10, dias, au, am).npv(env)
assert abs(envejecido - (NM * pata_mxn - SPOT * NU * au)) < 1e-6  # la pata USD completa vale NU * au
comun.comprobar("cap07-pv-envejecido", envejecido, 1e-3)

# --- cierre con la calibración: en MX-DEMO el swap de 26, 39 y 65 periodos nace al diferencial cotizado ---
with tempfile.TemporaryDirectory() as tmp:
    conn = db.connect(os.path.join(tmp, "cap07.db"))
    try:
        db.init_schema(conn)
        seed_market.seed_market(conn)
        conn.commit()
        demo = market.load_context(conn, "MX-DEMO")
    finally:
        conn.close()
xccy = PRODUCTS["xccy_swap"]
for id_, periodos in (("cap07-spread-par-2a", 26), ("cap07-spread-par-3a", 39)):
    p = xccy.validate({"side": "pay_usd", "notional_usd": 5e6, "periods": periodos, "exchange": "both"})
    r = xccy.price(p, demo)
    comun.comprobar(id_, r["risk"]["par_spread"], 1e-7)
    assert abs(r["pv"]) < 1e-6 and abs(r["risk"]["dv01_tiie"]) < 1e-6 and abs(r["risk"]["dv01_sofr"]) < 1e-6
    if periodos == 26:  # swap de 2 años, 5 millones de USD: todo el DV01 de tasa cae en MXN-USD
        comun.comprobar("cap07-dv01-mxn-usd", r["risk"]["dv01_mxn_usd"], 1e-3)
comun.terminar()
