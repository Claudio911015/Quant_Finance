# Engine Composability & MarketEnvironment Integration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `IEquityModel` into `MonteCarloEngine` so any model drives MC simulation, and make all equity engines read `spot`/`vol`/`riskFreeRate` from `MarketEnvironment` when a ticker is provided.

**Architecture:** Each engine gains a `ticker_` field and a new constructor. When `ticker_` is non-empty, `price(env)` reads market data from `env` and throws if it's missing — enabling bump-and-reprice workflows. When empty, existing `OptionParams` are used unchanged (backward compat: all current tests continue to pass). A single internal helper `detail/env_resolver.hpp` centralises the resolution logic. Separately, `MonteCarloEngine` gains a model-driven constructor accepting `shared_ptr<IEquityModel>` that delegates path simulation to the model.

**Tech Stack:** C++17, Google Test, CMake/CTest. All commands run from `~/Git/Quant_Finance/build/`.

**Branch:** `feature/engine-composability` (new worktree at `.worktrees/engine-composability`).

```bash
cd ~/Git/Quant_Finance
git worktree add .worktrees/engine-composability -b feature/engine-composability
cd .worktrees/engine-composability
mkdir -p build && cd build && cmake .. -DCMAKE_BUILD_TYPE=Debug && make -j$(nproc)
# Baseline: 153/153 must pass before touching anything
ctest --output-on-failure
```

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| **Create** | `include/qf/pricingengines/detail/env_resolver.hpp` | Shared resolution helper — reads spot/vol/rate from env by ticker |
| **Modify** | `include/qf/pricingengines/montecarlo.hpp` | New constructors: model-driven + env-aware |
| **Modify** | `src/pricingengines/montecarlo.cpp` | Implement model-driven and env-aware `price()` |
| **Modify** | `include/qf/pricingengines/blackscholes.hpp` | New env-aware constructor + `ticker_` field |
| **Modify** | `src/pricingengines/blackscholes.cpp` | Implement env-aware `price()` |
| **Modify** | `include/qf/pricingengines/binomialtree.hpp` | New env-aware constructor + `ticker_` field |
| **Modify** | `src/pricingengines/binomialtree.cpp` | Implement env-aware `price()` |
| **Modify** | `include/qf/pricingengines/finite_difference.hpp` | New env-aware constructor + `ticker_` field |
| **Modify** | `src/pricingengines/finite_difference.cpp` | Implement env-aware `price()` |
| **Modify** | `include/qf/pricingengines/heston.hpp` | New env-aware constructor + `ticker_` field |
| **Modify** | `src/pricingengines/heston.cpp` | Implement env-aware `price()` (spot + rate only; Heston params stay internal) |
| **Modify** | `include/qf/pricingengines/engine_factory.hpp` | Accept optional `ticker` parameter |
| **Modify** | `src/pricingengines/engine_factory.cpp` | Pass ticker through to engines |
| **Modify** | `tests/test_pricing_engines_oop.cpp` | All new tests live here |

---

## Task 1 — `MonteCarloEngine`: model-driven constructor

**Files:**
- Modify: `include/qf/pricingengines/montecarlo.hpp`
- Modify: `src/pricingengines/montecarlo.cpp`
- Modify: `tests/test_pricing_engines_oop.cpp`

- [ ] **Step 1.1 — Write failing tests**

Add at the bottom of `tests/test_pricing_engines_oop.cpp` (after existing tests):

```cpp
// ── Task 1: IEquityModel injection into MonteCarloEngine ─────────────────────
#include <qf/models/iequity_model.hpp>
#include <qf/models/bs_model.hpp>
#include <qf/models/heston_model.hpp>

TEST(MonteCarloEngine, BSModelDrivenMatchesLegacy) {
    // Model-driven MC with BlackScholesModel must agree with legacy MC
    // within 0.5% for ATM call (same params, enough paths for convergence)
    auto params = atm();  // S=100, K=100, r=0.05, q=0, sigma=0.20, T=1, Call
    auto model = std::make_shared<qf::models::BlackScholesModel>(
        params.riskFreeRate, params.dividendYield, params.volatility);

    auto legacyEngine = std::make_shared<MonteCarloEngine>(params, 200000, 42);
    auto modelEngine  = std::make_shared<MonteCarloEngine>(model, params, 200000, 1, 42);

    double legacyPrice = legacyEngine->price(emptyEnv());
    double modelPrice  = modelEngine->price(emptyEnv());

    EXPECT_EQ(modelEngine->name(), "MonteCarlo");
    // Both are MC with same seed/paths — should be very close
    EXPECT_NEAR(modelPrice, legacyPrice, 0.10);   // 10 cents tolerance on $10 option
    EXPECT_GT(modelPrice, 0.0);
}

TEST(MonteCarloEngine, HestonModelDrivenGivesPositivePrice) {
    auto params = atm();
    qf::models::HestonParams hp{0.04, 2.0, 0.04, 0.3, -0.7};
    auto model  = std::make_shared<qf::models::HestonModel>(hp);

    auto engine = std::make_shared<MonteCarloEngine>(model, params, 50000, 252, 42);

    EXPECT_EQ(engine->name(), "MonteCarlo");
    double p = engine->price(emptyEnv());
    EXPECT_GT(p, 0.0);
    EXPECT_LT(p, params.spot);   // call price < spot
}

TEST(MonteCarloEngine, HestonModelDrivenAgreesWithHestonEngine) {
    // MC with HestonModel should be within 3% of semi-analytical HestonEngine
    auto params = atm();
    qf::models::HestonParams hp{0.04, 2.0, 0.04, 0.3, -0.7};
    auto model  = std::make_shared<qf::models::HestonModel>(hp);

    // Semi-analytical
    pricingengines::HestonParams hpEngine{0.04, 2.0, 0.04, 0.3, -0.7};
    double analytical = hestonPrice(params, hpEngine);

    auto mcEngine = std::make_shared<MonteCarloEngine>(model, params, 200000, 252, 42);
    double mcPrice = mcEngine->price(emptyEnv());

    EXPECT_NEAR(mcPrice, analytical, analytical * 0.03);  // within 3%
}
```

- [ ] **Step 1.2 — Verify tests fail**

```bash
cd .worktrees/engine-composability/build
make -j$(nproc) 2>&1 | grep -E "error:|warning:" | head -20
```
Expected: compile errors — `MonteCarloEngine` has no constructor taking `IEquityModel`.

- [ ] **Step 1.3 — Update header**

Replace the class declaration in `include/qf/pricingengines/montecarlo.hpp`:

```cpp
#pragma once
#include <memory>
#include <string>
#include <qf/instruments/option.hpp>
#include <qf/pricingengines/ipricing_engine.hpp>
#include <qf/models/iequity_model.hpp>

namespace qf::pricingengines {

/// Free function (preserved for backward-compat)
double monteCarloBSPrice(const instruments::OptionParams& params,
                         int N = 100000, unsigned seed = 42);

class MonteCarloEngine : public IPricingEngine {
public:
    /// Legacy: params carry all market data; env is ignored.
    explicit MonteCarloEngine(instruments::OptionParams params,
                              int N = 100000, unsigned seed = 42);

    /// Model-driven (Improvement 1): model simulates the price path.
    /// nSteps = number of steps per path (relevant for Heston mean reversion).
    MonteCarloEngine(std::shared_ptr<models::IEquityModel> model,
                     instruments::OptionParams params,
                     int N = 100000, int nSteps = 252, unsigned seed = 42);

    double price(const core::MarketEnvironment& env) const override;
    std::string name() const override { return "MonteCarlo"; }

private:
    instruments::OptionParams params_;
    std::shared_ptr<models::IEquityModel> model_;   // null ⟹ legacy path
    int N_;
    int nSteps_ = 1;
    unsigned seed_;
};

} // namespace qf::pricingengines
```

- [ ] **Step 1.4 — Implement model-driven path in `src/pricingengines/montecarlo.cpp`**

Replace the file content:

```cpp
#include <qf/pricingengines/montecarlo.hpp>
#include <cmath>
#include <random>
#include <stdexcept>

namespace qf::pricingengines {

double monteCarloBSPrice(const instruments::OptionParams& p, int N, unsigned seed)
{
    if (N <= 0)
        throw std::invalid_argument("monteCarloBSPrice: N must be positive");
    if (p.spot <= 0.0 || p.strike <= 0.0 || p.maturity <= 0.0 || p.volatility <= 0.0)
        throw std::invalid_argument("monteCarloBSPrice: invalid option parameters");
    if (p.exercise != instruments::ExerciseType::European)
        throw std::invalid_argument("monteCarloBSPrice: only European options supported");

    std::mt19937_64 rng(seed);
    std::normal_distribution<double> Z(0.0, 1.0);

    const double drift = (p.riskFreeRate - p.dividendYield - 0.5*p.volatility*p.volatility)*p.maturity;
    const double diff  = p.volatility * std::sqrt(p.maturity);

    double sum = 0.0;
    for (int i = 0; i < N; ++i) {
        double ST = p.spot * std::exp(drift + diff * Z(rng));
        double payoff = (p.type == instruments::OptionType::Call)
                      ? std::max(ST - p.strike, 0.0)
                      : std::max(p.strike - ST, 0.0);
        sum += payoff;
    }
    return std::exp(-p.riskFreeRate * p.maturity) * sum / static_cast<double>(N);
}

// ── Constructors ─────────────────────────────────────────────────────────────

MonteCarloEngine::MonteCarloEngine(instruments::OptionParams params, int N, unsigned seed)
    : params_(std::move(params)), N_(N), seed_(seed) {}

MonteCarloEngine::MonteCarloEngine(std::shared_ptr<models::IEquityModel> model,
                                   instruments::OptionParams params,
                                   int N, int nSteps, unsigned seed)
    : params_(std::move(params)), model_(std::move(model)),
      N_(N), nSteps_(nSteps), seed_(seed)
{
    if (!model_)
        throw std::invalid_argument("MonteCarloEngine: model must not be null");
    if (N_ <= 0)
        throw std::invalid_argument("MonteCarloEngine: N must be positive");
    if (nSteps_ <= 0)
        throw std::invalid_argument("MonteCarloEngine: nSteps must be positive");
}

// ── price() ──────────────────────────────────────────────────────────────────

double MonteCarloEngine::price(const core::MarketEnvironment& env) const {
    if (!model_) {
        // Legacy path: ignore env, use params_ directly
        return monteCarloBSPrice(params_, N_, seed_);
    }

    // Model-driven path: delegate simulation to IEquityModel
    // Each path i uses seed_ + i to ensure independence
    const double S0 = params_.spot;
    const double K  = params_.strike;
    const double r  = params_.riskFreeRate;
    const double T  = params_.maturity;

    double sum = 0.0;
    for (int i = 0; i < N_; ++i) {
        auto path = model_->simulate(S0, T, nSteps_,
                                     seed_ + static_cast<unsigned>(i));
        double ST = path.back();
        double payoff = (params_.type == instruments::OptionType::Call)
                      ? std::max(ST - K, 0.0)
                      : std::max(K - ST, 0.0);
        sum += payoff;
    }
    return std::exp(-r * T) * sum / static_cast<double>(N_);
}

} // namespace qf::pricingengines
```

- [ ] **Step 1.5 — Build and run Task 1 tests**

```bash
cd .worktrees/engine-composability/build
make -j$(nproc) && ctest -R "MonteCarloEngine" --output-on-failure
```
Expected: all `MonteCarloEngine.*` tests pass (including the 3 new ones).

- [ ] **Step 1.6 — Run full suite to confirm no regressions**

```bash
ctest --output-on-failure
```
Expected: 156/156 pass.

- [ ] **Step 1.7 — Commit**

```bash
cd .worktrees/engine-composability
git add include/qf/pricingengines/montecarlo.hpp \
        src/pricingengines/montecarlo.cpp \
        tests/test_pricing_engines_oop.cpp
git commit -m "feat: MonteCarloEngine model injection — IEquityModel drives price path"
```

---

## Task 2 — `detail/env_resolver.hpp` shared helper

**Files:**
- Create: `include/qf/pricingengines/detail/env_resolver.hpp`

- [ ] **Step 2.1 — Create the file**

```cpp
// include/qf/pricingengines/detail/env_resolver.hpp
#pragma once
#include <qf/instruments/option.hpp>
#include <qf/core/market_environment.hpp>
#include <string>
#include <utility>

namespace qf::pricingengines::detail {

/// For engines that price equity options (BS, MC, BT, FDM):
/// if ticker is non-empty, reads spot / volatility / riskFreeRate from env.
/// If ticker is empty, returns params unchanged (backward-compat path).
/// Throws std::out_of_range if ticker is set but any required datum is missing.
inline instruments::OptionParams resolveEquityParams(
    instruments::OptionParams params,
    const std::string& ticker,
    const core::MarketEnvironment& env)
{
    if (ticker.empty()) return params;
    params.spot         = env.spot(ticker);
    params.volatility   = env.volatility(ticker);
    params.riskFreeRate = env.curve("default").zeroRate(params.maturity);
    return params;
}

/// For HestonEngine: only spot and riskFreeRate come from env
/// (Heston model params are not observable market data).
inline std::pair<double,double> resolveSpotAndRate(
    double defaultSpot, double defaultRate, double maturity,
    const std::string& ticker,
    const core::MarketEnvironment& env)
{
    if (ticker.empty()) return {defaultSpot, defaultRate};
    return {env.spot(ticker),
            env.curve("default").zeroRate(maturity)};
}

} // namespace qf::pricingengines::detail
```

- [ ] **Step 2.2 — Verify it compiles cleanly**

```bash
cd .worktrees/engine-composability/build
make -j$(nproc)
```
Expected: clean build (file is header-only, no symbols to register yet).

- [ ] **Step 2.3 — Commit**

```bash
cd .worktrees/engine-composability
git add include/qf/pricingengines/detail/env_resolver.hpp
git commit -m "feat: add detail/env_resolver.hpp — shared MarketEnvironment resolution helper"
```

---

## Task 3 — `BlackScholesEngine`: env-aware

**Files:**
- Modify: `include/qf/pricingengines/blackscholes.hpp`
- Modify: `src/pricingengines/blackscholes.cpp`
- Modify: `tests/test_pricing_engines_oop.cpp`

- [ ] **Step 3.1 — Write failing tests**

Add to `tests/test_pricing_engines_oop.cpp`:

```cpp
// ── Task 3: BlackScholesEngine env-aware ─────────────────────────────────────

static MarketEnvironment atmEnv() {
    // Matches atm() params: S=100, sigma=0.20, r=0.05
    MarketEnvironment env;
    env.setSpot("AAPL", 100.0);
    env.setVolatility("AAPL", 0.20);
    env.addCurve("default",
        qf::termstructure::YieldCurve({0.5,1.0,2.0,5.0},{0.05,0.05,0.05,0.05}));
    return env;
}

TEST(BlackScholesEngine, EnvAwareMatchesParamsBased) {
    // Using env-aware constructor with matching market data must give same price
    auto paramsEngine = BlackScholesEngine(atm());
    auto envEngine    = BlackScholesEngine(atm(), "AAPL");

    double expected = paramsEngine.price(emptyEnv());
    double actual   = envEngine.price(atmEnv());
    EXPECT_NEAR(actual, expected, 1e-8);
}

TEST(BlackScholesEngine, EnvAwareReadsDifferentSpot) {
    // Engine was constructed with spot=100; env has spot=110 — env wins
    auto envEngine = BlackScholesEngine(atm(), "AAPL");
    MarketEnvironment env;
    env.setSpot("AAPL", 110.0);
    env.setVolatility("AAPL", 0.20);
    env.addCurve("default",
        qf::termstructure::YieldCurve({0.5,1.0,2.0,5.0},{0.05,0.05,0.05,0.05}));

    // Price with S=110 must differ from S=100
    double priceS100 = BlackScholesEngine(atm()).price(emptyEnv());
    double priceS110 = envEngine.price(env);
    EXPECT_GT(priceS110, priceS100);   // call is worth more at higher spot
}

TEST(BlackScholesEngine, EnvAwareMissingSpotThrows) {
    auto engine = BlackScholesEngine(atm(), "AAPL");
    MarketEnvironment emptyNamed;  // no spot set
    // Must throw because ticker is set but env has no spot for "AAPL"
    EXPECT_THROW(engine.price(emptyNamed), std::out_of_range);
}

TEST(BlackScholesEngine, LegacyConstructorStillIgnoresEnv) {
    // Old constructor must ignore env content (backward compat)
    auto engine = BlackScholesEngine(atm());
    double p1 = engine.price(emptyEnv());
    double p2 = engine.price(atmEnv());  // env has different data but should be ignored
    EXPECT_DOUBLE_EQ(p1, p2);
}
```

- [ ] **Step 3.2 — Verify tests fail to compile**

```bash
cd .worktrees/engine-composability/build
make -j$(nproc) 2>&1 | grep "error:" | head -10
```
Expected: `BlackScholesEngine` has no constructor taking `(OptionParams, string)`.

- [ ] **Step 3.3 — Update header `include/qf/pricingengines/blackscholes.hpp`**

```cpp
#pragma once
#include <string>
#include <qf/instruments/option.hpp>
#include <qf/pricingengines/ipricing_engine.hpp>

namespace qf::pricingengines {

struct BSResult {
    double price;
    double delta;
    double gamma;
    double vega;
    double theta;
    double rho;
};

/// Free function (preserved for backward-compat)
BSResult blackScholes(const instruments::OptionParams& params);

/// Implied volatility via Brent (preserved)
double impliedVolatility(const instruments::OptionParams& params,
                         double marketPrice,
                         double tol = 1e-6, int maxIt = 100);

class BlackScholesEngine : public IPricingEngine {
public:
    /// Legacy: all market data in params; env is ignored.
    explicit BlackScholesEngine(instruments::OptionParams params);

    /// Env-aware: spot, vol, and riskFreeRate are read from env using ticker.
    BlackScholesEngine(instruments::OptionParams params, std::string ticker);

    double price(const core::MarketEnvironment& env) const override;
    std::string name() const override { return "BlackScholes"; }

private:
    instruments::OptionParams params_;
    std::string ticker_;   // empty ⟹ legacy (ignore env)
};

} // namespace qf::pricingengines
```

- [ ] **Step 3.4 — Update implementation `src/pricingengines/blackscholes.cpp`**

Add the new constructor and update `price()`. The `blackScholes()` free function and `impliedVolatility()` are unchanged — only modify below the "── Black-Scholes Engine ──" section:

```cpp
// Add at top (after existing includes):
#include <qf/pricingengines/detail/env_resolver.hpp>

// Replace the engine implementation at the bottom of the file:
BlackScholesEngine::BlackScholesEngine(instruments::OptionParams params)
    : params_(std::move(params)) {}

BlackScholesEngine::BlackScholesEngine(instruments::OptionParams params, std::string ticker)
    : params_(std::move(params)), ticker_(std::move(ticker)) {}

double BlackScholesEngine::price(const core::MarketEnvironment& env) const {
    auto p = detail::resolveEquityParams(params_, ticker_, env);
    return blackScholes(p).price;
}
```

- [ ] **Step 3.5 — Build and run Task 3 tests**

```bash
cd .worktrees/engine-composability/build
make -j$(nproc) && ctest -R "BlackScholesEngine" --output-on-failure
```
Expected: all `BlackScholesEngine.*` tests pass (7 total: 3 old + 4 new).

- [ ] **Step 3.6 — Run full suite**

```bash
ctest --output-on-failure
```
Expected: 160/160 pass.

- [ ] **Step 3.7 — Commit**

```bash
cd .worktrees/engine-composability
git add include/qf/pricingengines/blackscholes.hpp src/pricingengines/blackscholes.cpp \
        tests/test_pricing_engines_oop.cpp
git commit -m "feat: BlackScholesEngine reads spot/vol/rate from MarketEnvironment when ticker set"
```

---

## Task 4 — `MonteCarloEngine`: env-aware constructor

**Files:**
- Modify: `include/qf/pricingengines/montecarlo.hpp`
- Modify: `src/pricingengines/montecarlo.cpp`
- Modify: `tests/test_pricing_engines_oop.cpp`

- [ ] **Step 4.1 — Write failing tests**

```cpp
// ── Task 4: MonteCarloEngine env-aware ───────────────────────────────────────

TEST(MonteCarloEngine, EnvAwareReadsDifferentSpot) {
    MarketEnvironment env;
    env.setSpot("AAPL", 110.0);
    env.setVolatility("AAPL", 0.20);
    env.addCurve("default",
        qf::termstructure::YieldCurve({0.5,1.0,2.0,5.0},{0.05,0.05,0.05,0.05}));

    auto envEngine    = MonteCarloEngine(atm(), "AAPL", 100000, 42);
    auto legacyEngine = MonteCarloEngine(atm(), 100000, 42);

    double priceS110 = envEngine.price(env);
    double priceS100 = legacyEngine.price(emptyEnv());
    EXPECT_GT(priceS110, priceS100);
}

TEST(MonteCarloEngine, EnvAwareMissingTickerThrows) {
    auto engine = MonteCarloEngine(atm(), "AAPL", 100000, 42);
    EXPECT_THROW(engine.price(emptyEnv()), std::out_of_range);
}

TEST(MonteCarloEngine, LegacyConstructorIgnoresEnv) {
    auto engine = MonteCarloEngine(atm(), 100000, 42);
    double p1 = engine.price(emptyEnv());
    double p2 = engine.price(atmEnv());
    EXPECT_DOUBLE_EQ(p1, p2);
}
```

- [ ] **Step 4.2 — Verify tests fail to compile**

```bash
cd .worktrees/engine-composability/build
make -j$(nproc) 2>&1 | grep "error:" | head -5
```
Expected: no constructor `MonteCarloEngine(OptionParams, string, int, int)`.

- [ ] **Step 4.3 — Update header `include/qf/pricingengines/montecarlo.hpp`**

Add the env-aware constructor (keep existing two unchanged):

```cpp
    /// Env-aware: spot, vol, and riskFreeRate read from env using ticker.
    MonteCarloEngine(instruments::OptionParams params, std::string ticker,
                     int N = 100000, unsigned seed = 42);
```

Also add `std::string ticker_` to private members.

Full updated class (replace the class block):

```cpp
class MonteCarloEngine : public IPricingEngine {
public:
    /// Legacy: all market data in params; env is ignored.
    explicit MonteCarloEngine(instruments::OptionParams params,
                              int N = 100000, unsigned seed = 42);

    /// Model-driven: model simulates the price path.
    MonteCarloEngine(std::shared_ptr<models::IEquityModel> model,
                     instruments::OptionParams params,
                     int N = 100000, int nSteps = 252, unsigned seed = 42);

    /// Env-aware: spot, vol, and riskFreeRate read from env using ticker.
    MonteCarloEngine(instruments::OptionParams params, std::string ticker,
                     int N = 100000, unsigned seed = 42);

    double price(const core::MarketEnvironment& env) const override;
    std::string name() const override { return "MonteCarlo"; }

private:
    instruments::OptionParams params_;
    std::string ticker_;
    std::shared_ptr<models::IEquityModel> model_;
    int N_;
    int nSteps_ = 1;
    unsigned seed_;
};
```

- [ ] **Step 4.4 — Update implementation `src/pricingengines/montecarlo.cpp`**

Add at top: `#include <qf/pricingengines/detail/env_resolver.hpp>`

Add new constructor after existing ones:

```cpp
MonteCarloEngine::MonteCarloEngine(instruments::OptionParams params, std::string ticker,
                                   int N, unsigned seed)
    : params_(std::move(params)), ticker_(std::move(ticker)), N_(N), seed_(seed) {}
```

Update `price()` to use the resolver on the legacy path:

```cpp
double MonteCarloEngine::price(const core::MarketEnvironment& env) const {
    if (model_) {
        // Model-driven: resolve market data then simulate via model
        auto p = detail::resolveEquityParams(params_, ticker_, env);
        double sum = 0.0;
        for (int i = 0; i < N_; ++i) {
            auto path = model_->simulate(p.spot, p.maturity, nSteps_,
                                         seed_ + static_cast<unsigned>(i));
            double ST = path.back();
            double payoff = (p.type == instruments::OptionType::Call)
                          ? std::max(ST - p.strike, 0.0)
                          : std::max(p.strike - ST, 0.0);
            sum += payoff;
        }
        return std::exp(-p.riskFreeRate * p.maturity) * sum / static_cast<double>(N_);
    }
    // Legacy / env-aware: use free function with resolved params
    auto p = detail::resolveEquityParams(params_, ticker_, env);
    return monteCarloBSPrice(p, N_, seed_);
}
```

- [ ] **Step 4.5 — Build and run Task 4 tests**

```bash
cd .worktrees/engine-composability/build
make -j$(nproc) && ctest -R "MonteCarloEngine" --output-on-failure
```
Expected: all `MonteCarloEngine.*` tests pass (6 total: 3 from Task 1 + 3 new).

- [ ] **Step 4.6 — Run full suite**

```bash
ctest --output-on-failure
```
Expected: 163/163 pass.

- [ ] **Step 4.7 — Commit**

```bash
cd .worktrees/engine-composability
git add include/qf/pricingengines/montecarlo.hpp src/pricingengines/montecarlo.cpp \
        tests/test_pricing_engines_oop.cpp
git commit -m "feat: MonteCarloEngine env-aware constructor reads market data from MarketEnvironment"
```

---

## Task 5 — `BinomialTreeEngine` and `FDMEngine`: env-aware

**Files:**
- Modify: `include/qf/pricingengines/binomialtree.hpp`
- Modify: `src/pricingengines/binomialtree.cpp`
- Modify: `include/qf/pricingengines/finite_difference.hpp`
- Modify: `src/pricingengines/finite_difference.cpp`
- Modify: `tests/test_pricing_engines_oop.cpp`

- [ ] **Step 5.1 — Write failing tests**

```cpp
// ── Task 5: BinomialTreeEngine and FDMEngine env-aware ───────────────────────

TEST(BinomialTreeEngine, EnvAwareReadsDifferentVol) {
    // Construct with vol=0.20 in params; env has vol=0.30 — env wins
    auto envEngine = BinomialTreeEngine(atm(), "AAPL", 500);
    MarketEnvironment env;
    env.setSpot("AAPL", 100.0);
    env.setVolatility("AAPL", 0.30);
    env.addCurve("default",
        qf::termstructure::YieldCurve({0.5,1.0,2.0,5.0},{0.05,0.05,0.05,0.05}));

    double priceVol20 = BinomialTreeEngine(atm(), 500).price(emptyEnv());
    double priceVol30 = envEngine.price(env);
    EXPECT_GT(priceVol30, priceVol20);   // higher vol ⟹ higher option price
}

TEST(BinomialTreeEngine, EnvAwareMissingTickerThrows) {
    auto engine = BinomialTreeEngine(atm(), "AAPL", 500);
    EXPECT_THROW(engine.price(emptyEnv()), std::out_of_range);
}

TEST(FDMEngine, EnvAwareReadsDifferentSpot) {
    auto envEngine = FDMEngine(atm(), "AAPL");
    MarketEnvironment env;
    env.setSpot("AAPL", 90.0);   // OTM
    env.setVolatility("AAPL", 0.20);
    env.addCurve("default",
        qf::termstructure::YieldCurve({0.5,1.0,2.0,5.0},{0.05,0.05,0.05,0.05}));

    double priceATM = FDMEngine(atm()).price(emptyEnv());
    double priceOTM = envEngine.price(env);
    EXPECT_LT(priceOTM, priceATM);   // OTM cheaper than ATM
}

TEST(FDMEngine, EnvAwareMissingTickerThrows) {
    auto engine = FDMEngine(atm(), "AAPL");
    EXPECT_THROW(engine.price(emptyEnv()), std::out_of_range);
}
```

- [ ] **Step 5.2 — Update `include/qf/pricingengines/binomialtree.hpp`**

```cpp
#pragma once
#include <string>
#include <qf/instruments/option.hpp>
#include <qf/pricingengines/ipricing_engine.hpp>

namespace qf::pricingengines {

/// Free function (preserved for backward-compat)
double binomialTreeBSPrice(const instruments::OptionParams& params, int nSteps = 1000);

class BinomialTreeEngine : public IPricingEngine {
public:
    /// Legacy: all market data in params; env is ignored.
    explicit BinomialTreeEngine(instruments::OptionParams params, int nSteps = 1000);

    /// Env-aware: spot, vol, and riskFreeRate read from env using ticker.
    BinomialTreeEngine(instruments::OptionParams params, std::string ticker,
                       int nSteps = 1000);

    double price(const core::MarketEnvironment& env) const override;
    std::string name() const override { return "BinomialTree"; }

private:
    instruments::OptionParams params_;
    std::string ticker_;
    int nSteps_;
};

} // namespace qf::pricingengines
```

- [ ] **Step 5.3 — Update `src/pricingengines/binomialtree.cpp`**

Add at top: `#include <qf/pricingengines/detail/env_resolver.hpp>`

Add new constructor after existing one:

```cpp
BinomialTreeEngine::BinomialTreeEngine(instruments::OptionParams params,
                                        std::string ticker, int nSteps)
    : params_(std::move(params)), ticker_(std::move(ticker)), nSteps_(nSteps) {}
```

Update `price()`:

```cpp
double BinomialTreeEngine::price(const core::MarketEnvironment& env) const {
    auto p = detail::resolveEquityParams(params_, ticker_, env);
    return binomialTreeBSPrice(p, nSteps_);
}
```

- [ ] **Step 5.4 — Update `include/qf/pricingengines/finite_difference.hpp`**

```cpp
#pragma once
#include <string>
#include <qf/instruments/option.hpp>
#include <qf/pricingengines/ipricing_engine.hpp>

namespace qf::pricingengines {

enum class FDMethod { Explicit, Implicit, CrankNicolson };

/// Free function (preserved for backward-compat)
double finiteDifferenceBSPrice(const instruments::OptionParams& params,
                               int nS = 200, int nT = 200,
                               FDMethod method = FDMethod::CrankNicolson);

class FDMEngine : public IPricingEngine {
public:
    /// Legacy: all market data in params; env is ignored.
    explicit FDMEngine(instruments::OptionParams params,
                       int nS = 200, int nT = 200,
                       FDMethod method = FDMethod::CrankNicolson);

    /// Env-aware: spot, vol, and riskFreeRate read from env using ticker.
    FDMEngine(instruments::OptionParams params, std::string ticker,
              int nS = 200, int nT = 200,
              FDMethod method = FDMethod::CrankNicolson);

    double price(const core::MarketEnvironment& env) const override;
    std::string name() const override { return "FiniteDifference"; }

private:
    instruments::OptionParams params_;
    std::string ticker_;
    int nS_, nT_;
    FDMethod method_;
};

} // namespace qf::pricingengines
```

- [ ] **Step 5.5 — Update `src/pricingengines/finite_difference.cpp`**

Add at top: `#include <qf/pricingengines/detail/env_resolver.hpp>`

Add new constructor and update `price()`:

```cpp
FDMEngine::FDMEngine(instruments::OptionParams params, std::string ticker,
                     int nS, int nT, FDMethod method)
    : params_(std::move(params)), ticker_(std::move(ticker)),
      nS_(nS), nT_(nT), method_(method) {}

double FDMEngine::price(const core::MarketEnvironment& env) const {
    auto p = detail::resolveEquityParams(params_, ticker_, env);
    return finiteDifferenceBSPrice(p, nS_, nT_, method_);
}
```

- [ ] **Step 5.6 — Build and run Task 5 tests**

```bash
cd .worktrees/engine-composability/build
make -j$(nproc) && ctest -R "BinomialTree|FDMEngine" --output-on-failure
```
Expected: all `BinomialTree.*` and `FDMEngine.*` tests pass.

- [ ] **Step 5.7 — Run full suite**

```bash
ctest --output-on-failure
```
Expected: 167/167 pass.

- [ ] **Step 5.8 — Commit**

```bash
cd .worktrees/engine-composability
git add include/qf/pricingengines/binomialtree.hpp src/pricingengines/binomialtree.cpp \
        include/qf/pricingengines/finite_difference.hpp src/pricingengines/finite_difference.cpp \
        tests/test_pricing_engines_oop.cpp
git commit -m "feat: BinomialTreeEngine and FDMEngine env-aware constructors"
```

---

## Task 6 — `HestonEngine`: env-aware

**Files:**
- Modify: `include/qf/pricingengines/heston.hpp`
- Modify: `src/pricingengines/heston.cpp`
- Modify: `tests/test_pricing_engines_oop.cpp`

Note: `HestonEngine` reads `spot` and `riskFreeRate` from env (via `resolveSpotAndRate`). It does NOT read `volatility` from env — Heston's stochastic vol is driven by `HestonParams`, not `env.volatility()`.

- [ ] **Step 6.1 — Write failing tests**

```cpp
// ── Task 6: HestonEngine env-aware ───────────────────────────────────────────

TEST(HestonEngine, EnvAwareReadsDifferentSpot) {
    OptionParams opt = {100, 100, 0.05, 0.0, 0.0, 1.0,
                        OptionType::Call, ExerciseType::European};
    HestonParams hp{0.04, 2.0, 0.04, 0.3, -0.7};

    auto envEngine = HestonEngine(opt, hp, "AAPL");

    MarketEnvironment env;
    env.setSpot("AAPL", 110.0);
    env.addCurve("default",
        qf::termstructure::YieldCurve({0.5,1.0,2.0,5.0},{0.05,0.05,0.05,0.05}));

    double priceS100 = HestonEngine(opt, hp).price(emptyEnv());
    double priceS110 = envEngine.price(env);
    EXPECT_GT(priceS110, priceS100);
}

TEST(HestonEngine, EnvAwareMissingSpotThrows) {
    OptionParams opt = {100, 100, 0.05, 0.0, 0.0, 1.0,
                        OptionType::Call, ExerciseType::European};
    HestonParams hp{0.04, 2.0, 0.04, 0.3, -0.7};
    auto engine = HestonEngine(opt, hp, "AAPL");
    EXPECT_THROW(engine.price(emptyEnv()), std::out_of_range);
}
```

- [ ] **Step 6.2 — Update `include/qf/pricingengines/heston.hpp`**

```cpp
#pragma once
#include <string>
#include <qf/instruments/option.hpp>
#include <qf/pricingengines/ipricing_engine.hpp>

namespace qf::pricingengines {

struct HestonParams {
    double v0;
    double kappa;
    double theta;
    double sigma;
    double rho;
};

/// Free functions (preserved for backward-compat and qfpy)
double hestonPrice(const instruments::OptionParams& opt, const HestonParams& heston);
double hestonMonteCarlo(const instruments::OptionParams& opt,
                        const HestonParams& heston,
                        int nPaths = 100000, int nSteps = 252, unsigned seed = 42);

class HestonEngine : public IPricingEngine {
public:
    /// Legacy: all market data in params; env is ignored.
    HestonEngine(instruments::OptionParams opt, HestonParams heston);

    /// Env-aware: spot and riskFreeRate read from env using ticker.
    /// HestonParams are model calibration data — not read from env.
    HestonEngine(instruments::OptionParams opt, HestonParams heston,
                 std::string ticker);

    double price(const core::MarketEnvironment& env) const override;
    std::string name() const override { return "Heston"; }

private:
    instruments::OptionParams opt_;
    HestonParams heston_;
    std::string ticker_;
};

} // namespace qf::pricingengines
```

- [ ] **Step 6.3 — Update `src/pricingengines/heston.cpp`**

Add at top: `#include <qf/pricingengines/detail/env_resolver.hpp>`

Add new constructor and update `price()` (after existing `HestonEngine` constructor and `price()` at the bottom of the file):

```cpp
HestonEngine::HestonEngine(instruments::OptionParams opt, HestonParams heston,
                            std::string ticker)
    : opt_(std::move(opt)), heston_(std::move(heston)), ticker_(std::move(ticker)) {}

double HestonEngine::price(const core::MarketEnvironment& env) const {
    auto [spot, rate] = detail::resolveSpotAndRate(
        opt_.spot, opt_.riskFreeRate, opt_.maturity, ticker_, env);
    auto p = opt_;
    p.spot = spot;
    p.riskFreeRate = rate;
    return hestonPrice(p, heston_);
}
```

Note: the existing `HestonEngine::price()` implementation (which also calls `hestonPrice`) must be removed and replaced with this one.

- [ ] **Step 6.4 — Build and run Task 6 tests**

```bash
cd .worktrees/engine-composability/build
make -j$(nproc) && ctest -R "HestonEngine" --output-on-failure
```
Expected: all `HestonEngine.*` tests pass.

- [ ] **Step 6.5 — Run full suite**

```bash
ctest --output-on-failure
```
Expected: 169/169 pass.

- [ ] **Step 6.6 — Commit**

```bash
cd .worktrees/engine-composability
git add include/qf/pricingengines/heston.hpp src/pricingengines/heston.cpp \
        tests/test_pricing_engines_oop.cpp
git commit -m "feat: HestonEngine env-aware constructor (spot + rate from MarketEnvironment)"
```

---

## Task 7 — `EngineFactory`: ticker support

**Files:**
- Modify: `include/qf/pricingengines/engine_factory.hpp`
- Modify: `src/pricingengines/engine_factory.cpp`
- Modify: `tests/test_pricing_engines_oop.cpp`

- [ ] **Step 7.1 — Write failing tests**

```cpp
// ── Task 7: EngineFactory ticker support ─────────────────────────────────────

TEST(EngineFactory, EnvAwareEngineReadsMktData) {
    // Factory-built engine with ticker reads spot from env
    auto engine = EngineFactory::makeEquityEngine("BS", atm(), 0, 0, "AAPL");

    MarketEnvironment env;
    env.setSpot("AAPL", 110.0);
    env.setVolatility("AAPL", 0.20);
    env.addCurve("default",
        qf::termstructure::YieldCurve({0.5,1.0,2.0,5.0},{0.05,0.05,0.05,0.05}));

    double priceS100 = EngineFactory::makeEquityEngine("BS", atm())->price(emptyEnv());
    double priceS110 = engine->price(env);
    EXPECT_GT(priceS110, priceS100);
}

TEST(EngineFactory, NoTickerStillWorks) {
    // No ticker ⟹ backward-compat (env ignored)
    auto engine = EngineFactory::makeEquityEngine("MC", atm(), 50000, 42);
    EXPECT_GT(engine->price(emptyEnv()), 0.0);
}
```

- [ ] **Step 7.2 — Update `include/qf/pricingengines/engine_factory.hpp`**

```cpp
#pragma once
#include <memory>
#include <string>
#include <qf/pricingengines/ipricing_engine.hpp>
#include <qf/instruments/option.hpp>

namespace qf::pricingengines {

class EngineFactory {
public:
    /// @param method  "BS" | "MC" | "BT" | "FDM"
    /// @param params  OptionParams (contractual + fallback market data)
    /// @param simPaths  Number of MC paths (MC only)
    /// @param seed      RNG seed (MC only)
    /// @param ticker    If non-empty, engine reads market data from MarketEnvironment
    static std::shared_ptr<IPricingEngine>
    makeEquityEngine(const std::string& method,
                     const instruments::OptionParams& params,
                     int simPaths = 100000,
                     unsigned seed = 42,
                     std::string ticker = "");
};

} // namespace qf::pricingengines
```

- [ ] **Step 7.3 — Update `src/pricingengines/engine_factory.cpp`**

```cpp
#include <qf/pricingengines/engine_factory.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <qf/pricingengines/montecarlo.hpp>
#include <qf/pricingengines/binomialtree.hpp>
#include <qf/pricingengines/finite_difference.hpp>
#include <stdexcept>

namespace qf::pricingengines {

std::shared_ptr<IPricingEngine>
EngineFactory::makeEquityEngine(const std::string& method,
                                const instruments::OptionParams& params,
                                int simPaths, unsigned seed,
                                std::string ticker)
{
    if (method == "BS") {
        if (ticker.empty()) return std::make_shared<BlackScholesEngine>(params);
        return std::make_shared<BlackScholesEngine>(params, std::move(ticker));
    }
    if (method == "MC") {
        if (ticker.empty()) return std::make_shared<MonteCarloEngine>(params, simPaths, seed);
        return std::make_shared<MonteCarloEngine>(params, std::move(ticker), simPaths, seed);
    }
    if (method == "BT") {
        if (ticker.empty()) return std::make_shared<BinomialTreeEngine>(params);
        return std::make_shared<BinomialTreeEngine>(params, std::move(ticker));
    }
    if (method == "FDM") {
        if (ticker.empty()) return std::make_shared<FDMEngine>(params);
        return std::make_shared<FDMEngine>(params, std::move(ticker));
    }
    throw std::invalid_argument("EngineFactory: unknown method '" + method + "'");
}

} // namespace qf::pricingengines
```

- [ ] **Step 7.4 — Build and run Task 7 tests**

```bash
cd .worktrees/engine-composability/build
make -j$(nproc) && ctest -R "EngineFactory" --output-on-failure
```
Expected: all `EngineFactory.*` tests pass.

- [ ] **Step 7.5 — Run full suite**

```bash
ctest --output-on-failure
```
Expected: 171/171 pass.

- [ ] **Step 7.6 — Commit**

```bash
cd .worktrees/engine-composability
git add include/qf/pricingengines/engine_factory.hpp src/pricingengines/engine_factory.cpp \
        tests/test_pricing_engines_oop.cpp
git commit -m "feat: EngineFactory accepts optional ticker for env-aware engine construction"
```

---

## Task 8 — Integration test: bump-and-reprice

**Files:**
- Modify: `tests/test_pricing_engines_oop.cpp`

This task validates the complete end-to-end scenario: build a `MarketEnvironment`, price an option, bump a market datum, reprice — without constructing a new engine.

- [ ] **Step 8.1 — Write and run the integration test**

```cpp
// ── Task 8: Bump-and-reprice integration ─────────────────────────────────────

TEST(PricingEngines, BumpAndReprice) {
    // Build env-aware engines once
    auto bs  = EngineFactory::makeEquityEngine("BS",  atm(), 0,      0,  "AAPL");
    auto mc  = EngineFactory::makeEquityEngine("MC",  atm(), 100000, 42, "AAPL");
    auto bt  = EngineFactory::makeEquityEngine("BT",  atm(), 0,      0,  "AAPL");

    // Base scenario: S=100, sigma=0.20, r=0.05
    MarketEnvironment base;
    base.setSpot("AAPL", 100.0);
    base.setVolatility("AAPL", 0.20);
    base.addCurve("default",
        qf::termstructure::YieldCurve({0.5,1.0,2.0,5.0},{0.05,0.05,0.05,0.05}));

    double bsBase  = bs->price(base);
    double mcBase  = mc->price(base);
    double btBase  = bt->price(base);

    // Bump spot +10 (bump the env, not the engine)
    MarketEnvironment bumped = base;
    bumped.setSpot("AAPL", 110.0);

    double bsBumped = bs->price(bumped);
    double mcBumped = mc->price(bumped);
    double btBumped = bt->price(bumped);

    // All engines must show higher call price after spot bump
    EXPECT_GT(bsBumped, bsBase);
    EXPECT_GT(mcBumped, mcBase);
    EXPECT_GT(btBumped, btBase);

    // BS delta ≈ (price_up - price_down) / (2*dS)
    MarketEnvironment down = base;
    down.setSpot("AAPL", 99.0);
    double bsDown = bs->price(down);
    double numericalDelta = (bsBumped - bsDown) / (110.0 - 99.0);
    double analyticalDelta = blackScholes(atm()).delta;
    EXPECT_NEAR(numericalDelta, analyticalDelta, 0.02);
}
```

- [ ] **Step 8.2 — Build and run**

```bash
cd .worktrees/engine-composability/build
make -j$(nproc) && ctest -R "BumpAndReprice" --output-on-failure
```
Expected: `PricingEngines.BumpAndReprice` passes.

- [ ] **Step 8.3 — Run full suite and confirm count**

```bash
ctest --output-on-failure
```
Expected: 172/172 pass.

- [ ] **Step 8.4 — Commit**

```bash
cd .worktrees/engine-composability
git add tests/test_pricing_engines_oop.cpp
git commit -m "test: bump-and-reprice integration — validates env-driven repricing workflow"
```

---

## Task 9 — Merge to master

- [ ] **Step 9.1 — Final check**

```bash
cd .worktrees/engine-composability/build
make -j$(nproc) && ctest --output-on-failure
```
Expected: 172/172 pass, no warnings from changed files.

- [ ] **Step 9.2 — Merge**

```bash
cd ~/Git/Quant_Finance
git checkout master
git merge --no-ff feature/engine-composability \
    -m "feat: engine composability — IEquityModel injection + MarketEnvironment-driven pricing"
git worktree remove .worktrees/engine-composability
```

- [ ] **Step 9.3 — Verify master is clean**

```bash
cd build && make -j$(nproc) && ctest --output-on-failure
```
Expected: 172/172 on master.
