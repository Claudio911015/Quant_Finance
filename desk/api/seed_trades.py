"""Semilla de operaciones sintéticas (contrapartes inventadas, tasas fijas explícitas y no par)."""
import sqlite3

from desk.api.portfolio import create_trade

_ALFA = "Banco Alfa (sintético)"
_BETA = "Banco Beta (sintético)"
_GAMMA = "Banco Gamma (sintético)"

TRADES = [
    ("irs", _ALFA, {"curve": "TIIE-F", "side": "payer", "notional": 500e6, "periods": 26, "fixed_rate": 0.0680}),
    ("irs", _BETA, {"curve": "TIIE-F", "side": "receiver", "notional": 250e6, "periods": 65, "fixed_rate": 0.0695}),
    ("irs", _GAMMA, {"curve": "SOFR", "side": "payer", "notional": 20e6, "periods": 5, "fixed_rate": 0.0360}),
    ("fx_forward", _ALFA, {"side": "buy", "notional_usd": 10e6, "days": 182, "strike": 19.05}),
    ("fx_forward", _BETA, {"side": "sell", "notional_usd": 3e6, "days": 91, "strike": 18.85}),
    ("fx_option", _GAMMA, {"side": "buy", "option_type": "call", "notional_usd": 5e6, "days": 91, "strike": 19.00}),
    ("cap_floor", _ALFA, {"curve": "TIIE-F", "cap_type": "cap", "notional": 300e6, "periods": 39, "strike": 0.075}),
]


def seed_trades(conn: sqlite3.Connection) -> None:
    """Inserta las siete operaciones iniciales (sin commit; requiere el snapshot MX-DEMO ya sembrado)."""
    for product, counterparty, params in TRADES:
        create_trade(
            conn, {"product": product, "counterparty": counterparty, "params": params}
        )
