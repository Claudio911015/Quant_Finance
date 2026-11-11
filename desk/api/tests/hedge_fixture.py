"""Ayudas compartidas de las pruebas de coberturas (sin tests; no importa nada de los módulos de coberturas).

Las fechas se aceptan como `date` o como texto ISO.
"""
from datetime import date, timedelta
from typing import Any, Dict, Union

import pytest

DOC = {
    "risk_management_objective": "Fijar el costo del crédito sindicado",
    "hedged_risk": "Variabilidad de los intereses por TIIE de Fondeo",
    "effectiveness_method": "Términos críticos y escenarios con derivado hipotético",
    "ineffectiveness_sources": "Diferencias de fechas y nocional; riesgo de crédito no medido",
}

Day = Union[date, str]

# Reloj de las pruebas de coberturas: el alta es el mismo día de la designación por defecto (MX-DEMO, 2026-11-10).
# Sin esto el aviso `designation_backdated` dependería de la fecha real en que corre la suite.
CLOCK = "2026-11-10T18:00:00+00:00"


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    """Fija `hedges.now_iso` en `CLOCK`; cada módulo de pruebas de coberturas lo importa (autouse).

    Una prueba que necesite otra fecha la cambia con `monkeypatch.setattr("desk.api.hedges.now_iso", ...)`.
    """
    monkeypatch.setattr("desk.api.hedges.now_iso", lambda: CLOCK)
    return CLOCK


def _iso(day: Day) -> str:
    return day.isoformat() if isinstance(day, date) else day


def _snapshot_as_of(client, snapshot: str) -> date:
    r = client.get("/api/market/snapshots/%s" % snapshot)
    assert r.status_code == 200, r.get_json()
    return date.fromisoformat(r.get_json()["as_of"])


def roll(client, source: str, new_id: str, days: int) -> str:
    """Rueda `source` a un snapshot `new_id` con `as_of = as_of(source) + days`; devuelve ese `as_of` en ISO."""
    as_of = (_snapshot_as_of(client, source) + timedelta(days=days)).isoformat()
    r = client.post("/api/market/%s/roll" % source, json={"id": new_id, "as_of": as_of})
    assert r.status_code == 201, r.get_json()
    return as_of


def load_fixings(client, index: str, start: date, end: date, value: float) -> None:
    """Carga una fijación de `index` por día hábil en `[start, end)`."""
    lines = ["index,date,value"]
    day = start
    while day < end:
        if day.weekday() < 5:
            lines.append("%s,%s,%r" % (index, day.isoformat(), value))
        day += timedelta(days=1)
    r = client.post("/api/fixings/csv", json={"csv": "\n".join(lines)})
    assert r.status_code == 200, r.get_json()


def _book(client, body: Dict[str, Any]) -> Dict[str, Any]:
    r = client.post("/api/trades", json={"counterparty": "Banco Alfa (sintético)", **body})
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def par_irs(
    client, curve: str, notional: float, start: Day, maturity: Day, side: str = "payer",
    snapshot: str = "MX-DEMO",
) -> Dict[str, Any]:
    """Crea un `irs` sin `fixed_rate` (nace a la par en `snapshot`) y devuelve la operación."""
    return _book(
        client,
        {
            "product": "irs",
            "params": {"curve": curve, "side": side, "notional": notional, "periods": 1},
            "start_date": _iso(start),
            "maturity_date": _iso(maturity),
            "snapshot": snapshot,
        },
    )


def market_forward(
    client, side: str, notional_usd: float, maturity: Day, snapshot: str = "MX-DEMO"
) -> Dict[str, Any]:
    """Crea un `fx_forward` con strike = el forward de mercado en `snapshot` y devuelve la operación."""
    days = (date.fromisoformat(_iso(maturity)) - _snapshot_as_of(client, snapshot)).days
    params = {"side": side, "notional_usd": notional_usd, "days": days}
    r = client.post("/api/price/fx_forward", json={**params, "strike": 1.0, "snapshot": snapshot})
    assert r.status_code == 200, r.get_json()
    return _book(
        client,
        {
            "product": "fx_forward",
            "params": {**params, "strike": r.get_json()["risk"]["forward"]},
            "maturity_date": _iso(maturity),
            "snapshot": snapshot,
        },
    )


def designate(client, trade_id: int, item_kind: str, item_terms: Dict[str, Any], **overrides: Any):
    """`POST /api/hedges` con `snapshot="MX-DEMO"`, `hedge_type="cash_flow"`, `fraction=1.0` y `DOC`."""
    body = {
        "trade_id": trade_id,
        "snapshot": "MX-DEMO",
        "hedge_type": "cash_flow",
        "item_kind": item_kind,
        "item_terms": item_terms,
        "fraction": 1.0,
        "documentation": DOC,
    }
    body.update(overrides)
    return client.post("/api/hedges", json=body)
