# Heston Calibration to Listed Equity Option Quotes (P3) — Design Spec

**Date:** 2026-07-07
**Project:** Quant_Finance (`~/Git/Quant_Finance`)
**Status:** Approved (P3 of the roadmap — ships after P1 DVA/FVA `6ec9f06` and P2 ScenarioEngine `a23e1eb`)
**Scope:** Fit a `qf::pricingengines::HestonParams` set to a collection of listed European
equity option quotes, so the already-shipped Heston stack (`hestonPrice`, `HestonEngine`,
`HestonModel`, `make_heston_engine`) can be driven by the vanilla market instead of
hand-picked parameters. Ships as three sequenced, independently-committable pieces
(P3a optimizer prerequisite, P3b calibrator core, P3c Python bindings + example).

Output is a **calibrated `HestonParams`** (five scalars) — deliberately *not* a vol
surface object. P4 (surface in `MarketEnvironment`) stays untouched.

---

## 1. Context and Motivation

The Heston stack is complete on the pricing side: `src/pricingengines/heston.cpp`
holds a semi-analytical `hestonPrice` (Albrecher-corrected characteristic function +
Simpson quadrature, validated by `tests/test_pricingengines.cpp`), an env-aware
`HestonEngine`, and a Monte-Carlo pricer. `blackscholes.cpp` has a Brent-based
`impliedVolatility`. All three are already bound in `qfpy`.

The gap is that nobody can *mark* these tools to the listed market: `HestonEngine`
demands hand-picked `v0/kappa/theta/sigma/rho`, so an exotic priced under Heston is
not smile-consistent with the vanilla chain. Two concrete prerequisites are missing:

1. **No multi-dimensional optimizer.** `qf::math` has only 1-D rootfinding
   (`newtonRaphson`, `brent` in `rootfinding.hpp`). Five-parameter Heston calibration
   needs a derivative-free N-D minimizer. Heston has no cheap analytic gradient in this
   codebase, so Nelder-Mead (downhill simplex) is the scoped choice: ~200 lines, zero
   dependencies, `std::function`-based API consistent with the existing `qf::math` style.

2. **No option-quote container.** `MarketEnvironment` holds one flat vol per ticker
   (P4 surface unshipped), so there is no type carrying a `(strike, maturity, type,
   price)` chain to fit against.

De-risking facts:

- `hestonPrice` costs a couple of quadratures per evaluation; a Nelder-Mead calibration
  is a few hundred to low-thousands of objective evaluations → sub-second, no new pricer.
- A **synthetic round-trip** is an exact acceptance test: generate quotes from known
  `HestonParams` on a strike/maturity grid, calibrate from a perturbed start, and require
  parameter recovery + RMSE ≈ 0. No market data or external fixtures needed.

Deliberately **excluded** (future work, no rework needed): dividend term structure,
American quotes, a surface object, and local-vol. Scope is European vanillas on one
underlying with flat `r` and `q` (matching `OptionParams` fields as they exist today).

---

## 2. Chosen Approach

### P3a — Nelder-Mead optimizer in `qf::math` (prerequisite, small)

New two-file feature `include/qf/math/optimization.hpp` + `src/math/optimization.cpp`,
namespace `qf::math`.

```cpp
struct OptimResult {
    std::vector<double> x;   // argmin
    double fmin;             // f(x)
    int    iterations;       // simplex iterations performed
    bool   converged;        // true if tolerance met before maxIt
};

// Derivative-free downhill-simplex minimization (Nelder & Mead 1965).
OptimResult nelderMead(std::function<double(const std::vector<double>&)> f,
                       const std::vector<double>& x0,
                       double tol   = 1e-8,
                       int    maxIt = 2000,
                       double initialStep = 0.05);
```

Standard reflection/expansion/contraction/shrink with the textbook coefficients
(α=1, γ=2, ρ=0.5, σ=0.5). Initial simplex: `x0` plus one vertex per dimension offset by
`initialStep` (relative when the coordinate is non-zero, absolute otherwise).
Convergence when the spread of function values across the simplex falls below `tol`
(`2·|f_hi − f_lo| / (|f_hi| + |f_lo| + eps) < tol`). Never throws for a well-formed
non-empty `x0`; returns `converged=false` if `maxIt` is hit. Throws
`std::invalid_argument` on an empty `x0`.

**Tests** (added to `tests/test_math.cpp`): minimize a shifted quadratic (known min),
minimize the 2-D Rosenbrock from `(-1.2, 1.0)` recovering `(1,1)`, and confirm
`converged` flips to `false` when `maxIt` is starved to 1.

### P3b — `HestonCalibrator` (core, medium)

New two-file feature `include/qf/models/heston_calibrator.hpp` +
`src/models/heston_calibrator.cpp`, namespace `qf::models`. Uses
`pricingengines::HestonParams` (the type `hestonPrice`/`HestonEngine` consume) so a
calibration result plugs straight into `make_heston_engine` with no conversion.

```cpp
struct OptionQuote {
    double strike;
    double maturity;
    instruments::OptionType type;
    double marketPrice;      // undiscounted option premium in price space
};

enum class CalibrationObjective { Price, ImpliedVol };

struct CalibrationResult {
    pricingengines::HestonParams params;
    double rmse;                          // weighted RMSE in the chosen space
    std::vector<double> perQuoteErrors;   // model − market, one per quote (chosen space)
    bool   converged;
    int    iterations;
};

class HestonCalibrator {
public:
    HestonCalibrator(double spot, double r, double q = 0.0);

    CalibrationResult calibrate(
        const std::vector<OptionQuote>& quotes,
        const pricingengines::HestonParams& initialGuess,
        CalibrationObjective objective = CalibrationObjective::Price,
        bool   vegaWeighted = false,
        double tol   = 1e-8,
        int    maxIt = 2000) const;
};
```

**Parameter transforms (constraint handling).** Nelder-Mead searches an *unconstrained*
5-vector `y`; the objective maps `y → HestonParams` so every candidate already satisfies
the validation guards `hestonPrice` throws on:
`v0 = exp(y0)`, `kappa = exp(y1)`, `theta = exp(y2)`, `sigma = exp(y3)` (all `> 0`),
`rho = tanh(y4)` (in `(−1, 1)`). The forward map (`params → y`) with `log`/`atanh`
seeds the simplex from `initialGuess`. This keeps the search unconstrained while the
output always prices.

**Objective.** For each quote build an `OptionParams{spot, strike, r, q, ·, maturity,
type, European}`, price with `hestonPrice`.
- *Price space:* `err = modelPrice − marketPrice`.
- *ImpliedVol space:* convert both model and market prices to BS implied vol via the
  existing `impliedVolatility`, `err = modelIV − marketIV`. Quotes whose price is below
  intrinsic (no real IV) are guarded — a wide penalty is returned so the simplex steers away.
- *Vega weighting* (optional): divide each price-space error by BS vega (per unit vol,
  floored to avoid blow-ups on deep wings), approximating an IV-space fit while staying
  in price space. Ignored in ImpliedVol space (already vega-normalised).

`rmse = sqrt( mean( weightedErr² ) )`. `perQuoteErrors` are the *unweighted* errors in
the chosen space for reporting. If a candidate ever throws inside `hestonPrice`
(should not happen given the transforms, but guards belt-and-suspenders), that evaluation
returns a large finite penalty rather than propagating.

**Acceptance test** (`tests/test_calibration.cpp`, new GoogleTest file wired into
`tests/CMakeLists.txt`): pick `HestonParams{v0=.04,kappa=1.5,theta=.05,sigma=.4,rho=-.6}`,
generate a strike×maturity grid of synthetic call prices via `hestonPrice`, calibrate
from a perturbed initial guess, and assert (a) RMSE < 1e-4 in price space, (b) each
recovered parameter within a loose tolerance of truth, (c) `converged == true`. Plus:
an empty-quote-set throws; a single-quote fit runs; `perQuoteErrors.size() == quotes.size()`.

### P3c — qfpy bindings + example (small)

In `src/python_bindings/qfpy.cpp` (additive only):

- Bind `OptionQuote` (constructor + read/write fields), `CalibrationObjective` enum,
  `CalibrationResult` (read-only fields), and `HestonCalibrator`.
- Add a DataFrame-friendly free function
  `calibrate_heston(spot, r, q, quotes, objective=Price, vega_weighted=False)` where
  `quotes` is a list of `(strike, maturity, type, price)` tuples straight off a listed
  chain, returning the `CalibrationResult` whose `.params` feeds `make_heston_engine`.
- Bind `OptionType` if not already exposed (it is exposed via existing option bindings —
  verified before adding).

**Tests** (`tests/test_calibration_py.py`, mirroring `tests/test_scenario_py.py`'s
real-`.so`-loading harness with graceful skip): Python round-trip recovering params from
synthetic quotes; `perQuoteErrors` length matches; `.params` constructs a working
`make_heston_engine`.

**Example** `examples/heston_calibration.py`: build a synthetic chain, `calibrate_heston`,
reprice the chain from the fitted params, and print per-quote fit error in IV terms.

---

## 3. Backward-compatibility constraints

- No existing public signature changes anywhere. P3a is a brand-new `qf::math` module;
  P3b is a brand-new `qf::models` module using existing `pricingengines`/`instruments`
  types; P3c adds new bindings only.
- `pricingengines::HestonParams` (already bound) is reused as the calibration output — no
  new params type, no divergence from `make_heston_engine`.
- `qfxva` is not touched. The `models::HestonParams` legacy duplicate in
  `heston_model.hpp` is left as-is (untouched, unrelated to the pricer path).

---

## 4. Quant subtlety (must be in Doxygen)

- **Feller condition** `2·kappa·theta ≥ sigma²` is *not* enforced. Listed equity smiles
  routinely calibrate to `sigma²` above `2·kappa·theta`; forcing Feller degrades fit.
  The pricer's absorption-at-zero MC and the semi-analytic price both tolerate mild
  Feller violation, so the calibrator permits it and documents the trade-off.
- **Objective-space choice matters.** Price-space RMSE overweights ATM/long-dated quotes
  (largest premia); IV-space or vega-weighted price-space gives a more uniform smile fit.
  Default is price-space (simplest, exact for the round-trip test); desks fitting real
  smiles should prefer `ImpliedVol` or `vegaWeighted=true`.
- **Local minima.** Nelder-Mead is a local optimizer; Heston objectives are known to be
  multi-modal. The parameter transforms + a sensible `initialGuess` (ATM variance for
  `v0`/`theta`) mitigate this; a production desk would multi-start. Out of scope here.

---

## 5. Testing gate

- `tests/test_math.cpp`: Nelder-Mead quadratic + Rosenbrock recovery + starved-`maxIt`
  non-convergence flag.
- `tests/test_calibration.cpp`: synthetic round-trip recovery (RMSE < 1e-4, params within
  tolerance, converged), empty-quote throw, single-quote run, `perQuoteErrors` sizing.
- `tests/test_calibration_py.py`: real-`.so` Python round-trip with graceful skip; result
  `.params` drives `make_heston_engine`.
- **Regression gate:** full `ctest` suite stays green; each of P3a/P3b/P3c builds clean
  (`cmake --build build --target all && ctest --output-on-failure`) before its commit.
