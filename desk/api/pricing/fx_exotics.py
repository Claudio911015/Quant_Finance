"""No touch y double no touch USDMXN: Monte Carlo con barrera continua sobre trayectorias de QuantLib."""
import threading

import numpy as np
import QuantLib as ql

from desk.api.errors import ApiError
from desk.api.pricing.base import MAX_DAYS, Product
from desk.api.validation import MAX_AMOUNT, MAX_PRICE, choice, integer, number
from desk.validation.ql_curves import build_curve

PATHS, STEPS, SEED, LV_STRIKES = 20000, 10, 42, 41
CHART_POINTS, CHART_PATHS = 21, 2000
SPOT_BUMP = VOL_BUMP = 0.01
_LOCK = threading.Lock()  # la fecha de valuación de QuantLib es global al proceso: un precio a la vez


def _common(d):
    p = {
        "side": choice(d, "side", ["buy", "sell"]),
        "payout_mxn": number(d, "payout_mxn", gt=0, le=MAX_AMOUNT),
        "days": integer(d, "days", ge=1, le=MAX_DAYS),
        "model": choice(d, "model", ["smile", "flat"], "smile"),
        "method": choice(d, "method", ["mc", "analytic"], "mc"),
    }
    if p["method"] == "analytic" and p["model"] == "smile":
        raise ApiError(400, "El método analítico solo vale con el modelo plano", "method")
    return p


def _nt_validate(d):
    barrier = number(d, "barrier", gt=0, le=MAX_PRICE)
    return dict(_common(d), product="fx_no_touch", barrier=barrier, barrier_type=choice(d, "barrier_type", ["up", "down"]))


def _dnt_validate(d):
    lower = number(d, "lower", gt=0, le=MAX_PRICE)
    return dict(_common(d), product="fx_double_no_touch", lower=lower, upper=number(d, "upper", gt=lower, le=MAX_PRICE))


def _sides(p):
    """(campo, +1 si la barrera queda arriba del spot, rótulo) de cada barrera del producto."""
    if "barrier" in p:
        return [("barrier", 1 if p["barrier_type"] == "up" else -1, "barrera")]
    return [("lower", -1, "barrera inferior"), ("upper", 1, "barrera superior")]


def _build(p, mkt, spot, dvol):
    """Mercado -> QuantLib: (descuento MXN, proceso, vol plana, malla de strikes, tabla de vol local)."""
    T, a = p["days"] / 365.0, mkt.as_of
    today, dc = ql.Date(a.day, a.month, a.year), ql.Actual365Fixed()
    ql.Settings.instance().evaluationDate = today

    def curve(c):  # la ZeroCurve del arnés de validación (cero lineal, plana fuera de los pilares): idéntica a la del desk
        pillars = [{"days": q["days"], "df": mkt.curves[c].discount_factor(q["days"] / 365.0)} for q in mkt.pillars[c]]
        return build_curve({"pillars": pillars}, today)

    dom, fgn = curve(mkt.mxn_discount), curve("SOFR")
    q, sigma = ql.QuoteHandle(ql.SimpleQuote(spot)), mkt.surface.vol(mkt.spot, T) + dvol  # vol fija: la del spot sin chocar
    if p["model"] == "flat":
        vol = ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, ql.NullCalendar(), sigma, dc))
        return dom, ql.GarmanKohlagenProcess(q, fgn, dom, vol), sigma, None, None
    Tg, Kg, Vg = mkt.surface.to_grid()
    surf = ql.BlackVarianceSurface(
        today, ql.NullCalendar(), [today + int(round(t * 365)) for t in Tg], Kg,
        ql.Matrix([[Vg[j][i] + dvol for j in range(len(Tg))] for i in range(len(Kg))]), dc,
        ql.BlackVarianceSurface.ConstantExtrapolation, ql.BlackVarianceSurface.ConstantExtrapolation)
    surf.setInterpolation("bicubic")  # la bilineal por omisión da volatilidad local basura
    surf.enableExtrapolation()
    h = ql.BlackVolTermStructureHandle(surf)
    lv = ql.NoExceptLocalVolSurface(h, dom, fgn, q, sigma)  # Dupire; con varianza local negativa usa sigma
    # Dupire de QuantLib tabulado en la malla del Monte Carlo (15x más rápido que al vuelo, ~0.5 % de diferencia)
    times = [T * i / STEPS for i in range(STEPS)]
    times[0] = 1e-3 * T / STEPS
    ks = list(spot * np.exp(np.linspace(-5, 5, LV_STRIKES) * sigma * np.sqrt(T)))
    tab = np.array([[lv.localVol(t, k, True) for t in times] for k in ks])
    local = ql.LocalVolTermStructureHandle(ql.FixedLocalVolSurface(today, times, ks, ql.Matrix(tab.tolist()), dc))
    return dom, ql.GeneralizedBlackScholesProcess(q, fgn, dom, h, local), sigma, ks, tab


def _mc(proc, sigma, ks, tab, sides, T, n):
    """Probabilidad de no tocar (sin descontar) y su error estándar; `sides` = [(barrera, +1 si queda arriba del spot)]."""
    rsg = ql.GaussianRandomSequenceGenerator(ql.UniformRandomSequenceGenerator(STEPS, ql.UniformRandomGenerator(SEED)))
    pg = ql.GaussianPathGenerator(proc, T, STEPS, rsg, False)
    X = np.array([list(pg.next().value()) for _ in range(n)])  # copia: el Path es un búfer reutilizado
    sig = sigma if tab is None else np.column_stack([np.interp(X[:, i], ks, tab[:, i]) for i in range(STEPS)])
    s2, surv, alive = sig ** 2 * T / STEPS, 1.0, True
    for b, side in sides:
        lb = np.log(X / b)
        # Única matemática propia: P(cruzar b entre nodos) = exp(-2 ln(X_i/b) ln(X_i+1/b) / (s^2 dt)), puente browniano
        # (Beaglehole-Dybvig-Zhou 1997; Glasserman 2004, 6.4). Un nodo al otro lado da probabilidad > 1 y supervivencia < 0;
        # con los dos extremos del lado muerto da < 1, así que un nodo en la barrera o más allá mata la trayectoria aparte.
        # QuantLib 1.42 (Python) no da la probabilidad de cruce ni Monte Carlo de doble barrera; el no touch de una barrera podría replicarse con MCBarrierEngine y un diferencial de knock-outs, y se eligió un solo motor para los dos productos.
        surv = surv - np.exp(-2 * lb[:, :-1] * lb[:, 1:] / s2)
        alive = alive & (side * lb < 0).all(axis=1)
    v = np.maximum(surv, 0).prod(axis=1) * alive
    return v.mean(), v.std(ddof=1) / n ** 0.5


def _analytic(p, proc):
    """Valor descontado por unidad de pago con los motores analíticos de QuantLib (proceso plano)."""
    today = ql.Settings.instance().evaluationDate
    if "barrier" in p:
        b, up = p["barrier"], p["barrier_type"] == "up"
        o = ql.BarrierOption(ql.Barrier.UpOut if up else ql.Barrier.DownOut, b, 0.0,
                             ql.CashOrNothingPayoff(ql.Option.Put if up else ql.Option.Call, b, 1.0),
                             ql.AmericanExercise(today, today + p["days"], True))  # pago al vencimiento
        e = ql.AnalyticBinaryBarrierEngine(proc)
    else:
        o = ql.DoubleBarrierOption(ql.DoubleBarrier.KnockOut, p["lower"], p["upper"], 0.0,
                                   ql.CashOrNothingPayoff(ql.Option.Call, p["lower"], 1.0),
                                   ql.EuropeanExercise(today + p["days"]))
        e = ql.AnalyticDoubleBarrierBinaryEngine(proc)
    o.setPricingEngine(e)
    try:
        return o.NPV()
    except RuntimeError:  # la serie del double no touch no converge con corredores muy anchos
        raise ApiError(400, "La fórmula cerrada no converge con este corredor; use Monte Carlo", _sides(p)[0][0])


def _value(p, mkt, spot, dvol, n):
    """(valor signado en MXN, error estándar en MXN, probabilidad de no tocar)."""
    k, T = p["payout_mxn"] * (1 if p["side"] == "buy" else -1), p["days"] / 365.0
    dom, proc, sigma, ks, tab = _build(p, mkt, spot, dvol)
    df = dom.discount(T)
    u, se = (_analytic(p, proc) / df, 0.0) if p["method"] == "analytic" else _mc(
        proc, sigma, ks, tab, [(p[f], side) for f, side, _ in _sides(p)], T, n)
    return k * df * u, abs(k) * df * se, u


def _result(p, mkt):
    spot = mkt.spot
    pv, se, u = _value(p, mkt, spot, 0.0, PATHS)
    try:
        ref = pv if p["method"] == "analytic" else _value(dict(p, model="flat", method="analytic"), mkt, spot, 0.0, 0)[0]
    except ApiError:  # sin referencia; con method=analytic ya falló arriba
        ref = None
    h = min(SPOT_BUMP * spot, min(abs(spot - p[f]) for f, *_ in _sides(p)) / 2)  # el choque nunca alcanza una barrera
    delta = (_value(p, mkt, spot + h, 0.0, PATHS)[0] - pv) / h
    vega = _value(p, mkt, spot, VOL_BUMP, PATHS)[0] - pv
    return {
        "product": p["product"], "currency": "MXN", "pv": pv, "pv_mxn": pv,
        "risk": {"delta": delta, "vega": vega}, "cashflows": None,
        "details": {
            "price_pct": 100 * abs(pv) / p["payout_mxn"], "no_touch_probability": u, "std_error": se,
            "paths": 0 if p["method"] == "analytic" else PATHS, "model": p["model"], "method": p["method"],
            "analytic_flat_pv": ref,
        },
    }


def _price(p, mkt):
    sides, spot = _sides(p), mkt.spot
    for f, s, label in sides:
        if s * (spot - p[f]) >= 0:
            raise ApiError(400, "El spot %.4f ya tocó la %s" % (spot, label), f)
    bars = [p[f] for f, *_ in sides]
    # de barrera a barrera; con una sola, hasta el espejo del spot (en logaritmo), que lo deja al centro
    spots = np.linspace(*sorted(bars if len(bars) == 2 else [bars[0], spot * spot / bars[0]]), CHART_POINTS)
    with _LOCK:
        out = _result(p, mkt)
        out["details"]["chart"] = {
            "strike": None, "barriers": bars, "spots": spots.tolist(),
            "pnl": [_value(p, mkt, float(s), 0.0, CHART_PATHS)[0] for s in spots],
        }
    return out


PRODUCTS = {
    "fx_no_touch": Product("fx_no_touch", _nt_validate, _price, None, None),
    "fx_double_no_touch": Product("fx_double_no_touch", _dnt_validate, _price, None, None),
}
