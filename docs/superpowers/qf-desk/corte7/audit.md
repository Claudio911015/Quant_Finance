# Auditoría independiente — QF Desk corte 7 (validación contra QuantLib)

Rama `corte7`, commits ce51edf..ce01c28 (13 commits, todos de Claudio, sin Co-Authored-By). Auditado contra `design.md`, sin leer `plan.md`.
Backend real en 127.0.0.1:5097 con base temporal; Chrome headless propio en 9357 a 1280 px. Todo apagado al terminar; árbol de trabajo limpio (`git status` vacío).

## Suites

- C++ (`cmake --build build && ctest`) y `pytests`: **omitidas**, no hay árbol de CMake configurado en este worktree (`build/` solo contiene `src/qfpy*.so`); el corte no toca C++.
- Backend: `pytest desk/api/tests -q` → **2365 passed**, 0 fallos.
- UI: `npm test` → **19 archivos, 287 tests passed**.
- UI: `npm run build` → OK (solo el aviso conocido de bundle > 500 kB).
- Ninguna suite importa QuantLib (grep: solo `desk/validation/ql_*.py` y `run_quantlib.py` lo importan).

## Veredictos

### R1 — CUMPLE
Se corrió `desk/validation/make_report.sh` de punta a punta (exit 0, 0.4 s): `cases.json: 62 casos`, `reference.json: 62 casos, 62 con PV, 0 errores`, `report.json: 62 · 61 dentro · 1 explicada · 0 fuera`. Conteo propio por producto: irs 12, fx_option 10, fx_forward 8, equity_option 8, bond 8, cap_floor 8, swaption 8 (7 productos, ≥ 5 cada uno, 62 ≥ 60). El reporte regenerado es idéntico al versionado (diferencia máxima de PV desk y QL = 0; mismo `desk_commit` 02d9dd3, `desk_dirty` false); solo cambian marcas de tiempo. Los JSON se restauraron con `git checkout` tras la prueba.

### R2 — CUMPLE
Recalculo propio de |PV_desk − PV_ref|/nocional: peor por producto irs 5.99e-15, fx_forward 3.08e-16, fx_option 1.13e-16, equity_option 1.09e-16, bond 5.94e-8 (bond-08, cupón de 182.5 días vs fechas enteras), cap_floor 2.79e-16, swaption 1.84e-3. Único caso sobre tolerancia: swaption-04 (1.8432e-3 > 5e-4), listado en `known_differences.json` con causa concreta (bracket de bisección [f0 ± 10σ_r] en `src/instruments/swaption.cpp:162-168` que deja fuera la raíz y devuelve 0.0), magnitud esperada 1.843e-3 y cota 2e-3. Verificado: la réplica `T7-swaption-repro.py` reproduce las 8 diferencias de swaption con cociente observado/esperado 0.99–1.015, y el código C++ tiene exactamente ese bracket y el `return 0.0`.

### R3 — CUMPLE
Dos curvas (TIIE-F, SOFR), 10 pilares y 10 fechas intermedias cada una (estrictamente dentro de los pilares). Máx. |DF_desk − DF_QL|: pilares 0 en ambas (≤ 1e-12), intermedias 1.11e-16 en ambas (≤ 1e-8). Los DF del desk salen de `curve.discount_factor` del propio desk (no de una réplica), así que la comparación no es circular. Interpolación declarada: ZeroCurve lineal en cero continua, Actual365Fixed, plana fuera de pilares.

### R4 — CUMPLE
`GET /api/validation/report` → 200 con `generated_at`, `reference` (QuantLib 1.44, Python 3.12.16, entorno quantsuite-oracle), `desk_commit`, `current_commit`, `commit_matches: true`, totals, 7 filas de resumen, 2 curvas, 62 casos, 1 diferencia conocida. Pantalla `/validacion` a 1280 px: secciones Resumen por producto, Curvas, Casos (filtros por producto y veredicto, «Mostrando 62 de 62»), Diferencias conocidas y Cómo reproducir; fecha, versión y commit en la cabecera. Medición DOM: `scrollWidth` 1280 = `clientWidth`, ningún elemento con desborde horizontal ni recortado (incluida la columna Veredicto). Aviso de commit distinto comprobado con un backend parcheado (`desk_commit` falso): «El reporte se generó con el commit 02d9dd3 y el código de valuación actual está en abcdef1: regenera el reporte…». Navegación y paleta incluyen «Validación». Textos en español (con los detalles de pluralización de abajo).

### R5 — CUMPLE
`test_validation_report.py` existe y pasa. Mutaciones propias: (a) sumar 1 MXN a `pv_desk` de irs-01 → falla («rel_diff guardado … recalculado …»); (b) alterar `pv_desk` de fx_option-01 en 1e-5 del nocional recalculando abs/rel a mano → falla (veredicto y resumen no cuadran); (c) borrar `report.json` → falla con mensaje claro. Restaurado después.

### R6 — CUMPLE
`desk/validation/README.md` explica entorno (Python del backend 3.8, `quantsuite-oracle` con QuantLib 1.44, alternativa `pip install QuantLib==1.44`), `make_report.sh`, pasos sueltos, tolerancias, `desk_commit/desk_dirty` y cómo agregar casos. Metodología tiene la sección «Validación independiente» con enlace a la pantalla Validación y lo que no se compara (riesgo, XVA, contabilidad de coberturas, ORE).

### R7 — CUMPLE (con salvedad)
Backend, `npm test` y `npm run build` pasan; QuantLib no se importa en ninguna suite. Las dos suites de C++ no se pueden correr en este worktree (sin árbol de CMake); el corte no modifica `src/`, `include/` ni CMake.

## Construido sin que ningún R lo pidiera

- Sección «Curvas» en la pantalla y columna «Método de referencia» por producto (útiles; apoyan R3).
- Aviso de `desk_dirty` y aviso cuando git no está disponible (`commit_matches: null`).
- `desk_commit` = último commit que toca `VALUATION_PATHS` en lugar de `HEAD` (decisión razonable y documentada).
- Tests extra de backend: `test_validation_cases.py` (62 casos, PV = pricer), `test_validation_curves.py`, `test_validation_route.py`.
- Variables `BACKEND_PY`/`QL_PY` en `make_report.sh`; `--cases/--out` en `run_quantlib.py`, `--out` en `export_cases.py`.
- `validationFixture.ts` para los tests de UI.

## Defectos fuera de los R

- **Media** — Defecto real de valuación abierto: el desk devuelve PV 0.0 para swaption-04 (receptora TIIE-F, expira en 182 días), que vale ≈ 92,158.63 MXN. D3 y las Restricciones piden corregir aquí, con test, los defectos del desk que destape la validación; se dejó documentado como `defect` porque el worktree no compila C++. Hay que corregir `Swaption::price` (bracket en `src/instruments/swaption.cpp:162-168`) en otro corte o tras la fusión y borrar la entrada de `known_differences.json`.
- **Baja** — La prueba de humo no compara `report.json` contra `cases.json`/`reference.json`: si se edita `pv_desk` y se recalculan a mano `abs_diff`/`rel_diff` con un cambio que quede dentro de tolerancia, la suite pasa. R5 se cumple tal como está escrito.
- **Baja** — Pluralización sin concordancia en rótulos de casos: «swap de 1 años», «1 periodos», «1 cupones» (swaption-04, irs-06, irs-09, bond-03).
- **Baja** — En «Cómo reproducir», el paso 2 dice `run_quantlib.py` sin ruta ni intérprete, mientras que los pasos 1 y 3 dan el comando completo; el README sí lo da bien.
- **Baja** — El enlace de Metodología a Validación es `<a href="/validacion">` en lugar de un `Link` de React Router: recarga la página completa. Funciona porque el backend tiene fallback de SPA.
- **Baja** — `test_desk_commit_es_un_sha_de_40_hex_en_este_worktree` depende de que exista git; la suite falla si se corre desde un tarball sin `.git`.
- **Informativa** — Al fusionar otros cortes que toquen `VALUATION_PATHS` (p. ej. `desk/api/market.py`), la pantalla mostrará el aviso de commit distinto hasta regenerar el reporte. Es el comportamiento diseñado y el README lo dice.

## Segunda ronda

Commits nuevos revisados: dc99a0e..37153d8 (c5b822c, f4a4fbe, 78e098d, 37153d8). Sin `NO CUMPLE` en la primera ronda; se revisan los defectos y se vuelven a correr las suites. Backend probado con el cliente de pruebas de Flask y base temporal (no se levantaron procesos en 5097/9357; los cambios de UI de esta ronda son solo el fixture de tests). Árbol limpio al terminar.

### Suites
- C++ (`cmake --build build && ctest`) y `pytests`: **omitidas**, sigue sin haber árbol de CMake en el worktree (`build/` solo tiene `src/`); el corte no toca C++.
- Backend: `pytest desk/api/tests -q` → **2373 passed**, 0 fallos (antes 2365).
- UI: `npm test` → **19 archivos, 287 tests passed**. `npm run build` → OK (aviso conocido de bundle > 500 kB).

### Veredictos
- R1 CUMPLE — `make_report.sh` de punta a punta: 62 casos, 62 con PV, 0 errores; 61 dentro · 1 explicada · 0 fuera. PV regenerados idénticos a los versionados (diferencia máx. 0), `desk_commit` 78e098d, `desk_dirty` false. JSON restaurados con `git checkout`.
- R2 CUMPLE — sin cambio en PV; swaption-04 sigue como única diferencia explicada.
- R3 CUMPLE — sin cambios en curvas.
- R4 CUMPLE — `GET /api/validation/report` 200, `commit_matches: true` (78e098d = 78e098d), pasos de reproducción completos.
- R5 CUMPLE — reforzado: una mutación de 1e-9 MXN en `pv_desk` de irs-03 con abs/rel recalculados (dentro de tolerancia) ahora falla («pv_desk del reporte … distinto del de cases.json»); +1 MXN en irs-01 también falla.
- R6 CUMPLE — sin cambios.
- R7 CUMPLE (con la misma salvedad de C++).

### Estado de los defectos de la primera ronda
- Media, swaption-04 PV 0.0: **sigue abierto**. No se corrigió `Swaption::price` (este worktree no compila C++); sigue documentado como `defect` en `known_differences.json` con causa y magnitud. Debe corregirse en C++ tras la fusión o en otro corte, con test, y borrar la entrada.
- Baja, prueba de humo sin cruce con cases/reference: **corregido** (c5b822c), verificado por mutación.
- Baja, pluralización: **corregido** (78e098d): «1 periodo», «1 cupón», «swap de 1 año» en irs-06, irs-09, bond-03, swaption-04.
- Baja, paso 2 de «Cómo reproducir»: **corregido** (`python desk/validation/run_quantlib.py  # con el Python de QuantLib`).
- Baja, test de SHA sin git: **corregido** (f4a4fbe); en una copia `git archive` sin `.git` los tests de reporte y ruta pasan (15 passed).
- Baja, enlace `<a href="/validacion">` en Metodología: **no corregido** (MethodologyScreen.tsx:366); funciona por el fallback SPA.

### Regresiones
Ninguna encontrada.

### Defectos nuevos
- Baja — la salida de `compare.py` dice «1 explicadas» (sin concordancia); solo consola, no pantalla.
