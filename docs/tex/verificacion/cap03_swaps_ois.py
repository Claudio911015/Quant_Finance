"""Ejemplos verificables del capítulo 3 (swaps OIS): swap nuevo, swap envejecido con fijaciones y descuento con otra curva."""
import comun  # primero: arregla sys.path
from datetime import date, timedelta
from types import SimpleNamespace

from desk.api import valuation
from desk.api.qf import qfpy

LIN = qfpy.InterpolationMethod.Linear
NOM = 100e6
PAGADOR = qfpy.SwapType.Payer


def entorno(**curvas):
    env = qfpy.MarketEnvironment()
    for nombre, curva in curvas.items():
        env.add_curve(nombre.replace("_", "-"), curva)
    return env


def ejemplo_nuevo():
    """Swap TIIE-F de 70 días (cupones a 28, 56 y 70 días), pagador, K = 7.05 %, curva con ceros 7.00/7.05/7.10 %."""
    curva = qfpy.YieldCurve([28 / 365, 56 / 365, 84 / 365], [0.0700, 0.0705, 0.0710], LIN)
    env = entorno(TIIE_F=curva)
    swap = qfpy.OisSwap(NOM, 0.0705, 70, 28, PAGADOR, "TIIE-F")
    flujos = swap.cash_flows(env)
    for i, d in enumerate((28, 56, 70), start=1):
        comun.comprobar("cap03-df-%d" % d, curva.discount_factor(d / 365), 5e-11)
        comun.comprobar("cap03-flo-%d" % i, flujos[i - 1].float_amount, 0.005)
    comun.comprobar("cap03-fij-1", flujos[0].fixed_amount, 0.005)
    comun.comprobar("cap03-fij-2", flujos[1].fixed_amount, 0.005)
    comun.comprobar("cap03-fij-3", flujos[2].fixed_amount, 0.005)
    comun.comprobar("cap03-anualidad", swap.annuity(env), 0.005)
    comun.comprobar("cap03-tasa-par", swap.par_rate(env), 5e-11)
    comun.comprobar("cap03-pv-pagador", swap.npv(env), 0.005)
    telescopica = NOM * (1.0 - curva.discount_factor(70 / 365))
    comun.comprobar("cap03-flotante-telescopica", telescopica, 0.005)
    # la identidad de la fórmula coincide con la suma de la tabla de flujos y con A (S - K)
    assert abs(sum(f.float_amount * f.discount_factor for f in flujos) - telescopica) < 1e-6
    assert abs(swap.npv(env) - swap.annuity(env) * (swap.par_rate(env) - 0.0705)) < 1e-6


def ejemplo_envejecido():
    """El mismo swap (inicio lunes 2026-06-01) valuado el jueves 2026-06-11 con 10 días de fijaciones (fin de semana incluido)."""
    inicio, hoy = date(2026, 6, 1), date(2026, 6, 11)
    curva = qfpy.YieldCurve([18 / 365, 46 / 365, 60 / 365], [0.0702, 0.0707, 0.0712], LIN)
    env = entorno(TIIE_F=curva)
    tasas = [0.0700, 0.0701, 0.0701, 0.0702, 0.0703, None, None, 0.0702, 0.0701, 0.0700]  # sáb y dom sin publicar
    fijaciones = {"TIIE-F": {inicio + timedelta(days=i): r for i, r in enumerate(tasas) if r is not None}}
    mkt = SimpleNamespace(curves={"TIIE-F": curva}, as_of=hoy, env=env)
    operacion = {"start_date": inicio, "maturity_date": inicio + timedelta(days=70)}
    terminos = {"notional": NOM, "fixed_rate": 0.0705, "side": "payer", "curve": "TIIE-F"}
    avisos = []
    swap = valuation.aged_swap(operacion, terminos, mkt, fijaciones, avisos)
    assert avisos == [], avisos  # sábado y domingo no son fijaciones faltantes
    a = valuation.aged_swap_terms(operacion, terminos, mkt, fijaciones, [])
    assert (a["start_days"], a["pay_days"]) == (-10, [18, 46, 60]), a
    factor = valuation.accrued_factor("TIIE-F", inicio, hoy, fijaciones, mkt, [])
    # el mismo factor a mano: (1 + r n / 360) por cada fijación y sus n días (el viernes devenga 3)
    a_mano = 1.0
    for r, n in ((0.0700, 1), (0.0701, 1), (0.0701, 1), (0.0702, 1), (0.0703, 3), (0.0702, 1), (0.0701, 1), (0.0700, 1)):
        a_mano *= 1.0 + r * n / 360.0
    assert abs(a_mano - factor) < 1e-15
    flujos = swap.cash_flows(env)
    for d in (18, 46, 60):
        comun.comprobar("cap03-df-env-%d" % d, curva.discount_factor(d / 365), 5e-11)
    comun.comprobar("cap03-factor-acumulado", factor, 5e-11)
    comun.comprobar("cap03-flo-env-1", flujos[0].float_amount, 0.005)
    comun.comprobar("cap03-fij-env-1", flujos[0].fixed_amount, 0.005)
    comun.comprobar("cap03-anualidad-env", swap.annuity(env), 0.005)
    comun.comprobar("cap03-tasa-par-env", swap.par_rate(env), 5e-11)
    comun.comprobar("cap03-pv-envejecido", swap.npv(env), 0.005)
    telescopica = NOM * (factor - curva.discount_factor(60 / 365))
    comun.comprobar("cap03-flotante-telescopica-env", telescopica, 0.005)
    assert abs(sum(f.float_amount * f.discount_factor for f in flujos) - telescopica) < 1e-6


def ejemplo_colateral():
    """Swap del primer ejemplo con K = 9 % descontado en otra curva (cupones proyectados con TIIE-F)."""
    curva = qfpy.YieldCurve([28 / 365, 56 / 365, 84 / 365], [0.0700, 0.0705, 0.0710], LIN)
    descuento = qfpy.YieldCurve([28 / 365, 84 / 365], [0.0600, 0.0620], LIN)
    env = entorno(TIIE_F=curva, MXN_USD=descuento)
    simple = qfpy.OisSwap(NOM, 0.09, 70, 28, PAGADOR, "TIIE-F")
    doble = qfpy.OisSwap(NOM, 0.09, 70, 28, PAGADOR, "TIIE-F", discount_curve_key="MXN-USD")
    for d in (28, 56, 70):
        comun.comprobar("cap03-df-col-%d" % d, descuento.discount_factor(d / 365), 5e-11)
    comun.comprobar("cap03-anualidad-col", doble.annuity(env), 0.005)
    comun.comprobar("cap03-tasa-par-col", doble.par_rate(env), 5e-11)
    comun.comprobar("cap03-pv-un-curva", simple.npv(env), 0.005)
    comun.comprobar("cap03-pv-col", doble.npv(env), 0.005)
    flujos = doble.cash_flows(env)
    suma = sum(f.float_amount * f.discount_factor for f in flujos)
    comun.comprobar("cap03-flo-descontado-col", suma, 0.005)
    comun.comprobar("cap03-flo-telescopica-col", NOM * (1.0 - descuento.discount_factor(70 / 365)), 0.005)


ejemplo_nuevo()
ejemplo_envejecido()
ejemplo_colateral()
comun.terminar()
