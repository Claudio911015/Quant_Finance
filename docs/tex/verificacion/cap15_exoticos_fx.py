"""Ejemplos verificables del capítulo 15 (exóticos de FX: no touch y double no touch).

Insumos: el snapshot sintético MX-DEMO sembrado en una base temporal (nunca desk/data/desk.db), spot 18.60 y fecha
de valuación 2026-11-10. Cada valor sale del código del proyecto (desk.api.pricing.fx_exotics sobre QuantLib 1.42.1);
las fórmulas del texto (probabilidades de no tocar, serie de imágenes, Dupire, puente browniano) se recalculan a mano
solo para comprobar que el texto y el código dicen lo mismo. Las cifras de Monte Carlo usan la semilla y la malla del
módulo (fe.SEED, fe.STEPS); cambian si se cambian esas constantes.
"""
import math
import os
import tempfile
import types
from statistics import NormalDist

import comun  # primero: arregla sys.path
import numpy as np
import QuantLib as ql
from desk.api import db, market, seed_market
from desk.api.pricing import fx_exotics as fe

NT, DNT = "fx_no_touch", "fx_double_no_touch"


def contexto():
    """MarketContext de MX-DEMO (sintético) desde una base SQLite temporal."""
    with tempfile.TemporaryDirectory() as tmp:
        conn = db.connect(os.path.join(tmp, "cap15.db"))
        try:
            db.init_schema(conn)
            seed_market.seed_market(conn)
            conn.commit()
            return market.load_context(conn, "MX-DEMO")
        finally:
            conn.close()


mkt = contexto()
X0 = mkt.spot


def validar(nombre, **kw):
    base = {"side": "buy", "payout_mxn": 1e6, "days": 91, "model": "flat"}
    base.update(kw)
    return fe.PRODUCTS[nombre].validate(base)


def ncdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def no_toca(S, H, T, rd, rf, sig, arriba):
    """Probabilidad de no tocar una barrera (reflexión con deriva), a mano."""
    nu, s = rd - rf - 0.5 * sig ** 2, sig * math.sqrt(T)
    if arriba:
        b = math.log(H / S)
        return ncdf((b - nu * T) / s) - math.exp(2 * nu * b / sig ** 2) * ncdf((-b - nu * T) / s)
    a = math.log(S / H)
    return ncdf((a + nu * T) / s) - math.exp(-2 * nu * a / sig ** 2) * ncdf((-a + nu * T) / s)


def no_toca_doble(S, L, U, T, rd, rf, sig, nmax=50):
    """Probabilidad de no salir de (L, U): serie de imágenes, a mano."""
    nu, s = rd - rf - 0.5 * sig ** 2, sig * math.sqrt(T)
    x0, l, u = math.log(S), math.log(L), math.log(U)
    w, tot = u - l, 0.0
    for n in range(-nmax, nmax + 1):
        a = math.exp(-2 * n * nu * w / sig ** 2) * (ncdf((u - x0 + 2 * n * w - nu * T) / s) - ncdf((l - x0 + 2 * n * w - nu * T) / s))
        b = math.exp(2 * nu * (l - x0 - n * w) / sig ** 2) * (ncdf((u - 2 * l + x0 + 2 * n * w - nu * T) / s) - ncdf((x0 - l + 2 * n * w - nu * T) / s))
        tot += a - b
    return tot


def tasas(proc, T):
    cero = lambda h: h.zeroRate(T, ql.Continuous, ql.NoFrequency).rate()
    return cero(proc.riskFreeRate()), cero(proc.dividendYield())


# --- curvas: la ZeroCurve de QuantLib reproduce los factores de descuento del desk ---
T91 = 91 / 365.0
p = validar(NT, barrier=19.5, barrier_type="up")
dom, proc, sigma, ks, tab = fe._build(p, mkt, X0, 0.0)
hoy = ql.Settings.instance().evaluationDate
df_d, df_f = mkt.curves["TIIE-F"].discount_factor(T91), mkt.curves["SOFR"].discount_factor(T91)
assert abs(dom.discount(hoy + 91) - df_d) < 1e-9 and abs(proc.dividendYield().discount(hoy + 91) - df_f) < 1e-9
comun.comprobar("cap15-df-mxn-91", df_d, 1e-9)
comun.comprobar("cap15-df-sofr-91", df_f, 1e-9)
rd, rf = tasas(proc, T91)
assert abs(rd + math.log(df_d) / T91) < 1e-12 and abs(rf + math.log(df_f) / T91) < 1e-12
comun.comprobar("cap15-tasa-mxn-91", rd, 1e-9)
comun.comprobar("cap15-tasa-sofr-91", rf, 1e-9)
comun.comprobar("cap15-vol-plana-91", sigma, 1e-9)  # mkt.surface.vol(X0, T) de qfpy
assert abs(sigma - mkt.surface.vol(X0, T91)) < 1e-15

# --- superficie bicúbica de QuantLib y volatilidad local de Dupire (a 365 días con sonrisa) ---
p365 = validar(NT, days=365, model="smile", barrier=20.5, barrier_type="up")
dom365, proc365, sigma365, ks365, tab365 = fe._build(p365, mkt, X0, 0.0)
sup = proc365.blackVolatility()
Tg, Kg, Vg = mkt.surface.to_grid()
assert abs(sup.blackVol(Tg[1], Kg[3]) - Vg[1][3]) < 1e-12  # pasa por los nodos de la rejilla
comun.comprobar("cap15-vol-qfpy-fuera-nodo", mkt.surface.vol(18.25, 0.3), 1e-9)
comun.comprobar("cap15-vol-bicubica-fuera-nodo", sup.blackVol(0.3, 18.25), 1e-9)


def dupire(t, K):
    """Fórmula de Dupire en varianza total (Gatheral), derivadas por diferencias finitas, a mano."""
    fwd = lambda tt: X0 * proc365.dividendYield().discount(tt, True) / proc365.riskFreeRate().discount(tt, True)
    W = lambda y, tt: sup.blackVariance(tt, fwd(tt) * math.exp(y), True)
    y = math.log(K / fwd(t))
    dy, dt = y * 1e-4, 1e-4
    w, wp, wm = W(y, t), W(y + dy, t), W(y - dy, t)
    dwdy, d2w = (wp - wm) / (2 * dy), (wp - 2 * w + wm) / dy ** 2
    dwdt = (W(y, t + dt) - W(y, t - dt)) / (2 * dt)
    den = 1 - y / w * dwdy + 0.25 * (-0.25 - 1 / w + y * y / w / w) * dwdy ** 2 + 0.5 * d2w
    return math.sqrt(dwdt / den)


T365, nodo = 1.0, 5  # nodo de tiempo t = 5 T / 10 = 0.5 años; fila 21 de la tabla = X0 exp(0.25 sigma sqrt(T))
K21, t5 = ks365[21], T365 * nodo / fe.STEPS
assert abs(K21 - X0 * math.exp(np.linspace(-5, 5, fe.LV_STRIKES)[21] * sigma365 * math.sqrt(T365))) < 1e-12
assert abs(tab365[21, nodo] - dupire(t5, K21)) < 1e-6
comun.comprobar("cap15-vol-local-nodo", tab365[21, nodo], 1e-9)

# --- números aleatorios y avance de la trayectoria: GaussianPathGenerator reproducido a mano con las mismas normales ---
u0 = ql.UniformRandomGenerator(fe.SEED).next().value()
crudo = int(np.random.RandomState(fe.SEED).randint(0, 2 ** 32, dtype=np.uint64))
assert abs(u0 - (crudo + 0.5) / 2 ** 32) < 1e-15  # Mersenne Twister MT19937, u = (entero de 32 bits + 0.5) / 2^32
comun.comprobar("cap15-semilla-u0", u0, 1e-9)


def generador():
    return ql.GaussianRandomSequenceGenerator(ql.UniformRandomSequenceGenerator(fe.STEPS, ql.UniformRandomGenerator(fe.SEED)))


rsg = generador()  # se conserva: el vector que devuelve nextSequence() pertenece al generador
Z = list(rsg.nextSequence().value())
assert abs(Z[0] - NormalDist().inv_cdf(u0)) < 1e-7  # z = inversa de la normal acumulada de u
comun.comprobar("cap15-semilla-z0", Z[0], 1e-9)


def reproducir(pr, T, sig_en, instantanea):
    """Trayectoria a mano: X_{i+1} = X_i exp{(f_d - f_f - sig^2/2) dt + sig sqrt(dt) Z_i}; f sobre [t, t+dt] (plano) o [t, t+1e-4]."""
    dt, x = T / fe.STEPS, [X0]
    for i in range(fe.STEPS):
        t, h = i * dt, (1e-4 if instantanea else dt)
        fw = lambda c: math.log(c.discount(t, True) / c.discount(t + h, True)) / h
        sg = sig_en(x[-1], i)
        x.append(x[-1] * math.exp((fw(pr.riskFreeRate()) - fw(pr.dividendYield()) - 0.5 * sg ** 2) * dt + sg * math.sqrt(dt) * Z[i]))
    return x


pg = ql.GaussianPathGenerator(proc, T91, fe.STEPS, generador(), False)
gen = list(pg.next().value())
assert max(abs(a - b) for a, b in zip(gen, reproducir(proc, T91, lambda x, i: sigma, False))) < 1e-9  # plano: exacto
pg = ql.GaussianPathGenerator(proc365, 1.0, fe.STEPS, generador(), False)
gen = list(pg.next().value())
assert max(abs(a - b) for a, b in zip(gen, reproducir(proc365, 1.0, lambda x, i: float(np.interp(x, ks365, tab365[:, i])), True))) < 1e-9
comun.comprobar("cap15-camino-x1", gen[1], 1e-8)  # primer paso con sonrisa a 365 días

# --- referencias analíticas de QuantLib frente a las fórmulas cerradas del texto ---
pa = validar(NT, barrier=19.5, barrier_type="up", method="analytic")
u_ql = fe._analytic(pa, proc) / dom.discount(T91)
u_mano = no_toca(X0, 19.5, T91, rd, rf, sigma, True)
assert abs(u_ql - u_mano) < 1e-10
comun.comprobar("cap15-nt-u-an", u_ql, 1e-9)
pv_an = fe._value(pa, mkt, X0, 0.0, 0)[0]
assert abs(pv_an - 1e6 * df_d * u_mano) < 1e-4
comun.comprobar("cap15-nt-pv-an", pv_an, 1e-3)
pd_ = validar(NT, barrier=17.5, barrier_type="down", method="analytic")
u_ql = fe._analytic(pd_, proc) / dom.discount(T91)
assert abs(u_ql - no_toca(X0, 17.5, T91, rd, rf, sigma, False)) < 1e-10
comun.comprobar("cap15-ntabajo-u-an", u_ql, 1e-9)
pdn = validar(DNT, lower=17.5, upper=19.8, method="analytic")
u_ql = fe._analytic(pdn, proc) / dom.discount(T91)
assert abs(u_ql - no_toca_doble(X0, 17.5, 19.8, T91, rd, rf, sigma)) < 1e-10
comun.comprobar("cap15-dnt-u-an", u_ql, 1e-9)
comun.comprobar("cap15-dnt-pv-an", fe._value(pdn, mkt, X0, 0.0, 0)[0], 1e-3)

# --- MCBarrierEngine de QuantLib: rechaza el pago en efectivo, pero valúa la réplica con un diferencial de puts up-and-out ---
barrera = ql.BarrierOption(ql.Barrier.UpOut, 19.5, 0.0, ql.CashOrNothingPayoff(ql.Option.Put, 19.5, 1.0), ql.EuropeanExercise(hoy + 91))
barrera.setPricingEngine(ql.MCBarrierEngine(proc, "pseudorandom", timeSteps=fe.STEPS, brownianBridge=True, requiredSamples=fe.PATHS, seed=fe.SEED))
try:
    barrera.NPV()
    raise AssertionError("MCBarrierEngine aceptó el pago en efectivo")
except RuntimeError as e:
    assert "non-plain payoff" in str(e)


def put_up_and_out(strike):
    o = ql.BarrierOption(ql.Barrier.UpOut, 19.5, 0.0, ql.PlainVanillaPayoff(ql.Option.Put, strike), ql.EuropeanExercise(hoy + 91))
    o.setPricingEngine(ql.MCBarrierEngine(proc, "pseudorandom", timeSteps=fe.STEPS, brownianBridge=True, requiredSamples=fe.PATHS, seed=fe.SEED))
    return o.NPV()


epsilon = 0.1
replica = (put_up_and_out(19.5 + epsilon) - put_up_and_out(19.5)) / epsilon
assert abs(replica - pv_an / 1e6) < 0.01
comun.comprobar("cap15-replica-mcbarrier", replica, 1e-4)

# --- puente browniano: _mc con una trayectoria fija (se sustituye solo el generador de trayectorias) ---


class Camino:
    """Imita a ql.GaussianPathGenerator: devuelve siempre los mismos nodos."""

    def __init__(self, nodos):
        self.nodos = nodos

    def next(self):
        return self

    def value(self):
        return self.nodos


def supervivencia(nodos, barreras, sig, dt):
    """_mc del módulo sobre `nodos` con volatilidad plana `sig` y paso `dt`; devuelve el valor de la trayectoria."""
    real = fe.ql
    fe.ql = types.SimpleNamespace(
        GaussianRandomSequenceGenerator=real.GaussianRandomSequenceGenerator,
        UniformRandomSequenceGenerator=real.UniformRandomSequenceGenerator,
        UniformRandomGenerator=real.UniformRandomGenerator, GaussianPathGenerator=lambda *a: Camino(nodos))
    viejo, fe.STEPS = fe.STEPS, len(nodos) - 1
    try:
        return fe._mc(None, sig, None, None, barreras, dt * fe.STEPS, 2)[0]
    finally:
        fe.ql, fe.STEPS = real, viejo


dt = T91 / 10
cruce = lambda a, b, H, sig: math.exp(-2 * math.log(a / H) * math.log(b / H) / (sig ** 2 * dt))
p1 = cruce(18.80, 19.05, 19.5, 0.12)
assert abs(supervivencia([18.80, 19.05], [19.5], 0.12, dt) - (1 - p1)) < 1e-12
comun.comprobar("cap15-puente-p1", p1, 1e-9)
n3 = [18.60, 18.90, 19.20]
prod = (1 - cruce(18.60, 18.90, 19.5, 0.12)) * (1 - cruce(18.90, 19.20, 19.5, 0.12))
assert abs(supervivencia(n3, [19.5], 0.12, dt) - prod) < 1e-12
comun.comprobar("cap15-puente-prod3", prod, 1e-9)
pc = cruce(19.40, 19.60, 19.5, 0.12)  # nodos a lados opuestos: la fórmula da > 1 y el código fija el factor en 0
assert pc > 1 and supervivencia([19.40, 19.60], [19.5], 0.12, dt) == 0.0
comun.comprobar("cap15-puente-p-cruzado", pc, 1e-9)
suma = cruce(18.1, 18.1, 18.0, 0.12) + cruce(18.1, 18.1, 18.2, 0.12)  # corredor (18.0, 18.2): 1 - pL - pU < 0
assert suma > 1 and supervivencia([18.1, 18.1], [18.0, 18.2], 0.12, dt) == 0.0
comun.comprobar("cap15-puente-suma-doble", suma, 1e-9)
dos = supervivencia([18.1, 18.15, 18.1], [18.0, 18.2], 0.12, dt)
mano = 1.0
for a, b in ((18.1, 18.15), (18.15, 18.1)):
    mano *= max(1 - cruce(a, b, 18.0, 0.12) - cruce(a, b, 18.2, 0.12), 0.0)
assert abs(dos - mano) < 1e-12

# --- Monte Carlo (semilla 42, 20 000 trayectorias, 10 pasos) frente al analítico plano ---
for pref, nombre, kw, res in (("nt", NT, dict(barrier=19.5, barrier_type="up"), None),
                              ("dnt", DNT, dict(lower=17.5, upper=19.8), None)):
    r = fe._result(validar(nombre, **kw), mkt)
    d = r["details"]
    assert (d["paths"], d["model"], d["method"]) == (fe.PATHS, "flat", "mc") and d["std_error"] > 0
    comun.comprobar("cap15-%s-mc-pv" % pref, r["pv"], 1e-3)
    comun.comprobar("cap15-%s-mc-se" % pref, d["std_error"], 1e-3)
    comun.comprobar("cap15-%s-mc-prob" % pref, d["no_touch_probability"], 1e-6)
    z = (r["pv"] - d["analytic_flat_pv"]) / d["std_error"]
    assert abs(z) < 3
    comun.comprobar("cap15-%s-mc-z" % pref, z, 1e-4)
    if pref == "nt":
        delta_mc, vega_mc = r["risk"]["delta"], r["risk"]["vega"]
        pv_flat = r["pv"]
comun.comprobar("cap15-nt-delta-mc", delta_mc, 1e-2)
comun.comprobar("cap15-nt-vega-mc", vega_mc, 1e-2)

# --- con sonrisa (volatilidad local), mismas trayectorias normales ---
r = fe._result(validar(NT, barrier=19.5, barrier_type="up", model="smile"), mkt)
assert "smile_adjustment" not in r["details"]
comun.comprobar("cap15-nt-smile-pv", r["pv"], 1e-3)
comun.comprobar("cap15-nt-smile-dif", r["pv"] - pv_flat, 1e-2)
comun.comprobar("cap15-nt-smile-z", (r["pv"] - r["details"]["analytic_flat_pv"]) / r["details"]["std_error"], 1e-4)

# --- delta y vega: reprecio con el choque exacto del código (método analítico, a mano con la fórmula cerrada) ---
ra = fe._result(pa, mkt)
V = lambda S, sig: 1e6 * df_d * no_toca(S, 19.5, T91, rd, rf, sig, True)
d_mano = (V(X0 * 1.01, sigma) - V(X0, sigma)) / (0.01 * X0)
v_mano = V(X0, sigma + 0.01) - V(X0, sigma)
assert abs(ra["risk"]["delta"] - d_mano) < 1e-6 and abs(ra["risk"]["vega"] - v_mano) < 1e-6
comun.comprobar("cap15-nt-delta-an", ra["risk"]["delta"], 1e-3)
comun.comprobar("cap15-nt-vega-an", ra["risk"]["vega"], 1e-3)

# --- delta con la barrera a menos de 1 % del spot: el spot chocado ya pasó la barrera ---
pc_ = validar(NT, barrier=18.62, barrier_type="up")
h = 1e-4 * X0
real = (1e6 * df_d * (no_toca(X0 + h, 18.62, T91, rd, rf, sigma, True) - no_toca(X0 - h, 18.62, T91, rd, rf, sigma, True)) / (2 * h))
mc_ = fe._result(pc_, mkt)["risk"]["delta"]
an_ = fe._result(dict(pc_, method="analytic"), mkt)["risk"]["delta"]
assert mc_ > 0 > an_ and real < 0
comun.comprobar("cap15-delta-cerca-mc", mc_, 1e-2)
comun.comprobar("cap15-delta-cerca-an", an_, 1e-2)
comun.comprobar("cap15-delta-cerca-real", real, 1e-2)

# --- malla de tiempo e identidades (mismas trayectorias normales) ---
p30 = validar(NT, days=30, barrier=18.9, barrier_type="up")
dom30, proc30, sig30, *_ = fe._build(p30, mkt, X0, 0.0)
T30 = 30 / 365.0
u10, se10 = fe._mc(proc30, sig30, None, None, [18.9], T30, fe.PATHS)
fe.STEPS = 40
try:
    u40, se40 = fe._mc(proc30, sig30, None, None, [18.9], T30, fe.PATHS)
finally:
    fe.STEPS = 10
assert abs(u10 - u40) <= 3 * math.hypot(se10, se40)
comun.comprobar("cap15-malla-u10", u10, 1e-6)
comun.comprobar("cap15-malla-u40", u40, 1e-6)
comun.comprobar("cap15-malla-dif-se", (u10 - u40) / math.hypot(se10, se40), 1e-4)
pdw, pup, pdn2 = (validar(NT, barrier=17.5, barrier_type="down"), validar(NT, barrier=19.8, barrier_type="up"),
                  validar(DNT, lower=17.5, upper=19.8))
dom_, proc_, sig_, *_ = fe._build(pdn2, mkt, X0, 0.0)
u_dw = fe._mc(proc_, sig_, None, None, [17.5], T91, fe.PATHS)[0]
u_up = fe._mc(proc_, sig_, None, None, [19.8], T91, fe.PATHS)[0]
u_dn = fe._mc(proc_, sig_, None, None, [17.5, 19.8], T91, fe.PATHS)[0]
assert u_dn <= min(u_dw, u_up)
comun.comprobar("cap15-id-abajo", u_dw, 1e-6)
comun.comprobar("cap15-id-arriba", u_up, 1e-6)
comun.comprobar("cap15-id-doble", u_dn, 1e-6)

# --- gráfica: de la barrera al espejo del spot, con valor 0 en la barrera ---
gr = fe._price(validar(NT, barrier=19.5, barrier_type="up"), mkt)["details"]["chart"]
assert len(gr["spots"]) == fe.CHART_POINTS and gr["pnl"][-1] == 0 and gr["spots"][-1] == 19.5
comun.comprobar("cap15-grafica-x0", gr["spots"][0], 1e-9)  # X0^2 / B

# --- double no touch con corredor estrecho: el factor 1 - pL - pU frente a la serie exacta del puente (mismos nodos) ---


def trayectorias(proc, T, pasos, n):
    """Nodos de n trayectorias de GaussianPathGenerator, con la semilla del módulo (como _mc)."""
    rsg = ql.GaussianRandomSequenceGenerator(ql.UniformRandomSequenceGenerator(pasos, ql.UniformRandomGenerator(fe.SEED)))
    pg = ql.GaussianPathGenerator(proc, T, pasos, rsg, False)
    return np.array([list(pg.next().value()) for _ in range(n)])


def puente_exacto(X, L, U, s2, nmax=20):
    """Valor por trayectoria con la probabilidad exacta (serie de imágenes del puente) de no salir de (L, U) en cada paso."""
    lb, w, v = np.log(X / L), math.log(U / L), 0.0
    a, b = lb[:, :-1], lb[:, 1:]
    for n in range(-nmax, nmax + 1):
        v = v + np.exp(-2 * n * w * (b - a + n * w) / s2) - np.exp(-2 * (a + n * w) * (b + n * w) / s2)
    return np.where(((X > L) & (X < U)).all(axis=1), v.prod(axis=1), 0.0)


pdnc = validar(DNT, lower=17.5, upper=19.8, method="analytic")
_, procc, sigc, *_ = fe._build(pdnc, mkt, X0, 0.0)
sT = sigc * math.sqrt(T91)
NN = 100000
for pasos in (5, 10):
    fe.STEPS = pasos
    try:
        X = trayectorias(procc, T91, pasos, NN)
        for W, cod in ((0.6, "06"), (0.7, "07"), (0.8, "08"), (1.0, "10")):
            L, U = X0 * math.exp(-W * sT / 2), X0 * math.exp(W * sT / 2)
            u_cod = fe._mc(procc, sigc, None, None, [L, U], T91, NN)[0]
            u_ex = puente_exacto(X, L, U, sigc ** 2 * T91 / pasos).mean()
            if pasos == 10:
                u_an = fe._analytic(dict(pdnc, lower=L, upper=U), procc) / dom.discount(T91)
                comun.comprobar("cap15-estrecho-an-" + cod, u_an, 0.5 * 10 ** (math.floor(math.log10(u_an)) - 4))  # 5 cifras
            comun.comprobar("cap15-estrecho-sesgo-%s-%d" % (cod, pasos), 100 * (u_cod / u_ex - 1), 0.011)
    finally:
        fe.STEPS = 10

# --- reprecio de vainillas con sonrisa: vol implícita del Monte Carlo menos la de la superficie (puntos de vol) ---


def sesgo_vainillas(dias, pasos, n=200000):
    """Variable de control S_T (E = forward); strikes a m sigma sqrt(T) del forward; devuelve [(m, diferencia en puntos)]."""
    fe.STEPS = pasos
    try:
        pv = validar(NT, days=dias, model="smile", barrier=19.5, barrier_type="up")
        dm, pr, sg, *_ = fe._build(pv, mkt, X0, 0.0)
        T = dias / 365.0
        ST = np.array([pr_.value()[pasos] for pr_ in iter_caminos(pr, T, pasos, n)])
        F = X0 * pr.dividendYield().discount(T) / dm.discount(T)
        out = []
        for m in (-1.0, -0.5, 0.0, 0.5, 1.0):
            K = F * math.exp(m * sg * math.sqrt(T))
            pago, c = np.maximum(ST - K, 0), ST - F
            precio = (pago - np.cov(pago, c)[0, 1] / c.var(ddof=1) * c).mean()
            sd = ql.blackFormulaImpliedStdDev(ql.Option.Call, K, F, precio, 1.0, 0.0, sg * math.sqrt(T), 1e-10, 200)
            out.append((m, 100 * (sd / math.sqrt(T) - pr.blackVolatility().blackVol(T, K, True))))
        return out
    finally:
        fe.STEPS = 10


def iter_caminos(proc, T, pasos, n):
    rsg = ql.GaussianRandomSequenceGenerator(ql.UniformRandomSequenceGenerator(pasos, ql.UniformRandomGenerator(fe.SEED)))
    pg = ql.GaussianPathGenerator(proc, T, pasos, rsg, False)
    return (pg.next() for _ in range(n))


for dias, pasos in ((91, 10), (365, 10), (730, 10), (365, 40)):
    for (m, dif), cod in zip(sesgo_vainillas(dias, pasos), ("km1", "km05", "k0", "kp05", "kp1")):
        comun.comprobar("cap15-vain-%d-%d-%s" % (dias, pasos, cod), dif, 0.011)

# --- tabla de volatilidad local frente al Dupire de QuantLib calculado al vuelo (mismas normales, diferencia pareada) ---


def diferencia_tabla_vuelo(nombre, dias, n=40000, **kw):
    """Valor (por unidad de pago) con la tabla menos el valor con el Dupire al vuelo, para 41 y 161 strikes."""
    T = dias / 365.0
    p = validar(nombre, days=dias, model="smile", **kw)
    barreras = [p[f] for f, *_ in fe._sides(p)]
    dm, pr, sg, ks, tab = fe._build(p, mkt, X0, 0.0)
    lv = ql.NoExceptLocalVolSurface(pr.blackVolatility(), pr.riskFreeRate(), pr.dividendYield(), pr.stateVariable(), sg)
    pr2 = ql.GeneralizedBlackScholesProcess(pr.stateVariable(), pr.dividendYield(), pr.riskFreeRate(), pr.blackVolatility(),
                                            ql.LocalVolTermStructureHandle(lv))
    X = trayectorias(pr2, T, fe.STEPS, n)
    tiempos = [T * i / fe.STEPS for i in range(fe.STEPS)]
    tiempos[0] = 1e-3 * T / fe.STEPS
    sig = np.array([[lv.localVol(tiempos[i], X[j, i], True) for i in range(fe.STEPS)] for j in range(n)])
    surv = 1.0
    for b in barreras:
        lb = np.log(X / b)
        surv = surv - np.exp(-2 * lb[:, :-1] * lb[:, 1:] / (sig ** 2 * T / fe.STEPS))
    v_vuelo = np.maximum(surv, 0).prod(axis=1).mean()
    out = []
    for k in (41, 161):
        fe.LV_STRIKES = k
        try:
            _, pr3, sg3, ks3, tab3 = fe._build(p, mkt, X0, 0.0)
            out.append(100 * (fe._mc(pr3, sg3, ks3, tab3, barreras, T, n)[0] - v_vuelo))
        finally:
            fe.LV_STRIKES = 41
    return out


d41, d161 = diferencia_tabla_vuelo(NT, 91, barrier=19.5, barrier_type="up")
comun.comprobar("cap15-tabla-nt91-41", d41, 0.0011)
d41, d161 = diferencia_tabla_vuelo(NT, 730, barrier=22.0, barrier_type="up")
comun.comprobar("cap15-tabla-nt730-41", d41, 0.0011)
comun.comprobar("cap15-tabla-nt730-161", d161, 0.0011)
d41, d161 = diferencia_tabla_vuelo(DNT, 730, lower=15.5, upper=23.0)
comun.comprobar("cap15-tabla-dnt730-41", d41, 0.0011)
comun.comprobar("cap15-tabla-dnt730-161", d161, 0.0011)

# --- la serie de la fórmula cerrada de QuantLib no converge con corredores de ~50 sigma sqrt(T) o más ---


def primer_fallo(dias):
    """Primer ancho ln(U/L) (en sigma sqrt T, paso 0.5, centrado en el spot) en que AnalyticDoubleBarrierBinaryEngine falla."""
    pa_ = validar(DNT, days=dias, lower=17.5, upper=19.8, method="analytic")
    _, pr, sg, *_ = fe._build(pa_, mkt, X0, 0.0)
    s = sg * math.sqrt(dias / 365.0)
    for W in np.arange(1, 80, 0.5):
        try:
            fe._analytic(dict(pa_, lower=X0 * math.exp(-W * s / 2), upper=X0 * math.exp(W * s / 2)), pr)
        except fe.ApiError:
            return float(W)
    return None


fallos = {d: primer_fallo(d) for d in (1, 7, 91, 730)}
assert all(49 <= v <= 59 for v in fallos.values()), fallos
comun.comprobar("cap15-ancho-falla-91", fallos[91], 0.05)
comun.comprobar("cap15-ancho-falla-1", fallos[1], 0.05)
comun.comprobar("cap15-ancho-falla-730", fallos[730], 0.05)

comun.terminar()
