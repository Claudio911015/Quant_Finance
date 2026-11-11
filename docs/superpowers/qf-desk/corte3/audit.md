# Auditoría independiente — QF Desk corte 3

Rama `feat/qf-desk`, commits `ce51edf..046db38`, contrastados con `design.md`. Usé números propios: un script con `qfpy` de `build/src`, un backend real en :5093 con base temporal y Chrome headless propio en :9353 a 1280 px. Al terminar apagué todo.
Nota: el rango incluye 3887874 y b968653, que son del corte 4 (cierre y tercera ronda de coberturas). Quedan fuera de esta auditoría.

## Suites
- C++: `cmake --build build -j3` OK; `ctest --test-dir build` **449/449** pasan
- Bindings: `cmake --build build --target pytests` **80 tests OK**. Los 24 tests del corte 3 (`test_xccy_py`, `test_xccy_bootstrap_py`, `test_aged_bond_cap_py`) cargan el qfpy real; no se saltan.
- Backend: `pytest desk/api/tests -q` **2748 passed**
- UI: `npm test` **332/332** (20 archivos); `npm run build` OK

## Veredictos

| R | Veredicto | Evidencia |
|---|---|---|
| R1 | CUMPLE | Script propio con 4 forwards y 4 bases sobre curvas distintas a las de los tests. Max \|F_impl − F_cot\| = 0.0. Max \|npv\|/N_USD de las bases a su diferencial = 3.7e-15. Por HTTP, MX-DEMO da `csa.implied_vs_quoted.diff` = 0 en 1M/3M/6M/1Y. Hay tests en C++ y en Python. |
| R2 | CUMPLE (con salvedad) | Con los días de cotización iguales a los pilares de TIIE-F, la diferencia máxima de DF en 0–3640 d es 4.4e-16. Con otros días (30/91/182/365 y 728/1092/1820/3640), la diferencia entre pilares llega a **2.7e-6**, y en los pilares de base a 8.6e-8, porque la interpolación lineal de ceros usa otros nodos. Los tests (`test_market_csa` "en los días de TIIE-F", `test_xccy_bootstrap` R2) solo prueban la rejilla alineada. Las cotizaciones de MX-DEMO sí coinciden con los pilares de TIIE-F salvo el 1D. |
| R3 | CUMPLE | HTTP: Beta pasa a USD el 2026-11-10 y el IRS receptor sube de 1,602,628.73 a 1,605,024.25 (base negativa, flujo neto positivo, vale más); el forward 5 también cambia. Alfa pasa a USD con fecha 2026-11-11: valuar en MX-DEMO (11-10) da el PV anterior, idéntico, y en el rodado al 11-12 aplica USD. Un snapshot sin listas da el aviso `no_csa_curve` en los productos MXN de contrapartes USD; el SOFR de Gamma (MXN) no cambia. Los eventos se guardan con historial (respuesta `history`). |
| R4 | CUMPLE | Con la misma curva explícita, la diferencia es 0.0 (≤1e-12). Con descuento MXN-USD, mi suma independiente Σ(flotante proyectado − fijo)·DF_otra coincide a 0.0/N; el PV dual es −123,294.77 contra −120,693.78 single. |
| R5 | CUMPLE | npv al `parSpread` = −7.5e-9 (N = 5 M USD); PayUsd + PayMxn = 0.0; sin intercambios, la diferencia contra el PV de los intercambios calculado a mano es −3.7e-9. Identidad de P&L por HTTP: pnl 1,392,177.02 = pv_to 84,902.89 + settled 1,307,274.13 (ver defecto D1 sobre el intercambio inicial). |
| R6 | CUMPLE | HTTP: pricer (`details.discount_curve` = MXN-USD, par spread −0.0010), alta a la par (fx_rate 18.6, spread guardado), valuación en el portafolio, flujos por pata liquidados/proyectados con FIX/`fx_fallback`, DV01 por curva (MXN-USD 34,805; TIIE-F 0 por recalibración), escenarios (TIIE+100, SOFR+100, fx_spot) y VaR sin error, P&L y terminación (status `terminada`, PV 0, settled +80,000). En la ficha se ven las dos patas y el intercambio final, sin desbordes. |
| R7 | CUMPLE (frágil) | Seed con MX-DEMO: TIIE-F suma −13,978 contra paralelo −14,089 (0.79 %), SOFR 0.03 %, MXN-USD 0.00 %. Por operación siempre < 0.6 %. **Pero** al agregar un bono de 100 M (portafolio neto chico) TIIE-F queda en 5,521.5 contra 5,408.5 = **2.09 %**. La diferencia absoluta (~113 MXN) es la convexidad del cap: el paralelo es unilateral y los pilares usan diferencia central. Viene del corte 2; el criterio relativo falla en portafolios casi neutros. |
| R8 | CUMPLE | `/api/calendars/holidays` 2025–2027 MX: Viernes Santo (04-18-2025, 04-03-2026, 03-26-2027), 16-sep, Revolución trasladada (11-17-2025, 11-16-2026, 11-15-2027), 1.er lunes de febrero, 3.er lunes de marzo; 2030-10-01 transmisión del Poder Ejecutivo. US: Thanksgiving 11-27-2025/11-26-2026/11-25-2027, Good Friday, 07-03-2026 y 12-24-2027 observados. En el xccy envejecido hasta 2027-02-08, el `missing_fixing` de SOFR omite 11-11, 11-26, 12-25, 01-01 y 01-18 e incluye 11-16; el de TIIE-F omite 11-16, 12-25, 01-01 y 02-01 e incluye 11-11, 11-26 y 01-18. |
| R9 | CUMPLE | Bono de 100 M al 9 %, semestral, 4 periodos: el PV del portafolio el día del pacto (103,876,451.93839927) es idéntico al de `/api/price/bond`. Rodado día a día sube unos 19–20 mil por día sin escalones (11-11, 11-12, 11-13; 05-08, 05-09, 05-10). El día del cupón baja 4.48 M y el cupón aparece `settled`. En 2027-02-08: sucio 105,605,087.66 = limpio 103,385,909.58 + corrido 2,219,178.08 (= 9 M·90/365). El cap pasa el test del caplet fijado; leí el código: los caplets se cortan con `(k−1)·28 >= elapsed`. |
| R10 | CUMPLE | Recorrí a 1280 px Mercado, pricer xccy, Riesgo, Portafolio, la pestaña Contrapartes y las fichas 8 y 9: `scrollWidth` = 1280 y ningún elemento recortado sin scroll propio. Mercado muestra las tablas de puntos forward y de base, la curva MXN-USD con la marca «Sintética» y la nota de curva dependiente, y la tabla de forward implícito vs cotizado. Riesgo trae MXN-USD en la escalera. Los textos están en español; solo quedan los controles nativos del navegador («Choose File») y el aria oculto de AG Grid. |
| R11 | CUMPLE | `MethodologyScreen` tiene la sección «Colateral y curvas MXN» con: convenciones «(supuesto de convención)», efecto del colateral, nocional constante sin reinicio, fechas sin ajuste por inhábil, curva dependiente en riesgo. Se retiraron «Aproximaciones… llega en el corte 3» y «Los feriados todavía avisan…». |
| R12 | CUMPLE | Las cuatro suites pasan. Ningún test de coberturas cambió desde el cierre del corte 4 (3887874) y todos pasan. `test_r12_hedge_period_close_is_the_same_with_and_without_the_csa_lists` compara con y sin listas (rel 1e-8). |

## Construido sin que ningún R lo pidiera
- Endpoint `GET /api/calendars/holidays?from&to`: es un soporte razonable de D8.
- Rodar un snapshot conserva las listas CSA.
- Aviso al designar coberturas en día inhábil: lo pide D3(b), no un R.
- La ficha del bono muestra sucio/limpio/corrido.
- Pricer con `exchange` en cuatro modos (both/initial/final/none).
- El xccy se descuenta **siempre** con MXN-USD, aunque la contraparte tenga colateral MXN. Está declarado en Metodología, pero D5 no lo dice.

## Defectos fuera de los R
- **D1 (media)**: el intercambio inicial del xccy entra en el PV el día de inicio (`start >= on`) pero nunca se liquida (`counts(start)` excluye el pacto en el mismo día, y el docstring lo dice). Si el `fx_rate` difiere del spot, el P&L da un salto fantasma. Prueba: alta con fx_rate 19.5 y spread −0.001 en MX-DEMO (spot 18.6): PV el día 0 = 0.0, al día siguiente 9,017,121.54, P&L 9.02 M con settled 0. Además la ficha deja de mostrar el intercambio inicial. Con el alta a la par (fx_rate = spot) el efecto es ≈ 0.
- **D2 (baja)**: R7 relativo es frágil en portafolios con DV01 neto chico: llega a 2.09 % al agregar un bono. La causa es la convexidad del cap (paralelo unilateral contra pilares centrales).
- **D3 (baja)**: R2 exacto solo cuando los días de cotización coinciden con los pilares de TIIE-F; si no, la diferencia de DF llega a 2.7e-6. No está declarado en Metodología. MXN-USD no tiene pilar 1D: entre 0 y 28 d se extrapola plano.
- **D4 (baja)**: la tabla Contrapartes y `GET /api/counterparties` muestran como «Colateral vigente» el último evento aunque su fecha efectiva sea posterior a la fecha de valuación elegida. Ejemplo: Alfa aparece en USD mientras su PV al 11-10 sigue en MXN.
- **D5 (baja)**: al día siguiente de un cupón del bono, el corrido es medio día (12,328.77 en vez de 24,657.53) porque el calendario usa 182.5 d por periodo mientras el cupón se liquida en el día entero 182. La inconsistencia de medio día entre la fecha de pago liquidada y el inicio del devengo se repite cada cupón.
- **D6 (baja, por diseño)**: el cap/floor descarta el caplet ya fijado y aún no pagado, sin liquidarlo (`test_cap_still_has_no_settlement`). Su pago conocido sale del PV y no entra al P&L.
- **D7 (baja)**: un forward FX con colateral USD tiene sensibilidad ~0 a SOFR (SOFR+100 pb da −787 MXN en 3 M USD a 91 d) porque los puntos se fijan al recalibrar. Es coherente con D6, pero conviene decirlo en Metodología.

## Segunda ronda

Commits nuevos `dc7ddb3` (D1), `f390ebe` (D4) y `670b9cc` (Metodología para D2, D3, D5, D6 y D7). Reproduje los casos con mis propios números: backend real en :5093 con base temporal y Chrome headless en :9353 a 1280 px. Al terminar apagué los dos y comprobé que los puertos quedaron libres. No corregí nada ni hice commits.

### Suites
- C++: `cmake --build build -j3` OK; `ctest --test-dir build` **449/449** pasan
- Bindings: `cmake --build build --target pytests` **80 tests OK**
- Backend: `pytest desk/api/tests -q` **2754 passed**. Son 6 más que en la primera ronda: los tests `test_d1_*` de `test_xccy_product.py`.
- UI: `npm test` **335/335** (20 archivos), 3 más que antes por los tests de Contrapartes y Metodología; `npm run build` OK

### Defectos de la primera ronda
- En la primera ronda no hubo ningún NO CUMPLE.
- **D1 (media): CORREGIDO.** Hice una prueba distinta de los tests: Gamma, `pay_mxn`, 7 M USD, fx_rate 17.8 (el spot es 18.6) y sin fijaciones cargadas, así que entra el respaldo `fx_fallback`.
  - PV: −156,650.26 el día 0 y 5,433,502.78 el 11-11.
  - Ventana MX-DEMO→A1: settled −5,600,000 (= N·(fx_rate − spot)) y pnl −9,846.95, que es el devengo de un día.
  - Ventanas A1→A3 y A3→A4: settled 0. MX-DEMO→A4: pnl −39,407.41, que es la suma exacta de las tres ventanas, así que el intercambio se cuenta una sola vez.
  - Ficha: el intercambio inicial aparece `projected` el día 0 y `settled` el día 1.
  - Inicio diferido al 11-13 (Beta, fx_rate 19.9): se liquida solo en la ventana A3→A4 (−6.5 M, pnl 9,027.12), y las ventanas también suman exacto.
  - Metodología lo declara en «Cross currency swap» y en «Estados».
- **D4 (baja): CORREGIDO.** Con Alfa en USD desde el 2026-11-11, la tabla de Contrapartes da:
  - con MX-DEMO activo (11-10): «Colateral en MXN», con la nota «Colateral en USD desde 2026-11-11» y fecha «—»;
  - con A1 (11-11): «Colateral en USD 2026-11-11».
  - `scrollWidth` = 1280. El endpoint `GET /api/counterparties` sigue dando el último evento, pero el docstring ya lo dice y la interfaz lee `history`.
- **D2, D3, D5, D6 y D7 (baja): DECLARADOS en Metodología, no corregidos en el código.** Así lo permitía la primera ronda, porque son bajos.
  - «DV01 por plazo»: un portafolio casi neutro puede pasar del 2 %.
  - «Curva MXN-USD»: la paridad exacta solo se cumple en los pilares de TIIE-F, hay millonésimas fuera de ellos y no hay pilar 1D (se extrapola plano).
  - «Bono y cap/floor envejecidos»: el corrido de medio día después de un cupón, y el caplet fijado que sale del PV y no entra al P&L.
  - «Efecto del colateral»: el forward FX apenas reacciona a SOFR.

### Regresiones
No encontré ninguna. Las cuatro suites pasan y ningún test anterior cambió de resultado. El cambio de `xccy.settled` solo afecta al intercambio inicial; los demás flujos siguen en `(d0, d1]`. La identidad `pnl = pv_to − pv_from + settled` se cumple en todas las ventanas que probé.

### Veredictos
R1–R12 sin cambios: todos CUMPLEN. Las salvedades de R2 y R7 quedan declaradas en Metodología. R5 queda **sin salvedad**, porque D1 está cerrado.

### Defectos abiertos
Solo quedan bajos y declarados: D2, D3, D5, D6 y D7. No hay ninguno medio ni alto.
