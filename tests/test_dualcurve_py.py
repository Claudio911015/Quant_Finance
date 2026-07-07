"""Python-side tests for the dual-curve swap bindings (P5c).

Verifies capabilities that were impossible before P5:
  * both swap families can now be passed to the bound ScenarioEngine (they gained
    the Instrument base class);
  * dual-curve pricing and par-rate statics are reachable from Python.

Imports the *real* built qfpy from build/src, skipping gracefully when it is not
importable so the `pytests` target stays green without a build.
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
        if not hasattr(real, "CurveKeys"):
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


def _curve(mod, basis_bp=0.0):
    b = basis_bp * 1e-4
    return mod.YieldCurve(
        [0.5, 1.0, 2.0, 5.0, 10.0],
        [0.030 + b, 0.032 + b, 0.035 + b, 0.038 + b, 0.040 + b],
        mod.InterpolationMethod.Linear,
    )


@unittest.skipUnless(_HAVE_QFPY, "built qfpy extension not importable")
class DualCurveBindings(unittest.TestCase):
    def _env(self, proj_basis_bp):
        env = qfpy.MarketEnvironment(_curve(qfpy))          # "default"
        env.add_curve("USD.OIS", _curve(qfpy))
        env.add_curve("USD.3M", _curve(qfpy, proj_basis_bp))
        return env

    def test_curve_keys_roundtrip(self):
        keys = qfpy.CurveKeys("USD.OIS", "USD.3M")
        self.assertEqual(keys.discount_key, "USD.OIS")
        self.assertEqual(keys.projection_key, "USD.3M")
        self.assertFalse(keys.keys_equal())
        self.assertTrue(qfpy.CurveKeys().keys_equal())

    def test_irs_flows_through_scenario_engine(self):
        # Impossible before P5: the IRS binding did not declare the Instrument base.
        env = self._env(25.0)
        irs = qfpy.InterestRateSwap(
            1_000_000, 0.035, 5.0, 2.0, qfpy.SwapType.Payer,
            qfpy.CurveKeys("USD.OIS", "USD.3M"),
        )
        ois = qfpy.ScenarioEngine("USD.OIS").parallel_dv01(irs, env)
        proj = qfpy.ScenarioEngine("USD.3M").parallel_dv01(irs, env)
        self.assertGreater(abs(ois), 1.0)
        self.assertGreater(abs(proj), 1.0)

    def test_scheduled_swap_flows_through_scenario_engine(self):
        env = self._env(20.0)
        times = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
        fixed = qfpy.ScheduledLeg.make_fixed(
            1_000_000, 0.035, times, qfpy.CurveKeys("USD.OIS", "USD.OIS"))
        floating = qfpy.ScheduledLeg.make_floating(
            1_000_000, 0.0, times, qfpy.CurveKeys("USD.OIS", "USD.3M"))
        swap = qfpy.ScheduledSwap(fixed, floating)
        dv01 = qfpy.ScenarioEngine("USD.3M").parallel_dv01(swap, env)
        self.assertGreater(abs(dv01), 1.0)

    def test_basis_spread_raises_payer_npv_and_par_rate(self):
        env = self._env(30.0)  # projection 30 bp above OIS
        single = qfpy.InterestRateSwap(1_000_000, 0.035, 5.0, 2.0, qfpy.SwapType.Payer)
        dual = qfpy.InterestRateSwap(
            1_000_000, 0.035, 5.0, 2.0, qfpy.SwapType.Payer,
            qfpy.CurveKeys("USD.OIS", "USD.3M"))
        self.assertGreater(dual.npv(env), single.npv(env))

        # Hand-computed basis adjustment: floating PV lifts by ≈ N·0.0030·annuity_OIS.
        annuity = qfpy.InterestRateSwap.annuity(5.0, 2.0, env, "USD.OIS")
        approx = 1_000_000 * 0.0030 * annuity
        self.assertAlmostEqual(dual.npv(env) - single.npv(env), approx,
                               delta=approx * 0.05)

        # Dual par rate exceeds the OIS single-curve par rate by ≈ the basis.
        ois_env = qfpy.MarketEnvironment(_curve(qfpy))  # OIS data under "default"
        single_par = qfpy.InterestRateSwap.par_rate(5.0, 2.0, ois_env)
        dual_par = qfpy.InterestRateSwap.par_rate(5.0, 2.0, env, "USD.OIS", "USD.3M")
        self.assertGreater(dual_par, single_par)
        self.assertAlmostEqual(dual_par - single_par, 30e-4, delta=30e-4 * 0.10)

    def test_curve_keys_accessor_is_a_copy_not_an_internal_reference(self):
        # Regression: curve_keys() once returned reference_internal on def_readwrite fields,
        # so mutating the returned object silently repointed the swap's internal pricing
        # keys (and broke/altered subsequent npv()). It must hand back a detached copy.
        env = self._env(25.0)
        irs = qfpy.InterestRateSwap(
            1_000_000, 0.035, 5.0, 2.0, qfpy.SwapType.Payer,
            qfpy.CurveKeys("USD.OIS", "USD.3M"),
        )
        npv_before = irs.npv(env)
        # Attempt to vandalise the internal keys through the accessor.
        irs.curve_keys().projection_key = "NOPE"
        irs.curve_keys().discount_key = "NOPE"
        # The swap must be unaffected: keys unchanged and NPV identical.
        self.assertEqual(irs.curve_keys().projection_key, "USD.3M")
        self.assertEqual(irs.curve_keys().discount_key, "USD.OIS")
        self.assertEqual(irs.npv(env), npv_before)

        # Same guarantee for ScheduledLeg.
        leg = qfpy.ScheduledLeg.make_floating(
            1_000_000, 0.0, [0.5, 1.0], qfpy.CurveKeys("USD.OIS", "USD.3M"))
        leg.curve_keys().projection_key = "NOPE"
        self.assertEqual(leg.curve_keys().projection_key, "USD.3M")

    def test_instrument_pv_equals_npv(self):
        # The P5a wart fix, visible from Python via the Instrument.pv() base method.
        env = self._env(0.0)
        irs = qfpy.InterestRateSwap(1_000_000, 0.035, 5.0, 2.0, qfpy.SwapType.Payer)
        self.assertAlmostEqual(irs.pv(env), irs.npv(env), places=6)


if __name__ == "__main__":
    unittest.main()
