# QF Desk — Corte 3: curvas MXN como las arma el mercado

Repo `/home/claudio/Git/Quant_Finance`, rama `feat/qf-desk`. Base: cortes 1, 2 y 4 auditados (`docs/superpowers/qf-desk/`, en particular `corte2/plan.md` y `corte4/plan.md` § Contexto con las firmas reales). Claudio delegó todas las decisiones en Fable.

## Intención

Hoy un flujo en MXN se descuenta siempre con la curva TIIE-F. Eso es correcto con colateral en MXN; con un contrato de colateral en USD (lo habitual frente a bancos globales) el mercado descuenta MXN con la curva implícita en los forwards y cross currency swaps USDMXN. Este corte construye esa curva, permite elegir la moneda de colateral por contraparte, añade el cross currency swap como producto, introduce calendarios de días inhábiles y salda las aproximaciones que el corte 2 dejó declaradas "hasta el corte 3".

## Convenciones (decisión de Fable; se declaran en Metodología como supuestos, no como cita de fuente)

No hay acceso a la nota de Banorte ni a la metodología de CME desde aquí; estas convenciones son la práctica general de mercado tal como Fable la conoce y quedan marcadas `supuesto de convención` en Metodología para que un usuario con la fuente las confirme:
- Pata MXN: TIIE de Fondeo compuesta diariamente, cupones cada 28 días, ACT/360. Pata USD: SOFR compuesta, ACT/360.
- Cross currency swap USDMXN de base: SOFR plana contra TIIE de Fondeo + diferencial (la base se cotiza sobre la pata MXN), ambas patas con cupones cada 28 días, intercambio de nocional al inicio y al vencimiento, **nocional constante** (sin reinicio a mercado; se declara).
- Forward USDMXN: `F(T) = S × DF_USD(T) / DF_MXN^USD(T)`, con `DF_USD` de la curva SOFR y `DF_MXN^USD` la curva de descuento MXN bajo colateral USD.

## Decisiones de arquitectura

**D1 Curva nueva `MXN-USD`** (descuento MXN bajo colateral en USD). Se calibra, en C++, con: (a) puntos forward USDMXN para plazos cortos (hasta 1 año) y (b) diferenciales de cross currency swap para plazos largos; dadas la curva SOFR, la curva TIIE-F (proyección) y el spot. Interpolación igual a las curvas existentes. Si el snapshot no trae cotizaciones de forwards ni de base, la curva `MXN-USD` no existe y todo se valúa como en el corte 1.

**D2 C++ (serie, comparten `build/`).**
- `OisSwap` gana una clave de curva de **descuento** opcional distinta de la de proyección (por omisión, la misma: retrocompatible a 1e-12).
- `XccySwap` (nocional constante, intercambios inicial y final opcionales, pata USD SOFR, pata MXN TIIE-F + diferencial, lado paga-USD o paga-MXN), con `npv` en MXN, `parSpread`, flujos por pata.
- Bootstrap `bootstrapXccyDiscount(...)` que devuelve los pilares de `MXN-USD` a partir de las cotizaciones.
- `Bond` y `CapFloor` con calendario explícito de tiempos de pago (constructor nuevo, retrocompatible) para envejecer de forma exacta: el bono con cupón corrido (precio sucio; se reporta también limpio) y el cap sin el caplet ya fijado.
- Todo expuesto en `qfpy`.

**D3 Calendarios (`desk/api/calendars.py`, Python: es orquestación de fechas, no matemática).** Días inhábiles bancarios de México y de EE. UU. por reglas (fijos, lunes trasladados, Jueves y Viernes Santo, Thanksgiving, etc.) para 2020–2040, sin dependencias. Usos en este corte: (a) una fijación no publicada en día inhábil de su índice (TIIE-F: México; SOFR: EE. UU.; USDMXN: México) **no** es faltante: la tasa del último día hábil devenga los días intermedios; (b) aviso al designar un flujo pronosticado en día inhábil; (c) la interfaz marca los días inhábiles en el calendario de flujos. **No** se ajustan las fechas de pago de las operaciones existentes (se declara: las fechas son las pactadas).

**D4 Snapshot y contrapartes.** `snapshots.data` gana, opcionales, `fx_forwards` (`[{days, points}]`, puntos en pesos por dólar) y `xccy_basis` (`[{days, spread}]`, decimal). `MX-DEMO` trae valores sintéticos coherentes (rotulados). `MKT-LIVE` no los trae (no hay fuente libre): su `MXN-USD` no existe y se dice en la procedencia. `counterparties` gana `collateral_currency` (`MXN` por omisión, o `USD`), editable por `PUT /api/counterparties/<id>`; el cambio se guarda con historial (`counterparty_events`, solo inserción) y aplica desde su fecha.

**D5 Valuación.** Una operación en MXN (`irs` TIIE-F, `cap_floor`, `swaption`, `bond` en MXN, pata MXN de forwards y opciones FX) con contraparte de colateral USD descuenta con `MXN-USD` y proyecta con TIIE-F; si la curva no existe en el snapshot, usa TIIE-F y devuelve el aviso `no_csa_curve`. Con colateral MXN nada cambia respecto al corte 2 (1e-10 relativo). Los forwards y opciones FX ya usan paridad de tasas con las dos curvas; con `MXN-USD` disponible y colateral USD usan esa curva para el lado MXN.

**D6 Riesgo.** El DV01 por plazo añade la curva `MXN-USD` (desplazamiento de sus pilares con SOFR y TIIE-F fijas); escenarios y VaR la tratan como curva dependiente (se recalibra con las cotizaciones fijas cuando se mueve SOFR o TIIE-F, salvo en el desplazamiento propio). Se declara.

**D7 Producto `xccy_swap`** en pricer, portafolio, ciclo de vida (fechas, eventos, envejecimiento con fijaciones de ambos índices, flujos liquidados con FIX), P&L y riesgo, como cualquier otro producto.

**D8 Interfaz.** Mercado: tablas de puntos forward y de base, la curva `MXN-USD` en la gráfica con su procedencia, y tabla "forward implícito vs cotizado". Portafolio/contrapartes: moneda de colateral por contraparte. Pricer de cross currency swap. Riesgo: `MXN-USD` en el DV01. Ficha: días inhábiles marcados. Metodología: convenciones (como supuestos), qué cambia con el colateral, y se retiran las aproximaciones saldadas.

## Requisitos

- **R1** Todo instrumento de calibración reprecia a cero: swaps OIS de TIIE-F y SOFR (ya existía), forwards (`|F_implícito − F_cotizado| ≤ 1e-8`) y cross currency swaps a su diferencial cotizado (`|npv| ≤ 1e-8 × nocional`). Test en C++ y en Python.
- **R2** Con puntos forward iguales a la paridad de TIIE-F y SOFR y base cero, `MXN-USD` coincide con TIIE-F (1e-8 en factores de descuento) y todo PV coincide con el del corte 2 (1e-8 relativo).
- **R3** Colateral: cambiar una contraparte a USD cambia el PV de sus swaps MXN; con base negativa (MXN más barato de fondear vía USD, `DF_MXN^USD > DF_TIIE`) un flujo MXN positivo vale más; el cambio se guarda como evento y valuar en una fecha anterior al cambio da el PV anterior. Sin curva en el snapshot → aviso `no_csa_curve` y PV del corte 2.
- **R4** `OisSwap` con curva de descuento distinta: retrocompatible (1e-12) cuando son la misma; con descuento distinto, `npv` coincide con el cálculo independiente del test (suma de flujos proyectados × factores de la otra curva, 1e-10 × nocional).
- **R5** `XccySwap`: a su `parSpread` vale 0; paga-USD y paga-MXN son opuestos; sin intercambio de nocional el valor cambia en el valor presente de los intercambios; envejecido con fijaciones cumple la identidad de P&L del corte 2.
- **R6** `xccy_swap` como producto de punta a punta: alta desde el pricer, valuación en el portafolio, ficha con flujos de ambas patas, DV01 por curva, escenarios, VaR, P&L y terminación.
- **R7** DV01: incluye `MXN-USD` por plazo; para cada curva la suma por plazo cuadra con el paralelo dentro del 2 %.
- **R8** Calendarios: fechas conocidas de 2025–2027 de México y EE. UU. salen inhábiles (test con lista fija, incluidos Viernes Santo, 16 de septiembre, Thanksgiving y un lunes trasladado); un swap envejecido a través de un feriado sin fijación ese día no avisa `missing_fixing`; un día hábil sin fijación sí.
- **R9** Bono envejecido exacto: entre cupones el precio sucio = limpio + cupón corrido y el PV cambia de forma continua día a día (sin el escalón de la aproximación por periodos enteros); el día del pacto coincide con `/api/price` (1e-9). Cap/floor envejecido: el caplet ya fijado no entra; el resto coincide con un cap de los caplets restantes (1e-9). Los flujos del bono al vencimiento y sus cupones se liquidan (dejan de ser `no_settlement`).
- **R10** Interfaz según D8, sin desbordes a 1280 px, textos en español, procedencia visible (la curva `MXN-USD` de `MX-DEMO` es sintética).
- **R11** Metodología: convenciones marcadas como supuestos, efecto del colateral, nocional constante sin reinicio, fechas sin ajuste por inhábil, curva dependiente en riesgo; se retiran las frases de aproximaciones ya saldadas.
- **R12** Sin regresión: las cuatro suites pasan; las relaciones de cobertura del corte 4 siguen midiendo igual con colateral MXN (1e-8).

## Fuera de alcance (se declara)

Cross currency swap con reinicio de nocional a mercado; ajuste de fechas de pago por día inhábil y rezagos de pago; colateral en otras monedas o por operación; umbrales, montos mínimos de transferencia y valoración de la opción de colateral; curvas a plazo de TIIE 28 histórica; fuente real de puntos forward y de base (no hay fuente libre: entran por captura o importación, corte 8).

## Restricciones

- Las del corte 2 y 4 (Python 3.8 de anaconda, sin dependencias nuevas, guardia de no finitos, validación en la frontera, commits por tarea con rutas explícitas y `GRAPHIFY_SKIP_HOOK=1`, autor Claudio sin `Co-Authored-By`, sin `git stash`, sin push durante el corte).
- Matemática en C++ vía `qfpy`; las tareas C++ van **en serie** y primero; después backend e interfaz en paralelo con contratos fijados; tarea final de integración contra el backend real con capturas.
- Todo constructor o firma existente sigue funcionando igual (retrocompatibilidad probada).

## Trabajo en paralelo

Este corte se trabaja en el árbol principal (rama `feat/qf-desk`), porque es el que compila C++. Los cortes 5, 6 y 7 avanzan a la vez en otros worktrees y se fusionan después: **minimizar cambios en archivos compartidos** (`db.py`, `app.py`, `Shell.tsx`, `App.tsx`, `api/types.ts`, `api/client.ts`, `MethodologyScreen.tsx`): añadir en bloques contiguos delimitados por un comentario `corte 3`, sin reordenar ni reformatear lo existente.
