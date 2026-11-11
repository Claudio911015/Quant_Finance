# Plan: QF Desk — Corte 5 (operaciones: flujos, confirmaciones, FpML, conciliación)

Diseño: `/tmp/fableorchestrate/qf-corte5/design.md` (copia en el repo: `docs/superpowers/qf-desk/corte5/`). Worktree **`/home/claudio/Git/qf-wt/corte5`**, rama **`corte5`** (creada desde `feat/qf-desk`, base `ce51edf`). Base de código: cortes 1, 2 y 4 auditados.

## Contexto

Todo implementador lee esta sección completa y **solo su tarea**. Lo que sigue es decisión: donde el diseño dejaba un hueco, el planificador eligió y lo dejó en "Supuestos del planificador" (al final). Si encuentras otro hueco, elige lo más conservador, hazlo y anótalo en "Anotado por los implementadores".

### Entorno
- **Directorio de trabajo único:** `/home/claudio/Git/qf-wt/corte5` (worktree propio, rama `corte5`). Todo comando se corre desde ahí (salvo vitest/npm, desde `desk/ui`). **No tocar** `/home/claudio/Git/Quant_Finance` ni otros worktrees (`/home/claudio/Git/qf-wt/*` distintos de `corte5`): otros cortes avanzan en paralelo allí. Nunca push, merge, rebase ni `git stash`.
- **Python del backend:** `/home/claudio/anaconda3/bin/python` (3.8.18; Flask 2.3.3, pytest 8.2.0; Flask vive en `~/.local`: ejecutar sin `-I`). Sintaxis 3.8: nada de `match`, `X | Y`, `list[int]`/`dict[str, x]` evaluados en tiempo de ejecución; usar `typing`. **Sin paquetes nuevos** (ni Python ni npm). FpML solo con `xml.etree.ElementTree` de la biblioteca estándar.
- **Node** 22, **npm** 10. Interfaz en `desk/ui` (Vite + React 18 + TS, AG Grid, ECharts, react-router-dom, vitest + jsdom). `desk/ui/node_modules` ya está instalado: no correr `npm install`.
- **No hay C++ en este corte.** Este worktree no tiene árbol de CMake: `build/src/` contiene solo `qfpy.cpython-38-x86_64-linux-gnu.so` ya compilado, suficiente para el backend (`from desk.api.qf import qfpy`). **Nadie compila C++, corre `cmake` ni `ctest`**, ni toca `include/`, `src/`, `tests/*.cpp`, `CMakeLists.txt`, `build/`.
- **Suites** (desde la raíz del worktree salvo la interfaz):
  - C++: **no se corre aquí** (no hay árbol de CMake ni cambios C++). T7 comprueba que no hay cambios: `git diff --stat ce51edf -- include src CMakeLists.txt 'tests/*.cpp' | tail -1` → vacío.
  - Bindings Python (lo que corre el target `pytests`): `/home/claudio/anaconda3/bin/python -m unittest discover -s tests -p "test_*.py" 2>&1 | grep -E "^Ran|^OK|FAILED"` → `Ran 56 tests` y `OK`.
  - Backend: `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q 2>&1 | grep -E "passed|failed"` → `N passed`, sin `failed` (hoy se recolectan **2335**; no usar `tail`: un warning de pytest_asyncio sale tras el resumen).
  - Interfaz: `cd desk/ui && npm test 2>&1 | tail -5` (vitest run) y `npm run build 2>&1 | tail -5` (`tsc -b && vite build`) sin errores. La cuenta la da su salida.
- **Puertos y procesos de este corte:** backend de prueba **solo en 5085**; Chrome headless **solo en 9345** con perfil `/tmp/fableorchestrate/qf-corte5/chrome-profile`. 5070 es el desk de Claudio y los demás puertos son de otros cortes: no usarlos. Todo lo que se levante se apaga con `kill <PID>` (nunca `pkill -f`). Base temporal de integración: `/tmp/fableorchestrate/qf-corte5/it.db`. Arranque: `cd /home/claudio/Git/qf-wt/corte5 && /home/claudio/anaconda3/bin/python -c "from desk.api.app import create_app; create_app(db_path='/tmp/fableorchestrate/qf-corte5/it.db').run(host='127.0.0.1', port=5085)"`. La interfaz construida (`desk/ui/dist`) la sirve el mismo Flask.
- **No tocar** `~/Git/MarketDataFeed`, `desk/data/`, `graphify-out/`.

### Reglas de ejecución y commits
- Un commit por tarea, solo de tus rutas: `git add <rutas> && GRAPHIFY_SKIP_HOOK=1 git commit -m "<tipo>(desk): <por qué>" -- <rutas>`. Nunca `git add -A`/`.`. Autor: configuración global (Claudio). **Sin `Co-Authored-By`** ni otra línea de atribución. Mensaje en español que explique el porqué.
- Si `git commit` falla por `.git/index.lock` (el índice del worktree), esperar y reintentar; no borrar el lock salvo > 1 min sin proceso git vivo.
- **Archivos compartidos con otros cortes** (`desk/api/db.py`, `desk/api/app.py`, `desk/api/events.py`, `desk/api/settlement.py`, `desk/ui/src/App.tsx`, `desk/ui/src/components/Shell.tsx`, `desk/ui/src/screens/MethodologyScreen.tsx`, `desk/ui/src/screens/TradeScreen.tsx`, `desk/ui/src/screens/PortfolioScreen.tsx`, `desk/ui/src/api/types.ts`, `desk/ui/src/api/client.ts`): cambios mínimos, en un bloque contiguo delimitado por comentarios `# --- corte 5 ---` / `# --- fin corte 5 ---` (`// --- corte 5 ---` en TS; `{/* corte 5 */}` en JSX), añadido al final cuando se pueda; **sin reordenar ni reformatear** lo existente. `types.ts` y `client.ts` **no se tocan** en este corte (todo va en `opsTypes.ts`/`opsClient.ts`). Lo propio del corte va en módulos nuevos.
- Python valida, orquesta, suma/resta, convierte USD→MXN y persiste; **no hay fórmulas de pricing nuevas** (toda valuación por `valuation.value_trade`, `valuation.aged_swap`, `PRODUCTS[...]`). La búsqueda de Newton de la conciliación solo llama a la valuación existente. TS solo presenta.
- Validación en la frontera con `desk/api/validation.py`: `body_object()`, `number(d, name, gt=, ge=, lt=, le=, required=, default=)`, `integer(d, name, ge=, le=, required=)`, `choice(d, name, options, default=)`, `text(d, name, required=)`, `iso_date(d, name, required=True) -> date | None`, `finite_number(v)`, `has_non_finite(obj)`, `ensure_finite(payload)` (400 si hay no finitos), `MAX_AMOUNT = 1e13`, `NON_FINITE_MESSAGE`. Toda respuesta JSON numérica pasa por `ensure_finite`.
- Errores: `ApiError(status, mensaje_en_español, field)` (`desk/api/errors.py`) → `{"error", "field"}`; `field` = la clave tal como va en el cuerpo/consulta, sin prefijos. `NotImplementedError` → 501 (handler existente); `ValueError`/`RuntimeError` → 400 "No se pudo valuar: …". Una respuesta 4xx no deja nada escrito (la ruta solo hace `commit` al final del éxito).
- Sin flags, opciones, columnas ni pantallas no pedidas. Textos de interfaz en español.

### Convenciones heredadas (fijas)
- Fechas ISO `YYYY-MM-DD`, días naturales, sin calendario de inhábiles. **Fecha de valuación = `as_of` del snapshot.** "Día hábil" en este corte = lunes a viernes (sin feriados).
- Estado a la fecha `D` (`lifecycle.state`): `no_pactada` > `terminada` > `ejercida` > `vencida` (`D ≥ maturity_date`) > `viva`. Solo `viva` tiene PV ≠ 0.
- Flujos liquidados (`settlement.settled_flows`): un pago con fecha `P` está liquidado si la operación seguía `viva` el día `P − 1`. Signo de todo monto: **positivo = la empresa cobra**.
- Productos y `params` (forma guardada, ya validada):
  - `irs`: `{curve: "TIIE-F"|"SOFR", side: "payer"|"receiver", notional, periods, fixed_rate}` (`payer` = paga fija). `CURVES = {"TIIE-F": {"currency": "MXN", "period_days": 28}, "SOFR": {"currency": "USD", "period_days": 365}}`. `maturity_date = start + periods × period_days`. Cupones ACT/360, flotante = capitalización diaria de las fijaciones (`qfpy.compound_overnight`), fechas de pago `start + k` para `k` en `qfpy.ois_payment_days(días, period_days)`.
  - `fx_forward`: `{side: "buy"|"sell", notional_usd, strike, days}`, liquida por diferencias en MXN al vencimiento: `notional_usd × (FIX − strike)` (× −1 si `sell`).
  - `fx_option`: `{side: "buy"|"sell", option_type: "call"|"put", notional_usd, strike, days}` (vol de la superficie del snapshot).
  - `cap_floor`: `{curve, cap_type: "cap"|"floor", notional, strike, periods}`. `swaption`: `{curve, swaption_type: "payer"|"receiver", notional, strike, expiry_years, swap_tenor_years}` (`maturity_date` = expiración). `bond`: `{curve (default "TIIE-F"), face, coupon_rate, periods, frequency (default 2.0)}`. `equity_option`: `{option_type, spot, strike, volatility, rate, dividend_yield, maturity_years, quantity (default 1.0)}`.
  - `lifecycle.NOTIONAL_FIELD = {"irs": "notional", "cap_floor": "notional", "swaption": "notional", "fx_forward": "notional_usd", "fx_option": "notional_usd", "bond": "face", "equity_option": "quantity"}`.
- Alta de operación `POST /api/trades` (`portfolio.create_trade(conn, body)`): `{"product", "counterparty", "params", "trade_date"?, "start_date"?, "maturity_date"?, "snapshot"?}`; con `maturity_date` manda la fecha (`fit_to_maturity`: `irs` redondea `periods` y ajusta el vencimiento; FX fija `days = maturity − start`); un `irs` sin `fixed_rate` nace a la par. Devuelve `public_trade`.

### Firmas existentes que se usan (reales)
- `desk/api/db.py`: `SCHEMA` (script `CREATE … IF NOT EXISTS`), `init_schema(conn)` (lo ejecuta en cada arranque: tablas nuevas aparecen solas en bases existentes), `get_conn()`, `now_iso()`, `connect(path)`.
- `desk/api/app.py`: `create_app(db_path=None, seed=True)`; registra blueprints con `for module in (market, price, trades, risk, fixings, pnl, hedges): app.register_blueprint(module.bp)`.
- `desk/api/portfolio.py`: `load_trades(conn)` y `get_trade(conn, id)` (404 `field:"id"`) → `{"id","product","counterparty","trade_date","start_date","maturity_date" (date),"params","created_at","events"}`; `public_trade(trade)` (`notional`/`currency` de origen); `create_trade(conn, body) -> public_trade` (sin commit); `fit_to_maturity(product, params, start, maturity)`; `counterparty_id(conn, name)`.
- `desk/api/events.py`: `load_events(conn, trade_id)`, `insert_event(conn, trade_id, type, event_date: date, data) -> event` (sin commit; `type` ∈ `lifecycle.EVENT_TYPES`, incluye `"transfer"`), `public_event(e)`, `post_event(conn, trade_id, body)` (hoy rechaza `transfer` con 400 `type` y exige orden cronológico con 409 `event_date`), `API_EVENT_TYPES`.
- `desk/api/lifecycle.py`: `state(trade, events, on) -> {"status","terms","notional"}`; `EVENT_TYPES`; `NOTIONAL_FIELD`.
- `desk/api/valuation.py`: `value_trade(trade, mkt, fixings=None) -> {"status","notional","currency","pv","pv_mxn","warnings"}` (`pv` en MXN para FX y opciones de renta variable, en la moneda de la curva para el resto; `pv_mxn` siempre MXN); `aged_swap(trade, terms, mkt, fixings, warnings) -> qfpy.OisSwap`; `normalized(trade) -> (Product, params)`; `is_live(trade, on)`.
- `desk/api/settlement.py`: `settled_flows(trade, fixings, d0, d1, fallback_spot, mkt=None) -> (flows, warnings)` (ventana `(d0, d1]`; cada flujo `{"date","kind": "coupon"|"settlement"|"transfer","amount","currency","amount_mxn"}`; hoy **suma todos** los `transfer` de la operación); `trade_flows(conn, trade_id, snapshot_id)` (liquidados desde `trade_date − 1` hasta `as_of` + proyectados de `irs` y `bond` vivos, con `df` y `pv`); `_projected_irs(trade, terms, mkt, fixings, warnings)` y `_projected_bond(trade, terms, mkt)` (privadas: las reusa `ops_cashflows` importándolas; filas `{"date","kind":"coupon","status":"projected","amount","currency","df","pv"}`); `merge_warnings(*groups)`.
- `desk/api/pnl.py`: `compute_pnl(conn, from_id, to_id)` (filas con `id`, `pnl`; `pnl = pv_to − pv_from + Σ settled_flows`).
- `desk/api/market.py`: `load_context(conn, snapshot_id) -> MarketContext` (404 `field:"snapshot"`); `MarketContext(snapshot_id, as_of, curves, pillars, spot, surface, hw, factors)` con atributos homónimos y `env`; `mkt.shifted(curve=None, pillar_shifts_bp=None, parallel_bp=None, spot_pct=0.0) -> MarketContext` (copia; `spot × (1 + spot_pct/100)`); `list_snapshots(conn)` (cada uno con `id`, `as_of`, …); `CURVES`; `PAIR = "USDMXN"`.
- `desk/api/fixings.py`: `load_all(conn) -> Dict[str, Dict[date, float]]` (índices `TIIE-F`, `SOFR`, `USDMXN`).
- `desk/api/pricing/__init__.py`: `PRODUCTS[name]` con `.validate(params)`, `.price(params, mkt)`, `.pv_mxn(params, mkt)`, `.describe(params, as_of) -> {"notional","currency","maturity"}`.
- `desk/api/routes/trades.py`: `_trade_id(raw) -> int` (404 `field:"id"` si no es entero o fuera de rango; `routes/ops.py` lo importa, no lo copia).
- Pruebas: fixtures `app`, `client` de `desk/api/tests/conftest.py` (base temporal sembrada con `MX-DEMO`, `as_of = 2026-11-10` (martes), y 7 operaciones: id 1 `irs` TIIE-F payer 500e6 26 periodos K 6.80 % Banco Alfa; 2 `irs` TIIE-F receiver 250e6 Banco Beta; 3 `irs` SOFR payer 20e6 Banco Gamma; 4 `fx_forward` buy 10e6 Banco Alfa; 5 `fx_forward` sell 3e6 Banco Beta; 6 `fx_option` buy call 5e6 Banco Gamma; 7 `cap_floor` cap 300e6 Banco Alfa; contrapartes `"Banco Alfa (sintético)"`, `"Banco Beta (sintético)"`, `"Banco Gamma (sintético)"`); `empty_portfolio(client)`, `insert_raw_trade(app, product, terms_text)`. `desk/api/tests/hedge_fixture.py`: `roll(client, source, new_id, days) -> as_of ISO`, `load_fixings(client, index, start: date, end: date, value)` (un valor por día hábil en `[start, end)`), `par_irs(client, curve, notional, start, maturity, side="payer", snapshot="MX-DEMO") -> trade`, `market_forward(client, side, notional_usd, maturity, snapshot="MX-DEMO") -> trade`. Rodar snapshot: `POST /api/market/MX-DEMO/roll {"id":"D1","as_of":"2026-12-15"}`. Fijaciones: `POST /api/fixings/csv {"csv":"index,date,value\nTIIE-F,2026-11-10,0.07\n..."}`.
- Interfaz: `src/api/client.ts` (`ApiError {status, field}` exportada; `request<T>` es **privada**: no se exporta ni se toca), `src/api/types.ts` (`ProductId`, `Trade`, `TradeDetail`, `TradeEvent`, `Warning`, `FlowKind`…), `src/lib/format.ts` (`fmtNumber(v, dec)`, `fmtMoney(v, ccy)`, `fmtRate(dec)`, `fmtDate(iso)`), `src/state/SnapshotContext.tsx` (`useSnapshot() -> {snapshotId, setSnapshotId, snapshot, snapshots, reload, error}`), `src/components/Shell.tsx` (`NAV_ITEMS` `{to, label, icon}` con `Icon` SVG de 16 px; la paleta de comandos los toma de ahí; clases `shell__sidebar`, `shell__topbar`, `shell__main`; hoy: Mercado, Pricers, Portafolio, Riesgo, Coberturas, Metodología), `src/screens/MethodologyScreen.tsx` (secciones `Section {id, title, items: {label, text}[]}` pintadas con `SectionBlock`; grupos `PRODUCT_SECTIONS`, `GENERAL_SECTIONS`, `HEDGE_SECTIONS`, luego `LIMITS`; test con helper `row(label)` sobre `<dt>`), `src/screens/HedgeReportScreen.css` (patrón `@media print` que oculta `.shell__sidebar`/`.shell__topbar` y deja `.shell__main` sin padding: copiarlo). Tests de UI con `vi.mock('../api/client')`/`vi.mock('../../api/opsClient')` como en `PortfolioScreen.test.tsx`/`TradeScreen.test.tsx`.

### Esquema SQLite nuevo (lo agrega T1 al final de `db.SCHEMA`, en bloque `corte 5`)
```sql
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS trade_refs (trade_id INTEGER PRIMARY KEY REFERENCES trades(id), ref TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reconciliations (id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id TEXT NOT NULL, as_of TEXT NOT NULL, counterparty TEXT NOT NULL, tolerance REAL NOT NULL,
  csv TEXT NOT NULL, summary TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS reconciliations_no_update BEFORE UPDATE ON reconciliations BEGIN SELECT RAISE(ABORT, 'reconciliations es solo de inserción'); END;
CREATE TRIGGER IF NOT EXISTS reconciliations_no_delete BEFORE DELETE ON reconciliations BEGIN SELECT RAISE(ABORT, 'reconciliations es solo de inserción'); END;
CREATE TABLE IF NOT EXISTS reconciliation_rows (id INTEGER PRIMARY KEY AUTOINCREMENT,
  reconciliation_id INTEGER NOT NULL REFERENCES reconciliations(id), kind TEXT NOT NULL,
  trade_id INTEGER, result TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS reconciliation_rows_no_update BEFORE UPDATE ON reconciliation_rows BEGIN SELECT RAISE(ABORT, 'reconciliation_rows es solo de inserción'); END;
CREATE TRIGGER IF NOT EXISTS reconciliation_rows_no_delete BEFORE DELETE ON reconciliation_rows BEGIN SELECT RAISE(ABORT, 'reconciliation_rows es solo de inserción'); END;
```
`settings` y `trade_refs` son tablas de configuración (editables, sin disparadores). `reconciliation_rows.kind` ∈ `matched | bank_only | own_only`; `summary` y `result` son JSON. Ninguna migración. No hay tabla de flujos: el calendario se deriva.

### Constantes (fijas; las define T1)
```python
# desk/api/ops_settings.py
SETTING_KEYS = ("company_name",)
DEFAULT_COMPANY_NAME = "Empresa sin nombre (configurar en la confirmación)"
MAX_SETTING_LEN = 200
MAX_REF_LEN = 64
# desk/api/ops_settlements.py
CONFIRMED_KIND = "settlement_confirmed"
CURRENCIES = ("MXN", "USD")
# desk/api/ops_cashflows.py
FLOW_STATUSES = ("settled", "confirmed", "projected")
CSV_COLUMNS = ("date", "trade_id", "counterparty", "product", "kind", "status", "currency",
               "amount", "amount_mxn", "confirmed_amount", "difference")
# desk/api/ops_confirm.py
NOTICES = ("Documento informativo; no sustituye la confirmación ISDA ni el contrato marco firmado por las partes.",
           "Generado por QF Desk con los términos registrados; los montos variables dependen de fijaciones futuras.")
# desk/api/fpml.py
FPML_NS = "http://www.fpml.org/FpML-5/confirmation"
FPML_VERSION = "5-12"
FPML_PRODUCTS = ("irs", "fx_forward", "fx_option")
MAX_FPML_BYTES = 1000000
INDEX_TO_FPML = {"TIIE-F": "MXN-TIIE-ON-OIS Compound", "SOFR": "USD-SOFR-OIS Compound"}
TRADE_ID_SCHEME = "urn:qf-desk:trade-id"
# desk/api/ops_recon.py
DEFAULT_TOLERANCE = 0.0001        # fracción del nocional (= 0.01 %)
MAX_TOLERANCE = 0.1
EXPLAIN_CURVE_BP = 10.0           # |pb| ≤ 10 → explicable por curva
EXPLAIN_FX_PCT = 1.0              # |%| ≤ 1 → explicable por tipo de cambio
TERMS_CURVE_BP = 25.0             # sin explicación dentro de ±25 pb …
TERMS_FX_PCT = 2.0                # … o ±2 % de spot → bandera de términos
CURVE_PRODUCTS = ("irs", "cap_floor", "swaption", "bond")
FX_PRODUCTS = ("fx_forward", "fx_option")
RECON_STATUSES = ("conciliada", "explicable", "revisar")
MAX_CSV_ROWS = 5000
DISCLAIMER = "La descomposición es una ayuda de diagnóstico, no una prueba: indica qué movimiento explicaría la diferencia, no que lo haya causado."
```

### Contrato HTTP nuevo (backend ↔ interfaz)
Nada existente cambia de forma, salvo: `POST /api/trades/<id>/events` admite ahora `type: "transfer"` **solo** con `data.kind = "settlement_confirmed"` (misma validación y respuesta que `POST …/settlements`, envuelta como `{"events": [evento]}`); y `settled_flows` (por tanto P&L, flujos de la ficha y coberturas) **ignora** los `transfer` con ese `kind`. Todas las rutas nuevas viven en `desk/api/routes/ops.py` (blueprint `ops`), que T1 deja **completas** (parseo de id con `routes.trades._trade_id`, `body_object()`, delegación, `commit` en escrituras, `ensure_finite`, armado de respuestas CSV/XML); las tareas siguientes solo rellenan funciones de los módulos y **no editan `routes/ops.py`** (si hiciera falta, anotar y avisar). Toda validación de parámetros vive en los módulos.

**`GET /api/settings`** → 200 `{"company_name": "Empresa sin nombre (configurar en la confirmación)"}` (valor por omisión si no hay fila).
**`PUT /api/settings`** `{"company_name": "Tesorería Ejemplo, S.A. de C.V."}` → 200 con todas las claves. Clave desconocida → 400 con `field` = esa clave; `company_name` `text` obligatorio si viene, recortado, ≤ `MAX_SETTING_LEN` (400 `company_name`). Cuerpo vacío `{}` → 200 sin cambios. Inserta o reemplaza (`INSERT OR REPLACE`).

**`GET /api/trades/<id>/ref`** → 200 `{"trade_id": 1, "ref": null}`. **`PUT /api/trades/<id>/ref`** `{"ref": "BA-2026-0042"}` → 200 `{"trade_id": 1, "ref": "BA-2026-0042"}`; `ref` `null` o `""` (tras recortar) borra la referencia (`{"ref": null}`); no texto → 400 `ref`; > `MAX_REF_LEN` → 400 `ref`; misma referencia en otra operación de la **misma contraparte** → 409 `ref`. Orden: 404 `id` → 400 `ref` → 409 `ref`.

**`GET /api/cashflows?snapshot=&from=&to=&counterparty=&currency=&format=`** (D1). `snapshot` obligatorio (400/404 `snapshot`); `from`/`to` ISO opcionales e inclusivos (400 con su nombre; `from > to` → 400 `to`); `counterparty` texto exacto opcional (si no existe → 200 sin filas); `currency` ∈ `MXN|USD` (400 `currency`); `format` ∈ `json|csv` (400 `format`, default `json`).
Filas: para cada operación de `load_trades` (orden id), los **liquidados** de `settled_flows(trade, fixings, trade_date − 1 día, as_of, mkt.spot, mkt)` (los `transfer` de confirmación ya no salen ahí) y, si la operación está `viva` al `as_of`, los **proyectados** de `_projected_irs`/`_projected_bond` (solo `irs` y `bond`, como la ficha). Se filtra por ventana (`from ≤ date ≤ to`), contraparte y moneda (`currency` del flujo). Una operación que lanza al derivar sus flujos no tumba la respuesta: va a `errors` y no aporta filas.
```json
{"snapshot": "MX-DEMO", "as_of": "2026-11-10", "from": "2026-11-01", "to": null,
 "counterparty": null, "currency": null,
 "rows": [
   {"date": "2026-11-03", "trade_id": 1, "counterparty": "Banco Alfa (sintético)", "product": "irs", "kind": "coupon",
    "status": "confirmed", "currency": "MXN", "amount": 31000.0, "amount_mxn": 31000.0, "df": null, "pv": null,
    "confirmed_amount": 30990.0, "difference": -10.0},
   {"date": "2026-12-08", "trade_id": 1, "counterparty": "Banco Alfa (sintético)", "product": "irs", "kind": "coupon",
    "status": "projected", "currency": "MXN", "amount": -152340.12, "amount_mxn": -152340.12, "df": 0.99412, "pv": -151444.3,
    "confirmed_amount": null, "difference": null}],
 "totals": {"amount_mxn": -121340.12,
   "by_date": [{"date": "2026-11-03", "amount_mxn": 31000.0, "count": 1}],
   "by_counterparty": [{"counterparty": "Banco Alfa (sintético)", "amount_mxn": -121340.12, "count": 2}],
   "by_currency": [{"currency": "MXN", "amount": -121340.12, "amount_mxn": -121340.12, "count": 2}]},
 "errors": [{"trade_id": 9, "message": "No se pudo derivar sus flujos: …"}],
 "warnings": [{"code": "missing_fixing", "index": "TIIE-F", "dates": ["2026-11-05"], "message": "…"}]}
```
Reglas: `status` = `settled` (liquidado), `confirmed` (liquidado con confirmación) o `projected`. Un liquidado `coupon`/`settlement` con fecha `D` está `confirmed` si la operación tiene un evento `transfer` con `data.kind == "settlement_confirmed"` y `event_date == D`; entonces `confirmed_amount = data.amount` y `difference = confirmed_amount − amount` (misma moneda). Liquidados: `df`/`pv` `null`; `amount_mxn` el de `settled_flows`. Proyectados: `amount_mxn = amount × mkt.spot` si `currency == "USD"`, si no `amount`. Orden de filas: `(date, trade_id, kind)`. `totals.amount_mxn` = Σ `amount_mxn` de las filas; `by_date` por fecha ascendente, `by_counterparty` por nombre, `by_currency` por moneda (`amount` = Σ en esa moneda); `count` = filas. `warnings` = `merge_warnings` de todos.
CSV (`text/csv; charset=utf-8`, `Content-Disposition: attachment; filename="flujos-<snapshot>.csv"`): encabezado `CSV_COLUMNS`, una fila por fila JSON en el mismo orden, montos con `"%.2f"`, `null` → vacío, sin totales; `csv.writer` estándar.

**`POST /api/trades/<id>/settlements`** (D2) `{"date": "2026-12-08", "amount": 30990.0, "currency": "MXN", "snapshot": "MX-DEMO"}` → 201:
```json
{"event": {"id": 15, "trade_id": 1, "type": "transfer", "event_date": "2026-12-08",
           "data": {"kind": "settlement_confirmed", "amount": 30990.0, "currency": "MXN", "flow_kind": "coupon", "computed_amount": 31000.0},
           "prev_event_id": 3, "created_at": "2026-11-11T18:00:00+00:00"},
 "flow": {"date": "2026-12-08", "kind": "coupon", "amount": 31000.0, "currency": "MXN"},
 "difference": -10.0}
```
Validación en orden (primer error gana): 404 `id` → `date` ISO obligatorio (400 `date`) → `amount` `number(ge=-MAX_AMOUNT, le=MAX_AMOUNT)` (400 `amount`) → `currency` ∈ `CURRENCIES` (400 `currency`) → `snapshot` texto opcional (por omisión el snapshot de mayor `as_of`, empate por `id`); inexistente → 404 `snapshot` → `date > as_of` → 409 `date` ("El flujo del <date> aún no ocurre al <as_of>") → sin flujo derivado (`coupon` o `settlement`) con esa fecha en `settled_flows(trade, fixings, trade_date − 1, as_of, spot, mkt)` → 409 `date` ("No hay flujo derivado el <date>") → `currency` ≠ moneda del flujo → 409 `currency` → ya hay confirmación de esa operación en esa fecha → 409 `date` ("Ese flujo ya está confirmado"). Inserta con `events.insert_event(conn, id, "transfer", date, data)`; `data.computed_amount` = monto calculado al confirmar (solo registro: el calendario recalcula la diferencia). Las confirmaciones **no** cuentan para el orden cronológico de `post_event` (ni lo exigen ni lo bloquean) y no cambian estado, PV ni P&L.

**`GET /api/trades/<id>/confirmation`** (D3) → 200, para los 7 productos (términos **pactados**, `params` guardados; no lleva snapshot):
```json
{"trade_id": 1, "product": "irs", "product_label": "Swap de tasa de interés (OIS)", "generated_at": "2026-11-11T18:00:00+00:00",
 "parties": {"company": "Tesorería Ejemplo, S.A. de C.V.", "counterparty": "Banco Alfa (sintético)",
             "company_role": "Paga tasa fija", "counterparty_role": "Paga tasa variable"},
 "bank_ref": "BA-2026-0042",
 "dates": {"trade_date": "2026-11-10", "start_date": "2026-11-10", "maturity_date": "2028-10-31"},
 "terms": [{"key": "notional", "label": "Nocional", "value": 500000000.0, "format": "amount", "currency": "MXN"},
           {"key": "fixed_rate", "label": "Tasa fija", "value": 0.068, "format": "rate", "currency": null},
           {"key": "periods", "label": "Periodos", "value": 26, "format": "number", "currency": null}],
 "conventions": [{"key": "index", "label": "Índice variable", "value": "TIIE de Fondeo (TIIE-F)", "format": "text", "currency": null},
                 {"key": "day_count", "label": "Base de días", "value": "ACT/360", "format": "text", "currency": null},
                 {"key": "payment_frequency", "label": "Periodicidad de pago", "value": "Cada 28 días", "format": "text", "currency": null},
                 {"key": "compounding", "label": "Composición", "value": "Capitalización diaria de la tasa a un día (OIS), sin spread", "format": "text", "currency": null},
                 {"key": "business_days", "label": "Días hábiles", "value": "Días naturales, sin ajuste por inhábiles", "format": "text", "currency": null}],
 "schedule": [{"date": "2026-12-08", "description": "Cupón 1: pierna fija contra pierna variable", "amount": -264444.44, "currency": "MXN"}],
 "events_note": null,
 "notices": ["Documento informativo; no sustituye la confirmación ISDA ni el contrato marco firmado por las partes.",
             "Generado por QF Desk con los términos registrados; los montos variables dependen de fijaciones futuras."]}
```
`format` ∈ `amount | rate | number | text | date`. `events_note` = `null` si la operación no tiene más eventos que `execution` y confirmaciones; si tiene otros: `"La operación tiene eventos posteriores al pacto (<tipos en español separados por coma>): esta confirmación muestra los términos pactados."`. Contenido por producto (T4 verifica cada convención contra el pricer/`qfpy`; si el código dice otra cosa, manda el código y se anota):
| producto | `product_label` | `terms` (claves) | `conventions` (claves) | `schedule` |
|---|---|---|---|---|
| `irs` | Swap de tasa de interés (OIS) | notional, fixed_rate, periods | index, day_count (ACT/360), payment_frequency ("Cada 28 días"/"Cada 365 días"), compounding, business_days | un renglón por pago (`ois_payment_days`), `amount` = pierna fija con signo (−N·K·τ si `payer`, + si `receiver`), descripción "Cupón k: pierna fija contra pierna variable" |
| `fx_forward` | Forward de tipo de cambio USD/MXN | notional_usd, strike | settlement ("Por diferencias en MXN con el FIX USD/MXN del vencimiento"), business_days | vencimiento, `amount` null, "Liquidación por diferencias: nocional × (FIX − strike)" |
| `fx_option` | Opción de tipo de cambio USD/MXN | option_type, notional_usd, strike | exercise ("Europea"), settlement, premium ("Prima no registrada en QF Desk"), business_days | expiración, `amount` null |
| `cap_floor` | Cap / floor de tasa | cap_type, notional, strike, periods | index, day_count, payment_frequency, business_days | un renglón por periodo `start + k × period_days`, `amount` null |
| `swaption` | Swaption europea | swaption_type, notional, strike, expiry_years, swap_tenor_years | index, exercise ("Europea"), business_days | expiración, `amount` null |
| `bond` | Bono a tasa fija | face, coupon_rate, periods, frequency | day_count, payment_frequency ("<frequency> veces al año"), business_days | cupones en `start + round(k / frequency × 365)`, `amount = face × coupon_rate / frequency` (+ `face` en el último) |
| `equity_option` | Opción de renta variable | option_type, quantity, spot, strike, volatility, rate, dividend_yield, maturity_years | exercise ("Europea"), business_days | vencimiento, `amount` null |
`company_role`/`counterparty_role`: `irs` payer → "Paga tasa fija"/"Paga tasa variable" (receiver al revés); forwards y opciones `buy` → "Compra"/"Vende" (`sell` al revés); `bond` → "Tenedor"/"Emisor"; `cap_floor`/`swaption`/`equity_option` → "Compra"/"Vende" (las posiciones de estos productos son compradas). Etiquetas de `terms` en español: Nocional, Nocional (USD), Tasa fija, Periodos, Tipo de cambio pactado, Tipo de opción (valor "Call"/"Put"), Strike, Tipo (cap/floor → "Cap"/"Floor"; swaption → "Pagadora"/"Receptora"), Expiración (años), Plazo del swap (años), Valor nominal, Tasa cupón, Frecuencia, Cantidad, Spot, Volatilidad, Tasa, Rendimiento por dividendo, Plazo (años).

**`GET /api/trades/<id>/fpml`** (D4) → 200 `application/xml; charset=utf-8`, `Content-Disposition: attachment; filename="operacion-<id>.fpml.xml"`. Producto ∉ `FPML_PRODUCTS` → 400 `product`; operación con eventos distintos de `execution` y confirmaciones → 409 `id` ("FpML exporta solo operaciones sin eventos posteriores al pacto"); `fx_forward`/`fx_option` con `start_date ≠ trade_date` → 409 `id` (FpML no lleva ese dato).
**`POST /api/trades/fpml`** (cuerpo XML crudo, cualquier `Content-Type`) → 201 `{"trade": <public_trade>, "warnings": [{"code", "message"}]}`. Errores, todos **sin efectos**: cuerpo vacío o > `MAX_FPML_BYTES` → 400 `fpml`; contiene `<!DOCTYPE` o `<!ENTITY` (búsqueda sin distinguir mayúsculas, antes de parsear) → 400 `fpml` ("FpML con DTD o entidades no se acepta"); XML mal formado (`ET.ParseError`) → 400 `fpml` ("XML mal formado: <detalle>"); raíz ≠ `{FPML_NS}dataDocument` → 400 `fpml`; sin `trade` o con producto distinto de `swap`/`fxSingleLeg`/`fxOption` → 400 `fpml` ("Producto FpML no soportado: <nombre local>"); elemento obligatorio ausente o valor ilegible → 400 `fpml` nombrando el elemento; `swap` que no tenga exactamente una pierna fija y una variable con índice de `INDEX_TO_FPML` → 400 `fpml`. Con la estructura leída arma el cuerpo de `POST /api/trades` (`product`, `counterparty`, `trade_date`, `start_date`, `maturity_date`, `params`) y llama a `portfolio.create_trade`: sus 400 (p. ej. `notional`, `maturity_date`) pasan tal cual. Avisos: `party_assumed` ("Ninguna parte coincide con el nombre de la empresa: se tomó party1 como la empresa") cuando ningún `partyName` coincide con `company_name`.
Forma exportada (la importación lee exactamente estos elementos; números con `repr(float)` para ida y vuelta exacta; la empresa es `party1`, la contraparte `party2`):
```xml
<?xml version='1.0' encoding='utf-8'?>
<dataDocument xmlns="http://www.fpml.org/FpML-5/confirmation" fpmlVersion="5-12">
  <trade>
    <tradeHeader>
      <partyTradeIdentifier><partyReference href="party1"/><tradeId tradeIdScheme="urn:qf-desk:trade-id">1</tradeId></partyTradeIdentifier>
      <tradeDate>2026-11-10</tradeDate>
    </tradeHeader>
    <swap>  <!-- irs -->
      <productType>InterestRate:IRSwap:OIS</productType>
      <swapStream id="fixedLeg">
        <payerPartyReference href="party1"/><receiverPartyReference href="party2"/>
        <calculationPeriodDates id="fixedLegCalcDates">
          <effectiveDate><unadjustedDate>2026-11-10</unadjustedDate><dateAdjustments><businessDayConvention>NONE</businessDayConvention></dateAdjustments></effectiveDate>
          <terminationDate><unadjustedDate>2028-10-31</unadjustedDate><dateAdjustments><businessDayConvention>NONE</businessDayConvention></dateAdjustments></terminationDate>
          <calculationPeriodFrequency><periodMultiplier>28</periodMultiplier><period>D</period><rollConvention>NONE</rollConvention></calculationPeriodFrequency>
        </calculationPeriodDates>
        <paymentDates><calculationPeriodDatesReference href="fixedLegCalcDates"/><paymentFrequency><periodMultiplier>28</periodMultiplier><period>D</period></paymentFrequency><payRelativeTo>CalculationPeriodEndDate</payRelativeTo></paymentDates>
        <calculationPeriodAmount><calculation>
          <notionalSchedule><notionalStepSchedule><initialValue>500000000.0</initialValue><currency>MXN</currency></notionalStepSchedule></notionalSchedule>
          <fixedRateSchedule><initialValue>0.068</initialValue></fixedRateSchedule>
          <dayCountFraction>ACT/360</dayCountFraction>
        </calculation></calculationPeriodAmount>
      </swapStream>
      <swapStream id="floatingLeg">
        <payerPartyReference href="party2"/><receiverPartyReference href="party1"/>
        <!-- mismas calculationPeriodDates (id floatingLegCalcDates) y paymentDates -->
        <calculationPeriodAmount><calculation>
          <notionalSchedule><notionalStepSchedule><initialValue>500000000.0</initialValue><currency>MXN</currency></notionalStepSchedule></notionalSchedule>
          <floatingRateCalculation><floatingRateIndex>MXN-TIIE-ON-OIS Compound</floatingRateIndex></floatingRateCalculation>
          <dayCountFraction>ACT/360</dayCountFraction>
        </calculation></calculationPeriodAmount>
      </swapStream>
    </swap>
  </trade>
  <party id="party1"><partyName>Tesorería Ejemplo, S.A. de C.V.</partyName></party>
  <party id="party2"><partyName>Banco Alfa (sintético)</partyName></party>
</dataDocument>
```
- `irs`: TIIE-F → `28 D`; SOFR → `1 Y`; moneda de `CURVES`. Importar: `curve` por `floatingRateIndex` (inverso de `INDEX_TO_FPML`); `side` = `payer` si el pagador de la pierna fija es la empresa; `notional`, `fixed_rate`; `trade_date`, `start_date` = `effectiveDate`, `maturity_date` = `terminationDate`; `periods` = `max(1, round(días / period_days))` (lo hace `fit_to_maturity` con `params.periods` inicial 1).
- `fx_forward` → `<fxSingleLeg>`: `<productType>ForeignExchange:Forward</productType>`, `<exchangedCurrency1>` (USD: `payerPartyReference`, `receiverPartyReference`, `<paymentAmount><currency>USD</currency><amount>notional_usd</amount></paymentAmount>`), `<exchangedCurrency2>` (MXN, partes al revés, `amount = notional_usd × strike`, informativo), `<valueDate>maturity</valueDate>`, `<exchangeRate><quotedCurrencyPair><currency1>USD</currency1><currency2>MXN</currency2><quoteBasis>Currency2PerCurrency1</quoteBasis></quotedCurrencyPair><rate>strike</rate></exchangeRate>`, `<nonDeliverableSettlement><settlementCurrency>MXN</settlementCurrency></nonDeliverableSettlement>`. `buy` ⇔ la empresa es receptora de USD. Importar: `strike` de `rate` (no de `amount` MXN); `start_date = trade_date`; `maturity_date = valueDate`; `params.days` se reescribe.
- `fx_option` → `<fxOption>`: `<productType>ForeignExchange:VanillaOption</productType>`, `<buyerPartyReference>`, `<sellerPartyReference>`, `<europeanExercise><expiryDate>maturity</expiryDate><expiryTime><hourMinuteTime>12:00:00</hourMinuteTime><businessCenter>MXMC</businessCenter></expiryTime><valueDate>maturity</valueDate></europeanExercise>`, `<putCurrencyAmount>`/`<callCurrencyAmount>` (call de USD: call USD `notional_usd`, put MXN `notional_usd × strike`; put de USD al revés), `<strike><rate>strike</rate><strikeQuoteBasis>PutCurrencyPerCallCurrency</strikeQuoteBasis></strike>` (call; `CallCurrencyPerPutCurrency` en put). `buy` ⇔ la empresa es `buyer`. Sin prima (no se modela). Importar: `option_type` = `call` si `callCurrencyAmount/currency == "USD"`; `notional_usd` del monto USD; `strike` de `strike/rate`.
- La empresa al importar: la `party` cuyo `partyName` == `company_name` de `settings`; si ninguna, `party1` (aviso `party_assumed`); la contraparte es la otra `party` (`partyName` obligatorio).

**`POST /api/reconciliations`** (D5) `{"snapshot": "MX-DEMO", "counterparty": "Banco Alfa (sintético)", "csv": "trade_id,bank_pv,currency,bank_ref\n1,-1234567.89,MXN,\n,250000.0,MXN,BA-2026-0042\n", "tolerance": 0.0001}` → 201 detalle de corrida.
Validación en orden: `snapshot` texto obligatorio (400) → inexistente 404 `snapshot` → `counterparty` texto obligatorio (400) → contraparte inexistente en `counterparties` → 404 `counterparty` → `tolerance` `number(ge=0, le=MAX_TOLERANCE, required=False, default=DEFAULT_TOLERANCE)` (400 `tolerance`) → `csv` texto obligatorio (400 `csv`). CSV (`csv.reader` sobre el texto, líneas vacías ignoradas): encabezado obligatorio con columnas `trade_id`, `bank_pv`, `currency` y opcional `bank_ref` (en cualquier orden, recortadas); falta una → 400 `csv` ("Falta la columna 'bank_pv'"); 0 filas de datos o > `MAX_CSV_ROWS` → 400 `csv`; por fila (número de línea `n` contando el encabezado como 1): `trade_id` entero o vacío; si vacío, `bank_ref` obligatorio; `bank_pv` número finito; `currency` ∈ `MXN|USD`; error → 400 `csv` ("Línea n: …"); la misma operación (por id o por referencia resuelta) dos veces → 400 `csv` ("Línea n: la operación 7 ya viene en la línea m").
Emparejamiento: por `trade_id` si viene; si no, por `trade_refs.ref == bank_ref` entre las operaciones de esa contraparte. Sin pareja → `bank_only` con `reason`: "Operación inexistente" (id no existe), "La operación es de otra contraparte", "Referencia no encontrada". `own_only` = operaciones de la contraparte **vivas** al `as_of` que el CSV no trae. El PV del banco va con la **convención de signo de la empresa** (positivo = activo para la empresa).
Por fila emparejada (`fixings = load_all`, `mkt = load_context`):
- `own_pv_mxn = value_trade(trade, mkt, fixings)["pv_mxn"]`; `bank_pv_mxn = bank_pv × mkt.spot` si `currency == "USD"`, si no `bank_pv`; `difference_mxn = own_pv_mxn − bank_pv_mxn`; `notional_mxn = |state(...)["notional"]|` × `mkt.spot` si `describe(...)["currency"] == "USD"`; `difference_rel = difference_mxn / notional_mxn` (null si `notional_mxn == 0`).
- *fecha*: `prev_date`/`next_date` = día hábil (lun–vie) anterior/siguiente al `as_of`; `pv_prev`/`pv_next` = `value_trade(trade, context_at(mkt, d), fixings)["pv_mxn"]`; `attributed = min(own, pv_prev, pv_next) − tol_abs ≤ bank_pv_mxn ≤ max(…) + tol_abs`, con `tol_abs = tolerance × notional_mxn`.
- *curva* (solo `CURVE_PRODUCTS`, curva = `terms["curve"]`): `bp` tal que `value_trade(trade, mkt.shifted(curve=c, parallel_bp=bp), fixings)["pv_mxn"] == bank_pv_mxn`; Newton desde 0 con pendiente por diferencia finita de 1 pb sobre la valuación real, hasta 20 iteraciones, converge si `|f| ≤ 1e-8 × max(notional_mxn, 1)`; `null` si la pendiente es ~0 (`|slope| < 1e-12 × max(notional_mxn, 1)`), si `|bp| > 1000` o si no converge. `null` también en otros productos.
- *tipo de cambio* (solo `FX_PRODUCTS`): `pct` tal que `value_trade(trade, mkt.shifted(spot_pct=pct), fixings)["pv_mxn"] == bank_pv_mxn` (Newton, pendiente por diferencia de 0.01 %, mismos criterios, `null` si `|pct| > 50`); `spot = mkt.spot × (1 + pct/100)`.
- `status`: `conciliada` si `|difference_mxn| ≤ tol_abs`; si no, `explicable` si `attributed` o `|bp| ≤ EXPLAIN_CURVE_BP` o `|pct| ≤ EXPLAIN_FX_PCT`; si no, `revisar`. `terms_flag = status == "revisar" and (bp is None or |bp| > TERMS_CURVE_BP) and (pct is None or |pct| > TERMS_FX_PCT)`. Si la valuación lanza: `status` `revisar`, `error` con el mensaje, descomposición `null`.
Detalle de corrida (respuesta de `POST` y de `GET /api/reconciliations/<id>`):
```json
{"id": 1, "snapshot": "MX-DEMO", "as_of": "2026-11-10", "counterparty": "Banco Alfa (sintético)", "tolerance": 0.0001,
 "created_at": "2026-11-11T18:00:00+00:00",
 "disclaimer": "La descomposición es una ayuda de diagnóstico, no una prueba: …",
 "summary": {"matched": 3, "conciliada": 1, "explicable": 1, "revisar": 1, "bank_only": 1, "own_only": 1,
             "own_pv_mxn": -2500000.0, "bank_pv_mxn": -2480000.0, "difference_mxn": -20000.0},
 "rows": [{"line": 2, "trade_id": 1, "bank_ref": null, "product": "irs", "currency": "MXN",
           "notional_mxn": 500000000.0, "own_pv_mxn": -1234500.0, "bank_pv": -1234567.89, "bank_currency": "MXN",
           "bank_pv_mxn": -1234567.89, "difference_mxn": 67.89, "difference_rel": 1.3578e-07, "status": "conciliada",
           "decomposition": {"date": {"prev_date": "2026-11-09", "next_date": "2026-11-11", "pv_prev": -1240000.0, "pv_next": -1229000.0, "attributed": true},
                             "curve": {"curve": "TIIE-F", "bp": 0.0068}, "fx": null},
           "terms_flag": false, "error": null}],
 "bank_only": [{"line": 4, "trade_id": 999, "bank_ref": null, "bank_pv": 1000.0, "currency": "MXN", "reason": "Operación inexistente"}],
 "own_only": [{"trade_id": 7, "product": "cap_floor", "own_pv_mxn": 812345.0}]}
```
`fx` = `{"spot": 19.42, "pct": 1.2}` en FX; `curve` `null` en FX y `equity_option`. `summary` suma solo filas emparejadas sin `error`. Persistencia: un registro en `reconciliations` (`csv` crudo, `summary` JSON, `as_of` del snapshot, `created_at = now_iso()`) y una fila por elemento en `reconciliation_rows` (`kind` `matched`/`bank_only`/`own_only`, `trade_id` o NULL, `result` = el objeto JSON tal cual); el detalle se reconstruye de lo guardado (orden de inserción) y el `POST` devuelve exactamente lo que devolvería el `GET`.
**`GET /api/reconciliations[?counterparty=]`** → `{"reconciliations": [{"id", "snapshot", "as_of", "counterparty", "tolerance", "created_at", "summary"}]}` de la más reciente a la más antigua.
**`GET /api/reconciliations/<id>[?format=json|csv]`** → detalle o CSV; id no entero → 404 `id`; inexistente → 404 `id`; `format` inválido → 400 `format`. CSV (`conciliacion-<id>.csv`): encabezado `section,line,trade_id,bank_ref,product,status,own_pv_mxn,bank_pv,bank_currency,bank_pv_mxn,difference_mxn,difference_rel,date_attributed,curve_bp,fx_spot,terms_flag,reason`; `section` ∈ `conciliacion` (filas emparejadas), `solo_banco`, `solo_propia`; montos `"%.2f"`, `difference_rel` `"%.10f"`, `curve_bp` `"%.4f"`, `fx_spot` `"%.6f"`, booleanos `si`/`no`, vacíos para lo que no aplica; `reason` lleva el `error` en filas emparejadas con error.

### Interfaz Python interna (fija; T1 la deja con estas firmas)
- `desk/api/ops_settings.py` (**real en T1**): `get_settings(conn) -> Dict[str, str]`; `put_settings(conn, body) -> Dict[str, str]` (sin commit); `company_name(conn) -> str`; `get_ref(conn, trade_id) -> Optional[str]`; `put_ref(conn, trade_id, body) -> {"trade_id","ref"}` (sin commit; valida existencia con `portfolio.get_trade`); `refs_by_counterparty(conn, counterparty) -> Dict[str, int]` (ref → trade_id).
- `desk/api/ops_cashflows.py` (T1 stub, T2): `cashflows(conn, args) -> dict` (`args` = `request.args`); `cashflows_csv(payload) -> str`; `confirmations(trade) -> Dict[date, dict]` (fecha → `data` del `transfer` de confirmación; real ya en T1, lo usa T3).
- `desk/api/ops_settlements.py` (T1 stub, T3): `confirm_settlement(conn, trade_id, body) -> dict` (respuesta 201; sin commit); `is_confirmation(event) -> bool` (**real en T1**: `type == "transfer" and data.get("kind") == CONFIRMED_KIND`).
- `desk/api/ops_confirm.py` (T1 stub, T4): `confirmation(conn, trade_id) -> dict`.
- `desk/api/fpml.py` (T1 stub, T5): `export_trade(conn, trade_id) -> str` (XML con declaración); `import_trade(conn, raw: bytes) -> dict` (`{"trade","warnings"}`, sin commit).
- `desk/api/ops_recon.py` (T1 stub, T6): `create_run(conn, body) -> dict` (sin commit); `list_runs(conn, counterparty=None) -> List[dict]`; `get_run(conn, run_id) -> dict` (404 `id`); `run_csv(run) -> str`; `context_at(mkt, on: date) -> MarketContext` (**real en T1**: `MarketContext(mkt.snapshot_id, on, mkt.curves, mkt.pillars, mkt.spot, mkt.surface, mkt.hw, mkt.factors)`); `business_day(d: date, step: int) -> date` (**real en T1**: siguiente/anterior lun–vie); `reconcile_trade(trade, bank_pv_mxn, mkt, fixings, tolerance) -> dict` (fila sin `line`/`bank_*`).
- `desk/api/routes/ops.py` (**completo en T1**): las 13 rutas del contrato: `GET/PUT /api/settings`, `GET/PUT /api/trades/<id>/ref`, `GET /api/cashflows`, `POST /api/trades/<id>/settlements`, `GET /api/trades/<id>/confirmation`, `GET /api/trades/<id>/fpml`, `POST /api/trades/fpml`, `POST /api/reconciliations`, `GET /api/reconciliations`, `GET /api/reconciliations/<id>`. CSV con `Response(texto, mimetype="text/csv")` + `charset=utf-8` + `Content-Disposition`; XML con `Response(xml, mimetype="application/xml")` + `charset=utf-8` + `Content-Disposition`; `POST /api/trades/fpml` pasa `request.get_data()` (bytes) sin `body_object`.
- `desk/api/tests/ops_fixture.py` (T1; ayudas compartidas, sin tests): `confirm_raw(app, trade_id, day: date, amount, currency="MXN")` (inserta el evento por `events.insert_event` en una conexión propia y hace commit; para probar el calendario sin la ruta), `irs_trade(client, curve="TIIE-F", side="payer", notional=100e6, periods=52, fixed_rate=None, counterparty="Banco Alfa (sintético)", start=None) -> trade` (POST `/api/trades`), `fx_trade(client, product, side="buy", option_type="call", notional_usd=5e6, strike=19.5, days=120, counterparty=…) -> trade`, `own_pv(app, trade_id, snapshot="MX-DEMO", mkt_fn=None) -> float` (`pv_mxn` con `value_trade`; `mkt_fn(mkt) -> mkt'` permite desplazar el contexto: lo usan las pruebas de conciliación para fabricar el PV "del banco").

### Interfaz: piezas fijas (las crea U1)
- Rutas en `App.tsx` (bloque `corte 5`): `/operaciones` → `screens/ops/OpsScreen.tsx`; `/portafolio/:id/confirmacion` → `screens/ops/ConfirmationScreen.tsx`. Ambas `export default`.
- `Shell.tsx` `NAV_ITEMS`: entrada `{to: '/operaciones', label: 'Operaciones'}` (icono SVG de 16 px en el estilo de los demás, p. ej. dos flechas opuestas) insertada **justo antes de Metodología**, como bloque contiguo con comentario `corte 5`.
- `OpsScreen`: título "Operaciones", pestañas (`role="tablist"`, como `portfolio__tab`) **Flujos** y **Conciliación**, pestaña activa por `?tab=flujos|conciliacion` (default `flujos`) con `useSearchParams`; monta `<CashflowsPanel />` o `<ReconciliationPanel />` (cada uno en su archivo).
- `TradeScreen.tsx`: una línea `{/* corte 5 */}<TradeOpsPanel tradeId={trade.id} product={trade.product} />` dentro del encabezado de la ficha (tras los enlaces de cobertura) y su `import`. `PortfolioScreen.tsx`: `{/* corte 5 */}<FpmlImport />` en `portfolio__head`, junto al botón existente, y su `import`. `MethodologyScreen.tsx`: `import { OPS_SECTIONS } from './ops/opsMethodology'` y `{OPS_SECTIONS.map((s) => <SectionBlock key={s.id} section={s} />)}` tras `HEDGE_SECTIONS` (si `SectionBlock` tiene otra firma, imitar la de `HEDGE_SECTIONS`).
- `src/api/opsTypes.ts`: `FlowStatus`, `CashflowRow`, `CashflowTotals`, `CashflowsResponse`, `CashflowsQuery {snapshot, from?, to?, counterparty?, currency?}`, `Settings {company_name}`, `TradeRef {trade_id, ref}`, `SettlementBody {date, amount, currency, snapshot?}`, `SettlementResponse`, `ConfirmationRow {key, label, value: number|string, format: 'amount'|'rate'|'number'|'text'|'date', currency: string|null}`, `ScheduleRow`, `Confirmation`, `FpmlImportResponse {trade: Trade, warnings: {code, message}[]}`, `ReconStatus`, `ReconDecomposition`, `ReconRow`, `ReconBankOnly`, `ReconOwnOnly`, `ReconSummary`, `Reconciliation`, `ReconciliationSummary`, `CreateReconciliationBody {snapshot, counterparty, csv, tolerance?}` (transcripción exacta del contrato).
- `src/api/opsClient.ts`: helper privado propio `opsRequest<T>(method, path, body?: unknown, raw?: {text: string, contentType: string})` que replica el manejo de errores de `client.ts` y lanza el `ApiError` **importado** de `./client`; exporta `getCashflows(q)`, `cashflowsCsvUrl(q): string`, `confirmSettlement(tradeId, body)`, `getConfirmation(tradeId)`, `fpmlUrl(tradeId): string` (`/api/trades/<id>/fpml`), `importFpml(xml: string)` (`POST /api/trades/fpml`, `Content-Type: application/xml`), `getSettings()`, `putSettings(body)`, `getTradeRef(id)`, `putTradeRef(id, ref: string | null)`, `createReconciliation(body)`, `listReconciliations(q?: {counterparty?})` (devuelve el arreglo), `getReconciliation(id)`, `reconciliationCsvUrl(id): string`. Parámetros de consulta omitidos si son `undefined`/vacíos, con `URLSearchParams`.
- `src/screens/ops/opsLabels.ts`: `FLOW_STATUS_LABEL` (`settled` "Liquidado", `confirmed` "Confirmado", `projected` "Proyectado"), `FLOW_KIND_LABEL` (`coupon` "Cupón", `settlement` "Liquidación", `transfer` "Transferencia"), `RECON_STATUS_LABEL` (`conciliada` "Conciliada", `explicable` "Explicable", `revisar` "Revisar"), `PRODUCT_LABEL` (`irs` "Swap de tasa", `fx_forward` "Forward USD/MXN", `fx_option` "Opción USD/MXN", `cap_floor` "Cap / floor", `swaption` "Swaption", `bond` "Bono", `equity_option` "Opción de renta variable"), `FPML_PRODUCTS = ['irs','fx_forward','fx_option']`, `CSV_TEMPLATE = 'trade_id,bank_pv,currency,bank_ref\n'`.
- Stubs (U1) que rellenan U2–U6, cada uno `export` con su firma definitiva y `data-testid`: `screens/ops/CashflowsPanel.tsx` (`export function CashflowsPanel()`), `screens/ops/ReconciliationPanel.tsx` (`export function ReconciliationPanel()`), `screens/ops/ConfirmationScreen.tsx` (`export default`), `screens/ops/TradeOpsPanel.tsx` (`export function TradeOpsPanel({tradeId, product}: {tradeId: number; product: ProductId})`), `screens/ops/FpmlImport.tsx` (`export function FpmlImport()`), `screens/ops/opsMethodology.ts` (`export const OPS_SECTIONS: {id, title, items: {label, text}[]}[] = []`).
- Montos con `fmtMoney(v, ccy)`, fechas con `fmtDate`, tasas con `fmtRate`, cifras con clase `.num`; nada de `-0.00`. Cada componente con su `.css` propio en `screens/ops/` (prefijo de clase `ops-…`), sin tocar CSS existente.

---

## Tareas

### T1 — Esquema, módulos y rutas de operaciones como contrato
- **Modelo:** sonnet · **Depende de:** — (en paralelo con U1) · **R:** base de R1–R5, R5 (disparadores), R3 (`settings`), R2 (P&L intacto), R8
- **Objetivo:** dejar tablas, ajustes, referencias, exclusión de confirmaciones en `settled_flows` y **todas** las rutas registradas y completas; lo que falta responde 501 desde el módulo, para que T2–T6 solo rellenen funciones sin tocar rutas.
- **Archivos:** `desk/api/db.py` (bloque `corte 5` al final de `SCHEMA`), `desk/api/app.py` (importar `ops` y añadirlo a la tupla de blueprints: cambio mínimo marcado `corte 5`), `desk/api/settlement.py` (en `settled_flows`, saltar los `transfer` con `data.get("kind") == "settlement_confirmed"`; comentario `corte 5`), `desk/api/ops_settings.py` (nuevo, real), `desk/api/ops_cashflows.py`, `desk/api/ops_settlements.py`, `desk/api/ops_confirm.py`, `desk/api/fpml.py`, `desk/api/ops_recon.py` (nuevos: constantes, piezas reales marcadas en el Contexto, el resto stubs con `NotImplementedError`), `desk/api/routes/ops.py` (nuevo), `desk/api/tests/ops_fixture.py` (nuevo), `desk/api/tests/test_ops_schema.py` (nuevo).
- **Pasos:**
  1. Esquema y constantes del Contexto.
  2. `ops_settings.py` completo; `ops_cashflows.confirmations`, `ops_settlements.is_confirmation`, `ops_recon.context_at` y `ops_recon.business_day` reales.
  3. `routes/ops.py` con las 13 rutas según el contrato (cada stub propaga `NotImplementedError` → 501).
  4. `settlement.py`: la exclusión de confirmaciones (dos líneas).
  5. `ops_fixture.py` con las ayudas del Contexto.
  6. Tests (`test_ops_schema.py`): `UPDATE`/`DELETE` por SQL sobre `reconciliations` y `reconciliation_rows` (filas insertadas por SQL) → `sqlite3.DatabaseError`; una base existente sin las tablas nuevas (crear app, `DROP` por SQL las cuatro tablas y sus disparadores, `create_app` otra vez sobre la misma ruta) las recupera sin perder operaciones; `GET /api/settings` → default; `PUT` `{"company_name": "  Tesorería X  "}` → `"Tesorería X"`, persiste; `PUT {"foo": 1}` → 400 `foo`; `company_name` de 201 caracteres → 400; refs: `GET /api/trades/1/ref` → `null`; `PUT` y `GET` devuelven la referencia; misma ref en la operación 4 (también Banco Alfa) → 409 `ref`; en la 2 (Banco Beta) → 200; `{"ref": ""}` la borra; id `abc` → 404 `id`; **P&L intacto**: con `confirm_raw(app, 1, <fecha de un cupón ya liquidado tras rodar a +35 días>, 123.0)`, `/api/pnl?from=MX-DEMO&to=D1` y `/api/trades/1/flows?snapshot=D1` son idénticos (1e-12) a los de antes de insertar; `business_day(date(2026,11,13), 1) == date(2026,11,16)` y `business_day(date(2026,11,16), -1) == date(2026,11,13)`; `context_at` conserva curvas y spot; **registro de rutas**: cada una de las 13 `(método, regla)` está en `app.url_map` (sin depender de que sea stub, para que nadie tenga que editar este archivo).
- **Verificación:** `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests/test_ops_schema.py -q 2>&1 | grep -E "passed|failed"` → todo `passed`; suite backend completa sin `failed` (≥ 2335 + los nuevos).
- **Commit:** las doce rutas de archivo listadas.

### T2 — Calendario de flujos del portafolio
- **Modelo:** sonnet · **Depende de:** T1 · **R:** R1, R2 (calendario muestra confirmado y diferencia)
- **Objetivo:** `GET /api/cashflows` y su CSV según el contrato.
- **Archivos:** `desk/api/ops_cashflows.py` (solo `cashflows`, `cashflows_csv` y auxiliares privados), `desk/api/tests/test_ops_cashflows.py` (nuevo).
- **Pasos:** validar consulta en el orden del contrato; `load_context`, `fixings.load_all` una vez; por operación liquidados (`settled_flows`) + proyectados (`settlement._projected_irs`/`_projected_bond` si `viva`); marcar `confirmed` con `confirmations(trade)`; filtrar; ordenar; totales; `merge_warnings`; CSV con `csv.writer` sobre `io.StringIO`.
- **Tests:** R1: para las operaciones 1, 2 y 3 (y un `bond` creado por POST, `{"face": 1e8, "coupon_rate": 0.08, "periods": 6}`), Σ `amount × df` de sus filas `projected` == `value_trade(...)["pv"]` (1e-6 × nocional); filtros `from`/`to` (inclusivos), `counterparty` y `currency=USD` (solo la 3, la 4–6 no tienen proyectados) devuelven solo filas que cumplen; `totals.amount_mxn` == Σ filas (1e-9) y cada grupo de `by_*` == Σ de sus filas; `format=csv` → mismas filas (cuenta y `trade_id`/`date`/`status` en orden), encabezado exacto y `Content-Disposition`; tras rodar a +35 días (`hedge_fixture.roll`) los cupones pasados salen `settled`, y con `ops_fixture.confirm_raw` en uno de ellos sale `confirmed` con `confirmed_amount` y `difference = confirmed − amount`; el `transfer` de confirmación no aparece como fila; errores 400 `snapshot`/`from`/`to`/`currency`/`format`, 404 `snapshot`; operación corrupta (`insert_raw_trade`) va a `errors` y el resto responde 200.
- **Verificación:** `… -m pytest desk/api/tests/test_ops_cashflows.py -q 2>&1 | grep -E "passed|failed"`; suite backend completa sin `failed`.
- **Commit:** las dos rutas.

### T3 — Confirmar una liquidación
- **Modelo:** sonnet · **Depende de:** T1 · **R:** R2
- **Objetivo:** `POST /api/trades/<id>/settlements` y `transfer` de confirmación por `POST …/events`, sin efecto en PV ni P&L.
- **Archivos:** `desk/api/ops_settlements.py` (solo `confirm_settlement` y auxiliares), `desk/api/events.py` (bloque mínimo `corte 5`: en `post_event`, si `kind == "transfer"` y `data.kind == "settlement_confirmed"` delegar en `ops_settlements.confirm_settlement` (import tardío) y devolver `[evento]`; cualquier otro `transfer` sigue en 400 `type`; el cálculo de `last` para el orden cronológico ignora las confirmaciones con `ops_settlements.is_confirmation`), `desk/api/tests/test_ops_settlements.py` (nuevo).
- **Pasos:** validación en el orden del contrato; snapshot por omisión = mayor `as_of`; búsqueda del flujo derivado con `settled_flows`; duplicado por `ops_cashflows.confirmations(trade)` o recorriendo eventos; `insert_event`; respuesta con `public_event`.
- **Tests:** rodar a +35 (`D1`) con fijaciones TIIE-F cargadas (`hedge_fixture.load_fixings`); confirmar el cupón de la operación 1 en `as_of + 28` → 201, un evento `transfer` con `data.kind == "settlement_confirmed"`, `difference` = monto − calculado; mismo día otra vez → 409 `date`; fecha sin flujo (`as_of + 3`) → 409 `date`; fecha posterior al `as_of` del snapshot → 409 `date`; moneda USD en flujo MXN → 409 `currency`; `amount` `"x"` → 400 `amount`; `currency` `"EUR"` → 400; `snapshot` inexistente → 404; operación 999 → 404 `id`; forward de 20 días (`hedge_fixture.market_forward`) con FIX cargado: confirmar su `settlement` → 201; **PV y P&L** de `/api/portfolio/valuation?snapshot=D1` y `/api/pnl?from=MX-DEMO&to=D1` idénticos antes y después (1e-12, fila por fila); `/api/trades/1/flows` sin fila `transfer` nueva; por `POST /api/trades/1/events {"type": "transfer", "event_date": …, "data": {"kind": "settlement_confirmed", "amount": …, "currency": "MXN"}}` → 201 `{"events": [ … ]}`; `transfer` sin ese `kind` → 400 `type`; una confirmación con fecha posterior no impide un `quantity_change` anterior a ella (orden cronológico ignora confirmaciones) y una confirmación anterior al último evento se admite; nada se inserta en un 4xx.
- **Verificación:** `… -m pytest desk/api/tests/test_ops_settlements.py desk/api/tests/test_events_api.py -q 2>&1 | grep -E "passed|failed"`; suite backend completa sin `failed`.
- **Commit:** las tres rutas.

### T4 — Confirmación de la operación
- **Modelo:** sonnet · **Depende de:** T1 · **R:** R3
- **Objetivo:** `GET /api/trades/<id>/confirmation` para los 7 productos según la tabla del contrato.
- **Archivos:** `desk/api/ops_confirm.py`, `desk/api/tests/test_ops_confirm.py` (nuevo).
- **Pasos:** leer la operación (`get_trade`), `company_name`, `get_ref`; armar `terms`, `conventions`, `schedule` por producto (fechas de `irs` con `qfpy.ois_payment_days`; leer en solo lectura el pricer de cada producto en `desk/api/pricing/` y, si hace falta, `include/qf/` para confirmar base de días y periodicidad: si difiere de la tabla, manda el código y se anota); `events_note`; `NOTICES`; `ensure_finite` lo aplica la ruta.
- **Tests:** para los 7 productos (las 7 sembradas no traen `bond`, `swaption` ni `equity_option`: crearlos por POST) la respuesta tiene `parties`, `dates`, `terms`, `conventions`, `schedule` no vacío, `notices == NOTICES` y las claves de la tabla; `irs`: renglones = `len(ois_payment_days(...))`, último en `maturity_date`, Σ montos fijos == −N·K·Στ (payer); `bond`: último renglón incluye `face`; `PUT /api/settings` cambia `parties.company`; `bank_ref` refleja `PUT …/ref`; con un `quantity_change` registrado `events_note` lo menciona; id inexistente → 404 `id`.
- **Verificación:** `… -m pytest desk/api/tests/test_ops_confirm.py -q 2>&1 | grep -E "passed|failed"`; suite backend completa sin `failed`.
- **Commit:** las dos rutas.

### T5 — FpML: exportar e importar `irs`, `fx_forward`, `fx_option`
- **Modelo:** sonnet · **Depende de:** T1 · **R:** R4
- **Objetivo:** ida y vuelta FpML 5.x (vista de confirmación) con el subconjunto del contrato, importación segura.
- **Archivos:** `desk/api/fpml.py`, `desk/api/tests/test_ops_fpml.py` (nuevo).
- **Pasos:** exportar con `ET.Element`/`SubElement` bajo `FPML_NS` (registrar el espacio por omisión con `ET.register_namespace("", FPML_NS)`), `ET.tostring(root, encoding="unicode")` con la declaración; importar: tamaño → DTD/entidades → `ET.fromstring` dentro de `try` (`ParseError` → 400) → lectura estricta con mensajes que nombran el elemento → cuerpo de alta → `portfolio.create_trade`. Validar `href` contra las `party` declaradas. Ningún acceso a red ni a archivos.
- **Tests (R4):** al menos 3 variantes por producto — `irs`: TIIE-F payer, TIIE-F receiver con `start_date` posterior a `trade_date`, SOFR payer con otro vencimiento; `fx_forward`: buy, sell, otro strike/plazo; `fx_option`: buy call, sell put, buy put — para cada una exportar, importar, y comparar `product`, `params` (iguales exactos salvo flotantes a 1e-12 relativo), las tres fechas, `counterparty`, y `value_trade(...)["pv_mxn"]` (1e-9 relativo, o 1e-9 × nocional si |PV| es ~0) sobre `MX-DEMO`; con `company_name` igual a la `party1` exportada no hay aviso, con otro sí sale `party_assumed`; 400 `fpml` sin efectos (cuenta de `trades` igual) para: cuerpo vacío, XML truncado, `<!DOCTYPE …>` con entidad externa `SYSTEM "file:///etc/passwd"`, entidad interna (billion laughs), raíz ajena, `<bond>` (no soportado), falta `fixedRateSchedule`, índice desconocido; `notional` negativo → 400 `notional` (validación del alta); exportar `cap_floor` → 400 `product`; exportar con `quantity_change` → 409 `id`.
- **Verificación:** `… -m pytest desk/api/tests/test_ops_fpml.py -q 2>&1 | grep -E "passed|failed"`; suite backend completa sin `failed`.
- **Commit:** las dos rutas.

### T6 — Conciliación con el banco
- **Modelo:** sonnet · **Depende de:** T1 · **R:** R5
- **Objetivo:** `POST/GET /api/reconciliations` con descomposición indicativa, persistencia solo de inserción y CSV.
- **Archivos:** `desk/api/ops_recon.py` (todo salvo `context_at`/`business_day`, que ya existen), `desk/api/tests/test_ops_recon.py` (nuevo).
- **Pasos:** validación y lectura del CSV según el contrato; emparejamiento (id, `ops_settings.refs_by_counterparty`); `reconcile_trade` (fecha con `context_at`/`business_day`, curva y FX por Newton sobre `value_trade`, estado y bandera); `own_only`; inserción en una transacción; `get_run` reconstruye; `list_runs`; `run_csv`.
- **Tests (R5):** sobre Banco Alfa (op. 1, 4, 7) y una operación fuera de mercado creada con `ops_fixture.irs_trade(client, fixed_rate=0.03, notional=100e6, periods=52)` (precondición en el test: `|PV| > 30 × DV01`):
  (a) CSV con el PV propio exacto (`own_pv`) de todas → todas `conciliada`, `own_only == []`;
  (b) PV del banco = `own_pv(app, id, mkt_fn=lambda m: m.shifted(curve="TIIE-F", parallel_bp=5))` para un `irs` TIIE-F → `explicable`, `curve.bp` = 5 ± 0.1; y para un `fx_forward` con `spot_pct=0.5` → `explicable`, `fx.pct` = 0.5 ± 0.01;
  (c) PV del banco valuado un día hábil después (`mkt_fn=lambda m: ops_recon.context_at(m, ops_recon.business_day(m.as_of, 1))`) → `decomposition.date.attributed` true y estado `explicable` (o `conciliada` si cae en tolerancia: el test usa una operación cuyo PV cambie más que la tolerancia en un día, p. ej. la fuera de mercado);
  (d) nocional ×1.5 (PV de la misma operación con `notional × 1.5` en un dict en memoria) → `revisar` y `terms_flag` true;
  (e) `trade_id` 999 → `bank_only` "Operación inexistente"; operación de Banco Beta en el CSV de Alfa → `bank_only` "La operación es de otra contraparte"; `bank_ref` desconocida → "Referencia no encontrada"; `bank_ref` registrada con `PUT …/ref` empareja; omitir la 7 → `own_only` la lista;
  - USD: PV del banco en USD × spot == `bank_pv_mxn`; `tolerance` 0.5 → 400 `tolerance`; errores de CSV (falta columna, `bank_pv` `abc`, `currency` `EUR`, fila duplicada, sin filas) → 400 `csv` con "Línea n"; contraparte inexistente → 404 `counterparty`; nada se inserta en un 4xx;
  - persistencia: `GET /api/reconciliations/<id>` == respuesta del POST; lista de corridas con la más reciente primero y filtro `counterparty`; `UPDATE`/`DELETE` por SQL sobre las dos tablas → `sqlite3.DatabaseError`; `format=csv` → encabezado exacto, una fila por elemento con su `section`.
- **Verificación:** `… -m pytest desk/api/tests/test_ops_recon.py -q 2>&1 | grep -E "passed|failed"`; suite backend completa sin `failed`.
- **Commit:** las dos rutas.

### U1 — Contrato en la interfaz: tipos, cliente, rutas, navegación y stubs
- **Modelo:** sonnet · **Depende de:** — (en paralelo con T1) · **R:** R6 (base)
- **Objetivo:** dejar listas todas las piezas fijas de la interfaz para que U2–U6 trabajen en paralelo sin tocar archivos compartidos.
- **Archivos:** `desk/ui/src/api/opsTypes.ts` (nuevo), `desk/ui/src/api/opsClient.ts` (nuevo), `desk/ui/src/api/opsClient.test.ts` (nuevo), `desk/ui/src/App.tsx`, `desk/ui/src/components/Shell.tsx`, `desk/ui/src/components/Shell.test.tsx`, `desk/ui/src/screens/TradeScreen.tsx`, `desk/ui/src/screens/PortfolioScreen.tsx`, `desk/ui/src/screens/MethodologyScreen.tsx`, `desk/ui/src/screens/ops/OpsScreen.tsx` + `OpsScreen.css` + `OpsScreen.test.tsx` (nuevos, reales), `desk/ui/src/screens/ops/opsLabels.ts` (nuevo, real), stubs nuevos `desk/ui/src/screens/ops/CashflowsPanel.tsx`, `ReconciliationPanel.tsx`, `ConfirmationScreen.tsx`, `TradeOpsPanel.tsx`, `FpmlImport.tsx`, `opsMethodology.ts`.
- **Pasos:** transcribir "Interfaz: piezas fijas" y el contrato HTTP; stubs que renderizan `<section data-testid="<nombre>-stub" />` (o `null` en `TradeOpsPanel`/`FpmlImport`, que se montan en pantallas existentes y no deben romper sus tests); cambios en archivos compartidos solo en bloques `corte 5`.
- **Tests:** `opsClient.test.ts` (mock de `fetch`): `getCashflows({snapshot:'MX-DEMO', currency:'USD'})` llama `/api/cashflows?snapshot=MX-DEMO&currency=USD` (sin claves vacías); `cashflowsCsvUrl` añade `format=csv`; `confirmSettlement(1, b)` hace `POST /api/trades/1/settlements` con el cuerpo; `importFpml('<x/>')` envía el texto con `Content-Type: application/xml`; `putTradeRef(3, null)` envía `{"ref": null}` con `PUT`; `createReconciliation`, `listReconciliations({counterparty:'Banco Alfa (sintético)'})` (devuelve el arreglo `reconciliations`), `reconciliationCsvUrl(2)` == `/api/reconciliations/2?format=csv`, `fpmlUrl(4)` == `/api/trades/4/fpml`; un 409 → `ApiError` con `status` y `field`. `Shell.test.tsx`: la lista de enlaces pasa a siete con 'Operaciones' justo antes de 'Metodología' (ajustar el texto del `it`). `OpsScreen.test.tsx`: pestañas "Flujos" y "Conciliación"; `?tab=conciliacion` monta el stub de conciliación. Las pruebas existentes de `TradeScreen`, `PortfolioScreen`, `MethodologyScreen` y `App` siguen verdes.
- **Verificación:** `cd desk/ui && npm test 2>&1 | tail -5 && npm run build 2>&1 | tail -5` sin errores.
- **Commit:** las rutas listadas.

### U2 — Pestaña Flujos
- **Modelo:** sonnet · **Depende de:** U1 · **R:** R6, R2 (estado confirmado en pantalla)
- **Objetivo:** tabla de flujos filtrable con totales, exportación y confirmación de liquidación.
- **Archivos:** `desk/ui/src/screens/ops/CashflowsPanel.tsx`, `desk/ui/src/screens/ops/CashflowsPanel.css` (nuevo), `desk/ui/src/screens/ops/CashflowsPanel.test.tsx` (nuevo).
- **Pasos:** filtros "Desde", "Hasta" (`<input type="date">`; por omisión desde el `as_of` del snapshot menos 90 días hasta sin límite, para que se vean liquidados recientes y proyectados), "Contraparte" (de los nombres en las filas de una consulta sin filtro de contraparte) y "Moneda" (Todas/MXN/USD); snapshot de `useSnapshot()`; tabla (tabla HTML o AG Grid, como `PortfolioScreen`) con Fecha, Operación (enlace a `/portafolio/<id>`), Contraparte, Producto, Tipo, Estado, Moneda, Monto, Monto MXN, Confirmado, Diferencia; totales (general en MXN, por moneda y por contraparte) bajo la tabla; enlace "Exportar CSV" (`<a href={cashflowsCsvUrl(q)} download>`); en filas `settled` con `kind` `coupon`/`settlement`, botón "Confirmar liquidación" que abre un formulario en línea (monto prellenado con el calculado, moneda fija del flujo) y llama `confirmSettlement(trade_id, {date, amount, currency, snapshot})`; tras 201 recarga; un error se muestra con el mensaje del backend junto al formulario; `errors` y `warnings` como avisos. Sin desborde a 1280 px (la tabla hace scroll horizontal dentro de su contenedor si hace falta, no la página).
- **Tests:** con `vi.mock('../../api/opsClient')`: pinta filas y totales del simulado; cambiar "Moneda" a USD vuelve a llamar con `currency: 'USD'`; "Confirmado" muestra la diferencia de una fila `confirmed`; el botón solo aparece en filas `settled` de cupón/liquidación; enviar el formulario llama `confirmSettlement` con los valores y recarga; un `ApiError` 409 muestra su mensaje; el enlace CSV apunta a `cashflowsCsvUrl`.
- **Verificación:** `cd desk/ui && npm test 2>&1 | tail -5 && npm run build 2>&1 | tail -5` sin errores.
- **Commit:** las tres rutas.

### U3 — Pestaña Conciliación
- **Modelo:** sonnet · **Depende de:** U1 · **R:** R6
- **Objetivo:** correr una conciliación pegando o subiendo CSV, ver resultados con estado y descomposición, historial y exportación.
- **Archivos:** `desk/ui/src/screens/ops/ReconciliationPanel.tsx`, `desk/ui/src/screens/ops/ReconciliationPanel.css` (nuevo), `desk/ui/src/screens/ops/ReconciliationPanel.test.tsx` (nuevo).
- **Pasos:** formulario: "Contraparte" (`<select>` con las contrapartes de `listTrades()` de `client.ts`, únicas y ordenadas), snapshot del `useSnapshot()` (mostrado, no editable aquí), "Tolerancia (% del nocional)" (por omisión 0.01; se envía como fracción `/100`), `<textarea>` con `CSV_TEMPLATE` como `placeholder` y `<input type="file" accept=".csv,text/csv">` que carga el texto en el área (`file.text()`), botón "Conciliar"; resultado: resumen (conteos por estado, PV propio, PV banco, diferencia), tabla de filas (Operación, Producto, PV propio MXN, PV banco, Moneda, PV banco MXN, Diferencia, Dif./nocional en %, Estado con insignia por estado, Fecha "Atribuible"/"—", Curva "+5.0 pb", Tipo de cambio "19.42 (+1.20 %)", "Revisar términos" si `terms_flag`), listas "Solo en el banco" (con motivo) y "Solo en QF Desk", el `disclaimer` siempre visible, "Exportar CSV" (`reconciliationCsvUrl`); historial (`listReconciliations({counterparty})`) con fecha, snapshot y conteos, cada entrada carga su detalle con `getReconciliation`. Errores 400 del CSV se muestran tal cual (traen "Línea n").
- **Tests:** con mocks de `opsClient` y `client`: enviar llama `createReconciliation` con `{snapshot, counterparty, csv, tolerance: 0.0001}`; pinta las tres insignias de estado con su texto en español, la bandera de términos, `bank_only`/`own_only` y el aviso; cargar un archivo llena el área; un `ApiError` 400 `csv` muestra su mensaje; elegir una corrida del historial llama `getReconciliation(id)`.
- **Verificación:** `cd desk/ui && npm test 2>&1 | tail -5 && npm run build 2>&1 | tail -5` sin errores.
- **Commit:** las tres rutas.

### U4 — Confirmación imprimible
- **Modelo:** sonnet · **Depende de:** U1 · **R:** R6 (impresión sin barra lateral), R3 (vista)
- **Objetivo:** `/portafolio/:id/confirmacion`: documento claro de la confirmación, editable el nombre de la empresa, que imprime sin navegación.
- **Archivos:** `desk/ui/src/screens/ops/ConfirmationScreen.tsx`, `desk/ui/src/screens/ops/ConfirmationScreen.css` (nuevo), `desk/ui/src/screens/ops/ConfirmationScreen.test.tsx` (nuevo).
- **Pasos:** `getConfirmation(id)`; encabezado "Confirmación de operación" con `product_label`, número de operación y `generated_at`; secciones Partes (empresa y contraparte con su papel, referencia del banco), Fechas, Términos económicos, Convenciones (formateo por `format`: `amount` → `fmtMoney(v, currency)`, `rate` → `fmtRate`, `date` → `fmtDate`, `number` → `fmtNumber`), Calendario de pagos previsto (monto "Por determinar" si `null`), nota de eventos si existe, Avisos (los `notices` exactos); barra no imprimible (`.ops-no-print`) con "← Volver a la operación", "Imprimir" (`window.print()`) y el editor del nombre de la empresa (`getSettings`/`putSettings`, recarga la confirmación al guardar). `@media print` copiando el patrón de `HedgeReportScreen.css` (oculta `.shell__sidebar`, `.shell__topbar` y `.ops-no-print`; fondo blanco; una columna).
- **Tests:** pinta las seis secciones con los datos del simulado; `amount` null muestra "Por determinar"; guardar el nombre llama `putSettings({company_name})` y vuelve a pedir la confirmación; "Imprimir" llama `window.print` (espía); el CSS contiene `@media print` con `.shell__sidebar` (leer el archivo con `fs` en el test, como verificación estática).
- **Verificación:** `cd desk/ui && npm test 2>&1 | tail -5 && npm run build 2>&1 | tail -5` sin errores.
- **Commit:** las tres rutas.

### U5 — Ficha de operación (confirmación, FpML, referencia) e importación FpML en Portafolio
- **Modelo:** haiku · **Depende de:** U1 · **R:** R6
- **Objetivo:** enlaces y edición en la ficha; botón de importación en Portafolio.
- **Archivos:** `desk/ui/src/screens/ops/TradeOpsPanel.tsx`, `desk/ui/src/screens/ops/FpmlImport.tsx`, `desk/ui/src/screens/ops/TradeOps.css` (nuevo, lo importan ambos), `desk/ui/src/screens/ops/TradeOpsPanel.test.tsx` (nuevo), `desk/ui/src/screens/ops/FpmlImport.test.tsx` (nuevo).
- **Pasos:** `TradeOpsPanel`: fila compacta con `<Link to={`/portafolio/${tradeId}/confirmacion`}>Confirmación</Link>`, si `FPML_PRODUCTS.includes(product)` un `<a href={fpmlUrl(tradeId)} download>Descargar FpML</a>`, y "Referencia del banco: <valor o —> [Editar]" que abre un `<input>` (máx. 64) con Guardar/Cancelar → `putTradeRef(tradeId, valor || null)`; muestra el error del backend (409 "referencia repetida") bajo el campo. `FpmlImport`: botón "Importar FpML" que abre un panel con `<input type="file" accept=".xml,.fpml,application/xml">` o `<textarea>` para pegar y botón "Importar" → `importFpml(xml)`; con 201 muestra en el panel "Operación importada" con un enlace "Ver operación" a `/portafolio/<trade.id>` y los `warnings` si los hay (no navega sola, para que el aviso se lea); un 400 muestra el mensaje (`ApiError.message`).
- **Tests:** `TradeOpsPanel` con `irs` muestra los tres controles y con `cap_floor` no muestra "Descargar FpML"; editar y guardar llama `putTradeRef(5, 'BA-1')`; vacío envía `null`; un 409 muestra su mensaje. `FpmlImport`: pegar y enviar llama `importFpml` con el texto; con avisos los muestra y enlaza a la operación; un 400 muestra el mensaje.
- **Verificación:** `cd desk/ui && npm test 2>&1 | tail -5 && npm run build 2>&1 | tail -5` sin errores.
- **Commit:** las cinco rutas.

### U6 — Metodología de operaciones
- **Modelo:** haiku · **Depende de:** U1 · **R:** R7
- **Objetivo:** sección(es) de Metodología con lo que hace cada función y sus límites (D7).
- **Archivos:** `desk/ui/src/screens/ops/opsMethodology.ts`, `desk/ui/src/screens/ops/opsMethodology.test.tsx` (nuevo; renderiza `MethodologyScreen` dentro de `MemoryRouter`, como `MethodologyScreen.test.tsx`).
- **Pasos:** `OPS_SECTIONS` = una sección `{id: 'operaciones', title: 'Operaciones'}` con estos `items` (`label` exacto; `text` en español, 1–3 frases, contenido indicado):
  - "Calendario de flujos": une liquidados (derivados de términos y fijaciones) y proyectados (solo swaps y bonos vivos, del mismo instrumento que la valuación); signo positivo = se cobra; USD a MXN con FIX en liquidados y spot del snapshot en proyectados; los forwards y opciones no proyectan flujo.
  - "Liquidación confirmada": registra el pago real como evento `transfer` (`settlement_confirmed`); no cambia valuación ni P&L: el flujo derivado manda y la diferencia se reporta; una por flujo.
  - "Confirmación": documento informativo con términos pactados y convenciones; no sustituye la confirmación ISDA ni el contrato marco; sin firma.
  - "FpML": exporta e importa swaps OIS, forwards y opciones USD/MXN en FpML 5.12 (vista de confirmación) con el subconjunto de elementos necesario para ida y vuelta; no se valida contra el esquema XSD oficial; no se aceptan DTD ni entidades; nombres de índice ISDA (`MXN-TIIE-ON-OIS Compound`, `USD-SOFR-OIS Compound`) por verificar contra las definiciones vigentes; sin prima de opciones ni ajustes de días hábiles.
  - "Conciliación": compara el PV propio contra el del banco (convención de signo de la empresa; USD al spot del snapshot); conciliada si la diferencia ≤ 0.01 % del nocional (configurable); explicable si la atribuye la fecha (±1 día hábil), un desplazamiento paralelo de la curva de hasta ±10 pb o un movimiento de spot de hasta ±1 %; revisar en otro caso, con bandera de términos si ni ±25 pb ni ±2 % la explican.
  - "Descomposición indicativa": el texto de `DISCLAIMER` del backend, más: un solo factor a la vez, paralelo sobre tasa cero, sin calendario de inhábiles.
  - "Fuera de alcance": validación XSD, otros productos en FpML, mensajería (SWIFT, MarkitWire), instrucciones de liquidación y cuentas, neteo de pagos, conciliación de colateral, confirmación con firma.
- **Tests:** con el helper `row(label)` sobre `<dt>`: las siete etiquetas aparecen y "FpML" menciona "XSD"; "Conciliación" menciona "0.01 %".
- **Verificación:** `cd desk/ui && npm test 2>&1 | tail -5 && npm run build 2>&1 | tail -5` sin errores.
- **Commit:** las dos rutas.

### T7 — Integración contra el backend real y capturas
- **Modelo:** sonnet · **Depende de:** T1, T2, T3, T4, T5, T6, U1, U2, U3, U4, U5, U6 · **R:** R6, R8, verificación de punta a punta de R1–R5 y R7
- **Archivos:** ninguno nuevo; solo correcciones puntuales donde falle algo (commit de esas rutas). Respuestas en `/tmp/fableorchestrate/qf-corte5/it/`, capturas en `/tmp/fableorchestrate/qf-corte5/shots/` (no se commitean).
- **Pasos:**
  1. Suites: bindings (`… -m unittest discover -s tests -p "test_*.py"` → `OK`), backend (sin `failed`), interfaz (`npm test` y `npm run build`); C++: confirmar con `git diff --stat ce51edf -- include src CMakeLists.txt 'tests/*.cpp'` que no hay cambios (no se compila aquí). Reportar conteos.
  2. `mkdir -p /tmp/fableorchestrate/qf-corte5/{it,shots}`; `rm -f /tmp/fableorchestrate/qf-corte5/it.db`; backend en **5085** (comando del Contexto) en segundo plano con `run_in_background`, guardar el PID; esperar a que responda `curl -s http://127.0.0.1:5085/api/settings`.
  3. Recorrido por `curl` (guardar cada respuesta en `it/`): `PUT /api/settings` con un nombre; rodar `MX-DEMO` a `+35` (`D1`) y cargar fijaciones TIIE-F hábiles de `2026-11-10` a `D1.as_of − 1` y un FIX `USDMXN`; `GET /api/cashflows?snapshot=D1` (Σ filas = total; `format=csv` mismo número de filas); confirmar un cupón pasado de la op. 1 con `POST …/settlements` (201) y repetir (409); verificar que `/api/pnl?from=MX-DEMO&to=D1` no cambió (antes y después) y que el calendario la muestra `confirmed`; `GET /api/trades/1/confirmation` y la de un `bond` creado; exportar FpML de la op. 1, 4 y 6, importarlos (201) y comparar PV en `/api/portfolio/valuation?snapshot=MX-DEMO`; importar un XML con `<!DOCTYPE` (400); conciliación de Banco Alfa con un CSV construido de `/api/portfolio/valuation` (una fila exacta, una con +1 % de diferencia, un id inexistente y la 7 omitida) → estados esperados; `GET /api/reconciliations` y `?format=csv`.
  4. Construir la interfaz (`cd desk/ui && npm run build`) antes de arrancar o reiniciar el backend. Capturas a **1280 px** con Chrome headless propio: `google-chrome --headless=new --disable-gpu --remote-debugging-port=9345 --user-data-dir=/tmp/fableorchestrate/qf-corte5/chrome-profile --window-size=1280,900 --screenshot=/tmp/fableorchestrate/qf-corte5/shots/<n>.png http://127.0.0.1:5085/<ruta>` para `/operaciones`, `/operaciones?tab=conciliacion` (la corrida ya existe en el historial; si el detalle requiere clic, capturar el historial y verificar el detalle por `curl`), `/portafolio/1` (enlaces de operaciones), `/portafolio/1/confirmacion`, `/portafolio` (botón Importar FpML), `/metodologia` (además con `--window-size=1280,4000`). Revisar cada captura con `Read`: textos en español, sin desborde horizontal ni texto cortado; lo no comprobable se reporta como no verificado. Imprimir a PDF la confirmación (`--print-to-pdf=/tmp/fableorchestrate/qf-corte5/shots/confirmacion.pdf --no-pdf-header-footer`) y confirmar que no salen la barra lateral ni la superior (leer el PDF).
  5. Detener backend y Chrome con `kill <PID>` (nunca `pkill -f`); comprobar con `ss -ltnp | grep -E ':5085|:9345'` que no queda nada. `git status --short` limpio salvo lo ignorado.
  6. Último commit (correcciones o `git commit --allow-empty -m "test(desk): integración del corte 5 …"`) con `GRAPHIFY_SKIP_HOOK=1` (el grafo se regenera al fusionar en `feat/qf-desk`, no en el worktree).
- **Verificación:** reporte con cada comando y su resultado, conteos de las suites, rutas de capturas y PDF, y lista de correcciones.

---

## Orden y paralelismo

```
T1 ──┬─ T2 ─┐
     ├─ T3 ─┤
     ├─ T4 ─┤
     ├─ T5 ─┤
     └─ T6 ─┤
U1 ──┬─ U2 ─┤
     ├─ U3 ─┼─ T7
     ├─ U4 ─┤
     ├─ U5 ─┤
     └─ U6 ─┘
```
- **Ola 1 (2 agentes):** T1 y U1 a la vez (backend e interfaz no comparten archivos).
- **Ola 2 (10 agentes):** T2–T6 en cuanto termina T1; U2–U6 en cuanto termina U1. Archivos disjuntos por construcción: cada tarea toca solo su módulo/componente y su test nuevo; `routes/ops.py`, `opsTypes.ts`, `opsClient.ts`, `opsLabels.ts` y los archivos compartidos quedan cerrados tras T1/U1. Únicos archivos ya existentes que se tocan en la ola 2: `events.py` (solo T3). `settlement.py` lo toca solo T1.
- **Ola 3:** T7 sola.
- Sin C++: no hay cadena de compilación. Estimación: ola 1 ≈ 45–60 min, ola 2 ≈ 60–90 min, ola 3 ≈ 45–60 min: cabe en 5 horas con margen para una ronda de correcciones.

## Cobertura de requisitos

| R | Tareas |
|---|---|
| R1 | T2, T7 |
| R2 | T1 (`settled_flows` ignora confirmaciones), T3, T2 (estado y diferencia en el calendario), U2, T7 |
| R3 | T1 (`settings`), T4, U4, T7 |
| R4 | T5, U5, T7 |
| R5 | T1 (tablas solo de inserción), T6, U3, T7 |
| R6 | U1–U5, T7 (1280 px, PDF sin barra lateral) |
| R7 | U6 |
| R8 | todas (suite verde por tarea), T7 |

## Supuestos del planificador

1. **Confirmaciones fuera del P&L:** `settled_flows` hoy suma todo `transfer`; para cumplir R2 (PV y P&L sin cambio) se excluyen los `transfer` con `kind = settlement_confirmed` (T1). Afecta por igual a P&L, flujos de la ficha y coberturas.
2. **Confirmaciones y orden cronológico:** no cuentan para la regla de orden de `post_event` (ni la exigen ni la bloquean): confirmar un pago viejo no debe impedir registrar eventos de ciclo de vida, y viceversa.
3. **`snapshot` en `POST …/settlements`:** opcional (no estaba en el diseño); hace falta un contexto de mercado para derivar el cupón de un `irs`. Por omisión, el de mayor `as_of`. La interfaz manda el snapshot activo.
4. **Calendario:** proyecta solo lo que ya proyecta `settlement.py` (`irs` y `bond` vivos); forwards y opciones no tienen fila proyectada (solo su liquidación cuando ocurre). Sin `from`/`to` no hay límite de ventana; la interfaz propone desde `as_of − 90` días.
5. **Rutas propias:** referencia del banco y ajustes por `GET/PUT /api/trades/<id>/ref` y `GET/PUT /api/settings` (rutas nuevas en `routes/ops.py`); `trade_refs` y `settings` son editables (configuración, no hechos). Una referencia es única por contraparte (409 si se repite), no global.
6. **FpML:** documento `dataDocument` de FpML 5.12, vista de confirmación; la empresa es `party1` al exportar y, al importar, la parte cuyo nombre coincide con `company_name` (si ninguna, `party1` con aviso). Índices `MXN-TIIE-ON-OIS Compound` y `USD-SOFR-OIS Compound` por verificar contra las definiciones ISDA vigentes. Solo se exportan operaciones sin eventos posteriores al pacto (sus términos vigentes no serían representables con este subconjunto) y FX con `start_date = trade_date`. La importación devuelve `{"trade", "warnings"}` y no guarda el `tradeId` externo. La protección contra entidades es rechazar `<!DOCTYPE`/`<!ENTITY` antes de parsear (ElementTree no ofrece desactivar entidades internas).
7. **Confirmación:** muestra los términos **pactados** (no los vigentes) con una nota si hubo eventos; el calendario de pagos es previsto sin mercado (solo montos fijos conocidos). El nombre de la empresa se edita desde la propia vista de confirmación (el diseño no fijaba dónde).
8. **Conciliación:** `difference = propio − banco`; el PV del banco va con la convención de signo de la empresa; la curva de la descomposición es la del producto (`CURVE_PRODUCTS`), el tipo de cambio solo para FX, ninguno para `equity_option`; umbral de "explicable" por tipo de cambio ±1 % (el diseño solo fijaba ±10 pb y ±2 % para términos); `terms_flag` solo en filas `revisar`; `own_only` = operaciones de la contraparte vivas al `as_of`; `tolerance` en fracción del nocional (0.0001), la interfaz la pide en %.
9. **Suites en el worktree:** sin árbol de CMake, la suite C++ no se corre aquí (no hay cambios C++; T7 lo comprueba por `git diff`); la de bindings se corre con el mismo `unittest discover` que usa el target `pytests`. El commit de integración también lleva `GRAPHIFY_SKIP_HOOK=1`: el grafo se regenera al fusionar.
10. **Navegación:** "Operaciones" va justo antes de "Metodología" (no al final), como bloque `corte 5`; si otro corte añade en el mismo lugar, el conflicto de fusión es trivial.

## Anotado por los implementadores


### U1
- Commit `8fe78c6`. `npm test` 20 archivos / 286 pruebas; `npm run build` sin errores. No tocó types.ts ni client.ts. Se verificó (con una prueba temporal ya borrada) que `/operaciones`, `/operaciones?tab=conciliacion` y `/portafolio/1/confirmacion` montan sus stubs vía `App`.
- `opsClient.ts` exporta: `getCashflows(q: CashflowsQuery)`, `cashflowsCsvUrl(q)`, `confirmSettlement(tradeId, body: SettlementBody)`, `getConfirmation(tradeId)`, `getSettings()`, `putSettings(body: Partial<Settings>)`, `getTradeRef(id)`, `putTradeRef(id, ref: string | null)`, `fpmlUrl(tradeId)`, `importFpml(xml)`, `createReconciliation(body)`, `listReconciliations(q?: {counterparty?})` (devuelve el arreglo), `getReconciliation(id)`, `reconciliationCsvUrl(id)`. Los GET llaman `fetch('/api/...', {method: 'GET'})` (los mocks de `fetch` deben aceptar ese segundo argumento). Orden de la consulta: snapshot, from, to, counterparty, currency (+ format=csv).
- `opsTypes.ts`: añade `OpsCurrency = 'MXN' | 'USD'` (`CashflowsQuery.currency` y `SettlementBody.currency` lo usan; en tests/componentes un literal 'USD' compila, una variable `string` no). `CashflowRow.kind` es `FlowKind` de types.ts. `Warning` de types.ts se reutiliza en `CashflowsResponse.warnings`.
- Hueco de diseño (conservador): el contrato no dice qué lleva `decomposition` cuando un factor no converge ni cuando la valuación lanza. Tipado tolerante: `ReconRow.decomposition: ReconDecomposition | null`; `date`/`curve`/`fx` pueden ser `null` y `curve.bp`, `fx.spot`, `fx.pct` pueden ser `number | null`; `own_pv_mxn`, `difference_mxn`, `difference_rel` de `ReconRow` y `ReconOwnOnly.own_pv_mxn` son `number | null` (fila con `error`). U3 debe tratar todos como posiblemente `null`.
- `opsLabels.ts`: `FLOW_STATUS_LABEL`, `FLOW_KIND_LABEL`, `RECON_STATUS_LABEL`, `PRODUCT_LABEL`, `FPML_PRODUCTS: ProductId[]`, `CSV_TEMPLATE` tal cual la spec. Stubs: `CashflowsPanel`/`ReconciliationPanel` (`data-testid` `cashflows-stub`/`reconciliation-stub`), `ConfirmationScreen` (default, `confirmation-stub`), `TradeOpsPanel({tradeId, product})` y `FpmlImport()` devuelven `null`, `OPS_SECTIONS = []`. Al rellenarlos, `OpsScreen.test.tsx` busca `cashflows-stub`/`reconciliation-stub`: U2 y U3 deben ajustar esas aserciones (o mockear el panel con `vi.mock`) para que ese test siga verde.
- `Shell.test.tsx`: además de la lista de enlaces (siete), se actualizó la prueba de la paleta de comandos (ahora lista 'Operaciones' antes de 'Metodología'), porque la paleta toma sus pantallas de `NAV_ITEMS`.
- `OpsScreen` solo monta el panel activo (el otro se desmonta); la pestaña activa vive en `?tab=` (cambiar de pestaña hace `setSearchParams({tab})`, sin `replace`). Clases `ops__tabs`/`ops__tab`/`ops__panel`.
- `MethodologyScreen`: `OPS_SECTIONS` se pinta tras `HEDGE_SECTIONS` sin encabezado de grupo propio (la sección ya se titula "Operaciones"). `TradeOpsPanel` se monta tras los enlaces de cobertura y antes de `trade__facts` (fuera del `<header>`, donde viven esos enlaces); `FpmlImport` va tras el botón "Exportar CSV" dentro de `portfolio__head`.

### T1
- Commit `b368049`. Suite backend: 2386 passed (2335 + 51 de `test_ops_schema.py`). Rutas reales en `routes/ops.py` (blueprint `ops`, registrado en `app.py`); T2-T6 NO la editan.
- Son **12** pares (método, regla) distintos, no 13 como decía el plan (el `POST …/events` con `transfer` es de T3 en `events.py`). Reglas: `GET/PUT /api/settings`, `GET/PUT /api/trades/<trade_id>/ref`, `GET /api/cashflows`, `POST …/settlements`, `GET …/confirmation`, `GET …/fpml`, `POST /api/trades/fpml`, `POST/GET /api/reconciliations`, `GET /api/reconciliations/<run_id>`.
- La RUTA valida `format` (`json|csv`, 400 `format`) en `GET /api/cashflows` (antes de llamar al módulo: `cashflows` no necesita validarlo) y en `GET /api/reconciliations/<id>` (después de `get_run`: 404 `id` antes que 400 `format`). La ruta de cashflows nombra el CSV con `payload["snapshot"]` (T2 debe devolver `snapshot` en el cuerpo) y pasa por `ensure_finite`; `confirm_settlement`, `confirmation`, `import_trade`, `create_run`, `list_runs`/`get_run` también. `export_fpml`/`confirmation` solo parsean el id: el 404 `id` por operación inexistente lo lanzan T4/T5 (`portfolio.get_trade`); `confirm_settlement` ya recibe la operación verificada (404 antes de leer el cuerpo) pero igual puede volver a cargarla.
- `ops_settings` real: `put_ref` exige la clave `ref` (ausente → 400 `ref`; `null`/`""` borra), unicidad exacta (sensible a mayúsculas) por contraparte; `get_ref` no valida existencia (la ruta GET sí). `put_settings` valida todo antes de escribir. Constantes del Contexto en sus módulos tal cual.
- Reales: `ops_settlements.is_confirmation(event)`, `ops_cashflows.confirmations(trade) -> {date: data}` (importa `ops_settlements` a nivel de módulo; **T3 no debe importar `ops_cashflows` a nivel de módulo** desde `ops_settlements` (ciclo): hacerlo dentro de la función o recorrer `trade["events"]` con `is_confirmation`), `ops_recon.context_at`, `ops_recon.business_day(d, step)` (|step| días hábiles; solo lun–vie).
- `settlement.py` usa el literal `"settlement_confirmed"` (no importa `ops_settlements`, para evitar ciclos). Las confirmaciones no cambian estado (`lifecycle` ignora `transfer`).
- `tests/ops_fixture.py`: `confirm_raw` deja `flow_kind="coupon"` y `computed_amount=None`; `irs_trade`/`fx_trade` devuelven el JSON del alta; `own_pv(app, id, snapshot="MX-DEMO", mkt_fn=None)`; también exporta `ALFA`. `test_ops_schema.py` simula módulos con `monkeypatch` para fijar cabeceras/commits de las rutas: no se rompe cuando T2-T6 implementan (parchea el atributo del módulo).
- No comprobado: nada de interfaz ni de navegador (fuera de T1).

### U4
- Commit `a4a3c99`. `npm test` 25 archivos / 336 pruebas (incluye lo que otros agentes llevaban a la vez); `npm run build` sin errores. Solo toca `ConfirmationScreen.tsx` (`export default function ConfirmationScreen()`, lee `:id` con `useParams`), `.css` y `.test.tsx`.
- Llama `getConfirmation(id)`, `getSettings()` (precarga el editor; si falla, parte de `parties.company`) y `putSettings({company_name})` (recortado; al guardar relee la confirmación). Barra `.ops-no-print` (Volver a `/portafolio/<id>`, Imprimir = `window.print()`, editor del nombre, error de guardado con `role="alert"`); el documento tiene h1 "Confirmación de operación" y exactamente seis `h2` (Partes, Fechas, Términos económicos, Convenciones, Calendario de pagos previsto, Avisos). `events_note` va como párrafo `.ops-confirm__note` al final de la sección del calendario (no es sección propia). Clases `ops-confirm__*`; `.ops-no-print` se define en `ConfirmationScreen.css` (dentro de `@media print`: oculta `.shell__sidebar`, `.shell__topbar`, `.ops-no-print`).
- Decisión (hueco): `format: 'number'` → entero sin decimales; no entero → hasta 6 decimales sin ceros sobrantes con mínimo 2 (19.5 → "19.50"). `amount` sin `currency` → `fmtNumber(v, 2)`. Calendario vacío → "Sin pagos previstos." Guardar deshabilitado con nombre vacío (el backend lo rechaza igual).
- Prueba estática del CSS: el proyecto no trae `@types/node` y `tsconfig` fija `types: ["vite/client"]`, así que `import 'node:fs'` rompe `tsc -b`; el test hace `await import('node:fs' as string)` (sin tipos) y lee `src/screens/ops/ConfirmationScreen.css` relativo a la raíz de vitest (`desk/ui`; `import.meta.url` en jsdom no es `file:`, y `?raw` devuelve el CSS vacío). Si T7 corre vitest desde otro directorio, esa prueba fallaría por ruta.
- No comprobado: render real en navegador ni PDF de impresión (eso es T7); ningún `afterEach` extra además del `cleanup` global.

### U5
- Commit `a826ec9` (solo sus cinco rutas). Sin cambios en el backend ni en `api/`.
- `TradeOpsPanel({tradeId: number, product: ProductId})` (`TradeOpsPanel.tsx`): carga `getTradeRef` al montar; enlace `/portafolio/<id>/confirmacion`; `Descargar FpML` solo si `FPML_PRODUCTS.includes(product)`; edición con `maxLength 64`, vacío o solo espacios envía `putTradeRef(id, null)`; error de `ApiError` bajo el campo (`role="alert"`).
- `FpmlImport()` (`FpmlImport.tsx`): botón "Importar FpML" que abre panel con `<input type=file>` (lee con `FileReader`) y `<textarea aria-label="XML FpML">`; envía `importFpml(xml)`; en éxito muestra "Operación importada", enlace "Ver operación" a `/portafolio/<trade.id>` y `warnings`; no navega sola.
- `TradeOps.css` (nuevo, prefijo `ops-trade__*` / `ops-fpml*`) lo importan ambos componentes. Usa `var(--color-negative, #b42318)` como respaldo: confirmar que el token exista si se quiere el de la paleta.
- Los dos componentes necesitan contexto de router (usan `Link`); los tests montan `MemoryRouter`. Ya están montados en `TradeScreen`/`PortfolioScreen` (U1).
- Verificación: `npm test` 25 archivos / 336 pruebas OK; `npm run build` exit 0. En el primer intento fallaban CashflowsPanel y ConfirmationScreen.test.tsx (`node:fs` sin tipos) de otros agentes; tras reintentar pasaron.

### U3
- Commit `e387077`. `ReconciliationPanel.tsx`: `export function ReconciliationPanel()` (raíz `<section className="ops-recon" data-testid="reconciliation-panel">`; ya no existe `reconciliation-stub`). Usa `useSnapshot()` (`snapshotId`, `snapshot?.as_of`), `listTrades()` (contrapartes únicas ordenadas con `localeCompare`; la primera queda elegida) y `opsClient` (`createReconciliation`, `listReconciliations({counterparty})`, `getReconciliation`, `reconciliationCsvUrl`). Usa `Link` de react-router (necesita `MemoryRouter` en pruebas).
- Tolerancia: el campo es "Tolerancia (% del nocional)" (default `0.01`); se envía `Number((pct / 100).toPrecision(12))` (0.07 -> 0.0007 sin ruido); texto no numérico o negativo -> error local sin llamar al backend. Cambiar de contraparte limpia el resultado y recarga el historial; tras conciliar se recarga el historial.
- Convenciones de presentación: `null` -> "—"; curva "+5.0 pb"; FX "19.42 (+1.20 %)"; Dif./nocional = `difference_rel × 100` con 4 decimales; "Fecha" = "Atribuible"/"—" con `title` de PV previo/siguiente; "Revisar términos" y el `error` de la fila van dentro de la celda Estado; "Solo en el banco" / "Solo en QF Desk" son `region` con `aria-label`; el `disclaimer` va en el bloque de resultado (siempre visible mientras haya resultado).
- Toqué `OpsScreen.test.tsx` (fuera de mi lista, necesario): añadí un `vi.mock('./ReconciliationPanel', …)` con `data-testid="reconciliation-stub"`. Al commitear ese archivo entró también el `vi.mock('./CashflowsPanel', …)` que U2 ya había puesto en el árbol de trabajo (sin commitear); U2 no necesita repetirlo.
- Verificación: `npm test` 26 archivos / 339 pruebas verdes (incluye 15 nuevas de Conciliación y las de U2 en curso); `npm run build` sin errores. No comprobado: render en navegador real ni contra el backend real (lo cubre T7).

### U6
- Commit `b20488e`. `OPS_SECTIONS` (en `desk/ui/src/screens/ops/opsMethodology.ts`) sigue siendo `{id, title, items: {label, text}[]}[]` con una sola sección `operaciones` y las siete etiquetas exactas del plan (Calendario de flujos, Liquidación confirmada, Confirmación, FpML, Conciliación, Descomposición indicativa, Fuera de alcance).
- Descomposición indicativa repite el texto de `DISCLAIMER` de `desk/api/ops_recon.py` como literal en TS (no hay import cruzado); si el backend cambia el aviso, hay que actualizar ambos.
- La etiqueta "Fuera de alcance" también existe en `LIMITS` de `MethodologyScreen`; las pruebas de `opsMethodology.test.tsx` acotan la búsqueda a `#meth-operaciones` para no chocar.
- Pruebas: `opsMethodology.test.tsx` (3 pruebas) y `MethodologyScreen.test.tsx` en verde; `npm test` completo 26 archivos / 339 pruebas; `npm run build` sin errores.

### U2
- Commit `4d615d9`. `CashflowsPanel.tsx` (`export function CashflowsPanel()`, sin props), `CashflowsPanel.css` (prefijo `ops-cash__`), `CashflowsPanel.test.tsx` (15 pruebas). `npm test` 26 archivos / 339 pruebas; `npm run build` sin errores. No tocó `opsClient`/`opsTypes`/`types.ts`/`client.ts`. `OpsScreen.test.tsx` ya mockea `./CashflowsPanel` (la edición quedó en el commit `e387077` de U3, que commiteó el archivo entero).
- Consulta: `getCashflows({snapshot, from?, to?, counterparty?, currency?})` omitiendo claves vacías; "Desde" abre en `as_of − 90` días (UTC; `''` = sin límite elegido por el usuario) y no consulta hasta que `useSnapshot().snapshot.id === snapshotId` (muestra "Cargando snapshot…"). Contrapartes del filtro = nombres de filas de la última consulta SIN filtro de contraparte; con una elegida se conserva esa lista (si se amplía la ventana con una elegida, la lista no se refresca hasta volver a "Todas").
- Botón "Confirmar liquidación" solo si `status === 'settled'`, `kind` coupon/settlement y moneda MXN/USD; formulario en fila propia bajo la fila (monto prellenado `fmtNumber(amount,2)` sin comas, moneda fija como texto) → `confirmSettlement(trade_id, {date, amount, currency, snapshot: snapshotId})`; al 201 cierra y recarga; error → `role="alert"` dentro del formulario (monto no numérico se rechaza en cliente). El formulario se identifica por `trade_id|date` y se cierra en cada recarga.
- Totales bajo la tabla: general MXN, por moneda y por contraparte (no se pinta `by_date`: no se pidió). Enlace `<a download href={cashflowsCsvUrl(query)}>Exportar CSV</a>` con los filtros activos. `errors` ("Operación N: …") y `warnings` como listas de avisos.
- 1280 px comprobado en Chrome headless (9345) contra Flask (5085) con `/api/cashflows` simulado vía CDP (T2 aún sin implementar al medir): la página no desborda (`scrollWidth` 1280) y con filas de montos grandes la tabla cabe en 1040 px; si no cupiera, scroll horizontal dentro de `.ops-cash__scroll` y la columna de acción queda pegada a la derecha (sticky). Procesos apagados, puertos libres. Captura: `/tmp/fableorchestrate/qf-corte5/u2-flujos-1280.png` (T7 debe repetirla con el backend real).

### T3
- Commit `54284dc` (`ops_settlements.py`, `events.py`, `tests/test_ops_settlements.py`). Backend completo: 2453 passed (incluye lo que T2/T4 llevaban a la vez); `test_ops_settlements.py` + `test_events_api.py`: 142 passed.
- `ops_settlements.confirm_settlement(conn, trade_id, body) -> {"event" (public_event), "flow": {date, kind, amount, currency}, "difference"}`; `ops_settlements._snapshot_id(conn, body)` (privada). Importa `events, fixings, market, portfolio, settlement` a nivel de módulo (nunca `ops_cashflows`: ciclo). Duplicado se detecta recorriendo `trade["events"]` con `is_confirmation`. `data` del evento: `kind, amount, currency, flow_kind, computed_amount` (este último = monto calculado al confirmar).
- Snapshot por omisión = `max((as_of, id))` de `market.list_snapshots` (empate: el de mayor `id`, como `hedges.py`); sin snapshots → 404 `snapshot`. Solo se confirman flujos `coupon`/`settlement` (el `transfer` de terminación/ejercicio da 409 `date` "No hay flujo derivado"). Una operación ilegible sale por el manejador de `ValueError` (400 "No se pudo valuar: …"), sin escribir.
- `events.post_event`: bloque `corte 5` que delega en `confirm_settlement` si `type == "transfer"` y `data.kind == "settlement_confirmed"` (vía `_confirmation_events`, al final de `events.py`) y devuelve `[evento]` con `event_date` como `date`. Mapea `event_date`→`date`, `data.amount|currency|snapshot`. Decisión: en esa ruta los errores con `field: "date"` se reportan como `event_date` (la clave del cuerpo); `amount`/`currency`/`snapshot` igual. Cualquier otro `transfer` (sin `kind`, otro `kind`, `data` no objeto) sigue en 400 `type`.
- Orden cronológico: `last` y la guardia "sin execution" se calculan sobre `ordered` = eventos que no son confirmaciones (una operación con solo confirmaciones también da 409 `id`).
- T7: para confirmar desde la ruta hay que tener fijaciones cargadas del periodo (sin ellas el cupón usa la curva y avisa `missing_fixing`, pero la confirmación igual funciona).

### T2
- Commit `4bbc37d`. `test_ops_cashflows.py` 24 pruebas; suite backend completa 2453 passed, sin `failed` (incluye lo que T3/T4 llevaban a la vez). Solo tocó `ops_cashflows.py` y su prueba.
- `ops_cashflows.cashflows(conn, args) -> dict` y `cashflows_csv(payload) -> str` según el contrato; devuelve también `snapshot`, `from`/`to` (ISO o `null`), `counterparty`, `currency`. Orden de validación (primer error gana): `snapshot` (400 si falta/vacío) → `load_context` (404 `snapshot`) → `from` → `to` → `from > to` (400 `to`) → `currency` (400). `format` lo valida solo la ruta (`cashflows` lo ignora).
- Auxiliares privados: `_row`, `_trade_rows(trade, mkt, fixings) -> {"rows", "warnings": [grupos]}`, `_grouped(rows, key, with_amount=False)`. Importa `settlement._projected_irs/_projected_bond` (privadas) y `ops_settlements.CURRENCIES`.
- Decisiones: con `counterparty` se saltan antes de derivar las operaciones de otras contrapartes (sus errores no salen en `errors`); `counterparty` vacío o en blanco = sin filtro; `from=`/`to=`/`currency=` vacíos = 400. Solo se marca `confirmed` un liquidado `coupon`/`settlement` con confirmación en su fecha (un `transfer` real de terminación nunca); `difference = confirmed_amount − amount` sin comprobar moneda (la ruta de T3 ya garantiza que coincide). Una confirmación en una fecha sin flujo no agrega fila. Una operación que lanza no aporta filas ni avisos, solo `errors[{trade_id, message: "No se pudo derivar sus flujos: …"}]`.
- CSV: `csv.writer` por defecto (terminador `\r\n`, igual que el reporte de coberturas), montos `"%.2f"`, `null` → vacío; no normaliza `-0.00`. `df`/`pv` van en el JSON pero no en el CSV (no están en `CSV_COLUMNS`).

### T4
- Commit `711eee8` (`ops_confirm.py` + `tests/test_ops_confirm.py`, 35 pruebas); suite backend completa al terminar: 2488 passed. `confirmation(conn, trade_id) -> dict` (404 `id` vía `portfolio.get_trade`; 400 `product` si el producto no está en la tabla); no toca la ruta ni otros módulos. `NOTICES` sin cambios.
- Montos del calendario sin redondear (la interfaz los formatea): `irs` = ∓N·K·(k−k_prev)/360 con `qfpy.ois_payment_days`; `bond` = `face·coupon_rate/frequency` (+`face` en el último), fechas `start + round((k/frequency)·365)` (igual que `_bond_price`; el último coincide con `maturity_date`). `ScheduleRow.currency` siempre presente: moneda de la curva para irs/cap_floor/swaption/bond y `"MXN"` para fx_forward, fx_option y equity_option.
- Convención por código vs tabla: `bond` usa `day_count = "ACT/365"` (`qf::instruments::Bond` por omisión; la tabla no daba valor); `cap_floor`/`swaption` ACT/360 en el pricer, pero `swaption` no lleva `day_count` en `conventions` (la tabla solo pide index, exercise, business_days) y se respetó la tabla. Índice SOFR: "SOFR (Secured Overnight Financing Rate)".
- Hueco (conservador): el texto de `settlement` de `fx_option` no estaba fijado; quedó "Por diferencias en MXN con el FIX USD/MXN de la expiración, solo si la opción termina en el dinero" (QF Desk no deriva esa liquidación; es solo descripción del contrato). Formatos: tasas/volatilidad/dividendo/strike de cap-floor-swaption → `rate`; strike FX y de acción, spot, cantidad, plazos → `number`; `frequency` del bono en texto con `%g` ("2 veces al año", "0.5 veces al año").
- `events_note` nombra tipos distintos (sin repetir, orden de aparición) en español minúscula: fijación, transferencia (solo no-confirmación), cambio de nocional, cambio de términos, ejercicio, terminación anticipada. Los términos son siempre los `params` guardados (pactados), nunca los vigentes.

### T6
- Commit `c152aae` (solo `ops_recon.py` y `tests/test_ops_recon.py`). `test_ops_recon.py` 65 pruebas; suite backend completa 2612 passed (incluye lo que otros agentes llevaban). No toca `routes/ops.py`.
- `ops_recon`: `create_run(conn, body)`, `list_runs(conn, counterparty=None)`, `get_run(conn, run_id)`, `run_csv(run)`, `reconcile_trade(trade, bank_pv_mxn, mkt, fixings, tolerance) -> {trade_id, product, currency, notional_mxn, own_pv_mxn, difference_mxn, difference_rel, status, decomposition, terms_flag, error}`; nuevas constantes públicas `CURRENCIES` y `CSV_COLUMNS` (encabezado del CSV de descarga). `create_run` valida todo antes de insertar y devuelve `get_run` de lo insertado (el POST es idéntico al GET).
- Huecos (conservador): (1) fila con `error` (la valuación o la lectura de términos lanza): `status` `revisar`, `terms_flag` **false** (la fórmula literal daría true, pero un error no dice nada de los términos), `decomposition`/`own_pv_mxn`/`difference_*` null, `currency` null y `notional_mxn` 0.0 si ni los términos se leen. (2) `notional_mxn` usa el `notional` de `Product.describe` (el mismo de `value_trade`), no `state()["notional"]`: coincide en todos los productos salvo `equity_option`, donde es `quantity × spot` en MXN (con `quantity` pelada la tolerancia y `difference_rel` no tendrían sentido). (3) Línea `n` = línea física del texto (las vacías, o con solo comas, se ignoran pero cuentan en la numeración); `bank_pv` solo acepta decimal/exponente (rechaza `nan`, `inf`, `1_0`) y `|bank_pv| > 1e13` → 400 `csv`. (4) Duplicados: se compara el id efectivo (dado o resuelto por referencia) aunque no exista o sea de otra contraparte; las referencias sin resolver repetidas no se marcan. (5) `own_only` incluye una operación viva ilegible con `own_pv_mxn` null en vez de tumbar la corrida.
- Para quien consuma el JSON: `decomposition.date` puede ser `null` (falló valuar un día vecino), `curve.bp`/`fx.pct`/`fx.spot` null si Newton no converge. `jsonify` ordena las claves alfabéticamente (el orden del contrato solo vale en la persistencia y en el CSV).

### T5
- Commit `e523999` (solo `desk/api/fpml.py` y `desk/api/tests/test_ops_fpml.py`; 59 pruebas). Firmas sin cambio: `export_trade(conn, trade_id) -> str` (404 `id` → 400 `product` → 409 `id` por eventos distintos de `execution`/confirmaciones → 409 `id` por FX con `start_date ≠ trade_date`), `import_trade(conn, raw: bytes) -> {"trade","warnings"}` (sin commit; todo 400 `fpml` ocurre antes de escribir). Constantes del Contexto intactas; añade `FPML_TO_INDEX` (inverso de `INDEX_TO_FPML`). `routes/ops.py` no se tocó.
- Sale con sangría de dos espacios y declaración `<?xml version='1.0' encoding='utf-8'?>`; números con `repr(float)`. `ET.register_namespace("", FPML_NS)` se ejecuta al importar el módulo (efecto global del proceso).
- Importación: decodifica UTF-8 estricto (BOM tolerado; UTF-16 se rechaza porque escondería el `<!DOCTYPE` a la búsqueda) antes de buscar `<!DOCTYPE`/`<!ENTITY` (insensible a mayúsculas y a espacios tras `<!`) y parsear el `str`. Exactamente una `<trade>` y exactamente dos `<party>`; todo `href` de parte se valida contra ellas; la empresa es la `party` cuyo `partyName == company_name`, si no la primera (aviso `party_assumed` nombra su id).
- Huecos resueltos de forma conservadora (rechazar en vez de leer a medias): `irs` exige piernas opuestas, mismas fechas y nocional, moneda de la curva, frecuencia (`28 D`/`1 Y`) y `ACT/360`; FX exige `quoteBasis`/`strikeQuoteBasis` y par USD/MXN esperados, y el forward `nonDeliverableSettlement/settlementCurrency = MXN`. Un `irs` sin `fixedRateSchedule` ni `floatingRateCalculation` en una pierna → 400 que nombra ambos elementos.
- Igual que `POST /api/trades`, el vencimiento de un `irs` importado se ajusta a periodos enteros sin aviso (no se añadió un aviso `maturity_adjusted`). `trade_date`/`start_date` de FX = `tradeDate`; `maturity_date` = `valueDate` (forward) o `europeanExercise/expiryDate` (opción). No se comprueba el monto MXN del forward ni `valueDate` de la opción (informativos).
- No comprobado: caracteres de control en nombres (expat los acepta al importar; el XML exportado no se limpia). Las pruebas de otros agentes (`test_ops_recon.py`, T6 en curso) fallaban a ratos durante mi corrida; excluyéndolas la suite dio 2547 passed.

### T7
- Commit `6438dd8` (9 rutas: `ops_recon.py` + `test_ops_recon.py`, `FpmlImport.tsx/.test.tsx`, `TradeOpsPanel.tsx`, `TradeOps.css`, `ReconciliationPanel.tsx/.css/.test.tsx`). Suites finales: bindings 56 `OK`; backend 2613 passed; interfaz 26 archivos / 340 pruebas y `npm run build` exit 0; `git diff --stat ce51edf -- include src CMakeLists.txt 'tests/*.cpp'` vacío (C++ sin cambios, no se compiló).
- Corrección de fondo (`ops_recon._date_factor`): el día hábil vecino en que la operación no está `viva` (aún no pactada o ya vencida) vale 0 por definición; ese 0 entraba al rango de "atribuible a la fecha" y, en una operación pactada el día del `as_of`, casi cualquier PV del banco entre 0 y el propio salía atribuible (un bono con +15 pb salía `explicable`, ahora `revisar`). `pv_prev`/`pv_next` se siguen mostrando tal cual (0.0); solo se excluyen del rango. El contrato JSON no cambia.
- Correcciones de interfaz vistas a 1280 px: botones/campos/panel de U5 sin tema (clase `ops-trade__btn`, `ops-trade__input`), panel de FpML ahora flota bajo un botón que sigue visible (`aria-expanded`; ya no desplaza el encabezado de Portafolio), token de error `--neg` (`--color-negative` no existe), tabla de conciliación con 6 px laterales (cabía 1160 px en 1038), historial "1 conciliada · 1 explicable · … solo en el banco · … solo en QF Desk".
- Verificado de punta a punta con el backend real (5085, base `/tmp/fableorchestrate/qf-corte5/it.db`, respuestas en `it/`): ajustes, calendario (Σ filas = total; CSV = JSON en filas), confirmar 201 / repetir 409, P&L idéntico antes y después, FpML ida y vuelta de op. 1/4/6 con PV idéntico, `<!DOCTYPE>` 400 sin efectos, conciliación (conciliada / explicable / revisar con bandera / bank_only ×2 / own_only), historial y CSV; GET del detalle == respuesta del POST; triggers solo de inserción rechazan UPDATE/DELETE. Capturas en `shots/`, PDF `shots/confirmacion.pdf` (2 páginas, sin barra lateral ni superior).
- No corregido (solo reportado): la línea de tiempo de la ficha muestra una confirmación como "Transferencia · Importe MXN …" (TradeScreen, archivo compartido); el selector de archivo dice "Choose File / No file chosen" (idioma del navegador); la pestaña Flujos de la ficha no marca `confirmed` (solo el calendario de Operaciones); Chrome headless con `--screenshot`/`--print-to-pdf` no sale solo (hubo que usar `timeout`).

### Correcciones

Auditoría del corte 5 (`audit.md`): 8 de 8 requisitos CUMPLE; se corrigieron los 2 defectos de severidad media y 3 de los 4 de severidad baja (el cuarto, la bandera de términos cerca de la par, es un límite del método y solo se declaró), uno por commit y cada uno con su prueba. Commits `49837d3..90c6181` sobre `6438dd8`.

- **`49837d3` (media) FpML: el vencimiento ya no se mueve en silencio.** `fpml._swap_body` rechaza (400 `fpml`) un `irs` cuya `terminationDate` no cae en periodos enteros (28 d en TIIE-F, 365 en SOFR) desde `effectiveDate`, y el mensaje nombra la fecha pedida y la representable más cercana. Decisión de diseño que el documento no resolvía ("rechazar o avisar"): se eligió **rechazar**, lo más conservador y lo que el propio módulo declara ("rechaza lo que no puede representar fielmente"); cambia el supuesto 6 del planificador y la prueba `test_import_irs_maturity_is_fitted_to_whole_periods…`, que fijaba el redondeo, pasó a ser tres pruebas (TIIE-F, SOFR, y frontera de periodo que sí se acepta). Si `end <= start` sigue rechazándolo el alta (`maturity_date`). El resultado de exportar e importar no cambia (el export siempre cae en periodos enteros).
- **`e9c5868` (media) Confirmación de un `irs`: el calendario dice que es solo la pierna fija.** El renglón pasó de "Cupón n: pierna fija contra pierna variable" a "Cupón n: solo pierna fija (el neto a liquidar depende de la pierna variable)"; el monto no cambia. Se evitó añadir campos nuevos al contrato JSON.
- **`b5661aa` (baja) `prev_event_id`.** `events.insert_event` (bloque `corte 5`) ya no encadena a una confirmación de liquidación: `prev_event_id` apunta al último evento que no es confirmación, así una terminación posterior apunta a la `execution` y no a un registro de pago de fecha anterior. Las confirmaciones cuelgan del último evento del ciclo de vida sin extender la cadena. No cambia valuación, P&L ni orden cronológico.
- **`7ba5353` (baja) Selector de archivo en español.** Componente nuevo `FilePicker` (input nativo oculto pero enfocable + botón "Elegir archivo" + "Ningún archivo seleccionado"/nombre elegido) usado en Conciliación e Importar FpML; el control nativo sigue el idioma del navegador y no se traduce. Comprobado a 1280 px en Chrome headless (9345) contra el backend real (5085): sin desborde, mismo estilo de los demás botones.
- **`7ef5ed8` (baja) Aviso de fijaciones faltantes en Flujos.** Muestra las primeras 5 fechas y "… y N más" (la lista completa queda en el `title`), en vez de 117 fechas.
- **`90c6181` (baja) Metodología.** Declara los tres límites que faltaban: la bandera de términos no detecta un nocional distinto cerca de la par (PV≈0), FpML rechaza vencimientos fuera de periodos enteros, y el calendario de la confirmación de un swap es solo la pierna fija.

Suites tras las correcciones: backend 2616 passed (antes 2613); interfaz 27 archivos / 348 pruebas (antes 26 / 340) y `npm run build` exit 0; bindings 56 `OK`; C++ sin cambios (`git diff --stat ce51edf -- include src CMakeLists.txt 'tests/*.cpp'` vacío; no se compiló).

No corregido: (1) límite de la bandera de términos en operaciones a la par: es inherente al método (×1.5 de PV≈0 es 0); solo se declaró en Metodología. (2) De T7, fuera de la auditoría y en archivos compartidos (`TradeScreen`): la línea de tiempo de la ficha muestra una confirmación como "Transferencia · Importe MXN …" y la pestaña Flujos de la ficha no marca `confirmed` (solo el calendario de Operaciones). (3) Observación R5(c): con la tolerancia por omisión una diferencia de 1 día queda `conciliada` porque es < 0.01 % del nocional (con tolerancia 0 sale `explicable`); es el comportamiento del diseño, no un defecto. (4) Observación R6: el snapshot de la conciliación se elige con el selector global y no dentro de la pestaña; es una decisión de diseño de D6.
