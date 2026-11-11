"""Python-side tests for the MXN-USD discount bootstrap bindings (QF Desk, corte 3).

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
        if not hasattr(real, "bootstrap_xccy_discount"):
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

SPOT = 18.60

# MX-DEMO quotes (desk/api/seed_market.py): (days, rate); the first one is the 1-day deposit.
_TIIE_F = [(1, 0.0700), (28, 0.0698), (84, 0.0692), (168, 0.0685), (364, 0.0675),
           (728, 0.0670), (1092, 0.0672), (1820, 0.0680), (2548, 0.0690), (3640, 0.0705)]
_SOFR = [(1, 0.0390), (30, 0.0385), (91, 0.0380), (182, 0.0375), (365, 0.0370),
         (730, 0.0355), (1095, 0.0350), (1825, 0.0355), (2555, 0.0365), (3650, 0.0380)]
_FORWARDS = [(28, 0.0438), (84, 0.1317), (168, 0.2637), (364, 0.5745)]
_BASIS = [(728, -0.0010), (1092, -0.0012), (1820, -0.0015), (2548, -0.0017), (3640, -0.0020)]


def _ois_curve(rows, period_days):
    quotes = [qfpy.OisQuote(d, r, qfpy.OisQuoteType.Deposit if i == 0 else qfpy.OisQuoteType.Ois)
              for i, (d, r) in enumerate(rows)]
    return qfpy.bootstrap_ois(quotes, period_days)


def _forwards(rows):
    return [qfpy.FxForwardQuote(d, p) for d, p in rows]


def _basis(rows):
    return [qfpy.XccyBasisQuote(d, s) for d, s in rows]


@unittest.skipUnless(_HAVE_QFPY, "built qfpy extension not importable")
class XccyBootstrapBindings(unittest.TestCase):
    def setUp(self):
        self.usd = _ois_curve(_SOFR, 365)
        self.proj = _ois_curve(_TIIE_F, 28)

    def _env(self, xccy):
        env = qfpy.MarketEnvironment()
        env.add_curve("SOFR", self.usd)
        env.add_curve("TIIE-F", self.proj)
        env.add_curve("MXN-USD", xccy)
        env.set_spot("USDMXN", SPOT)
        return env

    def test_quote_classes_expose_their_fields(self):
        f = qfpy.FxForwardQuote(28, 0.0438)
        self.assertEqual((f.days, f.points), (28, 0.0438))
        b = qfpy.XccyBasisQuote(728, -0.001)
        self.assertEqual((b.days, b.spread), (728, -0.001))

    def test_r1_every_forward_and_every_basis_swap_reprices(self):
        xccy = qfpy.bootstrap_xccy_discount(_forwards(_FORWARDS), _basis(_BASIS), SPOT,
                                            self.usd, self.proj)
        env = self._env(xccy)
        for days, points in _FORWARDS:
            t = days / 365.0
            self.assertLessEqual(
                abs(SPOT * self.usd.discount_factor(t) / xccy.discount_factor(t) - (SPOT + points)), 1e-8)
            fwd = qfpy.FxForward(1.0, 1.0, days, qfpy.FxSide.Buy, "USDMXN", "MXN-USD", "SOFR")
            self.assertLessEqual(abs(fwd.forward_rate(env) - (SPOT + points)), 1e-8)
        n_usd = 1e6
        for days, spread in _BASIS:
            swap = qfpy.XccySwap(n_usd, SPOT, spread, 0, qfpy.ois_payment_days(days, 28), 1.0, 1.0,
                                 qfpy.XccySide.PayUsd, True, True)
            self.assertLessEqual(abs(swap.npv(env)), 1e-8 * n_usd * SPOT)

    def test_pillars_are_days_over_365_in_quote_order(self):
        xccy = qfpy.bootstrap_xccy_discount(_forwards(_FORWARDS), _basis(_BASIS), SPOT,
                                            self.usd, self.proj)
        days = [d for d, _ in _FORWARDS] + [d for d, _ in _BASIS]
        self.assertEqual(list(xccy.maturities()), [d / 365.0 for d in days])

    def test_negative_basis_lifts_the_mxn_curve_above_tiie_f(self):
        xccy = qfpy.bootstrap_xccy_discount(_forwards(_FORWARDS), _basis(_BASIS), SPOT,
                                            self.usd, self.proj)
        for days, _ in _BASIS:
            t = days / 365.0
            self.assertGreater(xccy.discount_factor(t), self.proj.discount_factor(t))

    def test_r2_parity_forwards_and_zero_basis_reproduce_tiie_f(self):
        parity = []
        for d in (1, 28, 84, 168, 364):
            t = d / 365.0
            parity.append((d, SPOT * self.usd.discount_factor(t) / self.proj.discount_factor(t) - SPOT))
        zero_basis = [(d, 0.0) for d in (728, 1092, 1820, 2548, 3640)]
        xccy = qfpy.bootstrap_xccy_discount(_forwards(parity), _basis(zero_basis), SPOT,
                                            self.usd, self.proj)
        for d in range(1, 3641, 7):
            t = d / 365.0
            self.assertLessEqual(abs(xccy.discount_factor(t) - self.proj.discount_factor(t)), 1e-8)

    def test_optional_arguments_and_validation_errors(self):
        xccy = qfpy.bootstrap_xccy_discount(
            _forwards(_FORWARDS), _basis(_BASIS), SPOT, self.usd, self.proj,
            period_days=28, accrual_dcc=qfpy.DayCountConvention.ACT_360,
            method=qfpy.InterpolationMethod.Linear)
        self.assertEqual(len(xccy.maturities()), len(_FORWARDS) + len(_BASIS))
        with self.assertRaises(ValueError):                       # fewer than two quotes
            qfpy.bootstrap_xccy_discount(_forwards(_FORWARDS[:1]), [], SPOT, self.usd, self.proj)
        with self.assertRaises(ValueError):                       # basis not after the last forward
            qfpy.bootstrap_xccy_discount(_forwards(_FORWARDS), _basis([(364, -0.001)]), SPOT,
                                         self.usd, self.proj)
        with self.assertRaises(ValueError):                       # non-positive spot
            qfpy.bootstrap_xccy_discount(_forwards(_FORWARDS), _basis(_BASIS), 0.0, self.usd, self.proj)
        with self.assertRaises(ValueError):                       # non-positive period
            qfpy.bootstrap_xccy_discount(_forwards(_FORWARDS), _basis(_BASIS), SPOT, self.usd,
                                         self.proj, period_days=0)
        with self.assertRaises(RuntimeError):                     # no root in the search range
            qfpy.bootstrap_xccy_discount(_forwards(_FORWARDS), _basis([(728, 5.0)]), SPOT,
                                         self.usd, self.proj)


if __name__ == "__main__":
    unittest.main()
