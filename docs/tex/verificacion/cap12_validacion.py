"""Ejemplos verificables del capítulo 12 (validación contra QuantLib).

Corre con el Python del backend (sin QuantLib): el PV del desk se recalcula con el código del proyecto
(`desk.validation.export_cases` sobre una base en memoria con el snapshot sintético MX-DEMO) y el PV de QuantLib
se lee de `desk/validation/reference.json`, que se versiona justamente para repetir la comparación sin QuantLib.
"""
import json
import math

import comun  # primero: arregla sys.path
from desk.api import market
from desk.validation import common, export_cases

REFERENCIA = comun.RAIZ / "desk" / "validation" / "reference.json"

conn = export_cases.demo_conn()
mkt = market.load_context(conn, common.SNAPSHOT_ID)
casos = {c["id"]: c for c in export_cases.build_cases(conn, mkt)}
curvas = export_cases.export_curves(mkt)
with open(REFERENCIA, encoding="utf-8") as f:
    pv_ref = {r["id"]: r["pv_ref"] for r in json.load(f)["cases"]}


def df_intermedio_tiie():
    """Primera fecha intermedia de TIIE-F: (día, DF del desk, ceros de los pilares 168 y 364, cero interpolado a mano)."""
    fila = curvas["TIIE-F"]["checks"][0]
    curva = mkt.curves["TIIE-F"]
    z0, z1 = curva.zero_rate(168 / 365.0), curva.zero_rate(364 / 365.0)
    z = z0 + (fila["days"] - 168) / (364 - 168) * (z1 - z0)
    a_mano = math.exp(-z * fila["days"] / 365.0)
    if abs(a_mano - fila["df"]) > 1e-14:
        raise AssertionError("la interpolación a mano difiere del DF del desk: %r vs %r" % (a_mano, fila["df"]))
    return fila["days"], fila["df"], z0, z1, z


def pv_bond08_fechas_enteras():
    """PV de bond-08 con las convenciones de QuantLib (fechas enteras, cupón ACT/365) y los DF de la curva del desk."""
    p = casos["bond-08"]["params"]
    curva = mkt.curves[p["curve"]]
    dias = [round(i * 365.0 / p["frequency"]) for i in range(1, p["periods"] + 1)]
    previo, pv = 0, 0.0
    for k, d in enumerate(dias):
        flujo = p["face"] * p["coupon_rate"] * (d - previo) / 365.0
        if k == len(dias) - 1:
            flujo += p["face"]
        pv += flujo * curva.discount_factor(d / 365.0)
        previo = d
    return pv


def diferencias(id_caso):
    c = casos[id_caso]
    return common.diffs(c["pv_desk"], pv_ref[id_caso], c["notional"])


dia, df, z168, z364, z_dia = df_intermedio_tiie()
comun.comprobar("cap12-dia-intermedio", float(dia), 0.5)
comun.comprobar("cap12-cero-168", z168, 1e-10)
comun.comprobar("cap12-cero-364", z364, 1e-10)
comun.comprobar("cap12-cero-intermedio", z_dia, 1e-10)
comun.comprobar("cap12-df-intermedio", df, 1e-11)
comun.comprobar("cap12-pv-bond08", casos["bond-08"]["pv_desk"], 1e-4)
comun.comprobar("cap12-pv-ref-bond08", pv_ref["bond-08"], 1e-4)
comun.comprobar("cap12-pv-bond08-fechas-enteras", pv_bond08_fechas_enteras(), 1e-4)
abs_b, rel_b = diferencias("bond-08")
comun.comprobar("cap12-dif-abs-bond08", abs_b, 5e-3)
comun.comprobar("cap12-dif-rel-bond08", rel_b, 5e-11)
abs_s, rel_s = diferencias("swaption-03")
comun.comprobar("cap12-dif-abs-swaption03", abs_s, 5e-5)
comun.comprobar("cap12-dif-rel-swaption03", rel_s, 5e-12)
comun.terminar()
