# Hallazgos de la documentación técnica

Discrepancias entre lo que el código **hace** y lo que declara la Metodología de la aplicación
(`desk/ui/src/screens/MethodologyScreen.tsx`, `desk/ui/src/screens/ops/opsMethodology.ts`) o el diseño del
corte correspondiente, encontradas al escribir los capítulos de `docs/tex/`. Un hallazgo **no se corrige ni
se maquilla**: el capítulo describe lo que el código hace y aquí queda anotado qué difiere, con archivo y
símbolo, para que se decida aparte (corregir el código o corregir la Metodología).

Archivo compartido entre redactores: releer antes de editar, añadir solo **al final**, commit inmediato.

## Formato de entrada

```
## HNN — <título corto>
Archivo: <ruta relativa al repo>
Símbolo: <función, clase o constante>
Qué hace el código: <comportamiento real, con convención de signo/base/unidad si aplica>
Qué declara la Metodología/el diseño: <texto o referencia al documento>
Impacto: <qué cambia para el usuario o el auditor>
Capítulo: <número y título del capítulo que lo describe>
```

`NN` es correlativo (H01, H02, …). Si dos redactores añaden a la vez, el segundo renumera la suya al releer.

## Entradas

## H01 — `bootstrapOis` con interpolación LogLinear no reprecia (y devuelve una curva sin error)
Archivo: include/qf/termstructure/ois_bootstrap.hpp (contrato) y src/termstructure/ois_bootstrap.cpp
Símbolo: bootstrapOis, con `method = InterpolationMethod::LogLinear` (binding `qfpy.bootstrap_ois(..., method=...)`)
Qué hace el código: `Interpolator` aplica «LogLinear» al logaritmo de la **tasa cero**, no del factor de descuento (src/math/interpolation.cpp), y el bootstrap busca la tasa cero del pilar con Brent en [-0.5, 2.0]. Con tasas cero no positivas el logaritmo es NaN, el residuo es NaN, `residual(lo) * residual(hi) > 0` es falso y Brent devuelve un valor sin sentido en vez de lanzar. Medido con las cotizaciones de MX-DEMO (TIIE-F, `period_days = 28`): la segunda tasa cero queda en 0.75 (el punto medio del intervalo de búsqueda), las demás también y la tasa par implícita de cada OIS sale 0.76 en vez de 0.0698--0.0675. Con `bootstrapXccyDiscount` el mismo método sí falla en voz alta (`RuntimeError: no zero rate solves the basis swap`).
Qué declara la Metodología/el diseño: el comentario de contrato de `bootstrapOis` y de `bootstrapXccyDiscount` dice que «every quote reprices exactly when method is local (Linear, LogLinear)». La Metodología («Curvas») solo declara interpolación lineal en tasa cero.
Impacto: ninguno en la aplicación: `market.py` nunca pasa `method` y usa el valor por omisión, Linear (donde sí reprecia a 3e-16). Solo afectaría a quien llame al binding con LogLinear. Con CubicSpline la desviación observada es del orden de 1e-6 en la tasa par, y eso sí está declarado en el contrato.
Capítulo: 2 (Curvas)

## H02 — Alta a la par de un swap que empieza antes del snapshot: tasa del swap envejecido, sin fijaciones y sin aviso
Archivo: `desk/api/portfolio.py`
Símbolo: `_at_par`
Qué hace el código: arma `valuation.aged_swap({start_date, maturity_date}, {..., fixed_rate: 0.0}, mkt, {}, [])` con `mkt` en el `as_of` del snapshot de la petición (o `MX-DEMO`) y guarda como tasa fija `par_rate(mkt.env)` de ese swap *envejecido*. Se pasan `fixings = {}` y la lista de avisos se descarta. Si `start_date == as_of` es la tasa par de inicio; si `start_date < as_of`, los días ya transcurridos del periodo en curso se capitalizan con la tasa a un día de la curva (`valuation.accrued_factor`, rama sin fijaciones) y la tasa guardada es la par del tramo que queda, no la par en la fecha de inicio. Reproducción: base temporal (`db.connect`, `db.init_schema`, `seed_market.seed_market`), pagador TIIE-F de 13 periodos, `portfolio._at_par(conn, {}, params, start, start + 13*28 días)`: con `start` = `as_of` de `MX-DEMO` (2026-11-10) devuelve 0.0675000000; con `start` 30 días antes devuelve 0.0676677218 sobre la misma curva.
Qué declara la Metodología/el diseño: Metodología, «Ciclo de vida y valuación a fecha», «Alta a la par»: «Un swap dado de alta sin tasa fija nace a la par: se guarda con la tasa par del snapshot de la petición (o MX-DEMO), de modo que su PV en la fecha de pacto es cero.»
Impacto: el PV es cero en la fecha del snapshot de la petición, no en la fecha de pacto ni de inicio cuando son anteriores. Y como no se consultan las fijaciones registradas, la tasa guardada depende de la curva y no de las fijaciones reales de esos días, sin ningún aviso `missing_fixing` al usuario. Con `start_date == as_of` (el caso normal de un alta del día) no hay diferencia.
Capítulo: 3 (Swaps de tasa OIS)

## H03 — El residuo de la cascada de P&L es cero por construcción; lo no atribuido cae en «Eventos»
Archivo: `desk/api/risk/explain.py`
Símbolo: `_components` (y `explain_pnl`)
Qué hace el código: `events = (pv_to + settled) − (values[-1] + s0)` es un componente de cierre: recoge todo lo que la cadena de mercados híbridos no explica (terminaciones, ejercicios, cambios de nocional y cualquier otro efecto residual de valuar con los eventos completos en vez de los de la fecha `from`). Con `carry = values[0] − pv_from + s0_origin`, los pasos `values[s] − values[s−1]`, el ajuste `fx += s0 − s0_origin` y `events`, la suma telescopa a `pv_to + settled − pv_from`, que es el P&L oficial de `pnl.compute_pnl`; por eso `residual = pnl − Σ(componentes)` vale 0.0 salvo redondeo de coma flotante. Medido con el forward FX y el IRS del ejemplo 6 del capítulo 9 (MX-DEMO → un snapshot con TIIE-F +25 pb, SOFR −25 pb y spot +3 %): residuo 0.0 en las dos operaciones. Solo es distinto de cero cuando la cascada de una operación lanza una excepción (entonces todo su P&L va al residuo y `explain_error` dice por qué). Además, ningún dato del snapshot que afecte al PV queda fuera de los bloques (cotizaciones de cada curva, puntos forward y base, spot, superficie de volatilidad y parámetros de Hull–White); lo demás (`factors`, rótulos) no entra a la valuación.
Qué declara la Metodología/el diseño: Metodología, «Riesgo avanzado», «Residuo»: «Por qué no es exactamente cero: la cascada suma exactamente el P&L salvo redondeo numérico y datos del mercado que no pertenecen a ningún bloque.» El diseño del corte 6 (D1) dice que «el residuo mide lo no atribuido» aunque la suma sea exacta por construcción.
Impacto: el residuo no mide ninguna calidad de la atribución: un P&L mal explicado por los bloques de mercado aparece en «Eventos» (y, por tanto, parece un efecto de terminaciones o ejercicios), no en «Residuo». Quien lea «Residuo ≈ 0» no debe concluir que los pasos de mercado lo explican todo. La Metodología debería decir que el residuo es cero por construcción y que «Eventos» es el componente de cierre, o el código debería aislar los eventos valuando con y sin ellos como también declara la Metodología («Terminaciones, ejercicios y cambios de nocional se aíslan valuando con y sin los eventos de la ventana»).
Capítulo: 9 (Riesgo)

## H04 — VaR histórico y ES se calculan en Python con una convención de cuantil distinta de la de C++
Archivo: `desk/api/risk/hist_var.py` (y `src/risk/var.cpp`)
Símbolo: `compute_hist_var`; `qf::risk::historicalVaR`
Qué hace el código: el percentil y el déficit esperado se calculan en Python: `k = max(1, ceil(round(W·(1 − α), 9)))`, `VaR = L_(k)·√H` y `ES = max(media de las k mayores pérdidas · √H, VaR)`, con las pérdidas ordenadas de mayor a menor. La media del ES incluye la pérdida del propio VaR (`L_(k)`) y no pondera fraccionariamente cuando `W(1 − α)` no es entero. La función C++ `historicalVaR` (no expuesta en `qfpy`, no usada por el backend) toma el índice `⌊(1 − α)n + 1e-9⌋` (base 0) del vector ordenado de menor a mayor: coincide con el desk salvo cuando `n(1 − α)` es entero, donde toma una pérdida más profunda (`k = n(1 − α) + 1`). Ejemplo con `W = 60`, `α = 0.95`: el desk toma la 3.ª peor pérdida (`k = 3`) y C++ la 4.ª.
Qué declara la Metodología/el diseño: Metodología, «Riesgo avanzado», «Déficit esperado»: «Promedio de las pérdidas más allá del VaR al mismo nivel; siempre es mayor o igual que el VaR.» y «VaR histórico»: «Percentil empírico». `CLAUDE.md` del repo: «Toda la matemática financiera vive en C++ y se llama por `qfpy`; Python valida, orquesta fechas y fijaciones, y persiste.»
Impacto: el ES del desk promedia las `k` peores pérdidas incluida la del VaR, no solo las que están «más allá» (con el ejemplo del capítulo 9 daría 2.90·e en vez de 2.85·e, 1.8 % más); y el cuantil y el ES se calculan fuera de C++, con una convención distinta de la de `historicalVaR`. Ninguna cifra del desk cambia hoy porque el backend no usa `historicalVaR`, pero quien la conecte obtendría otro cuantil cuando `W(1 − α)` sea entero.
Capítulo: 9 (Riesgo)
