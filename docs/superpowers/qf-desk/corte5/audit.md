# Auditoría independiente — QF Desk corte 5 (operaciones)

Rama `corte5`, commits `ce51edf..6438dd8` (13 commits). Contrastado contra `design.md`. Sin leer `plan.md` ni reportes.
Método: backend real en :5095 con BD temporal nueva (siembra demo + 30 operaciones creadas para la auditoría), scripts HTTP propios; los PV "del banco" se calcularon en proceso con `valuation.value_trade` y `MarketContext.shifted` / otra `as_of` (no con `ops_recon`). Interfaz: `npm run build` actual servida por el backend, Chrome headless propio en :9355 a 1280 px, `Emulation.setEmulatedMedia(print)` y `printToPDF`. Todo apagado al final; árbol de trabajo limpio.

## Veredictos

| R | Veredicto | Evidencia |
|---|---|---|
| R1 | CUMPLE | 8 operaciones `irs`/`bond` vivas (TIIE-F, SOFR, arranque futuro, bono con cupón pasado, swap iniciado en junio): Σ proyectado×df − PV = **0.0** exacto en todas (tolerancia 1e-6×nocional). Filtros rango 2027-01-01..06-30 (35/35 filas), contraparte (19/19), moneda USD (8/8): filas idénticas al subconjunto esperado. Totales general, por fecha, contraparte y moneda cuadran (montos y conteos) en las 4 consultas. CSV: 19 filas = JSON, mismas fechas/ids/estados/montos. |
| R2 | CUMPLE | `POST /api/trades/8/settlements` 201; evento `transfer` con `data.kind=settlement_confirmed`, `computed_amount`. Duplicado → 409; fecha sin flujo (2026-07-15) → 409; fecha futura → 409; monto no numérico → 400. ΔPV máx = **0.0**, ΔP&L (MX-DEMO→AUD-D1) máx = **0.0** (≤1e-12). Calendario: fila `status=confirmed`, `confirmed_amount` y `difference=123.45`. `/flows` de la operación sin cambios. |
| R3 | CUMPLE | `GET …/confirmation` 200 para los 7 productos (irs, fx_forward, fx_option, cap_floor, bond, swaption, equity_option) con `parties`, `dates`, `terms`, `conventions` (base de días, periodicidad, índice, composición donde aplica), `schedule` y `notices` (incl. "no sustituye la confirmación ISDA"). Tras `PUT /api/settings {company_name:"Otra Empresa SAB"}` la confirmación lo trae. Ver defecto D2 sobre el monto del calendario del irs. |
| R4 | CUMPLE | 11 variantes (4 irs: payer/receiver, TIIE-F/SOFR, arranque futuro, tasa 1e-05; 3 fx_forward: buy/sell, plazos 21–365 d, trade_date distinto; 4 fx_option: call/put × buy/sell): exportar→importar da mismos producto, contraparte, fechas y `params` idénticos; PV relativo **0.0**. Negativos → 400 y conteo de operaciones 37→37: XML mal formado, DOCTYPE con entidad externa (XXE), billion-laughs, DTD externo en documento válido, `swaption`/`bondOption` no soportados, cuerpo vacío, JSON, NaN, nocional negativo, UTF-16, namespace ajeno. Exportar `cap_floor` → 400. |
| R5 | CUMPLE | Contraparte con irs fuera de mercado (9.5 %), irs a la par y forward FX. (a) PV exacto → 3/3 `conciliada` (también en USD). (b) +5 pb → `explicable`, estimado **5.0000004 / 5.0000004 pb**; −5 pb → −4.9999994. (c) PV al 2026-11-11 → `date.attributed=true` en las 3 (con tolerancia por omisión el irs queda `conciliada` porque la diferencia de 1 día < 0.01 % del nocional; con tolerancia 0 → `explicable`). (d) nocional ×1.5 → irs off-market `revisar` + `terms_flag` (−132 pb), forward `revisar` + `terms_flag` (−4.25 %); el irs a la par (PV≈0) sale `conciliada` — límite inherente: ×1.5 de 0 es 0. (e) id 9999 → `bank_only` "Operación inexistente", operaciones omitidas → `own_only`. Corridas guardadas y listadas; CSV exportable con secciones. `UPDATE`/`DELETE` sobre `reconciliations` y `reconciliation_rows` → abortan por trigger. CSV inválido (sin columna, PV no numérico, NaN, id repetido, moneda EUR), contraparte inexistente y tolerancia negativa → 4xx sin crear corrida. |
| R6 | CUMPLE (con observación) | Nav "Operaciones"; pestañas Flujos (filtros desde/hasta/contraparte/moneda, Exportar CSV, "Confirmar liquidación" en liquidados) y Conciliación (contraparte, tolerancia, subir archivo o pegar CSV, resultados con estado y descomposición, historial, Exportar CSV). Ficha: Confirmación, Descargar FpML (solo en productos FpML), referencia del banco con Editar. Portafolio: "Importar FpML". A 1280 px `scrollWidth=clientWidth=1280` y ningún elemento pasa de 1281 px en Flujos, Conciliación, ficha, confirmación, portafolio y metodología. En `@media print` `.shell__sidebar` `display:none`, sin botones; PDF generado. Textos en español salvo el control nativo de archivo ("Choose File / No file chosen", depende del idioma del navegador). El snapshot de la conciliación se elige con el selector global, no dentro de la pestaña. |
| R7 | CUMPLE | `opsMethodology.ts` añade sección "Operaciones" en Metodología: calendario, liquidación confirmada, confirmación, FpML (sin XSD, sin DTD, índices por verificar), conciliación (umbrales), descomposición indicativa "no una prueba", fuera de alcance. |
| R8 | CUMPLE | pytest 2613 passed; vitest 26 archivos / 340 tests passed; `npm run build` OK (aviso de chunk >500 kB ya existente). Sin árbol de CMake en el worktree (solo `build/src/qfpy*.so`): ctest y `pytests` de CMake omitidos. |

## Construido sin que ningún R lo pidiera

- Regla "explicable" también por spot ±1 % en FX (D5 solo nombra curva ±10 pb y fecha).
- Confirmación de liquidación también por `POST /api/trades/<id>/events` con `type=transfer, data.kind=settlement_confirmed` (ruta paralela a `/settlements`).
- `snapshot` opcional en `/settlements` (toma el de mayor `as_of`) y 409 si la moneda no es la del flujo.
- `GET/PUT /api/trades/<id>/ref`, `GET /api/settings` (soporte de D5/D6, razonable).
- Edición del nombre de la empresa dentro de la pantalla de confirmación.
- En conciliación, operación de otra contraparte → `bank_only` con motivo propio; límite de 5000 filas; aviso `party_assumed` en importación FpML.
- Cambios en `events.py` (archivo compartido no listado en las restricciones), delimitados con `corte 5`.

## Defectos fuera de los R

| Sev. | Defecto |
|---|---|
| media | **Importar FpML altera la fecha de vencimiento en silencio**: un swap con `terminationDate` 2028-11-10 (no múltiplo de 28 d) se importa con vencimiento 2028-11-07 y `warnings: []`. El módulo dice que "rechaza lo que no puede representar fielmente"; debería rechazar o avisar. |
| media | **Calendario de la confirmación de un `irs` muestra solo la pierna fija** con el concepto "Cupón n: pierna fija contra pierna variable" (−544,444.44 en cada periodo, incluso en el cupón ya liquidado cuyo neto fue +1,385.98). El documento no aclara que es solo la pierna fija; puede confundirse con el neto a cotejar con el banco. |
| baja | Las confirmaciones de liquidación se encadenan en `prev_event_id` del ciclo de vida (una terminación posterior apunta a la confirmación, cuya fecha es anterior); hoy no rompe valuación ni P&L, pero mezcla eventos de registro con la cadena de ciclo de vida. |
| baja | Control de archivo nativo en inglés ("Choose File / No file chosen") en Conciliación (y probablemente en Importar FpML). |
| baja | En Flujos, el aviso de fijaciones faltantes lista los 117 días uno por uno, ocupando un bloque grande sobre la tabla. |
| baja | La bandera de términos no detecta un nocional distinto en una operación cercana a la par (PV≈0): limitación del método, no declarada en Metodología. |

## Segunda ronda

Commits nuevos `49837d3..90c6181` (6 commits sobre `6438dd8`), 17 archivos. La primera ronda no tuvo ningún NO CUMPLE; se verificaron los 2 defectos medios y, además, los 4 bajos. Método: cliente de prueba Flask en proceso con BD temporal nueva, más backend real en :5095 y Chrome headless propio en :9355 (`--lang=en-US`, a propósito, para probar el selector de archivo). Todo apagado al final; árbol de trabajo limpio.

### Defectos de la primera ronda

| Sev. | Defecto | Estado | Evidencia |
|---|---|---|---|
| media | FpML movía el vencimiento en silencio | CORREGIDO | `fpml._swap_body` rechaza si `(end-start) % period_days != 0`. Probado con los 3 irs sembrados (2 TIIE-F, 1 SOFR): ida y vuelta 201; con `terminationDate` +3 días da 400 y nombra la fecha más cercana ("2028-11-10 no cae en periodos enteros de 28 días … fecha más cercana: 2028-11-07"; SOFR con 365 días, igual). `terminationDate == effectiveDate` → 400 `maturity_date`. Metodología lo documenta. |
| media | Calendario de la confirmación del irs parecía el neto | CORREGIDO | El concepto ahora dice "Cupón 1: solo pierna fija (el neto a liquidar depende de la pierna variable)"; avisos de la confirmación y Metodología (Confirmación) lo explican. |
| baja | Confirmaciones en la cadena `prev_event_id` | CORREGIDO | `events.insert_event` salta las confirmaciones al elegir `prev`. En vivo (irs id 8 con arranque 2026-06-01): ejecución 8 ← confirmaciones 9 y 10 (prev=8) ← terminación 11 (prev=8) ← transfer 12 (prev=11). Prueba nueva en `test_ops_settlements.py`. La regla cronológica sigue cubierta por su prueba. |
| baja | Control de archivo nativo en inglés | CORREGIDO | `FilePicker` propio: con Chrome en inglés, Conciliación e Importar FpML muestran "Elegir archivo / Ningún archivo seleccionado"; el input nativo queda 1×1 px, opacidad 0, con `aria-label`. |
| baja | Aviso de fijaciones con 117 días | CORREGIDO | En vivo: "… (2026-06-01, …, 2026-06-05 … y 111 más)", lista completa en `title`. |
| baja | Bandera de términos ciega cerca de la par | CORREGIDO (documentado) | Metodología (Descomposición indicativa) lo declara; es limitación del método, no se cambió el cálculo. |

### Regresiones

Ninguna encontrada. fx_forward ×2 y fx_option exportar→importar 201; `/api/cashflows?snapshot=MX-DEMO` 200 (JSON y CSV); `/api/reconciliations` 200; a 1280 px `scrollWidth=clientWidth=1280` en Conciliación, Portafolio (con el diálogo de FpML) y Flujos. El cambio de `events.py` es interno a `insert_event` (ningún otro módulo lee `prev_event_id`).

### Veredictos

R1–R8 se mantienen en CUMPLE. R6 pierde la observación del control en inglés; queda solo la del snapshot de la conciliación, que se elige con el selector global.

### Suites

- CMake/ctest y `pytests`: omitidas, el worktree no tiene árbol de CMake (solo `build/src/qfpy*.so`).
- `pytest desk/api/tests -q`: **2616 passed** (antes 2613).
- `npm test`: **27 archivos / 348 tests passed** (antes 26 / 340).
- `npm run build`: OK (mismo aviso de chunk >500 kB que ya existía).

### Defectos nuevos

| Sev. | Defecto |
|---|---|
| baja | `insert_event` ahora recorre todos los eventos de la operación y parsea el JSON de cada `transfer` en cada alta (antes era un `MAX(id)`). Es correcto y con pocos eventos no se nota, pero crece con el número de confirmaciones. |
