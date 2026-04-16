# Graph Report - .  (2026-04-15)

## Corpus Check
- 104 files · ~35,308 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 300 nodes · 524 edges · 17 communities detected
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `AppTestCase` - 19 edges
2. `price()` - 7 edges
3. `calcBond()` - 6 edges
4. `cashflows()` - 5 edges
5. `maturities()` - 5 edges
6. `price()` - 5 edges
7. `price()` - 5 edges
8. `TEST()` - 5 edges
9. `yield()` - 4 edges
10. `duration()` - 4 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Communities

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (24): binomialTreeBSPrice(), price(), blackScholes(), impliedVolatility(), price(), EngineFactory, finiteDifferenceBSPrice(), optionIntrinsic() (+16 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (19): annuity(), discountAnnuity(), Leg, npv(), Swap, flatCurve(), swapCurve(), TEST() (+11 more)

### Community 2 - "Community 2"
Cohesion: 0.11
Nodes (7): identityCorr(), TEST(), atmCall(), bsPrice(), TEST(), parametricVaR(), portfolioVaR()

### Community 3 - "Community 3"
Cohesion: 0.12
Nodes (5): AppTestCase, ExerciseType, FDMethod, InterpolationMethod, OptionType

### Community 4 - "Community 4"
Cohesion: 0.11
Nodes (12): IMarketObserver, MarketEnvironment, addCurve(), MarketEnvironment(), notify(), setSpot(), setVolatility(), flatCurve() (+4 more)

### Community 5 - "Community 5"
Cohesion: 0.14
Nodes (10): A(), B(), simulate(), theta(), zeroRate(), IRateModel, TEST(), testCurve() (+2 more)

### Community 6 - "Community 6"
Cohesion: 0.19
Nodes (7): IEquityModel, TEST(), testCurve(), atm(), atmEnv(), emptyEnv(), TEST()

### Community 7 - "Community 7"
Cohesion: 0.22
Nodes (8): Instrument, IPricingEngine, calculatePV(), hwB(), hwSigmaP(), hwVariance(), hwZCBOption(), price()

### Community 8 - "Community 8"
Cohesion: 0.31
Nodes (8): calculatePV(), hwBondOption(), price(), annuity(), flatCurve(), irsNPV(), slopedCurve(), TEST()

### Community 9 - "Community 9"
Cohesion: 0.4
Nodes (7): calculatePV(), cashflows(), convexity(), duration(), maturities(), price(), yield()

### Community 10 - "Community 10"
Cohesion: 0.33
Nodes (7): calcBond(), fetchYieldCurve(), getCurveData(), hideError(), renderYieldCurve(), setLoading(), showError()

### Community 11 - "Community 11"
Cohesion: 0.31
Nodes (2): gaussLegendre(), glNodesWeights()

### Community 12 - "Community 12"
Cohesion: 0.42
Nodes (7): fetchHeston(), hideError(), price(), row(), setLoading(), showError(), validate()

### Community 13 - "Community 13"
Cohesion: 0.29
Nodes (1): IUnderlying

### Community 14 - "Community 14"
Cohesion: 0.46
Nodes (7): fetchConvergence(), fetchGreeksSurface(), fetchPayoff(), getFormPayload(), renderConvergenceChart(), renderGreeksChart(), renderPayoffChart()

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (0): 

### Community 16 - "Community 16"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **9 isolated node(s):** `IPricingEngine`, `MarketEnvironment`, `EngineFactory`, `PyIPricingEngine`, `CountingObserver` (+4 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 15`** (2 nodes): `CMakeCXXCompilerId.cpp`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (1 nodes): `compiler_depend.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What connects `IPricingEngine`, `MarketEnvironment`, `EngineFactory` to the rest of the system?**
  _9 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.06 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.11 - nodes in this community are weakly interconnected._
- **Should `Community 3` be split into smaller, more focused modules?**
  _Cohesion score 0.12 - nodes in this community are weakly interconnected._
- **Should `Community 4` be split into smaller, more focused modules?**
  _Cohesion score 0.11 - nodes in this community are weakly interconnected._
- **Should `Community 5` be split into smaller, more focused modules?**
  _Cohesion score 0.14 - nodes in this community are weakly interconnected._