"""Semilla de operaciones sintéticas (contrapartes inventadas, tasas fijas explícitas y no par)."""
import sqlite3

from desk.api import db
from desk.api.portfolio import create_trade
from desk.api.seed_market import SNAPSHOT_ID

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


# Corte 9: nueve operaciones más (tres por contraparte) para que el XVA tenga compensación real.
# Todas con tasa, diferencial y tipo de intercambio explícitos (nunca a la par) y `trade_date` fija
# para que el envejecimiento sea reproducible. No están en `TRADES`: la batería de validación
# contra QuantLib (`desk/validation/export_cases.py`) sigue sembrando solo las siete originales.
# Compensación parcial: Alfa (payer 500e6 vs receiver 300e6), Beta (receiver 250e6 vs payer 150e6),
# Gamma (SOFR payer 20e6 vs receiver 10e6).
XVA_TRADES = [
    ("irs", _ALFA, {"curve": "TIIE-F", "side": "receiver", "notional": 300e6, "periods": 39, "fixed_rate": 0.0710},
     "2025-11-10"),
    ("irs", _ALFA, {"curve": "SOFR", "side": "receiver", "notional": 15e6, "periods": 3, "fixed_rate": 0.0375},
     "2026-02-03"),
    ("xccy_swap", _ALFA, {"side": "pay_usd", "notional_usd": 20e6, "periods": 39, "fx_rate": 18.20,
                          "spread": 0.0005, "exchange": "both"}, "2026-05-12"),
    ("irs", _BETA, {"curve": "TIIE-F", "side": "payer", "notional": 150e6, "periods": 52, "fixed_rate": 0.0705},
     "2026-08-17"),
    ("xccy_swap", _BETA, {"side": "pay_mxn", "notional_usd": 10e6, "periods": 26, "fx_rate": 18.60,
                          "spread": 0.0010, "exchange": "both"}, "2026-11-10"),
    ("irs", _BETA, {"curve": "SOFR", "side": "payer", "notional": 12e6, "periods": 5, "fixed_rate": 0.0365},
     "2026-11-10"),
    ("irs", _GAMMA, {"curve": "SOFR", "side": "receiver", "notional": 10e6, "periods": 3, "fixed_rate": 0.0350},
     "2025-08-01"),
    ("irs", _GAMMA, {"curve": "TIIE-F", "side": "payer", "notional": 200e6, "periods": 13, "fixed_rate": 0.0690},
     "2026-11-10"),
    ("xccy_swap", _GAMMA, {"side": "pay_usd", "notional_usd": 8e6, "periods": 52, "fx_rate": 17.90,
                           "spread": 0.0000, "exchange": "final"}, "2025-02-14"),
]

_XVA_TRADES_KEY = "seed.xva_trades_v1"


def ensure_xva_trades(conn: sqlite3.Connection) -> None:
    """Añade las nueve operaciones del corte 9, una sola vez (sin commit).

    Idempotente con `settings["seed.xva_trades_v1"]`: bases nuevas y bases ya sembradas las reciben
    en el primer arranque, y un portafolio vaciado a mano después no se resiembra. No toca las
    existentes y no hace nada si el snapshot `MX-DEMO` no existe (no hay con qué fijar las fechas).
    """
    if conn.execute("SELECT 1 FROM settings WHERE key = ?", (_XVA_TRADES_KEY,)).fetchone():
        return
    if conn.execute("SELECT 1 FROM snapshots WHERE id = ?", (SNAPSHOT_ID,)).fetchone() is None:
        return
    for product, counterparty, params, trade_date in XVA_TRADES:
        create_trade(
            conn,
            {"product": product, "counterparty": counterparty, "params": params, "trade_date": trade_date},
        )
    conn.execute(
        "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
        (_XVA_TRADES_KEY, "1", db.now_iso()),
    )
