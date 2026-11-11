"""Python-side tests for the OisSwap discount-curve key and the XccySwap bindings (QF Desk, corte 3).

Imports the *real* built qfpy from build/src and skips when it is not importable, so the
`pytests` target stays green without a build.
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
        if not hasattr(real, "XccySwap"):
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

N_USD = 1e7
FX = 18.5
SPOT = 18.0


def _curve(base, step):
    """Pillar every 28 days up to 728 days, linear zero rates, t = days / 365."""
    mats = [28.0 * k / 365.0 for k in range(1, 27)]
    zeros = [base + step * k for k in range(1, 27)]
    return qfpy.YieldCurve(mats, zeros, qfpy.InterpolationMethod.Linear)


def _env():
    env = qfpy.MarketEnvironment()
    env.add_curve("SOFR", _curve(0.0400, 0.00015))
    env.add_curve("TIIE-F", _curve(0.0700, 0.00040))
    env.add_curve("MXN-USD", _curve(0.0640, 0.00030))
    env.set_spot("USDMXN", SPOT)
    return env


def _swap(side, spread=0.0, **kw):
    pay = kw.pop("pay", qfpy.ois_payment_days(364, 28))
    return qfpy.XccySwap(N_USD, FX, spread, 0, pay, 1.0, 1.0, side, True, True, **kw)


@unittest.skipUnless(_HAVE_QFPY, "built qfpy extension not importable")
class OisDiscountCurveKey(unittest.TestCase):
    def test_same_curve_under_another_key_matches_the_single_curve_swap(self):
        env = _env()
        env.add_curve("TIIE-F-COPY", _curve(0.0700, 0.00040))   # same pillars, other name
        pay = qfpy.ois_payment_days(364, 28)
        side = qfpy.SwapType.Payer
        for plain, keyed in (
            (qfpy.OisSwap(1e8, 0.0690, 364, 28, side, "TIIE-F"),
             qfpy.OisSwap(1e8, 0.0690, 364, 28, side, "TIIE-F", discount_curve_key="TIIE-F-COPY")),
            (qfpy.OisSwap(1e8, 0.0690, -10, pay, 1.0003, side, "TIIE-F"),
             qfpy.OisSwap(1e8, 0.0690, -10, pay, 1.0003, side, "TIIE-F", discount_curve_key="TIIE-F-COPY")),
        ):
            for a, b in ((keyed.npv(env), plain.npv(env)),
                         (keyed.par_rate(env), plain.par_rate(env)),
                         (keyed.annuity(env), plain.annuity(env))):
                self.assertLessEqual(abs(a - b), 1e-12 * abs(b))
            for fa, fb in zip(keyed.cash_flows(env), plain.cash_flows(env)):
                self.assertLessEqual(abs(fa.present_value - fb.present_value),
                                     1e-12 * abs(fb.present_value))

    def test_accessor_and_a_different_discount_curve(self):
        env = _env()
        plain = qfpy.OisSwap(1e8, 0.0690, 364, 28, qfpy.SwapType.Payer, "TIIE-F")
        other = qfpy.OisSwap(1e8, 0.0690, 364, 28, qfpy.SwapType.Payer, "TIIE-F",
                             discount_curve_key="MXN-USD")
        self.assertEqual(plain.discount_curve_key(), "TIIE-F")
        self.assertEqual(other.discount_curve_key(), "MXN-USD")
        self.assertGreater(abs(other.npv(env) - plain.npv(env)), 1.0)
        # Floating coupons are projected on TIIE-F whatever the discount curve is.
        for fa, fb in zip(other.cash_flows(env), plain.cash_flows(env)):
            self.assertLessEqual(abs(fa.float_amount - fb.float_amount), 1e-12 * abs(fb.float_amount))


@unittest.skipUnless(_HAVE_QFPY, "built qfpy extension not importable")
class XccySwapBindings(unittest.TestCase):
    def test_swap_at_par_spread_is_worth_zero(self):
        env = _env()
        n_mxn = N_USD * FX
        for side in (qfpy.XccySide.PayUsd, qfpy.XccySide.PayMxn):
            par = _swap(side).par_spread(env)
            at_par = _swap(side, spread=par)
            self.assertLess(abs(at_par.npv(env)), 1e-8 * n_mxn)
            self.assertAlmostEqual(at_par.par_spread(env), par, places=12)
        self.assertAlmostEqual(_swap(qfpy.XccySide.PayUsd).notional_mxn(), n_mxn, places=6)

    def test_sides_are_mirror_images(self):
        env = _env()
        a = _swap(qfpy.XccySide.PayUsd, 0.0015).npv(env)
        b = _swap(qfpy.XccySide.PayMxn, 0.0015).npv(env)
        self.assertLessEqual(abs(a + b), 1e-12 * abs(a))

    def test_cash_flows_are_accessible_and_sum_to_npv(self):
        env = _env()
        swap = _swap(qfpy.XccySide.PayUsd, 0.0015)
        rows = swap.cash_flows(env)
        pay = qfpy.ois_payment_days(364, 28)
        self.assertEqual(len(rows), 2 * (len(pay) + 2))
        first = rows[0]
        self.assertEqual((first.leg, first.kind, first.pay_days), ("USD", "exchange", 0))
        self.assertAlmostEqual(first.amount, N_USD, places=6)
        self.assertEqual(rows[1].leg, "MXN")
        self.assertAlmostEqual(rows[1].amount, -N_USD * FX, places=4)
        coupon = rows[3]
        self.assertEqual((coupon.leg, coupon.kind, coupon.pay_days), ("MXN", "coupon", 28))
        self.assertAlmostEqual(coupon.accrual, 28.0 / 360.0, places=12)
        self.assertAlmostEqual(coupon.present_value, coupon.amount * coupon.discount_factor, places=6)
        usd = next(r for r in rows if r.leg == "USD" and r.kind == "coupon")
        self.assertAlmostEqual(usd.present_value_mxn, usd.present_value * SPOT, places=6)
        total = sum(r.present_value_mxn for r in rows)
        self.assertLessEqual(abs(total - swap.npv(env)), 1e-9 * N_USD * FX)

    def test_curve_keys_are_configurable(self):
        env = _env()
        env.add_curve("MXN-ALT", _curve(0.0690, 0.00030))
        default = _swap(qfpy.XccySide.PayUsd, 0.001)
        alt = _swap(qfpy.XccySide.PayUsd, 0.001, mxn_discount_curve="MXN-ALT")
        self.assertGreater(abs(alt.npv(env) - default.npv(env)), 1.0)

    def test_validation_raises_value_error(self):
        side = qfpy.XccySide.PayUsd
        with self.assertRaises(ValueError):
            qfpy.XccySwap(0.0, FX, 0.0, 0, [28], 1.0, 1.0, side, True, True)
        with self.assertRaises(ValueError):
            qfpy.XccySwap(N_USD, 0.0, 0.0, 0, [28], 1.0, 1.0, side, True, True)
        with self.assertRaises(ValueError):
            qfpy.XccySwap(N_USD, FX, 0.0, 0, [28, 28], 1.0, 1.0, side, True, True)
        with self.assertRaises(ValueError):
            qfpy.XccySwap(N_USD, FX, 0.0, 0, [28], 1.01, 1.0, side, True, True)


if __name__ == "__main__":
    unittest.main()
