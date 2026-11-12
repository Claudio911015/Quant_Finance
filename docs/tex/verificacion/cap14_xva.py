"""Ejemplos verificables del capítulo 14 (XVA y curvas de crédito).

Todos los valores salen del código del proyecto: `qfxva` (bootstrap de CDS, motor de exposición, `compute_xva`,
`CVACalculator`) y `desk.api.risk.xva` (traducción desk -> motor, XVA incremental) sobre una base SQLite temporal
con el snapshot MX-DEMO. Las magnitudes marcadas «recálculo» en el texto se rehacen aquí con la stdlib siguiendo
las ecuaciones del capítulo y el script exige que coincidan con el código.

Los valores de Monte Carlo son reproducibles porque las semillas son fijas (`std::mt19937_64` sembrado con
(semilla, trayectoria)); con otra biblioteca estándar cambiarían dentro de su error estándar.
"""
import math
import os
import tempfile
from datetime import date, timedelta

import comun  # primero: arregla sys.path
from desk.api import db, market, portfolio, valuation
from desk.api import fixings as fixing_store
from desk.api.qf import qfpy
from desk.api.risk import credit_curves, xva
from desk.api.seed_market import seed_market
import qfxva

PILARES = [0.25, 0.5, 1, 2, 5, 10, 30]
LINEAL = qfpy.InterpolationMethod.Linear


def plana(r):
    """Curva cero plana a `r` (composición continua, interpolación lineal)."""
    return qfpy.YieldCurve(PILARES, [r] * len(PILARES), LINEAL)


def phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# ------------------------------------------------------------------------------------------------ curvas de crédito

def dias_de_prima(plazo):
    """d_k = round(365 k / 4) (redondeo del punto medio hacia arriba) y, si hace falta, el pago corto final."""
    trimestres = int(math.floor(4.0 * plazo + 1e-9))
    dias = [int(math.floor(365.0 * k / 4.0 + 0.5)) for k in range(1, trimestres + 1)]
    ultimo = int(math.floor(365.0 * plazo + 0.5))
    if not dias or ultimo > dias[-1]:
        dias.append(ultimo)
    return dias


def patas_cds(plazo, recup, supervivencia, r):
    """(pata de protección, anualidad de prima con prima devengada) por unidad de nominal; curva plana a `r`."""
    proteccion = prima = devengada = 0.0
    d_prev, t_prev, s_prev = 0, 0.0, 1.0
    for d in dias_de_prima(plazo):
        t, tau = d / 365.0, (d - d_prev) / 360.0
        s = supervivencia(t)
        df_medio = math.exp(-r * 0.5 * (t_prev + t))
        masa = s_prev - s
        proteccion += masa * df_medio
        prima += tau * s * math.exp(-r * t)
        devengada += 0.5 * tau * masa * df_medio
        d_prev, t_prev, s_prev = d, t, s
    return (1.0 - recup) * proteccion, prima + devengada


def curvas_de_credito():
    r, recup = 0.07, 0.40
    disc = plana(r)
    cotizaciones = [(1, 0.0080), (2, 0.0090), (3, 0.0100), (5, 0.0110)]
    curva = qfxva.bootstrap_cds_curve([qfxva.CdsQuote(t, s) for t, s in cotizaciones], recup, disc)
    h = curva.hazards()
    for j in range(4):
        comun.comprobar("cap14-cds-lambda-%d" % (j + 1), h[j], 5e-11)
    comun.comprobar("cap14-cds-supervivencia-5a", curva.survival_probability(5.0), 5e-11)
    # cada CDS de entrada vale cero con la curva ajustada
    for t, s in cotizaciones:
        assert abs(qfxva.cds_value(qfxva.CdsQuote(t, s), recup, curva, disc, 1.0)) < 1e-12
    # recálculo del primer tramo: la intensidad del tramo 1 reprecia el CDS a 1 año con las ecuaciones del capítulo
    proteccion, anualidad = patas_cds(1, recup, lambda t: math.exp(-h[0] * t), r)
    assert abs(proteccion - 0.0080 * anualidad) < 1e-12
    comun.comprobar("cap14-cds-proteccion-1a", proteccion, 5e-11)
    comun.comprobar("cap14-cds-anualidad-1a", anualidad, 5e-10)
    # una sola cotización plana: la intensidad cae cerca de s / (1 - R)
    una = qfxva.bootstrap_cds_curve([qfxva.CdsQuote(5, 0.0100)], recup, disc)
    assert abs(una.hazards()[0] / (0.0100 / 0.6) - 1.0) < 0.02
    comun.comprobar("cap14-cds-lambda-plana", una.hazards()[0], 5e-11)
    # cotizaciones que implican una intensidad negativa: error con mensaje claro
    try:
        qfxva.bootstrap_cds_curve([qfxva.CdsQuote(1, 0.0200), qfxva.CdsQuote(2, 0.0100)], recup, disc)
    except ValueError as exc:
        assert "quote at 2y implies a negative hazard rate" in str(exc)
    else:
        raise AssertionError("debía fallar con intensidad negativa")


# ------------------------------------------------------------------------------------------------ forma cerrada

N0, K0, A0, S0, T0 = 100e6, 0.085, 0.05, 0.01, 730   # swap de un solo periodo, 0 -> 730 días
R0 = 0.09


def vlog(t_dias):
    """Varianza del logaritmo de Y_t = P(t,T)/B(t): sigma^2 * int_0^t beta(s,T)^2 ds."""
    t, big_t = t_dias / 365.0, T0 / 365.0
    g = lambda u: u + 2.0 * math.exp(-A0 * u) / A0 - math.exp(-2.0 * A0 * u) / (2.0 * A0)
    return S0 * S0 / (A0 * A0) * (g(big_t) - g(big_t - t))


def forma_cerrada(dias, lam_c, lam_o, lgd_c, lgd_o, s_f):
    """(CVA, DVA, FVA) del swap de un periodo por las ecuaciones del capítulo (put/call de Black sobre Y)."""
    c = 1.0 + K0 * T0 / 360.0
    f = c * math.exp(-R0 * T0 / 365.0)
    cva = dva = fva = 0.0
    for i in range(1, len(dias)):
        t0, t1 = dias[i - 1] / 365.0, dias[i] / 365.0
        epe = ene = 0.0
        if dias[i] < T0:
            v = vlog(dias[i])
            sv = math.sqrt(v)
            d1 = (math.log(f) + 0.5 * v) / sv
            d2 = d1 - sv
            epe = N0 * (phi(-d2) - f * phi(-d1))
            ene = N0 * (f * phi(d1) - phi(d2))
        cva += lgd_c * epe * (math.exp(-lam_c * t0) - math.exp(-lam_c * t1))
        dva += lgd_o * ene * (math.exp(-lam_o * t0) - math.exp(-lam_o * t1))
        fva += s_f * (epe - ene) * math.exp(-lam_c * t1) * math.exp(-lam_o * t1) * (t1 - t0)
    return cva, dva, fva, N0 * (1.0 - f)


MODELO_DEMO = (0.05, 0.01, 0.03, 0.008, 0.12, 0.35, 0.30, -0.10)   # a, sigma MXN; a, sigma USD; vol FX; rho


def swap_un_periodo():
    dias = list(range(0, T0 + 1, 10))
    mercado = qfxva.ExposureMarket(plana(R0), plana(0.04), 18.6)
    cfg = qfxva.SimConfig(20000, 20261110, 0.95, dias)
    spec = qfxva.RateSwapSpec(qfxva.SwapCurrency.MXN, N0, K0, True, 0, [T0], 1.0)
    perfil = qfxva.ExposureEngine(mercado, qfxva.ExposureModel(*MODELO_DEMO), cfg).simulate(
        [qfxva.NettingSetSpec(swaps=[spec])])[0]
    cp, propia = qfxva.FlatHazardRate(lambda_=0.02), qfxva.FlatHazardRate(lambda_=0.01)
    x = qfxva.compute_xva(perfil, cp, 0.6, propia, 0.6, 0.005)
    cva, dva, fva, v0 = forma_cerrada(dias, 0.02, 0.01, 0.6, 0.6, 0.005)
    assert abs(perfil.value_at_zero - v0) < 1e-6 * N0
    assert abs(x.cva - cva) < 3.0 * x.cva_stderr and abs(x.dva - dva) < 3.0 * x.dva_stderr
    comun.comprobar("cap14-cf-valor-inicial", v0, 5e-4)
    comun.comprobar("cap14-cf-cva", cva, 5e-4)
    comun.comprobar("cap14-cf-dva", dva, 5e-4)
    comun.comprobar("cap14-cf-fva", fva, 5e-4)
    comun.comprobar("cap14-cf-motor-cva", x.cva, 5e-2)
    comun.comprobar("cap14-cf-motor-cva-ee", x.cva_stderr, 5e-2)
    comun.comprobar("cap14-cf-motor-dva", x.dva, 5e-2)
    comun.comprobar("cap14-cf-motor-fva", x.fva, 5e-2)
    comun.comprobar("cap14-cf-motor-z", (x.cva - cva) / x.cva_stderr, 5e-4)


# ------------------------------------------------------------------------------------------------ sin volatilidad

def sin_volatilidad():
    """Receptor 7.5 % a 13 periodos de 28 días sobre curva plana a 7 %: EPE(140 d) = max(V determinista, 0)."""
    n, k, r = 100e6, 0.075, 0.07
    pagos = [28 * (j + 1) for j in range(13)]
    cfg = qfxva.SimConfig(200, 1, 0.95, [0, 140, 364])
    modelo = qfxva.ExposureModel(0.05, 0.0, 0.03, 0.0, 0.0, 0.35, 0.30, -0.10)
    spec = qfxva.RateSwapSpec(qfxva.SwapCurrency.MXN, n, k, False, 0, pagos, 1.0)
    motor = qfxva.ExposureEngine(qfxva.ExposureMarket(plana(r), plana(0.04), 18.6), modelo, cfg)
    perfil = motor.simulate([qfxva.NettingSetSpec(swaps=[spec])])[0]
    # V(t) = (N / P(0,t)) * sum_{periodos impagos} [P(0, inicio) - (1 + K tau) P(0, pago)]
    p = lambda d: math.exp(-r * d / 365.0)
    t = 140
    v = 0.0
    for j, pago in enumerate(pagos):
        if pago <= t:
            continue
        inicio = pagos[j - 1] if j else 0
        v += p(inicio) - (1.0 + k * 28.0 / 360.0) * p(pago)
    v *= -n / p(t)   # el factor -1 es el signo del receptor (el pagador vale +N / P(0,t) por la suma)
    assert abs(perfil.epe[1] - max(v, 0.0)) < 1e-6 * n and perfil.ene[1] == 0.0
    env = qfpy.MarketEnvironment()
    env.add_curve("TIIE-F", plana(r))
    desk = qfpy.OisSwap(n, k, 0, pagos, 1.0, qfpy.SwapType.Receiver, "TIIE-F").npv(env)
    assert abs(perfil.value_at_zero - desk) < 1e-6 * n   # arranque exacto: V(0) es el npv de OisSwap
    comun.comprobar("cap14-sinvol-epe", perfil.epe[1], 5e-4)
    assert perfil.epe[2] == 0.0   # a los 364 días ya pagó el último flujo
    comun.comprobar("cap14-sinvol-valor-inicial", perfil.value_at_zero, 5e-4)


def malla_corta():
    """Un swap de 28 días cuyo último pago cae antes de la primera fecha mensual: CVA exactamente 0 en la malla mensual."""
    with tempfile.TemporaryDirectory() as carpeta:
        conn = db.connect(os.path.join(carpeta, "corto.db"))
        db.init_schema(conn)
        seed_market(conn)
        portfolio.create_trade(conn, {
            "product": "irs", "counterparty": CP, "trade_date": D0.isoformat(),
            "params": {"curve": "TIIE-F", "side": "receiver", "notional": 100e6, "periods": 1, "fixed_rate": 0.075}})
        mkt = market.load_context(conn, "MX-DEMO")
        trades = portfolio.load_trades(conn)
        spec = xva.build_set(trades, mkt, fixing_store.load_all(conn))[0]
        modelo, params = xva.model_from_snapshot(mkt)[0], xva.load_params(conn)
        plana_cp = qfxva.FlatHazardRate(lambda_=0.02)
        mensual = xva.report_days(mkt.as_of, trades[0]["maturity_date"])
        assert mensual == [0, 30]
        cvas = []
        for dias in (mensual, list(range(0, 29))):
            p = xva.engine(mkt, modelo, params, dias).simulate([spec])[0]
            cvas.append(qfxva.compute_xva(p, plana_cp, 0.6, plana_cp, 0.6, 0.005).cva)
        assert cvas[0] == 0.0 and cvas[1] > 0.0
        conn.close()
    return cvas


# ------------------------------------------------------------------------------------------------ desk

CP = "Banco Ejemplo"
D0 = date(2026, 11, 10)
COTIZ_CP = (90, 100, 110, 125, 135, 150)
COTIZ_PROPIA = (70, 80, 90, 105, 115, 125)


def base_del_desk(carpeta):
    """Base temporal: MX-DEMO, fijaciones TIIE-F de 7 %, un IRS envejecido y un xccy recién pactado en la misma contraparte."""
    conn = db.connect(os.path.join(carpeta, "ejemplo.db"))
    db.init_schema(conn)
    seed_market(conn)
    filas, dia = ["index,date,value"], date(2026, 8, 10)
    while dia < D0:
        if dia.weekday() < 5:
            filas.append("TIIE-F,%s,0.07" % dia.isoformat())
        dia += timedelta(days=1)
    fixing_store.import_csv(conn, "\n".join(filas))
    portfolio.create_trade(conn, {
        "product": "irs", "counterparty": CP, "trade_date": "2026-08-10",
        "params": {"curve": "TIIE-F", "side": "payer", "notional": 200e6, "periods": 26, "fixed_rate": 0.072}})
    portfolio.create_trade(conn, {
        "product": "xccy_swap", "counterparty": CP, "trade_date": "2026-11-10",
        "params": {"side": "pay_usd", "notional_usd": 10e6, "periods": 26, "fx_rate": 18.2, "spread": 0.0005,
                   "exchange": "both"}})
    portfolio.create_trade(conn, {
        "product": "irs", "counterparty": "Banco Espejo", "trade_date": "2026-08-10",
        "params": {"curve": "TIIE-F", "side": "payer", "notional": 200e6, "periods": 26, "fixed_rate": 0.072}})
    for entidad, spreads in ((CP, COTIZ_CP), ("Banco Espejo", COTIZ_CP), (credit_curves.OWN, COTIZ_PROPIA)):
        credit_curves.put_curve(conn, entidad, {
            "recovery": 0.4,
            "quotes": [{"tenor_years": t, "spread": s / 1e4} for t, s in zip((1, 2, 3, 5, 7, 10), spreads)]})
    conn.commit()
    return conn


def xva_del_desk(conn):
    mkt = market.load_context(conn, "MX-DEMO")
    fixings = fixing_store.load_all(conn)
    trades = [t for t in portfolio.load_trades(conn) if t["counterparty"] == CP]
    spec, incluidas, excluidas, _ = xva.build_set(trades, mkt, fixings)
    assert not excluidas
    # arranque exacto: el valor del motor en t = 0 es el PV del desk, operación por operación
    modelo = xva.model_from_snapshot(mkt)[0]
    params = xva.load_params(conn)
    dias = xva.report_days(mkt.as_of, max(t["maturity_date"] for t in trades))
    motor = xva.engine(mkt, modelo, params, dias)
    del_motor = motor.trade_values_at_zero(spec)   # swaps primero, luego xccys: el mismo orden que `trades`
    for valor, fila, nocional in zip(del_motor, incluidas, (200e6, 10e6 * 18.2)):
        assert abs(valor - fila["pv_mxn"]) < 1e-6 * nocional
    comun.comprobar("cap14-desk-pv-irs", incluidas[0]["pv_mxn"], 5e-5)
    comun.comprobar("cap14-desk-pv-xccy", incluidas[1]["pv_mxn"], 5e-5)
    return mkt, trades, spec, modelo, params, dias, motor


def xva_por_contraparte(conn):
    mkt, trades, spec, modelo, params, dias, motor = xva_del_desk(conn)
    cuerpo = xva.compute(conn, "MX-DEMO")
    cp = [c for c in cuerpo["counterparties"] if c["counterparty"] == CP][0]
    comun.comprobar("cap14-desk-pv-neto", cp["pv_mxn"], 5e-5)
    comun.comprobar("cap14-desk-cva", cp["cva_mxn"], 5e-3)
    comun.comprobar("cap14-desk-cva-ee", cp["cva_stderr_mxn"], 5e-3)
    comun.comprobar("cap14-desk-dva", cp["dva_mxn"], 5e-3)
    comun.comprobar("cap14-desk-fva", cp["fva_mxn"], 5e-3)
    comun.comprobar("cap14-desk-total", cp["total_mxn"], 5e-3)
    assert cp["total_mxn"] == cp["cva_mxn"] - cp["dva_mxn"] + cp["fva_mxn"]
    comun.comprobar("cap14-desk-epe-max", cp["epe_max_mxn"], 5e-3)

    # compensación: CVA de la unión <= suma de los CVA, con las mismas trayectorias
    cuentas = {}
    curvas = credit_curves.current(conn)
    cp_curva = credit_curves.build_curve(qfxva, curvas[CP], mkt)
    propia = credit_curves.build_curve(qfxva, curvas[credit_curves.OWN], mkt)
    solo_irs = qfxva.NettingSetSpec(swaps=spec.swaps, xccys=[])
    solo_xccy = qfxva.NettingSetSpec(swaps=[], xccys=spec.xccys)
    perfiles = motor.simulate([solo_irs, solo_xccy, spec])
    cva = [qfxva.compute_xva(p, cp_curva, 0.6, propia, 0.6, params["funding_spread"]).cva for p in perfiles]
    assert cva[2] == cp["cva_mxn"]
    assert cva[2] < cva[0] + cva[1]
    comun.comprobar("cap14-sub-cva-irs", cva[0], 5e-3)
    comun.comprobar("cap14-sub-cva-xccy", cva[1], 5e-3)
    comun.comprobar("cap14-sub-cva-union", cva[2], 5e-3)
    comun.comprobar("cap14-sub-ahorro", cva[0] + cva[1] - cva[2], 5e-3)

    # la malla mensual frente a la diaria, con las mismas trayectorias
    ultimo = (max(t["maturity_date"] for t in trades) - mkt.as_of).days
    diaria = xva.engine(mkt, modelo, params, list(range(0, ultimo + 2))).simulate([spec])[0]
    x_diaria = qfxva.compute_xva(diaria, cp_curva, 0.6, propia, 0.6, params["funding_spread"])
    comun.comprobar("cap14-malla-cva-diaria", x_diaria.cva, 5e-3)
    comun.comprobar("cap14-malla-cambio", 100.0 * (x_diaria.cva / cva[2] - 1.0), 5e-5)
    return cp


def incremental(conn, antes):
    base = {"snapshot": "MX-DEMO", "counterparty": CP, "product": "irs", "trade_date": "2026-11-10",
            "params": {"curve": "TIIE-F", "side": "payer", "notional": 150e6, "periods": 26}}
    r = xva.incremental(conn, base)
    assert abs(r["candidate"]["pv_mxn"]) < 1e-3   # sin tasa fija: nace a la par
    assert r["before"]["cva_mxn"] == antes["cva_mxn"] and r["before"]["total_mxn"] == antes["total_mxn"]
    for k in ("cva_mxn", "dva_mxn", "fva_mxn", "total_mxn"):
        assert r["delta"][k] == r["after"][k] - r["before"][k]
    comun.comprobar("cap14-inc-tasa-par", r["candidate"]["params"]["fixed_rate"], 5e-5)
    comun.comprobar("cap14-inc-cva", r["delta"]["cva_mxn"], 5e-3)
    comun.comprobar("cap14-inc-dva", r["delta"]["dva_mxn"], 5e-3)
    comun.comprobar("cap14-inc-fva", r["delta"]["fva_mxn"], 5e-3)
    comun.comprobar("cap14-inc-total", r["delta"]["total_mxn"], 5e-3)
    comun.comprobar("cap14-inc-total-pb", r["delta_bp"]["total"], 5e-5)
    inverso = dict(base, params=dict(base["params"], side="receiver"))
    contrario = xva.incremental(conn, inverso)
    comun.comprobar("cap14-inc-cva-receptor", contrario["delta"]["cva_mxn"], 5e-3)

    # espejo exacto de la única operación de otra contraparte
    espejo = xva.incremental(conn, {
        "snapshot": "MX-DEMO", "counterparty": "Banco Espejo", "product": "irs", "trade_date": "2026-08-10",
        "params": {"curve": "TIIE-F", "side": "receiver", "notional": 200e6, "periods": 26, "fixed_rate": 0.072}})
    for k in ("cva_mxn", "dva_mxn", "fva_mxn", "total_mxn", "epe_max_mxn", "pfe_max_mxn"):
        assert espejo["after"][k] == 0.0, k
    for k in ("cva_mxn", "dva_mxn", "fva_mxn", "total_mxn"):
        assert espejo["delta"][k] == -espejo["before"][k], k
    comun.comprobar("cap14-espejo-cva-antes", espejo["before"]["cva_mxn"], 5e-3)
    comun.comprobar("cap14-espejo-total-antes", espejo["before"]["total_mxn"], 5e-3)


# ------------------------------------------------------------------------------------------------ motor anterior

N1, A1, S1, HZ, LGD = 100e6, 0.05, 0.01, 0.02, 0.6
PAGOS = [28 * (k + 1) for k in range(65)]
MALLA = [28 * k for k in range(66)]


def curva_de_pruebas(ceros):
    return qfpy.YieldCurve([0.25, 1, 2, 3, 5, 7, 10, 12], ceros, LINEAL)


def cva_sin_descontar(tiempos, epe):
    return sum(LGD * epe[i] * (math.exp(-HZ * tiempos[i - 1]) - math.exp(-HZ * tiempos[i]))
               for i in range(1, len(tiempos)))


def tasa_par_ois(curva):
    env = qfpy.MarketEnvironment()
    env.add_curve("TIIE-F", curva)
    flotante = qfpy.OisSwap(1.0, 0.0, 0, PAGOS, 1.0, qfpy.SwapType.Payer, "TIIE-F").npv(env)
    fija_uno = qfpy.OisSwap(1.0, 1.0, 0, PAGOS, 1.0, qfpy.SwapType.Payer, "TIIE-F").npv(env)
    return flotante / (flotante - fija_uno)


def cva_del_motor(curva, tasa):
    sofr = curva_de_pruebas([0.0365, 0.0368, 0.0370, 0.0372, 0.0375, 0.0380, 0.0385, 0.0388])
    spec = qfxva.NettingSetSpec(swaps=[qfxva.RateSwapSpec(qfxva.SwapCurrency.MXN, N1, tasa, True, 0, PAGOS, 1.0)])
    cvas = []
    for b in range(10):   # 10 motores de 500 trayectorias con semillas distintas
        motor = qfxva.ExposureEngine(
            qfxva.ExposureMarket(curva, sofr, 18.6), qfxva.ExposureModel(*MODELO_DEMO),
            qfxva.SimConfig(500, 20261110 + 7919 * b, 0.95, MALLA))
        p = motor.simulate([spec])[0]
        cvas.append(cva_sin_descontar(p.times, p.epe))
    media = sum(cvas) / 10.0
    return media, math.sqrt(sum((c - media) ** 2 for c in cvas) / 9.0 / 10.0)


def cva_exacto(curva, tasa, pasos=1000):
    """CVA sin Monte Carlo: el swap fresco depende solo de x(t) ~ N(m, y); integral 1D por trapecio."""
    tau = 28.0 / 360.0
    tiempos, epe = [0.0], [0.0]
    for k in range(1, len(MALLA)):
        t = PAGOS[k - 1] / 365.0
        em = 1.0 - math.exp(-A1 * t)
        m = S1 * S1 / (2.0 * A1 * A1) * em * em
        y = S1 * S1 * (1.0 - math.exp(-2.0 * A1 * t)) / (2.0 * A1)
        sd = math.sqrt(y)
        integral = 0.0
        for n in range(pasos + 1):
            z = -8.0 + 16.0 * n / pasos
            x = m + sd * z

            def bono(dia):
                b = (1.0 - math.exp(-A1 * (dia - PAGOS[k - 1]) / 365.0)) / A1
                return curva.discount_factor(dia / 365.0) / curva.discount_factor(t) * math.exp(-b * x - 0.5 * b * b * y)

            fija = sum(tau * bono(PAGOS[j]) for j in range(k, len(PAGOS)))
            v = N1 * ((1.0 - bono(PAGOS[-1])) - tasa * fija) if k < len(PAGOS) else 0.0
            peso = 0.5 if n in (0, pasos) else 1.0
            integral += peso * max(v, 0.0) * math.exp(-0.5 * z * z)
        tiempos.append(t)
        epe.append(integral * (16.0 / pasos) / math.sqrt(2.0 * math.pi))
    return cva_sin_descontar(tiempos, epe)


def cva_anterior(curva):
    """CVA de `CVACalculator` para el swap fresco de 5 años a su propia tasa par (InterestRateSwap, 28/365)."""
    env = qfpy.MarketEnvironment()
    env.add_curve("default", curva)
    tasa = qfpy.InterestRateSwap.par_rate(5.0, 365.0 / 28.0, env)
    conjunto = qfxva.NettingSet()
    conjunto.add(N1, tasa, 5.0, 365.0 / 28.0, qfpy.SwapType.Payer)
    params = qfxva.SimParams(5000, [d / 365.0 for d in MALLA if d > 0], 4242)
    return qfxva.CVACalculator(qfpy.HullWhite(A1, S1, curva), qfxva.FlatHazardRate(lambda_=HZ), LGD,
                               params).compute(conjunto, env).cva


def motor_anterior():
    casos = (("plana", curva_de_pruebas([0.07] * 8)),
             ("pend", curva_de_pruebas([0.0690, 0.0700, 0.0705, 0.0710, 0.0715, 0.0720, 0.0725, 0.0728])))
    for nombre, curva in casos:
        tasa = tasa_par_ois(curva)
        motor, ee = cva_del_motor(curva, tasa)
        exacto = cva_exacto(curva, tasa)
        anterior = cva_anterior(curva)
        assert abs(motor - exacto) < 3.0 * ee and abs(motor / exacto - 1.0) < 0.05
        comun.comprobar("cap14-legacy-%s-exacto" % nombre, exacto, 5e-3)
        comun.comprobar("cap14-legacy-%s-motor" % nombre, motor, 5e-1)
        comun.comprobar("cap14-legacy-%s-motor-ee" % nombre, ee, 5e-1)
        comun.comprobar("cap14-legacy-%s-viejo" % nombre, anterior, 5e-1)
        comun.comprobar("cap14-legacy-%s-sesgo" % nombre, 100.0 * (anterior / exacto - 1.0), 5e-3)
        comun.comprobar("cap14-legacy-%s-sesgo-motor" % nombre, 100.0 * (motor / exacto - 1.0), 5e-3)
    # causa: la tasa corta media simulada por HullWhite::simulate queda por encima de la del modelo
    curva = casos[1][1]
    hw = qfpy.HullWhite(A1, S1, curva)
    horizonte, pasos, n = 4.4, int(4.4 * 252), 20000
    suma = sum(hw.simulate(horizonte, pasos, semilla)[pasos] for semilla in range(1, n + 1)) / n
    h = 1e-6
    forward = -(math.log(curva.discount_factor(horizonte + h)) - math.log(curva.discount_factor(horizonte - h))) / (2 * h)
    modelo = forward + S1 * S1 / (2.0 * A1 * A1) * (1.0 - math.exp(-A1 * horizonte)) ** 2
    comun.comprobar("cap14-legacy-tasa-modelo", modelo, 5e-7)
    comun.comprobar("cap14-legacy-tasa-simulada", suma, 5e-7)
    comun.comprobar("cap14-legacy-tasa-sesgo-pb", (suma - modelo) * 1e4, 5e-3)


def main():
    curvas_de_credito()
    swap_un_periodo()
    sin_volatilidad()
    malla_corta()
    with tempfile.TemporaryDirectory() as carpeta:
        conn = base_del_desk(carpeta)
        antes = xva_por_contraparte(conn)
        incremental(conn, antes)
        conn.close()
    motor_anterior()
    comun.terminar()


if __name__ == "__main__":
    main()
