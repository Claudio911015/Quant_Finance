# Auditoría — QF Desk corte 9 (XVA, XVA incremental, curvas de crédito sintéticas)

Rama `feat/qf-desk` (auditado sobre 6dabf5c; durante la auditoría otros agentes movieron HEAD a b7e97a5 solo con `docs/tex`). No se leyó `plan.md` ni se usaron los reportes de los implementadores. Scripts de la auditoría en `/tmp/claude-1000/-home-claudio/1a002a83-9ce7-4c4e-b315-b09b1e001eba/scratchpad/` (`indep.py`, `r2a.py`, `mutate.sh`, `api.py`, `r5.py`, `xccyprof.py`, `ui.mjs`, `ui4.mjs`; capturas en `uishots/`). Backend real en 5099 con base temporal `scratchpad/srv/audit.db`; Chrome headless en 9359. Todo apagado al terminar; árbol sin cambios fuera de `docs/tex/` y `graphify-out/` (ajenos).

## Suites

| Suite | Resultado |
|---|---|
| `cmake --build build -j3` + `ctest --test-dir build` | 506/506 pasan (93 s) |
| `cmake --build build --target pytests` | 97 OK |
| `pytest desk/api/tests -q -p no:cacheprovider` | 3607 pasan (173 s) |
| `npm test` (desk/ui) | 266 pasan, 18 archivos |
| `npm run build` | OK (tsc -b + vite; aviso de chunk > 500 kB) |
| Validación QuantLib (`GET /api/validation/report`) | 62 casos, 62 dentro, 0 fuera, `commit_matches: true`, `desk_dirty: false` |

## Derivación en papel del motor y comparación con el código

Medida riesgo neutral MXN, X = MXN por USD.

1. Cheyette/HW por moneda: r_c = f_c(0,t) + x_c, dx_c = (y_c − a_c x_c + μ_c)dt + σ_c dW_c, y = σ²(1−e^{−2at})/(2a). Código: `exposure_engine.cpp:36-38` (comentario) y `ouMoments` `:656-666`. Media: m(t) = ∫e^{−a(t−s)}(y(s)+μ)ds = σ²/(2a²)(1−e^{−at})² + μ(1−e^{−at})/a → coincide con `:663`. ∫m = σ²/(2a²)(t − 2(1−e^{−at})/a + (1−e^{−2at})/(2a)) + μ/a(t − (1−e^{−at})/a) → `:664`. Comprobé además que, con μ = 0, ∫m = ½Var(∫x), así E[e^{−∫r}] = P(0,t) exactamente.
2. Quanto: bajo Q^USD, dW^USD = dW^MXN − ρ_{USD,X}σ_X dt (Girsanov con densidad X·B_USD/B_MXN), luego bajo Q^MXN μ_USD = −ρ_{USD,X}σ_USDσ_X → `buildGrid :293`. Correcto.
3. Tipo de cambio: d ln X = (r_MXN + b − r_USD − σ_X²/2)dt + σ_X dW_X con b = −d ln q/dt, q = P_MXN-USD/P_TIIE; entonces ∫b sobre el paso = ln q_{n−1} − ln q_n y, con tasas deterministas, E[X_T] = X₀·P_SOFR/(P_TIIE·q) = X₀·P_SOFR/P_MXN-USD (el forward de mercado). Código `simulatePath :524-526` usa los incrementos exactos de ∫r de ambas monedas, el término de base con ese signo y −½σ_X²dt. Correcto.
4. Transición exacta: x̃_{n+1} = x̃_n e^{−aΔ} + ξ, ∫x̃ = x̃_n(1−e^{−aΔ})/a + η, ξ = σ∫e^{−aτ}dW, η = σ∫(1−e^{−aτ})/a dW, ζ = σ_X∫dW_X; la covarianza ∫f g dτ de los núcleos y el orden de actualización (η usa x̃ antes de actualizar) coinciden con `stepCovariance :668-683`, `kernelIntegral :68-75`, `simulatePath :516-519`. Cuenta bancaria I = −ln P(0,t) + ∫x̃ + ∫m (`:522-523`). Correcto.
5. Bono afín: P(t,T) = P(0,T)/P(0,t)·exp(−B x − ½B² y(t)), B = (1−e^{−a(T−t)})/a = (1 − e^{−aT}/e^{−at})/a → `computeBonds :559-560`. Para USD la fórmula usa el mismo estado x (el cambio de medida solo desplaza su ley). Correcto.
6. Pata flotante OIS: valor en t de N(Π−1) pagado en T con curva de descuento D ≠ proyección: N(F_i(t) − P_proj(t,T))·P_D/P_proj, con F_i(t) = acumulado·e^{∫_{s}^{t} r} si el periodo empezó, o P_proj(t,s) si no; P_D/P_proj = q(T)/q(t) con base determinista → `legValue :584-608`. Fija: −N K τ P_D(t,T). Pagador: flotante +, fija −. XCCY PayUsd: recibe pata MXN (+spread, intercambio inicial −N_MXN, final +N_MXN) y paga pata USD (signos opuestos), USD descontada con SOFR y convertida con X(t), MXN con MXN-USD (`compileSet :399-423`). Correcto.
7. Factor compuesto del periodo en curso: a0·exp(I(t) − I(max(inicio,0))) con a0 = factor del desk solo en el primer periodo (`:592-594`). Correcto.
8. Deflactores de la martingala: cuenta TIIE B, o de colateral B/q (`paidFlowsDeflated :622-650`, `deflatedValueStats :806-848`). X·q·B_USD/B_MXN es martingala con la deriva de (3), así que el swap USD y el xccy deflactados con B/q son martingalas. Correcto.

Independiente (script `indep.py`): swap MXN pagador de un solo periodo (0→730 d, K = 8.5 %, N = 100 M, curva plana 9 %, a = 0.05, σ = 0.01). V(t)/B(t) = N(1 − c·Y), Y lognormal con media P(0,T) y varianza log v(t) = σ²∫₀ᵗ B(s,T)²ds, así EPE*(t) = N·[Φ(−d₂) − FΦ(−d₁)] (put de Black) y ENE* el call. Con 20 000 trayectorias y malla de 30 días: CVA motor 49 654.8 ± 187.6 contra 49 769.3 cerrado (z = −0.61); DVA 485.4 ± 14.9 contra 501.6 (z = −1.09); FVA motor 20 065.7 contra 20 099.7 (−0.17 %); V₀ motor = exacto al centavo (2 076 168.69); total = CVA − DVA + FVA exacto.

Mutaciones (`mutate.sh`, cada una aplicada sobre una copia, reconstruido `qf_tests`, restaurado y reconstruido todo al final; `git diff -- src include` vacío después y `ctest -R "ExposureEngine|ComputeXva|PiecewiseHazard"` 43/43):

| Mutación | Detectada por | z |
|---|---|---|
| M1 signo de la deriva quanto | `MartingaleHoldsWithHighVolatilityAndCorrelation` (USD) y `MartingaleSeesBondConvexity…` (USD floater) | 13.7–22.7; −10.4/−12.1 |
| M2 signo de la deriva de base en ln X | `MartingaleHoldsWithHigh…` (xccy) y los dos `ZeroVolatilityLimit…` | 7.2–14.2 |
| M3 sin −½σ_X² | `MartingaleXccyCollateralAccount` (parámetros MX-DEMO) y la versión «hot» | −4.1 a −8.4; 7.5–14.7 |
| M4 sin convexidad −½B²y del bono | `MartingaleSeesBondConvexityAtExtremeVolatility` | −3.55 |
| M5 media de x sin el término y(t) de Cheyette | `MartingaleSeesBondConvexity…` | −3.4 a −4.5 |

Las cinco se detectan. Ojo: M1 no la detecta la prueba R2(b) con los parámetros de MX-DEMO (`MartingaleUsdSwapCollateralAccount` pasa mutada; el efecto quanto ρσσ_X ≈ 1e-4 queda bajo el ruido); la detecta la prueba con volatilidades y correlaciones altas. M4 y M5 solo las ve la prueba de volatilidad extrema.

Bootstrap de CDS independiente (`indep.py`): bisección propia con integración diaria de la pata de protección y devengo exacto al incumplimiento, mismas fechas de prima, ACT/360 y curva TIIE con pendiente; cotizaciones 60–120 pb, R = 40 %. Intensidades del motor contra las mías: diferencia relativa máxima 4.9e-5 (atribuible a la aproximación de medio periodo del código frente a mi integración diaria); el motor reprecia sus propias cotizaciones a ≤ 2e-17; con una sola cotización de 100 pb a 5 años, λ = 0.016713 contra s/(1−R) = 0.016667 (+0.28 %).

## Veredictos

| Req. | Inciso | Veredicto | Evidencia |
|---|---|---|---|
| R1 | ≥ 8 operaciones nuevas sobre Alfa/Beta/Gamma | CUMPLE | `desk/api/seed_trades.py:37-56`: 9 (3 por contraparte) |
| R1 | IRS TIIE-F y SOFR de ambos sentidos y plazos distintos; xccy de ambos sentidos | CUMPLE | mismo bloque: payer/receiver en TIIE-F y SOFR; xccy pay_usd y pay_mxn |
| R1 | cada contraparte con IRS y xccy; compensación parcial | CUMPLE | Alfa 500 M payer vs 300 M receiver, Beta y Gamma análogos (`:34-35`) |
| R1 | fechas escalonadas y algunas = as_of | CUMPLE | 2025-02-14 … 2026-08-17 y tres en 2026-11-10 (= as_of de MX-DEMO) |
| R1 | paso idempotente marcado en `settings`, sin tocar existentes | CUMPLE | `ensure_xva_trades :61-80`; dos `create_app` sobre la misma base: (16 operaciones, 4 curvas) antes y después; pruebas `test_seed_xva_trades.py` (16, y 7→16 en base antigua) |
| R1 | pruebas de conteo ajustadas | CUMPLE | suite desk 3607 verde |
| R2 | motor C++ 3 factores, malla, perfiles EPE/ENE/PFE, CVA/DVA/FVA, binding `qfxva` | CUMPLE | `include/qf/xva/exposure_engine.hpp`, `src/xva/exposure_engine.cpp`, `xva_bindings.cpp:88-201`; derivación arriba |
| R2 | (a) arranque exacto en todas las operaciones sembradas | CUMPLE | `r2a.py`: 12 operaciones vivas, máx \|motor − value_trade\|/N = 1.1e-15 con colateral MXN y también tras pasar las tres contrapartes a colateral USD (PV distintos, misma cota); valor del conjunto = suma del desk |
| R2 | (a) sin escalón a 1 día con vol cero | CUMPLE | `test_ExposureEngine.cpp:258-274` (cota de un día de devengo) |
| R2 | (b) martingala MXN, USD, xccy en 1, 3, 5 años, 3 EE | CUMPLE | `:297-335`; mutaciones M1–M3 detectadas (con la salvedad de potencia de arriba) |
| R2 | (c) límite sin volatilidad contra el desk envejecido con curva forward | CUMPLE | `:354-425`; M2 rompe ambas pruebas |
| R2 | (d) redefinida: CVA = forma cerrada (3 EE y 5 %), plana y con pendiente; humo contra `CVACalculator` en plana | CUMPLE | `:1013-1054`; mi forma cerrada independiente: z = −0.61 |
| R2 | (e) subaditividad y espejo exacto | CUMPLE | `:427-482`; en el servidor el espejo da `after` = 0 exacto |
| R3 | `GET /api/xva` por contraparte con todos los campos y perfil | CUMPLE | `api.py`: 200 en 3.6 s, campos `included/excluded/pv_mxn/cva/dva/fva/total/epe_max/pfe_max/profile{epe,ene,pfe}` |
| R3 | solo `irs` y `xccy_swap`; excluidos con rótulo en español | CUMPLE | «… Forward FX se excluye», «Cap / Floor», «Opción FX» |
| R3 | un conjunto por contraparte, compensación entre monedas; colateral solo cambia descuento; sin margen declarado | CUMPLE | `build_set`; `collateral_note` en la respuesta; PV cambia con colateral USD (r2a) |
| R4 | crédito de contraparte (curva → `counterparty_credit` → supuesto) | CUMPLE | `xva.py:187-201`; contrapartes nuevas salen con «Supuesto 1 % / 40 %» |
| R4 | `GET/PUT /api/xva/params` en `settings` con omisiones declaradas | CUMPLE | `GET` → `assumed.funding_spread: true` y `assumptions` lo lista |
| R4 | modelo del snapshot (HW, vol ATM 1 a de la superficie USDMXN, correlaciones de `factors`) | CUMPLE | `model.fx_vol_source = surface_atm_1y` (0.130), `hw` del snapshot, correlaciones 0.35/0.30/−0.10 declaradas |
| R4 | reproducible | CUMPLE | dos `GET /api/xva` idénticos byte a byte |
| R5 | contrato (antes, después, delta, pb, PV candidata, perfiles) | CUMPLE | `r5.py`; `xva.py:405-484` |
| R5 | mismas trayectorias | CUMPLE | una sola llamada `simulate([antes, después])` (`xva.py:449`); «antes» = `GET` previo al bit |
| R5 | (a) espejo de la única operación = −antes exacto | CUMPLE | servidor: xccy envejecido (Delta) e IRS SOFR envejecido (Epsilon): `delta == −before` exacto (igualdad de flotantes) en CVA, DVA, FVA y total; EPE después = 0 |
| R5 | (b) guardar y `GET` = después | CUMPLE | Beta + xccy de 80 periodos que alarga el vencimiento: diferencia relativa 0 en CVA, DVA, FVA, total, PV y EPE máx.; perfil EPE idéntico en los 75 puntos |
| R5 | (c) inválida = mismo 400 que `POST /api/trades`; producto fuera → 400 español; contraparte inexistente → 404 | CUMPLE | mismos `error` y `field` en tres casos; `fx_option` → 400; «Nadie SA» → 404 |
| R5 | la candidata nunca se guarda | CUMPLE | conteo de `trades`/`counterparties` en la base sin cambio tras los incrementales |
| R6 | `/api/credit/exposure` conserva contrato con el motor nuevo | CUMPLE | `credit.py:121-164`; `netting_sets[0].curve = "multimoneda"`, `credit_source`, `hazard_rate` = −ln S(5)/5; CVA idéntico al de `/api/xva`; EE(0) = max(PV,0) |
| R6 | sin tasa efectiva ni escalón; desk no llama `NettingSet`/`CVACalculator` | CUMPLE | `grep` en `desk/` solo encuentra la prueba que lo prohíbe (`test_credit.py:491-492`) y la Metodología |
| R6 | límites del corte 6 funcionan | CUMPLE | servidor: límite `pv_exposure` 1 M sobre Beta → uso 149.7 % «exceso»; `POST /api/limits/check` registra el exceso |
| R7 | menú «XVA», tabla, perfil, parámetros editables, panel incremental con campos del pricer, antes/después/incremental MXN y pb | CUMPLE | `ui.mjs` y `uishots/01-xva.png`, `02-incremental.png`, `03-incremental-xccy.png` |
| R7 | gráfica antes/después/incremento | CUMPLE | `XvaProfileChart.tsx:179-243` (series Antes, Después, Incremento y Cero; ECharts en canvas) |
| R7 | «Pactar» guarda y refresca | CUMPLE | `trades` 19 → 20; la fila de Alfa pasa de 5 a 6 incluidas en 2.8 s (`ui4.mjs`) |
| R7 | Crédito de Riesgo sustituida por enlace; límites en Riesgo | CUMPLE | `/riesgo`: pestaña «Crédito» con enlace a `/xva`; pestaña «Límites» presente |
| R7 | aviso permanente | CUMPLE | «XVA informativo: no entra al PV ni a la contabilidad» |
| R7 | **sin desborde horizontal a 1280 px** | **NO CUMPLE** | en `/xva`: `documentElement.scrollWidth` 1280 > `clientWidth` 1270 y `window.scrollTo(200,0)` deja `scrollX = 10`; el documento crece en vertical (scrollHeight 2033 frente a 790 con `.shell__main` desplazándose por dentro), aparece la barra vertical y el `min-width: 1280px` de `base.css:25` desborda 10 px. En `/mercado` y `/riesgo` no pasa. Causa probable: `.xva-sr` (`XvaScreen.css:310-317`, `position: absolute` sin ancestro posicionado) de `CreditCurvesPanel.tsx:149` |
| R7 | sin errores de consola, rótulos en español, Ctrl+K | CUMPLE | 0 errores ni excepciones en `/xva`; búsqueda de rótulos crudos (`irs`, `xccy_swap`, `_mxn`, `NaN`, `undefined`, `synthetic`, …) vacía; la paleta lista «XVA» |
| R8 | sección Metodología con modelo, parámetros, definiciones, incremental y límites | CUMPLE | `MethodologyScreen.tsx:407-445` |
| R9 | suites verdes y validación regenerada | CUMPLE | tabla de suites |
| R10 | (a) curvas sembradas, tabla de solo inserción, procedencia sintética visible | CUMPLE | `credit_curves.py:33-63`; Alfa 60–120, Beta 150–300, Gamma ≈ 95–101 plana, propia 70–125; `source.label` «Sintética (inventada para demostración)» en API y UI |
| R10 | (b) bootstrap, reprecio ≤ 1e-8, plana ≈ s/(1−R), negativas → error | CUMPLE | independiente arriba; `PUT` con una cotización que implica intensidad negativa → 400 «… intensidad de incumplimiento negativa en el tramo de 2 años», `field: quotes` |
| R10 | (c) `GET`/`PUT /api/credit/curves`, malla anual 10 a, S, PD acumulada y PD del año | CUMPLE | servidor: 4 entidades, `hazards` por tramo, `grid` de 10 años; Alfa λ₁ = 1.005 % frente a 60 pb/0.6 |
| R10 | (d) el XVA usa las curvas; respaldo plano; params solo fondeo y simulación | CUMPLE | `PUT` de `propia` (R = 35 %) cambia el DVA de todas las contrapartes; `/api/xva/params` solo trae fondeo, trayectorias, semilla y percentil |
| R10 | (e) sección «Curvas de crédito» editable, PD por año, gráfica de supervivencia, etiqueta «Sintética» | CUMPLE | texto de la pantalla y `CreditCurvesPanel.tsx:228-234` |
| R10 | (f) Metodología de curvas | CUMPLE | `MethodologyScreen.tsx`, «Curvas de crédito» |

Sensatez económica (MX-DEMO, 2000 trayectorias): xccy Beta id 12 (pay_mxn, 10 M USD, ambos intercambios): EPE crece de 0 a 20.0 M y PFE 95 % a 76.9 M en el día 700 y cae a 0 tras el intercambio final del día 728; ~0.13·√2·1.65 ≈ 30 % de 186 M más la deriva del valor esperado por los cupones netos (TIIE 9 % frente a SOFR 4 %, ≈ 9 M por año) da el orden de magnitud. Valor esperado sin descontar sube en el receptor de USD y baja en el pagador, que es la contrapartida de los cupones netos ya pagados. CVA Alfa 215 k ≈ 0.6 · EPE media ~10 M · PD acumulada ~3.5 %; Beta 521 k con PD a 5 años ~20 %; DVA Alfa 619 k con ENE ~30 M. FVA = s·Σ(EPE* − ENE*): negativo (beneficio) en conjuntos con valor neto negativo (Alfa −200 k ≈ 0.5 % · −16 M · 2.5 a); signo coherente con la definición del diseño.

## Construido sin que un requisito lo pidiera

- `ExposureEngine::deflatedValueStats` y `enum Deflator` en la cabecera pública (andamiaje de prueba expuesto en la API C++; no en Python).
- Liberación del GIL en `simulate`/`compute_xva` (commit 645c6e2) con su prueba; razonable para el servidor.
- `history` y `error` por curva en `/api/credit/curves`; tabla de «Operaciones de <contraparte>» en la pantalla; percentil de PFE, semilla y trayectorias editables por `PUT /api/xva/params` (el diseño los pedía fijos por omisión, no editables, aunque R10(d) los admite).
- `dva_stderr` en el resultado (no se publica en la API).

## Defectos

| # | Severidad | Defecto | Evidencia |
|---|---|---|---|
| 1 | Media | Desborde horizontal de 10 px y doble barra vertical en `/xva` a 1280 px (R7) | ver R7; causa probable `.xva-sr` absoluto sin ancestro posicionado |
| 2 | Baja | La prueba de martingala con parámetros de MX-DEMO no detecta el signo del quanto; solo la variante de volatilidades extremas lo hace. R2(b) se cumple porque esa variante existe, pero el poder depende de ella | mutación M1 |
| 3 | Baja | `credit_curves.as_of` guarda la fecha UTC de hoy, no la del snapshot (curva insertada el 2026-11-12 con snapshot del 2026-11-10) | respuesta del `PUT` |
| 4 | Baja | Mensaje de producto fuera del incremental mal construido: «… cross currency swaps: Opción FX no» | `xva.py:393` |
| 5 | Baja | Convenciones de CDS simplificadas: fechas de prima `round(k·365/4)` días, no fechas IMM con calendario, y vértices en 365·T días; la pata de protección descuenta a mitad de periodo. Diferencia ≤ 5e-5 relativa frente a integración diaria. Declararlo en Metodología | `piecewise_hazard_curve.cpp:33-47, 93-122` |

Conteo de tests: ctest 506, pytests (bindings) 97, desk/api 3607, vitest 266 (18 archivos); build de la UI OK.
