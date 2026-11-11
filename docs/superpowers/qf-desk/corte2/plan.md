# Plan: QF Desk — Corte 2 (operación con vida, valuación a fecha y P&L)

Diseño: `/tmp/fableorchestrate/qf-corte2/design.md` (copia en `docs/superpowers/qf-desk/corte2/design.md`). Repo: `/home/claudio/Git/Quant_Finance`, rama `feat/qf-desk`.

## Contexto

Todo implementador lee esta sección completa y solo su tarea. Las respuestas de Fable a P1–P10 (sección "Aclaraciones de Fable al plan" del diseño) ya están incorporadas aquí; P11 también está respondida (misma regla que `irs` para `cap_floor` y `bond`).

### Entorno
- Repo `/home/claudio/Git/Quant_Finance`, rama **`feat/qf-desk`** (ya existe y está en `origin`). **Nunca** push, merge ni `git stash`.
- **Python del backend:** `/home/claudio/anaconda3/bin/python` (3.8.18; Flask 2.3.3 y pytest 8.2.0 instalados, Flask vive en `~/.local`: ejecutar sin `-I`). Sintaxis 3.8: nada de `match`, `X | Y`, `list[int]`/`dict[str, x]` evaluados en tiempo de ejecución; usar `typing`. `date.fromisoformat` sí existe. **Sin paquetes nuevos** (ni Python ni npm).
- **Node** 22, **npm** 10. Interfaz en `desk/ui` (Vite + React 18 + TS, AG Grid, ECharts, react-router-dom, vitest + jsdom).
- **C++:** `cmake --build build -j4 2>&1 | tail -5` compila `qf`, `qf_tests` y `qfpy` (`build/src/qfpy.cpython-38-x86_64-linux-gnu.so`). Si `build/` no está configurado: `cmake -S . -B build`. **Ignorar `build_release/`.** Convención de tres archivos (`include/qf/<módulo>/<nombre>.hpp`, `src/<módulo>/<nombre>.cpp`, `tests/test_<nombre>.cpp`, snake_case), Doxygen (`@brief`, `@param`, `@return`) en todo método público, clases `PascalCase`, métodos `camelCase`.
- **Las cuatro suites** (todas desde la raíz del repo salvo vitest):
  - C++: `cmake --build build -j4 2>&1 | tail -3 && (cd build && ctest --output-on-failure 2>&1 | tail -3)` → `100% tests passed`. Hoy hay **396** tests; ninguno puede romperse.
  - Bindings Python: `cmake --build build --target pytests 2>&1 | tail -3` → `OK` (unittest sobre `tests/test_*.py`).
  - Backend: `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q 2>&1 | grep -E "passed|failed"` → `N passed`, sin `failed` (no usar `tail`: un warning de pytest_asyncio sale después del resumen).
  - Interfaz: `cd desk/ui && npm test 2>&1 | tail -5` (vitest run) y `npm run build 2>&1 | tail -5` (`tsc -b && vite build`) sin errores.
- **Carga de `qfpy`:** `from desk.api.qf import qfpy`. Si el `.so` no existe: `cmake --build build --target qfpy`.
- **Puertos:** el desk de Claudio usa **5070**: ningún agente arranca nada en 5070. Backend de prueba en **5071** con base temporal: `cd /home/claudio/Git/Quant_Finance && /home/claudio/anaconda3/bin/python -c "from desk.api.app import create_app; create_app(db_path='/tmp/fableorchestrate/qf-corte2/it.db').run(host='127.0.0.1', port=5071)"`. Para integración, la interfaz construida (`desk/ui/dist`) la sirve el propio Flask en 5071.
- **No tocar** `~/Git/MarketDataFeed`, `desk/data/` ni `graphify-out/`.

### Reglas de ejecución y commits
- Un commit por tarea, solo de tus rutas: `git add <rutas> && GRAPHIFY_SKIP_HOOK=1 git commit -m "<tipo>(desk|qf): <por qué>" -- <rutas>`. Nunca `git add -A`/`.`. Autor: la configuración global (Claudio). **Sin `Co-Authored-By`** ni otras líneas de atribución. Mensaje en español que explique el porqué.
- Si `git commit` falla por `.git/index.lock`, esperar y reintentar; no borrar el lock salvo que lleve > 1 min sin proceso git vivo.
- Tareas C++ en serie (comparten `build/`): **solo T1 compila C++** en este corte. Mientras T1 corre, nada más corre.
- Toda matemática financiera (descuento, capitalización, pricing, interpolación) está en C++ vía `qfpy`. Python valida, reúne fechas y fijaciones, llama a `qfpy`, suma/resta resultados, convierte USD→MXN (× spot o × FIX) y serializa. TS solo presenta.
- Guardia de no finitos y cotas del corte 1 (`desk/api/validation.py`: `number`, `integer`, `choice`, `text`, `body_object`, `ensure_finite`, `MAX_AMOUNT`, `MAX_PRICE`, `MAX_RATE`, `MIN_RATE`) aplican a todo cuerpo nuevo. Toda respuesta numérica pasa por `ensure_finite`.
- Errores: `ApiError(status, mensaje_en_español, field)` → `{"error", "field"}`. `field` = nombre de la clave tal como va en el cuerpo/consulta, sin prefijos.
- Sin flags, opciones, columnas ni pantallas no pedidas.

### Convenciones de fechas (fijas)
- Fechas ISO `YYYY-MM-DD`, días naturales, sin calendario de inhábiles ni ajuste.
- **Fecha de valuación = `as_of` del snapshot** usado. Tiempo de un flujo = `(fecha_flujo − fecha_valuación).days / 365` (convención del corte 1).
- Se descuentan solo flujos con fecha de pago **>** fecha de valuación. Un flujo con fecha `d` está **liquidado** en toda fecha de valuación `≥ d`. Ventana de P&L: flujos con fecha en `(from.as_of, to.as_of]`.
- Un evento con `event_date = d` rige en toda fecha `≥ d`. Orden de aplicación: `(event_date, id)` ascendente.
- Estado a la fecha `D` (precedencia en este orden): `no_pactada` si `D < trade_date`; `terminada` si hay `termination` con fecha ≤ D; `ejercida` si hay `exercise` con fecha ≤ D; `vencida` si `D ≥ maturity_date`; si no, `viva`. Solo `viva` tiene PV ≠ 0 y entra a DV01, escenarios y VaR; `no_pactada` tiene PV 0 y queda fuera de riesgo y de flujos (liquidados y proyectados).
- **Opciones vencidas sin ejercicio** (`fx_option`, `swaption`, `equity_option` en `vencida` sin `exercise`): PV 0 y aviso `expired_unexercised` ("vencida sin ejercicio registrado"). No hay ejercicio automático.
- **`maturity_date` por producto:** `irs`, `cap_floor`, `bond`, `fx_forward`: fin del contrato; `fx_option`, `equity_option`: vencimiento de la opción; **`swaption`: expiración de la opción** (el plazo del swap subyacente sigue en `terms.swap_tenor_years`).
- **Plazo ↔ fechas.** Sin `maturity_date` en la petición, `maturity_date = start_date +` plazo: `irs`, `cap_floor`: `periods × period_days` de la curva; `fx_forward`, `fx_option`: `days`; `swaption`: `round(expiry_years × 365)` (solo la expiración, no expiración + plazo como el `describe` del corte 1); `bond`: `round(periods / frequency × 365)`; `equity_option`: `round(maturity_years × 365)`. **Con `maturity_date` en la petición, manda sobre el plazo** y el tenor de `terms` se reescribe con `días = maturity_date − start_date`: `irs`: `periods = max(1, round(días / period_days))` y `maturity_date` se **ajusta** a `start_date + periods × period_days` (la respuesta devuelve la ajustada); `fx_forward`, `fx_option`: `days = días`; `swaption`: `expiry_years = días / 365`; `equity_option`: `maturity_years = días / 365`; `cap_floor`: igual que `irs` con el periodo de su curva; `bond`: `periods = max(1, round(días × frequency / 365))` y `maturity_date` ajustada a `start_date + round(periods / frequency × 365)` (respuesta de Fable a P11).
- **Calendario del swap (`irs`):** `period_days` de `market.CURVES` (TIIE-F 28, SOFR 365). Fechas de pago = `start_date + k` para `k` en `qfpy.ois_payment_days((maturity_date − start_date).days, period_days)`. Periodo en curso en `D`: el primero cuyo pago es `> D`; su inicio es el pago anterior (o `start_date`).
- **Fijaciones diarias:** índices `TIIE-F` y `SOFR` (tasa a un día, decimal, ACT/360) y `USDMXN` (FIX, MXN por USD). La fijación del día `k` devenga `[k, k+1)` con `d_i = 1`. El factor acumulado del periodo en curso en `D` es `qfpy.compound_overnight(tasas de los días [inicio, D), [1]*n, 360.0)`; si `inicio ≥ D` el factor es 1. **Índice de un `irs` = su `curve`.**
- **Fijación faltante:** para un día debido sin fijación se usa la última publicada anterior de ese índice; si no hay ninguna, la tasa a un día de la curva del snapshot (`(1/DF(1/365) − 1) × 360` con el DF de `qfpy`; la composición de fijaciones siempre con `qfpy.compound_overnight`). La valuación devuelve 200 con un aviso `missing_fixing`. Nunca es error.

### Formas de datos fijas
- **Aviso** (`warnings`, siempre lista): `{"code": "missing_fixing" | "fx_fallback" | "no_settlement" | "expired_unexercised", "index": str | null, "dates": [iso, ...], "message": str}`. `fx_fallback` = flujo USD convertido al spot del snapshot `to` por falta de FIX; `no_settlement` = cap/floor, swaption o bono vencido entre `from` y `to` sin liquidación derivada (fuera de alcance); `expired_unexercised` = opción vencida sin `exercise`.
- **Evento:** `{"id": int, "trade_id": int, "type": str, "event_date": iso, "data": {...}, "prev_event_id": int | null, "created_at": iso8601}`. `prev_event_id` = id del último evento insertado de esa operación (orden de inserción), `null` en el `execution`.
- **Catálogo** `EVENT_TYPES = ("execution", "reset", "transfer", "quantity_change", "terms_change", "exercise", "termination")`. `data` por tipo:
  - `execution`: `{}`.
  - `quantity_change`: `{"notional": float > 0}` = nuevo valor del campo nocional del producto (`NOTIONAL_FIELD`: `irs`, `cap_floor`, `swaption` → `notional`; `fx_forward`, `fx_option` → `notional_usd`; `bond` → `face`; `equity_option` → `quantity`).
  - `terms_change`: `{"terms": {parcial}}` mezclado sobre los términos vigentes y revalidado con `PRODUCTS[p].validate`. Solo admite el campo de precio del producto: `fixed_rate` (`irs`) o `strike` (`fx_forward`, `fx_option`, `cap_floor`, `swaption`, `equity_option`); cualquier otra clave, o un `bond`, → 400 `field: "terms"`. Solo por API (ninguna pantalla lo usa).
  - `termination` / `exercise`: `{"amount": float finito}`; inserta además un `transfer` con `{"amount": <mismo>, "currency": "MXN", "cause_event_id": <id>}`; importe positivo = cobra el tenedor, siempre MXN, y el `transfer` cuenta en `settled` del P&L. `exercise` solo para `fx_option`, `swaption` y `equity_option`; otro producto → 400 `field: "type"`.
  - `reset` y `transfer` existen en el catálogo pero no se aceptan por la API (`execution` tampoco) → 400 `field: "type"`.
- **Fijación:** `{"index": "TIIE-F" | "SOFR" | "USDMXN", "date": iso, "value": float}`. Tasas en `[−1, 10]`; `USDMXN` en `(0, MAX_PRICE]`.

### Esquema SQLite (lo crea T3)
```sql
CREATE TABLE IF NOT EXISTS snapshots (id TEXT PRIMARY KEY, label TEXT NOT NULL, synthetic INTEGER NOT NULL, as_of TEXT NOT NULL, data TEXT NOT NULL);  -- sin cambios
CREATE TABLE IF NOT EXISTS counterparties (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, product TEXT NOT NULL,
  counterparty_id INTEGER NOT NULL REFERENCES counterparties(id), trade_date TEXT NOT NULL, start_date TEXT NOT NULL,
  maturity_date TEXT NOT NULL, terms TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS trade_events (id INTEGER PRIMARY KEY AUTOINCREMENT, trade_id INTEGER NOT NULL REFERENCES trades(id),
  type TEXT NOT NULL, event_date TEXT NOT NULL, data TEXT NOT NULL, prev_event_id INTEGER REFERENCES trade_events(id), created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS trade_events_no_update BEFORE UPDATE ON trade_events BEGIN SELECT RAISE(ABORT, 'trade_events es solo de inserción'); END;
CREATE TRIGGER IF NOT EXISTS trade_events_no_delete BEFORE DELETE ON trade_events BEGIN SELECT RAISE(ABORT, 'trade_events es solo de inserción'); END;
CREATE TABLE IF NOT EXISTS fixings (index_name TEXT NOT NULL, fixing_date TEXT NOT NULL, value REAL NOT NULL, PRIMARY KEY (index_name, fixing_date));
```
`terms` = `params` normalizados del producto (la misma forma del corte 1, plazo incluido). Base del corte 1 = tabla `trades` con columna `params` (y `counterparty` texto): `init_schema` la migra (D8) de forma idempotente conservando los `id`.

### Interfaces Python internas (fijas)
- `desk/api/lifecycle.py` (T4; función pura sin DB; solo usa `PRODUCTS[p].validate` para `terms_change`): `EVENT_TYPES`, `STATUSES = ("no_pactada", "viva", "vencida", "terminada", "ejercida")`, `NOTIONAL_FIELD`, `state(trade, events, on: date) -> {"status": str, "terms": dict, "notional": float}`. `trade` = dict de `portfolio.load_trades` (fechas como `date`); `events` = lista de eventos (con `event_date` como `date`) en cualquier orden.
- `desk/api/events.py` (T4): `load_events(conn, trade_id) -> List[dict]`, `load_all_events(conn) -> Dict[int, List[dict]]`, `insert_event(conn, trade_id, type, event_date: date, data) -> dict`, `post_event(conn, trade_id, body) -> List[dict]` (valida y responde 400/404/409 del contrato).
- `desk/api/fixings.py` (T5): `INDICES = ("TIIE-F", "SOFR", "USDMXN")`, `add_fixing(conn, body) -> (dict, created: bool)`, `import_csv(conn, text) -> {"inserted": int, "unchanged": int}`, `list_fixings(conn, index=None, start=None, end=None) -> List[dict]`, `load_all(conn) -> Dict[str, Dict[date, float]]`.
- `desk/api/portfolio.py` (T3, ampliado en T7): `load_trades(conn)` → lista por id de `{"id", "product", "counterparty" (nombre), "trade_date", "start_date", "maturity_date" (date), "params" (términos de origen; `None` si el JSON está corrupto), "created_at", "events" (lista)}`; `get_trade(conn, id)` (404 `field: "id"`); `create_trade(conn, body)`; `list_trades(conn)`; `valuation(conn, snapshot_id)`; `trade_pv_mxn(trade, mkt, fixings) -> float` (0.0 si no está `viva` en `mkt.as_of`; lanza si no se puede valuar).
- `desk/api/valuation.py` (T7): `value_trade(trade, mkt, fixings) -> {"status", "notional", "currency", "pv", "pv_mxn", "warnings"}` con `pv` en la moneda de `/api/price` del producto (D6: `MXN` para `fx_forward`, `fx_option`, `equity_option`; moneda de la curva para el resto); `is_live(trade, on: date) -> bool`.
- `desk/api/settlement.py` (T9): `settled_flows(trade, fixings, d0: date, d1: date, fallback_spot: float) -> (flows, warnings)`; cada flujo `{"date", "kind": "coupon" | "settlement" | "transfer", "amount", "currency", "amount_mxn"}` con fecha en `(d0, d1]`.
- `desk/api/pnl.py` (T9): `compute_pnl(conn, from_id, to_id) -> dict` (forma del contrato).
- `market.py` (T6): `roll_snapshot(conn, source_id, body) -> dict` (devuelve el payload GET del nuevo).
- `qfpy` tras T1: `qfpy.compound_overnight(rates, days, day_base=360.0) -> float` y el constructor nuevo `qfpy.OisSwap(notional, fixed_rate, start_days, pay_days, accrued_factor, swap_type, curve_key, dcc=ACT_360)` (ver T1). El constructor del corte 1 sigue igual.

### Contrato HTTP nuevo o cambiado (backend ↔ interfaz)
Sin cambios: `/api/price/*`, `/api/risk/*` (formas), `/api/market/snapshots*`, `/api/market/refresh`. Nota: el diseño dice `/api/portfolio/value`; la ruta real es **`/api/portfolio/valuation`**.

**Operaciones**
- `POST /api/trades` `{"product", "counterparty", "params", "snapshot"?, "trade_date"?, "start_date"?, "maturity_date"?}` → 201 operación. Fechas ISO válidas o 400 con su campo; `trade_date ≤ start_date < maturity_date` o 400 (`field` = la fecha que rompe la regla: `start_date` si `start < trade`, `maturity_date` si `maturity ≤ start`). Contraparte nueva se da de alta en `counterparties`. Inserta un `execution` con `event_date = trade_date`. Defaults: `trade_date` y `start_date` ausentes → `as_of` del `snapshot` de la petición (o de `MX-DEMO` si no viene; snapshot inexistente → 404 `field: "snapshot"`); `start_date` ausente con `trade_date` presente → `start_date = trade_date`. Vencimiento y tenor: regla "Plazo ↔ fechas" de Convenciones (la `maturity_date` manda; en `irs` se ajusta y la respuesta devuelve la fecha ajustada y `params.periods` recalculado).
- Forma de una operación (POST, GET lista y GET una): `{"id", "product", "counterparty", "trade_date", "start_date", "maturity_date", "params", "notional", "currency", "maturity", "created_at"}` (`params` = términos de origen, `notional` de origen, `maturity` = `maturity_date`).
- `GET /api/trades` → `{"trades": [...]}` por id.
- `GET /api/trades/<id>` → operación + `"events": [evento...]` en orden `(event_date, id)`. Inexistente → 404 `field: "id"`.
- `GET /api/trades/<id>/state?date=YYYY-MM-DD` → `{"id", "date", "status", "notional", "terms"}`. `date` obligatorio/ISO → 400 `field: "date"`.
- `POST /api/trades/<id>/events` `{"type", "event_date", "data"}` → 201 `{"events": [evento, ...]}` (uno, o dos con el `transfer`). 404 `field: "id"`; tipo fuera del catálogo o no admitido → 400 `field: "type"`; `event_date` inválida o `< trade_date` → 400 `field: "event_date"`; `data` inválida → 400 con el nombre de la clave (`amount`, `notional`, `terms`); estado en `event_date` distinto de `viva` → **409** `field: "id"`.
- `DELETE /api/trades/<id>` → siempre **409** `field: "id"`, mensaje "Una operación no se borra: termínala" (404 si no existe). La interfaz ya no ofrece borrar.
- `GET /api/trades/<id>/flows?snapshot=<id>` → `{"id", "snapshot", "as_of", "flows": [{"date", "kind": "coupon" | "settlement" | "transfer", "status": "settled" | "projected", "amount", "currency", "df": num | null, "pv": num | null}], "warnings": [...]}`. `settled` = `settled_flows(trade, fixings, trade_date − 1 día, as_of)` (con `df`/`pv` `null`); `projected` = `cashflows` del pricer a la fecha (solo `irs` y `bond`; vacío si no está `viva`; `no_pactada` no tiene flujos de ningún tipo). Orden por fecha.

**Valuación** — `GET /api/portfolio/valuation?snapshot=<id>`: filas con, además de lo del corte 1, `"trade_date", "start_date", "maturity_date", "status", "warnings"`; `notional` = vigente a `as_of`; `pv` en la moneda de `/api/price` (D6, R10); PV 0 si no está `viva`. `total_mxn` igual que antes.

**Riesgo** — `/api/risk/dv01|scenarios|var`: solo operaciones `viva` en el `as_of` del snapshot; las demás no aparecen ni en totales ni en `trades`/`errors`.

**P&L** — `GET /api/pnl?from=<snapshot>&to=<snapshot>` → 
```json
{"from":{"snapshot":"MX-DEMO","as_of":"2026-11-10"},"to":{"snapshot":"D1","as_of":"2026-12-08"},
 "total_mxn":0.0,"totals":{"pv_from":0.0,"pv_to":0.0,"settled":0.0,"pnl":0.0},
 "rows":[{"id":1,"product":"irs","counterparty":"...","status_from":"viva","status_to":"viva",
          "pv_from":0.0,"pv_to":0.0,"settled":0.0,"pnl":0.0,"error":null,"warnings":[]}]}
```
Todo en MXN. `pnl = pv_to − pv_from + settled`; `settled` = suma de `amount_mxn` de `settled_flows(trade, fixings, from.as_of, to.as_of, spot_to)` (incluye los `transfer` de terminación/ejercicio). Una operación con `trade_date ∈ (from.as_of, to.as_of]` tiene `pv_from = 0` y `status_from = "no_pactada"` (no se modela prima ni pago inicial). Fila con error: cifras `null`, no suma. Falta `from`/`to` → 400 con ese campo; snapshot inexistente → 404 `field: "snapshot"`; `from.as_of > to.as_of` → 400 `field: "to"`.

**Fijaciones**
- `GET /api/fixings?index=&from=&to=` (todos opcionales) → `{"fixings": [fijación...]}` por `(index, date)`. Índice desconocido → 400 `field: "index"`; fecha inválida → 400 con su campo.
- `POST /api/fixings` `{"index", "date", "value"}` → 201 `{"fixing", "created": true}`; duplicado exacto → 200 `{"fixing", "created": false}`; misma clave con otro valor → 409 `field: "value"`; no finito o fuera de rango → 400 `field: "value"`.
- `POST /api/fixings/csv` `{"csv": "index,date,value\nTIIE-F,2026-11-10,0.0701\n..."}` → 200 `{"inserted", "unchanged"}`. Encabezado exacto obligatorio. Atómico: cualquier fila mala → nada se guarda, 400 `field: "csv"` con "Fila <n>: <motivo>" (n = número de línea, encabezado = 1); conflicto → 409 `field: "csv"`.

**Mercado — rodar**
- `POST /api/market/<id>/roll` `{"id": nuevo, "as_of": iso}` → 201 payload igual al de `GET /api/market/snapshots/<nuevo>`. Copia `synthetic` y `data` (incluidas `sources`) tal cual; `label = "<label original> · rodado al <as_of>"`. El nuevo es editable aunque el origen sea `MKT-LIVE`. `id` debe cumplir `^[A-Za-z0-9_-]{1,40}$` y no ser `MKT-LIVE` → 400 `field: "id"`; ya existe → 409 `field: "id"`; `as_of` inválida → 400 `field: "as_of"`; origen inexistente → 404 `field: "snapshot"`.

### Interfaz: piezas fijas (las crea U1)
- Rutas: las del corte 1 + **`/portafolio/:id`** → `screens/TradeScreen.tsx` (ficha).
- `screens/PortfolioScreen.tsx` monta `<PnlPanel />` (`screens/PnlPanel.tsx`) en una pestaña "P&L" junto al blotter; `screens/MarketScreen.tsx` monta `<FixingsPanel />` (`screens/FixingsPanel.tsx`) en una sección "Fijaciones". U1 deja los tres componentes como stubs exportados (`export default function X() { return <section data-testid="x-stub" /> }`).
- `src/api/types.ts`: tipos de todo el contrato nuevo: `TradeStatus`, `EventType`, `TradeEvent`, `Trade` (con fechas), `TradeDetail` (`Trade & {events}`), `TradeState`, `Warning`, `Flow`, `FlowsResponse`, `ValuationRow` (ampliado), `Fixing`, `FixingsCsvResult`, `PnlRow`, `PnlResponse`.
- `src/api/client.ts` añade: `getTrade(id)`, `tradeState(id, date)`, `tradeFlows(id, snapshot)`, `postEvent(id, body: {type, event_date, data})`, `listFixings(q?: {index?, from?, to?})`, `addFixing(body)`, `importFixingsCsv(csv: string)`, `rollSnapshot(sourceId, body: {id, as_of})`, `pnl(from, to)`; `createTrade` acepta `trade_date`, `start_date`, `maturity_date` opcionales. Errores = `ApiError` del corte 1.
- Estado en la interfaz se rotula: `no_pactada` → "No pactada", `viva` → "Viva", `vencida` → "Vencida", `terminada` → "Terminada", `ejercida` → "Ejercida". Montos con `fmtMoney`, fechas con `fmtDate`, cifras con `.num`.
- Tests de UI con `fetch`/cliente simulados (`vi.mock('../api/client')` como en las pruebas existentes de `PortfolioScreen.test.tsx`).

---

### Anotado tras T1 (firmas reales, commit 305f324)
- `qfpy.compound_overnight(rates, days, day_base=360.0)` → factor de capitalización.
- `qfpy.OisSwap(notional, fixed_rate, start_days, pay_days, accrued_factor, swap_type, curve_key, dcc=DayCountConvention.ACT_360)` (nuevo; `start_days` ≤ 0 si el periodo en curso ya empezó, `pay_days` lista de días a cada pago desde la fecha de valuación). El constructor del corte 1 `(notional, fixed_rate, maturity_days, period_days, swap_type, curve_key, dcc)` no cambió. Errores → `ValueError`.
- ctest: 402; pytests de bindings: 56; `desk/api`: 1798; vitest: 108.


### Anotado tras U1 (interfaz, commit 5ee2cdf)
- Tipos en `src/api/types.ts`: `TradeStatus`, `EventType`, `TradeEvent`, `Trade` (con `trade_date`, `start_date`, `maturity_date`), `TradeDetail = Trade & {events}`, `TradeState`, `Warning {code, index, dates, message}`, `Flow {date, kind, status:'settled'|'projected', amount, currency, df, pv}`, `FlowsResponse {id, snapshot, as_of, flows, warnings}`, `ValuationRow` (+ `status`, `warnings`, fechas), `FixingIndex`, `Fixing {index, date, value}`, `AddFixingResponse {fixing, created}`, `FixingsCsvResult {inserted, unchanged}`, `PnlRow`, `PnlResponse {from, to, total_mxn, totals, rows}`.
- Cliente `src/api/client.ts`: `getTrade(id)`, `tradeState(id, date)`, `tradeFlows(id, snapshot)`, `postEvent(id, {type, event_date, data})` → **devuelve `TradeEvent[]`**, `listFixings(q?)` → `Fixing[]`, `addFixing(body)`, `importFixingsCsv(csv)`, `rollSnapshot(sourceId, {id, as_of})`, `pnl(from, to)`, `createTrade(body)` con `snapshot?`, `trade_date?`, `start_date?`, `maturity_date?`.
- Stubs con `export default`: `screens/TradeScreen.tsx` (ruta `/portafolio/:id`), `screens/PnlPanel.tsx`, `screens/FixingsPanel.tsx`. `PortfolioScreen` tiene pestañas "Operaciones" / "P&L" (`portfolio-tab-blotter`, `portfolio-tab-pnl`); el blotter sigue montado y `PnlPanel` solo se monta con su pestaña activa. `MarketScreen` ya pone la sección y el `<h2>Fijaciones</h2>`; `FixingsPanel` no repite el encabezado.
- vitest: 112.

### Anotado tras T3 (backend, commit b222e2c; `desk/api` = 1887 tests)
- `validation.iso_date(d, name, required=True) -> date | None` (400 con `field=name`): reutilizarlo, no duplicar el parseo de fechas.
- `portfolio.py` real: `load_trades(conn)` (fechas como `date`, `params`, `events` ordenados por `(event_date, id)`), `get_trade(conn, id)` (404 `field:"id"`), `list_trades`, `create_trade(conn, body)`, `public_trade(trade)`, `counterparty_id`, `insert_trade`, `default_maturity`, `fit_to_maturity`. `delete_trade` ya no existe. `trade_pv_mxn(trade, mkt)` y `valuation(conn, snapshot_id)` siguen con la forma del corte 1 (T7 las amplía).
- `events.py` real: `load_events(conn, trade_id)`, `load_all_events(conn)`, `insert_event(conn, trade_id, type, event_date: date, data) -> dict` (encadena `prev_event_id`, sin commit), `public_event(e)`. Stub: `post_event(conn, trade_id, body)`.
- `lifecycle.py`: constantes `EVENT_TYPES`, `STATUSES`, `NOTIONAL_FIELD`; stub `state(trade, events, on)`.
- `fixings.py`: `INDICES`; stubs `add_fixing`, `import_csv`, `list_fixings(conn, index=None, start=None, end=None)` (debe validar `index` → 400 `field:"index"`), `load_all(conn)`.
- `valuation.py`: stubs `value_trade(trade, mkt, fixings)`, `is_live(trade, on)`. `settlement.py`: stubs `settled_flows(trade, fixings, d0, d1, fallback_spot)`, `trade_flows(conn, trade_id, snapshot_id)`. `pnl.py`: stub `compute_pnl(conn, from_id, to_id)`. `market.roll_snapshot(conn, source_id, body)`: stub.
- Las rutas ya están todas registradas, validan y delegan en esos módulos (hacen el commit y fijan el código HTTP); basta implementar las funciones stub.
- `tests/test_trades_dates.py::STUB_ROUTES` lista las rutas que aún dan 501: **quien implemente una ruta borra solo sus filas** (releer el archivo justo antes de editarlo: otras tareas en paralelo lo tocan).
- Para vaciar el portafolio en tests: `empty_portfolio(client)` e `insert_raw_trade(app, product, terms_text)` de `desk.api.tests.conftest` (`DELETE` responde 409).

### Anotado tras T4, T5 y T6 (commits ca201dd, cedab14, cbf7601; `desk/api` = 2073 tests)
- `lifecycle.state(trade, events, on: date) -> {"status", "terms", "notional"}`: pura; precedencia `no_pactada` > `terminada` > `ejercida` > `vencida` > `viva`; `ValueError` si `params` es `None` o producto desconocido.
- `events.post_event(conn, trade_id, body) -> List[Dict]` (1 o 2 eventos; `termination`/`exercise` añaden un `transfer` `{"amount", "currency": "MXN", "cause_event_id"}`); `events.API_EVENT_TYPES`.
- `fixings.add_fixing(conn, body) -> (dict, created)`, `import_csv(conn, text) -> {"inserted","unchanged"}`, `list_fixings(conn, index, start, end)`, **`load_all(conn) -> Dict[str, Dict[date, float]]`** (los tres índices siempre presentes).
- `market.roll_snapshot(conn, source_id, body)`: copia `synthetic` y `data`, rótulo `"<label> · rodado al <as_of>"`.

### T4b — Reglas de fecha de los eventos (decisión de Fable tras T4) — modelo sonnet
- **Objetivo:** dos ajustes en `events.post_event` (archivos: `desk/api/events.py`, `desk/api/tests/test_events_api.py`; no tocar `lifecycle.py`, `valuation.py`, `portfolio.py`).
  1. Un `exercise` con `event_date == maturity_date` se **acepta** (el ejercicio ocurre al vencimiento): para `exercise` la condición es "estado el día anterior a `event_date` es `viva` y `event_date ≤ maturity_date`". Para los demás tipos sigue la regla actual (estado en `event_date` distinto de `viva` → 409). `lifecycle.state` ya da precedencia a `ejercida` sobre `vencida`, así que el estado en el vencimiento queda `ejercida`.
  2. Los eventos se registran en orden cronológico: si `event_date` es anterior a la `event_date` del último evento ya guardado de la operación → 409 `field: "event_date"` con mensaje claro. Igual fecha se permite.
- **Tests:** ejercicio el día del vencimiento → 201 y estado `ejercida` ese día; ejercicio un día después → 409; evento con fecha anterior al último → 409 y nada insertado; ajustar el test existente que esperaba 409 en el día exacto del vencimiento para `exercise`.
- **Verificación:** `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q | grep -E "passed|failed"` → sin `failed`.

### Anotado tras T4b y T7 (commits cef5a10, 8798c85; `desk/api` = 2108 tests)
- `valuation.value_trade(trade, mkt, fixings=None) -> {"status","notional","currency","pv","pv_mxn","warnings"}`: `pv` en la moneda de `/api/price` (MXN para fx_forward, fx_option y equity_option), `pv_mxn` siempre MXN; estado distinto de `viva` → `pv = pv_mxn = 0.0`; lanza `ValueError`/`ApiError` si la operación es ilegible.
- `valuation.is_live(trade, on) -> bool` (True si el estado no se puede derivar, para que el `except` existente reporte la operación corrupta en `errors`). `valuation.normalized(trade) -> (Product, params)` (ya no existe `portfolio._normalized`).
- `portfolio.trade_pv_mxn(trade, mkt, fixings=None) -> float`; `portfolio.valuation(conn, snapshot_id)` carga `fixings.load_all` una vez y cada fila trae `id, product, counterparty, trade_date, start_date, maturity_date, status, notional, currency, maturity, pv, pv_mxn, warnings, error`.
- Eventos: se registran en orden cronológico (fecha anterior al último → 409 `field:"event_date"`); `exercise` el día del vencimiento se acepta.
- **Decisión de Fable (bono):** los periodos restantes del bono son `ceil((días − 0.5) × frequency / 365)` (no `ceil(días × frequency / 365)`), para que el día del pacto dé exactamente `periods` aunque `maturity_date` haya redondeado medio día. La aplica T8 en `valuation.py` con su test (bono `periods=3, frequency=2` valuado el día del pacto == `/api/price`).

## Tareas

### T1 — Swap OIS envejecido y `compoundOvernight` en C++ (+ `qfpy`)
- **Modelo:** sonnet · **Depende de:** — (primera y sola; nada corre en paralelo) · **R:** R3, R13 (C++ y bindings)
- **Objetivo:** que `OisSwap` valúe un swap con el periodo en curso ya iniciado (factor acumulado de fijaciones) o con inicio futuro, sin cambiar el constructor actual.
- **Archivos:** `include/qf/instruments/ois_swap.hpp`, `src/instruments/ois_swap.cpp`, `tests/test_ois_swap.cpp`, `src/python_bindings/qfpy.cpp`, `tests/test_ois_aged_py.py` (nuevo).
- **API:**
  ```cpp
  namespace qf::instruments {
  /// Π (1 + r_i · d_i / dayBase); vacío → 1. Lanza invalid_argument si tamaños difieren, d_i ≤ 0, dayBase ≤ 0 o algún factor ≤ 0.
  double compoundOvernight(const std::vector<double>& rates, const std::vector<int>& days, double dayBase = 360.0);
  class OisSwap {
    // nuevo, además del actual:
    OisSwap(double notional, double fixedRate, int startDays, std::vector<int> payDays, double accruedFactor,
            SwapType type, std::string curveKey, math::DayCountConvention dcc = math::DayCountConvention::ACT_360);
  };
  }
  ```
  Días relativos a la fecha de valuación. `payDays` estrictamente creciente, todos > 0, `startDays < payDays[0]`; `accruedFactor > 0`, y `== 1` si `startDays ≥ 0`; si no, `invalid_argument`. Periodo 1: de `startDays` a `payDays[0]`, `τ = yearFraction(payDays[0] − startDays, dcc)`; `floatAmount = N·(accruedFactor·DF(max(startDays,0))/DF(payDays[0]) − 1)` (DF(0) = 1). Resto igual al constructor actual. `parRate = Σ floatAmount·DF / annuity` en ambos constructores (para el actual coincide con la fórmula de hoy; comprobarlo). Internamente el constructor actual puede delegar en el nuevo con `startDays = 0`, `payDays = oisPaymentDays(...)`, `accruedFactor = 1`; `maturityDays()` = último pago; `periodDays()` del constructor nuevo = longitud del primer periodo.
- **Bindings:** `m.def("compound_overnight", ..., py::arg("rates"), py::arg("days"), py::arg("day_base") = 360.0)`; segundo `py::init` de `OisSwap` con `py::arg("notional"), py::arg("fixed_rate"), py::arg("start_days"), py::arg("pay_days"), py::arg("accrued_factor"), py::arg("swap_type"), py::arg("curve_key"), py::arg("dcc") = ACT_360`. El constructor existente no cambia de nombres de argumentos.
- **Pasos (TDD):**
  1. Tests C++ en `tests/test_ois_swap.cpp` (nuevos `TEST`s):
     - Retrocompatibilidad: para (364, 28) y (1825, 365) y ambos lados, el constructor nuevo con `startDays=0`, `payDays=oisPaymentDays`, factor 1 da `npv`, `parRate`, `annuity` y cada `cashFlows` iguales al actual a 1e-12 relativo.
     - `compoundOvernight`: vacío = 1; `{0.07}×1 día` = 1 + 0.07/360; tamaños distintos y días ≤ 0 lanzan.
     - **R3**: curva D0 (`bootstrapOis` con cotizaciones TIIE-F de 1 a 26×28 días, o una `YieldCurve` explícita), swap payer a la par (`parRate`) 364/28, N = 1e8. Para `τ ∈ {28, 14}`: fijaciones diarias `r_k = (DF0(k/365)/DF0((k+1)/365) − 1)·360`, `k = inicio_periodo..τ−1`; curva D1 = `YieldCurve` cuyos pilares están exactamente en los pagos restantes desplazados (`t' = (d − τ)/365`, `z'(t') = (z0(d/365)·d/365 − z0(τ/365)·τ/365)/t'`); swap envejecido con `startDays = inicio_periodo − τ`, `payDays` restantes − τ, `accruedFactor = compoundOvernight(r, 1…)`. Esperado: `npv_D1 = (npv_D0 − Σ_{pago ≤ τ} presentValue_D0) / DF0(τ/365)` a `1e-6·N`.
     - Validaciones del constructor nuevo lanzan.
  2. Implementar; Doxygen en lo nuevo.
  3. Bindings y `tests/test_ois_aged_py.py` (unittest, patrón de `tests/test_desk_bindings_py.py`): `compound_overnight` y el caso R3 con `τ = 28` desde Python, misma tolerancia; retrocompatibilidad 1e-12.
- **Verificación:** `cmake --build build -j4 2>&1 | tail -3 && (cd build && ctest -R OisSwap --output-on-failure | tail -3; ctest | tail -3)` → `100% tests passed` (≥ 396 + nuevos); `cmake --build build --target pytests 2>&1 | tail -3` → `OK`; `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q | grep -E "passed|failed"` → sin `failed` (nada del desk cambia).
- **Commit:** las cinco rutas.

### T2 — Fotografía del corte 1 para la migración
- **Modelo:** haiku · **Depende de:** T1 · **R:** R9 (insumo)
- **Objetivo:** congelar, con el código **actual** del backend (antes de T3), las filas de `trades` de una base del corte 1 y su PV con `MX-DEMO`, para que T3 pruebe que la migración no cambia nada.
- **Archivos:** `desk/api/tests/fixtures/corte1_trades.json` (nuevo), `desk/api/tests/corte1_fixture.py` (nuevo).
- **Pasos:**
  1. Script de un solo uso (no se commitea, en `/tmp/fableorchestrate/qf-corte2/`): `create_app(db_path=<tmp>)`, leer `SELECT id, product, counterparty, params, created_at FROM trades ORDER BY id` y `portfolio.valuation(conn, "MX-DEMO")`; escribir JSON `{"as_of": "2026-11-10", "trades": [{"id", "product", "counterparty", "params" (el texto JSON tal cual), "created_at", "pv_mxn": <float repr completo>}]}` con `json.dump(..., indent=2)`.
  2. `corte1_fixture.py`: `build_corte1_db(path) -> Path` que crea una base con el esquema exacto del corte 1 (copiar estas dos líneas: `CREATE TABLE snapshots (id TEXT PRIMARY KEY, label TEXT NOT NULL, synthetic INTEGER NOT NULL, as_of TEXT NOT NULL, data TEXT NOT NULL);` y `CREATE TABLE trades (id INTEGER PRIMARY KEY AUTOINCREMENT, product TEXT NOT NULL, counterparty TEXT NOT NULL, params TEXT NOT NULL, created_at TEXT NOT NULL);`), llama `desk.api.seed_market.seed_market(conn)`, inserta las filas del JSON con sus `id`, hace commit; y `golden_pv() -> Dict[int, float]`.
- **Verificación:** `/home/claudio/anaconda3/bin/python -c "import sys; sys.path.insert(0,'.'); from desk.api.tests.corte1_fixture import build_corte1_db, golden_pv; print(build_corte1_db('/tmp/fableorchestrate/qf-corte2/c1.db'), len(golden_pv()))"` → ruta y `7`; suite backend sin `failed`.
- **Commit:** las dos rutas.

### T3 — Esquema, migración, alta con fechas y rutas de contrato (backend)
- **Modelo:** sonnet · **Depende de:** T2 · **R:** R1 (alta, `execution`, disparadores), R9, R13 (backend)
- **Objetivo:** pasar al esquema del corte 2 con migración idempotente, crear operaciones con fechas y evento `execution`, y dejar registradas (como stubs 501) todas las rutas nuevas para que T4–T9 solo rellenen módulos.
- **Archivos:** `desk/api/db.py`, `desk/api/migrate.py` (nuevo), `desk/api/portfolio.py`, `desk/api/seed_trades.py`, `desk/api/app.py`, `desk/api/routes/trades.py`, `desk/api/routes/fixings.py` (nuevo, stub), `desk/api/routes/pnl.py` (nuevo, stub), `desk/api/routes/market.py`, `desk/api/lifecycle.py`, `desk/api/events.py`, `desk/api/fixings.py`, `desk/api/valuation.py`, `desk/api/settlement.py`, `desk/api/pnl.py` (los seis últimos como stubs con las firmas del Contexto que lanzan `NotImplementedError`, salvo lo que esta tarea necesita de `events.insert_event`), `desk/api/tests/test_schema_migration.py` (nuevo), `desk/api/tests/test_trades_dates.py` (nuevo), y los tests existentes que dependan de la forma vieja de `trades` (`test_portfolio.py`, ajuste mínimo).
- **Pasos:**
  1. `db.SCHEMA` = el del Contexto. `init_schema(conn)`: si existe `trades` con columna `params` (base del corte 1), llamar `migrate.migrate_v1(conn)` antes de crear lo nuevo. `migrate_v1`: en **una sola transacción**, renombrar `trades` → `trades_v1`, crear el esquema nuevo, dar de alta contrapartes, copiar cada fila conservando `id`, `product`, `created_at`, `terms = params`, `trade_date = start_date = as_of de MX-DEMO`, `maturity_date = start_date +` plazo (regla "Plazo ↔ fechas"; `swaption` = solo expiración), insertar un `execution` por operación con `event_date = trade_date`, y borrar `trades_v1`. Idempotente: en una base ya migrada no hace nada. Fila corrupta (JSON ilegible, producto desconocido o `params` que no validan): **aborta el arranque** con `RuntimeError` que nombra el `id` y el motivo; `ROLLBACK` completo, la base queda exactamente como estaba (sin migración parcial).
  2. `events.insert_event` real (lo demás de `events.py` stub). `portfolio.create_trade/list_trades/load_trades/get_trade` según el contrato (fechas, contraparte por `counterparties`, `execution`). Reglas de fechas, defaults y "Plazo ↔ fechas" del contrato. `seed_trades` sin fechas explícitas (toma los defaults) → mismo resultado que la migración.
  3. `portfolio.valuation` sigue valuando como en el corte 1 (aún sin envejecer; lo cambia T7) para que R9 se pueda comprobar ya: el PV con `MX-DEMO` de cada operación migrada debe ser el de `golden_pv()`.
  4. Rutas: `routes/trades.py` añade `GET /api/trades/<id>`, `GET /api/trades/<id>/state`, `POST /api/trades/<id>/events`, `GET /api/trades/<id>/flows` (delegan en los módulos; validan id → 404 y parámetros de consulta obligatorios); `DELETE` responde siempre 409 (404 si no existe). `routes/fixings.py` (`GET/POST /api/fixings`, `POST /api/fixings/csv`) y `routes/pnl.py` (`GET /api/pnl`) delegan en `fixings.py`/`pnl.py`. `routes/market.py` añade `POST /api/market/<id>/roll` → `market.roll_snapshot`; T3 añade en `market.py` un stub `roll_snapshot` que lanza `NotImplementedError` y T6 lo rellena. Registrar los blueprints nuevos en `app.py`. `NotImplementedError` → 501 (handler existente).
  5. Tests: `test_schema_migration.py` — base de `build_corte1_db` → `create_app` → 7 operaciones con los mismos `id`, cada una con exactamente un `execution`; PV por operación == `golden_pv()` a 1e-8 relativo; segundo `create_app` sobre la misma base no duplica operaciones, eventos ni contrapartes; una base del corte 1 con una fila corrupta añadida hace fallar `create_app` con un error que nombra su id, y la base sigue con el esquema viejo y las mismas filas. `UPDATE trade_events SET type='x'` y `DELETE FROM trade_events` por SQL directo → `sqlite3.DatabaseError`. `test_trades_dates.py` — alta con fechas guarda las tres y un `execution`; reglas de orden de fechas → 400 con el campo; fecha no ISO → 400; contraparte repetida reutiliza el id; `maturity_date` manda sobre el plazo (`fx_forward` con `days` 91 y vencimiento a 100 días → `params.days == 100`); `irs` TIIE-F con vencimiento a 100 días → `periods == 4` y `maturity_date` ajustada a `start + 112`; `swaption` sin `maturity_date` → `start + round(expiry_years × 365)`; `snapshot` en el cuerpo fija los defaults; `DELETE` → 409; `cap_floor` y `bond` con `maturity_date` → `periods` recalculado y fecha ajustada (P11); las rutas nuevas responden 501 JSON mientras sus módulos sean stub (excepto las que ya funcionan).
- **Verificación:** suite backend sin `failed`; `grep -c "def test_" desk/api/tests/test_schema_migration.py` ≥ 4.
- **Commit:** todas las rutas listadas.

### T4 — Ciclo de vida: `state()` y eventos por la API
- **Modelo:** sonnet · **Depende de:** T3 · **Paralela con:** T5, T6 · **R:** R1 (400 por tipo), R2, R5 (eventos y 409), R6 (estado)
- **Objetivo:** estado derivado puro y alta de eventos con sus validaciones.
- **Archivos:** `desk/api/lifecycle.py`, `desk/api/events.py`, `desk/api/tests/test_lifecycle.py` (nuevo), `desk/api/tests/test_events_api.py` (nuevo). (Las rutas ya existen desde T3: no tocar `routes/`.)
- **Pasos:**
  1. `lifecycle.state` según "Convenciones de fechas" y "Formas de datos" del Contexto: parte de `trade["params"]`, aplica en orden `(event_date, id)` los eventos con fecha ≤ `on`: `quantity_change` cambia `terms[NOTIONAL_FIELD[product]]`; `terms_change` mezcla y revalida (`PRODUCTS[p].validate`); `termination`/`exercise` fijan estado; luego `vencida` si `on ≥ maturity_date` y sigue `viva`. Sin estado guardado.
  2. `events.load_events`, `load_all_events`, `post_event` con las reglas del contrato (catálogo, tipos no admitidos, fecha, `data` por tipo, 409 si el estado en `event_date` no es `viva`, `transfer` acompañante con `cause_event_id`). Todo en una transacción; la ruta hace `commit`.
  3. `GET /api/trades/<id>` y `/state` usan estas funciones (las rutas de T3 ya delegan; si T3 dejó un nombre distinto, ajustar solo la llamada en el módulo, no la ruta).
- **Tests:** tabla de casos de `state` (`on < trade_date` → `no_pactada`; sin eventos; `quantity_change` antes/después de `on`; dos eventos misma fecha → gana el de mayor id; `termination` → `terminada` y luego no `vencida`; `on = maturity_date` → `vencida`); **R2**: para las 7 operaciones de la semilla más tres creadas en el test (una con dos `quantity_change`, una con `quantity_change` + `termination`, una con dos eventos de la misma fecha insertados en orden inverso a sus fechas de alta), `state()` recalculado desde `load_events` coincide con `GET /state` en 5 fechas (antes de inicio, inicio, entre eventos, después del último, vencimiento); **R1**: tipo `"novation"` → 400 `field: "type"`; `execution`/`reset`/`transfer` por la API → 400; **R5**: `termination` con `amount` inserta 2 eventos (`termination` + `transfer` con `prev_event_id` encadenado) y el estado pasa a `terminada` desde esa fecha; otro evento después → 409; **R6**: `quantity_change` cambia `notional` del estado solo desde su fecha; `amount`/`notional` no finitos → 400. `terms_change` con `strike`/`fixed_rate` → 201 y el estado lo refleja; con otra clave → 400 `field: "terms"`; `exercise` sobre un `irs` → 400 `field: "type"`; `DELETE` → 409.
- **Verificación:** `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests/test_lifecycle.py desk/api/tests/test_events_api.py -q | grep -E "passed|failed"` y la suite completa sin `failed`.
- **Commit:** las cuatro rutas.

### T5 — Fijaciones: alta, CSV, listado
- **Modelo:** sonnet · **Depende de:** T3 · **Paralela con:** T4, T6 · **R:** R7 (alta, CSV, listado, 409, 400)
- **Archivos:** `desk/api/fixings.py`, `desk/api/tests/test_fixings.py` (nuevo).
- **Pasos:** implementar las funciones del Contexto con las reglas del contrato (índices, rangos, ISO, idempotencia, 409, CSV atómico con número de fila, encabezado exacto, líneas vacías al final ignoradas). `load_all` devuelve `{índice: {date: valor}}` con los tres índices siempre presentes. Las rutas ya existen (T3).
- **Tests:** alta 201; duplicado exacto 200 `created: false` sin fila nueva; mismo día otro valor 409 `field: "value"`; `value` = `"NaN"`/`1e309`/`11`/`-1.5` → 400; `USDMXN` 0 → 400; índice `"LIBOR"` → 400 `field: "index"`; CSV de 3 filas válidas → `inserted: 3`; recargarlo → `unchanged: 3`; CSV con una fila mala en la línea 3 → 400 con "Fila 3" y nada insertado; encabezado distinto → 400; listado filtrado por índice y rango de fechas.
- **Verificación:** `... -m pytest desk/api/tests/test_fixings.py -q | grep -E "passed|failed"` y suite completa sin `failed`.
- **Commit:** las dos rutas.

### T6 — Rodar un snapshot
- **Modelo:** haiku · **Depende de:** T3 · **Paralela con:** T4, T5 · **R:** R13 (MKT-LIVE solo lectura; rodar crea otro editable), base de R4
- **Archivos:** `desk/api/market.py` (solo la función `roll_snapshot`), `desk/api/tests/test_market_roll.py` (nuevo).
- **Pasos:** reemplazar el stub `roll_snapshot(conn, source_id, body)` de T3 siguiendo exactamente "Mercado — rodar" del contrato (usar `validation.text`/`body_object`, `date.fromisoformat` para `as_of`; insertar con `INSERT` y devolver `snapshot_payload(conn, nuevo)`). No cambiar ninguna otra función de `market.py`.
- **Tests:** rodar `MX-DEMO` a `2026-12-08` con id `D1` → 201, `as_of` nuevo, mismas `quotes` y `sources`, `read_only` false, `label` con "rodado al 2026-12-08"; `PUT` sobre `D1` funciona; id repetido → 409; id `MKT-LIVE` o con espacios → 400 `field: "id"`; `as_of` `"2026-13-01"` → 400; origen inexistente → 404. Si existe una prueba que siembra `MKT-LIVE` (ver `test_live_market.py`), rodarlo y comprobar que el original sigue respondiendo 409 al `PUT` y el nuevo 200.
- **Verificación:** `... -m pytest desk/api/tests/test_market_roll.py -q | grep -E "passed|failed"` y suite completa sin `failed`.
- **Commit:** las dos rutas.

### T7 — Valuación a fecha (envejecimiento) y valuación del portafolio
- **Modelo:** sonnet · **Depende de:** T4, T5, T6 · **R:** R3 (backend), R5 (PV 0 desde la terminación), R6 (PV escala), R7 (aviso por fijación faltante), R8 (vencida → PV 0), R9 (PV sin cambio en `MX-DEMO`), R10
- **Objetivo:** cada operación se valúa en el `as_of` del snapshot con su estado vigente; `irs` con el constructor envejecido de `qfpy` y fijaciones; los demás acortando el plazo.
- **Archivos:** `desk/api/valuation.py`, `desk/api/portfolio.py` (`valuation`, `trade_pv_mxn`), `desk/api/tests/test_valuation_aged.py` (nuevo), `desk/api/tests/test_portfolio.py` (ajustes de forma de fila).
- **Pasos:**
  1. `value_trade(trade, mkt, fixings)`: `st = lifecycle.state(trade, trade["events"], mkt.as_of)`; si `st.status != "viva"` → `pv = pv_mxn = 0`; aviso `expired_unexercised` solo si es opción `vencida` sin `exercise`. Si `viva`:
     - `irs`: calendario y factor acumulado según el Contexto; avisos `missing_fixing` con las fechas faltantes; `qfpy.OisSwap(notional, fixed_rate, start_days, pay_days, factor, side, curve)` con los `terms` vigentes; `pv = npv(mkt.env)`, `pv_mxn` = `pv × spot` si la curva es USD.
     - `fx_forward`, `fx_option`: `days = (maturity_date − as_of).days` sobre los `terms` vigentes y el `Product.pv_mxn` existente.
     - `equity_option`: `maturity_years = (maturity_date − as_of).days / 365`.
     - `swaption`: `expiry_years = (maturity_date − as_of).days / 365` (maturity = expiración), `swap_tenor_years` de los `terms`.
     - `cap_floor` y `bond` — **aproximación declarada, sin C++ nuevo**: con `días = (maturity_date − as_of).days`, `periods = ceil(días / period_days)` (cap/floor, `period_days` de la curva) o `ceil(días × frequency / 365)` (bono), y el `Product.pv_mxn` existente con ese `periods`; el caplet o cupón en curso ya fijado se omite (no se agrega nada por él). Se declara en Metodología; lo exacto queda para el corte 3.
     - Si `trade_date ≤ as_of < start_date` (inicio futuro): `irs` con `start_days > 0` y factor 1; los demás con su plazo total desde `as_of`.
  2. `portfolio.trade_pv_mxn(trade, mkt, fixings)` = `value_trade(...)["pv_mxn"]`. `portfolio.valuation`: carga `fixings.load_all(conn)` una vez y añade a cada fila `trade_date`, `start_date`, `maturity_date`, `status`, `warnings`, `notional` vigente; `pv` según D6.
  3. Los módulos `risk/*.py` llaman hoy `portfolio.trade_pv_mxn(trade, mkt)`: **no** tocarlos aquí; para no romperlos, dar a `fixings` un default `None` que cargue nada (dict vacío) y que T8 los actualice.
- **Tests:** **R9**: base de `build_corte1_db` → PV por fila == `golden_pv()` a 1e-8 relativo (ahora pasando por `value_trade`). **R10**: para `fx_forward` y `fx_option` de la semilla, `rows[i].pv == POST /api/price/<p>` con los mismos términos (1e-8 relativo) y `pv == pv_mxn`. **R8**: un `fx_forward` de 30 días valuado en un snapshot rodado 30 y 31 días → `vencida`, PV 0; una `fx_option` en las mismas fechas → `vencida`, PV 0 y aviso `expired_unexercised`. **`no_pactada`**: snapshot rodado a `as_of − 5` → todas `no_pactada`, PV 0 y total 0. **Aproximación de bono y cap**: en un snapshot rodado 40 días dan PV finito y el `periods` pasado es el `ceil` esperado. **R5**: `termination` en D → PV 0 en snapshot con `as_of ≥ D`, PV igual al de antes en un snapshot con `as_of < D`. **R6**: `quantity_change` ×2 del nocional en D → PV ×2 (1e-10 relativo) en `as_of ≥ D` e igual antes. **R7**: `irs` TIIE-F pactado en `MX-DEMO`, valuado en un snapshot rodado 10 días sin fijaciones → 200 con `warnings[0].code == "missing_fixing"` y 10 fechas; con las 10 fijaciones cargadas, sin avisos. **R3 (backend)**: `irs` a la par (tasa = `par_rate` de `/api/price`) en `MX-DEMO`; snapshot `D1` con `as_of + 14` y curva TIIE-F = curva de `MX-DEMO` desplazada 14 días (insertar la fila de snapshot por SQL con cotizaciones OIS **en cada pago restante** calculadas como `par_rate` de un `qfpy.OisSwap` sobre una `YieldCurve` desplazada construida como en T1, más las mismas cotizaciones SOFR); fijaciones = forwards diarios de la curva de `MX-DEMO`; PV en `D1` = `(PV_D0 − 0)/DF0(14/365)` a `1e-6 × nocional`.
- **Verificación:** `... -m pytest desk/api/tests/test_valuation_aged.py -q | grep -E "passed|failed"`; suite completa sin `failed`.
- **Commit:** las cuatro rutas.

### T8 — Riesgo solo sobre operaciones vivas
- **Modelo:** sonnet · **Depende de:** T7 · **Paralela con:** T9, T10 · **R:** R5 (fuera de DV01, escenarios y VaR), R8 (fuera de riesgo)
- **Archivos:** `desk/api/risk/dv01.py`, `desk/api/risk/scenarios.py`, `desk/api/risk/var.py`, `desk/api/tests/test_risk_lifecycle.py` (nuevo).
- **Pasos:** cargar `fixings.load_all(conn)` una vez por petición; filtrar `portfolio.load_trades(conn)` con `valuation.is_live(t, mkt.as_of)`; pasar `fixings` a `portfolio.trade_pv_mxn`. Nada más cambia en las formas de respuesta.
- **Tests:** terminar la operación 1 en `MX-DEMO.as_of` → `/api/risk/dv01` cambia en exactamente su contribución previa, el id 1 no aparece en `scenarios[*].trades` ni en `errors`; VaR recalculado ≠ anterior; un `fx_forward` vencido en un snapshot rodado no aparece; en un snapshot anterior a `trade_date` (`no_pactada`) no aparece ninguna operación y los totales son 0; en un snapshot con `as_of` anterior a la terminación todo es igual que antes (comparar con las respuestas previas a 1e-9).
- **Verificación:** suite backend completa sin `failed` (incluidos `test_risk_*.py` existentes).
- **Commit:** las cuatro rutas.

### T9 — Flujos liquidados, P&L y calendario de flujos de la ficha
- **Modelo:** sonnet · **Depende de:** T7 · **Paralela con:** T8, T10 · **R:** R4, R8 (liquidación del forward con FIX)
- **Archivos:** `desk/api/settlement.py` (incluye `trade_flows(conn, trade_id, snapshot_id) -> dict`, al que delega la ruta `GET /api/trades/<id>/flows` creada por T3), `desk/api/pnl.py`, `desk/api/tests/test_pnl.py` (nuevo), `desk/api/tests/test_flows.py` (nuevo).
- **Pasos:**
  1. `settled_flows(trade, fixings, d0, d1, fallback_spot)` (los montos ya fijados se calculan en Python; la composición de fijaciones, siempre con `qfpy.compound_overnight`):
     - `irs`: por cada pago con fecha en `(d0, d1]` y operación `viva` en esa fecha: fijo `N·K·τ` y flotante `N·(compound_overnight(fijaciones del periodo) − 1)` con los términos y el nocional vigentes en la fecha de pago (sin prorrateo), neto con el signo del lado; regla de fijación faltante → aviso. Moneda de la curva; USD → MXN con FIX `USDMXN` de la fecha de pago o, si falta, `fallback_spot` + aviso `fx_fallback`.
     - `fx_forward` con `maturity_date ∈ (d0, d1]` y `viva` el día anterior: `notional_usd × (FIX − strike)` con signo `buy +`/`sell −`, en MXN; sin FIX → `fallback_spot` + aviso.
     - `transfer` con `event_date ∈ (d0, d1]`: su `amount` (MXN).
     - `cap_floor`, `swaption`, `bond` con `maturity_date ∈ (d0, d1]`: sin flujo, aviso `no_settlement`.
  2. `compute_pnl(conn, from_id, to_id)` y su contrato; `pv_*` con `portfolio.trade_pv_mxn` sobre cada contexto. `trade_flows(...)` para `GET /api/trades/<id>/flows`.
- **Tests:** **R4 identidad**: semilla, `D1 = roll(MX-DEMO, +35 días)` → por fila `pnl == pv_to − pv_from + settled` (1e-6) y `Σ pnl == total_mxn`; `totals` cuadran. **R4 swap**: `irs` TIIE-F a la par en `MX-DEMO`, `D1` = `as_of + 28` con curva desplazada (mismo método que T7, cotizaciones en cada pago restante) y fijaciones = forwards diarios → `settled ≠ 0` y `|pnl| < 1e-6 × nocional`. **R8**: `fx_forward` de 20 días, FIX `USDMXN` cargado en su vencimiento, `D1 = +35` → `settled == notional × (FIX − strike)` y `status_to == "vencida"`; sin FIX → usa spot de `D1` y aviso `fx_fallback`. Terminación entre `from` y `to` → `settled` incluye el `amount`. Operación con `trade_date` dentro de la ventana → `pv_from == 0`, `status_from == "no_pactada"`. `quantity_change` a mitad de periodo → el cupón liquidado usa entero el nocional nuevo. `from` posterior a `to` → 400 `field: "to"`. Flujos de la ficha: un `irs` valuado en `D1` lista el cupón del día 28 como `settled` y los siguientes como `projected` con `pv`; `Σ pv projected == pv` de la valuación (1e-6).
- **Verificación:** `... -m pytest desk/api/tests/test_pnl.py desk/api/tests/test_flows.py -q | grep -E "passed|failed"`; suite completa sin `failed`.
- **Commit:** las cuatro rutas.

### T10 — Metodología del corte 2
- **Modelo:** haiku · **Depende de:** T1 (solo para no correr junto al C++; toca un único archivo y va en paralelo con todo lo demás) · **R:** R12
- **Archivos:** `desk/ui/src/screens/MethodologyScreen.tsx`.
- **Pasos:** nueva sección "Ciclo de vida y valuación a fecha" y actualizar "Límites de este corte" (quitar "las operaciones no envejecen entre snapshots"). Contenido, en español: qué se guarda como evento (`execution`, `quantity_change`, `terms_change`, `exercise`, `termination`, `transfer` de la liquidación) y qué se deriva (cupones pagados de swaps y liquidación al vencimiento de forwards FX, de términos + fijaciones; `reset` no se usa, las fijaciones viven en su tabla); la fecha de valuación es el `as_of` del snapshot; convención de días (días naturales, `t = días/365`, devengo ACT/360, fijaciones diarias capitalizadas, sin inhábiles); regla de fijación faltante (última publicada anterior o tasa a un día de la curva, con aviso); P&L = PV(to) − PV(from) + liquidado en `(from, to]`, en MXN al FIX o al spot de `to` con aviso; estados (`no_pactada`, `viva`, `vencida`, `terminada`, `ejercida`) y que solo las vivas entran a riesgo; una operación pactada dentro de la ventana del P&L entra con `pv_from = 0` (sin prima ni pago inicial); la swaption vence en su expiración y las opciones vencidas sin ejercicio registrado valen 0 con aviso; bono y cap/floor envejecidos con aproximación (periodos enteros restantes por `ceil`, se omite el cupón o caplet en curso ya fijado; lo exacto en el corte 3); tras un cambio de nocional a mitad de periodo el cupón usa el nocional vigente al pago; los importes de terminación y ejercicio van en MXN, positivos si cobra el tenedor; las operaciones no se borran, se terminan; lo que no se hace (lista "Fuera de alcance" del diseño: novaciones, asignaciones, compensación, calendarios y ajuste de fechas, ejercicio automático, liquidación de caps/floors, swaptions y bonos vencidos — salen con PV 0 y aviso —, historia automática de snapshots, división del paquete y textos compartidos de tablas, usuarios y aprobación).
- **Verificación:** `cd desk/ui && npm run build 2>&1 | tail -3` sin errores; `npm test` pasa.
- **Commit:** la ruta.

### U1 — Contrato en la interfaz: tipos, cliente, rutas y stubs
- **Modelo:** sonnet · **Depende de:** — (puede empezar en cuanto T1 termine; no depende del backend) · **R:** R11 (base)
- **Archivos:** `desk/ui/src/api/types.ts`, `desk/ui/src/api/client.ts`, `desk/ui/src/api/client.test.ts`, `desk/ui/src/App.tsx`, `desk/ui/src/screens/TradeScreen.tsx` (stub), `desk/ui/src/screens/PnlPanel.tsx` (stub), `desk/ui/src/screens/FixingsPanel.tsx` (stub), `desk/ui/src/screens/PortfolioScreen.tsx` (solo montar la pestaña P&L con `<PnlPanel />`), `desk/ui/src/screens/MarketScreen.tsx` (solo montar `<FixingsPanel />`).
- **Pasos:** transcribir a TS el contrato nuevo del Contexto (`TradeStatus` incluye `no_pactada`; `Warning.code` incluye `expired_unexercised`; `createTrade` acepta además `snapshot`); funciones del cliente; ruta `/portafolio/:id`; stubs; montar sin cambiar nada más de esas pantallas.
- **Tests:** `client.test.ts`: `postEvent` envía `POST /api/trades/3/events` con el cuerpo; `importFixingsCsv('a')` envía `{"csv":"a"}`; `pnl('A','B')` llama `/api/pnl?from=A&to=B`; 409 → `ApiError` con `status 409`.
- **Verificación:** `cd desk/ui && npm test 2>&1 | tail -5 && npm run build 2>&1 | tail -5` sin errores.
- **Commit:** las rutas listadas.

### U2 — Selector con fecha de valuación
- **Modelo:** haiku · **Depende de:** U1 · **Paralela con:** U3–U8 · **R:** R11 (fecha visible en el selector)
- **Archivos:** `desk/ui/src/components/Shell.tsx`, `desk/ui/src/components/Shell.test.tsx`.
- **Pasos:** cada `<option>` del selector de snapshot muestra `"<label> · <as_of>"`; el rótulo del campo pasa de "Snapshot" a "Fecha de valuación". Nada más.
- **Tests:** con dos snapshots simulados, las opciones contienen sus `as_of`.
- **Verificación:** `npm test` y `npm run build` sin errores.
- **Commit:** las dos rutas.

### U3 — Alta de operación con fechas (pricer)
- **Modelo:** sonnet · **Depende de:** U1 · **Paralela con:** U2, U4–U8 · **R:** R11 (alta con fechas)
- **Archivos:** `desk/ui/src/screens/pricers/PricerForm.tsx`, `desk/ui/src/screens/pricers/PricerForm.css`, `desk/ui/src/screens/pricers/PricerForm.test.tsx`.
- **Pasos:** junto a "Contraparte", tres `<input type="date">`: "Fecha de pacto", "Inicio", "Vencimiento". Pacto e inicio prellenados con el `as_of` del snapshot activo; vencimiento vacío = se deriva del plazo del formulario (texto de ayuda: "Vacío: se calcula con el plazo"). "Agregar al portafolio" envía `trade_date`, `start_date` y, si no está vacío, `maturity_date`. `ApiError.field` de una fecha se muestra bajo esa fecha. Tras crear, mostrar la `maturity_date` devuelta (en `irs` puede venir ajustada al periodo; rotular "Vencimiento ajustado" si difiere de la capturada) y enlace "Ver ficha" a `/portafolio/<id>`.
- **Tests:** `createTrade` recibe las tres fechas; error 400 `field: "maturity_date"` aparece bajo Vencimiento; sin vencimiento no se envía la clave.
- **Verificación:** `npm test` y `npm run build` sin errores.
- **Commit:** las tres rutas.

### U4 — Ficha de operación
- **Modelo:** sonnet · **Depende de:** U1 · **Paralela con:** U2, U3, U5–U8 · **R:** R11 (línea de tiempo, calendario liquidado/proyectado, terminar y cambiar nocional)
- **Archivos:** `desk/ui/src/screens/TradeScreen.tsx`, `desk/ui/src/screens/TradeScreen.css` (nuevo), `desk/ui/src/screens/TradeScreen.test.tsx` (nuevo).
- **Pasos:** lee `:id`; carga `getTrade(id)`, `tradeState(id, snapshot.as_of)` y `tradeFlows(id, snapshotId)`; se recarga al cambiar de snapshot. Encabezado: producto, contraparte, fechas, estado (rótulo del Contexto) y nocional vigente. Línea de tiempo vertical de eventos (fecha, tipo en español, datos clave). Calendario de flujos (tabla): fecha, tipo, monto, moneda, DF, PV, con "Liquidado"/"Proyectado" diferenciado por texto y estilo; avisos arriba. Acciones (solo si el estado es `viva`; con `no_pactada` se muestra "No pactada a esta fecha"): "Terminar anticipadamente" (fecha + importe MXN) y "Cambiar nocional" (fecha + nuevo nocional) → `postEvent` → recarga; errores por campo bajo el input; 409 como banner. Enlace "Volver al portafolio".
- **Tests:** con mocks: aparecen los eventos en orden; un flujo `settled` y uno `projected` se rotulan distinto; "Terminar" llama `postEvent(id, {type:'termination', event_date, data:{amount}})`; con estado `terminada` no hay botones de acción.
- **Verificación:** `npm test` y `npm run build` sin errores.
- **Commit:** las tres rutas.

### U5 — Blotter con estado y filtro
- **Modelo:** sonnet · **Depende de:** U1 · **Paralela con:** U2–U4, U6–U8 · **R:** R11 (filtro por estado), R10 (presentación)
- **Archivos:** `desk/ui/src/screens/PortfolioScreen.tsx`, `desk/ui/src/screens/PortfolioScreen.css`, `desk/ui/src/screens/PortfolioScreen.test.tsx`.
- **Pasos:** columnas nuevas "Pacto", "Vencimiento" (ya existe: usar `maturity_date`), "Estado"; filtro por estado (selector "Todas / No pactada / Viva / Vencida / Terminada / Ejercida", default "Todas") que filtra filas en el cliente; el total mostrado sigue siendo `total_mxn` del backend; filas con `warnings` marcadas con el texto en tooltip; el id enlaza a `/portafolio/<id>`; la columna PV indica la moneda de `pv` (MXN para FX). **Quitar el botón de borrar** de cada fila (con su confirmación y la llamada a `deleteTrade`); las operaciones se terminan desde la ficha. No tocar la pestaña P&L (montada por U1).
- **Tests:** filtrar "Terminada" deja solo esas filas; el id es un enlace a la ficha; no hay botón de borrar (ajustar o quitar los tests existentes del borrado).
- **Verificación:** `npm test` y `npm run build` sin errores.
- **Commit:** las tres rutas.

### U6 — Vista de P&L
- **Modelo:** sonnet · **Depende de:** U1 · **Paralela con:** U2–U5, U7, U8 · **R:** R11 (P&L con total que cuadra)
- **Archivos:** `desk/ui/src/screens/PnlPanel.tsx`, `desk/ui/src/screens/PnlPanel.css` (nuevo), `desk/ui/src/screens/PnlPanel.test.tsx` (nuevo).
- **Pasos:** dos selectores de snapshot ("Desde", "Hasta", mostrando `label · as_of`; "Hasta" por defecto el snapshot activo, "Desde" el de `as_of` anterior más cercano si existe); botón "Calcular" → `pnl(from, to)`; tabla AG Grid por operación (id, producto, contraparte, estado desde/hasta, PV desde, PV hasta, Liquidado, P&L) con fila fija de total (`totals`); avisos por fila en tooltip; errores del backend junto al selector correspondiente.
- **Tests:** con mock, la fila total muestra `totals.pnl` y la suma de las filas sin error es igual al total; error 400 `field: "to"` aparece junto a "Hasta".
- **Verificación:** `npm test` y `npm run build` sin errores.
- **Commit:** las tres rutas.

### U7 — Pantalla de fijaciones
- **Modelo:** sonnet · **Depende de:** U1 · **Paralela con:** U2–U6, U8 · **R:** R11 (fijaciones con alta y CSV)
- **Archivos:** `desk/ui/src/screens/FixingsPanel.tsx`, `desk/ui/src/screens/FixingsPanel.css` (nuevo), `desk/ui/src/screens/FixingsPanel.test.tsx` (nuevo).
- **Pasos:** filtro por índice (TIIE-F, SOFR, USDMXN) y rango de fechas → `listFixings`; tabla (índice, fecha, valor; tasas en % con 4 decimales, USDMXN con 4 decimales); formulario de alta (índice, fecha, valor en % para tasas y en MXN para USDMXN; envía decimal) → `addFixing`, muestra "Ya existía" si `created: false`; carga CSV con `<input type="file" accept=".csv">` (lee el texto con `File.text()`) o pegado en `<textarea>` → `importFixingsCsv`; muestra "insertadas / sin cambio" y los errores 400/409 del backend tal cual.
- **Tests:** alta envía `{index:'TIIE-F', date, value: 0.0701}` al capturar `7.01`; el CSV pegado se envía tal cual; un 409 se muestra.
- **Verificación:** `npm test` y `npm run build` sin errores.
- **Commit:** las tres rutas.

### U8 — Botón "Rodar" en Mercado
- **Modelo:** haiku · **Depende de:** U1 · **Paralela con:** U2–U7 · **R:** R11 ("rodar" snapshot), R13 (rodar `MKT-LIVE` crea uno editable)
- **Archivos:** `desk/ui/src/screens/MarketScreen.tsx`, `desk/ui/src/screens/MarketScreen.css`, `desk/ui/src/screens/MarketScreen.test.tsx`.
- **Pasos:** botón "Rodar…" en la cabecera de Mercado (visible también en `MKT-LIVE`) que abre un formulario en línea con "Id nuevo" y "Fecha de valuación" → `rollSnapshot(snapshotId, {id, as_of})` → `reload()` del contexto y `setSnapshotId(nuevo)`; errores por campo bajo su input. No tocar la sección de fijaciones (montada por U1).
- **Tests:** con mock, enviar el formulario llama `rollSnapshot('MX-DEMO', {id:'D1', as_of:'2026-12-08'})` y luego selecciona `D1`; error 409 `field: "id"` aparece bajo "Id nuevo".
- **Verificación:** `npm test` y `npm run build` sin errores.
- **Commit:** las tres rutas.

### T11 — Integración contra el backend real y capturas
- **Modelo:** sonnet · **Depende de:** todas · **R:** R11 (capturas, 1280 px), R13 (suites), verificación de R1–R10 de punta a punta
- **Archivos:** ninguno nuevo; solo correcciones puntuales donde falle algo (commit de esas rutas). Capturas en `/tmp/fableorchestrate/qf-corte2/shots/` (no se commitean).
- **Pasos:**
  1. Las cuatro suites del Contexto → todas en verde (ctest ≥ 396 + nuevos).
  2. Migración real: `build_corte1_db('/tmp/fableorchestrate/qf-corte2/it.db')`; `cd desk/ui && npm run build`; arrancar el backend en **5071** con esa base (comando del Contexto) en segundo plano; esperar el puerto. Detener y volver a arrancar (dos arranques); `curl -s localhost:5071/api/trades | python -c "import sys,json; print(len(json.load(sys.stdin)['trades']))"` → `7`.
  3. Recorrido por `curl` (guardar respuestas en `/tmp/fableorchestrate/qf-corte2/it/`): rodar `MX-DEMO` a `+35` días (`D1`); cargar por CSV fijaciones TIIE-F diarias de `MX-DEMO.as_of` a `D1.as_of − 1` y un FIX `USDMXN`; crear un `fx_forward` de 20 días y un `irs` con fechas; `quantity_change` y `termination` sobre operaciones de la semilla; `GET /api/portfolio/valuation?snapshot=D1` (estados variados, sin errores), `/api/pnl?from=MX-DEMO&to=D1` (total = suma de filas), `/api/risk/dv01|scenarios|var` con `D1` (200, sin la terminada), `GET /api/trades/<id>/flows?snapshot=D1` (liquidados y proyectados).
  4. Capturas a 1280×800 con `google-chrome --headless=new --window-size=1280,800 --screenshot=<png> http://localhost:5071/<ruta>` de: `/mercado` (selector con fecha, botón Rodar, fijaciones), `/pricers/irs` (fechas de alta), `/portafolio` (estado y filtro) y su pestaña P&L, `/portafolio/<id>` (ficha con línea de tiempo y flujos), `/metodologia`. Como el snapshot activo se elige en la interfaz, si hace falta navegar por pasos usar las herramientas de navegador disponibles (Claude in Chrome) en lugar de nuevas dependencias. Revisar cada captura con `Read`: sin scroll horizontal ni texto cortado; si no hay forma de comprobarlo, reportarlo como no verificado.
  5. Detener el servidor (`kill` del PID guardado; nunca `pkill -f`). `git status --short` limpio salvo `graphify-out/`.
  6. El último commit (correcciones o `git commit --allow-empty -m "test(desk): integración del corte 2 ..."`) se hace **sin** `GRAPHIFY_SKIP_HOOK` para que el hook regenere el grafo una vez; no añadir los cambios de `graphify-out/` salvo que Fable lo pida.
- **Verificación:** reporte con cada comando y su resultado, rutas de las capturas y lista de correcciones.

---

## Orden y paralelismo

```
T1 (C++, sola)
 └─ T2 ── T3 ──┬─ T4 ─┐
               ├─ T5 ─┼─ T7 ──┬─ T8
               └─ T6 ─┘       ├─ T9
                              (T10 en cualquier momento tras T1)
 └─ U1 ──┬─ U2, U3, U4, U5, U6, U7, U8 (paralelas, archivos disjuntos)
                                                     └────────── T11 (tras todo)
```
U1–U8 no tocan backend y pueden correr junto a T2–T9 (archivos disjuntos). T10 solo toca `MethodologyScreen.tsx`.

## Cobertura de requisitos

| R | Tareas |
|---|---|
| R1 | T3, T4 |
| R2 | T4 |
| R3 | T1, T7 |
| R4 | T9 (T6 base) |
| R5 | T4, T7, T8 |
| R6 | T4, T7 |
| R7 | T5, T7 |
| R8 | T7, T8, T9 |
| R9 | T2, T3, T7 |
| R10 | T7, U5 |
| R11 | U1–U8, T11 |
| R12 | T10 |
| R13 | T1, T3, T6, U8, T11 |

## Preguntas para Fable

P1–P10 están resueltas en "Aclaraciones de Fable al plan" del diseño y ya forman parte del Contexto y de T3, T4, T7, T8, T9, T10, U4 y U5. El método de la curva desplazada (R3/R4) quedó aceptado.

- P11 respondida: `cap_floor` y `bond` siguen la regla de `irs` (ver Convenciones). No queda nada abierto.

## T12 — Correcciones tras la auditoría (decisiones de Fable) — modelo sonnet

Auditoría de Opus: R1–R13 CUMPLE, sin defectos medios ni altos. Estas correcciones cierran los defectos bajos y dos huecos de la integración. Cada una con su test. Un commit por bloque (backend / interfaz), `git commit -- <rutas>`, `GRAPHIFY_SKIP_HOOK=1`.

**Backend (`desk/api`)**
1. **Fines de semana no son fijaciones faltantes.** Las tasas a un día solo se publican en días hábiles: la del viernes devenga 3 días. En el factor acumulado (`valuation._accrued_factor` y su uso en `settlement.py`), sábado y domingo no se esperan: se agrupan con la fijación del día hábil anterior (días = 3 el viernes) y **no** generan `missing_fixing`. Solo un día de lunes a viernes sin fijación avisa (los feriados seguirán avisando hasta el corte 3; se declara). Si la carga trae una fijación en sábado o domingo, se usa tal cual. Tests: periodo que cruza un fin de semana con fijaciones solo en hábiles → sin aviso y factor == `compound_overnight` con días [1,1,1,1,3]; un miércoles faltante → aviso solo con esa fecha. R3/R4 deben seguir pasando (ajustar las fijaciones de esos tests si hace falta, sin relajar tolerancias).
2. **Rótulo al rodar:** si el rótulo del origen ya termina en ` · rodado al AAAA-MM-DD`, ese sufijo se reemplaza en vez de encadenarse.
3. **Alta de `irs` sin `fixed_rate`:** `create_trade` fija `fixed_rate` a la tasa par del swap con el snapshot de la petición (o `MX-DEMO`), de modo que la operación nace a la par y queda guardada con su tasa. La respuesta devuelve `params.fixed_rate`. Test: PV en la fecha de pacto ≈ 0 (1e-6 × nocional).
4. **CSV de fijaciones:** tolerar BOM UTF-8 al inicio y fin de línea `\r\n`.
5. **`events.post_event`:** operación sin eventos → error controlado (409 con mensaje), no 500.
6. Quitar el test esqueleto vacío de `test_trades_dates.py` (`STUB_ROUTES` y su test) si ya no cubre nada.
7. **Sin duplicación:** que `valuation.py` exponga con nombre público lo que `settlement.py` importa como privado (`_accrued_factor`, `_shortened`) y una función que arme el `OisSwap` envejecido, y que `settlement.py` la use en vez de repetir las ~12 líneas.

**Interfaz (`desk/ui`)**
8. P&L y blotter muestran el nombre del producto con los mismos rótulos en español de Pricers (no `irs`, `fx_forward`).
9. Blotter filtrado con 0 filas: un solo mensaje («Ninguna operación con ese estado»). La fila de total se rotula «Total del portafolio» cuando hay filtro activo.
10. Ficha: si la operación tiene un evento `termination` o `exercise` (en cualquier fecha), no se ofrecen acciones; en su lugar, una línea «Terminada el AAAA-MM-DD» / «Ejercida el AAAA-MM-DD». El encabezado «Acciones» no aparece vacío.
11. Nunca mostrar `-0.00`: el formateador de montos normaliza el cero negativo.
12. Metodología: la aproximación de bono y cap/floor se describe como es («se valúan con el número de periodos enteros restantes; dentro de un periodo no envejecen; tratamiento exacto en el corte 3»); añadir la regla de fines de semana y que los feriados aún avisan; el alta de un swap sin tasa fija nace a la par.

**Documentación**
13. `CLAUDE.md` del repo: actualizar el conteo de tests (ctest 402) y añadir una sección corta de QF Desk (qué es, `desk/run.sh`, las cuatro suites, dónde están diseño/plan/roadmap).

**Verificación:** las cuatro suites del Contexto sin fallos; reportar conteos.
