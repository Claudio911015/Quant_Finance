"""Ayudas compartidas de las pruebas de colateral y curva MXN-USD (sin tests).

Las fechas se aceptan como `date` o como texto ISO.
"""
import json
import sqlite3
from datetime import date
from typing import Any, Dict, Optional, Union

Day = Union[date, str]


def _iso(day: Day) -> str:
    return day.isoformat() if isinstance(day, date) else day


def set_collateral(client, name: str, currency: str, effective_date: Day):
    """`PUT /api/counterparties/<id>` de la contraparte `name` (id buscado en `GET /api/counterparties`).

    Devuelve la respuesta tal cual, sin comprobar el status: las pruebas de errores la usan también.
    """
    listing = client.get("/api/counterparties")
    assert listing.status_code == 200, listing.get_json()
    ids = {c["name"]: c["id"] for c in listing.get_json()["counterparties"]}
    assert name in ids, "contraparte inexistente en la prueba: %s" % name
    return client.put(
        "/api/counterparties/%d" % ids[name],
        json={"collateral_currency": currency, "effective_date": _iso(effective_date)},
    )


def trade_with(
    client,
    product: str,
    counterparty: str,
    params: Dict[str, Any],
    start: Optional[Day] = None,
    maturity: Optional[Day] = None,
    snapshot: str = "MX-DEMO",
) -> Dict[str, Any]:
    """`POST /api/trades` (debe responder 201) y devuelve la operación creada."""
    body = {"product": product, "counterparty": counterparty, "params": params, "snapshot": snapshot}
    if start is not None:
        body["start_date"] = _iso(start)
    if maturity is not None:
        body["maturity_date"] = _iso(maturity)
    r = client.post("/api/trades", json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def strip_csa(app, snapshot_id: str) -> None:
    """Quita `fx_forwards` y `xccy_basis` del `data` del snapshot por SQL directo (caso sin curva MXN-USD)."""
    conn = sqlite3.connect(app.config["DESK_DB"])
    try:
        row = conn.execute("SELECT data FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
        assert row is not None, "snapshot inexistente en la prueba: %s" % snapshot_id
        data = json.loads(row[0])
        data.pop("fx_forwards", None)
        data.pop("xccy_basis", None)
        conn.execute("UPDATE snapshots SET data = ? WHERE id = ?", (json.dumps(data), snapshot_id))
        conn.commit()
    finally:
        conn.close()
