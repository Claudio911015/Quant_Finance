"""Ayudas compartidas de las pruebas de operaciones del corte 5 (sin tests).

Las fechas se aceptan como `date` o como texto ISO.
"""
from datetime import date
from typing import Any, Callable, Dict, Optional, Union

from desk.api import events, fixings, market, portfolio, valuation
from desk.api.db import connect

ALFA = "Banco Alfa (sintético)"

Day = Union[date, str]


def _iso(day: Day) -> str:
    return day.isoformat() if isinstance(day, date) else day


def confirm_raw(app, trade_id: int, day: date, amount: float, currency: str = "MXN") -> None:
    """Inserta por `events.insert_event` (sin pasar por la ruta) una confirmación de liquidación.

    Abre su propia conexión y hace commit. `computed_amount` queda en `None`: no se calculó nada.
    """
    conn = connect(app.config["DESK_DB"])
    try:
        events.insert_event(
            conn,
            trade_id,
            "transfer",
            day,
            {
                "kind": "settlement_confirmed",
                "amount": amount,
                "currency": currency,
                "flow_kind": "coupon",
                "computed_amount": None,
            },
        )
        conn.commit()
    finally:
        conn.close()


def irs_trade(
    client,
    curve: str = "TIIE-F",
    side: str = "payer",
    notional: float = 100e6,
    periods: int = 52,
    fixed_rate: Optional[float] = None,
    counterparty: str = ALFA,
    start: Optional[Day] = None,
) -> Dict[str, Any]:
    """Da de alta un `irs` por `POST /api/trades` y devuelve la operación (sin `fixed_rate` nace a la par)."""
    params = {"curve": curve, "side": side, "notional": notional, "periods": periods}
    if fixed_rate is not None:
        params["fixed_rate"] = fixed_rate
    body = {"product": "irs", "counterparty": counterparty, "params": params}
    if start is not None:
        body["start_date"] = _iso(start)
    r = client.post("/api/trades", json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def fx_trade(
    client,
    product: str,
    side: str = "buy",
    option_type: str = "call",
    notional_usd: float = 5e6,
    strike: float = 19.5,
    days: int = 120,
    counterparty: str = ALFA,
) -> Dict[str, Any]:
    """Da de alta un `fx_forward` o `fx_option` por `POST /api/trades` y devuelve la operación."""
    params = {"side": side, "notional_usd": notional_usd, "strike": strike, "days": days}
    if product == "fx_option":
        params["option_type"] = option_type
    r = client.post(
        "/api/trades", json={"product": product, "counterparty": counterparty, "params": params}
    )
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def own_pv(
    app,
    trade_id: int,
    snapshot: str = "MX-DEMO",
    mkt_fn: Optional[Callable[[market.MarketContext], market.MarketContext]] = None,
) -> float:
    """`pv_mxn` de la operación en `snapshot`; `mkt_fn` puede desplazar el contexto (p. ej. `mkt.shifted(...)`)."""
    conn = connect(app.config["DESK_DB"])
    try:
        trade = portfolio.get_trade(conn, trade_id)
        mkt = market.load_context(conn, snapshot)
        if mkt_fn is not None:
            mkt = mkt_fn(mkt)
        return valuation.value_trade(trade, mkt, fixings.load_all(conn))["pv_mxn"]
    finally:
        conn.close()
