"""Rodar un snapshot (`POST /api/market/<id>/roll`): copia editable y contrato de errores (R13)."""
import pytest

from desk.api import db

SRC = "/api/market/snapshots/MX-DEMO"
ROLL = "/api/market/MX-DEMO/roll"


def _error(resp, status, field):
    assert resp.status_code == status
    body = resp.get_json()
    assert set(body) == {"error", "field"}
    assert body["error"]
    assert body["field"] == field


def test_roll_creates_editable_copy_with_same_quotes_and_sources(client):
    origin = client.get(SRC).get_json()
    r = client.post(ROLL, json={"id": "D1", "as_of": "2026-12-08"})
    assert r.status_code == 201
    new = r.get_json()
    assert new["id"] == "D1"
    assert new["as_of"] == "2026-12-08"
    assert new["label"] == origin["label"] + " · rodado al 2026-12-08"
    assert new["quotes"] == origin["quotes"]
    assert new["sources"] == origin["sources"]
    assert new["synthetic"] == origin["synthetic"]
    assert new["read_only"] is False
    assert client.get(SRC).get_json()["as_of"] == origin["as_of"]  # el origen no cambia


def test_put_on_rolled_snapshot_works(client):
    client.post(ROLL, json={"id": "D1", "as_of": "2026-12-08"})
    r = client.put("/api/market/snapshots/D1", json={"spot": 18.5})
    assert r.status_code == 200
    assert r.get_json()["fx"]["spot"] == 18.5


def test_repeated_id_is_409(client):
    client.post(ROLL, json={"id": "D1", "as_of": "2026-12-08"})
    _error(client.post(ROLL, json={"id": "D1", "as_of": "2026-12-09"}), 409, "id")


@pytest.mark.parametrize("bad_id", ["MKT-LIVE", "D 1", " D1", "D1 ", "", "x" * 41, 7])
def test_invalid_id_is_400(client, bad_id):
    _error(client.post(ROLL, json={"id": bad_id, "as_of": "2026-12-08"}), 400, "id")


def test_invalid_as_of_is_400(client):
    _error(client.post(ROLL, json={"id": "D1", "as_of": "2026-13-01"}), 400, "as_of")


def test_unknown_source_is_404(client):
    _error(
        client.post("/api/market/NO-EXISTE/roll", json={"id": "D1", "as_of": "2026-12-08"}),
        404,
        "snapshot",
    )


def test_rolling_mkt_live_gives_editable_copy(app, client):
    conn = db.connect(app.config["DESK_DB"])
    conn.execute(
        "INSERT INTO snapshots (id, label, synthetic, as_of, data) "
        "SELECT 'MKT-LIVE', label, synthetic, as_of, data FROM snapshots WHERE id = 'MX-DEMO'"
    )
    conn.commit()
    conn.close()
    live = "/api/market/snapshots/MKT-LIVE"
    assert client.get(live).get_json()["read_only"] is True
    assert client.put(live, json={"spot": 18.5}).status_code == 409

    r = client.post("/api/market/MKT-LIVE/roll", json={"id": "D2", "as_of": "2026-12-08"})
    assert r.status_code == 201
    assert client.put(live, json={"spot": 18.5}).status_code == 409
    assert client.put("/api/market/snapshots/D2", json={"spot": 18.5}).status_code == 200
