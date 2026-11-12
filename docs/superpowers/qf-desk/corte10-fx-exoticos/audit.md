# Auditoría — Exóticos de FX (no touch / double no touch), rama `fx-exoticos`

Worktree `/home/claudio/Git/qf-wt/fxexoticos` en `9b8ba0d`, limpio antes y después (`git status --short` vacío). Base de comparación: `ad1c2a2` (último commit previo al corte). Programas propios del auditor en `/tmp/claude-1000/-home-claudio/1a002a83-9ce7-4c4e-b315-b09b1e001eba/scratchpad/audit/` (`mc_check.py`, `ctx.py`, `serve.py`, `shoot.mjs` y capturas `a-*.png`). Backend de pruebas en 5094 con base temporal y Chrome headless en 9354, ambos apagados al terminar.

## Suites

| Suite | Resultado |
|---|---|
| `python -m pytest desk/api/tests -q -p no:cacheprovider` | **3619 passed** en 353 s (113 de ellas en `test_price_fx_exotics.py`, 122 s) |
| `npm test` (desk/ui) | **646 passed**, 42 archivos |
| `npm run build` | OK (`✓ built in 2.13s`) |

Pruebas anteriores modificadas: solo `Shell.test.tsx` (8 → 10 pricers) y `PricerForm.test.tsx` (el mock de `PricerChart` recibe `series`). Ambas cuentan pricers o son infraestructura, así que están justificadas.

## Veredictos

| R | Veredicto | Evidencia |
|---|---|---|
| R1 Pricers y validación | **CUMPLE** | Por HTTP en :5094 respondieron con 400 y `field`: spot sobre la barrera (`barrier`, `lower`), `lower ≥ upper` (`'upper' debe ser mayor que 19.0`), `analytic`+`smile` (`method`), `payout_mxn` 0 y 2e13, `days` 0, 18251 y 1.5, `barrier_type`, `side`, `model`, barrera no numérica o ausente. Los valores por omisión son `smile`/`mc`. Contrato `{product,currency,pv,pv_mxn,risk,cashflows,details}` (P2). Observación: el mensaje usa el nombre interno del campo («ya tocó la barrera 'lower'»). |
| R2 Resultado | **CUMPLE** | `details` = `analytic_flat_pv, chart, method, model, no_touch_probability, paths, price_pct, smile_adjustment, std_error`; `risk` = `delta, vega`; `chart = {strike:null, barriers:[…], spots[21], pnl[21]}`. Además: `price_pct = 100·DF·u`; `paths = 0` y `std_error = 0` en analítico (UI: «Trayectorias 0»). |
| R3 MC = analítico, vigilancia continua | **CUMPLE** | Programa propio (`mc_check.py`): `_mc` con un proceso GK propio sobre tasas planas, contra `AnalyticBinaryBarrierEngine` y `AnalyticDoubleBarrierBinaryEngine`. 16 casos (1 a 730 días; barrera a 0.05 del spot; corredores de 0.1 a 7.5 pesos; MXN/USD 10/4.5 %, 11/4 % y 2/10 %; vol 0.10 a 0.25) × 3 semillas (42, 7, 2026, cambiando `fe.SEED` en tiempo de ejecución sin tocar el archivo): **máx \|z\| = 1.72**. Malla: con 1, 2, 5, 10, 50 y 200 pasos el no touch de 30 días a 18.9 queda en 0.3158 / 0.3155 / 0.3142 / 0.3149 / 0.3186 / 0.3138 frente a 0.3141 analítico (±0.003). 6 semillas × 100k trayectorias en un corredor de 1.5σ√T: z conjunto +0.28 (10 pasos) y −0.41 (50 pasos), sin sesgo. |
| R4 Sonrisa | **CUMPLE** | Superficie plana de 0.14 construida por el auditor: smile − flat da z = −0.01, −0.01 y −0.00 en tres casos. MX-DEMO: precios finitos y dentro de [0, DF·K]. `smile_adjustment` aparece (2 022 MXN en NT 91d 19.5). Se omite el 400 por falta de superficie (P4), declarado en Metodología. Ver el defecto D3 (vainillas) y el D4 (`smile_adjustment` es ruido). |
| R5 Identidades | **NO CUMPLE (solo c, marginal)** | Casos propios en flat y smile: (b) NT 18.7 → 19.1 sube y DNT [18.2,18.9] → [18.0,18.9] sube; (d) DNT ≤ min(NT abajo 18.2, NT arriba 18.9); (e) sell + buy = 0 exacto; (f) idéntico en dos corridas. (a) y (c): con barrera a 900 000 el valor es exactamente K·DF de la curva **QuantLib reconstruida**, pero excede K·DF de la curva TIIE-F del desk en **1.25e-5** (91 d) y 3.65e-5 (182 d), por encima de la tolerancia de 1e-6 de R5(c), y queda *por encima* del pago descontado del desk (R5a). La prueba propia usa `rel=1e-4` (`test_price_fx_exotics.py:243`). Causa en D1. |
| R6 Eficiencia | **CUMPLE** | En proceso, con los valores por omisión: sin gráfica **0.94–1.02 s**, completo **1.55–1.84 s**; por HTTP 1.56 s (NT) y 1.55 s (DNT). Error estándar ≤ 0.33 % del pago (máximo teórico 0.35 % con p = 0.5). Existe `test_default_price_is_fast` con margen 3×. |
| R7 Mínimo código, QuantLib | **CUMPLE (con observaciones)** | 133 líneas de código en `fx_exotics.py` (sin blancos, docstrings ni comentarios; conteo con `ast`+`tokenize`) más 9 de registro (`__init__.py` y `routes/price.py`): **142 ≤ 180**. Un solo módulo, sin clases nuevas. La única matemática propia es la fórmula del puente (L89–91), declarada. Ver la tabla y las líneas sobrantes. |
| R8 Interfaz | **CUMPLE** | CDP a 1280×800: `overflowX:false` en ambos pricers y en Metodología; `ERRORES []` en consola; sin «Agregar al portafolio»; «± MXN 3,268.93 (error estándar)» bajo el PV; la tabla «Detalle del cálculo» incluye probabilidad de no tocar y referencia analítica; la gráfica marca 1 o 2 líneas «Barrera» (capturas `a-nt-full.png` y `a-dnt-full.png`); el error de campo sale en rojo bajo «Barrera inferior»; Ctrl+K + «touch» encuentra los dos productos; `sell` invierte los signos. Se reusan `PricerForm`/`PricerChart` sin componentes nuevos. |
| R9 Metodología | **CUMPLE** | `MethodologyScreen.tsx`, sección `fx-exoticos`: qué paga, barrera continua con puente, plano y sonrisa (Dupire de QuantLib, bicúbica, extrapolación constante, sustitución por la vol plana y diferencia frente a Dupire al vuelo), cálculo, semilla 42 con 20 000 × 10, límites (MXN, no estocástica ni vanna-volga, superficie sintética, sin rebate ni one touch, no se registran, no hay caso sin superficie). Lo de «0.3–0.8 % del pago» frente al cálculo al vuelo: medí −0.01 a −0.33 % (91 d a 2 a), del orden declarado. |
| R10 Dependencia | **CUMPLE** | `desk/README.md` lo agrega a Requisitos y a Instalación (`pip install "QuantLib==1.42.1"`). `QF_PYTHON=/usr/bin/python3 bash desk/run.sh` (Python sin QuantLib) imprime `[run.sh] falta QuantLib en /usr/bin/python3: … pip install "QuantLib==1.42.1"` y sale con `exit=1`. Las tres suites están verdes. |

## R7 — Funciones propias (`desk/api/pricing/fx_exotics.py`)

Líneas de código por función, sin blancos, docstrings ni comentarios. Nivel de módulo: imports 5, constantes 3, `PRODUCTS` 4.

| Función | Líneas | Qué hace | ¿Pieza de QuantLib 1.42.1 que la sustituya? (comprobado ejecutando) |
|---|---|---|---|
| `_common` | 11 | valida side, payout, days, model, method y la combinación analytic+smile | No; son los ayudantes de validación del desk |
| `_nt_validate` | 3 | barrera y tipo | No |
| `_dnt_validate` | 3 | lower y upper (> lower) | No |
| `_sides` | 4 | (campo, signo) de cada barrera | No; es solo pegamento |
| `_build` | 30 | snapshot → `DiscountCurve`, `GarmanKohlagenProcess`/`BlackVarianceSurface` → `NoExceptLocalVolSurface` → tabla `FixedLocalVolSurface` | La tabulación (L72–76) es optimización propia, sustituible por `NoExceptLocalVolSurface` al vuelo (≈15× más lento; diferencia medida −0.01 a −0.33 % del pago). Lo demás ya es QuantLib. |
| `_mc` | 11 | `GaussianPathGenerator` + supervivencia por puente en numpy (+ `np.interp` de la vol local) | **NT: sí.** `MCBarrierEngine` rechaza el pago en efectivo (`RuntimeError: non-plain payoff given`), pero acepta la réplica exacta con un diferencial de up-and-out puts con strikes b y b+h (pagan h en toda la zona viva), y ese motor ya aplica la corrección de puente: 0.2203 contra 0.2179 analítico (10 pasos, 20 000 trayectorias, 0.18 s). **DNT: no.** No existe Monte Carlo de doble barrera en el módulo; solo `AnalyticDoubleBarrier(Binary)Engine`, `Binomial*DoubleBarrierEngine`, `FdHestonDoubleBarrierEngine`, `VannaVolga*DoubleBarrierEngine` y `SuoWangDoubleBarrierEngine`. **Puente: no.** QuantLib no expone la probabilidad de cruce; `ql.BrownianBridge`, `SobolBrownianBridgeRsg` y `Burley2020SobolBrownianBridgeRsg` solo construyen trayectorias, y la fórmula vive dentro de `BarrierPathPricer` sin exponerse. Unificar fue decisión de Fable (P3); no es defecto, pero el comentario de L90 («QuantLib no trae Monte Carlo de barrera en efectivo») oculta que la réplica sí existe. |
| `_analytic` | 18 | `BarrierOption`/`DoubleBarrierOption` con `CashOrNothingPayoff` y motores analíticos | Ya es QuantLib; solo arma la opción |
| `_value` | 9 | signo, descuento, despacho mc/analytic | No; pegamento |
| `_result` | 18 | pv, referencia, delta y vega por reprecio, `details` | No |
| `_price` | 14 | barrera ya tocada + serie de la gráfica | No |
| **Total módulo** | **133** | + registro 9 = **142** | |

`run.sh` suma 4 líneas de shell.

Alternativas de QuantLib comprobadas que no se usaron:
- `FdBlackScholesBarrierEngine` acepta pago en efectivo (0.21860 contra 0.21791 analítico) y tiene opción de volatilidad local: una EDP para el NT con sonrisa, sin Monte Carlo. Claudio pidió Monte Carlo, así que es solo informativo.
- `GaussianSobolPathGenerator` (baja discrepancia, cambiando una línea) no se usó. Está justificado: con Sobol `std/√n` deja de ser un error estándar válido, y R2 lo exige.

## Líneas sobrantes y duplicaciones

Backend (`fx_exotics.py`):
1. **L86 `alive = True`, L91 `alive & (lb * lb[:, :1] > 0).all(axis=1)`, L92 `alive *`: redundantes.** Si dos nodos consecutivos quedan a lados opuestos de una barrera, `lb_i·lb_{i+1} < 0`, así que `exp(…) > 1`, `surv < 0` y `clip` da 0. Como el nodo 0 siempre está vivo (validado), toda trayectoria con un nodo muerto tiene ese cambio de signo. Una reimplementación sin `alive` dio resultados **idénticos (`==`)** en 4 casos (NT 30 d y 7 d, DNT 91 d y 365 d).
2. L92 `np.clip(surv, 0, 1)`: la cota superior 1 nunca actúa (surv ≤ 1); basta `np.maximum(surv, 0)`. Trivial.
3. `today + int(round(t * 365))` aparece dos veces (L52 y L64). El redondeo a días de los pilares es además parte de la causa de D1.
4. L48 y L98: `_build` muta `ql.Settings…evaluationDate` y `_analytic` la vuelve a leer del estado global en vez de recibir `today`. Es acoplamiento oculto (ver D6).
5. L133: la referencia analítica se recalcula aunque `p` ya sea flat+analytic (es el mismo número que `pv`). El costo es despreciable.
6. L156–157: `CHART_POINTS + 2` y `[1:-1]` recortan los extremos, así que la curva nunca llega a 0 en la barrera (en la gráfica termina en ~70 000 MXN junto a la línea «Barrera»). Incluir los extremos no costaría código.
7. `__init__.py`: `ChainMap` como «vista viva» existe solo para que los monkeypatch de pruebas sobre `PRODUCTS` lleguen a la ruta. Un `{**PRODUCTS, **fx_exotics.PRODUCTS}` sería más simple si las pruebas parchearan `PRICERS`.

Interfaz (`desk/ui/src/screens/pricers/`):
8. `PricerChart.tsx`: `buildOption` se exporta solo para las pruebas.
9. `PricerForm.tsx`: `NOT_TRADABLE` es una lista fija que duplica, en la UI, la división `PRODUCTS`/`PRICERS` del backend. Un campo en `ProductSpec` costaría lo mismo. Las ~140 líneas del diff son casi todas re-indentación por envolver el formulario de portafolio en el condicional: el código real nuevo son unas 30 líneas.
10. `fx_no_touch.ts`: `help: 'MXN por USD.'` solo en la barrera del NT, no en las del DNT (inconsistente y no pedido).

## Construido sin que un requisito lo pidiera

- Un 400 en español cuando la serie analítica del DNT no converge con `method=analytic`, y `analytic_flat_pv: null` («—» en la UI) con MC (commit `9b8ba0d`). Es razonable: corrige un 500.
- Las filas «Trayectorias», «Modelo» y «Método» en «Detalle del cálculo»: repiten entradas.
- La ayuda «MXN por USD.» en la barrera del NT.
- `buildOption` exportado y el `ChainMap` vivo (puntos 7 y 8).

## R6 — Dónde se va el tiempo

Perfil (`cProfile`) de una petición completa de NT con sonrisa, 2.27 s bajo el perfilador, con 102 000 trayectorias (3 × 20 000 para pv, delta y vega, más 21 × 2 000 para la gráfica):
- `Path.__getitem__` de SWIG (1.22 M llamadas) más su envoltura Python: **~1.05 s (≈46 %)**, por `list(pg.next().value())` en L84.
- `GaussianPathGenerator.next`: 0.45 s (≈20 %).
- La comprensión de L84: 0.30 s.
- `localVol` para las 22 tablas: 0.04 s. El resto es numpy.

**Mejora barata sin código:** no la hay. En 1.42.1 `ql.Path` solo expone `back, front, time, value`, sin acceso vectorial (comprobado). Lo único que no añade líneas es bajar la constante `CHART_PATHS` (la gráfica es ~0.7 s del total), a costa de una gráfica más ruidosa. Para el pv, delta y vega se regeneran tres veces las mismas normales; reusarlas requiere código.

## Correctitud (punto 2 del encargo)

- **Fórmula del puente** (L91): `P(cruce) = exp(−2 ln(X_i/b) ln(X_{i+1}/b) / (σ²Δt))`. Es correcta para el log-precio (el puente no depende de la deriva). Con sonrisa usa la vol local del nodo izquierdo, interpolada linealmente en la misma tabla que usa el proceso, así que es coherente.
- **Las dos barreras no se tratan como independientes:** el código usa `1 − p_l − p_u` por intervalo (cota de Bonferroni), no `(1−p_l)(1−p_u)`. El error por intervalo es P(cruzar ambas), siempre hacia abajo y luego recortado en 0. Medido con 100k trayectorias:

  | Corredor | 1 paso | 2 | 3 | 5 | 10 | 50 |
  |---|---|---|---|---|---|---|
  | 7 d, 0.97σ√T (valor 0.67 %) | −100 % | −57 % | −15 % | −3.8 % (z −2.7) | +2.3 % (z +1.1) | −0.9 % |
  | 30 d y 91 d, 1.5σ√T | −15 a −22 % | ≤ −1.4 % | | | ≤ 1 %, sin sesgo con 6 semillas | |

  Con `STEPS = 10` el sesgo está bajo el error de MC para corredores de ≥ ~1σ√T. Por debajo, el valor ya es < 1 % del pago.
- **Volatilidad local:** la tabla reproduce el Dupire al vuelo de QuantLib (vainillas: misma vol implícita ±0.1 punto). Pero el modelo **no reprecia las vainillas de la superficie a 1 año**: ATM 12.86 % contra 13.15 %, alas −0.3 a −0.7 puntos (z −3 a −8). Lo mismo pasa con Dupire al vuelo y 50 pasos, así que viene de Dupire sobre la bicúbica con extrapolación constante, no de la tabla. A 30 días cuadra dentro del ruido. En los bordes: strikes ±5σ√T con extrapolación constante (np.interp y `FixedLocalVolSurface` coinciden); el tiempo arranca en `1e-3·Δt` y el valor de t=0 se recorta; después del último pilar de la superficie (1 año) la varianza se extrapola. No hubo NaN hasta 18 250 días (`test_longest_valid_maturity_is_priced`).
- **Signos:** NT arriba (19.5): delta −536 k, vega −31 k. NT abajo (17.5, 730 d): delta +246 k, vega −22 k. DNT: vega negativa. `sell` invierte pv, delta, vega, referencia y ajuste. Correcto.
- **Descuento y moneda:** paga en MXN, descuenta con `mkt.mxn_discount` (TIIE-F) y usa `SOFR` como tasa extranjera del proceso GK. Correcto en concepto; ver D1.

## Defectos fuera de los requisitos

| # | Sev. | Defecto | Evidencia |
|---|---|---|---|
| D1 | **media** | La curva QuantLib reconstruida (`DiscountCurve` log-lineal, pilares redondeados a días, extrapolación de la última forward) no coincide con la curva del desk (`qfpy`): +1.25e-5 a 91 d, +3.65e-5 a 182 d, −1.2e-4 a 10 años, **−16.4 % (MXN) y −14.4 % (USD) a 50 años**. Los plazos válidos llegan a 18 250 días: todo precio a más de ~10 años usa un descuento distinto del resto del desk (opción FX, forward). También rompe R5(a)/(c) por 1e-5. | script propio: `ql/qfpy−1` por plazo; `fx_exotics.py:50-55` |
| D2 | baja | La gráfica no contiene el spot cuando la barrera está a más de ~15 % (rango fijo `barrera × 0.85/1.15`): con barrera 40 el eje va de 34.3 a 39.7 y el spot 18.6 queda fuera. | `fx_exotics.py:156`; POST con barrera 40 |
| D3 | media | Con sonrisa, el MC no reprecia las vainillas de la superficie a 1 año (−0.3 puntos ATM, hasta −0.7 en alas). Viene del Dupire de QuantLib sobre la superficie bicúbica con extrapolación constante, no de la tabla. No está declarado en Metodología y sesga `smile_adjustment`. | sección Correctitud |
| D4 | media | `smile_adjustment = pv_MC(smile) − analítico(flat)` mezcla el ruido de MC con el efecto sonrisa: en el caso por omisión vale 2 022 MXN con error estándar de 3 269 MXN, así que el número que la UI muestra como «Ajuste por sonrisa» no se distingue de cero. Con trayectorias comunes (MC smile − MC flat) sería 1 447. Es la definición de Fable (P5), pero engaña al lector. | salida de `_result` NT 91d 19.5 smile y flat |
| D5 | baja | Delta con `model=flat` vuelve a leer la vol de la superficie en el spot chocado (`mkt.surface.vol(spot·1.01, T)`), así que no es una delta de volatilidad plana: −545 339 contra −539 612 con vol fija (≈1 %). La gráfica «flat» también cambia de vol en cada punto. | `fx_exotics.py:58`; script propio |
| D6 | baja | `ql.Settings.instance().evaluationDate` es estado global del proceso: con Flask multihilo y dos snapshots de distinta fecha a la vez, `_analytic` podría leer la fecha del otro hilo (vencimiento del ejercicio). | `fx_exotics.py:48, 98` |
| D7 | baja | El mensaje de barrera tocada muestra el nombre interno del campo en inglés («ya tocó la barrera 'lower'»), no el rótulo. | captura `a-dnt-error.png` |
| D8 | baja | La curva de la gráfica no llega a la barrera (extremos recortados): visualmente el valor «salta» de ~70 000 a la línea de barrera. | `a-dnt-full.png`; L156–157 |
