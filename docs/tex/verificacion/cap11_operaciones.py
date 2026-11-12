"""Ejemplos verificables del capítulo 11 (operaciones: conciliación, flujos y confirmación de liquidaciones).

Bases temporales con el snapshot MX-DEMO (as_of 2026-11-10); nunca la base real.
"""
import os
import tempfile
from datetime import date, timedelta

import comun
from desk.api import db, market, ops_cashflows, ops_recon, ops_settlements, portfolio, seed_market, valuation
from desk.api import fixings as fixing_store

CONTRAPARTE = "Banco Ejemplo"
INICIO = date(2026, 11, 10)


def base(carpeta):
    conn = db.connect(os.path.join(carpeta, "ejemplo.db"))
    db.init_schema(conn)
    seed_market.seed_market(conn)
    return conn


def alta(conn, producto, vencimiento, params):
    return portfolio.create_trade(conn, {
        "product": producto, "counterparty": CONTRAPARTE, "trade_date": INICIO.isoformat(),
        "start_date": INICIO.isoformat(), "maturity_date": vencimiento.isoformat(), "params": params,
    })["id"]


def conciliacion(carpeta):
    conn = base(carpeta)
    swap = alta(conn, "irs", INICIO + timedelta(days=26 * 28),
                {"curve": "TIIE-F", "side": "payer", "notional": 500e6, "periods": 26, "fixed_rate": 0.068})
    forward = alta(conn, "fx_forward", date(2027, 5, 11),
                   {"side": "buy", "notional_usd": 10e6, "days": 182, "strike": 19.05})
    conn.commit()
    mkt = market.load_context(conn, "MX-DEMO")
    operaciones = {t["id"]: t for t in portfolio.load_trades(conn)}
    fijaciones = fixing_store.load_all(conn)
    tol = ops_recon.DEFAULT_TOLERANCE

    # Ejemplo 1: el banco valúa el swap con la curva TIIE-F 5 pb más arriba.
    propio = valuation.value_trade(operaciones[swap], mkt, fijaciones)["pv_mxn"]
    banco = valuation.value_trade(operaciones[swap], mkt.shifted(curve="TIIE-F", parallel_bp=5.0), fijaciones)["pv_mxn"]
    fila = ops_recon.reconcile_trade(operaciones[swap], banco, mkt, fijaciones, tol)
    assert fila["status"] == "explicable" and not fila["terms_flag"] and fila["own_pv_mxn"] == propio
    comun.comprobar("cap11-pv-propio", propio, 0.005)
    comun.comprobar("cap11-pv-banco", banco, 0.005)
    comun.comprobar("cap11-dif-curva", fila["difference_mxn"], 0.005)
    comun.comprobar("cap11-tolerancia-abs", tol * fila["notional_mxn"], 0.005)
    comun.comprobar("cap11-bp-implicito", fila["decomposition"]["curve"]["bp"], 1e-4)

    # Ejemplo 2: el banco valúa el mismo swap un día hábil después; el día anterior (2026-11-09) es anterior al
    # pacto, la operación no está viva y no ensancha el rango.
    siguiente = ops_recon.business_day(INICIO, 1)
    pv_siguiente = valuation.value_trade(operaciones[swap], ops_recon.context_at(mkt, siguiente), fijaciones)["pv_mxn"]
    fecha = ops_recon.reconcile_trade(operaciones[swap], pv_siguiente, mkt, fijaciones, 0.0)
    assert fecha["decomposition"]["date"]["attributed"] and fecha["status"] == "explicable"
    assert fecha["decomposition"]["date"]["pv_prev"] == 0.0
    comun.comprobar("cap11-pv-dia-siguiente", pv_siguiente, 0.005)
    comun.comprobar("cap11-dif-fecha", fecha["difference_mxn"], 0.005)

    # Ejemplo 3: el banco valúa el forward con el spot 0.5 % más arriba.
    mas_spot = valuation.value_trade(operaciones[forward], mkt.shifted(spot_pct=0.5), fijaciones)["pv_mxn"]
    fx = ops_recon.reconcile_trade(operaciones[forward], mas_spot, mkt, fijaciones, tol)
    assert fx["status"] == "explicable"
    comun.comprobar("cap11-spot-implicito", fx["decomposition"]["fx"]["spot"], 1e-4)

    # Ejemplo 4: los flujos proyectados del swap, descontados, suman su PV (calendario de flujos).
    r = ops_cashflows.cashflows(conn, {"snapshot": "MX-DEMO"})
    proyectados = [f for f in r["rows"] if f["trade_id"] == swap and f["status"] == "projected"]
    assert len(proyectados) == 26 and r["errors"] == []
    comun.comprobar("cap11-suma-flujos-pv", sum(f["pv"] for f in proyectados), 0.005)
    conn.close()


def confirmacion(carpeta):
    conn = base(carpeta)
    swap = alta(conn, "irs", INICIO + timedelta(days=56),
                {"curve": "TIIE-F", "side": "payer", "notional": 100e6, "periods": 2, "fixed_rate": 0.068})
    market.roll_snapshot(conn, "MX-DEMO", {"id": "D1", "as_of": "2026-12-11"})
    for i in range(28):  # primer periodo: 7 % en cada día hábil de México
        dia = INICIO + timedelta(days=i)
        if dia.weekday() < 5 and dia != date(2026, 11, 16):
            fixing_store.add_fixing(conn, {"index": "TIIE-F", "date": dia.isoformat(), "value": 0.07})
    conn.commit()
    # El banco liquidó 17 000.00 MXN en el cupón del 2026-12-08; el derivado vale 16 930.14.
    res = ops_settlements.confirm_settlement(
        conn, swap, {"date": "2026-12-08", "amount": 17000.0, "currency": "MXN", "snapshot": "D1"})
    assert abs(res["flow"]["amount"] - 16930.14353951835) < 1e-6
    fila = next(f for f in ops_cashflows.cashflows(conn, {"snapshot": "D1"})["rows"] if f["status"] == "confirmed")
    assert fila["difference"] == res["difference"]
    comun.comprobar("cap11-dif-confirmada", fila["difference"], 5e-5)
    conn.close()


def main():
    with tempfile.TemporaryDirectory(prefix="qfdocs-cap11-") as carpeta:
        conciliacion(carpeta)
    with tempfile.TemporaryDirectory(prefix="qfdocs-cap11b-") as carpeta:
        confirmacion(carpeta)
    comun.terminar()


if __name__ == "__main__":
    main()
