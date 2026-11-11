"""Python-side tests for the qfpy bindings the QF Desk backend relies on.

One case per exposed symbol: build it, value it, check the return type. Imports the
*real* built qfpy from build/src and skips when it is not importable, so the `pytests`
target stays green without a build.
"""
import glob
import importlib
import os
import sys
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_real_qfpy():
    build_dirs = [os.path.join(_REPO, "build", "src"), os.path.join(_REPO, "build")]
    if not any(glob.glob(os.path.join(d, "qfpy*.so")) for d in build_dirs):
        return None
    saved = sys.modules.pop("qfpy", None)
    added_paths = []
    for d in build_dirs:
        if os.path.isdir(d) and d not in sys.path:
            sys.path.insert(0, d)
            added_paths.append(d)
    try:
        real = importlib.import_module("qfpy")
        if not hasattr(real, "bootstrap_ois"):
            return None
        return real
    finally:
        if saved is not None:
            sys.modules["qfpy"] = saved
        else:
            sys.modules.pop("qfpy", None)
        for d in added_paths:
            try:
                sys.path.remove(d)
            except ValueError:
                pass


try:
    qfpy = _load_real_qfpy()
    _HAVE_QFPY = qfpy is not None
except Exception:  # pragma: no cover - environment without built bindings
    qfpy = None
    _HAVE_QFPY = False


def _quotes(rates):
    """Deposit at 28d plus par OIS at 1y and 2y."""
    t = qfpy.OisQuoteType
    return [qfpy.OisQuote(28, rates[0], t.Deposit),
            qfpy.OisQuote(364, rates[1], t.Ois),
            qfpy.OisQuote(728, rates[2], t.Ois)]


def _env():
    """TIIE-F (28d periods) and SOFR (annual) curves, USDMXN spot and a vol surface."""
    tiie = qfpy.bootstrap_ois(_quotes([0.0705, 0.0675, 0.0660]), 28)
    sofr = qfpy.bootstrap_ois(_quotes([0.0420, 0.0400, 0.0390]), 365)
    env = qfpy.MarketEnvironment()
    env.add_curve("TIIE-F", tiie)
    env.add_curve("SOFR", sofr)
    env.add_curve("default", tiie)
    env.set_spot("USDMXN", 18.60)
    env.set_vol_surface("USDMXN", qfpy.VolSurface(
        [30 / 365.0, 365 / 365.0], [17.0, 18.6, 20.0],
        [[0.12, 0.11, 0.12], [0.13, 0.12, 0.13]]))
    return env, tiie, sofr


@unittest.skipUnless(_HAVE_QFPY, "built qfpy extension not importable")
class DeskBindings(unittest.TestCase):
    def test_day_count_convention_enum(self):
        d = qfpy.DayCountConvention
        for name in ("ACT_360", "ACT_365", "ACT_ACT_ISDA", "THIRTY_360"):
            self.assertTrue(hasattr(d, name), name)

    def test_ois_quote_and_type(self):
        self.assertTrue(hasattr(qfpy.OisQuoteType, "Deposit"))
        self.assertTrue(hasattr(qfpy.OisQuoteType, "Ois"))
        q = qfpy.OisQuote(364, 0.0675, qfpy.OisQuoteType.Ois)
        self.assertEqual(q.days, 364)
        self.assertAlmostEqual(q.rate, 0.0675)
        self.assertEqual(q.type, qfpy.OisQuoteType.Ois)

    def test_bootstrap_ois_returns_curve_with_one_pillar_per_quote(self):
        curve = qfpy.bootstrap_ois(_quotes([0.0705, 0.0675, 0.0660]), 28)
        self.assertIsInstance(curve, qfpy.YieldCurve)
        self.assertEqual(len(curve.maturities()), 3)
        self.assertAlmostEqual(curve.maturities()[1], 364 / 365.0)

    def test_bootstrap_ois_accepts_dcc_and_method(self):
        curve = qfpy.bootstrap_ois(
            _quotes([0.0705, 0.0675, 0.0660]), 28,
            qfpy.DayCountConvention.ACT_365, qfpy.InterpolationMethod.LogLinear)
        self.assertIsInstance(curve, qfpy.YieldCurve)

    def test_bootstrap_ois_rejects_single_quote(self):
        with self.assertRaises(ValueError):
            qfpy.bootstrap_ois([qfpy.OisQuote(364, 0.0675, qfpy.OisQuoteType.Ois)], 28)

    def test_ois_payment_days(self):
        self.assertEqual(qfpy.ois_payment_days(100, 28), [28, 56, 84, 100])

    def test_ois_swap_at_par_rate_has_zero_npv(self):
        env, _, _ = _env()
        probe = qfpy.OisSwap(1e6, 0.05, 728, 28, qfpy.SwapType.Payer, "TIIE-F")
        par = probe.par_rate(env)
        self.assertIsInstance(par, float)
        swap = qfpy.OisSwap(1e6, par, 728, 28, qfpy.SwapType.Payer, "TIIE-F")
        self.assertAlmostEqual(swap.npv(env), 0.0, delta=1e-4)
        self.assertAlmostEqual(swap.pv(env), swap.npv(env))   # Instrument base

    def test_ois_swap_reprices_the_quote_it_was_bootstrapped_from(self):
        env, _, _ = _env()
        swap = qfpy.OisSwap(1e6, 0.0660, 728, 28, qfpy.SwapType.Payer, "TIIE-F",
                            qfpy.DayCountConvention.ACT_360)
        self.assertAlmostEqual(swap.npv(env), 0.0, delta=1e-3)

    def test_ois_swap_annuity_and_cash_flows(self):
        env, _, _ = _env()
        swap = qfpy.OisSwap(1e6, 0.07, 728, 28, qfpy.SwapType.Receiver, "TIIE-F")
        self.assertGreater(swap.annuity(env), 0.0)
        flows = swap.cash_flows(env)
        self.assertEqual(len(flows), len(qfpy.ois_payment_days(728, 28)))
        self.assertIsInstance(flows[0], qfpy.OisCashFlow)
        for name in ("pay_days", "pay_time", "accrual", "fixed_amount", "float_amount",
                     "net_amount", "discount_factor", "present_value"):
            self.assertTrue(hasattr(flows[0], name), name)
        self.assertEqual(flows[0].pay_days, 28)
        self.assertAlmostEqual(sum(f.present_value for f in flows), swap.npv(env), places=6)

    def test_ois_swap_payer_and_receiver_are_opposite(self):
        env, _, _ = _env()
        pay = qfpy.OisSwap(1e6, 0.07, 364, 28, qfpy.SwapType.Payer, "TIIE-F")
        rec = qfpy.OisSwap(1e6, 0.07, 364, 28, qfpy.SwapType.Receiver, "TIIE-F")
        self.assertAlmostEqual(pay.npv(env), -rec.npv(env), places=6)

    def test_fx_forward(self):
        env, _, _ = _env()
        self.assertTrue(hasattr(qfpy.FxSide, "Buy"))
        self.assertTrue(hasattr(qfpy.FxSide, "Sell"))
        fwd = qfpy.FxForward(1e6, 19.0, 182, qfpy.FxSide.Buy)
        rate = fwd.forward_rate(env)
        self.assertGreater(rate, 18.60)                      # MXN rates above USD rates
        self.assertIsInstance(fwd.npv(env), float)
        self.assertGreater(fwd.delta(env), 0.0)
        self.assertAlmostEqual(fwd.pv(env), fwd.npv(env))    # Instrument base
        at_fwd = qfpy.FxForward(1e6, rate, 182, qfpy.FxSide.Buy)
        self.assertAlmostEqual(at_fwd.npv(env), 0.0, delta=1e-4)
        sell = qfpy.FxForward(1e6, 19.0, 182, qfpy.FxSide.Sell, "USDMXN", "TIIE-F", "SOFR")
        self.assertAlmostEqual(sell.npv(env), -fwd.npv(env), places=6)

    def test_fx_option_and_greeks(self):
        env, _, _ = _env()
        opt = qfpy.FxOption(1e6, 18.6, 182, qfpy.OptionType.Call, qfpy.FxSide.Buy)
        g = opt.greeks(env)
        self.assertIsInstance(g, qfpy.FxOptionGreeks)
        for name in ("price", "delta", "gamma", "vega", "forward", "vol"):
            self.assertIsInstance(getattr(g, name), float, name)
        self.assertGreater(g.price, 0.0)
        self.assertAlmostEqual(opt.npv(env), g.price, places=6)
        self.assertAlmostEqual(opt.pv(env), g.price, places=6)   # Instrument base
        self.assertGreater(g.vol, 0.0)
        short = qfpy.FxOption(1e6, 18.6, 182, qfpy.OptionType.Call, qfpy.FxSide.Sell)
        self.assertAlmostEqual(short.greeks(env).price, -g.price, places=6)

    def test_cap_floor(self):
        _, tiie, _ = _env()
        self.assertTrue(hasattr(qfpy.CapFloorType, "Cap"))
        self.assertTrue(hasattr(qfpy.CapFloorType, "Floor"))
        cap = qfpy.CapFloor(qfpy.CapFloorType.Cap, 1e6, 0.065, 1.5, 4.0, 0.05, 0.01)
        floor = qfpy.CapFloor(qfpy.CapFloorType.Floor, 1e6, 0.065, 1.5, 4.0, 0.05, 0.01,
                              qfpy.DayCountConvention.ACT_360)
        self.assertGreater(cap.price(tiie), 0.0)
        self.assertGreater(floor.price(tiie), 0.0)
        env = qfpy.MarketEnvironment(tiie)
        self.assertAlmostEqual(cap.pv(env), cap.price(tiie), places=6)   # Instrument base

    def test_swaption(self):
        _, tiie, _ = _env()
        self.assertTrue(hasattr(qfpy.SwaptionType, "Payer"))
        self.assertTrue(hasattr(qfpy.SwaptionType, "Receiver"))
        payer = qfpy.Swaption(qfpy.SwaptionType.Payer, 1e6, 0.066, 1.0, 1.0, 2.0, 0.05, 0.01)
        recv = qfpy.Swaption(qfpy.SwaptionType.Receiver, 1e6, 0.066, 1.0, 1.0, 2.0, 0.05, 0.01,
                             qfpy.DayCountConvention.ACT_360)
        self.assertGreater(payer.price(tiie), 0.0)
        self.assertGreater(recv.price(tiie), 0.0)
        env = qfpy.MarketEnvironment(tiie)
        self.assertAlmostEqual(payer.pv(env), payer.price(tiie), places=6)   # Instrument base

    def test_swaption_type_does_not_shadow_swap_type(self):
        self.assertIs(qfpy.Payer, qfpy.SwapType.Payer)
        self.assertIsNot(qfpy.SwaptionType.Payer, qfpy.SwapType.Payer)

    def test_bond_cash_flow_schedule_and_dcc(self):
        _, tiie, _ = _env()
        bond = qfpy.Bond(1000.0, 0.05, 4, 2.0)
        sched = bond.cash_flow_schedule()
        self.assertEqual([t for t, _ in sched], [0.5, 1.0, 1.5, 2.0])
        self.assertEqual([c for _, c in sched], [25.0, 25.0, 25.0, 1025.0])
        bond360 = qfpy.Bond(1000.0, 0.05, 4, 2.0, qfpy.DayCountConvention.ACT_360)
        self.assertGreater(bond360.cash_flow_schedule()[0][1], 25.0)   # longer accrual
        self.assertGreater(bond360.price(tiie), bond.price(tiie))
        self.assertGreater(qfpy.Bond(1000.0, 0.05, 4).price(tiie), 0.0)   # legacy 3-arg form

    def test_delta_normal_var(self):
        var = qfpy.delta_normal_var([100.0], [2.0], [[1.0]], 0.99, 1.0)
        self.assertAlmostEqual(var, 2.3263478740 * 200.0, places=3)
        self.assertAlmostEqual(
            qfpy.delta_normal_var([100.0], [2.0], [[1.0]], 0.99, 4.0), 2 * var, places=6)
        hedged = qfpy.delta_normal_var([100.0, -100.0], [1.0, 1.0],
                                       [[1.0, 1.0], [1.0, 1.0]], 0.99, 1.0)
        self.assertAlmostEqual(hedged, 0.0, places=9)
        with self.assertRaises(ValueError):
            qfpy.delta_normal_var([1.0, 2.0], [1.0], [[1.0]], 0.99, 1.0)


if __name__ == "__main__":
    unittest.main()
