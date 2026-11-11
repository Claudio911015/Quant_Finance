"""Corte 6, T3: contrato de P&L explicado registrado; lo que falta responde 501 hasta que T4 lo implemente."""


def test_contract_stub(client):
    r = client.get("/api/pnl/explain?from=MX-DEMO&to=MX-DEMO")
    assert r.status_code == 501
    assert r.is_json and "error" in r.get_json()
