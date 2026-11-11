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
    assert [t["id"] for t in trades] == list(range(1, 8))
    assert [t["product"] for t in trades] == [
        "irs", "irs", "irs", "fx_forward", "fx_forward", "fx_option", "cap_floor"
    ]
    assert all(t["counterparty"].endswith("(sintético)") for t in trades)

    v = client.get("/api/portfolio/valuation?snapshot=MX-DEMO").get_json()
    assert v["snapshot"] == "MX-DEMO" and v["as_of"] == "2026-11-10"
    assert len(v["rows"]) == 7
    assert all(r["error"] is None for r in v["rows"])
    assert all(r["pv_mxn"] is not None for r in v["rows"])
    assert v["total_mxn"] == pytest.approx(sum(r["pv_mxn"] for r in v["rows"]))
    # las tasas fijas de la semilla no son par: el PV de los swaps no es trivial
    assert all(abs(r["pv_mxn"]) > 1e3 for r in v["rows"][:3])
    assert set(v["rows"][0]) == {
        "id", "product", "counterparty", "notional", "currency", "maturity",
        "pv", "pv_mxn", "error",
    }


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
    assert t["id"] == 8
    assert t["notional"] == 1e6 and t["currency"] == "MXN" and t["maturity"] == "2027-11-09"
    assert t["params"]["fixed_rate"] == 0.07 and t["created_at"]
    assert set(t) == {"id", "product", "counterparty", "trade_date", "start_date",
                      "maturity_date", "params", "notional", "currency", "maturity", "created_at"}
    assert t["trade_date"] == t["start_date"] == "2026-11-10" and t["maturity_date"] == t["maturity"]
    assert client.get("/api/trades").get_json()["trades"][-1] == t

    r = client.delete("/api/trades/8")  # una operación no se borra: se termina
    assert r.status_code == 409 and r.get_json()["field"] == "id"
    assert len(client.get("/api/trades").get_json()["trades"]) == 8


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
    assert len(trades) == 8  # 7 sembradas, sin resembrar, + la nueva
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

    assert len(client.get("/api/trades").get_json()["trades"]) == 10  # el listado no se rompe
    v = client.get("/api/portfolio/valuation?snapshot=MX-DEMO").get_json()
    good, bad = v["rows"][:7], v["rows"][7:]
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
        assert len(trades) == 7 and isinstance(trades[0]["params"], dict)
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
        # irs sin tasa fija explícita no se guarda (decisión de Fable)
        (_trade(params={k: v for k, v in IRS.items() if k != "fixed_rate"}), "fixed_rate"),
        (_trade(params={**IRS, "fixed_rate": None}), "fixed_rate"),
    ],
)
def test_create_invalid_is_400_with_field(client, body, field):
    r = client.post("/api/trades", json=body)
    assert r.status_code == 400
    assert r.get_json()["field"] == field
    assert len(client.get("/api/trades").get_json()["trades"]) == 7


def test_equity_option_trade_values_in_mxn(client):
    params = {"option_type": "call", "spot": 100.0, "strike": 100.0, "volatility": 0.2,
              "rate": 0.05, "dividend_yield": 0.0, "maturity_years": 1.0, "quantity": 10}
    assert client.post("/api/trades", json=_trade("equity_option", params)).status_code == 201
    row = client.get("/api/portfolio/valuation?snapshot=MX-DEMO").get_json()["rows"][-1]
    assert row["currency"] == "MXN" and row["error"] is None and row["pv_mxn"] > 0
