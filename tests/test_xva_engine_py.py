"""Python-side tests for the multi-currency exposure engine (qfxva.ExposureEngine / compute_xva).

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
        if not hasattr(real_qfxva, "ExposureEngine"):
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

_SPOT = 18.6
_MATS = [0.25, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 12.0]


def _curve(rates):
    return qfpy.YieldCurve(_MATS, rates, qfpy.InterpolationMethod.Linear)


def _market(with_basis=True):
    tiie = _curve([0.0690, 0.0700, 0.0705, 0.0710, 0.0715, 0.0720, 0.0725, 0.0728])
    sofr = _curve([0.0365, 0.0368, 0.0370, 0.0372, 0.0375, 0.0380, 0.0385, 0.0388])
    basis = _curve([0.0680, 0.0690, 0.0695, 0.0700, 0.0705, 0.0710, 0.0715, 0.0718]) if with_basis else None
    return qfxva.ExposureMarket(tiie, sofr, _SPOT, basis)


def _model(rho_mxn_usd=0.35):
    return qfxva.ExposureModel(a_mxn=0.05, sigma_mxn=0.01, a_usd=0.03, sigma_usd=0.008, fx_vol=0.12,
                               rho_mxn_usd=rho_mxn_usd, rho_mxn_fx=0.30, rho_usd_fx=-0.10)


def _engine(n_paths=200, seed=7, report_days=None, market=None, model=None):
    report = list(range(0, 1100, 30)) if report_days is None else report_days
    config = qfxva.SimConfig(n_paths=n_paths, seed=seed, pfe_quantile=0.95, report_days=report)
    return qfxva.ExposureEngine(market or _market(), model or _model(), config)


def _mxn_swap(payer=True, fixed=0.0710, notional=300e6):
    return qfxva.RateSwapSpec(currency=qfxva.SwapCurrency.MXN, notional=notional, fixed_rate=fixed,
                              payer=payer, start_days=-10, pay_days=[18 + 28 * k for k in range(39)],
                              accrued_factor=1.0007, csa_discount=True)


def _usd_swap(payer=False, fixed=0.0375, notional=15e6):
    return qfxva.RateSwapSpec(qfxva.SwapCurrency.USD, notional, fixed, payer, -100,
                              [265 + 365 * k for k in range(5)], 1.009)


def _xccy(pay_usd=True, notional_usd=20e6):
    return qfxva.XccySwapSpec(notional_usd=notional_usd, fx_rate=18.20, spread=0.0005, start_days=5,
                              pay_days=[33 + 28 * k for k in range(26)], accrued_factor_usd=1.0,
                              accrued_factor_mxn=1.0, pay_usd=pay_usd, initial_exchange=True,
                              final_exchange=True)


@unittest.skipUnless(_HAVE_BUILD, "built qfpy/qfxva extensions not importable")
class ExposureEngineBindings(unittest.TestCase):
    def setUp(self):
        self.set_a = qfxva.NettingSetSpec(swaps=[_mxn_swap(), _usd_swap()], xccys=[])
        self.set_b = qfxva.NettingSetSpec(swaps=[], xccys=[_xccy()])

    def test_simulate_returns_one_profile_per_set_starting_at_the_desk_value(self):
        engine = _engine()
        profiles = engine.simulate([self.set_a, self.set_b])
        self.assertEqual(len(profiles), 2)
        for prof, spec in zip(profiles, (self.set_a, self.set_b)):
            n = len(prof.days)
            self.assertEqual(prof.days, list(range(0, 1100, 30)))
            self.assertEqual(prof.times[1], 30 / 365.0)
            for series in (prof.times, prof.expected_value, prof.epe, prof.ene, prof.pfe,
                           prof.epe_disc, prof.ene_disc):
                self.assertEqual(len(series), n)
            # V(0) is the sum of the trade values, and the profile starts there (deterministic at t = 0).
            self.assertAlmostEqual(prof.value_at_zero, sum(engine.trade_values_at_zero(spec)),
                                   delta=1e-6 * abs(prof.value_at_zero))
            self.assertAlmostEqual(prof.epe[0], max(prof.value_at_zero, 0.0), delta=1e-6 * abs(prof.value_at_zero))
            self.assertGreater(max(prof.epe), 0.0)
            self.assertGreater(max(prof.pfe), max(prof.epe))
        # trade_values_at_zero: swaps first, then cross currency swaps.
        self.assertEqual(len(engine.trade_values_at_zero(self.set_a)), 2)
        self.assertEqual(len(engine.trade_values_at_zero(self.set_b)), 1)

    def test_path_matrices_are_not_exposed(self):
        prof = _engine(n_paths=20).simulate([self.set_a])[0]
        for name in ("path_disc_pos", "path_disc_neg", "pathDiscPos", "pathDiscNeg"):
            self.assertFalse(hasattr(prof, name), name)

    def test_one_set_does_not_change_anothers_profile(self):
        # The incremental XVA relies on this: "before" and "after" share the paths.
        engine = _engine()
        alone = engine.simulate([self.set_a])[0]
        together = engine.simulate([self.set_b, self.set_a])[1]
        self.assertEqual(alone.epe, together.epe)
        self.assertEqual(alone.epe_disc, together.epe_disc)
        again = engine.simulate([self.set_a])[0]
        self.assertEqual(alone.ene, again.ene)

    def test_compute_xva_follows_the_definitions(self):
        prof = _engine().simulate([self.set_a])[0]
        counterparty = qfxva.PiecewiseHazardCurve([1.0, 3.0, 6.0], [0.010, 0.020, 0.035])
        own = qfxva.FlatHazardRate(0.012)
        lgd_c, lgd_o, spread = 0.6, 0.55, 0.005
        r = qfxva.compute_xva(prof, counterparty, lgd_c, own, lgd_o, spread)

        cva = dva = fva = 0.0
        for i in range(1, len(prof.times)):
            t0, t1 = prof.times[i - 1], prof.times[i]
            sc0, sc1 = counterparty.survival_probability(t0), counterparty.survival_probability(t1)
            so0, so1 = own.survival_probability(t0), own.survival_probability(t1)
            cva += lgd_c * prof.epe_disc[i] * (sc0 - sc1)
            dva += lgd_o * prof.ene_disc[i] * (so0 - so1)
            fva += spread * (prof.epe_disc[i] - prof.ene_disc[i]) * sc1 * so1 * (t1 - t0)
        self.assertAlmostEqual(r.cva, cva, delta=1e-10 * abs(cva))
        self.assertAlmostEqual(r.dva, dva, delta=1e-10 * abs(dva))
        self.assertAlmostEqual(r.fva, fva, delta=1e-10 * abs(fva))
        self.assertAlmostEqual(r.total, r.cva - r.dva + r.fva, delta=1e-9)
        self.assertGreater(r.cva, 0.0)
        self.assertGreater(r.cva_stderr, 0.0)
        self.assertLess(r.cva_stderr, r.cva)
        self.assertGreater(r.dva_stderr, 0.0)

    def test_zero_hazard_gives_zero_cva_and_a_mirror_leaves_no_exposure(self):
        engine = _engine(n_paths=100)
        none = qfxva.FlatHazardRate(0.0)
        prof = engine.simulate([self.set_a])[0]
        r = qfxva.compute_xva(prof, none, 0.6, none, 0.6, 0.0)
        self.assertEqual((r.cva, r.dva, r.cva_stderr, r.dva_stderr, r.fva, r.total), (0.0,) * 6)

        mirror = _mxn_swap(payer=False)
        mirrored = qfxva.NettingSetSpec(swaps=[_mxn_swap(payer=True), mirror], xccys=[])
        mp = engine.simulate([mirrored])[0]
        self.assertEqual(mp.epe, [0.0] * len(mp.days))
        self.assertEqual(mp.ene, [0.0] * len(mp.days))
        credit = qfxva.FlatHazardRate(0.02)
        mr = qfxva.compute_xva(mp, credit, 0.6, credit, 0.6, 0.005)
        self.assertEqual((mr.cva, mr.dva, mr.fva, mr.total), (0.0, 0.0, 0.0, 0.0))

    def test_specs_are_editable_so_a_trade_can_be_mirrored(self):
        spec = _xccy(pay_usd=True)
        spec.pay_usd = False
        self.assertFalse(spec.pay_usd)
        swap = _mxn_swap()
        swap.payer = False
        swap.notional = 1e6
        self.assertEqual((swap.payer, swap.notional, swap.currency), (False, 1e6, qfxva.SwapCurrency.MXN))
        self.assertEqual(len(qfxva.NettingSetSpec().swaps), 0)

    def test_invalid_input_raises_value_error(self):
        # Correlation matrix that is not positive definite.
        with self.assertRaises(ValueError):
            _engine(model=qfxva.ExposureModel(0.05, 0.01, 0.03, 0.008, 0.12, 0.9, 0.9, -0.9))
        with self.assertRaises(ValueError):
            _engine(n_paths=0)
        with self.assertRaises(ValueError):
            _engine(report_days=[30, 60])        # must start at 0
        # csa_discount needs the MXN-USD curve.
        with self.assertRaises(ValueError):
            _engine(market=_market(with_basis=False)).simulate([self.set_a])
        # compute_xva: LGD in [0,1], funding spread >= 0.
        prof = _engine(n_paths=50).simulate([self.set_a])[0]
        credit = qfxva.FlatHazardRate(0.02)
        with self.assertRaises(ValueError):
            qfxva.compute_xva(prof, credit, 1.5, credit, 0.6, 0.005)
        with self.assertRaises(ValueError):
            qfxva.compute_xva(prof, credit, 0.6, credit, 0.6, -0.001)


if __name__ == "__main__":
    unittest.main()
