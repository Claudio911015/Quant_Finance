# Auditoría — Documentación técnica en LaTeX de QF Desk (`docs/tex/`, rama `feat/qf-desk`)

Fecha: 2026-11-11. Auditor independiente. No se modificó nada del repositorio ni se hicieron commits; todo lo
generado vive en `/tmp/qfdocs-audit/` (compilación) y en el scratchpad (verificación bibliográfica).
No se leyó `plan.md` ni se usaron los reportes de los redactores: cada afirmación de abajo se comprobó.

## 1. Veredicto por requisito

| R | Veredicto | Evidencia |
|---|---|---|
| R1 Compila | **CUMPLE** | `mkdir -p /tmp/qfdocs-audit/capitulos && cd docs/tex && latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=/tmp/qfdocs-audit qfdesk.tex` → rc=0, 167 páginas. `command grep -a -c -E "(Citation\|Reference).*undefined"` = 0; sin «There were undefined». Cajas desbordadas: 5, la mayor 7.81 pt (todas < 10 pt). `bibtex`: 0 warnings, 51 `\bibitem` = 51 entradas. Solo pdflatex/latexmk/bibtex. `.gitignore` excluye el PDF y auxiliares; README dice cómo compilar (también con `-outdir`). |
| R2 Estructura | **CUMPLE** (con defectos bajos) | `report`, español (`\babelprovide` declarado en README, respuesta 5 de Fable), un archivo por capítulo, `preambulo.tex`, `referencias.bib`, `plainnat-es.bst` con «y». Orden 1–15 correcto; cap. 4 titulado «Derivados de FX y opción sobre acción» (respuesta 2); apéndice de símbolos. Defectos: colisiones de notación (ver D-7). |
| R3 Fórmulas fieles | **CUMPLE** | `correr.py` rc=0: 13 scripts, 349 valores; cada capítulo 2–12 tiene ≥ 2 `\verif` (cap02 16, cap03 34, cap04 14, cap05 8, cap06 9, cap07 9, cap08 9, cap09 29, cap10 30, cap11 10, cap12 12; cap14 69, cap15 100). 46 fórmulas comparadas línea por línea contra el código (sección 5): **ninguna** describe el libro en lugar del código. Recuadros «Diferencia con la referencia» en todos los capítulos (incl. cupón de bono, composición continua del periodo en curso del XVA, base determinista). `comun.py` lee el valor impreso del propio `.tex` (no puede divergir). |
| R4 Referencias al código | **CUMPLE** | `referencias_codigo.py` rc=0: **1136** `\codigo`, 0 fallos (≥ 120). Toda `\section` con cálculo tiene ≥ 1 `\codigo`; 11 `\subsection` de ejemplos (y la subsección «Cobertura de valor razonable» del cap. 10) no tienen una propia pero su sección sí (D-9). Sin números de línea. |
| R5 Referencias académicas | **CUMPLE** (discrepancias menores) | 51 entradas (≥ 25), todas citadas; cada cap. 2–12 cita ≥ 2 obras. 36 libros/artículos con DOI/ISBN confirmados contra Crossref u Open Library (autores, título, año, revista/editorial, volumen, páginas); 15 `@manual` con URL oficial que responde y corresponde (FRED vía su CSV oficial, la página HTML no respondió en 90 s). Ninguna obra inventada. Discrepancias: tabla de la sección 2. Citas dudosas: sección 3. |
| R6 Honestidad | **CUMPLE** | Cada capítulo tiene recuadro `limites`; los límites de la Metodología (`MethodologyScreen.tsx`) están en el capítulo que corresponde: datos sintéticos (12 capítulos), fechas de pago sin ajuste (11), M-Bono 182 días fuera (cap06), acción con cero en DV01/VaR (cap04, cap09), sin wrong-way/base determinista/EPE* con cuenta TIIE-F/composición continua (cap14), pago solo MXN/sin rebate ni one touch/fuera del portafolio/vanna-volga (cap15), cliente Banxico sin probar con token (cap13), escenarios históricos aproximados (cap09). Aviso IFRS 9 en recuadro `aviso` al inicio del cap. 10 («pendiente de revisión por un contador… nadie la ha hecho aún»). No encontré nada descrito como hecho que el código no haga (comprobado: recalibración de MXN-USD en `shifted`, motor XVA sin `HullWhite`/`CVACalculator`, malla de integración `INTEGRATION_STEP=3`, ramas de `valuation.shortened` borradas, `hedge_ratio_mismatch`, `terms_flag` nulo de H17). Omisiones menores: D-10. |
| R7 Plantilla y README | **CUMPLE** (defectos bajos) | `_plantilla.tex` con las 8 secciones obligatorias; README con compilación (normal y `-outdir`), las dos verificaciones, excepción `@manual` declarada (respuesta 1), partición inglesa declarada, lista de comprobación de 11 pasos. Defectos: D-11. |
| R8 Sin tocar código | **CUMPLE** (una salvedad baja) | De `356ce1a` (esqueleto) a `HEAD`, los commits `docs(tex)`/`docs(hallazgos)` solo tocan `docs/tex/`, salvo `55332a9`, que además añade una sección a `docs/superpowers/qf-desk/corte10-fx-exoticos/plan.md` (documentación, no código: D-12). Los cambios de código del periodo (`f39d31f`, `2c1a4ab`, `1754d54`, …, `cc9344b`, `dfce263`) son las resoluciones de HALLAZGOS hechas por otras tareas, con su propio prefijo. |

## 2. Verificación de `referencias.bib` (51 entradas)

Fuentes: Crossref = `api.crossref.org/works/<doi>`; OL = `openlibrary.org/isbn/<isbn>.json` (+ autores por `/authors/<id>.json`); URL = GET de la URL oficial (código y `<title>`/primera página del PDF).

| Clave | Fuente consultada | Resultado | Discrepancias |
|---|---|---|---|
| hull1990 | Crossref 10.1093/rfs/3.4.573 | Confirmada | — |
| jamshidian1989 | Crossref 10.1111/j.1540-6261.1989.tb02413.x | Confirmada (44(1):205–209) | — |
| garman1983 | Crossref 10.1016/S0261-5606(83)80001-1 | Confirmada | — |
| black1976 | Crossref 10.1016/0304-405X(76)90024-6 | Confirmada | — |
| black1973 | Crossref 10.1086/260062 | Confirmada | — |
| hagan2006 | Crossref 10.1080/13504860500396032 | Confirmada | — |
| brigo2006 | Crossref 10.1007/978-3-540-34604-3 + OL 9783540221494 | Confirmada (Springer Finance, 2.ª ed.) | — |
| andersen2010 | OL 9780984422104 | Confirmada (Atlantic Financial Press, 2010) | — |
| hull2018 | OL 9780134472089 | Confirmada (Pearson, 10.ª ed.) | OL fecha la edición en ene-2017 (copyright 2018): aceptable |
| gregory2015 | OL 9781119109419 | Confirmada (Wiley, 2015) | — |
| glasserman2003 | Crossref 10.1007/978-0-387-21617-1 + OL 9780387004518 | Confirmada | — |
| jorion2007 | OL 9780071464956 | Confirmada (3.ª ed.) | OL: oct-2006 (copyright 2007): aceptable |
| mcneil2015 | OL 9780691166278 | Confirmada (ed. revisada 2015) | — |
| iasb2014 | URL ifrs.org | 200, «IFRS 9 Financial Instruments» | — |
| nyfed2026 | URL newyorkfed.org | 200, «Secured Overnight Financing Rate Data» | — |
| banxico2021 | URL banxico.org.mx (PDF) | 200, PDF «Determinación de la tasa TIIE de Fondeo» | Año inferido de los metadatos del PDF (declarado en la nota) |
| morini2011 | Crossref 10.1002/9781118467312 + OL 9780470977613 | Confirmada | — |
| fed2011 | URL federalreserve.gov (PDF) | 200, «SR Letter 11-7 Attachment … April 4, 2011» | — |
| ramirez2015 | Crossref 10.1002/9781119065876 + OL | Confirmada (ISBN de la edición electrónica) | — |
| merton1973 | Crossref 10.2307/3003143 | Confirmada (Bell J., 4(1), 1973) | **Falta `pages` (141–183)**; la bibliografía impresa sale sin páginas |
| du2018 | Crossref 10.1111/jofi.12620 | Confirmada | — |
| fujii2009 | Crossref 10.2139/ssrn.1440633 | Confirmada | Tipo `@misc`: **el DOI no se imprime** (la función `misc` de `plainnat-es.bst` no emite `doi`) |
| wystup2017 | OL 9781118471135 | Confirmada (Wiley, 2017) | Es la 2.ª edición; `edition` no consta |
| gamma1995 | OL 9780201633610 | Confirmada (4 autores) | — |
| banxico2026a | URL SIE API (JSON) | 200, SF331451 «TIIE de Fondeo a Un Día Hábil Bancario, Mediana ponderada por volumen» | — |
| banxico2026b | URL SIE API (JSON) | 200, SF43718 «Tipo de cambio Pesos por dólar…» | — |
| fred2026 | URL fred.stlouisfed.org | HTML sin respuesta en 90 s (2 intentos); la serie DEXMXUS existe (CSV oficial `fredgraph.csv?id=DEXMXUS` responde) | No se pudo abrir la página HTML citada |
| treasury2026 | URL home.treasury.gov | 200, «Daily Treasury Rates» | — |
| ametrano2013 | Crossref 10.2139/ssrn.2219548 | Confirmada | — |
| tuckman2012 | OL 9780470891698 | Confirmada (3.ª ed.) | — |
| ho1992 | Crossref 10.3905/jfi.1992.408049 | Confirmada (2(2):29–44) | Título completo «Key Rate Durations: Measures of Interest Rate Risks» (subtítulo omitido; Crossref solo da el principal) |
| acerbi2002 | Crossref 10.1016/S0378-4266(02)00283-2 | Confirmada | — |
| hyndman1996 | Crossref 10.1080/00031305.1996.10473566 | Confirmada | — |
| isda2021 | URL isda.org | 200, «2021 ISDA Interest Rate Derivatives Definitions» | La nota reconoce que el texto completo no se abrió |
| meeus1998 | OL 9780943396613 | Confirmada (Willmann-Bell, 1998) | Es la 2.ª edición; `edition` no consta |
| banxico2026c | URL banxico.org.mx (PDF) | 200, PDF «2026 bank holidays» | — |
| sifma2026 | URL sifma.org | 308 → misma ruta sin «/» final → 200 «Holiday Schedule - SIFMA» | URL con redirección permanente |
| frb2026 | URL federalreserve.gov/aboutthefed/k8.htm | 200, «Holidays Observed - K.8» | — |
| cdm2026 | URL cdm.finos.org | 200, «Event Model \| Common Domain Model» | — |
| fpml2026 | URL fpml.org | 200, «What is FpML®?» | — |
| bcbs2015 | URL bis.org (PDF) | 200, «Margin requirements for non-centrally cleared derivatives», March 2015; §3.15 trata disputas de valuación (comprobado en el PDF) | — |
| ritchken1995 | Crossref 10.1111/j.1467-9965.1995.tb00101.x | Confirmada | — |
| hull2000 | Crossref 10.3905/jod.2000.319115 | Confirmada | Autor «Hull, John C.» vs «Hull, John» en hull1990 (forma inconsistente, cosmético) |
| okane2008 | OL 9780470519288 | Confirmada | — |
| brigo2013 | Crossref 10.1002/9781118818589 + OL | Confirmada | ISBN de la edición electrónica |
| beaglehole1997 | Crossref 10.2469/faj.v53.n1.2057 | Confirmada | — |
| broadie1997 | Crossref 10.1111/1467-9965.00035 | Confirmada | — |
| kunitomo1992 | Crossref 10.1111/j.1467-9965.1992.tb00033.x | Confirmada | — |
| hui1996 | Crossref 10.1080/096031096334141 | Confirmada | — |
| haug2007 | OL 9780071389976 | Confirmada (2.ª ed.) | OL: dic-2006 (copyright 2007): aceptable |
| gatheral2006 | OL 9780470068250 | Confirmada (Wiley, 2006) | — |

Resumen: **51/51 obras existen**; 36 confirmadas por DOI/ISBN con metadatos coincidentes, 15 `@manual` con URL oficial que responde y corresponde (fred2026 solo por su endpoint CSV). Discrepancias, todas bajas: merton1973 sin páginas; fujii2009 con DOI no impreso; wystup2017 y meeus1998 sin edición; ho1992 sin subtítulo; fred2026 HTML no verificable desde aquí; forma de autor de Hull inconsistente.

## 3. Muestreo de citas (≥ 25, todos los capítulos)

Revisadas 58 citas (cap01 7, cap02 6, cap03 7, cap04 6, cap05 5, cap06 3, cap07 4, cap08 5, cap09 6, cap10 4, cap11 4, cap12 5, cap13 4, cap14 8, cap15 8). Respaldan razonablemente la afirmación, entre otras: hull1990/jamshidian1989/brigo2006 (cap. 3) en el cap05; garman1983/black1973/merton1973/black1976/wystup2017 en el cap04; fujii2009/du2018 en el cap07; ho1992, acerbi2002 (pesos fraccionarios del ES), hyndman1996 (definición 1, leída sobre el P&L a nivel 1−α) en el cap09; iasb2014 §6.5.6 y §6.5.12 y «la norma no fija umbral» en el cap10; bcbs2015 §3.15 (comprobado en el PDF) en el cap11; fed2011 (benchmarking) en el cap12; gatheral2006 (Dupire en varianza total, misma expresión), broadie1997 (β≈0.5826), beaglehole1997, glasserman2003 cap. 6 (puente) en el cap15; hull2000/okane2008 (CDS), ritchken1995 (forma de Markov) en el cap14.

Citas dudosas:

1. **cap01, §calendario US (y docstring de `calendars._observed`)**: «… el 2023-11-10 (viernes), día en que se habría observado Veterans Day (sábado 11); las Reservas Federales abren los viernes anteriores a un feriado en sábado \citep{frb2026}.» La página K.8 dice eso para *todo* feriado en sábado (lista explícitamente el 3-jul-2026 como día en que los Bancos de la Reserva abren), pero el código y el propio capítulo tratan 2026-07-03 como inhábil sin SOFR. La obra no explica por qué Veterans Day se trata distinto que el 4 de julio; la fuente que sí distingue es la recomendación de cierre de SIFMA. Cita que no respalda la regla que se le atribuye. Severidad media-baja.
2. **cap14, §14.3.3 «Transición exacta y trayectorias»**: «Cada trayectoria p toma sus cinco normales diarias de un std::mt19937_64 sembrado con (semilla,p) \citep[cap.~3]{glasserman2003}». El cap. 3 de Glasserman trata la generación de trayectorias, no el sembrado por trayectoria con `mt19937_64` (generadores en el cap. 2, y nada sobre esa siembra). Baja.
3. **cap10, §Límites**: «La prueba es de escenarios con razón de cambios, no de regresión ni de mínima varianza \citep{hull2018}». Hull trata la razón de mínima varianza con futuros, no las pruebas de efectividad contable (regresión, dollar offset); la frase de referencias lo acota bien, la de límites lo estira. Baja.
4. **cap14, «forma de Markov de Hull–White (de Cheyette)»**: se nombra a Cheyette sin citarlo (las cuatro obras citadas sí respaldan la forma de Markov). Baja.

## 4. Fórmulas que no corresponden al código

**Ninguna** en el muestreo. Fórmulas comparadas línea por línea (convención de días, signo, composición, interpolación, índices), priorizando las que no llevan `\verif`:

- cap02: (2.1) df, (2.2) interpolación lineal en tasa cero con extrapolación plana (`Interpolator::operator()`), (2.3) forward, (2.5) depósito, (2.6) días de pago, (2.7/2.8) par y residuo (`bootstrapOis`), (2.10) paridad, (2.13) base (`bootstrapXccyDiscount` + `XccySwap`), (2.14) descuento por colateral (`with_collateral`).
- cap03: (3.1) calendario, (3.5) cupón flotante con G solo en el periodo 1, (3.7–3.9) PV/anualidad/par (`OisSwap`), (3.12) factor compuesto (`compoundOvernight`), (3.14) envejecido (startDays negativo y τ del periodo completo), DV01 = PV − PV(+1 pb) con MXN-USD recalibrada (`_irs_price`, `MarketContext.shifted`).
- cap04: (4.5) volatilidad plana en vol fuera de [T1,Tn] (`VolSurface::vol`), (4.6–4.10) GK y griegas (vega/100), (4.12) griegas de la acción, theta/365, rho/100 (`blackscholes.cpp`).
- cap05: (5.4) ln A, (5.5) θ por diferencias finitas, (5.6) Euler con r0=z(10⁻⁴) (`hullwhite.cpp`), (5.14) cap doble curva por cociente de DF (`priceDualCurve`), (5.21) swaption doble curva por cociente de anualidades.
- cap06: (6.1) cupón = N·K·periodFraction(f, ACT/365)=N·K/f, (6.3) corrido lineal, (6.4) rendimiento continuo con el intervalo [−0.30,0.10] descrito, (6.5) duración/convexidad, (6.7) tiempos envejecidos y `min{0,…}` (`aging.aged_bond`).
- cap07: (7.1) cupón con G en el periodo 1 y spread·τ, (7.2) intercambio inicial solo si `startDays ≥ 0`, (7.4) telescópica USD (rederivada), (7.5) diferencial par (`XccySwap::parSpread`).
- cap08: (8.2) precedencia de estado (`lifecycle`), (8.6) FIX con último publicado sin hueco hábil (`settlement._fix`), (8.10) identidad de P&L.
- cap09: (9.4) rampa del steepener, (9.5/9.6) DV01 paralelo unilateral y por pilar central (`dv01.py`), (9.10/9.11) exposiciones (FX por ±1 %/0.02, `var.py`), (9.17) κ, VaR y ES con max (`hist_var.py`), cascada (9.19–9.23) (`explain.py`), (9.25/9.26) uso y redondeo a 9 decimales, 80/100 (`limits.py`).
- cap10: (10.9) regla del menor, (10.10) inefectividad, (10.12/10.13) reserva y reciclaje con `recycled_before` y el caso «ambos vencidos», (10.15) valor razonable (`hedge_measure.close_period`).
- cap11: (11.7) g(0)=Δ, (11.8) Newton por diferencia hacia adelante, h=1 pb/0.01 %, límites 1000 pb/50 %, 20 iteraciones, (11.9/11.10) estados y bandera con H17 (`ops_recon`).
- cap12: (12.4) diferencias y tolerancias 1e-6/1e-8, 1e-12/1e-8 en curvas (`desk/validation/common.py`), (12.10) bono del desk.
- cap13: (13.1) `round(percentRate/100,10)` (`nyfed.parse_sofr`), (13.2) Tesoro→OIS con umbral 365 días (`treasury_to_ois`), (13.5) sonrisa sintética (`seed_market._smile`).
- cap14: (14.x) CDS (prima ACT/360, DF al punto medio, devengo ½τ, `cdsValue`; días `round(365k/4)`), (14.15–14.18) CVA/DVA/FVA (`computeXva`).
- cap15: (15.7) tabla de vol local (161 strikes, t̃0=10⁻³h), (15.13) griegas (h acotado, vega sin dividir entre 0.01), (15.16) gráfica (21 puntos, espejo X0²/H) (`fx_exotics.py`).

## 5. `\verif` circulares o que no ejercitan el código del proyecto

Ninguno compara un número consigo mismo: `comun.comprobar` contrasta un valor calculado contra el impreso. Pero estos valores impresos los produce **la fórmula del propio script**, no una función del proyecto (todos bajos; varios están acotados por un `assert` contra el código):

| Id | Qué hace el script | Valoración |
|---|---|---|
| cap03-flo-telescopica-col | N(1−P_{c'}(70/365)) a mano; sin `assert` contra el código | Circular; el texto dice «que aquí no aplica» (es un contraste). Baja |
| cap03-flotante-telescopica, -env | Fórmula telescópica a mano, con `assert` contra la suma de flujos de `OisSwap` | Aceptable |
| cap05-caplet-sigma-p, cap05-swaption-x | σ_p y x* que `qfpy` no expone, calculados a mano; solo validados porque el precio completo a mano coincide con `qfpy` (1e-6) | Indirecto. Baja |
| cap06-rendimiento-semestral | 2(e^{y/2}−1) aplicado al rendimiento de `qfpy`; el código no calcula rendimiento semestral | Circular respecto de esa conversión. Baja |
| cap09-dv01-central-paralelo, cap09-dv01-convexidad, cap09-escenario-steepener-lineal | Aritmética del script sobre PV/DV01 del backend; el backend no calcula esas magnitudes | Ilustrativos, no comprueban código. Baja |
| cap12-cero-intermedio | Interpolación a mano, con `assert` contra el DF del desk | Aceptable |
| cap12-pv-bond08-fechas-enteras | Fórmula (12.11) con DF del desk calculada en el script; coincide con el valor impreso de QuantLib (`reference.json`) | Explicativa; no llama a QuantLib ni a un pricer. Baja |
| cap14-cf-cva/-dva/-fva/-valor-inicial, cap14-legacy-*-exacto, cap14-cds-proteccion-1a/-anualidad-1a | Referencias de forma cerrada/cuadratura del script, contrastadas con el motor (≤ 3 errores estándar; protección = s·anualidad con la intensidad del código) | Benchmarks legítimos, no circulares |
| cap15-semilla-u0 | Primer uniforme del generador de QuantLib | Ejercita QuantLib, no código del proyecto. Baja |
| cap15-puente-* | Fórmula del puente a mano, con `assert` exacto contra `fe._mc` sobre una trayectoria fija | Aceptable |

Nota: `cap15_exoticos_fx.py` importa `numpy` y `QuantLib`, y el README dice «los scripts usan solo la stdlib y el código del proyecto» (D-11).

## 6. HALLAZGOS.md

H01–H24: las 24 entradas tienen «Resolución:» con su commit. El texto de los capítulos es coherente con la resolución en todos los casos que revisé: H01 (cap02: LogLinear lanza), H02/H15 (cap03/cap07: 400 con inicio anterior, verificado por script), H03/H04 (cap09), H05 (cap12: 1e-6, «antes 5×10⁻⁴»), H07/H10/H11 (cap10: `hedge_ratio_mismatch`, sin `identity_residual` en valor razonable, sin término «moneda»), H13 (cap06), H14 (cap05: `shortened` sin ramas), H16 (cap04), H17 (cap11: bandera nula), H19 (cap01/cap08), H21 (cap14: malla de integración), H23/H24 (cap15: 161 strikes, choque acotado).

## 7. Lectura visual del PDF

Páginas leídas como imagen (62 dpi): 9, 21, 30, 38, 47, 54, 60, 68, 79, 88, 99, 107, 115, 125, 142 (una por capítulo 1–15), 155 (apéndice) y 164–167 (bibliografía completa). Legibles: ecuaciones numeradas, recuadros «Diferencia con la referencia» y tablas con booktabs bien compuestos; rutas `\codigo` en monoespaciado que parten sin desbordar. Errores visibles: la entrada de Fujii et al. sin DOI y la de Merton sin páginas; en el apéndice la columna «Macro» queda vacía en todas las filas por capítulo (cosmético).

## 8. Defectos con severidad

| Id | Severidad | Defecto |
|---|---|---|
| D-1 | Media-baja | cap01 (y docstring de `calendars._observed`): la regla «Veterans Day en sábado no se traslada» se justifica con frb2026, que dice lo mismo de todos los feriados en sábado (incluido el 3-jul-2026, que el código sí marca inhábil). La justificación correcta es la recomendación de SIFMA o la publicación de SOFR. |
| D-2 | Baja | `fujii2009` es `@misc` y `plainnat-es.bst` no imprime `doi` en `misc`: el lector no ve el DOI exigido por R5. |
| D-3 | Baja | `merton1973` sin `pages` (141–183). |
| D-4 | Baja | `wystup2017` y `meeus1998` sin `edition` (son segundas ediciones); `ho1992` sin subtítulo; forma de autor de Hull inconsistente (hull1990 vs hull2000). |
| D-5 | Baja | Citas dudosas 2–4 de la sección 3 (glasserman2003 cap. 3 para la siembra de `mt19937_64`; hull2018 para pruebas de efectividad; Cheyette sin cita). |
| D-6 | Baja | `\verif` ilustrativos o calculados por el script (sección 5): cap03-flo-telescopica-col, cap05-caplet-sigma-p, cap05-swaption-x, cap06-rendimiento-semestral, tres de cap09, cap12-pv-bond08-fechas-enteras, cap15-semilla-u0. No falsean nada, pero no prueban código del proyecto. |
| D-7 | Baja | Colisiones de notación entre capítulos pese a «los capítulos no redefinen símbolos»: φ (signo del lado en el cap03, densidad normal en el cap04), s (día de inicio en el cap03, signo en el cap04/15), ψ (diferencial en el cap07, valor de trayectoria en el cap15), σ para \vol y \hwsig; \Ann es «anualidad (años)» en el apéndice pero el cap03 la define escalada por el nocional (moneda). |
| D-8 | Baja | fred2026: la página HTML citada no respondió desde esta máquina (la serie existe por el CSV oficial). |
| D-9 | Baja | Subsecciones con fórmula sin `\codigo` propio (11; p. ej. cap10 «Cobertura de valor razonable», ec. 10.15, que no nombra `hedge_measure.close_period` en la subsección). R4 se cumple a nivel de sección. |
| D-10 | Baja | R6: no aparecen en ningún capítulo «Un solo usuario» (Metodología, «Alcance») ni la nota de que la gráfica de payoff de la swaption usa una anualidad aproximada (el cap01 solo dice que las gráficas son del navegador). |
| D-11 | Baja | README: «un capNN_<tema>.py por capítulo 2-12» (ya hay cap14 y cap15) y «los scripts usan solo la stdlib» (cap15 usa numpy y QuantLib). |
| D-12 | Baja | R8: el commit `55332a9` (docs(tex), cap. 15) también modifica `docs/superpowers/qf-desk/corte10-fx-exoticos/plan.md` (fuera de `docs/tex/`; documentación, no código). |
| D-13 | Baja | Apéndice de símbolos: columna «Macro» vacía en todas las filas por capítulo. |

Sin defectos de severidad alta.
