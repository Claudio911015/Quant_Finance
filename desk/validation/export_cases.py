"""Exporta las curvas (y, desde T2, los casos con su PV) del desk a `cases.json`.

Corre con el Python del backend: `python -m desk.validation.export_cases [--out RUTA]`.
"""
import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from desk.api import db, market
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


def build_cases(conn: sqlite3.Connection, mkt: "market.MarketContext") -> List[Dict[str, Any]]:
    """Casos de la batería con su PV del desk. Stub: lo llena T2."""
    return []


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
