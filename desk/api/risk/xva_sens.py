"""Sensibilidades del XVA por diferenciación adjunta (corte 12): cuerpo de `GET /api/xva/sensitivities`.

Sin fórmulas financieras: `xva._counterparty` da el XVA de referencia (los mismos parámetros, malla y trayectorias
que `GET /api/xva`), `qfxva` da las derivadas por unidad de insumo y aquí se pasan a MXN por pb, por 1 % del spot o
por punto, y se componen con el jacobiano del bootstrap de CDS. Derivadas parciales: nada se recalibra.
"""
import sqlite3
import time
from typing import Any, Callable, Dict, List

from desk.api import fixings as fixing_store
from desk.api import market
from desk.api.errors import ApiError
from desk.api.risk import credit_curves, xva

BP = 1e-4
CDS_BUMP = 1e-6  # 0.01 pb en decimal, para el jacobiano cotización -> intensidades
KEYS = ("cva", "dva", "fva", "total")
PARTIAL_NOTE = (
    "Derivadas parciales: al mover un pilar no se recalibran la curva MXN-USD ni las curvas de crédito "
    "(el bootstrap de CDS descuenta con TIIE-F)"
)
UNITS = {
    "curves": "MXN por pb", "fx": "MXN por 1 % del spot", "funding": "MXN por pb",
    "vols": "MXN por punto (vol USDMXN), por pb de vol normal (σ Hull-White), por 0.01 (a)",
    "cds": "MXN por pb (de cotización de CDS o, sin curva, de intensidad)",
}
VOLS = (  # (atributo del binding, rótulo, escala): vol USDMXN por 1 punto, σ por 1 pb de vol normal, a por 0.01
    ("fx_vol", "Volatilidad USDMXN", 0.01), ("sigma_mxn", "σ Hull-White TIIE-F", BP),
    ("a_mxn", "a Hull-White TIIE-F", 0.01), ("sigma_usd", "σ Hull-White SOFR", BP), ("a_usd", "a Hull-White SOFR", 0.01),
)


def _row(sens: Any, pick: Callable[[Any], float], scale: float) -> Dict[str, float]:
    """Fila `{cva, dva, fva, total}` de `pick(derivadas de cada medida) * scale`; `total = cva − dva + fva`."""
    cva, dva, fva = (pick(g) * scale for g in (sens.cva, sens.dva, sens.fva))
    return {"cva": cva, "dva": dva, "fva": fva, "total": cva - dva + fva}


def _credit(conn: sqlite3.Connection, mkt: Any, sens: Any, attr: str, info: Dict[str, Any], entity: str) -> Dict[str, Any]:
    """Crédito de una entidad: intensidad por tramo y, con curva de CDS, la sensibilidad a cada cotización
    (Σᵢ ∂X/∂λᵢ · ∂λᵢ/∂sₖ; el jacobiano sale de repreciar el bootstrap con la cotización k movida)."""
    if info["kind"] != "curve":
        single = {"to_years": None, **_row(sens, lambda g: getattr(g, attr)[0], BP)}
        return {"kind": info["kind"], "cds": [], "hazards": [single]}
    row = credit_curves.current(conn)[entity]
    quotes = row["quotes"]

    def hazards(k: int, bump: float) -> List[float]:
        moved = [dict(q, spread=q["spread"] + (bump if j == k else 0.0)) for j, q in enumerate(quotes)]
        return credit_curves.build_curve(xva._qfxva(), dict(row, quotes=moved), mkt).hazards()

    jac = [
        [(u - d) / (2 * CDS_BUMP) for u, d in zip(hazards(k, CDS_BUMP), hazards(k, -CDS_BUMP))]
        for k in range(len(quotes))
    ]
    dot = lambda g, k: sum(a * b for a, b in zip(getattr(g, attr), jac[k]))  # noqa: E731
    return {
        "kind": "curve",
        "cds": [{"tenor": "%gY" % q["tenor_years"], **_row(sens, lambda g: dot(g, k), BP)} for k, q in enumerate(quotes)],
        "hazards": [
            {"to_years": q["tenor_years"], **_row(sens, lambda g: getattr(g, attr)[i], BP)} for i, q in enumerate(quotes)
        ],
    }


def _curves(sens: Any, mkt: Any) -> List[Dict[str, Any]]:
    out = []  # type: List[Dict[str, Any]]
    for curve, attr in (("TIIE-F", "tiie"), ("SOFR", "sofr"), (market.CSA_CURVE, "mxn_usd")):
        if getattr(sens.cva, attr):
            pillars = [
                {"label": p["label"], "days": p["days"], **_row(sens, lambda g: getattr(g, attr)[i], BP)}
                for i, p in enumerate(mkt.pillars[curve])
            ]
            out.append({"curve": curve, "pillars": pillars, "dv01": {k: sum(p[k] for p in pillars) for k in KEYS}})
    return out


def compute(conn: sqlite3.Connection, snapshot_id: str, name: str) -> Dict[str, Any]:
    """Cuerpo de `GET /api/xva/sensitivities` (404 `snapshot`/`counterparty`, 501 sin XAD, `empty_reason` sin swaps)."""
    mkt = market.load_context(conn, snapshot_id)
    if conn.execute("SELECT 1 FROM counterparties WHERE name = ?", (name,)).fetchone() is None:
        raise ApiError(404, "Contraparte inexistente: %s" % name, "counterparty")
    if not xva._qfxva().HAS_XAD:
        raise ApiError(501, "Sensibilidades no disponibles: el motor se compiló sin XAD (QF_WITH_XAD=OFF)")
    fixings, params = fixing_store.load_all(conn), xva.load_params(conn)
    model, _, assumptions = xva.model_from_snapshot(mkt)
    own_curve, own_recovery, own_info = xva.own_credit(conn, mkt)
    trades = xva.live_by_counterparty(conn, mkt).get(name, [])
    t0 = time.perf_counter()
    cp, warnings, cp_curve = xva._counterparty(conn, mkt, model, params, fixings, (own_curve, own_recovery), name, trades)
    valuation_s = time.perf_counter() - t0
    zero = {k: 0.0 for k in KEYS}
    body = {
        "snapshot": snapshot_id, "as_of": mkt.as_of.isoformat(), "counterparty": name, "notice": xva.NOTICE,
        "method": "Diferenciación adjunta (XAD 2.2.0), cinta por trayectoria, derivadas trayectoria a trayectoria",
        "cds_jacobian": "Reprecio del bootstrap de CDS (diferencia central de 0.01 pb)",
        "params": params, "paths": params["n_paths"], "seed": params["seed"], "elapsed_s": 0.0,
        "valuation_elapsed_s": valuation_s, "n_inputs": 0, "bump_cost_estimate_s": 0.0,
        "xva": {k: cp[k] for k in ("cva_mxn", "dva_mxn", "fva_mxn", "total_mxn")}, "units": UNITS, "curves": [],
        "fx": dict(zero, label="USDMXN spot"), "vols": [], "funding": dict(zero),
        "credit": {
            side: {"kind": info["kind"], "cds": [], "hazards": []}
            for side, info in (("counterparty", cp["credit"]), ("own", own_info))
        },
        "empty_reason": "La contraparte no tiene swaps de tasa ni cross currency swaps vivos: no hay sensibilidades del XVA",
        "assumptions": assumptions + [xva.INTEGRATION_NOTE, PARTIAL_NOTE], "warnings": warnings,
    }  # type: Dict[str, Any]
    if not cp["included"]:
        return body
    spec = xva.build_set(trades, mkt, fixings)[0]
    days = xva.integration_days(xva.report_days(mkt.as_of, xva._last_maturity(trades, cp["included"])), spec)
    t0 = time.perf_counter()
    sens = xva.engine(mkt, model, params, days).xva_sensitivities(
        spec, cp_curve, 1.0 - cp["credit"]["recovery"], own_curve, 1.0 - own_recovery, params["funding_spread"]
    )
    elapsed, g = time.perf_counter() - t0, sens.cva
    n_inputs = len(g.tiie) + len(g.sofr) + len(g.mxn_usd) + len(g.counterparty_hazard) + len(g.own_hazard) + 7
    body.update(
        elapsed_s=elapsed, n_inputs=n_inputs, bump_cost_estimate_s=2 * n_inputs * valuation_s, empty_reason=None,
        curves=_curves(sens, mkt), fx=dict(body["fx"], **_row(sens, lambda d: d.spot, 0.01 * mkt.spot)),
        vols=[{"param": p, "label": label, **_row(sens, lambda d: getattr(d, p), scale)} for p, label, scale in VOLS],
        funding=_row(sens, lambda d: d.funding_spread, BP),
        credit={
            "counterparty": _credit(conn, mkt, sens, "counterparty_hazard", cp["credit"], name),
            "own": _credit(conn, mkt, sens, "own_hazard", own_info, credit_curves.OWN),
        },
    )
    return body
