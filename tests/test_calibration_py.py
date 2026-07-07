"""Python-side round-trip test for the Heston calibration bindings (P3c).

Imports the *real* built qfpy from build/src. Skipped gracefully when the module
is not importable (e.g. bindings not built), so the `pytests` target stays green
without a build. Mirrors the harness in tests/test_scenario_py.py.
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
        if not hasattr(real, "HestonCalibrator"):
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
class HestonCalibrationBindings(unittest.TestCase):
    SPOT, R, Q = 100.0, 0.03, 0.0
    STRIKES = [90.0, 100.0, 110.0]
    MATS = [0.5, 1.0, 2.0]

    def _truth(self):
        h = qfpy.HestonParams()
        h.v0, h.kappa, h.theta, h.sigma, h.rho = 0.04, 1.5, 0.05, 0.4, -0.6
        return h

    def _quote_tuples(self, truth):
        quotes = []
        for T in self.MATS:
            for K in self.STRIKES:
                opt = qfpy.OptionParams()
                opt.spot = self.SPOT
                opt.strike = K
                opt.riskFreeRate = self.R
                opt.dividendYield = self.Q
                opt.volatility = 0.0
                opt.maturity = T
                opt.type = qfpy.OptionType.Call
                opt.exercise = qfpy.ExerciseType.European
                px = qfpy.heston_price(opt, truth)
                quotes.append((K, T, qfpy.OptionType.Call, px))
        return quotes

    def test_calibrate_heston_dataframe_friendly_roundtrip(self):
        truth = self._truth()
        quotes = self._quote_tuples(truth)
        res = qfpy.calibrate_heston(self.SPOT, self.R, self.Q, quotes)
        self.assertTrue(res.converged)
        self.assertLess(res.rmse, 1e-2)
        self.assertEqual(len(res.per_quote_errors), len(quotes))
        self.assertAlmostEqual(res.params.v0, truth.v0, delta=5e-3)
        self.assertAlmostEqual(res.params.theta, truth.theta, delta=5e-3)

    def test_params_drive_make_heston_engine(self):
        truth = self._truth()
        quotes = self._quote_tuples(truth)
        res = qfpy.calibrate_heston(self.SPOT, self.R, self.Q, quotes)

        # The fitted params must plug straight into the existing engine factory.
        opt = qfpy.OptionParams()
        opt.spot = self.SPOT
        opt.strike = 100.0
        opt.riskFreeRate = self.R
        opt.dividendYield = self.Q
        opt.volatility = 0.0
        opt.maturity = 1.0
        opt.type = qfpy.OptionType.Call
        opt.exercise = qfpy.ExerciseType.European
        engine = qfpy.EngineFactory.make_heston_engine(opt, res.params)
        curve = qfpy.YieldCurve([0.5, 1.0, 2.0], [self.R, self.R, self.R],
                                qfpy.InterpolationMethod.Linear)
        env = qfpy.MarketEnvironment(curve)
        price = engine.price(env)
        self.assertGreater(price, 0.0)

    def test_calibrator_class_api(self):
        truth = self._truth()
        quotes = [qfpy.OptionQuote(K, T, qfpy.OptionType.Call, px)
                  for (K, T, _, px) in self._quote_tuples(truth)]
        guess = qfpy.HestonParams()
        guess.v0, guess.kappa, guess.theta, guess.sigma, guess.rho = \
            0.05, 1.2, 0.06, 0.5, -0.4
        calib = qfpy.HestonCalibrator(self.SPOT, self.R, self.Q)
        res = calib.calibrate(quotes, guess)
        self.assertEqual(len(res.per_quote_errors), len(quotes))
        self.assertLess(res.rmse, 1e-2)


if __name__ == "__main__":
    unittest.main()
