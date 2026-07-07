"""Python-side smoke tests for the qf::risk ScenarioEngine bindings (P2c).

Imports the *real* built qfpy from build/src. Skipped gracefully when the module
is not importable (e.g. bindings not built), so the `pytests` target stays green
without a build.
"""
import glob
import importlib
import os
import sys
import unittest

# Load the *real* built qfpy extension. A compiled extension only exports
# PyInit_qfpy, so it must import under the name "qfpy". But tests/test_app.py
# injects a *fake* qfpy into sys.modules that would shadow the real bindings under
# `unittest discover`. So: temporarily displace whatever is registered as "qfpy",
# import the real .so from the build tree, then restore the previous entry so
# test_app.py's fake environment is left exactly as it was.
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
        if not hasattr(real, "ScenarioEngine"):
            return None
        return real
    finally:
        # Restore the prior sys.modules["qfpy"] (the fake) for other test modules.
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
class ScenarioEngineBindings(unittest.TestCase):
    def _env(self):
        curve = qfpy.YieldCurve(
            [0.5, 1.0, 2.0, 5.0, 10.0],
            [0.03, 0.035, 0.04, 0.05, 0.06],
            qfpy.InterpolationMethod.Linear,
        )
        return qfpy.MarketEnvironment(curve), curve

    def test_curve_pillar_accessors_and_bump(self):
        env, curve = self._env()
        self.assertEqual(list(curve.maturities()), [0.5, 1.0, 2.0, 5.0, 10.0])
        self.assertEqual(len(curve.rates()), 5)
        up = curve.parallel_bump(10.0)  # +10 bp
        self.assertAlmostEqual(up.zero_rate(5.0), curve.zero_rate(5.0) + 0.001, places=10)

    def test_parallel_dv01_positive_for_bond(self):
        env, _ = self._env()
        bond = qfpy.Bond(100.0, 0.05, 10, 2.0)
        engine = qfpy.ScenarioEngine()  # default curve, 1 bp
        dv01 = engine.parallel_dv01(bond, env)
        self.assertGreater(dv01, 0.0)

    def test_key_rate_ladder_one_rung_per_pillar(self):
        env, curve = self._env()
        bond = qfpy.Bond(100.0, 0.05, 10, 2.0)
        engine = qfpy.ScenarioEngine()
        ladder = engine.key_rate_dv01s(bond, env)
        self.assertEqual(len(ladder), len(curve.maturities()))
        self.assertAlmostEqual(ladder[0].maturity, 0.5, places=10)
        # Ladder sums to the parallel DV01 under Linear interpolation.
        total = sum(r.dv01 for r in ladder)
        self.assertAlmostEqual(total, engine.parallel_dv01(bond, env), places=6)

    def test_run_scenario_and_named_shocks(self):
        env, _ = self._env()
        bond = qfpy.Bond(100.0, 0.05, 10, 2.0)
        engine = qfpy.ScenarioEngine()
        res = engine.run_scenario(bond, env, [10.0] * 5, "up10bp")
        self.assertEqual(res.label, "up10bp")
        self.assertAlmostEqual(res.pnl, res.scenario_pv - res.base_pv, places=10)
        self.assertLess(res.pnl, 0.0)  # rates up -> bond falls
        shock = engine.parallel_shock(bond, env, 100.0)
        self.assertLess(shock.pnl, 0.0)

    def test_key_rate_dataframe(self):
        try:
            import pandas  # noqa: F401
        except Exception:
            self.skipTest("pandas not available")
        env, curve = self._env()
        bond = qfpy.Bond(100.0, 0.05, 10, 2.0)
        engine = qfpy.ScenarioEngine()
        df = qfpy.key_rate_dv01_dataframe(engine, bond, env)
        self.assertEqual(list(df.columns), ["maturity", "dv01"])
        self.assertEqual(len(df), len(curve.maturities()))


if __name__ == "__main__":
    unittest.main()
