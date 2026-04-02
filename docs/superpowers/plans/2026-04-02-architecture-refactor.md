# Architecture Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce `MarketEnvironment`, `IRateModel`, `IEquityModel`, `IPricingEngine` (Strategy), `IUnderlying`, and `EngineFactory` — while preserving all existing `examples/` and Python binding APIs.

**Architecture:** Thin interfaces per domain (models, engines, underlyings) connected via a central `MarketEnvironment` context. `Instrument::pv()` transitions from `YieldCurve` to `MarketEnvironment`; legacy `pv(YieldCurve)` overloads preserve backward-compat. Free engine functions become thin wrappers over concrete `IPricingEngine` classes.

**Tech Stack:** C++17, GoogleTest, CMake 3.15+, pybind11 (optional). Build: `cd build && cmake --build . --target all && ctest --output-on-failure`.

---

## File Map

### New files
| Header | Implementation |
|--------|---------------|
| `include/qf/core/market_environment.hpp` | `src/core/market_environment.cpp` |
| `include/qf/models/irate_model.hpp` | *(header-only)* |
| `include/qf/models/iequity_model.hpp` | *(header-only)* |
| `include/qf/models/heston_model.hpp` | `src/models/heston_model.cpp` |
| `include/qf/models/bs_model.hpp` | `src/models/bs_model.cpp` |
| `include/qf/pricingengines/ipricing_engine.hpp` | *(header-only)* |
| `include/qf/pricingengines/engine_factory.hpp` | `src/pricingengines/engine_factory.cpp` |
| `include/qf/instruments/iunderlying.hpp` | `src/instruments/iunderlying.cpp` |
| `tests/test_market_environment.cpp` | — |
| `tests/test_models_interfaces.cpp` | — |
| `tests/test_pricing_engines_oop.cpp` | — |
| `tests/test_underlyings.cpp` | — |

### Modified files
| File | Change |
|------|--------|
| `include/qf/instruments/instrument.hpp` | Add `engine_`, `pv(MarketEnv)`, legacy `pv(YieldCurve)`, `calculatePV(MarketEnv)` |
| `include/qf/instruments/option.hpp` | Add new constructor with `IUnderlying`; keep legacy constructor |
| `include/qf/instruments/swap.hpp` | Remove duplicate state from `InterestRateSwap`; add `npv(MarketEnv)` overload |
| `include/qf/models/vasicek.hpp` | Add `public IRateModel`, `override` |
| `include/qf/models/hullwhite.hpp` | Add `public IRateModel`, `override` |
| `include/qf/pricingengines/blackscholes.hpp` | Add `BlackScholesEngine : IPricingEngine` |
| `include/qf/pricingengines/montecarlo.hpp` | Add `MonteCarloEngine : IPricingEngine` |
| `include/qf/pricingengines/binomialtree.hpp` | Add `BinomialTreeEngine : IPricingEngine` |
| `include/qf/pricingengines/finite_difference.hpp` | Add `FDMEngine : IPricingEngine` |
| `include/qf/pricingengines/heston.hpp` | Add `HestonEngine : IPricingEngine` |
| `src/instruments/option.cpp` | Update `calculatePV` to use `MarketEnvironment` |
| `src/instruments/swap.cpp` | Remove duplicate members; add `MarketEnv` overloads |
| `src/CMakeLists.txt` | Register new `.cpp` files |
| `tests/CMakeLists.txt` | Register new test files |

### Untouched (backward-compat guarantee)
- All `examples/*.cpp`
- `src/python_bindings/qfpy.cpp`
- `include/qf/instruments/bond.hpp`, `src/instruments/bond.cpp`
- All existing `tests/test_*.cpp`

---

## Task 1: MarketEnvironment

**Files:**
- Create: `include/qf/core/market_environment.hpp`
- Create: `src/core/market_environment.cpp`
- Create: `tests/test_market_environment.cpp`

- [ ] **Step 1.1: Write the failing tests**

```cpp
// tests/test_market_environment.cpp
#include <gtest/gtest.h>
#include <qf/core/market_environment.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/interpolation.hpp>
#include <stdexcept>

using namespace qf::core;
using namespace qf::termstructure;
using namespace qf::math;

namespace {
    YieldCurve flatCurve(double r) {
        return YieldCurve({0.5,1.0,2.0,5.0,10.0},{r,r,r,r,r},
                          InterpolationMethod::Linear);
    }
}

TEST(MarketEnvironment, DefaultCurveRoundTrip) {
    MarketEnvironment env(flatCurve(0.05));
    EXPECT_NEAR(env.curve().zeroRate(1.0), 0.05, 1e-9);
}

TEST(MarketEnvironment, NamedCurveRoundTrip) {
    MarketEnvironment env;
    env.addCurve("USD", flatCurve(0.05));
    env.addCurve("MXN", flatCurve(0.10));
    EXPECT_NEAR(env.curve("USD").zeroRate(1.0), 0.05, 1e-9);
    EXPECT_NEAR(env.curve("MXN").zeroRate(1.0), 0.10, 1e-9);
}

TEST(MarketEnvironment, MissingCurveThrows) {
    MarketEnvironment env;
    EXPECT_THROW(env.curve("USD"), std::out_of_range);
    EXPECT_THROW(env.curve(), std::out_of_range);
}

TEST(MarketEnvironment, SpotAndVolRoundTrip) {
    MarketEnvironment env;
    env.setSpot("AAPL", 150.0);
    env.setVolatility("AAPL", 0.25);
    EXPECT_DOUBLE_EQ(env.spot("AAPL"), 150.0);
    EXPECT_DOUBLE_EQ(env.volatility("AAPL"), 0.25);
}

TEST(MarketEnvironment, MissingSpotThrows) {
    MarketEnvironment env;
    EXPECT_THROW(env.spot("AAPL"), std::out_of_range);
    EXPECT_THROW(env.volatility("AAPL"), std::out_of_range);
}
```

- [ ] **Step 1.2: Run tests to verify they fail**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . --target all 2>&1 | tail -5
```
Expected: compile error — `qf/core/market_environment.hpp` not found.

- [ ] **Step 1.3: Write the header**

```cpp
// include/qf/core/market_environment.hpp
#pragma once
#include <string>
#include <unordered_map>
#include <qf/termstructure/yieldcurve.hpp>

namespace qf::core {

class MarketEnvironment {
public:
    MarketEnvironment() = default;

    /// Convenience constructor: adds curve under the "default" key.
    explicit MarketEnvironment(termstructure::YieldCurve defaultCurve);

    void addCurve(const std::string& name, termstructure::YieldCurve curve);

    /// @throws std::out_of_range if name not found.
    const termstructure::YieldCurve& curve(const std::string& name = "default") const;

    void setSpot(const std::string& ticker, double spot);
    void setVolatility(const std::string& ticker, double vol);

    /// @throws std::out_of_range if ticker not found.
    double spot(const std::string& ticker) const;

    /// @throws std::out_of_range if ticker not found.
    double volatility(const std::string& ticker) const;

private:
    std::unordered_map<std::string, termstructure::YieldCurve> curves_;
    std::unordered_map<std::string, double> spots_;
    std::unordered_map<std::string, double> vols_;
};

} // namespace qf::core
```

- [ ] **Step 1.4: Write the implementation**

```cpp
// src/core/market_environment.cpp
#include <qf/core/market_environment.hpp>
#include <stdexcept>

namespace qf::core {

MarketEnvironment::MarketEnvironment(termstructure::YieldCurve defaultCurve) {
    curves_.emplace("default", std::move(defaultCurve));
}

void MarketEnvironment::addCurve(const std::string& name, termstructure::YieldCurve curve) {
    curves_.insert_or_assign(name, std::move(curve));
}

const termstructure::YieldCurve& MarketEnvironment::curve(const std::string& name) const {
    auto it = curves_.find(name);
    if (it == curves_.end())
        throw std::out_of_range("MarketEnvironment: curve '" + name + "' not found");
    return it->second;
}

void MarketEnvironment::setSpot(const std::string& ticker, double spot) {
    spots_.insert_or_assign(ticker, spot);
}

void MarketEnvironment::setVolatility(const std::string& ticker, double vol) {
    vols_.insert_or_assign(ticker, vol);
}

double MarketEnvironment::spot(const std::string& ticker) const {
    auto it = spots_.find(ticker);
    if (it == spots_.end())
        throw std::out_of_range("MarketEnvironment: spot '" + ticker + "' not found");
    return it->second;
}

double MarketEnvironment::volatility(const std::string& ticker) const {
    auto it = vols_.find(ticker);
    if (it == vols_.end())
        throw std::out_of_range("MarketEnvironment: volatility '" + ticker + "' not found");
    return it->second;
}

} // namespace qf::core
```

- [ ] **Step 1.5: Register in CMake**

In `src/CMakeLists.txt`, add `core/market_environment.cpp` to the `add_library(qf ...)` sources list.

In `tests/CMakeLists.txt`, add `test_market_environment.cpp` to the test executable sources (follow the same pattern as existing test files in that CMakeLists.txt).

- [ ] **Step 1.6: Build and run new tests**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . --target all 2>&1 | tail -10
ctest --output-on-failure -R MarketEnvironment
```
Expected: all 5 new tests PASS. All existing tests still PASS.

- [ ] **Step 1.7: Commit**

```bash
cd /home/claudio/Git/Quant_Finance
git add include/qf/core/market_environment.hpp \
        src/core/market_environment.cpp \
        tests/test_market_environment.cpp \
        src/CMakeLists.txt \
        tests/CMakeLists.txt
git commit -m "feat: add MarketEnvironment — central market data container"
```

---

## Task 2: IRateModel + Vasicek/HullWhite override

**Files:**
- Create: `include/qf/models/irate_model.hpp`
- Modify: `include/qf/models/vasicek.hpp`
- Modify: `include/qf/models/hullwhite.hpp`
- Create: `tests/test_models_interfaces.cpp`

- [ ] **Step 2.1: Write failing test for IRateModel polymorphism**

```cpp
// tests/test_models_interfaces.cpp
#include <gtest/gtest.h>
#include <qf/models/irate_model.hpp>
#include <qf/models/vasicek.hpp>
#include <qf/models/hullwhite.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/interpolation.hpp>
#include <memory>
#include <cmath>

using namespace qf::models;
using namespace qf::termstructure;
using namespace qf::math;

namespace {
    YieldCurve testCurve() {
        return YieldCurve({0.5,1.0,2.0,5.0,10.0},
                          {0.03,0.035,0.04,0.045,0.05},
                          InterpolationMethod::CubicSpline);
    }
}

TEST(IRateModel, VasicekIsIRateModel) {
    std::shared_ptr<IRateModel> m = std::make_shared<Vasicek>(0.5, 0.05, 0.01, 0.03);
    EXPECT_GT(m->bondPrice(1.0), 0.0);
    EXPECT_GT(m->zeroRate(1.0), 0.0);
    EXPECT_EQ(m->simulate(1.0, 10, 42).size(), 11u);
}

TEST(IRateModel, HullWhiteIsIRateModel) {
    auto curve = testCurve();
    std::shared_ptr<IRateModel> m = std::make_shared<HullWhite>(0.1, 0.015, curve);
    EXPECT_NEAR(m->bondPrice(1.0), curve.discountFactor(1.0), 1e-12);
    EXPECT_GT(m->zeroRate(1.0), 0.0);
    // HullWhite has no simulate() in existing API — test size once added
}

TEST(IRateModel, PolymorphicDispatch) {
    std::vector<std::shared_ptr<IRateModel>> models;
    models.push_back(std::make_shared<Vasicek>(0.5, 0.05, 0.01, 0.03));
    auto curve = testCurve();
    models.push_back(std::make_shared<HullWhite>(0.1, 0.015, curve));
    for (auto& m : models) {
        EXPECT_GT(m->bondPrice(5.0), 0.0);
        EXPECT_LT(m->bondPrice(5.0), 1.0);
    }
}
```

- [ ] **Step 2.2: Run to verify failure**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . 2>&1 | tail -5
```
Expected: error — `irate_model.hpp` not found.

- [ ] **Step 2.3: Create IRateModel interface**

```cpp
// include/qf/models/irate_model.hpp
#pragma once
#include <vector>

namespace qf::models {

/// Abstract interface for short-rate models.
class IRateModel {
public:
    virtual ~IRateModel() = default;

    /// @brief Analytical zero-coupon bond price P(0, T).
    virtual double bondPrice(double T) const = 0;

    /// @brief Continuously compounded zero rate for maturity T.
    virtual double zeroRate(double T) const = 0;

    /// @brief Simulate a short-rate path using Euler-Maruyama.
    /// @return Vector of size (steps+1): path[0] = r0, path[steps] = r(T).
    virtual std::vector<double> simulate(double T, int steps,
                                          unsigned seed = 42) const = 0;
};

} // namespace qf::models
```

- [ ] **Step 2.4: Update Vasicek header to inherit IRateModel**

In `include/qf/models/vasicek.hpp`, change:
```cpp
// Before
class Vasicek {

// After
#include <qf/models/irate_model.hpp>
class Vasicek : public IRateModel {
```

Mark the three public methods as `override`:
```cpp
double bondPrice(double T) const override;
double zeroRate(double T) const override;
std::vector<double> simulate(double T, int steps, unsigned seed = 42) const override;
```

No changes to `src/models/vasicek.cpp` — signatures are identical.

- [ ] **Step 2.5: Update HullWhite header to inherit IRateModel**

`HullWhite` currently lacks `simulate()`. Add it alongside the `override`s:

```cpp
// include/qf/models/hullwhite.hpp — full updated header
#pragma once
#include <vector>
#include <qf/models/irate_model.hpp>
#include <qf/termstructure/yieldcurve.hpp>

namespace qf::models {

// dr(t) = [theta(t) - a*r(t)]*dt + sigma*dW(t)
class HullWhite : public IRateModel {
public:
    HullWhite(double a, double sigma, const termstructure::YieldCurve& curve);

    double bondPrice(double T) const override;
    double zeroRate(double T) const override;

    /// Euler-Maruyama simulation using the calibrated theta(t).
    std::vector<double> simulate(double T, int steps,
                                  unsigned seed = 42) const override;

private:
    double a_, sigma_;
    const termstructure::YieldCurve& curve_;

    double B(double T) const;
    double A(double T) const;
    double theta(double t) const;  // calibrated drift
};

} // namespace qf::models
```

- [ ] **Step 2.6: Implement HullWhite::simulate() and HullWhite::theta()**

Add to `src/models/hullwhite.cpp`:
```cpp
#include <random>
#include <cmath>

double HullWhite::theta(double t) const {
    // theta(t) = df/dt(0,t) + a*f(0,t) + sigma^2/(2a)*(1 - exp(-2a*t))
    // Approximate df/dt numerically
    const double dt = 1e-5;
    double f1 = curve_.forwardRate(t, t + dt);
    double f0 = (t > dt) ? curve_.forwardRate(t - dt, t) : f1;
    double dfdt = (f1 - f0) / dt;
    double ft = curve_.forwardRate(t, t + 1e-4);
    return dfdt + a_ * ft + (sigma_ * sigma_ / (2.0 * a_)) * (1.0 - std::exp(-2.0 * a_ * t));
}

std::vector<double> HullWhite::simulate(double T, int steps, unsigned seed) const {
    std::mt19937_64 rng(seed);
    std::normal_distribution<double> N(0.0, 1.0);

    double dt = T / steps;
    double sqdt = std::sqrt(dt);
    double r0 = curve_.zeroRate(1e-4);  // approximate r(0) as short end of curve

    std::vector<double> path(steps + 1);
    path[0] = r0;
    for (int i = 0; i < steps; ++i) {
        double t = i * dt;
        path[i + 1] = path[i]
            + (theta(t) - a_ * path[i]) * dt
            + sigma_ * sqdt * N(rng);
    }
    return path;
}
```

- [ ] **Step 2.7: Build and run tests**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . --target all 2>&1 | tail -10
ctest --output-on-failure -R "IRateModel|Vasicek|HullWhite"
```
Expected: all new interface tests PASS. Existing `Vasicek` and `HullWhite` tests still PASS.

- [ ] **Step 2.8: Commit**

```bash
cd /home/claudio/Git/Quant_Finance
git add include/qf/models/irate_model.hpp \
        include/qf/models/vasicek.hpp \
        include/qf/models/hullwhite.hpp \
        src/models/hullwhite.cpp \
        tests/test_models_interfaces.cpp \
        tests/CMakeLists.txt
git commit -m "feat: add IRateModel interface; Vasicek and HullWhite implement it"
```

---

## Task 3: IEquityModel + HestonModel split + BlackScholesModel

**Files:**
- Create: `include/qf/models/iequity_model.hpp`
- Create: `include/qf/models/heston_model.hpp` + `src/models/heston_model.cpp`
- Create: `include/qf/models/bs_model.hpp` + `src/models/bs_model.cpp`

- [ ] **Step 3.1: Write failing tests** (append to `tests/test_models_interfaces.cpp`)

```cpp
// Add to tests/test_models_interfaces.cpp:
#include <qf/models/iequity_model.hpp>
#include <qf/models/heston_model.hpp>
#include <qf/models/bs_model.hpp>

TEST(IEquityModel, HestonModelIsIEquityModel) {
    qf::models::HestonParams hp{0.04, 2.0, 0.04, 0.3, -0.7};
    std::shared_ptr<IEquityModel> m = std::make_shared<qf::models::HestonModel>(hp);
    auto path = m->simulate(100.0, 1.0, 252, 42);
    EXPECT_EQ(path.size(), 253u);
    EXPECT_DOUBLE_EQ(path[0], 100.0);
    for (double S : path) EXPECT_GT(S, 0.0);
}

TEST(IEquityModel, BSModelIsIEquityModel) {
    std::shared_ptr<IEquityModel> m =
        std::make_shared<qf::models::BlackScholesModel>(0.05, 0.0, 0.20);
    auto path = m->simulate(100.0, 1.0, 252, 42);
    EXPECT_EQ(path.size(), 253u);
    EXPECT_DOUBLE_EQ(path[0], 100.0);
    for (double S : path) EXPECT_GT(S, 0.0);
}

TEST(IEquityModel, PolymorphicEquityDispatch) {
    qf::models::HestonParams hp{0.04, 2.0, 0.04, 0.3, -0.7};
    std::vector<std::shared_ptr<IEquityModel>> models = {
        std::make_shared<qf::models::HestonModel>(hp),
        std::make_shared<qf::models::BlackScholesModel>(0.05, 0.0, 0.20)
    };
    for (auto& m : models) {
        auto p = m->simulate(100.0, 1.0, 52, 1);
        EXPECT_EQ(p.size(), 53u);
    }
}
```

- [ ] **Step 3.2: Create IEquityModel interface**

```cpp
// include/qf/models/iequity_model.hpp
#pragma once
#include <vector>

namespace qf::models {

/// Abstract interface for equity/asset price models.
class IEquityModel {
public:
    virtual ~IEquityModel() = default;

    /// @brief Simulate risk-neutral price path S(0)...S(T).
    /// @return Vector of size (steps+1): path[0] = S0.
    virtual std::vector<double> simulate(double S0, double T,
                                          int steps,
                                          unsigned seed = 42) const = 0;

    /// @brief Risk-neutral density p(S, T) — optional, default 0.
    virtual double riskNeutralDensity(double /*S*/, double /*T*/) const { return 0.0; }
};

} // namespace qf::models
```

- [ ] **Step 3.3: Create HestonModel — model extracted from pricingengines/heston.cpp**

```cpp
// include/qf/models/heston_model.hpp
#pragma once
#include <vector>
#include <qf/models/iequity_model.hpp>

namespace qf::models {

struct HestonParams {
    double v0;      ///< Initial variance
    double kappa;   ///< Mean reversion speed
    double theta;   ///< Long-run variance
    double sigma;   ///< Vol of vol
    double rho;     ///< Spot-variance correlation
};

/// Heston (1993) stochastic volatility model.
class HestonModel : public IEquityModel {
public:
    explicit HestonModel(const HestonParams& params);

    std::vector<double> simulate(double S0, double T,
                                  int steps,
                                  unsigned seed = 42) const override;

    const HestonParams& params() const { return params_; }

private:
    HestonParams params_;
};

} // namespace qf::models
```

```cpp
// src/models/heston_model.cpp
#include <qf/models/heston_model.hpp>
#include <random>
#include <cmath>
#include <stdexcept>

namespace qf::models {

HestonModel::HestonModel(const HestonParams& p) : params_(p) {
    if (p.v0 <= 0.0 || p.theta <= 0.0 || p.kappa <= 0.0)
        throw std::invalid_argument("HestonModel: v0, theta, kappa must be positive");
    if (p.sigma <= 0.0)
        throw std::invalid_argument("HestonModel: sigma must be positive");
    if (std::abs(p.rho) > 1.0)
        throw std::invalid_argument("HestonModel: |rho| must be <= 1");
}

std::vector<double> HestonModel::simulate(double S0, double T,
                                           int steps, unsigned seed) const {
    if (S0 <= 0.0 || T <= 0.0 || steps <= 0)
        throw std::invalid_argument("HestonModel::simulate: invalid parameters");

    std::mt19937_64 rng(seed);
    std::normal_distribution<double> N(0.0, 1.0);

    double dt = T / steps;
    double sqdt = std::sqrt(dt);
    double rho2 = std::sqrt(1.0 - params_.rho * params_.rho);

    std::vector<double> path(steps + 1);
    path[0] = S0;
    double S = S0, v = params_.v0;

    for (int i = 0; i < steps; ++i) {
        double z1 = N(rng);
        double z2 = params_.rho * z1 + rho2 * N(rng);
        double vp = std::max(v, 0.0);
        double svp = std::sqrt(vp);
        S *= std::exp(-0.5 * vp * dt + svp * sqdt * z1);
        v += params_.kappa * (params_.theta - vp) * dt + params_.sigma * svp * sqdt * z2;
        path[i + 1] = S;
    }
    return path;
}

} // namespace qf::models
```

- [ ] **Step 3.4: Create BlackScholesModel**

```cpp
// include/qf/models/bs_model.hpp
#pragma once
#include <vector>
#include <qf/models/iequity_model.hpp>

namespace qf::models {

/// Geometric Brownian Motion (Black-Scholes) equity model.
class BlackScholesModel : public IEquityModel {
public:
    /// @param r Risk-free rate, q dividend yield, sigma volatility.
    BlackScholesModel(double r, double q, double sigma);

    std::vector<double> simulate(double S0, double T,
                                  int steps,
                                  unsigned seed = 42) const override;

private:
    double r_, q_, sigma_;
};

} // namespace qf::models
```

```cpp
// src/models/bs_model.cpp
#include <qf/models/bs_model.hpp>
#include <random>
#include <cmath>
#include <stdexcept>

namespace qf::models {

BlackScholesModel::BlackScholesModel(double r, double q, double sigma)
    : r_(r), q_(q), sigma_(sigma) {
    if (sigma <= 0.0)
        throw std::invalid_argument("BlackScholesModel: sigma must be positive");
}

std::vector<double> BlackScholesModel::simulate(double S0, double T,
                                                 int steps, unsigned seed) const {
    if (S0 <= 0.0 || T <= 0.0 || steps <= 0)
        throw std::invalid_argument("BlackScholesModel::simulate: invalid parameters");

    std::mt19937_64 rng(seed);
    std::normal_distribution<double> N(0.0, 1.0);

    double dt = T / steps;
    double drift = (r_ - q_ - 0.5 * sigma_ * sigma_) * dt;
    double diffusion = sigma_ * std::sqrt(dt);

    std::vector<double> path(steps + 1);
    path[0] = S0;
    for (int i = 0; i < steps; ++i)
        path[i + 1] = path[i] * std::exp(drift + diffusion * N(rng));
    return path;
}

} // namespace qf::models
```

- [ ] **Step 3.5: Register new files in CMake**

In `src/CMakeLists.txt`, add to `add_library(qf ...)`:
```
models/heston_model.cpp
models/bs_model.cpp
```

In `tests/CMakeLists.txt`, ensure `test_models_interfaces.cpp` (already added in Task 2) is in the sources.

- [ ] **Step 3.6: Build and run tests**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . --target all 2>&1 | tail -10
ctest --output-on-failure -R "IEquityModel|IRateModel"
```
Expected: all new tests PASS. Existing `Heston` tests in `test_pricingengines.cpp` still PASS (they use `pricingengines::HestonParams` — unchanged).

- [ ] **Step 3.7: Commit**

```bash
cd /home/claudio/Git/Quant_Finance
git add include/qf/models/iequity_model.hpp \
        include/qf/models/heston_model.hpp \
        src/models/heston_model.cpp \
        include/qf/models/bs_model.hpp \
        src/models/bs_model.cpp \
        src/CMakeLists.txt
git commit -m "feat: add IEquityModel; HestonModel and BlackScholesModel implement it"
```

---

## Task 4: IPricingEngine interface

**Files:**
- Create: `include/qf/pricingengines/ipricing_engine.hpp`

- [ ] **Step 4.1: Create the interface**

No test needed here — the interface is abstract. Tests will come when concrete engines are implemented (Task 5).

```cpp
// include/qf/pricingengines/ipricing_engine.hpp
#pragma once
#include <string>
#include <qf/core/market_environment.hpp>

namespace qf::pricingengines {

/// Strategy interface for pricing engines.
class IPricingEngine {
public:
    virtual ~IPricingEngine() = default;

    /// @brief Compute price given the market environment.
    virtual double price(const core::MarketEnvironment& env) const = 0;

    /// @brief Human-readable engine identifier (for logging/debugging).
    virtual std::string name() const = 0;
};

} // namespace qf::pricingengines
```

- [ ] **Step 4.2: Verify it compiles**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . --target all 2>&1 | tail -5
```
Expected: build succeeds (header-only, no new `.cpp`).

- [ ] **Step 4.3: Commit**

```bash
cd /home/claudio/Git/Quant_Finance
git add include/qf/pricingengines/ipricing_engine.hpp
git commit -m "feat: add IPricingEngine strategy interface"
```

---

## Task 5: Concrete equity engines (BS, MC, BT, FDM)

**Files:**
- Modify: `include/qf/pricingengines/blackscholes.hpp`
- Modify: `include/qf/pricingengines/montecarlo.hpp`
- Modify: `include/qf/pricingengines/binomialtree.hpp`
- Modify: `include/qf/pricingengines/finite_difference.hpp`
- Create: `tests/test_pricing_engines_oop.cpp`

Each engine class holds `OptionParams` (or its relevant parameters), implements `IPricingEngine::price(MarketEnv)`, and the existing free function becomes a one-line wrapper.

- [ ] **Step 5.1: Write failing tests**

```cpp
// tests/test_pricing_engines_oop.cpp
#include <gtest/gtest.h>
#include <qf/pricingengines/ipricing_engine.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <qf/pricingengines/montecarlo.hpp>
#include <qf/pricingengines/binomialtree.hpp>
#include <qf/pricingengines/finite_difference.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/instruments/option.hpp>
#include <memory>
#include <cmath>

using namespace qf::pricingengines;
using namespace qf::instruments;
using namespace qf::core;

namespace {
    OptionParams atm() {
        return {100.0, 100.0, 0.05, 0.0, 0.20, 1.0,
                OptionType::Call, ExerciseType::European};
    }
    // Market env not needed by these engines (they carry params directly)
    MarketEnvironment emptyEnv() { return MarketEnvironment{}; }
}

TEST(BlackScholesEngine, IsIPricingEngine) {
    std::shared_ptr<IPricingEngine> e = std::make_shared<BlackScholesEngine>(atm());
    EXPECT_EQ(e->name(), "BlackScholes");
    double p = e->price(emptyEnv());
    // Must match existing free function
    EXPECT_NEAR(p, blackScholes(atm()).price, 1e-10);
}

TEST(MonteCarloEngine, IsIPricingEngine) {
    std::shared_ptr<IPricingEngine> e = std::make_shared<MonteCarloEngine>(atm(), 200000, 42);
    EXPECT_EQ(e->name(), "MonteCarlo");
    double p = e->price(emptyEnv());
    EXPECT_NEAR(p, monteCarloBSPrice(atm(), 200000, 42), 1e-10);
}

TEST(BinomialTreeEngine, IsIPricingEngine) {
    std::shared_ptr<IPricingEngine> e = std::make_shared<BinomialTreeEngine>(atm(), 500);
    EXPECT_EQ(e->name(), "BinomialTree");
    double p = e->price(emptyEnv());
    EXPECT_NEAR(p, binomialTreeBSPrice(atm(), 500), 1e-10);
}

TEST(FDMEngine, IsIPricingEngine) {
    std::shared_ptr<IPricingEngine> e =
        std::make_shared<FDMEngine>(atm(), 200, 200, FDMethod::CrankNicolson);
    EXPECT_EQ(e->name(), "FiniteDifference");
    double p = e->price(emptyEnv());
    EXPECT_NEAR(p, finiteDifferenceBSPrice(atm(), 200, 200, FDMethod::CrankNicolson), 1e-10);
}

TEST(PricingEngines, PutCallParityAcrossEngines) {
    OptionParams callP = atm();
    OptionParams putP  = {100,100,0.05,0.0,0.20,1.0,
                          OptionType::Put, ExerciseType::European};
    double parity = 100.0 * std::exp(-0.0) - 100.0 * std::exp(-0.05 * 1.0);

    for (auto& pair : std::vector<std::pair<
            std::shared_ptr<IPricingEngine>,
            std::shared_ptr<IPricingEngine>>>{
        {std::make_shared<BlackScholesEngine>(callP), std::make_shared<BlackScholesEngine>(putP)},
        {std::make_shared<BinomialTreeEngine>(callP,500), std::make_shared<BinomialTreeEngine>(putP,500)},
    }) {
        double c = pair.first->price(emptyEnv());
        double p = pair.second->price(emptyEnv());
        EXPECT_NEAR(c - p, parity, 0.05);  // 5ct tolerance for numerical methods
    }
}
```

- [ ] **Step 5.2: Run to verify compile failure**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . 2>&1 | tail -5
```
Expected: error — `BlackScholesEngine`, `MonteCarloEngine`, etc. not declared.

- [ ] **Step 5.3: Update blackscholes.hpp**

```cpp
// include/qf/pricingengines/blackscholes.hpp
#pragma once
#include <string>
#include <qf/instruments/option.hpp>
#include <qf/pricingengines/ipricing_engine.hpp>

namespace qf::pricingengines {

struct BSResult {
    double price, delta, gamma, vega, theta, rho;
};

/// Free function (preserved for backward-compat)
BSResult blackScholes(const instruments::OptionParams& params);

/// Implied vol via Brent (preserved)
double impliedVolatility(const instruments::OptionParams& params,
                         double marketPrice,
                         double tol = 1e-6, int maxIt = 100);

/// Strategy engine wrapping blackScholes()
class BlackScholesEngine : public IPricingEngine {
public:
    explicit BlackScholesEngine(instruments::OptionParams params);
    double price(const core::MarketEnvironment& env) const override;
    std::string name() const override { return "BlackScholes"; }
private:
    instruments::OptionParams params_;
};

} // namespace qf::pricingengines
```

Add to `src/pricingengines/blackscholes.cpp` (at the end):
```cpp
BlackScholesEngine::BlackScholesEngine(instruments::OptionParams params)
    : params_(std::move(params)) {}

double BlackScholesEngine::price(const core::MarketEnvironment& /*env*/) const {
    return blackScholes(params_).price;
}
```

- [ ] **Step 5.4: Update montecarlo.hpp**

```cpp
// include/qf/pricingengines/montecarlo.hpp
#pragma once
#include <string>
#include <qf/instruments/option.hpp>
#include <qf/pricingengines/ipricing_engine.hpp>

namespace qf::pricingengines {

/// Free function (preserved)
double monteCarloBSPrice(const instruments::OptionParams& params,
                         int N = 100000, unsigned seed = 42);

class MonteCarloEngine : public IPricingEngine {
public:
    MonteCarloEngine(instruments::OptionParams params, int N = 100000, unsigned seed = 42);
    double price(const core::MarketEnvironment& env) const override;
    std::string name() const override { return "MonteCarlo"; }
private:
    instruments::OptionParams params_;
    int N_;
    unsigned seed_;
};

} // namespace qf::pricingengines
```

Add to `src/pricingengines/montecarlo.cpp`:
```cpp
MonteCarloEngine::MonteCarloEngine(instruments::OptionParams params, int N, unsigned seed)
    : params_(std::move(params)), N_(N), seed_(seed) {}

double MonteCarloEngine::price(const core::MarketEnvironment& /*env*/) const {
    return monteCarloBSPrice(params_, N_, seed_);
}
```

- [ ] **Step 5.5: Update binomialtree.hpp**

```cpp
// include/qf/pricingengines/binomialtree.hpp
#pragma once
#include <string>
#include <qf/instruments/option.hpp>
#include <qf/pricingengines/ipricing_engine.hpp>

namespace qf::pricingengines {

/// Free function (preserved)
double binomialTreeBSPrice(const instruments::OptionParams& params, int nSteps = 1000);

class BinomialTreeEngine : public IPricingEngine {
public:
    BinomialTreeEngine(instruments::OptionParams params, int nSteps = 1000);
    double price(const core::MarketEnvironment& env) const override;
    std::string name() const override { return "BinomialTree"; }
private:
    instruments::OptionParams params_;
    int nSteps_;
};

} // namespace qf::pricingengines
```

Add to `src/pricingengines/binomialtree.cpp`:
```cpp
BinomialTreeEngine::BinomialTreeEngine(instruments::OptionParams params, int nSteps)
    : params_(std::move(params)), nSteps_(nSteps) {}

double BinomialTreeEngine::price(const core::MarketEnvironment& /*env*/) const {
    return binomialTreeBSPrice(params_, nSteps_);
}
```

- [ ] **Step 5.6: Update finite_difference.hpp**

```cpp
// include/qf/pricingengines/finite_difference.hpp
#pragma once
#include <string>
#include <qf/instruments/option.hpp>
#include <qf/pricingengines/ipricing_engine.hpp>

namespace qf::pricingengines {

enum class FDMethod { Explicit, Implicit, CrankNicolson };

/// Free function (preserved)
double finiteDifferenceBSPrice(const instruments::OptionParams& params,
                               int nS = 200, int nT = 200,
                               FDMethod method = FDMethod::CrankNicolson);

class FDMEngine : public IPricingEngine {
public:
    FDMEngine(instruments::OptionParams params,
              int nS = 200, int nT = 200,
              FDMethod method = FDMethod::CrankNicolson);
    double price(const core::MarketEnvironment& env) const override;
    std::string name() const override { return "FiniteDifference"; }
private:
    instruments::OptionParams params_;
    int nS_, nT_;
    FDMethod method_;
};

} // namespace qf::pricingengines
```

Add to `src/pricingengines/finite_difference.cpp`:
```cpp
FDMEngine::FDMEngine(instruments::OptionParams params, int nS, int nT, FDMethod method)
    : params_(std::move(params)), nS_(nS), nT_(nT), method_(method) {}

double FDMEngine::price(const core::MarketEnvironment& /*env*/) const {
    return finiteDifferenceBSPrice(params_, nS_, nT_, method_);
}
```

- [ ] **Step 5.7: Register new test file in CMake**

In `tests/CMakeLists.txt`, add `test_pricing_engines_oop.cpp` to sources.

- [ ] **Step 5.8: Build and run tests**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . --target all 2>&1 | tail -10
ctest --output-on-failure -R "BlackScholesEngine|MonteCarloEngine|BinomialTreeEngine|FDMEngine|PricingEngines"
```
Expected: all new OOP tests PASS. All existing `test_pricingengines.cpp` tests (which use the free functions) still PASS.

- [ ] **Step 5.9: Commit**

```bash
cd /home/claudio/Git/Quant_Finance
git add include/qf/pricingengines/blackscholes.hpp \
        include/qf/pricingengines/montecarlo.hpp \
        include/qf/pricingengines/binomialtree.hpp \
        include/qf/pricingengines/finite_difference.hpp \
        src/pricingengines/blackscholes.cpp \
        src/pricingengines/montecarlo.cpp \
        src/pricingengines/binomialtree.cpp \
        src/pricingengines/finite_difference.cpp \
        tests/test_pricing_engines_oop.cpp \
        tests/CMakeLists.txt
git commit -m "feat: wrap BS, MC, BT, FDM free functions as IPricingEngine classes"
```

---

## Task 6: HestonEngine

**Files:**
- Modify: `include/qf/pricingengines/heston.hpp`
- Modify: `src/pricingengines/heston.cpp`

The existing `pricingengines::HestonParams` is kept as-is (used by `qfpy.cpp`). `HestonEngine` composes it.

- [ ] **Step 6.1: Write failing tests** (append to `tests/test_pricing_engines_oop.cpp`)

```cpp
// Add to tests/test_pricing_engines_oop.cpp:
#include <qf/pricingengines/heston.hpp>

TEST(HestonEngine, IsIPricingEngine) {
    OptionParams opt = {100, 100, 0.05, 0.0, 0.0, 1.0,
                        OptionType::Call, ExerciseType::European};
    HestonParams hp{0.04, 2.0, 0.04, 0.3, -0.7};
    std::shared_ptr<IPricingEngine> e = std::make_shared<HestonEngine>(opt, hp);
    EXPECT_EQ(e->name(), "Heston");
    double p = e->price(emptyEnv());
    EXPECT_NEAR(p, hestonPrice(opt, hp), 1e-10);
}
```

- [ ] **Step 6.2: Update heston.hpp**

```cpp
// include/qf/pricingengines/heston.hpp
#pragma once
#include <string>
#include <qf/instruments/option.hpp>
#include <qf/pricingengines/ipricing_engine.hpp>

namespace qf::pricingengines {

struct HestonParams {
    double v0, kappa, theta, sigma, rho;
};

/// Free functions (preserved for qfpy backward-compat)
double hestonPrice(const instruments::OptionParams& opt, const HestonParams& heston);
double hestonMonteCarlo(const instruments::OptionParams& opt,
                        const HestonParams& heston,
                        int nPaths = 100000, int nSteps = 252, unsigned seed = 42);

class HestonEngine : public IPricingEngine {
public:
    HestonEngine(instruments::OptionParams opt, HestonParams heston);
    double price(const core::MarketEnvironment& env) const override;
    std::string name() const override { return "Heston"; }
private:
    instruments::OptionParams opt_;
    HestonParams heston_;
};

} // namespace qf::pricingengines
```

- [ ] **Step 6.3: Add HestonEngine implementation to heston.cpp**

Append at the end of `src/pricingengines/heston.cpp`:
```cpp
HestonEngine::HestonEngine(instruments::OptionParams opt, HestonParams heston)
    : opt_(std::move(opt)), heston_(std::move(heston)) {}

double HestonEngine::price(const core::MarketEnvironment& /*env*/) const {
    return hestonPrice(opt_, heston_);
}
```

- [ ] **Step 6.4: Build and run**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . --target all 2>&1 | tail -10
ctest --output-on-failure -R "HestonEngine|Heston"
```
Expected: all Heston tests PASS.

- [ ] **Step 6.5: Commit**

```bash
cd /home/claudio/Git/Quant_Finance
git add include/qf/pricingengines/heston.hpp \
        src/pricingengines/heston.cpp
git commit -m "feat: add HestonEngine : IPricingEngine"
```

---

## Task 7: EngineFactory

**Files:**
- Create: `include/qf/pricingengines/engine_factory.hpp`
- Create: `src/pricingengines/engine_factory.cpp`

- [ ] **Step 7.1: Write failing tests** (append to `tests/test_pricing_engines_oop.cpp`)

```cpp
// Add to tests/test_pricing_engines_oop.cpp:
#include <qf/pricingengines/engine_factory.hpp>

TEST(EngineFactory, MakesBlackScholesEngine) {
    auto e = EngineFactory::makeEquityEngine("BS", atm());
    EXPECT_EQ(e->name(), "BlackScholes");
    EXPECT_GT(e->price(emptyEnv()), 0.0);
}

TEST(EngineFactory, MakesMonteCarloEngine) {
    auto e = EngineFactory::makeEquityEngine("MC", atm(), 50000, 42);
    EXPECT_EQ(e->name(), "MonteCarlo");
    EXPECT_GT(e->price(emptyEnv()), 0.0);
}

TEST(EngineFactory, MakesBinomialTreeEngine) {
    auto e = EngineFactory::makeEquityEngine("BT", atm());
    EXPECT_EQ(e->name(), "BinomialTree");
    EXPECT_GT(e->price(emptyEnv()), 0.0);
}

TEST(EngineFactory, MakesFDMEngine) {
    auto e = EngineFactory::makeEquityEngine("FDM", atm());
    EXPECT_EQ(e->name(), "FiniteDifference");
    EXPECT_GT(e->price(emptyEnv()), 0.0);
}

TEST(EngineFactory, UnknownMethodThrows) {
    EXPECT_THROW(EngineFactory::makeEquityEngine("UNKNOWN", atm()), std::invalid_argument);
}
```

- [ ] **Step 7.2: Create EngineFactory header**

```cpp
// include/qf/pricingengines/engine_factory.hpp
#pragma once
#include <memory>
#include <string>
#include <qf/pricingengines/ipricing_engine.hpp>
#include <qf/instruments/option.hpp>
#include <qf/models/irate_model.hpp>

namespace qf::pricingengines {

class EngineFactory {
public:
    /// @brief Create an equity pricing engine by method name.
    /// @param method "BS" | "MC" | "BT" | "FDM" | "Heston"
    /// @param params OptionParams used by all equity engines.
    /// @param simPaths Number of simulation paths (MC/Heston only).
    /// @param seed RNG seed (MC/Heston only).
    /// @throws std::invalid_argument for unknown method.
    static std::shared_ptr<IPricingEngine>
    makeEquityEngine(const std::string& method,
                     const instruments::OptionParams& params,
                     int simPaths = 100000,
                     unsigned seed = 42);
};

} // namespace qf::pricingengines
```

- [ ] **Step 7.3: Create EngineFactory implementation**

```cpp
// src/pricingengines/engine_factory.cpp
#include <qf/pricingengines/engine_factory.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <qf/pricingengines/montecarlo.hpp>
#include <qf/pricingengines/binomialtree.hpp>
#include <qf/pricingengines/finite_difference.hpp>
#include <qf/pricingengines/heston.hpp>
#include <stdexcept>

namespace qf::pricingengines {

std::shared_ptr<IPricingEngine>
EngineFactory::makeEquityEngine(const std::string& method,
                                const instruments::OptionParams& params,
                                int simPaths, unsigned seed)
{
    if (method == "BS")
        return std::make_shared<BlackScholesEngine>(params);
    if (method == "MC")
        return std::make_shared<MonteCarloEngine>(params, simPaths, seed);
    if (method == "BT")
        return std::make_shared<BinomialTreeEngine>(params);
    if (method == "FDM")
        return std::make_shared<FDMEngine>(params);
    throw std::invalid_argument("EngineFactory: unknown method '" + method + "'");
}

} // namespace qf::pricingengines
```

- [ ] **Step 7.4: Register in CMake**

In `src/CMakeLists.txt`, add `pricingengines/engine_factory.cpp`.

- [ ] **Step 7.5: Build and run**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . --target all 2>&1 | tail -10
ctest --output-on-failure -R "EngineFactory"
```
Expected: all 5 EngineFactory tests PASS.

- [ ] **Step 7.6: Commit**

```bash
cd /home/claudio/Git/Quant_Finance
git add include/qf/pricingengines/engine_factory.hpp \
        src/pricingengines/engine_factory.cpp \
        src/CMakeLists.txt
git commit -m "feat: add EngineFactory for creating IPricingEngine by method name"
```

---

## Task 8: Update Instrument — Strategy pattern + MarketEnvironment

**Files:**
- Modify: `include/qf/instruments/instrument.hpp`
- Modify: `src/instruments/bond.cpp` (update `calculatePV` signature)
- Modify: `src/instruments/option.cpp` (update `calculatePV` signature)
- Modify: `src/instruments/swap.cpp` (update `calculatePV` in `Leg`)

This task makes the signature change. The legacy `pv(YieldCurve)` overload is added here to keep all existing tests passing.

- [ ] **Step 8.1: Update instrument.hpp**

```cpp
// include/qf/instruments/instrument.hpp
#pragma once
#include <memory>
#include <qf/core/market_environment.hpp>
#include <qf/termstructure/yieldcurve.hpp>

// Forward declare to avoid circular dependency
namespace qf::pricingengines { class IPricingEngine; }

namespace qf::instruments {

class Instrument {
public:
    Instrument() = default;
    explicit Instrument(double maturity) : maturity_(maturity) {}
    virtual ~Instrument() = default;

    double maturity() const { return maturity_; }
    void setMaturity(double m) { maturity_ = m; }

    void setPricingEngine(std::shared_ptr<pricingengines::IPricingEngine> engine);

    /// Primary API: price against a full market environment.
    double pv(const core::MarketEnvironment& env) const;

    /// Legacy overload for backward-compat: wraps curve in MarketEnvironment("default").
    double pv(const termstructure::YieldCurve& curve) const;

    double currentPV() const { return pv_; }

protected:
    /// Subclasses implement pricing against MarketEnvironment.
    virtual double calculatePV(const core::MarketEnvironment& env) const = 0;

    double maturity_ = 0.0;
    mutable double pv_ = 0.0;

private:
    std::shared_ptr<pricingengines::IPricingEngine> engine_;
};

} // namespace qf::instruments
```

- [ ] **Step 8.2: Add Instrument::pv() implementations**

Create `src/instruments/instrument.cpp`:
```cpp
// src/instruments/instrument.cpp
#include <qf/instruments/instrument.hpp>
#include <qf/pricingengines/ipricing_engine.hpp>

namespace qf::instruments {

void Instrument::setPricingEngine(
        std::shared_ptr<pricingengines::IPricingEngine> engine) {
    engine_ = std::move(engine);
}

double Instrument::pv(const core::MarketEnvironment& env) const {
    pv_ = engine_ ? engine_->price(env) : calculatePV(env);
    return pv_;
}

double Instrument::pv(const termstructure::YieldCurve& curve) const {
    return pv(core::MarketEnvironment(curve));
}

} // namespace qf::instruments
```

- [ ] **Step 8.3: Update Bond::calculatePV signature**

In `include/qf/instruments/bond.hpp`, change the override signature:
```cpp
double calculatePV(const core::MarketEnvironment& env) const override;
```
Add `#include <qf/core/market_environment.hpp>`.

In `src/instruments/bond.cpp`, update:
```cpp
#include <qf/core/market_environment.hpp>

double Bond::calculatePV(const core::MarketEnvironment& env) const {
    return price(env.curve());
}
```
(Bond already has `price(YieldCurve)` — this delegates to it.)

- [ ] **Step 8.4: Update Leg::calculatePV signature**

In `include/qf/instruments/swap.hpp`, update `Leg::calculatePV`:
```cpp
double calculatePV(const core::MarketEnvironment& env) const override;
```

In `src/instruments/swap.cpp`, update:
```cpp
double Leg::calculatePV(const core::MarketEnvironment& env) const {
    // Extract the same logic, using env.curve() instead of curve param
    const auto& curve = env.curve();
    if (floating_) {
        double floatPV = notional_ * (1.0 - curve.discountFactor(maturity()));
        if (spread_ != 0.0)
            floatPV += notional_ * spread_ * maturity() * curve.discountFactor(maturity());
        return floatPV;
    }
    int nPayments = static_cast<int>(std::max(1.0, maturity()));
    double fixedPV = 0.0;
    for (int i = 1; i <= nPayments; ++i) {
        double t = std::min(maturity(), static_cast<double>(i));
        fixedPV += notional_ * fixedRate_ * curve.discountFactor(t);
    }
    fixedPV += notional_ * curve.discountFactor(maturity());
    return fixedPV;
}
```

- [ ] **Step 8.5: Update Option::calculatePV signature**

In `include/qf/instruments/option.hpp`, update:
```cpp
double calculatePV(const core::MarketEnvironment& env) const override;
```
Add `#include <qf/core/market_environment.hpp>`.

In `src/instruments/option.cpp`, update:
```cpp
#include <qf/core/market_environment.hpp>

double Option::calculatePV(const core::MarketEnvironment& /*env*/) const {
    // Legacy path: use the fields stored directly on Option
    qf::instruments::OptionParams params{
        spot, strike, riskFreeRate, dividendYield,
        volatility, maturity(), type, exercise
    };
    return qf::pricingengines::blackScholes(params).price;
}
```

- [ ] **Step 8.6: Register instrument.cpp in CMake**

In `src/CMakeLists.txt`, add `instruments/instrument.cpp`.

- [ ] **Step 8.7: Build and run ALL tests**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . --target all 2>&1 | tail -10
ctest --output-on-failure
```
Expected: **all tests PASS** — including existing `test_instruments.cpp` (which calls `pv(curve)` with `YieldCurve`).

- [ ] **Step 8.8: Commit**

```bash
cd /home/claudio/Git/Quant_Finance
git add include/qf/instruments/instrument.hpp \
        src/instruments/instrument.cpp \
        include/qf/instruments/bond.hpp \
        src/instruments/bond.cpp \
        include/qf/instruments/swap.hpp \
        src/instruments/swap.cpp \
        include/qf/instruments/option.hpp \
        src/instruments/option.cpp \
        src/CMakeLists.txt
git commit -m "refactor: Instrument uses MarketEnvironment; legacy pv(YieldCurve) preserved"
```

---

## Task 9: IUnderlying + Option new constructor

**Files:**
- Create: `include/qf/instruments/iunderlying.hpp`
- Create: `src/instruments/iunderlying.cpp`
- Modify: `include/qf/instruments/option.hpp`
- Modify: `src/instruments/option.cpp`
- Create: `tests/test_underlyings.cpp`

The legacy `Option` constructor (with individual fields) is **kept**. The new constructor taking `shared_ptr<IUnderlying>` is added alongside it.

- [ ] **Step 9.1: Write failing tests**

```cpp
// tests/test_underlyings.cpp
#include <gtest/gtest.h>
#include <qf/instruments/iunderlying.hpp>
#include <qf/instruments/option.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <memory>

using namespace qf::instruments;
using namespace qf::core;

TEST(IUnderlying, EquityUnderlyingId) {
    EquityUnderlying u("AAPL");
    EXPECT_EQ(u.id(), "AAPL");
}

TEST(IUnderlying, RateUnderlyingId) {
    RateUnderlying u("USD");
    EXPECT_EQ(u.id(), "USD");
}

TEST(IUnderlying, PolymorphicId) {
    std::shared_ptr<IUnderlying> u = std::make_shared<EquityUnderlying>("GOOG");
    EXPECT_EQ(u->id(), "GOOG");
}

TEST(Option, NewConstructorWithUnderlying) {
    auto u = std::make_shared<EquityUnderlying>("AAPL");
    Option opt(u, 100.0, 1.0, OptionType::Call, ExerciseType::European);
    EXPECT_EQ(opt.underlying().id(), "AAPL");
    EXPECT_DOUBLE_EQ(opt.strikeValue(), 100.0);  // accessor for new-ctor strike
    EXPECT_EQ(opt.optionType(), OptionType::Call);
    EXPECT_EQ(opt.exerciseType(), ExerciseType::European);
}

TEST(Option, NewConstructorPricingViaMC) {
    auto u = std::make_shared<EquityUnderlying>("AAPL");
    Option opt(u, 100.0, 1.0, OptionType::Call, ExerciseType::European);

    MarketEnvironment env;
    env.setSpot("AAPL", 100.0);
    env.setVolatility("AAPL", 0.20);

    // Assign engine explicitly
    qf::instruments::OptionParams params{100,100,0.05,0.0,0.20,1.0,
                                         OptionType::Call, ExerciseType::European};
    auto engine = std::make_shared<qf::pricingengines::BlackScholesEngine>(params);
    opt.setPricingEngine(engine);
    double p = opt.pv(env);
    EXPECT_GT(p, 0.0);
    EXPECT_NEAR(p, qf::pricingengines::blackScholes(params).price, 1e-6);
}

TEST(Option, LegacyConstructorStillWorks) {
    // Ensure existing code compiles and gives same result
    Option opt;
    opt.spot = 100.0; opt.strike = 100.0; opt.riskFreeRate = 0.05;
    opt.dividendYield = 0.0; opt.volatility = 0.20;
    opt.type = OptionType::Call; opt.exercise = ExerciseType::European;
    opt.setMaturity(1.0);

    qf::termstructure::YieldCurve curve(
        {0.5,1.0,2.0},{0.05,0.05,0.05},
        qf::math::InterpolationMethod::Linear);
    double p = opt.pv(curve);  // uses legacy overload
    EXPECT_GT(p, 0.0);
}
```

- [ ] **Step 9.2: Create IUnderlying header**

```cpp
// include/qf/instruments/iunderlying.hpp
#pragma once
#include <string>

namespace qf::instruments {

/// Abstract underlying asset — key for MarketEnvironment lookup.
class IUnderlying {
public:
    virtual ~IUnderlying() = default;
    virtual std::string id() const = 0;
};

class EquityUnderlying : public IUnderlying {
public:
    explicit EquityUnderlying(std::string ticker);
    std::string id() const override;
private:
    std::string ticker_;
};

class RateUnderlying : public IUnderlying {
public:
    explicit RateUnderlying(std::string curveName);
    std::string id() const override;
private:
    std::string curveName_;
};

} // namespace qf::instruments
```

- [ ] **Step 9.3: Create IUnderlying implementation**

```cpp
// src/instruments/iunderlying.cpp
#include <qf/instruments/iunderlying.hpp>

namespace qf::instruments {

EquityUnderlying::EquityUnderlying(std::string ticker) : ticker_(std::move(ticker)) {}
std::string EquityUnderlying::id() const { return ticker_; }

RateUnderlying::RateUnderlying(std::string curveName) : curveName_(std::move(curveName)) {}
std::string RateUnderlying::id() const { return curveName_; }

} // namespace qf::instruments
```

- [ ] **Step 9.4: Update option.hpp — add new constructor alongside legacy**

```cpp
// include/qf/instruments/option.hpp
#pragma once
#include <memory>
#include <qf/instruments/instrument.hpp>
#include <qf/instruments/iunderlying.hpp>

namespace qf::instruments {

enum class OptionType   { Call, Put };
enum class ExerciseType { European, American };

class Option : public Instrument {
public:
    // ── Legacy constructor (backward-compat) ─────────────────────────────
    Option() = default;
    Option(double spot_, double strike_, double riskFreeRate_, double dividendYield_,
           double volatility_, double maturity_, OptionType type_, ExerciseType exercise_)
        : Instrument(maturity_), spot(spot_), strike(strike_),
          riskFreeRate(riskFreeRate_), dividendYield(dividendYield_),
          volatility(volatility_), type(type_), exercise(exercise_)
    {}

    // ── New constructor (with IUnderlying) ────────────────────────────────
    Option(std::shared_ptr<IUnderlying> underlying,
           double strike, double maturity,
           OptionType type, ExerciseType exercise);

    // Legacy public fields (preserved)
    double spot = 0.0, strike = 0.0, riskFreeRate = 0.0;
    double dividendYield = 0.0, volatility = 0.0;
    OptionType type = OptionType::Call;
    ExerciseType exercise = ExerciseType::European;

    // New accessors (only meaningful when constructed with IUnderlying)
    double strikeValue() const { return strike_; }
    OptionType optionType() const { return type_; }
    ExerciseType exerciseType() const { return exercise_; }
    const IUnderlying& underlying() const { return *underlying_; }

    double calculatePV(const core::MarketEnvironment& env) const override;

private:
    std::shared_ptr<IUnderlying> underlying_;
    double strike_ = 0.0;
    OptionType type_ = OptionType::Call;
    ExerciseType exercise_ = ExerciseType::European;
};

struct OptionParams {
    double spot, strike, riskFreeRate, dividendYield,
           volatility, maturity;
    OptionType type;
    ExerciseType exercise;
};

} // namespace qf::instruments
```

- [ ] **Step 9.5: Update option.cpp — add new constructor body**

```cpp
// src/instruments/option.cpp
#include <qf/instruments/option.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <qf/core/market_environment.hpp>

namespace qf::instruments {

Option::Option(std::shared_ptr<IUnderlying> underlying,
               double strikeVal, double maturity,
               OptionType optType, ExerciseType exer)
    : Instrument(maturity),
      underlying_(std::move(underlying)),
      strike_(strikeVal), type_(optType), exercise_(exer)
{}

double Option::calculatePV(const core::MarketEnvironment& /*env*/) const {
    // Legacy path: use fields stored on Option directly
    OptionParams params{spot, strike, riskFreeRate, dividendYield,
                        volatility, maturity(), type, exercise};
    return pricingengines::blackScholes(params).price;
}

} // namespace qf::instruments
```

- [ ] **Step 9.6: Register iunderlying.cpp in CMake**

In `src/CMakeLists.txt`, add `instruments/iunderlying.cpp`.

- [ ] **Step 9.7: Build and run all tests**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . --target all 2>&1 | tail -10
ctest --output-on-failure
```
Expected: all tests PASS.

- [ ] **Step 9.8: Commit**

```bash
cd /home/claudio/Git/Quant_Finance
git add include/qf/instruments/iunderlying.hpp \
        src/instruments/iunderlying.cpp \
        include/qf/instruments/option.hpp \
        src/instruments/option.cpp \
        tests/test_underlyings.cpp \
        tests/CMakeLists.txt \
        src/CMakeLists.txt
git commit -m "feat: add IUnderlying; Option gains new constructor while preserving legacy fields"
```

---

## Task 10: InterestRateSwap — remove duplicated state

**Files:**
- Modify: `include/qf/instruments/swap.hpp`
- Modify: `src/instruments/swap.cpp`

`InterestRateSwap` currently holds `notional_`, `fixedRate_`, `maturity_`, `frequency_` that duplicate data in the `Leg` objects it owns via `Swap`. After cleanup, these are removed and derived from the legs. `npv()` and `annuity()` get `MarketEnvironment` overloads while legacy `YieldCurve` variants are preserved.

- [ ] **Step 10.1: Verify tests pass before touching anything**

```bash
cd /home/claudio/Git/Quant_Finance/build
ctest --output-on-failure -R Swap
```
Expected: all Swap tests PASS. Note the exact test names for reference.

- [ ] **Step 10.2: Update swap.hpp — remove duplicate members, add MarketEnv overloads**

First, add `notional()` and `fixedRate()` accessors to `Leg` in `swap.hpp` (these are needed by `InterestRateSwap::npv()`):

```cpp
// In class Leg, add public accessors:
double notional() const { return notional_; }
double fixedRate() const { return fixedRate_; }
```

Then the `InterestRateSwap` declaration:

```cpp
// include/qf/instruments/swap.hpp — relevant portion (InterestRateSwap only)

class InterestRateSwap : public Swap {
public:
    InterestRateSwap(double notional, double fixedRate,
                     double maturity, double frequency, SwapType type);

    // Primary API (MarketEnvironment)
    double npv(const core::MarketEnvironment& env) const;
    double annuity(const core::MarketEnvironment& env) const;

    // Legacy overloads (backward-compat for existing tests and examples)
    double npv(const termstructure::YieldCurve& curve) const;
    double annuity(const termstructure::YieldCurve& curve) const;

    static double parRate(double maturity, double frequency,
                          const core::MarketEnvironment& env);
    static double parRate(double maturity, double frequency,
                          const termstructure::YieldCurve& curve);  // legacy
    static double annuity(double maturity, double frequency,
                          const core::MarketEnvironment& env);
    static double annuity(double maturity, double frequency,
                          const termstructure::YieldCurve& curve);  // legacy

private:
    // frequency_ and type_ are the only state not derivable from the Leg objects.
    // notional, fixedRate, maturity are read from payLeg()/receiveLeg() via new accessors.
    double frequency_;
    SwapType type_;
};
```

- [ ] **Step 10.3: Update swap.cpp — implement without duplicate members**

```cpp
// Replace InterestRateSwap section in src/instruments/swap.cpp:

InterestRateSwap::InterestRateSwap(double notional, double fixedRate,
                                   double maturity, double frequency,
                                   SwapType type)
    : Swap(
          Leg("USD", "ACT/365", notional, maturity, fixedRate, 0.0, false),
          Leg("USD", "ACT/365", notional, maturity, 0.0,       0.0, true),
          SwapLegType::FixedFloating),
      frequency_(frequency), type_(type)
{
    if (notional <= 0.0)
        throw std::invalid_argument("InterestRateSwap: notional must be positive");
    if (maturity <= 0.0)
        throw std::invalid_argument("InterestRateSwap: maturity must be positive");
    if (frequency <= 0.0)
        throw std::invalid_argument("InterestRateSwap: frequency must be positive");
}

// MarketEnvironment overloads — read notional and maturity from the legs via new accessors
double InterestRateSwap::annuity(const core::MarketEnvironment& env) const {
    return discountAnnuity(maturity(), frequency_, env.curve());
}

double InterestRateSwap::npv(const core::MarketEnvironment& env) const {
    const auto& curve = env.curve();
    // payLeg_ = fixed (notional() and fixedRate() come from Leg accessors added in Step 10.2)
    double notional = payLeg().notional();
    double fixedRate = payLeg().fixedRate();
    double mat = maturity();  // inherited from Instrument
    double floatingLeg = notional * (1.0 - curve.discountFactor(mat));
    double fixedLeg    = fixedRate * discountAnnuity(mat, frequency_, curve);
    double payer_npv   = floatingLeg - fixedLeg;
    return (type_ == SwapType::Payer) ? payer_npv : -payer_npv;
}

// Legacy YieldCurve overloads — delegate to MarketEnvironment versions
double InterestRateSwap::annuity(const termstructure::YieldCurve& curve) const {
    return annuity(core::MarketEnvironment(curve));
}

double InterestRateSwap::npv(const termstructure::YieldCurve& curve) const {
    return npv(core::MarketEnvironment(curve));
}

double InterestRateSwap::parRate(double maturity, double frequency,
                                  const core::MarketEnvironment& env) {
    return parRate(maturity, frequency, env.curve());
}

double InterestRateSwap::parRate(double maturity, double frequency,
                                  const termstructure::YieldCurve& curve) {
    if (maturity <= 0.0 || frequency <= 0.0)
        throw std::invalid_argument("InterestRateSwap::parRate: invalid parameters");
    double dt = 1.0 / frequency;
    int nPayments = static_cast<int>(maturity * frequency);
    double annuitySum = 0.0;
    for (int i = 1; i <= nPayments; ++i)
        annuitySum += dt * curve.discountFactor(i * dt);
    return (1.0 - curve.discountFactor(maturity)) / annuitySum;
}

double InterestRateSwap::annuity(double maturity, double frequency,
                                  const core::MarketEnvironment& env) {
    return discountAnnuity(maturity, frequency, env.curve());
}

double InterestRateSwap::annuity(double maturity, double frequency,
                                  const termstructure::YieldCurve& curve) {
    return discountAnnuity(maturity, frequency, curve);
}
```

- [ ] **Step 10.4: Build and run Swap tests**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . --target all 2>&1 | tail -10
ctest --output-on-failure -R Swap
```
Expected: all Swap tests PASS (including `ParRateGivesZeroNPV`, `PayerReceiverSymmetry`, `NPVScalesWithNotional`).

If any test fails, the `npv()` sign convention needs adjusting. The existing formula is:
```
floatLeg = notional * (1 - df(T))
fixedLeg = fixedRate * annuity * notional
payer_npv = floatLeg - fixedLeg   (positive when fixed < par)
```
Verify `receiveLeg().pv()` returns the floating leg value and `payLeg().pv()` returns the fixed leg value.

- [ ] **Step 10.5: Run full test suite**

```bash
ctest --output-on-failure
```
Expected: all tests PASS.

- [ ] **Step 10.6: Commit**

```bash
cd /home/claudio/Git/Quant_Finance
git add include/qf/instruments/swap.hpp \
        src/instruments/swap.cpp
git commit -m "refactor: remove duplicate state from InterestRateSwap; add MarketEnv overloads"
```

---

## Task 11: Final build verification and CMakeLists.txt audit

- [ ] **Step 11.1: Full clean build**

```bash
cd /home/claudio/Git/Quant_Finance/build
cmake --build . --clean-first --target all 2>&1 | tail -20
```
Expected: zero errors, zero warnings (or only pre-existing warnings).

- [ ] **Step 11.2: Full test suite**

```bash
ctest --output-on-failure -V
```
Expected: all tests PASS. Count the number of tests — it should be strictly greater than the count before the refactor.

- [ ] **Step 11.3: Verify examples still compile**

```bash
cmake --build . --target all 2>&1 | grep -E "(example|error)" | head -20
```
Expected: all example targets compile without errors.

- [ ] **Step 11.4: Check Python bindings still compile (if pybind11 available)**

```bash
cmake --build . --target qfpy 2>&1 | tail -10
```
Expected: `qfpy` compiles without errors.

- [ ] **Step 11.5: Final commit**

```bash
cd /home/claudio/Git/Quant_Finance
git add -A
git commit -m "chore: verify full build, tests, examples, and Python bindings post-refactor"
git push
```

---

## Summary

| Task | Component | New Files | Modified Files |
|------|-----------|-----------|----------------|
| 1 | `MarketEnvironment` | 3 | `src/CMakeLists.txt`, `tests/CMakeLists.txt` |
| 2 | `IRateModel` + Vasicek/HW | 2 | `vasicek.hpp`, `hullwhite.hpp/cpp` |
| 3 | `IEquityModel` + HestonModel + BSModel | 5 | — |
| 4 | `IPricingEngine` | 1 | — |
| 5 | BS/MC/BT/FDM engines | 1 test | 4 headers + 4 `.cpp` |
| 6 | `HestonEngine` | — | `heston.hpp`, `heston.cpp` |
| 7 | `EngineFactory` | 2 | `src/CMakeLists.txt` |
| 8 | `Instrument` Strategy | 1 | `instrument.hpp`, `bond.cpp`, `option.cpp`, `swap.cpp` |
| 9 | `IUnderlying` + Option | 3 | `option.hpp`, `option.cpp` |
| 10 | `InterestRateSwap` cleanup | — | `swap.hpp`, `swap.cpp` |
| 11 | Build verification | — | — |

**Patterns introduced:** Strategy, Factory Method, Facade, Adapter, Template Method.
