"""Corte 6, T3: contrato de VaR histórico registrado; lo que falta responde 501 hasta que T5 lo implemente."""


def test_contract_stub(client):
    r = client.post("/api/risk/var", json={"snapshot": "MX-DEMO", "horizon_days": 1, "confidence": 0.99, "method": "historical"})
    assert r.status_code == 501
    assert r.is_json and "error" in r.get_json()
