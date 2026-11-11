"""Compara el PV del desk con la referencia de QuantLib y escribe `report.json`.

Corre con el Python del backend: `python -m desk.validation.compare`. Lee `cases.json` (PV del desk y DF de sus
curvas), `reference.json` (PV y DF de QuantLib) y `known_differences.json` (diferencias explicadas); sale con
código 1 si algún caso queda fuera de tolerancia o alguna curva no coincide, pero escribe el reporte igualmente.
"""
import json
import sys
from typing import Any, Dict, List, Optional

from desk.validation import common

# Cada paso con su comando completo y el intérprete que lo corre (las rutas de ambos Python van en `reproduce`).
STEPS = [
    "python -m desk.validation.export_cases  # con el Python del backend",
    "python desk/validation/run_quantlib.py  # con el Python de QuantLib",
    "python -m desk.validation.compare  # con el Python del backend",
]


def _curve_checks(cases_doc: dict, reference_doc: dict) -> List[Dict[str, Any]]:
    """Una fila por curva (en el orden de `cases.json`) con la diferencia máxima de DF en pilares y en fechas intermedias."""
    rows = []
    for name, spec in cases_doc["curves"].items():
        ref = reference_doc["curves"][name]
        maxima = {}
        for kind, ref_key in (("pillars", "pillars"), ("checks", "checks")):
            desk_rows, ref_rows = spec[kind], ref[ref_key]
            if [r["days"] for r in desk_rows] != [r["days"] for r in ref_rows]:
                raise ValueError("Las fechas de %s de la curva %s no coinciden entre cases.json y reference.json" % (kind, name))
            maxima[kind] = max(abs(d["df"] - r["df_ref"]) for d, r in zip(desk_rows, ref_rows))
        rows.append({
            "curve": name,
            "currency": spec["currency"],
            "interpolation": ref["interpolation"],
            "pillars": len(spec["pillars"]),
            "pillar_max_abs_diff": maxima["pillars"],
            "pillar_tolerance": common.PILLAR_TOLERANCE,
            "checks": len(spec["checks"]),
            "check_max_abs_diff": maxima["checks"],
            "check_tolerance": common.CHECK_TOLERANCE,
            "ok": maxima["pillars"] <= common.PILLAR_TOLERANCE and maxima["checks"] <= common.CHECK_TOLERANCE,
        })
    return rows


def _case_rows(cases_doc: dict, reference_doc: dict, known_by_case: Dict[str, dict]) -> List[Dict[str, Any]]:
    refs = {row["id"]: row for row in reference_doc["cases"]}
    rows = []
    for case in cases_doc["cases"]:
        ref = refs.get(case["id"])
        pv_ref = ref["pv_ref"] if ref else None
        error = ref["error"] if ref else "La referencia de QuantLib no incluye este caso"
        abs_diff, rel_diff = common.diffs(case["pv_desk"], pv_ref, case["notional"])
        tolerance = common.TOLERANCES[case["product"]]
        rows.append({
            "id": case["id"],
            "product": case["product"],
            "label": case["label"],
            "source": case["source"],
            "trade_id": case["trade_id"],
            "currency": case["currency"],
            "notional": case["notional"],
            "pv_desk": case["pv_desk"],
            "pv_ref": pv_ref,
            "abs_diff": abs_diff,
            "rel_diff": rel_diff,
            "tolerance": tolerance,
            "verdict": common.classify(rel_diff, tolerance, known_by_case.get(case["id"])),
            "error": error,
        })
    return rows


def _summary(rows: List[Dict[str, Any]], methods: Dict[str, str]) -> List[Dict[str, Any]]:
    out = []
    for product in common.PRODUCTS:
        mine = [r for r in rows if r["product"] == product]
        measured = [r for r in mine if r["rel_diff"] is not None]
        worst = max(measured, key=lambda r: r["rel_diff"]) if measured else None
        out.append({
            "product": product,
            "label": common.PRODUCT_LABELS[product],
            "method": methods.get(product, ""),
            "tolerance": common.TOLERANCES[product],
            "cases": len(mine),
            "within": sum(1 for r in mine if r["verdict"] == "ok"),
            "explained": sum(1 for r in mine if r["verdict"] == "explained"),
            "failed": sum(1 for r in mine if r["verdict"] == "fail"),
            "worst_abs_diff": max(r["abs_diff"] for r in measured) if measured else None,
            "worst_rel_diff": worst["rel_diff"] if worst else None,
            "worst_case": worst["id"] if worst else None,
        })
    return out


def _known_rows(known_doc: dict, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id = {r["id"]: r for r in rows}
    out = []
    for entry in known_doc.get("differences", []):
        case = by_id.get(entry["case_id"])
        if case is None:
            raise ValueError("known_differences.json menciona el caso %s, que no está en cases.json" % entry["case_id"])
        out.append({
            "case_id": entry["case_id"],
            "product": case["product"],
            "label": case["label"],
            "kind": entry["kind"],
            "convention": entry["convention"],
            "cause": entry["cause"],
            "expected_rel_diff": entry["expected_rel_diff"],
            "max_rel_diff": entry["max_rel_diff"],
            "observed_rel_diff": case["rel_diff"],
            "tolerance": case["tolerance"],
            "verdict": case["verdict"],
        })
    return out


def compare(cases_doc: dict, reference_doc: dict, known_doc: dict) -> dict:
    """Documento completo de `report.json`."""
    known_by_case = {e["case_id"]: e for e in known_doc.get("differences", [])}
    rows = _case_rows(cases_doc, reference_doc, known_by_case)
    return {
        "generated_at": common.now_iso(),
        "snapshot": cases_doc["snapshot"],
        "desk_commit": cases_doc["desk_commit"],
        "desk_dirty": cases_doc["desk_dirty"],
        "reference": reference_doc["reference"],
        "reproduce": {
            "command": common.REPRODUCE_COMMAND,
            "backend_python": common.BACKEND_PYTHON,
            "quantlib_python": common.QUANTLIB_PYTHON,
            "steps": list(STEPS),
        },
        "tolerances": dict(common.TOLERANCES),
        "totals": {
            "cases": len(rows),
            "within": sum(1 for r in rows if r["verdict"] == "ok"),
            "explained": sum(1 for r in rows if r["verdict"] == "explained"),
            "failed": sum(1 for r in rows if r["verdict"] == "fail"),
        },
        "summary": _summary(rows, reference_doc.get("methods", {})),
        "curves": _curve_checks(cases_doc, reference_doc),
        "cases": rows,
        "known_differences": _known_rows(known_doc, rows),
    }


def _load(path, default: Optional[dict] = None) -> dict:
    if default is not None and not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    report = compare(
        _load(common.CASES_PATH),
        _load(common.REFERENCE_PATH),
        _load(common.KNOWN_PATH, {"differences": []}),
    )
    with open(common.REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")
    t = report["totals"]
    print("report.json: %d casos · %d dentro · %d explicadas · %d fuera" % (t["cases"], t["within"], t["explained"], t["failed"]))
    if t["failed"] > 0 or not all(c["ok"] for c in report["curves"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
