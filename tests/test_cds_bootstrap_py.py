"""Python-side tests for qfxva.bootstrap_cds_curve / cds_value / PiecewiseHazardCurve.

Imports the real built qfpy and qfxva from build/src and skips when they are not
importable, so the `pytests` target stays green without a build.
"""
import glob
import importlib
import os
import sys
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_real_modules():
    build_dirs = [os.path.join(_REPO, "build", "src"), os.path.join(_REPO, "build")]
    if not all(any(glob.glob(os.path.join(d, name + "*.so")) for d in build_dirs)
               for name in ("qfpy", "qfxva")):
        return None, None
    saved = {n: sys.modules.pop(n, None) for n in ("qfpy", "qfxva")}
    added_paths = []
    for d in build_dirs:
        if os.path.isdir(d) and d not in sys.path:
            sys.path.insert(0, d)
            added_paths.append(d)
    try:
        real_qfpy = importlib.import_module("qfpy")
        real_qfxva = importlib.import_module("qfxva")
        if not hasattr(real_qfxva, "bootstrap_cds_curve"):
            return None, None
        return real_qfpy, real_qfxva
    finally:
        for n, mod in saved.items():
            if mod is not None:
                sys.modules[n] = mod
            else:
                sys.modules.pop(n, None)
        for d in added_paths:
            try:
                sys.path.remove(d)
            except ValueError:
                pass


try:
    qfpy, qfxva = _load_real_modules()
    _HAVE_BUILD = qfxva is not None
except Exception:  # pragma: no cover - environment without built bindings
    qfpy = qfxva = None
    _HAVE_BUILD = False


def _discount():
    return qfpy.YieldCurve([0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0],
                           [0.0680, 0.0685, 0.0690, 0.0700, 0.0705, 0.0710, 0.0715, 0.0720, 0.0730],
                           qfpy.InterpolationMethod.Linear)


def _quotes(pairs):
    return [qfxva.CdsQuote(tenor_years=t, spread=s) for t, s in pairs]


@unittest.skipUnless(_HAVE_BUILD, "built qfpy/qfxva extensions not importable")
class CdsBootstrap(unittest.TestCase):
    def setUp(self):
        self.discount = _discount()
        self.pairs = [(1.0, 0.0050), (2.0, 0.0080), (3.0, 0.0110),
                      (5.0, 0.0150), (7.0, 0.0180), (10.0, 0.0200)]

    def test_every_input_quote_reprices_to_zero(self):
        quotes = _quotes(self.pairs)
        curve = qfxva.bootstrap_cds_curve(quotes, 0.40, self.discount)
        self.assertIsInstance(curve, qfxva.PiecewiseHazardCurve)
        self.assertIsInstance(curve, qfxva.ICreditCurve)
        self.assertEqual(len(curve.hazards()), len(quotes))
        notional = 1.0e6
        for q in quotes:
            value = qfxva.cds_value(q, 0.40, curve, self.discount, notional)
            self.assertLessEqual(abs(value), 1e-8 * notional)

    def test_curve_accessors_and_survival(self):
        curve = qfxva.PiecewiseHazardCurve(times=[1.0, 3.0], hazards=[0.02, 0.05])
        self.assertEqual(list(curve.times()), [1.0, 3.0])
        self.assertEqual(list(curve.hazards()), [0.02, 0.05])
        self.assertEqual(curve.hazard_rate(0.5), 0.02)
        self.assertEqual(curve.hazard_rate(2.0), 0.05)
        self.assertAlmostEqual(curve.survival_probability(2.0), 0.9323938199059483, places=14)  # exp(-0.07)
        self.assertEqual(curve.survival_probability(0.0), 1.0)

    def test_negative_hazard_raises_value_error(self):
        quotes = _quotes([(1.0, 0.0300), (2.0, 0.0050)])
        with self.assertRaises(ValueError) as ctx:
            qfxva.bootstrap_cds_curve(quotes, 0.40, self.discount)
        self.assertIn("negative hazard", str(ctx.exception))

    def test_invalid_input_raises_value_error(self):
        with self.assertRaises(ValueError):
            qfxva.bootstrap_cds_curve([], 0.40, self.discount)
        with self.assertRaises(ValueError):
            qfxva.bootstrap_cds_curve(_quotes([(2.0, 0.01), (1.0, 0.012)]), 0.40, self.discount)
        with self.assertRaises(ValueError):
            qfxva.bootstrap_cds_curve(_quotes([(1.0, 0.01)]), 1.0, self.discount)
        with self.assertRaises(ValueError):
            qfxva.PiecewiseHazardCurve([1.0, 2.0], [0.01])

    def test_bootstrapped_curve_drives_cva_calculator(self):
        curve = qfxva.bootstrap_cds_curve(_quotes(self.pairs), 0.40, self.discount)
        hw = qfpy.HullWhite(a=0.1, sigma=0.01, curve=self.discount)
        ns = qfxva.NettingSet()
        ns.add(notional=1e6, fixed_rate=0.05, maturity=5.0, frequency=1.0,
               swap_type=qfxva.SwapType.Payer)
        params = qfxva.SimParams(n_paths=200, monitor_dates=[0.25 * k for k in range(1, 21)], seed=7)
        result = qfxva.CVACalculator(hw, curve, 0.60, params).compute(ns, qfpy.MarketEnvironment(self.discount))
        self.assertGreaterEqual(result.cva, 0.0)
        self.assertTrue(result.cva == result.cva)  # finite, not NaN


if __name__ == "__main__":
    unittest.main()
