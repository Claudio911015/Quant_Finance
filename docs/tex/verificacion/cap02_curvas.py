"""Ejemplos verificables del capítulo 2 (curvas). Las cotizaciones son las de MX-DEMO, escritas aquí."""
import math

import comun  # primero: arregla sys.path
from desk.api.qf import qfpy

OIS, DEP = qfpy.OisQuoteType.Ois, qfpy.OisQuoteType.Deposit
SPOT = 18.60
TIIE_F = [(1, 0.0700), (28, 0.0698), (84, 0.0692), (168, 0.0685), (364, 0.0675), (728, 0.0670),
          (1092, 0.0672), (1820, 0.0680), (2548, 0.0690), (3640, 0.0705)]
SOFR = [(1, 0.0390), (30, 0.0385), (91, 0.0380), (182, 0.0375), (365, 0.0370), (730, 0.0355),
        (1095, 0.0350), (1825, 0.0355), (2555, 0.0365), (3650, 0.0380)]
FORWARDS = [(28, 0.0438), (84, 0.1317), (168, 0.2637), (364, 0.5745)]
BASIS = [(728, -0.0010), (1092, -0.0012), (1820, -0.0015), (2548, -0.0017), (3640, -0.0020)]


def curva(filas, periodo, deposito=True):
    """Curva OIS de `qfpy`; la primera cotización es depósito salvo `deposito=False`."""
    return qfpy.bootstrap_ois(
        [qfpy.OisQuote(d, r, DEP if (i == 0 and deposito) else OIS) for i, (d, r) in enumerate(filas)], periodo)


def mxn_usd(tiie, sofr):
    """MXN-USD de MX-DEMO con el periodo de 28 días de la base."""
    return qfpy.bootstrap_xccy_discount([qfpy.FxForwardQuote(d, p) for d, p in FORWARDS],
                                        [qfpy.XccyBasisQuote(d, s) for d, s in BASIS], SPOT, sofr, tiie, 28)


def sofr_df_730():
    """DF a 730 días de dos OIS anuales (3.70 % a 365 d, 3.55 % a 730 d); a mano: eq:cap02-cerrada."""
    c = curva([(365, 0.0370), (730, 0.0355)], 365, deposito=False)
    tau = 365.0 / 360.0
    p1 = 1.0 / (1.0 + 0.0370 * tau)
    p2 = (1.0 - 0.0355 * tau * p1) / (1.0 + 0.0355 * tau)
    assert abs(c.discount_factor(1.0) - p1) < 1e-12 and abs(c.discount_factor(2.0) - p2) < 1e-12
    return c.discount_factor(730 / 365.0)


def tiie_par_168():
    """Tasa par de 168 días (6 cupones de 28 d) sobre la TIIE-F de MX-DEMO, con OisSwap (eq:cap02-par)."""
    c = curva(TIIE_F, 28)
    env = qfpy.MarketEnvironment()
    env.add_curve("TIIE-F", c)
    par = qfpy.OisSwap(1.0, 0.0, 168, 28, qfpy.SwapType.Payer, "TIIE-F").par_rate(env)
    previo, anualidad = 0, 0.0
    for d in qfpy.ois_payment_days(168, 28):
        anualidad += (d - previo) / 360.0 * c.discount_factor(d / 365.0)
        previo = d
    assert abs(par - (1.0 - c.discount_factor(168 / 365.0)) / anualidad) < 1e-12
    return par


def tiie_df_168():
    """Factor de descuento del pilar de 168 días de la TIIE-F de MX-DEMO."""
    return curva(TIIE_F, 28).discount_factor(168 / 365.0)


def tiie_zero_56():
    """Tasa cero a 56 días: punto medio de los pilares de 28 y 84 días (eq:cap02-lineal)."""
    c = curva(TIIE_F, 28)
    medio = 0.5 * (c.zero_rate(28 / 365.0) + c.zero_rate(84 / 365.0))
    assert abs(c.zero_rate(56 / 365.0) - medio) < 1e-14
    return c.zero_rate(56 / 365.0)


def tiie_fwd_28_84():
    """Forward continua entre los pilares de 28 y 84 días (eq:cap02-forward)."""
    c = curva(TIIE_F, 28)
    p1, p2 = c.discount_factor(28 / 365.0), c.discount_factor(84 / 365.0)
    assert abs(c.forward_rate(28 / 365.0, 84 / 365.0) - math.log(p1 / p2) / (56 / 365.0)) < 1e-12
    return c.forward_rate(28 / 365.0, 84 / 365.0)


def _entorno():
    tiie, sofr = curva(TIIE_F, 28), curva(SOFR, 365)
    x = mxn_usd(tiie, sofr)
    env = qfpy.MarketEnvironment()
    for nombre, c in (("TIIE-F", tiie), ("SOFR", sofr), ("MXN-USD", x)):
        env.add_curve(nombre, c)
    env.set_spot("USDMXN", SPOT)
    return tiie, sofr, x, env


def mxnusd_df_28():
    """DF del pilar de 28 días de MXN-USD: paridad cubierta con los puntos forward (eq:cap02-paridad)."""
    _, sofr, x, _ = _entorno()
    assert abs(x.discount_factor(28 / 365.0) - SPOT * sofr.discount_factor(28 / 365.0) / (SPOT + 0.0438)) < 1e-14
    return x.discount_factor(28 / 365.0)


def forward_implicito_28():
    """Forward a 28 días implícito en MXN-USD: reproduce S + puntos (eq:cap02-fwd-implicito)."""
    return qfpy.FxForward(1.0, 1.0, 28, qfpy.FxSide.Buy, "USDMXN", "MXN-USD", "SOFR").forward_rate(_entorno()[3])


def mxnusd_df_728():
    """DF del pilar de 728 días de MXN-USD (primer pilar de base, resuelto con Brent)."""
    tiie, _, x, env = _entorno()
    s, dias = BASIS[0][1], qfpy.ois_payment_days(728, 28)
    previo, residuo = 0, -1.0 + x.discount_factor(728 / 365.0)
    for d in dias:  # eq:cap02-base, con los DF que entrega el código
        tau = (d - previo) / 360.0
        previo_df = 1.0 if previo == 0 else tiie.discount_factor(previo / 365.0)
        residuo += (previo_df / tiie.discount_factor(d / 365.0) - 1.0 + s * tau) * x.discount_factor(d / 365.0)
        previo = d
    assert abs(residuo) < 1e-12
    swap = qfpy.XccySwap(1.0, SPOT, s, 0, dias, 1.0, 1.0, qfpy.XccySide.PayUsd, True, True)
    assert abs(swap.npv(env)) < 1e-10
    return x.discount_factor(728 / 365.0)


comun.comprobar("cap02-sofr-df-730", sofr_df_730(), 1e-9)
comun.comprobar("cap02-tiie-df-168", tiie_df_168(), 1e-9)
comun.comprobar("cap02-tiie-par-168", tiie_par_168(), 1e-9)
comun.comprobar("cap02-tiie-zero-56", tiie_zero_56(), 1e-9)
comun.comprobar("cap02-tiie-fwd-28-84", tiie_fwd_28_84(), 1e-9)
comun.comprobar("cap02-mxnusd-df-28", mxnusd_df_28(), 1e-9)
comun.comprobar("cap02-fwd-implicito-28", forward_implicito_28(), 1e-9)
comun.comprobar("cap02-mxnusd-df-728", mxnusd_df_728(), 1e-9)
_tiie, _sofr, _x, _env = _entorno()
_t28, _t84, _t728 = 28 / 365.0, 84 / 365.0, 728 / 365.0
_paridad = qfpy.FxForward(1.0, 1.0, 28, qfpy.FxSide.Buy, "USDMXN", "TIIE-F", "SOFR").forward_rate(_env)
for _id, _valor in (("cap02-sofr-df-365", _sofr.discount_factor(1.0)), ("cap02-sofr-df-28", _sofr.discount_factor(_t28)),
                    ("cap02-tiie-zero-28", _tiie.zero_rate(_t28)), ("cap02-tiie-zero-84", _tiie.zero_rate(_t84)),
                    ("cap02-tiie-df-28", _tiie.discount_factor(_t28)), ("cap02-tiie-df-84", _tiie.discount_factor(_t84)),
                    ("cap02-tiie-df-728", _tiie.discount_factor(_t728)), ("cap02-fwd-paridad-28", _paridad)):
    comun.comprobar(_id, _valor, 1e-9)
comun.terminar()
