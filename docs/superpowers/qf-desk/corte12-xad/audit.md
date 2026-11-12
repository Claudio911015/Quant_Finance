# Auditoría — corte 12: sensibilidades del XVA por diferenciación adjunta con XAD

Rama `feat/qf-desk`. Auditado contra `design.md` (R1–R9, con las respuestas de Fable P1–P8 y la decisión sobre R5). No se leyó `plan.md` ni se usaron los reportes de los implementadores. Todo lo de abajo lo medí o comprobé yo, con programas propios sobre `qfxva` y la API, y con la pantalla en Chrome headless (backend en 5099 con base temporal, CDP en 9359). Queda fuera el capítulo 16 de `docs/tex/`, que otro agente escribía durante la auditoría.

## Veredictos

| R | Veredicto | Evidencia |
|---|---|---|
| R1 Dependencia | **CUMPLE** | `FetchContent` con el hash `aaf4e9ca…` (etiqueta `v2.2.0`, commit del 2026-11-11), detrás de `QF_WITH_XAD`, que vale `ON` por omisión. `build/_deps/xad-src/LICENSE.md` es la GNU AGPL v3, «o (a tu elección) cualquier versión posterior», y el README de XAD ofrece además una licencia comercial. Lo que dice `desk/README.md` es cierto (AGPL-3.0 o posterior, licencia comercial aparte, versión fijada por hash y recién publicada). En `/tmp/qf-noxad`, reconstruido sobre el HEAD: compila, ctest da 510/510 y pytests 101 OK, `qfxva.HAS_XAD` vale `False`, la ruta responde 501 con el texto «…el motor se compiló sin XAD (QF_WITH_XAD=OFF)», `GET /api/xva` responde 200 y una contraparte inexistente sigue dando 404. |
| R2 Motor diferenciable | **CUMPLE** | Bit a bit contra el árbol anterior al corte (worktree en `3d8f6f1`, compilado aparte y ya borrado). Las tres contrapartes sembradas, con 2000, 7 y 64 trayectorias, tienen idéntico el hash SHA-256 de `expected_value`, `epe`, `ene`, `pfe`, `epe_disc`, `ene_disc`, `path_disc_pos` y `path_disc_neg`. También son idénticos `value_at_zero`, `compute_xva` (cva, dva, fva, total y cva_stderr, comparados con `repr`) y `trade_values_at_zero`. El JSON de `GET /api/xva` sin los tiempos coincide byte a byte (28 959 caracteres). Diff de `exposure_engine.cpp`: +496/−134. El refactor `0014cf9` (+240/−131) es casi todo cambio de tipos, con 32 líneas `template <class Real>`, `ModelT`/`MarketT` y `ouMomentsT`/`stepCovarianceT` (estas dos se movieron y `detail::` delega en ellas, no se duplicaron). La AAD (`c85df00` y `f0b47b2`, ≈ 255 líneas) contiene las tres excepciones aceptadas, cada una con su comentario: `discountAt(PillarCurve)` de ≈ 15 líneas, el bucle por trayectoria y la suma ponderada. `survivalFromHazards` pasó a compartirse con `PiecewiseHazardCurve`. No encontré otra lógica duplicada. |
| R3 Sensibilidades por AAD | **CUMPLE** | Se derivan los 48 insumos de cada conjunto sembrado (10 de TIIE-F, 10 de SOFR, 9 de MXN-USD, spot, 5 del modelo, 6+6 intensidades y fondeo) contra CVA, DVA y FVA en una pasada. La cinta es por trayectoria: la parte común se graba una vez por hilo y en cada trayectoria se hace `computeAdjointsTo(common)` → `clearDerivativesAfter` → `resetTo`; al final, `computeAdjoints()` lleva los adjuntos a los insumos. El jacobiano de CDS sale por reprecio del bootstrap (diferencia central de 0.01 pb) y la respuesta lo declara en `cds_jacobian`. |
| R4 Correctas | **CUMPLE** | Ver la tabla de discrepancias: todos los insumos de las 3 contrapartes, contra choque central con las mismas trayectorias (2000) y sin recalibrar nada. La peor diferencia relativa, 4×10⁻⁴, está en σ Hull-White. Con volatilidad cero comparé la AAD con mi propia derivada analítica (regla de la cadena del caso determinista sobre un swap TIIE-F de 5 años; probé pagadora, receptora y uno que cambia de signo): error relativo ≤ 3×10⁻¹⁵ en CVA, DVA y FVA, y las derivadas respecto de SOFR, spot y volatilidades son exactamente 0. Mutación: no hay una prueba permanente. Las pruebas de C++ recorren cada pilar de cada curva (`expectCurveAgrees`), así que omitir la dependencia de un pilar las rompería. No volví a ejecutar la mutación yo. |
| R5 Eficientes (redefinido) | **CUMPLE** | Medido con un núcleo (`taskset -c 3`, AAD con `max_threads=1`, el mejor de 3; build Debug, que es el que sirve la API): Alfa 10.85 s / 1.47 s = **7.4×**, Beta 21.43 / 2.67 = **8.0×**, Gamma 8.81 / 1.36 = **6.5×**, todos ≤ 10. La AAD usa como máximo 2 hilos (`maxThreads = 2` por omisión). Tiempos reales de la ruta: Alfa 6.2 s, Beta 12.6 s y Gamma 5.7 s de reloj (`elapsed_s` 5.9, 12.0 y 5.4); la respuesta trae `bump_cost_estimate_s` (30, 60 y 35 s). La memoria no crece con las trayectorias: el RSS máximo de un proceso aislado (Beta) fue de 137.4, 137.5, 137.6 y 137.5 MB con 100, 500, 2000 y 6000 trayectorias. El RSS máximo del backend durante las peticiones fue de 154 MB. |
| R6 API | **CUMPLE** | Unidades verificadas contra las derivadas crudas del motor, con error relativo 0: pilar ×1e-4, spot ×0.01·spot (18.6), vol USDMXN ×0.01, σ ×1e-4, a ×0.01, fondeo e intensidades ×1e-4. El DV01 es la suma de los pilares, `total` = CVA − DVA + FVA en todas las filas, y CDS por pb coincide con el reprecio completo del bootstrap con error relativo ≤ 6×10⁻¹⁰. El `xva` de la ruta es igual al de `GET /api/xva` por HTTP en las 3 contrapartes. Los errores también responden bien: contraparte inexistente 404 (`field: counterparty`), sin `counterparty` 400, snapshot inexistente 404, y una contraparte sin operaciones da 200 con listas vacías, `empty_reason` y XVA 0. Las derivadas son parciales (`assumptions`) y se usan los mismos parámetros, malla y semilla. |
| R7 Interfaz | **CUMPLE** | En `/xva`, con el backend real, calculé las 3 contrapartes: el aviso «puede tardar decenas de segundos» aparece antes y durante el cálculo; al terminar se muestran el tiempo real, el de una valuación y el costo por choques; hay una tabla por curva y pilar con DV01 y otra de tipo de cambio, volatilidades, CDS por plazo de la contraparte y propios, y fondeo, con la unidad en cada grupo; y una gráfica de barras del CVA por pilar con una serie por curva en una sola gráfica. A 1280 px no hay desborde horizontal ni elementos fuera del ancho, no hay errores ni advertencias de consola, y los rótulos están en español. |
| R8 Metodología (interfaz) | **CUMPLE** | La sección «Sensibilidades del XVA» explica qué se deriva y respecto de qué, las unidades (las mismas que la API), el método adjunto, que las derivadas son trayectoria a trayectoria con las mismas trayectorias, malla y semilla, el costo, que son derivadas parciales sin recalibrar, los límites (sin segundo orden, sin correlaciones, sin PFE) y que XAD es AGPL-3.0 y opcional. El capítulo LaTeX no se auditó (fuera de alcance). |
| R9 Suites | **CUMPLE** (sin las verificaciones de `docs/tex`) | ctest 518/518, más 1 `DISABLED_AadTiming` que no corre; pytests 101 OK; `desk/api/tests` 3805 passed; vitest 681 passed; `npm run build` OK (solo el aviso de tamaño de chunk). Sin XAD: ctest 510/510 y pytests 101 OK. Validación QuantLib: 62 de 62 dentro, `desk_commit` f0b47b2 = commit vigente de valuación, así que `commit_matches: true`. No ejecuté las verificaciones de `docs/tex/`, porque el capítulo 16 estaba en curso. |

## Discrepancias AAD contra choque central (todas las entradas, mismas 2000 trayectorias, semilla 42)

Las derivadas están por unidad de insumo (tasa cero, σ, a, vol, λ y fondeo en decimal; spot en MXN/USD). La columna «rel» es el máximo de |AAD−choque|/|choque| entre las derivadas con |choque| > 1. La columna «abs» es el máximo de |AAD−choque|. Hay 48 insumos × CVA/DVA/FVA por contraparte.

| Clase (n insumos) | Alfa rel / abs | Beta rel / abs | Gamma rel / abs | Peor caso |
|---|---|---|---|---|
| Pilares TIIE-F (10) | 4.1e-5 / 121 | 8.2e-6 / 55 | 3.6e-4 / 18 | Gamma TIIE-F[5] CVA 827 006 contra 826 988 |
| Pilares SOFR (10) | 4.8e-5 / 41 | 1.9e-5 / 232 | 5.5e-5 / 470 | Gamma SOFR[6] DVA |
| Pilares MXN-USD (9) | 6.5e-6 / 11 | 9.0e-6 / 48 | 7.5e-6 / 10 | — |
| Spot (1) | 8.8e-5 / 12 | 4.0e-5 / 5.3 | 6.8e-5 / 2.7 | — |
| Vol USDMXN, σ y a de cada moneda (5) | 4.0e-4 / 26 | 1.6e-4 / 795 | 4.8e-5 / 435 | Alfa fx_vol DVA; Beta σ_USD CVA |
| Intensidades contraparte (6) | 6.6e-9 / 1.4e-4 | 8.5e-8 / 3.5e-4 | 1.8e-8 / 7.3e-5 | — |
| Intensidades propias (6) | 6.6e-9 / 8.2e-4 | 8.5e-8 / 1.1e-4 | 1.8e-8 / 2.1e-4 | — |
| Fondeo (1) | 1.7e-13 / 7e-6 | 2.8e-13 / 1.7e-6 | 2.5e-13 / 5.8e-6 | — |
| CDS contraparte (6), API por pb contra bootstrap completo | 2.1e-10 / 3e-7 | 7.6e-11 / 6e-8 | 5.7e-10 / 1e-7 | — |
| CDS propios (6), igual | 2.0e-10 / 8e-7 | 8.3e-11 / 8e-8 | 4.7e-10 / 4e-7 | — |
| Volatilidad cero, analítica propia (swap TIIE-F) | rel ≤ 3e-15 | | | |

El valor por AAD (media de las sumas por trayectoria) coincide con `compute_xva` hasta ~1e-15 relativo. 1 hilo contra 2: hay diferencias de redondeo (máx. 2.3e-5 MXN por unidad en una derivada de 33, y ≤ 1e-12 en escala de la clase). Con 2 hilos, repetir la corrida da resultados idénticos bit a bit, sin carreras.

**Signos y sentido económico.** DVA sube con la intensidad propia y CVA con la de la contraparte. Las volatilidades (vol FX y σ) suben CVA y DVA a la vez y `a` los baja, que es lo esperado de la opcionalidad. El fondeo solo mueve FVA, y FVA/0.5 % es igual a la sensibilidad por pb (Alfa −4125 = −206 233/50). Total = CVA − DVA + FVA. Un CDS de 1 año con sensibilidad negativa (en las 3 contrapartes) es el efecto del bootstrap, porque subir la cotización a 1 año baja la intensidad de los tramos siguientes, y coincide con el reprecio completo. Los plazos que el conjunto no alcanza dan 0.

## Lo construido que nadie pidió

- `detail::aadTapeBytes()` y `aadThreads()` son estado global (atómicos) de «la última llamada», solo para pruebas. Peticiones concurrentes las sobrescriben (es un diagnóstico, no afecta resultados).
- Parámetro `max_threads` expuesto en el binding de Python. Es útil para medir, pero no lo pide R5, que solo fija el tope.
- Bloque `hazards` del crédito en la respuesta cuando hay curva de CDS. La interfaz no lo muestra (solo enseña CDS), aunque R3(e) sí lo justifica.
- `key={reloadTick}` en `XvaScreen` para descartar sensibilidades obsoletas al cambiar parámetros. Es razonable y no estaba pedido.
- Refactor `run_notes` en `xva.py`, para que ambas rutas declaren las mismas notas. No cambia `GET /api/xva` (verificado byte a byte).

## Defectos

| Sev. | Defecto |
|---|---|
| media | **Presupuesto de Python excedido en bruto.** `xva_sens.py` tiene 130 líneas (108 de código sin docstrings ni comentarios), la ruta +5 y `xva.py` +20/−11. En total son ≈ 144 líneas netas, contra el tope de 120. Contando solo código queda en ≈ 122, al límite. Se puede recortar: la lista `hazards` duplicada cuando hay CDS (la UI no la usa), el `+ 7` manual de `n_inputs` (sale de contar las derivadas) y el diccionario `UNITS`, cuyos textos repite la UI. |
| baja | **R4 «una prueba detecta un adjunto mal propagado».** No existe como prueba permanente: hubo una mutación manual que luego se revirtió. La cobertura pilar a pilar la detectaría, pero el requisito pedía la prueba. |
| baja | **Volatilidad cero.** Con σ o la vol FX exactamente en 0, su derivada sale 0, porque `choleskySemidefinite` anula la columna, en lugar de la derivada lateral. No está documentado como límite. No afecta a los snapshots reales. |
| baja | `xvaSensitivities` valida el fondeo con el mensaje «computeXva: funding spread…»: el prefijo es el de otra función. |
| baja | `bump_cost_estimate_s` = 2 × insumos × `valuation_elapsed_s`, y esa valuación mide `_counterparty` completa con 8 hilos, mientras la AAD usa 2. La comparación de la interfaz mezcla números de hilos sin decirlo. |
| baja | Todo se mide en un build **Debug** (`CMAKE_BUILD_TYPE=Debug` en `build/`, que es el que sirve la API). Las razones de R5 (6.5–8.0× con un núcleo) y la cifra de la Metodología («unas 9 veces») valen para ese build. |
| baja | Las peticiones concurrentes a la ruta (Flask con hilos) multiplican la memoria: cada una usa hasta 2 cintas. No hay un tope global. |

No encontré defectos de severidad alta.

## Conteo de pruebas

ctest 518/518 con XAD (más 1 deshabilitada), 510/510 sin XAD; pytests 101 OK en ambos; `desk/api/tests` 3805 passed; vitest 681 passed; `npm run build` OK; validación QuantLib 62/62 con `commit_matches: true`.

Estado al terminar: no se modificó el árbol. Se borraron el worktree `/tmp/qf-pre-xad` y sus logs, se apagaron el backend 5099 y Chrome 9359, y se conservó `/tmp/qf-noxad`, reconstruido sobre el HEAD del momento.
