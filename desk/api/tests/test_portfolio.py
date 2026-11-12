import json

import pytest

from desk.api import portfolio
from desk.api.app import create_app
from desk.api.db import connect
from desk.api.tests.conftest import empty_portfolio, insert_raw_trade

IRS = {"curve": "TIIE-F", "side": "payer", "notional": 1e6, "periods": 13, "fixed_rate": 0.07}
FWD = {"side": "buy", "notional_usd": 1e6, "days": 91, "strike": 19.0}


def _trade(product="irs", params=None, counterparty="Banco Test"):
    return {"product": product, "counterparty": counterparty, "params": params or dict(IRS)}


def _insert_raw(app, product, params_text):
    insert_raw_trade(app, product, params_text)


def test_seed_creates_seven_trades_and_values_without_errors(client):
    trades = client.get("/api/trades").get_json()["trades"]
    # corte 9: tras las 7 originales se siembran 9 operaciones más (swaps y cross currency swaps)
    assert [t["id"] for t in trades] == list(range(1, 17))
    assert [t["product"] for t in trades[:7]] == [
        "irs", "irs", "irs", "fx_forward", "fx_forward", "fx_option", "cap_floor"
    ]
    assert all(t["counterparty"].endswith("(sintético)") for t in trades)

    v = client.get("/api/portfolio/valuation?snapshot=MX-DEMO").get_json()
    assert v["snapshot"] == "MX-DEMO" and v["as_of"] == "2026-11-10"
    assert len(v["rows"]) == 16
    assert all(r["error"] is None for r in v["rows"])
    assert all(r["pv_mxn"] is not None for r in v["rows"])
    assert v["total_mxn"] == pytest.approx(sum(r["pv_mxn"] for r in v["rows"]))
    # las tasas fijas de la semilla no son par: el PV de los swaps no es trivial
    assert all(abs(r["pv_mxn"]) > 1e3 for r in v["rows"][:3])
    assert set(v["rows"][0]) == {
        "id", "product", "counterparty", "trade_date", "start_date", "maturity_date", "status",
        "notional", "currency", "maturity", "pv", "pv_mxn", "warnings", "error", "collateral_currency",
    }
    # las 7 originales nacen en el as_of; las 9 del corte 9 traen su propia trade_date
    original = v["rows"][:7]
    assert all(r["status"] == "viva" and r["warnings"] == [] for r in original)
    assert all(r["trade_date"] == r["start_date"] == "2026-11-10" for r in original)
    assert all(r["maturity"] == r["maturity_date"] > "2026-11-10" for r in v["rows"])


def test_valuation_pv_is_in_row_currency(client):
    rows = client.get("/api/portfolio/valuation?snapshot=MX-DEMO").get_json()["rows"]
    sofr = rows[2]
    assert sofr["currency"] == "USD"
    assert sofr["pv_mxn"] == pytest.approx(sofr["pv"] * 18.60, rel=1e-12)
    assert rows[0]["currency"] == "MXN" and rows[0]["pv"] == rows[0]["pv_mxn"]


def test_valuation_matches_price_endpoint(client):
    rows = client.get("/api/portfolio/valuation?snapshot=MX-DEMO").get_json()["rows"]
    body = {"snapshot": "MX-DEMO", "curve": "TIIE-F", "side": "payer", "notional": 500e6,
            "periods": 26, "fixed_rate": 0.0680}
    price = client.post("/api/price/irs", json=body).get_json()
    assert rows[0]["pv_mxn"] == pytest.approx(price["pv_mxn"], rel=1e-12)


def test_create_list_and_delete_is_refused(client):
    r = client.post("/api/trades", json=_trade())
    assert r.status_code == 201
    t = r.get_json()
    assert t["id"] == 17  # 7 originales + 9 del corte 9 + la nueva
    assert t["notional"] == 1e6 and t["currency"] == "MXN" and t["maturity"] == "2027-11-09"
    assert t["params"]["fixed_rate"] == 0.07 and t["created_at"]
    assert set(t) == {"id", "product", "counterparty", "trade_date", "start_date",
                      "maturity_date", "params", "notional", "currency", "maturity", "created_at"}
    assert t["trade_date"] == t["start_date"] == "2026-11-10" and t["maturity_date"] == t["maturity"]
    assert client.get("/api/trades").get_json()["trades"][-1] == t

    r = client.delete("/api/trades/8")  # una operación no se borra: se termina
    assert r.status_code == 409 and r.get_json()["field"] == "id"
    assert len(client.get("/api/trades").get_json()["trades"]) == 17


def test_create_trims_counterparty_and_stores_normalized_params(client):
    r = client.post("/api/trades", json=_trade("fx_forward", {**FWD, "extra": 1}, "  Banco X  "))
    t = r.get_json()
    assert t["counterparty"] == "Banco X"
    assert set(t["params"]) == {"side", "notional_usd", "strike", "days"}
    assert t["currency"] == "USD" and t["maturity"] == "2027-02-09"


def test_persistence_across_create_app(tmp_path):
    db = tmp_path / "p.db"
    app1 = create_app(db_path=db)
    assert app1.test_client().post("/api/trades", json=_trade()).status_code == 201
    app2 = create_app(db_path=db)
    trades = app2.test_client().get("/api/trades").get_json()["trades"]
    assert len(trades) == 17  # 16 sembradas (7 + 9 del corte 9), sin resembrar, + la nueva
    assert trades[-1]["counterparty"] == "Banco Test"


def test_emptied_portfolio_is_not_reseeded(tmp_path):
    db = tmp_path / "e.db"
    app1 = create_app(db_path=db)
    empty_portfolio(app1.test_client())
    app2 = create_app(db_path=db)
    assert app2.test_client().get("/api/trades").get_json()["trades"] == []


def test_corrupt_rows_report_error_and_rest_is_valued(app, client):
    _insert_raw(app, "irs", json.dumps({"curve": "TIIE-F"}))  # faltan campos
    _insert_raw(app, "irs", "{no es json")  # JSON ilegible
    _insert_raw(app, "bono_raro", "{}")  # producto desconocido

    assert len(client.get("/api/trades").get_json()["trades"]) == 19  # el listado no se rompe
    v = client.get("/api/portfolio/valuation?snapshot=MX-DEMO").get_json()
    good, bad = v["rows"][:16], v["rows"][16:]  # 16 sembradas (7 + 9 del corte 9), luego las 3 corruptas
    assert all(r["error"] is None for r in good)
    assert len(bad) == 3
    for r in bad:
        assert r["error"] and r["pv"] is None and r["pv_mxn"] is None
        assert r["notional"] is None
    assert "Falta el parámetro" in bad[0]["error"]  # mensaje de validate, no un KeyError
    assert v["total_mxn"] == pytest.approx(sum(r["pv_mxn"] for r in good))


def test_trade_pv_mxn_and_load_trades(app):
    conn = connect(app.config["DESK_DB"])
    try:
        from desk.api import market

        mkt = market.load_context(conn, "MX-DEMO")
        trades = portfolio.load_trades(conn)
        assert len(trades) == 16 and isinstance(trades[0]["params"], dict)  # 7 + 9 del corte 9
        base = [portfolio.trade_pv_mxn(t, mkt) for t in trades]
        up = [portfolio.trade_pv_mxn(t, mkt.shifted(spot_pct=10.0)) for t in trades]
        assert up[0] == pytest.approx(base[0])  # irs TIIE-F no depende del spot
        assert up[3] != pytest.approx(base[3])  # fx_forward sí
        with pytest.raises(ValueError):
            portfolio.trade_pv_mxn({"product": "x", "params": {}}, mkt)
    finally:
        conn.close()


def test_delete_missing_is_404(client):
    r = client.delete("/api/trades/999")
    assert r.status_code == 404 and r.get_json()["field"] == "id"
    r = client.delete("/api/trades/abc")
    assert r.status_code == 404 and r.get_json()["field"] == "id"


def test_valuation_unknown_snapshot_is_404(client):
    r = client.get("/api/portfolio/valuation?snapshot=NOPE")
    assert r.status_code == 404 and r.get_json()["field"] == "snapshot"
    r = client.get("/api/portfolio/valuation")
    assert r.status_code == 400 and r.get_json()["field"] == "snapshot"


@pytest.mark.parametrize(
    "body, field",
    [
        ({**_trade(), "product": "bono_raro"}, "product"),
        ({k: v for k, v in _trade().items() if k != "product"}, "product"),
        ({**_trade(), "counterparty": "  "}, "counterparty"),
        ({k: v for k, v in _trade().items() if k != "counterparty"}, "counterparty"),
        ({**_trade(), "params": [1]}, "params"),
        ({k: v for k, v in _trade().items() if k != "params"}, "params"),
        (_trade(params={**IRS, "notional": -5}), "notional"),
        (_trade(params={k: v for k, v in IRS.items() if k != "periods"}), "periods"),
        (_trade("fx_forward", {**FWD, "side": "x"}), "side"),
    ],
)
def test_create_invalid_is_400_with_field(client, body, field):
    r = client.post("/api/trades", json=body)
    assert r.status_code == 400
    assert r.get_json()["field"] == field
    assert len(client.get("/api/trades").get_json()["trades"]) == 16  # 7 + 9 del corte 9


@pytest.mark.parametrize("omit", [True, False], ids=["sin fixed_rate", "fixed_rate null"])
@pytest.mark.parametrize("curve, periods", [("TIIE-F", 13), ("SOFR", 3)])
def test_irs_without_fixed_rate_is_booked_at_par(client, omit, curve, periods):
    params = {**IRS, "curve": curve, "periods": periods, "notional": 5e8}
    params = {k: v for k, v in params.items() if k != "fixed_rate"} if omit else {**params, "fixed_rate": None}
    r = client.post("/api/trades", json=_trade(params=params))
    assert r.status_code == 201, r.get_json()
    trade = r.get_json()
    assert isinstance(trade["params"]["fixed_rate"], float)
    par = client.post("/api/price/irs", json={**params, "fixed_rate": None, "snapshot": "MX-DEMO"})
    assert trade["params"]["fixed_rate"] == pytest.approx(par.get_json()["risk"]["par_rate"], rel=1e-9)
    assert client.get("/api/trades/%d" % trade["id"]).get_json()["params"]["fixed_rate"] == trade["params"]["fixed_rate"]
    row = {r["id"]: r for r in client.get("/api/portfolio/valuation?snapshot=MX-DEMO").get_json()["rows"]}[trade["id"]]
    assert row["error"] is None and row["status"] == "viva"
    assert abs(row["pv"]) < 1e-6 * 5e8  # nace a la par: PV 0 en la fecha de pacto


def test_irs_at_par_uses_the_request_snapshot_and_the_final_dates(client):
    r = client.post("/api/market/MX-DEMO/roll", json={"id": "D35", "as_of": "2026-12-15"})
    assert r.status_code == 201
    params = {k: v for k, v in IRS.items() if k not in ("fixed_rate", "periods")}
    body = {**_trade(params={**params, "periods": 4}), "snapshot": "D35", "maturity_date": "2027-04-27"}
    trade = client.post("/api/trades", json=body).get_json()
    # 133 días = 4.75 periodos de 28: se ajusta a 5 periodos (140 días)
    assert trade["trade_date"] == "2026-12-15" and trade["params"]["periods"] == 5
    assert trade["maturity_date"] == "2027-05-04"
    row = {r["id"]: r for r in client.get("/api/portfolio/valuation?snapshot=D35").get_json()["rows"]}[trade["id"]]
    assert abs(row["pv"]) < 1e-6 * 1e6


# H02: la par solo tiene sentido en la fecha de inicio. Con inicio anterior al as_of del snapshot el alta
# guardaba la par del swap envejecido (sin fijaciones, sin aviso): ahora exige la tasa pactada.
PAR_MESSAGE = (
    "Para una operación que ya empezó capture la tasa pactada: la tasa par solo se calcula en la fecha de inicio"
)


@pytest.mark.parametrize("omit", [True, False], ids=["sin fixed_rate", "fixed_rate null"])
def test_irs_that_already_started_needs_its_fixed_rate(client, omit):
    params = {k: v for k, v in IRS.items() if k != "fixed_rate"}
    params = params if omit else {**params, "fixed_rate": None}
    before = len(client.get("/api/trades").get_json()["trades"])
    r = client.post("/api/trades", json={**_trade(params=params), "trade_date": "2026-10-12"})  # as_of: 2026-11-10
    assert r.status_code == 400
    assert r.get_json() == {"error": PAR_MESSAGE, "field": "fixed_rate"}
    assert len(client.get("/api/trades").get_json()["trades"]) == before


def test_irs_that_already_started_with_its_fixed_rate_is_booked_as_given(client):
    r = client.post("/api/trades", json={**_trade(), "trade_date": "2026-10-12"})
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["params"]["fixed_rate"] == IRS["fixed_rate"]


def test_irs_par_is_judged_against_the_request_snapshot_not_the_default_one(client):
    assert client.post("/api/market/MX-DEMO/roll", json={"id": "D35", "as_of": "2026-12-15"}).status_code == 201
    params = {k: v for k, v in IRS.items() if k != "fixed_rate"}
    # 2026-11-24 es posterior al as_of de MX-DEMO pero anterior al de D35: con D35 ya empezó
    body = {**_trade(params=params), "trade_date": "2026-11-24", "snapshot": "D35"}
    r = client.post("/api/trades", json=body)
    assert (r.status_code, r.get_json()["field"]) == (400, "fixed_rate")
    assert client.post("/api/trades", json={**body, "snapshot": "MX-DEMO"}).status_code == 201


def test_irs_born_at_par_on_the_snapshot_date_or_later_still_works(client):
    params = {k: v for k, v in IRS.items() if k != "fixed_rate"}
    for start in ("2026-11-10", "2026-11-24"):  # el as_of de MX-DEMO y un inicio a futuro
        r = client.post("/api/trades", json={**_trade(params=params), "trade_date": start})
        assert r.status_code == 201 and isinstance(r.get_json()["params"]["fixed_rate"], float), start


def test_equity_option_trade_values_in_mxn(client):
    params = {"option_type": "call", "spot": 100.0, "strike": 100.0, "volatility": 0.2,
              "rate": 0.05, "dividend_yield": 0.0, "maturity_years": 1.0, "quantity": 10}
    assert client.post("/api/trades", json=_trade("equity_option", params)).status_code == 201
    row = client.get("/api/portfolio/valuation?snapshot=MX-DEMO").get_json()["rows"][-1]
    assert row["currency"] == "MXN" and row["error"] is None and row["pv_mxn"] > 0
