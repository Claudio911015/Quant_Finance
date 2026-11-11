"""Corte 6, T3: contrato de límites registrado; lo que falta responde 501 hasta que T6 lo implemente."""


def test_contract_stub(client):
    r = client.get("/api/limits")
    assert r.status_code == 501
    assert r.is_json and "error" in r.get_json()
