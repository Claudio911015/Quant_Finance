"""Corte 6, T3: contrato de conjuntos de escenarios registrado; lo que falta responde 501 hasta que T8 lo implemente."""


def test_contract_stub(client):
    r = client.get("/api/scenario-sets")
    assert r.status_code == 501
    assert r.is_json and "error" in r.get_json()
