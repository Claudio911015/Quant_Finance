"""P&L explicado por cascada entre dos snapshots (corte 6, D1).

El P&L oficial por operación es el de `pnl.compute_pnl`. Se reparte rodando el mercado de `from` a
la fecha de `to` (`H0`) y sustituyendo, en orden y acumulando, las cotizaciones de cada curva, el
tipo de cambio y la volatilidad por los de `to`. Cada paso es la diferencia entre dos
valuaciones consecutivas, así que la suma telescopa al P&L oficial: el residuo es ruido numérico.
Aquí solo se suma y resta; toda valuación sale de `valuation.value_trade` y `settlement`.
"""
import copy
import json
import sqlite3
from datetime import date
from typing import Any, Dict, List

from desk.api import fixings as fixing_store
from desk.api import market, pnl, portfolio, settlement, valuation
from desk.api.validation import NON_FINITE_MESSAGE, has_non_finite

# "TIIE-F" primero y luego las demás curvas de `market.CURVES` en orden alfabético.
_CURVE_ORDER = ["TIIE-F"] + sorted(c for c in market.CURVES if c != "TIIE-F")
# La curva `MXN-USD` (corte 3) es dependiente: no trae cotizaciones propias en `quotes`, sino los puntos
# forward y la base de `fx_forwards`/`xccy_basis`. Tiene su propio paso, después de las curvas de las que
# depende y antes del tipo de cambio; sin él, un cambio de esos puntos acabaría en "Eventos".
CSA_KEY = "curve:%s" % market.CSA_CURVE
CSA_QUOTES = ("fx_forwards", "xccy_basis")

STEPS = (
    [("carry", "Paso del tiempo y liquidaciones")]
    + [("curve:%s" % c, "Tasas %s" % c) for c in _CURVE_ORDER]
    + [
        (CSA_KEY, "Puntos forward y base (%s)" % market.CSA_CURVE),
        ("fx", "Tipo de cambio"),
        ("vol", "Volatilidad"),
        ("new_trades", "Operaciones nuevas"),
        ("events", "Eventos"),
        ("residual", "Residuo"),
    ]
)


_CURVE_KEYS = [key for key, _ in STEPS if key.startswith("curve:") and key != CSA_KEY]


def _replace_curve(quotes: List[Dict[str, Any]], curve: str, new: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """`quotes` con las de `curve` sustituidas por `new` (copias), en la posición de la primera."""
    out = []  # type: List[Dict[str, Any]]
    placed = False
    for q in quotes:
        if q["curve"] != curve:
            out.append(q)
        elif not placed:
            out.extend(copy.deepcopy(new))
            placed = True
    if not placed:
        out.extend(copy.deepcopy(new))
    return out


def _hybrid_contexts(conn: sqlite3.Connection, from_id: str, to_id: str, to_as_of: str) -> List[Any]:
    """Contextos `[H0, H1 (+TIIE-F), …, +cada curva, +puntos MXN-USD, +fx, +vol/hw]`, todos con `as_of = to.as_of`.

    Si un paso no cambia ningún dato respecto al anterior se reutiliza el mismo objeto: así su
    diferencia de valuación es 0.0 exacto y no se valúa dos veces.
    """
    d_from = json.loads(market._fetch(conn, from_id)["data"])
    d_to = json.loads(market._fetch(conn, to_id)["data"])
    label = "%s→%s" % (from_id, to_id)
    data = copy.deepcopy(d_from)
    stages = [copy.deepcopy(data)]
    for key in _CURVE_KEYS:
        curve = key.split(":", 1)[1]
        data["quotes"] = _replace_curve(data["quotes"], curve, [q for q in d_to["quotes"] if q["curve"] == curve])
        stages.append(copy.deepcopy(data))
    for name in CSA_QUOTES:
        if name in d_to:
            data[name] = copy.deepcopy(d_to[name])
        else:
            data.pop(name, None)
    stages.append(copy.deepcopy(data))
    data["fx"] = copy.deepcopy(d_to["fx"])
    stages.append(copy.deepcopy(data))
    data["vol_surface"] = copy.deepcopy(d_to["vol_surface"])
    data["hw"] = copy.deepcopy(d_to["hw"])
    stages.append(copy.deepcopy(data))
    contexts = []  # type: List[Any]
    for i, stage in enumerate(stages):
        if i and stage == stages[i - 1]:
            contexts.append(contexts[-1])
        else:
            contexts.append(market._build_context(label, to_as_of, stage))
    return contexts


def _components(
    trade: Dict[str, Any],
    row: Dict[str, Any],
    contexts: List[Any],
    fixings: Any,
    from_as_of: date,
    mkt_to: Any,
) -> Dict[str, float]:
    """Componentes de una operación (sin `residual`); lanza si la cascada no se puede valuar."""
    comps = {key: 0.0 for key, _ in STEPS}
    if trade["trade_date"] > from_as_of:  # pactada en la ventana: entra entera
        comps["new_trades"] = row["pnl"]
        return comps
    t0 = dict(trade, events=[e for e in trade["events"] if e["event_date"] <= from_as_of])
    values = []  # type: List[float]
    for i, ctx in enumerate(contexts):
        if i and ctx is contexts[i - 1]:
            values.append(values[-1])
        else:
            values.append(valuation.value_trade(t0, ctx, fixings)["pv_mxn"])
    flows, _ = settlement.settled_flows(t0, fixings, from_as_of, mkt_to.as_of, mkt_to.spot, mkt_to)
    s0 = sum((f["amount_mxn"] for f in flows), 0.0)
    comps["carry"] = values[0] - row["pv_from"] + s0
    for key, before, after in zip(_CURVE_KEYS + [CSA_KEY, "fx", "vol"], values, values[1:]):
        comps[key] = after - before
    comps["events"] = (row["pv_to"] + row["settled"]) - (values[-1] + s0)
    if has_non_finite(list(comps.values())):
        raise ValueError(NON_FINITE_MESSAGE)
    return comps


def explain_pnl(conn: sqlite3.Connection, from_id: str, to_id: str) -> Dict[str, Any]:
    """Cuerpo de `GET /api/pnl/explain`: el P&L de `compute_pnl` repartido en los pasos de `STEPS`.

    Por fila y en total, la suma de los componentes es el P&L (el residuo cierra la cuenta). Una fila
    con `error` en `compute_pnl` lleva `pnl` y `components` nulos y no suma; si la cascada de una
    operación con P&L válido falla, todo su P&L va al residuo y `explain_error` dice por qué.

    @raise ApiError 404 `snapshot` si un snapshot no existe; 400 `to` si `from` es posterior.
    """
    res = pnl.compute_pnl(conn, from_id, to_id)  # valida los snapshots y da el P&L oficial
    from_as_of = date.fromisoformat(res["from"]["as_of"])
    mkt_to = market.load_context(conn, to_id)
    fixings = fixing_store.load_all(conn)
    trades = {t["id"]: t for t in portfolio.load_trades(conn)}
    contexts = _hybrid_contexts(conn, from_id, to_id, res["to"]["as_of"])
    totals = {key: 0.0 for key, _ in STEPS}
    rows = []
    for src in res["rows"]:
        out = {
            "id": src["id"],
            "product": src["product"],
            "counterparty": src["counterparty"],
            "pnl": src["pnl"],
            "components": None,
            "error": src["error"],
            "explain_error": None,
            "warnings": src["warnings"],
        }  # type: Dict[str, Any]
        rows.append(out)
        if src["error"] is not None:
            continue
        try:
            comps = _components(trades[src["id"]], src, contexts, fixings, from_as_of, mkt_to)
        except Exception as e:  # la cascada de una operación nunca tumba el resto
            comps = {key: 0.0 for key, _ in STEPS}
            out["explain_error"] = str(e)
        comps["residual"] = src["pnl"] - sum(v for k, v in comps.items() if k != "residual")
        out["components"] = comps
        for key, value in comps.items():
            totals[key] += value
    return {
        "from": res["from"],
        "to": res["to"],
        "steps": [{"key": key, "label": label} for key, label in STEPS],
        "totals": {"pnl": res["total_mxn"], "components": totals},
        "rows": rows,
    }
