import json

import pytest

from desk.validation import common

NOT_FOUND = "Aún no hay reporte de validación: genera uno con desk/validation/make_report.sh"
COMMIT = "a" * 40


def _minimal_report():
    return {
        "generated_at": "2026-11-11T20:02:00+00:00",
        "snapshot": {"id": "MX-DEMO", "as_of": "2026-11-10", "spot": 18.6},
        "desk_commit": COMMIT,
        "desk_dirty": False,
        "reference": {"library": "QuantLib", "version": "1.44", "python": "3.12.16", "env": "quantsuite-oracle"},
        "tolerances": dict(common.TOLERANCES),
        "totals": {"cases": 0, "within": 0, "explained": 0, "failed": 0},
        "summary": [],
        "curves": [],
        "cases": [],
        "known_differences": [],
    }


@pytest.fixture
def report_app(app, tmp_path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(_minimal_report()), encoding="utf-8")
    app.config["VALIDATION_REPORT"] = str(path)
    return app


def test_devuelve_el_reporte_con_commit_actual(report_app, monkeypatch):
    monkeypatch.setattr(common, "desk_commit", lambda *a, **k: COMMIT)
    r = report_app.test_client().get("/api/validation/report")
    assert r.status_code == 200
    body = r.get_json()
    expected = _minimal_report()
    assert {k: body[k] for k in expected} == expected
    assert body["current_commit"] == COMMIT
    assert body["commit_matches"] is True


def test_commit_distinto_no_coincide(report_app, monkeypatch):
    monkeypatch.setattr(common, "desk_commit", lambda *a, **k: "b" * 40)
    body = report_app.test_client().get("/api/validation/report").get_json()
    assert body["current_commit"] == "b" * 40
    assert body["commit_matches"] is False


def test_sin_git_el_commit_es_nulo(report_app, monkeypatch):
    monkeypatch.setattr(common, "desk_commit", lambda *a, **k: None)
    body = report_app.test_client().get("/api/validation/report").get_json()
    assert body["current_commit"] is None
    assert body["commit_matches"] is None


def test_archivo_ausente_da_404(app, tmp_path):
    app.config["VALIDATION_REPORT"] = str(tmp_path / "no-existe.json")
    r = app.test_client().get("/api/validation/report")
    assert r.status_code == 404
    assert r.get_json() == {"error": NOT_FOUND, "field": None}


def test_sin_configuracion_usa_la_ruta_versionada(app, tmp_path, monkeypatch):
    assert "VALIDATION_REPORT" not in app.config
    monkeypatch.setattr(common, "REPORT_PATH", tmp_path / "no-existe.json")
    r = app.test_client().get("/api/validation/report")
    assert r.status_code == 404
    assert r.get_json()["error"] == NOT_FOUND
