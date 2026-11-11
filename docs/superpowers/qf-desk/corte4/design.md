# QF Desk — Corte 4: contabilidad de coberturas IFRS 9

Repo `/home/claudio/Git/Quant_Finance`, rama `feat/qf-desk`. Base: cortes 1 y 2 auditados (`docs/superpowers/qf-desk/design.md`, `corte2/design.md`, `corte2/plan.md` § Contexto con las firmas reales, `roadmap.md` §2 principios y §Corte 4). Claudio delegó todas las decisiones en Fable: no hay visto bueno intermedio.

## Intención

La contabilidad de coberturas es la función por la que una tesorería corporativa paga y la que la hoja de cálculo hace peor. Este corte permite designar una operación del portafolio como instrumento de cobertura de una partida (un crédito a tasa variable o un flujo pronosticado en USD), medir su efectividad, cerrar periodos y obtener los asientos **sugeridos** y un reporte por relación. El sistema no es el libro mayor y no sustituye al contador: eso se declara en pantalla y en el reporte.

## Decisiones de arquitectura

**D1 Datos (SQLite, `desk/api/db.py`).**
- `hedge_relationships(id, trade_id, fraction, hedge_type, item_kind, item_terms JSON, hedge_ratio, designation_date, designation_snapshot, documentation JSON, created_at)`. No se actualiza tras crearse.
- `hedge_events(id, relationship_id, type, event_date, data JSON, created_at)`: solo inserción (disparadores, como `trade_events`). Tipos: `designation`, `period_close`, `dedesignation`.
- `hedge_periods(id, relationship_id, snapshot_id, as_of, result JSON, created_at)`: solo inserción; un cierre por fecha, en orden cronológico estricto. `result` guarda todas las cifras y los asientos del periodo (principio 3: toda cifra se puede explicar).

**D2 Tipos.** `hedge_type`: `cash_flow` o `fair_value`. `item_kind`:
- `floating_loan`: crédito o deuda a tasa variable (`index` TIIE-F o SOFR, `notional`, `start_date`, `maturity_date`, `side`: `pays_floating` si la empresa paga la variable, `receives_floating` si la cobra). Instrumento admitido: `irs` sobre el mismo índice.
- `forecast_fx`: compra o venta pronosticada en USD (`amount_usd`, `date`, `side`: `buy_usd` o `sell_usd`). Instrumento admitido: `fx_forward`.
Otras combinaciones → 400. `fraction` ∈ (0, 1] es la proporción de la operación designada; `hedge_ratio` > 0 es unidades de instrumento por unidad de partida (1 por omisión).

**D3 Derivado hipotético.** La partida cubierta se representa con un derivado hipotético valuado con el mismo motor (`valuation.value_trade` sobre una operación sintética en memoria, nunca guardada en `trades`):
- `floating_loan`: un `irs` con el nocional, fechas e índice del crédito, del lado que compensa el riesgo (paga fija si la empresa `pays_floating`), con tasa fija = tasa par al snapshot de designación (vale 0 al designar).
- `forecast_fx`: un `fx_forward` por `amount_usd` a `date`, compra si `buy_usd`, con strike = forward al snapshot de designación (vale 0 al designar).
El hipotético tiene el mismo signo económico que un instrumento perfecto; así "instrumento idéntico al hipotético" da inefectividad cero.

**D4 Medición por periodo (cierre con un snapshot, `POST /api/hedges/<id>/periods {snapshot}`).** Todo en MXN. Sea `F` la fracción.
- `inst_cum = F × (PV_inst(t) − PV_inst(designación))`, `hypo_cum = PV_hypo(t) − PV_hypo(designación)` (valores limpios de lo ya liquidado: el PV solo contiene flujos futuros).
- `settled_period = F ×` flujos liquidados del instrumento en `(cierre anterior o designación, t]` (de `settlement.settled_flows`).
- **Flujo de efectivo:** saldo de la reserva `oci(t) = signo(inst_cum) × min(|inst_cum|, |hypo_cum|)` si ambos tienen el mismo signo, y 0 si no. `Δoci = oci(t) − oci(t−1)`. Inefectividad del periodo a resultados `= (inst_cum(t) − inst_cum(t−1)) − Δoci`. **Reciclaje:** `settled_period` se reconoce en resultados (es el flujo cubierto que ocurrió: el cupón neto del swap o la liquidación del forward); al vencer el instrumento su PV es 0, de modo que la reserva queda en 0 y todo lo acumulado ya pasó por resultados vía liquidaciones.
- **Valor razonable:** el cambio del instrumento del periodo va a resultados y el cambio del hipotético del periodo, con signo contrario, ajusta el valor en libros de la partida contra resultados; la inefectividad es la suma neta. No hay reserva.
- Identidad de control (se guarda y se prueba): `Δinst_cum + settled_period = Δoci + inefectividad + reciclaje` (flujo de efectivo) — es decir, el P&L del instrumento del periodo (el mismo de `/api/pnl` × F) se reparte completo entre otro resultado integral y resultados.

**D5 Asientos sugeridos.** Cada cierre produce asientos con cuentas fijas: `Derivado (valor razonable)`, `ORI — reserva de cobertura`, `Resultados — inefectividad de cobertura`, `Resultados — partida cubierta (reciclaje)`, `Efectivo`, `Partida cubierta — ajuste de valor razonable`. Cada asiento: `{account, debit, credit, memo}` en MXN, redondeado a centavos con el residuo de redondeo absorbido en resultados de modo que cargos = abonos exacto.

**D6 Efectividad prospectiva (`GET /api/hedges/<id>/effectiveness?snapshot=`).** (a) Coincidencia de términos críticos: nocional (× razón × fracción), índice o moneda, fechas de inicio y vencimiento, cada uno `match`/`mismatch` con ambos valores. (b) Análisis de escenarios: bajo los escenarios del corte 1 (`risk/scenarios.py`), razón `ΔPV_inst × F / ΔPV_hypo` por escenario. Conclusión `relación económica: sí` si todas las razones son positivas; se informa además cuántas caen en 0.8–1.25 **solo como referencia** (IFRS 9 no fija umbral; se declara).

**D7 Desdesignación (`POST /api/hedges/<id>/dedesignate {date, reason}`).** Inserta el evento, exige que la fecha no sea anterior al último cierre, y desde entonces no admite más cierres (409). El saldo de la reserva queda congelado y visible en el reporte con la nota de que se recicla cuando ocurra el flujo cubierto. Si la operación deja de estar `viva` a la fecha de un cierre (terminada, ejercida), el cierre se rechaza con 409 pidiendo desdesignar; si está `vencida`, el cierre se permite (es el cierre final, con PV 0).

**D8 Reporte (`GET /api/hedges/<id>/report`, y `?format=csv` para los asientos).** Documentación de designación (objetivo de gestión de riesgo, riesgo cubierto, partida, instrumento, razón, método de efectividad, fuentes de inefectividad), prueba prospectiva, tabla de periodos, asientos por periodo y acumulados, nivel de jerarquía de valor razonable (**Nivel 2** para todos los instrumentos del desk: insumos observables; con la procedencia `synthetic/mixed/live` del snapshot usado) y el aviso de revisión contable. La interfaz ofrece vista imprimible.

**D9 Interfaz.** Pantalla nueva **Coberturas** en la navegación: lista de relaciones (estado `activa` / `desdesignada`, tipo, operación, saldo de reserva), alta con formulario (operación del portafolio, tipo, partida y sus términos, fracción, razón, documentación), detalle con términos críticos, escenarios, periodos, asientos, "Cerrar periodo" (elige snapshot), "Desdesignar", exportar CSV e imprimir. La ficha de operación muestra si está designada.

**D10 Revisión contable.** La hoja de ruta exige revisión por un contador IFRS 9 y nadie puede hacerla en este corte. Se declara de forma visible: banda permanente en la pantalla y en el reporte ("Asientos sugeridos. Metodología pendiente de revisión por un contador con experiencia en IFRS 9") y sección en Metodología con las simplificaciones.

## Requisitos

- **R1** Alta (`POST /api/hedges`): guarda la relación y un evento `designation`; valida combinaciones de D2, `fraction`, `hedge_ratio`, fechas ISO, operación existente y `viva` a la fecha de designación, y que la suma de fracciones activas de una operación no pase de 1 (409). `UPDATE`/`DELETE` sobre `hedge_events` y `hedge_periods` fallan por disparador.
- **R2** Hipotético idéntico: una relación cuyo instrumento tiene los mismos términos que el hipotético (swap pactado a la par en la designación con nocional, índice y fechas del crédito; forward al forward de mercado por el monto y fecha del flujo) tiene, en todo cierre, inefectividad 0 y `Δoci = Δinst_cum` (1e-6 × nocional).
- **R3** Menor de los dos: caso sobrecubierto (nocional del instrumento 120 % del crédito): `|oci| = |hypo_cum|` y el exceso va a resultados; caso subcubierto (80 %): `|oci| = |inst_cum|` e inefectividad 0. Con signos opuestos, `oci = 0`.
- **R4** Los asientos de cada periodo cuadran exacto (cargos = abonos al centavo) y también el acumulado; la identidad de control de D4 se cumple (1e-6 MXN) y `Δinst_cum + settled_period` coincide con `F ×` el `pnl` de `/api/pnl` para esa operación y ese par de snapshots.
- **R5** Reciclaje: en un periodo donde el swap liquida un cupón, el asiento incluye `Efectivo` contra `Resultados — partida cubierta (reciclaje)` por ese importe; en el cierre al vencimiento de un forward designado, la reserva queda en 0 y el acumulado en resultados es igual a la liquidación total.
- **R6** Valor razonable: el periodo registra el cambio del instrumento y el ajuste de la partida; con hipotético idéntico el neto en resultados es 0.
- **R7** Efectividad prospectiva: términos críticos con `match`/`mismatch` correctos (test con un vencimiento distinto) y razones por escenario; con hipotético idéntico todas las razones son 1 (1e-6).
- **R8** Desdesignar genera el evento, congela el saldo y bloquea nuevos cierres (409); cerrar con un snapshot no posterior al último cierre → 409; cerrar con la operación terminada → 409.
- **R9** Reporte: contiene todas las secciones de D8; el CSV de asientos suma cargos = abonos; el nivel de jerarquía y la procedencia del snapshot aparecen.
- **R10** Interfaz: pantalla Coberturas con lista, alta, detalle, cierre de periodo, desdesignación, exportación y vista imprimible; la banda de D10 siempre visible; la ficha de operación indica la designación. Sin desbordes a 1280 px; textos en español.
- **R11** Metodología declara: el derivado hipotético, la regla del menor, el reciclaje por liquidaciones, que los asientos son sugeridos, las simplificaciones (sin costo de cobertura ni valor temporal de opciones, sin riesgo de crédito en la medición, sin ajuste de base para partidas no financieras, sin reequilibrio de la razón) y la revisión contable pendiente.
- **R12** Sin regresión: las cuatro suites pasan.

## Fuera de alcance (se declara)

Opciones como instrumento de cobertura y su valor temporal; costo de cobertura (base de divisa); coberturas de inversión neta; reequilibrio; ajuste de base; riesgo de crédito (CVA/DVA) en la efectividad; designación de componentes de riesgo; libro mayor y pólizas reales; revelaciones de IFRS 7.

## Restricciones

- Las del corte 2 (`corte2/plan.md` § Contexto): Python 3.8 de anaconda, sin dependencias nuevas, guardia de no finitos, validación en la frontera, commits por tarea con rutas explícitas, `GRAPHIFY_SKIP_HOOK=1`, autor Claudio sin `Co-Authored-By`, sin `git stash`, sin push durante el corte.
- No hay C++ nuevo: todo se valúa con el motor existente (`valuation.value_trade`, `settlement.settled_flows`, `pricing`).
- Contratos (rutas y formas de datos) fijados antes de repartir; backend e interfaz en paralelo; tarea final de integración contra el backend real con capturas.
