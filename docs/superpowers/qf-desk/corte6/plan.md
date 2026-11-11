# Plan: QF Desk — Corte 6 (riesgo avanzado)

Diseño: `/tmp/fableorchestrate/qf-corte6/design.md` (en el repo: `docs/superpowers/qf-desk/corte6/` tras el corte). Worktree: `/home/claudio/Git/qf-wt/corte6`, rama **`corte6`** (creada desde `feat/qf-desk`, último commit `ce51edf`). Base: cortes 1, 2 y 4 (firmas en `docs/superpowers/qf-desk/corte2/plan.md` y `corte4/plan.md`, § Contexto).

## Contexto

Todo implementador lee esta sección completa y solo su tarea. Lo que sigue es decisión: no hay a quién preguntar. Si una tarea encuentra un hueco, elige lo más conservador, lo aplica solo en sus archivos y lo reporta en su mensaje final (el orquestador lo anota abajo).

### Entorno
- Directorio de trabajo **`/home/claudio/Git/qf-wt/corte6`** (worktree propio). Trabajar **solo** aquí: otros cortes avanzan a la vez en `/home/claudio/Git/qf-wt/corte5`, `corte7` y en `/home/claudio/Git/Quant_Finance`; no tocarlos, no leer su `build/`. **Nunca** push, merge, rebase ni `git stash`.
- **Python del backend:** `/home/claudio/anaconda3/bin/python` (3.8.18; Flask 2.3.3, pytest 8.2.0; Flask vive en `~/.local`: ejecutar sin `-I`). Sintaxis 3.8 (nada de `match`, `X | Y`, `list[int]` evaluado en ejecución; usar `typing`). **Sin paquetes nuevos** (ni Python ni npm; no usar numpy en el desk: Python puro).
- **Node** 22, **npm** 10. Interfaz en `desk/ui` (Vite + React 18 + TS, AG Grid, ECharts, vitest + jsdom). `desk/ui/node_modules` ya está instalado.
- **C++:** el worktree no trae `build/`; lo crea T1. Configuración obligatoria (igual que el repo principal, para que `qfpy`/`qfxva` salgan para Python 3.8): `cmake -S . -B build -DPYTHON_EXECUTABLE=/home/claudio/anaconda3/bin/python -DCMAKE_BUILD_TYPE=Debug`. Siempre `-j3` (otros cortes compilan a la vez). `qf` es biblioteca **estática**; `qfpy` y `qfxva` son módulos en `build/src/` (`desk/api/qf.py` añade esa ruta a `sys.path`).
- **Regla de compilación en paralelo:** mientras corren tareas de backend, **nadie** construye el objetivo `all` ni `qfpy` (reescribir `qfpy.so` rompe las pruebas ajenas). T2 construye solo `--target qf qf_tests qfxva`. Solo T1 (al inicio, sola) y T9 (al final, sola) construyen todo.
- **Las cuatro suites** (desde la raíz del worktree salvo vitest):
  - C++: `cmake --build build -j3 2>&1 | tail -3 && (cd build && ctest --output-on-failure 2>&1 | tail -3)` → `100% tests passed` (≈ 402 antes del corte; T1 anota la cifra).
  - Bindings: `cmake --build build --target pytests 2>&1 | tail -3` → `OK`.
  - Backend: `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q 2>&1 | grep -E "passed|failed"` → `N passed`, sin `failed` (no usar `tail`: un warning sale tras el resumen).
  - Interfaz: `cd desk/ui && npm test 2>&1 | tail -5` y `npm run build 2>&1 | tail -5` (`tsc -b && vite build`), sin errores.
- **Puertos y procesos de este corte:** backend de prueba **5086** con base temporal `/tmp/fableorchestrate/qf-corte6/it.db`: `cd /home/claudio/Git/qf-wt/corte6 && /home/claudio/anaconda3/bin/python -c "from desk.api.app import create_app; create_app(db_path='/tmp/fableorchestrate/qf-corte6/it.db').run(host='127.0.0.1', port=5086)"`. Chrome headless con `--remote-debugging-port=9346 --user-data-dir=/tmp/fableorchestrate/qf-corte6/chrome-profile`. Nunca 5070 (el desk de Claudio), 5071 ni 9222. Apagar todo lo que se levante con `kill <PID>` (nunca `pkill -f`).
- **No tocar** `~/Git/MarketDataFeed`, `desk/data/`, `graphify-out/`, ni `POST /api/market/refresh` (sale a la red).

### Reglas de ejecución y commits
- Un commit por tarea, solo de tus rutas: `git add <rutas> && GRAPHIFY_SKIP_HOOK=1 git commit -m "<tipo>(desk): <por qué>" -- <rutas>`. Nunca `git add -A`/`.`. Autor: configuración global (Claudio). **Sin `Co-Authored-By`** ni otra línea de atribución. Mensaje en español que explique el porqué.
- Si `git commit` falla por `.git/index.lock` (el worktree comparte `.git` con los otros cortes), esperar y reintentar; no borrar el lock salvo > 1 min sin proceso git vivo.
- **Archivos compartidos con otros cortes** (`desk/api/db.py`, `app.py`, `routes/risk.py`, `risk/scenarios.py`, `risk/var.py`, `src/python_bindings/qfpy.cpp`, `desk/ui/src/api/client.ts`, `api/types.ts`, `App.tsx`, `Shell.tsx`, `RiskScreen.tsx`, `MethodologyScreen.tsx`): solo añadir, en **un bloque contiguo** delimitado por `# --- corte 6: … ---` / `// --- corte 6: … ---` y `# --- fin corte 6 ---`, sin reordenar, renombrar ni reformatear lo existente. Este corte **no toca** `risk/var.py`, `qfpy.cpp`, `api/types.ts`, `App.tsx` ni `Shell.tsx`.
- Python valida, orquesta, suma/resta, ordena y persiste; no hay fórmulas de pricing nuevas (la exposición simulada y el CVA salen de `qfxva`). TS solo presenta.
- Validación en la frontera con `desk/api/validation.py`: `body_object()`, `number(d, name, gt=, ge=, lt=, le=, required=, default=)`, `integer(d, name, ge=, le=, required=)`, `choice(d, name, options, default=)`, `text(d, name, required=)`, `iso_date(d, name, required=True)`, `finite_number(v)`, `has_non_finite(obj)`, `ensure_finite(payload)` (400 si hay no finitos), `MAX_AMOUNT = 1e13`, `MAX_HORIZON_DAYS`, `NON_FINITE_MESSAGE`. Toda respuesta JSON numérica pasa por `ensure_finite`. `request.args` sirve como `d` para los validadores.
- Errores: `ApiError(status, mensaje_en_español, field)` (`desk/api/errors.py`) → `{"error", "field"}`. `NotImplementedError` → 501 (handler existente); `ValueError`/`RuntimeError` → 400 "No se pudo valuar: …". Id de ruta no entero o ≥ 2^63 → 404 `field:"id"` (patrón `routes/trades._trade_id`).
- Hechos **solo de inserción**: cada tabla nueva lleva disparadores `BEFORE UPDATE`/`BEFORE DELETE` con `RAISE(ABORT, '<tabla> es solo de inserción')`. Los cambios de estado se registran insertando eventos.
- Sin flags, opciones, columnas ni pantallas no pedidas. Textos de interfaz en español. Montos con `fmtMoney(v, 'MXN')`, fechas con `fmtDate`, cifras con clase `.num`.
- **Este archivo (`plan.md`) no lo editan los implementadores**: cada tarea reporta en su mensaje final firmas reales, cifras de pruebas, commit y decisiones; el orquestador lo anota en "Anotado por los implementadores".

### Firmas existentes que se usan (reales)
- `desk/api/db.py`: `SCHEMA` (script con `CREATE TABLE IF NOT EXISTS`/`CREATE TRIGGER IF NOT EXISTS`; `init_schema(conn)` lo ejecuta en cada arranque: tablas nuevas aparecen solas en bases existentes), `connect(path)`, `get_conn()`, `now_iso()`.
- `desk/api/app.py`: `create_app(db_path=None, seed=True)`; registra blueprints en `for module in (market, price, trades, risk, fixings, pnl, hedges): app.register_blueprint(module.bp)`; `_seed_if_empty` siembra `MX-DEMO` (`as_of = 2026-11-10`) y 7 operaciones en el primer arranque.
- `desk/api/market.py`: `CURVES = {"TIIE-F": {"currency":"MXN","period_days":28}, "SOFR": {"currency":"USD","period_days":365}}`, `PAIR = "USDMXN"`, `LIVE_ID = "MKT-LIVE"`; `MarketContext` (`snapshot_id`, `as_of` date, `curves` {nombre: `qfpy.YieldCurve`}, `pillars`, `spot`, `surface`, `hw` = `{"TIIE-F": {"a","sigma"}, "SOFR": {...}}`, `factors` = `{"names": ["TIIE-F","SOFR","USDMXN"], "units": ["bp","bp","ret"], "daily_vols": [4.0, 5.0, 0.0075], "correlations": [[...]]}` en `MX-DEMO`, `env`, `shifted(curve=, pillar_shifts_bp=, parallel_bp=, spot_pct=)`); `load_context(conn, id)` (404 `snapshot`); **privadas que este corte usa a propósito:** `_fetch(conn, id) -> Row(id,label,synthetic,as_of,data)` (404) y `_build_context(snapshot_id, as_of_iso, data_dict) -> MarketContext`. `data` del snapshot: `quotes` (lista `{id,curve,label,days,type,rate}`), `fx` (`{"spot", …}`), `vol_surface` (`{expiry_days,strikes,vols}`), `hw`, `factors`, `sources`. `sources_of(data)`, `data_quality(sources) -> "synthetic"|"live"|"mixed"`, `list_snapshots(conn)`.
- Rutas de mercado: `GET /api/market/snapshots`, `PUT /api/market/snapshots/<id>` `{"quotes":[{"id","rate"}], "spot"}`, `POST /api/market/<id>/roll` `{"id","as_of"}`.
- `desk/api/portfolio.py`: `load_trades(conn)` → `{"id","product","counterparty","trade_date","start_date","maturity_date" (date),"params","created_at","events"}` (`events` con `event_date` date e `id`); `trade_pv_mxn(trade, mkt, fixings=None)`; `valuation(conn, snapshot_id)` = cuerpo de `GET /api/portfolio/valuation?snapshot=` → `{"snapshot","as_of","total_mxn","rows":[{"id","product","counterparty",…,"status","notional","currency","pv","pv_mxn","warnings","error"}]}`.
- `desk/api/lifecycle.py`: `state(trade, events, on) -> {"status","terms","notional"}`; aplica solo eventos con `event_date <= on`; `no_pactada` si `on < trade_date`.
- `desk/api/valuation.py`: `value_trade(trade, mkt, fixings=None) -> {"status","notional","currency","pv","pv_mxn","warnings"}` (usa `trade["events"]`; `pv_mxn` 0 si no `viva`); `is_live(trade, on)`.
- `desk/api/settlement.py`: `settled_flows(trade, fixings, d0, d1, fallback_spot, mkt=None) -> (flows, warnings)` (ventana `(d0, d1]`, flujos con `amount_mxn`); `merge_warnings(*groups)`.
- `desk/api/pnl.py`: `compute_pnl(conn, from_id, to_id)` → `{"from":{"snapshot","as_of"},"to":{…},"total_mxn","totals":{"pv_from","pv_to","settled","pnl"},"rows":[{"id","product","counterparty","status_from","status_to","pv_from","pv_to","settled","pnl","error","warnings"}]}`; `pnl = pv_to − pv_from + settled` con `settled_flows(trade, fixings, from.as_of, to.as_of, mkt_to.spot, mkt_to)`. 404 `snapshot`, 400 `to` si `from` es posterior. Ruta `GET /api/pnl?from=&to=` (400 `from`/`to` si faltan).
- `desk/api/fixings.py`: `INDICES = ("TIIE-F","SOFR","USDMXN")`, `load_all(conn) -> {índice: {date: valor}}` (tasas en decimal, USDMXN en MXN por USD), `import_csv(conn, text)` (patrón a copiar: encabezado exacto, BOM, todo o nada, `{"inserted","unchanged"}`, 409 si la clave existe con otro valor).
- `desk/api/fred.py`: `fetch_dexmxus(url) -> [(fecha ISO, MXN por USD)]` ascendente (admite `file://`); config `app.config["FRED_DEXMXUS_URL"]`. `desk/api/marketdata.py`: `treasury_5y_history(mdf_db) -> [(fecha ISO, decimal)]` ascendente (409 si historia corta); config `app.config["MDF_DB"]`. Pruebas: `desk/api/tests/mdf_fixture.py` (`make_mdf_db(...)`, `make_fred_csv(path, rows)`).
- `desk/api/risk/dv01.py`: `compute_dv01(conn, snapshot_id)` → `{"curves": {curva: {"parallel_mxn", "points"}}, "errors", …}` (DV01 = PV base − PV +1 pb).
- `desk/api/risk/var.py` (**no se modifica**): `compute_var(conn, snapshot_id, body)` (valida `horizon_days` `gt=0, le=MAX_HORIZON_DAYS` y `confidence` `gt=0, lt=1`, `factor_vols` opcional) → `{"snapshot","var_mxn","horizon_days","confidence","factors":[{"factor","unit","exposure_mxn","daily_vol","var_mxn"}],"errors"}`; `_exposure_fns(mkt, fixings)` (privada, la reutiliza `hist_var`): una función `(trade, pv_base) -> exposición MXN` por factor en el orden de `mkt.factors["names"]`; curvas en MXN por **+1 pb**, USDMXN en MXN por **unidad de rendimiento** (diferencia central ±1 %).
- `desk/api/risk/scenarios.py`: `_validate(body)` (400 `scenarios`, mensajes `"Escenario %d: …"`), `_shock(mkt, spec)`, `shock = _shock`, `DEFAULT_SCENARIOS` (los 8 de la pantalla), `run_scenarios(conn, snapshot_id, body)` → `{"snapshot","scenarios":[{"name","total_mxn","trades":[{"id","pnl_mxn","error"}]}]}`. `run_scenarios` busca `_validate` y `_shock` como globales del módulo en cada llamada.
- `desk/api/routes/risk.py`: blueprint `risk` (`/api/risk`), `POST /dv01`, `POST /scenarios`, `POST /var` (cada una: `body_object()`, `text(body,"snapshot")`, delega, `jsonify(ensure_finite(...))`).
- C++ `qf::xva` (`include/qf/xva/`): `FlatHazardRate(lambda)` (`SP(t)=exp(−λt)`), `NettingSet::add(notional, fixedRate, maturity_years, frequency_per_year, SwapType)` (swaps vainilla; a tiempo `t` revalúa el swap residual, vencidos se omiten), `SimParams{nPaths, monitorDates (años, >0, ascendentes), seed}`, `CVACalculator(model, credit, lgd, params).compute(ns, env) -> CVAResult{cva, dva, fva, bcva, profile[TimeStep{t, epe, ene, survProb, ownSurvProb, contribution, …}]}`. La simulación: rejilla `ceil(T_max·252)` pasos, trayectoria `p` con semilla `seed + p`, curva condicional HW por `conditionalBondPrice` en tenores fijos; trayectorias degeneradas aportan 0. **No calcula PFE** (lo añade T2). Python: módulo `qfxva` (`src/python_bindings/xva_bindings.cpp`): `FlatHazardRate(lambda_=)`, `SwapType.Payer/Receiver`, `NettingSet().add(notional=, fixed_rate=, maturity=, frequency=, swap_type=)`, `SimParams(n_paths=, monitor_dates=, seed=)`, `CVACalculator(hw, credit, lgd, params).compute(netting_set, env)`; el modelo es `qfpy.HullWhite(a=, sigma=, curve=)` y `env` un `qfpy.MarketEnvironment(curve)`. Prueba de referencia: `web/tests/test_xva.py`, `tests/test_CVACalculator.cpp`.
- Pruebas backend: fixtures `app`, `client` de `desk/api/tests/conftest.py` (base temporal sembrada con `MX-DEMO` y 7 operaciones: `irs` Alfa TIIE-F payer 500 M, `irs` Beta TIIE-F receiver 250 M, `irs` Gamma SOFR payer 20 M USD, `fx_forward` Alfa y Beta, `fx_option` Gamma, `cap_floor` Alfa; contrapartes `"Banco Alfa (sintético)"`, `"Banco Beta (sintético)"`, `"Banco Gamma (sintético)"`); `empty_portfolio(client)`; `desk/api/tests/hedge_fixture.py`: `roll(client, source, new_id, days) -> as_of ISO`, `load_fixings(client, index, start, end, value)`, `par_irs(...)`. Alta de operación: `POST /api/trades {"product","counterparty","params", "snapshot"?, "trade_date"?, …}`; evento: `POST /api/trades/<id>/events` (ver `routes/trades.py`).
- Interfaz: `src/api/client.ts` (`request<T>(method, path, body?)` **privada**, antepone `/api`; `ApiError {status, field}`; `riskVar`, `riskScenarios`, `listTrades`, `listSnapshots`), `src/api/types.ts` (`VarResponse`, `ScenarioSpec`, `ScenariosResponse`, `TradeError`, `SnapshotSummary`, …), `src/lib/format.ts` (`fmtNumber(v, dec)`, `fmtMoney(v, ccy)`, `fmtRate(dec)`, `fmtDate(iso)`), `src/state/SnapshotContext.tsx` (`useSnapshot() -> {snapshotId, setSnapshotId, snapshot, snapshots, reload, error}`), `src/components/EChart.tsx` (`EChart({option, height=260, ariaLabel})`, `cssColor(token)`), `src/screens/RiskScreen.tsx` (`export function RiskScreen()` arma `Dv01Section`, `VarSection`, `ScenariosSection`; sus pruebas lo montan **sin router**, dentro de `SnapshotProvider`, con `vi.mock('../api/client')`), `src/screens/MethodologyScreen.tsx` (grupos `<h2 className="meth-group">` con arreglos `Section[]` `{id, title, items: {label, text}[]}` y `SectionBlock`; test con helper `row(label)` sobre `<dt>`). Ruta `/riesgo` ya existe en `App.tsx` y en `Shell`.

### Esquema SQLite nuevo (lo agrega T3 al final de `db.SCHEMA`, en el bloque `corte 6`)
```sql
CREATE TABLE IF NOT EXISTS factor_history (factor TEXT NOT NULL, source TEXT NOT NULL, date TEXT NOT NULL,
  value REAL NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY (factor, source, date));
CREATE TABLE IF NOT EXISTS limits (id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT NOT NULL, key TEXT NOT NULL,
  metric TEXT NOT NULL, amount REAL NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS limit_events (id INTEGER PRIMARY KEY AUTOINCREMENT, limit_id INTEGER NOT NULL REFERENCES limits(id),
  type TEXT NOT NULL, amount REAL, reason TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS limit_breaches (id INTEGER PRIMARY KEY AUTOINCREMENT, limit_id INTEGER NOT NULL REFERENCES limits(id),
  snapshot_id TEXT NOT NULL, as_of TEXT NOT NULL, amount REAL NOT NULL, usage REAL NOT NULL, pct REAL NOT NULL,
  created_at TEXT NOT NULL, UNIQUE (limit_id, as_of));
CREATE TABLE IF NOT EXISTS counterparty_credit (id INTEGER PRIMARY KEY AUTOINCREMENT,
  counterparty_id INTEGER NOT NULL REFERENCES counterparties(id), hazard_rate REAL NOT NULL, recovery REAL NOT NULL,
  as_of TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS scenario_sets (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
  description TEXT, scenarios TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS scenario_set_events (id INTEGER PRIMARY KEY AUTOINCREMENT,
  set_id INTEGER NOT NULL REFERENCES scenario_sets(id), type TEXT NOT NULL, created_at TEXT NOT NULL);
```
Más dos disparadores (`<tabla>_no_update`, `<tabla>_no_delete`, mensaje `'<tabla> es solo de inserción'`) para **cada una** de las siete tablas. `scenarios` es JSON (lista de especificaciones normalizadas). `limits.amount` es el monto de alta; el vigente sale de los eventos. Ninguna migración: `init_schema` las crea en bases existentes. `counterparties` no se toca.

### Constantes y vocabulario (fijos; los define T3)
```python
# desk/api/risk/explain.py
STEPS = [("carry", "Paso del tiempo y liquidaciones"), ("curve:TIIE-F", "Tasas TIIE-F"), ("curve:SOFR", "Tasas SOFR"),
         ("fx", "Tipo de cambio"), ("vol", "Volatilidad"), ("new_trades", "Operaciones nuevas"),
         ("events", "Eventos"), ("residual", "Residuo")]
# las curvas: "TIIE-F" primero y luego las demás de market.CURVES en orden alfabético ("curve:<nombre>")
# desk/api/risk/factor_history.py
FACTORS = {"TIIE-F": "bp", "SOFR": "bp", "USDMXN": "ret"}
SOURCES = ("synthetic", "csv", "live", "fixings")
OBSERVED_PRIORITY = ("csv", "live", "fixings")      # en "observed", por (factor, fecha) gana el primero
SOURCE_LABEL = {"synthetic": "Sintético (semilla fija, vols y correlaciones de MX-DEMO)", "csv": "CSV cargado",
                "live": "FRED / MarketDataFeed", "fixings": "Fijaciones cargadas"}
CSV_HEADER = "factor,date,value"
MAX_ABS = {"bp": 1000.0, "ret": 1.0}                # cota de |valor| por unidad (como var._MAX_FACTOR_VOL)
SYNTHETIC_SEED = 20261110
SYNTHETIC_DAYS = 500                               # días hábiles (lun–vie) estrictamente anteriores al as_of de MX-DEMO
MAX_GAP_DAYS = 5                                   # al derivar: pares de observaciones a más de 5 días naturales se omiten
# desk/api/risk/hist_var.py
DEFAULT_WINDOW, MIN_WINDOW, MAX_WINDOW = 250, 60, 10000
HISTORY_SOURCES = ("synthetic", "observed")
# desk/api/risk/limits.py
SCOPES = ("counterparty", "factor", "portfolio")
METRICS = ("pv_exposure", "dv01", "fx_delta", "var")
METRICS_BY_SCOPE = {"counterparty": ("pv_exposure",), "factor": ("dv01", "fx_delta"), "portfolio": ("var",)}
PORTFOLIO_KEY = "portfolio"
LIMIT_EVENT_TYPES = ("create", "change", "retire")
ALERT_PCT, BREACH_PCT = 80.0, 100.0
STATUS_OK, STATUS_ALERT, STATUS_BREACH = "ok", "alerta", "exceso"
LIMIT_ACTIVE, LIMIT_RETIRED = "activo", "baja"
VAR_LIMIT_PARAMS = {"horizon_days": 1, "confidence": 0.99}   # el límite de VaR es sobre el paramétrico a 1 día 99 %
# desk/api/risk/credit.py
DEFAULT_HAZARD, DEFAULT_RECOVERY = 0.01, 0.40
N_PATHS, SEED, PFE_QUANTILE = 500, 42, 0.95
COVERED_PRODUCTS = ("irs",)
CVA_NOTICE = "CVA informativo: no entra al PV ni a la contabilidad de coberturas"
ASSUMED_NOTE = "Supuesto: probabilidad de incumplimiento 1 % anual y recuperación 40 % (sin parámetros capturados)"
# desk/api/risk/scenario_sets.py
BUILTIN_SETS  # ver "Escenarios" abajo
SET_EVENT_TYPES = ("retire",)
MAX_NAME = 80
```

### Reglas de cálculo (fijas)

**P&L explicado (D1, `explain.explain_pnl(conn, from_id, to_id)`).** Primero `res = pnl.compute_pnl(conn, from_id, to_id)` (valida y da el `pnl` oficial por operación). Mercados: `M_from = load_context(from)`, `M_to = load_context(to)`; datos crudos `D_from`, `D_to` (`json.loads(market._fetch(...)["data"])`). Contextos híbridos, todos con `as_of = to.as_of`, armados con `market._build_context("%s→%s" % (from_id, to_id), to_as_of_iso, datos)` sobre copias profundas de `D_from` en las que se reemplaza, en cascada y acumulando: `H0` = `D_from` tal cual (mercado de `from` rodado a la fecha `to`: mismos pilares en días); `H1` = `H0` con las cotizaciones (`quotes` con `curve == "TIIE-F"`) de `D_to`; `H2` = `H1` + las de `SOFR` (y luego cada curva restante en orden alfabético); `H3` = + `fx` completo de `D_to`; `H4` = + `vol_surface` y `hw` de `D_to`. Para cada operación `T` de `res["rows"]` sin `error`:
- Si `T.trade_date > from.as_of` (pactada en la ventana): `new_trades = pnl`, todos los demás componentes 0, `residual = 0`.
- Si no: `T0` = copia de `T` con `events` filtrados a `event_date <= from.as_of`. `V(t, M) = valuation.value_trade(t, M, fixings)["pv_mxn"]`; `S(t) = Σ amount_mxn` de `settled_flows(t, fixings, from.as_of, to.as_of, M_to.spot, M_to)`. Entonces `carry = V(T0,H0) − pv_from + S(T0)` (`pv_from` de la fila de `compute_pnl`); `curve:TIIE-F = V(T0,H1) − V(T0,H0)`; `curve:SOFR = V(T0,H2) − V(T0,H1)`; `fx = V(T0,H3) − V(T0,H2)`; `vol = V(T0,H4) − V(T0,H3)`; `new_trades = 0`; `events = (pv_to + settled) − (V(T0,H4) + S(T0))` (`pv_to`, `settled` de la fila de `compute_pnl`; vale 0 si no hubo eventos en la ventana).
- `residual = pnl − Σ(los otros siete)`. Por construcción la cascada telescopa: el residuo es ruido numérico o mercado no asignado a ningún bloque.
- Si la cascada lanza para una operación con `pnl` válido: todos los componentes 0, `residual = pnl`, `explain_error = str(e)`. Filas con `error` en `compute_pnl`: `pnl` y `components` `null`, no suman.
- Totales: `totals.pnl = res["total_mxn"]`; `totals.components[k] = Σ` de filas sin `error`. Invariantes (R1): por fila y en total `Σ components == pnl` a 1e-6 MXN; con mercado idéntico rodado, `curve:*`, `fx`, `vol` = 0.0 exactos.

**Historia de factores (D2, `factor_history`).** Valores: `TIIE-F`, `SOFR` = cambio diario en **pb**; `USDMXN` = rendimiento **logarítmico** diario (`ln(s_t/s_{t−1})`, como `live_market.daily_vol_logret`). Cada fila fechada en el día del segundo dato.
- `import_csv(conn, text)`: encabezado exacto `factor,date,value`, BOM y `\r\n` admitidos, todo o nada; `factor` ∈ `FACTORS`, fecha ISO, valor finito con `|valor| ≤ MAX_ABS[unidad]` (400 `csv` con `"Fila n: …"`); fuente `csv`; misma clave `(factor,"csv",fecha)` con el mismo valor → `unchanged`, con otro → 409 `csv` sin insertar nada. → `{"inserted","unchanged"}`.
- `derive(conn, source, config)`: `source` ∈ `("fixings","live")` (400 `source`). `fixings`: de `fixings.load_all(conn)`, por índice, pares de fechas consecutivas ordenadas; tasas `(v_t − v_{t−1})·1e4`, USDMXN `ln(v_t/v_{t−1})`; pares con más de `MAX_GAP_DAYS` días naturales entre sí se omiten y se cuentan en `skipped_gaps`. `live`: `SOFR` de `marketdata.treasury_5y_history(config["MDF_DB"])` (pb; la misma aproximación que `MKT-LIVE`) y `USDMXN` de `fred.fetch_dexmxus(config["FRED_DEXMXUS_URL"])`; un error de lectura → 502 `source` con el motivo (409 de historia corta se propaga). Inserción idempotente como el CSV (clave existente con otro valor → 409 `source`). → `{"source","inserted","unchanged","skipped_gaps"}`.
- `seed_synthetic(conn) -> int`: si existe el snapshot `MX-DEMO` y no hay filas `synthetic`, inserta `SYNTHETIC_DAYS` días hábiles anteriores a su `as_of` con normales correlacionadas (`random.Random(SYNTHETIC_SEED)`, `gauss(0,1)`, Cholesky en Python puro de la matriz `factors["correlations"]` de `MX-DEMO`, escaladas por `daily_vols`); devuelve las filas insertadas (0 si no aplica). Sin commit. Reproducible: mismas cifras en cualquier base.
- `summary(conn)` → ver contrato.
- `window(conn, history_source, as_of, n) -> (dates, {factor: [valores]}, by_source)`: fechas `<= as_of` con valor para **los tres** factores, las últimas `n` en orden ascendente. `synthetic` usa solo filas `synthetic`; `observed` usa `csv`/`live`/`fixings` con la prioridad `OBSERVED_PRIORITY` por `(factor, fecha)`. `by_source` = cuántas observaciones (factor-fecha) aportó cada fuente.

**VaR histórico (D3, `hist_var.compute_hist_var(conn, snapshot_id, body)`).** Valida en este orden: `horizon_days` (`gt=0, le=MAX_HORIZON_DAYS`), `confidence` (`gt=0, lt=1`), `window_days` (`integer`, `ge=MIN_WINDOW, le=MAX_WINDOW`, por omisión 250), `history_source` (`choice` en `HISTORY_SOURCES`; por omisión `"synthetic"` si `market.data_quality(market.sources_of(data))` del snapshot es `"synthetic"`, si no `"observed"`); luego 404 `snapshot`. Exposiciones: mismo recorrido que `var.compute_var` (operaciones `viva`, `var._exposure_fns(mkt, fixings)`, operaciones que fallan van a `errors`). Historia: `window(...)`; con menos de `window_days` fechas → **409** `field:"window_days"`, mensaje `"Historia insuficiente: hay %d días con los tres factores hasta el %s (se piden %d)"`. P&L diario `p_t = Σ_k exposure_k · x_{k,t}` (pb para curvas, rendimiento para USDMXN). Pérdidas `L_t = −p_t` ordenadas de mayor a menor; `k = max(1, ceil(round(N·(1−confidence), 9)))`; `var_mxn = L_(k) · sqrt(horizon_days)`; `es_mxn = media(L_(1..k)) · sqrt(horizon_days)` (≥ VaR por construcción); `worst_day` = fecha y `p_t` (sin escalar) de la mayor pérdida. `method` ausente o `"parametric"` → `var.compute_var` sin cambios (la ruta despacha; respuesta idéntica, R3 1e-12).

**Límites (D4, `limits`).** Combinaciones: `counterparty` → `pv_exposure` con `key` = nombre de contraparte existente; `factor` → `dv01` con `key` ∈ `market.CURVES`, o `fx_delta` con `key == "USDMXN"`; `portfolio` → `var` con `key = "portfolio"` (si falta, se pone). Uso a un snapshot (solo límites `activo`):
- `pv_exposure` = `max(Σ pv_mxn de las filas de portfolio.valuation(conn, snap) con counterparty == key y error nulo, 0)`.
- `dv01` = `|dv01.compute_dv01(conn, snap)["curves"][key]["parallel_mxn"]|`.
- `fx_delta` = `|exposure_mxn de USDMXN en var.compute_var(conn, snap, VAR_LIMIT_PARAMS)| / 100` (MXN por 1 % de USDMXN).
- `var` = `var_mxn` de esa misma llamada.
- `pct = usage / amount · 100`; con `p = round(pct, 9)`: `p < 80` → `ok`; `80 ≤ p ≤ 100` → `alerta`; `p > 100` → `exceso`. Cada cálculo se hace una vez por petición (no por límite); `errors` = unión de los `errors` de las rutas usadas (sin repetir id).
- Monto vigente = `amount` del último evento `create`/`change`; estado `baja` si hay evento `retire`. `check` inserta en `limit_breaches` una fila por límite en `exceso` cuya `(limit_id, as_of)` no exista (devuelve solo las nuevas); repetir `check` con la misma fecha no inserta nada.

**Crédito (D5, `credit`).** Por contraparte, con las operaciones `viva` al `as_of`:
- Cubiertas: `product == "irs"`. Las demás van a `excluded` con `reason = "La exposición simulada solo cubre swaps de tasa (irs): <producto> se excluye"`.
- Conjuntos de compensación (netting sets): uno por `(contraparte, curva)`; no hay compensación entre monedas (el perfil de la contraparte es la suma de sus conjuntos; cota superior conservadora).
- Cada `irs` entra a `qfxva.NettingSet().add(notional = lifecycle.state(...)["notional"], fixed_rate = terms["fixed_rate"], maturity = (maturity_date − as_of).days / 365, frequency = 365 / CURVES[curve]["period_days"], swap_type = Payer si side == "payer" si no Receiver)`.
- Modelo `qfpy.HullWhite(a=mkt.hw[curva]["a"], sigma=mkt.hw[curva]["sigma"], curve=mkt.curves[curva])`; `env = qfpy.MarketEnvironment(mkt.curves[curva])`.
- Rejilla mensual común por contraparte: fechas `as_of + k meses` (mismo día; si no existe, último día del mes), `k = 1..K` con `K` el primero cuya fecha ≥ último vencimiento cubierto de la contraparte; `t_k = días/365`. Punto `t = 0` en `as_of`.
- `pts = qfxva.simulate_exposure(hw, ns, qfxva.SimParams(n_paths=N_PATHS, monitor_dates=[t_k], seed=SEED), pfe_quantile=PFE_QUANTILE)` (T2). En `t_k`: `ee = epe·fx`, `pfe = max(pfe_raw, epe)·fx`, con `fx = 1` (MXN) o `mkt.spot` (USD, `SOFR`).
- En `t = 0`: `ee = pfe = max(PV_ns, 0)` con `PV_ns = Σ value_trade(...)["pv_mxn"]` de sus operaciones cubiertas (así EE(0) = max(PV,0) exacto, R4).
- `cva_ns = qfxva.CVACalculator(hw, qfxva.FlatHazardRate(lambda_=hazard), lgd=1−recovery, params=mismos SimParams).compute(ns, env).cva · fx`; `cva` contraparte = Σ. Con `hazard = 0` es 0 exacto.
- Parámetros: vigentes = fila de `counterparty_credit` con mayor `id` para esa contraparte; si no hay, `DEFAULT_HAZARD`/`DEFAULT_RECOVERY` con `assumed: true`. Cambiar = insertar fila nueva (`as_of` = fecha UTC de hoy).

**Escenarios (D6, `scenario_sets` + bloque en `scenarios.py`).** Tipo nuevo `"combined"`: `{"name", "type": "combined", "shocks": [<choque>, …]}`; cada choque es una especificación `parallel`/`steepener`/`fx_spot` sin `name` (1 a 8 choques; no se anidan); se aplican en el orden dado sobre el mismo contexto (`mkt.shifted` encadenado). Conjuntos de fábrica (`builtin`, sin id, no se dan de baja; los históricos son **aproximaciones** rotuladas):
- `"Por omisión"`: los 8 de `scenarios.DEFAULT_SCENARIOS`.
- `"Depreciación 2008"`: un escenario combinado del mismo nombre: USDMXN +35 %, TIIE-F +100 pb paralelo, SOFR −200 pb paralelo.
- `"2016 elecciones EE. UU."`: USDMXN +12 %, TIIE-F +75 pb, SOFR +25 pb.
- `"Marzo 2020"`: USDMXN +25 %, TIIE-F −100 pb, SOFR −150 pb.
Nombre único (tras `strip`, comparación exacta) entre los de fábrica y los activos. Baja lógica = evento `retire`. Correr un conjunto = `run_scenarios` con sus `scenarios` (mismo motor: resultado idéntico a mandarlos en línea, R5).

### Contrato HTTP nuevo o cambiado (backend ↔ interfaz)
Rutas nuevas en `desk/api/routes/risk_adv.py` (blueprint `risk_adv`, sin prefijo, registrado en `app.py`). Cambios en `routes/risk.py`: solo `POST /api/risk/var` (`method`) y `POST /api/risk/scenarios` (`set`). Todo lo demás existente no cambia de forma.

**`GET /api/pnl/explain?from=MX-DEMO&to=D1`** → 200 (400 `from`/`to` si faltan; 404 `snapshot`; 400 `to` si `from` es posterior).
```json
{"from": {"snapshot": "MX-DEMO", "as_of": "2026-11-10"}, "to": {"snapshot": "D1", "as_of": "2026-12-10"},
 "steps": [{"key": "carry", "label": "Paso del tiempo y liquidaciones"}, {"key": "curve:TIIE-F", "label": "Tasas TIIE-F"},
           {"key": "curve:SOFR", "label": "Tasas SOFR"}, {"key": "fx", "label": "Tipo de cambio"}, {"key": "vol", "label": "Volatilidad"},
           {"key": "new_trades", "label": "Operaciones nuevas"}, {"key": "events", "label": "Eventos"}, {"key": "residual", "label": "Residuo"}],
 "totals": {"pnl": -812345.12, "components": {"carry": 120000.0, "curve:TIIE-F": -950000.0, "curve:SOFR": 3000.0, "fx": 14654.88,
            "vol": 0.0, "new_trades": 0.0, "events": 0.0, "residual": 0.0}},
 "rows": [{"id": 1, "product": "irs", "counterparty": "Banco Alfa (sintético)", "pnl": -400000.0,
           "components": {"carry": 50000.0, "curve:TIIE-F": -450000.0, "curve:SOFR": 0.0, "fx": 0.0, "vol": 0.0,
                          "new_trades": 0.0, "events": 0.0, "residual": 0.0},
           "error": null, "explain_error": null, "warnings": []}]}
```
`warnings` = las de la fila de `compute_pnl`. Filas en el orden de `compute_pnl`.

**`POST /api/risk/var`** gana `method` (`choice`, `("parametric","historical")`, por omisión `parametric`; 400 `method`). Ausente o `parametric` → respuesta actual **sin cambios** (sin clave `method`). `historical` → cuerpo `{"snapshot","horizon_days","confidence","method":"historical","window_days"?,"history_source"?}` → 200:
```json
{"snapshot": "MX-DEMO", "method": "historical", "var_mxn": 2345678.9, "es_mxn": 2789012.3, "horizon_days": 10.0, "confidence": 0.99,
 "window_days": 250, "worst_day": {"date": "2026-03-12", "pnl_mxn": -1234567.8},
 "history": {"source": "synthetic", "label": "Sintético (semilla fija, vols y correlaciones de MX-DEMO)",
             "from": "2025-11-13", "to": "2026-11-09", "observations": 250, "by_source": {"synthetic": 750}},
 "factors": [{"factor": "TIIE-F", "unit": "bp", "exposure_mxn": -152000.0}, {"factor": "SOFR", "unit": "bp", "exposure_mxn": 9000.0},
             {"factor": "USDMXN", "unit": "ret", "exposure_mxn": 230000000.0}],
 "errors": []}
```
`history.label` = `SOURCE_LABEL["synthetic"]` o `"Observada: CSV cargado, FRED / MarketDataFeed y fijaciones (en ese orden de prioridad)"`. 409 `window_days` si falta historia.

**`GET /api/factor-history`** → `{"factors": [{"factor": "TIIE-F", "unit": "bp", "sources": [{"source": "synthetic", "label": "…", "count": 500, "first": "2024-12-11", "last": "2026-11-09"}]}, …]}` (los tres factores siempre, `sources` solo las que tienen filas, en el orden de `SOURCES`).
**`POST /api/factor-history/csv`** `{"csv": "factor,date,value\nTIIE-F,2026-11-09,1.5\nUSDMXN,2026-11-09,-0.004"}` → 200 `{"inserted": 2, "unchanged": 0}` (`csv` no texto → 400 `csv`).
**`POST /api/factor-history/derive`** `{"source": "fixings"}` → 200 `{"source": "fixings", "inserted": 41, "unchanged": 0, "skipped_gaps": 2}`.

**`GET /api/limits`** → `{"limits": [limit…]}` por `id` (activos y de baja). Límite:
```json
{"id": 1, "scope": "counterparty", "key": "Banco Alfa (sintético)", "metric": "pv_exposure", "amount": 50000000.0,
 "status": "activo", "created_at": "2026-11-11T18:00:00+00:00",
 "events": [{"id": 1, "type": "create", "amount": 50000000.0, "reason": null, "created_at": "2026-11-11T18:00:00+00:00"}]}
```
**`POST /api/limits`** `{"scope": "counterparty", "key": "Banco Alfa (sintético)", "metric": "pv_exposure", "amount": 50000000, "reason": "Política 2026"}` → 201 límite (inserta `limits` y el evento `create` en una transacción). Validación en orden: `scope` (`choice`, 400 `scope`); `metric` (`choice` en `METRICS`, 400; fuera de `METRICS_BY_SCOPE[scope]` → 400 `metric`); `key` (`text`; contraparte inexistente → 400 `key`; curva/`USDMXN` inválidos → 400 `key`; `portfolio` admite ausente o `"portfolio"`); `amount` (`gt=0, le=MAX_AMOUNT`, 400 `amount`); `reason` texto opcional; ya hay un límite `activo` con la misma `(scope, key, metric)` → 409 `key`.
**`POST /api/limits/<id>/events`** `{"type": "change", "amount": 60000000, "reason": "…"}` o `{"type": "retire", "reason": "…"}` → 201 límite. 404 `id`; `type` ∈ `("change","retire")` (400 `type`); `change` exige `amount` (400); límite ya de `baja` → 409 `id`.
**`GET /api/limits/usage?snapshot=MX-DEMO`** (400 `snapshot` si falta, 404 si no existe) → 
```json
{"snapshot": "MX-DEMO", "as_of": "2026-11-10", "thresholds": {"alert_pct": 80.0, "breach_pct": 100.0},
 "usage": [{"limit_id": 1, "scope": "counterparty", "key": "Banco Alfa (sintético)", "metric": "pv_exposure",
            "amount": 50000000.0, "usage": 41000000.0, "pct": 82.0, "status": "alerta"}],
 "errors": []}
```
**`POST /api/limits/check?snapshot=MX-DEMO`** → 200 lo mismo más `"new_breaches": [breach…]`. Exceso (`GET /api/limits/breaches` → `{"breaches": [...]}` por `id` descendente):
```json
{"id": 1, "limit_id": 2, "scope": "factor", "key": "TIIE-F", "metric": "dv01", "snapshot": "MX-DEMO", "as_of": "2026-11-10",
 "amount": 100000.0, "usage": 152000.0, "pct": 152.0, "created_at": "2026-11-11T18:00:00+00:00"}
```

**`GET /api/credit/params`** → `{"params": [{"counterparty": "Banco Alfa (sintético)", "hazard_rate": 0.01, "recovery": 0.4, "as_of": null, "assumed": true, "history": []}, …]}` (todas las contrapartes de `counterparties`, por nombre; `history` = filas guardadas `{"hazard_rate","recovery","as_of","created_at"}` de la más nueva a la más vieja).
**`POST /api/credit/params`** `{"counterparty": "Banco Alfa (sintético)", "hazard_rate": 0.02, "recovery": 0.35}` → 201 el elemento de esa contraparte. `counterparty` texto (400), inexistente → 404 `counterparty`; `hazard_rate` `ge=0, le=1`; `recovery` `ge=0, lt=1`.
**`GET /api/credit/exposure?snapshot=MX-DEMO`** (400/404 `snapshot`) →
```json
{"snapshot": "MX-DEMO", "as_of": "2026-11-10", "n_paths": 500, "seed": 42, "pfe_quantile": 0.95, "notice": "CVA informativo: no entra al PV ni a la contabilidad de coberturas",
 "counterparties": [{"counterparty": "Banco Alfa (sintético)", "hazard_rate": 0.01, "recovery": 0.4, "assumed": true,
   "assumed_note": "Supuesto: probabilidad de incumplimiento 1 % anual y recuperación 40 % (sin parámetros capturados)",
   "pv_mxn": -1250000.0, "cva_mxn": 3456.7,
   "netting_sets": [{"curve": "TIIE-F", "currency": "MXN", "trades": [1], "pv_mxn": -1250000.0, "cva_mxn": 3456.7}],
   "profile": [{"date": "2026-11-10", "t": 0.0, "ee_mxn": 0.0, "pfe_mxn": 0.0}, {"date": "2026-12-10", "t": 0.0822, "ee_mxn": 812000.0, "pfe_mxn": 3100000.0}],
   "excluded": [{"id": 4, "product": "fx_forward", "reason": "La exposición simulada solo cubre swaps de tasa (irs): fx_forward se excluye"}]}],
 "excluded": [{"id": 4, "counterparty": "Banco Alfa (sintético)", "product": "fx_forward", "reason": "…"}],
 "warnings": []}
```
Contrapartes = las que tienen operaciones `viva` al `as_of`, por nombre; sin `irs` cubiertos → `netting_sets: []`, `profile: []`, `pv_mxn: 0.0`, `cva_mxn: 0.0`. `assumed_note` es `null` si `assumed` es falso. `pv_mxn` = Σ PV de las cubiertas.

**`GET /api/scenario-sets`** → `{"sets": [set…]}`: primero los 4 de fábrica en el orden de arriba, luego los activos por `id`. Conjunto:
```json
{"id": null, "name": "Marzo 2020", "builtin": true, "approximation": true, "status": "activo",
 "description": "Aproximación histórica: USDMXN +25 %, TIIE-F −100 pb y SOFR −150 pb a la vez",
 "scenarios": [{"name": "Marzo 2020", "type": "combined", "shocks": [{"type": "fx_spot", "pct": 25.0},
   {"type": "parallel", "curve": "TIIE-F", "bp": -100.0}, {"type": "parallel", "curve": "SOFR", "bp": -150.0}]}],
 "created_at": null}
```
Los guardados: `"id": 5, "builtin": false, "approximation": false, "description": <texto o null>, "created_at": "…"`.
**`POST /api/scenario-sets`** `{"name": "Choque Banxico", "description": "…", "scenarios": [{"name": "TIIE-F +100", "type": "parallel", "curve": "TIIE-F", "bp": 100}]}` → 201 conjunto. `name` texto ≤ `MAX_NAME` (400 `name`); `scenarios` vía `scenarios._validate` (400 `scenarios`, admite `combined`); nombre repetido → 409 `name`.
**`POST /api/scenario-sets/<id>/retire`** → 200 conjunto con `"status": "baja"`; 404 `id` (incluye ids no enteros); ya de baja → 409 `id`.
**`POST /api/risk/scenarios`** acepta `{"snapshot": "MX-DEMO", "set": "Marzo 2020"}` en lugar de `scenarios`: respuesta = la actual más `"set": "Marzo 2020"`. `set` y `scenarios` juntos → 400 `set`; `set` no texto → 400 `set`; inexistente o de baja → 404 `set`. Sin `set`, nada cambia.

### Interfaz Python interna (fija; T3 la deja con stubs `NotImplementedError` salvo lo marcado "real")
- `desk/api/risk/explain.py` (T4): `STEPS` (real), `explain_pnl(conn, from_id, to_id) -> dict`.
- `desk/api/risk/factor_history.py` (T5): constantes (reales), `seed_synthetic(conn) -> int` (**stub que devuelve 0**, no lanza: lo llama `create_app`), `import_csv(conn, text) -> dict`, `derive(conn, source, config) -> dict`, `summary(conn) -> dict`, `window(conn, history_source, as_of, n)`.
- `desk/api/risk/hist_var.py` (T5): constantes (reales), `compute_hist_var(conn, snapshot_id, body) -> dict`.
- `desk/api/risk/limits.py` (T6): constantes (reales), `list_limits(conn)`, `create_limit(conn, body)`, `add_event(conn, limit_id, body)`, `usage(conn, snapshot_id)`, `check(conn, snapshot_id)`, `list_breaches(conn)` (escrituras sin commit).
- `desk/api/risk/credit.py` (T7): constantes (reales), `list_params(conn)`, `set_params(conn, body)`, `exposure(conn, snapshot_id)`.
- `desk/api/risk/scenario_sets.py` (T8): `BUILTIN_SETS` (real, según "Escenarios"), `list_sets(conn)`, `create_set(conn, body)`, `retire_set(conn, set_id)`, `resolve(conn, name) -> List[spec]` (404 `set`).
- `desk/api/routes/risk_adv.py` (T3, **final**: ninguna otra tarea lo edita): todas las rutas nuevas; cada una valida lo que es de la ruta (`from`/`to`/`snapshot` presentes como en `routes/pnl.py`; ids con el patrón `_trade_id` y `field:"id"`; `csv` texto), delega, hace `conn.commit()` en escrituras y `jsonify(ensure_finite(...))`; códigos 201 donde el contrato lo dice. `credit` importa `qfxva` de forma perezosa (dentro de las funciones, tras `from desk.api.qf import qfpy`) para que el backend arranque aunque T2 no haya terminado.

### Interfaz: piezas fijas (las crea U1)
- `src/api/client.ts`: añadir al final, en bloque `corte 6`, `export { request as apiRequest };` (nada más).
- `src/api/riskTypes.ts` (nuevo): transcripción exacta del contrato: `ExplainStepKey`, `ExplainStep`, `ExplainRow`, `ExplainResponse`, `VarMethod`, `HistVarResponse`, `HistVarBody`, `FactorHistorySummary`, `FactorHistoryImport`, `FactorHistoryDerive`, `LimitScope`, `LimitMetric`, `LimitStatus` (`'ok'|'alerta'|'exceso'`), `LimitEvent`, `Limit`, `CreateLimitBody`, `LimitEventBody`, `LimitUsage`, `LimitUsageResponse`, `LimitBreach`, `LimitCheckResponse`, `CreditParams`, `CreditProfilePoint`, `CreditNettingSet`, `CreditExcluded`, `CreditCounterparty`, `CreditExposureResponse`, `Shock`, `CombinedScenario`, `LibraryScenario` (= `ScenarioSpec | CombinedScenario`), `ScenarioSet`, `CreateScenarioSetBody`, `SetScenariosResponse` (= `ScenariosResponse & {set: string}`).
- `src/api/riskClient.ts` (nuevo; usa `apiRequest`): `pnlExplain(from, to)`, `riskVarHistorical(snapshot, {horizon_days, confidence, window_days?, history_source?})`, `factorHistorySummary()`, `importFactorHistoryCsv(csv)`, `deriveFactorHistory(source)`, `listLimits() -> Limit[]`, `createLimit(body)`, `addLimitEvent(id, body)`, `limitUsage(snapshot)`, `checkLimits(snapshot)`, `listBreaches() -> LimitBreach[]`, `creditExposure(snapshot)`, `listCreditParams() -> CreditParams[]`, `setCreditParams(body)`, `listScenarioSets() -> ScenarioSet[]`, `createScenarioSet(body)`, `retireScenarioSet(id)`, `runScenarioSet(snapshot, set)`. Las que devuelven listas desenvuelven (`limits`, `breaches`, `params`, `sets`). Parámetros de consulta con `encodeURIComponent`.
- `src/screens/risk/labels.ts`: `RISK_TABS = [{id:'sensibilidades',label:'Sensibilidades'},{id:'var',label:'VaR'},{id:'pnl',label:'P&L explicado'},{id:'limites',label:'Límites'},{id:'credito',label:'Crédito'},{id:'escenarios',label:'Escenarios'}]`, `LIMIT_SCOPE_LABEL` (`counterparty` "Contraparte", `factor` "Factor", `portfolio` "Portafolio"), `LIMIT_METRIC_LABEL` (`pv_exposure` "Exposición (PV positivo neto)", `dv01` "DV01 por curva", `fx_delta` "Delta USDMXN (MXN por 1 %)", `var` "VaR paramétrico 1 día 99 %"), `LIMIT_STATUS_LABEL` (`ok` "En límite", `alerta` "Alerta", `exceso` "Exceso"), `HISTORY_SOURCE_LABEL` (`synthetic` "Sintética", `observed` "Observada").
- `src/screens/risk/RiskTabs.tsx` (`export function RiskTabs({sensitivities}: {sensitivities: ReactNode})`): `role="tablist"` con un `role="tab"` por `RISK_TABS` (`aria-selected`), panel `role="tabpanel"`; pestaña inicial = `?tab=` de `window.location.search` si es válida, si no `sensibilidades`; al cambiar, `window.history.replaceState(null, '', '?tab=<id>')` conservando el resto de la consulta (sin router: las pruebas actuales montan `RiskScreen` sin router). Solo monta la pestaña activa. Pestañas: `sensibilidades` → `sensitivities`; `var` → `<VarTab/>`; `pnl` → `<PnlExplainTab/>`; `limites` → `<LimitsTab/>`; `credito` → `<CreditTab/>`; `escenarios` → `<ScenarioLibraryTab/>`.
- `src/screens/RiskScreen.tsx`: solo cambia el cuerpo de `RiskScreen()`: `<div className="risk"><h1>Riesgo</h1><RiskTabs sensitivities={<>…lo de hoy (risk__top con Dv01Section y VarSection, y ScenariosSection)…</>} /></div>` más el `import` (bloque `corte 6`). "Sensibilidades" = todo lo actual, sin cambios.
- `src/screens/risk/risk-adv.css` (U1; los demás solo lo leen): clases comunes `.radv-card`, `.radv-grid2` (dos columnas ≥ 900 px, una debajo), `.radv-note`, `.radv-note--warn`, `.radv-note--error`, `.radv-tiles`, `.radv-tile`, `.radv-table` (con `overflow-x: auto` en su contenedor `.radv-scroll`), `.radv-bar` (barra de uso con `--pct`), colores por `data-status`. Todo con los tokens existentes de `styles/`.
- Cada pestaña (`VarTab.tsx`, `PnlExplainTab.tsx`, `LimitsTab.tsx`, `CreditTab.tsx`, `ScenarioLibraryTab.tsx` en `src/screens/risk/`) es `export function X()` sin props, lee el snapshot de `useSnapshot()`, importa solo de `riskClient`/`client`, y tiene su `.css` y `.test.tsx` propios (`vi.mock('../../api/riskClient')`, montada dentro de `SnapshotProvider` con `listSnapshots` simulado como en `RiskScreen.test.tsx`). Errores de la API con su `error` en `.radv-note--error` `role="alert"`; 409 de historia y avisos en `.radv-note--warn` `role="status"`.

## Supuestos del planificador
1. **Configuración de CMake:** además del comando del encargo se pasan `-DPYTHON_EXECUTABLE=/home/claudio/anaconda3/bin/python -DCMAKE_BUILD_TYPE=Debug`, como el `build/` del repo principal, para que `qfpy`/`qfxva` se construyan para el Python 3.8 del desk.
2. **PFE en C++:** `qf::xva` no calcula PFE; se añade una función de biblioteca nueva `qf::xva::simulateExposure` (archivos nuevos, sin tocar `CVACalculator`) que reproduce exactamente sus trayectorias y la expone `qfxva`. `qfpy.cpp` no se toca. El PFE reportado es `max(cuantil 95 %, EE)` para garantizar PFE ≥ EE.
3. **Crédito solo para `irs`** (lo único que modela `NettingSet`); cap/floor, forwards y opciones FX se excluyen con aviso. Un conjunto de compensación por `(contraparte, curva)`, sin compensación entre monedas; EE(0) se toma de la valuación del desk (no del modelo), así EE(0) = max(PV,0) exacto. 500 trayectorias, semilla 42 (compilación Debug).
4. **P&L explicado:** las operaciones pactadas en la ventana van completas a "Operaciones nuevas"; "Eventos" es un paso separado; los flujos liquidados sin eventos van en "Paso del tiempo"; la cascada telescopa, así que el residuo es solo ruido numérico o datos fuera de los bloques (se declara en Metodología).
5. **Historia de factores:** la tabla lleva además `source` y `created_at`, con clave `(factor, source, date)`, para que la semilla sintética no choque con datos reales. El VaR usa historia `synthetic` en snapshots sintéticos y `observed` en los demás (se puede forzar con `history_source`). USDMXN en rendimiento logarítmico. La semilla (500 días hábiles) se inserta al arrancar si existe `MX-DEMO` y no hay filas sintéticas. De FRED/MarketDataFeed se deriva solo lo que ya existe: SOFR con el proxy 5Y de `MKT-LIVE` y USDMXN; TIIE-F solo de fijaciones o CSV.
6. **VaR histórico:** percentil empírico `k = ceil(N·(1−c))`-ésima mayor pérdida, ES = media de las `k` mayores, escalado por raíz del horizonte; máximo 10 000 días. La interfaz no carga CSV de historia (la API sí).
7. **Límites:** `fx_delta` en MXN por 1 % de USDMXN; el límite de VaR es sobre el paramétrico a 1 día y 99 %; `limits` también es solo de inserción (el monto vigente sale de los eventos); umbrales con el porcentaje redondeado a 9 decimales.
8. **Escenarios históricos:** se modelan con un tipo nuevo `combined` (varios choques a la vez), añadido a `scenarios.py` reasignando `_validate`/`_shock`/`shock` en un bloque al final (sin editar el código existente). Valores aproximados: 2008 (USDMXN +35 %, TIIE-F +100 pb, SOFR −200 pb), 2016 (+12 %, +75 pb, +25 pb), marzo 2020 (+25 %, −100 pb, −150 pb). Los 4 conjuntos de fábrica viven en código, no en la base.
9. **Interfaz:** "Sensibilidades" conserva toda la pantalla actual (DV01, VaR paramétrico y escenarios fijos) para no romper sus pruebas; la pestaña activa va en `?tab=` sin router. Las rutas nuevas viven en `routes/risk_adv.py`; `routes/risk.py` solo gana el despacho de `method` y `set`.

## Tareas

### T1 — Configurar y compilar el worktree; línea base de las cuatro suites
- **Modelo:** haiku · **Depende de:** — · **R:** R8 (línea base)
- **Objetivo:** dejar `build/` listo (con `qfpy` y `qfxva` para Python 3.8) y anotar las cifras de partida.
- **Archivos:** ninguno versionado (`build/` está en `.gitignore`). Sin commit.
- **Pasos:**
  1. `cd /home/claudio/Git/qf-wt/corte6 && cmake -S . -B build -DPYTHON_EXECUTABLE=/home/claudio/anaconda3/bin/python -DCMAKE_BUILD_TYPE=Debug 2>&1 | tail -3`.
  2. `cmake --build build -j3 2>&1 | tail -3` (varios minutos; correr en segundo plano y esperar si hace falta). Comprobar `ls build/src/qfpy.cpython-38-x86_64-linux-gnu.so build/src/qfxva.cpython-38-x86_64-linux-gnu.so`.
  3. Correr las cuatro suites del Contexto (C++ sin recompilar: `(cd build && ctest 2>&1 | tail -3)`; bindings; backend; `cd desk/ui && npm test 2>&1 | tail -5 && npm run build 2>&1 | tail -5`). Borrar `desk/ui/dist` no hace falta (no se versiona).
- **Verificación:** los dos `.so` existen; `ctest` → `100% tests passed`; `pytests` → `OK`; backend sin `failed`; vitest y build sin errores. Reportar las cuatro cifras.

### T2 — PFE en `qf::xva` y `qfxva.simulate_exposure`
- **Modelo:** sonnet · **Depende de:** T1 · **R:** R4 (base: EE/PFE simulados), R8
- **Objetivo:** que Python obtenga EPE, ENE y PFE por fecha con las mismas trayectorias que `CVACalculator`.
- **Archivos:** `include/qf/xva/exposure_profile.hpp` (nuevo), `src/xva/exposure_profile.cpp` (nuevo), `src/CMakeLists.txt` (añadir `xva/exposure_profile.cpp` justo después de `xva/cva_calculator.cpp`), `tests/test_ExposureProfile.cpp` (nuevo), `tests/CMakeLists.txt` (añadirlo a `qf_tests`), `src/python_bindings/xva_bindings.cpp` (añadir al final del módulo), `tests/test_xva_exposure_py.py` (nuevo, unittest).
- **API:**
  ```cpp
  namespace qf::xva {
  struct ExposurePoint { double t; double epe; double ene; double pfe; };
  /// Valor neto del netting set sobre las MISMAS trayectorias que CVACalculator::compute (rejilla
  /// ceil(T_max·252) pasos mínimo 10, semilla seed+p, curva condicional HW en los mismos tenores, Linear);
  /// trayectorias degeneradas cuentan V = 0. epe = media de max(V,0), ene = media de max(−V,0),
  /// pfe = cuantil empírico de max(V,0): orden ascendente, índice ceil(q·n)−1.
  /// Lanza invalid_argument con las mismas validaciones de SimParams que CVACalculator y si q ∉ (0,1).
  std::vector<ExposurePoint> simulateExposure(const qf::models::IRateModel& model, const NettingSet& ns,
                                              const SimParams& params, double pfeQuantile = 0.95);
  }
  ```
  Binding: `py::class_<ExposurePoint>(m, "ExposurePoint")` con `t, epe, ene, pfe` de solo lectura; `m.def("simulate_exposure", [](const qf::models::HullWhite& hw, const NettingSet& ns, const SimParams& p, double q) {...}, py::arg("hw"), py::arg("netting_set"), py::arg("params"), py::arg("pfe_quantile") = 0.95)`. Doxygen en lo nuevo.
- **Pasos (TDD):**
  1. Tests C++ (patrón de `tests/test_CVACalculator.cpp`): con el modelo y netting set de ese test y `seed = 42`, `epe`/`ene` de cada punto iguales a `CVACalculator::compute(...).profile[k].epe/.ene` a 1e-12 relativo; `pfe ≥ 0`; `pfe(0.99) ≥ pfe(0.95) ≥ pfe(0.5)`; netting set vacío → todo 0; `q = 0`, `q = 1`, fechas vacías/no positivas/desordenadas y `nPaths = 0` lanzan.
  2. Implementar en archivos nuevos (no tocar `cva_calculator.*`).
  3. Binding y `tests/test_xva_exposure_py.py` (unittest, patrón de `tests/test_desk_bindings_py.py`; importa `qfpy` y `qfxva` desde `build/src`): misma igualdad EPE vs `CVACalculator` a 1e-12 y `pfe ≥ 0`.
  4. **Compilar solo** `cmake --build build -j3 --target qf qf_tests qfxva 2>&1 | tail -3` (si se añadió un archivo, `cmake -S . -B build` antes reconfigura). **No** construir `all` ni `qfpy`: hay pruebas de backend corriendo en paralelo con el `qfpy.so` actual.
- **Verificación:** `(cd build && ctest -R "ExposureProfile|CVACalculator" --output-on-failure 2>&1 | tail -3; ctest 2>&1 | tail -3)` → `100% tests passed`; `/home/claudio/anaconda3/bin/python -m unittest discover -s tests -p "test_xva_exposure_py.py" -v 2>&1 | tail -3` → `OK`; `cmake --build build --target pytests 2>&1 | tail -3` → `OK`.
- **Commit:** las siete rutas.

### T3 — Esquema, módulos y rutas del corte 6 como contrato (backend)
- **Modelo:** sonnet · **Depende de:** T1 · **R:** base de R1–R5; R2 (disparadores de eventos y bitácora), R8
- **Objetivo:** dejar tablas, constantes, rutas y despachos registrados; lo que falta responde 501 con el contrato para que T4–T8 solo rellenen sus módulos.
- **Archivos:** `desk/api/db.py` (bloque `corte 6` al final de `SCHEMA`), `desk/api/app.py` (bloque `corte 6` justo después del `for … register_blueprint`: importar y registrar `routes.risk_adv.bp`; y si `seed` es verdadero, abrir conexión, `factor_history.seed_synthetic(conn)`, `commit`, cerrar), `desk/api/routes/risk.py` (bloque `corte 6`: en `risk_var`, tras `text(body,"snapshot")`, `method = choice(body, "method", ("parametric","historical"), default="parametric")` y si es `historical` devolver `hist_var.compute_hist_var(...)`; en `risk_scenarios`, si `"set" in body`: 400 `set` si también viene `scenarios` o si `set` no es texto no vacío, `specs = scenario_sets.resolve(conn, set)`, correr `scenarios.run_scenarios(conn, snapshot, {"scenarios": specs})` y añadir `"set"` a la respuesta; esas son las únicas líneas que cambian en funciones existentes), `desk/api/routes/risk_adv.py` (nuevo, final), `desk/api/risk/explain.py`, `factor_history.py`, `hist_var.py`, `limits.py`, `credit.py`, `scenario_sets.py` (nuevos: constantes reales y funciones stub `raise NotImplementedError` según "Interfaz Python interna"; `seed_synthetic` devuelve 0), `desk/api/tests/test_risk_adv_schema.py` (nuevo) y los archivos de prueba stub `desk/api/tests/test_pnl_explain.py`, `test_hist_var.py`, `test_limits.py`, `test_credit.py`, `test_scenario_sets.py` (nuevos, cada uno con un solo test `test_contract_stub` que su tarea reemplaza).
- **Pasos:**
  1. Esquema y disparadores del Contexto (siete tablas, catorce disparadores).
  2. Módulos con constantes y stubs; `scenario_sets.BUILTIN_SETS` real (lista de dicts con `name`, `approximation`, `description`, `scenarios`).
  3. `routes/risk_adv.py` con las 15 rutas nuevas del contrato (explain, factor-history ×3, limits ×6, credit ×3, scenario-sets ×3).
  4. `routes/risk.py` y `app.py` como se describe; `method` inválido → 400 `method`.
  5. `test_risk_adv_schema.py`: `UPDATE`/`DELETE` por SQL directo sobre cada una de las siete tablas (filas insertadas por SQL) → `sqlite3.DatabaseError`; una base creada, a la que se le borran por SQL las siete tablas y sus disparadores, recupera todo al volver a llamar `create_app` sobre la misma ruta sin perder operaciones; `POST /api/risk/var` sin `method` y con `"method":"parametric"` dan exactamente el mismo JSON que antes (comparar con `var.compute_var` llamado directo); `"method":"x"` → 400 `method`; `POST /api/risk/scenarios` con `set` y `scenarios` → 400 `set`; `GET /api/limits/abc/…` ids no enteros → 404 `id`.
  6. Cada `test_<área>.py` stub: una petición representativa de su área → 501 JSON (`explain`: `GET /api/pnl/explain?from=MX-DEMO&to=MX-DEMO`; `hist_var`: `POST /api/risk/var` con `method: historical`; `limits`: `GET /api/limits`; `credit`: `GET /api/credit/params`; `scenario_sets`: `GET /api/scenario-sets`).
- **Verificación:** `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests/test_risk_adv_schema.py desk/api/tests/test_pnl_explain.py desk/api/tests/test_hist_var.py desk/api/tests/test_limits.py desk/api/tests/test_credit.py desk/api/tests/test_scenario_sets.py -q 2>&1 | grep -E "passed|failed"` y suite backend completa sin `failed`.
- **Commit:** las 15 rutas de archivo.

### T4 — P&L explicado por cascada
- **Modelo:** sonnet · **Depende de:** T3 · **Paralela con:** T2, T5, T6, T7, T8 · **R:** R1
- **Objetivo:** `GET /api/pnl/explain` según el contrato y las reglas D1.
- **Archivos:** `desk/api/risk/explain.py`, `desk/api/tests/test_pnl_explain.py` (reemplaza el stub).
- **Pasos:** implementar `explain_pnl` (reglas del Contexto). Tests: (a) para MX-DEMO→D1 rodado (+30 días, `hedge_fixture.roll`) con fijaciones TIIE-F cargadas en la ventana (`hedge_fixture.load_fixings`), `Σ components == pnl` de `/api/pnl` a 1e-6 por fila y en total, y `curve:*`, `fx`, `vol`, `new_trades`, `events` = 0.0 exactos (todo en `carry`); (b) mercado movido: rodar a +30 días, `PUT /api/market/snapshots/D1` con todas las cotizaciones TIIE-F +25 pb y SOFR −25 pb y `spot` × 1.03; identidad a 1e-6 por fila y total, `|residual total| < 0.02·|pnl total|` o `< 1e-4 · nocional bruto` (Σ nocionales de las 7 operaciones en MXN), y `curve:TIIE-F` del swap Alfa tiene el signo esperado (payer gana con tasas al alza); (c) una operación pactada dentro de la ventana (`POST /api/trades` con el snapshot D1) cae entera en `new_trades`; (d) una terminación con fecha en la ventana (`POST /api/trades/<id>/events`) deja su efecto en `events` y la identidad se mantiene; (e) `from` posterior → 400 `to`; falta `from` → 400 `from`; snapshot inexistente → 404 `snapshot`.
- **Verificación:** `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests/test_pnl_explain.py -q 2>&1 | grep -E "passed|failed"`; suite backend completa sin `failed`.
- **Commit:** las dos rutas.

### T5 — Historia de factores y VaR histórico
- **Modelo:** sonnet · **Depende de:** T3 · **Paralela con:** T2, T4, T6, T7, T8 · **R:** R3
- **Objetivo:** tabla `factor_history` operativa (semilla, CSV, derivación) y `method: "historical"` según el contrato.
- **Archivos:** `desk/api/risk/factor_history.py`, `desk/api/risk/hist_var.py`, `desk/api/tests/test_hist_var.py` (reemplaza el stub), `desk/api/tests/test_factor_history.py` (nuevo).
- **Pasos:** implementar según "Historia de factores" y "VaR histórico". Tests de historia: la semilla crea 500 filas por factor solo una vez (crear la app dos veces sobre la misma base) y da las mismas cifras en dos bases distintas; su desviación muestral queda a ±15 % de `daily_vols` de MX-DEMO; CSV: encabezado malo → 400 `csv`, fila con factor desconocido/valor fuera de cota → 400 con `"Fila n"`, recarga idéntica → `unchanged`, mismo día con otro valor → 409 sin insertar nada; `derive fixings` con fijaciones TIIE-F 7.00 %/7.10 % en dos días hábiles seguidos → 10.0 pb, con un hueco de 8 días → `skipped_gaps`; `derive live` con `mdf_fixture.make_mdf_db` y `make_fred_csv` (rutas en `app.config`) inserta SOFR y USDMXN; `GET /api/factor-history` con la forma del contrato. Tests de VaR: **R3** — cargar por CSV 5 000 días hábiles de normales correlacionadas generadas en el test (`random.Random(7)`, vols y correlaciones de MX-DEMO), `POST /api/risk/var` con `method: historical`, `history_source: "observed"`, `window_days: 5000`, `horizon_days: 1`, `confidence: 0.99` queda a menos del 10 % del paramétrico del mismo snapshot; `es_mxn ≥ var_mxn`; `window_days: 6000` con la semilla de 500 → 409 `window_days`; `window_days: 59` → 400; sin `method` el JSON es idéntico (1e-12) al de `var.compute_var`; `worst_day` es la fecha de la mayor pérdida recalculada en el test con las exposiciones devueltas; escalado `var(h=4) = 2·var(h=1)` a 1e-9.
- **Verificación:** `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests/test_hist_var.py desk/api/tests/test_factor_history.py -q 2>&1 | grep -E "passed|failed"`; suite backend completa sin `failed`.
- **Commit:** las cuatro rutas.

### T6 — Límites, uso y bitácora de excesos
- **Modelo:** sonnet · **Depende de:** T3 · **Paralela con:** T2, T4, T5, T7, T8 · **R:** R2
- **Objetivo:** rutas de límites según el contrato y las reglas D4.
- **Archivos:** `desk/api/risk/limits.py`, `desk/api/tests/test_limits.py` (reemplaza el stub).
- **Pasos:** implementar. Tests: alta de cada combinación válida (201, evento `create`) y cada rechazo del orden de validación; duplicado activo → 409 `key`; `change` inserta evento y cambia `amount` (la fila de `limits` no cambia); `retire` → `baja`, sale de `usage`, otro evento → 409 `id`; uso recalculado desde las rutas existentes (`GET /api/portfolio/valuation`, `POST /api/risk/dv01`, `POST /api/risk/var` con 1 día y 0.99) para las cuatro métricas a 1e-6; estados en los umbrales: montos `usage/0.7999`, `usage/0.8`, `usage/1.0`, `usage/1.0001` → `ok`, `alerta`, `alerta`, `exceso`; `check` dos veces con el mismo snapshot inserta un solo exceso por límite, con otro snapshot de otra fecha inserta otro; `UPDATE`/`DELETE` en `limit_events` y `limit_breaches` por SQL → error.
- **Verificación:** `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests/test_limits.py -q 2>&1 | grep -E "passed|failed"`; suite backend completa sin `failed`.
- **Commit:** las dos rutas.

### T7 — Exposición, PFE y CVA por contraparte
- **Modelo:** sonnet · **Depende de:** T2, T3 · **Paralela con:** T4, T5, T6, T8 · **R:** R4
- **Objetivo:** `/api/credit/*` según el contrato y las reglas D5, usando `qfxva`.
- **Archivos:** `desk/api/risk/credit.py`, `desk/api/tests/test_credit.py` (reemplaza el stub).
- **Pasos:** implementar (importar `qfxva` dentro de las funciones, tras `from desk.api.qf import qfpy`). Tests sobre el portafolio sembrado: por contraparte y punto `ee ≥ 0`, `pfe ≥ ee`; `profile[0].ee_mxn == max(pv_mxn, 0)` a 1e-6 relativo (y comprobado contra `GET /api/portfolio/valuation` sumando los `irs` vivos de esa contraparte); la rejilla es mensual y su última fecha ≥ último vencimiento; Gamma (SOFR) se convierte con el `spot`; `hazard_rate = 0` → `cva_mxn == 0.0`; `cva(0.01) < cva(0.05)`; `POST /api/credit/params` dos veces deja dos filas (por SQL) y la vigente es la última; `fx_forward`, `fx_option`, `cap_floor` aparecen en `excluded` con su `reason`; validaciones (`recovery: 1` → 400, contraparte inexistente → 404 `counterparty`); misma respuesta en dos llamadas (semilla fija). Mantener el archivo bajo ~60 s en Debug.
- **Verificación:** `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests/test_credit.py -q 2>&1 | grep -E "passed|failed"`; suite backend completa sin `failed`.
- **Commit:** las dos rutas.

### T8 — Biblioteca de escenarios y escenarios combinados
- **Modelo:** sonnet · **Depende de:** T3 · **Paralela con:** T2, T4–T7 · **R:** R5
- **Objetivo:** conjuntos con nombre y el tipo `combined`, sin cambiar el comportamiento de los escenarios actuales.
- **Archivos:** `desk/api/risk/scenario_sets.py`, `desk/api/risk/scenarios.py` (solo un bloque `corte 6` al final), `desk/api/tests/test_scenario_sets.py` (reemplaza el stub).
- **Pasos:**
  1. En `scenarios.py`, al final: `_validate_single = _validate`, `_shock_single = _shock`; nuevo `_validate(body)` que recorre la lista: los no `combined` se validan con `_validate_single({"scenarios": [spec]})[0]` (re-lanzando su error con el índice correcto: `_bad(i, <mensaje sin el prefijo "Escenario 1: ">)`); los `combined` exigen `shocks` lista de 1 a 8 especificaciones válidas no `combined` (se validan igual, con `name` provisional que luego se quita); nuevo `_shock(mkt, spec)` que encadena `_shock_single` para `combined`; `shock = _shock`.
  2. `scenario_sets.py` según el contrato.
- **Tests:** crear, listar (fábrica primero), nombre repetido (también contra uno de fábrica) → 409 `name`, baja → no aparece y 409 al repetir, `retire` de id inexistente → 404; **R5**: `POST /api/risk/scenarios {"set": "<guardado>"}` da exactamente (1e-12) los mismos `scenarios` que mandarlos en línea, igual con `"Marzo 2020"` contra su combinado en línea; un `combined` de un solo choque coincide con el escenario simple; un `combined` TIIE-F +50 y USDMXN +10 % ≠ suma de ambos solo por interacción (y sobre un `irs` TIIE-F puro es igual a 1e-9); `set` inexistente o de baja → 404 `set`; `test_risk_dv01_scenarios.py` y `test_hedges_effectiveness.py` siguen verdes.
- **Verificación:** `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests/test_scenario_sets.py desk/api/tests/test_risk_dv01_scenarios.py desk/api/tests/test_hedges_effectiveness.py -q 2>&1 | grep -E "passed|failed"`; suite backend completa sin `failed`.
- **Commit:** las tres rutas.

### U1 — Contrato en la interfaz: tipos, cliente, pestañas y stubs
- **Modelo:** sonnet · **Depende de:** — (en paralelo con T1) · **R:** R6 (base)
- **Objetivo:** que U2–U6 solo rellenen su pestaña.
- **Archivos:** `desk/ui/src/api/client.ts` (solo la línea del bloque `corte 6`), `desk/ui/src/api/riskTypes.ts` (nuevo), `desk/ui/src/api/riskClient.ts` (nuevo), `desk/ui/src/api/riskClient.test.ts` (nuevo), `desk/ui/src/screens/RiskScreen.tsx` (solo `RiskScreen()` e import), `desk/ui/src/screens/risk/labels.ts`, `RiskTabs.tsx`, `RiskTabs.test.tsx`, `risk-adv.css` (nuevos), y stubs `desk/ui/src/screens/risk/VarTab.tsx`, `PnlExplainTab.tsx`, `LimitsTab.tsx`, `CreditTab.tsx`, `ScenarioLibraryTab.tsx` (cada uno `export function X() { return <section data-testid="<x>-stub" /> }`).
- **Pasos:** según "Interfaz: piezas fijas". Tests: `riskClient.test.ts` (con `fetch` simulado como `client.test.ts`: método, ruta y cuerpo de cada función, desenvolvimiento de listas, `ApiError` con `field`); `RiskTabs.test.tsx` (seis pestañas en orden y con su texto; por omisión `Sensibilidades` muestra el contenido recibido; clic en `VaR` monta el stub y deja `?tab=var` en `window.location.search`; `?tab=credito` inicial abre Crédito; valor inválido cae en Sensibilidades). `RiskScreen.test.tsx` existente debe seguir verde sin cambios.
- **Verificación:** `cd desk/ui && npm test 2>&1 | tail -5 && npm run build 2>&1 | tail -5` sin errores.
- **Commit:** todas las rutas listadas.

### U2 — Pestaña VaR: paramétrico e histórico lado a lado
- **Modelo:** sonnet · **Depende de:** U1 · **Paralela con:** U3–U7 · **R:** R6 (D7 VaR), presentación de R3
- **Archivos:** `desk/ui/src/screens/risk/VarTab.tsx`, `VarTab.css`, `VarTab.test.tsx` (nuevos o reemplazo del stub).
- **Pasos:** entradas `Horizonte (días)` (10), `Confianza (%)` (99), `Ventana (días)` (250) y un botón `Calcular`; llama `riskVar` (paramétrico, de `client.ts`) y `riskVarHistorical` en paralelo y muestra dos tarjetas en `.radv-grid2`: **Paramétrico** (VaR, tabla por factor con exposición y vol) y **Histórico** (VaR, ES, peor día con fecha y P&L, tabla por factor con exposición, y "Historia usada": `HISTORY_SOURCE_LABEL`, `label`, rango `from`–`to`, observaciones). Diferencia `Histórico − Paramétrico` en MXN y % bajo ambas. 409 de historia → nota `role="status"` en la tarjeta histórica con el mensaje del backend (la paramétrica sigue visible); 400 → mensaje bajo el campo (`field`). Recalcula al cambiar de snapshot.
- **Tests:** ambas tarjetas con sus cifras formateadas; peor día y rango visibles; 409 solo en la histórica; error 400 `window_days` bajo su campo; recalcula al cambiar de snapshot (patrón `SwitchTo` de `RiskScreen.test.tsx`).
- **Verificación:** `npm test` y `npm run build` sin errores.
- **Commit:** las tres rutas.

### U3 — Pestaña P&L explicado: cascada y tabla por operación
- **Modelo:** sonnet · **Depende de:** U1 · **Paralela con:** U2, U4–U7 · **R:** R6 (D7 P&L), presentación de R1
- **Archivos:** `desk/ui/src/screens/risk/PnlExplainTab.tsx`, `PnlExplainTab.css`, `PnlExplainTab.test.tsx`.
- **Pasos:** selectores `Desde` y `Hasta` con `snapshots` de `useSnapshot()` (rotulados `id · fmtDate(as_of)`); por omisión `Hasta` = snapshot actual y `Desde` = el de mayor `as_of` anterior; si no hay anterior, `Desde` = actual y `Hasta` = el siguiente posterior; si solo hay uno, nota "Se necesitan dos snapshots"; `?from=&to=` en la URL inicial tienen prioridad. Gráfica de cascada con `EChart` (barras flotantes: una por paso en el orden de `steps`, más una barra final "P&L total"; colores por signo con `cssColor`), `ariaLabel="Cascada del P&L explicado"`. Tabla (en `.radv-scroll`) por operación: id, producto, contraparte, P&L y una columna por paso con su `label`; fila de totales; filas con `error` muestran el error en una celda que abarca los pasos; `explain_error` como nota en la fila. Pie: "La suma de los pasos más el residuo es el P&L de la pestaña P&L; el orden de la cascada importa (ver Metodología)".
- **Tests:** columnas en el orden de `steps`; totales; cambio de `Desde` vuelve a llamar `pnlExplain`; fila con error; opción de la gráfica con 9 barras (función pura exportada `cascadeOption(res)` probada sin ECharts).
- **Verificación:** `npm test` y `npm run build` sin errores.
- **Commit:** las tres rutas.

### U4 — Pestaña Límites: uso, alta/cambio/baja y bitácora
- **Modelo:** sonnet · **Depende de:** U1 · **Paralela con:** U2, U3, U5–U7 · **R:** R6 (D7 Límites), presentación de R2
- **Archivos:** `desk/ui/src/screens/risk/LimitsTab.tsx`, `LimitsTab.css`, `LimitsTab.test.tsx`.
- **Pasos:** tabla de uso (`limitUsage(snapshot)`): alcance, clave, métrica (`LIMIT_METRIC_LABEL`), monto, uso, barra `.radv-bar` con `--pct` (tope visual 100 %, texto con el % real), estado (`LIMIT_STATUS_LABEL`, `data-status`), acciones `Cambiar monto` (campo en línea → `addLimitEvent(id, {type:'change', amount})`) y `Dar de baja` (confirmación → `retire`). Formulario de alta: `Alcance` → `Métrica` (filtrada por alcance) → `Clave` (contraparte: nombres únicos de `listTrades()`; curva: TIIE-F/SOFR; `USDMXN`; portafolio: oculto), `Monto (MXN)`, `Motivo`. Botón `Revisar límites` → `checkLimits(snapshot)`: aviso con los excesos nuevos (o "Sin excesos nuevos"). Bitácora (`listBreaches()`): fecha de valuación, snapshot, límite, monto, uso, %. Errores 400/409 bajo el campo de su `field`.
- **Tests:** estados con su texto y `data-status`; alta manda el cuerpo correcto y refresca; métricas filtradas por alcance; cambio y baja llaman a `addLimitEvent`; `Revisar límites` muestra los nuevos; 409 `key` bajo Clave.
- **Verificación:** `npm test` y `npm run build` sin errores.
- **Commit:** las tres rutas.

### U5 — Pestaña Crédito: EE/PFE, CVA y parámetros
- **Modelo:** sonnet · **Depende de:** U1 · **Paralela con:** U2–U4, U6, U7 · **R:** R6 (D7 Crédito), presentación de R4
- **Archivos:** `desk/ui/src/screens/risk/CreditTab.tsx`, `CreditTab.css`, `CreditTab.test.tsx`.
- **Pasos:** `creditExposure(snapshot)` (puede tardar: indicador "Simulando exposición…"). Banda `role="note"` con `notice`. Tabla de contrapartes: nombre, PV cubierto, CVA, probabilidad de incumplimiento anual (%), recuperación (%), marca "Supuesto" si `assumed` (con `assumed_note` como título). Al elegir una (por omisión la primera), gráfica `EChart` de EE y PFE contra fecha (dos líneas, `ariaLabel="Perfil de exposición"`), lista de conjuntos de compensación y lista de `excluded` en `.radv-note--warn`. Formulario de parámetros (`Prob. de incumplimiento anual (%)`, `Recuperación (%)`, convertidos a decimal) → `setCreditParams` y recarga exposición; historial de parámetros de `listCreditParams()`. Pie: "500 trayectorias Hull-White, semilla fija; solo swaps de tasa; sin colateral ni compensación entre monedas".
- **Tests:** tabla y CVA; cambiar de contraparte cambia la gráfica (función pura `profileOption(cp)` probada); `excluded` visible; enviar parámetros convierte % a decimal y recarga; error 400 `recovery` bajo su campo.
- **Verificación:** `npm test` y `npm run build` sin errores.
- **Commit:** las tres rutas.

### U6 — Pestaña Escenarios: biblioteca, alta, baja y corrida
- **Modelo:** sonnet · **Depende de:** U1 · **Paralela con:** U2–U5, U7 · **R:** R6 (D7 Escenarios), presentación de R5
- **Archivos:** `desk/ui/src/screens/risk/ScenarioLibraryTab.tsx`, `ScenarioLibraryTab.css`, `ScenarioLibraryTab.test.tsx`.
- **Pasos:** lista de conjuntos (`listScenarioSets()`) con nombre, descripción, marca "De fábrica" y "Aproximación histórica" (`approximation`), y el detalle legible de cada escenario (choques como "TIIE-F +100 pb", "USDMXN +25 %", combinados unidos con " · "). Acciones: `Correr` (`runScenarioSet(snapshot, name)` → tabla por operación con una columna por escenario y fila de total, como la tabla de escenarios actual pero en `.radv-table`), `Dar de baja` (solo guardados, con confirmación). Formulario `Nuevo conjunto`: nombre, descripción y filas de escenario (nombre, tipo `parallel`/`steepener`/`fx_spot`, curva o %, valor), agregar/quitar filas → `createScenarioSet`. Errores `name`/`scenarios` bajo su campo (el mensaje de `scenarios` ya trae "Escenario n").
- **Tests:** lista con marcas; correr muestra columnas y total; alta manda el cuerpo correcto; 409 `name` bajo el campo; baja oculta el botón en los de fábrica.
- **Verificación:** `npm test` y `npm run build` sin errores.
- **Commit:** las tres rutas.

### U7 — Metodología del corte 6
- **Modelo:** haiku · **Depende de:** — (solo toca Metodología; en paralelo con todo) · **R:** R7
- **Archivos:** `desk/ui/src/screens/MethodologyScreen.tsx` (bloque `corte 6`: arreglo `RISK_ADV_SECTIONS` y su grupo al final del JSX, tras el de coberturas), `desk/ui/src/screens/MethodologyScreen.test.tsx` (tests nuevos al final).
- **Pasos:** grupo `<h2 className="meth-group">Riesgo avanzado</h2>` con una sección `SectionBlock` (id `riesgo-avanzado`, título "Riesgo avanzado") cuyos ítems (label → texto) son: **Orden de la cascada** (paso del tiempo y liquidaciones con el mercado de origen rodado a la fecha final; luego TIIE-F, SOFR y las demás curvas en orden alfabético, tipo de cambio, volatilidad —superficie y parámetros Hull-White—, operaciones nuevas y eventos; cada paso cambia un bloque del mercado de origen por el de destino); **Residuo** (por qué no es exactamente cero: la cascada suma exactamente el P&L salvo redondeo numérico y datos del mercado que no pertenecen a ningún bloque; los efectos cruzados se atribuyen al paso posterior, así que cambiar el orden cambia la atribución pero no el total); **Operaciones nuevas y eventos** (las pactadas en la ventana van completas a su paso; terminaciones, ejercicios y cambios de nocional se aíslan valuando con y sin los eventos de la ventana); **VaR histórico** (revaluación por sensibilidades —delta—, no revaluación completa: P&L diario = exposiciones por cambios históricos; percentil empírico; escala por raíz del horizonte, como el paramétrico; ventana de 250 días por omisión, mínimo 60; sin historia suficiente no se calcula); **Déficit esperado** (promedio de las pérdidas más allá del VaR al mismo nivel; siempre ≥ VaR); **Historia de factores** (cambios diarios en pb de TIIE-F y SOFR y rendimiento logarítmico de USDMXN; fuentes: CSV, fijaciones, FRED/MarketDataFeed —SOFR con el proxy del Tesoro a 5 años—; los snapshots sintéticos usan la historia sintética); **Historia sintética de MX-DEMO** (500 días hábiles generados con semilla fija 20261110 a partir de las volatilidades y correlaciones de MX-DEMO; inventada para demostración); **Límites** (por contraparte, PV positivo neto; por curva, DV01; por USDMXN, delta en MXN por 1 %; del portafolio, VaR paramétrico a 1 día y 99 %; alerta desde 80 %, exceso por encima de 100 %; se cambian con eventos, no se editan; la bitácora registra un exceso por límite y fecha de valuación); **Exposición y CVA** (simulación Hull-White de 500 trayectorias con semilla fija sobre una rejilla mensual hasta el último vencimiento; EE = exposición esperada, PFE = percentil 95 % de la exposición positiva, nunca menor que la EE; CVA = (1 − recuperación) × Σ EE × probabilidad de incumplimiento en cada intervalo); **Supuestos de crédito** (curva de riesgo plana por contraparte; por omisión 1 % anual y recuperación 40 %, rotulados como supuesto; cada cambio se guarda como fila nueva); **Alcance del crédito** (solo swaps de tasa; forwards, opciones FX y caps/floors se excluyen con aviso; un conjunto de compensación por contraparte y curva, sin compensación entre monedas; sin colateral); **CVA informativo** (no entra al PV ni a la contabilidad de coberturas); **Escenarios históricos** (aproximaciones con choques fijos aplicados a la vez: Depreciación 2008 —USDMXN +35 %, TIIE-F +100 pb, SOFR −200 pb—; 2016 elecciones EE. UU. —USDMXN +12 %, TIIE-F +75 pb, SOFR +25 pb—; Marzo 2020 —USDMXN +25 %, TIIE-F −100 pb, SOFR −150 pb—; no reproducen la curva completa de esas fechas); **Fuera de alcance** (VaR por revaluación completa y Monte Carlo del portafolio; DVA, FVA y colateral; pruebas de respaldo del VaR; flujo de aprobación de límites; curvas de crédito con plazo).
- **Tests:** con `row(label)`: "Residuo" contiene "orden"; "VaR histórico" contiene "sensibilidades"; "Historia sintética de MX-DEMO" contiene "20261110"; "CVA informativo" contiene "no entra al PV"; "Escenarios históricos" contiene "Marzo 2020" y "+35 %"; "Fuera de alcance" contiene "DVA".
- **Verificación:** `npm test` y `npm run build` sin errores.
- **Commit:** las dos rutas.

### T9 — Integración contra el backend real, capturas y las cuatro suites
- **Modelo:** sonnet · **Depende de:** T1, T2, T3, T4, T5, T6, T7, T8, U1, U2, U3, U4, U5, U6, U7 · **R:** R6 (1280 px, textos), R8, verificación de R1–R7 de punta a punta
- **Archivos:** ninguno nuevo; solo correcciones puntuales donde falle algo (commit de esas rutas). Respuestas en `/tmp/fableorchestrate/qf-corte6/it/`, capturas en `/tmp/fableorchestrate/qf-corte6/shots/` (no se commitean).
- **Pasos:**
  1. Compilación completa (ya nadie corre en paralelo): `cmake --build build -j3 2>&1 | tail -3`; las cuatro suites → verde; reportar conteos contra la línea base de T1.
  2. `rm -f /tmp/fableorchestrate/qf-corte6/it.db`; `cd desk/ui && npm run build`; backend en **5086** (comando del Contexto) en segundo plano, guardar el PID, esperar el puerto (`curl -s 127.0.0.1:5086/api/market/snapshots`).
  3. Recorrido por `curl` (guardar cada respuesta): rodar `MX-DEMO` a `D1` (+30 días), cargar fijaciones TIIE-F diarias hábiles de la ventana, mover `D1` (TIIE-F +25 pb, SOFR −25 pb, spot × 1.03); `GET /api/pnl/explain?from=MX-DEMO&to=D1` y comprobar con `python3 -c` la identidad contra `/api/pnl` (1e-6) y el residuo (< 2 % del P&L); `POST /api/risk/var` paramétrico e histórico (ES ≥ VaR; `history.source` = `synthetic`) y con `window_days: 9000` → 409; crear un límite por cada métrica con montos que den `ok`, `alerta` y `exceso`, `usage`, `check` dos veces (un solo exceso por límite); `GET /api/credit/exposure?snapshot=MX-DEMO` (EE(0) = max(PV,0), PFE ≥ EE, excluidos listados), `POST /api/credit/params` y ver subir el CVA; crear un conjunto de escenarios, correrlo por nombre y en línea (iguales), correr `"Marzo 2020"`, darlo de baja.
  4. Capturas a 1280×800 con Chrome headless propio: `google-chrome --headless=new --disable-gpu --remote-debugging-port=9346 --user-data-dir=/tmp/fableorchestrate/qf-corte6/chrome-profile --window-size=1280,800 --virtual-time-budget=15000 --screenshot=/tmp/fableorchestrate/qf-corte6/shots/<n>.png 'http://127.0.0.1:5086/riesgo?tab=<id>'` para `sensibilidades`, `var`, `pnl&from=MX-DEMO&to=D1`, `limites`, `credito`, `escenarios`, y `/metodologia` con `--window-size=1280,3000`. Revisar cada captura con `Read`: textos en español, sin desborde horizontal ni texto cortado, gráficas visibles; lo no comprobable se reporta como no verificado. Si una pestaña necesita interacción para verse, recorrerla con un script CDP sobre el puerto 9346 (sin dependencias nuevas) y revisar la consola sin errores.
  5. Detener backend y Chrome con `kill <PID>` (nunca `pkill -f`); comprobar con `ss -ltnp | grep -E ':5086|:9346'` que no queda nada. `git status --short` limpio.
  6. Último commit (correcciones o `git commit --allow-empty -m "test(desk): integración del corte 6 …"`) con `GRAPHIFY_SKIP_HOOK=1` (el grafo se regenera al fusionar a `feat/qf-desk`, no en el worktree).
- **Verificación:** reporte con cada comando y su resultado, conteos de las cuatro suites, rutas de las capturas y lista de correcciones.

## Orden y paralelismo

```
T1 (build) ──┬─ T2 (C++ PFE, solo --target qf qf_tests qfxva) ──────────┐
             └─ T3 (contrato backend) ──┬─ T4, T5, T6, T8 (paralelas) ──┤
                                        └─ T7 (también tras T2) ────────┤
U1 ──┬─ U2, U3, U4, U5, U6 (paralelas, archivos disjuntos) ─────────────├─ T9 (tras todo, sola)
U7 (en cualquier momento) ──────────────────────────────────────────────┘
```
- Grupo A (inmediato): **T1, U1, U7**.
- Grupo B: **T2 y T3** (tras T1) junto con **U2–U6** (tras U1).
- Grupo C: **T4, T5, T6, T8** (tras T3) y **T7** (tras T2 y T3).
- **T9** al final, sola.
- Archivos: cada archivo tiene un solo dueño por grupo. `routes/risk_adv.py`, `routes/risk.py`, `db.py`, `app.py` y los stubs de prueba son de T3; cada `test_<área>.py` pasa después a una sola tarea (T4–T8). Si una tarea necesita cambiar una ruta, lo reporta y lo corrige T9. C++: T1 → T2 → T9 en serie.

## Cobertura de requisitos

| R | Tareas |
|---|---|
| R1 | T4, U3, T9 |
| R2 | T3 (disparadores), T6, U4, T9 |
| R3 | T5, U2, T9 |
| R4 | T2, T7, U5, T9 |
| R5 | T8, U6, T9 |
| R6 | U1–U6, T9 (1280 px) |
| R7 | U7 |
| R8 | T1 (línea base), cada tarea (su suite verde), T9 |

## Anotado por los implementadores

(Lo llena el orquestador con lo que reporta cada tarea: firmas reales, cifras de pruebas, commits y decisiones.)

### U7
- Commit `2a4a68c` en `corte6`: solo `desk/ui/src/screens/MethodologyScreen.tsx` y `MethodologyScreen.test.tsx`.
- Tipo nuevo local: `RISK_ADV_SECTIONS: Section[]` (bloque `// --- corte 6 ---` antes de `LIMITS`); sección `id: 'riesgo-avanzado'`, h2 `meth-riesgo-avanzado`, 14 filas (Orden de la cascada, Residuo, Operaciones nuevas y eventos, VaR histórico, Déficit esperado, Historia de factores, Historia sintética de MX-DEMO, Límites, Exposición y CVA, Supuestos de crédito, Alcance del crédito, CVA informativo, Escenarios históricos, Fuera de alcance).
- JSX: grupo `<h2 className="meth-group">Riesgo avanzado</h2>` entre coberturas y "Límites de este corte", delimitado con `{/* --- corte 6 --- */}`.
- Tests: `describe('riesgo avanzado (corte 6)')` al final del archivo con helper `riskRow(label)` acotado a `#meth-riesgo-avanzado` (las etiquetas "Fuera de alcance" existen también en coberturas, así que `row()` global no sirve).
- Verificación: `npx vitest run src/screens/MethodologyScreen.test.tsx` → 14/14. `npx vite build` → OK.
- `npm run build` (tsc -b) falla por archivos de otros cortes no commiteados (`src/screens/risk/RiskTabs.test.tsx`: `toBeInTheDocument` sin tipar). No es de U7.
- `npm test` completo: 6 fallos, todos en archivos ajenos a U7 (RiskTabs, en curso).

### U1
- Commit `7c99102`. Interfaz: 287 pruebas verdes (266 base + 21 nuevas), `npm run build` sin errores. `client.ts` solo gana `export { request as apiRequest };`.
- `src/api/riskTypes.ts`: todos los tipos del contrato. Extras no listados: `HistorySource` (`'synthetic'|'observed'`), `CreditParamsBody` (`{counterparty, hazard_rate, recovery}`). `ExplainStepKey` = `'carry'|`curve:${string}`|'fx'|'vol'|'new_trades'|'events'|'residual'`; `ExplainRow.pnl`/`components` son `null` en filas con `error`. `CreditExcluded.counterparty?` solo viene en la lista global. `CreateLimitBody.key?` opcional (portfolio). `Shock` = especificación sin `name`.
- `src/api/riskClient.ts`: `pnlExplain(from,to)`, `riskVarHistorical(snapshot, HistVarBody)`, `factorHistorySummary()`, `importFactorHistoryCsv(csv)`, `deriveFactorHistory('fixings'|'live')`, `listLimits()`, `createLimit(body)`, `addLimitEvent(id, body)`, `limitUsage(snapshot)`, `checkLimits(snapshot)` (POST sin cuerpo), `listBreaches()`, `creditExposure(snapshot)`, `listCreditParams()`, `setCreditParams(body)`, `listScenarioSets()`, `createScenarioSet(body)`, `retireScenarioSet(id)` (POST sin cuerpo), `runScenarioSet(snapshot, set)`; las listas ya vienen desenvueltas.
- `labels.ts` exporta además `RiskTabId`. `RiskTabs` solo monta la pestaña activa; escribe `?tab=` con `replaceState(window.history.state, ...)` (conserva el estado del router y el resto de la consulta y el hash; el plan decía `null`). Contenedor: `<div role="tabpanel" id="risk-panel" class="radv-panel">` (flex columna, gap 16 px) con pestañas `id="risk-tab-<id>"`.
- Stubs: `data-testid` = id de la pestaña + `-stub`: `var-stub`, `pnl-stub`, `limites-stub`, `credito-stub`, `escenarios-stub`. `RiskTabs.test.tsx` mockea los cinco módulos de pestaña con sus propios stubs, así que U2–U6 pueden reemplazar los archivos sin romperlo. El proyecto NO tiene jest-dom: en pruebas usar `.textContent`, `getAttribute`, `toBeTruthy()`/`toBeNull()`.
- `risk-adv.css`: `.radv-tabs/.radv-tab` (pestañas), `.radv-panel`, `.radv-card`, `.radv-grid2` (2 columnas desde 900 px), `.radv-note` (+`--warn`, `--error`), `.radv-tiles`/`.radv-tile`, `.radv-scroll` + `.radv-table`, `.radv-status[data-status=ok|alerta|exceso]` (color de texto), `.radv-bar[data-status]` con `--pct` como número sin unidad (`style={{'--pct': 82} as CSSProperties}`; el relleno se corta en 100 %). Se carga desde `RiskTabs.tsx`. No hay clases de formulario comunes: cada pestaña define las suyas (como `.risk-field` de `RiskScreen.css`, que también se puede copiar).

### T1
- `build/` configurado y compilado en `/home/claudio/Git/qf-wt/corte6/build` (Debug, Python 3.8 de anaconda). Artefactos: `build/src/qfpy.cpython-38-x86_64-linux-gnu.so` y `build/src/qfxva.cpython-38-x86_64-linux-gnu.so`. Ninguna firma nueva; sin commit.
- Desvío del Contexto: la configuración requiere `-DCMAKE_CXX_FLAGS="-fvisibility-inlines-hidden -std=c++17 -fmessage-length=0 -march=nocona -mtune=haswell -ftree-vectorize -fPIC -fstack-protector-strong -fno-plt -O2 -ffunction-sections -pipe" -DCMAKE_POSITION_INDEPENDENT_CODE=ON -DGTest_DIR=/usr/lib/x86_64-linux-gnu/cmake/GTest` y compilador `/usr/bin/g++`. Con el entorno de conda (`CXXFLAGS` con `-isystem anaconda3/include`) el compilador conda no ve `/usr/include` (pybind11) y GTest de anaconda no enlaza.
- Para reconstruir sin reconfigurar: `env -u CXXFLAGS cmake --build build -j3` (la caché ya tiene lo anterior). Target por tarea: `--target qf qf_tests qfxva` (T2) y `--target pytests` para bindings.
- Línea base: ctest `100% tests passed, 0 tests failed out of 402`; pytests `OK`; backend `2335 passed`; vitest `20 files, 287 tests passed`; `npm run build` exit 0.
- Ningún proceso levantado (no quedó backend ni Chrome).

### U2
- Commit `479d84c` en `corte6`: `desk/ui/src/screens/risk/VarTab.tsx` (reemplaza el stub; sigue siendo `export function VarTab()` sin props), `VarTab.css` y `VarTab.test.tsx` (11 pruebas). Interfaz: 298 pruebas verdes (287 + 11), `npm run build` exit 0.
- Importa solo de `api/client` (`ApiError`, `riskVar`) y `api/riskClient` (`riskVarHistorical`); las pruebas mockean ambos módulos. Llama `riskVar(snapshot, horizonDays, confianzaDecimal)` y `riskVarHistorical(snapshot, {horizon_days, confidence, window_days})` en paralelo (no manda `history_source`: manda el backend su valor por omisión).
- Comportamiento: calcula al montar y al cambiar de snapshot con los últimos valores ya aplicados; los campos tecleados solo aplican al pulsar `Calcular` (el formulario es un `<form>`, Enter también calcula; el botón se deshabilita mientras carga). Campo no numérico: error `Ingresa un número válido` bajo el campo y no se llama a la API.
- Errores: solo un 400 cuyo `field` sea `horizon_days`/`confidence`/`window_days` va bajo su campo (`id="vartab-<horizon|confidence|window>-error"`, `aria-describedby`); la tarjeta afectada dice "Sin resultado: corrige el campo señalado.". El 409 de historia corta NO va bajo el campo: es `.radv-note--warn role="status"` solo en la tarjeta Histórico. Cualquier otro error: `.radv-note--error role="alert"` en la tarjeta que falló.
- Estructura para pruebas/capturas: `region` "Paramétrico", "Histórico" y "Diferencia" (esta solo si ambas respuestas existen; texto `MXN +250,000.00 (+25.00 %)`, `+` solo en positivos, sin % si el paramétrico es 0). Etiquetas de campos: `Horizonte (días)`, `Confianza (%)`, `Ventana (días)`. Peor día rotulado "Peor día (P&L de 1 día)" (el backend lo da sin escalar). `HISTORY_SOURCE_LABEL` en "Fuente"; `label` en "Descripción".
- Decisiones propias: `fmtVol`/`UNIT_LABEL` se duplican en `VarTab.tsx` (los de `RiskScreen.tsx` son privados y importarlos haría un ciclo con `RiskTabs`). Con `is-loading` se conservan los datos anteriores en opacidad 0.6 (como `VarSection`). No se muestra `history.by_source` (no se pidió).
- No comprobado: aspecto real a 1280 px y contra el backend real (lo cubre T9; el backend de `method: historical` aún lo hace T5).

### U3
- Commit `f69fb97` en `corte6`: `desk/ui/src/screens/risk/PnlExplainTab.tsx`, `PnlExplainTab.css`, `PnlExplainTab.test.tsx` (20 pruebas; interfaz completa 22 archivos / 318 pruebas verdes, `npm run build` exit 0).
- Exporta `PnlExplainTab(): JSX.Element` (sin props) y `cascadeOption(res: ExplainResponse): EChartsCoreOption` (pura; 9 categorías en `xAxis.data`: los `steps` en orden + "P&L total"; tres series apiladas `Base` transparente / tramo sobre el cero / tramo bajo el cero, color `--pos` o `--neg` por signo del valor, línea del cero con `markLine`).
- `EChart.tsx` solo registra líneas y mapas de calor: la pestaña hace `use([BarChart, MarkLineComponent])` en su propio archivo (registro global de echarts/core; no se tocó `EChart.tsx`). Comprobado con ECharts real renderizando la opción a SVG.
- Selección: `Desde`/`Hasta` (`<select>` rotulados `id · fmtDate(as_of)`); `?from=&to=` de la URL inicial ganan si son snapshots conocidos; lo elegido a mano se conserva, y mientras no se elija nada los valores por omisión siguen al snapshot activo. Llama `pnlExplain(from, to)` al cambiar cualquiera (sin botón). 400 `from`/`to` bajo su selector; otros errores en `.radv-note--error role="alert"`. Con < 2 snapshots: nota "Se necesitan dos snapshots" y no llama.
- Hueco resuelto: si todos los snapshots tienen el mismo `as_of` (sin anterior ni posterior) se compara el primero distinto (por id) contra el activo. Los `warnings` de cada fila NO se muestran (la tarea no los pide). Importes con `fmtMoney(v,'MXN')` en todas las celdas (tabla ancha: desplaza dentro de `.radv-scroll`); `explain_error` va en una fila-nota `role="status"` bajo la operación. Productos con `productTitle` de `pricers/registry`.
- Clases propias con prefijo `pnlx-`; además `.radv-card.is-loading` (opacidad) definida en `PnlExplainTab.css`. T9: verificar a 1280 px la cascada (etiquetas del eje x con `overflow: 'break'`, altura 340) y el scroll horizontal de la tabla.

### U4
- Commit `0928754` en `corte6`: `desk/ui/src/screens/risk/LimitsTab.tsx` (reemplaza el stub), `LimitsTab.css`, `LimitsTab.test.tsx` (22 pruebas). `npm test` 23 archivos / 340 pruebas verdes; `npm run build` exit 0.
- `export function LimitsTab()` sin props; devuelve un fragmento con tres `<section class="radv-card">` con nombre accesible: "Uso de límites" (tabla `limitUsage(snapshotId)`, botón `Revisar límites` -> `checkLimits`), "Nuevo límite" (formulario) y "Bitácora de excesos" (`listBreaches()`). Solo importa de `client` (`ApiError`, `listTrades`) y `riskClient` (`limitUsage`, `checkLimits`, `createLimit`, `addLimitEvent`, `listBreaches`); no usa `listLimits`.
- Formulario (labels exactos): `Alcance`, `Métrica`, `Clave` (oculta en portafolio), `Monto (MXN)`, `Motivo`, botón `Agregar límite`. Cuerpo: `{scope, metric, amount, key?}` (+ `reason` recortado solo si no está vacío; el portafolio no manda `key`). Errores con `field` en scope/metric/key/amount/reason salen bajo su campo (`aria-invalid` + `aria-describedby` = `<id>-error`); cualquier otro error, en `role="alert"`. Monto vacío/no numérico se rechaza en el cliente (`Ingresa un número válido`, field `amount`) sin llamar al backend.
- Decisión (hueco): la clave de factor se ata a la métrica: `dv01` -> TIIE-F, SOFR; `fx_delta` -> USDMXN (el plan solo decía "curva: TIIE-F/SOFR; USDMXN"). `METRICS_BY_SCOPE` y `FACTOR_KEYS` están duplicados en el componente (labels.ts es de U1). Contrapartes: nombres únicos y ordenados de `listTrades()`; si falla o no hay, el select dice "Sin opciones" y hay un aviso.
- Acciones por fila: `Cambiar monto` abre campo en línea (`aria-label="Nuevo monto (MXN)"`, `Guardar`/`Cancelar`) -> `addLimitEvent(id, {type:'change', amount})`; `Dar de baja` -> confirmación en línea (`Confirmar baja`/`Cancelar`, sin `window.confirm`) -> `{type:'retire'}`; tras éxito recarga el uso; errores del backend salen en la misma fila. Sin `reason` en cambio/baja (no se pidió).
- Barra: `.radv-bar[data-status]` con `--pct` = pct acotado a [0,100]; el texto lleva el % real con 1 decimal (`152.0 %`). El portafolio muestra `—` en Clave. `errors` de la respuesta de uso se avisan como `role="status"` (operaciones excluidas). Al cambiar de snapshot recalcula el uso (solo la última respuesta escribe) y borra el aviso de `Revisar límites`; la bitácora no depende del snapshot y se recarga tras cada revisión.
- No comprobado contra el backend real (T6 aún no existe en el worktree): las pruebas usan `riskClient` simulado; T9 debe verificar formas reales de `usage`/`check`/`breaches` y el 409 `key` del alta.

### U5
- Commit `8bc4c7d` en `corte6`: `desk/ui/src/screens/risk/CreditTab.tsx` (reemplaza el stub; sigue siendo `export function CreditTab()` sin props), `CreditTab.css`, `CreditTab.test.tsx` (17 pruebas). Interfaz: 24 archivos / 357 pruebas verdes, `tsc -b` y `npm run build` exit 0.
- Exporta además `profileOption(cp: CreditCounterparty, pfeQuantile?: number): EChartsCoreOption` (función pura: `xAxis` categoría con las fechas, dos series `line` "EE" y "PFE 95 %" —"PFE" sin cuantil—, en MXN). Importa de `api/client` solo `ApiError`, de `api/riskClient` `creditExposure`, `listCreditParams`, `setCreditParams`, y `EChart`/`cssColor` de `components/EChart` (solo `LineChart`, ya registrado).
- Estructura para pruebas/capturas: banda `role="note"` (el `notice`), regiones "Contrapartes", "Perfil de <contraparte>" (gráfica `ariaLabel="Perfil de exposición"`), "Conjuntos de compensación", "Parámetros de crédito". Elegir contraparte = botón con su nombre (`aria-pressed`); la marca "Supuesto" (con `assumed_note` como `title`) va junto al nombre, fuera del botón. Campos `Prob. de incumplimiento anual (%)` y `Recuperación (%)` (ids `credittab-hazard`/`credittab-recovery`, errores `…-error`), botón `Guardar parámetros`; % se convierte a decimal con `toPrecision(12)`.
- Comportamiento: simula al montar y al cambiar de snapshot ("Simulando exposición…" `role="status"`; al cambiar de snapshot se descarta lo anterior, tras guardar parámetros se conserva atenuado). Tras guardar, reemplaza el elemento en la lista de parámetros con la respuesta del POST y vuelve a pedir `creditExposure` (no vuelve a pedir `listCreditParams`). Un 400 con `field` `hazard_rate`/`recovery` va bajo su campo; cualquier otro error del POST va en `.radv-note--error role="alert"`; no numérico no llama a la API.
- Decisiones propias: las `excluded` que se muestran son las de la contraparte elegida (la lista global es su unión, no se repite); `warnings` de la respuesta, si hay, salen en `.radv-note--warn role="status"`; el pie usa `n_paths` de la respuesta ("500 trayectorias Hull-White, semilla fija; solo swaps de tasa; sin colateral ni compensación entre monedas."); contraparte sin `profile` muestra nota en vez de gráfica; el formulario aplica a la contraparte elegida y parte de sus valores vigentes.
- No comprobado: aspecto real a 1280 px y contra el backend real (`/api/credit/*` lo hace T7/T3; lo cubre T9). La gráfica solo se probó por su opción (jsdom no tiene canvas).

### U6
- Commit `c6f4b29` en `corte6`: `desk/ui/src/screens/risk/ScenarioLibraryTab.tsx` (reemplaza el stub), `ScenarioLibraryTab.css`, `ScenarioLibraryTab.test.tsx` (18 pruebas). Interfaz completa: 25 archivos / 375 pruebas verdes, `npm run build` exit 0.
- Exporta `ScenarioLibraryTab(): JSX.Element` (sin props). Importa de `api/client` (`ApiError`, `listTrades`) y `api/riskClient` (`listScenarioSets`, `createScenarioSet`, `retireScenarioSet`, `runScenarioSet`); las pruebas mockean ambos módulos.
- Regiones para pruebas/capturas: "Conjuntos de escenarios" (un `<li>` por conjunto con `<h3>` = nombre), "Corrida: <nombre>" (solo tras `Correr`) y "Nuevo conjunto". Botones: `aria-label` "Correr <nombre>" / "Dar de baja <nombre>" (texto visible "Correr"/"Dar de baja"), luego "Confirmar baja"/"Cancelar"; formulario: "Agregar escenario", "Quitar escenario n", "Crear conjunto". Etiquetas: "Nombre", "Descripción", "Nombre/Tipo/Curva del escenario n", "Choque (pb) del escenario n" o "Variación (%) del escenario n" (USDMXN spot no lleva curva).
- Texto de choques: "TIIE-F +100 pb", "TIIE-F steepener +25 pb", "USDMXN +25 %", menos real "−"; combinados unidos con " · ". Si el nombre del escenario ya es el choque no se repite.
- Decisiones: `Correr` llama `runScenarioSet(snapshotId, set.name)` + `listTrades()` (para rotular filas `#id producto · contraparte`); al cambiar de snapshot el resultado se descarta (no se recalcula solo); la tabla usa `fmtNumber(v, 0)`, `n/d` con `title` = error, `<tfoot>` para el total. El formulario ofrece solo `parallel`/`steepener`/`fx_spot` (no `combined`), siempre deja >= 1 fila (el botón Quitar se deshabilita con una), manda `name`/`description` con `trim` y omite la descripción vacía. Un valor no numérico se avisa en el cliente como `Escenario n: ingresa un número válido` bajo los escenarios (field `scenarios`, `id="scn-rows-error"`); `name` -> `id="scn-name-error"`; cualquier otro error del alta es `.radv-note--error role="alert"`. Errores de correr/baja salen en el propio conjunto.
- No comprobado: aspecto real a 1280 px ni contra el backend real (lo cubre T9; `GET /api/scenario-sets` depende de T8). El detalle de "Por omisión" lista los 8 escenarios sin colapsar.

### T3
- Commit `3e80463` en `corte6` (16 archivos: `db.py`, `app.py`, `routes/risk.py`, `routes/risk_adv.py`, los seis módulos `risk/*` y siete archivos de prueba). Backend completo: 2370 pasan (2335 base + 35 nuevas). El plan dice "15" rutas/archivos: son 16 rutas (explain 1, factor-history 3, limits 6, credit 3, scenario-sets 3) y 16 archivos; se hicieron todas.
- Esquema: siete tablas + 14 disparadores `<tabla>_no_update`/`_no_delete` (mensaje `'<tabla> es solo de inserción'`) al final de `db.SCHEMA` (comentarios SQL `-- --- corte 6 ---`). `create_app` registra `risk_adv.bp` y, con `seed=True`, llama `factor_history.seed_synthetic(conn)` (stub: devuelve 0) con su propia conexión y `commit`.
- Constantes reales ya en los módulos tal como en "Constantes y vocabulario"; `explain.STEPS` es una lista de tuplas (curvas desde `market.CURVES`); `scenario_sets.BUILTIN_SETS` es una lista de dicts `{name, approximation, description, scenarios}` (los 3 históricos con un escenario `combined` cuyos `shocks` van en orden fx_spot, TIIE-F, SOFR; "Por omisión" lleva copia profunda de `DEFAULT_SCENARIOS`): `list_sets` debe copiarla antes de entregarla. Stubs (todas `raise NotImplementedError` -> 501): `explain.explain_pnl(conn, from_id, to_id)`, `factor_history.import_csv(conn, text)/derive(conn, source, config)/summary(conn)/window(conn, history_source, as_of, n)`, `hist_var.compute_hist_var(conn, snapshot_id, body)`, `limits.list_limits(conn)/create_limit(conn, body)/add_event(conn, limit_id: int, body)/usage(conn, snapshot_id)/check(conn, snapshot_id)/list_breaches(conn)`, `credit.list_params(conn)/set_params(conn, body)/exposure(conn, snapshot_id)`, `scenario_sets.list_sets(conn)/create_set(conn, body)/retire_set(conn, set_id: int)/resolve(conn, name)`.
- `risk_adv.py` (final): las rutas envuelven las listas (`{"limits"|"breaches"|"params"|"sets": ...}`), hacen `commit` tras escribir y devuelven 201 en alta/evento/params/creación; `limits.check` y `scenario_sets.retire_set` responden 200. Ids no enteros o >= 2^63 -> 404 `id` en `limits/<id>/events` y `scenario-sets/<id>/retire`; la existencia (404 `id`, 409) la decide el módulo. `limits_event` valida el id antes de leer el cuerpo. Ya validan en la ruta: `from`/`to`/`snapshot` presentes (400), `csv` texto (400 `csv`), `source` en (`fixings`, `live`) (400 `source`; `derive` puede revalidar), `body_object()`. `derive` recibe `current_app.config`.
- `routes/risk.py`: `method` vía `choice` (`null` cuenta como ausente, como en todo `validation`); `historical` -> `hist_var.compute_hist_var(conn, snapshot_id, body)` con el cuerpo completo. `set`: 400 `set` si va junto a `scenarios` o no es texto no vacío; luego `scenario_sets.resolve(conn, set)` -> `run_scenarios(conn, snapshot, {"scenarios": specs})` + `"set"`. Hasta que T8 extienda `scenarios._validate` con `combined`, los conjuntos históricos no correrán.
- Pruebas: `test_risk_adv_schema.py` (esquema, recreación, `method`, `set`, ids, y un test extra de las constantes reales `STEPS`/`BUILTIN_SETS`); cada `test_<área>.py` trae solo `test_contract_stub(client)` (501 JSON con `error`): T4-T8 lo reemplazan. La verificación de ids del plan dice `GET /api/limits/abc/…`; la única ruta con id es `POST /api/limits/<id>/events` y esa es la que se prueba.

### T2
- Commit `839a88d` en `corte6` (siete rutas). C++: `qf::xva::ExposurePoint{double t, epe, ene, pfe}` y `std::vector<ExposurePoint> qf::xva::simulateExposure(const qf::models::IRateModel&, const NettingSet&, const SimParams&, double pfeQuantile = 0.95)` en `include/qf/xva/exposure_profile.hpp`; `epe`/`ene` salen bit a bit iguales a `CVACalculator::compute(...).profile`. Cuantil: índice `ceil(round(q·n, 9)) − 1` sobre `max(V,0)` ordenado (el redondeo a 9 decimales evita que `0.07·100 = 7.000000000000001` mueva el índice; mismo criterio que `hist_var`).
- Python: `qfxva.simulate_exposure(hw, netting_set, params, pfe_quantile=0.95) -> list[qfxva.ExposurePoint]` (`t`, `epe`, `ene`, `pfe` solo lectura); `ValueError` ante q ∉ (0,1), fechas vacías/no positivas/desordenadas o `n_paths = 0`. `pfe` es el cuantil crudo: **`max(pfe, epe)` lo aplica `credit.py`**, no el binding.
- **Hueco de diseño resuelto (T7 debe saberlo):** `qfpy` y `qfxva` registraban ambos el enum C++ `SwapType`, así que `import qfxva` en un proceso con `qfpy` ya importado lanzaba `ImportError: type "SwapType" is already registered` (y `web/tests/test_xva.py` se saltaba en silencio por eso). Arreglo en `xva_bindings.cpp`: si `qfpy` ya registró el tipo, `qfxva.SwapType` es el mismo objeto que `qfpy.SwapType`. **Orden obligatorio: importar `qfpy` ANTES que `qfxva`** (con `qfxva` primero, `import qfpy` sigue fallando y `qfpy.cpp` está fuera de alcance). `desk/api/qf.py` ya importa `qfpy`; `credit.py` debe importar `qfxva` después (dentro de la función o tras `qf`).
- `qfxva.so` reconstruido en `build/src/` (solo `--target qf qf_tests qfxva`; `qfpy.so` intacto, no se construyó `all`). Con `env -u CXXFLAGS` delante de `cmake --build` (ver T1).
- Cifras: `ctest -R "ExposureProfile|CVACalculator"` 18/18; `ctest` completo `100% tests passed, 0 tests failed out of 410` (402 + 8 nuevas); `tests/test_xva_exposure_py.py` 3 pruebas `OK` (no omitidas); `pytests` (59 pruebas) `OK`, las 3 corren dentro del descubrimiento completo.

### T5
- Commit `a4cf6c8` en `corte6`: `risk/factor_history.py`, `risk/hist_var.py`, `tests/test_hist_var.py` (reemplaza el stub; 28 pruebas), `tests/test_factor_history.py` (nuevo; 28). Backend completo: 2554 pasan.
- `factor_history`: `seed_synthetic(conn) -> int` (real: 500 días hábiles lun-vie antes del as_of de MX-DEMO, 1500 filas, fecha final 2026-11-09), `import_csv(conn, text) -> {"inserted","unchanged"}`, `derive(conn, source, config) -> {"source","inserted","unchanged","skipped_gaps"}`, `summary(conn)`, `window(conn, history_source, as_of_iso, n) -> (fechas, {factor: [valores]}, by_source)` (si hay menos de `n` fechas devuelve las que haya; el 409 lo da `hist_var`). Auxiliar `_store(conn, source, rows, field)` (todo o nada, 409 sin insertar). `hist_var`: `compute_hist_var(conn, snapshot_id, body)` y constante extra `OBSERVED_LABEL`.
- Huecos resueltos (conservador): (1) `derive`: un cambio diario fuera de `MAX_ABS` (p. ej. SOFR 1 %→50 %) detiene todo con 409 `source` en vez de descartarse o guardarse; (2) `derive live` toma USDMXN de FRED solo en la ventana de MKT-LIVE (últimas `MAX_CHANGES+1` = 251 observaciones, igual que el SOFR 5Y) y aplica también la regla `MAX_GAP_DAYS`; (3) errores de `live`: ApiError de MarketDataFeed que NO empiecen por "Historia insuficiente" y fallos de FRED (OSError/ValueError) -> 502 `source`; el 409 de historia corta se propaga; (4) `derive fixings` puede dar 409 `source` legítimo si se cargan fijaciones intermedias después de derivar (el cambio de un día cambia de valor): así lo fija el contrato.
- `hist_var`: usa `market._fetch` + `market._build_context`; `ES = max(media(k mayores), VaR)` (el máximo solo evita que el redondeo ponga ES < VaR); `worst_day.pnl_mxn` sin escalar; `by_source` solo lista fuentes con aportes. `window_days`/`history_source` en `null` cuentan como ausentes. Con MX-DEMO (sintético): VaR 1 día 99 % ≈ 3.19 M (250 d) frente a 3.36 M paramétrico; R3 (5 000 días CSV) da 3.3629 M vs 3.3613 M (0.04 %).
- No comprobado: ruta real contra MarketDataFeed/FRED en vivo (solo fixtures `make_mdf_db`/`make_fred_csv`); la UI no carga CSV de historia (solo la API).

### T4
- Commit `a231301` en `corte6`: `desk/api/risk/explain.py` y `desk/api/tests/test_pnl_explain.py` (9 pruebas; reemplaza el stub). Backend completo: 2554 pasan (con T2/T5/T6 ya integrados en el worktree al momento de correr).
- `explain.explain_pnl(conn, from_id, to_id) -> dict` (`{"from","to","steps":[{key,label}],"totals":{"pnl","components"},"rows":[{id,product,counterparty,pnl,components,error,explain_error,warnings}]}`); `STEPS` sin cambios. Privadas: `_hybrid_contexts(conn, from_id, to_id, to_as_of) -> List[MarketContext]` (H0..H4 en orden de `STEPS`: base, +curvas, +fx, +vol/hw; reutiliza el mismo objeto cuando un paso no cambia datos, así la diferencia es 0.0 exacto), `_components(trade, row, contexts, fixings, from_as_of, mkt_to)`, `_replace_curve`. Usa `market._fetch` y `market._build_context` (privadas, previsto en el Contexto); los contextos híbridos llevan `snapshot_id = "<from>→<to>"`.
- Decisiones: `residual = pnl − Σ(otros siete)` por fila (los totales suman filas); un componente no finito, o cualquier excepción de la cascada de una operación, manda todo el P&L al residuo con `explain_error` y no tumba el resto; los `warnings` de cada fila son los de `compute_pnl`. Una operación con `trade_date > from.as_of` entra entera a `new_trades`.
- JSON: Flask ordena las claves alfabéticamente, así que `components` NO llega en el orden de `steps`; la interfaz debe indexar por `steps[].key` (U3 ya lo hace: `cascadeOption` toma los `steps` en orden). Con mercado idéntico rodado, `curve:*`, `fx`, `vol`, `events` y `new_trades` salen 0.0 exactos; con mercado movido el residuo es ~0 (< 1e-3 MXN en las 7 operaciones de la semilla).
- Observación para T9/Metodología: en la cascada, los forwards/opciones FX también reaccionan a `curve:TIIE-F` y `curve:SOFR` (el forward usa ambas curvas), no solo `fx`.

### T8
- Commit `c88c549` en `corte6`: `desk/api/risk/scenario_sets.py`, `desk/api/risk/scenarios.py` (solo bloque `# --- corte 6: escenarios combinados ---` al final; `import` del archivo intacto), `desk/api/tests/test_scenario_sets.py` (72 pruebas). Backend completo: 2554 pasan; los tres archivos de la verificación: 145 pasan.
- `scenarios.py`: `_validate_single`/`_shock_single` (originales), nuevos `_validate(body)`, `_shock(mkt, spec)`, `shock = _shock`. `combined` normalizado: `{"name", "type": "combined", "shocks": [<choque sin name>]}`; 1 a 8 choques simples, sin anidar. Errores: `Escenario i: choque j: <mensaje>`, `Escenario i: 'shocks' debe ser una lista de 1 a 8 choques`, `Escenario i: choque j: un escenario combinado no se anida`; los de escenarios simples quedan idénticos (mismo texto, índice correcto). Los choques se encadenan sobre el mismo contexto (dos `fx_spot` de +10 % componen +21 %).
- `scenario_sets.py`: `list_sets(conn)`, `create_set(conn, body)`, `retire_set(conn, set_id)`, `resolve(conn, name) -> List[spec]` (copias profundas de `BUILTIN_SETS`). Conjunto = `{id, name, builtin, approximation, status, description, scenarios, created_at}`. Alta: valida `name` (`text`, ≤ 80, 400 `name`), `description` (texto o null; vacío -> null; 400 `description`), `scenarios` (400 `scenarios`) y al final 409 `name` si repite uno de fábrica o uno activo (comparación exacta tras `strip`; el nombre de uno de baja se reutiliza y `resolve` toma el activo). `retire_set`: 404 `id` / 409 `id`. `resolve`: 404 `set`. Las escrituras no hacen commit (lo hace la ruta).
- Decisiones/huecos (conservadores): no se limita el largo de `description` ni se rechazan nombres de escenario repetidos dentro de un conjunto (no se pidió); `description` no texto -> 400 `description` (el plan no fijaba el campo). El mensaje de `type` inválido de escenarios simples no menciona `combined` (se conserva el texto original). Interacción: sobre el portafolio sembrado, TIIE-F +50 pb con USDMXN +10 % difiere de la suma en ~58.7 mil MXN (solo la `fx_option`, id 6); los `irs` TIIE-F (ids 1 y 2) coinciden exactos.
- Primera corrida completa del backend dio 2 fallos ajenos (T5 a medias: `test_factor_history.py` y el stub viejo de `test_hist_var.py`); un minuto después la suite completa pasó. No se levantó backend, Chrome ni ningún proceso.

### T6
- Commit `2d03519` en `corte6`: `desk/api/risk/limits.py` y `desk/api/tests/test_limits.py` (48 pruebas; backend completo 2554 pasan, 0 fallos). Constantes y firmas tal como en el contrato: `list_limits(conn)`, `create_limit(conn, body)`, `add_event(conn, limit_id, body)`, `usage(conn, snapshot_id)`, `check(conn, snapshot_id)`, `list_breaches(conn)`; escrituras sin commit.
- `amount` en la forma HTTP del límite y en `usage[].amount` = monto **vigente** (último evento `create`/`change`); la fila de `limits` conserva el de alta. `events[]` = `{id,type,amount,reason,created_at}`; el evento `retire` lleva `amount: null`.
- Orden de validación de `add_event`: 404 `id`, 400 `type`, 400 `amount` (solo `change`, `gt=0, le=MAX_AMOUNT`), 400 `reason` (texto opcional), 409 `id` si ya está de `baja`. `create_limit`: scope, metric (+ pertenencia a `METRICS_BY_SCOPE`), key, amount, reason, duplicado activo 409 `key`. `key` de portafolio: ausente/null -> `"portfolio"`, cualquier otro texto (incluso "") -> 400 `key`; `fx_delta` solo admite `USDMXN` (`market.PAIR`), `dv01` solo `market.CURVES`.
- `pct` (en `usage` y en `limit_breaches`) se informa **ya redondeado a 9 decimales** y el estado sale de ese mismo valor (así `usage/0.8` da exactamente 80.0 = alerta y el estado siempre es coherente con el `pct` mostrado).
- `usage` carga el contexto del snapshot (404 `snapshot`) y solo calcula lo que algún límite activo usa: valuación (pv_exposure), `dv01.compute_dv01` (dv01), una sola `var.compute_var(conn, snap, {"horizon_days":1,"confidence":0.99})` (fx_delta y var). `errors` = unión sin repetir `id` en el orden valuación, dv01, var (de la valuación se toman las filas con `error`, de todas las contrapartes). Sin límites activos devuelve `usage: []`.
- `check` inserta en `limit_breaches` solo si no existe `(limit_id, as_of)` (un snapshot distinto con la misma fecha no inserta otro; el `snapshot` del exceso es el del primer `check`). Devuelve el cuerpo de `usage` más `new_breaches` (formas completas con scope/key/metric del límite). `list_breaches` va por `id` descendente.
- No comprobado: capturas ni la pestaña de U4 contra este backend (lo cubre T9). Un monto mínimo absurdo (p. ej. 1e-300) haría `pct` infinito y `ensure_finite` respondería 400 al pedir el uso; no se acotó el monto mínimo porque el contrato solo pide `gt=0`.

### T7
- Commit `ea07807` en `corte6` (solo `desk/api/risk/credit.py` y `desk/api/tests/test_credit.py`, 31 pruebas, ~10 s). Backend completo: 2584 pasan. Sin cambios de rutas (`risk_adv.py` ya delegaba).
- Firmas: `credit.list_params(conn) -> List[dict]` (por nombre; `{counterparty, hazard_rate, recovery, as_of, assumed, history}`), `credit.set_params(conn, body) -> dict` (mismo elemento; orden de validación: `counterparty` texto, `hazard_rate`, `recovery`, luego 404 `counterparty`; `as_of` = `now_iso()[:10]`; sin commit), `credit.exposure(conn, snapshot_id) -> dict` (contrato D5). Privadas: `_add_months(start, k)`, `_grid(as_of, last_maturity)`, `_history(conn)`, `_params_row(name, rows)`.
- `qfxva` se importa dentro de `exposure()` tras `from desk.api.qf import qfpy` (orden obligatorio de T2). Rejilla mensual calculada siempre desde `as_of` (sin acumular el recorte de fin de mes).
- Decisión (hueco): con varios conjuntos por contraparte (TIIE-F y SOFR) EE(0)=PFE(0)=Σ max(PV_conjunto, 0), no max(PV total, 0); coincide con max(pv_mxn,0) cuando hay un solo conjunto (caso sembrado, R4) y es coherente con "sin compensación entre monedas" de la rejilla. Perfil = suma de conjuntos (`ee=epe·fx`, `pfe=max(pfe,epe)·fx`), orden de conjuntos = orden de `market.CURVES` (TIIE-F, SOFR).
- Decisión (hueco): un `irs` vivo que no se puede valuar o sin `fixed_rate` va a `excluded` con `reason = "No se pudo valuar: <error>"` (no detiene al resto); `warnings` de nivel superior = avisos de `value_trade` de los `irs` cubiertos, fusionados con `settlement.merge_warnings`. Contrapartes sin `irs` cubiertos igual aparecen (con `netting_sets: []`, `profile: []`) y con sus supuestos; las que no tienen operaciones vivas no aparecen.
- Cada llamada a `exposure` simula dos veces por conjunto (`simulate_exposure` y `CVACalculator.compute`, misma semilla); en el portafolio sembrado tarda ~0.6 s en Debug. Sin tope de rejilla (un swap muy largo = muchas fechas).

### T9
- Commit `68cdc65` en `corte6` (5 rutas de interfaz): `CreditTab.tsx` renderizaba `warnings` como texto, pero el backend los entrega como objetos `Warning` (`{code, index, dates, message}`): React error 31 y pestaña en blanco con fijaciones SOFR faltantes. `riskTypes.ts`: `ExplainRow.warnings` y `CreditExposureResponse.warnings` ahora son `Warning[]` (de `api/types`); la pestaña muestra `w.message`; prueba de regresión nueva. Además `MethodologyScreen.tsx`: `Alcance` de "Límites de este corte" pasa de "Sin XVA…" a "CVA informativo solo de swaps de tasa; sin DVA, FVA ni colateral. Un solo usuario.".
- Cuatro suites (compilación completa limpia): ctest 410/410 (línea base 402 + 8 de T2), pytests 59 `OK`, backend 2584 passed, vitest 25 archivos / 377 pruebas, `npm run build` exit 0.
- Recorrido de punta a punta contra el backend real en :5086 (scripts `/tmp/fableorchestrate/qf-corte6/it_a..e.py`, respuestas en `it/`): identidad P&L explicado == `/api/pnl` a 0.0 por fila y total, residuo 0, mercado idéntico -> curvas/fx/vol 0.0 exactos; VaR histórico 10.1 M vs paramétrico 10.6 M (MX-DEMO), ES >= VaR, `history.source` = `synthetic`, `window_days: 9000` -> 409; límites ok/alerta/exceso, `check` doble -> 3 excesos y 0 nuevos; EE(0)=PFE(0)=max(PV,0), PFE >= EE, excluidos 4/5/6/7; hazard 1 % -> 5 % sube el CVA de Alfa 21.5 k -> 121.6 k, hazard 0 -> CVA 0.0 exacto; conjunto propio por nombre == en línea, "Marzo 2020" corre, baja -> 404 `set`; disparadores de las siete tablas abortan UPDATE/DELETE. Capturas 1280 px en `shots/` (`<pestaña>.png` a 800 de alto, `<pestaña>_full.png` a 2000, `metodologia*.png`, `i1..i5` de interacciones) sin errores de consola ni desborde de página.
- Para capturar: `chrome --screenshot` con `--remote-debugging-port` no termina solo (timeout 90 s) y la pantalla de Riesgo desplaza dentro del shell (la captura "full page" no ve el resto); se usó CDP con el WebSocket global de Node 22 (`cdp_shots.mjs`, `cdp_interact.mjs`) y un viewport alto.
- Observaciones sin corregir (cosméticas): en "Por omisión" los nombres usan "-" y los choques "−", así que no se deduplican (aparece "TIIE-F -50 pb  TIIE-F −50 pb"); en VaR histórico el encabezado "Exposición" queda a la izquierda de cifras alineadas a la derecha; la tabla de P&L explicado mide 1167 px dentro de un contenedor de 996 y desplaza horizontalmente (diseñado, `overflow-x: auto`); el `<select>` de métrica de "Nuevo límite" recorta "Exposición (PV positivo neto)".

### Correcciones

Pasada de correcciones tras la auditoría independiente (`audit.md`), en `corte6` sobre `68cdc65`. Seis commits, todos con `GRAPHIFY_SKIP_HOOK=1`, autor Claudio, sin atribución, sin push. Sin cambios de C++ ni de contrato HTTP (solo cambió el texto de `reason` de `excluded`).

- **Defecto 1 (alto) — perfil EE/PFE y CVA incoherentes con el PV del desk** · `2540a0a` (`risk/credit.py`, `tests/test_credit.py`). Causa medida: no era el signo ni la curva reconstruida (rebuilt vs original < 0.01 pb en t ≈ 0), sino dos efectos del swap "fresco" de `qfxva`: (a) base de días: el desk valúa ACT/360 y el modelo ACT/365 (con la tasa × 365/360 el modelo reproduce el PV del desk a 1e-10 en t = 0); (b) a t > 0, `NettingSet::netValue` revalúa un swap residual con `int(plazo · frecuencia)` cupones y pierde el último periodo incompleto (para Alfa, un cupón de 28 días ≈ 2.3 M MXN): de ahí el salto de +2.3 M en t ≈ 1e-4. Corrección sin tocar C++ ni el contrato: cada swap entra al modelo con pagos diarios (`_MODEL_FREQUENCY = 365`, el error por periodo incompleto baja a un cupón diario) y con una tasa fija efectiva calibrada a que el valor del modelo en t = 0 sea exactamente el PV del desk (`_effective_fixed_rate`: el valor es lineal en la tasa, dos valuaciones con `qfpy.InterestRateSwap`; no hay fórmula de pricing nueva). Resultado en MX-DEMO: EE(1 mes) Alfa 0.58 M (antes 2.29 M), Gamma 0.93 M (antes 9.9 M), Beta 2.10 M (EE(0) = 1.60 M; antes caía a 1.0 M); CVA con 1 %: Alfa 12.0 k (21.5 k), Beta 93.8 k, Gamma 71.2 k (192.8 k). Costo: ~2 s por `GET /api/credit/exposure` en Debug (antes 0.6 s); `test_credit.py` pasó de ~10 s a ~42 s.
  - Tests nuevos: calibración exacta (1e-9) del swap del modelo al PV del desk; error si no hay cupones; con volatilidad despreciable el modelo arranca en el PV del desk (|Δ| < 0.05 % del nocional, mismo signo) y un mes después difiere solo por el acarreo (< 0.2 % del nocional; el escalón anterior era de 0.5 a 3 %).
- **Defecto 2 (medio) — EE(0) por contraparte con más de una curva** · mismo commit. EE(0) = PFE(0) = max(Σ PV de la contraparte, 0), como pide R4 (antes Σ por curva de max(PV, 0)). Decisión de diseño no resuelta por el documento, la más conservadora: los puntos mensuales siguen sumando los conjuntos por curva (cota superior, sin compensación entre monedas: `qfxva` no simula dos monedas con shocks conjuntos), y el punto de hoy compensa porque es un valor conocido. Consecuencia declarada: en una contraparte con dos monedas el primer punto mensual puede quedar por encima de EE(0) (ocurre también con un solo conjunto de PV negativo: EE(0) = 0 y EE(1 mes) > 0 por opcionalidad). Test reemplazado por uno parametrizado (Σ PV > 0 y < 0).
- **Defecto 3 (bajo) — tabla de P&L explicado a 1280 px** · `8f035f3`. Medía 1167 px en 996: ahora 996 sin desplazamiento (Residuo visible). Importes en pesos enteros con el valor con centavos en `title` (la identidad la garantiza el backend, no la presentación), y encabezados de pasos que pueden partirse. Los tests de celdas pasan a "MXN -400,000"; pie ampliado.
- **Defecto 4 (bajo) — códigos internos en avisos de crédito** · en `2540a0a`. `reason` ahora dice "La exposición simulada solo cubre swaps de tasas (IRS): Forward FX se excluye" (rótulos de la interfaz: Forward FX, Opción FX, Cap / Floor); `product` conserva el código. Test de regresión con regex.
- **Defecto 5 (bajo) — "Por omisión" con nombre y choque duplicados** · `f7b9452`. La interfaz comparaba nombre y choque por texto exacto (guion ASCII vs signo menos, "+" y espacios); ahora los normaliza. Los nombres del backend no se tocaron (son clave de la API y de pruebas).
- **Documentación derivada** · `f3b0a8e` (Metodología: fila nueva "Coherencia con la valuación"; "Alcance del crédito" y "Exposición y CVA" ajustados; pie de Crédito) y `8a9e5cd` (límite conocido en `credit.py`: un swap con inicio futuro queda anclado a su PV pero su perfil es aproximado).
- **Cosméticos de T9, no marcados por la auditoría pero baratos** · `668d25f`: encabezados de columnas numéricas alineados a la derecha en todas las tablas `.radv-table` (VaR, Límites, Crédito), y rejilla de "Nuevo límite" con 215 px mínimos para que el select no recorte "Exposición (PV positivo neto)".

No corregido: "steepener" en español (heredado de cortes anteriores, fuera de este corte); el perfil de crédito sigue sin colateral, DVA/FVA ni compensación entre monedas a futuro (declarado en Metodología); las observaciones "Construido sin que un R lo pidiera" son decisiones aceptadas, no defectos.

Verificación (compilación incremental sin cambios; 6 commits): ctest 410/410; pytests (59) OK; backend 2588 passed; vitest 25 archivos / 379 pruebas; `npm run build` exit 0. Recorrido real con backend en :5086 y Chrome en :9346 (1280 px: sin desborde de página en VaR, P&L, Límites, Crédito, Escenarios; consola sin errores; EE(0) = max(PV, 0) en las tres contrapartes y con Alfa en dos monedas), todo apagado al final (`ss` sin 5086 ni 9346).
