"""Python-level tests for qfxva bindings."""
import sys, os, pytest

# Locate the built module — try multiple locations
_build = os.path.join(os.path.dirname(__file__), "..", "..", "build")
for _p in [_build, os.path.join(_build, "src"), os.path.join(_build, "bindings")]:
    sys.path.insert(0, _p)

try:
    import qfxva
    import qfpy
except ImportError as e:
    pytest.skip(f"C++ modules not built: {e}", allow_module_level=True)


def _make_hw():
    curve = qfpy.YieldCurve([0.5, 1.0, 2.0, 5.0, 10.0], [0.04]*5,
                             qfpy.InterpolationMethod.Linear)
    return qfpy.HullWhite(a=0.1, sigma=0.01, curve=curve)


def _make_env():
    curve = qfpy.YieldCurve([0.5, 1.0, 2.0, 5.0, 10.0], [0.04]*5,
                             qfpy.InterpolationMethod.Linear)
    return qfpy.MarketEnvironment(curve)


def _quarterly(mat):
    result = []
    t = 0.25
    while t <= mat + 1e-9:
        result.append(t)
        t += 0.25
    return result


def test_result_to_dataframe():
    hw     = _make_hw()
    credit = qfxva.FlatHazardRate(lambda_=0.02)
    params = qfxva.SimParams(n_paths=200, monitor_dates=_quarterly(3.0), seed=42)
    calc   = qfxva.CVACalculator(hw, credit, lgd=0.6, params=params)

    ns = qfxva.NettingSet()
    ns.add(notional=1e6, fixed_rate=0.10, maturity=3.0,
           frequency=1.0, swap_type=qfxva.SwapType.Receiver)

    result = calc.compute(ns, _make_env())
    df = result.to_dataframe()

    assert list(df.columns) == ["t", "epe", "surv_prob", "contribution"]
    assert len(df) == len(_quarterly(3.0))


def test_cva_positive_for_itm_receiver():
    hw     = _make_hw()
    credit = qfxva.FlatHazardRate(lambda_=0.02)
    params = qfxva.SimParams(n_paths=500, monitor_dates=_quarterly(5.0), seed=42)
    calc   = qfxva.CVACalculator(hw, credit, lgd=0.6, params=params)

    ns = qfxva.NettingSet()
    # Deep ITM receiver: receives 10% fixed on a 4% flat curve
    ns.add(notional=1e6, fixed_rate=0.10, maturity=5.0,
           frequency=1.0, swap_type=qfxva.SwapType.Receiver)

    result = calc.compute(ns, _make_env())
    assert result.cva > 0.0
