# Auditoría independiente — QF Desk corte 2 (`feat/qf-desk`, commits 35afa48..41f0a3f)

Auditor: agente independiente, 2026-11-11. No se leyó `plan.md` ni se usaron los reportes de los implementadores.
No se arregló nada ni se hicieron commits. Backend propio en 127.0.0.1:5073 con base temporal (scratchpad) y
Chrome headless en el puerto 9333 con perfil propio; ambos apagados al terminar (`ss -ltn` sin 5073/9333).
No se tocaron el 5070, el 9222 ni el Brave del usuario.

## Suites (corridas por el auditor)

| Suite | Comando | Resultado |
|---|---|---|
| C++ | `cmake --build build -j4 && ctest --test-dir build` | BUILD=0; `100% tests passed, 0 tests failed out of 402` |
| Bindings | `cmake --build build --target pytests` | `Ran 56 tests ... OK` (incluye `tests/test_ois_aged_py.py`, 4 tests, `-v` todos ok) |
| desk/api | `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q` | `2150 passed, 1 skipped` |
| vitest | `cd desk/ui && npm test` | `Test Files 13 passed (13)`, `Tests 159 passed (159)` |
| build UI | `npm run build` | `✓ built`, exit 0 (solo el aviso de chunk > 500 kB, deuda declarada) |

El skip es `test_trades_dates.py:225 test_unimplemented_routes_answer_501_json` con conjunto de parámetros vacío (andamio del contrato que ya no tiene rutas 501).

## Veredictos

| R | Veredicto | Evidencia |
|---|---|---|
| R1 | CUMPLE | `POST /api/trades` → 201 con `trade_date/start_date/maturity_date`; `GET /api/trades/8` → un evento `execution`. SQL directo: `UPDATE trade_events ...` y `DELETE FROM trade_events ...` → `trade_events es solo de inserción` (disparadores `desk/api/db.py:19-20`). Tipo `bogus` → 400 `field:"type"`; `execution`/`reset`/`transfer` → 400 `field:"type"` (P9, `events.py:129-132`). `start_date < trade_date` → 400; fecha inválida → 400. |
| R2 | CUMPLE | Script propio: para las 13+ operaciones (semilla + creadas con `quantity_change`, `termination`, `terms_change`) en 5 fechas, `lifecycle.state()` recalculado desde cero con los eventos en orden invertido vs `GET /api/trades/<id>/state`: `65 comparaciones, 0 discrepancias`. Orden `(event_date, id)` en `lifecycle.py:50`; tests `test_same_date_events_the_highest_id_wins`, `test_events_in_any_order_give_the_same_state`. |
| R3 | CUMPLE | Cálculo propio con `qfpy` (curva MX-DEMO TIIE-F y SOFR; swaps par de 728, 1820 y 1095 días; payer y receiver; envejecido a s = 10, 28, 37, 200 días; fijaciones = forwards a un día de D0 compuestas con `compound_overnight`; curva desplazada con pilares en los pagos restantes): peor `|PV_envejecido − PV_D0(flujos restantes)/DF0(s)| / N = 1.5e-15` (tolerancia 1e-6). Constructor nuevo con periodo sin iniciar vs constructor viejo: diferencia relativa `0.0` en todos los casos. Test C++ `tests/test_ois_swap.cpp` y Python `tests/test_ois_aged_py.py` pasan. |
| R4 | CUMPLE | HTTP propio: swap TIIE-F par (2 periodos, N=1e9, tasa par calculada por mí), fijaciones TIIE-F D0..D0+27 = forwards de D0 por CSV, snapshot `AUD-D1` = rodado de MX-DEMO a D0+28 con el pilar 28d puesto a DF0(56)/DF0(28) (DF verificado igual a 1e-16). `GET /api/pnl?from=MX-DEMO&to=AUD-D1`: identidad `pnl == pv_to − pv_from + settled` peor error absoluto `0`; `total_mxn − Σ pnl = 0.0`. Swap par: `settled = 23354.280840778` (mi cupón: `23354.280840555`), `pv_to = −23354.28084055662` (el mío: idéntico), `pnl/N = 2.2e-16`. En UI, el total del P&L (4,886,471.58) coincide con la suma de las filas. |
| R5 | CUMPLE | `termination` sobre la operación 1 el D0+14 → 201 con `termination` + `transfer` (`cause_event_id`). Valuación en MX-DEMO (D0) antes/después: `−942898.4794959975` ambas; en AUD-D1: `terminada`, PV 0. Escenarios en AUD-D1 no listan la operación 1; DV01/VaR la filtran con `valuation.is_live` (`risk/dv01.py`, `risk/var.py`, `risk/scenarios.py`); test `test_r5_terminated_trade_leaves_dv01_by_exactly_its_prior_contribution`. Evento posterior (`quantity_change`, `termination`) → 409. |
| R6 | CUMPLE | `quantity_change` 250e6→500e6 en D0+14 (op. 2): PV en D0 sin cambio (`1602628.727` ambos), en AUD-D1 razón exacta `2.0`. En un `fx_forward` 10e6→5e6: razón `0.5`. |
| R7 | CUMPLE | CSV de 28 filas → `{"inserted":28}`; repetido → `{"inserted":0,"unchanged":28}`; alta USDMXN 201, duplicado exacto 200 `created:false`, otro valor 409; tasa 11 y −1.5 → 400; `NaN` → 400; CSV con `inf` en fila 3 → 400 y no guarda la fila 2 (atómico); filtro `index/from/to` devuelve 10. Swap con fijaciones faltantes (snapshot D0+40) → 200 con aviso `missing_fixing` y las 12 fechas. |
| R8 | CUMPLE | `fx_forward` de 20 días, FIX USDMXN 19.5 al vencimiento: en el P&L D0→D1 `status_to: vencida`, `pv_to: 0`, `settled: 500000.0` (=1e6×(19.5−19.0)); fuera de escenarios en AUD-D1. Opciones vencidas sin ejercicio: PV 0 y `expired_unexercised`; swaption/cap/bono vencidos: aviso `no_settlement`. |
| R9 | CUMPLE | Prueba propia con el código del corte 1 (`git archive 35afa48 desk/api`): base v1 sembrada, PV con el código viejo, después `create_app` nuevo dos veces sobre la copia: 7/7 operaciones con los mismos id, una `execution` cada una, `pv_mxn` diferencia relativa `0` en todas (el `pv` de las filas FX cambia a MXN por D6, a propósito); sin duplicados al arrancar dos veces. |
| R10 | CUMPLE | Filas `fx_forward`/`fx_option` de `/api/portfolio/valuation?snapshot=MX-DEMO` vs `POST /api/price/<producto>` con los mismos términos: diferencia relativa `0.0` en las 5 filas; `pv` y `pv_mxn` en MXN. |
| R11 | CUMPLE | Chrome headless propio a 1280×800 sobre el build actual: `/mercado`, `/pricers/irs`, `/portafolio`, P&L, `/portafolio/1`, `/portafolio/2`, `/riesgo`, `/metodologia` con `documentElement.scrollWidth = 1280` y 0 elementos que salgan de 1280 (también con etiquetas largas de snapshots rodados). Visto: fecha en el selector (`… · 2026-12-08`), alta con fechas de pacto/inicio/vencimiento, ficha con línea de tiempo y calendario `Liquidado`/`Proyectado`, filtro por estado (Todas…Ejercida), terminar y cambiar nocional ejecutados desde la ficha (eventos creados por la API), vista P&L con total = suma, fijaciones con alta y CSV, botón «Rodar…». Vitest 159/159. |
| R12 | CUMPLE | `desk/ui/src/screens/MethodologyScreen.tsx` sección «Ciclo de vida y valuación a fecha»: eventos guardados vs derivados, fijación faltante, convención de días (días naturales, t=días/365, ACT/360, sin inhábiles), fuera de alcance, aproximaciones de bono/cap, P10, P2. |
| R13 | CUMPLE | Las cuatro suites pasan (tabla arriba). `MKT-LIVE` (insertado en la base temporal): `PUT` → 409; rodarlo → 201, `read_only: false`, etiqueta `«Mercado vivo (prueba auditor) · rodado al 2026-11-20»`; `PUT` al rodado → 200 y `MKT-LIVE` sigue con spot 18.6; id `MKT-LIVE` en el rodado → 400; id repetido → 409. MX-DEMO no cambia al editar su rodado. |

Aclaraciones verificadas además: P1 (`DELETE` → 409 «Una operación no se borra: termínala»), P2 (operación con `trade_date` futuro: `no_pactada`, PV 0, `pv_from = 0` en el P&L), P4 (swaption: `maturity_date` = expiración), P6 (`exercise` sobre `irs` → 400; ejercicio de `fx_option` el día del vencimiento → `ejercida` y transfer en `settled`), P7 (irs con vencimiento a 100 días → 4 periodos, fecha ajustada a 112 días), P8 (`terms_change` solo `strike`/`fixed_rate`), P11 (cap con `maturity_date` explícita ajustada a 4 periodos).

## Construido sin que un R lo pidiera

- `GET /api/trades/<id>/state?date=` y `GET /api/trades/<id>/flows?snapshot=` (soporte de R2 y de la ficha; razonables).
- Avisos `fx_fallback`, `no_settlement`, `expired_unexercised` con forma `{code,index,dates,message}` y fusión por `(code,index)`.
- Carga de CSV desde archivo («Archivo») además de pegar texto; filtro por estado incluye «No pactada».
- Marcador de avisos en filas del blotter/P&L; ids del blotter enlazan a la ficha.
- `OisSwap::parRate` reescrito sobre los flujos (necesario para el swap envejecido).
- `docs/superpowers/qf-desk/corte2/plan.md` y cambios a `corte2/design.md` comprometidos en el repo.

## Defectos encontrados

Ninguno de severidad alta o media.

Baja:
1. Bono y cap/floor envejecidos con `ceil` de periodos (`valuation.py:125-129`): dentro de un periodo el instrumento no envejece. El bono de 4 semestres vale lo mismo en D0 y en D0+40 (1,020,382.38): se valúa como 2.0 años en vez de 1.89, con los cupones corridos, no omitidos. Es la aproximación declarada en P3, pero Metodología dice «se omite el cupón en curso», y lo que pasa es que el calendario se recorre.
2. El blotter filtrado por estado deja el Total de todo el portafolio (`PortfolioScreen.tsx:284`, intencional) y con 0 filas muestra a la vez «Sin operaciones. Agrega una desde Pricers.» y «Ninguna operación con ese estado» aunque hay 13 operaciones.
3. Si la ficha se valúa en una fecha anterior a una terminación ya registrada, sigue ofreciendo «Terminar» y «Cambiar nocional», que siempre dan 409. También muestra cupones proyectados posteriores a la terminación (correcto a esa fecha, pero confunde).
4. Fijaciones en días naturales: con datos reales (solo días hábiles), todo swap envejecido llevará un aviso `missing_fixing` por cada fin de semana. El respaldo con la última publicada es correcto, pero el aviso será ruido permanente hasta el corte 3 (calendarios).
5. El encabezado del CSV debe ser exactamente `index,date,value` (`fixings.py:64`): un CSV de Excel con BOM se rechaza en la fila 1.
6. Test esqueleto saltado (`test_trades_dates.py:224`, conjunto de parámetros vacío): código muerto.
7. Formato `-0.00` en PV desde de swaps par (UI P&L).
8. `post_event` usa `max(...)` sobre los eventos (`events.py:149`): una operación sin eventos (solo posible si se corrompe la base) daría 500 en vez de un error controlado.
9. `CLAUDE.md` del repo dice «153 tests» de ctest; hoy son 402 (documentación desactualizada, fuera del corte).
