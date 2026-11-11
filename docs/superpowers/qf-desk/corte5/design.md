# QF Desk — Corte 5: operaciones (flujos, confirmaciones, FpML, conciliación)

Repo `/home/claudio/Git/Quant_Finance`. Este corte se trabaja en un worktree propio (rama `corte5`, creada desde `feat/qf-desk`); se fusiona al final. Base: cortes 1, 2 y 4 (`docs/superpowers/qf-desk/`, firmas reales en `corte2/plan.md` y `corte4/plan.md` § Contexto). Claudio delegó todas las decisiones en Fable.

## Intención

Cerrar el "back office": saber qué se paga y se cobra y cuándo, confirmar cada operación con un documento, intercambiar operaciones en el estándar FpML y, sobre todo, **conciliar la valuación propia contra la del banco** explicando la diferencia. La conciliación es la función con mejor demostración comercial.

## Decisiones de arquitectura

- **D1 Calendario de flujos del portafolio** (`GET /api/cashflows?snapshot=&from=&to=&counterparty=&currency=`): une, para todas las operaciones vivas o con flujos en la ventana, los flujos liquidados y proyectados que ya produce `settlement.py` (`trade_flows`/`settled_flows`); cada fila: fecha, operación, contraparte, producto, tipo, estado (liquidado/proyectado), moneda, monto (signo: positivo = se cobra) y monto en MXN; totales por fecha, contraparte y moneda. `?format=csv` exporta. No hay tabla nueva.
- **D2 Marcar liquidado** (`POST /api/trades/<id>/settlements {date, amount, currency}`): registra que un flujo derivado se pagó de verdad insertando un evento `transfer` con `data.kind = "settlement_confirmed"`, la fecha y el monto real; se añade `transfer` con ese `kind` como único `transfer` permitido por la API. El calendario muestra "confirmado" y la diferencia entre el monto calculado y el confirmado. No cambia valuación ni P&L (el flujo derivado sigue mandando; la diferencia se reporta). Duplicado (misma operación y fecha) → 409.
- **D3 Confirmación** (`GET /api/trades/<id>/confirmation`): JSON con partes (la empresa: nombre configurable en `settings`, tabla clave-valor nueva; la contraparte), fechas, términos económicos completos con sus convenciones (base de días, periodicidad, índice, composición), calendario de pagos previsto y avisos legales fijos ("documento informativo; no sustituye la confirmación ISDA"). Vista imprimible en la interfaz (`/portafolio/:id/confirmacion`, con `@media print`).
- **D4 FpML** (`desk/api/fpml.py`, solo `xml.etree.ElementTree`): exportar (`GET /api/trades/<id>/fpml`) e importar (`POST /api/trades/fpml`, cuerpo XML) para `irs` (swap OIS), `fx_forward` (`fxSingleLeg`) y `fx_option` (`fxOption`), FpML 5.x vista de confirmación, con el subconjunto de elementos necesario para ida y vuelta. Importar valida estructura y valores con las mismas reglas que el alta; XML mal formado o producto no soportado → 400 con mensaje claro; se desactiva la resolución de entidades (sin DTD externos). No se valida contra el esquema XSD oficial (no hay dependencia); se declara.
- **D5 Conciliación con el banco.** `POST /api/reconciliations {snapshot, counterparty, csv}` con CSV `trade_id,bank_pv,currency[,bank_ref]` (o `bank_ref` contra una referencia externa guardada en la operación: `trades` no se toca; la referencia vive en `settings`-like tabla `trade_refs(trade_id, ref)`), guarda la corrida (`reconciliations`, `reconciliation_rows`, solo inserción) y devuelve por operación: PV propio (MXN), PV del banco convertido a MXN al spot del snapshot, diferencia, diferencia relativa al nocional, y una **descomposición indicativa** de la diferencia:
  - *fecha*: cuánto cambia el PV propio valuando un día hábil antes y uno después (si la diferencia cae dentro de ese rango, se atribuye a fecha de valuación);
  - *curva*: desplazamiento paralelo de la curva del producto (en pb) que iguala el PV propio al del banco (resuelto con el DV01 y una iteración de Newton sobre la valuación real);
  - *tipo de cambio*: para productos FX, el spot que iguala;
  - *términos*: bandera si el nocional o el vencimiento implícitos no cuadran (la diferencia supera lo explicable por ±25 pb o ±2 % de spot).
  Estados por fila: `conciliada` (|dif| ≤ tolerancia: por omisión 0.01 % del nocional, configurable en la petición), `explicable` (curva dentro de ±10 pb o fecha), `revisar`. Operaciones del banco que no existen, y operaciones propias que el banco no trae, se listan aparte. Exportable a CSV. La descomposición es una ayuda de diagnóstico, no una prueba; se declara.
- **D6 Interfaz.** Pantalla nueva **Operaciones** en la navegación con pestañas: *Flujos* (tabla filtrable por rango, contraparte y moneda; totales; exportar; "confirmar liquidación" en flujos pasados), *Conciliación* (elegir contraparte y snapshot, pegar o subir CSV, tabla de resultados con estados y descomposición, historial de corridas, exportar). En la ficha de operación: enlaces a Confirmación (vista imprimible), "Descargar FpML" y referencia del banco editable. En Portafolio: "Importar FpML".
- **D7 Metodología:** qué es cada cosa, límites de FpML, carácter indicativo de la descomposición.

## Requisitos

- **R1** `/api/cashflows`: la suma de montos proyectados × factor de descuento de una operación coincide con su PV (para `irs` y `bond`, 1e-6 × nocional); filtros por rango, contraparte y moneda; totales cuadran con la suma de filas; CSV con las mismas filas.
- **R2** Confirmar una liquidación inserta el `transfer` con `kind = settlement_confirmed`; duplicado → 409; fecha sin flujo derivado → 409; PV y P&L no cambian (1e-12); el calendario muestra el estado confirmado y la diferencia.
- **R3** Confirmación: contiene todas las secciones de D3 para los 7 productos; el nombre de la empresa sale de `settings` (editable por `PUT /api/settings`).
- **R4** FpML ida y vuelta: para `irs`, `fx_forward` y `fx_option` (cada uno con al menos 3 variantes: lados, monedas/curvas, fechas), exportar e importar produce una operación con los mismos términos y fechas y el mismo PV (1e-9 relativo). XML mal formado, con DTD/entidad externa, o producto no soportado → 400 sin efectos.
- **R5** Conciliación: (a) CSV con el PV propio exacto → todas `conciliada`; (b) PV del banco calculado con la curva desplazada +5 pb → `explicable`, con desplazamiento estimado 5 pb ± 0.1; (c) PV del banco valuado un día hábil después → atribuida a fecha; (d) nocional distinto (×1.5) → `revisar` con bandera de términos; (e) operación inexistente y operación faltante listadas; la corrida queda guardada y sus tablas rechazan `UPDATE`/`DELETE`.
- **R6** Interfaz según D6, sin desbordes a 1280 px, textos en español; la confirmación imprime sin barra lateral.
- **R7** Metodología actualizada (D7).
- **R8** Sin regresión: las cuatro suites pasan.

## Fuera de alcance (se declara)

Validación contra XSD de FpML; otros productos en FpML; mensajería (SWIFT, MarkitWire); instrucciones de liquidación y cuentas; neteo de pagos; conciliación de colateral; confirmación con firma.

## Restricciones

Las de los cortes anteriores (Python 3.8 de anaconda, sin dependencias nuevas en backend ni interfaz, guardia de no finitos, validación en la frontera, tablas de hechos solo de inserción, commits por tarea con `GRAPHIFY_SKIP_HOOK=1 git commit ... -- <rutas>`, autor Claudio sin `Co-Authored-By`, sin `git stash`, sin push). No hay C++ nuevo. Otros cortes avanzan en paralelo en otros worktrees: **minimizar cambios en archivos compartidos** (`db.py`, `app.py`, `Shell.tsx`, `App.tsx`, `api/types.ts`, `api/client.ts`, `MethodologyScreen.tsx`): añadir al final, en bloques contiguos y delimitados por un comentario `corte 5`, sin reordenar ni reformatear lo existente; lo propio del corte va en módulos nuevos (`desk/api/ops_*.py`, `routes/ops.py`, `desk/ui/src/screens/ops/`, `api/opsTypes.ts`, `api/opsClient.ts`).
