"""Corte 6, T3: contrato de crédito registrado; lo que falta responde 501 hasta que T7 lo implemente."""


def test_contract_stub(client):
    r = client.get("/api/credit/params")
    assert r.status_code == 501
    assert r.is_json and "error" in r.get_json()
