# CVA Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a standalone CVA calculator (`qf::xva`) for vanilla IRS netting sets using Monte Carlo + Hull-White, with pybind11 Python bindings exposing `CVAResult.to_dataframe()`.

**Architecture:** New namespace `qf::xva` added to the `qf` library. `CVACalculator` simulates N Hull-White short-rate paths, rebuilds the discount curve at each monitor date via a new `HullWhite::conditionalBondPrice(t, T, r_t)` method, evaluates the netting set's residual NPV, and integrates EPE against the flat hazard rate. Python module `qfxva` wraps the result with a `to_dataframe()` convenience method.

**Tech Stack:** C++20, GoogleTest, pybind11, pytest

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `include/qf/models/hullwhite.hpp` | Modify | Add `conditionalBondPrice(t,T,r_t)` declaration |
| `src/models/hullwhite.cpp` | Modify | Implement `conditionalBondPrice` |
| `include/qf/xva/credit_curve.hpp` | Create | `ICreditCurve` interface + `FlatHazardRate` |
| `src/xva/credit_curve.cpp` | Create | `FlatHazardRate::survivalProbability` |
| `include/qf/xva/cva_result.hpp` | Create | `TimeStep` + `CVAResult` structs |
| `include/qf/xva/netting_set.hpp` | Create | `NettingSet` (stores IRS params, builds residual swaps) |
| `src/xva/netting_set.cpp` | Create | `NettingSet::netValue(env, t)` |
| `include/qf/xva/cva_calculator.hpp` | Create | `SimParams` + `CVACalculator` |
| `src/xva/cva_calculator.cpp` | Create | MC simulation loop |
| `tests/test_CVACalculator.cpp` | Create | 3 GoogleTest cases |
| `src/python_bindings/xva_bindings.cpp` | Create | pybind11 `qfxva` module |
| `src/CMakeLists.txt` | Modify | Add xva sources to `qf`; add `qfxva` target |
| `tests/CMakeLists.txt` | Modify | Add `test_CVACalculator.cpp` to `qf_tests` |

---

## Task 1: Add `conditionalBondPrice` to HullWhite

**Files:**
- Modify: `include/qf/models/hullwhite.hpp`
- Modify: `src/models/hullwhite.cpp`
- Modify: `tests/test_models.cpp` (append new TEST block)

### Formula

```
P(t,T|r_t) = [P(0,T)/P(0,t)] * exp( B(t,T)*(f(0,t) - r_t)
              - (σ²/4a) * B(t,T)² * (1 - exp(-2at)) )

B(t,T) = (1 - exp(-a*(T-t))) / a
f(0,t) = instantaneous forward rate from initial curve at t
```

- [ ] **Step 1: Add declaration to header**

In `include/qf/models/hullwhite.hpp`, add inside the `public:` section, after `simulate`:

```cpp
/// @brief Compute the zero-coupon bond price P(t,T) conditional on r(t).
/// @param t    Observation time in years (0 ≤ t < T).
/// @param T    Maturity in years.
/// @param r_t  Simulated short rate at time t.
/// @return     Risk-neutral conditional discount factor P(t,T|r(t)).
double conditionalBondPrice(double t, double T, double r_t) const;
```

- [ ] **Step 2: Implement in `src/models/hullwhite.cpp`**

Add after the `simulate` function:

```cpp
double HullWhite::conditionalBondPrice(double t, double T, double r_t) const
{
    if (T <= t)
        throw std::invalid_argument(
            "HullWhite::conditionalBondPrice: T must be > t");

    // Special case: at t≈0 the model reproduces the initial curve exactly
    if (t < 1e-6)
        return curve_.discountFactor(T);

    double tau   = T - t;
    double B_tT  = (1.0 - std::exp(-a_ * tau)) / a_;

    // Instantaneous forward rate from the initial market curve at t
    const double eps = 1e-5;
    double f0t = curve_.forwardRate(t, t + eps);

    // ln A(t,T) — deterministic part of the H-W bond price formula
    double lnA = std::log(curve_.discountFactor(T) / curve_.discountFactor(t))
               + B_tT * f0t
               - (sigma_ * sigma_ / (4.0 * a_))
                 * B_tT * B_tT * (1.0 - std::exp(-2.0 * a_ * t));

    return std::exp(lnA - B_tT * r_t);
}
```

- [ ] **Step 3: Write the failing test**

Append to `tests/test_models.cpp`:

```cpp
// ═══════════════════════════════════════════════════════════════════════════
// HullWhite::conditionalBondPrice
// ═══════════════════════════════════════════════════════════════════════════

TEST(HullWhiteConditionalBondPrice, AtT0MatchesInitialCurve) {
    YieldCurve curve({0.5,1,2,5,10}, {0.04,0.04,0.04,0.04,0.04});
    HullWhite hw(0.1, 0.01, curve);
    // At t≈0, conditionalBondPrice should equal bondPrice (initial curve)
    for (double T : {1.0, 3.0, 5.0, 10.0}) {
        EXPECT_NEAR(hw.conditionalBondPrice(0.0, T, 0.04),
                    hw.bondPrice(T), 1e-8);
    }
}

TEST(HullWhiteConditionalBondPrice, PositiveAndLessThanOne) {
    YieldCurve curve({0.5,1,2,5,10}, {0.04,0.04,0.04,0.04,0.04});
    HullWhite hw(0.1, 0.01, curve);
    for (double t : {1.0, 2.0, 3.0}) {
        for (double T : {t+0.5, t+2.0, t+5.0}) {
            double P = hw.conditionalBondPrice(t, T, 0.04);
            EXPECT_GT(P, 0.0) << "t=" << t << " T=" << T;
            EXPECT_LT(P, 1.0) << "t=" << t << " T=" << T;
        }
    }
}

TEST(HullWhiteConditionalBondPrice, HigherRateLowerPrice) {
    YieldCurve curve({0.5,1,2,5,10}, {0.04,0.04,0.04,0.04,0.04});
    HullWhite hw(0.1, 0.01, curve);
    double P_low  = hw.conditionalBondPrice(1.0, 5.0, 0.02);
    double P_high = hw.conditionalBondPrice(1.0, 5.0, 0.08);
    EXPECT_GT(P_low, P_high);
}
```

- [ ] **Step 4: Build and run**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . --target qf_tests 2>&1 | tail -5
./tests/qf_tests --gtest_filter="HullWhiteConditionalBondPrice*"
```

Expected: `3 tests passed`

- [ ] **Step 5: Commit**

```bash
cd /home/claudio/Git/Quant_Finance
git add include/qf/models/hullwhite.hpp src/models/hullwhite.cpp tests/test_models.cpp
git commit -m "feat(models): add HullWhite::conditionalBondPrice for CVA simulation"
```

---

## Task 2: CMakeLists setup

**Files:**
- Modify: `src/CMakeLists.txt`
- Modify: `tests/CMakeLists.txt`

- [ ] **Step 1: Add xva sources to the `qf` library**

In `src/CMakeLists.txt`, add to the `add_library(qf ...)` source list (after `risk/var.cpp`):

```cmake
    xva/credit_curve.cpp
    xva/netting_set.cpp
    xva/cva_calculator.cpp
```

- [ ] **Step 2: Add `qfxva` pybind11 module**

In `src/CMakeLists.txt`, after the existing `if(pybind11_FOUND)` block, add:

```cmake
if(pybind11_FOUND)
    pybind11_add_module(qfxva
        python_bindings/xva_bindings.cpp
    )
    target_link_libraries(qfxva PRIVATE qf)
    target_include_directories(qfxva PRIVATE ${CMAKE_SOURCE_DIR}/include)
    set_target_properties(qfxva PROPERTIES PREFIX "")
endif()
```

- [ ] **Step 3: Add CVA test file to `qf_tests`**

In `tests/CMakeLists.txt`, add `test_CVACalculator.cpp` to the `add_executable(qf_tests ...)` source list.

- [ ] **Step 4: Create source stubs so CMake doesn't fail**

```bash
mkdir -p /home/claudio/Git/Quant_Finance/src/xva
touch /home/claudio/Git/Quant_Finance/src/xva/credit_curve.cpp
touch /home/claudio/Git/Quant_Finance/src/xva/netting_set.cpp
touch /home/claudio/Git/Quant_Finance/src/xva/cva_calculator.cpp
touch /home/claudio/Git/Quant_Finance/src/python_bindings/xva_bindings.cpp
touch /home/claudio/Git/Quant_Finance/tests/test_CVACalculator.cpp
```

- [ ] **Step 5: Verify CMake configures without errors**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake .. 2>&1 | grep -E "error|warning|xva|qfxva" | head -20
```

Expected: no errors, `qfxva` target found if pybind11 is available.

- [ ] **Step 6: Commit**

```bash
cd /home/claudio/Git/Quant_Finance
git add src/CMakeLists.txt tests/CMakeLists.txt src/xva/ src/python_bindings/xva_bindings.cpp tests/test_CVACalculator.cpp
git commit -m "build: add qf::xva sources, qfxva pybind11 module, and CVA test target"
```

---

## Task 3: ICreditCurve + FlatHazardRate

**Files:**
- Create: `include/qf/xva/credit_curve.hpp`
- Create: `src/xva/credit_curve.cpp`

- [ ] **Step 1: Write the header**

Create `include/qf/xva/credit_curve.hpp`:

```cpp
#pragma once

namespace qf::xva {

/// @brief Interface for counterparty credit curves.
/// Implementations return the survival probability SP(t) = P(no default in [0,t]).
class ICreditCurve {
public:
    virtual ~ICreditCurve() = default;
    /// @param t  Time in years (t ≥ 0).
    /// @return   Survival probability in [0,1].
    virtual double survivalProbability(double t) const = 0;
};

/// @brief Flat (constant) hazard rate credit curve.
/// SP(t) = exp(-lambda * t).
class FlatHazardRate : public ICreditCurve {
public:
    /// @param lambda  Hazard rate in decimal (e.g. 0.02 = 200 bps CDS spread / LGD).
    explicit FlatHazardRate(double lambda);
    double survivalProbability(double t) const override;
private:
    double lambda_;
};

} // namespace qf::xva
```

- [ ] **Step 2: Write the implementation**

Create `src/xva/credit_curve.cpp`:

```cpp
#include <qf/xva/credit_curve.hpp>
#include <cmath>
#include <stdexcept>

namespace qf::xva {

FlatHazardRate::FlatHazardRate(double lambda) : lambda_(lambda)
{
    if (lambda < 0.0)
        throw std::invalid_argument("FlatHazardRate: lambda must be non-negative");
}

double FlatHazardRate::survivalProbability(double t) const
{
    if (t < 0.0)
        throw std::invalid_argument("FlatHazardRate::survivalProbability: t must be >= 0");
    return std::exp(-lambda_ * t);
}

} // namespace qf::xva
```

- [ ] **Step 3: Write the failing test** (add to `tests/test_CVACalculator.cpp`)

```cpp
#include <gtest/gtest.h>
#include <qf/xva/credit_curve.hpp>
#include <cmath>

using namespace qf::xva;

TEST(FlatHazardRate, SurvivalAtZeroIsOne) {
    FlatHazardRate cr(0.02);
    EXPECT_NEAR(cr.survivalProbability(0.0), 1.0, 1e-12);
}

TEST(FlatHazardRate, SurvivalDecaysExponentially) {
    double lambda = 0.05;
    FlatHazardRate cr(lambda);
    for (double t : {1.0, 2.0, 5.0, 10.0}) {
        EXPECT_NEAR(cr.survivalProbability(t), std::exp(-lambda * t), 1e-12);
    }
}

TEST(FlatHazardRate, ZeroLambdaAlwaysOne) {
    FlatHazardRate cr(0.0);
    for (double t : {0.0, 1.0, 10.0})
        EXPECT_NEAR(cr.survivalProbability(t), 1.0, 1e-12);
}
```

- [ ] **Step 4: Build and run**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . --target qf_tests 2>&1 | tail -5
./tests/qf_tests --gtest_filter="FlatHazardRate*"
```

Expected: `3 tests passed`

- [ ] **Step 5: Commit**

```bash
cd /home/claudio/Git/Quant_Finance
git add include/qf/xva/credit_curve.hpp src/xva/credit_curve.cpp tests/test_CVACalculator.cpp
git commit -m "feat(xva): add ICreditCurve interface and FlatHazardRate"
```

---

## Task 4: CVAResult header

**Files:**
- Create: `include/qf/xva/cva_result.hpp`

- [ ] **Step 1: Write the header** (pure data, no implementation file needed)

Create `include/qf/xva/cva_result.hpp`:

```cpp
#pragma once
#include <vector>

namespace qf::xva {

/// @brief Per-date contribution to CVA.
struct TimeStep {
    double t;            ///< Monitor date in years.
    double epe;          ///< Expected Positive Exposure E[max(V,0)] at t.
    double survProb;     ///< Survival probability SP(t).
    double contribution; ///< LGD * EPE(t) * [SP(t-1) - SP(t)].
};

/// @brief Output of CVACalculator::compute().
struct CVAResult {
    double cva;                    ///< Total CVA scalar (sum of contributions).
    std::vector<TimeStep> profile; ///< Per-date breakdown.
};

} // namespace qf::xva
```

- [ ] **Step 2: Commit**

```bash
cd /home/claudio/Git/Quant_Finance
git add include/qf/xva/cva_result.hpp
git commit -m "feat(xva): add CVAResult and TimeStep structs"
```

---

## Task 5: NettingSet

**Files:**
- Create: `include/qf/xva/netting_set.hpp`
- Create: `src/xva/netting_set.cpp`

Design note: `NettingSet` stores the construction parameters of each IRS (not `shared_ptr<Swap>`) because `InterestRateSwap::npv` is not virtual through `Swap*`. At each monitor date `t`, it builds a residual `InterestRateSwap` with `maturity = original_maturity - t` and evaluates its NPV against the conditional market environment.

- [ ] **Step 1: Write the header**

Create `include/qf/xva/netting_set.hpp`:

```cpp
#pragma once
#include <vector>
#include <qf/core/market_environment.hpp>
#include <qf/instruments/swap.hpp>

namespace qf::xva {

/// @brief Collection of vanilla IRS sharing the same counterparty.
///
/// Stores swap parameters and builds residual instruments at each
/// simulation date so that only future cash flows are priced.
class NettingSet {
public:
    /// @brief Register a vanilla interest-rate swap in this netting set.
    /// @param notional   Notional principal.
    /// @param fixedRate  Fixed coupon rate (annual, decimal).
    /// @param maturity   Original maturity in years from t = 0.
    /// @param frequency  Payment periods per year (e.g. 2 = semi-annual).
    /// @param type       Payer or Receiver from the portfolio's perspective.
    void add(double notional, double fixedRate, double maturity,
             double frequency, qf::instruments::SwapType type);

    /// @brief Net mark-to-market at simulation time t.
    ///
    /// Builds residual swaps (remaining maturity = original - t) and sums
    /// their NPVs. Swaps that have matured (maturity ≤ t) are skipped.
    /// @param env  MarketEnvironment containing the conditional yield curve.
    /// @param t    Current simulation time in years.
    double netValue(const qf::core::MarketEnvironment& env, double t = 0.0) const;

    std::size_t size() const;

private:
    struct Entry {
        double notional, fixedRate, maturity, frequency;
        qf::instruments::SwapType type;
    };
    std::vector<Entry> entries_;
};

} // namespace qf::xva
```

- [ ] **Step 2: Write the implementation**

Create `src/xva/netting_set.cpp`:

```cpp
#include <qf/xva/netting_set.hpp>
#include <qf/instruments/swap.hpp>
#include <stdexcept>

namespace qf::xva {

void NettingSet::add(double notional, double fixedRate, double maturity,
                     double frequency, qf::instruments::SwapType type)
{
    if (notional  <= 0.0) throw std::invalid_argument("NettingSet::add: notional must be positive");
    if (maturity  <= 0.0) throw std::invalid_argument("NettingSet::add: maturity must be positive");
    if (frequency <= 0.0) throw std::invalid_argument("NettingSet::add: frequency must be positive");
    entries_.push_back({notional, fixedRate, maturity, frequency, type});
}

double NettingSet::netValue(const qf::core::MarketEnvironment& env, double t) const
{
    double net = 0.0;
    for (const auto& e : entries_) {
        double rem = e.maturity - t;
        if (rem <= 0.0) continue;   // swap has already matured
        qf::instruments::InterestRateSwap residual(
            e.notional, e.fixedRate, rem, e.frequency, e.type);
        net += residual.npv(env);
    }
    return net;
}

std::size_t NettingSet::size() const { return entries_.size(); }

} // namespace qf::xva
```

- [ ] **Step 3: Write the failing test** (append to `tests/test_CVACalculator.cpp`)

```cpp
#include <qf/xva/netting_set.hpp>
#include <qf/termstructure/yieldcurve.hpp>

using namespace qf::instruments;
using namespace qf::termstructure;

TEST(NettingSet, EmptySetNetValueIsZero) {
    NettingSet ns;
    YieldCurve curve({0.5,1,2,5,10}, {0.04,0.04,0.04,0.04,0.04});
    qf::core::MarketEnvironment env(curve);
    EXPECT_NEAR(ns.netValue(env, 0.0), 0.0, 1e-12);
}

TEST(NettingSet, MaturedSwapSkipped) {
    NettingSet ns;
    ns.add(1e6, 0.05, 2.0, 1.0, SwapType::Payer);
    YieldCurve curve({0.5,1,2,5,10}, {0.04,0.04,0.04,0.04,0.04});
    qf::core::MarketEnvironment env(curve);
    // At t=3 the swap matured at T=2, so net value must be 0
    EXPECT_NEAR(ns.netValue(env, 3.0), 0.0, 1e-12);
}

TEST(NettingSet, PayerReceiverNetToZero) {
    // Identical payer + receiver same params → net ≈ 0
    NettingSet ns;
    ns.add(1e6, 0.04, 5.0, 1.0, SwapType::Payer);
    ns.add(1e6, 0.04, 5.0, 1.0, SwapType::Receiver);
    YieldCurve curve({0.5,1,2,5,10}, {0.04,0.04,0.04,0.04,0.04});
    qf::core::MarketEnvironment env(curve);
    EXPECT_NEAR(ns.netValue(env, 0.0), 0.0, 1e-6);
}
```

- [ ] **Step 4: Build and run**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . --target qf_tests 2>&1 | tail -5
./tests/qf_tests --gtest_filter="NettingSet*"
```

Expected: `3 tests passed`

- [ ] **Step 5: Commit**

```bash
cd /home/claudio/Git/Quant_Finance
git add include/qf/xva/netting_set.hpp src/xva/netting_set.cpp tests/test_CVACalculator.cpp
git commit -m "feat(xva): add NettingSet with residual swap valuation"
```

---

## Task 6: CVACalculator

**Files:**
- Create: `include/qf/xva/cva_calculator.hpp`
- Create: `src/xva/cva_calculator.cpp`

- [ ] **Step 1: Write the header**

Create `include/qf/xva/cva_calculator.hpp`:

```cpp
#pragma once
#include <optional>
#include <vector>
#include <qf/models/hullwhite.hpp>
#include <qf/xva/credit_curve.hpp>
#include <qf/xva/netting_set.hpp>
#include <qf/xva/cva_result.hpp>
#include <qf/core/market_environment.hpp>

namespace qf::xva {

struct SimParams {
    std::size_t nPaths;                  ///< Number of Monte Carlo paths.
    std::vector<double> monitorDates;    ///< Observation times in years (sorted, all > 0).
    std::optional<unsigned int> seed;    ///< RNG seed; random if absent.
};

class CVACalculator {
public:
    /// @param hw      Hull-White model (calibrated to the initial yield curve).
    /// @param credit  Counterparty credit curve.
    /// @param lgd     Loss Given Default in [0,1] (e.g. 0.6 = 40 % recovery).
    /// @param params  Simulation parameters.
    CVACalculator(const qf::models::HullWhite& hw,
                  const ICreditCurve& credit,
                  double lgd,
                  SimParams params);

    /// @brief Run the CVA simulation over the netting set.
    /// @param ns   Portfolio of swaps with the same counterparty.
    /// @param env  Initial market environment (used to seed the initial curve).
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

- [ ] **Step 2: Write the implementation**

Create `src/xva/cva_calculator.cpp`:

```cpp
#include <qf/xva/cva_calculator.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/interpolation.hpp>
#include <algorithm>
#include <cmath>
#include <random>
#include <stdexcept>

namespace qf::xva {

CVACalculator::CVACalculator(const qf::models::HullWhite& hw,
                             const ICreditCurve& credit,
                             double lgd,
                             SimParams params)
    : hw_(hw), credit_(credit), lgd_(lgd), params_(std::move(params))
{
    if (lgd < 0.0 || lgd > 1.0)
        throw std::invalid_argument("CVACalculator: LGD must be in [0,1]");
    if (params_.monitorDates.empty())
        throw std::invalid_argument("CVACalculator: monitorDates must not be empty");
    if (params_.nPaths == 0)
        throw std::invalid_argument("CVACalculator: nPaths must be > 0");
}

CVAResult CVACalculator::compute(const NettingSet& ns,
                                  const qf::core::MarketEnvironment&) const
{
    const auto& dates = params_.monitorDates;
    const std::size_t nDates = dates.size();
    double T_max = dates.back();

    // Simulate on a daily grid fine enough to cover all monitor dates
    int totalSteps = std::max(static_cast<int>(std::ceil(T_max * 252)), 10);
    double dt = T_max / static_cast<double>(totalSteps);

    // Tenors used to rebuild the conditional yield curve at each node
    // (τ from current time; kept short enough for the YieldCurve interpolator)
    const std::vector<double> baseTenors =
        {1.0/12, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 30.0};

    // Accumulate EPE per monitor date
    std::vector<double> epeAccum(nDates, 0.0);

    unsigned seed = params_.seed.has_value()
                  ? params_.seed.value()
                  : static_cast<unsigned>(std::random_device{}());

    for (std::size_t p = 0; p < params_.nPaths; ++p) {
        // One HW short-rate path over [0, T_max]
        auto path = hw_.simulate(T_max, totalSteps, seed + static_cast<unsigned>(p));

        for (std::size_t k = 0; k < nDates; ++k) {
            double t_k = dates[k];
            // Map t_k to nearest path index
            int idx = static_cast<int>(std::round(t_k / dt));
            idx = std::clamp(idx, 0, totalSteps);
            double r_tk = path[static_cast<std::size_t>(idx)];

            // Build conditional yield curve: P(t_k, t_k+τ | r_tk)
            // Include only tenors that produce T = t_k + τ > t_k (always true) and
            // are sensible for the curve interpolator (at least 2 points).
            std::vector<double> tenors, zeroRates;
            tenors.reserve(baseTenors.size());
            zeroRates.reserve(baseTenors.size());
            for (double tau : baseTenors) {
                double P = hw_.conditionalBondPrice(t_k, t_k + tau, r_tk);
                if (P > 0.0 && P < 1.0) {
                    tenors.push_back(tau);
                    zeroRates.push_back(-std::log(P) / tau);
                }
            }
            if (tenors.size() < 2) continue; // degenerate — skip this date/path

            qf::termstructure::YieldCurve simCurve(
                tenors, zeroRates, qf::math::InterpolationMethod::Linear);
            qf::core::MarketEnvironment simEnv(simCurve);

            double netVal = ns.netValue(simEnv, t_k);
            epeAccum[k] += std::max(netVal, 0.0);
        }
    }

    // Assemble result
    CVAResult result;
    result.profile.resize(nDates);
    result.cva = 0.0;
    double sp_prev = 1.0;

    for (std::size_t k = 0; k < nDates; ++k) {
        double epe     = epeAccum[k] / static_cast<double>(params_.nPaths);
        double sp      = credit_.survivalProbability(dates[k]);
        double contrib = lgd_ * epe * (sp_prev - sp);
        result.profile[k] = {dates[k], epe, sp, contrib};
        result.cva += contrib;
        sp_prev = sp;
    }

    return result;
}

} // namespace qf::xva
```

- [ ] **Step 3: Build (no test yet — written in Task 7)**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . --target qf 2>&1 | tail -10
```

Expected: builds cleanly with no errors.

- [ ] **Step 4: Commit**

```bash
cd /home/claudio/Git/Quant_Finance
git add include/qf/xva/cva_calculator.hpp src/xva/cva_calculator.cpp
git commit -m "feat(xva): implement CVACalculator with HW Monte Carlo simulation"
```

---

## Task 7: CVACalculator tests

**Files:**
- Modify: `tests/test_CVACalculator.cpp` (append three TEST blocks)

- [ ] **Step 1: Write helpers and three test cases**

Append to `tests/test_CVACalculator.cpp`:

```cpp
#include <qf/xva/cva_calculator.hpp>
#include <qf/models/hullwhite.hpp>

// ── Shared helpers ──────────────────────────────────────────────────────────

static qf::termstructure::YieldCurve flatCurve(double r) {
    return qf::termstructure::YieldCurve(
        {0.5, 1.0, 2.0, 5.0, 10.0}, {r, r, r, r, r});
}

static std::vector<double> quarterlyDates(double maturity) {
    std::vector<double> d;
    for (double t = 0.25; t <= maturity + 1e-9; t += 0.25)
        d.push_back(t);
    return d;
}

// ── TEST 1: Zero LGD → CVA == 0 ────────────────────────────────────────────

TEST(CVACalculator, ZeroLGDGivesZeroCVA) {
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.01, curve);
    qf::xva::FlatHazardRate credit(0.02);
    qf::xva::SimParams params{1000, quarterlyDates(5.0), 42u};
    qf::xva::CVACalculator calc(hw, credit, /*lgd=*/0.0, params);

    qf::xva::NettingSet ns;
    ns.add(1e6, 0.05, 5.0, 1.0, qf::instruments::SwapType::Payer);

    qf::core::MarketEnvironment env(curve);
    auto result = calc.compute(ns, env);
    EXPECT_NEAR(result.cva, 0.0, 1e-10);
}

// ── TEST 2: Deep ITM payer swap → CVA > 0 and consistent with analytics ────

TEST(CVACalculator, DeepITMPayerSwapPositiveCVA) {
    // Fixed rate 10% on a 4% flat curve → deeply in-the-money payer
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.005, curve); // low vol for stable EPE
    qf::xva::FlatHazardRate credit(0.02);
    qf::xva::SimParams params{5000, quarterlyDates(5.0), 42u};
    qf::xva::CVACalculator calc(hw, credit, /*lgd=*/0.6, params);

    qf::xva::NettingSet ns;
    ns.add(1e6, 0.10, 5.0, 1.0, qf::instruments::SwapType::Payer);

    qf::core::MarketEnvironment env(curve);
    auto result = calc.compute(ns, env);

    // CVA must be strictly positive
    EXPECT_GT(result.cva, 0.0);

    // All contributions must be non-negative (EPE ≥ 0, SP decreasing)
    for (const auto& step : result.profile)
        EXPECT_GE(step.contribution, -1e-8);

    // Rough analytical bound: CVA ≈ LGD * V0 * (1 - SP(5))
    // V0 = ~200k for 1M notional, 10% fixed on 4% flat, 5Y annual
    // SP(5) = exp(-0.02*5) ≈ 0.905
    // CVA ≈ 0.6 * 200e3 * 0.095 ≈ 11400
    // MC noise: accept ±30%
    EXPECT_GT(result.cva, 3000.0);
    EXPECT_LT(result.cva, 50000.0);
}

// ── TEST 3: Netting — payer + receiver same params → CVA ≈ 0 ───────────────

TEST(CVACalculator, NettingReducesExposureToNearZero) {
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.01, curve);
    qf::xva::FlatHazardRate credit(0.02);
    qf::xva::SimParams params{2000, quarterlyDates(5.0), 42u};
    qf::xva::CVACalculator calc(hw, credit, /*lgd=*/0.6, params);

    // Payer + receiver same params → net value ≈ 0 at every simulation step
    qf::xva::NettingSet ns;
    ns.add(1e6, 0.05, 5.0, 1.0, qf::instruments::SwapType::Payer);
    ns.add(1e6, 0.05, 5.0, 1.0, qf::instruments::SwapType::Receiver);

    qf::core::MarketEnvironment env(curve);
    auto result = calc.compute(ns, env);

    // CVA of a perfectly netted portfolio ≈ 0
    EXPECT_NEAR(result.cva, 0.0, 500.0); // tolerance for MC noise on near-zero EPE
}
```

- [ ] **Step 2: Run**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . --target qf_tests 2>&1 | tail -5
./tests/qf_tests --gtest_filter="CVACalculator*"
```

Expected: `3 tests passed`

- [ ] **Step 3: Run full suite to catch regressions**

```bash
./tests/qf_tests 2>&1 | tail -5
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
cd /home/claudio/Git/Quant_Finance
git add tests/test_CVACalculator.cpp
git commit -m "test(xva): add CVACalculator tests: ZeroLGD, DeepITM, Netting"
```

---

## Task 8: Python bindings

**Files:**
- Create: `src/python_bindings/xva_bindings.cpp`

- [ ] **Step 1: Write the binding file**

Create `src/python_bindings/xva_bindings.cpp`:

```cpp
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <qf/xva/credit_curve.hpp>
#include <qf/xva/netting_set.hpp>
#include <qf/xva/cva_result.hpp>
#include <qf/xva/cva_calculator.hpp>
#include <qf/models/hullwhite.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/instruments/swap.hpp>

namespace py = pybind11;
using namespace qf::xva;
using namespace qf::instruments;

PYBIND11_MODULE(qfxva, m) {
    m.doc() = "qf::xva — CVA calculator Python bindings";

    // ── ICreditCurve (abstract base, not directly instantiable) ──
    py::class_<ICreditCurve>(m, "ICreditCurve")
        .def("survival_probability", &ICreditCurve::survivalProbability, py::arg("t"));

    // ── FlatHazardRate ────────────────────────────────────────────
    py::class_<FlatHazardRate, ICreditCurve>(m, "FlatHazardRate")
        .def(py::init<double>(), py::arg("lambda_"),
             "Flat hazard rate: SP(t) = exp(-lambda * t). "
             "lambda_ in decimal (e.g. 0.02 = 200 bps).")
        .def("survival_probability", &FlatHazardRate::survivalProbability, py::arg("t"));

    // ── SwapType enum ─────────────────────────────────────────────
    py::enum_<SwapType>(m, "SwapType")
        .value("Payer",    SwapType::Payer)
        .value("Receiver", SwapType::Receiver);

    // ── NettingSet ────────────────────────────────────────────────
    py::class_<NettingSet>(m, "NettingSet")
        .def(py::init<>())
        .def("add", &NettingSet::add,
             py::arg("notional"), py::arg("fixed_rate"), py::arg("maturity"),
             py::arg("frequency"), py::arg("swap_type"),
             "Add a vanilla IRS to the netting set.")
        .def("size", &NettingSet::size);

    // ── SimParams ─────────────────────────────────────────────────
    py::class_<SimParams>(m, "SimParams")
        .def(py::init([](std::size_t nPaths,
                         std::vector<double> monitorDates,
                         py::object seed) {
            SimParams p;
            p.nPaths       = nPaths;
            p.monitorDates = std::move(monitorDates);
            if (!seed.is_none())
                p.seed = seed.cast<unsigned int>();
            return p;
        }),
        py::arg("n_paths"), py::arg("monitor_dates"), py::arg("seed") = py::none())
        .def_readwrite("n_paths",       &SimParams::nPaths)
        .def_readwrite("monitor_dates", &SimParams::monitorDates);

    // ── TimeStep ──────────────────────────────────────────────────
    py::class_<TimeStep>(m, "TimeStep")
        .def_readonly("t",            &TimeStep::t)
        .def_readonly("epe",          &TimeStep::epe)
        .def_readonly("surv_prob",    &TimeStep::survProb)
        .def_readonly("contribution", &TimeStep::contribution);

    // ── CVAResult ─────────────────────────────────────────────────
    py::class_<CVAResult>(m, "CVAResult")
        .def_readonly("cva",     &CVAResult::cva)
        .def_readonly("profile", &CVAResult::profile)
        .def("to_dataframe", [](const CVAResult& r) {
            py::dict d;
            std::vector<double> ts, epes, sps, contribs;
            ts.reserve(r.profile.size());
            epes.reserve(r.profile.size());
            sps.reserve(r.profile.size());
            contribs.reserve(r.profile.size());
            for (const auto& step : r.profile) {
                ts.push_back(step.t);
                epes.push_back(step.epe);
                sps.push_back(step.survProb);
                contribs.push_back(step.contribution);
            }
            d["t"]            = ts;
            d["epe"]          = epes;
            d["surv_prob"]    = sps;
            d["contribution"] = contribs;
            py::object pd = py::module_::import("pandas");
            return pd.attr("DataFrame")(d);
        }, "Return profile as a pandas DataFrame with columns: t, epe, surv_prob, contribution.");

    // ── CVACalculator ─────────────────────────────────────────────
    py::class_<CVACalculator>(m, "CVACalculator")
        .def(py::init<const qf::models::HullWhite&,
                      const ICreditCurve&,
                      double,
                      SimParams>(),
             py::arg("hw"), py::arg("credit"), py::arg("lgd"), py::arg("params"),
             py::keep_alive<1,2>(),   // calculator keeps hw alive
             py::keep_alive<1,3>())   // calculator keeps credit alive
        .def("compute", &CVACalculator::compute,
             py::arg("netting_set"), py::arg("env"),
             "Run CVA simulation. Returns CVAResult.");
}
```

- [ ] **Step 2: Build the Python module**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . --target qfxva 2>&1 | tail -10
```

Expected: `qfxva.so` created in `build/` (or `build/src/`).

- [ ] **Step 3: Write Python tests**

Create `web/tests/test_xva.py` (in the Quant_Finance project, not MarketDataFeed):

```python
"""Python-level tests for qfxva bindings."""
import sys, os, pytest

# Locate the built module
BUILD_DIR = os.path.join(os.path.dirname(__file__), "..", "build")
sys.path.insert(0, BUILD_DIR)
sys.path.insert(0, os.path.join(BUILD_DIR, "src"))

try:
    import qfxva
    import qfpy
except ImportError as e:
    pytest.skip(f"C++ modules not built: {e}", allow_module_level=True)


def _make_hw():
    curve = qfpy.YieldCurve([0.5, 1.0, 2.0, 5.0, 10.0], [0.04]*5)
    return qfpy.HullWhite(a=0.1, sigma=0.01, curve=curve)


def _make_env():
    curve = qfpy.YieldCurve([0.5, 1.0, 2.0, 5.0, 10.0], [0.04]*5)
    return qfpy.MarketEnvironment(curve)


def _quarterly(mat):
    import numpy as np
    return list(np.arange(0.25, mat + 1e-9, 0.25))


def test_result_to_dataframe():
    hw     = _make_hw()
    credit = qfxva.FlatHazardRate(lambda_=0.02)
    params = qfxva.SimParams(n_paths=200, monitor_dates=_quarterly(3.0), seed=42)
    calc   = qfxva.CVACalculator(hw, credit, lgd=0.6, params=params)

    ns = qfxva.NettingSet()
    ns.add(notional=1e6, fixed_rate=0.05, maturity=3.0,
           frequency=1.0, swap_type=qfxva.SwapType.Payer)

    result = calc.compute(ns, _make_env())
    df = result.to_dataframe()

    assert list(df.columns) == ["t", "epe", "surv_prob", "contribution"]
    assert len(df) == len(_quarterly(3.0))


def test_cva_positive_for_itm_payer():
    hw     = _make_hw()
    credit = qfxva.FlatHazardRate(lambda_=0.02)
    params = qfxva.SimParams(n_paths=500, monitor_dates=_quarterly(5.0), seed=42)
    calc   = qfxva.CVACalculator(hw, credit, lgd=0.6, params=params)

    ns = qfxva.NettingSet()
    # Deep ITM payer: fixed rate 10% on a 4% curve
    ns.add(notional=1e6, fixed_rate=0.10, maturity=5.0,
           frequency=1.0, swap_type=qfxva.SwapType.Payer)

    result = calc.compute(ns, _make_env())
    assert result.cva > 0.0
```

- [ ] **Step 4: Run Python tests**

```bash
cd /home/claudio/Git/Quant_Finance
PYTHONPATH=build:build/src python -m pytest web/tests/test_xva.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
cd /home/claudio/Git/Quant_Finance
git add src/python_bindings/xva_bindings.cpp web/tests/test_xva.py
git commit -m "feat(xva): add pybind11 qfxva module with CVAResult.to_dataframe()"
```

---

## Final verification

- [ ] **Run full C++ suite**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . --target all 2>&1 | tail -5
ctest --output-on-failure 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Smoke test from Python**

```bash
cd /home/claudio/Git/Quant_Finance
PYTHONPATH=build:build/src python3 - <<'EOF'
import qfxva, qfpy
curve  = qfpy.YieldCurve([0.5,1,2,5,10], [0.04]*5)
hw     = qfpy.HullWhite(a=0.1, sigma=0.01, curve=curve)
credit = qfxva.FlatHazardRate(lambda_=0.02)
dates  = [i*0.25 for i in range(1, 21)]  # quarterly, 5Y
params = qfxva.SimParams(n_paths=2000, monitor_dates=dates, seed=42)
calc   = qfxva.CVACalculator(hw, credit, lgd=0.6, params=params)
ns     = qfxva.NettingSet()
ns.add(1e6, 0.10, 5.0, 1.0, qfxva.SwapType.Payer)
env    = qfpy.MarketEnvironment(curve)
r      = calc.compute(ns, env)
print(f"CVA = {r.cva:,.2f}")
print(r.to_dataframe().head())
EOF
```

Expected: prints a positive CVA and a 5-row DataFrame.

- [ ] **Push to remote**

```bash
cd /home/claudio/Git/Quant_Finance
git push origin feature/qf-extensions
```
