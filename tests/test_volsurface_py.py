"""Python-side tests for the VolSurface bindings (P4c).

Imports the *real* built qfpy from build/src. Skipped gracefully when the module
is not importable (e.g. bindings not built), so the `pytests` target stays green
without a build. Mirrors the harness in tests/test_calibration_py.py.
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
        if not hasattr(real, "VolSurface"):
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


@unittest.skipUnless(_HAVE_QFPY, "built qfpy extension not importable")
class VolSurfaceBindings(unittest.TestCase):
    SPOT, R, Q = 100.0, 0.03, 0.01
    STRIKES = [90.0, 100.0, 110.0]
    MATS = [0.5, 1.0, 2.0]
    TRUE_VOLS = [
        [0.24, 0.20, 0.22],
        [0.25, 0.21, 0.23],
        [0.26, 0.22, 0.24],
    ]

    def test_grid_recovery_at_pillars(self):
        s = qfpy.VolSurface(self.MATS, self.STRIKES, self.TRUE_VOLS)
        for i, T in enumerate(self.MATS):
            for j, K in enumerate(self.STRIKES):
                self.assertAlmostEqual(s.vol(K, T), self.TRUE_VOLS[i][j], places=10)

    def test_to_grid_roundtrip(self):
        s = qfpy.VolSurface(self.MATS, self.STRIKES, self.TRUE_VOLS)
        mats, strikes, vols = s.to_grid()
        self.assertEqual(list(mats), self.MATS)
        self.assertEqual(list(strikes), self.STRIKES)
        self.assertEqual([list(r) for r in vols], self.TRUE_VOLS)

    def _bs_price(self, K, T, vol):
        opt = qfpy.OptionParams()
        opt.spot = self.SPOT
        opt.strike = K
        opt.riskFreeRate = self.R
        opt.dividendYield = self.Q
        opt.volatility = vol
        opt.maturity = T
        opt.type = qfpy.OptionType.Call
        opt.exercise = qfpy.ExerciseType.European
        return qfpy.black_scholes(opt)["price"]

    def test_from_quotes_roundtrip(self):
        quotes = []
        for i, T in enumerate(self.MATS):
            for j, K in enumerate(self.STRIKES):
                px = self._bs_price(K, T, self.TRUE_VOLS[i][j])
                quotes.append(qfpy.OptionQuote(K, T, qfpy.OptionType.Call, px))
        s = qfpy.VolSurface.from_quotes(self.SPOT, self.R, self.Q, quotes)
        for i, T in enumerate(self.MATS):
            for j, K in enumerate(self.STRIKES):
                self.assertAlmostEqual(s.vol(K, T), self.TRUE_VOLS[i][j], delta=1e-4)

    def test_set_on_environment_prefers_surface(self):
        curve = qfpy.YieldCurve(self.MATS, [self.R] * len(self.MATS),
                                qfpy.InterpolationMethod.Linear)
        env = qfpy.MarketEnvironment(curve)
        env.set_volatility("AAPL", 0.99)   # flat vol the surface must override
        s = qfpy.VolSurface(self.MATS, self.STRIKES, self.TRUE_VOLS)
        env.set_vol_surface("AAPL", s)
        self.assertTrue(env.has_vol_surface("AAPL"))
        self.assertAlmostEqual(env.volatility("AAPL", 90.0, 0.5), 0.24, places=10)
        # Scalar accessor untouched.
        self.assertAlmostEqual(env.volatility("AAPL"), 0.99, places=10)

    def test_surface_from_heston_smoke(self):
        h = qfpy.HestonParams()
        h.v0, h.kappa, h.theta, h.sigma, h.rho = 0.04, 1.5, 0.05, 0.4, -0.6
        s = qfpy.surface_from_heston(h, self.SPOT, self.R, self.Q,
                                     self.STRIKES, self.MATS)
        # A calibrated Heston surface should produce sensible positive equity vols
        # and exhibit skew (OTM put vol above ATM at a given maturity).
        atm = s.vol(100.0, 1.0)
        otm_put = s.vol(90.0, 1.0)
        self.assertGreater(atm, 0.0)
        self.assertLess(atm, 1.0)
        self.assertGreater(otm_put, atm)


if __name__ == "__main__":
    unittest.main()
