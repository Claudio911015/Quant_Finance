# Graph Report - /home/claudio/Git/Quant_Finance  (2026-06-23)

## Corpus Check
- Corpus is ~47,899 words - fits in a single context window. You may not need a graph.

## Summary
- 486 nodes · 796 edges · 37 communities detected
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 26 edges (avg confidence: 0.63)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `MarketEnvironmentBuilder` - 27 edges
2. `AppTestCase` - 19 edges
3. `qf Static Library` - 13 edges
4. `_MarketEnvironment` - 9 edges
5. `QuantFinance Library` - 8 edges
6. `fetch_treasury_curve_yfinance()` - 7 edges
7. `_make_ticker_mock()` - 7 edges
8. `price()` - 7 edges
9. `fetch_treasury_curve_fred()` - 6 edges
10. `fetch_equity()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `MarketEnvironmentBuilder` --conceptually_related_to--> `MarketEnvironment (qf::core)`  [INFERRED]
  python/market_feed.py → CLAUDE.md
- `_YieldCurve Stub` --conceptually_related_to--> `qfpy.YieldCurve (C++ binding)`  [INFERRED]
  python/tests/test_market_feed.py → src/CMakeLists.txt
- `_MarketEnvironment Stub` --conceptually_related_to--> `qfpy.MarketEnvironment (C++ binding)`  [INFERRED]
  python/tests/test_market_feed.py → src/CMakeLists.txt
- `fetch_treasury_curve_yfinance()` --calls--> `qfpy.YieldCurve (C++ binding)`  [EXTRACTED]
  python/market_feed.py → src/CMakeLists.txt
- `fetch_treasury_curve_fred()` --calls--> `qfpy.YieldCurve (C++ binding)`  [EXTRACTED]
  python/market_feed.py → src/CMakeLists.txt

## Communities

### Community 0 - "Binomial Tree Pricing"
Cohesion: 0.07
Nodes (28): binomialTreeBSPrice(), price(), blackScholes(), impliedVolatility(), price(), EngineFactory, finiteDifferenceBSPrice(), optionIntrinsic() (+20 more)

### Community 1 - "Market Environment Builder"
Cohesion: 0.05
Nodes (32): MarketEnvironmentBuilder, Construye un qfpy.MarketEnvironment listo para usar con los pricing engines., Descarga datos y devuelve el MarketEnvironment.          Args:             verbo, _make_fred_response(), _make_ticker_mock(), _make_yf_df(), _MarketEnvironment, Simula una respuesta CSV de FRED con una sola fila de datos. (+24 more)

### Community 2 - "Architecture & Build Config"
Cohesion: 0.07
Nodes (35): build_release CMakeCache (Release build), CVACalculator (qf::xva), EngineFactory, IRateModel Interface, MarketEnvironment (qf::core), example_live.py — Demostración del feed de datos reales + pricing con qfpy.  Des, MarketEnvironmentBuilder, env_summary() (+27 more)

### Community 3 - "Equity Models (BS & Heston)"
Cohesion: 0.09
Nodes (11): simulate(), theta(), zeroRate(), IEquityModel, IRateModel, TEST(), testCurve(), TEST() (+3 more)

### Community 4 - "Yield Curve Bootstrap"
Cohesion: 0.11
Nodes (16): annuity(), flatCurve(), irsNPV(), slopedCurve(), TEST(), annuity(), flatCurve(), irsNPV() (+8 more)

### Community 5 - "Cap/Floor IR Instruments"
Cohesion: 0.1
Nodes (13): calculatePV(), hwBondOption(), price(), Instrument, IPricingEngine, calculatePV(), hwB(), hwSigmaP() (+5 more)

### Community 6 - "Flask Web App Tests"
Cohesion: 0.12
Nodes (5): AppTestCase, ExerciseType, FDMethod, InterpolationMethod, OptionType

### Community 7 - "Market Observer Interface"
Cohesion: 0.11
Nodes (12): IMarketObserver, MarketEnvironment, addCurve(), MarketEnvironment(), notify(), setSpot(), setVolatility(), flatCurve() (+4 more)

### Community 8 - "Credit Curve & Hazard Rate"
Cohesion: 0.14
Nodes (6): ICreditCurve, NettingSet, flatCurve(), quarterlyDates(), TEST(), PyICreditCurve

### Community 9 - "Swap Pricing"
Cohesion: 0.14
Nodes (12): annuity(), calculateCouponPV(), calculatePV(), cashFlows(), discountAnnuity(), Leg, makeFixed(), makeFloating() (+4 more)

### Community 10 - "Greeks & Risk Measures"
Cohesion: 0.13
Nodes (7): identityCorr(), TEST(), atmCall(), bsPrice(), TEST(), parametricVaR(), portfolioVaR()

### Community 11 - "Bond Pricing"
Cohesion: 0.26
Nodes (10): calculatePV(), cashflows(), convexity(), duration(), maturities(), price(), yield(), flatCurve() (+2 more)

### Community 12 - "Flask REST API"
Cohesion: 0.14
Nodes (2): api_swap(), Price an IRS or ScheduledSwap.      Request JSON (mode='regular'):     {

### Community 13 - "Swaps Frontend JS"
Cohesion: 0.35
Nodes (9): formatCurrency(), getCurve(), hideSwError(), priceRegular(), priceScheduled(), setLoading(), setMode(), showResults() (+1 more)

### Community 14 - "Bonds Frontend JS"
Cohesion: 0.33
Nodes (7): calcBond(), fetchYieldCurve(), getCurveData(), hideError(), renderYieldCurve(), setLoading(), showError()

### Community 15 - "Python Bindings (pybind11)"
Cohesion: 0.2
Nodes (10): Instruments Module, Math Module, Pricing Engines Module, qfpy Python Bindings (pybind11), QuantFinance Library, Rate Models Module, Risk Module, Term Structure Module (+2 more)

### Community 16 - "Numerical Methods"
Cohesion: 0.31
Nodes (2): gaussLegendre(), glNodesWeights()

### Community 17 - "Heston Frontend JS"
Cohesion: 0.42
Nodes (7): fetchHeston(), hideError(), price(), row(), setLoading(), showError(), validate()

### Community 18 - "Underlying Asset Types"
Cohesion: 0.29
Nodes (1): IUnderlying

### Community 19 - "Charts & UI Frontend"
Cohesion: 0.46
Nodes (7): fetchConvergence(), fetchGreeksSurface(), fetchPayoff(), getFormPayload(), renderConvergenceChart(), renderGreeksChart(), renderPayoffChart()

### Community 20 - "XVA Python Tests"
Cohesion: 0.57
Nodes (6): _make_env(), _make_hw(), _quarterly(), Python-level tests for qfxva bindings., test_cva_positive_for_itm_receiver(), test_result_to_dataframe()

### Community 21 - "Release Build Targets"
Cohesion: 0.5
Nodes (4): build_release Release Build Configuration, doxygen CMake Target, pytests CMake Target, run_web_ui CMake Target

### Community 22 - "IR & Equity Examples"
Cohesion: 0.67
Nodes (3): heston Example Executable, interest_rate_models Example Executable, swap_pricing Example Executable

### Community 23 - "CMake Compiler ID"
Cohesion: 1.0
Nodes (0): 

### Community 24 - "CMake Project Structure"
Cohesion: 1.0
Nodes (2): Examples Targets, QuantFinance CMake Project

### Community 25 - "Yield Curve Examples"
Cohesion: 1.0
Nodes (2): bootstrap Example Executable, yield_curve Example Executable

### Community 26 - "Python Package Init"
Cohesion: 1.0
Nodes (0): 

### Community 27 - "Compiler Dependencies"
Cohesion: 1.0
Nodes (0): 

### Community 28 - "Architecture Docs"
Cohesion: 1.0
Nodes (1): CLAUDE.md — Architecture & Build Guide

### Community 29 - "IEquityModel Interface"
Cohesion: 1.0
Nodes (1): IEquityModel Interface

### Community 30 - "IPricingEngine Interface"
Cohesion: 1.0
Nodes (1): IPricingEngine Interface

### Community 31 - "Monte Carlo Example"
Cohesion: 1.0
Nodes (1): monte_carlo Example Executable

### Community 32 - "Bond Pricing Example"
Cohesion: 1.0
Nodes (1): bond_pricing Example Executable

### Community 33 - "Black-Scholes Example"
Cohesion: 1.0
Nodes (1): black_scholes Example Executable

### Community 34 - "qf Static Library Target"
Cohesion: 1.0
Nodes (1): qf CMake Target (Static Library)

### Community 35 - "qfpy Bindings Target"
Cohesion: 1.0
Nodes (1): qfpy CMake Target (Python Bindings)

### Community 36 - "Test Suite Target"
Cohesion: 1.0
Nodes (1): qf_tests CMake Target (Test Suite)

## Knowledge Gaps
- **58 isolated node(s):** `market_feed.py — Feeds de datos reales hacia qf::core::MarketEnvironment.  Fuent`, `Obtiene el último precio de cierre usando yfinance 1.x (MultiIndex DataFrame).`, `Descarga yields del Tesoro US vía Yahoo Finance y construye una YieldCurve.`, `Descarga la curva del Tesoro US desde FRED (Federal Reserve Bank of St. Louis).`, `Devuelve (spot, atm_iv) para el ticker dado.      La vol implícita ATM se estima` (+53 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `CMake Compiler ID`** (2 nodes): `CMakeCXXCompilerId.cpp`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `CMake Project Structure`** (2 nodes): `Examples Targets`, `QuantFinance CMake Project`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Yield Curve Examples`** (2 nodes): `bootstrap Example Executable`, `yield_curve Example Executable`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Python Package Init`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Compiler Dependencies`** (1 nodes): `compiler_depend.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Architecture Docs`** (1 nodes): `CLAUDE.md — Architecture & Build Guide`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `IEquityModel Interface`** (1 nodes): `IEquityModel Interface`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `IPricingEngine Interface`** (1 nodes): `IPricingEngine Interface`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Monte Carlo Example`** (1 nodes): `monte_carlo Example Executable`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Bond Pricing Example`** (1 nodes): `bond_pricing Example Executable`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Black-Scholes Example`** (1 nodes): `black_scholes Example Executable`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `qf Static Library Target`** (1 nodes): `qf CMake Target (Static Library)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `qfpy Bindings Target`** (1 nodes): `qfpy CMake Target (Python Bindings)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Test Suite Target`** (1 nodes): `qf_tests CMake Target (Test Suite)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MarketEnvironmentBuilder` connect `Community 1` to `Community 2`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `MarketEnvironmentBuilder` (e.g. with `example_live.py — Demostración del feed de datos reales + pricing con qfpy.  Des` and `_YieldCurve`) actually correct?**
  _`MarketEnvironmentBuilder` has 14 INFERRED edges - model-reasoned connections that need verification._
- **What connects `market_feed.py — Feeds de datos reales hacia qf::core::MarketEnvironment.  Fuent`, `Obtiene el último precio de cierre usando yfinance 1.x (MultiIndex DataFrame).`, `Descarga yields del Tesoro US vía Yahoo Finance y construye una YieldCurve.` to the rest of the system?**
  _58 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.07 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.05 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.07 - nodes in this community are weakly interconnected._
- **Should `Community 3` be split into smaller, more focused modules?**
  _Cohesion score 0.09 - nodes in this community are weakly interconnected._