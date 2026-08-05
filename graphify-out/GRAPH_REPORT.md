# Graph Report - /home/claudio/Git/Quant_Finance  (2026-07-07)

## Corpus Check
- 137 files · ~60,000 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 527 nodes · 889 edges · 35 communities detected
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 16 edges (avg confidence: 0.87)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `AppTestCase` - 19 edges
2. `DualCurveBindings` - 8 edges
3. `QuantFinance Library` - 8 edges
4. `CVACalculator` - 8 edges
5. `VolSurfaceBindings` - 7 edges
6. `ScenarioEngineBindings` - 7 edges
7. `price()` - 7 edges
8. `HestonCalibrationBindings` - 6 edges
9. `priceRegular()` - 6 edges
10. `priceScheduled()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `IPricingEngine Interface` --semantically_similar_to--> `Pricing Engines Module`  [INFERRED] [semantically similar]
  docs/superpowers/specs/2026-04-02-architecture-refactor-design.md → README.md
- `IRateModel Interface` --semantically_similar_to--> `Rate Models Module`  [INFERRED] [semantically similar]
  docs/superpowers/specs/2026-04-02-architecture-refactor-design.md → README.md
- `Flask (Python web dependency)` --conceptually_related_to--> `QuantFinance Library`  [INFERRED]
  python_web/requirements.txt → README.md
- `Backward Compatibility Constraint` --conceptually_related_to--> `qfpy Python Bindings (pybind11)`  [INFERRED]
  docs/superpowers/specs/2026-04-02-architecture-refactor-design.md → README.md
- `Hull-White short-rate model` --implements--> `IRateModel interface`  [INFERRED]
  docs/superpowers/specs/2026-04-15-cva-engine-design.md → CLAUDE.md

## Hyperedges (group relationships)
- **Strategy Pattern Interface Trio** — design_ipricing_engine, design_irate_model, design_iequity_model [EXTRACTED 0.95]
- **XVA computation flow: MC paths to EPE/ENE to CVA/DVA/FVA** — qf_CVACalculator, qf_EPE, qf_ENE, qf_CVA, qf_DVA, qf_FVA [EXTRACTED 1.00]
- **Rate risk: scenario repricing yields DV01 ladders and P&L shocks** — qf_ScenarioEngine, qf_YieldCurve, qf_Instrument, qf_KeyRateDV01, qf_ParallelDV01 [EXTRACTED 1.00]
- **Equity vol marking: quoted chains to Heston calibration to VolSurface to engine repricing** — qf_OptionQuote, qf_HestonCalibrator, qf_VolSurface, qf_BlackScholesEngine, qf_MonteCarloEngine [INFERRED 0.85]

## Communities

### Community 0 - "Equity Pricing Engines"
Cohesion: 0.06
Nodes (29): binomialTreeBSPrice(), price(), blackScholes(), impliedVolatility(), price(), EngineFactory, example_live.py — Demostración del feed de datos reales + pricing con qfpy.  Des, finiteDifferenceBSPrice() (+21 more)

### Community 1 - "Market Environment & Observers"
Cohesion: 0.08
Nodes (22): IMarketObserver, MarketEnvironment, addCurve(), MarketEnvironment(), notify(), setSpot(), setVolatility(), setVolSurface() (+14 more)

### Community 2 - "Design Specs: Core Concepts"
Cohesion: 0.07
Nodes (35): Bilateral CVA (BCVA), Bond, Counterparty Valuation Adjustment (CVA), CVACalculator, CVAResult (CVA + DVA + FVA + profile), CapFloor, Credit curve (counterparty default probability), Debit Valuation Adjustment (DVA) (+27 more)

### Community 3 - "Rate & Equity Models"
Cohesion: 0.09
Nodes (11): simulate(), theta(), zeroRate(), IEquityModel, IRateModel, TEST(), testCurve(), TEST() (+3 more)

### Community 4 - "Instruments & Day Count"
Cohesion: 0.1
Nodes (13): calculatePV(), hwBondOption(), price(), Instrument, IPricingEngine, calculatePV(), hwB(), hwSigmaP() (+5 more)

### Community 5 - "Yield Curve & Bootstrap"
Cohesion: 0.12
Nodes (14): annuity(), flatCurve(), irsNPV(), slopedCurve(), TEST(), flatCurve(), slopedCurve(), TEST() (+6 more)

### Community 6 - "Web App Tests"
Cohesion: 0.12
Nodes (5): AppTestCase, ExerciseType, FDMethod, InterpolationMethod, OptionType

### Community 7 - "CVA/XVA Engine"
Cohesion: 0.13
Nodes (6): ICreditCurve, NettingSet, flatCurve(), quarterlyDates(), TEST(), PyICreditCurve

### Community 8 - "Risk & VaR"
Cohesion: 0.13
Nodes (7): identityCorr(), TEST(), atmCall(), bsPrice(), TEST(), parametricVaR(), portfolioVaR()

### Community 9 - "Swap Pricing"
Cohesion: 0.18
Nodes (14): annuity(), calculateCouponPV(), calculatePV(), cashFlows(), discountAnnuity(), Leg, makeFixed(), makeFloating() (+6 more)

### Community 10 - "Heston Calibration & Vol Surface"
Cohesion: 0.18
Nodes (12): calibrate(), fromUnconstrained(), toUnconstrained(), tryImpliedVol(), makeSyntheticQuotes(), TEST(), makeGrid(), TEST() (+4 more)

### Community 11 - "Library Architecture"
Cohesion: 0.12
Nodes (17): Backward Compatibility Constraint, EngineFactory, IEquityModel Interface, IPricingEngine Interface, IRateModel Interface, MarketEnvironment, Strategy Pattern for Pricing, Instruments Module (+9 more)

### Community 12 - "Scenario & Dual-curve Tests"
Cohesion: 0.24
Nodes (13): flattener(), keyRateDV01s(), parallelDV01(), parallelShock(), priceWithCurve(), rampShifts(), runScenario(), steepener() (+5 more)

### Community 13 - "Flask API Routes"
Cohesion: 0.14
Nodes (2): api_swap(), Price an IRS or ScheduledSwap.      Request JSON (mode='regular'):     {

### Community 14 - "Bond Instruments"
Cohesion: 0.32
Nodes (10): calculatePV(), cashflows(), convexity(), duration(), maturities(), price(), yield(), flatCurve() (+2 more)

### Community 15 - "Numerical Math"
Cohesion: 0.23
Nodes (5): gaussLegendre(), glNodesWeights(), centroid(), extrapolate(), nelderMead()

### Community 16 - "Dual-curve Py Bindings"
Cohesion: 0.27
Nodes (3): _curve(), DualCurveBindings, Python-side tests for the dual-curve swap bindings (P5c).  Verifies capabilities

### Community 17 - "Swaps Web UI"
Cohesion: 0.35
Nodes (9): formatCurrency(), getCurve(), hideSwError(), priceRegular(), priceScheduled(), setLoading(), setMode(), showResults() (+1 more)

### Community 18 - "Underlyings"
Cohesion: 0.22
Nodes (1): IUnderlying

### Community 19 - "VolSurface Py Bindings"
Cohesion: 0.22
Nodes (2): Python-side tests for the VolSurface bindings (P4c).  Imports the *real* built q, VolSurfaceBindings

### Community 20 - "ScenarioEngine Py Bindings"
Cohesion: 0.31
Nodes (2): Python-side smoke tests for the qf::risk ScenarioEngine bindings (P2c).  Imports, ScenarioEngineBindings

### Community 21 - "Bonds Web UI"
Cohesion: 0.33
Nodes (7): calcBond(), fetchYieldCurve(), getCurveData(), hideError(), renderYieldCurve(), setLoading(), showError()

### Community 22 - "Heston Calib Bindings"
Cohesion: 0.39
Nodes (2): HestonCalibrationBindings, Python-side round-trip test for the Heston calibration bindings (P3c).  Imports

### Community 23 - "Web UI Core"
Cohesion: 0.42
Nodes (7): fetchHeston(), hideError(), price(), row(), setLoading(), showError(), validate()

### Community 24 - "Charts Web UI"
Cohesion: 0.46
Nodes (7): fetchConvergence(), fetchGreeksSurface(), fetchPayoff(), getFormPayload(), renderConvergenceChart(), renderGreeksChart(), renderPayoffChart()

### Community 25 - "XVA Py Tests"
Cohesion: 0.57
Nodes (6): _make_env(), _make_hw(), _quarterly(), Python-level tests for qfxva bindings., test_cva_positive_for_itm_receiver(), test_result_to_dataframe()

### Community 26 - "Dual-curve Design"
Cohesion: 0.33
Nodes (7): CurveKeys (discountKey + projectionKey), Dual-curve pricing (OIS + projection), InterestRateSwap, OIS/index basis spread, OIS discount curve, Projection/index curve, ScheduledSwap

### Community 27 - "Market Data Feed"
Cohesion: 0.67
Nodes (5): MarketEnvironmentBuilder, fetch_equity, fetch_treasury_curve_fred, fetch_treasury_curve_yfinance, _yf_last_close

### Community 28 - "Engine Factory"
Cohesion: 0.5
Nodes (4): BlackScholesEngine, EngineFactory, IPricingEngine interface, MonteCarloEngine

### Community 29 - "CMake Build"
Cohesion: 1.0
Nodes (2): Examples Targets, QuantFinance CMake Project

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): env_summary

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): _YieldCurve Stub

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): _MarketEnvironment Stub

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (0): 

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): IUnderlying Interface

## Knowledge Gaps
- **57 isolated node(s):** `env_summary`, `example_live.py — Demostración del feed de datos reales + pricing con qfpy.  Des`, `_YieldCurve Stub`, `_MarketEnvironment Stub`, `IPricingEngine` (+52 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `CMake Build`** (2 nodes): `Examples Targets`, `QuantFinance CMake Project`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `env_summary`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `_YieldCurve Stub`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `_MarketEnvironment Stub`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `IUnderlying Interface`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What connects `env_summary`, `example_live.py — Demostración del feed de datos reales + pricing con qfpy.  Des`, `_YieldCurve Stub` to the rest of the system?**
  _57 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Equity Pricing Engines` be split into smaller, more focused modules?**
  _Cohesion score 0.06 - nodes in this community are weakly interconnected._
- **Should `Market Environment & Observers` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._
- **Should `Design Specs: Core Concepts` be split into smaller, more focused modules?**
  _Cohesion score 0.07 - nodes in this community are weakly interconnected._
- **Should `Rate & Equity Models` be split into smaller, more focused modules?**
  _Cohesion score 0.09 - nodes in this community are weakly interconnected._
- **Should `Instruments & Day Count` be split into smaller, more focused modules?**
  _Cohesion score 0.1 - nodes in this community are weakly interconnected._
- **Should `Yield Curve & Bootstrap` be split into smaller, more focused modules?**
  _Cohesion score 0.12 - nodes in this community are weakly interconnected._