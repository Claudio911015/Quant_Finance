# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test

```bash
# Configure (once)
cmake -S . -B build

# Build everything
cmake --build build --target all 2>&1

# Run C++ tests (GoogleTest) — 153 tests, must all pass before commit
cd build && ctest --output-on-failure 2>&1

# Single test file
cd build && ctest -R CVACalculator --output-on-failure

# Build Python bindings
cmake --build build --target qfpy

# Run Python tests
cmake --build build --target pytests

# Web UI (port 5001)
python3 python_web/app.py
```

**Mandatory workflow per task:** build → ctest → commit. Never advance if any step fails.

## Architecture

### Core abstractions

| Interface | Namespace | Implementations |
|---|---|---|
| `IRateModel` | `qf::models` | `Vasicek`, `HullWhite` |
| `IEquityModel` | `qf::models` | `BlackScholesModel`, `HestonModel` |
| `IPricingEngine` | `qf::pricingengines` | `BlackScholesEngine`, `MonteCarloEngine`, `BinomialTreeEngine`, `FDMEngine`, `HestonEngine` |
| `IUnderlying` | `qf::instruments` | equity underlyings |
| `IMarketObserver` | `qf::core` | instruments that reprice on market data change |

**`MarketEnvironment`** (`qf::core`) is the central market data container. It holds named yield curves, spot prices, and implied vols. Instruments query it at pricing time; it notifies subscribers (Observer pattern) on any mutation.

**`EngineFactory::makeEquityEngine("BS"/"MC"/"BT"/"FDM")`** decouples engine selection from calling code.

**`Instrument::pv(MarketEnvironment)`** is the primary pricing API. The legacy `pv(YieldCurve)` overload is preserved for backward-compat with `qfpy`.

### Important distinction

`HestonModel` (in `qf::models`) ≠ `HestonParams` (in `qf::pricingengines::heston.hpp`) — different namespaces. `HestonParams` is preserved for `qfpy` backward-compat.

### XVA module (`qf::xva`)

`CVACalculator` takes an `IRateModel&` (not a concrete type), `ICreditCurve`, LGD, and `SimParams`. Runs Hull-White Monte Carlo over a `NettingSet`. Python bindings in `src/python_bindings/xva_bindings.cpp` expose `qfxva` module.

### Python bindings

- `qfpy` — main bindings (`src/python_bindings/qfpy.cpp`): options, bonds, swaps, curves
- `qfxva` — XVA bindings (`src/python_bindings/xva_bindings.cpp`): `CVAResult.to_dataframe()`

Web UI (`python_web/app.py`, Flask port 5001) imports `qfpy` from `build/src/`. Build `qfpy` target before running.

### Web UI pages

2 pages, 8 JSON endpoints: Options (BS/MC/BT/FDM) and Bonds/Swaps/IRS tab.

## File Conventions

**For each new feature, create three files:**
```
include/qf/<module>/MyClass.hpp
src/<module>/MyClass.cpp
tests/test_MyClass.cpp
```
Update `CMakeLists.txt` if adding new source files or test targets.

**Namespaces:** `qf::instruments`, `qf::pricingengines`, `qf::models`, `qf::math`, `qf::risk`, `qf::termstructure`, `qf::xva`, `qf::core`

**Naming:** `PascalCase` classes · `camelCase` methods/variables · `UPPER_SNAKE_CASE` constants

**Doxygen** all public methods: `@brief`, `@param`, `@return`.

## Plans & Specs

Implementation plans and design specs live in `docs/superpowers/plans/` and `docs/superpowers/specs/`. Read the relevant spec before working on any existing feature area. Active plan: `2026-04-19-quantengine-merge.md` (merging QF + MarketDataFeed into QuantEngine).
