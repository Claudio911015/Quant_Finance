import re

import pytest

from desk.api import market
from desk.validation import common, export_cases

EXPECTED_PILLAR_DAYS = {
    "TIIE-F": [1, 28, 84, 168, 364, 728, 1092, 1820, 2548, 3640],
    "SOFR": [1, 30, 91, 182, 365, 730, 1095, 1825, 2555, 3650],
}


@pytest.fixture(scope="module")
def mkt():
    conn = export_cases.demo_conn()
    try:
        return market.load_context(conn, common.SNAPSHOT_ID)
    finally:
        conn.close()


def test_export_curves_trae_diez_pilares_con_el_df_exacto_del_desk(mkt):
    curves = export_cases.export_curves(mkt)
    assert list(curves) == ["TIIE-F", "SOFR"]
    for name, days in EXPECTED_PILLAR_DAYS.items():
        pillars = curves[name]["pillars"]
        assert [p["days"] for p in pillars] == days
        assert len(pillars) == 10
        for p in pillars:
            assert p["df"] == mkt.curves[name].discount_factor(p["days"] / 365)
        assert curves[name]["currency"] == market.CURVES[name]["currency"]
        assert curves[name]["period_days"] == market.CURVES[name]["period_days"]


def test_las_fechas_intermedias_estan_dentro_de_los_pilares(mkt):
    curves = export_cases.export_curves(mkt)
    for name, days in EXPECTED_PILLAR_DAYS.items():
        checks = curves[name]["checks"]
        assert [c["days"] for c in checks] == common.check_days(days)
        assert len(checks) == 10
        assert all(days[0] < c["days"] < days[-1] for c in checks)
        for c in checks:
            assert c["df"] == mkt.curves[name].discount_factor(c["days"] / 365)


def test_build_arma_el_documento_completo():
    doc = export_cases.build()
    assert doc["snapshot"]["id"] == "MX-DEMO"
    assert doc["snapshot"]["spot"] == 18.6
    assert doc["hw"]["TIIE-F"] == {"a": 0.05, "sigma": 0.01}
    assert set(doc) == {"generated_at", "snapshot", "desk_commit", "desk_dirty", "hw", "curves", "cases"}
    assert len(doc["cases"]) == 62  # la batería la llena build_cases (T2)


def test_classify():
    tol = 1e-6
    known = {"max_rel_diff": 4e-6}
    assert common.classify(None, tol, None) == "fail"
    assert common.classify(None, tol, known) == "fail"
    assert common.classify(0.0, tol, None) == "ok"
    assert common.classify(tol, tol, None) == "ok"
    assert common.classify(3e-6, tol, known) == "explained"
    assert common.classify(4e-6, tol, known) == "explained"
    assert common.classify(5e-6, tol, known) == "fail"
    assert common.classify(3e-6, tol, None) == "fail"


def test_diffs():
    assert common.diffs(1.0, None, 1.0) == (None, None)
    assert common.diffs(1.0, float("nan"), 1.0) == (None, None)
    assert common.diffs(1.0, float("inf"), 1.0) == (None, None)
    assert common.diffs(10.0, 7.0, 100.0) == (3.0, 0.03)


def test_check_days_son_diez_y_estrictamente_interiores():
    days = common.check_days([1, 28, 3640])
    assert len(days) == common.CHECK_COUNT
    assert days == sorted(days)
    assert all(1 < d < 3640 for d in days)


def test_desk_commit_es_un_sha_de_40_hex_en_este_worktree():
    assert re.fullmatch(r"[0-9a-f]{40}", common.desk_commit())


def test_desk_commit_sin_git_es_none(tmp_path):
    assert common.desk_commit(tmp_path) is None
    assert common.desk_dirty(tmp_path) is None
