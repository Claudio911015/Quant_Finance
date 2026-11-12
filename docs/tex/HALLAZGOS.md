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
Resolución: `bootstrapOis` lanza `std::invalid_argument` con `InterpolationMethod::LogLinear` (`ValueError` en `qfpy`); no se implementó el bootstrap log-lineal. El comentario de contrato de `bootstrapOis` y de `bootstrapXccyDiscount` dice ahora que solo Linear reprecia exactamente (CubicSpline de forma aproximada; `bootstrapXccyDiscount` con LogLinear sigue fallando con `std::runtime_error`). Pruebas: `OisBootstrap.LogLinearIsRejected` (C++) y `test_bootstrap_ois_rejects_loglinear`; la prueba de bindings que aceptaba LogLinear usa CubicSpline. Commit f39d31f.

## H02 — Alta a la par de un swap que empieza antes del snapshot: tasa del swap envejecido, sin fijaciones y sin aviso
Archivo: `desk/api/portfolio.py`
Símbolo: `_at_par`
Qué hace el código: arma `valuation.aged_swap({start_date, maturity_date}, {..., fixed_rate: 0.0}, mkt, {}, [])` con `mkt` en el `as_of` del snapshot de la petición (o `MX-DEMO`) y guarda como tasa fija `par_rate(mkt.env)` de ese swap *envejecido*. Se pasan `fixings = {}` y la lista de avisos se descarta. Si `start_date == as_of` es la tasa par de inicio; si `start_date < as_of`, los días ya transcurridos del periodo en curso se capitalizan con la tasa a un día de la curva (`valuation.accrued_factor`, rama sin fijaciones) y la tasa guardada es la par del tramo que queda, no la par en la fecha de inicio. Reproducción: base temporal (`db.connect`, `db.init_schema`, `seed_market.seed_market`), pagador TIIE-F de 13 periodos, `portfolio._at_par(conn, {}, params, start, start + 13*28 días)`: con `start` = `as_of` de `MX-DEMO` (2026-11-10) devuelve 0.0675000000; con `start` 30 días antes devuelve 0.0676677218 sobre la misma curva.
Qué declara la Metodología/el diseño: Metodología, «Ciclo de vida y valuación a fecha», «Alta a la par»: «Un swap dado de alta sin tasa fija nace a la par: se guarda con la tasa par del snapshot de la petición (o MX-DEMO), de modo que su PV en la fecha de pacto es cero.»
Impacto: el PV es cero en la fecha del snapshot de la petición, no en la fecha de pacto ni de inicio cuando son anteriores. Y como no se consultan las fijaciones registradas, la tasa guardada depende de la curva y no de las fijaciones reales de esos días, sin ningún aviso `missing_fixing` al usuario. Con `start_date == as_of` (el caso normal de un alta del día) no hay diferencia.
Capítulo: 3 (Swaps de tasa OIS)
Resolución: omitir `fixed_rate` solo se permite si `start_date` ≥ el `as_of` del snapshot usado; si no, 400 con `field` `fixed_rate` y el mensaje «Para una operación que ya empezó capture la tasa pactada: la tasa par solo se calcula en la fecha de inicio» (`portfolio._at_par`). La siembra (`TRADES`, `XVA_TRADES`) ya traía tasa y diferencial explícitos: el PV de las 16 operaciones sembradas es idéntico bit a bit antes y después. El XVA incremental usa `prepare_trade` y cambia igual (una prueba que dependía de la par con inicio pasado captura ahora `fx_rate` y `spread`). Pruebas nuevas en `test_portfolio.py` y `test_xva_incremental.py`; Metodología «Alta a la par». Commit 1754d54.

## H03 — El residuo de la cascada de P&L es cero por construcción; lo no atribuido cae en «Eventos»
Archivo: `desk/api/risk/explain.py`
Símbolo: `_components` (y `explain_pnl`)
Qué hace el código: `events = (pv_to + settled) − (values[-1] + s0)` es un componente de cierre: recoge todo lo que la cadena de mercados híbridos no explica (terminaciones, ejercicios, cambios de nocional y cualquier otro efecto residual de valuar con los eventos completos en vez de los de la fecha `from`). Con `carry = values[0] − pv_from + s0_origin`, los pasos `values[s] − values[s−1]`, el ajuste `fx += s0 − s0_origin` y `events`, la suma telescopa a `pv_to + settled − pv_from`, que es el P&L oficial de `pnl.compute_pnl`; por eso `residual = pnl − Σ(componentes)` vale 0.0 salvo redondeo de coma flotante. Medido con el forward FX y el IRS del ejemplo 6 del capítulo 9 (MX-DEMO → un snapshot con TIIE-F +25 pb, SOFR −25 pb y spot +3 %): residuo 0.0 en las dos operaciones. Solo es distinto de cero cuando la cascada de una operación lanza una excepción (entonces todo su P&L va al residuo y `explain_error` dice por qué). Además, ningún dato del snapshot que afecte al PV queda fuera de los bloques (cotizaciones de cada curva, puntos forward y base, spot, superficie de volatilidad y parámetros de Hull–White); lo demás (`factors`, rótulos) no entra a la valuación.
Qué declara la Metodología/el diseño: Metodología, «Riesgo avanzado», «Residuo»: «Por qué no es exactamente cero: la cascada suma exactamente el P&L salvo redondeo numérico y datos del mercado que no pertenecen a ningún bloque.» El diseño del corte 6 (D1) dice que «el residuo mide lo no atribuido» aunque la suma sea exacta por construcción.
Impacto: el residuo no mide ninguna calidad de la atribución: un P&L mal explicado por los bloques de mercado aparece en «Eventos» (y, por tanto, parece un efecto de terminaciones o ejercicios), no en «Residuo». Quien lea «Residuo ≈ 0» no debe concluir que los pasos de mercado lo explican todo. La Metodología debería decir que el residuo es cero por construcción y que «Eventos» es el componente de cierre, o el código debería aislar los eventos valuando con y sin ellos como también declara la Metodología («Terminaciones, ejercicios y cambios de nocional se aíslan valuando con y sin los eventos de la ventana»).
Capítulo: 9 (Riesgo)
Resolución: la Metodología («Riesgo avanzado», «Residuo» y «Operaciones nuevas y eventos») dice que el residuo es un control aritmético, cero por construcción salvo redondeo, y que lo no atribuido a los pasos de mercado cae en «Eventos», el componente de cierre. Sin cambio de código. Commit 5287e1e.

## H04 — VaR histórico y ES se calculan en Python con una convención de cuantil distinta de la de C++
Archivo: `desk/api/risk/hist_var.py` (y `src/risk/var.cpp`)
Símbolo: `compute_hist_var`; `qf::risk::historicalVaR`
Qué hace el código: el percentil y el déficit esperado se calculan en Python: `k = max(1, ceil(round(W·(1 − α), 9)))`, `VaR = L_(k)·√H` y `ES = max(media de las k mayores pérdidas · √H, VaR)`, con las pérdidas ordenadas de mayor a menor. La media del ES incluye la pérdida del propio VaR (`L_(k)`) y no pondera fraccionariamente cuando `W(1 − α)` no es entero. La función C++ `historicalVaR` (no expuesta en `qfpy`, no usada por el backend) toma el índice `⌊(1 − α)n + 1e-9⌋` (base 0) del vector ordenado de menor a mayor: coincide con el desk salvo cuando `n(1 − α)` es entero, donde toma una pérdida más profunda (`k = n(1 − α) + 1`). Ejemplo con `W = 60`, `α = 0.95`: el desk toma la 3.ª peor pérdida (`k = 3`) y C++ la 4.ª.
Qué declara la Metodología/el diseño: Metodología, «Riesgo avanzado», «Déficit esperado»: «Promedio de las pérdidas más allá del VaR al mismo nivel; siempre es mayor o igual que el VaR.» y «VaR histórico»: «Percentil empírico». `CLAUDE.md` del repo: «Toda la matemática financiera vive en C++ y se llama por `qfpy`; Python valida, orquesta fechas y fijaciones, y persiste.»
Impacto: el ES del desk promedia las `k` peores pérdidas incluida la del VaR, no solo las que están «más allá» (con el ejemplo del capítulo 9 daría 2.90·e en vez de 2.85·e, 1.8 % más); y el cuantil y el ES se calculan fuera de C++, con una convención distinta de la de `historicalVaR`. Ninguna cifra del desk cambia hoy porque el backend no usa `historicalVaR`, pero quien la conecte obtendría otro cuantil cuando `W(1 − α)` sea entero.
Capítulo: 9 (Riesgo)
Resolución: la Metodología declara el cuantil (la k-ésima peor pérdida sin interpolar, k = max(1, ⌈W(1 − α)⌉)) y que el ES promedia las k peores pérdidas, incluida la del VaR, calculados en Python y no con `historicalVaR`. Sin cambio de código. Commit 83dbcc9.

## H05 — Tolerancia de 5e-4 en cap/floor y swaption: cinco órdenes de magnitud por encima de lo observado
Archivo: `desk/validation/common.py`
Símbolo: `TOLERANCES` (entradas `cap_floor` y `swaption`) y `classify`
Qué hace el código: clasifica como `ok` cualquier caso con diferencia relativa al nocional ≤ 5e-4 en `cap_floor` y `swaption`, sin más aviso. En el reporte versionado las 16 diferencias de esos dos productos son ≤ 2.98e-9 (`swaption-03`) y ≤ 2.79e-16 (`cap_floor-02`), es decir, entre cinco y doce órdenes de magnitud bajo la tolerancia. Un defecto de hasta 5e-4 del nocional (100 000 MXN sobre 200 000 000 MXN) quedaría `ok` y la prueba de humo (`test_el_reporte_versionado_no_tiene_problemas`) no lo vería; la swaption que sí se detectó (`swaption-04`) era de 1.84e-3.
Qué declara la Metodología/el diseño: Metodología, «Validación contra QuantLib», «Tolerancias»: «caps/floors y swaptions con Hull-White 5e-4, porque las implementaciones y convenciones del modelo difieren.» Diseño del corte 7 (D3): «modelo y convenciones de implementación distintos; la diferencia se explica caso por caso».
Impacto: la razón declarada ya no es lo que miden los datos (con los mismos insumos y el mismo modelo la diferencia es de redondeo y del orden de 1e-9 en la swaption), de modo que la tolerancia no acota la discrepancia real: es un margen de protección contra futuras diferencias de convención, y la validación de Hull–White es mucho menos sensible de lo que sugiere el texto. No se propone aquí un valor nuevo; sería una decisión sobre cuánta diferencia de implementación se tolera.
Capítulo: 12 (Validación contra QuantLib)
Resolución: la tolerancia de `cap_floor` y `swaption` baja a 1e-6 del nocional (`desk/validation/common.py`, README del arnés, Metodología «Tolerancias» y fixture de la interfaz). `make_report.sh` regenerado sobre el commit ea8d1cf: 62 dentro, 0 explicadas, 0 fuera, `commit_matches: true` (peores diferencias: 2.98e-9 en swaption y 2.79e-16 en cap/floor). La prueba que edita un PV dentro de tolerancia usa 5e-7. Commit d386877.

## H06 — La Metodología no declara varios límites de la validación que el README del arnés sí declara (o que ninguno declara)
Archivo: `desk/ui/src/screens/MethodologyScreen.tsx` (y `desk/validation/README.md`)
Símbolo: `VALIDATION_SECTIONS` («Qué se compara», «Curvas idénticas», «Qué no se compara»)
Qué hace el código: el arnés entrega a QuantLib los factores de descuento ya armados (`ql_curves.build_curve`), de modo que no valida el bootstrap y que en los pilares la comparación de curvas es una identidad salvo redondeo; las opciones USDMXN usan la volatilidad plana que el escritorio leyó de su superficie en (K, T) (insumo `vol` de `export_cases._inputs`), así que no valida la interpolación de la superficie; solo se usan las curvas `TIIE-F` y `SOFR` con colateral en pesos (`MarketContext.mxn_discount = "TIIE-F"` por omisión), sin la curva MXN-USD ni el `xccy_swap` (los siete productos de `common.PRODUCTS` no lo incluyen); QuantLib usa `NullCalendar`/`Unadjusted` y fechas enteras, y ningún caso pasa del último pilar (la extrapolación plana no se ejerce).
Qué declara la Metodología/el diseño: «Qué se compara» dice «con las mismas curvas, spot, volatilidades y parámetros de Hull-White» y «Qué no se compara» solo enumera «Riesgo (DV01, escenarios, VaR), XVA, contabilidad de coberturas, valuación de operaciones envejecidas con fijaciones y datos de mercado reales de un proveedor». El README del arnés sí declara que no valida el bootstrap, la superficie ni el envejecimiento, pero ni él ni la Metodología mencionan el cross currency swap, la curva MXN-USD, los calendarios ni la extrapolación.
Impacto: quien lea solo la Metodología (la pantalla de la aplicación) puede creer que el bootstrap, la superficie de volatilidad y el cross currency swap están validados contra QuantLib. Lo correcto es añadir esos puntos a «Qué no se compara».
Capítulo: 12 (Validación contra QuantLib)
Resolución: la Metodología («Qué no se compara») añade el bootstrap, la interpolación de la superficie, el cross currency swap, la curva MXN-USD, los calendarios y la extrapolación. Commit 3198f6f.

## H07 — `hedge_ratio` no entra en la medición del periodo
Archivo: `desk/api/hedge_measure.py` y `desk/api/hedge_effectiveness.py`
Símbolo: `measure` (compara `F × instrumento` con el derivado hipotético sin escalar) y `critical_terms` (única función que usa la razón)
Qué hace el código: la razón `h` se guarda al designar y solo se compara en el término crítico de nocional (`F × nocional del instrumento` contra `h × nocional de la partida`). `measure` no la usa: el hipotético tiene el nocional de la partida, sin multiplicar por `h`, y la regla del menor y el reciclaje comparan siempre contra él. Comprobado: swap de 600 M contra crédito de 500 M con `hedge_ratio = 1.2` (los cinco términos críticos salen `match`) da en el primer cierre inefectividad 41 720.6329, idéntica a la de la misma cobertura con `hedge_ratio = 1`.
Qué declara la Metodología/el diseño: el diseño del corte 4 (D2) define `hedge_ratio` como «unidades de instrumento por unidad de partida» y la aclaración P-aceptada dice que «solo entra a la comparación de nocional». La Metodología («Coberturas») no lo menciona: lista como simplificación solo «sin reequilibrio de la razón de cobertura». IFRS 9 6.4.1(c)(iii) pide que la razón designada sea la de las cantidades realmente cubiertas.
Impacto: una razón distinta de 1 que el usuario considera intencional aparece como sobre o subcobertura en la medición: la parte del instrumento que excede a la partida va a inefectividad aunque la razón la justifique, y una cobertura por debajo de la razón no genera inefectividad. El campo sirve solo para avisar de `mismatch` en nocional.
Capítulo: 10 (Contabilidad de coberturas IFRS 9)
Resolución: la medición no cambia (decisión contable pendiente de un contador). El alta avisa `hedge_ratio_mismatch` si `hedge_ratio` difiere en más de 1 % de (fracción designada × nocional del instrumento) / nocional de la partida; la Metodología (fila «Razón de cobertura» y lista de avisos) y el reporte de la relación (`DECL_HEDGE_RATIO`) declaran que se compara la fracción designada del instrumento contra la partida completa y que la razón capturada es informativa. El punto quedó como observación 8 en las «Observaciones contables que siguen abiertas» de `docs/superpowers/qf-desk/corte4/audit.md`, que es la lista de cuestiones para el contador. Commit 0912da3.

## H08 — El aviso `forecast_date_holiday` no está en la Metodología
Archivo: `desk/api/hedges.py`
Símbolo: `_designation_warnings`
Qué hace el código: además de `no_economic_relationship`, `instrument_off_market`, `forecast_date_weekend` y `designation_backdated`, emite `forecast_date_holiday` cuando la fecha del flujo pronosticado es un día inhábil de México (lunes a viernes): «se liquidará con el último FIX publicado».
Qué declara la Metodología/el diseño: Metodología, «Coberturas», «Derivado fuera de mercado»: «Al designar, el alta avisa de esto, de que la prueba prospectiva no muestre relación económica, de un flujo pronosticado en fin de semana (…) y de una cobertura documentada más de un día después de su fecha de designación». No menciona el inhábil.
Impacto: ninguno en cifras: el aviso informa, no bloquea ni cambia la medición. La lista de avisos de la Metodología está incompleta.
Capítulo: 10 (Contabilidad de coberturas IFRS 9)
Resolución: la Metodología lista `forecast_date_holiday` entre los avisos del alta. Commit 47a2977.

## H09 — La relación queda «concluida» también cuando instrumento y partida vencen juntos
Archivo: `desk/api/hedges.py`
Símbolo: `status`
Qué hace el código: devuelve `concluida` siempre que el `trade_status` del último cierre es `vencida` (el instrumento), sin mirar si el derivado hipotético también venció. Comprobado: swap idéntico al crédito, cierre a 35 días y cierre final al vencimiento: estado `concluida` con reserva 0.00 (sin nada pendiente de reciclar).
Qué declara la Metodología/el diseño: Metodología, «Reciclaje»: «En el cierre final la reserva queda en 0 si el instrumento y la partida vencen juntos. Si el instrumento vence antes que el flujo cubierto, la reserva se conserva en ORI (…) y la relación pasa a Concluida». Presenta `concluida` solo para el segundo caso; el diseño (F2) la describe como «instrumento vencido; reserva pendiente de reciclar».
Impacto: el estado «concluida» no distingue la cobertura terminada del todo de la que aún tiene reserva pendiente: hay que mirar el saldo de la reserva. La nota de reserva pendiente del reporte sí se muestra solo si el saldo no es cero.
Capítulo: 10 (Contabilidad de coberturas IFRS 9)
Resolución: la Metodología dice que la relación queda Concluida siempre que el último cierre fue el final, también con instrumento y partida vencidos juntos y reserva cero. Commit 4fb5d75.

## H10 — La identidad de control de valor razonable vale cero por construcción
Archivo: `desk/api/hedge_measure.py`
Símbolo: `measure` (rama `fair_value`, campo `identity_residual`)
Qué hace el código: calcula `identity_residual = (d_inst_cum + settled_period) − (ineffectiveness − item_adjustment + settled_period)` con `ineffectiveness = d_inst_cum + item_adjustment`: el resultado es algebraicamente cero para cualquier entrada, de modo que no detecta ningún error de la rama.
Qué declara la Metodología/el diseño: diseño del corte 4, D4: «Identidad de control (se guarda y se prueba)». La Metodología no habla de la identidad, y el diseño la enuncia con detalle para flujo de efectivo (donde sí es una comprobación: depende de `inst_total`, `effective_cum`, `oci` y `recycled`).
Impacto: en valor razonable el campo `identity_residual` siempre es 0.0 y no sirve de control; la única comprobación del periodo es el cuadre de cargos y abonos.
Capítulo: 10 (Contabilidad de coberturas IFRS 9)
Resolución: ningún consumidor necesitaba el campo (la interfaz solo lo declaraba en un tipo y una prueba lo leía como aserción vacía): en valor razonable el periodo ya no guarda `identity_residual`; en flujo de efectivo se conserva. Commit ac3725d.

## H11 — El término crítico «moneda» del flujo pronosticado compara una constante
Archivo: `desk/api/hedge_effectiveness.py`
Símbolo: `critical_terms`
Qué hace el código: para `forecast_fx` emite `_term("currency", "USD", "USD")`: ambos lados están fijos, así que el término siempre sale `match`.
Qué declara la Metodología/el diseño: Metodología, «Efectividad prospectiva»: «Términos críticos (nocional, índice o moneda, fechas y sentido…)». Sugiere una comparación real de la moneda.
Impacto: ninguno hoy: el único par admitido es USDMXN con un `fx_forward`, y el alta rechaza otras combinaciones. El término es informativo y no puede fallar.
Capítulo: 10 (Contabilidad de coberturas IFRS 9)
Resolución: `critical_terms` ya no emite el término «moneda» del flujo pronosticado (ni su rótulo ni su tipo en la interfaz); la Metodología deja de mencionarlo. La prueba del forward idéntico espera nocional, vencimiento y sentido. Commit 9684cbe.

## H12 — El residuo de redondeo en valor razonable no va a «inefectividad»
Archivo: `desk/api/hedges.py` y `desk/api/hedge_measure.py`
Símbolo: `MAIN_RESULT_ACCOUNT`; `journal`
Qué hace el código: el residuo de redondeo se absorbe en la última línea de la cuenta de resultados principal del tipo: «Resultados — inefectividad de cobertura» en flujo de efectivo y «Resultados — cobertura de valor razonable» en valor razonable (donde no existe una cuenta de inefectividad separada).
Qué declara la Metodología/el diseño: Metodología, «Coberturas», «Asientos sugeridos»: «el residuo del periodo va a resultados por inefectividad», sin distinguir el tipo.
Impacto: solo la redacción: en valor razonable el residuo (a lo más unos centavos) queda mezclado con el resultado de cobertura, no en una línea de inefectividad.
Capítulo: 10 (Contabilidad de coberturas IFRS 9)
Resolución: la Metodología («Asientos sugeridos») dice que el residuo de redondeo va a la cuenta principal de resultados del tipo: «Resultados — inefectividad de cobertura» en flujo de efectivo y «Resultados — cobertura de valor razonable» en valor razonable. Sin cambio de código. Commit d79f023.

## H13 — El cupón del bono no devenga ACT/360: es nominal × tasa / frecuencia y el corrido es lineal en días/365
Archivo: `src/instruments/bond.cpp` y `desk/api/pricing/rates.py`
Símbolo: `Bond::cashflows`; `_bond_instrument`
Qué hace el código: `_bond_instrument` construye `qfpy.Bond(face, coupon_rate, periods, frequency)` sin base de días, con la ACT/365 por omisión: el cupón de cada periodo es `face × coupon_rate / frequency` (`periodFraction(frequency, ACT_365) = 1/frequency`) y el corrido del bono envejecido es `face × coupon_rate × (tiempo transcurrido desde el último cupón, en años de i/frecuencia y días/365)`. No hay base ACT/360 ni conteo de los días reales de cada periodo.
Qué declara la Metodología/el diseño: Metodología, «Ciclo de vida y valuación a fecha», «Convención de días»: «Días naturales, t = días/365, devengo ACT/360, fijaciones diarias capitalizadas»; «Bono»: «Flujos fijos descontados con la curva elegida»; «Límites», «Bono»: «Periodos uniformes; la convención M-Bono de 182 días queda fuera».
Impacto: un bono de nominal 10^8 y cupón 7.5 % semestral paga 3 750 000 por periodo; con devengo ACT/360 sobre 182.5 días pagaría 3 802 083.33 (+1.4 %). La frase «devengo ACT/360» rige para los swaps y las opciones de tasa, no para el bono. La validación contra QuantLib usa ACT/365 y coincide a 6e-8 del nocional (caso bond-08), de modo que el cálculo es coherente con lo que el código hace, no con la frase general de la Metodología.
Capítulo: 6 (Bonos)
Resolución: la Metodología limita «devengo ACT/360» a los swaps y las opciones de tasa y añade la fila «Cupón» del bono (nominal × tasa / frecuencia, corrido lineal en días/365). Sin cambio de código. Commit 6319970.

## H14 — Docstring y ramas de `valuation.shortened` describen un envejecimiento de cap/floor y bono que `value_trade` ya no usa
Archivo: `desk/api/valuation.py`
Símbolo: docstring del módulo y `shortened`
Qué hace el código: `value_trade` valúa el bono y el cap/floor con `aging.bond_pv_mxn` y `aging.cap_floor_pv_mxn` (calendario exacto, cupón corrido, caplet fijado fuera del valor) y solo pasa por `shortened` la swaption, las opciones FX y la opción sobre acción. Las ramas `cap_floor` (`periods = ceil(días / días del periodo)`) y bono (`periods = ceil((días − 0.5)·frecuencia / 365)`) de `shortened` no tienen llamador, y el docstring del módulo sigue presentándolas como «aproximación declarada» que acorta los periodos con `ceil`.
Qué declara la Metodología/el diseño: Metodología, «Ciclo de vida y valuación a fecha», «Bono y cap/floor envejecidos»: calendario exacto de i/frecuencia años con cupón corrido y caplet ya fijado fuera del valor; no habla de periodos enteros.
Impacto: ninguno en el cálculo; un lector que solo vea `valuation.py` puede creer que el bono y el cap/floor se envejecen por periodos enteros.
Capítulo: 5 (Hull–White) y 6 (Bonos)
Resolución: se borraron las ramas `cap_floor` y bono de `valuation.shortened` (sin llamador, comprobado con grep) y se corrigió el docstring del módulo. Las suites no cambian. Commit ea8d1cf.

## H15 — Alta a la par de un cross currency swap que empieza antes del snapshot: diferencial del swap envejecido, sin fijaciones y sin aviso
Archivo: `desk/api/xccy.py` (llamada desde `desk/api/portfolio.py`, `prepare_trade`)
Símbolo: `at_par` (vía `resolve` y `aged_xccy`)
Qué hace el código: si el alta no trae `fx_rate` o `spread`, `at_par` arma el swap con las fechas de la operación y lo envejece con `mkt` en el `as_of` del snapshot de la petición (o `MX-DEMO`), con `fixings = {}` y descartando la lista de avisos: `fx_rate` queda en el spot de ese snapshot y `spread` es `par_spread(mkt.env)` del swap *envejecido*. Si `start_date == as_of` es el diferencial de la cotización; si `start_date < as_of`, los días ya transcurridos del periodo en curso se capitalizan en cada pata con la tasa a un día de su curva (`valuation.accrued_factor` sin fijaciones) y el diferencial guardado hace cero el PV en el `as_of`, no en la fecha de inicio. Medido con `xccy.at_par` sobre `MX-DEMO` (spot 18.60, 5 millones de USD, 26 periodos, ambos intercambios, base temporal sembrada con `seed_market`): con `start_date = as_of` el diferencial es −0.0010000 (la cotización de 2 años); con inicio 14 días antes, −0.0016137; 30 días antes, −0.0010829; 60 días antes, −0.0011729. `fx_rate` es 18.6 en todos.
Qué declara la Metodología/el diseño: Metodología, «Ciclo de vida y valuación a fecha», «Alta a la par»: «Un swap dado de alta sin tasa fija nace a la par: se guarda con la tasa par del snapshot de la petición (o MX-DEMO), de modo que su PV en la fecha de pacto es cero.»; y el docstring de `at_par`: «la operación nace a la par y queda guardada con ambos».
Impacto: el PV es cero en la fecha del snapshot de la petición, no en la de pacto ni en la de inicio cuando son anteriores; el diferencial guardado depende de los días transcurridos y de la tasa a un día de la curva, no de las fijaciones reales, sin aviso `missing_fixing`, y `fx_rate` es el spot del snapshot y no el tipo de cambio de la fecha de inicio. Con `start_date == as_of` (el alta del día) no hay diferencia. Es el mismo mecanismo que H02 para el `irs`.
Capítulo: 7 (Cross currency swap)
Resolución: la misma regla que H02 para el diferencial del `xccy_swap` (`xccy.at_par`: 400 con `field` `spread` y «Para una operación que ya empezó capture el diferencial pactado: el diferencial par solo se calcula en la fecha de inicio»). La regla no se extendió a `fx_rate` omitido, que sigue tomando el spot del snapshot. Commit 1754d54.

## H16 — El comentario de contrato de `VolSurface` dice extrapolación plana en varianza; el código extrapola plano en volatilidad
Archivo: `include/qf/termstructure/volsurface.hpp` (contrato) y `src/termstructure/volsurface.cpp`
Símbolo: `VolSurface` (comentario de clase) y `VolSurface::vol`
Qué hace el código: `vol` ancla la varianza total en (T = 0, w = 0) y la interpola linealmente hasta el último plazo, de modo que antes del primer plazo la volatilidad es la del primer pilar; a partir del último plazo devuelve la volatilidad del último pilar (plana en volatilidad, la varianza total sigue creciendo como σ_n²·T). Medido con una superficie de plazos 0.25 y 0.5 años y strikes 18, 19 y 20 (volatilidades 0.130, 0.120, 0.125 y 0.135, 0.125, 0.130): `vol(18.5, 0.125)` = 0.125 y `vol(18.5, 0.7)` = 0.130. Los comentarios en línea de `vol` describen esto correctamente.
Qué declara la Metodología/el diseño: el comentario de clase de `VolSurface` dice que el segundo paso interpola «w linearly in T (flat extrapolation on w)»; con extrapolación plana en la varianza la volatilidad sería √(w_1/T) = 0.1768 a 0.125 años y √(w_n/T) = 0.1099 a 0.7 años. La Metodología («Opción FX») solo dice «Vol de la superficie por plazo y strike».
Impacto: ninguno en el cálculo; quien lea el contrato del encabezado en vez del cuerpo de `vol` esperaría una volatilidad que sube antes del primer plazo y decae después del último.
Capítulo: 4 (Derivados de FX y opción sobre acción)
Resolución: el comentario de contrato de `VolSurface` dice que la extrapolación es plana en volatilidad (σ del primer pilar antes del primer plazo y σ del último después). Solo comentario. Commit 2c1a4ab.

## H17 — La bandera de términos de la conciliación se levanta sin probar ningún factor en `xccy_swap` y `equity_option`
Archivo: `desk/api/ops_recon.py`
Símbolo: `reconcile_trade` (con `CURVE_PRODUCTS` y `FX_PRODUCTS`)
Qué hace el código: `terms_flag = status == "revisar" and (bp is None or abs(bp) > 25) and (pct is None or abs(pct) > 2)`. `bp` solo se calcula para `CURVE_PRODUCTS` (`irs`, `cap_floor`, `swaption`, `bond`) y `pct` solo para `FX_PRODUCTS` (`fx_forward`, `fx_option`). Para `xccy_swap` y `equity_option` ambos son `None`, de modo que cualquier fila `revisar` de esos dos productos sale con bandera de términos aunque ni la curva ni el tipo de cambio se hayan probado (verificado con un `equity_option` y un `xccy_swap` cuyo PV del banco difiere en 5 millones de MXN: `terms_flag` verdadero, `decomposition.curve` y `decomposition.fx` en `None`).
Qué declara la Metodología/el diseño: Metodología, «Conciliación»: «se marca para revisar, con bandera de términos si ni ±25 pb ni ±2 % la explican»; corte 5, D5: bandera «si la diferencia supera lo explicable por ±25 pb o ±2 % de spot».
Impacto: para esos dos productos la bandera no aporta información (es siempre verdadera en `revisar`); un auditor que la lea como «se probó el desplazamiento de curva y de spot y no explica» se equivoca. En los demás productos la regla coincide con la Metodología.
Capítulo: 11 (Operaciones: conciliación)
Resolución: en `xccy_swap` y `equity_option` la fila `revisar` sale con `terms_flag` nulo y `terms_reason` «sin descomposición para este producto» (también en la columna `reason` del CSV); la interfaz lo rotula «Sin descomposición para este producto» y la Metodología de Conciliación lo declara. Los productos con factores no cambian. Commit baa4631.

## H18 — El docstring de `settlement.py` dice que el bono no liquida; el código ya liquida cupones y amortización
Archivo: `desk/api/settlement.py`
Símbolo: docstring del módulo (lista de productos) y `settled_flows`
Qué hace el código: `settled_flows` despacha el bono a `aging.bond_settled`, que emite los cupones (`coupon`) y la amortización (`redemption`) en `(d0, d1]` con la misma regla de «viva el día anterior» que el `irs`; solo `cap_floor` y `swaption` (`_NO_SETTLEMENT`) quedan con el aviso `no_settlement`. El docstring del módulo todavía enumera «`cap_floor`, `swaption`, `bond`: sin flujo derivado al vencer, solo el aviso `no_settlement` (el bono lo despacha a `aging`; T9 lo hará liquidar)».
Qué declara la Metodología/el diseño: Metodología, «Bono y cap/floor envejecidos»: «sus cupones y su amortización se liquidan»; el cap/floor y la swaption no tienen liquidación derivada.
Impacto: ninguno en el cálculo; el encabezado del módulo describe un estado anterior y puede hacer creer que el cupón y la amortización de un bono no entran al P&L.
Capítulo: 8 (Ciclo de vida, liquidaciones y P&L)
Resolución: el docstring de `settlement.py` dice que el bono liquida cupones y amortización por `aging.bond_settled`. Commit 31873c5.

## H19 — El calendario `US` marca inhábil el 2023-11-10, pero la Fed de Nueva York publicó SOFR ese día
Archivo: `desk/api/calendars.py`
Símbolo: `_united_states`, `_observed`
Qué hace el código: un feriado de fecha fija en sábado se observa el viernes anterior (excepto el 1 de enero). Veterans Day de 2023 cayó en sábado (11 de noviembre), así que `is_business_day("US", date(2023, 11, 10))` es falso (`holidays("US", 2023)` lo nombra «Veterans Day»). Comprobación hecha el 2026-11-11 con la API de la Fed de Nueva York (`search.json`, año por año de 2020 a 2026; 1 712 observaciones del 2020-01-02 al 2026-11-09): todos los días que el calendario marca hábiles tienen SOFR, y la única fecha con SOFR publicada que el calendario marca inhábil es 2023-11-10 (`percentRate` 5.32). Las Reservas Federales abren el viernes anterior a un feriado en sábado (Fed, K.8), aunque el calendario SIFMA sí lo trata como cierre.
Qué declara la Metodología/el diseño: Metodología, «Calendarios»: «de publicación de SOFR (SIFMA) en EE. UU. para SOFR, por reglas 2020–2040. Una fijación no publicada en día inhábil de su índice no es faltante.» El docstring del módulo dice «calendario SIFMA (el de la publicación de SOFR)».
Impacto: bajo. Una operación envejecida a través del 2023-11-10 con SOFR cargada ese día la usa tal cual (una fijación cargada en día inhábil se usa), y una fijación faltante ese día no avisaría. Los demás sábados observados de 2020 a 2026 (3 de julio de 2020, 24 de diciembre de 2021, 3 de julio de 2026) sí coinciden con la ausencia de SOFR. El próximo caso de Veterans Day en sábado es el 2028-11-11 (viernes 2028-11-10): sin comprobar.
Capítulo: 1 (Introducción, arquitectura y convenciones)
Resolución: el Día de los Veteranos en sábado no se traslada al viernes en el calendario `US` (`calendars._observed` cambia `is_new_year` por `saturday_to_friday`); los traslados de 2020-07-03, 2021-12-24 y 2026-07-03 no cambian y el domingo sigue pasando al lunes. La regla se confirmó con la comparación del hallazgo, repetida el 2026-11-11 tras la corrección con las mismas 1 712 observaciones de SOFR de la Fed de Nueva York (ninguna fecha con SOFR es inhábil y ningún día hábil entre 2020-01-02 y 2026-11-09 carece de SOFR), con K.8 de la Fed y con el archivo de SIFMA, que lista Veterans Day 2023 sin recomendación de cierre. No se contrastó el caso 2028-11-10. Pruebas en `test_calendars.py`. Commit d4e6f30.

## H20 — `MDF_FETCH` por omisión sigue a `MDF_DB`; el README lo da como una ruta fija
Archivo: `desk/api/app.py`
Símbolo: `create_app` (`app.config["MDF_FETCH"]`)
Qué hace el código: `MDF_FETCH` por omisión es `<directorio de MDF_DB>/examples/fetch_sofr`. Con `MDF_DB` sin definir coincide con la ruta del README (`~/Git/MarketDataFeed/build/examples/fetch_sofr`); si solo se define `MDF_DB`, el ejecutable que se busca cambia con ella.
Qué declara la Metodología/el diseño: `desk/README.md`, «Datos de mercado reales»: «`MDF_FETCH`: `~/Git/MarketDataFeed/build/examples/fetch_sofr`» como ruta por omisión.
Impacto: bajo; solo afecta a quien cambie `MDF_DB` y espere que el ejecutable siga en la ruta fija. Un refresco con la ruta equivocada responde 502 («No se pudo ejecutar MarketDataFeed»).
Capítulo: 13 (Fuentes de datos y procedencia)
Resolución: `desk/README.md` dice que `MDF_FETCH` por omisión es `<directorio de MDF_DB>/examples/fetch_sofr`. Commit 70963b6.

## H21 — El XVA se integra sobre la malla de reporte mensual con el extremo derecho; la Metodología habla de «malla diaria» y no declara esa discretización
Archivo: `desk/api/risk/xva.py` (y `desk/api/risk/credit.py`)
Símbolo: `report_days` (usa `credit._grid`) y, en C++, `computeXva` (suma sobre `profile.times`)
Qué hace el código: la simulación avanza por días, pero CVA, DVA y FVA se calculan solo con los perfiles descontados de la malla de reporte (hoy y fechas mensuales hasta el primer mes que alcanza el último vencimiento), multiplicando el perfil de cada fecha por la probabilidad de incumplimiento del intervalo que termina en ella (regla del extremo derecho). En una fecha en que una operación ya pagó su último flujo el valor es cero, así que el intervalo donde vence aporta exposición cero. Medido con `docs/tex/verificacion/cap14_xva.py` (mismas trayectorias, solo cambia la malla): Banco Ejemplo (IRS TIIE-F de 200 millones envejecido más XCCY de 10 millones de USD con intercambio final, 2 años) tiene CVA 91 386.08 con la malla mensual y 94 347.53 con malla diaria (+3.24 %; el error estándar de Monte Carlo del CVA es 3.4 %). Un swap receptor de un solo periodo de 28 días (PV 40 226 MXN, intensidad plana 2 %, LGD 0.6) tiene CVA exactamente 0 con la malla mensual (fechas 0 y 30 días) y 35.72 MXN con malla diaria.
Qué declara la Metodología/el diseño: Metodología, XVA, «Modelo y medida»: «Malla diaria, trayectorias y semilla fijas»; los límites del XVA no mencionan que los ajustes se integren sobre una malla mensual con el extremo derecho. El diseño (R2) pide la exposición reportada en una malla mensual, pero no declara su efecto sobre el CVA.
Impacto: sesgo sistemático a la baja en operaciones cuya exposición se concentra al final (intercambio final de un XCCY) y CVA cero en operaciones que vencen antes de la primera fecha mensual; en el ejemplo es del tamaño del error de Monte Carlo. No cambia la forma de los perfiles publicados (EPE, ENE, PFE mensuales).
Capítulo: 14 (XVA y curvas de crédito)

## H22 — La Metodología dice que cada operación se descuenta con la curva de su contraparte; el código descuenta SOFR con SOFR y la pata MXN del XCCY con MXN-USD sea cual sea el colateral
Archivo: `desk/api/risk/xva.py`
Símbolo: `_swap_spec`, `_xccy_spec`
Qué hace el código: solo el IRS TIIE-F cambia de curva con el colateral de la contraparte (`csa_discount` si el colateral es USD y el snapshot trae MXN-USD). El IRS SOFR siempre descuenta con SOFR. El XCCY usa `with_collateral("USD")`: su pata MXN descuenta con MXN-USD (TIIE-F si el snapshot no la trae) aunque la contraparte tenga colateral MXN, y su pata USD con SOFR; es lo que hace la valuación del desk (capítulo 7), y el motor coincide con el PV del desk en t = 0.
Qué declara la Metodología/el diseño: Metodología, XVA, «Modelo y medida»: «Cada operación se descuenta con la curva de su contraparte.»
Impacto: bajo; la frase lee como si el colateral de la contraparte eligiera la curva de todos los productos, y solo lo hace en el IRS TIIE-F. El PV y el XVA son coherentes con la valuación del desk.
Capítulo: 14 (XVA y curvas de crédito)
Resolución: la Metodología del XVA («Modelo y medida») dice que solo el IRS TIIE-F cambia de curva con el colateral de la contraparte; el IRS SOFR descuenta siempre con SOFR y el cross currency swap su pata MXN con MXN-USD (TIIE-F si falta) y su pata USD con SOFR. Sin cambio de código. Commit 550dac5.


## H23 — La delta de Monte Carlo de un no touch con la barrera a menos de 1 % del spot sale con el signo contrario: el spot chocado ya pasó la barrera y la fórmula del puente da una supervivencia positiva
Archivo: `desk/api/pricing/fx_exotics.py`
Símbolo: `_result` (delta), `_value`, `_mc`, `_price`
Qué hace el código: `_price` rechaza con 400 una barrera ya tocada solo contra el spot de la petición. La delta se obtiene revaluando con el spot ×1.01 (`_value(p, mkt, spot * (1 + SPOT_BUMP), …)`) sin volver a comprobar la barrera. Si la barrera de arriba está en (X0, 1.01·X0), el spot chocado queda del lado muerto; en `_mc` los nodos de la trayectoria quedan todos del mismo lado de la barrera, el producto de logaritmos es positivo, `exp(-2 ln(X_i/b) ln(X_{i+1}/b)/(σ²Δt))` es menor que 1 y la supervivencia resulta positiva en vez de cero (la fórmula del puente no distingue de qué lado de la barrera está el camino). El motor analítico de QuantLib devuelve 0 con el spot sobre la barrera y no tiene el problema. Medido el 2026-11-11 con MX-DEMO (spot 18.60, 91 días, modelo plano, pago de 1 000 000 MXN, barrera superior 18.62): delta de Monte Carlo +631 697.97, delta del método analítico −66 483.61, delta verdadera (diferencia central de la forma cerrada, paso 1e-4·X0) −619 678.96. Con la barrera en 18.70 el Monte Carlo da +25 816 frente a −626 012 (diferencia central); con 18.80 (más de 1 % arriba) ya coincide (−632 897 frente a −628 962). El caso del double no touch con la barrera superior a menos de 1 % es el mismo mecanismo (el choque es solo hacia arriba, de modo que la barrera inferior no se ve afectada).
Qué declara la Metodología/el diseño: Metodología, «Exóticos de FX», «Error de Monte Carlo»: «delta (+1 % de spot) y vega (+1 punto de vol) por reprecio con la misma semilla». El diseño (R1) pide el 400 de «barrera ya tocada al valuar»; no dice nada del spot chocado.
Impacto: la delta mostrada en la interfaz es incorrecta (hasta de signo) para un no touch hacia arriba con la barrera a menos de 1 % del spot, justo el caso en que la delta es mayor. No afecta al precio, a la vega ni a la gráfica (los spots de la gráfica no pasan de la barrera).
Capítulo: 15 (Exóticos de FX)

## H24 — La Metodología da 0.3–0.8 % del pago como diferencia entre la tabla de volatilidad local y Dupire al vuelo; hasta un año es de 0.01–0.07 % y solo a dos años llega a 0.3–0.5 %
Archivo: `desk/ui/src/screens/MethodologyScreen.tsx` (sección `fx-exoticos`, «Modelos») y `desk/api/pricing/fx_exotics.py`
Símbolo: `_build` (tabla `FixedLocalVolSurface` de `LV_STRIKES = 41` strikes)
Qué hace el código: tabula la volatilidad local de Dupire de QuantLib en 41 strikes entre ±5σ√T y 10 tiempos, e interpola linealmente en strike. Medido el 2026-11-11 (diferencia pareada con las mismas normales, 40 000 trayectorias, valor con la tabla menos valor con `NoExceptLocalVolSurface` al vuelo, en % del pago): no touch superior 19.5 a 91 días −0.018 %; no touch superior 22.0 a 2 años −0.314 %; double no touch (15.5, 23.0) a 2 años −0.515 %. Con 161 strikes, −0.003 % y +0.030 % en los dos casos de 2 años: la diferencia viene de la interpolación lineal en strike de la tabla (a 2 años el paso de 0.25σ√T equivale a 4.6 % del spot). La auditoría del corte midió −0.01 a −0.33 % entre 91 días y 2 años.
Qué declara la Metodología/el diseño: Metodología, «Exóticos de FX», «Modelos»: «Diferencia frente a Dupire al vuelo: del orden de 0.3–0.8 % del pago» (la cifra del plan, antes de la auditoría).
Impacto: bajo. La cifra declarada solo vale a 2 años; a 91 días y a un año la diferencia es entre cinco y treinta veces menor. No cambia ningún precio.
Capítulo: 15 (Exóticos de FX)
