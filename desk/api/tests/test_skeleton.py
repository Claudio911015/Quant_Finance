def _assert_error(resp, status, field):
    assert resp.status_code == status
    body = resp.get_json()
    assert set(body) == {"error", "field"}
    assert isinstance(body["error"], str) and body["error"]
    assert body["field"] == field


def test_unknown_route_is_json_404(client):
    _assert_error(client.get("/api/no-existe"), 404, None)


def test_unknown_product_is_404_on_product(client):
    resp = client.post("/api/price/inexistente", json={"snapshot": "MX-DEMO"})
    _assert_error(resp, 404, "product")


def test_malformed_json_on_trades_is_400(client):
    resp = client.post(
        "/api/trades", data="{no es json", content_type="application/json"
    )
    _assert_error(resp, 400, None)


def test_qfpy_importable_via_desk():
    from desk.api.qf import qfpy

    assert hasattr(qfpy, "YieldCurve")
