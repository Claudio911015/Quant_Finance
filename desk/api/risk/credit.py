"""Exposición por contraparte (EE/PFE), CVA informativo y parámetros de crédito (corte 6, D5).

Solo los `irs` se simulan (`qfxva.NettingSet` solo modela swaps de tasa vainilla): cap/floor, forwards
y opciones FX se listan en `excluded`. Hay un conjunto de compensación por `(contraparte, curva)`, sin
compensación entre monedas: el perfil mensual de la contraparte es la suma de sus conjuntos (cota
superior conservadora). Aquí no hay fórmulas nuevas: la exposición simulada y el CVA salen de `qfxva`.
`counterparty_credit` es solo de inserción: cambiar parámetros es insertar una fila; la
vigente es la de mayor `id`.

Coherencia con la valuación del desk (corrección de la auditoría del corte 6). El swap de `qfxva` es un
swap "fresco" de pagos regulares (ACT/365, un cupón por periodo, el último periodo incompleto se pierde
al revaluar a `t > 0`) y no el `OisSwap` del desk (ACT/360, calendario por fechas, periodo en curso con
su devengo). Alimentado con los términos crudos daba un valor inicial distinto del PV del desk, hasta de
signo contrario, y un escalón en el primer mes. Por eso cada swap se entrega al modelo (a) con pagos
diarios (`_MODEL_FREQUENCY`): aproxima la acumulación continua y reduce el error del último periodo
incompleto a un día de cupón, y (b) con una tasa fija efectiva calibrada para que el valor del modelo en
`t = 0` sea exactamente el PV del desk (`_effective_fixed_rate`; absorbe la base de días y el calendario).
El PV es lineal en la tasa fija, así que bastan dos valuaciones. Con esto el modelo vale el PV del desk en
`t = 0` exactamente (y EE(0), PFE(0) salen de ese PV), pero NO empieza ahí un instante después: en cuanto
`t > 0` el swap del modelo ya no incluye el cupón diario en curso, y el valor cae de golpe hasta un cupón
diario (`nocional × tasa / 365`) respecto del PV. En MX-DEMO es −86 mil MXN en Alfa (500 M de nocional,
0.017 % del nocional pero 9 % de su PV de −0.94 M), −36 mil en Beta y −1.6 mil en Gamma. Cada punto mensual
del perfil carga ese mismo orden de error. No se corrige: el calendario del swap vive en C++ y calibrar a
`t = 0+` solo movería el error de lugar.

EE(0) y PFE(0) son max(PV de la contraparte, 0): el valor de hoy sí compensa entre monedas. Los puntos
mensuales siguientes no (cada conjunto se simula por separado), así que en una contraparte con swaps en
dos monedas el primer punto mensual puede quedar por encima de EE(0): es la cota superior declarada.

Límite conocido: el modelo ve cada swap como uno fresco desde hoy hasta su vencimiento. Un swap que aún
no empieza (`start_date` posterior al `as_of`) queda igual de anclado a su PV en t = 0, pero su perfil
posterior es solo una aproximación.

`qfxva` se importa dentro de las funciones, después de `qfpy` (orden obligatorio: ambos registran el
mismo enum de C++ y `qfxva` lo reutiliza solo si `qfpy` ya está cargado), para que el backend arranque
aunque el módulo no esté compilado. Las escrituras no hacen commit: lo hace la ruta.
"""
import calendar
import math
import sqlite3
from datetime import date
from typing import Any, Dict, List, Tuple

from desk.api import lifecycle, market, portfolio
from desk.api import fixings as fixing_store
from desk.api import valuation
from desk.api.db import now_iso
from desk.api.errors import ApiError
from desk.api.pricing import PRODUCT_LABEL
from desk.api.settlement import merge_warnings
from desk.api.validation import number, text

DEFAULT_HAZARD, DEFAULT_RECOVERY = 0.01, 0.40
N_PATHS, SEED, PFE_QUANTILE = 500, 42, 0.95
COVERED_PRODUCTS = ("irs",)
CVA_NOTICE = "CVA informativo: no entra al PV ni a la contabilidad de coberturas"
ASSUMED_NOTE = "Supuesto: probabilidad de incumplimiento 1 % anual y recuperación 40 % (sin parámetros capturados)"

_DAYS_PER_YEAR = 365.0
_MODEL_FREQUENCY = 365.0  # pagos por año que ve `qfxva` (diarios): ver el docstring del módulo
_MODEL_MATURITY_EPS_DAYS = 1e-6  # evita que `int(plazo · frecuencia)` pierda un día por redondeo binario
_NOT_COVERED = "La exposición simulada solo cubre swaps de tasas (IRS): %s se excluye"
_NOT_VALUED = "No se pudo valuar: %s"



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


def _model_maturity(trade: Dict[str, Any], as_of: date) -> float:
    return ((trade["maturity_date"] - as_of).days + _MODEL_MATURITY_EPS_DAYS) / _DAYS_PER_YEAR


def _effective_fixed_rate(
    qfpy: Any, curve: Any, side: Any, notional: float, maturity: float, pv: float
) -> float:
    """Tasa fija con la que el swap del modelo vale `pv` hoy sobre `curve`.

    El valor del swap de `qfpy.InterestRateSwap` (el mismo que usa `qfxva.NettingSet` en `t = 0`) es
    lineal en la tasa fija, así que dos valuaciones (tasa 0 y tasa 1) fijan la recta y se despeja la
    tasa. `pv` va en la moneda de la curva. Lanza `ValueError` si el swap no tiene cupones que valuar.
    """
    env = qfpy.MarketEnvironment(curve)
    v0 = qfpy.InterestRateSwap(notional, 0.0, maturity, _MODEL_FREQUENCY, side).npv(env)
    v1 = qfpy.InterestRateSwap(notional, 1.0, maturity, _MODEL_FREQUENCY, side).npv(env)
    slope = v1 - v0
    rate = (pv - v0) / slope if slope else float("nan")
    if not math.isfinite(rate):
        raise ValueError("no se pudo calibrar la tasa fija efectiva del swap")
    return rate


def _netting_set(qfxva: Any, trades: List[Dict[str, Any]], as_of: date) -> Any:
    ns = qfxva.NettingSet()
    for t in trades:
        ns.add(
            notional=t["notional"],
            fixed_rate=t["model_rate"],
            maturity=_model_maturity(t, as_of),
            frequency=_MODEL_FREQUENCY,
            swap_type=qfxva.SwapType.Payer if t["terms"]["side"] == "payer" else qfxva.SwapType.Receiver,
        )
    return ns


def _counterparty(
    qfxva: Any,
    mkt: Any,
    name: str,
    params: Dict[str, Any],
    covered: List[Dict[str, Any]],
    excluded: List[Dict[str, Any]],
) -> Dict[str, Any]:
    from desk.api.qf import qfpy

    as_of = mkt.as_of
    by_curve = {}  # type: Dict[str, List[Dict[str, Any]]]
    for t in covered:
        by_curve.setdefault(t["terms"]["curve"], []).append(t)
    curves = [c for c in market.CURVES if c in by_curve]  # orden de `market.CURVES`

    profile = []  # type: List[Dict[str, Any]]
    netting_sets = []  # type: List[Dict[str, Any]]
    if covered:
        dates = _grid(as_of, max(t["maturity_date"] for t in covered))
        ts = [(d - as_of).days / _DAYS_PER_YEAR for d in dates]
        ee = [0.0] * len(dates)
        pfe = [0.0] * len(dates)
        sim = qfxva.SimParams(n_paths=N_PATHS, monitor_dates=ts, seed=SEED)
        credit = qfxva.FlatHazardRate(lambda_=params["hazard_rate"])
        for curve in curves:
            trades = by_curve[curve]
            fx = 1.0 if market.CURVES[curve]["currency"] == "MXN" else mkt.spot
            hw = qfpy.HullWhite(a=mkt.hw[curve]["a"], sigma=mkt.hw[curve]["sigma"], curve=mkt.curves[curve])
            ns = _netting_set(qfxva, trades, as_of)
            for k, p in enumerate(qfxva.simulate_exposure(hw, ns, sim, pfe_quantile=PFE_QUANTILE)):
                ee[k] += p.epe * fx
                pfe[k] += max(p.pfe, p.epe) * fx  # PFE >= EE por construcción
            calc = qfxva.CVACalculator(hw, credit, lgd=1.0 - params["recovery"], params=sim)
            cva = calc.compute(ns, qfpy.MarketEnvironment(mkt.curves[curve])).cva * fx
            pv = sum(t["pv_mxn"] for t in trades)
            netting_sets.append(
                {
                    "curve": curve,
                    "currency": market.CURVES[curve]["currency"],
                    "trades": [t["id"] for t in trades],
                    "pv_mxn": pv,
                    "cva_mxn": cva,
                }
            )
        # EE(0) = PFE(0) = max(PV de la contraparte, 0) con la valuación del desk: el valor de hoy compensa
        # entre monedas; los puntos mensuales no (cota superior declarada, ver el docstring del módulo).
        ee0 = max(sum(t["pv_mxn"] for t in covered), 0.0)
        profile = [{"date": as_of.isoformat(), "t": 0.0, "ee_mxn": ee0, "pfe_mxn": ee0}] + [
            {"date": d.isoformat(), "t": t, "ee_mxn": e, "pfe_mxn": f}
            for d, t, e, f in zip(dates, ts, ee, pfe)
        ]
    return {
        "counterparty": name,
        "hazard_rate": params["hazard_rate"],
        "recovery": params["recovery"],
        "assumed": params["assumed"],
        "assumed_note": ASSUMED_NOTE if params["assumed"] else None,
        "pv_mxn": sum(ns["pv_mxn"] for ns in netting_sets),
        "cva_mxn": sum(ns["cva_mxn"] for ns in netting_sets),
        "netting_sets": netting_sets,
        "profile": profile,
        "excluded": excluded,
    }


def exposure(conn: sqlite3.Connection, snapshot_id: str) -> Dict[str, Any]:
    """Cuerpo de `GET /api/credit/exposure`: perfil EE/PFE mensual y CVA de cada contraparte con operaciones vivas."""
    from desk.api.qf import qfpy  # debe cargarse antes que qfxva
    import qfxva

    mkt = market.load_context(conn, snapshot_id)
    fixings = fixing_store.load_all(conn)
    hist = _history(conn)
    ids = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM counterparties")}

    covered = {}  # type: Dict[str, List[Dict[str, Any]]]
    excluded = {}  # type: Dict[str, List[Dict[str, Any]]]
    warnings = []  # type: List[List[Dict[str, Any]]]
    for trade in portfolio.load_trades(conn):
        if not valuation.is_live(trade, mkt.as_of):
            continue
        name = trade["counterparty"]
        covered.setdefault(name, [])
        excluded.setdefault(name, [])
        if trade["product"] not in COVERED_PRODUCTS:
            label = PRODUCT_LABEL.get(trade["product"], trade["product"])
            excluded[name].append({"id": trade["id"], "product": trade["product"], "reason": _NOT_COVERED % label})
            continue
        try:
            terms = lifecycle.state(trade, trade["events"], mkt.as_of)["terms"]
            v = valuation.value_trade(trade, mkt, fixings)
            if terms["fixed_rate"] is None:
                raise ValueError("Falta el parámetro 'fixed_rate'")
            side = qfpy.SwapType.Payer if terms["side"] == "payer" else qfpy.SwapType.Receiver
            model_rate = _effective_fixed_rate(
                qfpy, mkt.curves[terms["curve"]], side, v["notional"], _model_maturity(trade, mkt.as_of), v["pv"]
            )
        except Exception as e:  # una operación que no se valúa se excluye; no detiene al resto
            excluded[name].append(
                {"id": trade["id"], "product": trade["product"], "reason": _NOT_VALUED % e}
            )
            continue
        warnings.append(v["warnings"])
        covered[name].append(
            {
                "id": trade["id"],
                "terms": terms,
                "notional": v["notional"],
                "maturity_date": trade["maturity_date"],
                "model_rate": model_rate,
                "pv_mxn": v["pv_mxn"],
            }
        )

    counterparties = []
    flat_excluded = []  # type: List[Dict[str, Any]]
    for name in sorted(covered):
        params = _params_row(name, hist.get(ids.get(name), []))
        counterparties.append(_counterparty(qfxva, mkt, name, params, covered[name], excluded[name]))
        flat_excluded += [dict(counterparty=name, **x) for x in excluded[name]]
    return {
        "snapshot": snapshot_id,
        "as_of": mkt.as_of.isoformat(),
        "n_paths": N_PATHS,
        "seed": SEED,
        "pfe_quantile": PFE_QUANTILE,
        "notice": CVA_NOTICE,
        "counterparties": counterparties,
        "excluded": flat_excluded,
        "warnings": merge_warnings(*warnings),
    }
