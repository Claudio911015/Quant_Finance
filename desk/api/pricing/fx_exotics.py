"""No touch y double no touch USDMXN: Monte Carlo con barrera continua sobre trayectorias de QuantLib."""
import numpy as np
import QuantLib as ql

from desk.api.errors import ApiError
from desk.api.pricing.base import MAX_DAYS, Product
from desk.api.validation import MAX_AMOUNT, MAX_PRICE, choice, integer, number

PATHS, STEPS, SEED, LV_STRIKES = 20000, 10, 42, 41
CHART_POINTS, CHART_PATHS = 21, 2000
SPOT_BUMP = VOL_BUMP = 0.01


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
    """(campo, +1 si la barrera queda arriba del spot) de cada barrera del producto."""
    if "barrier" in p:
        return [("barrier", 1 if p["barrier_type"] == "up" else -1)]
    return [("lower", -1), ("upper", 1)]


def _build(p, mkt, spot, dvol):
    """Mercado -> QuantLib: (descuento MXN, proceso, vol plana, malla de strikes, tabla de vol local)."""
    T, a = p["days"] / 365.0, mkt.as_of
    today, dc = ql.Date(a.day, a.month, a.year), ql.Actual365Fixed()
    ql.Settings.instance().evaluationDate = today

    def curve(c):
        ts = list(c.maturities())
        dates = [today] + [today + int(round(t * 365)) for t in ts]
        k = ql.DiscountCurve(dates, [1.0] + [c.discount_factor(t) for t in ts], dc)
        k.enableExtrapolation()  # los pilares llegan a ~10 años y los plazos válidos a 50
        return ql.YieldTermStructureHandle(k)

    dom, fgn = curve(mkt.curves[mkt.mxn_discount]), curve(mkt.curves["SOFR"])
    q, sigma = ql.QuoteHandle(ql.SimpleQuote(spot)), mkt.surface.vol(spot, T) + dvol
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


def _mc(proc, sigma, ks, tab, bars, T, n):
    """Probabilidad de no tocar (sin descontar) y su error estándar."""
    rsg = ql.GaussianRandomSequenceGenerator(ql.UniformRandomSequenceGenerator(STEPS, ql.UniformRandomGenerator(SEED)))
    pg = ql.GaussianPathGenerator(proc, T, STEPS, rsg, False)
    X = np.array([list(pg.next().value()) for _ in range(n)])  # copia: el Path es un búfer reutilizado
    sig = sigma if tab is None else np.column_stack([np.interp(X[:, i], ks, tab[:, i]) for i in range(STEPS)])
    s2, surv, alive = sig ** 2 * T / STEPS, 1.0, True
    for b in bars:
        lb = np.log(X / b)
        # Única matemática propia: P(cruzar b entre nodos) = exp(-2 ln(X_i/b) ln(X_i+1/b) / (s^2 dt)), puente browniano
        # (Beaglehole-Dybvig-Zhou 1997; Glasserman 2004, 6.4); QuantLib no trae Monte Carlo de barrera en efectivo
        surv, alive = surv - np.exp(-2 * lb[:, :-1] * lb[:, 1:] / s2), alive & (lb * lb[:, :1] > 0).all(axis=1)
    v = alive * np.clip(surv, 0, 1).prod(axis=1)
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
    if p["method"] == "analytic":
        u, se = _analytic(p, proc) / df, 0.0
    else:
        u, se = _mc(proc, sigma, ks, tab, [p[f] for f, _ in _sides(p)], T, n)
    return k * df * u, abs(k) * df * se, u


def _result(p, mkt):
    spot = mkt.spot
    pv, se, u = _value(p, mkt, spot, 0.0, PATHS)
    try:
        ref = _value(dict(p, model="flat", method="analytic"), mkt, spot, 0.0, 0)[0]
    except ApiError:  # sin referencia; con method=analytic ya falló arriba
        ref = None
    delta = (_value(p, mkt, spot * (1 + SPOT_BUMP), 0.0, PATHS)[0] - pv) / (SPOT_BUMP * spot)
    vega = _value(p, mkt, spot, VOL_BUMP, PATHS)[0] - pv
    return {
        "product": p["product"], "currency": "MXN", "pv": pv, "pv_mxn": pv,
        "risk": {"delta": delta, "vega": vega}, "cashflows": None,
        "details": {
            "price_pct": 100 * abs(pv) / p["payout_mxn"], "no_touch_probability": u, "std_error": se,
            "paths": 0 if p["method"] == "analytic" else PATHS, "model": p["model"], "method": p["method"],
            "analytic_flat_pv": ref, "smile_adjustment": None if ref is None else (pv - ref if p["model"] == "smile" else 0.0),
        },
    }


def _price(p, mkt):
    sides, spot = _sides(p), mkt.spot
    for f, s in sides:
        if s * (spot - p[f]) >= 0:
            raise ApiError(400, "El spot %.4f ya tocó la barrera '%s'" % (spot, f), f)
    out = _result(p, mkt)
    bars = [p[f] for f, _ in sides]
    lo, hi = sorted(bars if len(bars) == 2 else [bars[0], bars[0] * (0.85 if sides[0][1] > 0 else 1.15)])
    spots = np.linspace(lo, hi, CHART_POINTS + 2)[1:-1]
    out["details"]["chart"] = {
        "strike": None, "barriers": bars, "spots": spots.tolist(),
        "pnl": [_value(p, mkt, float(s), 0.0, CHART_PATHS)[0] for s in spots],
    }
    return out


PRODUCTS = {
    "fx_no_touch": Product("fx_no_touch", _nt_validate, _price, None, None),
    "fx_double_no_touch": Product("fx_double_no_touch", _dnt_validate, _price, None, None),
}
