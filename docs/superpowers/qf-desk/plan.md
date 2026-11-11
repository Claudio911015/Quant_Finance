# Plan: QF Desk

Diseño: `/tmp/fableorchestrate/qf-desk/design.md`. Repo: `/home/claudio/Git/Quant_Finance`.

## Contexto

Todo implementador lee esta sección completa y solo su tarea.

### Entorno
- Repo: `/home/claudio/Git/Quant_Finance`. Rama de trabajo: `feat/qf-desk`, creada por T1 desde **`master`** (en este repo no existe `main`). Nunca hacer push.
- **Python del backend:** `/home/claudio/anaconda3/bin/python` (Python **3.8.18**; Flask 2.3.3 y pytest 8.2.0 ya instalados). Sintaxis 3.8: nada de `match`, ni `X | Y` en tipos, ni `list[int]`/`dict[str, x]` evaluados en tiempo de ejecución (usar `typing.List`/`Dict`/`Optional` o `from __future__ import annotations`). No instalar paquetes Python.
- **Node** 22.23, **npm** 10.9.
- **C++:** `cmake --build build -j4 2>&1 | tail -5` compila `qf`, `qf_tests` y `qfpy` (el `.so` sale en `build/src/qfpy.cpython-38-x86_64-linux-gnu.so`). Si `build/` no está configurado: `cmake -S . -B build`. **Ignorar `build_release/`.**
- **Convención C++ de tres archivos:** `include/qf/<módulo>/<nombre>.hpp` + `src/<módulo>/<nombre>.cpp` + `tests/test_<nombre>.cpp`; los nombres de archivo existentes van en snake_case (`capfloor.hpp`, `scenario.cpp`). Añadir el `.cpp` a la lista de `add_library(qf ...)` en `src/CMakeLists.txt` y el test a `add_executable(qf_tests ...)` en `tests/CMakeLists.txt`. Doxygen (`@brief`, `@param`, `@return`) en todo método público. Clases `PascalCase`, métodos `camelCase`.
- **Suites:**
  - C++: `cmake --build build -j4 2>&1 | tail -3 && cd build && ctest --output-on-failure 2>&1 | tail -3` → `100% tests passed`. Hoy hay **347** tests (el `CLAUDE.md` dice 153; está desactualizado). Ninguno existente puede romperse.
  - Bindings Python existentes: `cmake --build build --target pytests 2>&1 | tail -3` → `OK`.
  - Backend: desde la raíz del repo, `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q 2>&1 | tail -3` → `N passed`.
  - Frontend: `cd desk/ui && npm test 2>&1 | tail -5` (vitest run) y `npm run build 2>&1 | tail -5` (`tsc -b && vite build`, sin errores).
- **Cómo carga `qfpy` el backend:** `desk/api/qf.py` inserta `<repo>/build/src` en `sys.path` e importa `qfpy`; el resto del backend hace `from desk.api.qf import qfpy`. Si el `.so` no existe, error claro que pide `cmake --build build --target qfpy`.
- **Arranque del backend:** `/home/claudio/anaconda3/bin/python -m desk.api.app` desde la raíz del repo → Flask en `0.0.0.0:5070`. Base: `desk/data/desk.db` (ignorada por git). `create_app(db_path=None, seed=True)`; los tests usan `create_app(db_path=tmp_path/"t.db")`.

### Reglas de ejecución
- Todas las tareas trabajan en el mismo árbol y la rama `feat/qf-desk`. Las tareas paralelas tocan archivos disjuntos; **las que compilan C++ (T2–T6) van en serie**.
- Commit solo de tus archivos: `git add <rutas exactas>` (nunca `git add -A` ni `git add .`), luego `GRAPHIFY_SKIP_HOOK=1 git commit -m "<por qué>"`. El hook post-commit de graphify reescribe `graphify-out/`; con commits en paralelo se pisan, por eso se salta (única excepción: el último commit de T15). **Nunca añadir nada de `graphify-out/`.** Sin `Co-Authored-By`. Sin push.
- Si `git commit` falla por `.git/index.lock`, esperar unos segundos y reintentar (otra tarea está commiteando); no borrar el lock salvo que lleve más de un minuto sin proceso git vivo.
- Toda la matemática financiera está en C++ y se llama por `qfpy`. El Python solo valida, arma objetos, llama a `qfpy`, resta/suma resultados (P&L = PV choque − PV base), convierte USD→MXN con el spot y serializa. No escribir fórmulas de pricing, descuento, interpolación ni VaR en Python ni TS.
- Sin dependencias fuera de las listadas en el diseño (más las aprobadas en Aclaraciones: `jsdom`, `@fontsource/inter`, `@fontsource/jetbrains-mono`; y las implícitas `typescript`, `vite`, `@vitejs/plugin-react`, `@types/*`). La app funciona sin internet: nada de CDN. Sin flags, opciones ni pantallas no pedidas.

### Estructura de `desk/`
```
desk/
  __init__.py                vacío
  .gitignore                 data/ y ui/node_modules/, ui/dist/
  run.sh  README.md          (T14)
  data/                      desk.db (no versionado)
  api/
    __init__.py
    app.py                   create_app(); sirve ui/dist en "/" y fallback SPA; __main__ → puerto 5070
    qf.py                    carga qfpy
    errors.py                ApiError + handlers JSON
    validation.py            helpers de validación
    db.py                    conexión sqlite3 + esquema
    seed_market.py           seed_market(conn)    (stub T1, lo llena T7)
    seed_trades.py           seed_trades(conn)    (stub T1, lo llena T10)
    market.py                MarketContext y snapshots (T7)
    portfolio.py             trades + valuación (T10)
    pricing/__init__.py      PRODUCTS = {**rates.PRODUCTS, **fx.PRODUCTS}
    pricing/base.py          Product (namedtuple) y helpers comunes
    pricing/rates.py         irs, cap_floor, swaption, bond (T8)
    pricing/fx.py            fx_forward, fx_option, equity_option (T9)
    risk/__init__.py
    risk/dv01.py  risk/scenarios.py   (T11)
    risk/var.py                       (T12)
    routes/__init__.py
    routes/market.py routes/price.py routes/trades.py routes/risk.py   (blueprints; T1 los crea completos y delegan en los módulos de arriba)
    tests/conftest.py        fixtures app, client
    tests/test_*.py
  ui/                        Vite + React 18 + TS (U1)
```

### Interfaces Python internas (fijas)
- `desk/api/errors.py`: `class ApiError(Exception): __init__(self, status: int, error: str, field: Optional[str] = None)`. Handler → `{"error": <texto en español>, "field": <str|null>}` con ese status. Handlers JSON también para 404/405 de Flask y para JSON mal formado (400, `field: null`). Excepciones `ValueError`/`RuntimeError` salidas de `qfpy` durante una valuación de entrada ya validada → 400 `{"error": "No se pudo valuar: <msg>", "field": null}`.
- `desk/api/validation.py`: `body_object()` (JSON objeto o 400), `number(d, name, *, gt=None, ge=None, lt=None, required=True, default=None)`, `integer(d, name, *, ge=None, required=True)`, `choice(d, name, options, default=None)`, `text(d, name, required=True)`. Todos lanzan `ApiError(400, msg, field=name)`. Rechazan `bool`, `NaN`, `inf`.
- `desk/api/pricing/base.py`: `Product = namedtuple("Product", "name validate price pv_mxn describe")` donde
  - `validate(params: dict) -> dict` normaliza o lanza `ApiError(400, ..., field)`;
  - `price(params, mkt: MarketContext) -> dict` devuelve el cuerpo de respuesta de `/api/price` (ver contrato);
  - `pv_mxn(params, mkt) -> float` PV en MXN (USD × `mkt.spot`), usado por portafolio y riesgo;
  - `describe(params, as_of: date) -> {"notional": float, "currency": "MXN"|"USD", "maturity": "YYYY-MM-DD"}`.
  - Cada módulo `rates.py`/`fx.py` exporta `PRODUCTS: Dict[str, Product]`.
- `desk/api/market.py` (T7):
  - `CURVES = {"TIIE-F": {"currency": "MXN", "period_days": 28}, "SOFR": {"currency": "USD", "period_days": 365}}`
  - `class MarketContext`: atributos `snapshot_id`, `as_of: date`, `curves: Dict[str, qfpy.YieldCurve]`, `pillars: Dict[str, List[dict]]` (`{"label","days"}` por cotización, en orden), `spot: float`, `surface: qfpy.VolSurface`, `hw: dict`, `factors: dict`, `env: qfpy.MarketEnvironment` (curvas `"TIIE-F"` y `"SOFR"`, spot `"USDMXN"`, superficie `"USDMXN"`); métodos `env_with_default(curve: str) -> qfpy.MarketEnvironment` (lo mismo + curva `"default"` = esa curva, para `CapFloor`/`Swaption`/`Bond`, que leen `"default"`), `shifted(curve=None, pillar_shifts_bp=None, parallel_bp=None, spot_pct=0.0) -> MarketContext` (copia con la curva desplazada vía `YieldCurve.bumped`/`parallel_bump` de qfpy y/o spot × (1+pct/100)).
  - `load_context(conn, snapshot_id) -> MarketContext` (404 `field: "snapshot"` si no existe).
  - Tiempo de curva: `t = days / 365`. Fecha de pago = `as_of + days` (días naturales, sin calendario de inhábiles; aprobado, se declara como límite en Metodología).
- `desk/api/portfolio.py` (T10): `list_trades(conn) -> List[dict]`, `create_trade(conn, body) -> dict`, `delete_trade(conn, id)`, `valuation(conn, snapshot_id) -> dict`, `load_trades(conn) -> List[dict]` (cada uno con `params` ya decodificado).
- Convención DV01 en todo el desk (igual que `qf::risk::ScenarioEngine`): `DV01 = PV(base) − PV(curva +1 pb)`, positivo si el PV sube cuando bajan las tasas.

### Esquema SQLite (T1)
```sql
CREATE TABLE IF NOT EXISTS snapshots (id TEXT PRIMARY KEY, label TEXT NOT NULL, synthetic INTEGER NOT NULL, as_of TEXT NOT NULL, data TEXT NOT NULL);  -- data = JSON con quotes, fx, vol_surface, hw, factors
CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, product TEXT NOT NULL, counterparty TEXT NOT NULL, params TEXT NOT NULL, created_at TEXT NOT NULL);
```
`create_app(seed=True)`: si `snapshots` está vacía llama `seed_market(conn)`; si además `trades` está vacía en ese mismo primer arranque, `seed_trades(conn)`. (Un portafolio vaciado a mano no se resiembra.)

### Contrato HTTP (backend ↔ frontend)
Todas las tasas en decimales (0.0725 = 7.25 %); el frontend las muestra en % con 4 decimales y envía decimales. Montos en unidades de moneda. Fechas ISO `YYYY-MM-DD`. Errores: `{"error": str, "field": str|null}` con 400/404; `field` es el nombre del parámetro tal como aparece en el cuerpo (sin prefijos), o `"snapshot"`, `"product"`, `"counterparty"`, `"quotes"`, `"spot"`.

**Mercado**
- `GET /api/market/snapshots` → `{"snapshots": [{"id": "MX-DEMO", "label": str, "synthetic": true, "as_of": "2026-11-10"}]}`
- `GET /api/market/snapshots/<id>` → 
```json
{"id":"MX-DEMO","label":"México demo (sintético)","synthetic":true,"as_of":"2026-11-10",
 "quotes":[{"id":"TIIE-F:13x28","curve":"TIIE-F","label":"13x28","type":"ois","days":364,"rate":0.0675}],
 "curves":{"TIIE-F":{"currency":"MXN","period_days":28,
            "points":[{"label":"13x28","days":364,"t":0.99726,"zero":0.0661,"df":0.9362,"forward":0.0652}]},
           "SOFR":{"currency":"USD","period_days":365,"points":[...]}},
 "fx":{"pair":"USDMXN","spot":18.60},
 "vol_surface":{"pair":"USDMXN","expiry_days":[30,91,182,365],"strikes":[17.0,...],"vols":[[0.12,...]]},
 "hw":{"TIIE-F":{"a":0.05,"sigma":0.01},"SOFR":{"a":0.03,"sigma":0.008}},
 "factors":{"names":["TIIE-F","SOFR","USDMXN"],"units":["bp","bp","ret"],"daily_vols":[4.0,5.0,0.0075],"correlations":[[1,0.35,0.30],[0.35,1,-0.10],[0.30,-0.10,1]]}}
```
  `points` = un punto por cotización de esa curva; `zero` continua ACT/365 (`curve.zero_rate(t)`), `df` = `curve.discount_factor(t)`, `forward` = `curve.forward_rate(t_prev, t)` con `t_prev` el punto anterior (0 para el primero). `vols[i][j]` = expiry `i` × strike `j`.
- `PUT /api/market/snapshots/<id>` cuerpo (ambos opcionales, al menos uno): `{"quotes":[{"id":"TIIE-F:13x28","rate":0.0685}], "spot": 18.75}` → misma forma que el GET, recalculada. `id` desconocido → 400 `field:"quotes"`; `rate` fuera de (−0.05, 1) → 400 `field:"quotes"`; `spot` ≤ 0 → 400 `field:"spot"`.

**Pricers:** `POST /api/price/<product>`, cuerpo = parámetros planos + `"snapshot"` (obligatorio). Producto desconocido → 404 `field:"product"`. Respuesta:
```json
{"product":"irs","currency":"MXN","pv":123.45,"pv_mxn":123.45,
 "risk":{"dv01":-4567.8,"par_rate":0.0671},
 "cashflows":[{"date":"2026-12-08","days":28,"amount":-1234.5,"df":0.9947,"pv":-1228.0}],
 "details":{}}
```
`cashflows` es `null` salvo en `irs` y `bond`. `amount` neto desde la óptica del tenedor (positivo = cobro). `sum(cashflows.pv) == pv`.

| producto | parámetros (además de `snapshot`) | `currency` | `risk` |
|---|---|---|---|
| `irs` | `curve` ∈ {`TIIE-F`,`SOFR`}; `side` ∈ {`payer`,`receiver`} (payer = paga fija); `notional` > 0; `periods` entero ≥ 1 (TIIE-F: cupones de 28 días; SOFR: años); `fixed_rate` decimal opcional (ausente o `null` → tasa par) | de la curva | `dv01`, `par_rate` |
| `fx_forward` | `side` ∈ {`buy`,`sell`} (compra/venta de USD); `notional_usd` > 0; `strike` > 0 (MXN por USD); `days` entero ≥ 1 | `MXN` | `delta` (∂PV/∂S), `forward` |
| `fx_option` | `side` ∈ {`buy`,`sell`}; `option_type` ∈ {`call`,`put`} (sobre USD); `notional_usd` > 0; `strike` > 0; `days` entero ≥ 1 | `MXN` | `delta`, `gamma`, `vega` (por 1 punto de vol), `forward`, `vol` |
| `cap_floor` | `curve`; `cap_type` ∈ {`cap`,`floor`}; `notional` > 0; `strike` > 0; `periods` entero ≥ 1 | de la curva | `dv01` |
| `swaption` | `curve`; `swaption_type` ∈ {`payer`,`receiver`}; `notional` > 0; `strike` > 0; `expiry_years` > 0; `swap_tenor_years` > 0 | de la curva | `dv01` |
| `bond` | `curve`; `face` > 0; `coupon_rate` ≥ 0; `periods` entero ≥ 1; `frequency` > 0 (default 2) | de la curva | `dv01`, `duration`, `convexity` |
| `equity_option` | `option_type`; `spot` > 0; `strike` > 0; `volatility` > 0; `rate`; `dividend_yield` ≥ 0; `maturity_years` > 0; `quantity` > 0 (default 1) | `MXN` | `delta`, `gamma`, `vega`, `theta`, `rho` |

**Portafolio**
- `POST /api/trades` `{"product": str, "counterparty": str no vacío, "params": {...parámetros del producto, sin snapshot}}` → 201 `{"id": int, "product", "counterparty", "params", "notional", "currency", "maturity", "created_at"}`. Producto desconocido → 400 `field:"product"`; errores de `params` usan el nombre del parámetro.
- `GET /api/trades` → `{"trades": [ <misma forma> ]}` ordenado por `id`.
- `DELETE /api/trades/<id>` → 204; inexistente → 404 `field:"id"`.
- `GET /api/portfolio/valuation?snapshot=<id>` → `{"snapshot", "as_of", "total_mxn", "rows": [{"id","product","counterparty","notional","currency","maturity","pv","pv_mxn","error"}]}`. `pv` en la moneda de la operación; si falla, `pv`/`pv_mxn` = `null`, `error` = texto, y no suma al total.

**Riesgo** (cuerpo JSON con `"snapshot"` obligatorio; operaciones con error se reportan en `errors` y se excluyen)
- `POST /api/risk/dv01` → `{"snapshot", "total_mxn", "parallel_mxn", "curves": {"TIIE-F": {"parallel_mxn": x, "points": [{"label","days","dv01_mxn"}]}, "SOFR": {...}}, "errors": [{"id","error"}]}`. `points` = key-rate por pilar (una por cotización de la curva); `total_mxn` = suma de todos los puntos; `parallel_mxn` = suma de los paralelos por curva.
- `POST /api/risk/scenarios` `{"snapshot", "scenarios": [{"name": str, "type": "parallel"|"steepener", "curve": "TIIE-F"|"SOFR", "bp": num} | {"name", "type": "fx_spot", "pct": num}]}` (lista no vacía obligatoria) → `{"snapshot", "scenarios": [{"name", "total_mxn", "trades": [{"id","pnl_mxn","error"}]}]}`. Steepener = rampa lineal de −bp (primer pilar) a +bp (último), igual que `ScenarioEngine::steepener`.
- `POST /api/risk/var` `{"snapshot", "horizon_days": num > 0, "confidence": 0 < c < 1, "factor_vols": {"TIIE-F": num ≥ 0, "SOFR": num ≥ 0, "USDMXN": num ≥ 0}}` (`factor_vols` opcional y parcial: cada llave presente sustituye la vol diaria del snapshot para esa petición; llave desconocida o valor inválido → 400 `field:"factor_vols"`) → `{"snapshot", "var_mxn", "horizon_days", "confidence", "factors": [{"factor","unit","exposure_mxn","daily_vol","var_mxn"}], "errors": [...]}`.
  Factores: exactamente tres, `TIIE-F` paralelo (bp), `SOFR` paralelo (bp), `USDMXN` (rendimiento relativo del spot, `ret`); sin factores por plazo. Exposición: tasa = P&L MXN ante +1 pb paralelo en esa curva (= −DV01 paralelo); `USDMXN` = delta FX × spot = P&L MXN por unidad de rendimiento relativo. `var_mxn` total con la matriz 3×3 del snapshot; `var_mxn` por factor = VaR de ese factor solo. `equity_option` aporta cero a DV01, escenarios y VaR.

### Frontend: interfaces fijas
- Rutas (`react-router-dom`): `/mercado`, `/pricers/:product` (`/pricers` redirige a `/pricers/irs`), `/portafolio`, `/riesgo`, `/metodologia`; `/` redirige a `/mercado`.
- `src/api/types.ts`: tipos TS exactos del contrato de arriba (`SnapshotSummary`, `Snapshot`, `Quote`, `CurvePoint`, `ProductId`, `PriceResponse`, `Cashflow`, `Trade`, `ValuationResponse`, `Dv01Response`, `ScenarioSpec`, `ScenariosResponse`, `VarResponse`).
- `src/api/client.ts`: `class ApiError extends Error { status: number; field: string | null }` y funciones `listSnapshots()`, `getSnapshot(id)`, `updateSnapshot(id, body)`, `price(product, body)`, `listTrades()`, `createTrade(body)`, `deleteTrade(id)`, `valuation(snapshot)`, `riskDv01(snapshot)`, `riskScenarios(snapshot, scenarios)`, `riskVar(snapshot, horizonDays, confidence)`. Base `/api` (en dev Vite hace proxy a `http://localhost:5070`).
- `src/lib/format.ts`: `fmtMoney(v: number, ccy: string)` → `"MXN 1,234,567.89"`; `fmtRate(dec: number)` → `"7.2500 %"`; `fmtNumber(v, decimals)`; `fmtDate(iso)` → ISO tal cual. Locale `en-US` para el separador de miles con coma (aprobado).
- `src/state/SnapshotContext.tsx`: `SnapshotProvider` y `useSnapshot(): { snapshotId: string; setSnapshotId(id: string): void; snapshot: Snapshot | null; snapshots: SnapshotSummary[]; reload(): Promise<void>; setSnapshot(s: Snapshot): void }`. Default `"MX-DEMO"`.
- `src/components/Shell.tsx` envuelve las rutas; `src/components/CommandPalette.tsx` (cmdk, Ctrl+K).
- Pricers dirigidos por especificación: `src/screens/pricers/types.ts` define
  ```ts
  export type FieldKind = 'number' | 'int' | 'percent' | 'select' | 'text';
  export interface FieldSpec { name: string; label: string; kind: FieldKind; default: string | number | null; options?: { value: string; label: string }[]; optional?: boolean; help?: string }
  export interface ProductSpec { product: ProductId; title: string; fields: FieldSpec[]; chart: 'cashflows' | 'payoff' | 'none' }
  ```
  `percent` se captura en % y se envía en decimal. Un archivo por producto en `src/screens/pricers/products/<product>.ts` exporta `spec: ProductSpec`; `src/screens/pricers/registry.ts` (U1) importa los siete y exporta `PRODUCT_SPECS: Record<ProductId, ProductSpec>`. `src/screens/pricers/PricerForm.tsx` (U5) renderiza cualquier `ProductSpec`.
- Tokens CSS en `src/styles/tokens.css` (`--bg`, `--bg-elev`, `--border`, `--text`, `--text-dim`, `--accent`, `--pos`, `--neg`, `--warn`, `--space-1..6`, `--font-sans: Inter, ...`, `--font-mono: 'JetBrains Mono', ...`, `--fs-xs..lg`). Cifras siempre con clase `.num` (mono, alineadas a la derecha, `tabular-nums`).
- Tests de UI: archivos `*.test.ts(x)` junto al componente; vitest con entorno `jsdom` (aprobado).

---

### Decisiones fijadas por T1 (commit 2d308a7) — respetarlas
- Firmas ya llamadas por las rutas (no tocar las rutas): `risk.dv01.compute_dv01(conn, snapshot_id)`, `risk.scenarios.run_scenarios(conn, snapshot_id, body)`, `risk.var.compute_var(conn, snapshot_id, body)`; cada una valida lo suyo y responde 404 si el snapshot no existe. Mercado: `market.list_snapshots(conn)`, `market.snapshot_payload(conn, id)`, `market.update_snapshot(conn, id, body)`, `market.load_context(conn, id)`.
- `routes/price.py` valida con `PRODUCTS[p].validate` y llama `price(params_normalizados, mkt)`: `price`, `pv_mxn` y `describe` reciben params ya normalizados. Orden en `/api/price/<product>`: producto desconocido (404), cuerpo, `snapshot`, `validate`, y al final `load_context`.
- Las rutas de escritura hacen `conn.commit()`; `db.get_conn()` da una conexión por petición.
- Handlers globales: `ValueError`/`RuntimeError` → 400 "No se pudo valuar: …"; `NotImplementedError` → 501.
- Los módulos stub existen ya (`market.py`, `portfolio.py`, `pricing/*.py`, `risk/*.py`, `seed_*.py`): se rellenan, no se crean.
- Ejecutar Python sin `-I` (Flask 2.3.3 vive en `~/.local`). Para ver el conteo de pytest usar `| grep -E "passed|failed"`, no `| tail -2` (un warning de pytest_asyncio sale después del resumen).

### Bindings `qfpy` disponibles tras T6 (commit 130b469) — usar estos nombres exactos
- Enums (se usan calificados, p. ej. `qfpy.FxSide.Buy`): `DayCountConvention` (`ACT_360`, `ACT_365`, `ACT_ACT_ISDA`, `THIRTY_360`), `OisQuoteType` (`Deposit`, `Ois`), `FxSide` (`Buy`, `Sell`), `CapFloorType` (`Cap`, `Floor`), `SwaptionType` (`Payer`, `Receiver`). `SwapType` y `OptionType` son los que ya existían.
- Funciones: `bootstrap_ois(quotes, period_days, accrual_dcc=ACT_360, method=Linear) -> YieldCurve` (≥2 cotizaciones, si no `ValueError`); `ois_payment_days(maturity_days, period_days)`; `delta_normal_var(exposures, daily_vols, correlations, confidence, horizon_days)`.
- `OisQuote(days, rate, type)`. `OisSwap(notional, fixed_rate, maturity_days, period_days, swap_type, curve_key, dcc=ACT_360)`: `npv(env)`, `par_rate(env)`, `annuity(env)`, `cash_flows(env)` → `OisCashFlow` (`pay_days`, `pay_time`, `accrual`, `fixed_amount`, `float_amount`, `net_amount`, `discount_factor`, `present_value`).
- `FxForward(notional_foreign, strike, maturity_days, side, pair="USDMXN", domestic_curve="TIIE-F", foreign_curve="SOFR")`: `npv(env)`, `forward_rate(env)`, `delta(env)`.
- `FxOption(notional_foreign, strike, maturity_days, option_type, side, pair=..., domestic_curve=..., foreign_curve=...)`: `npv(env)`, `greeks(env)` → `FxOptionGreeks` (`price`, `delta`, `gamma`, `vega` por 1 punto de vol, `forward`, `vol`).
- `CapFloor(type, notional, strike, maturity, frequency, hw_a, hw_sigma, dcc=ACT_365)` y `Swaption(type, notional, strike, expiry, swap_tenor, frequency, hw_a, hw_sigma, dcc=ACT_365)`: `price(curve)`; todos los instrumentos tienen `pv(env)`.
- `Bond(faceValue, couponRate, periods, frequency=2.0, dcc=ACT_365)` + `cash_flow_schedule()` → lista de (tiempo en años, monto).
- Ejemplo de entorno completo (curvas, spot, superficie): `tests/test_desk_bindings_py.py`.

### `MarketContext` tal como quedó en T7 (commit 895ec72)
- `load_context(conn, snapshot_id)` reconstruye todo en cada llamada: para recorrer muchas operaciones usa un solo contexto y `shifted()`. Snapshot inexistente → `ApiError(404, ..., "snapshot")`.
- Atributos: `snapshot_id`, `as_of` (`datetime.date`; fecha de pago = `as_of + timedelta(days)`), `curves["TIIE-F"|"SOFR"]` (`YieldCurve`, tiempo = días/365), `pillars[curve]` (lista `{"label","days"}` en el mismo orden que `curves[curve].maturities()`), `spot` (float), `surface`, `hw` (`{curva: {"a","sigma"}}`), `factors` (`{"names","units","daily_vols","correlations"}`), `env`.
- `env` trae curvas `"TIIE-F"` y `"SOFR"`, spot y superficie `"USDMXN"`; NO trae `"default"`. Para `CapFloor`, `Swaption` y `Bond` usar `ctx.env_with_default(curve)` (curva desconocida → `ValueError`).
- `ctx.shifted(curve=None, pillar_shifts_bp=None, parallel_bp=None, spot_pct=0.0)` devuelve un contexto nuevo sin mutar. `pillar_shifts_bp`: un valor por pilar de `curve`, en orden (key-rate: 1.0 en un índice; steepener: rampa lineal de −bp a +bp). `parallel_bp` usa `parallel_bump`. `spot_pct` multiplica el spot por `1 + pct/100`. Los bp son de tasa cero continua, no de cotización.
- `MX-DEMO`: 10 cotizaciones por curva (ids `TIIE-F:1D`, `TIIE-F:13x28`, `SOFR:1Y`…), superficie de 4 vencimientos × 8 strikes (17.0 a 20.5).

### Decisiones de Fable tras T8/T9 (ver P11 y P12 en design.md)
- `pricing/rates.py` y `pricing/fx.py` están hechos (commits 529ae00 y 1209727); `PRODUCTS[p]` ofrece `validate`, `price`, `pv_mxn`, `describe`. `irs` devuelve la tasa usada en `details.fixed_rate`.
- T10: `POST /api/trades` con `irs` sin `fixed_rate` (ausente o null) → 400 `field: "fixed_rate"`. Las operaciones de la semilla llevan `fixed_rate` explícito y no par (para que tengan PV y riesgo no triviales).
- T13: añadir en `validate` las cotas `periods` ≤ 1200, días ≤ 18250, años ≤ 50 → 400 con el campo, con tests.
- T15: en `PricerForm`, tras valuar un `irs` con la tasa en blanco, rellenar el campo con `details.fixed_rate` (en %) para que "Agregar al portafolio" la envíe; test de ello.

### Portafolio tal como quedó en T10 (commit 1a86851) — punto de entrada para riesgo
- `portfolio.load_trades(conn)` → lista por id de `{"id","product","counterparty","params","created_at"}` (`params` es `None` si la fila está corrupta).
- `portfolio.trade_pv_mxn(trade, mkt) -> float`: PV en MXN contra cualquier `MarketContext`, incluido `mkt.shifted(...)`. Puede lanzar (`ValueError`, `ApiError`, error de qfpy): quien recorre el portafolio envuelve en `try/except Exception`, anota `{"id", "error": str(e)}` en `errors` y excluye esa operación.
- Patrón: `mkt = market.load_context(conn, snap)` una vez; `trades = portfolio.load_trades(conn)`; por cada choque `trade_pv_mxn(t, mkt.shifted(...))`. `equity_option` no depende del mercado: su contribución sale cero sola.
- Semilla: 7 operaciones (3 irs, 2 fx_forward, 1 fx_option, 1 cap_floor), total ≈ 1,536,786 MXN en MX-DEMO.

## Tareas

### T1 — Rama y esqueleto del backend
- **Modelo:** sonnet · **Depende de:** — · **R:** R5 (marco de errores), R12 (servir `dist/`, puerto 5070)
- **Objetivo:** crear `feat/qf-desk` y todo el esqueleto de `desk/` con rutas que ya validan y delegan, para que el resto rellene módulos sin tocar rutas.
- **Archivos:** `desk/__init__.py`, `desk/.gitignore`, `desk/api/{__init__,app,qf,errors,validation,db,seed_market,seed_trades,market,portfolio}.py`, `desk/api/pricing/{__init__,base,rates,fx}.py`, `desk/api/risk/{__init__,dv01,scenarios,var}.py`, `desk/api/routes/{__init__,market,price,trades,risk}.py`, `desk/api/tests/{__init__,conftest,test_skeleton}.py`.
- **Pasos:**
  1. `git checkout master && git checkout -b feat/qf-desk`.
  2. Crear los archivos con las interfaces del Contexto. Stubs: `market.py`, `portfolio.py`, `risk/*.py`, `seed_*.py` definen las funciones con la firma del Contexto y `raise NotImplementedError` (o no hacen nada en `seed_*`); `rates.PRODUCTS = {}`, `fx.PRODUCTS = {}`.
  3. Rutas: cada endpoint del contrato registrado en su blueprint; validan lo genérico (cuerpo objeto, `snapshot` presente, producto en `PRODUCTS` → 404 `field:"product"`) y llaman al módulo. Mientras el módulo sea stub, `NotImplementedError` → 501 JSON `{"error":"No implementado","field":null}`.
  4. `app.py`: `create_app(db_path=None, seed=True)`, abre/crea el esquema, siembra según el Contexto, registra blueprints y handlers; sirve `desk/ui/dist/index.html` en `/` y cualquier ruta no-`/api` que no sea archivo (fallback SPA) si existe `dist`; si no, `/` responde 200 texto "Interfaz no construida: ejecutar desk/run.sh". `if __name__ == "__main__"`: `create_app().run(host="0.0.0.0", port=5070)`.
  5. `conftest.py`: inserta la raíz del repo en `sys.path`; fixtures `app(tmp_path)` y `client`.
  6. `test_skeleton.py`: `/api/no-existe` → 404 JSON con `error` y `field`; `POST /api/price/inexistente` → 404 `field=="product"`; JSON mal formado en `POST /api/trades` → 400 JSON; `qfpy` importable vía `desk.api.qf`.
- **Verificación:** `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q 2>&1 | tail -2` → `passed`, 0 failed; `git branch --show-current` → `feat/qf-desk`.
- **Commit:** las rutas listadas.

### T2 — Bootstrap OIS en C++
- **Modelo:** sonnet · **Depende de:** T1 · **R:** R1
- **Objetivo:** curva cero desde depósitos y swaps OIS con periodo en días y devengo ACT/360 (la función `bootstrap()` existente usa `dt = 1/freq` para tiempo y devengo y no sirve para cupones de 28 días ACT/360).
- **Archivos:** `include/qf/termstructure/ois_bootstrap.hpp`, `src/termstructure/ois_bootstrap.cpp`, `tests/test_ois_bootstrap.cpp`, `src/CMakeLists.txt`, `tests/CMakeLists.txt`.
- **API:**
  ```cpp
  namespace qf::termstructure {
  struct OisQuote { int days; double rate; enum Type { Deposit, Ois } type; };
  std::vector<int> oisPaymentDays(int maturityDays, int periodDays); // k*periodDays (k=1..), y maturityDays como último si no es múltiplo
  YieldCurve bootstrapOis(const std::vector<OisQuote>& quotes, int periodDays,
                          math::DayCountConvention accrualDcc = math::DayCountConvention::ACT_360,
                          math::InterpolationMethod method = math::InterpolationMethod::Linear);
  }
  ```
  Tiempo `t = days/365`; tasas cero continuas. Depósito: `DF = 1/(1 + r·days/360)`. OIS: ecuación par `R·Σ τ_i·DF(t_i) = 1 − DF(T)`, `τ_i = (d_i − d_{i−1})/360`; las DF intermedias salen de la propia curva interpolada (incluido el pilar nuevo), resolviendo la tasa cero del pilar nuevo con el Brent de `qf/math/rootfinding.hpp` (tolerancia ≤ 1e-14). Validar: no vacío, `days` estrictamente crecientes y > 0, `periodDays` > 0; `std::invalid_argument` si no.
- **Pasos:** TDD: test primero; implementar; registrar en CMake.
- **Tests mínimos:** cada OIS reprecia a su tasa (par recalculada con la curva resultante a 1e-10); depósito reprecia; subir 10 pb todas las cotizaciones baja toda DF con `t > 0`; `oisPaymentDays(364, 28)` = 13 pagos, `oisPaymentDays(90, 365)` = `{90}`, `oisPaymentDays(400, 365)` = `{365, 400}`; entradas inválidas lanzan.
- **Verificación:** `cmake --build build -j4 2>&1 | tail -3 && cd build && ctest -R OisBootstrap --output-on-failure | tail -3` y luego `ctest | tail -3` → `100% tests passed`.

### T3 — Swap OIS en C++
- **Modelo:** sonnet · **Depende de:** T2 · **R:** R2
- **Objetivo:** instrumento OIS (TIIE-F 28 días, SOFR anual) con tasa par y tabla de flujos cuya suma de PV iguala el NPV.
- **Archivos:** `include/qf/instruments/ois_swap.hpp`, `src/instruments/ois_swap.cpp`, `tests/test_ois_swap.cpp`, `src/CMakeLists.txt`, `tests/CMakeLists.txt`.
- **API:**
  ```cpp
  namespace qf::instruments {
  struct OisCashFlow { int payDays; double payTime; double accrual; double fixedAmount; double floatAmount; double netAmount; double discountFactor; double presentValue; };
  class OisSwap : public Instrument {
   public:
    OisSwap(double notional, double fixedRate, int maturityDays, int periodDays, SwapType type,
            std::string curveKey, math::DayCountConvention dcc = math::DayCountConvention::ACT_360);
    double npv(const core::MarketEnvironment& env) const;            // Σ presentValue
    double calculatePV(const core::MarketEnvironment& env) const override { return npv(env); }
    double parRate(const core::MarketEnvironment& env) const;        // tasa fija con npv = 0
    double annuity(const core::MarketEnvironment& env) const;        // Σ N·τ_i·DF(t_i)
    std::vector<OisCashFlow> cashFlows(const core::MarketEnvironment& env) const;
    // getters: notional(), fixedRate(), maturityDays(), periodDays(), type(), curveKey()
  };
  }
  ```
  Calendario con `termstructure::oisPaymentDays`; `t = días/365`; `τ_i = (d_i − d_{i−1})/360`. `floatAmount_i = N·(DF(t_{i−1})/DF(t_i) − 1)` (flotante compuesta diaria por replicación, `t_0 = 0`), `fixedAmount_i = N·K·τ_i`; `netAmount` = flotante − fija para `Payer`, al revés para `Receiver`; descuento y proyección con `env.curve(curveKey)`. `maturity()` = `maturityDays/365`. Validar notional > 0, días > 0.
- **Tests mínimos:** `|npv(parRate)| < 1e-10·N`; `Σ presentValue == npv` a 1e-12 relativo; payer = −receiver; 13 flujos para 364/28; `ScenarioEngine("TIIE-F").parallelDV01` de un receiver > 0.
- **Verificación:** `cmake --build build -j4 2>&1 | tail -3 && cd build && ctest --output-on-failure | tail -3` → `100% tests passed`.

### T4 — Forward y opción FX (Garman-Kohlhagen) en C++
- **Modelo:** sonnet · **Depende de:** T3 · **R:** R2
- **Objetivo:** forward USDMXN por paridad cubierta y opción europea GK leyendo curvas, spot y superficie del `MarketEnvironment` por nombre (para que los choques de curva/spot del desk los afecten).
- **Archivos:** `include/qf/instruments/fx_forward.hpp`, `src/instruments/fx_forward.cpp`, `tests/test_fx_forward.cpp`, `include/qf/instruments/fx_option.hpp`, `src/instruments/fx_option.cpp`, `tests/test_fx_option.cpp`, `src/CMakeLists.txt`, `tests/CMakeLists.txt`.
- **API:**
  ```cpp
  enum class FxSide { Buy, Sell };   // compra/venta de la divisa extranjera
  class FxForward : public Instrument {
    FxForward(double notionalForeign, double strike, int maturityDays, FxSide side,
              std::string pair = "USDMXN", std::string domesticCurve = "TIIE-F", std::string foreignCurve = "SOFR");
    double npv(const core::MarketEnvironment& env) const;          // s·N·(S·DF_f − K·DF_d), s = +1 Buy / −1 Sell, en moneda doméstica
    double forwardRate(const core::MarketEnvironment& env) const;  // S·DF_f/DF_d
    double delta(const core::MarketEnvironment& env) const;        // s·N·DF_f
  };
  struct FxOptionGreeks { double price; double delta; double gamma; double vega; double forward; double vol; };
  class FxOption : public Instrument {
    FxOption(double notionalForeign, double strike, int maturityDays, OptionType type, FxSide side,
             std::string pair = "USDMXN", std::string domesticCurve = "TIIE-F", std::string foreignCurve = "SOFR");
    double npv(const core::MarketEnvironment& env) const;
    FxOptionGreeks greeks(const core::MarketEnvironment& env) const; // todo ya × s·N; vega por 1 punto de vol (Δσ = 0.01)
  };
  ```
  `T = días/365`, `r_d = −ln DF_d(T)/T`, `r_f = −ln DF_f(T)/T`, `σ = env.volatility(pair, K, T)`. Reusar `qf::pricingengines::blackScholes` con `dividendYield = r_f` (eso es GK); no reescribir la fórmula. Revisar las unidades de vega de `blackScholes` y escalar a "por 1 punto". `FxSide` va en `fx_forward.hpp` y `fx_option.hpp` lo incluye.
- **Tests mínimos:** forward PV == fórmula con DFs de las curvas a 1e-12; `delta` == diferencia finita de spot; paridad call − put == PV del forward con mismo strike a 1e-10 relativo; Buy = −Sell; la vol se toma de la superficie cuando existe.
- **Verificación:** build + `ctest --output-on-failure | tail -3` → `100% tests passed`.

### T5 — VaR delta-normal y flujos de bono en C++
- **Modelo:** sonnet · **Depende de:** T4 · **R:** R2 (flujos de `bond`), R4 (VaR)
- **Objetivo:** (a) VaR paramétrico sobre exposiciones con signo (la `portfolioVaR` existente exige valor total positivo y no aplica a derivados); (b) exponer los flujos del bono, hoy privados.
- **Archivos:** `include/qf/risk/delta_normal_var.hpp`, `src/risk/delta_normal_var.cpp`, `tests/test_delta_normal_var.cpp`, `include/qf/instruments/bond.hpp`, `src/instruments/bond.cpp`, `tests/test_bond_cashflows.cpp`, `src/CMakeLists.txt`, `tests/CMakeLists.txt`.
- **API:**
  ```cpp
  namespace qf::risk {
  double deltaNormalVaR(const std::vector<double>& exposures,   // P&L por movimiento unitario del factor
                        const std::vector<double>& dailyVols,   // en la misma unidad del factor
                        const std::vector<std::vector<double>>& correlations,
                        double confidence, double horizonDays);
  // = normInvCDF(confidence) · sqrt(horizonDays) · sqrt(Σ_ij e_i e_j σ_i σ_j ρ_ij); invalid_argument si tamaños no cuadran, confidence ∉ (0,1), horizon ≤ 0, vol < 0
  }
  // Bond: añadir público
  std::vector<std::pair<double, double>> cashFlowSchedule() const; // (tiempo en años, monto) usando cashflows()/maturities() privados
  ```
- **Tests mínimos:** un factor: VaR == |e|·σ·z·√h a 1e-12; dos factores con ρ=1 y ρ=−1 contra el cálculo a mano; errores lanzan. Bono: `Σ monto·DF(t)` == `price(curve)` a 1e-10.
- **Verificación:** build + `ctest --output-on-failure | tail -3` → `100% tests passed`.

### T6 — Exponer en `qfpy` lo nuevo y lo que faltaba
- **Modelo:** sonnet · **Depende de:** T5 · **R:** R1, R2, R4
- **Objetivo:** que el backend tenga por `qfpy` todo lo que necesita.
- **Archivos:** `src/python_bindings/qfpy.cpp`, `tests/test_desk_bindings_py.py`.
- **Exponer** (snake_case en Python, todos los instrumentos con base `Instrument` para que `pv(env)` funcione):
  - `DayCountConvention` (enum: `ACT_360`, `ACT_365`, `ACT_ACT_ISDA`, `THIRTY_360`).
  - `OisQuoteType` (`Deposit`, `Ois`), `OisQuote(days, rate, type)`, `bootstrap_ois(quotes, period_days, accrual_dcc=ACT_360, method=Linear)`, `ois_payment_days(maturity_days, period_days)`.
  - `OisCashFlow` (campos `pay_days, pay_time, accrual, fixed_amount, float_amount, net_amount, discount_factor, present_value`), `OisSwap(notional, fixed_rate, maturity_days, period_days, swap_type, curve_key, dcc=ACT_360)` con `npv`, `par_rate`, `annuity`, `cash_flows`.
  - `FxSide`, `FxForward(...)` con `npv`, `forward_rate`, `delta`; `FxOptionGreeks`, `FxOption(...)` con `npv`, `greeks`.
  - `CapFloorType`, `CapFloor(type, notional, strike, maturity, frequency, hw_a, hw_sigma, dcc=ACT_365)` con `price(curve)`; `SwaptionType`, `Swaption(type, notional, strike, expiry, swap_tenor, frequency, hw_a, hw_sigma, dcc=ACT_365)` con `price(curve)`.
  - `Bond.cash_flow_schedule()`; constructor de `Bond` con `dcc` opcional.
  - `delta_normal_var(exposures, daily_vols, correlations, confidence, horizon_days)`.
- **Test** (`unittest`, mismo patrón de `sys.path` que `tests/test_dualcurve_py.py`): un caso por símbolo expuesto (construye, valúa, tipo de retorno), y `OisSwap` a su tasa par ≈ 0.
- **Verificación:** `cmake --build build -j4 2>&1 | tail -3`; `cd build && ctest | tail -2` → `100% tests passed`; `cmake --build build --target pytests 2>&1 | tail -3` → `OK`.

### T7 — Mercado: snapshot `MX-DEMO`, curvas y endpoints
- **Modelo:** sonnet · **Depende de:** T6 · **R:** R1, R5, R13 (snapshot)
- **Archivos:** `desk/api/market.py`, `desk/api/seed_market.py`, `desk/api/tests/test_market.py`. (Las rutas ya existen en `routes/market.py`; solo tocarlas si falta pasar algo, y entonces incluirlas en el commit.)
- **Pasos:**
  1. `seed_market(conn)`: inserta `MX-DEMO`, `label` "México demo (sintético)", `synthetic=1`, `as_of` "2026-11-10", con estos datos (todo sintético):
     - TIIE-F (`period_days` 28): depósito `1D` 1 día 7.00 %; OIS `1x28` 6.98, `3x28` 6.92, `6x28` 6.85, `13x28` 6.75, `26x28` 6.70, `39x28` 6.72, `65x28` 6.80, `91x28` 6.90, `130x28` 7.05 (%; `days` = n×28). Ids `TIIE-F:<label>`.
     - SOFR (`period_days` 365): depósito `1D` 3.90 %; OIS `1M`(30 d) 3.85, `3M`(91) 3.80, `6M`(182) 3.75, `1Y`(365) 3.70, `2Y`(730) 3.55, `3Y`(1095) 3.50, `5Y`(1825) 3.55, `7Y`(2555) 3.65, `10Y`(3650) 3.80. Ids `SOFR:<label>`.
     - Spot USDMXN 18.60.
     - Superficie: `expiry_days` [30, 91, 182, 365], `strikes` [17.0, 17.5, …, 20.5]; `vol = atm(T) + 0.5·ln(K/18.60)² + 0.03·ln(K/18.60)` con `atm` = 0.115, 0.120, 0.125, 0.130.
     - `hw` y `factors` exactamente como el ejemplo del contrato.
  2. `market.py`: `MarketContext`, `load_context`, `snapshot_payload`, `list_snapshots`, `update_snapshot` según Contexto y contrato. Curvas con `qfpy.bootstrap_ois` (Linear); superficie con `qfpy.VolSurface(expiry_days/365, strikes, vols)`. `shifted()` con `bumped`/`parallel_bump`. `update_snapshot` valida y persiste en `data`.
- **Tests:** lista contiene `MX-DEMO`; GET trae `quotes`, `curves` con `zero`/`df`/`forward`, `fx`, `vol_surface`, `hw`, `factors`; PUT +10 pb a todas las cotizaciones TIIE-F → toda `df` con `t>0` baja y SOFR no cambia; PUT spot; 404 snapshot inexistente; 400 por `id` desconocido, `rate` no numérico, `spot` ≤ 0; persistencia: PUT, nueva `create_app` sobre la misma DB, GET refleja el cambio.
- **Verificación:** `pytest desk/api/tests -q 2>&1 | tail -2` → 0 failed.

### T8 — Pricers de tasas: `irs`, `cap_floor`, `swaption`, `bond`
- **Modelo:** sonnet · **Depende de:** T7 · **Paralela con:** T9 · **R:** R2, R5
- **Archivos:** `desk/api/pricing/rates.py`, `desk/api/tests/test_price_rates.py`.
- **Pasos:** implementar los cuatro `Product` (validate/price/pv_mxn/describe) con los parámetros y respuestas del contrato.
  - `irs`: `qfpy.OisSwap(notional, fixed_rate or par, periods·period_days, period_days, Payer/Receiver, curve)` sobre `mkt.env`; `fixed_rate` ausente → `par_rate` (crear con tasa 0, pedir `par_rate`, recrear). `cashflows` desde `cash_flows()` (`date = as_of + pay_days`). `dv01 = PV(mkt) − PV(mkt.shifted(curve=c, parallel_bp=1))`.
  - `cap_floor`: `qfpy.CapFloor(..., maturity = periods·period_days/365, frequency = 365/period_days, hw_a, hw_sigma` de `mkt.hw[curve]`, `dcc = ACT_360)`; valuar con `pv(mkt.env_with_default(curve))`.
  - `swaption`: `qfpy.Swaption(..., frequency = 365/period_days, hw` de la curva, `ACT_360)` sobre `env_with_default`.
  - `bond`: `qfpy.Bond(face, coupon_rate, periods, frequency)`; `pv` en `env_with_default(curve)`; `duration`/`convexity` con la curva; flujos con `cash_flow_schedule()` (`date = as_of + round(t·365)`, `df = curve.discount_factor(t)`). `curve` opcional, default `TIIE-F`.
  - `describe`: vencimiento = `as_of` + días del último flujo / del final del swap subyacente.
  - USD → `pv_mxn = pv · mkt.spot`.
- **Tests (R2):** `irs` TIIE-F y SOFR a su `par_rate` → `|pv| < 1e-6·notional`; `sum(cashflows.pv)` == `pv` a 1e-8 relativo; payer = −receiver; `cap_floor` cap y floor con PV > 0; `swaption`/`bond` responden con las llaves del contrato; validación: falta `notional` → 400 `field=="notional"`, `notional` negativo, `periods` 0, `curve` inválida, snapshot inexistente → 404.
- **Verificación:** `pytest desk/api/tests/test_price_rates.py -q 2>&1 | tail -2` → 0 failed.

### T9 — Pricers FX y renta variable: `fx_forward`, `fx_option`, `equity_option`
- **Modelo:** sonnet · **Depende de:** T7 · **Paralela con:** T8 · **R:** R2, R5
- **Archivos:** `desk/api/pricing/fx.py`, `desk/api/tests/test_price_fx.py`.
- **Pasos:**
  - `fx_forward`: `qfpy.FxForward(notional_usd, strike, days, Buy/Sell)` sobre `mkt.env`; `risk = {delta, forward}`.
  - `fx_option`: `qfpy.FxOption(...)`; `risk` desde `greeks()`; sin payoff (el payoff al vencimiento lo dibuja el frontend).
  - `equity_option`: `qfpy.OptionParams` + `qfpy.black_scholes`; PV = `quantity · price`; griegas × `quantity`. Moneda MXN. No depende del mercado: su contribución a DV01, escenarios y VaR es cero.
  - `describe`: notional = `notional_usd` (USD) / `quantity·spot` (MXN); vencimiento `as_of + days` o `+ round(maturity_years·365)`.
- **Tests (R2):** `fx_forward` == `N·(S·DF_usd − K·DF_mxn)` calculado en el test con `mkt.curves[...].discount_factor(days/365)` de `load_context` a 1e-8 relativo; `fx_option` call − put == PV del `fx_forward` buy con mismo strike/días a 1e-8 relativo; venta = −compra; validación de cada campo (faltante, negativo, `option_type` inválido) → 400 con `field`.
- **Verificación:** `pytest desk/api/tests/test_price_fx.py -q 2>&1 | tail -2` → 0 failed.

### T10 — Portafolio: CRUD, valuación y semilla de operaciones
- **Modelo:** sonnet · **Depende de:** T8, T9 · **R:** R3, R5, R13 (portafolio)
- **Archivos:** `desk/api/portfolio.py`, `desk/api/seed_trades.py`, `desk/api/tests/test_portfolio.py`.
- **Pasos:**
  1. `portfolio.py` según Contexto y contrato; `create_trade` valida `product` (400 `field:"product"`), `counterparty`, y `params` con `PRODUCTS[p].validate`; guarda `params` normalizados en JSON; respuesta enriquecida con `describe(params, as_of del snapshot MX-DEMO)` (derivado al vuelo, no se guarda).
  2. `valuation`: por operación `try: pv_mxn` / `except Exception as e: error=str(e)`; nunca deja propagar.
  3. `seed_trades(conn)` inserta (contrapartes sintéticas):
     1. `irs` TIIE-F payer 500,000,000, 26 periodos, 6.80 %, "Banco Alfa (sintético)";
     2. `irs` TIIE-F receiver 250,000,000, 65 periodos, 6.95 %, "Banco Beta (sintético)";
     3. `irs` SOFR payer 20,000,000, 5 periodos, 3.60 %, "Banco Gamma (sintético)";
     4. `fx_forward` buy 10,000,000 USD, 182 días, strike 19.05, "Banco Alfa (sintético)";
     5. `fx_forward` sell 3,000,000 USD, 91 días, strike 18.85, "Banco Beta (sintético)";
     6. `fx_option` buy call 5,000,000 USD, 91 días, strike 19.00, "Banco Gamma (sintético)";
     7. `cap_floor` cap TIIE-F 300,000,000, 39 periodos, strike 7.50 %, "Banco Alfa (sintético)".
- **Tests:** base nueva → 7 operaciones sembradas y valuación con 7 filas sin error; crear, listar, borrar; **persistencia**: crear, construir otra `create_app` sobre la misma DB, la operación sigue; una fila corrupta (insertar a mano `params` inválidos en SQLite) da `error` en su fila y el resto y el total se calculan; `DELETE` inexistente → 404; `snapshot` inexistente en valuación → 404; producto desconocido → 400.
- **Verificación:** `pytest desk/api/tests -q 2>&1 | tail -2` → 0 failed.

### T11 — Riesgo: DV01 por plazo y escenarios
- **Modelo:** sonnet · **Depende de:** T10 · **Paralela con:** T12 · **R:** R4, R5
- **Archivos:** `desk/api/risk/dv01.py`, `desk/api/risk/scenarios.py`, `desk/api/tests/test_risk_dv01_scenarios.py`.
- **Pasos:**
  - DV01: por operación y por curva y pilar `i`: `pv_mxn(mkt) − pv_mxn(mkt.shifted(curve=c, pillar_shifts_bp=e_i))` (vector con 1 en `i`); paralelo con `parallel_bp=1`. Agregar según contrato.
  - Escenarios: `parallel` → `shifted(curve, parallel_bp=bp)`; `steepener` → vector rampa de −bp a +bp sobre los pilares de la curva; `fx_spot` → `shifted(spot_pct=pct)`. P&L = `pv_mxn(choque) − pv_mxn(base)` por operación; validar cada escenario (tipo, curva, `bp`/`pct` numéricos, `pct` > −100) → 400 `field:"scenarios"`.
- **Tests (R4)** con una DB temporal sin la semilla de operaciones (`seed=True` y luego borrar trades, o insertar las propias): portafolio solo de `irs` TIIE-F → `|Σ key-rate − paralelo| < 2 %·|paralelo|`; escenario paralelo TIIE-F +1 pb: `|(−pnl) − DV01 total| < 2 %·|DV01 total|`; spot +10 % mueve solo operaciones FX y SOFR; entradas inválidas → 400/404.
- **Verificación:** `pytest desk/api/tests -q 2>&1 | tail -2` → 0 failed.

### T12 — Riesgo: VaR delta-normal
- **Modelo:** sonnet · **Depende de:** T10 · **Paralela con:** T11 · **R:** R4, R5
- **Archivos:** `desk/api/risk/var.py`, `desk/api/tests/test_risk_var.py`.
- **Pasos:** tres factores en el orden de `mkt.factors.names`. Exposición de tasa por curva = Σ operaciones `pv_mxn(mkt.shifted(curve=c, parallel_bp=1)) − pv_mxn(mkt)`. Exposición `USDMXN` = Σ operaciones `(pv_mxn(spot_pct=+1) − pv_mxn(spot_pct=−1)) / 0.02` (delta × spot, por unidad de rendimiento). Vols diarias del snapshot sustituidas por `factor_vols` si llegan. VaR total = `qfpy.delta_normal_var(exposures, vols, correlations, confidence, horizon_days)`; VaR por factor = la misma función con un solo factor (`[[1.0]]`). Respuesta según contrato. Validar `horizon_days` > 0, `0 < confidence < 1`, `factor_vols` (objeto, llaves ∈ nombres, números ≥ 0) → 400 con su `field`.
- **Tests (R4):** portafolio con un solo `fx_forward` (borrar los sembrados y crear uno): el `var_mxn` del factor `USDMXN` == `|delta|·S·σ·z·√h` a 1e-6 relativo, con `delta` del pricer `fx_forward`, `S` = spot, σ = vol diaria `USDMXN` del snapshot, `z = statistics.NormalDist().inv_cdf(confidence)`; con `factor_vols={"TIIE-F":0,"SOFR":0}` el `var_mxn` total == ese mismo valor a 1e-6; `equity_option` sola → VaR 0; entradas inválidas (incl. `factor_vols` con llave desconocida o negativa) → 400.
- **Verificación:** `pytest desk/api/tests -q 2>&1 | tail -2` → 0 failed.

### T13 — Barrido de errores por endpoint (R5)
- **Modelo:** sonnet · **Depende de:** T11, T12 · **R:** R5
- **Archivos:** `desk/api/tests/test_errors.py`; y, solo si un caso devuelve 500, el módulo culpable (incluirlo en el commit).
- **Pasos:** test parametrizado que recorre cada endpoint del contrato con: cuerpo vacío, cuerpo no-objeto (lista, string), JSON inválido, cada campo obligatorio faltante, números negativos/cero donde no caben, `NaN`/string en campos numéricos, booleanos en campos numéricos, producto y snapshot inexistentes, id de trade inexistente. Afirma status ∈ {400, 404}, JSON con llaves `error` y `field`, y nunca 500. Corregir lo que falle en la frontera del API.
- **Verificación:** `pytest desk/api/tests -q 2>&1 | tail -2` → 0 failed.

### U1 — Esqueleto del frontend
- **Modelo:** sonnet · **Depende de:** T1 · **R:** R6 (tema, tokens), R12 (build)
- **Archivos:** `desk/ui/package.json`, `desk/ui/package-lock.json`, `desk/ui/vite.config.ts`, `desk/ui/tsconfig.json` (+ `tsconfig.node.json` si hace falta), `desk/ui/index.html`, `desk/ui/src/main.tsx`, `desk/ui/src/App.tsx`, `desk/ui/src/vite-env.d.ts`, `desk/ui/src/setupTests.ts`, `desk/ui/src/styles/tokens.css`, `desk/ui/src/styles/base.css`, placeholders: `src/components/Shell.tsx`, `src/components/CommandPalette.tsx`, `src/state/SnapshotContext.tsx`, `src/api/types.ts`, `src/api/client.ts`, `src/lib/format.ts`, `src/screens/{MarketScreen,PortfolioScreen,RiskScreen,MethodologyScreen}.tsx`, `src/screens/pricers/{PricersScreen,PricerForm}.tsx`, `src/screens/pricers/types.ts` (contenido final del Contexto), `src/screens/pricers/registry.ts`, `src/screens/pricers/products/{irs,fx_forward,fx_option,cap_floor,swaption,bond,equity_option}.ts` (spec con `fields: []`), `src/App.test.tsx`.
- **Pasos:**
  1. `npm create`-equivalente a mano: deps `react@18`, `react-dom@18`, `react-router-dom`, `ag-grid-community`, `echarts`, `cmdk`; devDeps `typescript`, `vite`, `@vitejs/plugin-react`, `@types/react`, `@types/react-dom`, `vitest`, `@testing-library/react`, `jsdom`; deps `@fontsource/inter`, `@fontsource/jetbrains-mono` (importadas en `main.tsx`). Scripts: `dev`, `build: "tsc -b && vite build"`, `test: "vitest run"`. `npm install`.
  2. `vite.config.ts`: plugin react, proxy `/api` → `http://localhost:5070`, `test: { environment: 'jsdom', setupFiles: 'src/setupTests.ts' }`.
  3. Tokens y base CSS (tema oscuro denso, `min-width` del layout ≤ 1280 px, `overflow-x: hidden` en el contenedor principal), fuentes Inter y JetBrains Mono desde `@fontsource` (sin CDN; la app debe funcionar sin internet).
  4. `App.tsx` con las rutas del Contexto dentro de `<Shell>` y `main.tsx` con `SnapshotProvider` + `BrowserRouter`. Placeholders mínimos que compilan y respetan las firmas del Contexto (los tipos y el cliente pueden quedar como firma con `throw new Error('pendiente')`; U2 los reemplaza).
  5. `App.test.tsx`: renderiza `/metodologia` sin lanzar.
- **Verificación:** `cd desk/ui && npm test 2>&1 | tail -4` → `passed`; `npm run build 2>&1 | tail -3` → sin errores, `dist/index.html` existe.

### U2 — Tipos, cliente API y formato
- **Modelo:** sonnet · **Depende de:** U1 · **R:** R6, R8 (errores por campo)
- **Archivos:** `desk/ui/src/api/types.ts`, `desk/ui/src/api/client.ts`, `desk/ui/src/api/client.test.ts`, `desk/ui/src/lib/format.ts`, `desk/ui/src/lib/format.test.ts`.
- **Pasos:** transcribir el contrato a tipos TS; cliente `fetch` que en status ≥ 400 lanza `ApiError(status, error, field)` leyendo el JSON; `204` → `undefined`. Formato según Contexto.
- **Tests:** `fmtRate(0.0725)` → `"7.2500 %"`; `fmtMoney(1234567.891, 'MXN')` → `"MXN 1,234,567.89"`; el cliente convierte una respuesta 400 `{"error":"x","field":"notional"}` en `ApiError` con `field === 'notional'` (mock de `fetch` con `vi.fn`).
- **Verificación:** `npm test` y `npm run build` sin errores.

### U3 — Marco: barra lateral, barra superior, snapshot global, paleta Ctrl+K
- **Modelo:** sonnet · **Depende de:** U2 · **R:** R6
- **Archivos:** `desk/ui/src/components/Shell.tsx`, `desk/ui/src/components/Shell.css`, `desk/ui/src/components/CommandPalette.tsx`, `desk/ui/src/components/CommandPalette.css`, `desk/ui/src/state/SnapshotContext.tsx`, `desk/ui/src/components/Shell.test.tsx`.
- **Pasos:** navegación lateral (Mercado, Pricers, Portafolio, Riesgo, Metodología); barra superior con `<select>` de snapshots (de `listSnapshots`) y distintivo "Datos sintéticos" visible si `snapshot.synthetic`; `SnapshotContext` carga lista y snapshot activo y expone la interfaz del Contexto; paleta `cmdk` con Ctrl+K (y Cmd+K) con una entrada por pantalla y una por pricer (de `PRODUCT_SPECS`), Esc cierra, Enter navega.
- **Tests:** con `fetch` simulado, aparece "Datos sintéticos"; Ctrl+K abre la paleta y contiene "Swap IRS"/las siete entradas de pricers.
- **Verificación:** `npm test` y `npm run build` sin errores.

### U4 — Pantalla Mercado
- **Modelo:** sonnet · **Depende de:** U3 · **Paralela con:** U5, U8, U9, U10 · **R:** R7
- **Archivos:** `desk/ui/src/screens/MarketScreen.tsx`, `desk/ui/src/screens/MarketScreen.css`, `desk/ui/src/components/EChart.tsx`, `desk/ui/src/screens/MarketScreen.test.tsx`.
- **Pasos:** `EChart.tsx` (wrapper mínimo `echarts.init`/`setOption`/`dispose`, redimensiona con el contenedor). Por curva (TIIE-F, SOFR): gráfica de `zero` y `forward` contra `days` y tabla AG Grid de cotizaciones con `rate` editable en %; al confirmar la celda → `updateSnapshot(id, {quotes:[{id, rate}]})` → `setSnapshot(respuesta)` y la gráfica se redibuja; error → mensaje junto a la tabla y se revierte la celda. Spot USDMXN editable (`{spot}`). Superficie: heatmap ECharts plazo × strike con vols en %. Parámetros Hull-White (`hw`: `a`, `σ` por curva) en una tabla de solo lectura.
- **Tests:** renderiza con un snapshot de prueba (incluye los valores `hw` sin inputs); editar el spot llama a `updateSnapshot` con `{spot: n}` (mock).
- **Verificación:** `npm test` y `npm run build` sin errores.

### U5 — Formulario de pricer genérico + `irs` y `fx_forward`
- **Modelo:** sonnet · **Depende de:** U3 · **Paralela con:** U4, U8, U9, U10 · **R:** R8
- **Archivos:** `desk/ui/src/screens/pricers/PricersScreen.tsx`, `desk/ui/src/screens/pricers/PricerForm.tsx`, `desk/ui/src/screens/pricers/PricerForm.css`, `desk/ui/src/screens/pricers/products/irs.ts`, `desk/ui/src/screens/pricers/products/fx_forward.ts`, `desk/ui/src/screens/pricers/PricerForm.test.tsx`. (Si U4 aún no creó `components/EChart.tsx`, crear `screens/pricers/PricerChart.tsx` propio con echarts; no tocar archivos de U4.)
- **Pasos:** `PricersScreen` lee `:product`, lista de productos a la izquierda y `PricerForm` con `PRODUCT_SPECS[product]`. `PricerForm`: inputs según `FieldSpec` (Enter = valuar), botón "Valuar" → `price(product, {...params, snapshot})`; resultado: PV y PV MXN, tabla de `risk`, tabla AG Grid de `cashflows` si hay, gráfica: `cashflows` → barras de `amount` por fecha; `payoff` → payoff al vencimiento calculado en el frontend (intrínseco × nocional menos prima = PV, solo presentación; PV y griegas siempre del backend). Campo "Contraparte" + botón "Agregar al portafolio" → `createTrade`. `ApiError.field` → mensaje bajo ese input; sin `field` → banner. Specs: `irs` (TIIE-F, payer, 100,000,000, 13 periodos, tasa fija opcional vacía) y `fx_forward` (buy, 1,000,000 USD, 91 días, strike 18.90). Revaluar al cambiar de snapshot si ya hay resultado.
- **Tests:** error 400 con `field: "notional"` aparece junto al input de nocional; "Agregar al portafolio" llama a `createTrade` con `{product, counterparty, params}`.
- **Verificación:** `npm test` y `npm run build` sin errores.

### U6 — Especificaciones de los otros cinco pricers
- **Modelo:** haiku · **Depende de:** U5 · **R:** R8
- **Archivos:** `desk/ui/src/screens/pricers/products/{fx_option,cap_floor,swaption,bond,equity_option}.ts`.
- **Pasos:** llenar `spec` siguiendo el formato de `products/irs.ts` y los parámetros del contrato. `title` en español. `chart`: `payoff` para `fx_option` y `equity_option`, `cashflows` para `bond`, `none` para `cap_floor` y `swaption`. Defaults: `fx_option` buy call 1,000,000 USD 91 días strike 19.00; `cap_floor` TIIE-F cap 100,000,000 strike 7.50 % 39 periodos; `swaption` TIIE-F payer 100,000,000 strike 7.00 % expiry 1 año tenor 5 años; `bond` TIIE-F face 100 cupón 8.00 % 20 periodos frecuencia 2; `equity_option` call spot 55.00 strike 55.00 vol 25 % tasa 7.00 % dividendo 2 % 1 año cantidad 1,000. `select` con etiquetas en español (p.ej. `payer` → "Pagador de fija").
- **Verificación:** `cd desk/ui && npm run build 2>&1 | tail -3` sin errores y `npm test` pasa.

### U8 — Pantalla Portafolio (blotter)
- **Modelo:** sonnet · **Depende de:** U3 · **Paralela con:** U4, U5, U9, U10 · **R:** R9
- **Archivos:** `desk/ui/src/screens/PortfolioScreen.tsx`, `desk/ui/src/screens/PortfolioScreen.css`, `desk/ui/src/screens/PortfolioScreen.test.tsx`.
- **Pasos:** AG Grid con columnas id, producto, contraparte, nocional, moneda, vencimiento, PV MXN (ordenables y con filtro), fila fija de total (`pinnedBottomRowData` con `total_mxn`), filas con `error` marcadas y el texto en tooltip; botón borrar por fila (confirmación) → `deleteTrade` y recarga; botón "Exportar CSV" (`api.exportDataAsCsv`). Recarga `valuation(snapshotId)` cuando cambia el snapshot.
- **Tests:** con datos simulados aparece la fila de total; cambiar `snapshotId` vuelve a llamar `valuation`.
- **Verificación:** `npm test` y `npm run build` sin errores.

### U9 — Pantalla Riesgo
- **Modelo:** sonnet · **Depende de:** U3 · **Paralela con:** U4, U5, U8, U10 · **R:** R10
- **Archivos:** `desk/ui/src/screens/RiskScreen.tsx`, `desk/ui/src/screens/RiskScreen.css`, `desk/ui/src/screens/RiskScreen.test.tsx`. (Gráfica: si `components/EChart.tsx` de U4 no existe aún, usar echarts directamente en un `useEffect` dentro de este archivo.)
- **Pasos:** escalera DV01: barras por pilar con una serie por curva (de `riskDv01`), totales arriba. Tabla de escenarios (AG Grid: fila por operación, columna por escenario, fila total) con este set fijo enviado a `riskScenarios`: TIIE-F paralelo +50 y −50 pb, SOFR paralelo +50 y −50 pb, TIIE-F steepener 25 pb, SOFR steepener 25 pb, USDMXN +10 % y −10 %. Tarjeta VaR con inputs horizonte (días, default 10) y confianza (%, default 99) que llaman `riskVar` (sin `factor_vols`); muestra VaR total y una fila por factor (exposición, vol diaria, VaR individual); errores junto al input. Todo se recarga al cambiar de snapshot.
- **Tests:** con mocks, la tarjeta muestra el VaR total y los tres factores; cambiar horizonte vuelve a llamar `riskVar` con el valor nuevo.
- **Verificación:** `npm test` y `npm run build` sin errores.

### U10 — Pantalla Metodología
- **Modelo:** haiku · **Depende de:** U3 · **Paralela con:** U4, U5, U8, U9 · **R:** R11
- **Archivos:** `desk/ui/src/screens/MethodologyScreen.tsx`, `desk/ui/src/screens/MethodologyScreen.css`.
- **Pasos:** página estática en español; una sección por producto (`irs` TIIE-F, `irs` SOFR, `fx_forward`, `fx_option`, `cap_floor`, `swaption`, `bond`, `equity_option`) con modelo, convenciones y curvas, tomados de esta lista: IRS TIIE-F = OIS, cupones 28 días, ACT/360, flotante compuesta diaria, descuento y proyección `TIIE-F`; IRS SOFR = OIS anual ACT/360, curva `SOFR`; forward USDMXN = paridad cubierta con `TIIE-F` (MXN) y `SOFR` (USD); opción USDMXN = Garman-Kohlhagen, vol de la superficie por plazo y strike; cap/floor y swaption = Hull-White de un factor con parámetros `a`, `σ` del snapshot; bono = flujos fijos descontados con la curva elegida; opción de renta variable = Black-Scholes con insumos capturados; curvas = bootstrap de depósito + OIS par, tasas cero continuas ACT/365, interpolación lineal en tasa cero; DV01 = PV(base) − PV(+1 pb); VaR = delta-normal con volatilidades y correlaciones de factores del snapshot. Cap/floor y swaption declaran los parámetros Hull-White `a`, `σ` por curva tomados del snapshot. VaR: tres factores (TIIE-F paralelo, SOFR paralelo, USDMXN rendimiento relativo), sin factores por plazo. Sección "Límites de este corte": datos sintéticos; sin XVA; un solo usuario; fechas en días naturales sin calendario de inhábiles, `t = días/365`, SOFR en periodos de 365 días; bono con periodos uniformes (la convención M-Bono de 182 días queda fuera); `equity_option` aporta su PV pero cero a DV01, escenarios y VaR; las operaciones no envejecen entre snapshots (vencimientos derivados del `as_of`); el payoff de opciones es al vencimiento y solo ilustrativo; moneda de reporte MXN al spot del snapshot.
- **Verificación:** `npm run build 2>&1 | tail -3` sin errores; `npm test` pasa (el test de U1 ya renderiza `/metodologia`).

### T14 — `run.sh` y `README.md`
- **Modelo:** haiku · **Depende de:** T1, U1 · **R:** R12
- **Archivos:** `desk/run.sh` (ejecutable), `desk/README.md`.
- **Pasos:** `run.sh` con `set -euo pipefail`: ubica la raíz del repo relativa al script; si falta `build/src/qfpy*.so`, `cmake -S . -B build && cmake --build build --target qfpy -j4`; `cd desk/ui && npm ci` si no hay `node_modules`, `npm run build`; desde la raíz `exec /home/claudio/anaconda3/bin/python -m desk.api.app` (permitir sobreescribir el intérprete con `QF_PYTHON`). README en español: requisitos (Python 3.8 de anaconda con Flask, Node 22, CMake, GTest, pybind11), instalación, `./desk/run.sh`, URL `http://localhost:5070`, cómo correr las cuatro suites (comandos del Contexto), qué es `MX-DEMO` (sintético) y dónde vive la base.
- **Verificación:** `bash -n desk/run.sh && test -x desk/run.sh && echo ok` → `ok`.

### T15 — Integración y entrega
- **Modelo:** sonnet · **Depende de:** todas · **R:** R12, R13 (verificación), R6 (1280×800)
- **Archivos:** ninguno nuevo; solo correcciones puntuales donde falle algo (commit de esas rutas).
- **Pasos:**
  1. `cmake --build build -j4 && cd build && ctest | tail -2` → `100% tests passed` (≥ 347 + nuevos).
  2. `cmake --build build --target pytests | tail -3` → `OK`.
  3. `pytest desk/api/tests -q | tail -2` → 0 failed.
  4. `cd desk/ui && npm test && npm run build` → sin errores.
  5. `rm -f desk/data/desk.db && ./desk/run.sh &` (en segundo plano), esperar al puerto; `curl -s localhost:5070/ | grep -q '<div id="root"'` y `curl -s localhost:5070/api/market/snapshots | grep -q MX-DEMO`; `curl -s 'localhost:5070/api/portfolio/valuation?snapshot=MX-DEMO'` con 7 filas sin error; `POST /api/risk/dv01`, `/scenarios`, `/var` responden 200 con contenido. Detener el servidor.
  6. Si hay navegador disponible, abrir a 1280×800 las cinco pantallas: sin scroll horizontal, con contenido sin capturar nada. Si no, reportarlo como no verificado.
  7. `git status --short` limpio salvo `graphify-out/` y `desk/data/`.
  8. El último commit de T15 (las correcciones, o si no hubo ninguna, `git commit --allow-empty -m "..."`) se hace **sin** `GRAPHIFY_SKIP_HOOK` para que el hook regenere el grafo una vez; no añadir los cambios de `graphify-out/` que deje el hook salvo que Fable lo pida.
- **Verificación:** las salidas anteriores; reporte final con cada comando y su resultado.

---

## Preguntas para Fable

Sin preguntas. P1–P10 resueltas en `## Aclaraciones` de `design.md` e incorporadas al Contexto y a T7, T8, T9, T10, T12, T15, U1, U4, U5, U9 y U10.
