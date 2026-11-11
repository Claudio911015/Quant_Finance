# Plan: QF Desk — Corte 7 (validación independiente contra QuantLib)

Diseño: `/tmp/fableorchestrate/qf-corte7/design.md`. Worktree **`/home/claudio/Git/qf-wt/corte7`**, rama **`corte7`** (creada desde `feat/qf-desk`, base `ce51edf`). Otros cortes avanzan a la vez en otros worktrees: nadie sale de este directorio.

## Contexto

Todo implementador lee esta sección completa y solo su tarea. Lo que sigue es decisión; los huecos del diseño están resueltos en "Supuestos del planificador" (al final) y ya incorporados aquí.

### Entorno
- **Directorio de trabajo único:** `/home/claudio/Git/qf-wt/corte7`. Todas las rutas del plan son relativas a él. No tocar `/home/claudio/Git/Quant_Finance` ni otros `qf-wt/*`.
- **Python del backend:** `/home/claudio/anaconda3/bin/python` (3.8.18; Flask 2.3.3, pytest 8.2.0; Flask vive en `~/.local`: ejecutar sin `-I`). Sintaxis 3.8: nada de `match`, `X | Y`, `list[int]`/`dict[str, x]` evaluados en tiempo de ejecución; usar `typing`. **Sin paquetes nuevos** (ni Python ni npm).
- **Python de QuantLib (solo el arnés, nunca el backend):** `/home/claudio/anaconda3/envs/quantsuite-oracle/bin/python` (Python 3.12.16, **QuantLib 1.44**; entorno conda `quantsuite-oracle`, ya existe: no crear `qfvalid`). Tiene `ql.OvernightIndexedSwap`, `ql.FxForward` + `ql.DiscountingFxForwardEngine(sourceCurve, targetCurve, spotQuoteHandle)`, `ql.JamshidianSwaptionEngine`, `ql.AnalyticCapFloorEngine`, `ql.GarmanKohlagenProcess`. En adelante `$QLPY`.
- **No hay C++ en este corte.** Este worktree no tiene árbol de CMake: `build/src/` solo contiene `qfpy.cpython-38-x86_64-linux-gnu.so` ya compilado (lo carga `desk/api/qf.py`). Nadie compila, ni corre `cmake`/`ctest`, ni toca `include/`, `src/`, `tests/*.cpp`, `CMakeLists.txt`, `build/`. Un defecto que viva en C++ se documenta (ver "Diferencias conocidas"), no se corrige aquí.
- **Node** 22, **npm** 10. Interfaz en `desk/ui` (Vite + React 18 + TS, vitest + jsdom); `desk/ui/node_modules` ya instalado.
- **Las suites** (desde la raíz del worktree salvo vitest):
  - Backend: `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q 2>&1 | grep -E "passed|failed"` → `N passed`, sin `failed` (hoy se recolectan **2335**; no usar `tail`: un warning de pytest_asyncio sale tras el resumen).
  - Bindings `qfpy` (sin CMake, mismo comando que el target `pytests`): `/home/claudio/anaconda3/bin/python -m unittest discover -s tests -p "test_*.py" 2>&1 | tail -3` → `OK`.
  - Interfaz: `cd desk/ui && npm test 2>&1 | grep -E "Test Files|Tests "` (hoy **266** tests en 18 archivos) y `npm run build 2>&1 | tail -5` (`tsc -b && vite build`) sin errores.
  - C++ (ctest): **no se corre en este worktree** (no hay árbol de CMake). En su lugar se comprueba que el corte no toca C++: `git diff --stat ce51edf -- src include tests/*.cpp CMakeLists.txt` vacío.
- **Puertos y procesos:** el desk de Claudio usa **5070**: nadie arranca nada ahí. Backend de prueba de este corte en **5087** con base temporal: `cd /home/claudio/Git/qf-wt/corte7 && /home/claudio/anaconda3/bin/python -c "from desk.api.app import create_app; create_app(db_path='/tmp/fableorchestrate/qf-corte7/it.db').run(host='127.0.0.1', port=5087)"`. La interfaz construida (`desk/ui/dist`) la sirve el mismo Flask. Chrome headless: `google-chrome --headless=new --disable-gpu --user-data-dir=/tmp/fableorchestrate/qf-corte7/chrome-profile` (si hace falta CDP, `--remote-debugging-port=9347`). Todo lo que se levante se apaga con `kill <PID>` (nunca `pkill -f`).
- **No tocar** `desk/data/`, `graphify-out/`, `~/Git/MarketDataFeed`.
- **QuantLib no se importa en ninguna suite** (R7): ningún archivo bajo `desk/api/` ni `tests/` ni `desk/ui/` hace `import QuantLib`; ningún archivo de `desk/validation/` se llama `test_*.py`. Comprobación: `grep -rnE "^\s*(import|from) QuantLib" desk/api tests desk/ui/src` vacío.

### Reglas de ejecución y commits
- Un commit por tarea, solo de tus rutas: `git add <rutas> && GRAPHIFY_SKIP_HOOK=1 git commit -m "<tipo>(desk): <por qué>" -- <rutas>`. Nunca `git add -A`/`.`, nunca `git stash`, nunca push ni merge. Autor: configuración global (Claudio). **Sin `Co-Authored-By`** ni ninguna otra línea de atribución. Mensaje en español que explique el porqué.
- Si `git commit` falla por `.git/index.lock` (u otro lock del worktree), esperar y reintentar; no borrar el lock salvo > 1 min sin proceso git vivo.
- **Archivos compartidos con otros cortes** (`desk/api/app.py`, `desk/ui/src/components/Shell.tsx`, `desk/ui/src/App.tsx`, `desk/ui/src/api/types.ts`, `desk/ui/src/api/client.ts`, `desk/ui/src/screens/MethodologyScreen.tsx`): solo **añadir** en bloques contiguos delimitados por `# corte 7` / `// corte 7` al inicio y `# fin corte 7` / `// fin corte 7` al final; no reordenar ni reformatear nada existente. Lo propio va en módulos nuevos.
- Python orquesta y compara; no hay fórmulas de pricing nuevas en el desk. En `desk/validation/run_quantlib.py` y `ql_*.py` el PV lo calcula **QuantLib** (instrumento + motor); si algún producto no tiene instrumento equivalente, se documenta en su `METHODS` (ver contrato).
- Errores HTTP: `ApiError(status, mensaje_en_español, field)` (`desk/api/errors.py`) → `{"error", "field"}`. Toda respuesta JSON pasa por `ensure_finite` (`desk/api/validation.py`, el módulo de **validación de entrada** del backend; no confundir con el paquete nuevo `desk/validation/`).
- Sin flags, opciones, columnas ni pantallas no pedidas. Textos de interfaz y mensajes en español.

### Firmas existentes que se usan (reales)
- `desk/api/db.py`: `connect(path) -> sqlite3.Connection` (`row_factory=sqlite3.Row`; acepta `":memory:"`), `init_schema(conn)`, `get_conn()`, `now_iso()` (ISO UTC con `+00:00`).
- `desk/api/seed_market.py`: `seed_market(conn)` (inserta `MX-DEMO`, `AS_OF = "2026-11-10"`, `SPOT = 18.60`; sin commit), `demo_data()`. TIIE-F: 10 pilares (1, 28, 84, 168, 364, 728, 1092, 1820, 2548, 3640 días); SOFR: 10 pilares (1, 30, 91, 182, 365, 730, 1095, 1825, 2555, 3650 días). Hull-White: TIIE-F `a=0.05, sigma=0.01`; SOFR `a=0.03, sigma=0.008`.
- `desk/api/seed_trades.py`: `TRADES` (7 tuplas `(product, counterparty, params)`) y `seed_trades(conn)` (requiere `MX-DEMO` sembrado). En una base nueva sus ids son 1–7 en ese orden: 1 `irs` TIIE-F payer 500e6 26 periodos 6.80 %; 2 `irs` TIIE-F receiver 250e6 65 periodos 6.95 %; 3 `irs` SOFR payer 20e6 5 periodos 3.60 %; 4 `fx_forward` buy 10e6 182 d 19.05; 5 `fx_forward` sell 3e6 91 d 18.85; 6 `fx_option` buy call 5e6 91 d 19.00; 7 `cap_floor` cap TIIE-F 300e6 39 periodos 7.5 %.
- `desk/api/market.py`: `load_context(conn, snapshot_id) -> MarketContext` (atributos `snapshot_id`, `as_of` (date), `curves: Dict[str, qfpy.YieldCurve]`, `pillars: Dict[str, List[{"label","days"}]]`, `spot`, `hw`, `env`); `CURVES = {"TIIE-F": {"currency": "MXN", "period_days": 28}, "SOFR": {"currency": "USD", "period_days": 365}}`. `qfpy.YieldCurve.discount_factor(t)` con `t = días/365`.
- **Curvas del desk (C++, fijo):** `qfpy.bootstrap_ois` arma la curva con interpolación **lineal sobre la tasa cero continua**, `t = días/365`, `DF(t) = exp(−z(t)·t)`, y **extrapolación plana de la tasa cero** fuera de `[primer pilar, último pilar]` (`src/math/interpolation.cpp`).
- `desk/api/pricing/__init__.py`: `PRODUCTS: Dict[str, Product]`; `Product(name, validate, price, pv_mxn, describe)`. `PRODUCTS[p].validate(raw) -> params normalizados` (o `ApiError` 400); `PRODUCTS[p].price(params, mkt) -> {"product","currency","pv","pv_mxn","risk","cashflows","details"}`. `pv` va en la moneda del producto: la de la curva en `irs`, `cap_floor`, `swaption`, `bond`; MXN en `fx_forward`, `fx_option`, `equity_option`. Detalles útiles: `irs` → `risk.par_rate`, `details.fixed_rate`; `fx_forward` → `risk.forward`; `fx_option` → `risk.vol` (σ que usó el desk, leída de la superficie en (K, T)), `risk.forward`; `cap_floor`/`swaption` → `details.hw_a`, `details.hw_sigma`.
- Convenciones de los pricers del desk (C++, fijas; las replica QuantLib):
  - `irs` (`qfpy.OisSwap`): pagos en `k·period_days` días (`qfpy.ois_payment_days(periods·period_days, period_days)`), fija ACT/360 sobre días reales del periodo, flotante por replicación `N·(DF(t_{i−1})/DF(t_i) − 1)`, descuento y proyección con la misma curva. `payer` = paga fija.
  - `fx_forward` (`qfpy.FxForward`): `T = days/365`, `F = S·DF_SOFR(T)/DF_TIIE(T)`, `PV_MXN = s·N_usd·(F − K)·DF_TIIE(T)`, `s = +1` buy, `−1` sell.
  - `fx_option` (`qfpy.FxOption`): Garman-Kohlhagen, `r_d = −ln DF_TIIE(T)/T`, `r_f = −ln DF_SOFR(T)/T`, σ de la superficie en (K, T); `PV_MXN = s·N_usd·precio`.
  - `equity_option` (`qfpy.black_scholes`): Black-Scholes europeo con `rate` y `dividend_yield` continuos, `T = maturity_years`; `PV = quantity·precio`. No depende del snapshot.
  - `bond` (`qfpy.Bond(face, coupon_rate, periods, frequency)`, ACT/365): flujos en `t_i = i/frequency` años, cupón `face·coupon_rate/frequency`, principal en el último; descuento con la curva `curve` (default TIIE-F).
  - `cap_floor` (`qfpy.CapFloor`, Hull-White analítico): `n = periods` caplets en `[t_{i−1}, t_i]`, `t_i = i·period_days/365`, `t_0 = 0` (el primero es intrínseco), `τ = period_days/360` en el strike, `dt = period_days/365` en σ_p.
  - `swaption` (`qfpy.Swaption`, Hull-White + Jamshidian): `n = round(swap_tenor_years·365/period_days)` pagos en `T_exp + i·period_days/365`, `c_i = N·K·τ` (`τ = period_days/360`), `c_n = N·(1 + K·τ)`.
- `desk/api/portfolio.py`: `load_trades(conn) -> List[dict]` (`{"id","product","counterparty","trade_date","start_date","maturity_date","params","created_at","events"}`). `desk/api/valuation.py`: `value_trade(trade, mkt, fixings=None) -> {"status","notional","currency","pv","pv_mxn","warnings"}` (`pv` en la moneda del producto, como `PRODUCTS[p].price`).
- Rutas Flask: blueprint por módulo en `desk/api/routes/` (`bp = Blueprint("risk", __name__, url_prefix="/api/risk")`, `@bp.get(...)`, `return jsonify(ensure_finite(...))`). La SPA de `app.py` responde todo lo que no empieza por `api/`.
- Pruebas backend: fixtures `app`, `client` de `desk/api/tests/conftest.py` (base temporal sembrada con `MX-DEMO`, `as_of = 2026-11-10`, 7 operaciones). `monkeypatch` de pytest disponible.
- Interfaz: `src/api/client.ts` (`request<T>(method, path, body?)` privada; `BASE = '/api'`; `ApiError {status, field}`), `src/api/types.ts`, `src/lib/format.ts` (`fmtNumber(v, dec)`, `fmtMoney(v, ccy)`, `fmtRate(dec)`, `fmtDate(iso)`, `fmtDateTime(iso)`), `src/components/Shell.tsx` (`NAV_ITEMS` `{to, label, icon}` con `<Icon>` SVG de 16 px; la paleta de comandos los toma de ahí), `src/components/Shell.test.tsx` (`it('enlaza las seis pantallas y marca la activa')` y `it.each(...)('%s abre la paleta con las seis pantallas y los siete pricers')` comparan la lista exacta de etiquetas), `src/App.tsx` (`<Routes>` con una `<Route>` por pantalla), `src/screens/MethodologyScreen.tsx` (`Section {id, title, items: {label, text: ReactNode}[]}`, `SectionBlock`, grupos `<h2 className="meth-group">`; su test renderiza **sin router** y usa `row(label)` sobre `<dt>`). Tests de pantalla con `vi.mock('../api/client')` como en `HedgesScreen.test.tsx`.

### Paquete nuevo `desk/validation/` (contrato fijo)
Estructura final (quién crea cada archivo, entre paréntesis):
```
desk/validation/
  __init__.py            (T1, vacío)
  common.py              (T1) constantes, rutas, procedencia git, diferencias; stdlib, válido en 3.8 y 3.12, NO importa desk.api
  export_cases.py        (T1 curvas + stub; T2 casos) Python del backend: python -m desk.validation.export_cases
  cases.json             (T1 con cases: []; T2 completo; T7 regenera) versionado
  run_quantlib.py        (T3) Python de QuantLib: $QLPY desk/validation/run_quantlib.py [--cases P] [--out P]
  ql_curves.py           (T3) curvas QuantLib desde los DF del desk
  ql_rates.py            (T3 stub; T4) irs, bond
  ql_hw.py               (T3 stub; T5) cap_floor, swaption
  ql_fx.py               (T3 stub; T6) fx_forward, fx_option, equity_option
  reference.json         (T7) versionado
  compare.py             (T7) Python del backend: python -m desk.validation.compare
  known_differences.json (T7) versionado
  report.json            (T7; T9 lo regenera al final) versionado, lo sirve el backend
  make_report.sh         (T7) encadena export → QuantLib → compare
  README.md              (T7) cómo regenerar
```

**`common.py` (T1; firma exacta):**
```python
PRODUCTS = ("irs", "fx_forward", "fx_option", "equity_option", "bond", "cap_floor", "swaption")
PRODUCT_LABELS = {"irs": "Swap OIS (TIIE de Fondeo y SOFR)", "fx_forward": "Forward USDMXN",
                  "fx_option": "Opción USDMXN (Garman-Kohlhagen)", "equity_option": "Opción sobre acción (Black-Scholes)",
                  "bond": "Bono a tasa fija", "cap_floor": "Cap/floor (Hull-White)", "swaption": "Swaption (Hull-White)"}
TOLERANCES = {"irs": 1e-6, "fx_forward": 1e-8, "fx_option": 1e-6, "equity_option": 1e-6,
              "bond": 1e-6, "cap_floor": 5e-4, "swaption": 5e-4}   # |PV_desk − PV_ref| / nocional
PILLAR_TOLERANCE = 1e-12     # |DF_desk − DF_ql| en pilares
CHECK_TOLERANCE = 1e-8       # |DF_desk − DF_ql| en fechas intermedias
CHECK_COUNT = 10
MIN_CASES = 60
MIN_CASES_PER_PRODUCT = 5
VERDICTS = ("ok", "explained", "fail")
KNOWN_KINDS = ("convention", "interpolation", "defect")
SOURCES = ("portfolio", "battery")
SNAPSHOT_ID = "MX-DEMO"
FAR_DAYS = 36500             # nodo lejano para la extrapolación plana en QuantLib
VALIDATION_DIR = Path(__file__).resolve().parent
REPO_ROOT = VALIDATION_DIR.parents[1]
CASES_PATH = VALIDATION_DIR / "cases.json"
REFERENCE_PATH = VALIDATION_DIR / "reference.json"
KNOWN_PATH = VALIDATION_DIR / "known_differences.json"
REPORT_PATH = VALIDATION_DIR / "report.json"
# Código cuya última modificación define la versión de la valuación del desk.
VALUATION_PATHS = ("src", "include", "CMakeLists.txt", "desk/api/pricing", "desk/api/market.py",
                   "desk/api/valuation.py", "desk/api/qf.py", "desk/api/seed_market.py",
                   "desk/api/seed_trades.py", "desk/validation/export_cases.py")
BACKEND_PYTHON = "/home/claudio/anaconda3/bin/python"
QUANTLIB_PYTHON = "/home/claudio/anaconda3/envs/quantsuite-oracle/bin/python"
QUANTLIB_ENV = "quantsuite-oracle"
REPRODUCE_COMMAND = "desk/validation/make_report.sh"

def now_iso() -> str: ...                       # datetime.now(timezone.utc).isoformat(timespec="seconds")
def desk_commit(root: Path = REPO_ROOT) -> Optional[str]: ...
    # `git -C <root> log -1 --format=%H -- <VALUATION_PATHS>` (subprocess, timeout 5 s); None si git falla o sale vacío
def desk_dirty(root: Path = REPO_ROOT) -> Optional[bool]: ...
    # `git -C <root> status --porcelain -- <VALUATION_PATHS>` no vacío; None si git falla
def check_days(pillar_days: List[int]) -> List[int]: ...
    # [int(round(first + (last − first)·(k + 0.5)/CHECK_COUNT)) for k in range(CHECK_COUNT)]
def diffs(pv_desk: float, pv_ref: Optional[float], notional: float) -> Tuple[Optional[float], Optional[float]]: ...
    # (|pv_desk − pv_ref|, |pv_desk − pv_ref| / notional); (None, None) si pv_ref es None o no finito
def classify(rel_diff: Optional[float], tolerance: float, known: Optional[dict]) -> str: ...
    # None → "fail"; rel ≤ tol → "ok"; known y rel ≤ known["max_rel_diff"] → "explained"; si no → "fail"
```

**Nocional y moneda de cada caso** (relativa = `abs_diff / notional`; ambos en la moneda de `pv`):
`irs`, `cap_floor`, `swaption`: `params.notional`; `bond`: `params.face` — moneda de su curva (USD si `SOFR`). `fx_forward`, `fx_option`: `params.notional_usd × spot` en MXN. `equity_option`: `params.quantity × params.spot` en MXN.

**`cases.json`** (lo escribe `export_cases.py`; ejemplo abreviado, cifras ilustrativas):
```json
{"generated_at": "2026-11-11T20:00:00+00:00",
 "snapshot": {"id": "MX-DEMO", "as_of": "2026-11-10", "spot": 18.6},
 "desk_commit": "ce51edf0c1…(40 hex)", "desk_dirty": false,
 "hw": {"TIIE-F": {"a": 0.05, "sigma": 0.01}, "SOFR": {"a": 0.03, "sigma": 0.008}},
 "curves": {
   "TIIE-F": {"currency": "MXN", "period_days": 28,
              "pillars": [{"label": "1D", "days": 1, "df": 0.9998082…}, {"label": "1x28", "days": 28, "df": 0.99466…}],
              "checks": [{"days": 183, "df": 0.96655…}]},
   "SOFR": {"currency": "USD", "period_days": 365, "pillars": [], "checks": []}},
 "cases": [
   {"id": "irs-01", "product": "irs", "source": "portfolio", "trade_id": 1,
    "label": "Paga fija TIIE-F · 26 periodos de 28 días · fija 6.8000 % · portafolio #1",
    "params": {"curve": "TIIE-F", "side": "payer", "notional": 500000000.0, "periods": 26, "fixed_rate": 0.068},
    "inputs": {"period_days": 28, "payment_days": [28, 56, 728]},
    "currency": "MXN", "notional": 500000000.0, "pv_desk": -1234567.89},
   {"id": "fx_option-02", "product": "fx_option", "source": "battery", "trade_id": null,
    "label": "Compra call USD 2,000,000 a 30 días · strike 18.6000",
    "params": {"side": "buy", "option_type": "call", "notional_usd": 2000000.0, "strike": 18.6, "days": 30},
    "inputs": {"spot": 18.6, "vol": 0.1151, "forward": 18.6293},
    "currency": "MXN", "notional": 37200000.0, "pv_desk": 512345.67}]}
```
- `curves[c].pillars`: un elemento por pilar de `mkt.pillars[c]`, `df = mkt.curves[c].discount_factor(days/365.0)`. `curves[c].checks`: `common.check_days([p["days"] …])`, mismo cálculo de `df`.
- `params`: los normalizados por `PRODUCTS[p].validate(raw)` y, en `irs`, `fixed_rate` **siempre numérico** (si el caso es "a la par", la `par_rate` del desk: `price(...)["risk"]["par_rate"]`).
- `inputs` por producto (lo que la referencia necesita y no está en `params`; se lee del desk, no se recalcula): `irs` `{"period_days", "payment_days"}` (`qfpy.ois_payment_days`); `fx_forward` `{"spot", "forward"}` (`risk.forward`); `fx_option` `{"spot", "vol", "forward"}` (`risk.vol`, `risk.forward`); `equity_option` `{"days"}` (`round(maturity_years·365)`); `bond` `{"schedule": [{"t", "amount"}…]}` (`qfpy.Bond(...).cash_flow_schedule()`, diagnóstico); `cap_floor` `{"period_days", "hw_a", "hw_sigma"}`; `swaption` `{"period_days", "payments", "hw_a", "hw_sigma"}` (`payments = round(swap_tenor_years·365/period_days)`).
- `pv_desk`: casos `portfolio` → `value_trade(trade, mkt)["pv"]` sobre la operación cargada con `load_trades`; casos `battery` → `PRODUCTS[p].price(params, mkt)["pv"]`.

**Batería de casos (fija; T2 la transcribe tal cual; 62 casos).** Ids `"<product>-NN"` numerados por producto en este orden; los `portfolio` primero.

| id | origen | params (antes de `validate`) |
|---|---|---|
| irs-01..03 | portafolio #1, #2, #3 | los de `seed_trades.TRADES[0..2]` |
| irs-04 | batería | TIIE-F payer 100e6, 13 periodos, a la par |
| irs-05 | batería | TIIE-F receiver 100e6, 13, `fixed_rate` 0.0750 |
| irs-06 | batería | TIIE-F payer 50e6, 1, 0.0650 |
| irs-07 | batería | TIIE-F receiver 200e6, 39, 0.0600 |
| irs-08 | batería | TIIE-F payer 300e6, 91, 0.0720 |
| irs-09 | batería | SOFR receiver 10e6, 1, 0.0380 |
| irs-10 | batería | SOFR payer 25e6, 3, a la par |
| irs-11 | batería | SOFR receiver 15e6, 7, 0.0300 |
| irs-12 | batería | SOFR payer 40e6, 10, 0.0420 |
| fx_forward-01..02 | portafolio #4, #5 | `TRADES[3..4]` |
| fx_forward-03..08 | batería | (side, notional_usd, days, strike): (buy, 5e6, 30, 18.70), (sell, 5e6, 30, 18.50), (buy, 2e6, 365, 19.40), (sell, 8e6, 365, 20.00), (buy, 1e6, 730, 19.80), (sell, 3e6, 7, 18.62) |
| fx_option-01 | portafolio #6 | `TRADES[5]` |
| fx_option-02..10 | batería | (side, option_type, notional_usd, days, strike): (buy, call, 2e6, 30, 18.60), (buy, put, 2e6, 30, 18.60), (sell, call, 3e6, 182, 19.50), (sell, put, 3e6, 182, 18.00), (buy, call, 1e6, 365, 17.50), (buy, put, 1e6, 365, 20.50), (buy, call, 4e6, 91, 21.00), (sell, put, 2e6, 91, 18.85), (sell, call, 1e6, 730, 19.00) |
| equity_option-01..08 | batería | (option_type, spot, strike, volatility, rate, dividend_yield, días, quantity), con `maturity_years = días/365.0`: (call, 100, 100, .20, .07, .02, 365, 1000), (put, 100, 100, .20, .07, .02, 365, 1000), (call, 100, 80, .25, .07, 0, 182, 500), (put, 100, 120, .35, .07, 0, 730, 500), (call, 100, 130, .25, .07, .01, 30, 2000), (put, 100, 90, .30, .07, .01, 91, 2000), (call, 50, 50, .30, .04, .05, 1825, 100), (put, 250, 262.5, .18, .10, 0, 365, 50) |
| bond-01..08 | batería | (curve, face, coupon_rate, periods, frequency): (TIIE-F, 100e6, .08, 6, 365/182), (TIIE-F, 100e6, .07, 20, 365/182), (TIIE-F, 50e6, 0, 1, 1), (TIIE-F, 10e6, .10, 13, 365/28), (SOFR, 20e6, .04, 5, 1), (SOFR, 20e6, .03, 8, 365/91), (TIIE-F, 30e6, .065, 3, 365/91), (TIIE-F, 100e6, .075, 6, 2) — `frequency` como `365.0/182` etc.; bond-08 usa la frecuencia por omisión del desk (semestral exacta = 182.5 días) |
| cap_floor-01 | portafolio #7 | `TRADES[6]` |
| cap_floor-02..08 | batería | (curve, cap_type, notional, periods, strike): (TIIE-F, cap, 100e6, 13, .070), (TIIE-F, floor, 100e6, 13, .065), (TIIE-F, cap, 50e6, 6, .060), (TIIE-F, floor, 200e6, 39, .070), (SOFR, cap, 20e6, 5, .040), (SOFR, floor, 20e6, 3, .035), (SOFR, cap, 10e6, 10, .030) |
| swaption-01..08 | batería | (curve, swaption_type, notional, strike, días de expiración, swap_tenor_years), con `expiry_years = días/365.0`: (TIIE-F, payer, 100e6, .070, 365, 2), (TIIE-F, receiver, 100e6, .070, 365, 2), (TIIE-F, payer, 200e6, .068, 730, 5), (TIIE-F, receiver, 50e6, .065, 182, 1), (TIIE-F, receiver, 100e6, .065, 1095, 3), (SOFR, payer, 20e6, .036, 365, 5), (SOFR, receiver, 20e6, .035, 730, 3), (SOFR, payer, 10e6, .040, 1825, 5) |

Conteo: irs 12, fx_forward 8, fx_option 10, equity_option 8, bond 8, cap_floor 8, swaption 8 = **62**. Ningún caso pasa del último pilar de su curva (TIIE-F 3640 días, SOFR 3650).

**Rótulos (`label`, en español; T2):** `irs` "`{Paga fija|Recibe fija}` `{curve}` · `{periods}` periodos de `{period_days}` días · fija `{fixed_rate·100:.4f}` %" + " (a la par)" si lo es; `fx_forward` "`{Compra|Venta}` USD `{notional_usd:,.0f}` a `{days}` días · strike `{strike:.4f}`"; `fx_option` "`{Compra|Venta}` `{call|put}` USD `{notional_usd:,.0f}` a `{days}` días · strike `{strike:.4f}`"; `equity_option` "`{Call|Put}` · S `{spot:g}` · K `{strike:g}` · `{días}` días · σ `{vol·100:g}` % · r `{rate·100:g}` % · q `{q·100:g}` % · `{quantity:g}` títulos"; `bond` "Bono `{curve}` · cupón `{coupon·100:.2f}` % · `{periods}` cupones cada `{365/frequency:g}` días"; `cap_floor` "`{Cap|Floor}` `{curve}` · `{periods}` periodos · strike `{strike·100:.2f}` %"; `swaption` "`{Pagadora|Receptora}` `{curve}` · expira en `{días}` días · swap de `{tenor:g}` años · strike `{strike·100:.2f}` %". A los de portafolio se añade " · portafolio #`{trade_id}`".

**`reference.json`** (lo escribe `run_quantlib.py`):
```json
{"generated_at": "2026-11-11T20:01:00+00:00",
 "reference": {"library": "QuantLib", "version": "1.44", "python": "3.12.16", "env": "quantsuite-oracle"},
 "curves": {"TIIE-F": {"interpolation": "ZeroCurve lineal en tasa cero continua, Actual365Fixed, plana fuera de los pilares (nodos en el día 0 y en el día 36500)",
                       "pillars": [{"days": 1, "df_ref": 0.9998082…}], "checks": [{"days": 183, "df_ref": 0.96655…}]},
            "SOFR": {"interpolation": "…", "pillars": [], "checks": []}},
 "methods": {"irs": "OvernightIndexedSwap + DiscountingSwapEngine (NullCalendar, ACT/360, sin rezago)", "bond": "…", "…": "…"},
 "cases": [{"id": "irs-01", "pv_ref": -1234567.88, "error": null},
           {"id": "swaption-03", "pv_ref": null, "error": "sin pricer de QuantLib para swaption"}]}
```
`pv_ref` en la misma moneda y con el mismo signo que `pv_desk`. Un caso que falla en QuantLib lleva `pv_ref: null` y `error` con el mensaje; el arnés no se detiene.

**`known_differences.json`** (T7; vacío si nada excede su tolerancia):
```json
{"differences": [
  {"case_id": "bond-08", "kind": "convention",
   "convention": "Fechas de pago fraccionarias",
   "cause": "El desk descuenta los cupones semestrales en t = i/2 años (182.5·i días); QuantLib solo admite fechas enteras y se usan round(182.5·i) días con cupón ACT/365 de días reales. Reproducir la diferencia con los DF del desk en ambos calendarios da la magnitud esperada.",
   "expected_rel_diff": 3.1e-6, "max_rel_diff": 4.0e-6}]}
```
Reglas: `kind` ∈ `KNOWN_KINDS`; `cause` concreta (qué convención difiere y cuánto explica, ≥ 40 caracteres; nunca "diferencia de modelo" a secas); `expected_rel_diff` calculado por un procedimiento reproducible descrito en `cause` y dentro de ±10 % de la diferencia observada; `max_rel_diff` ≥ la observada (cota que el reporte usa para clasificar). `defect` solo para un defecto del desk que vive en C++ (no se compila aquí): queda abierto y se reporta a Fable; un defecto del desk en Python se corrige en el corte (T7) con su test.

**`report.json`** (lo escribe `compare.py`; lo sirve el backend tal cual):
```json
{"generated_at": "2026-11-11T20:02:00+00:00",
 "snapshot": {"id": "MX-DEMO", "as_of": "2026-11-10", "spot": 18.6},
 "desk_commit": "ce51edf0c1…", "desk_dirty": false,
 "reference": {"library": "QuantLib", "version": "1.44", "python": "3.12.16", "env": "quantsuite-oracle"},
 "reproduce": {"command": "desk/validation/make_report.sh",
               "backend_python": "/home/claudio/anaconda3/bin/python",
               "quantlib_python": "/home/claudio/anaconda3/envs/quantsuite-oracle/bin/python",
               "steps": ["python -m desk.validation.export_cases", "run_quantlib.py", "python -m desk.validation.compare"]},
 "tolerances": {"irs": 1e-6, "fx_forward": 1e-8, "fx_option": 1e-6, "equity_option": 1e-6, "bond": 1e-6, "cap_floor": 5e-4, "swaption": 5e-4},
 "totals": {"cases": 62, "within": 61, "explained": 1, "failed": 0},
 "summary": [{"product": "irs", "label": "Swap OIS (TIIE de Fondeo y SOFR)", "method": "OvernightIndexedSwap + …",
              "tolerance": 1e-6, "cases": 12, "within": 12, "explained": 0, "failed": 0,
              "worst_abs_diff": 0.0021, "worst_rel_diff": 4.2e-12, "worst_case": "irs-08"}],
 "curves": [{"curve": "TIIE-F", "currency": "MXN", "interpolation": "ZeroCurve lineal …",
             "pillars": 10, "pillar_max_abs_diff": 1.1e-16, "pillar_tolerance": 1e-12,
             "checks": 10, "check_max_abs_diff": 2.2e-16, "check_tolerance": 1e-8, "ok": true}],
 "cases": [{"id": "irs-01", "product": "irs", "label": "…", "source": "portfolio", "trade_id": 1,
            "currency": "MXN", "notional": 500000000.0, "pv_desk": -1234567.89, "pv_ref": -1234567.88,
            "abs_diff": 0.01, "rel_diff": 2e-11, "tolerance": 1e-6, "verdict": "ok", "error": null}],
 "known_differences": [{"case_id": "bond-08", "product": "bond", "label": "…", "kind": "convention",
                        "convention": "Fechas de pago fraccionarias", "cause": "…",
                        "expected_rel_diff": 3.1e-6, "max_rel_diff": 4.0e-6,
                        "observed_rel_diff": 3.05e-6, "tolerance": 1e-6, "verdict": "explained"}]}
```
- `summary` en el orden de `PRODUCTS`; `within` = `ok`, `explained`, `failed` = `fail`; `worst_*` sobre los casos con `rel_diff` no nulo (`null` si ninguno). `cases` en el orden de `cases.json`. `curves` en el orden de `CURVES` (TIIE-F, SOFR); `ok` = ambas diferencias máximas ≤ su tolerancia. `known_differences` = una fila por entrada de `known_differences.json`, con lo observado. `desk_commit`/`desk_dirty` = los de `cases.json` (el momento en que se calcularon los PV del desk).

### Contrato HTTP nuevo (backend ↔ interfaz)
**`GET /api/validation/report`** (blueprint `validation` en `desk/api/routes/validation.py`) → 200 con el contenido de `report.json` más dos claves:
```json
{"…todo report.json…": "…", "current_commit": "ce51edf0c1…", "commit_matches": true}
```
- Ruta del archivo: `current_app.config.get("VALIDATION_REPORT") or common.REPORT_PATH` (las pruebas fijan `app.config["VALIDATION_REPORT"]` a un archivo temporal).
- `current_commit = common.desk_commit()` (llamado como atributo del módulo, `from desk.validation import common` → `common.desk_commit()`, para que las pruebas lo sustituyan con `monkeypatch.setattr(common, "desk_commit", …)`); `commit_matches = current_commit == report["desk_commit"]` si `current_commit` no es `None`, si no `null`.
- Archivo ausente → **404** `{"error": "Aún no hay reporte de validación: genera uno con desk/validation/make_report.sh", "field": null}`. JSON ilegible → 500 por el manejador existente (no se prueba).
- `jsonify(ensure_finite(payload))`.

### Interfaz: piezas fijas (las crea U1)
- `types.ts` (bloque `// corte 7` al final):
```ts
export type ValidationProduct = 'irs' | 'fx_forward' | 'fx_option' | 'equity_option' | 'bond' | 'cap_floor' | 'swaption';
export type ValidationVerdict = 'ok' | 'explained' | 'fail';
export type KnownDifferenceKind = 'convention' | 'interpolation' | 'defect';
export interface ValidationCase { id: string; product: ValidationProduct; label: string; source: 'portfolio' | 'battery'; trade_id: number | null; currency: string; notional: number; pv_desk: number; pv_ref: number | null; abs_diff: number | null; rel_diff: number | null; tolerance: number; verdict: ValidationVerdict; error: string | null; }
export interface ValidationProductSummary { product: ValidationProduct; label: string; method: string; tolerance: number; cases: number; within: number; explained: number; failed: number; worst_abs_diff: number | null; worst_rel_diff: number | null; worst_case: string | null; }
export interface ValidationCurveCheck { curve: string; currency: string; interpolation: string; pillars: number; pillar_max_abs_diff: number; pillar_tolerance: number; checks: number; check_max_abs_diff: number; check_tolerance: number; ok: boolean; }
export interface KnownDifference { case_id: string; product: ValidationProduct; label: string; kind: KnownDifferenceKind; convention: string; cause: string; expected_rel_diff: number; max_rel_diff: number; observed_rel_diff: number | null; tolerance: number; verdict: ValidationVerdict; }
export interface ValidationReport { generated_at: string; snapshot: { id: string; as_of: string; spot: number }; desk_commit: string | null; desk_dirty: boolean | null; reference: { library: string; version: string; python: string; env: string }; reproduce: { command: string; backend_python: string; quantlib_python: string; steps: string[] }; tolerances: Record<ValidationProduct, number>; totals: { cases: number; within: number; explained: number; failed: number }; summary: ValidationProductSummary[]; curves: ValidationCurveCheck[]; cases: ValidationCase[]; known_differences: KnownDifference[]; current_commit: string | null; commit_matches: boolean | null; }
```
- `client.ts` (bloque `// corte 7` al final, con su propia línea `import type { ValidationReport } from './types';` justo después del bloque de imports existente): `export function getValidationReport(): Promise<ValidationReport> { return request('GET', '/validation/report'); }`.
- Ruta `/validacion` → `screens/ValidationScreen.tsx` (`export default function ValidationScreen()`).
- `Shell.tsx` `NAV_ITEMS`: entrada `{to: '/validacion', label: 'Validación'}` **al final** (después de Metodología), icono SVG de 16 px en el estilo de los demás (p. ej. `<path d="M3 8.5l3 3 7-7" />`).
- `src/screens/validationFixture.ts` (U1): `export const VALIDATION_REPORT: ValidationReport` coherente con el contrato: 7 productos en `summary` (uno con `explained: 1`), 2 curvas `ok`, 10 casos (al menos uno por producto, uno `explained` de `bond`, uno `portfolio`), 1 diferencia conocida, `commit_matches: true`, `desk_dirty: false`. Lo usan las pruebas de U1 y U2.
- Etiquetas (en `ValidationScreen.tsx`, no en archivos compartidos): veredicto `ok` "Dentro de tolerancia", `explained` "Diferencia explicada", `fail` "Fuera de tolerancia"; tipo `convention` "Convención", `interpolation` "Interpolación", `defect` "Defecto abierto"; origen `portfolio` "Portafolio de ejemplo", `battery` "Batería". Diferencias y tolerancias en notación científica con 2 decimales (`v.toExponential(2)`, `0` → "0", `null` → "—"); PV con `fmtNumber(v, 2)` y la moneda en su columna; commits a 7 caracteres.

---

## Tareas

### T1 — Contrato del arnés: `common`, curvas exportadas, ruta y registro
- **Modelo:** sonnet · **Depende de:** — · **R:** base de R1, R3, R4 (ruta)
- **Objetivo:** dejar el paquete `desk/validation/` con `common.py` real, la exportación de curvas real, `cases.json` con curvas y `cases: []`, y `GET /api/validation/report` completo, para que T2–T7 y U1–U3 avancen sin leerse.
- **Archivos:** `desk/validation/__init__.py` (nuevo, vacío), `desk/validation/common.py` (nuevo), `desk/validation/export_cases.py` (nuevo), `desk/validation/cases.json` (generado), `desk/api/routes/validation.py` (nuevo), `desk/api/app.py` (solo un bloque `# corte 7` justo antes de `return app`), `desk/api/tests/test_validation_route.py` (nuevo), `desk/api/tests/test_validation_curves.py` (nuevo).
- **Pasos:**
  1. `common.py` exactamente como el Contexto (stdlib; `typing` para anotaciones; `subprocess.run([...], capture_output=True, text=True, timeout=5, check=False)`).
  2. `export_cases.py`: `demo_conn() -> sqlite3.Connection` (`db.connect(":memory:")`, `db.init_schema`, `seed_market`, `seed_trades`, `commit`); `export_curves(mkt) -> dict` (forma `curves` del Contexto); `build_cases(conn, mkt) -> List[dict]` **stub que devuelve `[]`** (lo llena T2); `build(conn=None) -> dict` (documento completo de `cases.json`: `generated_at`, `snapshot` con `spot`, `desk_commit`, `desk_dirty`, `hw` = `mkt.hw`, `curves`, `cases`); `main(argv=None)` con `--out` (por omisión `common.CASES_PATH`) que escribe `json.dump(doc, f, indent=2, ensure_ascii=False)` + salto de línea final e imprime `"cases.json: N casos"`; `if __name__ == "__main__": main()`.
  3. Generar `cases.json`: `/home/claudio/anaconda3/bin/python -m desk.validation.export_cases`.
  4. `routes/validation.py` según el contrato HTTP. En `app.py`, bloque `# corte 7` … `# fin corte 7` antes de `return app`: `from desk.api.routes import validation as validation_routes` y `app.register_blueprint(validation_routes.bp)` (no tocar la tupla existente de blueprints).
  5. Tests `test_validation_route.py` (fixture que escribe un reporte mínimo del contrato en `tmp_path` y fija `app.config["VALIDATION_REPORT"]`): 200 devuelve el reporte más `current_commit`/`commit_matches`; con `desk_commit` sustituido igual al del reporte → `true`, distinto → `false`, `None` → `null`; archivo ausente → 404 con el mensaje del contrato; sin fijar la configuración apunta a `common.REPORT_PATH` (comprobar con `monkeypatch` de `common.REPORT_PATH` a un archivo inexistente → 404). `test_validation_curves.py`: `export_curves` trae 10 pilares por curva con los días del Contexto y `df` == `mkt.curves[c].discount_factor(d/365)` exacto; `checks` == `common.check_days(...)` (10 por curva, estrictamente dentro de `[primero, último]`); `common.classify`: `None`→fail, `≤ tol`→ok, conocido dentro de `max_rel_diff`→explained, conocido por encima→fail; `common.diffs(1.0, None, 1.0) == (None, None)`; `common.desk_commit()` devuelve 40 hex en este worktree.
- **Verificación:** `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests/test_validation_route.py desk/api/tests/test_validation_curves.py -q 2>&1 | grep -E "passed|failed"` → sin `failed`; `python -c "import json;d=json.load(open('desk/validation/cases.json'));print(len(d['curves']['TIIE-F']['pillars']),len(d['curves']['SOFR']['checks']),d['cases'])"` → `10 10 []`; suite backend completa sin `failed`.
- **Commit:** las ocho rutas.

### T2 — Batería de casos y PV del desk
- **Modelo:** sonnet · **Depende de:** T1 · **Paralela con:** T3, U1–U3 · **R:** R1 (≥ 60 casos, 7 productos, ≥ 5 por producto)
- **Objetivo:** `build_cases` con los 62 casos de la tabla del Contexto, `params`/`inputs`/`notional`/`currency`/`label`/`pv_desk` según el contrato; `cases.json` regenerado.
- **Archivos:** `desk/validation/export_cases.py` (solo `build_cases` y auxiliares privados), `desk/validation/cases.json`, `desk/api/tests/test_validation_cases.py` (nuevo).
- **Pasos:** transcribir la tabla (una lista de tuplas por producto); casos de portafolio desde `portfolio.load_trades(conn)` (ids 1–7) con `pv_desk = value_trade(trade, mkt)["pv"]` y `params` = `PRODUCTS[p].validate(trade["params"])` (con `fixed_rate` numérico); casos de batería con `validate` + `price`; `inputs` y `notional` según el Contexto; rótulos según la plantilla. Regenerar `cases.json`.
- **Tests:** 62 casos, ids únicos con el patrón del Contexto; conteo por producto exacto (12/8/10/8/8/8/8) y ≥ `MIN_CASES_PER_PRODUCT`; 7 casos `portfolio` con `trade_id` 1–7; para cada caso `pv_desk` == `PRODUCTS[p].price(params, mkt)["pv"]` (1e-9 relativo al nocional; para los de portafolio prueba que el camino de `value_trade` y el del pricer coinciden); `irs` siempre con `fixed_rate` numérico y en irs-04/irs-10 igual a `risk.par_rate`; `notional`/`currency` según la regla (fx_forward-03: `5e6 × 18.6`, MXN; irs-09: USD); `fx_option` trae `inputs.vol > 0`; todo `label` no vacío y en español (contiene "días" o "periodos" o "cupones" según el producto); el JSON es serializable y sin no finitos (`has_non_finite`).
- **Verificación:** `… -m pytest desk/api/tests/test_validation_cases.py -q 2>&1 | grep -E "passed|failed"`; `/home/claudio/anaconda3/bin/python -m desk.validation.export_cases` imprime `cases.json: 62 casos`; suite backend completa sin `failed`.
- **Commit:** las tres rutas.

### T3 — Runner de QuantLib y curvas idénticas
- **Modelo:** sonnet · **Depende de:** T1 · **Paralela con:** T2, U1–U3 · **R:** R3
- **Objetivo:** `run_quantlib.py` que lee `cases.json`, reconstruye cada curva en QuantLib, mide los DF de pilares y fechas intermedias, despacha cada caso al pricer de su producto y escribe `reference.json`; stubs de los tres módulos de pricers.
- **Archivos:** `desk/validation/run_quantlib.py` (nuevo), `desk/validation/ql_curves.py` (nuevo), `desk/validation/ql_rates.py`, `desk/validation/ql_hw.py`, `desk/validation/ql_fx.py` (nuevos, stubs: `PRICERS = {}` y `METHODS = {}`).
- **Interfaz fija (la usan T4–T6):**
  - `ql_curves.py`: `setup(as_of_iso: str) -> ql.Date` (fija `ql.Settings.instance().evaluationDate` y devuelve la fecha); `build_curve(spec: dict, today: ql.Date) -> ql.YieldTermStructureHandle` donde `spec` = `cases["curves"][c]`: `ql.ZeroCurve(dates, zeros, ql.Actual365Fixed(), ql.NullCalendar(), ql.Linear(), ql.Continuous)` con nodos `today` (cero = la del primer pilar), cada pilar (`today + days`, cero = `−ln(df)/(days/365)`) y `today + FAR_DAYS` (cero = la del último pilar), es decir extrapolación plana como el desk; `INTERPOLATION` (texto del contrato); `curve_report(spec, handle, today) -> {"interpolation", "pillars": [{"days","df_ref"}], "checks": [{"days","df_ref"}]}` con `df_ref = handle.discount(today + days)`.
  - `run_quantlib.py`: `sys.path.insert(0, <directorio del archivo>)`; `import common, ql_curves, ql_rates, ql_hw, ql_fx`; `Context` = dict `{"today": ql.Date, "curves": {"TIIE-F": handle, "SOFR": handle}, "spot": float, "hw": cases["hw"], "currencies": {"TIIE-F": ql.MXNCurrency(), "SOFR": ql.USDCurrency()}}`; registro `PRICERS = {**ql_rates.PRICERS, **ql_hw.PRICERS, **ql_fx.PRICERS}` con firma `pricer(case: dict, ctx: dict) -> float` (PV en la moneda y con el signo de `pv_desk`); `METHODS` igual. Un producto sin pricer → `pv_ref: null`, `error: "sin pricer de QuantLib para <producto>"`; una excepción → `pv_ref: null`, `error: str(exc)`. `main(argv=None)` con `--cases` (default `common.CASES_PATH`) y `--out` (default `common.REFERENCE_PATH`); escribe el JSON del contrato (`indent=2`) e imprime `"reference.json: N casos, M con PV, K errores"`.
- **Pasos:** lo de arriba; `reference.version = ql.__version__`, `python = platform.python_version()`, `env = common.QUANTLIB_ENV`.
- **Verificación** (no hay suite de Python 3.12: verificación por comando):
  1. `$QLPY desk/validation/run_quantlib.py --out /tmp/fableorchestrate/qf-corte7/ref-T3.json` → termina con código 0 (con los stubs, todos los casos que haya llevan `error`).
  2. `$QLPY -c "import json;c=json.load(open('desk/validation/cases.json'));r=json.load(open('/tmp/fableorchestrate/qf-corte7/ref-T3.json'))
for n in ('TIIE-F','SOFR'):
  for k in ('pillars','checks'):
    print(n,k,max(abs(a['df']-b['df_ref']) for a,b in zip(c['curves'][n][k],r['curves'][n][k])))"` → pilares ≤ 1e-12 y fechas intermedias ≤ 1e-8 en ambas curvas (si no, revisar la construcción antes de declarar nada).
  3. `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q 2>&1 | grep -E "passed|failed"` sin `failed` (comprueba que nada de QuantLib entró a la suite).
- **Commit:** las cinco rutas.

### T4 — Referencia QuantLib: swaps OIS y bonos
- **Modelo:** sonnet · **Depende de:** T2, T3 · **Paralela con:** T5, T6 · **R:** R2 (irs, bond)
- **Archivos:** `desk/validation/ql_rates.py` (solo este).
- **Pasos:**
  - `irs`: `ql.OvernightIndex(<nombre>, 0, currency, ql.NullCalendar(), ql.Actual360(), handle)`; `ql.Schedule` desde la lista explícita `[today] + [today + d for d in inputs.payment_days]` con `ql.NullCalendar()` y `ql.Unadjusted`; `ql.OvernightIndexedSwap(ql.Swap.Payer|Receiver, notional, schedule, fixed_rate, ql.Actual360(), index, 0.0, 0, ql.Unadjusted, ql.NullCalendar(), True)` (valor telescópico) con `ql.DiscountingSwapEngine(handle)`; `NPV()`.
  - `bond`: fechas de pago `today + round(i·365/frequency)` días, `i = 1..periods`; `ql.FixedRateBond(0, face, schedule, [coupon_rate], ql.Actual365Fixed())` con esas fechas (`ql.Schedule` explícita, NullCalendar, Unadjusted) y `ql.DiscountingBondEngine(handle)`; `NPV()`. Con las frecuencias de días enteros (365/182, 365/91, 365/28, 1) debe coincidir a 1e-6; bond-08 (frecuencia 2) se espera fuera: calcular la diferencia esperada con un procedimiento reproducible (los DF del desk en `i/2` años contra `round(182.5·i)` días y el cupón ACT/365 de días reales de QuantLib) y anotarla.
  - `METHODS = {"irs": "…", "bond": "…"}` en español, con las piezas de QuantLib usadas.
- **Verificación:** `$QLPY desk/validation/run_quantlib.py --out /tmp/fableorchestrate/qf-corte7/ref-T4.json` y luego
  `$QLPY -c "import json;c=json.load(open('desk/validation/cases.json'));r={x['id']:x for x in json.load(open('/tmp/fableorchestrate/qf-corte7/ref-T4.json'))['cases']}
for k in c['cases']:
  if k['product'] in ('irs','bond'):
    v=r[k['id']]['pv_ref']; print(k['id'], '%.3e'%(abs(k['pv_desk']-v)/k['notional']) if v is not None else r[k['id']]['error'])"` → todos los `irs` ≤ 1e-6 y los `bond` ≤ 1e-6 salvo los anotados.
- **Al terminar:** anotar en `## Anotado por los implementadores` cada caso fuera de tolerancia con causa concreta, procedimiento y magnitud esperada vs observada (T7 los pasa a `known_differences.json`); si la causa es un defecto del desk, describirlo (archivo, línea, efecto).
- **Commit:** la ruta.

### T5 — Referencia QuantLib: caps/floors y swaptions con Hull-White
- **Modelo:** sonnet · **Depende de:** T2, T3 · **Paralela con:** T4, T6 · **R:** R2 (cap_floor, swaption)
- **Archivos:** `desk/validation/ql_hw.py` (solo este).
- **Pasos:**
  - Índice común: `ql.IborIndex(<nombre>, ql.Period(period_days, ql.Days), 0, currency, ql.NullCalendar(), ql.Unadjusted, False, ql.Actual360(), handle)`; modelo `ql.HullWhite(handle, hw_a, hw_sigma)`.
  - `cap_floor`: fechas `today + i·period_days`, `i = 0..periods`; `ql.IborLeg([notional], schedule, index, paymentDayCounter=ql.Actual360(), paymentConvention=ql.Unadjusted, fixingDays=[0])`; `ql.Cap(leg, [strike])` o `ql.Floor(leg, [strike])`; `ql.AnalyticCapFloorEngine(model, handle)`. El primer caplet fija hoy (intrínseco, como el desk).
  - `swaption`: expiración `today + días` (`round(expiry_years·365)`), pagos `expiración + i·period_days`, `i = 0..payments`; `ql.VanillaSwap(Payer|Receiver, notional, fixedSchedule, strike, ql.Actual360(), floatSchedule, index, 0.0, ql.Actual360())`; `ql.Swaption(swap, ql.EuropeanExercise(expiración))`; `ql.JamshidianSwaptionEngine(model, handle)`.
  - `METHODS` en español.
  - Tolerancia 5e-4 relativa al nocional: toda diferencia, aun dentro, se anota caso por caso con su explicación (D3: "la diferencia se explica caso por caso").
- **Verificación:** igual que T4 con `--out /tmp/fableorchestrate/qf-corte7/ref-T5.json` y productos `('cap_floor','swaption')` → todos ≤ 5e-4 salvo los anotados.
- **Al terminar:** anotar como T4 (incluida la peor diferencia de cada producto y su causa aunque esté dentro).
- **Commit:** la ruta.

### T6 — Referencia QuantLib: forwards y opciones FX, opciones sobre acción
- **Modelo:** sonnet · **Depende de:** T2, T3 · **Paralela con:** T4, T5 · **R:** R2 (fx_forward, fx_option, equity_option)
- **Archivos:** `desk/validation/ql_fx.py` (solo este).
- **Pasos:**
  - `fx_forward`: `ql.FxForward(notional_usd, ql.USDCurrency(), ql.MXNCurrency(), strike, today + days, paySourceCurrency=(side == "sell"), settlementDays=0, paymentCalendar=ql.NullCalendar())` con `ql.DiscountingFxForwardEngine(curva SOFR, curva TIIE-F, QuoteHandle(SimpleQuote(spot)))`; PV en MXN con el signo del desk (comprobar el sentido de `spot`, `paySourceCurrency` y de `NPV()` contra `inputs.forward`: `fairForwardRate()` debe igualarlo a 1e-10; si el instrumento no permite liquidación en la fecha exacta, documentar en `METHODS` y usar la alternativa más cercana de QuantLib).
  - `fx_option`: `ql.GarmanKohlagenProcess(QuoteHandle(spot), curva SOFR, curva TIIE-F, ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, ql.NullCalendar(), inputs.vol, ql.Actual365Fixed())))`; `ql.VanillaOption(ql.PlainVanillaPayoff(Call|Put, strike), ql.EuropeanExercise(today + days))`; `ql.AnalyticEuropeanEngine`; `PV = s·notional_usd·NPV()`.
  - `equity_option`: `ql.BlackScholesMertonProcess` con `FlatForward(today, dividend_yield, Actual365Fixed, Continuous)`, `FlatForward(today, rate, …)`, `BlackConstantVol(volatility)` y spot; ejercicio `today + inputs.days`; `PV = quantity·NPV()`.
  - `METHODS` en español.
- **Verificación:** igual que T4 con `--out /tmp/fableorchestrate/qf-corte7/ref-T6.json` y productos `('fx_forward','fx_option','equity_option')` → forwards ≤ 1e-8, opciones ≤ 1e-6, salvo los anotados.
- **Al terminar:** anotar como T4.
- **Commit:** la ruta.

### T7 — Comparación, diferencias conocidas, `make_report.sh`, README y reporte versionado
- **Modelo:** sonnet · **Depende de:** T4, T5, T6 · **R:** R1, R2, R3, R6 (README)
- **Archivos:** `desk/validation/compare.py` (nuevo), `desk/validation/make_report.sh` (nuevo, ejecutable), `desk/validation/known_differences.json` (nuevo), `desk/validation/README.md` (nuevo), `desk/validation/cases.json`, `desk/validation/reference.json`, `desk/validation/report.json`; **solo si hay un defecto del desk en Python:** el archivo de `desk/api/` que lo contiene y un test nuevo en `desk/api/tests/` que lo pruebe.
- **Pasos:**
  1. `compare.py`: `compare(cases_doc, reference_doc, known_doc) -> dict` (forma `report.json` del Contexto, con `common.diffs`, `common.classify`, `common.TOLERANCES`, `common.PILLAR_TOLERANCE`/`CHECK_TOLERANCE`, `reproduce` desde `common`); `main()` lee `CASES_PATH`, `REFERENCE_PATH`, `KNOWN_PATH` (ausente = `{"differences": []}`), escribe `REPORT_PATH` (`indent=2`, `ensure_ascii=False`) e imprime `"report.json: N casos · W dentro · E explicadas · F fuera"`; sale con código 1 si `F > 0` o alguna curva no está `ok` (pero escribe el reporte).
  2. `make_report.sh`: `#!/usr/bin/env bash`, `set -euo pipefail`, `cd "$(dirname "$0")/../.."`, `BACKEND_PY="${BACKEND_PY:-/home/claudio/anaconda3/bin/python}"`, `QL_PY="${QL_PY:-/home/claudio/anaconda3/envs/quantsuite-oracle/bin/python}"`, y los tres pasos (`"$BACKEND_PY" -m desk.validation.export_cases`, `"$QL_PY" desk/validation/run_quantlib.py`, `"$BACKEND_PY" -m desk.validation.compare`). `chmod +x`.
  3. Correr `desk/validation/make_report.sh`. Con lo anotado por T4–T6 y lo que salga, para cada caso fuera de tolerancia: si es un **defecto del desk en Python**, corregirlo con su test (y volver a correr); si vive en **C++**, entrada `kind: "defect"` y anotarlo para Fable; si es **convención o interpolación**, entrada con causa concreta y `expected_rel_diff` recalculado aquí por el procedimiento descrito (±10 % de lo observado) y `max_rel_diff` ≥ observado. Ninguna entrada para casos dentro de tolerancia.
  4. README (español): qué valida y qué no; entorno (`quantsuite-oracle`, QuantLib 1.44, Python 3.12; el backend no depende de QuantLib; cómo crear un entorno equivalente con `pip install QuantLib==1.44` en otra máquina); comandos (`desk/validation/make_report.sh`, variables `BACKEND_PY`/`QL_PY`, los tres pasos sueltos); archivos y su forma; tolerancias; cómo agregar un caso; qué hace el aviso de commit (`VALUATION_PATHS`) y que hay que **commitear el código antes de regenerar** para que `desk_dirty` sea `false`; el test de humo.
  5. Commit de código y datos; luego **regenerar** con `make_report.sh` (el `desk_commit` ya es el definitivo para los PV) y, si cambió algo además de `generated_at`, entender por qué; commit final de los cuatro JSON.
- **Verificación:** `desk/validation/make_report.sh` sale con 0 e imprime `62 casos · … · 0 fuera`; `python -c` sobre `report.json`: `totals.failed == 0`, `cases ≥ 60`, 7 productos con ≥ 5, ambas curvas `ok`, `desk_dirty == false`; suite backend completa sin `failed`.
- **Commit:** las rutas tocadas (dos commits según el paso 5).

### T8 — Prueba de humo del reporte en la suite del backend
- **Modelo:** sonnet · **Depende de:** T7 · **R:** R5, D5
- **Archivos:** `desk/api/tests/test_validation_report.py` (nuevo).
- **Pasos:** función privada `_problems(report: dict, known: dict) -> List[str]` (independiente de `compare.py`; usa solo `common`) que comprueba: `cases ≥ MIN_CASES`; los 7 `PRODUCTS` con ≥ `MIN_CASES_PER_PRODUCT`; ids únicos; por caso `tolerance == TOLERANCES[product]`, `abs_diff`/`rel_diff` **recalculados** desde `pv_desk`, `pv_ref` y `notional` iguales a los guardados (`math.isclose(rel_tol=1e-9, abs_tol=1e-15)`), veredicto recalculado con `classify` y la entrada de `known` == guardado, y ningún `fail`; `totals` y `summary` cuadran con `cases`; cada entrada de `known` existe en `cases`, `kind` ∈ `KNOWN_KINDS`, `cause` ≥ 40 caracteres, `convention` no vacío, `expected_rel_diff` a ±10 % de lo observado; curvas `ok` con diferencias ≤ tolerancias. Tests: `test_el_reporte_existe` (falla si `common.REPORT_PATH` no existe, con mensaje que manda a `make_report.sh`); `test_el_reporte_versionado_no_tiene_problemas` (`_problems == []`, el mensaje lista los problemas); `test_un_pv_alterado_a_mano_falla` (copia profunda, `pv_desk` del primer caso `+= 1e-3 × notional`, `_problems` no vacío); `test_un_caso_fuera_sin_explicacion_falla` (copia con `pv_ref` desplazado `10 × tolerance × notional` y verdict sin tocar → problemas); `test_una_explicacion_sin_caso_falla`.
- **Verificación:** `… -m pytest desk/api/tests/test_validation_report.py -q 2>&1 | grep -E "passed|failed"` sin `failed`; manual: `cp desk/validation/report.json /tmp/fableorchestrate/qf-corte7/report.bak && python -c` que altere un `pv_desk` en `report.json` → el test falla; `cp /tmp/fableorchestrate/qf-corte7/report.bak desk/validation/report.json` → pasa; `git diff --quiet desk/validation/report.json` (restaurado). Suite backend completa sin `failed`.
- **Commit:** la ruta.

### U1 — Contrato en la interfaz: tipos, cliente, ruta, navegación y stub
- **Modelo:** sonnet · **Depende de:** — · **Paralela con:** todo · **R:** base de R4
- **Archivos:** `desk/ui/src/api/types.ts`, `desk/ui/src/api/client.ts`, `desk/ui/src/api/client.test.ts`, `desk/ui/src/App.tsx`, `desk/ui/src/components/Shell.tsx`, `desk/ui/src/components/Shell.test.tsx`, `desk/ui/src/screens/ValidationScreen.tsx` (nuevo, stub `export default function ValidationScreen() { return <section data-testid="validation-stub"><h1>Validación independiente</h1></section>; }`), `desk/ui/src/screens/validationFixture.ts` (nuevo).
- **Pasos:** transcribir "Interfaz: piezas fijas" en bloques `// corte 7`; en `App.tsx` una línea de import y una `<Route path="/validacion" …>` después de la de Metodología, cada una en su bloque `// corte 7` (en JSX: `{/* corte 7 */}`); entrada de navegación al final de `NAV_ITEMS`.
- **Tests:** `client.test.ts`: `getValidationReport()` llama `GET /api/validation/report` y devuelve el cuerpo; un 404 → `ApiError` con `status 404`. `Shell.test.tsx`: las dos listas exactas terminan en `'Validación'` (renombrar los `it` a "las siete pantallas"; la paleta: "las siete pantallas y los siete pricers"). `validationFixture.ts` compila con `tsc -b`.
- **Verificación:** `cd desk/ui && npm test 2>&1 | grep -E "Test Files|Tests "` sin fallos y `npm run build 2>&1 | tail -5` sin errores.
- **Commit:** las ocho rutas.

### U2 — Pantalla Validación
- **Modelo:** sonnet · **Depende de:** U1 · **Paralela con:** T2–T8, U3 · **R:** R4
- **Archivos:** `desk/ui/src/screens/ValidationScreen.tsx`, `desk/ui/src/screens/ValidationScreen.css` (nuevo), `desk/ui/src/screens/ValidationScreen.test.tsx` (nuevo).
- **Pasos:** `getValidationReport()` al montar. Secciones, en este orden:
  1. `<h1>Validación independiente</h1>` y una línea de procedencia: "Generado el `{fmtDateTime(generated_at)}` · QuantLib `{reference.version}` (Python `{reference.python}`, entorno `{reference.env}`) · snapshot `{snapshot.id}` al `{fmtDate(snapshot.as_of)}` · commit `{desk_commit 7}`".
  2. Avisos (`role="status"`, clase `vld-warning`), solo cuando aplican: `commit_matches === false` → "El reporte se generó con el commit `{desk_commit 7}` y el código de valuación actual está en `{current_commit 7}`: regenera el reporte (ver «Cómo reproducir»)."; `commit_matches === null` → "No se pudo determinar el commit actual del código de valuación."; `desk_dirty === true` → "El reporte se generó con cambios sin commit en el código de valuación.".
  3. Totales: "`{cases}` casos · `{within}` dentro de tolerancia · `{explained}` con diferencia explicada · `{failed}` fuera de tolerancia".
  4. "Resumen por producto": tabla Producto, Método de referencia, Casos, Dentro, Explicadas, Fuera, Peor diferencia (rel. al nocional), Tolerancia.
  5. "Curvas": tabla Curva, Interpolación, Máx. diferencia en pilares, Máx. diferencia en fechas intermedias, Tolerancias (`pilares {p} · intermedias {c}`), Estado ("Idénticas" / "Difieren").
  6. "Casos": filtros `<select aria-label="Producto">` ("Todos los productos" + `summary[].label`) y `<select aria-label="Veredicto">` ("Todos los veredictos" + las tres etiquetas); texto "Mostrando n de m casos"; tabla Caso, Producto, Descripción (con "Portafolio de ejemplo" si aplica), Moneda, Nocional, PV QF Desk, PV QuantLib, Diferencia, Dif. relativa, Tolerancia, Veredicto (`null` → "—"; `error` como `title`).
  7. "Diferencias conocidas": por entrada, caso (id y rótulo), producto, tipo, convención, causa, "esperada `{e}` · observada `{o}` · tolerancia `{t}`"; vacío: "Ninguna: todos los casos están dentro de su tolerancia."
  8. "Cómo reproducir": `<pre>` con `reproduce.command` y los pasos, y las rutas de los dos Python.
  - Errores: 404 → "Aún no hay reporte de validación. Genera uno con desk/validation/make_report.sh."; otros → banda con el mensaje.
  - A 1280 px sin desborde horizontal de la página: tablas en contenedor con `overflow-x: auto`, fuente de cifras `.num`, `Descripción` que envuelve; prefijo de clases `vld-`.
- **Tests (con `VALIDATION_REPORT` del fixture y `vi.mock('../api/client')`):** aparecen las 7 filas del resumen y "QuantLib 1.44" en la procedencia; filtrar por un producto deja solo sus casos y actualiza "Mostrando"; filtrar "Diferencia explicada" deja solo el caso explicado; la diferencia conocida muestra su causa y "Convención"; sin aviso con `commit_matches: true`; con `false` aparece el aviso con ambos commits a 7 caracteres; con `null` el aviso de commit indeterminado; con `desk_dirty: true` su aviso; 404 → mensaje de "Aún no hay reporte"; "Cómo reproducir" muestra `desk/validation/make_report.sh`.
- **Verificación:** `npm test` y `npm run build` sin errores.
- **Commit:** las tres rutas.

### U3 — Metodología: validación independiente
- **Modelo:** haiku · **Depende de:** — · **Paralela con:** todo · **R:** R6 (Metodología enlaza a Validación), D6
- **Archivos:** `desk/ui/src/screens/MethodologyScreen.tsx`, `desk/ui/src/screens/MethodologyScreen.test.tsx`.
- **Pasos:** (a) bloque `// corte 7` con `const VALIDATION_SECTIONS: Section[]` justo antes de `function SectionBlock`; (b) en el JSX, bloque `{/* corte 7 */}` … `{/* fin corte 7 */}` justo antes de la sección "Límites de este corte": `<h2 className="meth-group">Validación independiente</h2>` y el `SectionBlock` de la sección `{id: 'validacion', title: 'Validación contra QuantLib'}` con estos ítems (label → texto):
  - **Referencia** → "QuantLib, ejecutado fuera del backend en un entorno de Python aparte; la versión y el entorno quedan en cada reporte. El escritorio no depende de QuantLib."
  - **Qué se compara** → "El PV de los siete productos (swaps OIS de TIIE de Fondeo y SOFR, forwards y opciones USDMXN, opciones sobre acción, bonos, caps/floors y swaptions) en el snapshot MX-DEMO: el portafolio de ejemplo y una batería de casos por producto (lados, plazos, dentro y fuera del dinero), con las mismas curvas, spot, volatilidades y parámetros de Hull-White."
  - **Curvas idénticas** → "QuantLib reconstruye cada curva desde los factores de descuento del escritorio en sus pilares, con la misma interpolación (lineal en tasa cero continua, t = días/365, plana fuera de los pilares). Se comprueba en los pilares (1e-12) y en 10 fechas intermedias (1e-8)."
  - **Tolerancias** → "Relativas al nocional: swaps OIS 1e-6; forwards 1e-8; opciones FX y sobre acción 1e-6; bonos 1e-6; caps/floors y swaptions con Hull-White 5e-4, porque las implementaciones y convenciones del modelo difieren."
  - **Diferencias conocidas** → "Toda diferencia mayor a su tolerancia queda explicada caso por caso (qué convención difiere y cuánto explica) o se trata como defecto. Una prueba de la suite del backend falla si algún caso excede su tolerancia sin explicación."
  - **Qué no se compara** → "Riesgo (DV01, escenarios, VaR), XVA, contabilidad de coberturas, valuación de operaciones envejecidas con fijaciones y datos de mercado reales de un proveedor. ORE no se usa como segunda referencia."
  - **Reporte** → JSX: `<>El último reporte, con su fecha, la versión de QuantLib, el commit con que se generó y cómo regenerarlo, está en la <a href="/validacion">pantalla Validación</a>.</>` (enlace `<a>` simple: la pantalla de Metodología se prueba sin router).
- **Tests:** con `row(label)`: "Tolerancias" contiene "5e-4" y "1e-8"; "Qué no se compara" contiene "VaR" y "contabilidad de coberturas"; "Curvas idénticas" contiene "lineal en tasa cero"; el enlace `getByRole('link', {name: 'pantalla Validación'})` tiene `href` `/validacion`.
- **Verificación:** `npm test` y `npm run build` sin errores.
- **Commit:** las dos rutas.

### T9 — Integración contra el backend real, capturas y las suites
- **Modelo:** sonnet · **Depende de:** T1–T8, U1–U3 (todas) · **R:** R1, R4 (1280 px, textos), R5, R7; verificación de R1–R6 de punta a punta
- **Archivos:** ninguno nuevo; solo correcciones puntuales donde falle algo (commit de esas rutas) y, si el paso 2 lo pide, los JSON regenerados. Respuestas en `/tmp/fableorchestrate/qf-corte7/it/`, capturas en `/tmp/fableorchestrate/qf-corte7/shots/` (no se commitean).
- **Pasos:**
  1. Suites: backend, bindings (`unittest discover`), vitest y `npm run build` → verdes; reportar conteos. C++: `git diff --stat ce51edf -- src include tests/*.cpp CMakeLists.txt` vacío (no hay árbol de CMake; reportar "no aplica: sin cambios en C++"). `grep -rnE "^\s*(import|from) QuantLib" desk/api tests desk/ui/src` vacío (R7).
  2. R1 de punta a punta: `git status --short desk/validation` limpio; `desk/validation/make_report.sh` → código 0 y `0 fuera`; `git diff --stat desk/validation`: solo deben cambiar marcas de tiempo (`generated_at`); si cambia algo más, investigar. Si quedó distinto, commit de los JSON regenerados.
  3. R5: `cp desk/validation/report.json /tmp/fableorchestrate/qf-corte7/report.bak`; alterar un `pv_desk` con `python -c`; `pytest desk/api/tests/test_validation_report.py` → falla; restaurar con `cp` → pasa; `git diff --quiet desk/validation/report.json`.
  4. `cd desk/ui && npm run build`; `rm -f /tmp/fableorchestrate/qf-corte7/it.db`; backend en **5087** (comando del Contexto) en segundo plano, guardar el PID, esperar el puerto. `curl -s http://127.0.0.1:5087/api/validation/report > /tmp/fableorchestrate/qf-corte7/it/report.json` → `commit_matches: true`, `totals.failed == 0`, 7 productos en `summary`.
  5. Capturas con Chrome headless propio (`--user-data-dir=/tmp/fableorchestrate/qf-corte7/chrome-profile`): `google-chrome --headless=new --disable-gpu --user-data-dir=… --window-size=1280,800 --screenshot=<png> http://127.0.0.1:5087/validacion`, otra de `/validacion` a `1280,4000`, y `/metodologia` a `1280,8000` (la sección nueva está al final). Revisar cada captura con `Read`: textos en español, sin desborde horizontal ni texto cortado, procedencia y totales visibles; si es posible, comprobar `document.documentElement.scrollWidth <= 1280` por CDP en el puerto **9347** (script de Node 22 en `/tmp`, sin dependencias); lo no comprobable se reporta como no verificado.
  6. Aviso de commit distinto (R4): detener el servidor (`kill <PID>`); copiar `report.json` a `/tmp/fableorchestrate/qf-corte7/it/report-otro.json` cambiando `desk_commit` a `"0000000000000000000000000000000000000000"`; arrancar en 5087 con `app = create_app(db_path=…); app.config["VALIDATION_REPORT"] = "/tmp/fableorchestrate/qf-corte7/it/report-otro.json"; app.run(...)`; captura de `/validacion` a 1280×800 con el aviso visible; detener.
  7. Apagar todo (`kill <PID>` del backend y de cualquier Chrome lanzado). `git status --short` limpio salvo `graphify-out/`.
  8. Último commit (correcciones o `git commit --allow-empty -m "test(desk): integración del corte 7 …"`), también con `GRAPHIFY_SKIP_HOOK=1`.
- **Verificación:** reporte con cada comando y su resultado, conteos de las suites, rutas de capturas y lista de correcciones.

---

## Orden y paralelismo

```
T1 ──┬─ T2 ──┐
     └─ T3 ──┴─┬─ T4 ─┐
               ├─ T5 ─┼─ T7 ── T8 ──┐
               └─ T6 ─┘             ├─ T9
U1 ── U2 ───────────────────────────┤
U3 ─────────────────────────────────┘
```
- Grupo A (inmediato): **T1, U1, U3**.
- Grupo B: **T2 y T3** (tras T1), **U2** (tras U1).
- Grupo C: **T4, T5, T6** (tras T2 y T3).
- Grupo D: **T7** (tras T4–T6), luego **T8**.
- **T9** al final, sola.
- Archivos: ninguna pareja de tareas concurrentes comparte archivo. `export_cases.py` y `cases.json`: T1 → T2 → T7 en serie. T4–T6 escriben cada una su `ql_*.py` y su referencia en `/tmp` (`--out`), nunca `desk/validation/reference.json` (solo T7). T3 lee `cases.json` solo por sus curvas (iguales en T1 y T2), así que puede correr mientras T2 lo regenera. `Shell.test.tsx` solo U1; `MethodologyScreen*` solo U3.
- Camino crítico: T1 → T3/T2 → T4–T6 → T7 → T8 → T9 (seis niveles).

## Cobertura de requisitos

| R | Tareas |
|---|---|
| R1 | T2 (62 casos, 7 productos, ≥ 5), T7 (`make_report.sh` de punta a punta), T9 |
| R2 | T4, T5, T6 (referencia por producto y diferencias anotadas), T7 (`known_differences.json` con causa y magnitud), T8 |
| R3 | T1 (DF exportados), T3 (curvas QuantLib y comprobación), T7 (en el reporte), T8 |
| R4 | T1 (ruta), U1, U2, T9 (1280 px, aviso de commit) |
| R5 | T8, T9 (alteración manual) |
| R6 | T7 (README), U3 (Metodología enlaza a Validación) |
| R7 | todas (suite verde por tarea), T3 y T9 (sin QuantLib en las suites) |

## Supuestos del planificador

1. **Entorno de QuantLib:** se usa el entorno existente `quantsuite-oracle` (QuantLib 1.44, Python 3.12.16), no se crea `qfvalid` (D1 manda crearlo solo si ninguno lo tiene; los entornos que el diseño menciona no lo tienen, pero este sí, y `qfcurriculum` trae la 1.43). Se anota en README y en cada reporte.
2. **Suite C++:** no se corre en este worktree (no hay árbol de CMake y está prohibido compilar aquí). Se sustituye por la comprobación de que el corte no toca C++ (`git diff` vacío contra `ce51edf`). La suite de bindings sí corre, con `unittest discover` sobre `tests/` (el mismo comando que el target `pytests`).
3. **Defectos en C++:** si la validación destapa uno, no se corrige aquí (no se compila); queda en `known_differences.json` con `kind: "defect"`, causa y magnitud, y se reporta a Fable. Los defectos en Python del desk sí se corrigen en T7 con su test.
4. **"Commit del desk" y aviso de commit distinto:** el commit relevante no es `HEAD` (commitear `report.json` cambiaría `HEAD` y el aviso saldría siempre), sino el último commit que tocó el código de valuación (`VALUATION_PATHS`). El backend lo recalcula en cada petición con `git log`; si git no está disponible, `commit_matches` es `null` y la pantalla lo dice. Además se registra `desk_dirty` (cambios sin commit en esas rutas al generar). Al fusionar con otros cortes que toquen valuación (p. ej. el 3, de curvas), el aviso aparecerá: es lo correcto y se regenera tras la fusión.
5. **Interpolación idéntica en QuantLib:** `ZeroCurve` lineal en cero continua con `Actual365Fixed`, más un nodo en el día 0 (cero del primer pilar) y otro en el día 36500 (cero del último) para reproducir la extrapolación plana del desk. Con ello R3 debe cumplirse sin declarar diferencias de interpolación.
6. **Volatilidad de las opciones FX:** se valida la fórmula de Garman-Kohlhagen con la σ que usó el desk (leída de su superficie en (K, T) y exportada por caso), no la interpolación de la superficie; se declara en Metodología implícitamente como "mismas volatilidades".
7. **Plazos con días enteros:** QuantLib trabaja con fechas enteras; los casos de batería usan plazos que caen en días enteros (`maturity_years`/`expiry_years = días/365`, bonos con frecuencia `365/días`). Se incluye un solo caso con la frecuencia por omisión del desk (bono semestral de 182.5 días, bond-08) para documentar esa convención como diferencia conocida si excede la tolerancia.
8. **Batería fija:** 62 casos (12/8/10/8/8/8/8), todos dentro del último pilar de su curva; el portafolio de ejemplo son las 7 operaciones de `seed_trades` valuadas con `value_trade` al `as_of` de `MX-DEMO` (sin envejecimiento ni fijaciones, que quedan declarados como no validados).
9. **Intermedios versionados:** `cases.json` y `reference.json` se versionan junto a `report.json` y `known_differences.json` (son pequeños y permiten a un tercero repetir la comparación sin QuantLib).
10. **`expected_rel_diff`** de una diferencia conocida debe reproducir la observada a ±10 % con un procedimiento descrito en `cause`; `max_rel_diff` es la cota con que se clasifica. Así "cuánto explica" es verificable por el test de humo.
11. **Ubicación en la navegación:** "Validación" va al final de la barra lateral (después de Metodología), por la regla de añadir al final de los archivos compartidos. La ruta es `/validacion`.
12. **Enlace desde Metodología:** `<a href="/validacion">` simple (recarga la SPA, que Flask sirve), porque las pruebas de Metodología renderizan sin router y cambiar eso tocaría todas sus pruebas.
13. **Commits:** todos con `GRAPHIFY_SKIP_HOOK=1`, también el último: el grafo se regenera una vez tras fusionar los cortes, para no regenerarlo en paralelo desde varios worktrees.
14. **`make_report.sh`** acepta `BACKEND_PY`/`QL_PY` del entorno (con los de esta máquina por omisión) para poder correrse en otra; y `run_quantlib.py`/`export_cases.py` aceptan `--out` (y `--cases`) para que T4–T6 trabajen en paralelo sin pisar el `reference.json` versionado.

## Anotado por los implementadores

### T1
- Commit `91b622a` (8 rutas). `desk/validation/common.py` exactamente como el Contexto (constantes, rutas, `now_iso`, `desk_commit(root)`, `desk_dirty(root)`, `check_days`, `diffs`, `classify`); `diffs` además devuelve `(None, None)` si `pv_ref` es `inf`/`nan`. `common.desk_commit()` → 40 hex (hoy `91b622a…` tras el commit, porque `export_cases.py` está en `VALUATION_PATHS`).
- `desk/validation/export_cases.py`: `demo_conn() -> sqlite3.Connection`; `export_curves(mkt) -> {curva: {currency, period_days, pillars:[{label,days,df}], checks:[{days,df}]}}` (orden TIIE-F, SOFR, de `market.CURVES`); `build_cases(conn, mkt) -> List[dict]` es el STUB que devuelve `[]` (T2 lo reemplaza); `build(conn=None) -> dict` (claves `generated_at, snapshot{id,as_of,spot}, desk_commit, desk_dirty, hw, curves, cases`; cierra la conexión solo si la creó él); `main(argv=None)` con `--out` (imprime `cases.json: N casos`). `python -m desk.validation.export_cases` desde la raíz del worktree.
- `cases.json` versionado tiene `cases: []`, `desk_commit` = `6c097b0…` y `desk_dirty: true` (se generó antes de commitear): es provisional, T2 lo regenera y T7/T9 definitivos. T3 puede leer `curves[c].pillars/checks` ya.
- Ruta `GET /api/validation/report` en `desk/api/routes/validation.py` (`bp`, prefijo `/api/validation`), registrada en `app.py` en un bloque `# corte 7`. Lee `app.config["VALIDATION_REPORT"]` o `common.REPORT_PATH` (atributo, se resuelve por petición); 404 con el mensaje del contrato y `field: null`; `commit_matches` usa `report.get("desk_commit")`.
- Tests nuevos: `test_validation_route.py` (5) y `test_validation_curves.py` (8). Suite backend completa: 2348 passed (2335 + 13). Grep de `import QuantLib` en `desk/api tests desk/ui/src` vacío.
- Los archivos de UI modificados en el worktree (App.tsx, client.ts, types.ts, Shell*.tsx) son de U1 y no se tocaron ni se incluyeron en el commit.

### U3
- Commit `b64fec6` (2 rutas: `desk/ui/src/screens/MethodologyScreen.tsx`, `MethodologyScreen.test.tsx`).
- `MethodologyScreen.tsx`: bloque `// corte 7` con `const VALIDATION_SECTIONS: Section[]` (una sección `validacion`, 7 ítems: Referencia, Qué se compara, Curvas idénticas, Tolerancias, Diferencias conocidas, Qué no se compara, Reporte) antes de `SectionBlock`; en el JSX, `{/* corte 7 */}` con `<h2 className="meth-group">Validación independiente</h2>` y su `SectionBlock`, justo antes de "Límites de este corte".
- El ítem "Reporte" es JSX con `<a href="/validacion">pantalla Validación</a>` (recarga la SPA, no usa router).
- Tests: bloque `describe('validación contra QuantLib')` con 3 pruebas dentro de `describe('MethodologyScreen')`.
- Sin decisiones nuevas de diseño. U2 no necesita nada de U3; el enlace a `/validacion` depende solo de la ruta que cree U1/T-ruta.

### U1
- Commit `494e766` (8 archivos). `types.ts`, `client.ts`, `App.tsx` y `Shell.tsx` llevan bloques `// corte 7` / `// fin corte 7`; en `client.ts` hay un segundo `import type { ValidationReport } from './types';` justo tras el bloque de imports y `getValidationReport(): Promise<ValidationReport>` (GET `/validation/report`) al final.
- `types.ts` exporta tal cual el contrato: `ValidationProduct`, `ValidationVerdict`, `KnownDifferenceKind`, `ValidationCase`, `ValidationProductSummary`, `ValidationCurveCheck`, `KnownDifference`, `ValidationReport`.
- `App.tsx`: `import ValidationScreen from './screens/ValidationScreen'` (default) y `<Route path="/validacion" …>` tras Metodología. `Shell.tsx`: `NAV_ITEMS` termina en `{to: '/validacion', label: 'Validación'}`; `Shell.test.tsx` renombrado a "las siete pantallas" con 'Validación' al final en ambas listas.
- `ValidationScreen.tsx` es el stub del plan (`<section data-testid="validation-stub"><h1>Validación independiente</h1></section>`); U2 lo reemplaza entero.
- `screens/validationFixture.ts` exporta `VALIDATION_REPORT`: 10 casos (irs-01 portafolio #1 y irs-04; fx_forward-03; fx_option-02; equity_option-01; bond-01 y bond-08 `explained`; cap_floor-02; swaption-01 y -03), 7 productos en `summary` (bond con `explained: 1`), 2 curvas `ok`, 1 diferencia conocida (bond-08, `convention`), `totals {10, 9, 1, 0}`, `commit_matches: true`, `desk_dirty: false`, commits de 40 caracteres. Números coherentes (abs_diff = |pv_desk − pv_ref|, rel_diff = abs_diff/notional); `equity_option` en MXN con notional 100000. Para probar el aviso de commit distinto, U2 hace `{...VALIDATION_REPORT, commit_matches: false}` (o `null`).
- Decisión: en el contrato `cap_floor`/`swaption` tienen tolerancia 5e-4, así que el único `explained` es bond-08 (rel_diff 3.051e-6 > 1e-6).
- vitest sube a 271 en 18 archivos (2 míos en client.test.ts; el resto de U3 en Metodología); `npm run build` limpio.

### U2
- Commit `0a691f7` (3 rutas: `ValidationScreen.tsx` reemplaza el stub, `ValidationScreen.css`, `ValidationScreen.test.tsx`). Lo ya existente de U1 no se tocó; `export default function ValidationScreen()` sin props, llama `getValidationReport()` al montar.
- Estados: cargando (`<p class="vld-dim">`, sin role), 404 → `<p class="vld-empty" role="status">` con "Aún no hay reporte de validación. Genera uno con desk/validation/make_report.sh.", otro `ApiError` o fallo de red → `<p class="vld-error" role="alert">` (mensaje del `ApiError`, o "No se pudo conectar con el backend"). Avisos de commit/dirty: `<p class="vld-warning" role="status">` (solo cuando aplican; sin ellos no hay ningún `role="status"` en la pantalla).
- Tablas con nombre accesible por su `<h2>` (`aria-labelledby`): "Resumen por producto", "Curvas", "Casos" (`getByRole('table', {name})`); filtros `aria-label="Producto"` (valores `all` o la clave del producto) y `aria-label="Veredicto"` (`all|ok|explained|fail`). "Diferencias conocidas" va como `<article class="vld-known">` con `<dl>` (Caso, Producto, Tipo, Convención, Causa, Magnitud), no como tabla. "Cómo reproducir": `<pre>` con `reproduce.command` y `1. paso`…, y dos `<p>` con "Python del backend: …" / "Python de QuantLib: …".
- Formato: `fmtSci` (`toExponential(2)`, `0` → "0", `null` → "—") para diferencias, tolerancias y peor diferencia; `fmtNumber(v, 2)` para nocional y PV; commits a 7 caracteres (`—` si es `null`). Decisión conservadora: la tabla de resumen no muestra `worst_case` (el plan no lo pide) ni la tarjeta de diferencias conocidas el `verdict`.
- El repo no usa `@testing-library/jest-dom` (no hay `toBeInTheDocument`/`toHaveTextContent`): los tests usan `.textContent`/`toBeTruthy`. vitest 287 (271 + 16) en 19 archivos, `npm run build` limpio. NO comprobado: el aspecto real a 1280 px sin desborde horizontal (CSS con `overflow-x: auto` en cada tabla, `.num`, descripción que envuelve) — queda para la captura de T9 con el backend real.

### T3
- Commit `2e012ac` (5 rutas: `run_quantlib.py`, `ql_curves.py`, `ql_rates.py`, `ql_hw.py`, `ql_fx.py`). Los tres `ql_*` de pricers son stubs de 4 líneas (`PRICERS = {}`, `METHODS = {}`): T4/T5/T6 los reemplazan enteros.
- `ql_curves.py`: `INTERPOLATION` (str), `setup(as_of_iso: str) -> ql.Date`, `build_curve(spec: dict, today: ql.Date) -> ql.YieldTermStructureHandle` (ZeroCurve lineal/continuo/Actual365Fixed con nodos día 0, pilares y día `FAR_DAYS`; llama `enableExtrapolation()`), `curve_report(spec, handle, today) -> {"interpolation","pillars":[{days,df_ref}],"checks":[{days,df_ref}]}`. Importa `common` (mismo directorio, por `sys.path`).
- `run_quantlib.py`: `PRICERS`/`METHODS` (fusión de los tres módulos, calculada al importar), `build_context(cases_doc) -> ctx` (`today, curves, spot, hw, currencies` como en el Contexto; `ctx["curves"][c]` es un `YieldTermStructureHandle`), `price_case(case, ctx) -> {"id","pv_ref","error"}` (nunca lanza; un PV no finito → `pv_ref: null`, `error: "QuantLib devolvió un PV no finito"`), `run(cases_doc) -> dict` (documento de reference.json), `main(argv=None)` con `--cases` y `--out`. Código de salida 0 aunque haya errores.
- Para probar un pricer suelto sin tocar el registro: `import run_quantlib as rq; ctx = rq.build_context(json.load(open(cases)))` con `sys.path` apuntando a `desk/validation/`.
- Curvas medidas con cases.json de T1: diferencia máxima en pilares 0.0 y en fechas intermedias 1.1e-16, en TIIE-F y SOFR (R3 sin diferencias de interpolación declaradas). Con los 62 casos de T2 y los stubs: `reference.json: 62 casos, 0 con PV, 62 errores`.
- Suite backend durante T3: 2359 passed, 1 failed ajeno: `test_validation_curves.py::test_build_arma_el_documento_con_cases_vacio_en_este_paso` (T1) espera `cases == []` y T2 (sin commitear aún) ya llena `build_cases`; T2 debe actualizar ese test.

### T2
- Commit `02d9dd3` (4 rutas: `export_cases.py`, `cases.json`, `test_validation_cases.py` nuevo y `test_validation_curves.py`, donde solo cambió el test de T1 que exigía `cases == []`: ahora exige 62). Suite backend: 2360 passed.
- `export_cases.build_cases(conn, mkt) -> List[dict]`: por producto (orden `common.PRODUCTS`) primero las operaciones de `portfolio.load_trades(conn)` de ese producto y luego la batería; ids `"<producto>-NN"`. Tablas privadas `_IRS_BATTERY`, … `_SWAPTION_BATTERY`, `_battery_raw(product)`, `_inputs`, `_notional_currency`, `_label`, `_case`. Importa `PRODUCTS`, `qfpy` (vía `desk.api.qf`), `portfolio`, `valuation`.
- Cada caso: `id, product, source, trade_id, label, params, inputs, currency, notional, pv_desk` (claves exactas del contrato). `params` = salida de `PRODUCTS[p].validate`; en `irs` `fixed_rate` siempre float (par del desk en irs-04/-10; el rótulo lleva "(a la par)"). `bond`: `params.frequency` es float (bond-08 = 2.0 por omisión; bond-01/02 = 365/182). `swaption`/`equity_option`: `expiry_years`/`maturity_years` = días/365.0 (días enteros recuperables con `round(x*365)`).
- `inputs`: irs `{period_days, payment_days}`; fx_forward `{spot, forward}`; fx_option `{spot, vol, forward}`; equity_option `{days}`; bond `{schedule:[{t, amount}]}`; cap_floor `{period_days, hw_a, hw_sigma}`; swaption `{period_days, payments, hw_a, hw_sigma}`. `currency` = la de `pv` (MXN en fx y equity; la de la curva en el resto); `notional` de fx = `notional_usd * spot` (p. ej. 3e6*18.6 = 55800000.00000001, sin redondear).
- `cases.json` regenerado (62 casos): su `desk_commit` es `91b622a` y `desk_dirty: true` (se generó antes de commitear); es provisional, T7/T9 lo regeneran tras commitear.
- HALLAZGO para T5/T7: `swaption-04` (receptora TIIE-F, expira 182 días, swap 1 año, strike 6.50 %) da `pv_desk = 0.0` exacto en el desk. Sondeo: con TIIE-F y expiración <= 182 días el pricer C++ devuelve 0.0 para strikes alejados del ATM (payer 6.0 % y 6.5 % a 91 y 182 días = 0.0 aunque son ITM; payer 7.0 % sí da 62,885 y receiver 7.0 % 221,832; a 270 días payer 6.5 % ya da 187,247). Es muy probable un defecto/límite del Jamshidian en C++ (la raíz r* no se encuentra y devuelve 0); si QuantLib da un PV distinto de 0, el caso queda `fail` y debe ir a `known_differences.json` como `defect` (no se corrige aquí). No es una decisión de diseño mía: la batería queda como el plan la fija.
- Gramática de la plantilla respetada tal cual ("1 periodos", "1 cupones"), sin pluralizar.

### T4
- Commit `<ver git log>` (1 ruta: `desk/validation/ql_rates.py`). `PRICERS = {"irs": price_irs, "bond": price_bond}`, `METHODS = {"irs": …, "bond": …}` (español, con las piezas de QuantLib), firma `price_irs(case, ctx) -> float` y `price_bond(case, ctx) -> float`; helper privado `_schedule(today, offsets) -> ql.Schedule` (`[today] + [today + d]`, NullCalendar, Unadjusted).
- `irs`: `OvernightIndex("Fondeo-<curva>", 0, ctx currency, NullCalendar, Actual360, handle)` + `OvernightIndexedSwap(..., telescopicValueDates=True)` + `DiscountingSwapEngine(handle)`; `Payer` = paga fija, mismo signo que el desk. `bond`: `FixedRateBond(0, face, schedule, [coupon], Actual365Fixed, Unadjusted, 100.0, Date(), NullCalendar)` (hay que pasar `Unadjusted` y `NullCalendar` explícitos: el `Following` por omisión con calendario vacío falla) + `DiscountingBondEngine`; fechas `today + round(i·365/frequency)` con el `round` de Python (mitades al par).
- Resultado medido (`|pv_desk − pv_ref| / notional`): los 12 `irs` entre 3e-17 y 6e-15; bond-01..07 ≤ 1.5e-15; **bond-08 = 5.94e-8, o sea DENTRO de la tolerancia 1e-6 (veredicto `ok`)**. No hay ningún caso `irs`/`bond` fuera de tolerancia ni defecto del desk: T7 no necesita entrada en `known_differences.json` para estos productos (el plan suponía 3.1e-6 para bond-08; no se cumple porque dos efectos casi se cancelan).
- Descomposición de bond-08 (reproducible con los DF del desk, `handle.discount(t)` para el desk en t = i/2 y `handle.discount(today + d)` para QuantLib; script en `/tmp/fableorchestrate/qf-corte7/t4_bond08.py`, `$QLPY` desde la raíz): días de pago QuantLib 182, 365, 548, 730, 912, 1095 (periodos de 182/183 días). Efecto solo de las fechas de descuento (cupones del desk 3.75e6 fijos): +3.235e-6 · efecto solo de los cupones ACT/365 con días reales: −3.149e-6 · neto +5.94e-8 (coincide con la diferencia observada). Con redondeo "mitades arriba" (183, 365, 548, 730, 913, 1095): neto −2.35e-7; con floor: +1.85e-7: bond-08 queda dentro de 1e-6 con cualquier redondeo, así que la elección no cambia el veredicto.
- Consecuencia para T7/T9: con el reporte real, `totals.explained` será 0 salvo que T5/T6 destapen algo (p. ej. swaption-04 con `pv_desk = 0.0`); el fixture de U1 (bond-08 `explained`) es solo de prueba y no coincide con el reporte real. Si T7 quiere conservar bond-08 como diferencia conocida de convención, `cause` debe decir que las dos partes son ±3.2e-6 y el neto 5.9e-8 (no 3.1e-6), pero con rel ≤ tolerancia el caso sale `ok` y la entrada no se usa: lo conservador es no inventarla.
- Suite backend: 2360 passed (sin QuantLib en `desk/api`, `tests`, `desk/ui/src`). `desk/validation/ql_hw.py` aparecía modificado en el worktree (T5 a medias): no se tocó ni se incluyó en mi commit.

### T5
- Commit `83a2ccd` (solo `desk/validation/ql_hw.py`). Deja `METHODS = {"cap_floor", "swaption"}` (español) y `PRICERS = {"cap_floor": price_cap_floor, "swaption": price_swaption}`, ambos `(case, ctx) -> float` en la moneda de la curva. Helpers privados `_dates`, `_schedule`, `_index`. Usa `inputs.hw_a/hw_sigma` (no `ctx["hw"]`). Salida de prueba: `/tmp/fableorchestrate/qf-corte7/ref-T5.json`.
- cap_floor (8): todos ≤ 2.8e-16 del nocional. Peor `cap_floor-02` = 2.791e-16 (`cap_floor-04` 1.95e-16, `-03` 1.81e-16). Sin diferencia de modelo: misma fórmula (opción sobre ZCB de Hull-White con σ_p y t = días/365) y el primer caplet intrínseco coincide con la fijación de hoy de QuantLib; el residuo es redondeo de coma flotante (orden de suma/exp/log). No va a `known_differences.json`.
- swaption (8): 7 de 8 dentro de 5e-4 (1e-8 a 2.6e-7), pero NINGUNA es redondeo: es un defecto del desk en C++ (`src/instruments/swaption.cpp`, `Swaption::price`, Jamshidian). El desk toma `P_HW(T_exp,T_i|r) = F_i·exp(−B_i·r)` con `F_i = P(0,T_i)/P(0,T_exp)` y omite del `A(T_exp,T_i)` de Hull-White el factor `exp(B_i·f(0,T_exp) − σ²/(4a)·B_i²·(1−e^{−2a·T_exp}))`, que su propio comentario sí lista. El término de `f(0,T_exp)` solo desplaza `r*` (queda expresada como desviación respecto de la tasa, ≈ 0 en vez de ≈ f0); el de σ² no se absorbe y mueve los strikes `X_i` de los ZCB.
- Procedimiento reproducible (réplica en Python con los DF del desk y bisección; script `/tmp/fableorchestrate/qf-corte7/T5-swaption-repro.py`, correr con el Python del backend desde la raíz del worktree): (a) réplica de la fórmula del desk reproduce `pv_desk` a ≤ 4e-11 del nocional; (b) la misma réplica con el `A` completo reproduce QuantLib a ≤ 3e-9 (casi todos ≤ 3e-11). Diferencia esperada = |a − b|/nocional vs observada |desk − QuantLib|/nocional: swaption-01 2.961e-9 vs 2.984e-9; -02 2.961e-9 vs 2.921e-9; -03 1.953e-7 vs 1.924e-7; -04 1.843e-3 vs 1.843e-3; -05 4.780e-8 vs 4.778e-8; -06 2.963e-8 vs 2.966e-8; -07 1.044e-8 vs 1.045e-8; -08 2.638e-7 vs 2.638e-7 (todas dentro de ±1.5 %). Peor dentro de tolerancia: swaption-08 (2.638e-7; payer SOFR 5y×5y, el mayor `B²·(1−e^{−2aT})`).
- `swaption-04` (receptora TIIE-F, expira 182 días, strike 6.50 %): `pv_desk = 0.0`, QuantLib 92,158.63; observada 1.843e-3 > 5e-4 → `fail` salvo que T7 lo registre como `kind: "defect"` (abierto, vive en C++; reportar a Fable). Causa: el bracket de la bisección `[f0 − 10·σ_r, f0 + 10·σ_r]` está centrado en f0, pero por la omisión anterior la raíz del desk está en coordenadas de desviación (≈ 0, no ≈ f0); con expiración corta `σ_r` es pequeño (≈ 0.007 a 182 días), el borde inferior queda ≈ −0.0015 y la raíz cae debajo: `swapNPV(lo) < 0` → `return 0.0` ("deep OTM", mal clasificado; la opción vale ~0.18 % del nocional). Réplica con el mismo bracket da 0.0 exacto; ensanchando el bracket a [−1, 1] da 92,158.638 (a 7.5e-11 de QuantLib). Magnitud esperada = |0 − 92,158.634|/50e6 = 1.843e-3. Mismo mecanismo explica el hallazgo de T2 (payer 6.0 %/6.5 % a 91 y 182 días = 0.0). Sugerencia para T7: `max_rel_diff` ≈ 2.0e-3 para swaption-04; para los otros siete, si se registran, `kind: "defect"` con la omisión de `A` (o `convention` solo si se decide tratarlo como convención, que no lo es).

### T6
- Commit `201e5cd` (1 ruta: `desk/validation/ql_fx.py`). `PRICERS = {"fx_forward": price_fx_forward, "fx_option": price_fx_option, "equity_option": price_equity_option}` y `METHODS` con los mismos tres productos (español, con las piezas de QuantLib); firmas `price_*(case, ctx) -> float`; helpers privados `_sign(side)` y `_flat_vol(today, vol)`.
- `fx_forward`: `ql.FxForward(notional_usd, USD, MXN, strike, today+days, paySourceCurrency=(side=="sell"), 0, NullCalendar)` + `DiscountingFxForwardEngine(SOFR, TIIE-F, spot=18.6 MXN por USD)`. El PV en MXN es `npvTargetCurrency()` (`NPV()` viene en USD, la moneda origen). El pricer lanza `ValueError` si `float(fairForwardRate())` difiere de `inputs.forward` en más de 1e-10 relativo: en QuantLib 1.44 `fairForwardRate()` devuelve un float (no un objeto con `.rate()`), y con spot sin invertir coincide exacto con el forward del desk en los 8 casos.
- `fx_option`: `GarmanKohlagenProcess(spot, SOFR foránea, TIIE-F doméstica, BlackConstantVol(inputs.vol, Actual365Fixed))` + `AnalyticEuropeanEngine`; `PV = ±notional_usd·NPV()`. Usa la σ que el desk leyó de su superficie (supuesto 6): se valida la fórmula, no la interpolación de la superficie. `equity_option`: `BlackScholesMertonProcess` con `FlatForward` (Actual365Fixed, continuo), vencimiento `today + inputs.days`; `PV = quantity·NPV()`.
- Resultado medido (`|pv_desk − pv_ref| / notional`, `reference.json` con los 62 casos: 62 con PV, 0 errores): fx_forward 5.9e-17 a 3.1e-16 (tol 1e-8); fx_option 3.1e-18 a 1.1e-16 (tol 1e-6); equity_option 0 a 1.1e-16 (tol 1e-6). Los 26 casos están dentro de tolerancia por 9 o más órdenes de magnitud: no hay diferencia conocida ni defecto del desk en estos tres productos, T7 no necesita entradas en `known_differences.json` para ellos.
- Sin huecos de diseño: `settlementDays=0` y `NullCalendar` para que el pago caiga exactamente en `hoy + días` (la alternativa por omisión, 2 días de rezago, desplazaría el vencimiento). Suite backend: 2360 passed; sin `import QuantLib` en `desk/api`, `tests` ni `desk/ui/src`.

### T7
- Commits `cccdf47` (compare.py, make_report.sh, known_differences.json, README.md) y `a695888` (cases.json, reference.json, report.json regenerados con el código ya commiteado: `desk_commit` = `02d9dd3`, `desk_dirty` false; el reporte solo difiere del anterior en `generated_at`). Nada de `desk/api/` ni C++ tocado.
- `compare.py`: `compare(cases_doc, reference_doc, known_doc) -> dict` (forma de `report.json`; lanza `ValueError` si `known_differences.json` nombra un caso inexistente o si los días de pilares/checks no coinciden entre `cases.json` y `reference.json`), `main()` (escribe `REPORT_PATH`, imprime `report.json: N casos · W dentro · E explicadas · F fuera`, sale 1 si `F>0` o alguna curva no `ok`). `within` = veredictos `ok`; `explained` aparte. `curves` sigue el orden de `cases.json` (TIIE-F, SOFR). `make_report.sh` ejecutable, acepta `BACKEND_PY`/`QL_PY`.
- Resultado real: 62 casos · 61 dentro · 1 explicada · 0 fuera; curvas `ok` (pilares 0.0, intermedias 1.1e-16). Peor por producto: irs 6.0e-15, fx_forward 3.1e-16, fx_option 1.1e-16, equity_option 1.1e-16, bond 5.9e-8 (bond-08, dentro de 1e-6, sin entrada), cap_floor 2.8e-16, swaption 1.84e-3 (swaption-04).
- `known_differences.json` tiene UNA entrada: `swaption-04`, `kind: "defect"`, `expected_rel_diff` 1.843e-3 (observada 1.8432e-3), `max_rel_diff` 2.0e-3; la `cause` describe el procedimiento (réplica Jamshidian con los DF de cases.json, bracket del desk -> 0.0; con A completo y bisección en [-1, 1] -> 92,158.63). DEFECTO ABIERTO EN C++ para Fable: `src/instruments/swaption.cpp` (`Swaption::price`) omite del A(T_exp,T_i) el factor exp(B·f0 - sigma²/(4a)·B²·(1-e^{-2aT})) y el bracket `[f0 ± 10·rStd]` deja la raíz fuera con expiraciones cortas (devuelve 0.0 "deep OTM"); afecta también a payer 6.0 %/6.5 % TIIE-F a 91 y 182 días. No hay entrada para las otras 7 swaptions (3e-9 a 2.6e-7, dentro de 5e-4) ni para bond-08.
- Para T8: `known_differences.json` -> `known["differences"]`; la fila de `report["known_differences"]` trae `observed_rel_diff` = rel_diff del caso y `verdict` = el del caso (`explained`); `totals.explained == 1`. Para T9: el fixture de U1 (bond-08 explained) NO coincide con el reporte real (el real explicado es swaption-04, tipo `defect`, mostrará "Defecto abierto"). README menciona `desk/api/tests/test_validation_report.py` (nombre de T8). Verificado con el cliente de pruebas de Flask: `GET /api/validation/report` -> 200, `commit_matches: true`. Suite backend: 2360 passed.

### T8
- Commit `dc99a0e` (1 ruta: `desk/api/tests/test_validation_report.py`, nuevo). Nada más tocado; QuantLib no se importa.
- `_problems(report: dict, known: dict) -> List[str]` (privada, solo usa `common`): recalcula `abs_diff`/`rel_diff` con `common.diffs` y el veredicto con `common.classify` (con la entrada de `known` del caso), compara con `math.isclose(rel_tol=1e-9, abs_tol=1e-15)` (None vs None cuenta como igual), y verifica cuenta mínima y por producto, ids únicos, `tolerance == TOLERANCES`, ningún `fail`, `totals`, `summary` (conteos, tolerancia, `worst_rel_diff`/`worst_abs_diff`/`worst_case`), curvas (`ok` y diferencias contra `PILLAR_TOLERANCE`/`CHECK_TOLERANCE` de `common`, no las guardadas) y diferencias conocidas (caso existente, `kind`, `cause` >= 40, `convention` no vacía, `expected_rel_diff` a ±10 % de lo observado).
- Decisión (interpretación de "la entrada de known == guardado"): además de reclasificar con `known`, exige que `report["known_differences"]` tenga exactamente los `case_id` de `known["differences"]` y que `kind/convention/cause/expected_rel_diff/max_rel_diff` coincidan, y que `observed_rel_diff`/`verdict` de cada fila cuadren con el caso. `known` se lee de `common.KNOWN_PATH` (ausente = `{"differences": []}`). No se comprueba `report["tolerances"]` (el plan no lo pide; cada caso ya se compara con `common.TOLERANCES`).
- Tests (5): `test_el_reporte_existe`, `test_el_reporte_versionado_no_tiene_problemas` (el mensaje lista los problemas), `test_un_pv_alterado_a_mano_falla`, `test_un_caso_fuera_sin_explicacion_falla` (usa el primer caso `ok`), `test_una_explicacion_sin_caso_falla`. Leen `common.REPORT_PATH`/`KNOWN_PATH` por petición; para T9: tras regenerar `report.json` basta correr este archivo para confirmar coherencia.
- Verificado: archivo 5 passed; alterar `pv_desk` de irs-01 en `report.json` lo hace fallar (1 failed) y, restaurado desde el respaldo, vuelve a 5 passed con `git diff --quiet` limpio; 12 mutaciones ad hoc (totals, summary, worst, tolerancia, id repetido, curva, pocos casos, cause corta, expected lejano, kind, known vacío) las detecta `_problems`. Suite backend completa: 2365 passed (2360 + 5).

### T9
- Commit `ce01c28` (1 ruta: `desk/ui/src/screens/ValidationScreen.css`). Única corrección: a 1280 px la tabla "Casos" medía 1079 px dentro de una tarjeta de 996 px y `overflow-x: auto` ocultaba parte de la columna Veredicto ("Dentro d…"). Se quitó `white-space: nowrap` de `.vld-verdict` y `.vld-table td.vld-wrap` bajó `min-width` de 220px a 160px; ahora `tableW == wrapW == 996` y ningún contenedor desborda (CDP, puerto 9347, `scrollWidth` 1280 en `/validacion` y `/metodologia`). Las etiquetas de veredicto no cambiaron.
- Suites finales: backend 2365 passed; bindings `unittest discover` 56 tests OK (imprime `qfpy loaded from: <fake-qfpy>`, es de la suite existente); vitest 287 en 19 archivos; `npm run build` limpio. C++: `git diff --stat ce51edf -- src include tests/*.cpp CMakeLists.txt` vacío; grep de `import QuantLib` en `desk/api tests desk/ui/src` vacío; sin `test_*.py` en `desk/validation/`.
- R1: `make_report.sh` → código 0, `62 casos · 61 dentro · 1 explicadas · 0 fuera`; el diff contra lo versionado fue solo `generated_at` (3 líneas), así que se restauraron los tres JSON con `git checkout --` y NO se commiteó ruido de marcas de tiempo. R5: con `pv_desk` de irs-01 alterado `test_validation_report.py` da 1 failed (totals y summary no cuadran); restaurado, 5 passed y `git diff --quiet` limpio.
- API real en 5087: `commit_matches: true` (`02d9dd3`, `desk_dirty` false), `totals {62, 61 dentro, 1 explicada, 0 fuera}`, 7 productos, curvas ok. Con `desk_commit` = 40 ceros la pantalla muestra el aviso de commit distinto. Capturas en `/tmp/fableorchestrate/qf-corte7/shots/` (`validacion-1280x800.png`, `validacion-1280x4000.png`, `validacion-1280x7000.png`, `metodologia-1280x8000.png`, `validacion-commit-distinto-1280x800.png` más recortes `crop-*.png`); respuestas en `.../it/`.
- Pendiente cosmético NO corregido (no pedido): en "Curvas" el nombre "TIIE-F" parte la línea tras el guion ("TIIE-" / "F"). El fixture de U1 (bond-08 explained) no coincide con el reporte real (swaption-04, tipo `defect`, se muestra "Defecto abierto"); es solo de prueba.
- Defecto abierto en C++ que Fable debe tratar fuera de este corte: `src/instruments/swaption.cpp` (`Swaption::price`), ver `known_differences.json` y T5/T7.

### Correcciones
Tras la auditoría independiente (`audit.md`). Cuatro commits sobre `ce01c28`: `c5b822c`, `f4a4fbe`, `78e098d`, `37153d8`. Suites finales: backend 2373 passed, bindings 56 OK, vitest 287 en 19 archivos, `npm run build` limpio; C++ no aplica (`git diff --stat ce51edf -- src include tests/*.cpp CMakeLists.txt` vacío).

- **Corregido (baja): la prueba de humo no cruzaba `report.json` con `cases.json`/`reference.json`** (`c5b822c`, `desk/api/tests/test_validation_report.py`). Nueva `_source_problems(report, cases_doc, reference_doc)`: compara con su fuente `desk_commit`/`desk_dirty`/`snapshot`/`reference` y, por caso, `product`, `label`, `source`, `trade_id`, `currency`, `notional`, `pv_desk` (de `cases.json`) y `pv_ref`/`error` (de `reference.json`), y recalcula `pillar_max_abs_diff`/`check_max_abs_diff` desde los DF de ambas fuentes. 5 tests nuevos (el reporte versionado coincide; `swaption-01` con `pv_desk` +1e-5 del nocional y `abs_diff`/`rel_diff` recalculados a mano: `_problems == []` pero el cruce falla —es justo el escenario de la auditoría—; `pv_ref` editado; curva editada; `desk_commit` de otro commit). Comprobado a mano sobre `report.json`: la edición de `swaption-01` ahora hace fallar la suite; restaurado con `cp`, `git diff --quiet` limpio.
- **Corregido (baja): pluralización de rótulos** (`78e098d`, `export_cases.py`). Helper `_count(n, singular, plural)`: «1 periodo», «1 cupón», «swap de 1 año» (irs-06, irs-09, bond-03, swaption-04); el resto sigue en plural. `test_validation_cases.py`: `LABEL_WORD` pasa a expresiones regulares (`periodos? de`, `cup(ón|ones) cada`, …) y un test nuevo fija los rótulos con cantidad 1 y descarta `1 periodos|cupones|años` en los 62.
- **Corregido (baja): paso 2 de «Cómo reproducir»** (`78e098d`, `compare.py`, `validationFixture.ts`). `STEPS` ahora es `python -m desk.validation.export_cases  # con el Python del backend`, `python desk/validation/run_quantlib.py  # con el Python de QuantLib`, `python -m desk.validation.compare  # con el Python del backend`. Test nuevo `test_validation_compare.py` (los pasos son comandos completos con su intérprete; el reporte versionado trae los mismos `STEPS`, test añadido con los JSON en `37153d8`).
- **Corregido (baja): `test_desk_commit_es_un_sha_de_40_hex_en_este_worktree` dependía de git** (`f4a4fbe`, `test_validation_curves.py`): `skipif` si no hay `git` o no hay `.git` (decisión conservadora: `desk_commit()` devuelve `None` por diseño sin git, y la ruta contesta `commit_matches: null`). Verificado en una copia sin `.git`: 7 passed, 1 skipped (la copia se borró).
- **Datos regenerados** (`37153d8`): `make_report.sh` de punta a punta con el código ya commiteado (`desk_dirty: false`, `desk_commit` `78e098d` = `common.desk_commit()`); los PV no cambian (62 · 61 dentro · 1 explicada · 0 fuera); solo cambian `generated_at`, `desk_commit`, los 4 rótulos y los pasos. Comprobado contra el backend real en 5087 (apagado después): `commit_matches: true`.

**No corregido**
- **Media: `swaption-04` (PV 0.0 del desk vs 92,158.63 de QuantLib) sigue abierto.** Vive en C++ (`src/instruments/swaption.cpp`, `Swaption::price`) y este worktree no puede compilar ni correr ctest; sin recompilar, `build/src/qfpy*.so` no cambia, así que un cambio en el fuente no se podría probar ni se reflejaría en el reporte. Sigue como `kind: "defect"` en `known_differences.json`. Propuesta para el corte que sí compile: (a) en `swapNPV` y en `X_i` usar `A(T_exp,T_i)` completo, `F_i·exp(B_i·f0 − σ²/(4a)·B_i²·(1−e^{−2a·T_exp}))`, y (b) centrar el bracket de la bisección en 0 o ensancharlo (la réplica de T5 con `[-1, 1]` da 92,158.638, a 7.5e-11 de QuantLib), en vez de `[f0 ± 10·rStd]`; con (a) también desaparecen las diferencias de 3e-9 a 2.6e-7 de las otras siete swaptions. Test C++ sugerido: receptora TIIE-F, expira 182 días, strike 6.50 %, swap de 1 año, ≈ 92,158.63. Después, borrar la entrada de `known_differences.json` y regenerar el reporte.
- **Baja: el enlace de Metodología a Validación sigue siendo `<a href="/validacion">`.** Cambiarlo a `Link` exige `Router` y los ~14 `render(<MethodologyScreen />)` de su test no lo tienen (supuesto 12 del plan); tocarlos choca con los cortes que editan `MethodologyScreen.tsx`/su test en paralelo. Funciona por el fallback de SPA del backend; solo recarga la página.
- **Cosmético heredado de T9 (no está en la auditoría): «TIIE-F» parte la línea en la tabla «Curvas».** No se tocó (CSS sin test útil y fuera de lo marcado).
- **Informativa:** al fusionar con cortes que toquen `VALUATION_PATHS` la pantalla avisará de commit distinto hasta regenerar el reporte; es lo diseñado.
