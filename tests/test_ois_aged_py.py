"""Python-side tests for the aged OIS swap and compound_overnight bindings (QF Desk, corte 2).

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
        if not hasattr(real, "compound_overnight"):
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

N = 1e8


def _df(curve, day):
    return 1.0 if day == 0 else curve.discount_factor(day / 365.0)


def _curve_26():
    """TIIE-F: 28d deposit and par OIS every 28 days up to 728 days (26 quotes)."""
    t = qfpy.OisQuoteType
    quotes = [qfpy.OisQuote(28 * k, 0.0700 + 0.0004 * k, t.Deposit if k == 1 else t.Ois)
              for k in range(1, 27)]
    return qfpy.bootstrap_ois(quotes, 28)


def _env(curve):
    env = qfpy.MarketEnvironment()
    env.add_curve("TIIE-F", curve)
    return env


@unittest.skipUnless(_HAVE_QFPY, "built qfpy extension not importable")
class OisAgedBindings(unittest.TestCase):
    def test_compound_overnight(self):
        self.assertEqual(qfpy.compound_overnight([], []), 1.0)
        self.assertAlmostEqual(qfpy.compound_overnight([0.07], [1]), 1 + 0.07 / 360, places=15)
        self.assertAlmostEqual(qfpy.compound_overnight([0.07], [1], 365.0), 1 + 0.07 / 365, places=15)
        self.assertAlmostEqual(qfpy.compound_overnight([0.07, 0.08], [1, 2], day_base=360.0),
                               (1 + 0.07 / 360) * (1 + 0.08 * 2 / 360), places=15)
        with self.assertRaises(ValueError):
            qfpy.compound_overnight([0.07, 0.07], [1])
        with self.assertRaises(ValueError):
            qfpy.compound_overnight([0.07], [0])

    def test_new_constructor_at_start_zero_matches_the_old_one(self):
        curve = _curve_26()
        env = _env(curve)
        for side in (qfpy.SwapType.Payer, qfpy.SwapType.Receiver):
            old = qfpy.OisSwap(N, 0.0690, 364, 28, side, "TIIE-F")
            new = qfpy.OisSwap(N, 0.0690, 0, qfpy.ois_payment_days(364, 28), 1.0, side, "TIIE-F")
            for a, b in ((new.npv(env), old.npv(env)),
                         (new.par_rate(env), old.par_rate(env)),
                         (new.annuity(env), old.annuity(env))):
                self.assertLessEqual(abs(a - b), 1e-12 * abs(b))
            for fa, fb in zip(new.cash_flows(env), old.cash_flows(env)):
                self.assertEqual(fa.pay_days, fb.pay_days)
                self.assertLessEqual(abs(fa.present_value - fb.present_value),
                                     1e-12 * abs(fb.present_value))

    def test_new_constructor_validates(self):
        with self.assertRaises(ValueError):
            qfpy.OisSwap(N, 0.07, 0, [28, 28], 1.0, qfpy.SwapType.Payer, "TIIE-F")
        with self.assertRaises(ValueError):
            qfpy.OisSwap(N, 0.07, 0, [28], 1.01, qfpy.SwapType.Payer, "TIIE-F")

    def test_aged_swap_matches_original_value_rebased_to_the_new_date(self):
        # R3: age a 364/28 payer by tau days with D0-forward fixings; the aged swap on the
        # shifted curve is worth (npv_D0 - PV_D0 of the flows already paid) / DF0(tau).
        c0 = _curve_26()
        env0 = _env(c0)
        par = qfpy.OisSwap(N, 0.0, 364, 28, qfpy.SwapType.Payer, "TIIE-F").par_rate(env0)
        k = par + 0.0010
        swap0 = qfpy.OisSwap(N, k, 364, 28, qfpy.SwapType.Payer, "TIIE-F")
        pay0 = qfpy.ois_payment_days(364, 28)
        rows0 = swap0.cash_flows(env0)
        npv0 = swap0.npv(env0)

        for tau in (28, 14):
            first = next(i for i, d in enumerate(pay0) if d > tau)
            period_start = pay0[first - 1] if first else 0
            fixings = [(_df(c0, d) / _df(c0, d + 1) - 1.0) * 360.0 for d in range(period_start, tau)]
            accrued = qfpy.compound_overnight(fixings, [1] * len(fixings))
            settled = sum(r.present_value for r in rows0[:first])

            mats, zeros, pay1 = [], [], []
            for d in pay0[first:]:
                t1 = (d - tau) / 365.0
                mats.append(t1)
                zeros.append((c0.zero_rate(d / 365.0) * d / 365.0
                              - c0.zero_rate(tau / 365.0) * tau / 365.0) / t1)
                pay1.append(d - tau)
            env1 = _env(qfpy.YieldCurve(mats, zeros, qfpy.InterpolationMethod.Linear))

            aged = qfpy.OisSwap(N, k, period_start - tau, pay1, accrued,
                                qfpy.SwapType.Payer, "TIIE-F")
            expected = (npv0 - settled) / _df(c0, tau)
            self.assertAlmostEqual(aged.npv(env1), expected, delta=1e-6 * N, msg="tau=%d" % tau)


if __name__ == "__main__":
    unittest.main()
