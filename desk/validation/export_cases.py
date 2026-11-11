"""Exporta las curvas (y, desde T2, los casos con su PV) del desk a `cases.json`.

Corre con el Python del backend: `python -m desk.validation.export_cases [--out RUTA]`.
"""
import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from desk.api import db, market, portfolio, valuation
from desk.api.pricing import PRODUCTS
from desk.api.qf import qfpy
from desk.api.seed_market import seed_market
from desk.api.seed_trades import seed_trades
from desk.validation import common


def demo_conn() -> sqlite3.Connection:
    """Base en memoria con el mercado `MX-DEMO` y las siete operaciones de ejemplo."""
    conn = db.connect(":memory:")
    db.init_schema(conn)
    seed_market(conn)
    seed_trades(conn)
    conn.commit()
    return conn


def export_curves(mkt: "market.MarketContext") -> Dict[str, Any]:
    """Pilares y fechas intermedias de cada curva con el DF que calcula el desk."""
    curves = {}  # type: Dict[str, Any]
    for name, spec in market.CURVES.items():
        curve = mkt.curves[name]
        pillars = mkt.pillars[name]
        curves[name] = {
            "currency": spec["currency"],
            "period_days": spec["period_days"],
            "pillars": [
                {"label": p["label"], "days": p["days"], "df": curve.discount_factor(p["days"] / 365.0)}
                for p in pillars
            ],
            "checks": [
                {"days": d, "df": curve.discount_factor(d / 365.0)}
                for d in common.check_days([p["days"] for p in pillars])
            ],
        }
    return curves


# --------------------------------------------------------------------------- batería fija
# Una lista por producto, en el orden del plan: los parámetros "crudos" que recibe `validate`.
# Los casos de portafolio (primeros de cada producto) salen de las operaciones sembradas.
# Los plazos caen en días enteros (QuantLib no admite fechas fraccionarias): ver el plan, supuesto 7.

_IRS_BATTERY = [
    # (curve, side, notional, periods, fixed_rate); fixed_rate None = a la par
    ("TIIE-F", "payer", 100e6, 13, None),
    ("TIIE-F", "receiver", 100e6, 13, 0.0750),
    ("TIIE-F", "payer", 50e6, 1, 0.0650),
    ("TIIE-F", "receiver", 200e6, 39, 0.0600),
    ("TIIE-F", "payer", 300e6, 91, 0.0720),
    ("SOFR", "receiver", 10e6, 1, 0.0380),
    ("SOFR", "payer", 25e6, 3, None),
    ("SOFR", "receiver", 15e6, 7, 0.0300),
    ("SOFR", "payer", 40e6, 10, 0.0420),
]
_FX_FORWARD_BATTERY = [
    # (side, notional_usd, days, strike)
    ("buy", 5e6, 30, 18.70),
    ("sell", 5e6, 30, 18.50),
    ("buy", 2e6, 365, 19.40),
    ("sell", 8e6, 365, 20.00),
    ("buy", 1e6, 730, 19.80),
    ("sell", 3e6, 7, 18.62),
]
_FX_OPTION_BATTERY = [
    # (side, option_type, notional_usd, days, strike)
    ("buy", "call", 2e6, 30, 18.60),
    ("buy", "put", 2e6, 30, 18.60),
    ("sell", "call", 3e6, 182, 19.50),
    ("sell", "put", 3e6, 182, 18.00),
    ("buy", "call", 1e6, 365, 17.50),
    ("buy", "put", 1e6, 365, 20.50),
    ("buy", "call", 4e6, 91, 21.00),
    ("sell", "put", 2e6, 91, 18.85),
    ("sell", "call", 1e6, 730, 19.00),
]
_EQUITY_BATTERY = [
    # (option_type, spot, strike, volatility, rate, dividend_yield, días, quantity)
    ("call", 100.0, 100.0, 0.20, 0.07, 0.02, 365, 1000.0),
    ("put", 100.0, 100.0, 0.20, 0.07, 0.02, 365, 1000.0),
    ("call", 100.0, 80.0, 0.25, 0.07, 0.0, 182, 500.0),
    ("put", 100.0, 120.0, 0.35, 0.07, 0.0, 730, 500.0),
    ("call", 100.0, 130.0, 0.25, 0.07, 0.01, 30, 2000.0),
    ("put", 100.0, 90.0, 0.30, 0.07, 0.01, 91, 2000.0),
    ("call", 50.0, 50.0, 0.30, 0.04, 0.05, 1825, 100.0),
    ("put", 250.0, 262.5, 0.18, 0.10, 0.0, 365, 50.0),
]
_BOND_BATTERY = [
    # (curve, face, coupon_rate, periods, frequency); frequency None = la del desk (semestral exacta)
    ("TIIE-F", 100e6, 0.08, 6, 365.0 / 182),
    ("TIIE-F", 100e6, 0.07, 20, 365.0 / 182),
    ("TIIE-F", 50e6, 0.0, 1, 1.0),
    ("TIIE-F", 10e6, 0.10, 13, 365.0 / 28),
    ("SOFR", 20e6, 0.04, 5, 1.0),
    ("SOFR", 20e6, 0.03, 8, 365.0 / 91),
    ("TIIE-F", 30e6, 0.065, 3, 365.0 / 91),
    ("TIIE-F", 100e6, 0.075, 6, None),
]
_CAP_FLOOR_BATTERY = [
    # (curve, cap_type, notional, periods, strike)
    ("TIIE-F", "cap", 100e6, 13, 0.070),
    ("TIIE-F", "floor", 100e6, 13, 0.065),
    ("TIIE-F", "cap", 50e6, 6, 0.060),
    ("TIIE-F", "floor", 200e6, 39, 0.070),
    ("SOFR", "cap", 20e6, 5, 0.040),
    ("SOFR", "floor", 20e6, 3, 0.035),
    ("SOFR", "cap", 10e6, 10, 0.030),
]
_SWAPTION_BATTERY = [
    # (curve, swaption_type, notional, strike, días de expiración, swap_tenor_years)
    ("TIIE-F", "payer", 100e6, 0.070, 365, 2.0),
    ("TIIE-F", "receiver", 100e6, 0.070, 365, 2.0),
    ("TIIE-F", "payer", 200e6, 0.068, 730, 5.0),
    ("TIIE-F", "receiver", 50e6, 0.065, 182, 1.0),
    ("TIIE-F", "receiver", 100e6, 0.065, 1095, 3.0),
    ("SOFR", "payer", 20e6, 0.036, 365, 5.0),
    ("SOFR", "receiver", 20e6, 0.035, 730, 3.0),
    ("SOFR", "payer", 10e6, 0.040, 1825, 5.0),
]


def _battery_raw(product: str) -> List[Dict[str, Any]]:
    """Los parámetros crudos de la batería de un producto (lo que recibe `validate`)."""
    if product == "irs":
        return [
            {"curve": c, "side": s, "notional": n, "periods": k, "fixed_rate": r}
            for c, s, n, k, r in _IRS_BATTERY
        ]
    if product == "fx_forward":
        return [
            {"side": s, "notional_usd": n, "days": d, "strike": k} for s, n, d, k in _FX_FORWARD_BATTERY
        ]
    if product == "fx_option":
        return [
            {"side": s, "option_type": t, "notional_usd": n, "days": d, "strike": k}
            for s, t, n, d, k in _FX_OPTION_BATTERY
        ]
    if product == "equity_option":
        return [
            {
                "option_type": t, "spot": s, "strike": k, "volatility": v, "rate": r,
                "dividend_yield": q, "maturity_years": d / 365.0, "quantity": n,
            }
            for t, s, k, v, r, q, d, n in _EQUITY_BATTERY
        ]
    if product == "bond":
        raws = []  # type: List[Dict[str, Any]]
        for c, face, cpn, k, f in _BOND_BATTERY:
            raw = {"curve": c, "face": face, "coupon_rate": cpn, "periods": k}
            if f is not None:
                raw["frequency"] = f
            raws.append(raw)
        return raws
    if product == "cap_floor":
        return [
            {"curve": c, "cap_type": t, "notional": n, "periods": k, "strike": x}
            for c, t, n, k, x in _CAP_FLOOR_BATTERY
        ]
    if product == "swaption":
        return [
            {
                "curve": c, "swaption_type": t, "notional": n, "strike": x,
                "expiry_years": d / 365.0, "swap_tenor_years": y,
            }
            for c, t, n, x, d, y in _SWAPTION_BATTERY
        ]
    raise ValueError("producto sin batería: %s" % product)


# ------------------------------------------------------------------ inputs, nocional, rótulo

def _round_days(years: float) -> int:
    return int(round(years * 365))


def _inputs(product: str, p: Dict[str, Any], priced: Dict[str, Any], mkt: "market.MarketContext") -> Dict[str, Any]:
    """Lo que la referencia necesita y no está en `params`; se lee del desk, no se recalcula."""
    risk, details = priced["risk"], priced["details"]
    if product == "irs":
        period_days = market.CURVES[p["curve"]]["period_days"]
        pay = qfpy.ois_payment_days(p["periods"] * period_days, period_days)
        return {"period_days": period_days, "payment_days": [int(d) for d in pay]}
    if product == "fx_forward":
        return {"spot": mkt.spot, "forward": risk["forward"]}
    if product == "fx_option":
        return {"spot": mkt.spot, "vol": risk["vol"], "forward": risk["forward"]}
    if product == "equity_option":
        return {"days": _round_days(p["maturity_years"])}
    if product == "bond":
        schedule = qfpy.Bond(p["face"], p["coupon_rate"], p["periods"], p["frequency"]).cash_flow_schedule()
        return {"schedule": [{"t": t, "amount": a} for t, a in schedule]}
    period_days = market.CURVES[p["curve"]]["period_days"]
    out = {"period_days": period_days}  # cap_floor y swaption
    if product == "swaption":
        out["payments"] = int(round(p["swap_tenor_years"] * 365 / period_days))
    out["hw_a"] = details["hw_a"]
    out["hw_sigma"] = details["hw_sigma"]
    return out


def _notional_currency(product: str, p: Dict[str, Any], mkt: "market.MarketContext"):
    """(nocional, moneda) en que se mide la diferencia relativa; la moneda es la de `pv`."""
    if product in ("irs", "cap_floor", "swaption"):
        return p["notional"], market.CURVES[p["curve"]]["currency"]
    if product == "bond":
        return p["face"], market.CURVES[p["curve"]]["currency"]
    if product in ("fx_forward", "fx_option"):
        return p["notional_usd"] * mkt.spot, "MXN"
    return p["quantity"] * p["spot"], "MXN"


def _count(n: float, singular: str, plural: str) -> str:
    """«1 periodo», «26 periodos», «1 año», «2 años»: concuerda el sustantivo con la cantidad."""
    return "%g %s" % (n, singular if n == 1 else plural)


def _label(product: str, p: Dict[str, Any], inputs: Dict[str, Any], at_par: bool) -> str:
    if product == "irs":
        side = "Paga fija" if p["side"] == "payer" else "Recibe fija"
        text = "%s %s · %s de %d días · fija %.4f %%" % (
            side, p["curve"], _count(p["periods"], "periodo", "periodos"), inputs["period_days"], p["fixed_rate"] * 100
        )
        return text + (" (a la par)" if at_par else "")
    if product == "fx_forward":
        return "%s USD %s a %d días · strike %.4f" % (
            "Compra" if p["side"] == "buy" else "Venta", format(p["notional_usd"], ",.0f"), p["days"], p["strike"]
        )
    if product == "fx_option":
        return "%s %s USD %s a %d días · strike %.4f" % (
            "Compra" if p["side"] == "buy" else "Venta", p["option_type"],
            format(p["notional_usd"], ",.0f"), p["days"], p["strike"],
        )
    if product == "equity_option":
        return "%s · S %g · K %g · %d días · σ %g %% · r %g %% · q %g %% · %g títulos" % (
            p["option_type"].capitalize(), p["spot"], p["strike"], inputs["days"],
            p["volatility"] * 100, p["rate"] * 100, p["dividend_yield"] * 100, p["quantity"],
        )
    if product == "bond":
        return "Bono %s · cupón %.2f %% · %s cada %g días" % (
            p["curve"], p["coupon_rate"] * 100, _count(p["periods"], "cupón", "cupones"), 365 / p["frequency"]
        )
    if product == "cap_floor":
        return "%s %s · %s · strike %.2f %%" % (
            p["cap_type"].capitalize(), p["curve"], _count(p["periods"], "periodo", "periodos"), p["strike"] * 100
        )
    return "%s %s · expira en %d días · swap de %s · strike %.2f %%" % (
        "Pagadora" if p["swaption_type"] == "payer" else "Receptora", p["curve"],
        _round_days(p["expiry_years"]), _count(p["swap_tenor_years"], "año", "años"), p["strike"] * 100,
    )


def _case(
    product: str, number: int, trade: Optional[Dict[str, Any]], raw: Dict[str, Any],
    mkt: "market.MarketContext",
) -> Dict[str, Any]:
    """Un caso: `trade` es la operación del portafolio (None en la batería) y `raw` sus parámetros."""
    pricer = PRODUCTS[product]
    params = pricer.validate(raw)
    at_par = False
    if product == "irs" and params["fixed_rate"] is None:
        # "A la par": la tasa fija siempre queda numérica, la par del desk.
        params["fixed_rate"] = pricer.price(params, mkt)["risk"]["par_rate"]
        at_par = True
    priced = pricer.price(params, mkt)
    pv_desk = priced["pv"] if trade is None else valuation.value_trade(trade, mkt)["pv"]
    inputs = _inputs(product, params, priced, mkt)
    notional, currency = _notional_currency(product, params, mkt)
    label = _label(product, params, inputs, at_par)
    if trade is not None:
        label += " · portafolio #%d" % trade["id"]
    return {
        "id": "%s-%02d" % (product, number),
        "product": product,
        "source": "portfolio" if trade is not None else "battery",
        "trade_id": trade["id"] if trade is not None else None,
        "label": label,
        "params": params,
        "inputs": inputs,
        "currency": currency,
        "notional": notional,
        "pv_desk": pv_desk,
    }


def build_cases(conn: sqlite3.Connection, mkt: "market.MarketContext") -> List[Dict[str, Any]]:
    """Los 62 casos: las operaciones del portafolio de ejemplo y la batería fija, con su PV del desk.

    Por producto, primero los casos de portafolio (en el orden de `load_trades`) y luego los de batería.
    """
    trades = portfolio.load_trades(conn)
    cases = []  # type: List[Dict[str, Any]]
    for product in common.PRODUCTS:
        rows = [(t, t["params"]) for t in trades if t["product"] == product]
        rows += [(None, raw) for raw in _battery_raw(product)]
        for number, (trade, raw) in enumerate(rows, start=1):
            cases.append(_case(product, number, trade, raw, mkt))
    return cases


def build(conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Documento completo de `cases.json`."""
    own = conn is None
    if conn is None:
        conn = demo_conn()
    try:
        mkt = market.load_context(conn, common.SNAPSHOT_ID)
        return {
            "generated_at": common.now_iso(),
            "snapshot": {"id": mkt.snapshot_id, "as_of": mkt.as_of.isoformat(), "spot": mkt.spot},
            "desk_commit": common.desk_commit(),
            "desk_dirty": common.desk_dirty(),
            "hw": mkt.hw,
            "curves": export_curves(mkt),
            "cases": build_cases(conn, mkt),
        }
    finally:
        if own:
            conn.close()


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Exporta las curvas y los casos del desk a cases.json")
    parser.add_argument("--out", default=str(common.CASES_PATH), help="archivo de salida")
    args = parser.parse_args(argv)
    doc = build()
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("cases.json: %d casos" % len(doc["cases"]))


if __name__ == "__main__":
    main()
