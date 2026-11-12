"""Ejemplos verificables del capítulo 8 (ciclo de vida, liquidaciones y P&L).

Base temporal con el snapshot MX-DEMO (as_of 2026-11-10) y dos snapshots rodados; nunca la base real.
"""
import os
import tempfile
from datetime import date, timedelta

import comun
from desk.api import db, events, market, pnl, portfolio, seed_market, settlement, valuation
from desk.api import fixings as fixing_store

CONTRAPARTE = "Banco Ejemplo"
INICIO, FIN = date(2026, 11, 10), date(2026, 12, 11)  # as_of de MX-DEMO y del snapshot D1


def fijacion(conn, indice, dia, valor):
    fixing_store.add_fixing(conn, {"index": indice, "date": dia.isoformat(), "value": valor})


def alta(conn, producto, vencimiento, params):
    return portfolio.create_trade(conn, {
        "product": producto, "counterparty": CONTRAPARTE, "trade_date": INICIO.isoformat(),
        "start_date": INICIO.isoformat(), "maturity_date": vencimiento.isoformat(), "params": params,
    })["id"]


def construir(carpeta):
    conn = db.connect(os.path.join(carpeta, "ejemplo.db"))
    db.init_schema(conn)
    seed_market.seed_market(conn)
    market.roll_snapshot(conn, "MX-DEMO", {"id": "D1", "as_of": FIN.isoformat()})
    irs = {"curve": "TIIE-F", "side": "payer", "notional": 100e6, "periods": 2, "fixed_rate": 0.068}
    ids = {
        "irs": alta(conn, "irs", INICIO + timedelta(days=56), irs),
        "irs_terminado": alta(conn, "irs", INICIO + timedelta(days=56), irs),
        "fwd": alta(conn, "fx_forward", date(2026, 12, 10),
                    {"side": "buy", "notional_usd": 10e6, "days": 30, "strike": 18.70}),
    }
    events.post_event(conn, ids["irs_terminado"], {
        "type": "termination", "event_date": "2026-12-01", "data": {"amount": 5000.0}})
    for dia in (INICIO + timedelta(days=i) for i in range(28)):  # primer periodo: 7 % en cada día hábil de México
        if dia.weekday() < 5 and dia != date(2026, 11, 16):  # 2026-11-16: Día de la Revolución
            fijacion(conn, "TIIE-F", dia, 0.07)
    fijacion(conn, "USDMXN", date(2026, 12, 10), 18.95)
    conn.commit()
    return conn, ids


def main():
    with tempfile.TemporaryDirectory(prefix="qfdocs-cap08-") as carpeta:
        conn, ids = construir(carpeta)
        mkt = market.load_context(conn, "D1")
        todas = fixing_store.load_all(conn)

        # Ejemplo 1: factor acumulado con la regla de fin de semana y feriado (lunes 9 a martes 17, exclusivo:
        # el viernes 13 devenga sábado, domingo y el lunes feriado 16). Fijaciones propias, distintas de las de la base.
        semana = {date(2026, 11, d): r for d, r in {9: 0.0700, 10: 0.0702, 11: 0.0704, 12: 0.0706, 13: 0.0708}.items()}
        publicadas = {"TIIE-F": semana}
        avisos = []
        factor = valuation.accrued_factor("TIIE-F", date(2026, 11, 9), date(2026, 11, 17), publicadas, mkt, avisos)
        a_mano = 1.0
        for dia, r in semana.items():
            a_mano *= 1.0 + r * (4 if dia.day == 13 else 1) / 360.0
        assert avisos == [] and abs(factor - a_mano) < 1e-13
        comun.comprobar("cap08-factor-semana", factor, 1e-10)

        # Ejemplo 2: cupón liquidado del swap payer (día 28, 2026-12-08).
        trade = next(t for t in portfolio.load_trades(conn) if t["id"] == ids["irs"])
        flujos, avisos = settlement.settled_flows(trade, todas, INICIO, FIN, mkt.spot, mkt)
        assert avisos == [] and [f["date"] for f in flujos] == ["2026-12-08"]
        factor1 = (1 + 0.07 / 360) ** 15 * (1 + 3 * 0.07 / 360) ** 3 * (1 + 4 * 0.07 / 360)  # 15 días de 1, 3 de 3, 1 de 4
        a_mano = 100e6 * (factor1 - 1) - 100e6 * 0.068 * 28 / 360
        assert abs(flujos[0]["amount_mxn"] - a_mano) < 1e-6
        comun.comprobar("cap08-cupon-irs", flujos[0]["amount_mxn"], 0.005)

        # Ejemplos 3-4: P&L entre MX-DEMO y D1.
        r = pnl.compute_pnl(conn, "MX-DEMO", "D1")
        filas = {f["id"]: f for f in r["rows"]}
        for f in filas.values():
            assert f["error"] is None and abs(f["pnl"] - (f["pv_to"] - f["pv_from"] + f["settled"])) < 1e-6
        irs, term, fwd = filas[ids["irs"]], filas[ids["irs_terminado"]], filas[ids["fwd"]]
        assert (irs["status_from"], irs["status_to"]) == ("viva", "viva")
        comun.comprobar("cap08-pv-irs-inicial", irs["pv_from"], 0.005)
        comun.comprobar("cap08-pv-irs-final", irs["pv_to"], 0.005)
        comun.comprobar("cap08-pnl-irs", irs["pnl"], 0.005)
        assert term["status_to"] == "terminada" and term["pv_to"] == 0.0 and term["settled"] == 5000.0
        comun.comprobar("cap08-pnl-terminacion", term["pnl"], 0.005)

        # Ejemplos 5-7: forward FX vencido dentro de la ventana, liquidado con el FIX del vencimiento.
        assert fwd["status_to"] == "vencida" and fwd["pv_to"] == 0.0
        comun.comprobar("cap08-pv-fwd", fwd["pv_from"], 0.005)
        comun.comprobar("cap08-liquidado-fwd", fwd["settled"], 0.005)
        comun.comprobar("cap08-pnl-fwd", fwd["pnl"], 0.005)
        conn.close()
    comun.terminar()


if __name__ == "__main__":
    main()
