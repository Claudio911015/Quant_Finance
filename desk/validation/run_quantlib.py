"""Runner de la referencia independiente: lee cases.json, reconstruye las curvas en QuantLib y valúa cada caso.

Se corre con el Python del entorno de QuantLib (nunca con el del backend):

    $QLPY desk/validation/run_quantlib.py [--cases P] [--out P]

Cada producto tiene su pricer en ql_rates / ql_hw / ql_fx con la firma `pricer(case, ctx) -> float`
(PV en la moneda y con el signo de `pv_desk`). Un caso que falla no detiene el arnés: queda con
`pv_ref: null` y el mensaje en `error`.
"""
import argparse
import json
import math
import platform
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import QuantLib as ql  # noqa: E402

import common  # noqa: E402
import ql_curves  # noqa: E402
import ql_fx  # noqa: E402
import ql_hw  # noqa: E402
import ql_rates  # noqa: E402

PRICERS = {**ql_rates.PRICERS, **ql_hw.PRICERS, **ql_fx.PRICERS}
METHODS = {**ql_rates.METHODS, **ql_hw.METHODS, **ql_fx.METHODS}


def build_context(cases_doc: dict) -> dict:
    """Contexto compartido por los pricers: fecha, curvas de QuantLib, spot, Hull-White y monedas."""
    today = ql_curves.setup(cases_doc["snapshot"]["as_of"])
    curves = {name: ql_curves.build_curve(spec, today) for name, spec in cases_doc["curves"].items()}
    return {
        "today": today,
        "curves": curves,
        "spot": float(cases_doc["snapshot"]["spot"]),
        "hw": cases_doc["hw"],
        "currencies": {"TIIE-F": ql.MXNCurrency(), "SOFR": ql.USDCurrency()},
    }


def price_case(case: dict, ctx: dict) -> dict:
    """{"id", "pv_ref", "error"} de un caso; nunca lanza."""
    product = case["product"]
    pricer = PRICERS.get(product)
    if pricer is None:
        return {"id": case["id"], "pv_ref": None, "error": "sin pricer de QuantLib para %s" % product}
    try:
        pv = float(pricer(case, ctx))
    except Exception as exc:  # el arnés sigue con los demás casos
        return {"id": case["id"], "pv_ref": None, "error": str(exc) or exc.__class__.__name__}
    if not math.isfinite(pv):
        return {"id": case["id"], "pv_ref": None, "error": "QuantLib devolvió un PV no finito"}
    return {"id": case["id"], "pv_ref": pv, "error": None}


def run(cases_doc: dict) -> dict:
    """Documento completo de reference.json para un cases.json ya cargado."""
    ctx = build_context(cases_doc)
    curves = {
        name: ql_curves.curve_report(spec, ctx["curves"][name], ctx["today"])
        for name, spec in cases_doc["curves"].items()
    }
    return {
        "generated_at": common.now_iso(),
        "reference": {
            "library": "QuantLib",
            "version": ql.__version__,
            "python": platform.python_version(),
            "env": common.QUANTLIB_ENV,
        },
        "curves": curves,
        "methods": dict(METHODS),
        "cases": [price_case(case, ctx) for case in cases_doc["cases"]],
    }


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Referencia de QuantLib para la validación del desk.")
    parser.add_argument("--cases", default=str(common.CASES_PATH))
    parser.add_argument("--out", default=str(common.REFERENCE_PATH))
    args = parser.parse_args(argv)

    with open(args.cases, encoding="utf-8") as f:
        cases_doc = json.load(f)
    doc = run(cases_doc)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")

    rows = doc["cases"]
    priced = sum(1 for r in rows if r["pv_ref"] is not None)
    errors = sum(1 for r in rows if r["error"] is not None)
    print("reference.json: %d casos, %d con PV, %d errores" % (len(rows), priced, errors))


if __name__ == "__main__":
    main()
