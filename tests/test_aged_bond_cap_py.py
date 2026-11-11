"""Python-side tests for the aged bond / cap-floor calendars and dual-curve pricing (QF Desk, corte 3).

Imports the *real* built qfpy from build/src and skips when it is not importable, so the
`pytests` target stays green without a build.
"""
import glob
import importlib
import math
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
        if not hasattr(real.Bond, "accrued_interest"):
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


def _rel(a, b):
    return abs(a - b) / max(abs(b), 1e-300)


def _curve():
    return qfpy.YieldCurve([0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
                           [0.04, 0.042, 0.045, 0.05, 0.055, 0.06],
                           qfpy.InterpolationMethod.Linear)


def _flat(r):
    return qfpy.YieldCurve([0.05, 0.5, 1.0, 2.0, 5.0, 10.0], [r] * 6, qfpy.InterpolationMethod.Linear)


@unittest.skipUnless(_HAVE_QFPY, "qfpy is not built")
class AgedBondTests(unittest.TestCase):
    # Values captured with the constructor from periods/frequency BEFORE the explicit calendar
    # existed: the new constructor and the old one must keep giving them (1e-12 relative).
    PRICE = 1022.3384664111719
    DURATION = 3.617744487825848
    CONVEXITY = 13.912814735773349
    YIELD_1010 = 0.05636606851047596

    def test_periods_constructor_is_unchanged(self):
        b = qfpy.Bond(1000.0, 0.06, 8, 2.0)
        c = _curve()
        self.assertLess(_rel(b.price(c), self.PRICE), 1e-12)
        self.assertLess(_rel(b.duration(c), self.DURATION), 1e-12)
        self.assertLess(_rel(b.convexity(c), self.CONVEXITY), 1e-12)
        self.assertLess(_rel(getattr(b, "yield")(1010.0), self.YIELD_1010), 1e-12)
        self.assertEqual(b.accrued_interest(), 0.0)
        self.assertLess(_rel(b.clean_price(c), self.PRICE), 1e-12)

    def test_regular_calendar_reproduces_the_anchors(self):
        b = qfpy.Bond(1000.0, 0.06, 2.0, [(i + 1) / 2.0 for i in range(8)], 0.0)
        c = _curve()
        self.assertLess(_rel(b.price(c), self.PRICE), 1e-12)
        self.assertLess(_rel(b.duration(c), self.DURATION), 1e-12)
        self.assertLess(_rel(b.convexity(c), self.CONVEXITY), 1e-12)
        self.assertLess(_rel(getattr(b, "yield")(1010.0), self.YIELD_1010), 1e-12)
        self.assertEqual(b.accrued_interest(), 0.0)
        sched = b.cash_flow_schedule()
        self.assertEqual([t for t, _ in sched], [(i + 1) / 2.0 for i in range(8)])
        self.assertAlmostEqual(sched[-1][1], 1030.0, places=10)

    def test_accrued_interest_and_clean_price(self):
        c = _curve()
        # Aged 100 days of a semi-annual bond whose pay days are 182.5 days apart.
        pay = [82.5 / 365.0 + 0.5 * k for k in range(3)]
        b = qfpy.Bond(1000.0, 0.06, 2.0, pay, -100.0 / 365.0)
        share = (100.0 / 365.0) / 0.5             # 100 of the 182.5 days of the period have elapsed
        self.assertAlmostEqual(b.accrued_interest(), 30.0 * share, places=10)
        self.assertLess(_rel(b.clean_price(c) + b.accrued_interest(), b.price(c)), 1e-12)
        self.assertLess(b.clean_price(c), b.price(c))

    def test_invalid_calendars_raise_value_error(self):
        for pay, prev in (([], 0.0), ([0.0, 0.5], 0.0), ([0.5, 0.5], 0.0), ([0.5, 1.0], 0.1)):
            with self.assertRaises(ValueError):
                qfpy.Bond(1000.0, 0.06, 2.0, pay, prev)


@unittest.skipUnless(_HAVE_QFPY, "qfpy is not built")
class AgedCapFloorTests(unittest.TestCase):
    # Captured with the constructor from maturity/frequency before the explicit calendar existed.
    CAP_28D = 56999.01300016707       # Cap N=1e8 K=7% 26 x 28d, ACT/360, a=0.03 sigma=0.01
    FLOOR_6M = 1045062.4572669467     # Floor N=1e8 K=5% 3y semi-annual, ACT/365

    def test_periods_constructor_is_unchanged(self):
        c = _curve()
        cap = qfpy.CapFloor(qfpy.CapFloorType.Cap, 1e8, 0.07, 26 * 28 / 365.0, 365 / 28.0,
                            0.03, 0.01, qfpy.DayCountConvention.ACT_360)
        fl = qfpy.CapFloor(qfpy.CapFloorType.Floor, 1e8, 0.05, 3.0, 2.0, 0.03, 0.01)
        self.assertLess(_rel(cap.price(c), self.CAP_28D), 1e-12)
        self.assertLess(_rel(fl.price(c), self.FLOOR_6M), 1e-12)

    def test_even_boundaries_reproduce_the_anchors(self):
        c = _curve()
        cap = qfpy.CapFloor(qfpy.CapFloorType.Cap, 1e8, 0.07, [k * 28 / 365.0 for k in range(27)],
                            0.03, 0.01, qfpy.DayCountConvention.ACT_360)
        fl = qfpy.CapFloor(qfpy.CapFloorType.Floor, 1e8, 0.05, [k * 0.5 for k in range(7)], 0.03, 0.01)
        self.assertLess(_rel(cap.price(c), self.CAP_28D), 1e-12)
        self.assertLess(_rel(fl.price(c), self.FLOOR_6M), 1e-12)
        self.assertAlmostEqual(cap.maturity(), 26 * 28 / 365.0, places=12)

    def test_dropping_the_first_caplet_equals_the_cap_of_the_rest(self):
        c = _curve()
        t = [28.0 * k / 365.0 for k in range(27)]
        mk = lambda b: qfpy.CapFloor(qfpy.CapFloorType.Cap, 1e8, 0.05, b, 0.03, 0.01,
                                     qfpy.DayCountConvention.ACT_360)
        self.assertLess(_rel(mk(t).price(c) - mk(t[:2]).price(c), mk(t[1:]).price(c)), 1e-12)

    def test_price_dual_with_the_same_curve_is_the_plain_price(self):
        c = _curve()
        cap = qfpy.CapFloor(qfpy.CapFloorType.Cap, 1e8, 0.07, [k * 28 / 365.0 for k in range(27)],
                            0.03, 0.01, qfpy.DayCountConvention.ACT_360)
        sw = qfpy.Swaption(qfpy.SwaptionType.Payer, 1e8, 0.05, 1.0, 5.0, 2.0, 0.03, 0.01)
        self.assertLess(_rel(cap.price_dual(c, c), cap.price(c)), 1e-12)
        self.assertLess(_rel(sw.price_dual(c, c), sw.price(c)), 1e-12)

    def test_price_dual_cap_is_caplets_times_the_discount_ratio(self):
        proj, disc = _flat(0.05), _flat(0.048)
        t = [28.0 * k / 365.0 for k in range(27)]
        cap = qfpy.CapFloor(qfpy.CapFloorType.Cap, 1e8, 0.05, t, 0.03, 0.01, qfpy.DayCountConvention.ACT_360)
        expected = 0.0
        for i in range(1, len(t)):
            one = qfpy.CapFloor(qfpy.CapFloorType.Cap, 1e8, 0.05, [t[i - 1], t[i]], 0.03, 0.01,
                                qfpy.DayCountConvention.ACT_360)
            expected += one.price(proj) * disc.discount_factor(t[i]) / proj.discount_factor(t[i])
        self.assertLess(_rel(cap.price_dual(proj, disc), expected), 1e-12)
        self.assertGreater(cap.price_dual(proj, disc), cap.price(proj))

    def test_price_dual_swaption_is_the_price_times_the_annuity_ratio(self):
        proj, disc = _flat(0.05), _flat(0.048)
        sw = qfpy.Swaption(qfpy.SwaptionType.Payer, 1e8, 0.05, 1.0, 5.0, 2.0, 0.03, 0.01)

        def annuity(curve):
            return sum(0.5 * curve.discount_factor(1.0 + k / 2.0) for k in range(1, 11))

        expected = sw.price(proj) * annuity(disc) / annuity(proj)
        self.assertLess(_rel(sw.price_dual(proj, disc), expected), 1e-12)
        self.assertGreater(sw.price_dual(proj, disc), sw.price(proj))

    def test_invalid_boundaries_raise_value_error(self):
        for bounds in ([], [0.5], [-0.1, 0.5], [0.0, 0.5, 0.5], [0.0, math.nan]):
            with self.assertRaises(ValueError):
                qfpy.CapFloor(qfpy.CapFloorType.Cap, 1e6, 0.05, bounds, 0.1, 0.01)


if __name__ == "__main__":
    unittest.main()
