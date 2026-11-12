"""H21: CVA, DVA y FVA se integran sobre una malla más fina que el perfil que se publica.

La malla mensual con el extremo derecho sesgaba el CVA ~3 % a la baja y daba CVA 0 a un swap de 28 días. Aquí se
prueba la malla de integración (`xva.integration_days`) contra la integración diaria con las mismas trayectorias
(el motor simula por días: cambiar la malla no cambia las trayectorias), con las cotas de la decisión: CVA a menos
de 0.5 % y DVA y FVA a menos de 1 % en el portafolio sembrado y en el caso del hallazgo; el swap de 28 días con CVA
positivo y a menos de 2 %. Y que lo publicado (perfil, máximos) sigue siendo mensual.
"""
from datetime import date, timedelta

import pytest

from desk.api import db, market, portfolio
from desk.api import fixings as fixing_store
from desk.api.risk import credit_curves, xva

SNAP = "MX-DEMO"
AS_OF = date(2026, 11, 10)
NAMES = ("Banco Alfa (sintético)", "Banco Beta (sintético)", "Banco Gamma (sintético)")
EJEMPLO = "Banco Ejemplo"


def _qfxva():
    return xva._qfxva()


def _rel(a, b):
    return abs(a / b - 1.0)


def _integrate(conn, name, flat=None):
    """`{malla: XvaResult}` de la contraparte `name` con la malla mensual, la de integración y la diaria, mismas
    trayectorias. `flat = (intensidad contraparte, intensidad propia, LGD)` sustituye las curvas de crédito."""
    qfxva = _qfxva()
    mkt = market.load_context(conn, SNAP)
    trades = xva.live_by_counterparty(conn, mkt)[name]
    spec, included, _, _ = xva.build_set(trades, mkt, fixing_store.load_all(conn))
    params = xva.load_params(conn)
    model = xva.model_from_snapshot(mkt)[0]
    if flat is None:
        curve, recovery, _ = xva.credit_for(conn, name, mkt)
        own, own_recovery, _ = xva.own_credit(conn, mkt)
        lgd, own_lgd = 1.0 - recovery, 1.0 - own_recovery
    else:
        curve, own = qfxva.FlatHazardRate(lambda_=flat[0]), qfxva.FlatHazardRate(lambda_=flat[1])
        lgd = own_lgd = flat[2]
    report = xva.report_days(mkt.as_of, xva._last_maturity(trades, included))
    grids = {"mensual": report, "integración": xva.integration_days(report, spec), "diaria": list(range(report[-1] + 1))}
    out = {}
    for label, days in grids.items():
        profile = xva.engine(mkt, model, params, days).simulate([spec])[0]
        out[label] = qfxva.compute_xva(profile, curve, lgd, own, own_lgd, params["funding_spread"])
    return out


# ------------------------------------------------------------------ la malla

def test_integration_days_hold_the_required_dates():
    qfxva = _qfxva()
    swap = qfxva.RateSwapSpec(qfxva.SwapCurrency.MXN, 1e8, 0.07, True, -10, [18, 46, 74], 1.01)   # envejecido
    xccy = qfxva.XccySwapSpec(
        notional_usd=1e6, fx_rate=18.6, spread=0.0, start_days=45, pay_days=[73, 101, 129],
        accrued_factor_usd=1.0, accrued_factor_mxn=1.0, pay_usd=True, initial_exchange=True, final_exchange=True,
    )
    spec = qfxva.NettingSetSpec(swaps=[swap], xccys=[xccy])
    report = [0, 30, 61, 91, 122, 152]
    days = xva.integration_days(report, spec)
    assert days[0] == 0 and days[-1] == report[-1] and days == sorted(set(days))
    required = set(report) | set(range(0, report[-1] + 1, xva.INTEGRATION_STEP))
    for pay in (18, 46, 74, 73, 101, 129):      # pagos y vencimientos (74 y 129), y el día anterior a cada uno
        required |= {pay - 1, pay}
    required |= {44, 45}                        # intercambio inicial futuro del xccy
    assert set(days) == required
    assert -11 not in days and -10 not in days  # el inicio pasado del swap envejecido no es una fecha


def test_the_seeded_trades_maturities_are_integration_dates(app):
    conn = db.connect(app.config["DESK_DB"])
    try:
        mkt = market.load_context(conn, SNAP)
        fixings = fixing_store.load_all(conn)
        for name, trades in xva.live_by_counterparty(conn, mkt).items():
            spec, included, _, _ = xva.build_set(trades, mkt, fixings)
            report = xva.report_days(mkt.as_of, xva._last_maturity(trades, included))
            days = set(xva.integration_days(report, spec))
            for t in trades:
                if t["id"] in {i["id"] for i in included}:
                    maturity = (t["maturity_date"] - mkt.as_of).days
                    assert {maturity - 1, maturity} <= days, (name, t["id"])
    finally:
        conn.close()


# ------------------------------------------------------------------ exactitud frente a la malla diaria

@pytest.mark.parametrize("name", NAMES)
def test_seeded_counterparties_integrate_within_the_bounds_of_the_daily_grid(app, name):
    conn = db.connect(app.config["DESK_DB"])
    try:
        x = _integrate(conn, name)
    finally:
        conn.close()
    assert _rel(x["integración"].cva, x["diaria"].cva) < 0.005
    assert _rel(x["integración"].dva, x["diaria"].dva) < 0.01
    assert _rel(x["integración"].fva, x["diaria"].fva) < 0.01
    # la prueba tiene dientes: la malla mensual sola sesgaba cada uno más de 1 % a la baja
    assert x["mensual"].cva < x["diaria"].cva and _rel(x["mensual"].cva, x["diaria"].cva) > 0.01


def _banco_ejemplo(conn):
    """El caso del hallazgo H21: IRS TIIE-F de 200 millones envejecido y XCCY de 10 millones de USD con ambos
    intercambios, 2 años, con curvas de CDS propias y de la contraparte."""
    rows, day = ["index,date,value"], date(2026, 8, 10)
    while day < AS_OF:
        if day.weekday() < 5:
            rows.append("TIIE-F,%s,0.07" % day.isoformat())
        day += timedelta(days=1)
    fixing_store.import_csv(conn, "\n".join(rows))
    portfolio.create_trade(conn, {
        "product": "irs", "counterparty": EJEMPLO, "trade_date": "2026-08-10",
        "params": {"curve": "TIIE-F", "side": "payer", "notional": 200e6, "periods": 26, "fixed_rate": 0.072}})
    portfolio.create_trade(conn, {
        "product": "xccy_swap", "counterparty": EJEMPLO, "trade_date": "2026-11-10",
        "params": {"side": "pay_usd", "notional_usd": 10e6, "periods": 26, "fx_rate": 18.2, "spread": 0.0005,
                   "exchange": "both"}})
    for entity, spreads in ((EJEMPLO, (90, 100, 110, 125, 135, 150)), (credit_curves.OWN, (70, 80, 90, 105, 115, 125))):
        credit_curves.put_curve(conn, entity, {
            "recovery": 0.4,
            "quotes": [{"tenor_years": t, "spread": s / 1e4} for t, s in zip((1, 2, 3, 5, 7, 10), spreads)]})
    conn.commit()


def test_the_finding_case_integrates_within_the_bounds_of_the_daily_grid(app):
    conn = db.connect(app.config["DESK_DB"])
    try:
        _banco_ejemplo(conn)
        x = _integrate(conn, EJEMPLO)
    finally:
        conn.close()
    assert _rel(x["integración"].cva, x["diaria"].cva) < 0.005
    assert _rel(x["integración"].dva, x["diaria"].dva) < 0.01
    assert _rel(x["integración"].fva, x["diaria"].fva) < 0.01
    # el hallazgo: la malla mensual daba el CVA ~3 % por debajo
    assert 0.02 < 1.0 - x["mensual"].cva / x["diaria"].cva < 0.05


def test_a_28_day_swap_has_positive_cva(app):
    conn = db.connect(app.config["DESK_DB"])
    try:
        portfolio.create_trade(conn, {
            "product": "irs", "counterparty": EJEMPLO, "trade_date": AS_OF.isoformat(),
            "params": {"curve": "TIIE-F", "side": "receiver", "notional": 100e6, "periods": 1, "fixed_rate": 0.075}})
        conn.commit()
        x = _integrate(conn, EJEMPLO, flat=(0.02, 0.02, 0.6))
    finally:
        conn.close()
    assert x["mensual"].cva == 0.0                       # el hallazgo: el único mes cae después del pago
    assert x["integración"].cva > 0.0
    assert _rel(x["integración"].cva, x["diaria"].cva) < 0.02
    assert _rel(x["integración"].fva, x["diaria"].fva) < 0.01
    # el DVA de este receptor en el dinero vale centésimas de peso: se compara en valor absoluto
    assert abs(x["integración"].dva - x["diaria"].dva) < 0.01


# ------------------------------------------------------------------ lo publicado sigue siendo mensual

def _monthly_dates(conn, name):
    mkt = market.load_context(conn, SNAP)
    trades = xva.live_by_counterparty(conn, mkt)[name]
    spec, included, _, _ = xva.build_set(trades, mkt, fixing_store.load_all(conn))
    return [(AS_OF + timedelta(days=d)).isoformat() for d in xva.report_days(mkt.as_of, xva._last_maturity(trades, included))]


def test_published_profiles_and_maxima_are_the_monthly_ones(app, client):
    assert client.put("/api/xva/params", json={"n_paths": 100}).status_code == 200
    conn = db.connect(app.config["DESK_DB"])
    try:
        expected = {name: _monthly_dates(conn, name) for name in NAMES}
    finally:
        conn.close()
    body = client.get("/api/xva?snapshot=%s" % SNAP).get_json()
    assert xva.INTEGRATION_NOTE in body["assumptions"]
    for cp in body["counterparties"]:
        assert [p["date"] for p in cp["profile"]] == expected[cp["counterparty"]]
        assert cp["epe_max_mxn"] == max(p["epe_mxn"] for p in cp["profile"])
        assert cp["pfe_max_mxn"] == max(p["pfe_mxn"] for p in cp["profile"])
    exposure = client.get("/api/credit/exposure?snapshot=%s" % SNAP).get_json()
    for cp in exposure["counterparties"]:
        assert [p["date"] for p in cp["profile"]] == expected[cp["counterparty"]]

    request = {"snapshot": SNAP, "counterparty": NAMES[1], "product": "irs", "trade_date": AS_OF.isoformat(),
               "params": {"curve": "TIIE-F", "side": "payer", "notional": 1e8, "periods": 13}}
    inc = client.post("/api/xva/incremental", json=request).get_json()
    after = [p["date"] for p in inc["profile"]]
    assert after == expected[NAMES[1]]                   # la candidata (13 periodos) no alarga el conjunto
    assert inc["before"]["epe_max_mxn"] == max(p["epe_before_mxn"] for p in inc["profile"])
    assert inc["after"]["epe_max_mxn"] == max(p["epe_after_mxn"] for p in inc["profile"])


def test_report_days_is_the_monthly_grid_of_the_published_profile():
    # el día 0 y las fechas mensuales hasta el primer mes que alcanza el último vencimiento (2027-02-10)
    assert xva.report_days(AS_OF, date(2027, 2, 10)) == [0, 30, 61, 92]
    assert xva.report_days(AS_OF, date(2027, 2, 11)) == [0, 30, 61, 92, 120]
