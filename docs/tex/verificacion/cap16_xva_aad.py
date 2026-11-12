"""Ejemplos verificables del capítulo 16 (sensibilidades del XVA por diferenciación adjunta).

Todos los valores salen del código del proyecto: `qfxva` (`ExposureEngine.xva_sensitivities`, `simulate`,
`compute_xva`, `bootstrap_cds_curve`) y `desk.api.risk.xva_sens` (la lógica de `GET /api/xva/sensitivities`) sobre
una base SQLite temporal con el snapshot MX-DEMO. Las magnitudes marcadas «recálculo» en el texto se rehacen aquí
con la stdlib siguiendo las ecuaciones del capítulo y el script exige que coincidan con el código.

Los valores de Monte Carlo son reproducibles porque las semillas son fijas (`std::mt19937_64` sembrado con
(semilla, trayectoria)); con otra biblioteca estándar cambiarían dentro de su error estándar. Las derivadas por
choque se calculan con las MISMAS trayectorias que las adjuntas (misma semilla), que es lo que las hace comparables.

Necesita `qfxva` compilado con XAD (`QF_WITH_XAD`, activo por omisión): sin él no hay nada que verificar.
"""
import math
import os
import tempfile

import comun  # primero: arregla sys.path
import cap14_xva as c14  # la forma cerrada del swap de un periodo (capítulo 14) y las curvas planas
from desk.api import db, market, portfolio
from desk.api import fixings as fixing_store
from desk.api.qf import qfpy  # noqa: F401  (qfpy se carga antes que qfxva)
from desk.api.risk import credit_curves, xva, xva_sens
from desk.api.seed_market import seed_market
import qfxva

BP = 1e-4
MODELO = c14.MODELO_DEMO  # a_M, sigma_M, a_U, sigma_U, vol FX, rho_MU, rho_MX, rho_UX


def verificar(id, valor, decimales):
    """Compara con el valor impreso en el .tex, que lleva `decimales` decimales: tolerancia = media unidad del último."""
    comun.comprobar(id, valor, 0.5 * 10.0 ** (-decimales))


def central(mas, menos, ancho):
    """Diferencia central de ternas (CVA, DVA, FVA) con el ancho del intervalo."""
    return [(a - b) / ancho for a, b in zip(mas, menos)]


# ------------------------------------------------------------------------------------------------ AAD contra choque

DIAS = list(range(0, 751, 30))
CP_TRAMOS, PROPIA_TRAMOS = ([1.0, 3.0], [0.015, 0.025]), ([1.0, 3.0], [0.006, 0.010])
LGD_C, LGD_O, FONDEO = 0.6, 0.5, 0.005


def conjunto():
    """IRS TIIE-F pagador de 100 M al 6.5 % (26 periodos de 28 días) y IRS SOFR receptor de 5 M USD al 4 %."""
    mxn = qfxva.RateSwapSpec(qfxva.SwapCurrency.MXN, 100e6, 0.065, True, 0, [28 * (k + 1) for k in range(26)], 1.0)
    usd = qfxva.RateSwapSpec(qfxva.SwapCurrency.USD, 5e6, 0.04, False, 0, [91 * (k + 1) for k in range(8)], 1.0)
    return qfxva.NettingSetSpec(swaps=[mxn, usd])


def motor(tiie=None, sofr=None, spot=18.6, modelo=MODELO):
    mercado = qfxva.ExposureMarket(tiie or c14.plana(0.07), sofr or c14.plana(0.04), spot)
    return qfxva.ExposureEngine(mercado, qfxva.ExposureModel(*modelo), qfxva.SimConfig(400, 42, 0.95, DIAS))


def xva_de(eng, spec, cp):
    """(CVA, DVA, FVA) por simulación y `compute_xva`: el camino de doble precisión, sin derivadas."""
    perfil = eng.simulate([spec])[0]
    x = qfxva.compute_xva(perfil, cp, LGD_C, qfxva.PiecewiseHazardCurve(*PROPIA_TRAMOS), LGD_O, FONDEO)
    return [x.cva, x.dva, x.fva]


def aad_contra_choque():
    spec = conjunto()
    cp = qfxva.PiecewiseHazardCurve(*CP_TRAMOS)
    propia = qfxva.PiecewiseHazardCurve(*PROPIA_TRAMOS)
    base = motor()
    s = base.xva_sensitivities(spec, cp, LGD_C, propia, LGD_O, FONDEO)

    # el valor de las mismas trayectorias es el de computeXva (hasta redondeo) y no depende del número de hilos
    ref = xva_de(base, spec, cp)
    for calculado, esperado in zip((s.value.cva, s.value.dva, s.value.fva), ref):
        assert abs(calculado - esperado) <= 1e-12 * abs(esperado)
    uno = base.xva_sensitivities(spec, cp, LGD_C, propia, LGD_O, FONDEO, max_threads=1)
    assert all(abs(a - b) <= 1e-9 * abs(b) + 1e-9 for a, b in zip(s.cva.tiie, uno.cva.tiie))
    verificar("cap16-aad-valor-cva", s.value.cva, 4)

    tiie, sofr, h = c14.plana(0.07), c14.plana(0.04), 0.1  # h: pb de tasa cero (1e-5 en tasa)
    sigma_mas = lambda d: MODELO[:1] + (MODELO[1] + d,) + MODELO[2:]  # noqa: E731
    cp_mas = lambda d: qfxva.PiecewiseHazardCurve(CP_TRAMOS[0], [CP_TRAMOS[1][0] + d, CP_TRAMOS[1][1]])  # noqa: E731
    # insumo -> (derivada adjunta por unidad, factor a la unidad del reporte, choque central en esa unidad)
    filas = {
        "tiie-2a": (lambda g: g.tiie[3], BP, central(
            xva_de(motor(tiie=tiie.bumped(3, h)), spec, cp), xva_de(motor(tiie=tiie.bumped(3, -h)), spec, cp), 2 * h)),
        "sofr-2a": (lambda g: g.sofr[3], BP, central(
            xva_de(motor(sofr=sofr.bumped(3, h)), spec, cp), xva_de(motor(sofr=sofr.bumped(3, -h)), spec, cp), 2 * h)),
        "spot": (lambda g: g.spot, 0.01 * 18.6, central(
            xva_de(motor(spot=18.6 + 1e-3), spec, cp), xva_de(motor(spot=18.6 - 1e-3), spec, cp), 2e-3 / (0.01 * 18.6))),
        "sigma": (lambda g: g.sigma_mxn, BP, central(
            xva_de(motor(modelo=sigma_mas(1e-5)), spec, cp), xva_de(motor(modelo=sigma_mas(-1e-5)), spec, cp), 2e-5 / BP)),
        "hazard": (lambda g: g.counterparty_hazard[0], BP, central(
            xva_de(base, spec, cp_mas(1e-6)), xva_de(base, spec, cp_mas(-1e-6)), 2e-6 / BP)),
    }
    mayor = 0.0
    for nombre, (elegir, factor, choque) in filas.items():
        adjunta = [elegir(g) * factor for g in (s.cva, s.dva, s.fva)]
        for a, c in zip(adjunta, choque):  # tolerancia de R4: max(1 %, 1e-4 MXN por unidad del reporte)
            assert abs(a - c) <= max(0.01 * abs(c), 1e-4), (nombre, a, c)
            if abs(c) >= 1e-2:  # la diferencia relativa solo tiene sentido donde la derivada no es (casi) cero
                mayor = max(mayor, abs(a - c) / abs(c))
        verificar("cap16-aad-%s" % nombre, adjunta[0], 3)
        verificar("cap16-choque-%s" % nombre, choque[0], 3)
    verificar("cap16-aad-dif-max", 100.0 * mayor, 4)

    # DV01 paralelo de TIIE-F: la suma de los pilares frente al desplazamiento de toda la curva
    dv01_aad = BP * sum(s.cva.tiie)
    dv01_choque = (xva_de(motor(tiie=tiie.parallel_bump(h)), spec, cp)[0]
                   - xva_de(motor(tiie=tiie.parallel_bump(-h)), spec, cp)[0]) / (2 * h)
    assert abs(dv01_aad - dv01_choque) <= 0.01 * abs(dv01_choque)
    verificar("cap16-aad-dv01", dv01_aad, 3)
    verificar("cap16-choque-dv01", dv01_choque, 3)


# ------------------------------------------------------------------------------------------------ sin volatilidad

def sin_volatilidad():
    """Swap de un periodo (capítulo 14) con volatilidades cero: toda trayectoria es la misma y V/B = N(1 - F)
    constante hasta el pago, F = gamma P(0,T). Las derivadas del CVA y el FVA son entonces las de una expresión
    cerrada en la tasa cero del pilar de 2 años, en las intensidades y en el fondeo."""
    n, k, t_dias, r = c14.N0, c14.K0, c14.T0, c14.R0
    dias = list(range(0, t_dias + 1, 10))
    mercado = qfxva.ExposureMarket(c14.plana(r), c14.plana(0.04), 18.6)
    modelo = qfxva.ExposureModel(0.05, 0.0, 0.03, 0.0, 0.0, 0.35, 0.30, -0.10)
    eng = qfxva.ExposureEngine(mercado, modelo, qfxva.SimConfig(8, 20261110, 0.95, dias))
    spec = qfxva.NettingSetSpec(swaps=[qfxva.RateSwapSpec(qfxva.SwapCurrency.MXN, n, k, True, 0, [t_dias], 1.0)])
    lam_c, lam_o, lgd, s_f = 0.02, 0.01, 0.6, 0.005
    s = eng.xva_sensitivities(spec, qfxva.FlatHazardRate(lambda_=lam_c), lgd, qfxva.FlatHazardRate(lambda_=lam_o), lgd, s_f)

    gamma = 1.0 + k * t_dias / 360.0
    f = gamma * math.exp(-r * t_dias / 365.0)  # F = gamma P(0, T), T = 2 años = el pilar de 2 años
    ultimo = (t_dias - 10) / 365.0  # 720 d: la última fecha con el flujo todavía dentro de V
    sup_c = lambda t: math.exp(-lam_c * t)  # noqa: E731
    exacto_cva = lgd * n * (1.0 - f) * (1.0 - sup_c(ultimo))
    assert abs(s.value.cva - exacto_cva) <= 1e-12 * exacto_cva and s.value.dva == 0.0
    suma_ss = sum(sup_c(d / 365.0) * math.exp(-lam_o * d / 365.0) * 10 / 365.0 for d in dias[1:] if d < t_dias)
    d_cva = BP * lgd * n * 2.0 * f * (1.0 - sup_c(ultimo))  # dCVA/dz(2 años) por pb: dF/dz = -T F con T = 2
    d_fva = BP * s_f * n * 2.0 * f * suma_ss
    d_haz = BP * lgd * n * (1.0 - f) * ultimo * sup_c(ultimo)  # dCVA/dh_c por pb
    d_fondeo = BP * n * (1.0 - f) * suma_ss  # dFVA/ds_f por pb
    assert abs(BP * s.cva.tiie[3] - d_cva) <= 1e-9 * d_cva
    assert abs(BP * s.fva.tiie[3] - d_fva) <= 1e-9 * d_fva
    assert abs(BP * s.cva.counterparty_hazard[0] - d_haz) <= 1e-9 * d_haz
    assert abs(BP * s.fva.funding_spread - d_fondeo) <= 1e-9 * d_fondeo
    assert all(abs(BP * v) <= 1e-9 * d_cva for i, v in enumerate(s.cva.tiie) if i != 3)  # los demás pilares: cero
    assert all(v == 0.0 for v in list(s.cva.sofr) + list(s.fva.sofr) + [s.cva.spot, s.dva.tiie[3]])
    verificar("cap16-cero-valor-cva", exacto_cva, 4)
    verificar("cap16-cero-dcva-analitica", d_cva, 6)
    verificar("cap16-cero-dcva-aad", BP * s.cva.tiie[3], 6)
    verificar("cap16-cero-dfva-analitica", d_fva, 6)
    verificar("cap16-cero-dfva-aad", BP * s.fva.tiie[3], 6)
    verificar("cap16-cero-dhaz-analitica", d_haz, 6)
    verificar("cap16-cero-dhaz-aad", BP * s.cva.counterparty_hazard[0], 6)


# ------------------------------------------------------------------------------------------------ insesgadez

def vega_forma_cerrada():
    """dCVA/dsigma_M, dDVA/dsigma_M y dFVA/dsigma_M del swap de un periodo (capítulo 14): la derivada exacta de la
    forma cerrada (diferencia central de la función analítica de cap14_xva) frente a la media de 20 lotes
    independientes de la derivada adjunta (3000 trayectorias cada uno): el estimador es insesgado."""
    dias = list(range(0, c14.T0 + 1, 10))  # la malla del capítulo 14, la misma en la forma cerrada y en el motor

    def cerrada(sigma):
        anterior, c14.S0 = c14.S0, sigma
        try:
            return c14.forma_cerrada(dias, 0.02, 0.01, 0.6, 0.6, 0.005)[:3]
        finally:
            c14.S0 = anterior

    h = 1e-5
    exacta = [BP * (a - b) / (2 * h) for a, b in zip(cerrada(c14.S0 + h), cerrada(c14.S0 - h))]  # por pb de vol normal
    spec = qfxva.NettingSetSpec(swaps=[qfxva.RateSwapSpec(qfxva.SwapCurrency.MXN, c14.N0, c14.K0, True, 0, [c14.T0], 1.0)])
    lotes, n = 20, 3000
    lista = []
    for b in range(lotes):
        mercado = qfxva.ExposureMarket(c14.plana(c14.R0), c14.plana(0.04), 18.6)
        config = qfxva.SimConfig(n, 20261110 + 7919 * b, 0.95, dias)
        eng = qfxva.ExposureEngine(mercado, qfxva.ExposureModel(*MODELO), config)
        s = eng.xva_sensitivities(spec, qfxva.FlatHazardRate(lambda_=0.02), 0.6, qfxva.FlatHazardRate(lambda_=0.01), 0.6, 0.005)
        lista.append([BP * g.sigma_mxn for g in (s.cva, s.dva, s.fva)])
    zs = []
    for k, nombre in enumerate(("cva", "dva", "fva")):
        xs = [fila[k] for fila in lista]
        media = sum(xs) / lotes
        ee = math.sqrt(sum((x - media) ** 2 for x in xs) / (lotes - 1) / lotes)
        zs.append((media - exacta[k]) / ee)
        verificar("cap16-vega-exacta-%s" % nombre, exacta[k], 4)
        verificar("cap16-vega-media-%s" % nombre, media, 4)
        verificar("cap16-vega-ee-%s" % nombre, ee, 4)
    assert max(abs(z) for z in zs) < 3.0
    verificar("cap16-vega-z-max", max(abs(z) for z in zs), 3)


# ------------------------------------------------------------------------------------------------ desk

CP, CP_XCCY = "Banco Ejemplo", "Banco Cruzado"
COTIZ_CP = (90, 100, 110, 125, 135, 150)
COTIZ_PROPIA = (70, 80, 90, 105, 115, 125)


def base_del_desk(carpeta):
    """Base temporal: MX-DEMO, un IRS TIIE-F pagador en `CP` y un cross currency swap en `CP_XCCY`, con curvas de crédito."""
    conn = db.connect(os.path.join(carpeta, "sens.db"))
    db.init_schema(conn)
    seed_market(conn)
    portfolio.create_trade(conn, {
        "product": "irs", "counterparty": CP, "trade_date": "2026-11-10",
        "params": {"curve": "TIIE-F", "side": "payer", "notional": 200e6, "periods": 26, "fixed_rate": 0.065}})
    portfolio.create_trade(conn, {
        "product": "xccy_swap", "counterparty": CP_XCCY, "trade_date": "2026-11-10",
        "params": {"side": "pay_usd", "notional_usd": 10e6, "periods": 26, "fx_rate": 18.2, "spread": 0.0005,
                   "exchange": "both"}})
    for entidad, spreads in ((CP, COTIZ_CP), (CP_XCCY, COTIZ_CP), (credit_curves.OWN, COTIZ_PROPIA)):
        credit_curves.put_curve(conn, entidad, {
            "recovery": 0.4,
            "quotes": [{"tenor_years": t, "spread": s / 1e4} for t, s in zip((1, 2, 3, 5, 7, 10), spreads)]})
    xva.put_params(conn, {"n_paths": 400})
    conn.commit()
    return conn


class Contraparte:
    """Lo que `xva_sens.compute` arma, para repreciar a mano una contraparte con las mismas trayectorias."""

    def __init__(self, conn, nombre):
        self.mkt = market.load_context(conn, "MX-DEMO")
        self.params = xva.load_params(conn)
        self.modelo = xva.model_from_snapshot(self.mkt)[0]
        trades = xva.live_by_counterparty(conn, self.mkt)[nombre]
        self.spec, incluidas, _, _ = xva.build_set(trades, self.mkt, fixing_store.load_all(conn))
        report = xva.report_days(self.mkt.as_of, xva._last_maturity(trades, incluidas))
        self.dias = xva.integration_days(report, self.spec)
        self.cp, cp_rec, _ = xva.credit_for(conn, nombre, self.mkt)
        self.propia, propia_rec, _ = xva.own_credit(conn, self.mkt)
        self.lgd_c, self.lgd_o = 1.0 - cp_rec, 1.0 - propia_rec

    def perfil(self, mkt=None):
        return xva.engine(mkt or self.mkt, self.modelo, self.params, self.dias).simulate([self.spec])[0]

    def xva(self, perfil, cp=None):
        x = qfxva.compute_xva(perfil, cp or self.cp, self.lgd_c, self.propia, self.lgd_o, self.params["funding_spread"])
        return [x.cva, x.dva, x.fva]


def credito_y_api(conn):
    cuerpo = xva_sens.compute(conn, "MX-DEMO", CP)
    referencia = [c for c in xva.compute(conn, "MX-DEMO")["counterparties"] if c["counterparty"] == CP][0]
    for clave in ("cva_mxn", "dva_mxn", "fva_mxn", "total_mxn"):
        assert cuerpo["xva"][clave] == referencia[clave]  # el XVA de referencia es el de GET /api/xva, igual a igual
    verificar("cap16-api-cva", cuerpo["xva"]["cva_mxn"], 4)
    verificar("cap16-api-n-insumos", float(cuerpo["n_inputs"]), 0)

    c = Contraparte(conn, CP)
    fila = credit_curves.current(conn)[CP]
    cds = {r["tenor"]: r for r in cuerpo["credit"]["counterparty"]["cds"]}
    haz = cuerpo["credit"]["counterparty"]["hazards"]

    def curva_con(k, delta):  # el bootstrap vuelto a correr con la cotización k movida `delta`
        movidas = [dict(q, spread=q["spread"] + (delta if j == k else 0.0)) for j, q in enumerate(fila["quotes"])]
        return credit_curves.build_curve(qfxva, dict(fila, quotes=movidas), c.mkt)

    # jacobiano del bootstrap por reprecio: J[k][i] = d h_i / d s_k (diferencia central de 0.01 pb)
    bump = xva_sens.CDS_BUMP
    jac = [[(u - d) / (2 * bump) for u, d in zip(curva_con(k, bump).hazards(), curva_con(k, -bump).hazards())]
           for k in range(len(fila["quotes"]))]
    assert all(jac[k][i] == 0.0 for k in range(6) for i in range(k))  # triangular: h_i no depende de s_k si k > i
    verificar("cap16-cred-j11", jac[0][0], 6)
    verificar("cap16-cred-j12", jac[0][1], 6)
    verificar("cap16-cred-j22", jac[1][1], 6)
    verificar("cap16-cred-dcva-h1", haz[0]["cva"], 4)
    verificar("cap16-cred-dcva-h2", haz[1]["cva"], 4)

    # regla de la cadena: dCVA/ds_k = sum_i dCVA/dh_i J[k][i]; y el reprecio del CDS con el mismo perfil
    perfil = c.perfil()
    for k, tenor in enumerate(("1Y", "2Y")):
        cadena = sum(haz[i]["cva"] * jac[k][i] for i in range(6))
        assert abs(cadena - cds[tenor]["cva"]) <= 1e-9 * abs(cadena)
        valores = [c.xva(perfil, curva_con(k, d))[0] for d in (bump, -bump)]
        choque = (valores[0] - valores[1]) / (2 * bump) * BP
        assert abs(cds[tenor]["cva"] - choque) <= max(0.01 * abs(choque), 1e-4)
        verificar("cap16-cred-dcva-cds%d-api" % (k + 1), cds[tenor]["cva"], 6)
        verificar("cap16-cred-dcva-cds%d-choque" % (k + 1), choque, 6)

    # independiente del adjunto: dCVA/dh_i desde el perfil descontado, -LGD sum_j EPE*_j [l_i S]_{j-1}^{j}
    vertices, tasas = c.cp.times(), c.cp.hazards()
    ell = lambda i, t: max(min(t, vertices[i] if i + 1 < len(vertices) else t) - (vertices[i - 1] if i else 0.0), 0.0)  # noqa: E731
    sup = lambda t: math.exp(-sum(tasas[i] * ell(i, t) for i in range(len(tasas))))  # noqa: E731
    veces = [d / 365.0 for d in c.dias]
    for i in (0, 1):
        analitica = -c.lgd_c * sum(
            perfil.epe_disc[j] * (ell(i, veces[j - 1]) * sup(veces[j - 1]) - ell(i, veces[j]) * sup(veces[j]))
            for j in range(1, len(veces)))
        assert abs(BP * analitica - haz[i]["cva"]) <= 1e-9 * abs(haz[i]["cva"]), (i, analitica, haz[i]["cva"])

    # el FVA es lineal en el diferencial de fondeo: dFVA/ds_f = FVA / s_f
    esperado = BP * cuerpo["xva"]["fva_mxn"] / c.params["funding_spread"]
    assert abs(cuerpo["funding"]["fva"] - esperado) <= 1e-9 * abs(esperado)
    verificar("cap16-cred-fondeo", cuerpo["funding"]["fva"], 4)


def parcial_frente_a_total(conn):
    """Cross currency swap con descuento MXN-USD: el DV01 del CVA a TIIE-F como derivada parcial (MXN-USD fija) y como
    derivada total con la curva MXN-USD recalibrada por el desk (`MarketContext.shifted`)."""
    cuerpo = xva_sens.compute(conn, "MX-DEMO", CP_XCCY)
    c = Contraparte(conn, CP_XCCY)
    aad = cuerpo["curves"][0]["dv01"]
    assert [x["curve"] for x in cuerpo["curves"]] == ["TIIE-F", "SOFR", market.CSA_CURVE]
    h = 0.1  # pb
    mas, menos = c.mkt.shifted("TIIE-F", parallel_bp=h), c.mkt.shifted("TIIE-F", parallel_bp=-h)
    total = central(c.xva(c.perfil(mas)), c.xva(c.perfil(menos)), 2 * h)
    col_mas, col_menos = mas.curves[market.CSA_CURVE].rates(), menos.curves[market.CSA_CURVE].rates()
    fija = []
    for m in (mas, menos):  # la misma curva TIIE-F desplazada, pero con la MXN-USD original
        m.curves = dict(m.curves)
        m.curves[market.CSA_CURVE] = c.mkt.curves[market.CSA_CURVE]
        fija.append(c.xva(c.perfil(m)))
    parcial = central(fija[0], fija[1], 2 * h)
    for calculado, clave in zip(parcial, ("cva", "dva", "fva")):  # la AAD es la derivada parcial (MXN-USD fija)
        assert abs(calculado - aad[clave]) <= max(0.01 * abs(aad[clave]), 1e-4), (clave, calculado, aad[clave])
    # reconstrucción de la total: parcial + sum_l (dX/dz_col,l) * (cuánto se mueve el pilar l de MXN-USD por 1 pb de TIIE-F)
    mueve = [(a - b) / (2 * h) / BP for a, b in zip(col_mas, col_menos)]
    reconstruida = aad["cva"] + sum(p["cva"] * dz for p, dz in zip(cuerpo["curves"][2]["pillars"], mueve))
    assert abs(reconstruida - total[0]) <= 0.01 * abs(total[0])
    verificar("cap16-parcial-aad-cva", aad["cva"], 3)
    verificar("cap16-parcial-choque-cva", parcial[0], 3)
    verificar("cap16-total-choque-cva", total[0], 3)
    verificar("cap16-total-reconstruida-cva", reconstruida, 3)
    verificar("cap16-parcial-aad-total", aad["total"], 3)
    verificar("cap16-parcial-choque-total", parcial[0] - parcial[1] + parcial[2], 3)
    verificar("cap16-total-choque-total", total[0] - total[1] + total[2], 3)
    verificar("cap16-mueve-2a", mueve[4], 4)
    verificar("cap16-mueve-10a", mueve[8], 4)


def main():
    if not getattr(qfxva, "HAS_XAD", False):
        raise SystemExit("qfxva se compiló sin XAD (QF_WITH_XAD=OFF): no hay sensibilidades que verificar")
    aad_contra_choque()
    sin_volatilidad()
    vega_forma_cerrada()
    with tempfile.TemporaryDirectory() as carpeta:
        conn = base_del_desk(carpeta)
        credito_y_api(conn)
        parcial_frente_a_total(conn)
        conn.close()
    comun.terminar()


if __name__ == "__main__":
    main()
