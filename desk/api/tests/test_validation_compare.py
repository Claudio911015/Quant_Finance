import json

from desk.validation import common, compare


def test_los_pasos_para_reproducir_son_comandos_completos_con_su_interprete():
    # La pantalla Validación los muestra tal cual en «Cómo reproducir»: el paso de QuantLib no puede quedarse en
    # el nombre del script suelto mientras los otros dos dan el comando completo.
    steps = compare.STEPS
    assert len(steps) == 3
    assert "python -m desk.validation.export_cases" in steps[0]
    assert "python desk/validation/run_quantlib.py" in steps[1]
    assert "python -m desk.validation.compare" in steps[2]
    assert "Python de QuantLib" in steps[1]
    assert all("Python del backend" in s for s in (steps[0], steps[2]))


def test_el_reporte_versionado_trae_los_pasos_de_compare():
    with open(common.REPORT_PATH, encoding="utf-8") as f:
        report = json.load(f)
    assert report["reproduce"]["steps"] == compare.STEPS, "regenera el reporte con desk/validation/make_report.sh"
