# QF Desk — Corte 2: la operación con vida y el mercado con historia

Repo `/home/claudio/Git/Quant_Finance`, rama `feat/qf-desk` (ya en `origin`; **no** hacer push ni merge durante el corte). Base: corte 1 y "mercado real" auditados (`docs/superpowers/qf-desk/design.md`, `roadmap.md` §2 principios y §Corte 2).

## Intención

Hoy una operación es un JSON con plazos en días que siempre se valúa "como recién pactada". Sin fechas ni historia no hay envejecimiento, ni P&L, ni base para la contabilidad de coberturas (corte 4). Este corte da a cada operación fechas fijas, una historia de eventos inmutables y una valuación a **fecha de valuación**, y permite comparar dos fechas (P&L). Se copia la forma del modelo de eventos de CDM, no el modelo completo.

## Decisiones de arquitectura

**D1 Datos (SQLite, `desk/api/db.py`).**
- `counterparties(id, name UNIQUE)`.
- `trades(id, product, counterparty_id, trade_date, start_date, maturity_date, terms JSON, created_at)`: identidad y términos económicos de origen. No se actualiza nunca tras crearse.
- `trade_events(id, trade_id, type, event_date, data JSON, prev_event_id, created_at)`: solo inserción; disparadores de SQLite abortan `UPDATE` y `DELETE`. Tipos válidos: `execution`, `reset`, `transfer`, `quantity_change`, `terms_change`, `exercise`, `termination`.
- `fixings(index_name, fixing_date, value, PRIMARY KEY(index_name, fixing_date))`. Índices: `TIIE-F`, `SOFR` (tasa a un día, decimal) y `USDMXN` (FIX).
- `snapshots`: se conserva; su `as_of` **es** la fecha de valuación. Se añade "rodar" un snapshot: copia con nuevo `as_of` y los mismos datos (`POST /api/market/<id>/roll {as_of, id}`), para tener mercado en varias fechas.

**D2 Estado derivado.** `state(trade, eventos, fecha)` es función pura (módulo `desk/api/lifecycle.py`): aplica los eventos con `event_date ≤ fecha` en orden y devuelve términos vigentes (nocional tras `quantity_change`, términos tras `terms_change`) y estado: `viva`, `vencida` (fecha ≥ vencimiento), `terminada`, `ejercida`. Nada guarda el estado; siempre se recalcula.

**D3 Qué es evento guardado y qué se deriva.** Se guardan los hechos no derivables: `execution` (al crear), `quantity_change`, `terms_change`, `exercise`, `termination` y el `transfer` de la liquidación de una terminación o ejercicio. Los cupones ya pagados de un swap y la liquidación al vencimiento de un forward FX **se derivan** de términos + fijaciones (función `settled_flows(trade, d0, d1)`), no se guardan como eventos. `reset` queda en el catálogo pero las fijaciones viven en `fixings`. Esto se declara en Metodología.

**D4 Valuación a fecha.** Toda valuación recibe la fecha de valuación (el `as_of` del snapshot elegido) y usa el estado a esa fecha. Tiempos restantes = (fecha de flujo − fecha de valuación) con la misma convención de días del corte 1. Solo se descuentan flujos con fecha de pago > fecha de valuación.
- **Swap OIS envejecido, en C++:** `OisSwap` acepta un calendario con el periodo en curso ya iniciado: tiempo (negativo) desde el inicio del periodo en curso y el **factor de capitalización acumulado** de ese periodo hasta la fecha de valuación; el cupón flotante del periodo en curso es `N × (factor_acumulado × DF(hoy)/DF(fin) − 1)`. Una función C++ `compoundOvernight(tasas, días, base)` compone las fijaciones diarias (ACT/360). Ambas se exponen en `qfpy`. Python solo reúne fijaciones y fechas. El constructor actual sigue funcionando igual (retrocompatible).
- **Fijación faltante:** si falta una fijación ya debida del periodo en curso, se usa la última publicada anterior (o, si no hay ninguna, la tasa a un día de la curva) y la respuesta lleva `warnings` con el índice y las fechas faltantes. No es error.
- **Demás productos** (forward y opción FX, cap/floor, swaption, bono, opción de acción): envejecen acortando el plazo restante; en `vencida`, `terminada` o `ejercida` su PV es 0 y salen de riesgo. Bono: solo cupones futuros.

**D5 P&L entre dos fechas.** `GET /api/pnl?from=<snapshot>&to=<snapshot>` devuelve por operación `pv_from`, `pv_to`, `settled` (flujos liquidados en `(from, to]`, en MXN al FIX de su fecha o, si falta, al spot del snapshot `to` con aviso) y `pnl = pv_to − pv_from + settled`, más el total. Todo en MXN.

**D6 Deuda del corte 1 incluida.** El `pv` de las filas FX en `/api/portfolio/value` pasa a MXN, igual que `/api/price`.

**D7 Interfaz.** El selector global muestra la fecha de valuación de cada snapshot. Alta de operación con fechas (pacto, inicio, vencimiento; el plazo en días sigue aceptándose y se convierte). Ficha de operación: línea de tiempo de eventos y calendario de flujos (liquidados / proyectados). Blotter con filtro por estado. Acciones: terminar anticipadamente, cambiar nocional. Portafolio: vista de P&L entre dos snapshots. Mercado: fijaciones (tabla, alta manual, carga CSV `index,date,value`) y botón "rodar".

**D8 Migración.** Al arrancar con una base del corte 1, las operaciones se convierten: `trade_date = start_date =` `as_of` del snapshot `MX-DEMO`, `maturity_date = start_date + plazo`, y un evento `execution`. Idempotente.

## Requisitos

- **R1** Crear una operación (`POST /api/trades`) guarda fechas de pacto, inicio y vencimiento e inserta un evento `execution`. `UPDATE` y `DELETE` sobre `trade_events` fallan por disparador (test que lo intenta por SQL directo). Tipo de evento fuera del catálogo → 400.
- **R2** Replay: para toda operación (semilla + las creadas en tests con cambios de nocional y terminación), `state()` recalculado desde cero coincide con lo que devuelve la API; el orden de inserción de eventos de la misma fecha no cambia el resultado salvo por `id`.
- **R3** Envejecimiento del OIS (test en C++ y en Python): swap a la par pactado en D0; en D0+28 días, con fijaciones diarias iguales a los forwards a un día de la curva de D0 y la curva de D0 desplazada 28 días, su PV coincide con el valor forward en D0 capitalizado, tolerancia `1e-6 × nocional`. Además, con el constructor nuevo y periodo sin iniciar, `npv` es idéntico al constructor actual (1e-12 relativo).
- **R4** Identidad de P&L: para toda operación de la semilla y dos snapshots D0 < D1, `pnl == pv_to − pv_from + settled` (1e-6 MXN) y la suma por operación es el total. Un swap que paga cupón entre D0 y D1 muestra `settled ≠ 0` y su P&L con fijaciones = forwards y curva desplazada es ≈ 0 (1e-6 × nocional).
- **R5** Terminación anticipada (`POST /api/trades/<id>/events` tipo `termination` con importe): inserta `termination` y `transfer`, el estado pasa a `terminada`, y desde esa fecha la operación tiene PV 0 y no aparece en DV01, escenarios ni VaR; en una fecha anterior sigue valuando igual que antes. Evento sobre operación ya terminada → 409.
- **R6** Cambio de nocional (`quantity_change`): desde su fecha el PV escala con el nuevo nocional; antes de su fecha no cambia.
- **R7** Fijaciones: alta manual y por CSV (`POST /api/fixings`, `POST /api/fixings/csv`), listado filtrable; duplicado exacto es idempotente, valor distinto para la misma clave → 409; valores no finitos o fuera de [−1, 10] (tasas) → 400. Un swap con fijación debida faltante devuelve 200 con `warnings` no vacío.
- **R8** Vencimiento: una operación valuada en fecha ≥ vencimiento tiene estado `vencida`, PV 0 y queda fuera de riesgo. Un forward FX vencido entre D0 y D1 aporta su liquidación a `settled` usando el FIX `USDMXN` de su vencimiento.
- **R9** Migración: una base del corte 1 (fixture) arranca sin perder operaciones; cada una tiene `execution`; su PV con `MX-DEMO` no cambia (1e-8 relativo) respecto al valor previo; arrancar dos veces no duplica nada.
- **R10** `pv` de filas FX en `/api/portfolio/value` en MXN e igual al de `/api/price` para los mismos términos (1e-8 relativo).
- **R11** Interfaz (comprobable con capturas y tests de vitest): fecha de valuación visible en el selector; alta con fechas; ficha con línea de tiempo y calendario de flujos que distingue liquidados de proyectados; filtro por estado; terminar y cambiar nocional desde la ficha; vista de P&L con total que cuadra con la suma; pantalla de fijaciones con alta y CSV; "rodar" snapshot. Sin desbordes horizontales a 1280 px.
- **R12** Metodología declara: qué se guarda como evento y qué se deriva, la regla de fijación faltante, la convención de días, y lo que este corte no hace.
- **R13** Sin regresión: `ctest`, pytest de bindings, pytest de `desk/api` y vitest pasan; `MKT-LIVE` sigue de solo lectura (rodar crea otro snapshot editable, rotulado con la procedencia del original).

## Fuera de alcance (se declara)

Novaciones, asignaciones, compensación; calendarios de días inhábiles y ajuste de fechas (corte 3); ejercicio automático de opciones (el `exercise` es manual, con importe); liquidación derivada de caps/floors, swaptions y bonos vencidos (salen con PV 0 y aviso); historia automática de snapshots diarios; división del paquete de la interfaz y textos de tablas compartidos (deuda que se queda); usuarios y aprobación (corte 8).

## Restricciones

- Matemática en C++ vía `qfpy`; Python orquesta. Python 3.8 (`/home/claudio/anaconda3/bin/python`), sin dependencias nuevas en backend ni interfaz.
- Guardia central de no finitos y cotas de magnitud del corte 1 aplican a todo cuerpo nuevo; fechas ISO válidas, `trade_date ≤ start_date < maturity_date`.
- Tareas C++ en serie (comparten `build/`); contratos (rutas y formas de datos) en la primera tarea; una tarea final de integración contra el backend real.
- Commits por tarea con rutas explícitas (`git commit -- <rutas>`), `GRAPHIFY_SKIP_HOOK=1`, autor Claudio, sin `Co-Authored-By`, sin `git stash`, sin push.
- No tocar `~/Git/MarketDataFeed`. Puerto 5070 en uso por el desk: los agentes usan puertos propios.
