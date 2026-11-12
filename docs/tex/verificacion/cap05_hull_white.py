"""Ejemplos verificables del capítulo 5 (Hull-White: cap/floor y swaption).

El valor impreso sale de qfpy y de desk.api.aging; las magnitudes intermedias que qfpy no expone (sigma_p, x*)
se recalculan aquí con la stdlib, siguiendo las fórmulas del capítulo, y además se exige que el recálculo
completo reproduzca el precio de qfpy.
"""
import math
from datetime import date, timedelta
from types import SimpleNamespace

import comun  # primero: arregla sys.path
from desk.api import aging
from desk.api.qf import qfpy

ACT360 = qfpy.DayCountConvention.ACT_360
PILARES = [0.25, 0.5, 1, 2, 5, 10, 30]


def plana(r):
    """Curva cero plana a `r` (composición continua, interpolación lineal)."""
    return qfpy.YieldCurve(PILARES, [r] * len(PILARES), qfpy.InterpolationMethod.Linear)


def phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def caplet_a_mano(r, nocional, k, a, s, t0, t1):
    """(sigma_p, valor) del caplet [t0, t1] sobre una curva plana a `r`, con la ecuación del capítulo."""
    delta = t1 - t0
    tau = delta * 365.0 / 360.0
    p0, p1 = math.exp(-r * t0), math.exp(-r * t1)
    x = 1.0 / (1.0 + k * tau)
    sp = s * (1.0 - math.exp(-a * delta)) / a * math.sqrt((1.0 - math.exp(-2.0 * a * t0)) / (2.0 * a))
    h = math.log(p1 / (x * p0)) / sp + sp / 2.0
    return sp, nocional * (1.0 + k * tau) * (x * p0 * phi(sp - h) - p1 * phi(-h))


def swaption_a_mano(r, nocional, k, te, n, a, s):
    """(x*, precio pagador) de la swaption anual de n pagos desde `te` sobre una curva plana a `r`."""
    tau = 365.0 / 360.0
    pe = math.exp(-r * te)
    p = [math.exp(-r * (te + j)) for j in range(1, n + 1)]
    c = [nocional * k * tau] * n
    c[-1] += nocional
    v = s * s / (2.0 * a) * (1.0 - math.exp(-2.0 * a * te))
    b = [(1.0 - math.exp(-a * j)) / a for j in range(1, n + 1)]
    f = [pj / pe for pj in p]

    def valor_bono(x):
        return sum(c[j] * f[j] * math.exp(-b[j] * x - 0.5 * v * b[j] ** 2) for j in range(n))

    lo, hi = -1.0, 1.0  # el NPV del swap, valor_bono(x) - nocional, decrece en x: bisección
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if valor_bono(mid) > nocional else (lo, mid)
    x_star = 0.5 * (lo + hi)
    total = 0.0
    for j in range(n):
        xj = f[j] * math.exp(-b[j] * x_star - 0.5 * v * b[j] ** 2)
        sp = s / a * (1.0 - math.exp(-a * (j + 1))) * math.sqrt((1.0 - math.exp(-2.0 * a * te)) / (2.0 * a))
        h = math.log(p[j] / (xj * pe)) / sp + sp / 2.0
        total += c[j] * (xj * pe * phi(sp - h) - p[j] * phi(-h))
    return x_star, total


def caplet():
    curva, n, k, a, s = plana(0.07), 1e8, 0.07, 0.05, 0.01
    t0, t1 = 336 / 365, 364 / 365  # caplet de TIIE-F: periodo 13 de 28 días, hoy + 336 d a hoy + 364 d
    sp, mano = caplet_a_mano(0.07, n, k, a, s, t0, t1)
    cf = qfpy.CapFloor(qfpy.CapFloorType.Cap, n, k, [t0, t1], a, s, ACT360)
    valor = cf.price(curva)
    assert abs(valor - mano) < 1e-6, (valor, mano)
    comun.comprobar("cap05-caplet-valor", valor, 1e-4)
    comun.comprobar("cap05-caplet-sigma-p", sp, 1e-9)
    comun.comprobar("cap05-caplet-doble-curva", cf.price_dual(curva, plana(0.06)), 1e-4)


def swaption():
    curva, n, k, te, a, s = plana(0.05), 1e6, 0.05, 1.0, 0.03, 0.008

    def precio(tipo):
        return qfpy.Swaption(tipo, n, k, te, 2.0, 1.0, a, s, ACT360).price(curva)

    pagador, receptor = precio(qfpy.SwaptionType.Payer), precio(qfpy.SwaptionType.Receiver)
    x_star, mano = swaption_a_mano(0.05, n, k, te, 2, a, s)
    assert abs(pagador - mano) < 1e-6, (pagador, mano)
    comun.comprobar("cap05-swaption-x", x_star, 1e-9)
    comun.comprobar("cap05-swaption-pagador", pagador, 1e-4)
    comun.comprobar("cap05-swaption-paridad", pagador - receptor, 1e-4)


def cap_envejecido():
    curva, k, a, s = plana(0.07), 0.07, 0.05, 0.01
    inicio = date(2026, 1, 2)
    mkt = SimpleNamespace(as_of=inicio + timedelta(days=100), hw={"TIIE-F": {"a": a, "sigma": s}},
                          curves={"TIIE-F": curva}, mxn_discount="TIIE-F", spot=1.0)
    operacion = {"start_date": inicio}
    terminos = {"curve": "TIIE-F", "cap_type": "cap", "notional": 1e8, "strike": k, "periods": 13}
    envejecido = aging.cap_floor_pv_mxn(operacion, terminos, mkt)
    # a mano: entran los caplets k = 5..13 (inicio (k-1)*28 >= 100 días), con fronteras (k*28-100)/365
    mano = sum(caplet_a_mano(0.07, 1e8, k, a, s, ((j - 1) * 28 - 100) / 365, (j * 28 - 100) / 365)[1]
               for j in range(5, 14))
    assert abs(envejecido - mano) < 1e-6, (envejecido, mano)
    completo = qfpy.CapFloor(qfpy.CapFloorType.Cap, 1e8, k, 13 * 28 / 365, 365 / 28, a, s, ACT360).price(curva)
    comun.comprobar("cap05-cap-completo", completo, 1e-4)
    comun.comprobar("cap05-cap-envejecido", envejecido, 1e-4)


caplet()
swaption()
cap_envejecido()
comun.terminar()
