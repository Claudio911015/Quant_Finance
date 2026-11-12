"""Ejemplos verificables del capítulo 9 (riesgo): DV01, escenarios, VaR, VaR histórico, límites y P&L explicado.

Cada ejemplo llama a las funciones del backend (`desk.api.risk.*`) sobre una base temporal sembrada con
MX-DEMO; nunca se lee la base real del desk.
"""
import json
import os
import tempfile
from datetime import date, timedelta

import comun  # primero: arregla sys.path
from desk.api import db, market, portfolio, seed_market
from desk.api import fixings as fixing_store
from desk.api.qf import qfpy
from desk.api.risk import dv01, explain, factor_history, hist_var, limits, scenarios, var

IRS = {"curve": "TIIE-F", "side": "payer", "notional": 100e6, "periods": 26, "fixed_rate": 0.068}
FWD = {"side": "buy", "notional_usd": 10e6, "days": 182, "strike": 19.05}
SNAP = "MX-DEMO"


def base(directorio, *trades):
    """Base temporal con MX-DEMO y las operaciones dadas (producto, parámetros), contraparte «Banco Test»."""
    conn = db.connect(os.path.join(directorio, "t.db"))
    db.init_schema(conn)
    seed_market.seed_market(conn)
    for producto, params in trades:
        portfolio.create_trade(conn, {"product": producto, "counterparty": "Banco Test", "params": params})
    conn.commit()
    return conn


def historia_csv(n=60):
    """CSV de n días hábiles que terminan en el as_of de MX-DEMO: TIIE-F = 0.1 (t − 30.5) pb, lo demás 0."""
    dias, dia = [], date.fromisoformat(seed_market.AS_OF)
    while len(dias) < n:
        if dia.weekday() < 5:
            dias.append(dia)
        dia -= timedelta(days=1)
    dias.reverse()
    filas = ["factor,date,value"]
    for t, d in enumerate(dias, start=1):
        filas += ["TIIE-F,%s,%r" % (d.isoformat(), round(0.1 * (t - 30.5), 10)),
                  "SOFR,%s,0" % d.isoformat(), "USDMXN,%s,0" % d.isoformat()]
    return "\n".join(filas) + "\n"


with tempfile.TemporaryDirectory() as tmp:
    # --- DV01 y escenarios de un IRS payer TIIE-F de 100 millones a 26 periodos de 28 días ---
    conn = base(tmp, ("irs", IRS))
    r = dv01.compute_dv01(conn, SNAP)["curves"]["TIIE-F"]
    pilar = {p["label"]: p["dv01_mxn"] for p in r["points"]}
    mkt, op, fijaciones = market.load_context(conn, SNAP), portfolio.load_trades(conn)[0], fixing_store.load_all(conn)

    def valor(contexto):
        return portfolio.trade_pv_mxn(op, contexto, fijaciones)

    v0 = valor(mkt)
    vmas = valor(mkt.shifted(curve="TIIE-F", parallel_bp=1.0))
    vmenos = valor(mkt.shifted(curve="TIIE-F", parallel_bp=-1.0))
    comun.comprobar("cap09-dv01-pv-base", v0, 0.01)
    comun.comprobar("cap09-dv01-pv-mas1", vmas, 0.01)
    comun.comprobar("cap09-dv01-pv-menos1", vmenos, 0.01)
    central, convexidad = (vmenos - vmas) / 2.0, (vmenos + vmas - 2.0 * v0) / 2.0
    # la aritmética es del script, pero se amarra al código: suma de pilares y DV01 paralelo vienen de `dv01.compute_dv01`
    assert abs(central - sum(pilar.values())) < 0.01, (central, sum(pilar.values()))
    assert abs(convexidad - (sum(pilar.values()) - r["parallel_mxn"])) < 1e-4, (convexidad, sum(pilar.values()) - r["parallel_mxn"])
    comun.comprobar("cap09-dv01-central-paralelo", central, 0.01)
    comun.comprobar("cap09-dv01-convexidad", convexidad, 1e-4)
    comun.comprobar("cap09-dv01-paralelo", r["parallel_mxn"], 0.01)
    comun.comprobar("cap09-dv01-pilar-26x28", pilar["26x28"], 0.01)
    comun.comprobar("cap09-dv01-suma-pilares", sum(pilar.values()), 0.01)
    comun.comprobar("cap09-dv01-diferencia", sum(pilar.values()) - r["parallel_mxn"], 1e-4)

    esc = scenarios.run_scenarios(conn, SNAP, {"scenarios": [
        {"name": "+50", "type": "parallel", "curve": "TIIE-F", "bp": 50.0},
        {"name": "-50", "type": "parallel", "curve": "TIIE-F", "bp": -50.0},
        {"name": "steepener", "type": "steepener", "curve": "TIIE-F", "bp": 25.0},
    ]})["scenarios"]
    comun.comprobar("cap09-escenario-mas50", esc[0]["total_mxn"], 0.01)
    comun.comprobar("cap09-escenario-menos50", esc[1]["total_mxn"], 0.01)
    comun.comprobar("cap09-escenario-steepener", esc[2]["total_mxn"], 0.01)
    # primer orden del steepener de 25 pb: −Σ DV01_k δ_k con la rampa δ_j = −25 + 50 j / 9 (10 pilares)
    lineal = -sum(p["dv01_mxn"] * (-25.0 + 50.0 * j / 9.0) for j, p in enumerate(r["points"]))
    assert abs(lineal - esc[2]["total_mxn"]) < 50.0, (lineal, esc[2]["total_mxn"])  # segundo orden: unos 14 MXN frente al escenario del código
    comun.comprobar("cap09-escenario-steepener-lineal", lineal, 0.01)

    # --- VaR paramétrico: del IRS (ruta completa) y de un vector de exposiciones (qfpy) ---
    v = var.compute_var(conn, SNAP, {"horizon_days": 1, "confidence": 0.99})
    comun.comprobar("cap09-var-exposicion-tiie", v["factors"][0]["exposure_mxn"], 0.01)
    comun.comprobar("cap09-var-irs", v["var_mxn"], 0.01)
    corr = [[1.0, 0.35, 0.30], [0.35, 1.0, -0.10], [0.30, -0.10, 1.0]]
    comun.comprobar("cap09-z-99", qfpy.delta_normal_var([1.0], [1.0], [[1.0]], 0.99, 1.0), 1e-9)
    e3, s3 = [300000.0, -120000.0, 2000000.0], [4.0, 5.0, 0.0075]
    comun.comprobar("cap09-var-vector", qfpy.delta_normal_var(e3, s3, corr, 0.99, 10.0), 0.01)
    solos = [qfpy.delta_normal_var([e], [s], [[1.0]], 0.99, 10.0) for e, s in zip(e3, s3)]
    comun.comprobar("cap09-var-suma-factores", sum(solos), 0.01)

    # --- VaR histórico y ES sobre una historia explícita de 60 días ---
    factor_history.import_csv(conn, historia_csv())
    conn.commit()
    h = hist_var.compute_hist_var(conn, SNAP, {"horizon_days": 1, "confidence": 0.95, "window_days": 60,
                                               "history_source": "observed"})
    comun.comprobar("cap09-var-historico", h["var_mxn"], 0.01)
    comun.comprobar("cap09-es-historico", h["es_mxn"], 0.01)
    comun.comprobar("cap09-peor-dia", h["worst_day"]["pnl_mxn"], 0.01)

    # --- límite de DV01 de TIIE-F: uso, porcentaje y estado ---
    limits.create_limit(conn, {"scope": "factor", "key": "TIIE-F", "metric": "dv01", "amount": 20000})
    conn.commit()
    uso = limits.usage(conn, SNAP)["usage"][0]
    comun.comprobar("cap09-limite-uso", uso["usage"], 0.01)
    comun.comprobar("cap09-limite-pct", uso["pct"], 1e-6)
    conn.close()

with tempfile.TemporaryDirectory() as tmp:
    # --- P&L explicado: IRS + forward FX entre MX-DEMO y D1 (TIIE-F +25 pb, SOFR −25 pb, spot +3 %) ---
    conn = base(tmp, ("irs", IRS), ("fx_forward", FWD))
    datos = json.loads(conn.execute("SELECT data FROM snapshots WHERE id = ?", (SNAP,)).fetchone()["data"])
    for q in datos["quotes"]:
        q["rate"] = round(q["rate"] + (0.0025 if q["curve"] == "TIIE-F" else -0.0025), 6)
    datos["fx"]["spot"] = round(datos["fx"]["spot"] * 1.03, 6)
    conn.execute("INSERT INTO snapshots (id, label, synthetic, as_of, data) VALUES ('D1', 'D1', 1, ?, ?)",
                 (seed_market.AS_OF, json.dumps(datos)))
    conn.commit()
    filas = {f["id"]: f for f in explain.explain_pnl(conn, SNAP, "D1")["rows"]}
    comun.comprobar("cap09-explain-irs-tiie", filas[1]["components"]["curve:TIIE-F"], 0.01)
    comun.comprobar("cap09-explain-fwd-tiie", filas[2]["components"]["curve:TIIE-F"], 0.01)
    comun.comprobar("cap09-explain-fwd-sofr", filas[2]["components"]["curve:SOFR"], 0.01)
    comun.comprobar("cap09-explain-fwd-fx", filas[2]["components"]["fx"], 0.01)
    comun.comprobar("cap09-explain-fwd-pnl", filas[2]["pnl"], 0.01)
    comun.comprobar("cap09-explain-residuo", filas[2]["components"]["residual"], 1e-6)
    conn.close()

comun.terminar()
