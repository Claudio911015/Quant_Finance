"""Exposición por contraparte (EE/PFE), CVA informativo y parámetros de crédito (cortes 6 y 9).

La exposición y el CVA vienen del motor multimoneda de `risk/xva.py` (`qfxva.ExposureEngine`), el mismo de
`GET /api/xva`: aquí solo se les da la forma del contrato de `GET /api/credit/exposure`. Un conjunto de
compensación por contraparte, con swaps de tasa (MXN y USD) y cross currency swaps compensados entre monedas;
cap/floor, forwards, opciones y bonos se listan en `excluded`. Aquí no hay fórmulas: Python solo reparte los
campos.

El motor valúa cada operación con exactamente los términos del desk (los de `valuation.value_trade`), así que
el valor en t = 0 es el PV del desk y no hay escalón en el primer mes: EE(0) y PFE(0) son max(PV neto, 0) y los
puntos mensuales siguientes parten de ahí. Ya no hay tasa fija efectiva calibrada ni swaps de pagos diarios
(los parches que el corte 6 necesitaba para el motor de swaps frescos). `EE` y `PFE` son los perfiles sin
descontar (los que se comparan contra límites); el CVA descuenta con la cuenta bancaria MXN simulada.

Crédito: la curva de CDS de la contraparte (`credit_source: "curve"`) o, sin ella, la intensidad plana de
`counterparty_credit` o el supuesto declarado 1 % / 40 % (`credit_source: "flat"`; `assumed` distingue el
supuesto). `hazard_rate` informa la intensidad media a 5 años, −ln S(5)/5, de la curva que se usó.
`counterparty_credit` es solo de inserción: cambiar parámetros es insertar una fila; la vigente es la de mayor
`id`. Los parámetros de simulación (trayectorias, semilla, percentil) son los de `GET /api/xva/params`.

`risk/xva.py` importa este módulo (usa sus parámetros y su malla mensual), por eso `exposure` importa `xva`
dentro de la función: arriba cerraría un ciclo. Las escrituras no hacen commit: lo hace la ruta.
"""
import calendar
import sqlite3
from datetime import date
from typing import Any, Dict, List

from desk.api.db import now_iso
from desk.api.errors import ApiError
from desk.api.validation import number, text

DEFAULT_HAZARD, DEFAULT_RECOVERY = 0.01, 0.40
CVA_NOTICE = "CVA informativo: no entra al PV ni a la contabilidad de coberturas"
ASSUMED_NOTE = "Supuesto: probabilidad de incumplimiento 1 % anual y recuperación 40 % (sin parámetros capturados)"
HAZARD_YEARS = 5.0  # plazo de la intensidad media que informa `hazard_rate`


# ------------------------------------------------------------------ parámetros

def _history(conn: sqlite3.Connection) -> Dict[int, List[Dict[str, Any]]]:
    """Filas guardadas por `counterparty_id`, de la más nueva a la más vieja."""
    out = {}  # type: Dict[int, List[Dict[str, Any]]]
    for r in conn.execute(
        "SELECT id, counterparty_id, hazard_rate, recovery, as_of, created_at"
        " FROM counterparty_credit ORDER BY id DESC"
    ):
        out.setdefault(r["counterparty_id"], []).append(
            {
                "hazard_rate": r["hazard_rate"],
                "recovery": r["recovery"],
                "as_of": r["as_of"],
                "created_at": r["created_at"],
            }
        )
    return out


def _params_row(name: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if rows:
        cur = rows[0]
        hazard, recovery, as_of, assumed = cur["hazard_rate"], cur["recovery"], cur["as_of"], False
    else:
        hazard, recovery, as_of, assumed = DEFAULT_HAZARD, DEFAULT_RECOVERY, None, True
    return {
        "counterparty": name,
        "hazard_rate": float(hazard),
        "recovery": float(recovery),
        "as_of": as_of,
        "assumed": assumed,
        "history": rows,
    }


def list_params(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Parámetros vigentes de todas las contrapartes, por nombre, con su historia (más nueva primero)."""
    hist = _history(conn)
    return [
        _params_row(r["name"], hist.get(r["id"], []))
        for r in conn.execute("SELECT id, name FROM counterparties ORDER BY name")
    ]


def set_params(conn: sqlite3.Connection, body: Dict[str, Any]) -> Dict[str, Any]:
    """Inserta una fila de parámetros para la contraparte y devuelve su elemento de `list_params` (sin commit)."""
    name = text(body, "counterparty")
    hazard = number(body, "hazard_rate", ge=0, le=1)
    recovery = number(body, "recovery", ge=0, lt=1)
    row = conn.execute("SELECT id FROM counterparties WHERE name = ?", (name,)).fetchone()
    if row is None:
        raise ApiError(404, "Contraparte inexistente: %s" % name, "counterparty")
    now = now_iso()
    conn.execute(
        "INSERT INTO counterparty_credit (counterparty_id, hazard_rate, recovery, as_of, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (row["id"], hazard, recovery, now[:10], now),  # `as_of` = fecha UTC de hoy
    )
    return _params_row(name, _history(conn).get(row["id"], []))


# ------------------------------------------------------------------ exposición y CVA

def _add_months(start: date, k: int) -> date:
    """`start` + `k` meses, mismo día; si el mes no lo tiene, su último día."""
    m = start.month - 1 + k
    year, month = start.year + m // 12, m % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def _grid(as_of: date, last_maturity: date) -> List[date]:
    """Fechas mensuales `as_of + k meses`, `k = 1..K` con `K` el primero cuya fecha es >= `last_maturity`."""
    out = []  # type: List[date]
    k = 1
    while True:
        d = _add_months(as_of, k)
        out.append(d)
        if d >= last_maturity:
            return out
        k += 1


def _counterparty(cp: Dict[str, Any], curve: Any) -> Dict[str, Any]:
    """Elemento de `counterparties` del contrato de crédito a partir del de `GET /api/xva` y su curva."""
    from desk.api.risk import xva

    info = cp["credit"]
    ids = [i["id"] for i in cp["included"]]
    return {
        "counterparty": cp["counterparty"],
        "hazard_rate": xva.average_hazard(curve, HAZARD_YEARS),
        "recovery": info["recovery"],
        "assumed": info["assumed"],
        "assumed_note": info["note"] if info["assumed"] else None,
        "credit_source": "curve" if info["kind"] == "curve" else "flat",
        "pv_mxn": cp["pv_mxn"],
        "cva_mxn": cp["cva_mxn"],
        "netting_sets": [{"curve": "multimoneda", "trades": ids, "pv_mxn": cp["pv_mxn"], "cva_mxn": cp["cva_mxn"]}]
        if ids
        else [],
        "profile": [
            {"date": p["date"], "t": p["t"], "ee_mxn": p["epe_mxn"], "pfe_mxn": p["pfe_mxn"]} for p in cp["profile"]
        ],
        "excluded": cp["excluded"],
    }


def exposure(conn: sqlite3.Connection, snapshot_id: str) -> Dict[str, Any]:
    """Cuerpo de `GET /api/credit/exposure`: perfil EE/PFE mensual y CVA de cada contraparte con operaciones vivas,
    calculados con el motor multimoneda de `risk/xva.py` (mismas trayectorias, parámetros y CVA que `GET /api/xva`)."""
    from desk.api.risk import xva  # dentro de la función: `xva` importa este módulo

    body, curves = xva.compute_detailed(conn, snapshot_id)
    counterparties = [_counterparty(cp, curves[cp["counterparty"]]) for cp in body["counterparties"]]
    return {
        "snapshot": snapshot_id,
        "as_of": body["as_of"],
        "n_paths": body["params"]["n_paths"],
        "seed": body["params"]["seed"],
        "pfe_quantile": body["params"]["pfe_quantile"],
        "notice": CVA_NOTICE,
        "counterparties": counterparties,
        "excluded": [dict(counterparty=cp["counterparty"], **x) for cp in counterparties for x in cp["excluded"]],
        "warnings": body["warnings"],
    }
