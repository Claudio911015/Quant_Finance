"""Cruces entre los cortes 3 (colateral USD, xccy_swap), 5 (operaciones), 6 (riesgo avanzado) y 7
(validación) que cada corte, construido por separado, no podía probar."""
import json
import sqlite3
from datetime import date

import pytest

from desk.api import market
from desk.api.db import connect
from desk.api.ops_recon import context_at
from desk.api.tests.csa_fixture import set_collateral, trade_with
from desk.api.tests.hedge_fixture import load_fixings, roll
from desk.api.tests.ops_fixture import ALFA

AS_OF = date(2026, 11, 10)
XCCY = {"side": "pay_usd", "notional_usd": 10_000_000.0, "periods": 26}
BOND = {"face": 1e8, "coupon_rate": 0.08, "periods": 6}


@pytest.fixture
def desk(client):
    """Alfa con colateral en USD desde el `as_of` de MX-DEMO, más un xccy_swap y un bono suyos."""
    assert set_collateral(client, ALFA, "USD", AS_OF).status_code == 200
    xccy = trade_with(client, "xccy_swap", ALFA, XCCY)["id"]
    bond = trade_with(client, "bond", ALFA, BOND)["id"]
    return {"xccy": xccy, "bond": bond}


def _spot(client, snapshot="MX-DEMO"):
    return client.get("/api/market/snapshots/%s" % snapshot).get_json()["fx"]["spot"]


def _get(client, url):
    r = client.get(url)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def _roll_with_fixings(client, days=35):
    """Rueda MX-DEMO a D1 y publica fijaciones TIIE-F y SOFR de todo el periodo: sin avisos de fijación."""
    end = roll(client, "MX-DEMO", "D1", days)
    load_fixings(client, "TIIE-F", AS_OF, date.fromisoformat(end), 0.0705)
    load_fixings(client, "SOFR", AS_OF, date.fromisoformat(end), 0.0405)
    return end


def _move_csa_quotes(app, snapshot="D1"):
    """Mueve por SQL los puntos forward y la base del snapshot (la API no los edita)."""
    db = sqlite3.connect(app.config["DESK_DB"])
    try:
        data = json.loads(db.execute("SELECT data FROM snapshots WHERE id = ?", (snapshot,)).fetchone()[0])
        for q in data["fx_forwards"]:
            q["points"] *= 1.25
        for q in data["xccy_basis"]:
            q["spread"] -= 0.0010
        db.execute("UPDATE snapshots SET data = ? WHERE id = ?", (json.dumps(data), snapshot))
        db.commit()
    finally:
        db.close()


# ------------------------------------------------------------------ contexto de mercado


def test_context_at_keeps_the_collateral_and_the_mxn_usd_quotes(app):
    conn = connect(app.config["DESK_DB"])
    try:
        mkt = market.load_context(conn, "MX-DEMO").with_collateral("USD")
    finally:
        conn.close()
    other = context_at(mkt, date(2026, 11, 11))
    assert other.as_of == date(2026, 11, 11) and mkt.as_of == AS_OF
    assert other.collateral == "USD" and other.mxn_discount == "MXN-USD"
    assert other.csa_quotes is mkt.csa_quotes and other.curve_names() == mkt.curve_names()
    # un choque posterior sigue recalibrando MXN-USD con las cotizaciones fijas
    assert other.shifted(spot_pct=1.0).curves["MXN-USD"] is not mkt.curves["MXN-USD"]


# ----------------------------------------------------- calendario de flujos (corte 5 × 3)


def test_calendar_projected_flows_add_up_to_the_pv_with_usd_collateral_and_a_xccy(client, desk):
    rows = _get(client, "/api/cashflows?snapshot=MX-DEMO")["rows"]
    valuation_rows = {r["id"]: r for r in _get(client, "/api/portfolio/valuation?snapshot=MX-DEMO")["rows"]}
    spot = _spot(client)
    for trade_id in (1, desk["bond"], desk["xccy"]):  # el irs 1 es de Alfa: descuenta con MXN-USD
        projected = [r for r in rows if r["trade_id"] == trade_id and r["status"] == "projected"]
        assert projected, trade_id
        in_mxn = sum(r["amount"] * r["df"] * (spot if r["currency"] == "USD" else 1.0) for r in projected)
        assert in_mxn == pytest.approx(valuation_rows[trade_id]["pv_mxn"], abs=1e-6 * 186e6)


def test_calendar_lists_the_xccy_coupons_and_notional_exchanges_each_in_its_currency(client, desk):
    body = _get(client, "/api/cashflows?snapshot=MX-DEMO")
    assert body["errors"] == []
    mine = [r for r in body["rows"] if r["trade_id"] == desk["xccy"]]
    assert {r["product"] for r in mine} == {"xccy_swap"} and {r["status"] for r in mine} == {"projected"}
    assert {(r["kind"], r["currency"]) for r in mine} == {
        ("coupon", "USD"), ("coupon", "MXN"), ("exchange", "USD"), ("exchange", "MXN")}
    spot = _spot(client)
    for r in mine:
        assert r["amount_mxn"] == pytest.approx(r["amount"] * (spot if r["currency"] == "USD" else 1.0))
    # el intercambio inicial (USD hacia dentro, MXN hacia fuera) y el final (al revés) se compensan en nocional
    exchanges = [r for r in mine if r["kind"] == "exchange"]
    assert len(exchanges) == 4 and sum(r["amount"] for r in exchanges if r["currency"] == "USD") == pytest.approx(0.0)
    assert [r["date"] for r in exchanges] == sorted(r["date"] for r in exchanges)
    assert exchanges[-1]["date"] == "2028-11-07"
    # los filtros del calendario también ven al xccy
    only_usd = _get(client, "/api/cashflows?snapshot=MX-DEMO&currency=USD")["rows"]
    assert desk["xccy"] in {r["trade_id"] for r in only_usd}


def test_calendar_settled_xccy_flows_after_rolling_and_the_csv_keeps_them(client, desk):
    _roll_with_fixings(client)
    body = _get(client, "/api/cashflows?snapshot=D1")
    mine = [r for r in body["rows"] if r["trade_id"] == desk["xccy"] and r["status"] != "projected"]
    assert {(r["date"], r["kind"], r["currency"]) for r in mine} == {
        ("2026-11-10", "exchange", "USD"), ("2026-11-10", "exchange", "MXN"),
        ("2026-12-08", "coupon", "USD"), ("2026-12-08", "coupon", "MXN")}
    csv_body = client.get("/api/cashflows?snapshot=D1&format=csv").data.decode("utf-8")
    assert csv_body.count("xccy_swap") == len([r for r in body["rows"] if r["trade_id"] == desk["xccy"]])


# ---------------------------------------------- confirmación de liquidaciones (corte 5 × 3)


def _settle(client, trade_id, day, amount, currency, snapshot="D1"):
    return client.post(
        "/api/trades/%d/settlements" % trade_id,
        json={"date": day, "amount": amount, "currency": currency, "snapshot": snapshot},
    )


def _coupon_rows(client, trade_id):
    rows = _get(client, "/api/cashflows?snapshot=D1")["rows"]
    return {r["currency"]: r for r in rows if r["trade_id"] == trade_id and r["kind"] == "coupon"
            and r["date"] == "2026-12-08"}


def test_each_xccy_coupon_leg_is_confirmed_on_its_own(client, desk):
    _roll_with_fixings(client)
    legs = _coupon_rows(client, desk["xccy"])
    assert legs["USD"]["status"] == legs["MXN"]["status"] == "settled"

    usd = _settle(client, desk["xccy"], "2026-12-08", -31000.0, "USD")
    assert usd.status_code == 201, usd.get_json()
    legs = _coupon_rows(client, desk["xccy"])
    assert legs["USD"]["status"] == "confirmed" and legs["USD"]["confirmed_amount"] == -31000.0
    assert legs["MXN"]["status"] == "settled" and legs["MXN"]["confirmed_amount"] is None  # la otra pata sigue sin confirmar

    mxn = _settle(client, desk["xccy"], "2026-12-08", 1_000_000.0, "MXN")
    assert mxn.status_code == 201, mxn.get_json()
    legs = _coupon_rows(client, desk["xccy"])
    assert legs["MXN"]["status"] == "confirmed" and legs["MXN"]["confirmed_amount"] == 1_000_000.0
    assert legs["MXN"]["difference"] == pytest.approx(1_000_000.0 - legs["MXN"]["amount"])
    assert legs["USD"]["confirmed_amount"] == -31000.0  # la primera no cambió

    again = _settle(client, desk["xccy"], "2026-12-08", 1.0, "USD")
    assert again.status_code == 409 and again.get_json()["error"] == "Ese flujo ya está confirmado"


def test_a_notional_exchange_is_not_confirmable_and_says_so(client, desk):
    _roll_with_fixings(client)
    r = _settle(client, desk["xccy"], "2026-11-10", 1.0, "USD")
    assert r.status_code == 409 and r.get_json()["field"] == "date"
    assert "solo cupones y liquidaciones" in r.get_json()["error"]
    assert _settle(client, desk["xccy"], "2026-12-09", 1.0, "USD").get_json()["error"].startswith(
        "No hay flujo derivado")


# ---------------------------------------------- documentos y FpML (corte 5 × 3)


def test_confirmation_and_fpml_refuse_the_xccy_in_spanish_and_without_a_500(client, desk):
    conf = client.get("/api/trades/%d/confirmation" % desk["xccy"])
    assert conf.status_code == 400
    assert conf.get_json() == {"error": "No hay plantilla de confirmación para Cross currency swap USDMXN",
                               "field": "product"}
    fpml = client.get("/api/trades/%d/fpml" % desk["xccy"])
    assert fpml.status_code == 400 and fpml.get_json()["field"] == "product"
    message = fpml.get_json()["error"]
    assert "Cross currency swap USDMXN no se exporta" in message
    assert "xccy_swap" not in message and "irs" not in message  # ni códigos internos
    # el bono, que tampoco exporta, recibe el mismo trato
    assert "Bono no se exporta" in client.get("/api/trades/%d/fpml" % desk["bond"]).get_json()["error"]


# ---------------------------------------------------------- conciliación (corte 5 × 3)


def _reconcile(client, trade_id, bank_pv):
    csv_text = "trade_id,bank_pv,currency,bank_ref\n%d,%r,MXN,\n" % (trade_id, bank_pv)
    r = client.post("/api/reconciliations",
                    json={"snapshot": "MX-DEMO", "counterparty": ALFA, "csv": csv_text})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["rows"][0]


def test_reconciling_a_xccy_works_and_flags_a_large_difference_for_review(client, desk):
    own = {r["id"]: r for r in _get(client, "/api/portfolio/valuation?snapshot=MX-DEMO")["rows"]}[
        desk["xccy"]]["pv_mxn"]
    same = _reconcile(client, desk["xccy"], own)
    assert same["error"] is None and same["status"] == "conciliada" and same["own_pv_mxn"] == pytest.approx(own)
    assert same["product"] == "xccy_swap" and same["notional_mxn"] == pytest.approx(10_000_000.0 * _spot(client))
    far = _reconcile(client, desk["xccy"], own + 5_000_000.0)
    assert far["error"] is None and far["status"] == "revisar" and far["terms_flag"] is True
    assert far["decomposition"]["curve"] is None and far["decomposition"]["fx"] is None  # solo hay fecha


# ----------------------------------------------- riesgo avanzado (corte 6 × 3): P&L explicado


def test_pnl_explain_closes_with_a_xccy_and_usd_collateral_when_the_forward_points_move(app, client, desk):
    _roll_with_fixings(client)
    _move_csa_quotes(app)
    official = _get(client, "/api/pnl?from=MX-DEMO&to=D1")
    body = _get(client, "/api/pnl/explain?from=MX-DEMO&to=D1")
    assert body["totals"]["pnl"] == official["total_mxn"]
    assert sum(body["totals"]["components"].values()) == pytest.approx(official["total_mxn"], abs=1e-6)
    rows = {r["id"]: r for r in body["rows"]}
    assert desk["xccy"] in rows and rows[desk["xccy"]]["error"] is None
    for ref in official["rows"]:
        row = rows[ref["id"]]
        assert row["explain_error"] is None
        assert sum(row["components"].values()) == pytest.approx(ref["pnl"], abs=1e-6)
        # nada de lo que se movió en el mercado cae en «Eventos» (ninguna operación tiene eventos)
        assert row["components"]["events"] == pytest.approx(0.0, abs=1e-6), ref["id"]
        assert abs(row["components"]["residual"]) < 1e-6
    # el efecto de los puntos forward y la base está en su rubro, no perdido ni escondido
    csa = body["totals"]["components"]["curve:MXN-USD"]
    assert csa != 0.0 and [s["label"] for s in body["steps"] if s["key"] == "curve:MXN-USD"] == [
        "Puntos forward y base (MXN-USD)"]
    assert rows[desk["xccy"]]["components"]["curve:MXN-USD"] != 0.0
    assert rows[desk["bond"]]["components"]["curve:MXN-USD"] != 0.0  # el bono TIIE-F de Alfa descuenta con MXN-USD
    # una contraparte sin colateral USD no siente esos puntos
    assert rows[5]["counterparty"] != ALFA and rows[5]["components"]["curve:MXN-USD"] == 0.0


def test_pnl_explain_moves_nothing_to_the_new_rubric_when_the_points_do_not_move(client, desk):
    _roll_with_fixings(client)
    body = _get(client, "/api/pnl/explain?from=MX-DEMO&to=D1")
    assert body["totals"]["components"]["curve:MXN-USD"] == 0.0
    assert body["totals"]["components"]["events"] == 0.0


# ----------------------------------------------- riesgo avanzado (corte 6 × 3): VaR, límites, CVA


def test_historical_var_and_limits_work_on_a_book_with_a_xccy_and_usd_collateral(client, desk):
    body = {"snapshot": "MX-DEMO", "horizon_days": 1, "confidence": 0.99}
    parametric = client.post("/api/risk/var", json=body)
    historical = client.post("/api/risk/var", json={**body, "method": "historical"})
    assert parametric.status_code == historical.status_code == 200
    assert historical.get_json()["errors"] == [] and historical.get_json()["var_mxn"] > 0
    assert [f["factor"] for f in historical.get_json()["factors"]] == ["TIIE-F", "SOFR", "USDMXN"]
    for payload in (
        {"scope": "portfolio", "key": "portfolio", "metric": "var", "amount": 1e6},
        {"scope": "counterparty", "key": ALFA, "metric": "pv_exposure", "amount": 1e6},
        {"scope": "factor", "key": "USDMXN", "metric": "fx_delta", "amount": 1e6},
        {"scope": "factor", "key": "SOFR", "metric": "dv01", "amount": 1e3},
    ):
        assert client.post("/api/limits", json=payload).status_code == 201, payload
    usage = _get(client, "/api/limits/usage?snapshot=MX-DEMO")
    assert usage["errors"] == [] and len(usage["usage"]) == 4
    assert all(u["usage"] == u["usage"] and u["status"] in ("ok", "alerta", "exceso") for u in usage["usage"])
    checked = client.post("/api/limits/check?snapshot=MX-DEMO")
    assert checked.status_code == 200 and checked.get_json()["errors"] == []
    # la curva dependiente no es un factor limitable: la API lo dice con claridad
    refused = client.post("/api/limits", json={"scope": "factor", "key": "MXN-USD", "metric": "dv01", "amount": 1})
    assert refused.status_code == 400 and refused.get_json()["field"] == "key"


def test_cva_excludes_the_xccy_naming_the_product_not_its_code(client, desk):
    body = _get(client, "/api/credit/exposure?snapshot=MX-DEMO")
    alfa = [c for c in body["counterparties"] if c["counterparty"] == ALFA][0]
    excluded = {e["id"]: e for e in alfa["excluded"]}
    assert excluded[desk["xccy"]]["product"] == "xccy_swap"
    assert excluded[desk["xccy"]]["reason"] == (
        "La exposición simulada solo cubre swaps de tasas (IRS): Cross currency swap USDMXN se excluye")
    assert excluded[desk["bond"]]["reason"].endswith("Bono se excluye")
    assert desk["xccy"] not in [t for ns in alfa["netting_sets"] for t in ns["trades"]]


# --------------------------------------------------------------- validación (corte 7 × 3)


def test_validation_report_is_served_with_a_xccy_in_the_book(client, desk):
    body = _get(client, "/api/validation/report")
    assert body["totals"]["failed"] == 0 and body["cases"]
    # el reporte lo genera el commit que lo versiona: si la valuación cambió después, solo se avisa
    assert body["commit_matches"] in (True, False, None) and "current_commit" in body
