"""Ejemplos verificables del capítulo 6 (bonos).

Precio, duración, convexidad y rendimiento salen de qfpy.Bond; el corrido y los precios del bono envejecido, de
desk.api.aging (que arma el qfpy.Bond con calendario explícito). La conversión a rendimiento periódico es la
fórmula del texto aplicada al rendimiento que devuelve qfpy.
"""
import math
from datetime import date, timedelta
from types import SimpleNamespace

import comun  # primero: arregla sys.path
from desk.api import aging
from desk.api.qf import qfpy

PILARES = [0.25, 0.5, 1, 2, 5, 10, 30]


def plana(r):
    """Curva cero plana a `r` (composición continua, interpolación lineal)."""
    return qfpy.YieldCurve(PILARES, [r] * len(PILARES), qfpy.InterpolationMethod.Linear)


def bono_regular():
    curva = plana(0.06)
    bono = qfpy.Bond(1e6, 0.08, 4, 2.0)  # 2 años, cupón 8 % semestral: 40 000 x3 y 1 040 000
    precio = bono.price(curva)
    flujos = bono.cash_flow_schedule()
    assert abs(precio - sum(c * math.exp(-0.06 * t) for t, c in flujos)) < 1e-6
    comun.comprobar("cap06-precio-sucio", precio, 1e-4)
    comun.comprobar("cap06-duracion", bono.duration(curva), 1e-8)
    comun.comprobar("cap06-convexidad", bono.convexity(curva), 1e-8)
    # a la par (precio = nominal) el rendimiento continuo y su equivalente semestral
    y = getattr(bono, "yield")(1e6)
    comun.comprobar("cap06-rendimiento-par", y, 1e-9)
    comun.comprobar("cap06-rendimiento-semestral", 2.0 * (math.exp(y / 2.0) - 1.0), 1e-9)


def bono_envejecido():
    curva = plana(0.06)
    inicio = date(2026, 1, 2)
    operacion = {"start_date": inicio}
    terminos = {"curve": "TIIE-F", "face": 1e6, "coupon_rate": 0.08, "periods": 4, "frequency": 2.0}

    def cotizacion(dias):
        mkt = SimpleNamespace(as_of=inicio + timedelta(days=dias), curves={"TIIE-F": curva},
                              mxn_discount="TIIE-F", spot=1.0)
        return aging.bond_quote(operacion, terminos, mkt)

    q = cotizacion(90)
    # curva plana y ningún cupón pagado: el sucio es el precio del día del pacto capitalizado 90 días
    sucio_a_mano = qfpy.Bond(1e6, 0.08, 4, 2.0).price(curva) * math.exp(0.06 * 90 / 365)
    assert abs(q["dirty"] - sucio_a_mano) < 1e-6
    assert abs(q["dirty"] - q["clean"] - q["accrued"]) < 1e-9
    comun.comprobar("cap06-corrido", q["accrued"], 1e-4)
    comun.comprobar("cap06-precio-sucio-envejecido", q["dirty"], 1e-4)
    comun.comprobar("cap06-precio-limpio", q["clean"], 1e-4)
    # el día 183 el cupón del día 182 (365/2 = 182.5 redondea al par) lleva medio día de corrido
    comun.comprobar("cap06-corrido-dia-183", cotizacion(183)["accrued"], 1e-4)


bono_regular()
bono_envejecido()
comun.terminar()
