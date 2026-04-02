# Architecture Refactor — Design Spec
**Date:** 2026-04-02  
**Project:** Quant_Finance  
**Status:** Approved

---

## 1. Context and Motivation

The library already has a working `Instrument` base class with `calculatePV()` virtual pure, and concrete instruments (`Bond`, `Option`, `Swap`, `Leg`) that inherit from it. However, three architectural gaps exist:

1. **Models have no common interface.** `Vasicek` and `HullWhite` are standalone concrete classes. `Heston` is incorrectly placed in `pricingengines/` mixing model parameters with pricing logic.
2. **Pricing engines are free functions.** `blackScholes(...)`, `monteCarloBSPrice(...)`, `binomialTreeBSPrice(...)`, etc. are standalone functions — no `IPricingEngine` interface, no Strategy pattern, despite copilot-instructions documenting this as the desired pattern.
3. **Underlyings are not abstracted.** `Option` has public fields (`spot`, `strike`, `vol`...) mixing contractual terms with underlying data. `OptionParams` is a flat DTO with no type hierarchy. `InterestRateSwap` redeclares state already present in its base classes.
4. **`Instrument::pv()` is hardcoded to `YieldCurve`.** Options do not naturally take a yield curve as their primary market input — this coupling forces `calculatePV()` to ignore the curve or use it artificially.

### Constraints

- **Backward-compatible with `examples/` and Python bindings (`qfpy`).** All existing free functions, `OptionParams`, and `YieldCurve`-based APIs must continue to compile and behave identically.
- **C++17**, existing namespace structure (`qf::instruments`, `qf::pricingengines`, `qf::models`, etc.), and CMake build system are preserved.

---

## 2. Chosen Approach

**Thin interfaces per domain + Strategy pattern + MarketEnvironment**

Three orthogonal abstractions, each with single responsibility:

```
IUnderlying          IRateModel / IEquityModel      IPricingEngine
─────────────        ──────────────────────────     ──────────────
EquityUnderlying  →  Vasicek (IRateModel)        →  BlackScholesEngine
RateUnderlying    →  HullWhite (IRateModel)      →  MonteCarloEngine
                  →  HestonModel (IEquityModel)   →  BinomialTreeEngine
                  →  BlackScholesModel            →  FDMEngine
                                                  →  HestonEngine
```

A `MarketEnvironment` aggregates yield curves, spots, and volatilities. `Instrument::pv()` receives `MarketEnvironment` instead of `YieldCurve`. Legacy APIs are preserved via thin overloads and wrappers.

---

## 3. Component Design

### 3.1 `MarketEnvironment`

**File:** `include/qf/core/market_environment.hpp` + `src/core/market_environment.cpp`

```cpp
namespace qf::core {

class MarketEnvironment {
public:
    // Yield curves indexed by name (e.g. "USD", "MXN", "default")
    void addCurve(const std::string& name, termstructure::YieldCurve curve);
    const termstructure::YieldCurve& curve(const std::string& name = "default") const;

    // Equity market data
    void setSpot(const std::string& ticker, double spot);
    void setVolatility(const std::string& ticker, double vol);
    double spot(const std::string& ticker) const;
    double volatility(const std::string& ticker) const;

    // Convenience constructor for single-curve use (backward-compat)
    explicit MarketEnvironment(termstructure::YieldCurve defaultCurve);
};

} // namespace qf::core
```

**Backward-compat:** `Instrument` retains a deprecated overload:
```cpp
double pv(const termstructure::YieldCurve& curve) const;
// Internally: return pv(core::MarketEnvironment(curve));
```
This keeps all existing `examples/` and Python bindings compiling without modification.

---

### 3.2 Model Interfaces

**File:** `include/qf/models/irate_model.hpp`

```cpp
namespace qf::models {

class IRateModel {
public:
    virtual ~IRateModel() = default;

    /// Analytical zero-coupon bond price P(0, T)
    virtual double bondPrice(double T) const = 0;

    /// Zero rate for maturity T
    virtual double zeroRate(double T) const = 0;

    /// Simulate rate path (Euler-Maruyama or equivalent)
    virtual std::vector<double> simulate(double T, int steps,
                                          unsigned seed = 42) const = 0;
};

} // namespace qf::models
```

**File:** `include/qf/models/iequity_model.hpp`

```cpp
namespace qf::models {

class IEquityModel {
public:
    virtual ~IEquityModel() = default;

    /// Simulate underlying price path
    virtual std::vector<double> simulate(double S0, double T,
                                          int steps, unsigned seed = 42) const = 0;

    /// Risk-neutral density (optional — default returns 0.0)
    virtual double riskNeutralDensity(double S, double T) const { return 0.0; }
};

} // namespace qf::models
```

**Modifications to existing model classes:**

| Class | Change |
|-------|--------|
| `Vasicek` | Add `public IRateModel`, mark methods `override` |
| `HullWhite` | Add `public IRateModel`, mark methods `override` |
| `HestonModel` *(new)* | New class in `models/`, extracted from `pricingengines/heston.cpp`, implements `IEquityModel` |
| `BlackScholesModel` *(new)* | Thin wrapper in `models/`, implements `IEquityModel` using GBM simulation |

**Heston split:** The current `heston.cpp` in `pricingengines/` mixes model parameters and pricing formula. It is split into:
- `models/heston_model.hpp/cpp` — parameters (`kappa`, `theta`, `sigma`, `rho`, `v0`) + `simulate()`
- `pricingengines/heston_engine.hpp/cpp` — `HestonEngine : IPricingEngine` using Heston characteristic function

The existing `hestonPrice(HestonParams)` free function is kept as a one-line wrapper.

---

### 3.3 `IPricingEngine` and Strategy Pattern

**File:** `include/qf/pricingengines/ipricing_engine.hpp`

```cpp
namespace qf::pricingengines {

class IPricingEngine {
public:
    virtual ~IPricingEngine() = default;

    /// Compute price given current market environment
    virtual double price(const core::MarketEnvironment& env) const = 0;

    /// Engine identifier (for logging/debugging)
    virtual std::string name() const = 0;
};

} // namespace qf::pricingengines
```

**Concrete engine classes** (each free function becomes a class):

| New Class | Implements | Wraps existing function |
|-----------|-----------|------------------------|
| `BlackScholesEngine` | `IPricingEngine` | `blackScholes(OptionParams)` |
| `MonteCarloEngine` | `IPricingEngine` | `monteCarloBSPrice(OptionParams, N, seed)` |
| `BinomialTreeEngine` | `IPricingEngine` | `binomialTreeBSPrice(OptionParams, nSteps)` |
| `FDMEngine` | `IPricingEngine` | existing FDM function |
| `HestonEngine` | `IPricingEngine` | `hestonPrice(HestonParams)` |

All original free functions are preserved as one-line wrappers — zero breakage.

**`Instrument` gains an optional engine (Strategy pattern):**

```cpp
class Instrument {
public:
    void setPricingEngine(std::shared_ptr<IPricingEngine> engine);

    // With engine assigned: delegates to engine->price(env)
    // Without engine: falls back to calculatePV(env) (existing behavior)
    double pv(const core::MarketEnvironment& env) const;

    // Legacy overload for backward-compat
    double pv(const termstructure::YieldCurve& curve) const;

protected:
    virtual double calculatePV(const core::MarketEnvironment& env) const = 0;

private:
    std::shared_ptr<IPricingEngine> engine_;
    double maturity_ = 0.0;
    mutable double pv_ = 0.0;
};
```

**`EngineFactory`:**

```cpp
// include/qf/pricingengines/engine_factory.hpp
namespace qf::pricingengines {

class EngineFactory {
public:
    /// Create an equity pricing engine by method name
    /// method: "BS" | "MC" | "BT" | "FDM" | "Heston"
    static std::shared_ptr<IPricingEngine>
    makeEquityEngine(const std::string& method,
                     const instruments::OptionParams& params,
                     int simPaths = 100000,
                     unsigned seed = 42);

    /// Create a rate model engine
    /// model: "Vasicek" | "HullWhite"
    static std::shared_ptr<IPricingEngine>
    makeRateEngine(const std::string& model,
                   const models::IRateModel& rateModel);
};

} // namespace qf::pricingengines
```

Usage with new API (optional — legacy still works):
```cpp
auto engine = EngineFactory::makeEquityEngine("MC", params, 200000);
option.setPricingEngine(engine);
double price = option.pv(env);  // delegates to MonteCarloEngine

// Legacy — unchanged
double price = monteCarloBSPrice(params, 200000);
```

---

### 3.4 `IUnderlying` and `Option` Refactor

**File:** `include/qf/instruments/iunderlying.hpp`

```cpp
namespace qf::instruments {

class IUnderlying {
public:
    virtual ~IUnderlying() = default;
    /// Key for MarketEnvironment lookup (ticker or curve name)
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

**`Option` — encapsulation + composition:**

Current `Option` has public fields (`spot`, `strike`, `volatility`, ...) mixing underlying data with contractual terms.

After refactor:
```cpp
class Option : public Instrument {
public:
    Option(std::shared_ptr<IUnderlying> underlying,
           double strike, double maturity,
           OptionType type, ExerciseType exercise);

    // All accessors are const — immutable after construction
    double strike() const;
    OptionType optionType() const;
    ExerciseType exerciseType() const;
    const IUnderlying& underlying() const;

    // calculatePV resolves spot/vol from MarketEnvironment via underlying.id()
    double calculatePV(const core::MarketEnvironment& env) const override;

protected:
    std::shared_ptr<IUnderlying> underlying_;
    double strike_;
    OptionType type_;
    ExerciseType exercise_;
};
```

`OptionParams` struct is **preserved unchanged** as the DTO used by free functions and Python bindings.

---

### 3.5 `InterestRateSwap` — Remove Duplicated State

`InterestRateSwap` currently redeclares `notional_`, `fixedRate_`, `maturity_`, `frequency_` that already exist in `Instrument` base or in the `Leg` objects it holds via `Swap`.

After refactor, `InterestRateSwap` holds only what's genuinely new:

```cpp
class InterestRateSwap : public Swap {
public:
    InterestRateSwap(double notional, double fixedRate,
                     double maturity, double frequency, SwapType type);

    // Uses payLeg()/receiveLeg() inherited from Swap — no data duplication
    double npv(const core::MarketEnvironment& env) const;
    double annuity(const core::MarketEnvironment& env) const;

    static double parRate(double maturity, double frequency,
                          const core::MarketEnvironment& env);
    static double annuity(double maturity, double frequency,
                          const core::MarketEnvironment& env);

private:
    SwapType type_;  // Only new state — SwapType is not in Swap base
};
```

---

## 4. File Inventory

### New files

| Header | Implementation | Description |
|--------|---------------|-------------|
| `include/qf/core/market_environment.hpp` | `src/core/market_environment.cpp` | Central market data container |
| `include/qf/models/irate_model.hpp` | *(header-only interface)* | Abstract rate model |
| `include/qf/models/iequity_model.hpp` | *(header-only interface)* | Abstract equity model |
| `include/qf/models/heston_model.hpp` | `src/models/heston_model.cpp` | Heston parameters + simulation |
| `include/qf/models/bs_model.hpp` | `src/models/bs_model.cpp` | GBM simulation under BS |
| `include/qf/pricingengines/ipricing_engine.hpp` | *(header-only interface)* | Abstract pricing engine |
| `include/qf/pricingengines/engine_factory.hpp` | `src/pricingengines/engine_factory.cpp` | Factory for engine creation |
| `include/qf/instruments/iunderlying.hpp` | `src/instruments/iunderlying.cpp` | Abstract underlying + EquityUnderlying + RateUnderlying |

### Modified files

| File | Change |
|------|--------|
| `include/qf/instruments/instrument.hpp` | `pv(YieldCurve)` → `pv(MarketEnvironment)` + legacy overload + `engine_` member |
| `include/qf/instruments/option.hpp` | Encapsulate fields, compose `IUnderlying` |
| `include/qf/instruments/swap.hpp` | Remove duplicate state from `InterestRateSwap` |
| `include/qf/models/vasicek.hpp` | Add `public IRateModel`, `override` |
| `include/qf/models/hullwhite.hpp` | Add `public IRateModel`, `override` |
| `include/qf/pricingengines/blackscholes.hpp` | Add `BlackScholesEngine : IPricingEngine` |
| `include/qf/pricingengines/montecarlo.hpp` | Add `MonteCarloEngine : IPricingEngine` |
| `include/qf/pricingengines/binomialtree.hpp` | Add `BinomialTreeEngine : IPricingEngine` |
| `include/qf/pricingengines/finite_difference.hpp` | Add `FDMEngine : IPricingEngine` |
| `include/qf/pricingengines/heston.hpp` | Add `HestonEngine : IPricingEngine`; split model to `models/` |
| `CMakeLists.txt` | Register new source files in `src/core/`, `src/models/` |

### Untouched files (backward-compat guarantee)

- All `examples/*.cpp`
- `src/python_bindings/qfpy.cpp`
- `include/qf/instruments/bond.hpp` and `src/instruments/bond.cpp`
- `include/qf/math/*.hpp`, `include/qf/risk/*.hpp`, `include/qf/termstructure/*.hpp`
- All `tests/test_*.cpp` (existing tests continue to pass without modification)

---

## 5. Testing Strategy

- Every new interface and concrete class gets a corresponding `tests/test_*.cpp`
- New test files: `test_market_environment.cpp`, `test_models_interfaces.cpp`, `test_pricing_engines.cpp`, `test_underlyings.cpp`
- Existing tests (`test_instruments.cpp`, `test_pricingengines.cpp`, etc.) must pass **without modification** — this is the primary backward-compat validation gate
- Build verification: `cd build && cmake --build . --target all && ctest --output-on-failure`

---

## 6. Design Patterns Applied

| Pattern | Where |
|---------|-------|
| **Strategy** | `Instrument::setPricingEngine()` + `IPricingEngine` |
| **Factory Method** | `EngineFactory::makeEquityEngine()` / `makeRateEngine()` |
| **Facade** | Legacy free functions as thin wrappers over new engine classes |
| **Adapter** | `pv(YieldCurve)` overload adapts old API to new `MarketEnvironment` |
| **Template Method** | `Instrument::pv()` orchestrates `calculatePV()` or `engine_->price()` |

---

## 7. Out of Scope

- Calibration methods (`calibrate()`) on model classes — future iteration
- Observer pattern for curve/parameter changes — future iteration
- Additional instruments (Swaption, Cap, Floor) — future iteration
- GPU / AAD pricing engines — future iteration
