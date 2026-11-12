"""Ejemplos verificables del capítulo 10 (coberturas IFRS 9).

Base temporal con el snapshot MX-DEMO sembrado y tres snapshots rodados (+35, +70 y +364 días); un
crédito TIIE-F de 500 M a 13 periodos de 28 días, fijaciones de 7 %. Las relaciones se dan de alta y se
cierran con el código de la aplicación (`hedges.create_hedge`, `hedge_measure.close_period`); nada se
recalcula aquí con fórmulas propias salvo las comprobaciones aritméticas de la regla del menor.
"""
import comun  # primero: arregla sys.path
import os
import tempfile
from datetime import date, timedelta

from desk.api import db, fixings as fixing_store, hedge_effectiveness, hedge_measure, hedges, market, portfolio
from desk.api.seed_market import seed_market

D0 = date(2026, 11, 10)
FIN = D0 + timedelta(days=364)  # 13 periodos de 28 días: el swap tiene exactamente las fechas del crédito
FIN_FIJO = D0 + timedelta(days=28 * 26)
DOC = {k: "ejemplo" for k in ("risk_management_objective", "hedged_risk", "effectiveness_method", "ineffectiveness_sources")}
CREDITO = {"index": "TIIE-F", "notional": 500e6, "start_date": D0.isoformat(), "maturity_date": FIN.isoformat(),
           "side": "pays_floating"}


def entorno(carpeta):
    """Conexión a una base temporal con MX-DEMO, snapshots D1/D2/D3 y fijaciones TIIE-F de 7 %."""
    conn = db.connect(os.path.join(carpeta, "ejemplo.db"))
    db.init_schema(conn)
    seed_market(conn)
    for snapshot, dias in (("D1", 35), ("D2", 70), ("D3", 364)):
        market.roll_snapshot(conn, "MX-DEMO", {"id": snapshot, "as_of": (D0 + timedelta(days=dias)).isoformat()})
    filas, dia = ["index,date,value"], D0
    while dia < FIN:
        if dia.weekday() < 5:
            filas.append("TIIE-F,%s,0.07" % dia.isoformat())
        dia += timedelta(days=1)
    fixing_store.import_csv(conn, "\n".join(filas))
    conn.commit()
    return conn


def cobertura(conn, nocional, lado, tipo="cash_flow", partida="floating_loan", terminos=None, fin=FIN):
    """Swap TIIE-F a la par (sin `fixed_rate`) designado como cobertura; devuelve el id de la relación."""
    swap = portfolio.create_trade(conn, {
        "product": "irs", "counterparty": "Banco Alfa (sintético)", "snapshot": "MX-DEMO",
        "params": {"curve": "TIIE-F", "side": lado, "notional": nocional, "periods": 1},
        "start_date": D0.isoformat(), "maturity_date": fin.isoformat()})
    rel = hedges.create_hedge(conn, {
        "trade_id": swap["id"], "snapshot": "MX-DEMO", "hedge_type": tipo, "item_kind": partida,
        "item_terms": terminos or CREDITO, "fraction": 1.0, "documentation": DOC})
    conn.commit()
    return rel["id"]


def cerrar(conn, hid, snapshot):
    periodo = hedge_measure.close_period(conn, hid, {"snapshot": snapshot})
    conn.commit()
    return periodo


def regla_menor(conn):
    """Sobrecubierto (swap de 600 M), subcubierto (400 M) y de signo opuesto frente a un crédito de 500 M, cierre D1."""
    sobre = cerrar(conn, cobertura(conn, 600e6, "payer"), "D1")
    sub = cerrar(conn, cobertura(conn, 400e6, "payer"), "D1")
    opuesto = cerrar(conn, cobertura(conn, 500e6, "receiver"), "D1")
    comun.comprobar("cap10-inst-cum-1", sobre["inst_cum"], 1e-4)
    comun.comprobar("cap10-liq-inst-1", sobre["settled_period"], 1e-4)
    comun.comprobar("cap10-hypo-cum-1", sobre["hypo_cum"], 1e-4)
    comun.comprobar("cap10-liq-hip-1", sobre["hypo_settled_period"], 1e-4)
    comun.comprobar("cap10-inst-total", sobre["inst_total"], 1e-4)
    comun.comprobar("cap10-hypo-total", sobre["hypo_total"], 1e-4)
    comun.comprobar("cap10-efectiva", sobre["effective_cum"], 1e-4)
    comun.comprobar("cap10-inefectividad", sobre["ineffectiveness"], 1e-4)
    comun.comprobar("cap10-reserva-1", sobre["oci"], 1e-4)
    comun.comprobar("cap10-reciclaje-1", sobre["recycled"], 1e-4)
    comun.comprobar("cap10-sub-efectiva", sub["effective_cum"], 1e-4)
    comun.comprobar("cap10-opuesto-inefectividad", opuesto["ineffectiveness"], 1e-4)


def reserva_acumulada(conn):
    """Segundo cierre (D2) de una cobertura sobrecubierta de 600 M: reserva, asiento a ORI e identidad del periodo."""
    hid = cobertura(conn, 600e6, "payer")
    cerrar(conn, hid, "D1")
    p2 = cerrar(conn, hid, "D2")
    ori = [e for e in p2["entries"] if e["account"] == hedges.ACC_OCI][0]
    comun.comprobar("cap10-efectiva-2", p2["effective_cum"], 1e-4)
    comun.comprobar("cap10-reserva-2", p2["oci"], 1e-4)
    comun.comprobar("cap10-asiento-ori-2", ori["credit"], 5e-3)
    comun.comprobar("cap10-reciclaje-2", p2["recycled"], 1e-4)
    comun.comprobar("cap10-inefectividad-2", p2["ineffectiveness"], 1e-4)
    comun.comprobar("cap10-pnl-instrumento-2", p2["instrument_pnl"], 1e-4)


def asiento_con_residuo():
    """`journal` con saldos cuyo redondeo a centavos deja un centavo de descuadre."""
    cifras = {"ineffectiveness": 40.001, "recycled": 0.0}
    saldos = {hedges.ACC_DERIVATIVE: 100.005, hedges.ACC_OCI: -60.004, hedges.ACC_CASH: 0.0, hedges.ACC_ITEM_ADJ: 0.0}
    lineas = {e["account"]: e for e in hedge_measure.journal("cash_flow", cifras, saldos, {})}
    comun.comprobar("cap10-asiento-derivado", lineas[hedges.ACC_DERIVATIVE]["debit"], 5e-3)
    comun.comprobar("cap10-asiento-ori", lineas[hedges.ACC_OCI]["credit"], 5e-3)
    comun.comprobar("cap10-asiento-residuo", lineas[hedges.ACC_INEFFECTIVENESS]["credit"], 5e-3)


def razon_escenarios(conn):
    """Razón por escenario de la prueba prospectiva con swaps de 600 M y 650 M frente a un crédito de 500 M."""
    for nocional, nombre in ((600e6, "120"), (650e6, "130")):
        prueba = hedge_effectiveness.effectiveness(conn, cobertura(conn, nocional, "payer"), "MX-DEMO")
        razon = [r["ratio"] for r in prueba["scenarios"] if r["name"] == "TIIE-F +50 pb"][0]
        comun.comprobar("cap10-razon-" + nombre, razon, 5e-7)
        if nombre == "120":
            comun.comprobar("cap10-contados", prueba["scenarios_counted"], 0.5)
        comun.comprobar("cap10-en-rango-" + nombre, prueba["in_reference_range"], 0.5)


def valor_razonable(conn):
    """Deuda a tasa fija de 300 M cubierta con un swap receptor idéntico: primer cierre (D1)."""
    deuda = {"index": "TIIE-F", "notional": 300e6, "start_date": D0.isoformat(),
             "maturity_date": FIN_FIJO.isoformat(), "side": "pays_fixed"}
    p = cerrar(conn, cobertura(conn, 300e6, "receiver", "fair_value", "fixed_loan", deuda, FIN_FIJO), "D1")
    comun.comprobar("cap10-vr-ajuste", p["item_adjustment"], 1e-4)
    comun.comprobar("cap10-vr-resultado", p["fv_result"], 1e-4)


def cierre_final(conn):
    """Swap idéntico al crédito: cierre D1 y cierre final al vencimiento (D3)."""
    hid = cobertura(conn, 500e6, "payer")
    reciclado = cerrar(conn, hid, "D1")["recycled"]
    final = cerrar(conn, hid, "D3")
    comun.comprobar("cap10-final-reciclaje", reciclado + final["recycled"], 1e-4)
    comun.comprobar("cap10-final-reserva", final["oci"], 5e-5)


with tempfile.TemporaryDirectory() as carpeta:
    base = entorno(carpeta)
    regla_menor(base)
    reserva_acumulada(base)
    razon_escenarios(base)
    valor_razonable(base)
    cierre_final(base)
    base.close()
asiento_con_residuo()
comun.terminar()
