# Auditoría independiente — QF Desk corte 6 (rama `corte6`, commits posteriores a ce51edf)

Método: lectura del código de `desk/api/risk/*`, `routes/risk_adv.py`, diffs en archivos compartidos; backend real en 127.0.0.1:5096 con base temporal nueva (semilla MX-DEMO); scripts propios por HTTP (no los `it_*.py` de los implementadores); Chrome headless propio en 9356 a 1280×900 con medición de desbordes por DOM y capturas propias. No se leyó plan.md. Todo se apagó al final; el worktree quedó sin cambios.

## Suites (R8)

| Suite | Resultado |
|---|---|
| `cmake --build build -j3` | OK |
| `ctest --test-dir build` | 449/449 pasan |
| `cmake --build build --target pytests` | 80 tests OK |
| `pytest desk/api/tests -q` | 2584 passed |
| `npm test` (vitest) | 25 archivos, 377 tests pasan |
| `npm run build` | OK (solo aviso de tamaño de chunk) |

## Veredictos

### R1 P&L explicado — CUMPLE
- Roll de MX-DEMO (2026-11-10) a 2026-12-10 con mercado idéntico: total −642,470.13 MXN, 100 % en "Paso del tiempo", resto de componentes 0.0 exacto.
- Roll + TIIE-F +25 pb, SOFR −25 pb, spot +3 % (PUT al snapshot): total 677,380.25 = carry −593,606.89 + TIIE-F 296,921.52 + SOFR −4,115,245.39 + FX 5,089,311.00 + vol 0 + residuo 0.0.
- Suma de componentes vs `/api/pnl`: diferencia máxima por operación 0.0 y en total 0.0 (≤ 1e-6). Residuo 0 % del P&L.
- Nota: el residuo es exactamente 0 por construcción (telescópico), como dice D1; operaciones nuevas y eventos solo los cubren los tests del implementador (test_pnl_explain.py), no los reproduje por HTTP.

### R2 Límites — CUMPLE
- Alta (201) para las 4 métricas; uso recalculado por mí desde rutas existentes (`/api/portfolio/valuation` por contraparte, `/api/risk/dv01`, delta USDMXN de `/api/risk/var` ÷ 100, VaR paramétrico 1d 99 %): diferencia relativa 0.0 en las 5.
- Umbrales con montos elegidos para que el % fuera exacto: 79.99 → ok, 80.0 → alerta, 100.0 → alerta, 100.01 → exceso, 50 → ok.
- `check` dos veces: 1 exceso nuevo y luego 0; bitácora con 1 fila. Cambio de monto y baja por evento (201).
- SQLite directo: UPDATE/DELETE rechazados por trigger en `limits`, `limit_events`, `limit_breaches` (y también `factor_history`, `counterparty_credit`, `scenario_sets`, `scenario_set_events`).

### R3 VaR histórico — CUMPLE
- Historia propia (no la de los tests): 5 000 días hábiles normales correlacionados (Cholesky de la matriz de MX-DEMO, vols 4 pb / 5 pb / 0.75 %, `random.Random(777)`) cargada por `/api/factor-history/csv` (15 000 insertadas; recarga = 15 000 sin cambios, idempotente).
- VaR histórico 99 % 1d = 3,359,451.64 vs paramétrico 3,361,345.99 → −0.06 % (< 10 %). Mi recálculo propio (pérdida nº 50 de 5 000) da el mismo valor exacto; ES = 3,797,874.17 ≥ VaR.
- Historia insuficiente (window 5 000 sin CSV) → 409 `window_days`; window 59 → 400.
- Sin `method` y con `method: "parametric"` dan JSON idéntico (diferencia 0); la rama nueva solo se toma con `historical`.

### R4 Crédito — CUMPLE (en la letra), con defecto alto en la coherencia del perfil
- EE y PFE no negativos y PFE ≥ EE en los 3 perfiles (25, 61 y 61 puntos mensuales hasta el último vencimiento).
- EE(0) = max(PV, 0) exacto (Alfa 0, Beta 1,602,628.73, Gamma 0); pero se cumple porque el punto t=0 se **sustituye** con el PV del desk, no porque lo produzca la simulación (ver defecto 1).
- CVA con hazard 0 = 0.0; 0.5 % → 10,793; 2 % → 42,673; 5 % → 104,239 (crece). Cada cambio inserta fila (4 filas en `counterparty_credit`, historia devuelta 4).
- Excluidos con aviso: fx_forward ×2, cap_floor, fx_option. Aviso "CVA informativo…" presente en API y UI.

### R5 Escenarios — CUMPLE
- Crear (201), nombre duplicado (409), listar, baja (200, estado `baja`, desaparece de la lista), correr dado de baja → 404 `set`.
- Conjunto propio con un paralelo y un combinado: correr por `set` vs en línea → diferencia máxima 0.0 sobre todos los números. Igual para "Marzo 2020" y "Por omisión" (0.0).
- De fábrica: Por omisión (8), Depreciación 2008, 2016 elecciones EE. UU., Marzo 2020, rotulados "Aproximación histórica".

### R6 Interfaz — CUMPLE (con observaciones menores)
- Seis pestañas en Riesgo: Sensibilidades, VaR, P&L explicado, Límites, Crédito, Escenarios.
- VaR: paramétrico e histórico lado a lado, ES, peor día con fecha, historia usada (fuente, rango, observaciones). P&L: cascada en barras + tabla por operación. Límites: barras de uso, estados, alta, cambio de monto, baja, "Revisar límites", bitácora. Crédito: tabla por contraparte, gráfica EE/PFE 95 %, parámetros editables, excluidos. Escenarios: biblioteca, correr, nuevo conjunto, baja.
- 1280 px: `scrollWidth` del documento = 1280 en todas las pestañas y Metodología (sin desborde de página). Única salvedad: la tabla de P&L explicado (1072 px) desborda su contenedor (996 px) dentro de un `overflow-x:auto`; la columna Residuo queda oculta hasta desplazar.
- Textos en español, salvo códigos internos crudos en avisos de crédito (`fx_forward`, `cap_floor`, `irs`) y "steepener" (heredado de cortes anteriores).

### R7 Metodología — CUMPLE
Grupo "Riesgo avanzado": orden de la cascada, por qué el residuo no es cero, VaR histórico por sensibilidades (no revaluación completa), ES, historia sintética de MX-DEMO (500 días, semilla 20261110), supuestos de crédito (1 %, 40 %, supuesto), alcance del CVA, escenarios históricos con sus choques, fuera de alcance. "Sin XVA" se sustituyó por el alcance del CVA.

### R8 Sin regresión — CUMPLE
Ver tabla de suites.

## Construido sin que un R lo pidiera
- `GET /api/factor-history` (resumen), `POST /api/factor-history/derive` (fixings/live) y `history_source` (`synthetic`/`observed`) en el VaR histórico: lo apoya D2, pero no lo pide ningún R.
- Tipo de escenario `combined` (hasta 8 choques) en `risk/scenarios.py`: necesario para los históricos de D6.
- Regla extra: un solo límite activo por (scope, key, metric) → 409.
- El límite `var` queda fijo al paramétrico 1d 99 % (D4 no fija los parámetros).
- `GET /api/limits`, `GET /api/limits/breaches`, `GET /api/credit/params` (lecturas de apoyo a la UI).
- C++: `qf::xva` `simulate_exposure` (EPE/ENE/PFE) + test GoogleTest y test de bindings: lo permite D5.

## Defectos fuera de los R

1. **ALTA — El perfil EE/PFE y el CVA no son coherentes con la valuación del desk.** `credit.py` arma un `qfxva.NettingSet` con un swap "fresco" (nocional, tasa fija, plazo restante, frecuencia) y simula con Hull-White; luego **sustituye** el punto t=0 por max(PV del desk, 0). Medido con qfxva a t≈1e-4 (2 000 trayectorias):
   - Alfa (payer TIIE-F): PV del desk −942,898; EE qfxva(≈0) +2,214,782 → EE salta de 0 a 2.29 M en el primer mes.
   - Beta (receiver TIIE-F): PV del desk +1,602,629; ENE qfxva(≈0) 360,828 (signo contrario).
   - Gamma (payer SOFR, 20 M USD): PV del desk −849,247 MXN; EE qfxva(≈0) +11,208,504 MXN → EE(1 m) 9.9 M.

   El modelo de qfxva no reproduce el PV del desk (ni el signo), así que EE/PFE para t>0 y el CVA (p. ej. 192,822 en Gamma, cuyo PV es negativo) no se pueden comparar con el resto de la pantalla. Se ve como un escalón en la gráfica de Crédito. R4 se cumple solo por la sustitución en t=0.
2. **MEDIA — EE(0) por contraparte con más de una curva.** Se suma max(PV del conjunto, 0) por curva, sin compensar entre monedas, en vez de max(PV de la contraparte, 0). Está declarado en la Metodología, pero contradice la letra de R4 si una contraparte tiene swaps en TIIE-F y SOFR (no pasa en el portafolio de ejemplo).
3. **BAJA — La tabla de P&L explicado a 1280 px** necesita desplazamiento horizontal interno (1072/996 px); la columna Residuo no se ve sin desplazar.
4. **BAJA — Códigos internos en la interfaz:** "La exposición simulada solo cubre swaps de tasa (irs): fx_forward se excluye" (también `cap_floor`).
5. **BAJA — Biblioteca "Por omisión":** el nombre y la descripción de cada escenario se muestran en dos columnas desalineadas, con guion ASCII en uno ("TIIE-F -50 pb") y signo menos tipográfico en el otro ("TIIE-F −50 pb"); se lee como duplicado.

## Segunda ronda

Commits revisados desde la primera ronda: 2540a0a, f3b0a8e, f7b9452, 8f035f3, 668d25f, 8a9e5cd (13 archivos, todos en `desk/`; sin C++). Método: backend propio en 127.0.0.1:5096 con base nueva (`/tmp/fableorchestrate/qf-corte6/r2/r2.db`), mis scripts HTTP de la primera ronda (`it_a`..`it_e`) re-ejecutados contra 5096, un script propio con qfxva directo (`r2/coh.py`), y Chrome headless propio en 9356 a 1280 px. Todo apagado al final; el worktree quedó limpio.

### Suites
| Suite | Resultado |
|---|---|
| `cmake --build build -j3` | OK (exit 0) |
| `ctest --test-dir build` | 410/410 pasan |
| `cmake --build build --target pytests` | 59 tests OK |
| `pytest desk/api/tests -q` | 2588 passed |
| `npm test` | 25 archivos, 379 tests pasan |
| `npm run build` | OK (solo aviso de tamaño de chunk) |

Corrección a la primera ronda: los conteos 449 (ctest) y 80 (pytests) estaban mal; `ctest -N` da 410 y el log de pytests da `Ran 59 tests`, igual que la línea base del plan (402 + 8). No hay pruebas perdidas.

### Defectos de la primera ronda
1. **ALTA (perfil EE/PFE incoherente con el PV del desk) — CORREGIDO.** Cada swap entra al modelo con pagos diarios y una tasa fija efectiva calibrada al PV del desk (`_effective_fixed_rate`). Comprobado por mí: `InterestRateSwap.npv` con la tasa calibrada = PV del desk exacto en los 3 swaps. Simulación qfxva a t = 1e-6 (20 000 trayectorias): Alfa −856,895 frente a PV −942,898; Beta 1,566,515 frente a 1,602,629; Gamma −818,616 frente a −849,247 MXN. Ahora tienen el mismo signo y la diferencia restante no depende de sigma (barrido de 1e-7 a sigma: igual). EE en el primer mes: Alfa 0 → 580k, Gamma 0 → 929k, Beta 1.60 M → 2.10 M. Es una curva continua y ya no hay escalón (captura `r2/shots/credito.png`). CVA con supuestos 1 %/40 %: Alfa 12,026; Beta 93,764; Gamma 71,233.
2. **MEDIA (EE(0) sin compensar entre monedas) — CORREGIDO.** EE(0) = PFE(0) = max(suma del PV cubierto de la contraparte, 0). Lo cubre `test_ee_at_zero_nets_across_currencies_and_later_points_do_not` (Alfa con un swap SOFR, ambos signos del total). Mis scripts dan EE(0) = max(PV, 0) exacto en las 3 contrapartes, tanto en MX-DEMO como en D1. La Metodología y el pie de Crédito dicen que los puntos mensuales no compensan.
3. **BAJA (tabla P&L explicado desborda) — CORREGIDO.** A 1280 px la tabla mide 996 px en un contenedor de 996 px, así que la columna Residuo se ve sin desplazar.
4. **BAJA (códigos internos) — CORREGIDO.** El aviso ahora dice "…solo cubre swaps de tasas (IRS): Forward FX / Cap / Floor / Opción FX se excluye". En el texto de la pestaña Crédito no aparece `irs`, `fx_forward`, `cap_floor` ni `fx_option`.
5. **BAJA (biblioteca "Por omisión" duplicada) — CORREGIDO.** Se muestra una sola línea por escenario.

### Regresiones
- Los scripts `it_a`..`it_e` re-ejecutados dan 174 OK. Hay 2 FAIL, los dos en `it_d`, y son esperados: el script buscaba el texto viejo "swaps de tasa (irs)", que cambió a propósito con el defecto 4.
- R1 (cascada con residuo 0 y suma igual a `/api/pnl`), R2 (límites, umbrales y bitácora), R3 (VaR histórico ≈ paramétrico, 409/400), R5 (conjuntos, 404 dado de baja, igualdad por `set`/en línea) y triggers de solo inserción siguen igual.
- UI a 1280 px: `scrollWidth` = 1280 en las 6 pestañas y en Metodología, sin errores de consola ni respuestas HTTP ≥ 400.

### Veredictos (segunda ronda)
R1 CUMPLE · R2 CUMPLE · R3 CUMPLE · R4 CUMPLE (ya sin el defecto alto) · R5 CUMPLE · R6 CUMPLE · R7 CUMPLE · R8 CUMPLE.

### Defectos nuevos o restantes
1. **BAJA — Queda una diferencia de un cupón diario entre el ancla del desk y la simulación.** Con la tasa calibrada, el valor que simula qfxva en t → 0 queda por debajo del PV del desk en un monto fijo: Alfa −86k (9 % del PV, 0.017 % del nocional), Beta −36k (2 %), Gamma −1.6k USD (4 %). No depende de sigma: es el cupón diario que el modelo pierde al revaluar en t > 0. La prueba `test_simulated_swap_starts_at_the_desk_pv…` lo tolera (0.05 % del nocional) y además lo oculta, porque usa sigma = 1e-7. El docstring dice "El perfil nace entonces del PV del desk", lo cual es cierto solo dentro de ese margen. No cambia el signo ni produce un escalón visible.
2. **BAJA (observación) — En un conjunto creado por el usuario siguen saliendo nombre y choque en dos líneas casi iguales** (p. ej. "TIIE-F +100" / "TIIE-F +100 pb"). Es lo que el usuario capturó; el arreglo solo deduplica cuando son iguales salvo el signo menos.
