"""XVA por contraparte (corte 9, R2a, R3, R4, R10d): CVA, DVA y FVA con el motor multimoneda de `qfxva`.

Aquí no hay fórmulas: Python arma las especificaciones de cada contraparte desde sus operaciones vivas con
exactamente los términos que valúa el desk (`valuation.aged_swap_terms`, `xccy.aged_xccy_terms`), pasa el
mercado, el modelo y las curvas de crédito a `qfxva.ExposureEngine` y `qfxva.compute_xva`, y da forma al JSON.
Un solo conjunto de compensación por contraparte, con swaps de tasas (MXN y USD) y cross currency swaps; el
valor del conjunto en t = 0 es el PV del desk. El resto de productos se lista en `excluded`.

* Parámetros (`xva.*` en `settings`): fondeo, trayectorias, semilla y percentil de PFE; ver `load_params`.
* Modelo: Hull-White de las dos curvas del snapshot, volatilidad USDMXN ATM a 1 año de la superficie y
  correlaciones de los factores del snapshot. Lo que falta usa omisiones que se declaran en `assumptions`.
* Crédito: la curva de CDS de la contraparte (`credit_curves`) o, sin ella, la intensidad plana de
  `counterparty_credit` o, sin nada, el supuesto 1 % / 40 %; el crédito propio (`"propia"`) igual, sin la
  intensidad plana.
* XVA incremental (`incremental`): el conjunto de la contraparte con y sin una operación candidata que no se
  guarda, simulados en una sola llamada al motor (mismas trayectorias), así que la diferencia no lleva ruido
  de Monte Carlo entre corridas.
* `GET /api/credit/exposure` (`risk/credit.py`) usa `compute_detailed`: la exposición y el CVA son los de aquí.
* Mallas (H21): el perfil que se publica es mensual (`report_days`), pero CVA, DVA y FVA se integran sobre una malla
  más fina (`integration_days`): la mensual, cada `INTEGRATION_STEP` días, las fechas de pago y de intercambio de
  nocional de las operaciones y el día anterior a cada una. El motor simula siempre por días: cambiar la malla no
  cambia las trayectorias, solo en cuántas fechas se mide la exposición que entra a la suma.

`qfxva` se importa dentro de las funciones, después de `qfpy` (ambos registran tipos C++ compartidos), para que
el backend arranque aunque el módulo no esté compilado. Las escrituras no hacen commit: lo hace la ruta.
"""
import math
import sqlite3
from datetime import date, timedelta
from typing import Any, Dict, List, Tuple

from desk.api import collateral, lifecycle, market, portfolio, valuation, xccy
from desk.api import fixings as fixing_store
from desk.api.db import now_iso
from desk.api.errors import ApiError
from desk.api.pricing import PRODUCT_LABEL, PRODUCTS
from desk.api.risk import credit, credit_curves
from desk.api.settlement import merge_warnings
from desk.api.validation import choice, integer, number, text

DEFAULTS = {"funding_spread": 0.005, "n_paths": 2000, "seed": 42, "pfe_quantile": 0.95}
NOTICE = "XVA informativo: no entra al PV ni a la contabilidad"
COLLATERAL_NOTE = "Exposición sin colateral ni margen: la moneda de colateral solo cambia la curva de descuento"
COVERED_PRODUCTS = ("irs", "xccy_swap")
CORRELATION_NOTE = (
    "Correlaciones tomadas de los cambios diarios de los factores del snapshot (TIIE-F, SOFR, USDMXN): "
    "aproximación de las correlaciones de los brownianos del modelo"
)
INTEGRATION_STEP = 3  # días entre fechas de la malla de integración (además de pagos e intercambios)
INTEGRATION_NOTE = (
    "CVA, DVA y FVA se integran sobre una malla más fina que el perfil mostrado (mensual): cada %d días, más "
    "cada fecha de pago y de intercambio de nocional y el día anterior a cada una, con la exposición de la "
    "fecha al final de cada intervalo (regla del extremo derecho) y las mismas trayectorias diarias" % INTEGRATION_STEP
)
HW_DEFAULTS = {"TIIE-F": (0.05, 0.01), "SOFR": (0.03, 0.008)}
FX_VOL_DEFAULT = 0.12

_PREFIX = "xva."
_NOT_COVERED = "El XVA solo cubre swaps de tasa y cross currency swaps: %s se excluye"
_NOT_VALUED = "No se pudo valuar: %s"
_TRADING_DAYS = 252.0


def _qfxva() -> Any:
    from desk.api.qf import qfpy  # noqa: F401  (debe cargarse antes que qfxva)
    import qfxva

    return qfxva


# ------------------------------------------------------------------ parámetros

def _stored(conn: sqlite3.Connection) -> Dict[str, str]:
    return {
        r["key"][len(_PREFIX):]: r["value"]
        for r in conn.execute("SELECT key, value FROM settings WHERE key LIKE ?", (_PREFIX + "%",))
    }


def load_params(conn: sqlite3.Connection) -> Dict[str, Any]:
    """`{funding_spread, n_paths, seed, pfe_quantile}` vigentes: lo guardado en `settings` o su omisión."""
    stored = _stored(conn)
    kinds = {"funding_spread": float, "n_paths": int, "seed": int, "pfe_quantile": float}
    return {k: kinds[k](stored[k]) if k in stored else DEFAULTS[k] for k in DEFAULTS}


def params_response(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Cuerpo de `GET /api/xva/params`: los cuatro valores, `assumed` (¿el fondeo es la omisión?) y `defaults`."""
    out = load_params(conn)  # type: Dict[str, Any]
    out["assumed"] = {"funding_spread": "funding_spread" not in _stored(conn)}
    out["defaults"] = dict(DEFAULTS)
    return out


def put_params(conn: sqlite3.Connection, body: Dict[str, Any]) -> Dict[str, Any]:
    """Valida todo el cuerpo (cualquier subconjunto de los cuatro), guarda en `settings` y responde como el GET.

    @raise ApiError 400 con `field` = la clave desconocida o la que no cumple su rango.
    """
    for key in body:
        if key not in DEFAULTS:
            raise ApiError(400, "Ajuste desconocido: %s" % key, key)
    values = {}  # type: Dict[str, Any]
    if "funding_spread" in body:
        values["funding_spread"] = number(body, "funding_spread", ge=0, le=0.1)
    if "n_paths" in body:
        values["n_paths"] = integer(body, "n_paths", ge=100, le=20000)
    if "seed" in body:
        values["seed"] = integer(body, "seed", ge=0, le=2 ** 31 - 1)
    if "pfe_quantile" in body:
        values["pfe_quantile"] = number(body, "pfe_quantile", ge=0.5, le=0.999)
    now = now_iso()
    for key, value in values.items():
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            (_PREFIX + key, str(value), now),
        )
    return params_response(conn)


# ------------------------------------------------------------------ modelo

def model_from_snapshot(mkt: Any) -> Tuple[Any, Dict[str, Any], List[str]]:
    """`(ExposureModel, model_json, assumptions)` del snapshot.

    `a` y `sigma` de `mkt.hw`; la volatilidad USDMXN es la ATM a 1 año de la superficie (strike = spot) o,
    sin superficie, la volatilidad diaria del factor USDMXN por √252; las correlaciones salen de
    `mkt.factors` (TIIE-F/SOFR, TIIE-F/USDMXN, SOFR/USDMXN). Cada dato que falta usa su omisión
    (`HW_DEFAULTS`, `FX_VOL_DEFAULT`, correlaciones 0) y deja una línea en `assumptions`.

    El modelo se valida al construir el motor (`engine`): unas correlaciones no definidas positivas lanzan
    `ValueError`, que la API responde como 400.
    """
    qfxva = _qfxva()
    assumptions = []  # type: List[str]
    hw = {}  # type: Dict[str, Dict[str, float]]
    for curve, (a, sigma) in HW_DEFAULTS.items():
        found = (mkt.hw or {}).get(curve) or {}
        if "a" in found and "sigma" in found:
            hw[curve] = {"a": float(found["a"]), "sigma": float(found["sigma"])}
        else:
            hw[curve] = {"a": a, "sigma": sigma}
            assumptions.append(
                "El snapshot no trae los parámetros Hull-White de %s: se usó a = %g y σ = %g" % (curve, a, sigma)
            )

    factors = mkt.factors or {}
    names = list(factors.get("names") or [])
    surface = getattr(mkt, "surface", None)
    if surface is not None:
        fx_vol, source = float(surface.vol(mkt.spot, 1.0)), "surface_atm_1y"
    elif "USDMXN" in names and factors.get("daily_vols"):
        fx_vol, source = float(factors["daily_vols"][names.index("USDMXN")]) * math.sqrt(_TRADING_DAYS), "factor_daily_vol"
    else:
        fx_vol, source = FX_VOL_DEFAULT, "default"
        assumptions.append("El snapshot no trae superficie ni volatilidad del factor USDMXN: se usó %g" % FX_VOL_DEFAULT)

    if all(n in names for n in ("TIIE-F", "SOFR", "USDMXN")) and factors.get("correlations"):
        c = factors["correlations"]
        i, j, k = names.index("TIIE-F"), names.index("SOFR"), names.index("USDMXN")
        rho = {"mxn_usd": float(c[i][j]), "mxn_fx": float(c[i][k]), "usd_fx": float(c[j][k])}
        assumptions.append(CORRELATION_NOTE)
    else:
        rho = {"mxn_usd": 0.0, "mxn_fx": 0.0, "usd_fx": 0.0}
        assumptions.append("El snapshot no trae las correlaciones de los factores (TIIE-F, SOFR, USDMXN): se usó 0")

    model = qfxva.ExposureModel(
        a_mxn=hw["TIIE-F"]["a"], sigma_mxn=hw["TIIE-F"]["sigma"],
        a_usd=hw["SOFR"]["a"], sigma_usd=hw["SOFR"]["sigma"], fx_vol=fx_vol,
        rho_mxn_usd=rho["mxn_usd"], rho_mxn_fx=rho["mxn_fx"], rho_usd_fx=rho["usd_fx"],
    )
    return model, {"hw": hw, "fx_vol": fx_vol, "fx_vol_source": source, "correlations": rho}, assumptions


# ------------------------------------------------------------------ crédito

def _credit_info(kind: str, recovery: float, source: Any, assumed: bool, note: Any) -> Dict[str, Any]:
    return {"kind": kind, "recovery": recovery, "source": source, "assumed": assumed, "note": note}


def _assumed(qfxva: Any, note: str = credit.ASSUMED_NOTE) -> Tuple[Any, float, Dict[str, Any]]:
    curve = qfxva.FlatHazardRate(lambda_=credit.DEFAULT_HAZARD)
    return curve, credit.DEFAULT_RECOVERY, _credit_info("assumed", credit.DEFAULT_RECOVERY, None, True, note)


def _curve_credit(qfxva: Any, conn: sqlite3.Connection, entity: str, mkt: Any) -> Tuple[Any, float, Any, Any]:
    """`(curva, recuperación, fuente, nota)` de la curva de CDS vigente; `curva` es `None` si no hay o no se ajusta."""
    row = credit_curves.current(conn).get(entity)
    if row is None:
        return None, 0.0, None, None
    try:
        return credit_curves.build_curve(qfxva, row, mkt), row["recovery"], dict(credit_curves.SOURCE), None
    except ValueError as exc:  # la curva existe pero no cuadra con este snapshot: se declara y se usa el respaldo
        return None, 0.0, None, "%s: se usó el respaldo" % credit_curves._bootstrap_message(exc)


def credit_for(conn: sqlite3.Connection, name: str, mkt: Any) -> Tuple[Any, float, Dict[str, Any]]:
    """`(curva de crédito, recuperación, info)` de la contraparte: su curva de CDS, o la intensidad plana de
    `counterparty_credit` (`kind: "flat"`), o el supuesto (`kind: "assumed"`). `info` es el bloque `credit`
    del JSON. Una curva que no cuadra con el snapshot se sustituye por el respaldo y lo dice en `note`."""
    qfxva = _qfxva()
    curve, recovery, source, failure = _curve_credit(qfxva, conn, name, mkt)
    if curve is not None:
        return curve, recovery, _credit_info("curve", recovery, source, False, None)
    row = conn.execute("SELECT id FROM counterparties WHERE name = ?", (name,)).fetchone()
    params = credit._params_row(name, credit._history(conn).get(row["id"] if row else None, []))
    if params["assumed"]:
        return _assumed(qfxva, failure or credit.ASSUMED_NOTE)
    flat = qfxva.FlatHazardRate(lambda_=params["hazard_rate"])
    note = failure or "Intensidad plana capturada en los parámetros de crédito (sin estructura temporal)"
    return flat, params["recovery"], _credit_info("flat", params["recovery"], None, False, note)


def own_credit(conn: sqlite3.Connection, mkt: Any) -> Tuple[Any, float, Dict[str, Any]]:
    """Como `credit_for` para el crédito propio (`"propia"`): su curva de CDS o, sin ella, el supuesto."""
    qfxva = _qfxva()
    curve, recovery, source, failure = _curve_credit(qfxva, conn, credit_curves.OWN, mkt)
    if curve is not None:
        return curve, recovery, dict(_credit_info("curve", recovery, source, False, None), entity=credit_curves.OWN)
    curve, recovery, info = _assumed(qfxva, failure or credit.ASSUMED_NOTE)
    return curve, recovery, dict(info, entity=credit_curves.OWN)


# ------------------------------------------------------------------ especificaciones y simulación

def _swap_spec(qfxva: Any, trade: Dict[str, Any], terms: Dict[str, Any], mkt: Any, fixings: Any) -> Any:
    vm = mkt.with_collateral(collateral.currency_on(trade, mkt.as_of))
    a = valuation.aged_swap_terms(trade, terms, vm, fixings, [])
    usd = market.CURVES[a["curve"]]["currency"] == "USD"
    return qfxva.RateSwapSpec(
        currency=qfxva.SwapCurrency.USD if usd else qfxva.SwapCurrency.MXN,
        notional=a["notional"], fixed_rate=a["fixed_rate"], payer=a["side"] == "payer",
        start_days=a["start_days"], pay_days=a["pay_days"], accrued_factor=a["accrued_factor"],
        csa_discount=not usd and a["discount"] == market.CSA_CURVE,
    )


def _xccy_spec(qfxva: Any, trade: Dict[str, Any], terms: Dict[str, Any], mkt: Any, fixings: Any) -> Any:
    a = xccy.aged_xccy_terms(trade, terms, mkt, fixings, [])
    return qfxva.XccySwapSpec(
        notional_usd=a["notional_usd"], fx_rate=a["fx_rate"], spread=a["spread"],
        start_days=a["start_days"], pay_days=a["pay_days"],
        accrued_factor_usd=a["accrued_factor_usd"], accrued_factor_mxn=a["accrued_factor_mxn"],
        pay_usd=a["side"] == "pay_usd", initial_exchange=a["initial_exchange"], final_exchange=a["final_exchange"],
        csa_discount=a["csa_discount"],
    )


def build_set(
    trades: List[Dict[str, Any]], mkt: Any, fixings: Any
) -> Tuple[Any, List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """`(NettingSetSpec, included, excluded, warnings)` de las operaciones vivas de una contraparte.

    `included` (`{id, product, label, pv_mxn}`, en el orden de `trades`) son los `irs` y `xccy_swap` que se
    pudieron valuar con el desk (`pv_mxn` es `valuation.value_trade`); `excluded` (`{id, product, reason}`)
    los demás o los que no se valúan (una operación que falla no detiene al resto). `warnings` son los avisos de
    valuación de las incluidas (fijaciones faltantes, curva de colateral). El motor ordena los valores en t = 0
    primero swaps de tasa y luego cross currency swaps.
    """
    qfxva = _qfxva()
    swaps, xccys, included, excluded, warnings = [], [], [], [], []  # type: List[Any]
    for trade in trades:
        name = trade["product"]
        label = PRODUCT_LABEL.get(name, name)
        if name not in COVERED_PRODUCTS:
            excluded.append({"id": trade["id"], "product": name, "reason": _NOT_COVERED % label})
            continue
        try:
            terms = lifecycle.state(trade, trade["events"], mkt.as_of)["terms"]
            value = valuation.value_trade(trade, mkt, fixings)
            if name == "irs":
                spec = _swap_spec(qfxva, trade, terms, mkt, fixings)
            else:
                spec = _xccy_spec(qfxva, trade, terms, mkt, fixings)
        except Exception as exc:
            excluded.append({"id": trade["id"], "product": name, "reason": _NOT_VALUED % exc})
            continue
        (swaps if name == "irs" else xccys).append(spec)
        warnings.append(value["warnings"])
        included.append({"id": trade["id"], "product": name, "label": label, "pv_mxn": value["pv_mxn"]})
    return qfxva.NettingSetSpec(swaps=swaps, xccys=xccys), included, excluded, merge_warnings(*warnings)


def report_days(as_of: date, last_maturity: date) -> List[int]:
    """Malla del perfil publicado, en días desde `as_of`: el día 0 y las fechas mensuales hasta `last_maturity`."""
    return [0] + [(d - as_of).days for d in credit._grid(as_of, last_maturity)]


def integration_days(report: List[int], spec: Any) -> List[int]:
    """Malla de integración del XVA: `report` (mensual), un día de cada `INTEGRATION_STEP` desde el 0, y de cada
    operación de `spec` las fechas de pago (la última es el vencimiento), la de inicio si es futura (intercambio
    inicial) y el día anterior a cada una. El día anterior a un pago es donde la exposición todavía incluye el flujo;
    con la regla del extremo derecho, una malla sin él da al intervalo del pago la exposición ya sin el flujo.
    Termina en `report[-1]`, que es el primer mes que alcanza el último vencimiento."""
    horizon = report[-1]
    days = set(report) | set(range(0, horizon + 1, INTEGRATION_STEP))
    for leg in list(spec.swaps) + list(spec.xccys):
        for d in list(leg.pay_days) + ([leg.start_days] if leg.start_days > 0 else []):
            days.update((d - 1, d))
    return sorted(d for d in days if 0 <= d <= horizon)


def engine(mkt: Any, model: Any, params: Dict[str, Any], days: List[int]) -> Any:
    """`qfxva.ExposureEngine` del snapshot con los parámetros de simulación y la malla `days` (de integración)."""
    qfxva = _qfxva()
    exposure_market = qfxva.ExposureMarket(
        mkt.curves["TIIE-F"], mkt.curves["SOFR"], mkt.spot, mkt.curves.get(market.CSA_CURVE)
    )
    config = qfxva.SimConfig(
        n_paths=params["n_paths"], seed=params["seed"], pfe_quantile=params["pfe_quantile"], report_days=days
    )
    return qfxva.ExposureEngine(exposure_market, model, config)


def _shown(profile: Any, report: List[int]) -> List[int]:
    """Índices de las fechas de `profile` (malla de integración) que pertenecen al perfil publicado `report`."""
    shown = set(report)
    return [i for i, d in enumerate(profile.days) if d in shown]


def _profile_points(profile: Any, as_of: date, shown: List[int]) -> List[Dict[str, Any]]:
    days, times, epe, ene, pfe = profile.days, profile.times, profile.epe, profile.ene, profile.pfe  # cada acceso copia
    return [
        {
            "date": (as_of + timedelta(days=days[i])).isoformat(), "t": times[i],
            "epe_mxn": epe[i], "ene_mxn": ene[i], "pfe_mxn": pfe[i],
        }
        for i in shown
    ]


def _counterparty(
    conn: sqlite3.Connection, mkt: Any, model: Any, params: Dict[str, Any], fixings: Any,
    own: Tuple[Any, float], name: str, trades: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Any]:
    """Elemento de `counterparties`, los avisos de valuación de sus operaciones y su curva de crédito."""
    qfxva = _qfxva()
    spec, included, excluded, warnings = build_set(trades, mkt, fixings)
    cp_curve, recovery, info = credit_for(conn, name, mkt)
    out = {
        "counterparty": name, "credit": info, "included": included, "excluded": excluded,
        "pv_mxn": sum(i["pv_mxn"] for i in included),
        "cva_mxn": 0.0, "cva_stderr_mxn": 0.0, "dva_mxn": 0.0, "fva_mxn": 0.0, "total_mxn": 0.0,
        "epe_max_mxn": 0.0, "pfe_max_mxn": 0.0, "profile": [],
    }  # type: Dict[str, Any]
    if included:
        report = report_days(mkt.as_of, _last_maturity(trades, included))
        profile = engine(mkt, model, params, integration_days(report, spec)).simulate([spec])[0]
        x = qfxva.compute_xva(profile, cp_curve, 1.0 - recovery, own[0], 1.0 - own[1], params["funding_spread"])
        points = _profile_points(profile, mkt.as_of, _shown(profile, report))
        out.update(
            cva_mxn=x.cva, cva_stderr_mxn=x.cva_stderr, dva_mxn=x.dva, fva_mxn=x.fva, total_mxn=x.total,
            epe_max_mxn=max(p["epe_mxn"] for p in points), pfe_max_mxn=max(p["pfe_mxn"] for p in points),
            profile=points,
        )
    return out, warnings, cp_curve


def _last_maturity(trades: List[Dict[str, Any]], included: List[Dict[str, Any]]) -> date:
    """Mayor vencimiento entre las operaciones de `trades` que quedaron en `included`."""
    ids = {i["id"] for i in included}
    return max(t["maturity_date"] for t in trades if t["id"] in ids)


def live_by_counterparty(conn: sqlite3.Connection, mkt: Any) -> Dict[str, List[Dict[str, Any]]]:
    """Operaciones vivas al `as_of` del snapshot por nombre de contraparte (orden de id dentro de cada una)."""
    out = {}  # type: Dict[str, List[Dict[str, Any]]]
    for trade in portfolio.load_trades(conn):
        if valuation.is_live(trade, mkt.as_of):
            out.setdefault(trade["counterparty"], []).append(trade)
    return out


def average_hazard(curve: Any, years: float = 5.0) -> float:
    """Intensidad media a `years` años de una curva de crédito: −ln S(years) / years."""
    return math.log(1.0 / curve.survival_probability(years)) / years


def compute(conn: sqlite3.Connection, snapshot_id: str) -> Dict[str, Any]:
    """Cuerpo de `GET /api/xva`: CVA, DVA, FVA y perfil de exposición de cada contraparte con operaciones vivas."""
    return compute_detailed(conn, snapshot_id)[0]


def compute_detailed(conn: sqlite3.Connection, snapshot_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """`(cuerpo de GET /api/xva, {contraparte: curva de crédito usada})`; lo segundo lo necesita `credit.exposure`
    para informar la intensidad media sin volver a construir la curva."""
    mkt = market.load_context(conn, snapshot_id)
    fixings = fixing_store.load_all(conn)
    params = params_response(conn)
    simulation = {k: params[k] for k in DEFAULTS}
    model, model_json, assumptions = model_from_snapshot(mkt)
    assumptions.append(INTEGRATION_NOTE)
    own_curve, own_recovery, own_info = own_credit(conn, mkt)
    if not mkt.csa_available:
        assumptions.append(
            "El snapshot no trae la curva MXN-USD: la base cross currency se tomó nula y el descuento con "
            "colateral USD usa TIIE-F"
        )
    if params["assumed"]["funding_spread"]:
        assumptions.append("Spread de fondeo %.2f %%: valor por omisión, sin ajuste capturado" % (simulation["funding_spread"] * 100))
    if own_info["assumed"]:
        assumptions.append("Crédito propio: %s" % own_info["note"])
    counterparties = []  # type: List[Dict[str, Any]]
    curves = {}  # type: Dict[str, Any]
    warnings = []  # type: List[List[Dict[str, Any]]]
    for name, trades in sorted(live_by_counterparty(conn, mkt).items()):
        cp, warns, curves[name] = _counterparty(
            conn, mkt, model, simulation, fixings, (own_curve, own_recovery), name, trades
        )
        if cp["credit"]["assumed"]:
            assumptions.append("%s: %s" % (name, cp["credit"]["note"]))
        counterparties.append(cp)
        warnings.append(warns)
    body = {
        "snapshot": snapshot_id,
        "as_of": mkt.as_of.isoformat(),
        "notice": NOTICE,
        "collateral_note": COLLATERAL_NOTE,
        "params": simulation,
        "model": model_json,
        "assumptions": assumptions,
        "own_credit": own_info,
        "counterparties": counterparties,
        "warnings": merge_warnings(*warnings),
    }
    return body, curves


# ------------------------------------------------------------------ XVA incremental

_CANDIDATE_NOT_COVERED = "El XVA incremental solo cubre swaps de tasas y cross currency swaps; %s no está cubierto"
_CANDIDATE_NOT_LIVE = "La operación candidata no está viva en la fecha de valuación del snapshot (%s)"


def _side(pv: float, x: Any, epe: List[float], pfe: List[float]) -> Dict[str, Any]:
    """Bloque `before`/`after` del incremental: PV del conjunto, XVA y máximos del perfil mostrado (`epe`, `pfe`
    ya reducidos a la malla mensual), sin descontar."""
    return {
        "pv_mxn": pv, "cva_mxn": x.cva, "cva_stderr_mxn": x.cva_stderr, "dva_mxn": x.dva, "fva_mxn": x.fva,
        "total_mxn": x.total, "epe_max_mxn": max(epe), "pfe_max_mxn": max(pfe),
    }


def incremental(conn: sqlite3.Connection, body: Dict[str, Any]) -> Dict[str, Any]:
    """Cuerpo de `POST /api/xva/incremental`: XVA del conjunto de la contraparte antes y después de la candidata.

    `body` es el de `POST /api/trades` más `snapshot` (obligatorio). La candidata no se guarda. Antes y después
    salen de una sola llamada a `simulate([antes, después])`, con la malla de integración del «después» (que
    incluye las fechas de la candidata): las dos comparten trayectorias y malla, así que `delta` no lleva ruido de
    Monte Carlo entre corridas y una candidata espejo de la única operación del conjunto da exactamente `−antes`.
    El perfil y los máximos que se publican son los de la malla mensual.

    Orden de errores: `snapshot` ausente, `product` (el `choice` de `POST /api/trades`), producto fuera del XVA,
    contraparte inexistente (404), los términos con `portfolio.prepare_trade` (mismos mensajes y `field` que
    `POST /api/trades`) y candidata no viva en el `as_of` del snapshot.
    """
    snapshot_id = text(body, "snapshot")
    product = choice(body, "product", tuple(PRODUCTS))
    label = PRODUCT_LABEL.get(product, product)
    if product not in COVERED_PRODUCTS:
        raise ApiError(400, _CANDIDATE_NOT_COVERED % label, "product")
    name = text(body, "counterparty")
    if conn.execute("SELECT 1 FROM counterparties WHERE name = ?", (name,)).fetchone() is None:
        raise ApiError(404, "Contraparte inexistente: %s" % name, "counterparty")
    prepared = portfolio.prepare_trade(conn, body)

    mkt = market.load_context(conn, snapshot_id)
    candidate = dict(prepared, id=None, events=[], collateral=collateral.history(conn).get(name, []))
    if not valuation.is_live(candidate, mkt.as_of):
        raise ApiError(400, _CANDIDATE_NOT_LIVE % mkt.as_of.isoformat(), "trade_date")
    fixings = fixing_store.load_all(conn)
    value = valuation.value_trade(candidate, mkt, fixings)

    existing = live_by_counterparty(conn, mkt).get(name, [])
    spec_before, included_before, _, warn_before = build_set(existing, mkt, fixings)
    spec_candidate, included_candidate, excluded_candidate, warn_candidate = build_set([candidate], mkt, fixings)
    if not included_candidate:
        raise ApiError(400, excluded_candidate[0]["reason"], "params")
    qfxva = _qfxva()
    spec_after = qfxva.NettingSetSpec(
        swaps=spec_before.swaps + spec_candidate.swaps, xccys=spec_before.xccys + spec_candidate.xccys
    )

    params = load_params(conn)
    model = model_from_snapshot(mkt)[0]
    cp_curve, recovery, _ = credit_for(conn, name, mkt)
    own_curve, own_recovery, _ = own_credit(conn, mkt)
    report = report_days(mkt.as_of, _last_maturity(existing + [candidate], included_before + included_candidate))
    p_before, p_after = engine(mkt, model, params, integration_days(report, spec_after)).simulate(
        [spec_before, spec_after]
    )
    shown = _shown(p_after, report)
    days, times = p_after.days, p_after.times  # cada acceso a un atributo del perfil copia el vector
    epe_b, ene_b, pfe_b = p_before.epe, p_before.ene, p_before.pfe
    epe_a, ene_a, pfe_a = p_after.epe, p_after.ene, p_after.pfe
    x_before, x_after = (
        qfxva.compute_xva(p, cp_curve, 1.0 - recovery, own_curve, 1.0 - own_recovery, params["funding_spread"])
        for p in (p_before, p_after)
    )

    pv_before = sum(i["pv_mxn"] for i in included_before)
    pv_candidate = included_candidate[0]["pv_mxn"]
    before = _side(pv_before, x_before, [epe_b[i] for i in shown], [pfe_b[i] for i in shown])
    after = _side(pv_before + pv_candidate, x_after, [epe_a[i] for i in shown], [pfe_a[i] for i in shown])
    delta = {k: after[k] - before[k] for k in ("cva_mxn", "dva_mxn", "fva_mxn", "total_mxn")}
    notional_mxn = value["notional"] * (mkt.spot if value["currency"] == "USD" else 1.0)
    return {
        "snapshot": snapshot_id,
        "as_of": mkt.as_of.isoformat(),
        "counterparty": name,
        "notice": NOTICE,
        "candidate": {
            "product": product, "label": label, "params": prepared["params"],
            "trade_date": prepared["trade_date"].isoformat(), "start_date": prepared["start_date"].isoformat(),
            "maturity_date": prepared["maturity_date"].isoformat(),
            "notional": value["notional"], "currency": value["currency"], "notional_mxn": notional_mxn,
            "pv_mxn": pv_candidate,
        },
        "before": before,
        "after": after,
        "delta": delta,
        "delta_bp": {k[:-4]: v / notional_mxn * 1e4 for k, v in delta.items()},
        "profile": [
            {
                "date": (mkt.as_of + timedelta(days=days[i])).isoformat(), "t": times[i],
                "epe_before_mxn": epe_b[i], "ene_before_mxn": ene_b[i],
                "epe_after_mxn": epe_a[i], "ene_after_mxn": ene_a[i],
            }
            for i in shown
        ],
        "warnings": merge_warnings(warn_before, warn_candidate),
    }
