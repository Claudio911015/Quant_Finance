# CVA Engine Design — Standalone Calculator

**Date:** 2026-04-15  
**Project:** Quant_Finance (`~/Git/Quant_Finance`)  
**Scope:** Standalone CVA calculator for vanilla Interest Rate Swaps, extensible to other products and XVA terms.

---

## Context

The project already implements Hull-White (`qf::models::HullWhite`), vanilla IRS (`qf::instruments::Swap`), Monte Carlo pricing engine, and term structure bootstrapping. There is no counterparty credit risk module. This spec designs `qf::xva` — a new namespace that adds CVA computation as a first-class feature, reusing existing model and instrument infrastructure without modifying it.

CVA formula (discrete approximation):

```
CVA ≈ LGD · Σ_t EPE(t) · [SP(t-1) - SP(t)]
```

where EPE(t) = Expected Positive Exposure at time t, SP(t) = survival probability at t.

---

## Architecture

New namespace `qf::xva`, independent of `IPricingEngine`. CVA is a portfolio-level calculation (netting set), not a single-instrument price — forcing it into `IPricingEngine` would be a design error.

### File Structure

```
include/qf/xva/
    credit_curve.hpp       — ICreditCurve interface + FlatHazardRate
    netting_set.hpp        — NettingSet (portfolio of swaps, same counterparty)
    cva_result.hpp         — CVAResult (scalar CVA + full EPE profile)
    cva_calculator.hpp     — CVACalculator (orchestrates MC simulation)

src/xva/
    credit_curve.cpp
    netting_set.cpp
    cva_calculator.cpp

tests/
    test_CVACalculator.cpp

bindings/
    xva_bindings.cpp       — pybind11 module "qfxva"
```

`CMakeLists.txt` additions:
- Library target `qf_xva` linked against `qf`
- Python extension target `qfxva` (pybind11) producing `build/bindings/qfxva.so`
- Test target `test_CVACalculator` added to `ctest`

---

## Components

### `ICreditCurve` + `FlatHazardRate`

```cpp
// include/qf/xva/credit_curve.hpp
namespace qf::xva {

class ICreditCurve {
public:
    virtual ~ICreditCurve() = default;
    virtual double survivalProbability(double t) const = 0;
};

class FlatHazardRate : public ICreditCurve {
public:
    explicit FlatHazardRate(double lambda);  // lambda in decimal, e.g. 0.02 = 200bps
    double survivalProbability(double t) const override;  // exp(-lambda * t)
private:
    double lambda_;
};

} // namespace qf::xva
```

Extensibility: `PiecewiseHazardRate` (bootstrapped from CDS curve) implements `ICreditCurve` in a future iteration without touching `CVACalculator`.

---

### `NettingSet`

```cpp
// include/qf/xva/netting_set.hpp
namespace qf::xva {

class NettingSet {
public:
    void add(std::shared_ptr<qf::instruments::Swap> swap);
    // Returns Σ V_i(env) — net mark-to-market of portfolio
    double netValue(const qf::core::MarketEnvironment& env) const;
    std::size_t size() const;
};

} // namespace qf::xva
```

`netValue()` delegates to each swap's pricing engine inside the provided `MarketEnvironment`. Netting is natural: the sum can be negative (liability), and `max(netValue, 0)` gives the exposure.

---

### `CVAResult`

```cpp
// include/qf/xva/cva_result.hpp
namespace qf::xva {

struct TimeStep {
    double t;
    double epe;           // Expected Positive Exposure at t
    double survProb;      // Survival probability SP(t)
    double contribution;  // LGD * EPE(t) * [SP(t-1) - SP(t)]
};

struct CVAResult {
    double cva;                        // Total CVA scalar
    std::vector<TimeStep> profile;     // Per-date breakdown
};

} // namespace qf::xva
```

---

### `CVACalculator`

```cpp
// include/qf/xva/cva_calculator.hpp
namespace qf::xva {

struct SimParams {
    std::size_t nPaths;
    std::vector<double> monitorDates;  // in years, e.g. {0.25, 0.5, ..., 5.0}
    std::optional<unsigned int> seed;  // for reproducibility
};

class CVACalculator {
public:
    CVACalculator(const qf::models::HullWhite& hw,
                  const ICreditCurve& credit,
                  double lgd,
                  SimParams params);

    CVAResult compute(const NettingSet& ns,
                      const qf::core::MarketEnvironment& env) const;

private:
    const qf::models::HullWhite& hw_;
    const ICreditCurve& credit_;
    double lgd_;
    SimParams params_;
};

} // namespace qf::xva
```

---

## Monte Carlo Pipeline

`CVACalculator::compute()` executes the following per path `i = 1..N`:

1. Simulate short rate path `r(t_k)` at each monitor date using `HullWhite::simulate()`
2. At each `t_k`, reconstruct the discount curve from `r(t_k)` using `HullWhite::zeroRate()` and build a `MarketEnvironment`
3. Call `NettingSet::netValue(env_k)` → `V_k^i`
4. Accumulate: `EPE(t_k) += max(V_k^i, 0) / N`

After all paths:

```
For each monitor date t_k:
    contribution(t_k) = LGD * EPE(t_k) * [SP(t_{k-1}) - SP(t_k)]
CVA = Σ_k contribution(t_k)
```

RNG: `std::mt19937` seeded from `SimParams::seed` (or `std::random_device` if absent). Consistent with the existing `MonteCarloEngine`.

---

## Python Bindings (`qfxva`)

Module `qfxva` built with pybind11. Exposed API:

```python
import qfxva

credit  = qfxva.FlatHazardRate(lambda_=0.02)
params  = qfxva.SimParams(n_paths=10_000,
                           monitor_dates=[0.25, 0.5, ..., 5.0],
                           seed=42)
calc    = qfxva.CVACalculator(hw, credit, lgd=0.6, params=params)

ns = qfxva.NettingSet()
ns.add(swap1)
ns.add(swap2)

result = calc.compute(ns, market_env)
result.cva                # float
result.to_dataframe()     # pandas DataFrame: columns [t, epe, surv_prob, contribution]
```

`to_dataframe()` is implemented in the binding layer (not in C++) by converting `profile` to a Python dict that pandas accepts. No pandas dependency in C++.

`build/bindings/` is added to `PYTHONPATH` in the Flask dashboard startup script.

---

## Testing

### C++ (GoogleTest) — `tests/test_CVACalculator.cpp`

| Test | What it verifies |
|------|-----------------|
| `CVA_ZeroLGD` | CVA == 0 when LGD=0, regardless of exposure |
| `CVA_DeepInTheMoney` | Deep ITM swap: CVA ≈ `LGD · V_0 · (1 - SP(T))` analytically |
| `CVA_NettingReducesExposure` | Pay-fixed + receive-fixed same terms: net exposure ≈ 0, CVA ≈ 0 |

### Python (pytest) — `web/tests/test_xva.py`

| Test | What it verifies |
|------|-----------------|
| `test_result_to_dataframe` | DataFrame has correct columns, `len == len(monitor_dates)` |
| `test_cva_positive` | ATM swap + positive hazard rate → CVA > 0 |

---

## Future Extensions (out of scope for v1)

- `PiecewiseHazardRate` — bootstrapped from CDS curve term structure
- DVA — bilateral CVA using own default probability
- Collateral/CSA — threshold and MTA in exposure calculation
- Other underlyings — equity swaps, cross-currency swaps (new `NettingSet::add()` overloads)
- Wrong-Way Risk — correlation between exposure and default probability
