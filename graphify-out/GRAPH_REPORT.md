# Graph Report - Quant_Finance  (2026-11-11)

## Corpus Check
- 263 files · ~357,968 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 7669 nodes · 17287 edges · 544 communities (251 shown, 293 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 582 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- rates.py
- MarketEnvironment
- PortfolioScreen.tsx
- Swaption
- YieldCurve
- Swap
- Yield curve with discount factors and forward rates
- test_finite_guard.py
- test_errors.py
- VolSurface
- ApiError
- QF Desk: backend Flask+SQLite en desk/api y UI React+TS+Vite en desk/ui sobre qfpy
- vitest
- MarketScreen.tsx
- Bond
- get_conn
- RiskScreen.tsx
- IUnderlying
- HestonParams
- sqlite3
- OptionParams
- ApiError
- api/types.ts
- TEST
- pytest
- qfpy.cpp
- Option
- VaRResult
- PricerForm.tsx
- HestonModel
- portfolio.py
- DeskBindings
- test_fred.py
- register_error_handlers
- test_refresh.py
- Tabla trade_events (solo insercion, tipo, fecha, datos, evento previo)
- test_risk_dv01_scenarios.py
- PnlExplainTab.test.tsx
- IPricingEngine
- HedgeScreen.tsx
- api/market.py
- test_live_market.py
- test_ops_fpml.py
- fmtNumber
- opsClient.ts
- live_market.py
- test_price_fx.py
- test_calendars.py
- test_market.py
- test_risk_var.py
- test_market_feed.py
- TEST
- market_environment.cpp
- CVACalculator
- json
- MethodologyScreen.tsx
- common.py
- charts.js
- AppTestCase
- test_credit.py
- Vasicek
- test_hedges_periods.py
- Corte 1: workstation nucleo (hecho y auditado)
- TEST
- test_market_csa.py
- ois_swap.cpp
- TEST
- DV01 (sensibilidad de precio a 1 pb)
- Tabla trades (identidad, terminos, fecha de pacto, inicio y vencimiento)
- Instrument
- MarketEnvironmentBuilder
- test_banxico.py
- compilerOptions
- Instrumento XccySwap (nocional constante primero)
- bond.cpp
- OptimResult
- cmath
- _roll
- TEST
- ApiError
- daycount.cpp
- test_portfolio.py
- test_scenario_sets.py
- test_xccy_product.py
- FxOption
- python_web/app.py
- now_iso
- designate
- TEST
- R2 Pricers: POST /api/price/<producto>
- fetch_equity
- CVA Engine Design
- QF Desk: workstation de valuacion de derivados
- R8 Pricers UI: formulario por producto con resultado y grafica
- test_events_api.py
- test_fixings_fetch.py
- test_backup.py
- test_fixings.py
- DualCurveBindings
- create_app
- R11 Metodologia: pagina por producto con modelo, convenciones y limites
- Snapshot sembrado MX-DEMO
- test_ops_settlements.py
- test_ops_recon.py
- TEST
- .price
- swaps.js
- test_counterparties.py
- test_ops_schema.py
- Lista de dependencias permitidas
- Fecha de valuacion: descuenta solo futuros, compone fijaciones del periodo en curso
- Corte 2: la operacion con vida y el mercado con historia
- VolSurface (P4a) - Implied-Vol Surface
- stdexcept
- ScenarioEngineBindings
- VolSurfaceBindings
- RootFinding
- iso_date
- Corte 5 R1: calendario de flujos por fecha, contraparte y moneda con exportacion
- Corte 3 tarea cero: fijar convenciones (base de dias, rezagos, calendario, TIIE a plazo)
- Despliegue con contenedores, respaldos, licencia y terminos de uso
- Skill fableorchestrate (corridas por corte: Fable, Opus, Sonnet, Haiku)
- test_factor_history.py
- capfloor.cpp
- test_hedges_dedesignation.py
- QF Desk Corte 7 - diseno (validacion contra QuantLib)
- settled_flows
- bonds.js
- Greeks Calculator
- HestonCalibrationBindings
- test_collateral_valuation.py
- connect
- desk/api: backend
- CRUD /api/trades persistido en SQLite; sobrevive reinicios
- Tasa cero y tasa forward
- Decision: QuantLib en Python como referencia principal de validacion
- qfpy
- export_cases.py
- test_hedges_release.py
- par_irs
- test_integration_cortes.py
- MarketContext
- compare.py
- test_validation_report.py
- state
- test_limits.py
- Auditoria independiente QF Desk corte 7 (validacion contra QuantLib)
- fetch_treasury_curve_fred
- Vasicek Rate Model
- xva_bindings.cpp
- test_xva.py
- choice
- test_skeleton.py
- settled
- bs_model.cpp
- test_hist_var.py
- TEST
- CVaRGreaterThanVaR
- GammaPositive
- VegaPositive
- Amortizing
- AnalyticalBondPriceKnownValue
- ATMCallApproachesBlackScholes
- ATMCallKnownValue
- ATMPutKnownValue
- BondACT360CouponRatio
- BondACT365DefaultIsUnchanged
- BondPriceDecreasing
- BondPriceDecreasingInMaturity
- BrentSine
- BrokenFirstPeriod
- BSModelDrivenMatchesLegacy
- BSModelIsIEquityModel
- CallDeltaBetweenZeroAndOne
- CallPriceAboveIntrinsicValue
- CallPricePositive
- CallPutSameGammaAndVega
- CallRhoPositive
- CallThetaNegative
- CapFloorACT360CapFloorParity
- CapFloorACT360CapLowerFloorHigher
- CommodityUnderlyingId
- ConsistentWithParametric
- CubicSplineExactAtKnots
- CubicSplineSmoothBetweenKnots
- CubicSplineThreePointsWorks
- CubicSplineTwoPointsIsLinear
- CubicSplineWithTwoStrikesIsLinear
- DeepITMCallApproachesForwardPrice
- DeepITMReceiverSwapPositiveCVA
- DeepOTMCallNearZero
- DefaultCurveAccessibleByName
- DefaultCurveRoundTrip
- DeltaPutBetweenMinusOneAndZero
- test_trades_dates.py
- run.sh
- DiscountFactorDecreasingInMaturity
- DiscountFactorLessThanOne
- DiscountFactorsPositive
- DiscountWhenCouponBelowYield
- DiversificationReducesVaR
- Formato: montos con separador de miles y moneda, tasas en % con 4 decimales, fechas ISO
- DualParRateExceedsSingleWhenProjectionAboveOis
- DualParRateReducesToSingleWhenKeysEqual
- DuplicateSubscribeNotifiesOnce
- DurationLessThanMaturity
- Dv01KnownValue
- Dv01PositiveForBond
- DVAOfPayerMatchesCVAOfReceiver
- EmptyInstrumentsThrows
- EmptyPositionsThrows
- EmptyQuotesThrows
- EnvAwareEngineReadsMktData
- EnvAwareReadsDifferentSpot
- EnvAwareReadsDifferentVol
- EquityUnderlyingId
- Value-at-Risk computation (three methodologies)
- ExpiredObserverDoesNotCrash
- FixedLegDV01MatchesAnalyticDerivative
- FlatCurveDiscountFactor
- FlatCurveForwardRateEqualsSpot
- FlatFallbackThrowsWhenMissing
- FlatFallbackWhenNoSurface
- FlatInputGivesFlatCurve
- FlatStrikeExtrapolation
- ForwardRateConsistencyWithDiscountFactors
- ForwardRateInvalidOrderThrows
- FromQuotesRejectsIncompleteGrid
- FxUnderlyingId
- GammaMatchesBS
- GaussLegendreSine
- generate_docs.sh
- HestonModelDrivenAgreesWithHestonEngine
- HestonModelDrivenGivesPositivePrice
- HestonModelIsIEquityModel
- HigherRateLowerPrice
- HigherVolOfVolWidensSmile
- HistoricalVaR
- ImpliedVolITMPut
- ImpliedVolObjectiveRoundTrip
- ImpliedVolOTMCall
- InstrumentPvEqualsEconomicNpv_Receiver
- InterpolatesBetweenPillars
- InvalidNotionalThrows
- InvalidPeriodsThrows
- KeyEqualMatchesSingleCurveForFractionalMaturities
- KnownValue95
- LegEnumConstructor
- LegStringConstructorACT360
- LegUnknownStringThrows
- LinearClampsAboveUpperBound
- LinearClampsBelowLowerBound
- LinearExactAtKnots
- LinearMidpoint
- LogLinearExactAtKnots
- LongerBondHasHigherDuration
- LongerSwapHasLargerAnnuity
- MakesBinomialTreeEngine
- MakesFDMEngine
- MakesMonteCarloEngine
- MaturityExtrapolationIsFlatInVol
- MissingSpotThrows
- MonotonicallyDecreasingDiscountFactors
- MonteCarloVaR
- MultipleObserversAllNotified
- NegativeLambdaThrows
- NegativeSpotThrows
- NegativeVolThrows
- NettingReducesExposureToNearZero
- NewConstructorPricingViaEngine
- NewtonRaphsonCubic
- NonPositiveDateThrows
- NoOwnCreditGivesZeroDVAAndBCVAEqualsCVA
- NPVScalesWithNotional
- NPVZeroAtParRate
- OverwriteCurve
- OverwriteSpotAndVol
- ParallelBumpShiftsZeroRateUniformly
- ParametricVaR
- ParRateOnFlatCurve
- Parse30360
- ParseACT365
- ParseACTACT
- ParseUnknownThrows
- PayerNegativeWhenFixedAbovePar
- PayerPositiveWhenFixedBelowPar
- PayerReceiverNetToZero
- PayerReceiverSymmetry
- PerfectNegativeCorrelationReducesVaR
- PerfectPositiveCorrelation
- PeriodFraction30360EqualsACT365
- PeriodFractionACT360IsLargerThanACT365
- PeriodFractionACTACTEqualsACT365
- PillarRoundTrip
- PolymorphicEquityDispatch
- PolymorphicFx
- PolymorphicId
- PositiveAndLessThanOne
- PositiveBasisRaisesPayerNpv
- PositiveMeanReducesVaR
- PremiumWhenCouponAboveYield
- PriceDecreaseAsYieldIncrease
- PutCallDeltaParity
- PutCallParity
- PutCallParityAcrossEngines
- PutConvergesToBlackScholes
- PutDeltaBetweenMinusOneAndZero
- PutPricePositive
- PutRhoNegative
- RateUnderlyingId
- RejectsBadDimensions
- RejectsCalendarArbitrage
- RejectsNonPositiveVol
- RepricesQuotesWithinTolerance
- RhoMatchesBS
- RosenbrockRecovery
- RunScenarioRejectsSizeMismatch
- ScheduledSwapFlowsThroughScenarioEngine
- SetSpotNotifiesObserver
- SetVolatilityNotifiesObserver
- ShortEndAnchorReturnsFirstPillarVol
- SimpsonExponential
- SimpsonInvalidN
- SimpsonSine
- SimulatePathMeanReverts
- SinglePillarBumpIsLocalUnderLinear
- SpotAndVolRoundTrip
- StarvedIterationsDoNotConverge
- SurvivalDecaysExponentially
- SwapParRatesRecovered
- FlatHazardRate.ZeroLambdaAlwaysOne
- DayCount.YearFractionACT365
- DayCount.YearFractionACTACT_BadDaysInYear
- DayCount.YearFractionACTACT_LeapYear
- DayCount.YearFractionTHIRTY360Throws
- Bond.YTMEqualsRateAtPar
- Bond.ZeroCouponBondAnalytical
- IRateModel.VasicekIsIRateModel
- Vasicek.ZeroRateConsistentWithBondPrice
- MarketObserver.UnsubscribeAllPreventsNotification
- EngineFactory.UnknownMethodThrows
- MonteCarloVaR.VaRPositiveForSymmetricDist
- NumericalGreeks.ThetaMatchesBS
- NumericalGreeks.ThetaNegativeForLongCall
- NumericalGreeks.VegaMatchesBS
- ParametricVaR.VaRIncreasesWithVolatility
- ParametricVaR.VaRScalesWithPortfolioValue
- VolSurface.VolRejectsNonPositiveMaturity
- test_ops_cashflows.py
- monteCarloBSPrice
- README.md - Project Overview
- confirm_settlement
- hedge_effectiveness.py
- value_trade
- test_hedges_report.py
- limits.py
- test_pnl.py
- xccy_swap.cpp
- ops_confirm.py
- D5 Conciliación con el banco
- roll
- test_hedges_schema.py
- sys
- test_validation_cases.py
- market_forward
- test_risk_lifecycle.py
- test_ExposureProfile.cpp
- dependencies
- D3 Confirmación de operación
- Veredicto R1 P&L explicado: CUMPLE
- _rel
- reconcile_trade
- test_xccy_py.py
- collateral.py
- create_run
- events.py (insert_event, cambios delimitados con corte 5)
- exposure_profile.cpp
- swaption.cpp
- init_schema
- test_market_roll.py
- C7 Declaraciones en Metodologia y reporte: reciclaje con hipotetico proxy, componente de tasa, causa obligatoria
- R11 Metodologia declara hipotetico, regla del menor, reciclaje, asientos sugeridos, simplificaciones y revision pendiente
- XccyBootstrapBindings
- R1 SOFR real desde la Fed de Nueva York
- _post
- D4 Medicion por periodo: reserva OCI por regla del menor, inefectividad, reciclaje e identidad de control
- D5 CVA y exposicion usando qf::xva existente en C++, expuesto en qfpy en serie y solo en este worktree
- D3 VaR historico: revaluacion por sensibilidades (delta) con cambios historicos de los ultimos N dias
- Tabla de interfaces core y sus implementaciones
- .shifted
- desk_commit
- D1 Datos en SQLite (desk/api/db.py)
- D4 Valuacion a fecha de valuacion (as_of del snapshot)
- Veredicto R5 Escenarios: CUMPLE
- Veredicto R4 Credito: CUMPLE en la letra, con defecto alto en coherencia del perfil (primera ronda)
- XccyCashFlow
- OisAgedBindings
- test_validation_route.py
- Auditoria independiente QF Desk corte 2 (feat/qf-desk, 35afa48..41f0a3f)
- Tabla trade_events solo insercion con disparadores UPDATE/DELETE
- D5 P&L entre dos fechas: endpoint GET /api/pnl?from&to
- OisSwap en C++ con periodo en curso iniciado y factor de capitalizacion acumulado
- D6 DV01 por plazo incluye MXN-USD; escenarios y VaR la tratan como curva dependiente (declarado)
- D2 Trabajo C++ en serie, comparten build/
- D4 Exportación e importación FpML
- D4 Limites: scopes counterparty, factor y portfolio; metricas pv_exposure, dv01, fx_delta y var
- Veredicto R6 Interfaz: CUMPLE con observaciones menores
- SimulateExposure
- Estados viva, vencida, terminada y ejercida
- Seccion Fuera de alcance del corte 2
- D3 Calendarios desk/api/calendars.py: dias inhabiles MX y EE. UU. 2020-2040 por reglas, sin dependencias
- D5 Operacion MXN con colateral USD descuenta con MXN-USD y proyecta con TIIE-F; con colateral MXN no cambia
- Diseño Corte 5 QF Desk (operaciones)
- D2 Historia de factores para VaR historico (factores del VaR del corte 1)
- desk/api/backup.py con API de respaldo de sqlite3
- Cruce xccy y colateral USD en riesgo avanzado del corte 6: cascada P&L, VaR, limites, CVA
- POST /api/fixings/fetch: índices SOFR, TIIE-F, USDMXN; rango máximo 366 días
- Corte 8 excluye usuarios y roles, aprobación de dos personas, multiempresa, contenedores, licencia e importación PiP/Valmer/Bloomberg
- D7 Interfaz: selector de fecha, alta con fechas, ficha, blotter, P&L, fijaciones, rodar
- D8 Interfaz: mercado, contrapartes, pricer xccy, riesgo, ficha con dias inhabiles, metodologia
- Convenciones de mercado (supuesto de convención, decisión de Fable)
- C3 Regla del menor sobre acumulados desde la designacion, con reciclaje y OCI = efectivo menos reciclaje
- D6 Efectividad prospectiva: coincidencia de terminos criticos y razon por escenario, umbral 0.8-1.25 solo referencial
- D1 Datos SQLite: tablas hedge_relationships, hedge_events y hedge_periods (solo insercion)
- R8 Sin regresión: las cuatro suites pasan
- Causa probable: corte 3 cambio envejecimiento y corte 5 se escribio contra el comportamiento anterior
- test_swaption.cpp
- origen
- MKT-LIVE: construido desde MarketDataFeed (SOFR, Treasuries) y FRED (DEXMXUS); solo lectura; se reescribe completo
- D1 Curva MXN-USD: descuento MXN bajo colateral en USD, calibrada con forwards y bases
- D3 Derivado hipotetico valuado con el motor existente, nunca guardado en trades
- R2 Banxico listo e inactivo sin token
- R6 Documentacion en desk/README.md y Metodologia
- Build de todos los targets
- Validación de PV de 62 casos: 7 operaciones del portafolio más batería fija de 8 a 12 por producto
- Seccion Restricciones del corte 2
- D8 Migracion idempotente de base corte 1 con evento execution
- counterparties.collateral_currency (MXN por omision o USD), editable por PUT /api/counterparties/<id>
- Bond y CapFloor con calendario explicito de pagos para envejecer de forma exacta
- C6 Avisos al designar no bloqueantes: no_economic_relationship, instrument_off_market, forecast_date_weekend
- Veredicto C8: CORREGIDO, interfaz sin desbordes, fechas ISO y errores de formulario limpiados; selector de snapshot menor
- D8 Reporte por relacion y exportacion CSV de asientos, con nivel 2 de jerarquia de valor razonable
- R8 Desdesignar genera evento, congela saldo y bloquea cierres (409); cierre con snapshot no posterior o operacion terminada da 409
- Veredicto R2 Limites: CUMPLE
- Tabla factor_history(factor, date, value): solo insercion y carga CSV idempotente
- D6 Confirmacion de xccy compara con cupon y no con intercambio (baja)
- R3 Procedencia visible con boton Traer de la fuente
- _period
- OisSwap gana clave de curva de descuento opcional (retrocompatible)
- C5 Liberacion de la reserva congelada con causa flow_occurred o flow_no_longer_expected
- D2 Tipos: hedge_type cash_flow o fair_value; item_kind floating_loan, forecast_fx y (tras P4) fixed_loan
- D9 Interfaz: pantalla Coberturas con lista, alta, detalle, cierre, desdesignacion, exportacion e impresion
- Correccion de conteos: ctest 449 y pytests 80 estaban mal; no hay pruebas perdidas (linea base 402 mas 8)
- R7 Suites en verde sin cambios injustificados
- Planes y specs en docs/superpowers/plans y specs
- Por feature crear include/qf/<module>/X.hpp, src/<module>/X.cpp, tests/test_X.cpp y actualizar CMakeLists
- MarketEnvironment: contenedor central de mercado (curvas, spots, vols) con patrón Observer
- --keep N borra las copias más viejas y solo toca archivos con nombre exacto
- Respaldo y restauración con python -m desk.api.backup
- Integración Banxico lista pero sin probar contra token real; formato de éxito no verificado (pendiente)
- Observacion abierta 1: cierre final con partida que sobrevive al instrumento recicla toda la reserva (6.5.12(a))
- Defecto N-2 (media): terminacion del instrumento no medible; pago de terminacion y cupon no se asientan
- C1 Designacion en orden y sin solapar frente a eventos previos de la misma operacion (corrige D-1)
- C4 Saldos de balance sin deriva de redondeo: diferencia de saldos acumulados redondeados (corrige D-3)
- Auditoria: metodo de prueba con backend real en puerto 5073, base temporal y Chrome headless a 1280 px
- I9 Interfaz recorrida en CDP: 8 pantallas sin errores, defecto visual D2
- Validacion del corte 7: report y smoke test, desk_commit como aviso
- Formato de respuesta HECHO o BLOQUEADO con evidencia por punto
- Tabla snapshots (una por fecha de valuacion)
- Snapshot gana curva de base y moneda de colateral por contraparte
- Principio 4: cada requisito comprobable por un tercero
- El CLI de backup siempre actúa sobre desk/data/desk.db; no hay flag --db
- make_report.sh
- Agregar caso: fila al final de la tabla de producto en export_cases.py, commit y make_report
- Commitear código de valuación antes de regenerar para que desk_commit sea definitivo y desk_dirty false
- Validación de curvas: DF en pilares y diez fechas intermedias; interpolación lineal sobre tasa cero continua, plana fuera de pilares
- Segunda ronda suites: ctest 449, bindings 80, backend 2754 passed, UI 335/335
- Minimizar cambios en archivos compartidos (db.py, app.py, Shell.tsx, App.tsx, api/types.ts, api/client.ts, MethodologyScreen.tsx) en bloques marcados corte 3
- Observacion abierta 4: retroactividad absoluta frente a 6.4.1(b); Metodologia afirma que la designacion no es retroactiva
- Observacion abierta 6: causas de desdesignacion aceptadas sin verificar contra los datos
- Defecto N-3 (baja): periodos guardados antes de bf8f948 dan 500 al cerrar un periodo nuevo
- Veredicto R12: CUMPLE, las cuatro suites en verde
- Veredicto R6: CUMPLE, valor razonable con deuda fija y swap identico
- Segunda ronda: commits revisados 2540a0a, f3b0a8e, f7b9452, 8f035f3, 668d25f, 8a9e5cd (13 archivos en desk/, sin C++)
- Minimizar cambios en archivos compartidos (db.py, app.py, Shell.tsx, App.tsx, api/types.ts, api/client.ts, MethodologyScreen.tsx, RiskScreen.tsx, risk/var.py, risk/scenarios.py, qfpy.cpp): solo anadir al final en bloques delimitados por comentario corte 6
- Veredicto R5 Carga por pantalla: CUMPLE (251 kB de entrada)
- Swaption 2f5b733: matematica correcta, diferencias con QuantLib cero
- desk/api/errors.py con ApiError y code opcional
- Tabla fixings (indice, fecha, valor)
- Corte 2 fuera de alcance: novaciones, asignaciones, compensacion, calendarios
- Asientos sugeridos (el sistema no es el libro mayor)
- Efectividad prospectiva (terminos criticos, escenarios) y retrospectiva por periodo
- Tasas guardadas en decimal (0.0389 = 3.89 %)
- Intencion corte 2: operacion con fechas, historia y valuacion a fecha
- Alcance de auditoria: commits ce51edf..046db38 contrastados con design.md; incluye 3887874 y b968653 del corte 4 (fuera de auditoria)
- Construido sin R: ficha del bono muestra sucio, limpio y corrido
- Construido sin R: pricer de xccy con exchange en cuatro modos (both, initial, final, none)
- Construido sin R: rodar un snapshot conserva las listas CSA
- Metodo independiente: script propio con qfpy de build/src, backend real en :5093 con base temporal, Chrome headless en :9353 a 1280 px
- Suite backend pytest desk/api/tests 2748 passed (primera ronda)
- Suite bindings pytests 80 OK; 24 tests del corte 3 cargan qfpy real y no se saltan
- Suite C++ ctest 449/449 pasan (primera ronda)
- Suite UI npm test 332/332 (20 archivos) y npm run build OK (primera ronda)
- Restricciones heredadas de cortes 2 y 4: Python 3.8, sin dependencias nuevas, guardia de no finitos, commits por tarea, sin git stash, sin push
- Observacion contable 8: componente forward incluido sin eleccion de 6.5.16, declarado como simplificacion
- Restricciones heredadas del corte 2: Python 3.8, sin dependencias nuevas, commits por tarea, sin git stash ni push
- Construido sin R: GET /api/limits, GET /api/limits/breaches y GET /api/credit/params como lecturas de apoyo a la UI
- Defecto 5 BAJA (primera ronda): biblioteca Por omision muestra nombre y descripcion duplicados; corregido en segunda ronda
- Observacion BAJA: en conjuntos creados por el usuario siguen saliendo nombre y choque en dos lineas casi iguales (TIIE-F +100 contra TIIE-F +100 pb)
- Suite cmake --build build -j3: OK
- Suite npm run build: OK con aviso de tamano de chunk
- Suite npm test (vitest): 377 tests primera ronda, 379 segunda ronda
- Suite pytest desk/api/tests: 2584 passed primera ronda, 2588 passed segunda ronda
- Claudio delego todas las decisiones en Fable
- Restriccion heredada: commits por tarea con GRAPHIFY_SKIP_HOOK=1, autor Claudio sin Co-Authored-By, sin git stash, sin push
- Restriccion heredada: Python 3.8 de anaconda, sin dependencias nuevas, guardia de no finitos, validacion en la frontera
- Trabajo en worktree propio, rama corte6 creada desde feat/qf-desk, se fusiona al final
- Corte 4 R4: reciclaje de OCI a resultados al ocurrir el flujo cubierto
- Corte 4 R6: reporte por relacion exportable (documentacion, prueba, asientos, jerarquia VR)
- Corte 5 R4: conciliacion con archivo de valuaciones del banco, diferencia y descomposicion
- Corte 6 R1: P&L explicado entre fechas, residuo menor a 2 por ciento
- Corte 6 R2: limites por contraparte y factor, alerta y bitacora de excesos
- Corte 6 R5: biblioteca de escenarios guardados (depreciaciones historicas)
- Corte 7 R3: pagina de Validacion generada del ultimo reporte con fecha y version
- Empresas separadas: un cliente no ve datos de otro
- Deuda corte 1: paquete de interfaz supera 500 kB, cargar por pantalla
- Deuda corte 1: desplazamientos de riesgo sobre tasa cero, no sobre cotizacion
- Deuda corte 1: textos de tablas en espanol definidos por pantalla, compartir uno
- Fuente: Eclipse Tradista

## God Nodes (most connected - your core abstractions)
1. `ApiError` - 169 edges
2. `MarketContext` - 82 edges
3. `get_conn()` - 78 edges
4. `roll()` - 77 edges
5. `connect()` - 75 edges
6. `fmtNumber()` - 75 edges
7. `ensure_finite()` - 65 edges
8. `designate()` - 63 edges
9. `ApiError` - 60 edges
10. `load_context()` - 58 edges

## Surprising Connections (you probably didn't know these)
- `Engine Factory` --rationale_for--> `Copilot Instructions - Design Patterns & Workflow`  [INFERRED]
  src/pricingengines/engine_factory.cpp → .github/copilot-instructions.md
- `HestonModel` --calls--> `IEquityModel.HestonInvalidParamsThrow`  [INFERRED]
  include/qf/models/heston_model.hpp → tests/test_models_interfaces.cpp
- `InterestRateSwap` --calls--> `Swap.InvalidParamsThrow`  [INFERRED]
  include/qf/instruments/swap.hpp → tests/test_instruments.cpp
- `HestonEngine` --references--> `HestonCalibrator (P3) - Heston Calibration`  [EXTRACTED]
  include/qf/pricingengines/heston.hpp → docs/superpowers/specs/2026-07-07-heston-calibration-design.md
- `Engine Factory` --references--> `Architecture Refactor - MarketEnvironment & Strategy Pattern`  [EXTRACTED]
  src/pricingengines/engine_factory.cpp → docs/superpowers/specs/2026-04-02-architecture-refactor-design.md

## Import Cycles
- 3-file cycle: `desk/api/db.py -> desk/api/migrate.py -> desk/api/portfolio.py -> desk/api/db.py`
- 4-file cycle: `desk/api/collateral.py -> desk/api/db.py -> desk/api/migrate.py -> desk/api/portfolio.py -> desk/api/collateral.py`
- 4-file cycle: `desk/api/lifecycle.py -> desk/api/pricing/__init__.py -> desk/api/pricing/xccy.py -> desk/api/xccy.py -> desk/api/lifecycle.py`
- 5-file cycle: `desk/api/collateral.py -> desk/api/db.py -> desk/api/migrate.py -> desk/api/portfolio.py -> desk/api/valuation.py -> desk/api/collateral.py`

## Hyperedges (group relationships)
- **Interest Rate Model Implementations** — src_models_hullwhite, src_models_vasicek [EXTRACTED 0.90]
- **Dual-curve IRS: separate discount and projection curves** — qf_instruments_InterestRateSwap, qf_instruments_CurveKeys, qf_termstructure_YieldCurve [EXTRACTED 0.90]
- **Bootstrap workflow: deposits and swaps -> curve calibration** — qf_termstructure_Bootstrap, qf_instruments_InterestRateSwap, qf_termstructure_YieldCurve [EXTRACTED 0.95]
- **Heston Calibration & Pricing Pipeline** — src_math_optimization, engine_blackscholes, engine_heston [EXTRACTED 0.95]
- **Equity Option Pricing Pipeline** — include_qf_models_iequity_model_iequitymodel, include_qf_pricingengines_ipricing_engine_ipricingengine [EXTRACTED 0.95]
- **Instrument pricing via MarketEnvironment** — qf_instruments_Instrument, qf_core_MarketEnvironment, qf_termstructure_YieldCurve [EXTRACTED 0.95]
- **Comprobaciones numericas de validacion** — docs_superpowers_qf_desk_design_r1_check_10pb_df, docs_superpowers_qf_desk_design_r2_check_irs_par, docs_superpowers_qf_desk_design_r2_check_fx_forward_formula, docs_superpowers_qf_desk_design_r2_check_put_call, docs_superpowers_qf_desk_design_r2_check_suma_flujos, docs_superpowers_qf_desk_design_r4_check_dv01_suma_paralelo, docs_superpowers_qf_desk_design_r4_check_escenario_paralelo, docs_superpowers_qf_desk_design_r4_check_var_fx [EXTRACTED 1.00]
- **Descomposición indicativa de la conciliación** — docs_superpowers_qf_desk_corte5_design_d5, docs_superpowers_qf_desk_corte5_design_desc_fecha, docs_superpowers_qf_desk_corte5_design_desc_curva, docs_superpowers_qf_desk_corte5_design_desc_tc, docs_superpowers_qf_desk_corte5_design_desc_terminos [EXTRACTED 1.00]
- **Defectos de la auditoria del corte 6 (primera ronda) y su estado** — docs_superpowers_qf_desk_corte6_audit_defecto1_perfil_eepfe_incoherente, docs_superpowers_qf_desk_corte6_audit_defecto2_eeo_sin_compensar, docs_superpowers_qf_desk_corte6_audit_defecto3_tabla_pnl_desborda, docs_superpowers_qf_desk_corte6_audit_defecto4_codigos_internos, docs_superpowers_qf_desk_corte6_audit_defecto5_biblioteca_duplicada [EXTRACTED 1.00]
- **Tablas de persistencia de coberturas (relaciones, eventos y periodos)** — docs_superpowers_qf_desk_corte4_design_hedge_relationships, docs_superpowers_qf_desk_corte4_design_hedge_events, docs_superpowers_qf_desk_corte4_design_hedge_periods [EXTRACTED 1.00]
- **Fundamentos de la operacion con vida (corte 2)** — docs_superpowers_qf_desk_roadmap_corte2_trades, docs_superpowers_qf_desk_roadmap_corte2_trade_events, docs_superpowers_qf_desk_roadmap_corte2_fixings, docs_superpowers_qf_desk_roadmap_corte2_snapshots, docs_superpowers_qf_desk_roadmap_corte2_tipos_evento, docs_superpowers_qf_desk_roadmap_corte2_estado_derivado [EXTRACTED 1.00]
- **Cortes que dependen del corte 2 (fechas e historia)** — docs_superpowers_qf_desk_roadmap_corte2, docs_superpowers_qf_desk_roadmap_corte4, docs_superpowers_qf_desk_roadmap_corte6 [EXTRACTED 1.00]
- **Pendientes abiertos al cierre del 2026-11-11** — docs_superpowers_qf_desk_roadmap_pend_contador_ifrs9, docs_superpowers_qf_desk_roadmap_pend_token_banxico, docs_superpowers_qf_desk_roadmap_pend_curvas_sinteticas, docs_superpowers_qf_desk_roadmap_pend_plataforma_multiusuario, docs_superpowers_qf_desk_roadmap_pend_limites_metodologia [EXTRACTED 1.00]
- **Unified Pricing Engine Interface** — engine_blackscholes, engine_montecarlo, engine_binomialtree, engine_finitedifference, engine_heston, src_pricingengines_engine_factory [EXTRACTED 1.00]
- **Flujo de fijaciones desde la fuente** — desk_readme_fixings_fetch_endpoint, desk_readme_fixings_no_overwrite, desk_readme_fixings_error_codes, desk_readme_fixings_sources_endpoint [EXTRACTED 1.00]
- **Requisitos R1 a R8 del corte 6** — docs_superpowers_qf_desk_corte6_design_r1_pnl_explicado, docs_superpowers_qf_desk_corte6_design_r2_limites, docs_superpowers_qf_desk_corte6_design_r3_var_historico, docs_superpowers_qf_desk_corte6_design_r4_credito, docs_superpowers_qf_desk_corte6_design_r5_escenarios, docs_superpowers_qf_desk_corte6_design_r6_interfaz, docs_superpowers_qf_desk_corte6_design_r7_metodologia, docs_superpowers_qf_desk_corte6_design_r8_sin_regresion [EXTRACTED 1.00]
- **Stack de frontend permitido** — docs_superpowers_qf_desk_design_arq_frontend_react_ts_vite, docs_superpowers_qf_desk_design_tech_ag_grid_community, docs_superpowers_qf_desk_design_tech_echarts, docs_superpowers_qf_desk_design_tech_cmdk, docs_superpowers_qf_desk_design_tech_react_router_dom, docs_superpowers_qf_desk_design_tech_vitest_testing_library [EXTRACTED 1.00]
- **XVA Valuation Pipeline (CVA/DVA/FVA)** — CVACalculator, NettingSet, include_qf_models_hullwhite, FlatHazardRate, MarketEnvironment [EXTRACTED 1.00]
- **Arnes de validacion contra QuantLib** — docs_superpowers_qf_desk_corte7_design_d2, docs_superpowers_qf_desk_corte7_design_export_cases_py, docs_superpowers_qf_desk_corte7_design_run_quantlib_py, docs_superpowers_qf_desk_corte7_design_compare_py, docs_superpowers_qf_desk_corte7_design_make_report_sh, docs_superpowers_qf_desk_corte7_design_report_json [INFERRED 0.75]
- **Flujo pricer, portafolio y riesgo** — docs_superpowers_qf_desk_design_r2_pricers, docs_superpowers_qf_desk_design_r3_trades_crud, docs_superpowers_qf_desk_design_r3_valuation_endpoint, docs_superpowers_qf_desk_design_r8_agregar_portafolio, docs_superpowers_qf_desk_design_r4_riesgo [INFERRED 0.75]
- **Flujo de traer fijaciones de la fuente** — docs_superpowers_qf_desk_corte8_design_endpoint_fixings_fetch, desk_api_fixings_fetch, docs_superpowers_qf_desk_corte8_design_reuso_fixings_py, docs_superpowers_qf_desk_corte8_design_conflicts_respuesta [INFERRED 0.75]
- **Procedencia Banxico con token y rechazo** — docs_superpowers_qf_desk_corte8_design_env_banxico_token, desk_api_banxico, docs_superpowers_qf_desk_corte8_design_p4_banxico_token_rechazado, docs_superpowers_qf_desk_corte8_design_endpoint_fixings_sources [INFERRED 0.75]
- **Defectos de segunda ronda sobre la regla del menor y la reserva (N-1, N-2, N-3)** — docs_superpowers_qf_desk_corte4_audit_n1, docs_superpowers_qf_desk_corte4_audit_n2, docs_superpowers_qf_desk_corte4_audit_n3 [INFERRED 0.75]
- **Hull-White Jamshidian Decomposition (Bisection + ZCB Options)** — src_math_integration_cpp [INFERRED 0.80]
- **Risk Measurement System** — ScenarioEngine, include_qf_instruments_bond, Leg, MarketEnvironment [INFERRED 0.82]
- **Colateral por contraparte: almacenamiento, historial, valuacion y verificacion** — docs_superpowers_qf_desk_corte3_design_collateral_currency, docs_superpowers_qf_desk_corte3_design_counterparty_events, docs_superpowers_qf_desk_corte3_design_d5_valuacion_colateral, docs_superpowers_qf_desk_corte3_design_r3 [INFERRED 0.85]
- **Defectos bajos abiertos de la auditoria** — docs_superpowers_qf_desk_corte3_audit_d2_r7_fragil, docs_superpowers_qf_desk_corte3_audit_d3_r2_pilares, docs_superpowers_qf_desk_corte3_audit_d5_corrido_medio_dia, docs_superpowers_qf_desk_corte3_audit_d6_caplet_fijado, docs_superpowers_qf_desk_corte3_audit_d7_fx_forward_sofr [INFERRED 0.85]
- **Dual-Curve Pricing Framework** — InterestRateSwap, ScheduledSwap, CurveKeys, ScenarioEngine [INFERRED 0.85]
- **Heston model captures volatility smile via stochastic vol** — qf_models_HestonModel, qf_pricingengines_HestonEngine, qf_termstructure_VolSurface [INFERRED 0.85]
- **Fixed Income Rate Risk Analysis** — include_qf_models_irate_model_iratemodel, include_qf_termstructure_yieldcurve, include_qf_risk_scenario_scenarioengine [INFERRED 0.85]
- **Rate-Risk Tooling: ScenarioEngine + YieldCurve bumps to DV01 ladder + scenarios** — scenarioengine_component, yieldcurve_component, keyrate_dv01, scenario_result [INFERRED 0.85]
- **Flujo del cross currency swap: motor, producto y verificacion R5/R6** — docs_superpowers_qf_desk_corte3_design_xccyswap, docs_superpowers_qf_desk_corte3_design_d7_producto_xccy_swap, docs_superpowers_qf_desk_corte3_design_r5, docs_superpowers_qf_desk_corte3_design_r6 [INFERRED 0.85]
- **XVA Computation Pipeline: CVACalculator to CVAResult with EPE/ENE/DVA/FVA** — cvaxva_component, cvaengine_spec, netting_set, icredit_curve, cva_result [INFERRED 0.85]
- **Heston Model Calibration Workflow** — include_qf_models_heston_calibrator_hestoncalibrator, include_qf_math_optimization_neldermead, include_qf_pricingengines_heston_hestonengine [INFERRED 0.90]
- **Vol Surface Ecosystem: Heston calibration to VolSurface to MarketEnvironment integration** — hestonpx_component, volsurface_component, market_environment, implied_vol_inverter [INFERRED 0.90]
- **Web Pricing Stack (Flask → qfpy → C++ Engines)** — web_flask_app, python_web_static_js_bonds, python_web_static_js_swaps [INFERRED 0.90]

## Communities (544 total, 293 thin omitted)

### Community 0 - "rates.py"
Cohesion: 0.15
Nodes (30): _bond_describe(), _bond_instrument(), _bond_price(), _bond_pv(), _bond_validate(), _cap_floor_describe(), _cap_floor_instrument(), _cap_floor_price() (+22 more)

### Community 1 - "MarketEnvironment"
Cohesion: 0.05
Nodes (37): Dual-Curve Pricing (P5), addCurve, curves_, hasVolSurface, observers_, setSpot, setVolatility, setVolSurface (+29 more)

### Community 2 - "PortfolioScreen.tsx"
Cohesion: 0.04
Nodes (47): pnl(), valuation(), PnlResponse, PnlRow, TradeStatus, ValuationResponse, ValuationRow, columnDefs (+39 more)

### Community 3 - "Swaption"
Cohesion: 0.11
Nodes (6): Swaption, dcc_, hw_a_, hw_sigma_, Integration Methods, DayCount.SwaptionPayerACT360LowerReceiverHigher

### Community 4 - "YieldCurve"
Cohesion: 0.03
Nodes (50): main(), HullWhite, a_, bondPrice, conditionalBondPrice, curve_, sigma_, simulate (+42 more)

### Community 5 - "Swap"
Cohesion: 0.03
Nodes (63): main(), CurveKeys, discountKey, projectionKey, InterestRateSwap, annuity, frequency_, keys_ (+55 more)

### Community 6 - "Yield curve with discount factors and forward rates"
Cohesion: 0.07
Nodes (47): Black-Scholes example: European call valuation, Bond pricing and yield curve usage, Curve bootstrapping from deposits and swaps, Finite difference schemes vs Black-Scholes, Heston calibration to listed option chain, Heston vs Black-Scholes comparison with volatility smile, Vasicek and Hull-White model demonstration, Monte Carlo pricing comparison (MC vs BS vs Binomial) (+39 more)

### Community 7 - "test_finite_guard.py"
Cohesion: 0.10
Nodes (28): _add_poisoned_trade(), _assert_400(), _assert_non_finite_400(), _call(), _deep(), _poison_fx_forward(), _strict(), test_b1_el_mismo_caso_como_operacion_se_guarda_pero_la_valuacion_sigue_finita() (+20 more)

### Community 8 - "test_errors.py"
Cohesion: 0.10
Nodes (33): _case(), _delete_cases(), _drop(), _dv01_cases(), _just_above(), _market_cases(), _non_finite(), _price_cases() (+25 more)

### Community 9 - "VolSurface"
Cohesion: 0.05
Nodes (29): Interpolator, method_, spline_M_, x_, y_, brent, VolSurface, buildSmiles (+21 more)

### Community 10 - "ApiError"
Cohesion: 0.16
Nodes (22): latest_sofr(), latest_treasury_curve(), _query(), treasury_5y_history(), make_mdf_db(), _conflict(), _history(), test_database_without_tables_is_409() (+14 more)

### Community 11 - "QF Desk: backend Flask+SQLite en desk/api y UI React+TS+Vite en desk/ui sobre qfpy"
Cohesion: 0.06
Nodes (25): Docs del desk en docs/superpowers/qf-desk (design, plan, roadmap, corte2..corte8, integracion), Cuatro suites de test del desk (C++, pytests, backend pytest, UI vitest+build), QF Desk: backend Flask+SQLite en desk/api y UI React+TS+Vite en desk/ui sobre qfpy, ./desk/run.sh sirve QF Desk en puerto 5070, Regenerar validación QuantLib del desk con desk/validation/make_report.sh tras tocar valuación, Bindings qfpy (qfpy.cpp): opciones, bonos, swaps, curvas, Target pytests (tests Python), Target qfpy (bindings Python) (+17 more)

### Community 12 - "vitest"
Cohesion: 0.05
Nodes (53): name, private, scripts, build, dev, test, type, version (+45 more)

### Community 13 - "MarketScreen.tsx"
Cohesion: 0.03
Nodes (79): getSnapshot(), listSnapshots(), refreshMarket(), rollSnapshot(), updateSnapshot(), CsaInfo, CurvePoint, DataQuality (+71 more)

### Community 14 - "Bond"
Cohesion: 0.05
Nodes (27): main(), Bond, couponRate_, dcc_, faceValue_, frequency_, payTimes_, prevCouponTime_ (+19 more)

### Community 15 - "get_conn"
Cohesion: 0.05
Nodes (76): close_conn(), get_conn(), public_event(), get_trade(), change_collateral(), list_counterparties(), add_fixing(), fetch_from_source() (+68 more)

### Community 16 - "RiskScreen.tsx"
Cohesion: 0.08
Nodes (38): riskDv01(), riskScenarios(), riskVar(), Dv01Response, ScenarioSpec, ScenariosResponse, CSA_CURVE_NOTE, buildRows() (+30 more)

### Community 17 - "IUnderlying"
Cohesion: 0.11
Nodes (22): CommodityUnderlying, code_, id, EquityUnderlying, id, ticker_, FxUnderlying, id (+14 more)

### Community 18 - "HestonParams"
Cohesion: 0.04
Nodes (52): nelderMead, CalibrationResult, converged, iterations, params, perQuoteErrors, rmse, HestonCalibrator (+44 more)

### Community 19 - "sqlite3"
Cohesion: 0.07
Nodes (11): _matched(), measure(), _previous(), _fmt(), run_csv(), _yes_no(), _smile(), merge_warnings() (+3 more)

### Community 20 - "OptionParams"
Cohesion: 0.04
Nodes (44): OptionParams, dividendYield, exercise, maturity, riskFreeRate, spot, strike, type (+36 more)

### Community 21 - "ApiError"
Cohesion: 0.03
Nodes (116): ApiError, listTrades(), request(), addLimitEvent(), checkLimits(), createLimit(), createScenarioSet(), creditExposure() (+108 more)

### Community 22 - "api/types.ts"
Cohesion: 0.03
Nodes (112): addFixing(), closeHedgePeriod(), dedesignateHedge(), deleteTrade(), fetchFixings(), fixingSources(), getTrade(), getValidationReport() (+104 more)

### Community 23 - "TEST"
Cohesion: 0.05
Nodes (17): CapFloor, boundaryTimes_, dcc_, hw_a_, hw_sigma_, CapFloorType, Cap, Floor (+9 more)

### Community 24 - "pytest"
Cohesion: 0.15
Nodes (25): assert_error(), ok(), post(), test_bond_curve_defaults_to_tiie_and_frequency_to_two(), test_bond_response_keys_and_cashflows(), test_bond_sofr_converts_to_mxn(), test_cap_dv01_negative_floor_positive(), test_cap_floor_has_positive_pv() (+17 more)

### Community 25 - "qfpy.cpp"
Cohesion: 0.07
Nodes (28): CurveKeys for Dual-Curve Pricing, DayCount Convention Enum, InterestRateSwap Class, Interpolator Class, Leg Class, MarketEnvironment Class, ScenarioEngine Class, ScheduledLeg Class (+20 more)

### Community 26 - "Option"
Cohesion: 0.04
Nodes (43): Binomial Tree Pricing Engine, Black-Scholes Pricing Engine, Finite Difference Pricing Engine, Monte Carlo Pricing Engine, main(), monteCarloBSPrice(), Copilot Instructions - Design Patterns & Workflow, Option (+35 more)

### Community 27 - "VaRResult"
Cohesion: 0.08
Nodes (23): Heston Pricing Engine, PortfolioPosition, meanReturn, stddev, value, VaRResult, cvar, var (+15 more)

### Community 28 - "PricerForm.tsx"
Cohesion: 0.04
Nodes (74): createTrade(), price(), Cashflow, CollateralCurrency, PriceResponse, XccyCashflow, CommandPalette(), Props (+66 more)

### Community 29 - "HestonModel"
Cohesion: 0.07
Nodes (26): CVACalculator Class, FlatHazardRate Credit Curve, NettingSet Class, Simulation Parameters, Architecture Refactor - MarketEnvironment & Strategy Pattern, BlackScholesModel, q_, r_ (+18 more)

### Community 30 - "portfolio.py"
Cohesion: 0.08
Nodes (21): _add_days(), _at_par(), counterparty_id(), create_trade(), _dates_from_body(), _decode(), default_maturity(), _describe() (+13 more)

### Community 31 - "DeskBindings"
Cohesion: 0.13
Nodes (3): DeskBindings, _env(), _quotes()

### Community 32 - "test_fred.py"
Cohesion: 0.12
Nodes (12): fetch_dexmxus(), parse_dexmxus(), make_fred_csv(), test_fetch_missing_file_propagates_urlerror(), test_fetch_passes_url_as_is_with_20s_timeout_and_no_user_agent(), test_fetch_reads_a_file_url(), test_fetch_without_valid_observations_propagates_valueerror(), test_make_fred_csv_writes_header_and_blanks() (+4 more)

### Community 33 - "register_error_handlers"
Cohesion: 0.36
Nodes (6): register_error_handlers(), _api_error(), _http_error(), _not_implemented(), _pricing_error(), _response()

### Community 34 - "test_refresh.py"
Cohesion: 0.09
Nodes (33): _arm(), _exit3(), _fred_missing(), _fred_no_valid_rows(), _fred_short_history(), _fx_rows(), _hist5(), _live_row() (+25 more)

### Community 35 - "Tabla trade_events (solo insercion, tipo, fecha, datos, evento previo)"
Cohesion: 0.20
Nodes (10): Corte 2 R1: operacion con fechas y evento execution; trade_events inmutable, Corte 2 R2: test de replay desde cero da el mismo estado, Corte 2 R5: terminacion anticipada genera evento y flujo, sale de valuacion, Corte 2 R7: ficha de operacion con linea de tiempo y calendario de flujos, Tipos de evento: execution, reset, transfer, quantity_change, terms_change, exercise, termination, Tabla trade_events (solo insercion, tipo, fecha, datos, evento previo), Disparador SQLite que rechaza UPDATE y DELETE en trade_events, Corte 4 R5: desdesignar genera evento y congela saldo acumulado (+2 more)

### Community 36 - "test_risk_dv01_scenarios.py"
Cohesion: 0.17
Nodes (22): _add(), _clear(), _dv01(), _insert_raw(), irs_client(), _scenarios(), test_dv01_corrupt_rows_are_reported_and_excluded(), test_dv01_shape_on_seed_portfolio() (+14 more)

### Community 37 - "PnlExplainTab.test.tsx"
Cohesion: 0.08
Nodes (27): ExplainResponse, ExplainStepKey, cssColor(), EChart(), EChartProps, axisMoney(), Bar, cascadeOption() (+19 more)

### Community 38 - "IPricingEngine"
Cohesion: 0.05
Nodes (34): BinomialTreeEngine, nSteps_, params_, price, ticker_, BlackScholesEngine, params_, price (+26 more)

### Community 39 - "HedgeScreen.tsx"
Cohesion: 0.04
Nodes (101): createHedge(), getHedge(), hedgeReport(), CriticalTerm, DedesignationCause, EffectivenessResponse, HedgeDetail, HedgeDocumentation (+93 more)

### Community 40 - "api/market.py"
Cohesion: 0.05
Nodes (37): load_all(), _build_context(), _calibrate_csa(), _csa_info(), _curve_points(), _curves_payload(), data_quality(), _fetch() (+29 more)

### Community 41 - "test_live_market.py"
Cohesion: 0.05
Nodes (60): demo_data(), _quotes(), _all_finite(), _assert_key_rates_add_up(), conn(), _end_at(), _fx_rows(), _fx_series() (+52 more)

### Community 42 - "test_ops_fpml.py"
Cohesion: 0.05
Nodes (86): _amount(), _bad(), _check_party_refs(), _date(), _expect(), _export_fx_forward(), _export_fx_option(), _export_irs() (+78 more)

### Community 43 - "fmtNumber"
Cohesion: 0.05
Nodes (81): listCounterparties(), setCollateral(), reconciliationCsvUrl(), listCreditParams(), CreditCounterparty, CreditParams, HistVarResponse, Counterparty (+73 more)

### Community 44 - "opsClient.ts"
Cohesion: 0.04
Nodes (88): cashflowPairs(), cashflowsCsvUrl(), confirmSettlement(), createReconciliation(), fpmlUrl(), getCashflows(), getConfirmation(), getReconciliation() (+80 more)

### Community 45 - "live_market.py"
Cohesion: 0.15
Nodes (9): build_live_data(), daily_vol_bp(), daily_vol_logret(), rebuild_live(), sample_std(), save_live(), _sources(), treasury_to_ois() (+1 more)

### Community 46 - "test_price_fx.py"
Cohesion: 0.17
Nodes (18): _bad(), ctx(), _ok(), _price(), _rel(), test_equity_option_does_not_depend_on_market(), test_equity_option_matches_black_scholes_times_quantity(), test_equity_option_quantity_defaults_to_one() (+10 more)

### Community 47 - "test_calendars.py"
Cohesion: 0.06
Nodes (55): _easter(), holidays(), holidays_between(), is_business_day(), is_holiday(), _last_weekday(), _mexico(), _nth_weekday() (+47 more)

### Community 48 - "test_market.py"
Cohesion: 0.12
Nodes (16): ctx(), _dfs(), _error(), test_bootstrapped_curve_reprices_its_quote(), test_env_with_default_points_to_requested_curve(), test_get_snapshot_shape(), test_put_bad_quotes_is_400_on_quotes(), test_put_bad_spot_is_400_on_spot() (+8 more)

### Community 49 - "test_risk_var.py"
Cohesion: 0.21
Nodes (15): _factor(), _ok(), _only(), _rel(), test_corrupt_trade_is_reported_and_excluded(), test_empty_portfolio_has_zero_var(), test_equity_option_alone_has_zero_var(), test_factor_vols_override_is_partial_and_per_request() (+7 more)

### Community 50 - "test_market_feed.py"
Cohesion: 0.14
Nodes (13): fetch_equity, fetch_treasury_curve_fred, fetch_treasury_curve_yfinance, fetch_treasury_curve_yfinance(), _yf_last_close(), _make_yf_df(), test_fetch_treasury_curve_yf_raises_on_no_data(), test_fetch_treasury_curve_yf_returns_yield_curve() (+5 more)

### Community 51 - "TEST"
Cohesion: 0.14
Nodes (5): makeEnv(), smile(), sofr(), TEST(), tiief()

### Community 52 - "market_environment.cpp"
Cohesion: 0.08
Nodes (23): IMarketObserver, onMarketUpdate, notify, MarketEnvironment::addCurve(), MarketEnvironment::hasVolSurface(), MarketEnvironment::MarketEnvironment(), MarketEnvironment::notify(), MarketEnvironment::setSpot() (+15 more)

### Community 53 - "CVACalculator"
Cohesion: 0.03
Nodes (58): IRateModel, bondPrice, conditionalBondPrice, simulate, zeroRate, FlatHazardRate, lambda_, survivalProbability (+50 more)

### Community 54 - "json"
Cohesion: 0.07
Nodes (34): _booked(), _close(), close_period(), dedesignate(), _entry(), release_reserve(), _since(), build_report() (+26 more)

### Community 55 - "MethodologyScreen.tsx"
Cohesion: 0.10
Nodes (21): DECL_DEDESIGNATION, DECL_DESIGNATION_DATE, DECL_FV_ACCRUAL, DECL_FV_COMPONENT, DECL_FV_PRESENTATION, DECL_OFF_MARKET, DECL_RECYCLING, HEDGE_DECLARATIONS (+13 more)

### Community 56 - "common.py"
Cohesion: 0.06
Nodes (20): build_curve(), curve_report(), setup(), _zero(), _flat_vol(), price_equity_option(), price_fx_forward(), price_fx_option() (+12 more)

### Community 57 - "charts.js"
Cohesion: 0.18
Nodes (16): fetchConvergence(), fetchGreeksSurface(), fetchPayoff(), getFormPayload(), plotlyConfig, plotlyLayout, renderConvergenceChart(), renderGreeksChart() (+8 more)

### Community 59 - "test_credit.py"
Cohesion: 0.07
Nodes (42): _add_months(), _counterparty(), _effective_fixed_rate(), exposure(), _grid(), _history(), list_params(), _model_maturity() (+34 more)

### Community 60 - "Vasicek"
Cohesion: 0.07
Nodes (20): B, Vasicek, a_, bondPrice, conditionalBondPrice, r0_, sigma_, simulate (+12 more)

### Community 61 - "test_hedges_periods.py"
Cohesion: 0.10
Nodes (47): _cents(), journal(), move(), load_fixings(), _accounts(), _balanced(), _cents(), _close() (+39 more)

### Community 62 - "Corte 1: workstation nucleo (hecho y auditado)"
Cohesion: 0.50
Nodes (3): Corte 1: workstation nucleo (hecho y auditado), Corte 2 R8: migracion de operaciones del corte 1 sin perdidas, PV sin cambio 1e-8, Deuda corte 1: hallazgos de la auditoria del corte 1 a saldar

### Community 63 - "TEST"
Cohesion: 0.04
Nodes (27): OisSwap, accruedFactor_, curveKey_, dcc_, discountCurveKey_, payDays_, startDays_, MarketEnvironment.MissingCurveThrows (+19 more)

### Community 64 - "test_market_csa.py"
Cohesion: 0.08
Nodes (49): csa_quotes_data(), ensure_csa_quotes(), strip_csa(), test_fixture_helpers_create_trades_and_strip_the_csa_quotes(), _bad(), _conn(), _context(), _data() (+41 more)

### Community 65 - "ois_swap.cpp"
Cohesion: 0.10
Nodes (22): OisCashFlow, accrual, discountFactor, fixedAmount, floatAmount, netAmount, payDays, payTime (+14 more)

### Community 66 - "TEST"
Cohesion: 0.06
Nodes (28): XccySide, PayMxn, PayUsd, XccySwap, accruedFactorMxn_, accruedFactorUsd_, dcc_, finalExchange_ (+20 more)

### Community 67 - "DV01 (sensibilidad de precio a 1 pb)"
Cohesion: 0.16
Nodes (17): Delta FX por spot (exposicion USDMXN), DV01 (sensibilidad de precio a 1 pb), Empinamiento de la curva (choque de pendiente), Key-rate DV01 por curva y plazo, Matriz de correlacion 3x3 de factores de riesgo, VaR parametrico delta-normal, P2: VaR con exactamente tres factores USDMXN, TIIE-F paralelo y SOFR paralelo, P8: equity_option aporta PV al portafolio; en DV01, escenarios y VaR su contribucion es cero (+9 more)

### Community 68 - "Tabla trades (identidad, terminos, fecha de pacto, inicio y vencimiento)"
Cohesion: 0.40
Nodes (5): Tabla counterparties, Tabla trades (identidad, terminos, fecha de pacto, inicio y vencimiento), Derivado hipotetico que representa la partida cubierta, Entidad hedge_relationships (instrumento, partida cubierta, tipo, razon, documentacion), Corte 4 R1: hipotetico identico da inefectividad cero, todo el cambio a OCI

### Community 69 - "Instrument"
Cohesion: 0.05
Nodes (43): Black-Scholes Pricing Engine, HestonCalibrator Class, Heston Pricing Engine, Instrument, calculatePV, engine_, pv, setPricingEngine (+35 more)

### Community 70 - "MarketEnvironmentBuilder"
Cohesion: 0.13
Nodes (5): MarketEnvironmentBuilder, test_builder_add_equity_calls_fetch(), test_builder_flat_curve_no_network(), test_builder_flat_curve_rate_is_correct(), test_builder_manual_spot_overrides_fetched()

### Community 71 - "test_banxico.py"
Cohesion: 0.06
Nodes (33): fetch_series(), parse_series(), fetch_sofr(), parse_sofr(), _body(), FakeResponse, test_fetch_fix_url(), test_fetch_propagates_network_errors_without_leaking_the_token() (+25 more)

### Community 72 - "compilerOptions"
Cohesion: 0.12
Nodes (15): compilerOptions, isolatedModules, jsx, lib, module, moduleResolution, noEmit, noFallthroughCasesInSwitch (+7 more)

### Community 73 - "Instrumento XccySwap (nocional constante primero)"
Cohesion: 0.28
Nodes (9): Cliente de API Banxico (TIIE de Fondeo y FIX), escrito y probado solo con respuestas simuladas, Bootstrap conjunto de proyeccion y descuento en C++, Corte 3 R1: todo instrumento de calibracion reprecia a cero incl. xccy, Corte 3 R5: XccySwap como producto en pricer, portafolio y riesgo, Instrumento XccySwap (nocional constante primero), Datos reales: fijaciones TIIE de Fondeo y FIX de Banxico, SOFR de la Fed NY, curvas de proveedor, Pendiente 2: token BANXICO_TOKEN, cliente TIIE-F y FIX sin probar contra API real, SOFR (tasa de referencia USD) (+1 more)

### Community 74 - "bond.cpp"
Cohesion: 0.19
Nodes (9): Bond::Bond(), Bond::cashflows(), Bond::cashFlowSchedule(), Bond::cleanPrice(), Bond::convexity(), Bond::duration(), Bond::maturities(), Bond::price() (+1 more)

### Community 75 - "OptimResult"
Cohesion: 0.16
Nodes (10): OptimResult, converged, fmin, iterations, x, Nelder-Mead Optimizer, centroid(), extrapolate() (+2 more)

### Community 76 - "cmath"
Cohesion: 0.09
Nodes (4): deltaNormalVaR(), TEST(), upwardCurve(), TEST()

### Community 77 - "_roll"
Cohesion: 0.13
Nodes (44): _live(), _pay_days(), test_bond_accrued_interest_grows_linearly_between_coupons(), test_bond_coupon_dated_on_the_snapshot_is_settled_and_not_in_the_value(), test_bond_flows_settle_coupons_and_then_the_redemption(), test_bond_quote_is_none_until_it_is_alive_and_after_it_matures(), test_bond_rolled_day_by_day_has_no_step_and_dirty_clean_accrued_add_up(), test_bond_that_starts_in_the_future_keeps_its_calendar_and_has_no_accrued() (+36 more)

### Community 78 - "TEST"
Cohesion: 0.19
Nodes (4): makeEnv(), sofr(), TEST(), tiief()

### Community 79 - "ApiError"
Cohesion: 0.06
Nodes (24): ApiError, _fetch_fx(), _refresh(), _run_fetch(), run_refresh(), _why(), _business_days_before(), _changes() (+16 more)

### Community 80 - "daycount.cpp"
Cohesion: 0.16
Nodes (8): dayCountFromString(), dayCountName(), periodFraction(), yearFraction(), DayCount.DayCountName, DayCount.ParseACT360, DayCount.PeriodFractionACT365IsOneOverFreq, DayCount.YearFractionACT360

### Community 81 - "test_portfolio.py"
Cohesion: 0.11
Nodes (19): app(), client(), insert_raw_trade(), test_irs_without_fixed_rate_fails_clearly(), _insert_raw(), test_corrupt_rows_report_error_and_rest_is_valued(), test_create_invalid_is_400_with_field(), test_create_list_and_delete_is_refused() (+11 more)

### Community 82 - "test_scenario_sets.py"
Cohesion: 0.10
Nodes (48): _assert_same_scenarios(), _combined(), _count(), _create(), _err(), _list(), _run_inline(), _run_set() (+40 more)

### Community 83 - "test_xccy_product.py"
Cohesion: 0.11
Nodes (43): empty_portfolio(), _book(), _compound(), _context(), _event(), _fix_at_spot(), _flows(), _load_market_fixings() (+35 more)

### Community 84 - "FxOption"
Cohesion: 0.07
Nodes (12): FxForward, domesticCurve_, foreignCurve_, pair_, FxSide, Buy, Sell, FxOption (+4 more)

### Community 85 - "python_web/app.py"
Cohesion: 0.24
Nodes (12): api_bond(), api_greeks_surface(), api_implied_vol(), api_model_convergence(), api_payoff(), api_price(), api_price_heston(), api_swap() (+4 more)

### Community 86 - "now_iso"
Cohesion: 0.07
Nodes (22): now_iso(), get_ref(), get_settings(), put_ref(), put_settings(), _builtin(), _builtin_named(), create_set() (+14 more)

### Community 87 - "designate"
Cohesion: 0.12
Nodes (40): designate(), _body(), _book_at(), _clock(), _codes(), _counts(), _fixed_loan(), _fx() (+32 more)

### Community 88 - "TEST"
Cohesion: 0.09
Nodes (13): OisQuote, days, rate, type, Type, Deposit, Ois, bootstrapOis() (+5 more)

### Community 89 - "R2 Pricers: POST /api/price/<producto>"
Cohesion: 0.18
Nodes (14): Opciones vainilla europeas USDMXN con Garman-Kohlhagen, Volatilidad tomada de la superficie por plazo y strike, Modelo Garman-Kohlhagen para opciones FX, Modelo Hull-White (cap/floor, swaption), Paridad put-call, Portafolio de ejemplo de al menos 6 operaciones (irs TIIE-F, irs SOFR, fx_forward, fx_option, cap_floor), R13 Semilla de demostracion en primer arranque con base vacia, Producto cap_floor (Hull-White) (+6 more)

### Community 90 - "fetch_equity"
Cohesion: 0.16
Nodes (7): fetch_equity(), _make_ticker_mock(), test_fetch_equity_option_chain_empty_falls_back_to_hv30(), test_fetch_equity_option_iv_nan_falls_back_to_hv30(), test_fetch_equity_raises_when_hv30_hist_empty(), test_fetch_equity_raises_when_hv30_insufficient_rows(), test_fetch_equity_uses_hv30_when_no_options()

### Community 91 - "CVA Engine Design"
Cohesion: 0.28
Nodes (3): CVA Engine Design, CVACalculator DVA/FVA Extension (P1), XVA Python Tests

### Community 92 - "QF Desk: workstation de valuacion de derivados"
Cohesion: 0.17
Nodes (11): P10: rama desde master y commits con GRAPHIFY_SKIP_HOOK=1; ultimo commit de T15 sin esa variable, QF Desk: workstation de valuacion de derivados, R3 Portafolio: CRUD de operaciones y valuacion, GET /api/portfolio/valuation?snapshot=<id>: PV por operacion y PV total en MXN, R9 Portafolio UI: blotter ordenable, filtrable y revaluado al cambiar snapshot, Fila de total, borrar operacion y exportar a CSV, Rama de trabajo feat/qf-desk, Pantallas de pricing Bloomberg SWPM y OVML (referencia visual) (+3 more)

### Community 93 - "R8 Pricers UI: formulario por producto con resultado y grafica"
Cohesion: 0.17
Nodes (13): P3: cap/floor y swaption con Hull-White; a y sigma por curva en el snapshot, P7: payoff al vencimiento es presentacion y puede vivir en el frontend; PV y griegas siempre del backend, Escalera de DV01 por plazo en barras, una serie por curva, R10 Riesgo UI: escalera DV01, tabla de escenarios y tarjeta VaR, Tarjeta de VaR con horizonte y confianza editables, Grafica de tasa cero y forward mas tabla de cotizaciones editable, Mapa de calor de superficie de vol plazo x strike, R7 Mercado UI: curvas, cotizaciones editables, superficie y spot (+5 more)

### Community 94 - "test_events_api.py"
Cohesion: 0.15
Nodes (40): _build_trades(), event_rows(), _five_dates(), get_state(), iso(), new_trade(), post(), test_any_event_after_a_termination_is_409_and_inserts_nothing() (+32 more)

### Community 95 - "test_fixings_fetch.py"
Cohesion: 0.13
Nodes (31): FakeResponse, fixture_bytes(), http_error(), no_real_token(), post(), served(), serve(), fake_urlopen() (+23 more)

### Community 96 - "test_backup.py"
Cohesion: 0.10
Nodes (26): backup(), BackupError, _copies(), _copy(), _free_name(), _integrity(), main(), _open_ro() (+18 more)

### Community 97 - "test_fixings.py"
Cohesion: 0.11
Nodes (37): _count(), _csv(), _list(), loaded(), _post(), test_add_exact_duplicate_is_200_not_created_and_no_new_row(), test_add_fixing_returns_201_with_fixing(), test_csv_bad_row_on_line_3_names_the_row_and_saves_nothing() (+29 more)

### Community 99 - "create_app"
Cohesion: 0.08
Nodes (24): create_app(), _seed_if_empty(), seed_market(), build_corte1_db(), golden_pv(), _load(), test_existing_base_without_the_table_recovers_it_when_the_app_is_recreated(), test_summary_without_seed_lists_the_three_factors_empty() (+16 more)

### Community 100 - "R11 Metodologia: pagina por producto con modelo, convenciones y limites"
Cohesion: 0.17
Nodes (9): Directorio desk/ (todo lo nuevo), desk/ui: frontend, Frontend React 18 + TypeScript + Vite, python_web/ sin tocar, P4: as_of 2026-11-10, dias naturales, t = dias/365, SOFR en periodos de 365 dias, P5: bond con clase Bond uniforme y curva TIIE-F por defecto; convencion M-Bono fuera de alcance, P9: fechas de flujo derivadas de parametros y as_of del snapshot, R11 Metodologia: pagina por producto con modelo, convenciones y limites (+1 more)

### Community 101 - "Snapshot sembrado MX-DEMO"
Cohesion: 0.21
Nodes (10): Snapshot sembrado MX-DEMO, SOFR: swap OIS, cupones anuales, ACT/360, Tasa flotante TIIE-F compuesta diaria, TIIE de Fondeo: swap OIS, cupones cada 28 dias, ACT/360, Forward USDMXN por paridad cubierta de tasas, Curva SOFR, Curva TIIE-F, Comprobacion: fx_forward = N(S*DF_usd - K*DF_mxn) a 1e-8 relativo (+2 more)

### Community 102 - "test_ops_settlements.py"
Cohesion: 0.12
Nodes (30): confirmations(), confirmation_event(), events_in_db(), iso(), settle(), settled_coupon(), test_a_confirmation_changes_neither_valuation_nor_pnl_nor_flows(), test_a_currency_that_is_not_the_flows_is_409() (+22 more)

### Community 103 - "test_ops_recon.py"
Cohesion: 0.15
Nodes (31): own_pv(), _csv(), _dv01(), _off_market(), _row(), _run(), _spot(), test_a_day_when_the_trade_is_not_alive_does_not_widen_the_date_range() (+23 more)

### Community 104 - "TEST"
Cohesion: 0.08
Nodes (10): bootstrapXccyDiscount(), trialCurve(), validate(), basisSwapNpv(), demoBasis(), demoForwards(), envWith(), sofr() (+2 more)

### Community 105 - ".price"
Cohesion: 0.17
Nodes (4): Bond::calculatePV(), CapFloor::calculatePV(), Swaption::calculatePV(), PyIPricingEngine

### Community 106 - "swaps.js"
Cohesion: 0.35
Nodes (9): formatCurrency(), getCurve(), hideSwError(), priceRegular(), priceScheduled(), setLoading(), setMode(), showResults() (+1 more)

### Community 107 - "test_counterparties.py"
Cohesion: 0.10
Nodes (25): currency_on(), _iso(), set_collateral(), _alfa_id(), _conn(), _listing(), _put(), test_a_change_on_the_same_date_as_the_last_one_is_accepted_and_the_later_event_wins() (+17 more)

### Community 108 - "test_ops_schema.py"
Cohesion: 0.07
Nodes (15): _insert_run(), _sql(), test_confirmation_does_not_change_pnl_or_flows(), test_existing_database_without_the_new_tables_recovers_them(), test_fpml_export_and_import_responses(), test_other_transfers_still_count(), test_reconciliation_id_that_cannot_exist_is_404_id(), test_reconciliation_rows_survive_a_rejected_change() (+7 more)

### Community 109 - "Lista de dependencias permitidas"
Cohesion: 0.24
Nodes (9): P13: tipografia Source Sans 3, Source Serif 4 y paleta calida; reemplaza fuentes de P1, P1: jsdom aprobado como dependencia de desarrollo; fuentes empaquetadas sin CDN, Barra superior: selector global de snapshot y distintivo Datos sinteticos, R6 Marco: tema oscuro denso tipo terminal, Navegacion lateral: Mercado, Pricers, Portafolio, Riesgo, Metodologia, Paleta de comandos Ctrl+K que lleva a pantallas y pricers, cmdk (paleta de comandos), react-router-dom (navegacion) (+1 more)

### Community 110 - "Fecha de valuacion: descuenta solo futuros, compone fijaciones del periodo en curso"
Cohesion: 0.29
Nodes (5): OisSwap (extension en C++ para periodo en curso), Corte 2 R3: envejecimiento de swap a la par, valor proyectado 1e-6 x nocional, Selector global: de snapshot a fecha de valuacion, Deuda corte 1: pv de filas FX en USD mientras /api/price da MXN, qfpy (bindings Python de Quant_Finance)

### Community 111 - "Corte 2: la operacion con vida y el mercado con historia"
Cohesion: 0.06
Nodes (26): Carril comercial: aviso legal de valuacion antes de cualquier piloto, Carril comercial: tres conversaciones con tesoreros o contralores antes del corte 4, Corte 2: la operacion con vida y el mercado con historia, Corte 3: curvas MXN multi-curva y cross currency swap, Corte 3 R2: forwards USDMXN implicitos coinciden con puntos forward cotizados, Corte 4: contabilidad de coberturas IFRS 9, Advertencia: contador con experiencia IFRS 9 debe revisar diseno y resultado, Corte 5: operaciones (flujos, confirmaciones, conciliacion) (+18 more)

### Community 112 - "VolSurface (P4a) - Implied-Vol Surface"
Cohesion: 0.29
Nodes (4): HestonCalibrator (P3) - Heston Calibration, VolSurface C++ Tests, VolSurface Python Tests, VolSurface (P4a) - Implied-Vol Surface

### Community 113 - "stdexcept"
Cohesion: 0.09
Nodes (14): FxOptionGreeks, delta, forward, gamma, price, vega, vol, FxForward::delta() (+6 more)

### Community 116 - "RootFinding"
Cohesion: 0.08
Nodes (13): gaussLegendre(), glNodesWeights(), simpson(), Root Finding Methods, brent(), newtonRaphson(), Integration.GaussLegendreGaussian, Integration.GaussLegendrePolynomial (+5 more)

### Community 117 - "iso_date"
Cohesion: 0.08
Nodes (15): add_fixing(), _download(), fetch_fixings(), list_sources(), _request_range(), _token(), _why(), import_csv() (+7 more)

### Community 122 - "test_factor_history.py"
Cohesion: 0.10
Nodes (29): window(), _csv(), _fixings(), _live_sources(), _rows(), test_csv_accepts_bom_and_crlf(), test_csv_bad_header_is_400_csv(), test_csv_bounds_are_inclusive() (+21 more)

### Community 123 - "capfloor.cpp"
Cohesion: 0.20
Nodes (9): Caplet, tEnd, value, CapFloor::CapFloor(), CapFloor::caplets(), CapFloor::price(), CapFloor::priceDualCurve(), hwBondOption() (+1 more)

### Community 124 - "test_hedges_dedesignation.py"
Cohesion: 0.16
Nodes (28): _close(), _counts(), _dedesignate(), _detail(), _events(), _hedge(), _loan(), _snapshot() (+20 more)

### Community 125 - "QF Desk Corte 7 - diseno (validacion contra QuantLib)"
Cohesion: 0.07
Nodes (20): QF Desk Corte 7 - diseno (validacion contra QuantLib), Archivos compartidos a minimizar: app.py, Shell.tsx, App.tsx, api/types.ts, api/client.ts, MethodologyScreen.tsx, compare.py - une cases y reference y escribe report.json, Entornos conda: pyfinance, qlib, openbb, base, qfvalid (pip install QuantLib), Modulo desk/validation/, export_cases.py - escribe cases.json con Python del backend, Fuera de alcance: ORE, validacion de XVA, VaR, DV01, contabilidad de coberturas y datos de mercado de proveedor, GET /api/validation/report (+12 more)

### Community 126 - "settled_flows"
Cohesion: 0.12
Nodes (16): bond_settled(), _grouped(), _row(), _trade_rows(), _fix(), _flow(), _forward_settlement(), _fx_fallback() (+8 more)

### Community 127 - "bonds.js"
Cohesion: 0.33
Nodes (7): calcBond(), fetchYieldCurve(), getCurveData(), hideError(), renderYieldCurve(), setLoading(), showError()

### Community 128 - "Greeks Calculator"
Cohesion: 0.31
Nodes (8): HullWhite::simulate(), Greeks Calculator, delta(), dv01(), gamma(), rho(), theta(), vega()

### Community 130 - "test_collateral_valuation.py"
Cohesion: 0.15
Nodes (28): trade_with(), _book(), _close(), _context(), _dv01(), _parity_snapshot(), _rows(), _sql() (+20 more)

### Community 131 - "connect"
Cohesion: 0.09
Nodes (34): connect(), _hand_cap(), test_cap_aged_30_days_values_only_the_caplets_that_have_not_fixed(), test_cap_whose_caplet_fixes_on_the_snapshot_date_keeps_it_at_intrinsic_value(), test_on_the_trade_date_the_aged_value_is_the_price(), test_sofr_cap_ages_with_annual_periods_and_values_in_mxn(), test_without_method_the_json_is_the_parametric_one(), test_load_context_unknown_snapshot_is_404() (+26 more)

### Community 132 - "desk/api: backend"
Cohesion: 0.28
Nodes (7): desk/api: backend, Backend sirve dist/ del frontend en puerto 5070, Backend Flask sobre bindings qfpy, Interprete Python 3.8 de anaconda, R12 Arranque y pruebas, Pruebas de aceptacion: ctest completo, pytest desk/api/tests, npm test y npm run build, desk/run.sh: construye la interfaz y levanta todo en el puerto 5070

### Community 133 - "CRUD /api/trades persistido en SQLite; sobrevive reinicios"
Cohesion: 0.25
Nodes (6): Persistencia en sqlite3 (desk/data/desk.db), P11: irs guardado exige fixed_rate; POST /api/trades sin fixed_rate responde 400, P12: cotas de entrada periods <= 1200, dias de vencimiento <= 18250, anos <= 50, CRUD /api/trades persistido en SQLite; sobrevive reinicios, R5 Errores: entrada invalida responde 400 o 404 con JSON error y field, Boton Agregar al portafolio que crea la operacion

### Community 134 - "Tasa cero y tasa forward"
Cohesion: 0.31
Nodes (9): Factor de descuento, Tasa cero y tasa forward, Tasa par de un swap, Comprobacion: tras +10 pb en TIIE-F, todo factor de descuento a plazo >0 baja, GET /api/market/snapshots/<id>: cotizaciones y por curva plazo, tasa cero, factor de descuento y forward, GET /api/market/snapshots lista snapshots, R1 Mercado: snapshot MX-DEMO, curvas, spot y superficie, PUT /api/market/snapshots/<id> cambia cotizaciones y recalcula curvas (+1 more)

### Community 135 - "Decision: QuantLib en Python como referencia principal de validacion"
Cohesion: 0.40
Nodes (4): ORE como segunda referencia solo si un prospecto la pide (XVA y exposicion), Corte 7 R1: arnes que valua portafolio en QF Desk y referencia, diferencia por operacion, Fuente: Open Source Risk Engine (LSEG), QuantLib

### Community 137 - "export_cases.py"
Cohesion: 0.10
Nodes (18): test_build_incluye_los_62_casos_junto_a_las_curvas(), mkt(), test_build_arma_el_documento_completo(), test_check_days_son_diez_y_estrictamente_interiores(), test_export_curves_trae_diez_pilares_con_el_df_exacto_del_desk(), test_las_fechas_intermedias_estan_dentro_de_los_pilares(), check_days(), _battery_raw() (+10 more)

### Community 138 - "test_hedges_release.py"
Cohesion: 0.16
Nodes (28): _cents(), _counts(), _dedesignate(), _dedesignate_after_close(), _loan(), _negative_reserve(), _ori_cents(), _positive_reserve() (+20 more)

### Community 139 - "par_irs"
Cohesion: 0.21
Nodes (27): par_irs(), _effectiveness(), _fixed_loan(), _fx(), _hedge(), _loan(), _ok(), _ratios() (+19 more)

### Community 140 - "test_integration_cortes.py"
Cohesion: 0.12
Nodes (25): _coupon_rows(), desk(), _explain_with_spot(), _get(), _move_csa_quotes(), _reconcile(), _roll_with_fixings(), _settle() (+17 more)

### Community 141 - "MarketContext"
Cohesion: 0.13
Nodes (14): aged_bond(), aged_cap_floor(), _bond_curve(), bond_pv_mxn(), bond_quote(), cap_floor_pv_mxn(), _coupon_amount(), _discount_key() (+6 more)

### Community 142 - "compare.py"
Cohesion: 0.10
Nodes (19): gap(), f(), test_el_reporte_versionado_trae_los_pasos_de_compare(), test_la_salida_de_consola_concuerda_en_numero(), test_classify(), classify(), now_iso(), _case_rows() (+11 more)

### Community 143 - "test_validation_report.py"
Cohesion: 0.12
Nodes (20): test_diffs(), _close(), known(), _load_known(), _load_report(), _problems(), _reescribir_a_mano(), report() (+12 more)

### Community 144 - "state"
Cohesion: 0.24
Nodes (24): state(), day(), ev(), make_trade(), test_events_in_any_order_give_the_same_state(), test_execution_reset_and_transfer_do_not_change_the_state(), test_exercise_makes_it_ejercida_and_never_vencida(), test_not_agreed_wins_over_everything_else() (+16 more)

### Community 145 - "test_limits.py"
Cohesion: 0.14
Nodes (23): _change(), _make(), _row(), _sql(), test_breach_records_the_amount_in_force(), test_change_inserts_event_and_limits_row_stays(), test_check_ignores_alerts_and_retired_limits(), test_check_inserts_one_breach_per_limit_and_is_idempotent() (+15 more)

### Community 146 - "Auditoria independiente QF Desk corte 7 (validacion contra QuantLib)"
Cohesion: 0.07
Nodes (16): Auditoria independiente QF Desk corte 7 (validacion contra QuantLib), Alcance: rama corte7, commits ce51edf..ce01c28 (13 commits de Claudio), auditado contra design.md sin leer plan.md, Construido sin que ningun R lo pidiera: seccion Curvas, columna Metodo de referencia, aviso desk_dirty, validationFixture.ts, Entrada defect de known_differences.json para swaption-04, Regresiones: ninguna encontrada, T7-swaption-repro.py: reproduce las 8 diferencias de swaption con cociente 0.99-1.015, Segunda ronda: commits dc99a0e..37153d8 (4 commits) revisados; sin NO CUMPLE, Suite backend pytest desk/api/tests: 2365 passed primera ronda, 2373 segunda (+8 more)

### Community 147 - "fetch_treasury_curve_fred"
Cohesion: 0.29
Nodes (4): fetch_treasury_curve_fred(), _make_fred_response(), test_fetch_treasury_curve_fred_raises_on_no_data(), test_fetch_treasury_curve_fred_returns_yield_curve()

### Community 150 - "test_xva.py"
Cohesion: 0.57
Nodes (5): _make_env(), _make_hw(), _quarterly(), test_cva_positive_for_itm_receiver(), test_result_to_dataframe()

### Community 151 - "choice"
Cohesion: 0.16
Nodes (21): _domestic(), _equity_bs(), _equity_describe(), _equity_price(), _equity_pv_mxn(), _equity_validate(), _fx_describe(), _fx_forward() (+13 more)

### Community 152 - "test_skeleton.py"
Cohesion: 0.53
Nodes (4): _assert_error(), test_malformed_json_on_trades_is_400(), test_unknown_product_is_404_on_product(), test_unknown_route_is_json_404()

### Community 153 - "settled"
Cohesion: 0.11
Nodes (13): _describe(), _price(), _pv_mxn(), _swap(), aged_xccy(), discount_curve(), projected(), pv_mxn() (+5 more)

### Community 155 - "test_hist_var.py"
Cohesion: 0.15
Nodes (22): _correlated_days(), _hist(), _insert_live_snapshot(), _load_csv(), _ok(), _series(), test_default_is_synthetic_250_days_with_contract_shape(), test_empty_portfolio_has_zero_var() (+14 more)

### Community 194 - "test_trades_dates.py"
Cohesion: 0.22
Nodes (23): _body(), _iso(), _mat(), _post(), _sql(), test_create_with_dates_stores_three_dates_and_one_execution(), test_date_order_rules_name_the_offending_field(), test_defaults_come_from_mx_demo_as_of() (+15 more)

### Community 348 - "test_ops_cashflows.py"
Cohesion: 0.06
Nodes (52): report_csv(), cashflows_csv(), _money(), _read_csv(), confirm_raw(), _get(), _new_bond(), _pv() (+44 more)

### Community 359 - "confirm_settlement"
Cohesion: 0.13
Nodes (11): _confirmation_events(), _decode(), insert_event(), load_all_events(), load_events(), post_event(), _terms_data(), confirm_settlement() (+3 more)

### Community 360 - "hedge_effectiveness.py"
Cohesion: 0.13
Nodes (11): assess(), critical_terms(), effectiveness(), _pv(), _require_live(), _same_amount(), _term(), _cents() (+3 more)

### Community 361 - "value_trade"
Cohesion: 0.13
Nodes (11): _model_swap_inputs(), test_public_helpers_build_the_instrument_value_trade_prices(), accrued_factor(), aged_swap(), _irs_pv(), is_live(), normalized(), _sensitive_to_mxn_discount() (+3 more)

### Community 362 - "test_hedges_report.py"
Cohesion: 0.20
Nodes (21): _cents(), _close(), _csv_rows(), _dedesignate(), _hedge(), _loan(), _report(), test_a_relationship_without_closes_reports_empty_sections() (+13 more)

### Community 363 - "limits.py"
Cohesion: 0.18
Nodes (11): add_event(), _breach_dict(), check(), create_limit(), _event_dict(), list_breaches(), list_limits(), _load() (+3 more)

### Community 364 - "test_pnl.py"
Cohesion: 0.18
Nodes (20): test_bond_pnl_across_its_maturity_includes_the_redemption(), test_bond_pnl_over_200_days_is_the_value_change_plus_the_settled_coupons(), _assert_adds_up(), _pnl(), test_cap_maturing_in_the_window_warns_that_it_has_no_settlement_but_a_bond_does_settle(), test_exercise_transfer_adds_to_settled(), test_from_later_than_to_is_rejected_on_the_to_field(), test_last_coupon_at_maturity_counts_as_settled() (+12 more)

### Community 365 - "xccy_swap.cpp"
Cohesion: 0.14
Nodes (17): buildPeriods(), discountAt(), LegRow, accrual, amount, day, df, kind (+9 more)

### Community 366 - "ops_confirm.py"
Cohesion: 0.30
Nodes (16): _bond(), _business_days(), _buy_sell(), _cap_floor(), confirmation(), _equity_option(), _events_note(), _fx_forward() (+8 more)

### Community 367 - "D5 Conciliación con el banco"
Cohesion: 0.09
Nodes (21): Construido extra: límite de 5000 filas y bank_only por contraparte distinta, Construido extra: GET/PUT trades ref y GET /api/settings, Construido extra: regla explicable por spot ±1 % en FX, Defecto baja: bandera de términos ciega cerca de la par, Corregido (documentado) en Metodología: bandera ciega cerca de la par, Veredicto R5: CUMPLE (conciliación casos a-e), Veredicto R7: CUMPLE (sección Operaciones en Metodología), Descomposición: desplazamiento paralelo de curva en pb (Newton con DV01) (+13 more)

### Community 368 - "roll"
Cohesion: 0.20
Nodes (15): roll(), rolled(), _assert_identity(), _explain(), _get(), _gross_notional_mxn(), test_cascade_failure_sends_the_pnl_to_residual(), test_errors() (+7 more)

### Community 369 - "test_hedges_schema.py"
Cohesion: 0.16
Nodes (11): _db(), _hedge_by_sql(), _sql(), test_a_corte2_database_recovers_the_three_tables_without_losing_trades(), test_detail_of_a_relationship_inserted_by_sql(), test_hedge_tables_reject_update_and_delete(), test_hypothetical_trade_is_an_in_memory_trade_that_never_reaches_the_trades_table(), test_periods_and_dedesignation_show_up_in_the_detail_and_the_summary() (+3 more)

### Community 370 - "sys"
Cohesion: 0.24
Nodes (5): _load_real_qfpy(), _load_real_qfpy(), _load_real_qfpy(), _load_real_qfpy(), _load_real_modules()

### Community 371 - "test_validation_cases.py"
Cohesion: 0.12
Nodes (8): by_id(), cases(), env(), mkt(), test_el_documento_es_serializable_y_sin_no_finitos(), test_los_rotulos_concuerdan_en_numero_con_la_cantidad(), test_rotulos_no_vacios_y_en_espanol(), test_siete_casos_de_portafolio_con_trade_id_1_a_7_y_primeros_de_su_producto()

### Community 372 - "market_forward"
Cohesion: 0.16
Nodes (11): _book(), frozen_clock(), _iso(), market_forward(), _snapshot_as_of(), _codes(), _fx_item(), test_a_forecast_flow_on_a_mexican_holiday_warns_with_its_name() (+3 more)

### Community 373 - "test_risk_lifecycle.py"
Cohesion: 0.27
Nodes (16): _all(), _approx(), _csv(), _dv01(), _iso(), _roll(), _scenario_ids(), _scenarios() (+8 more)

### Community 374 - "test_ExposureProfile.cpp"
Cohesion: 0.14
Nodes (4): flatCurve(), mixedNettingSet(), quarterlyDates(), TEST()

### Community 375 - "dependencies"
Cohesion: 0.10
Nodes (18): dependencies, ag-grid-community, cmdk, echarts, @fontsource/source-sans-3, @fontsource/source-serif-4, react, react-dom (+10 more)

### Community 376 - "D3 Confirmación de operación"
Cohesion: 0.11
Nodes (16): Construido extra: edición del nombre de empresa en pantalla de confirmación, Defecto baja: aviso de fijaciones faltantes lista 117 días, Defecto baja: control de archivo nativo en inglés, Defecto media: calendario del irs muestra solo pierna fija sin aclararlo, Corregido: aviso resumido con y 111 más, Corregido: FilePicker propio con textos en español, Corregido: concepto indica que es solo pierna fija, Observación R6: snapshot de conciliación se elige con el selector global (+8 more)

### Community 377 - "Veredicto R1 P&L explicado: CUMPLE"
Cohesion: 0.12
Nodes (16): Nota R1: operaciones nuevas y eventos solo cubiertos por tests del implementador (test_pnl_explain.py), no reproducidos por HTTP, R1 prueba: roll mas TIIE-F +25 pb, SOFR -25 pb, spot +3 por ciento; total 677,380.25 con componentes carry, TIIE-F, SOFR, FX y residuo 0.0, R1 prueba: roll de MX-DEMO a 2026-12-10 con mercado identico, total -642,470.13 MXN, 100 por ciento en paso del tiempo, R1 prueba: suma de componentes contra /api/pnl con diferencia 0.0 por operacion y en total, Veredicto R1 P&L explicado: CUMPLE, Veredicto R8 Sin regresion: CUMPLE, Base del corte 6: cortes 1, 2 y 4 de QF Desk, GET /api/pnl/explain?from=&to= (P&L explicado por operacion y total) (+8 more)

### Community 378 - "_rel"
Cohesion: 0.21
Nodes (5): AgedBondTests, AgedCapFloorTests, _curve(), _flat(), _rel()

### Community 379 - "reconcile_trade"
Cohesion: 0.14
Nodes (10): business_day(), context_at(), _date_factor(), _describe(), _newton(), reconcile_trade(), test_context_at_keeps_the_collateral_and_the_mxn_usd_quotes(), test_business_day_skips_weekends() (+2 more)

### Community 380 - "test_xccy_py.py"
Cohesion: 0.22
Nodes (6): _curve(), _env(), _load_real_qfpy(), OisDiscountCurveKey, _swap(), XccySwapBindings

### Community 381 - "collateral.py"
Cohesion: 0.26
Nodes (7): change_collateral(), _currency_of(), _events_by_counterparty(), history(), list_counterparties(), _public(), _trade_counts()

### Community 382 - "create_run"
Cohesion: 0.18
Nodes (8): create_run(), _csv_error(), get_run(), list_runs(), _pair(), _parse_row(), _summary(), refs_by_counterparty()

### Community 383 - "events.py (insert_event, cambios delimitados con corte 5)"
Cohesion: 0.13
Nodes (14): Construido extra: confirmación de liquidación también vía POST /events, Construido extra: snapshot opcional en /settlements y 409 por moneda, Defecto nuevo baja: insert_event recorre todos los eventos y parsea cada transfer, Defecto baja: confirmaciones encadenadas en prev_event_id, events.py (insert_event, cambios delimitados con corte 5), Corregido: insert_event salta confirmaciones al elegir prev, Segunda ronda: ninguna regresión encontrada, Veredicto R1: CUMPLE (calendario cuadra con PV) (+6 more)

### Community 384 - "exposure_profile.cpp"
Cohesion: 0.12
Nodes (7): ExposurePoint, ene, epe, pfe, t, PYBIND11_MODULE(), simulateExposure()

### Community 385 - "swaption.cpp"
Cohesion: 0.19
Nodes (10): SwaptionType, Payer, Receiver, hwB(), hwSigmaP(), hwVariance(), hwZCBOption(), Swaption::price() (+2 more)

### Community 386 - "init_schema"
Cohesion: 0.19
Nodes (5): init_schema(), _abort(), is_v1(), migrate_v1(), _plan()

### Community 387 - "test_market_roll.py"
Cohesion: 0.21
Nodes (7): _error(), test_a_suffix_that_is_not_at_the_end_of_the_label_is_kept(), test_invalid_as_of_is_400(), test_invalid_id_is_400(), test_repeated_id_is_409(), test_rolling_mkt_live_gives_editable_copy(), test_unknown_source_is_404()

### Community 388 - "C7 Declaraciones en Metodologia y reporte: reciclaje con hipotetico proxy, componente de tasa, causa obligatoria"
Cohesion: 0.15
Nodes (10): Observacion abierta 5: ajuste de partida en valor razonable incluye devengo (6.5.8(b)); no se detecta por pruebas, Observacion abierta 7: simplificaciones aceptables pero no todas declaradas (base, costo, momento de reciclaje), Veredicto C2: CORREGIDO con hueco (si la operacion termino no se mide hasta la terminacion, N-2), Veredicto C7: CORREGIDO, hedgeDeclarations.ts como fuente unica para Metodologia y reporte, Defecto D-2 (media): la desdesignacion no mide hasta su fecha; frozen_oci es el saldo del ultimo cierre, Observacion contable 3: momento del reciclaje, debe ser cuando afecta resultados (6.5.11(d)), Observacion contable 5: desdesignacion voluntaria sin causa prohibida por 6.5.6, Observacion contable 6: valor razonable mide con swap a tasa par y no amortiza el ajuste (6.5.8, 6.5.10) (+2 more)

### Community 389 - "R11 Metodologia declara hipotetico, regla del menor, reciclaje, asientos sugeridos, simplificaciones y revision pendiente"
Cohesion: 0.17
Nodes (12): Veredicto R11: CUMPLE, metodologia con hipotetico, regla del menor y simplificaciones, Fuera de alcance: ajuste de base para partidas no financieras, Fuera de alcance: costo de cobertura (base de divisa, puntos forward), Fuera de alcance: riesgo de credito CVA/DVA en la efectividad, Fuera de alcance: revelaciones de IFRS 7, Fuera de alcance: coberturas de inversion neta, Fuera de alcance: libro mayor y polizas reales, Fuera de alcance: opciones como instrumento de cobertura y su valor temporal (+4 more)

### Community 390 - "XccyBootstrapBindings"
Cohesion: 0.27
Nodes (4): _basis(), _forwards(), _ois_curve(), XccyBootstrapBindings

### Community 391 - "R1 SOFR real desde la Fed de Nueva York"
Cohesion: 0.17
Nodes (5): D3 Rango de FixingsPanel sin tope supera 366 dias (baja), Veredicto R1 SOFR real: CUMPLE, Lista conflicts en la respuesta de fetch, API SOFR de la Fed de Nueva York, R1 SOFR real desde la Fed de Nueva York

### Community 392 - "_post"
Cohesion: 0.22
Nodes (9): _count(), _post(), test_a_4xx_or_a_failure_while_computing_leaves_nothing_stored(), test_body_validation_order_and_fields(), test_both_tables_are_insert_only(), test_csv_errors_are_400_csv_with_the_line_and_write_nothing(), test_same_trade_by_id_and_by_resolved_reference_is_a_duplicate(), test_tolerance_out_of_range_is_400() (+1 more)

### Community 393 - "D4 Medicion por periodo: reserva OCI por regla del menor, inefectividad, reciclaje e identidad de control"
Cohesion: 0.18
Nodes (9): Veredicto R3: CUMPLE, regla del menor verificada por fuera al 1e-6, Veredicto R4: CUMPLE, asientos cuadran y identidad con /api/pnl, Veredicto R5: CUMPLE, reciclaje en cupones y cierre final del forward, Endpoint POST /api/hedges/<id>/periods (cierre de periodo con snapshot), Endpoint GET /api/pnl (P&L de referencia para la identidad de control), R3 Regla del menor: caso sobrecubierto 120 por ciento y subcubierto 80 por ciento; signos opuestos dan OCI cero, R4 Asientos cuadran al centavo por periodo y en acumulado; identidad de control a 1e-6 MXN y coincidencia con /api/pnl, R5 Reciclaje: asiento Efectivo contra reciclaje en cupones; reserva en 0 al vencer forward designado (+1 more)

### Community 394 - "D5 CVA y exposicion usando qf::xva existente en C++, expuesto en qfpy en serie y solo en este worktree"
Cohesion: 0.22
Nodes (9): Construido sin R: qf::xva simulate_exposure (EPE, ENE, PFE) con test GoogleTest y test de bindings, permitido por D5, Perfil de exposicion esperada (EE) y PFE 95 por ciento en rejilla mensual hasta el ultimo vencimiento, por contraparte, Producto no cubierto por el modulo existente se excluye con aviso, Modulo qf::xva en C++ (include/qf/xva/) y sus tests, a exponer en qfpy lo que falte, Curva de riesgo plana por contraparte: por omision 1 por ciento de hazard y 40 por ciento de recovery, rotulado como supuesto, Tabla counterparty_credit(counterparty_id, hazard_rate, recovery, as_of): solo insercion; counterparties no se toca, Fuera de alcance: VaR por revaluacion completa y Monte Carlo del portafolio; DVA, FVA y colateral en la exposicion; backtesting del VaR; limites con flujo de aprobacion (corte 8); curvas de credito con plazo, R4 Credito: EE y PFE no negativos, EE(0) igual a max(PV,0) por contraparte, PFE mayor o igual a EE, CVA cero con PD cero y creciente, cambios de parametros como fila nueva, productos no cubiertos listados con aviso (+1 more)

### Community 395 - "D3 VaR historico: revaluacion por sensibilidades (delta) con cambios historicos de los ultimos N dias"
Cohesion: 0.20
Nodes (10): R3 prueba: historia insuficiente da 409 window_days; window 59 da 400, R3 prueba: historia propia de 5000 dias correlacionados (Cholesky, semilla 777) cargada por CSV; recarga idempotente, R3 prueba: sin method y con method parametric dan JSON identico, R3 valores: VaR historico 99 por ciento 1d 3,359,451.64 contra parametrico 3,361,345.99 (-0.06 por ciento); ES 3,797,874.17 mayor o igual a VaR, Veredicto R3 VaR historico: CUMPLE, Deficit esperado (ES) al mismo nivel y fecha del peor dia; percentil empirico, Historia insuficiente produce HTTP 409 con mensaje, Interfaz muestra VaR parametrico e historico lado a lado (+2 more)

### Community 396 - "Tabla de interfaces core y sus implementaciones"
Cohesion: 0.20
Nodes (9): Tabla de interfaces core y sus implementaciones, CVACalculator: IRateModel, ICreditCurve, LGD, SimParams; Hull-White Monte Carlo sobre NettingSet, EngineFactory::makeEquityEngine BS/MC/BT/FDM, IEquityModel (qf::models): BlackScholesModel, HestonModel, IPricingEngine (qf::pricingengines): BS, MC, Binomial, FDM, Heston engines, IRateModel (qf::models): Vasicek, HullWhite, IUnderlying (qf::instruments) subyacentes de equity, Bindings qfxva (xva_bindings.cpp) y CVAResult.to_dataframe (+1 more)

### Community 398 - "desk_commit"
Cohesion: 0.27
Nodes (5): test_desk_commit_es_un_sha_de_40_hex_en_este_worktree(), test_desk_commit_sin_git_es_none(), desk_commit(), desk_dirty(), _git()

### Community 399 - "D1 Datos en SQLite (desk/api/db.py)"
Cohesion: 0.20
Nodes (7): Defecto baja 5: encabezado CSV debe ser exactamente index,date,value; rechaza BOM de Excel, Veredicto R7: CUMPLE (CSV atomico, 409, 400 con NaN e inf), R7 Fijaciones: alta manual y CSV, duplicados idempotentes, 409 valor distinto, 400 fuera de rango, warnings por faltante, Snapshots y operacion rodar (POST /api/market/<id>/roll), Tabla counterparties(id, name UNIQUE), Tabla fixings (index_name, fixing_date, value) con indices TIIE-F, SOFR y USDMXN, Tabla trades (identidad y terminos de origen, no se actualiza)

### Community 400 - "D4 Valuacion a fecha de valuacion (as_of del snapshot)"
Cohesion: 0.20
Nodes (6): Defecto baja 1: bono y cap/floor envejecidos con ceil de periodos no envejecen dentro del periodo, Defecto baja 4: fijaciones en dias naturales generan aviso missing_fixing permanente en fines de semana, Veredicto R12: CUMPLE (seccion Ciclo de vida y valuacion a fecha en MethodologyScreen.tsx), Veredicto R8: CUMPLE (forward FX vencido liquida 500000.0 en settled), R12 Metodologia declara eventos guardados vs derivados, regla de faltante, convencion de dias y limites, R8 Vencimiento: estado vencida, PV 0; forward FX vencido liquida con FIX USDMXN

### Community 401 - "Veredicto R5 Escenarios: CUMPLE"
Cohesion: 0.22
Nodes (9): Construido sin R: tipo de escenario combined (hasta 8 choques) en risk/scenarios.py, necesario para los historicos de D6, R5 prueba: crear 201, duplicado 409, listar, baja 200, correr dado de baja 404, R5: escenarios de fabrica Por omision (8), Depreciacion 2008, 2016 elecciones EE. UU., Marzo 2020, rotulados Aproximacion historica, R5 prueba: correr por set igual a en linea con diferencia 0.0 (Marzo 2020, Por omision y conjunto propio), Veredicto R5 Escenarios: CUMPLE, Ocho escenarios por omision mas historicos predefinidos (Depreciacion 2008, 2016 elecciones EE. UU., Marzo 2020), rotulados como aproximacion, POST /api/risk/scenarios acepta set por nombre, Tablas scenario_sets y scenario_set_events: solo insercion, baja logica por evento (+1 more)

### Community 402 - "Veredicto R4 Credito: CUMPLE en la letra, con defecto alto en coherencia del perfil (primera ronda)"
Cohesion: 0.22
Nodes (9): Defecto 1 ALTA (primera ronda): perfil EE/PFE y CVA incoherentes con el PV del desk; qfxva no reproduce el PV ni el signo (Alfa, Beta, Gamma), Defecto 2 MEDIA (primera ronda): EE(0) suma max(PV,0) por curva sin compensar entre monedas; contradice la letra de R4; corregido en segunda ronda, Defecto nuevo BAJA: queda diferencia de un cupon diario entre el ancla del desk y la simulacion en t cero (Alfa -86k, Beta -36k, Gamma -1.6k USD); la prueba test_simulated_swap_starts_at_the_desk_pv tolera 0.05 por ciento y usa sigma 1e-7, R4 valores: CVA 0 con hazard 0; 10,793 con 0.5 por ciento; 42,673 con 2 por ciento; 104,239 con 5 por ciento; 4 filas en counterparty_credit, R4: EE(0) = max(PV,0) exacto pero por sustitucion del punto t=0 con el PV del desk, no por la simulacion, R4: productos excluidos con aviso (fx_forward x2, cap_floor, fx_option) y aviso de CVA informativo en API y UI, Regresion: R1, R2, R3, R5 y triggers de solo insercion siguen igual en segunda ronda; UI sin desbordes a 1280 px y sin errores de consola, Veredicto R4 Credito: CUMPLE en la letra, con defecto alto en coherencia del perfil (primera ronda) (+1 more)

### Community 403 - "XccyCashFlow"
Cohesion: 0.20
Nodes (9): XccyCashFlow, accrual, amount, discountFactor, kind, leg, payDays, presentValue (+1 more)

### Community 404 - "OisAgedBindings"
Cohesion: 0.24
Nodes (4): _curve_26(), _df(), _env(), OisAgedBindings

### Community 405 - "test_validation_route.py"
Cohesion: 0.28
Nodes (3): _minimal_report(), report_app(), test_devuelve_el_reporte_con_commit_actual()

### Community 406 - "Auditoria independiente QF Desk corte 2 (feat/qf-desk, 35afa48..41f0a3f)"
Cohesion: 0.22
Nodes (9): Build UI npm run build exit 0 con aviso de chunk mayor de 500 kB, Defecto baja 6: test esqueleto saltado es codigo muerto, Defecto baja 9: CLAUDE.md del repo dice 153 tests de ctest, hoy son 402, Auditoria independiente QF Desk corte 2 (feat/qf-desk, 35afa48..41f0a3f), Test esqueleto saltado test_unimplemented_routes_answer_501_json con parametros vacios, Suite bindings qfpy: 56 tests OK incluye test_ois_aged_py, Suite C++ ctest: 402 tests pasan, Suite desk/api pytest: 2150 passed, 1 skipped (+1 more)

### Community 407 - "Tabla trade_events solo insercion con disparadores UPDATE/DELETE"
Cohesion: 0.22
Nodes (5): Defecto baja 8: post_event usa max sobre eventos y daria 500 si una operacion no tiene eventos, Veredicto R1: CUMPLE (201, evento execution, triggers bloquean UPDATE/DELETE), R1 Crear operacion guarda fechas y evento execution; UPDATE/DELETE bloqueados; tipo invalido 400, Tabla trade_events solo insercion con disparadores UPDATE/DELETE, Catalogo de tipos de evento (execution, reset, transfer, quantity_change, terms_change, exercise, termination)

### Community 408 - "D5 P&L entre dos fechas: endpoint GET /api/pnl?from&to"
Cohesion: 0.22
Nodes (6): Veredicto R10: CUMPLE (diferencia relativa 0.0 en 5 filas FX), Veredicto R6: CUMPLE (razon exacta 2.0 y 0.5 en nocional), D5 P&L entre dos fechas: endpoint GET /api/pnl?from&to, R10 pv de filas FX en /api/portfolio/valuation en MXN e igual a /api/price, R6 Cambio de nocional quantity_change escala PV desde su fecha, Funcion settled_flows(trade, d0, d1) para cupones y liquidacion derivados

### Community 409 - "OisSwap en C++ con periodo en curso iniciado y factor de capitalizacion acumulado"
Cohesion: 0.22
Nodes (7): Veredicto R3: CUMPLE (peor error 1.5e-15 frente a tolerancia 1e-6), Veredicto R4: CUMPLE (identidad P&L exacta, swap par pnl/N 2.2e-16), Funcion C++ compoundOvernight(tasas, dias, base) ACT/360, OisSwap en C++ con periodo en curso iniciado y factor de capitalizacion acumulado, Exposicion de OIS envejecido y compoundOvernight en qfpy, R3 Envejecimiento OIS a la par en C++ y Python con tolerancia 1e-6 x nocional, R4 Identidad de P&L: pnl = pv_to - pv_from + settled y suma por operacion

### Community 410 - "D6 DV01 por plazo incluye MXN-USD; escenarios y VaR la tratan como curva dependiente (declarado)"
Cohesion: 0.22
Nodes (8): D2 (baja) DECLARADO: R7 relativo fragil en portafolios con DV01 neto chico (convexidad del cap), D3 (baja) DECLARADO: R2 exacto solo cuando dias de cotizacion coinciden con pilares TIIE-F; MXN-USD sin pilar 1D, D7 (baja) DECLARADO: forward FX con colateral USD tiene sensibilidad casi cero a SOFR, R2 CUMPLE con salvedad: exacto solo en pilares TIIE-F; otros dias dan diferencia de DF hasta 2.7e-6, R7 CUMPLE (fragil): 0.79 por ciento en MX-DEMO pero 2.09 por ciento con bono de 100 M en portafolio neto chico, Veredicto final: R1-R12 cumplen; R5 sin salvedad; defectos abiertos solo bajos (D2, D3, D5, D6, D7), R2 Con puntos forward = paridad TIIE-F/SOFR y base cero, MXN-USD coincide con TIIE-F y PV con corte 2 (1e-8), R7 DV01 incluye MXN-USD; suma por plazo cuadra con el paralelo dentro del 2 por ciento

### Community 411 - "D2 Trabajo C++ en serie, comparten build/"
Cohesion: 0.25
Nodes (7): R5 CUMPLE: npv al parSpread -7.5e-9 con N=5M; PayUsd + PayMxn = 0; identidad P&L por HTTP, R6 CUMPLE de punta a punta por HTTP: pricer, alta a la par, portafolio, flujos, DV01 por curva, escenarios, VaR, terminacion, bootstrapXccyDiscount: devuelve pilares de MXN-USD desde cotizaciones, Todo lo nuevo expuesto en qfpy, R5 XccySwap: valor cero al parSpread, paga-USD y paga-MXN opuestos, identidad de P&L del corte 2, R6 xccy_swap de punta a punta: alta, portafolio, ficha, DV01 por curva, escenarios, VaR, P&L, terminacion, XccySwap: nocional constante, intercambios opcionales, npv en MXN, parSpread, flujos por pata

### Community 412 - "D4 Exportación e importación FpML"
Cohesion: 0.25
Nodes (8): Defecto media: importar FpML altera el vencimiento en silencio, Corregido: rechazo si el vencimiento no cae en periodos enteros, Veredicto R4: CUMPLE (11 variantes FpML ida y vuelta), GET /api/trades/<id>/fpml, POST /api/trades/fpml, Fuera de alcance: validación contra XSD de FpML, desk/api/fpml.py (solo xml.etree.ElementTree), R4 FpML ida y vuelta con al menos 3 variantes por producto

### Community 413 - "D4 Limites: scopes counterparty, factor y portfolio; metricas pv_exposure, dv01, fx_delta y var"
Cohesion: 0.28
Nodes (8): Construido sin R: el limite var queda fijo al VaR parametrico 1d 99 por ciento porque D4 no fija parametros, Construido sin R: regla de un solo limite activo por (scope, key, metric) que da 409, GET /api/limits/usage?snapshot= (uso, porcentaje y estado de cada limite), POST /api/limits/check?snapshot= (registra excesos nuevos, uno por limite y fecha de valuacion), Tabla limit_breaches: solo insercion, bitacora de excesos detectados, Tabla limits(id, scope, key, metric, amount, created_at), Estados de limite: ok menor de 80 por ciento, alerta de 80 a 100 por ciento, exceso mayor de 100 por ciento, R2 Limites: alta por evento, uso calculado correcto por metrica, estados en 80 y 100 por ciento, check registra exceso una vez por limite y fecha, UPDATE y DELETE rechazados

### Community 414 - "Veredicto R6 Interfaz: CUMPLE con observaciones menores"
Cohesion: 0.25
Nodes (8): Defecto 3 BAJA (primera ronda): tabla de P&L explicado desborda a 1280 px (1072 contra 996 px); corregido en segunda ronda, Defecto 4 BAJA (primera ronda): codigos internos (irs, fx_forward, cap_floor) en avisos de la interfaz; corregido en segunda ronda, R6: scrollWidth del documento = 1280 px en todas las pestanas y Metodologia (sin desborde de pagina), R6: seis pestanas en Riesgo (Sensibilidades, VaR, P&L explicado, Limites, Credito, Escenarios) con contenido verificado, R6: textos en espanol salvo codigos internos crudos en avisos de credito y el termino steepener, Regresion: 2 FAIL en it_d esperados, el script buscaba el texto viejo swaps de tasa (irs), Veredicto R6 Interfaz: CUMPLE con observaciones menores, R6 Interfaz segun D7: sin desbordes a 1280 px y textos en espanol

### Community 415 - "SimulateExposure"
Cohesion: 0.25
Nodes (4): _curve(), _netting_set(), _quarterly(), SimulateExposure

### Community 416 - "Estados viva, vencida, terminada y ejercida"
Cohesion: 0.25
Nodes (6): Veredicto R2: CUMPLE (65 comparaciones, 0 discrepancias en replay), Veredicto R5: CUMPLE (terminacion, PV 0 en AUD-D1, 409 en evento posterior), Estados viva, vencida, terminada y ejercida, Modulo desk/api/lifecycle.py, R2 Replay: state recalculado desde cero coincide con la API; orden de insercion irrelevante, R5 Terminacion anticipada: termination y transfer, estado terminada, PV 0 fuera de riesgo; 409 si ya terminada

### Community 417 - "Seccion Fuera de alcance del corte 2"
Cohesion: 0.25
Nodes (8): Seccion Fuera de alcance del corte 2, Pendiente corte 3: calendarios de dias inhabiles y ajuste de fechas, Deuda que se queda: division del paquete de interfaz y textos de tablas compartidos, Pendiente: ejercicio automatico de opciones (exercise manual con importe), Pendiente: historia automatica de snapshots diarios, Pendiente: liquidacion derivada de caps/floors, swaptions y bonos vencidos (PV 0 con aviso), Pendiente: novaciones, asignaciones y compensacion, Pendiente corte 8: usuarios y aprobacion

### Community 418 - "D3 Calendarios desk/api/calendars.py: dias inhabiles MX y EE. UU. 2020-2040 por reglas, sin dependencias"
Cohesion: 0.25
Nodes (4): Construido sin R: aviso al designar coberturas en dia inhabil (pedido por D3(b)), R8 CUMPLE: holidays 2025-2027 MX y US verificados; missing_fixing omite e incluye los dias esperados, Fuera de alcance: reinicio de nocional, ajuste por inhabil y rezagos, otras monedas de colateral, umbrales, TIIE 28 historica, fuente real de puntos (corte 8), R8 Calendarios 2025-2027 MX y EE. UU.: feriados fijos, trasladados, Viernes Santo, Thanksgiving; missing_fixing solo en dias habiles

### Community 419 - "D5 Operacion MXN con colateral USD descuenta con MXN-USD y proyecta con TIIE-F; con colateral MXN no cambia"
Cohesion: 0.25
Nodes (6): Hallazgo: xccy se descuenta siempre con MXN-USD aunque la contraparte tenga colateral MXN; D5 no lo dice, R12 CUMPLE: cuatro suites pasan; test de coberturas con y sin listas CSA (rel 1e-8), R3 CUMPLE: Beta a USD el 2026-11-10 sube IRS receptor (base negativa); Alfa con fecha 2026-11-11; no_csa_curve verificado, Aviso no_csa_curve cuando el snapshot no trae la curva: usa TIIE-F, R12 Sin regresion: cuatro suites pasan; coberturas del corte 4 miden igual con colateral MXN (1e-8), R3 Colateral: cambiar contraparte a USD cambia PV; base negativa; evento con historial; sin curva da no_csa_curve

### Community 420 - "Diseño Corte 5 QF Desk (operaciones)"
Cohesion: 0.25
Nodes (8): Auditoría independiente QF Desk corte 5 (dos rondas), Diseño Corte 5 QF Desk (operaciones), Fuera de alcance: conciliación de colateral, Fuera de alcance: confirmación con firma, Fuera de alcance: instrucciones de liquidación y cuentas, Fuera de alcance: mensajería SWIFT y MarkitWire, Fuera de alcance: neteo de pagos, Fuera de alcance: otros productos en FpML

### Community 421 - "D2 Historia de factores para VaR historico (factores del VaR del corte 1)"
Cohesion: 0.25
Nodes (5): Construido sin R: GET /api/factor-history, POST /api/factor-history/derive y history_source (synthetic u observed) en el VaR historico, Veredicto R7 Metodologia: CUMPLE (grupo Riesgo avanzado con cascada, VaR historico, supuestos de credito, alcance CVA, escenarios, fuera de alcance), Factores del VaR: cambio diario TIIE-F en pb, SOFR en pb, rendimiento USDMXN, Fuentes de la historia: fijaciones cargadas (fixings), serie de MarketDataFeed/FRED integrada para MKT-LIVE, o CSV, R7 Metodologia actualizada segun D8

### Community 422 - "desk/api/backup.py con API de respaldo de sqlite3"
Cohesion: 0.29
Nodes (6): Construido sin requisito: backup atomico, ocultar confirmacion xccy, ruta en Ctrl+K, commit 1abca0f, D5 backup pisa copia del mismo segundo y --keep borra archivos ajenos (baja), Veredicto R4 Respaldo y restauracion: CUMPLE, desk/api/backup.py con API de respaldo de sqlite3, desk/api/db.py resuelve la ruta de la base, R4 Respaldo y restauracion de la base

### Community 423 - "Cruce xccy y colateral USD en riesgo avanzado del corte 6: cascada P&L, VaR, limites, CVA"
Cohesion: 0.25
Nodes (8): D1 FX de flujos USD liquidados cae en carry y no en tipo de cambio (media), I13 credit.py: magnitud -86k documentada, test mide escalon de un cupon, I5 P&L explicado con xccy y colateral USD cierra con defecto de atribucion D1, I6 VaR historico y limites no se rompen, I7 CVA excluye el xccy con aviso, desk/api/credit.py, Cruce xccy y colateral USD en riesgo avanzado del corte 6: cascada P&L, VaR, limites, CVA, Pendiente menor: simulacion de credit.py arranca un cupon por debajo del PV

### Community 424 - "POST /api/fixings/fetch: índices SOFR, TIIE-F, USDMXN; rango máximo 366 días"
Cohesion: 0.29
Nodes (6): Fijaciones: POST /api/fixings/fetch; Banxico requiere BANXICO_TOKEN, BANXICO_TOKEN: solo para TIIE de Fondeo (SF331451) y FIX (SF43718); nunca se guarda ni devuelve, Errores de fijaciones: 400 validación, 409 banxico_token_missing, 502 fuente o banxico_token_rejected; sin escritura en 409 y 502, POST /api/fixings/fetch: índices SOFR, TIIE-F, USDMXN; rango máximo 366 días, Respuesta de ejemplo de fijaciones (fetched, inserted, unchanged, conflicts), GET /api/fixings/sources: disponibilidad, reason y last_date por índice

### Community 425 - "Corte 8 excluye usuarios y roles, aprobación de dos personas, multiempresa, contenedores, licencia e importación PiP/Valmer/Bloomberg"
Cohesion: 0.29
Nodes (3): MX-DEMO: cartera sintética del seed, no representa posiciones reales, QF Desk: app local de valuación y riesgo de cartera demo MX-DEMO sobre el motor C++, Comandos de prueba: C++, pytests, backend pytest, frontend npm test y build

### Community 426 - "D7 Interfaz: selector de fecha, alta con fechas, ficha, blotter, P&L, fijaciones, rodar"
Cohesion: 0.29
Nodes (7): Defecto baja 2: blotter filtrado muestra mensajes contradictorios con 0 filas, Defecto baja 3: ficha ofrece Terminar y Cambiar nocional tras terminacion ya registrada, Defecto baja 7: formato -0.00 en PV de swaps par en UI P&L, Construido sin que un R lo pidiera: endpoints state y flows, avisos, carga CSV por archivo, OisSwap parRate reescrito, Veredicto R11: CUMPLE (Chrome headless 1280 px sin desborde, vistas revisadas), D7 Interfaz: selector de fecha, alta con fechas, ficha, blotter, P&L, fijaciones, rodar, R11 Interfaz comprobable: selector, alta, ficha, filtro, terminar, P&L, fijaciones, rodar, sin desbordes a 1280 px

### Community 427 - "D8 Interfaz: mercado, contrapartes, pricer xccy, riesgo, ficha con dias inhabiles, metodologia"
Cohesion: 0.29
Nodes (6): Construido sin R: endpoint GET /api/calendars/holidays (soporte de D8), R10 CUMPLE: 1280 px sin desbordes en Mercado, pricer xccy, Riesgo, Portafolio, Contrapartes y fichas; textos en espanol, D4 snapshots.data gana fx_forwards opcional: [{days, points}] en pesos por dolar, D8 Interfaz: mercado, contrapartes, pricer xccy, riesgo, ficha con dias inhabiles, metodologia, MX-DEMO trae valores sinteticos coherentes, rotulados, R10 Interfaz segun D8, sin desbordes a 1280 px, textos en espanol, procedencia visible de MX-DEMO

### Community 428 - "Convenciones de mercado (supuesto de convención, decisión de Fable)"
Cohesion: 0.29
Nodes (6): R11 CUMPLE: MethodologyScreen con seccion Colateral y curvas MXN; frases de aproximaciones retiradas, Pata MXN: TIIE de Fondeo compuesta diaria, cupones cada 28 días, ACT/360, Pata USD: SOFR compuesta, ACT/360, Forward USDMXN F(T)=S x DF_USD(T) / DF_MXN^USD(T), R11 Metodologia: convenciones como supuestos, efecto del colateral, nocional constante, fechas sin ajuste, retirar aproximaciones saldadas, Cross currency swap de base: SOFR plana contra TIIE de Fondeo mas diferencial, nocional constante

### Community 429 - "C3 Regla del menor sobre acumulados desde la designacion, con reciclaje y OCI = efectivo menos reciclaje"
Cohesion: 0.29
Nodes (5): Observacion abierta 2: reserva sin respaldo N-1 no declarada en Metodologia, Veredicto C3: CORREGIDO segun su texto, formulas verificadas en 20 cierres, pero produce reserva sin respaldo (N-1), Defecto N-1 (media): reciclaje sin reserva que lo respalde cuando el efectivo acumulado es cero, Observacion contable 1: regla del menor sobre PV limpio, no sobre acumulados desde el inicio (6.5.11(a)), Observacion contable 2: reciclaje lleva todo el cupon del swap sobrecubierto, incluido el exceso

### Community 430 - "D6 Efectividad prospectiva: coincidencia de terminos criticos y razon por escenario, umbral 0.8-1.25 solo referencial"
Cohesion: 0.29
Nodes (5): Extra no pedido: DEFAULT_SCENARIOS duplicado frente a RiskScreen.tsx (dos fuentes de verdad), Veredicto R7: CUMPLE, terminos criticos match y mismatch y razones por escenario, Endpoint GET /api/hedges/<id>/effectiveness (prueba prospectiva), R7 Efectividad prospectiva: match y mismatch de terminos criticos y razones por escenario igual a 1 con hipotetico identico, Modulo risk/scenarios.py con los escenarios DEFAULT_SCENARIOS

### Community 431 - "D1 Datos SQLite: tablas hedge_relationships, hedge_events y hedge_periods (solo insercion)"
Cohesion: 0.29
Nodes (6): Extra no pedido: disparadores tambien en hedge_relationships, Extra no pedido: filtro GET /api/hedges?trade_id= usado por la ficha de operacion, Modulo desk/api/db.py (esquema SQLite del desk), Tabla hedge_events (eventos designation, period_close, dedesignation, reserve_release), Tabla hedge_periods (cierres por fecha en orden cronologico, con result JSON), Tabla hedge_relationships (relaciones de cobertura, no se actualiza tras crearse)

### Community 432 - "R8 Sin regresión: las cuatro suites pasan"
Cohesion: 0.29
Nodes (7): CMake/ctest y pytests omitidas (worktree sin árbol CMake), Suites: pytest 2616 pasan, vitest 348 pasan, build OK, Veredicto R8: CUMPLE (suites en verde), Restricción: minimizar cambios en archivos compartidos (db.py, app.py, Shell.tsx, App.tsx), Módulos nuevos desk/api/ops_*.py y routes/ops.py, R8 Sin regresión: las cuatro suites pasan, Restricciones heredadas: Python 3.8, sin dependencias nuevas, commits por tarea

### Community 433 - "Causa probable: corte 3 cambio envejecimiento y corte 5 se escribio contra el comportamiento anterior"
Cohesion: 0.29
Nodes (7): I1 test de flujos proyectados del bono pasa; causa movida a aging, I2 test de filas solo IRS y bonos pasa sin cambiar la prueba, I3 context_at copia el contexto original y pasa, Causa probable: corte 3 cambio envejecimiento y corte 5 se escribio contra el comportamiento anterior, Fallo test_projected_flows_discount_back_to_the_pv_of_the_trade[bond], Fallo test_context_at_keeps_the_market_and_changes_only_the_date, Fallo test_only_irs_and_bonds_have_projected_rows_and_usd_rows_convert_at_the_spot

### Community 434 - "test_swaption.cpp"
Cohesion: 0.57
Nodes (5): annuity(), flatCurve(), irsNPV(), quadraturePrice(), slopedCurve()

### Community 435 - "origen"
Cohesion: 0.33
Nodes (3): origen(), test_cli_modulo_como_script_con_base_temporal(), correr()

### Community 436 - "MKT-LIVE: construido desde MarketDataFeed (SOFR, Treasuries) y FRED (DEXMXUS); solo lectura; se reescribe completo"
Cohesion: 0.33
Nodes (6): Actualización manual con fetch_sofr --latest --treasury, MKT-LIVE: construido desde MarketDataFeed (SOFR, Treasuries) y FRED (DEXMXUS); solo lectura; se reescribe completo, Actualizar datos: botón en pantalla Mercado o POST /api/market/refresh, MDF_DB: base de MarketDataFeed (sofr.db por omisión), MDF_FETCH: ejecutable fetch_sofr de MarketDataFeed, SOFR desde la Fed de Nueva York: fijaciones reales

### Community 437 - "D1 Curva MXN-USD: descuento MXN bajo colateral en USD, calibrada con forwards y bases"
Cohesion: 0.40
Nodes (4): R1 CUMPLE: max |F_impl - F_cot| = 0.0; max |npv|/N de bases 3.7e-15; HTTP diff 0, D4 snapshots.data gana xccy_basis opcional: [{days, spread}] en decimal, MKT-LIVE no trae forwards ni base: su MXN-USD no existe y se dice en procedencia, R1 Calibracion reprecia a cero: OIS, forwards (1e-8) y cross currency swaps a su diferencial; test C++ y Python

### Community 438 - "D3 Derivado hipotetico valuado con el motor existente, nunca guardado en trades"
Cohesion: 0.33
Nodes (4): Veredicto R2: CUMPLE, inefectividad cero con swap identico y forward, R2 Hipotetico identico: inefectividad cero y delta OCI igual a delta instrumento en todo cierre, Restriccion: no hay C++ nuevo, todo se valua con el motor existente, Funcion valuation.value_trade del motor existente (valua el hipotetico)

### Community 439 - "R2 Banxico listo e inactivo sin token"
Cohesion: 0.33
Nodes (5): Veredicto R2 Banxico inactivo sin token: CUMPLE, Series de Banxico SF331451 y SF43718 sin verificar contra Banxico, API SIE de Banxico, Variable de entorno BANXICO_TOKEN, R2 Banxico listo e inactivo sin token

### Community 440 - "R6 Documentacion en desk/README.md y Metodologia"
Cohesion: 0.33
Nodes (3): Veredicto R6 Documentacion: CUMPLE, Fuera de alcance del corte 8, R6 Documentacion en desk/README.md y Metodologia

### Community 441 - "Build de todos los targets"
Cohesion: 0.40
Nodes (4): Build de todos los targets, Configuración CMake (una vez), Suite C++ ctest (463 tests GoogleTest), Ejecutar un test C++ con ctest -R

### Community 442 - "Validación de PV de 62 casos: 7 operaciones del portafolio más batería fija de 8 a 12 por producto"
Cohesion: 0.40
Nodes (4): Producto nuevo requiere pricer en ql_*.py (PRICERS, METHODS) y entrada en common.py (PRODUCTS, TOLERANCES), Validación de PV de 62 casos: 7 operaciones del portafolio más batería fija de 8 a 12 por producto, Diferencia relativa = |PV_desk - PV_ref| / nocional, Tolerancias relativas por producto: irs 1e-6, fx_forward 1e-8, fx_option 1e-6, equity_option 1e-6, bond 1e-6, cap_floor 5e-4, swaption 5e-4

### Community 443 - "Seccion Restricciones del corte 2"
Cohesion: 0.40
Nodes (5): Veredicto R13: CUMPLE (suites verdes, MKT-LIVE protegido por rodado), R13 Sin regresion: ctest, pytest bindings, pytest desk/api y vitest pasan; MKT-LIVE de solo lectura, Restriccion: no tocar MarketDataFeed y puerto 5070 reservado al desk, Restriccion: Python 3.8 de Anaconda, sin dependencias nuevas, matematica en C++ via qfpy, Seccion Restricciones del corte 2

### Community 444 - "D8 Migracion idempotente de base corte 1 con evento execution"
Cohesion: 0.40
Nodes (3): Veredicto R9: CUMPLE (migracion sin diferencia relativa, sin duplicados), D8 Migracion idempotente de base corte 1 con evento execution, R9 Migracion de base corte 1 sin perdida, PV sin cambio, arranque doble sin duplicar

### Community 445 - "counterparties.collateral_currency (MXN por omision o USD), editable por PUT /api/counterparties/<id>"
Cohesion: 0.40
Nodes (5): D1 (media) CORREGIDO: intercambio inicial del xccy entra al PV el dia de inicio pero no se liquida; salto fantasma en P&L, D4 (baja) CORREGIDO: tabla Contrapartes mostraba colateral del ultimo evento aunque fecha efectiva fuera posterior, Segunda ronda: commits dc7ddb3 (D1), f390ebe (D4) y 670b9cc (Metodologia para D2, D3, D5, D6, D7), counterparties.collateral_currency (MXN por omision o USD), editable por PUT /api/counterparties/<id>, counterparty_events: historial solo de insercion; el cambio aplica desde su fecha

### Community 446 - "Bond y CapFloor con calendario explicito de pagos para envejecer de forma exacta"
Cohesion: 0.40
Nodes (5): D5 (baja) DECLARADO: corrido de medio dia al dia siguiente del cupon (182.5 vs 182 dias), D6 (baja, por diseno) DECLARADO: caplet fijado no pagado sale del PV sin liquidarse ni entrar a P&L, R9 CUMPLE: bono 100M al 9 por ciento, PV dia del pacto igual a /api/price/bond; sucio = limpio + corrido en 2027-02-08, Bond y CapFloor con calendario explicito de pagos para envejecer de forma exacta, R9 Bono envejecido exacto: sucio = limpio + cupon corrido, continuo dia a dia; cap envejecido sin caplet fijado

### Community 447 - "C6 Avisos al designar no bloqueantes: no_economic_relationship, instrument_off_market, forecast_date_weekend"
Cohesion: 0.40
Nodes (4): Veredicto C6: CORREGIDO, avisos devueltos y guardados; termino side resuelve D-4, Defecto D-4 (baja): terminos criticos de credito sin sentido; swap del lado equivocado coincide, Defecto D-5 (baja): fecha de flujo pronosticado en fin de semana sin advertencia al designar, Observacion contable 9: designacion sin relacion economica se acepta sin advertencia (6.4.1(c)(i))

### Community 448 - "Veredicto C8: CORREGIDO, interfaz sin desbordes, fechas ISO y errores de formulario limpiados; selector de snapshot menor"
Cohesion: 0.40
Nodes (3): Veredicto C8: CORREGIDO, interfaz sin desbordes, fechas ISO y errores de formulario limpiados; selector de snapshot menor, Defecto D-6 (baja): campo de fecha de Desdesignar con formato del navegador (12/15/2026), Defecto N-4 (baja): selector de snapshot de Liberar reserva y Desdesignar arranca en snapshot global, da 409

### Community 449 - "D8 Reporte por relacion y exportacion CSV de asientos, con nivel 2 de jerarquia de valor razonable"
Cohesion: 0.40
Nodes (4): Extra no pedido: ruta propia /coberturas/:id/reporte para la vista imprimible, Veredicto R9: CUMPLE, reporte con secciones D8 y CSV que cuadra, Endpoint GET /api/hedges/<id>/report (y format=csv para asientos), R9 Reporte con todas las secciones de D8; CSV de asientos cuadra; nivel de jerarquia y procedencia del snapshot visibles

### Community 450 - "R8 Desdesignar genera evento, congela saldo y bloquea cierres (409); cierre con snapshot no posterior o operacion terminada da 409"
Cohesion: 0.40
Nodes (3): Veredicto R8: CUMPLE, desdesignacion, bloqueo de cierres y 409 por terminacion, Endpoint POST /api/hedges/<id>/dedesignate (desdesignacion con snapshot y causa), R8 Desdesignar genera evento, congela saldo y bloquea cierres (409); cierre con snapshot no posterior o operacion terminada da 409

### Community 451 - "Veredicto R2 Limites: CUMPLE"
Cohesion: 0.40
Nodes (5): R2 prueba: check dos veces registra 1 exceso y luego 0; bitacora con 1 fila; cambio y baja por evento, R2 prueba: alta por 201 en 4 metricas; uso recalculado desde rutas existentes con diferencia relativa 0.0 en 5 casos, R2 prueba: UPDATE y DELETE rechazados por trigger en limits, limit_events, limit_breaches, factor_history, counterparty_credit, scenario_sets y scenario_set_events, R2 prueba: umbrales exactos 79.99 ok, 80.0 alerta, 100.0 alerta, 100.01 exceso, 50 ok, Veredicto R2 Limites: CUMPLE

### Community 452 - "Tabla factor_history(factor, date, value): solo insercion y carga CSV idempotente"
Cohesion: 0.40
Nodes (4): Tabla factor_history(factor, date, value): solo insercion y carga CSV idempotente, POST /api/risk/var con parametro method parametric o historical, Tabla limit_events: solo insercion (creacion, cambio, baja), Hechos solo de insercion: triggers de solo insercion en tablas nuevas del corte

### Community 453 - "D6 Confirmacion de xccy compara con cupon y no con intercambio (baja)"
Cohesion: 0.40
Nodes (5): Cierre: agente corrigio D1-D6 con pruebas, sin nueva auditoria independiente, D6 Confirmacion de xccy compara con cupon y no con intercambio (baja), I4 xccy en operaciones: flujos, confirmacion y rechazos verificados en vivo, Cruce xccy_swap en operaciones del corte 5: flujos, confirmacion, FpML y conciliacion, desk/api/ops* modulos de operaciones del corte 5

### Community 454 - "R3 Procedencia visible con boton Traer de la fuente"
Cohesion: 0.40
Nodes (3): Veredicto R3 Procedencia visible: CUMPLE, GET /api/fixings/sources, R3 Procedencia visible con boton Traer de la fuente

### Community 455 - "_period"
Cohesion: 0.50
Nodes (3): _numbers(), _period(), test_r12_hedge_period_close_is_the_same_with_and_without_the_csa_lists()

### Community 456 - "OisSwap gana clave de curva de descuento opcional (retrocompatible)"
Cohesion: 0.50
Nodes (4): R4 CUMPLE: diferencia 0.0 con misma curva; PV dual -123,294.77 vs single -120,693.78 con suma independiente, OisSwap gana clave de curva de descuento opcional (retrocompatible), R4 OisSwap con curva de descuento distinta: retrocompatible 1e-12 y suma independiente 1e-10 x nocional, Restriccion: constructores y firmas existentes siguen funcionando igual

### Community 457 - "C5 Liberacion de la reserva congelada con causa flow_occurred o flow_no_longer_expected"
Cohesion: 0.50
Nodes (3): Veredicto C5: CORREGIDO, liberacion parcial y total con validaciones y reporte, Observacion contable 4: reserva congelada sin mecanismo de reciclaje (6.5.12), Endpoint POST /api/hedges/<id>/release (liberacion de reserva congelada)

### Community 459 - "D9 Interfaz: pantalla Coberturas con lista, alta, detalle, cierre, desdesignacion, exportacion e impresion"
Cohesion: 0.50
Nodes (3): Veredicto R10: CUMPLE, interfaz sin desbordes a 1280 px y banda D10 presente, R10 Interfaz Coberturas sin desbordes a 1280 px, textos en espanol, banda D10 siempre visible, Pantalla Coberturas de la interfaz (lista, alta, detalle, reporte)

### Community 460 - "Correccion de conteos: ctest 449 y pytests 80 estaban mal; no hay pruebas perdidas (linea base 402 mas 8)"
Cohesion: 0.50
Nodes (4): Correccion de conteos: ctest 449 y pytests 80 estaban mal; no hay pruebas perdidas (linea base 402 mas 8), Metodo de la auditoria independiente: lectura de codigo, backend en 127.0.0.1:5096 con base temporal, Chrome headless en 9356 a 1280x900, sin leer plan.md, Suite ctest: primera ronda reporto 449/449 (erroneo), segunda ronda 410/410 segun ctest -N, Suite pytests bindings qfpy: primera ronda 80 (erroneo), segunda ronda 59 tests OK

### Community 461 - "R7 Suites en verde sin cambios injustificados"
Cohesion: 0.50
Nodes (3): Veredicto R7 Suites: CUMPLE, Suites corridas por el auditor (ctest 463, pytests 83, backend 3438, UI 575, build 251 kB), R7 Suites en verde sin cambios injustificados

### Community 462 - "Planes y specs en docs/superpowers/plans y specs"
Cohesion: 0.67
Nodes (3): Plan activo 2026-04-19-quantengine-merge: fusión QF y MarketDataFeed en QuantEngine, Auditoría de repo 2026-07-07: gitignore de graphify-out, plan movido, commit 0f81591, Planes y specs en docs/superpowers/plans y specs

### Community 464 - "MarketEnvironment: contenedor central de mercado (curvas, spots, vols) con patrón Observer"
Cohesion: 0.67
Nodes (3): IMarketObserver (qf::core) instrumentos que reprecian, Instrument::pv(MarketEnvironment) API primaria; overload legacy pv(YieldCurve) para qfpy, MarketEnvironment: contenedor central de mercado (curvas, spots, vols) con patrón Observer

### Community 472 - "Auditoria: metodo de prueba con backend real en puerto 5073, base temporal y Chrome headless a 1280 px"
Cohesion: 0.67
Nodes (3): Auditoria: metodo de prueba con backend real en puerto 5073, base temporal y Chrome headless a 1280 px, Segunda ronda de auditoria: escenarios propios con 255 comprobaciones sobre snapshots S1 a S4, Auditoria: resultados de suites C++ (402), qfpy (56), desk/api (2292 a 2335) y UI (229 a 266)

### Community 473 - "I9 Interfaz recorrida en CDP: 8 pantallas sin errores, defecto visual D2"
Cohesion: 0.67
Nodes (3): D2 Tabla de flujos de Operaciones desplaza a 1280 px (baja), I9 Interfaz recorrida en CDP: 8 pantallas sin errores, defecto visual D2, Recorrido de interfaz en puerto 5088 y CDP 9348 sin errores ni rotulos crudos

### Community 477 - "Snapshot gana curva de base y moneda de colateral por contraparte"
Cohesion: 0.67
Nodes (3): Corte 3 R3: cambio de moneda de colateral cambia PV; base cero iguala corte 1, Corte 3 R4: DV01 por plazo incluye curva de base, suma cuadra con paralelo al 2 por ciento, Snapshot gana curva de base y moneda de colateral por contraparte

## Ambiguous Edges - Review These
- `P10: rama desde master y commits con GRAPHIFY_SKIP_HOOK=1; ultimo commit de T15 sin esa variable` → `Rama de trabajo feat/qf-desk`  [AMBIGUOUS]
  docs/superpowers/qf-desk/design.md · relation: conceptually_related_to
- `Bindings qfpy (qfpy.cpp): opciones, bonos, swaps, curvas` → `swaption-04: defecto de Swaption::price (raíz de Jamshidian fuera de bisección, 0.0 vs 92,158.63 MXN; falta término de varianza de HW); corregido en commit 2f5b733`  [AMBIGUOUS]
  desk/validation/README.md · relation: conceptually_related_to
- `Intencion del corte 6: pasar de cuanto vale y cuanto riesgo tiene a por que cambio, cuanto puedo perder, cuanto me debe cada contraparte y si estoy dentro de limites` → `Base del corte 6: cortes 1, 2 y 4 de QF Desk`  [AMBIGUOUS]
  docs/superpowers/qf-desk/corte6/design.md · relation: conceptually_related_to
- `desk/api/db.py resuelve la ruta de la base` → `Puertos de prueba 5088 y Chrome 9348, no tocar 5070`  [AMBIGUOUS]
  docs/superpowers/qf-desk/corte8/design.md · relation: conceptually_related_to
- `P8 T7 se lanza tras terminar el agente de swaption` → `P10 Fuera de alcance se declara solo en desk/README.md`  [AMBIGUOUS]
  docs/superpowers/qf-desk/corte8/design.md · relation: conceptually_related_to
- `Corte 3 motivacion: descuento MXN con cross currency swaps SOFR vs TIIE, separado de proyeccion` → `Fuente: Banorte, valuacion de swaps de TIIE legacy`  [AMBIGUOUS]
  docs/superpowers/qf-desk/roadmap.md · relation: cites
- `Deuda corte 1: pv de filas FX en USD mientras /api/price da MXN` → `qfpy (bindings Python de Quant_Finance)`  [AMBIGUOUS]
  docs/superpowers/qf-desk/roadmap.md · relation: references

## Knowledge Gaps
- **970 isolated node(s):** `addCurve`, `curves_`, `hasVolSurface`, `observers_`, `setSpot` (+965 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 2973 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **293 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CapFloor` connect `TEST` to `MarketEnvironment`, `Swaption`, `Swap`, `Bond`, `qfpy.cpp`, `capfloor.cpp`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Are the 32 inferred relationships involving `ApiError` (e.g. with `_date()` and `_prospective()`) actually correct?**
  _`ApiError` has 32 INFERRED edges - model-reasoned connections that need verification._
- **What connects `addCurve`, `curves_`, `hasVolSurface` to the rest of the system?**
  _970 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `MarketEnvironment` be split into smaller, more focused modules?**
  _Cohesion score 0.0453551912568306 - nodes in this community are weakly interconnected._
- **Why does `ApiError` connect `ApiError` to `rates.py`, `test_errors.py`, `ApiError`, `get_conn`, `state`, `sqlite3`, `choice`, `portfolio.py`, `api/market.py`, `test_live_market.py`, `test_ops_fpml.py`, `live_market.py`, `json`, `test_credit.py`, `now_iso`, `test_ops_cashflows.py`, `confirm_settlement`, `hedge_effectiveness.py`, `limits.py`, `test_ops_schema.py`, `ops_confirm.py`, `iso_date`, `collateral.py`, `create_run`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `P10: rama desde master y commits con GRAPHIFY_SKIP_HOOK=1; ultimo commit de T15 sin esa variable` and `Rama de trabajo feat/qf-desk`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Bindings qfpy (qfpy.cpp): opciones, bonos, swaps, curvas` and `swaption-04: defecto de Swaption::price (raíz de Jamshidian fuera de bisección, 0.0 vs 92,158.63 MXN; falta término de varianza de HW); corregido en commit 2f5b733`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._