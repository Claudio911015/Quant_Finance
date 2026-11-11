"""Prueba de humo del reporte de validación contra QuantLib versionado en `desk/validation/report.json`.

No importa QuantLib ni `compare.py`: recalcula diferencias y veredictos desde los PV guardados con `common`, para que
un reporte editado a mano, desactualizado respecto de sus propios números o con un caso fuera de tolerancia sin
explicar rompa la suite del backend. Para regenerarlo: `desk/validation/make_report.sh`.
"""
import copy
import json
import math
from typing import Any, Dict, List, Optional

import pytest

from desk.validation import common

MISSING = (
    "No existe %s: genera el reporte con desk/validation/make_report.sh y versiónalo"
    % common.REPORT_PATH
)


def _close(a: Optional[float], b: Optional[float]) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-15)


def _problems(report: dict, known: dict) -> List[str]:
    """Lista de incoherencias del reporte (vacía si todo cuadra). Solo usa `common`."""
    out = []  # type: List[str]
    cases = report["cases"]
    entries = {e["case_id"]: e for e in known.get("differences", [])}

    if len(cases) < common.MIN_CASES:
        out.append("hay %d casos y se exigen al menos %d" % (len(cases), common.MIN_CASES))
    for product in common.PRODUCTS:
        n = sum(1 for c in cases if c["product"] == product)
        if n < common.MIN_CASES_PER_PRODUCT:
            out.append("%s tiene %d casos y se exigen al menos %d" % (product, n, common.MIN_CASES_PER_PRODUCT))
    ids = [c["id"] for c in cases]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        out.append("id de caso repetido: %s" % dup)

    # Cada caso: tolerancia, diferencias y veredicto recalculados desde pv_desk, pv_ref y notional.
    recomputed = {}  # type: Dict[str, Dict[str, Any]]
    for c in cases:
        cid = c["id"]
        tolerance = common.TOLERANCES.get(c["product"])
        if tolerance is None or c["tolerance"] != tolerance:
            out.append("%s: tolerancia %r distinta de la de %s (%r)" % (cid, c["tolerance"], c["product"], tolerance))
            continue
        abs_diff, rel_diff = common.diffs(c["pv_desk"], c["pv_ref"], c["notional"])
        if not _close(abs_diff, c["abs_diff"]):
            out.append("%s: abs_diff guardado %r, recalculado %r" % (cid, c["abs_diff"], abs_diff))
        if not _close(rel_diff, c["rel_diff"]):
            out.append("%s: rel_diff guardado %r, recalculado %r" % (cid, c["rel_diff"], rel_diff))
        verdict = common.classify(rel_diff, tolerance, entries.get(cid))
        if verdict != c["verdict"]:
            out.append("%s: veredicto guardado %r, recalculado %r" % (cid, c["verdict"], verdict))
        if c["verdict"] == "fail" or verdict == "fail":
            out.append("%s: fuera de tolerancia %r sin explicación (diferencia relativa %r)" % (cid, tolerance, rel_diff))
        recomputed[cid] = {"abs_diff": abs_diff, "rel_diff": rel_diff, "product": c["product"], "verdict": verdict}

    # Totales y resumen por producto.
    verdicts = [r["verdict"] for r in recomputed.values()]
    expected_totals = {
        "cases": len(cases),
        "within": verdicts.count("ok"),
        "explained": verdicts.count("explained"),
        "failed": verdicts.count("fail"),
    }
    if report["totals"] != expected_totals:
        out.append("totals %r no cuadra con los casos (%r)" % (report["totals"], expected_totals))
    rows = {s["product"]: s for s in report["summary"]}
    if [s["product"] for s in report["summary"]] != list(common.PRODUCTS):
        out.append("summary no lista los productos %r en orden" % (common.PRODUCTS,))
    for product in common.PRODUCTS:
        s = rows.get(product)
        if s is None:
            continue
        mine = [r for r in recomputed.values() if r["product"] == product]
        measured = [r for r in mine if r["rel_diff"] is not None]
        expected = {
            "cases": sum(1 for c in cases if c["product"] == product),
            "within": sum(1 for r in mine if r["verdict"] == "ok"),
            "explained": sum(1 for r in mine if r["verdict"] == "explained"),
            "failed": sum(1 for r in mine if r["verdict"] == "fail"),
        }
        for key, value in expected.items():
            if s[key] != value:
                out.append("summary de %s: %s guardado %r, recalculado %r" % (product, key, s[key], value))
        if s["tolerance"] != common.TOLERANCES[product]:
            out.append("summary de %s: tolerancia %r distinta de %r" % (product, s["tolerance"], common.TOLERANCES[product]))
        worst_rel = max((r["rel_diff"] for r in measured), default=None)
        worst_abs = max((r["abs_diff"] for r in measured), default=None)
        if not _close(s["worst_rel_diff"], worst_rel):
            out.append("summary de %s: worst_rel_diff guardado %r, recalculado %r" % (product, s["worst_rel_diff"], worst_rel))
        if not _close(s["worst_abs_diff"], worst_abs):
            out.append("summary de %s: worst_abs_diff guardado %r, recalculado %r" % (product, s["worst_abs_diff"], worst_abs))
        worst_case = recomputed.get(s["worst_case"])
        if worst_rel is not None and (worst_case is None or worst_case["product"] != product
                                      or not _close(worst_case["rel_diff"], worst_rel)):
            out.append("summary de %s: worst_case %r no es el caso de mayor diferencia relativa" % (product, s["worst_case"]))

    # Diferencias conocidas: cada entrada tiene caso, motivo concreto y magnitud reproducida.
    for cid, e in entries.items():
        case = recomputed.get(cid)
        if case is None:
            out.append("known_differences: %s no existe en los casos del reporte" % cid)
            continue
        if e.get("kind") not in common.KNOWN_KINDS:
            out.append("known_differences %s: kind %r fuera de %r" % (cid, e.get("kind"), common.KNOWN_KINDS))
        if len(e.get("cause") or "") < 40:
            out.append("known_differences %s: cause de menos de 40 caracteres" % cid)
        if not (e.get("convention") or "").strip():
            out.append("known_differences %s: convention vacía" % cid)
        observed = case["rel_diff"]
        expected_rel = e.get("expected_rel_diff")
        if observed is None or expected_rel is None or abs(expected_rel - observed) > 0.10 * observed:
            out.append("known_differences %s: expected_rel_diff %r no está a ±10 %% de lo observado (%r)" % (cid, expected_rel, observed))
    shown = {k["case_id"]: k for k in report["known_differences"]}
    if len(shown) != len(report["known_differences"]) or set(shown) != set(entries):
        out.append("known_differences del reporte %r no coincide con known_differences.json %r" % (sorted(shown), sorted(entries)))
    for cid, k in shown.items():
        e = entries.get(cid)
        if e is None:
            continue
        for key in ("kind", "convention", "cause", "expected_rel_diff", "max_rel_diff"):
            if k.get(key) != e.get(key):
                out.append("known_differences %s: %s del reporte distinto del de known_differences.json" % (cid, key))
        if cid in recomputed and (not _close(k.get("observed_rel_diff"), recomputed[cid]["rel_diff"])
                                  or k.get("verdict") != recomputed[cid]["verdict"]):
            out.append("known_differences %s: observed_rel_diff o verdict del reporte no cuadran con el caso" % cid)

    # Curvas: idénticas dentro de las tolerancias de `common`.
    if not report["curves"]:
        out.append("el reporte no trae curvas")
    for curve in report["curves"]:
        name = curve["curve"]
        if curve["pillar_max_abs_diff"] > common.PILLAR_TOLERANCE:
            out.append("curva %s: diferencia en pilares %r > %r" % (name, curve["pillar_max_abs_diff"], common.PILLAR_TOLERANCE))
        if curve["check_max_abs_diff"] > common.CHECK_TOLERANCE:
            out.append("curva %s: diferencia en fechas intermedias %r > %r" % (name, curve["check_max_abs_diff"], common.CHECK_TOLERANCE))
        if not curve["ok"]:
            out.append("curva %s: marcada como no ok" % name)
    return out


def _load_report() -> dict:
    with open(common.REPORT_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_known() -> dict:
    if not common.KNOWN_PATH.exists():
        return {"differences": []}
    with open(common.KNOWN_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def report() -> dict:
    assert common.REPORT_PATH.exists(), MISSING
    return _load_report()


@pytest.fixture
def known() -> dict:
    return _load_known()


def test_el_reporte_existe():
    assert common.REPORT_PATH.exists(), MISSING


def test_el_reporte_versionado_no_tiene_problemas(report, known):
    problems = _problems(report, known)
    assert problems == [], "El reporte de validación tiene problemas:\n- " + "\n- ".join(problems)


def test_un_pv_alterado_a_mano_falla(report, known):
    altered = copy.deepcopy(report)
    altered["cases"][0]["pv_desk"] += 1e-3 * altered["cases"][0]["notional"]
    assert _problems(altered, known) != []


def test_un_caso_fuera_sin_explicacion_falla(report, known):
    altered = copy.deepcopy(report)
    case = next(c for c in altered["cases"] if c["verdict"] == "ok")
    case["pv_ref"] += 10 * case["tolerance"] * case["notional"]
    # El veredicto guardado ("ok") y las diferencias no se tocan: el reporte miente sobre este caso.
    assert _problems(altered, known) != []


def test_una_explicacion_sin_caso_falla(report, known):
    altered = copy.deepcopy(known)
    altered.setdefault("differences", []).append({
        "case_id": "no-existe-99",
        "kind": "convention",
        "convention": "Convención inventada",
        "cause": "Explicación de un caso que no está en el reporte, con longitud suficiente para pasar el mínimo.",
        "expected_rel_diff": 1e-6,
        "max_rel_diff": 2e-6,
    })
    assert _problems(report, altered) != []
