"""Procedencia (`sources`, `data_quality`, `read_only`) de los snapshots y no regresión de MX-DEMO."""
import copy
import json

import pytest

from desk.api import db, market, seed_market

DEMO = "/api/market/snapshots/MX-DEMO"
LIVE = "/api/market/snapshots/MKT-LIVE"
LIVE_PUT_ERROR = "Mercado vivo se reconstruye en cada actualización; no se edita"


def _src(kind, as_of=None):
    return {"kind": kind, "label": "x", "as_of": as_of}


def _sources(**kinds):
    """7 fuentes; todas `synthetic` salvo las indicadas por clave (con `:` como `_`)."""
    out = {key: _src("synthetic") for key in market.SOURCE_KEYS}
    for key, kind in kinds.items():
        out[key.replace("__", ":")] = _src(kind, None if kind == "synthetic" else "2026-11-10")
    return out


def _insert_live(app_path, sources=None):
    """Inserta a mano un `MKT-LIVE` (copia de `demo_data()` más `sources`)."""
    data = copy.deepcopy(seed_market.demo_data())
    if sources is None:
        sources = _sources(
            curve__SOFR="proxy", spot="live", factor_vols="mixed"
        )
    data["sources"] = sources
    conn = db.connect(app_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO snapshots (id, label, synthetic, as_of, data) "
            "VALUES ('MKT-LIVE', 'Mercado vivo (SOFR aproximada)', 1, '2026-11-10', ?)",
            (json.dumps(data),),
        )
        conn.commit()
    finally:
        conn.close()
    return data


def test_constants():
    assert market.LIVE_ID == "MKT-LIVE"
    assert market.SOURCE_KEYS == (
        "curve:TIIE-F", "curve:SOFR", "spot", "surface", "hw", "factor_vols", "factor_corr"
    )
    assert market.SOURCE_KINDS == ("live", "proxy", "synthetic", "mixed")
    assert set(market.DEFAULT_SOURCES) == set(market.SOURCE_KEYS)
    assert all(
        s == {
            "kind": "synthetic",
            "label": "Sintético (inventado para demostración)",
            "as_of": None,
        }
        for s in market.DEFAULT_SOURCES.values()
    )


def test_demo_list_has_seven_synthetic_sources_and_no_read_only(client):
    (item,) = client.get("/api/market/snapshots").get_json()["snapshots"]
    assert item["id"] == "MX-DEMO"
    assert item["data_quality"] == "synthetic"
    assert item["synthetic"] is True
    assert "read_only" not in item
    assert set(item["sources"]) == set(market.SOURCE_KEYS)
    assert all(s["kind"] == "synthetic" and s["as_of"] is None for s in item["sources"].values())


def test_demo_detail_has_sources_and_is_editable(client):
    s = client.get(DEMO).get_json()
    assert s["data_quality"] == "synthetic" and s["synthetic"] is True
    assert s["read_only"] is False
    assert set(s["sources"]) == set(market.SOURCE_KEYS)
    assert all(v["kind"] == "synthetic" and v["as_of"] is None for v in s["sources"].values())


def test_demo_rest_of_payload_equals_demo_data(client):
    s = client.get(DEMO).get_json()
    expected = seed_market.demo_data()
    for key in ("quotes", "fx", "vol_surface", "hw", "factors"):
        assert s[key] == expected[key], key


def test_put_on_demo_still_works_and_carries_provenance(client):
    base = client.get(DEMO).get_json()
    q = base["quotes"][0]
    r = client.put(DEMO, json={"quotes": [{"id": q["id"], "rate": q["rate"] + 0.001}]})
    assert r.status_code == 200
    body = r.get_json()
    assert body["quotes"][0]["rate"] == pytest.approx(q["rate"] + 0.001)
    assert body["read_only"] is False
    assert body["data_quality"] == "synthetic"
    assert set(body["sources"]) == set(market.SOURCE_KEYS)


@pytest.mark.parametrize(
    "sources, expected",
    [
        (_sources(), "synthetic"),
        (_sources(**{
            "curve__TIIE-F": "live", "curve__SOFR": "proxy", "spot": "live",
            "surface": "live", "hw": "proxy", "factor_vols": "live", "factor_corr": "live",
        }), "live"),
        (_sources(**{
            "curve__TIIE-F": "proxy", "curve__SOFR": "proxy", "spot": "proxy",
            "surface": "proxy", "hw": "proxy", "factor_vols": "mixed", "factor_corr": "proxy",
        }), "mixed"),
        (_sources(spot="live"), "mixed"),
        (_sources(curve__SOFR="proxy", spot="live", factor_vols="mixed"), "mixed"),
    ],
)
def test_data_quality_rule(sources, expected):
    assert market.data_quality(sources) == expected


def test_sources_of_defaults_when_missing():
    assert market.sources_of({"quotes": []}) == market.DEFAULT_SOURCES
    own = _sources(spot="live")
    assert market.sources_of({"sources": own}) is own


def test_live_snapshot_returns_stored_sources_and_read_only(client, tmp_path):
    sources = _sources(curve__SOFR="proxy", spot="live", factor_vols="mixed")
    _insert_live(tmp_path / "t.db", sources)

    detail = client.get(LIVE).get_json()
    assert detail["sources"] == sources
    assert detail["read_only"] is True
    assert detail["data_quality"] == "mixed"
    assert detail["synthetic"] is True

    listed = {s["id"]: s for s in client.get("/api/market/snapshots").get_json()["snapshots"]}
    assert listed["MKT-LIVE"]["sources"] == sources
    assert listed["MKT-LIVE"]["data_quality"] == "mixed"
    assert "read_only" not in listed["MKT-LIVE"]
    assert listed["MX-DEMO"]["data_quality"] == "synthetic"
    # `MKT-LIVE` ordena antes que `MX-DEMO`
    assert [s["id"] for s in client.get("/api/market/snapshots").get_json()["snapshots"]] == [
        "MKT-LIVE", "MX-DEMO"
    ]


@pytest.mark.parametrize(
    "body",
    [
        {"quotes": [{"id": "SOFR:1Y", "rate": 0.04}], "spot": 19.0},
        {"spot": 19.0},
        {"quotes": [{"id": "NOPE", "rate": 0.04}]},
        {"quotes": "no es lista"},
        {"spot": -5},
        {},
    ],
)
def test_put_on_live_is_409_and_writes_nothing(client, tmp_path, body):
    _insert_live(tmp_path / "t.db")
    conn = db.connect(tmp_path / "t.db")
    before = conn.execute("SELECT * FROM snapshots WHERE id = 'MKT-LIVE'").fetchone()
    before = tuple(before)
    conn.close()

    r = client.put(LIVE, json=body)
    assert r.status_code == 409
    assert r.get_json() == {"error": LIVE_PUT_ERROR, "field": None}

    conn = db.connect(tmp_path / "t.db")
    after = tuple(conn.execute("SELECT * FROM snapshots WHERE id = 'MKT-LIVE'").fetchone())
    conn.close()
    assert after == before


def test_put_on_missing_live_is_404_not_409(client):
    r = client.put(LIVE, json={"spot": 19.0})
    assert r.status_code == 404
    assert r.get_json()["field"] == "snapshot"


def test_demo_valuation_total_unchanged(client):
    """R7: la valuación de MX-DEMO no cambia con la procedencia."""
    v = client.get("/api/portfolio/valuation?snapshot=MX-DEMO").get_json()
    assert len(v["rows"]) == 16  # 7 originales + 9 del corte 9
    assert all(r["error"] is None for r in v["rows"])
    # el valor fijado es el de las 7 originales: las 9 del corte 9 se suman aparte
    assert sum(r["pv_mxn"] for r in v["rows"][:7]) == pytest.approx(1536785.72, rel=1e-6)
