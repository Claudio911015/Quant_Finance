# Graph Report - .  (2026-09-11)

## Corpus Check
- 143 files · ~60,882 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1814 nodes · 2477 edges · 312 communities (106 shown, 206 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 208 edges (avg confidence: 0.81)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 98
- Community 99
- Community 100
- Community 101
- Community 102
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107
- Community 108
- Community 109
- Community 110
- Community 111
- Community 112
- Community 113
- Community 114
- Community 115
- Community 116
- Community 117
- Community 118
- Community 119
- Community 120
- Community 121
- Community 122
- Community 123
- Community 124
- Community 125
- Community 126
- Community 127
- Community 128
- Community 129
- Community 130
- Community 131
- Community 132
- Community 133
- Community 134
- Community 135
- Community 136
- Community 137
- Community 138
- Community 139
- Community 140
- Community 141
- Community 142
- Community 143
- Community 144
- Community 145
- Community 146
- Community 147
- Community 148
- Community 149
- Community 150
- Community 151
- Community 152
- Community 153
- Community 154
- Community 155
- Community 156
- Community 157
- Community 158
- Community 159
- Community 160
- Community 161
- Community 162
- Community 163
- Community 164
- Community 165
- Community 166
- Community 167
- Community 168
- Community 169
- Community 170
- Community 171
- Community 172
- Community 173
- Community 174
- Community 175
- Community 176
- Community 177
- Community 178
- Community 179
- Community 180
- Community 181
- Community 182
- Community 183
- Community 184
- Community 185
- Community 186
- Community 187
- Community 188
- Community 189
- Community 190
- Community 191
- Community 192
- Community 193
- Community 194
- Community 195
- Community 196
- Community 197
- Community 198
- Community 199
- Community 200
- Community 201
- Community 202
- Community 203
- Community 204
- Community 205
- Community 206
- Community 207
- Community 208
- Community 209
- Community 210
- Community 211
- Community 212
- Community 213
- Community 214
- Community 215
- Community 216
- Community 217
- Community 218
- Community 219
- Community 220
- Community 221
- Community 222
- Community 223
- Community 224
- Community 225
- Community 226
- Community 227
- Community 228
- Community 229
- Community 230
- Community 231
- Community 232
- Community 233
- Community 234
- Community 235
- Community 236
- Community 237
- Community 238
- Community 239
- Community 240
- Community 241
- Community 242
- Community 243
- Community 244
- Community 245
- Community 246
- Community 247
- Community 248
- Community 249
- Community 250
- Community 251
- Community 252
- Community 253
- Community 254
- Community 255
- Community 256
- Community 257
- Community 258
- Community 259
- Community 260
- Community 261
- Community 262
- Community 263
- Community 264
- Community 265
- Community 266
- Community 267
- Community 268
- Community 269
- Community 270
- Community 271
- Community 272
- Community 273
- Community 274
- Community 275
- Community 276
- Community 277
- Community 278
- Community 279
- Community 280
- Community 281
- Community 282
- Community 283
- Community 284
- Community 285
- Community 286
- Community 287
- Community 288
- Community 289
- Community 290
- Community 291
- Community 292
- Community 293
- Community 294
- Community 295
- Community 296
- Community 297
- Community 298
- Community 299
- Community 300
- Community 301
- Community 302
- Community 303
- Community 308
- Community 309
- Community 311

## God Nodes (most connected - your core abstractions)
1. `Option` - 38 edges
2. `OptionParams` - 36 edges
3. `Instrument` - 32 edges
4. `Bond` - 28 edges
5. `CVACalculator` - 27 edges
6. `HestonParams` - 27 edges
7. `VolSurface` - 26 edges
8. `Swaption` - 26 edges
9. `ScenarioEngine` - 25 edges
10. `Swap` - 25 edges

## Surprising Connections (you probably didn't know these)
- `Engine Factory` --rationale_for--> `Copilot Instructions - Design Patterns & Workflow`  [INFERRED]
  src/pricingengines/engine_factory.cpp → .github/copilot-instructions.md
- `HestonEngine` --references--> `HestonCalibrator (P3) - Heston Calibration`  [EXTRACTED]
  include/qf/pricingengines/heston.hpp → docs/superpowers/specs/2026-07-07-heston-calibration-design.md
- `InterestRateSwap` --calls--> `Swap.InvalidParamsThrow`  [INFERRED]
  include/qf/instruments/swap.hpp → tests/test_instruments.cpp
- `Engine Factory` --references--> `Architecture Refactor - MarketEnvironment & Strategy Pattern`  [EXTRACTED]
  src/pricingengines/engine_factory.cpp → docs/superpowers/specs/2026-04-02-architecture-refactor-design.md
- `VolSurface C++ Tests` --implements--> `VolSurface (P4a) - Implied-Vol Surface`  [EXTRACTED]
  tests/test_volsurface.cpp → docs/superpowers/specs/2026-07-07-vol-surface-design.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Interest Rate Model Implementations** — src_models_hullwhite, src_models_vasicek, src_xva_cva_calculator [EXTRACTED 0.90]
- **Dual-curve IRS: separate discount and projection curves** — qf_instruments_InterestRateSwap, qf_instruments_CurveKeys, qf_termstructure_YieldCurve [EXTRACTED 0.90]
- **Bootstrap workflow: deposits and swaps -> curve calibration** — qf_termstructure_Bootstrap, qf_instruments_InterestRateSwap, qf_termstructure_YieldCurve [EXTRACTED 0.95]
- **Heston Calibration & Pricing Pipeline** — src_models_heston_calibrator, src_math_optimization, engine_blackscholes, engine_heston [EXTRACTED 0.95]
- **Equity Option Pricing Pipeline** — include_qf_models_iequity_model_iequitymodel, include_qf_pricingengines_ipricing_engine_ipricingengine, include_qf_pricingengines_engine_factory_enginefactory [EXTRACTED 0.95]
- **Instrument pricing via MarketEnvironment** — qf_instruments_Instrument, qf_core_MarketEnvironment, qf_termstructure_YieldCurve [EXTRACTED 0.95]
- **Unified Pricing Engine Interface** — engine_blackscholes, engine_montecarlo, engine_binomialtree, engine_finitedifference, engine_heston, src_pricingengines_engine_factory [EXTRACTED 1.00]
- **XVA Valuation Pipeline (CVA/DVA/FVA)** — CVACalculator, NettingSet, include_qf_models_hullwhite, FlatHazardRate, MarketEnvironment [EXTRACTED 1.00]
- **Hull-White Jamshidian Decomposition (Bisection + ZCB Options)** — src_instruments_swaption_cpp, src_instruments_capfloor_cpp, src_math_integration_cpp [INFERRED 0.80]
- **Risk Measurement System** — ScenarioEngine, include_qf_instruments_bond, Leg, MarketEnvironment [INFERRED 0.82]
- **Dual-Curve Pricing Framework** — InterestRateSwap, ScheduledSwap, CurveKeys, ScenarioEngine [INFERRED 0.85]
- **Dual-Curve Pricing (Projection vs Discount)** — src_instruments_swap_cpp, instruments_scheduled_swap, src_core_market_environment_cpp [INFERRED 0.85]
- **Heston model captures volatility smile via stochastic vol** — qf_models_HestonModel, qf_pricingengines_HestonEngine, qf_termstructure_VolSurface [INFERRED 0.85]
- **Fixed Income Rate Risk Analysis** — include_qf_models_irate_model_iratemodel, include_qf_termstructure_yieldcurve, include_qf_risk_scenario_scenarioengine [INFERRED 0.85]
- **Rate-Risk Tooling: ScenarioEngine + YieldCurve bumps to DV01 ladder + scenarios** — scenarioengine_component, yieldcurve_component, keyrate_dv01, scenario_result [INFERRED 0.85]
- **XVA Computation Pipeline: CVACalculator to CVAResult with EPE/ENE/DVA/FVA** — cvaxva_component, cvaengine_spec, netting_set, icredit_curve, cva_result [INFERRED 0.85]
- **Heston Model Calibration Workflow** — include_qf_models_heston_calibrator_hestoncalibrator, include_qf_math_optimization_neldermead, include_qf_pricingengines_heston_hestonengine [INFERRED 0.90]
- **Vol Surface Ecosystem: Heston calibration to VolSurface to MarketEnvironment integration** — hestonpx_component, volsurface_component, market_environment, implied_vol_inverter [INFERRED 0.90]
- **Web Pricing Stack (Flask → qfpy → C++ Engines)** — web_flask_app, python_web_static_js_bonds, python_web_static_js_swaps, src_instruments_bond_cpp, src_instruments_swap_cpp [INFERRED 0.90]

## Communities (312 total, 206 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (49): CVACalculator Class, CurveKeys for Dual-Curve Pricing, DayCount Convention Enum, FlatHazardRate Credit Curve, InterestRateSwap Class, Interpolator Class, Leg Class, MarketEnvironment Class (+41 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (45): shared_ptr, Instrument, calculatePV, engine_, pv, setPricingEngine, string, KeyRateDV01 (+37 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (47): Black-Scholes example: European call valuation, Bond pricing and yield curve usage, Curve bootstrapping from deposits and swaps, Finite difference schemes vs Black-Scholes, Heston calibration to listed option chain, Heston vs Black-Scholes comparison with volatility smile, Vasicek and Hull-White model demonstration, Monte Carlo pricing comparison (MC vs BS vs Binomial) (+39 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (31): core::IMarketObserver, IMarketObserver, onMarketUpdate, notify, shared_ptr, string, weak_ptr, MarketEnvironment::addCurve() (+23 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (33): CVAResult - cva, dva, fva, bcva, profile, CVA Engine Design, CVACalculator DVA/FVA Extension (P1), FlatHazardRate - ICreditCurve implementation, HestonCalibrator (P3) - Heston Calibration, ICreditCurve Interface, impliedVolatility - Brent-based inverter, Interpolator (1-D linear/cubic with flat extrapolation) (+25 more)

### Community 5 - "Community 5"
Cohesion: 0.07
Nodes (31): FromQuotesMergesFloatingPointNoisyPillars, FromQuotesRoundTrip, brent, vector, VolSurface, buildSmiles, fromQuotes, maturities_ (+23 more)

### Community 6 - "Community 6"
Cohesion: 0.08
Nodes (33): Black-Scholes Pricing Engine, HestonCalibrator Class, Heston Pricing Engine, CommodityUnderlying, code_, id, EquityUnderlying, id (+25 more)

### Community 7 - "Community 7"
Cohesion: 0.07
Nodes (25): CurveKeys - discountKey / projectionKey pair, Dual-Curve Pricing (P5), weak_ptr, addCurve, curves_, hasVolSurface, observers_, setSpot (+17 more)

### Community 8 - "Community 8"
Cohesion: 0.09
Nodes (29): CVaRGreaterOrEqualToVaR, PortfolioPosition, meanReturn, stddev, value, VaRResult, cvar, var (+21 more)

### Community 9 - "Community 9"
Cohesion: 0.08
Nodes (26): BrentRequiresBracket, BrentSquareRoot, EmptyStartThrows, GaussLegendreGaussian, GaussLegendrePolynomial, Integration, NelderMead, NewtonRaphsonSquareRoot (+18 more)

### Community 10 - "Community 10"
Cohesion: 0.09
Nodes (17): AmortizingFloatingDualEqualsReplicationWhenDataEqual, DayCountConvention, string_view, Leg, calculatePV, currency_, dcc_, floating_ (+9 more)

### Community 11 - "Community 11"
Cohesion: 0.11
Nodes (17): CurveKeys, discountKey, projectionKey, string, vector, PeriodSpec, accrualFrac, notional (+9 more)

### Community 12 - "Community 12"
Cohesion: 0.10
Nodes (16): YieldCurve, vector, bumped, discountFactor, forwardRate, interp_, maturities_, method_ (+8 more)

### Community 13 - "Community 13"
Cohesion: 0.11
Nodes (17): shared_ptr, Option, calculatePV, dividendYield, exercise, riskFreeRate, spot, strike (+9 more)

### Community 14 - "Community 14"
Cohesion: 0.13
Nodes (20): fetch_treasury_curve_fred(), fetch_treasury_curve_yfinance(), Descarga la curva del Tesoro US desde FRED (Federal Reserve Bank of St. Louis).…, Obtiene el último precio de cierre usando yfinance 1.x (MultiIndex DataFrame)., Descarga yields del Tesoro US vía Yahoo Finance y construye una YieldCurve.…, _yf_last_close(), _make_fred_response(), _make_yf_df() (+12 more)

### Community 15 - "Community 15"
Cohesion: 0.14
Nodes (16): AmericanPutAboveEuropean, BinomialTree, BumpAndReprice, Heston, InvalidParametersThrows, MonteCarlo, PricingEngines, m (+8 more)

### Community 16 - "Community 16"
Cohesion: 0.11
Nodes (16): BilateralConfigValidation, DeepOTMPayerSwapPositiveDVA, FundingSpreadDrivesPositiveFVA, CVACalculator, fundingSpread_, lgd_, ownCredit_, ownLgd_ (+8 more)

### Community 17 - "Community 17"
Cohesion: 0.18
Nodes (16): fetchConvergence(), fetchGreeksSurface(), fetchPayoff(), getFormPayload(), plotlyConfig, plotlyLayout, renderConvergenceChart(), renderGreeksChart() (+8 more)

### Community 19 - "Community 19"
Cohesion: 0.14
Nodes (14): AmortizingFloating, CashFlowsInvariantUnderOisBumpChangeUnderProjectionBump, makeFixed, makeFloating, ScheduledSwap, cashFlows, npv, payLeg_ (+6 more)

### Community 20 - "Community 20"
Cohesion: 0.12
Nodes (17): CVAResult, bcva, cva, dva, fva, profile, vector, TimeStep (+9 more)

### Community 21 - "Community 21"
Cohesion: 0.15
Nodes (16): Binomial Tree Pricing Engine, Black-Scholes Pricing Engine, Finite Difference Pricing Engine, Heston Pricing Engine, Monte Carlo Pricing Engine, Copilot Instructions - Design Patterns & Workflow, makeEquityEngine, makeHestonEngine (+8 more)

### Community 22 - "Community 22"
Cohesion: 0.19
Nodes (15): pair_, size_t, string, discountAnnuity(), InterestRateSwap::annuity(), InterestRateSwap::npv(), InterestRateSwap::parRate(), Leg::calculatePV() (+7 more)

### Community 23 - "Community 23"
Cohesion: 0.16
Nodes (15): vector, OptimResult, converged, fmin, iterations, x, ShiftedQuadraticMinimum, Nelder-Mead Optimizer (+7 more)

### Community 24 - "Community 24"
Cohesion: 0.16
Nodes (15): fetch_equity(), Devuelve (spot, atm_iv) para el ticker dado. La vol implícita ATM se estima…, Descarga datos y devuelve el MarketEnvironment. Args: verbose: Si True, imprime…, _make_ticker_mock(), Crea un mock de yf.Ticker con spot y opciones configurables., Si no hay opciones disponibles, usa HV30 como vol., Si el hist para HV30 está vacío, RuntimeError claro., Si el hist tiene solo 1 fila, no se puede calcular retorno — RuntimeError. (+7 more)

### Community 25 - "Community 25"
Cohesion: 0.12
Nodes (7): MarketEnvironmentBuilder, Construye un qfpy.MarketEnvironment listo para usar con los pricing engines.…, Builder con curva plana y spots manuales — cero llamadas a red., test_builder_add_equity_calls_fetch(), test_builder_flat_curve_no_network(), test_builder_flat_curve_rate_is_correct(), test_builder_manual_spot_overrides_fetched()

### Community 26 - "Community 26"
Cohesion: 0.14
Nodes (12): BSModelInvalidSigmaThrows, HullWhiteIsIRateModel, BlackScholesModel, q_, r_, sigma_, simulate, IEquityModel (+4 more)

### Community 27 - "Community 27"
Cohesion: 0.15
Nodes (14): CapFloorDCCDefaultIsACT365, CapFloorParityFlatCurve, CapFloorParitySlopedCurve, price, annuity(), flatCurve(), irsNPV(), slopedCurve() (+6 more)

### Community 28 - "Community 28"
Cohesion: 0.13
Nodes (14): EmptySetNetValueIsZero, Entry, vector, NettingSet, add, entries_, netValue, size (+6 more)

### Community 29 - "Community 29"
Cohesion: 0.20
Nodes (7): DayCountConvention, Swaption, dcc_, hw_a_, hw_sigma_, Integration Methods, Swaption.AccessorsReturnConstructedValues

### Community 30 - "Community 30"
Cohesion: 0.24
Nodes (14): api_bond(), api_greeks_surface(), api_implied_vol(), api_model_convergence(), api_payoff(), api_price(), api_price_heston(), api_swap() (+6 more)

### Community 31 - "Community 31"
Cohesion: 0.18
Nodes (10): Architecture Refactor - MarketEnvironment & Strategy Pattern, CLAUDE.md - Build, Test, Architecture, IEquityModel Interface, vector, HestonModel, params_, q_, r_ (+2 more)

### Community 32 - "Community 32"
Cohesion: 0.14
Nodes (14): ConvergesToBSWhenVolOfVolNearZero, HestonParams, kappa, rho, sigma, theta, v0, kappa (+6 more)

### Community 33 - "Community 33"
Cohesion: 0.15
Nodes (13): AnnuityPositive, DefaultKeysReplicateReplicationIdentity, InterestRateSwap, annuity, frequency_, keys_, type_, InstrumentPvEqualsEconomicNpv_Payer (+5 more)

### Community 34 - "Community 34"
Cohesion: 0.17
Nodes (9): Bootstrap, Swap, payLeg_, receiveLeg_, LegAndSwapPV, SwapLegType, Swap.LegAndSwapPV, Bootstrap.UnsortedInstrumentsThrows (+1 more)

### Community 35 - "Community 35"
Cohesion: 0.17
Nodes (12): Bond, calculatePV, couponRate_, dcc_, faceValue_, frequency_, periods_, DayCountConvention (+4 more)

### Community 36 - "Community 36"
Cohesion: 0.22
Nodes (7): CapFloor, dcc_, hw_a_, hw_sigma_, DayCountConvention, CapFloor.AccessorsReturnConstructedValues, AccessorsReturnConstructedValues

### Community 37 - "Community 37"
Cohesion: 0.17
Nodes (12): shared_ptr, string, MonteCarloEngine, model_, N_, nSteps_, params_, price (+4 more)

### Community 38 - "Community 38"
Cohesion: 0.17
Nodes (12): FlatHazardRate, lambda_, survivalProbability, ICreditCurve Interface, ICreditCurve, survivalProbability, NegativeTimeThrows, CVACalculator::CVACalculator() (+4 more)

### Community 39 - "Community 39"
Cohesion: 0.24
Nodes (4): _curve(), DualCurveBindings, skipUnless, Python-side tests for the dual-curve swap bindings (P5c). Verifies capabilities…

### Community 40 - "Community 40"
Cohesion: 0.24
Nodes (11): CalibrationObjective, nelderMead, HestonCalibrator, q_, r_, spot_, vector, fromUnconstrained() (+3 more)

### Community 41 - "Community 41"
Cohesion: 0.21
Nodes (11): complex, IsIPricingEngine, MonteCarloApproachesAnalytical, charFunc(), string, HestonEngine::HestonEngine(), HestonEngine::price(), hestonMonteCarlo() (+3 more)

### Community 42 - "Community 42"
Cohesion: 0.17
Nodes (11): DualParRateZeroesDualNpvForFractionalMaturity, main(), npv, parRate, KeyEqualMatchesSingleCurveToMachinePrecision, ParRateGivesZeroNPV, NettingSet::netValue(), DualCurve.DualParRateZeroesDualNpvForFractionalMaturity (+3 more)

### Community 43 - "Community 43"
Cohesion: 0.20
Nodes (11): ExactlyMatchesMarketCurve, main(), HullWhite, a_, bondPrice, curve_, sigma_, simulate (+3 more)

### Community 44 - "Community 44"
Cohesion: 0.20
Nodes (8): example_live.py — Demostración del feed de datos reales + pricing con qfpy.…, fetch_equity, fetch_treasury_curve_fred, fetch_treasury_curve_yfinance, env_summary(), market_feed.py — Feeds de datos reales hacia qf::core::MarketEnvironment.…, Imprime un resumen tabular del MarketEnvironment., qfpy

### Community 45 - "Community 45"
Cohesion: 0.21
Nodes (11): ExplicitImplicitCrankConverge, FiniteDifference, string, vector, FDMEngine::FDMEngine(), FDMEngine::price(), finiteDifferenceBSPrice(), optionIntrinsic() (+3 more)

### Community 46 - "Community 46"
Cohesion: 0.17
Nodes (11): HullWhite - IRateModel implementation, IRateModel, bondPrice, conditionalBondPrice, simulate, zeroRate, Vasicek Rate Model, IRateModel Interface (+3 more)

### Community 47 - "Community 47"
Cohesion: 0.27
Nodes (11): cashflows, maturities, Bond::Bond(), Bond::cashflows(), Bond::convexity(), Bond::duration(), Bond::maturities(), Bond::price() (+3 more)

### Community 48 - "Community 48"
Cohesion: 0.17
Nodes (12): OptionParams, dividendYield, exercise, maturity, riskFreeRate, spot, strike, type (+4 more)

### Community 49 - "Community 49"
Cohesion: 0.17
Nodes (12): B, Vasicek, a_, r0_, sigma_, simulate, zeroRate, SimulatePathLength (+4 more)

### Community 50 - "Community 50"
Cohesion: 0.35
Nodes (9): formatCurrency(), getCurve(), hideSwError(), priceRegular(), priceScheduled(), setLoading(), setMode(), showResults() (+1 more)

### Community 51 - "Community 51"
Cohesion: 0.20
Nodes (4): BlackScholes, main(), monteCarloBSPrice(), BlackScholes.InvalidParamsThrow

### Community 52 - "Community 52"
Cohesion: 0.22
Nodes (10): CallPriceNonNegative, ImpliedVolRoundTrip, blackScholes(), BlackScholesEngine::BlackScholesEngine(), BlackScholesEngine::price(), string, impliedVolatility(), makeCall() (+2 more)

### Community 53 - "Community 53"
Cohesion: 0.18
Nodes (10): ConditionalBondPriceInvalidThrows, compute, vector, flatCurve(), quarterlyDates(), CVACalculator.UnsortedDatesThrows, CVACalculator.ZeroLGDGivesZeroCVA, Vasicek.ConditionalBondPriceInvalidThrows (+2 more)

### Community 54 - "Community 54"
Cohesion: 0.18
Nodes (6): DoesNotNotifyLiveObservers, bootstrap, Interpolation, vector, Interpolator::Interpolator(), ScenarioEngine.DoesNotNotifyLiveObservers

### Community 55 - "Community 55"
Cohesion: 0.20
Nodes (10): EnvAwareMissingSpotThrows, HestonEngine, heston_, opt_, price, ticker_, string, HestonParams (pricingengines) (+2 more)

### Community 56 - "Community 56"
Cohesion: 0.20
Nodes (10): EnvAwareMissingTickerThrows, FDMEngine, method_, nS_, nT_, params_, price, ticker_ (+2 more)

### Community 57 - "Community 57"
Cohesion: 0.27
Nodes (3): skipUnless, Python-side smoke tests for the qf::risk ScenarioEngine bindings (P2c). Imports…, ScenarioEngineBindings

### Community 58 - "Community 58"
Cohesion: 0.20
Nodes (3): skipUnless, Python-side tests for the VolSurface bindings (P4c). Imports the *real* built…, VolSurfaceBindings

### Community 59 - "Community 59"
Cohesion: 0.22
Nodes (9): ATMPayerEqualsReceiver, PayerReceiverParityFlatCurve, PayerReceiverParitySlopedCurve, annuity(), irsNPV(), slopedCurve(), Swaption.ATMPayerEqualsReceiver, Swaption.PayerReceiverParityFlatCurve (+1 more)

### Community 60 - "Community 60"
Cohesion: 0.31
Nodes (5): string, normCDF, normPDF, blackScholes, IPricingEngine Interface

### Community 61 - "Community 61"
Cohesion: 0.31
Nodes (8): DayCountConvention, SwaptionType, hwB(), hwSigmaP(), hwVariance(), hwZCBOption(), Swaption::price(), Swaption::Swaption()

### Community 62 - "Community 62"
Cohesion: 0.20
Nodes (8): vector, Interpolator, method_, spline_M_, x_, y_, InvalidInputThrows, Interpolation.InvalidInputThrows

### Community 63 - "Community 63"
Cohesion: 0.33
Nodes (7): calcBond(), fetchYieldCurve(), getCurveData(), hideError(), renderYieldCurve(), setLoading(), showError()

### Community 64 - "Community 64"
Cohesion: 0.31
Nodes (10): vector, HullWhite::simulate(), Greeks Calculator, function, delta(), dv01(), gamma(), rho() (+2 more)

### Community 65 - "Community 65"
Cohesion: 0.33
Nodes (3): HestonCalibrationBindings, skipUnless, Python-side round-trip test for the Heston calibration bindings (P3c). Imports…

### Community 66 - "Community 66"
Cohesion: 0.22
Nodes (8): BondACT360CouponLargerThanACT365, CashFlowsLength, price, ParPriceWhenCouponEqualsYield, DayCount.BondACT360CouponLargerThanACT365, flatCurve(), Bond.ParPriceWhenCouponEqualsYield, ScheduledSwap.CashFlowsLength

### Community 67 - "Community 67"
Cohesion: 0.22
Nodes (9): BondParallelDV01MatchesDurationTimesPrice, DurationPositive, duration, parallelDV01, InterestRateSwapFlowsThroughScenarioEngine, DualCurve.InterestRateSwapFlowsThroughScenarioEngine, Bond.DurationPositive, linearCurve() (+1 more)

### Community 68 - "Community 68"
Cohesion: 0.22
Nodes (8): BumpedRejectsBadPillarIndex, FlatCurveZeroRate, flatCurve(), slopedCurve(), YieldCurve.BumpedRejectsBadPillarIndex, YieldCurve.FlatCurveZeroRate, YieldCurve.ZeroRateAtKnots, ZeroRateAtKnots

### Community 69 - "Community 69"
Cohesion: 0.22
Nodes (9): DepositsRecoverZeroRates, BootstrapInstrument, frequency, maturity, rate, type, bootstrap(), vector (+1 more)

### Community 70 - "Community 70"
Cohesion: 0.22
Nodes (8): HestonCalibration, calibrate, SingleQuoteRunsAndSizesErrors, SyntheticRoundTripRecoversParams, vector, makeSyntheticQuotes(), HestonCalibration.SingleQuoteRunsAndSizesErrors, HestonCalibration.SyntheticRoundTripRecoversParams

### Community 71 - "Community 71"
Cohesion: 0.28
Nodes (7): IPricingEngine, name, price, shared_ptr, string, EngineFactory::makeEquityEngine(), EngineFactory::makeHestonEngine()

### Community 72 - "Community 72"
Cohesion: 0.25
Nodes (8): BlackScholesEngine, params_, price, ticker_, string, LegacyConstructorStillIgnoresEnv, resolveEquityParams, BlackScholesEngine.LegacyConstructorStillIgnoresEnv

### Community 73 - "Community 73"
Cohesion: 0.29
Nodes (7): ConvergesToBlackScholes, binomialTreeBSPrice(), BinomialTreeEngine::BinomialTreeEngine(), BinomialTreeEngine::price(), string, BinomialTreeEngine.IsIPricingEngine, BinomialTree.ConvergesToBlackScholes

### Community 74 - "Community 74"
Cohesion: 0.25
Nodes (7): ConvexityPositive, main(), convexity, yield, Bond.ConvexityPositive, Bond.YTMRoundTrip, YTMRoundTrip

### Community 75 - "Community 75"
Cohesion: 0.32
Nodes (6): CapFloor::CapFloor(), CapFloor::price(), CapFloorType, DayCountConvention, hwBondOption(), normCDF()

### Community 76 - "Community 76"
Cohesion: 0.29
Nodes (7): BinomialTreeEngine, nSteps_, params_, price, ticker_, string, BinomialTreeEngine.EnvAwareMissingTickerThrows

### Community 77 - "Community 77"
Cohesion: 0.29
Nodes (7): size_t, vector, SimParams, monitorDates, nPaths, seed, optional

### Community 78 - "Community 78"
Cohesion: 0.29
Nodes (6): AddCurveNotifiesObserver, MarketObserver, flatCurve(), MarketObserver.AddCurveNotifiesObserver, MarketObserver.UnsubscribeIndividual, UnsubscribeIndividual

### Community 79 - "Community 79"
Cohesion: 0.38
Nodes (6): DualCurve, MissingProjectionKeyThrows, makeEnv(), oisCurve(), projCurve(), DualCurve.MissingProjectionKeyThrows

### Community 80 - "Community 80"
Cohesion: 0.29
Nodes (7): CalibrationResult, converged, iterations, params, perQuoteErrors, rmse, vector

### Community 81 - "Community 81"
Cohesion: 0.29
Nodes (7): BSResult, delta, gamma, price, rho, theta, vega

### Community 82 - "Community 82"
Cohesion: 0.29
Nodes (7): NumericalGreeks, CapFloor.InvalidParamsThrow, InvalidParamsThrow, Swap.InvalidParamsThrow, HullWhite.InvalidParamsThrow, NumericalGreeks.InvalidParamsThrow, Swaption.InvalidParamsThrow

### Community 84 - "Community 84"
Cohesion: 0.29
Nodes (3): Vasicek Rate Model, vector, Vasicek::simulate()

### Community 85 - "Community 85"
Cohesion: 0.33
Nodes (6): price, PayerPriceNonNegative, SwaptionPayerACT360LowerReceiverHigher, DayCount.SwaptionPayerACT360LowerReceiverHigher, flatCurve(), Swaption.PayerPriceNonNegative

### Community 86 - "Community 86"
Cohesion: 0.33
Nodes (5): OptionQuote, marketPrice, maturity, strike, type

### Community 87 - "Community 87"
Cohesion: 0.40
Nodes (5): shared_ptr, string, monteCarloBSPrice(), MonteCarloEngine::MonteCarloEngine(), MonteCarloEngine::price()

### Community 88 - "Community 88"
Cohesion: 0.50
Nodes (4): DeltaMatchesBS, atmCall(), bsPrice(), NumericalGreeks.DeltaMatchesBS

### Community 89 - "Community 89"
Cohesion: 0.40
Nodes (4): HullWhiteConditionalBondPrice, InvalidArgThrowsWhenTNotGreaterThan_t, HullWhiteConditionalBondPrice.InvalidArgThrowsWhenTNotGreaterThan_t, testCurve()

### Community 90 - "Community 90"
Cohesion: 0.40
Nodes (5): calculatePV, calculatePV, CapFloor.CalculatePVMatchesPrice, CalculatePVMatchesPrice, Swaption.CalculatePVMatchesPrice

### Community 91 - "Community 91"
Cohesion: 0.67
Nodes (3): string, resolveEquityParams(), resolveSpotAndRate()

### Community 92 - "Community 92"
Cohesion: 0.50
Nodes (4): KeyRateDV01 - per-pillar ladder rung, ScenarioResult - label, basePV, scenarioPV, pnl, ScenarioEngine (P2) - Curve Rate-Risk Tooling, YieldCurve with pillar access (P2a)

### Community 93 - "Community 93"
Cohesion: 0.50
Nodes (3): pricingengines::IPricingEngine, string, PyIPricingEngine

### Community 94 - "Community 94"
Cohesion: 0.50
Nodes (3): shared_ptr, Option::calculatePV(), Option::Option()

### Community 96 - "Community 96"
Cohesion: 0.50
Nodes (3): vector, HestonModel::HestonModel(), HestonModel::simulate()

### Community 97 - "Community 97"
Cohesion: 0.67
Nodes (3): AtT0MatchesInitialCurve, conditionalBondPrice, HullWhiteConditionalBondPrice.AtT0MatchesInitialCurve

### Community 98 - "Community 98"
Cohesion: 0.67
Nodes (3): BondPricePositiveAndLessThanOne, bondPrice, Vasicek.BondPricePositiveAndLessThanOne

### Community 99 - "Community 99"
Cohesion: 0.67
Nodes (3): ConditionalBondPricePositive, conditionalBondPrice, Vasicek.ConditionalBondPricePositive

### Community 100 - "Community 100"
Cohesion: 0.67
Nodes (3): EnvAwareMatchesParamsBased, atmEnv(), BlackScholesEngine.EnvAwareMatchesParamsBased

### Community 101 - "Community 101"
Cohesion: 0.67
Nodes (3): PortfolioVaR.CVaRGreaterThanVaR, CVaRGreaterThanVaR, ParametricVaR.CVaRGreaterThanVaR

### Community 102 - "Community 102"
Cohesion: 0.67
Nodes (3): BlackScholes.GammaPositive, GammaPositive, NumericalGreeks.GammaPositive

### Community 103 - "Community 103"
Cohesion: 0.67
Nodes (3): BlackScholes.VegaPositive, VegaPositive, NumericalGreeks.VegaPositive

## Knowledge Gaps
- **470 isolated node(s):** `FDMethod`, `calculatePV`, `engine_`, `setPricingEngine`, `dv01` (+465 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **206 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CVACalculator` connect `Community 16` to `Community 38`, `Community 7`, `Community 12`, `Community 77`, `Community 46`, `Community 83`, `Community 20`, `Community 53`, `Community 54`, `Community 28`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Why does `Instrument` connect `Community 1` to `Community 0`, `Community 34`, `Community 35`, `Community 36`, `Community 6`, `Community 71`, `Community 10`, `Community 11`, `Community 13`, `Community 15`, `Community 19`, `Community 29`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Why does `OptionParams` connect `Community 48` to `Community 37`, `Community 6`, `Community 71`, `Community 72`, `Community 40`, `Community 73`, `Community 41`, `Community 76`, `Community 45`, `Community 88`, `Community 15`, `Community 51`, `Community 52`, `Community 87`, `Community 55`, `Community 56`, `Community 91`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `MarketEnvironment` (e.g. with `MarketEnvironmentBuilder` and `market_feed.py`) actually correct?**
  _`MarketEnvironment` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `FDMethod`, `calculatePV`, `engine_` to the rest of the system?**
  _470 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.0611764705882353 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.06196078431372549 - nodes in this community are weakly interconnected._