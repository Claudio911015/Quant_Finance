"""Python-side tests for qfxva.simulate_exposure (EPE / ENE / PFE per monitor date).

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
        if not hasattr(real_qfxva, "simulate_exposure"):
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


def _quarterly(maturity):
    out, t = [], 0.25
    while t <= maturity + 1e-9:
        out.append(t)
        t += 0.25
    return out


def _curve():
    return qfpy.YieldCurve([0.5, 1.0, 2.0, 5.0, 10.0], [0.04] * 5,
                           qfpy.InterpolationMethod.Linear)


def _netting_set():
    ns = qfxva.NettingSet()
    ns.add(notional=1e6, fixed_rate=0.05, maturity=5.0, frequency=1.0,
           swap_type=qfxva.SwapType.Payer)
    ns.add(notional=5e5, fixed_rate=0.03, maturity=3.0, frequency=2.0,
           swap_type=qfxva.SwapType.Receiver)
    return ns


@unittest.skipUnless(_HAVE_BUILD, "built qfpy/qfxva extensions not importable")
class SimulateExposure(unittest.TestCase):
    def setUp(self):
        self.curve = _curve()
        self.hw = qfpy.HullWhite(a=0.1, sigma=0.01, curve=self.curve)
        self.ns = _netting_set()
        self.params = qfxva.SimParams(n_paths=300, monitor_dates=_quarterly(5.0), seed=42)

    def test_epe_and_ene_match_cva_calculator_profile(self):
        credit = qfxva.FlatHazardRate(lambda_=0.02)
        env = qfpy.MarketEnvironment(self.curve)
        cva = qfxva.CVACalculator(self.hw, credit, lgd=0.6, params=self.params).compute(self.ns, env)
        pts = qfxva.simulate_exposure(self.hw, self.ns, self.params)

        self.assertEqual(len(pts), len(cva.profile))
        for pt, step in zip(pts, cva.profile):
            self.assertIsInstance(pt, qfxva.ExposurePoint)
            self.assertEqual(pt.t, step.t)
            self.assertAlmostEqual(pt.epe, step.epe, delta=1e-12 * max(1.0, abs(step.epe)))
            self.assertAlmostEqual(pt.ene, step.ene, delta=1e-12 * max(1.0, abs(step.ene)))

    def test_pfe_is_non_negative_and_grows_with_quantile(self):
        p50 = qfxva.simulate_exposure(self.hw, self.ns, self.params, pfe_quantile=0.5)
        p95 = qfxva.simulate_exposure(self.hw, self.ns, self.params)  # default 0.95
        p99 = qfxva.simulate_exposure(self.hw, self.ns, self.params, 0.99)

        self.assertTrue(any(pt.pfe > 0.0 for pt in p99))
        for a, b, c in zip(p50, p95, p99):
            self.assertGreaterEqual(a.pfe, 0.0)
            self.assertGreaterEqual(b.pfe, a.pfe)
            self.assertGreaterEqual(c.pfe, b.pfe)

    def test_invalid_arguments_raise_value_error(self):
        for q in (0.0, 1.0):
            with self.assertRaises(ValueError):
                qfxva.simulate_exposure(self.hw, self.ns, self.params, pfe_quantile=q)
        bad = qfxva.SimParams(n_paths=0, monitor_dates=_quarterly(1.0), seed=42)
        with self.assertRaises(ValueError):
            qfxva.simulate_exposure(self.hw, self.ns, bad)


if __name__ == "__main__":
    unittest.main()
