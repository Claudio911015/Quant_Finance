# Plan — corte 10: no touch y double no touch USDMXN (QuantLib)

Diseño: `/tmp/fableorchestrate/qf-fxexoticos/design.md`. Requisitos `R1..R10` de ahí.

## Contexto

### Rutas y reglas
- Worktree: `/home/claudio/Git/qf-wt/fxexoticos` (rama `fx-exoticos`). **No tocar** `/home/claudio/Git/Quant_Finance` (otro corte en curso), el puerto 5070, Brave/9222, `~/Git/MarketDataFeed`, `graphify-out/`, `docs/`. Sin C++, sin ctest.
- Python del backend: `/home/claudio/anaconda3/bin/python` (3.8.18, numpy 1.24.3). Nada de `match` ni `X | Y`. `qfpy` ya compilado en `build/src/qfpy.cpython-38-x86_64-linux-gnu.so`.
- Commits en español con el porqué, sin `Co-Authored-By` ni trailers, rutas explícitas, sin push, sin `git stash`:
  `GRAPHIFY_SKIP_HOOK=1 git commit -m "…" -- <rutas>`
- Suites: `cd /home/claudio/Git/qf-wt/fxexoticos && /home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q` · `cd desk/ui && npm test && npm run build`.
- Regla nueva del corte: la matemática vive en QuantLib (o `qfpy`), nunca en Python propio. Única excepción declarada abajo (puente browniano del corredor).

### Cómo está hecho un pricer hoy (`desk/api/pricing/fx.py`)
- `Product = namedtuple("Product", "name validate price pv_mxn describe")` en `desk/api/pricing/base.py`.
- `validate(params) -> dict` normalizado con helpers de `desk/api/validation.py`: `number(d, name, gt=, ge=, le=, required=, default=)`, `integer(d, name, ge=, le=)`, `choice(d, name, options, default=None)`; cotas `MAX_AMOUNT=1e13`, `MAX_PRICE=1e6` (validation.py) y `MAX_DAYS=18250` (base.py). Errores: `raise ApiError(400, "<mensaje en español>", "<field>")` (`desk/api/errors.py`) → cuerpo `{"error", "field"}`.
- `price(params, mkt) -> dict` con la forma **real** del contrato (no existen claves `result`/`chart`/`inputs`; donde R1/R2 los nombran, léase este contrato — decisión P2):
  `{"product", "currency": "MXN", "pv", "pv_mxn", "risk": {..floats..}, "cashflows": None, "details": {...}}`. La ruta `desk/api/routes/price.py` hace `PRODUCTS[product].validate(body sin snapshot)`, `load_context(...)` y `jsonify(ensure_finite(...))` (todo número debe ser finito).
- Contexto de mercado `mkt` (`desk/api/market.py`, `MarketContext`): `mkt.as_of` (date), `mkt.spot` (float, 18.60 en MX-DEMO, as_of 2026-11-10), `mkt.curves[name]` (`qfpy.YieldCurve`: `.maturities()` en años, `.discount_factor(t)`), curva MXN = `getattr(mkt, "mxn_discount", "TIIE-F")` (como `_domestic` de fx.py), USD = `mkt.curves["SOFR"]`; `mkt.surface` (`qfpy.VolSurface`): `.to_grid()` → `(maturities_años[4], strikes[8], vols[expiry][strike])`, `.vol(strike, T)`. La superficie **siempre** existe en el contexto (`_build_context` exige `data["vol_surface"]`).
- Registro backend: `desk/api/pricing/__init__.py` → `PRODUCTS = {**rates.PRODUCTS, **fx.PRODUCTS, **xccy.PRODUCTS}` y `PRODUCT_LABEL`. **Ojo:** `PRODUCTS` también lo usan `portfolio.create_trade` (acepta cualquier clave), `valuation`, `lifecycle`, `migrate`, `events`; registrar ahí haría los exóticos agregables al portafolio (fuera de alcance). **Decisión P1:** los exóticos **no** entran en `PRODUCTS`; `fx_exotics.PRODUCTS` (dict `{name: Product(name, validate, price, None, None)}`) solo lo consulta la ruta de precios: en `desk/api/routes/price.py` se usa `PRICERS = {**PRODUCTS, **fx_exotics.PRODUCTS}` en lugar de `PRODUCTS` (definido en `desk/api/pricing/__init__.py` junto a `PRODUCTS`). `PRODUCT_LABEL` sí recibe los dos rótulos.
- Registro UI: `desk/ui/src/api/types.ts` (`ProductId` unión), `desk/ui/src/screens/pricers/registry.ts` (`PRODUCT_SPECS: Record<ProductId, ProductSpec>`), `products/<id>.ts` con `spec: ProductSpec = {product, title, fields: FieldSpec[], chart: 'cashflows'|'payoff'|'none'}` (`FieldSpec`: `name,label,kind('number'|'int'|'percent'|'select'|'text'),default,options?,optional?,help?`). La gráfica de payoff hoy la **calcula la UI** desde `params` (`PricerChart.tsx: payoffFor`, serie `PayoffSeries = {strike, spots, pnl}`); `PricerForm.tsx: ResultView` muestra `pv`, `pv_mxn`, tabla `risk` con `RISK_LABELS` (`delta`, `vega` ya tienen rótulo) y el panel «Agregar al portafolio» para todo producto.
- Pruebas guardia que enumeran productos: `desk/api/tests/test_errors.py` (`SPECS`, `MAGNITUDE_CAPS`, `set(SPECS) == set(PRODUCTS)` y URLs `/api/price/<p>` de `PRODUCTS`), `desk/api/tests/test_live_market.py` (`PRICER_CASES == set(PRODUCTS)`), `desk/ui/src/components/Shell.test.tsx` (`toHaveLength(8)` y «ocho pricers»). Como los exóticos no entran a `PRODUCTS`, las del backend **no cambian**; se añaden casos equivalentes en el archivo de pruebas nuevo. La de UI pasa a 10 / «diez» (justificada: dos pricers nuevos en `PRODUCT_SPECS`).

### Contrato de respuesta (decisiones P2 y P5)
```
{"product": "fx_no_touch"|"fx_double_no_touch", "currency": "MXN",
 "pv": ±, "pv_mxn": ±,                       # ± = signo de side (sell = −buy)
 "risk": {"delta": ±, "vega": ±},            # delta = (V(1.01·S) − V(S)) / (0.01·S); vega = V(σ+0.01) − V(σ)
 "cashflows": None,
 "details": {"price_pct", "no_touch_probability", "std_error", "paths", "model", "method",
             "analytic_flat_pv", "smile_adjustment",
             "chart": {"strike": null, "barriers": [B] | [L, U], "spots": [...21], "pnl": [...21]}}}
```
`price_pct = 100·|pv|/payout`, `no_touch_probability = precio_sin_signo / (payout · df_MXN(T))`, `std_error` en MXN (0 si analytic), `paths` = PATHS (0 si analytic), `analytic_flat_pv` siempre (signado), `smile_adjustment = pv − analytic_flat_pv` con `model=smile` y 0 con `flat`. Delta unilateral (+1 % de spot) y vega (+0.01 a toda la superficie antes de Dupire, o a la vol plana), misma semilla. Vol plana = `mkt.surface.vol(spot, T)` de `qfpy`. `method=analytic`: `pv` del motor analítico, `paths = 0`, `std_error = 0`, griegas por reprecio analítico. `pnl` = valor signado (MXN) en cada spot; la UI marca cada elemento de `barriers` con una línea vertical. Gráfica: 21 spots equiespaciados en el lado vivo (no touch arriba: `[0.85·B, B)`, abajo: `(B, 1.15·B]`; double: `(L, U)`), cada punto = solo precio (sin griegas) con `CHART_PATHS` trayectorias y la misma semilla.

### Constantes del módulo (por omisión)
`PATHS = 20000`, `STEPS = 10`, `SEED = 42`, `CHART_POINTS = 21`, `CHART_PATHS = 2000`, `LV_STRIKES = 41` (malla de strikes de la tabla de volatilidad local: `spot·exp(linspace(−5, 5, 41)·σ·√T)`), choques `SPOT_BUMP = 0.01`, `VOL_BUMP = 0.01`. Rendimiento medido con estas constantes (abajo).

### Traducción del mercado a QuantLib (medida con QuantLib 1.42.1)
```python
import QuantLib as ql, numpy as np
today = ql.Date(as_of.day, as_of.month, as_of.year); ql.Settings.instance().evaluationDate = today
dc = ql.Actual365Fixed()
def curve(c):  # qfpy.YieldCurve -> handle; pilares en años, día 0 con df 1
    ts = [0.0] + list(c.maturities())
    return ql.YieldTermStructureHandle(ql.DiscountCurve([today + int(round(t*365)) for t in ts], [c.discount_factor(t) for t in ts], dc))
dom, fgn = curve(mkt.curves[mxn]), curve(mkt.curves["SOFR"])
Tg, Kg, Vg = mkt.surface.to_grid()
surf = ql.BlackVarianceSurface(today, ql.NullCalendar(), [today + int(round(t*365)) for t in Tg], Kg,
                               ql.Matrix([[Vg[j][i] + dvol for j in range(len(Tg))] for i in range(len(Kg))]), dc,
                               ql.BlackVarianceSurface.ConstantExtrapolation, ql.BlackVarianceSurface.ConstantExtrapolation)
surf.setInterpolation("bicubic"); surf.enableExtrapolation()
sigma = mkt.surface.vol(spot, T) + dvol        # vol plana = superficie en (spot, vencimiento)
q = ql.QuoteHandle(ql.SimpleQuote(spot))
# flat:
proc = ql.GarmanKohlagenProcess(q, fgn, dom, ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, ql.NullCalendar(), sigma, dc)))
# smile: volatilidad local de Dupire por QuantLib, tabulada en la malla del MC (ver por qué abajo)
h = ql.BlackVolTermStructureHandle(surf)
lv = ql.NoExceptLocalVolSurface(h, dom, fgn, q, sigma)       # Dupire; donde la varianza local sale negativa usa sigma
times = [T*i/STEPS for i in range(STEPS)]; times[0] = 1e-3*T/STEPS
ks = list(spot*np.exp(np.linspace(-5, 5, LV_STRIKES)*sigma*np.sqrt(T)))
tab = np.array([[lv.localVol(t, k, True) for t in times] for k in ks])   # numpy: la reusa el puente
proc = ql.GeneralizedBlackScholesProcess(q, fgn, dom, h, ql.LocalVolTermStructureHandle(ql.FixedLocalVolSurface(today, times, ks, ql.Matrix(tab.tolist()), dc)))
```
Hallazgos que fijan esta forma (todas medidas):
- Interpolación **por omisión (bilineal)** de `BlackVarianceSurface` da volatilidad local basura (0.026 / 0.115 / 0.003 alternando entre strikes); **`bicubic`** da 0.125–0.15, coherente.
- Con extrapolación por omisión `LocalVolSurface` lanza «decreasing variance» lejos de la malla; con `ConstantExtrapolation` lanza «negative local vol^2» solo justo en los strikes extremos (17.0 y 20.5; 400 de 20 200 puntos de una malla de prueba). `NoExceptLocalVolSurface` lo absorbe.
- Dupire **al vuelo** (proceso con `LocalVolSurface`/`NoExcept…`) cuesta ~5 µs por llamada en C++: el no touch con 20 000×5 pasos tarda **1.1 s por cada 2 patas** (≈4 s con griegas) → incumple R6. Tabulado en `FixedLocalVolSurface` (41×10 llamadas, 1–5 ms) el mismo MC baja a **0.07 s por 2 patas** (≈15×). Diferencia de precio tabla vs. al vuelo: ≤ 0.003 a 30–182 días y ~0.008 a 730 días con 10 pasos (converge al subir pasos).
- Con superficie plana la volatilidad local es la plana → `smile` reproduce `flat` (R4).
- Decisión P6: esta tabulación cuenta como delegada a QuantLib; se declara con un comentario de una línea en el módulo y en Metodología (incluida la sustitución por la vol plana donde la varianza local sale negativa y la diferencia ~0.3–0.8 % frente a Dupire al vuelo).
- Decisión P4: no hay 400 por snapshot sin superficie (`_build_context` ya la exige); se declara en Metodología.

### Motor de Monte Carlo único (decisión P3: enfoque (3) para los dos productos)
Un solo motor: trayectorias de `ql.GaussianPathGenerator` + supervivencia por puente browniano en `numpy`. **No se usa `MCBarrierEngine`** (además no acepta pago en efectivo: `non-plain payoff given`). El no touch es el mismo motor con una barrera (`[B]`), el double no touch con dos (`[L, U]`): mismas trayectorias, así R5(d) es exacta trayectoria a trayectoria (comprobado: `dnt <= nt_arriba` y `dnt <= nt_abajo` en las 20 000).
```python
rsg = ql.GaussianRandomSequenceGenerator(ql.UniformRandomSequenceGenerator(STEPS, ql.UniformRandomGenerator(SEED)))
pg = ql.GaussianPathGenerator(proc, T, STEPS, rsg, False)
X = np.array([list(pg.next().value()) for _ in range(n)])      # (n, STEPS+1); copiar: el Path es un búfer reutilizado
sig = np.full((n, STEPS), sigma) if tab is None else np.column_stack([np.interp(X[:, i], ks, tab[:, i]) for i in range(STEPS)])
s2, p, alive = sig**2 * T / STEPS, 1.0, True
for b in barriers:                                               # [B] o [L, U]
    lb = np.log(X / b)
    # puente browniano: P(cruzar b entre nodos) = exp(-2·ln(X_i/b)·ln(X_{i+1}/b)/(σ²Δt)) (Beaglehole-Dybvig-Zhou / Glasserman §6.4); única matemática propia
    p, alive = p - np.exp(-2 * lb[:, :-1] * lb[:, 1:] / s2), alive & (lb * lb[:, :1] > 0).all(axis=1)
v = alive * np.clip(p, 0, 1).prod(axis=1) * dom.discount(T)     # valor por unidad de pago, por trayectoria
unit, se = v.mean(), v.std(ddof=1) / n**0.5
```
- `sigma` = vol plana; con `smile`, `ks`/`tab` son la malla de strikes y la tabla `LV_STRIKES × STEPS` (como `numpy`) con la que se construyó `FixedLocalVolSurface`: `np.interp` en el nodo devuelve el mismo valor que usó QuantLib al evolucionar (interpolación lineal en strike, extrapolación constante).
- Formular cada barrera por separado (en vez de `ln(X/L)`, `ln(U/X)` con `L=0`/`U=∞`) evita divisiones por cero y avisos de `numpy`; `alive` exige que ningún nodo cruce (el spot ya se validó en el lado vivo).
- Para dos barreras la suma de las dos probabilidades es la aproximación de primer orden de la serie de imágenes; medida suficiente (abajo).
- Sin vectorización posible desde Python: el bucle por trayectoria cuesta 0.30 s por juego (20 000×10); `StochasticProcessArray` + `GaussianMultiPathGenerator` en lotes no mejora (0.29 s). Sobol (`GaussianSobolPathGenerator`) cuesta igual y se descarta (sin error estándar honesto).
- Delta y vega: se regeneran las trayectorias con la misma semilla sobre el proceso con spot ×1.01 y con vol +0.01 (en `smile`, +0.01 a toda la superficie antes de Dupire) → 3 juegos por precio.
- Vigilancia discreta (sin el factor del puente) sobrevalúa 25–37 errores estándar; con el puente el resultado no depende de la malla (5 vs 20 pasos, abajo).

Analíticos de referencia (R3, `analytic_flat_pv`, `method=analytic`), siempre con el proceso plano:
```python
# no touch: ejercicio AMERICANO con pago al vencimiento; strike B del lado vivo = no touch puro (con spot fuera devuelve 0)
bt, typ = (ql.Barrier.UpOut, ql.Option.Put) if up else (ql.Barrier.DownOut, ql.Option.Call)
o = ql.BarrierOption(bt, B, 0.0, ql.CashOrNothingPayoff(typ, B, 1.0), ql.AmericanExercise(today, today + days, True))
o.setPricingEngine(ql.AnalyticBinaryBarrierEngine(proc))
# double no touch: ejercicio EUROPEO (con americano lanza "non-European exercise given")
o = ql.DoubleBarrierOption(ql.DoubleBarrier.KnockOut, L, U, 0.0, ql.CashOrNothingPayoff(ql.Option.Call, L, 1.0), ql.EuropeanExercise(today + days))
o.setPricingEngine(ql.AnalyticDoubleBarrierBinaryEngine(proc))
```

Validación medida del motor único (plano, 20 000 trayectorias, 10 pasos salvo que se diga):
- No touch, 12 casos (7–730 días, arriba y abajo, barreras cerca y lejos): |z| ≤ 1.12 frente a `AnalyticBinaryBarrierEngine`.
- Double no touch, 13 casos (7–730 días, corredores de 0.6 a 11 pesos): |z| ≤ 1.35 frente a `AnalyticDoubleBarrierBinaryEngine` con 5 y con 20 pasos; corredor (10, 40) da exactamente `df` (error 0 ⇒ R5(c)).
- Error estándar ≤ 0.32 % del pago en todos los casos (R6 pide ≤ 0.5 %).

### Tiempos medidos (esta máquina, prototipo sin Flask; `load_context` = 2.5 ms; una petición `fx_option` = 5 ms)
Precio por omisión = 3 juegos de trayectorias (base, delta, vega) + analítico; gráfica = 21 spots × 2 000 trayectorias × 1 juego.

| producto | modelo | plazo | precio (s) | gráfica (s) |
|---|---|---|---|---|
| no touch o double no touch | flat | 30–730 d | 0.98 | 0.65 |
| no touch o double no touch | smile | 30–730 d | 1.03–1.06 | 0.75–0.77 |

(El costo es el bucle de trayectorias, igual para una o dos barreras.) R6 se cumple: peor caso 1.06 s el precio y 1.83 s con gráfica; los límites de prueba (3×) son 4.5 s y 15 s. Con Dupire al vuelo, en lugar de la tabla, el precio pasaría de ~4 s (por eso la tabla, P6).

### Instalación de QuantLib (R10)
`/home/claudio/anaconda3/bin/python -m pip install "QuantLib==1.42.1"` (rueda manylinux cp38 disponible; probada en `/tmp/qlprobe-lib`). Hoy **no** está instalado en ese Python.

## Tareas

### T1 — Dependencia QuantLib (modelo: haiku)
- **Objetivo:** QuantLib disponible y declarado (R10, parte de dependencia).
- **Archivos:** `desk/README.md`, `desk/run.sh`.
- **Pasos:**
  1. `/home/claudio/anaconda3/bin/python -m pip install "QuantLib==1.42.1"`.
  2. `desk/README.md`: en «Requisitos» añadir `- QuantLib 1.42.1 para Python (pricers de exóticos FX).`; en «Instalación» añadir la línea `/home/claudio/anaconda3/bin/python -m pip install "QuantLib==1.42.1"`.
  3. `desk/run.sh`: antes de `# 1. Binding C++ qfpy`, añadir:
     ```bash
     if ! "$PY" -c "import QuantLib" 2>/dev/null; then
       echo "[run.sh] falta QuantLib en $PY: $PY -m pip install \"QuantLib==1.42.1\"" >&2
       exit 1
     fi
     ```
  4. `GRAPHIFY_SKIP_HOOK=1 git commit -m "build(desk): QuantLib 1.42.1 como dependencia del backend, porque los exóticos FX se valúan con sus motores en vez de matemática propia" -- desk/README.md desk/run.sh`.
- **Verificación:** `/home/claudio/anaconda3/bin/python -c "import QuantLib as ql; print(ql.__version__)"` → `1.42.1`; `QF_PYTHON=/usr/bin/false bash desk/run.sh; echo $?` → `[run.sh] falta QuantLib…` y `1`.
- **R:** R10 (dependencia). **Depende de:** —.

### T2 — Backend: `fx_exotics.py`, registro de precios y pruebas (modelo: sonnet)
- **Objetivo:** los dos pricers con el motor único, analíticos, griegas, gráfica y validación del Contexto; pruebas primero.
- **Archivos:** nuevo `desk/api/pricing/fx_exotics.py`; `desk/api/pricing/__init__.py` (`PRICERS` y dos entradas en `PRODUCT_LABEL`: `"fx_no_touch": "No touch USDMXN"`, `"fx_double_no_touch": "Double no touch USDMXN"`); `desk/api/routes/price.py` (`PRODUCTS` → `PRICERS`, 3 usos); nuevo `desk/api/tests/test_price_fx_exotics.py`.
- **Pasos:**
  1. Pruebas en `test_price_fx_exotics.py`. Fixture `ctx` como en `test_price_fx.py` (`app` crea la base; `market.load_context(db.connect(tmp_path / "t.db"), "MX-DEMO")`). Contexto con superficie plana: `market._build_context("FLAT", "2026-11-10", data)` con el `data` de MX-DEMO (leer la fila de `snapshots`) y todas las vols = 0.12. Llamar `fx_exotics.PRODUCTS[name].validate/price` directamente, y por HTTP (`client.post("/api/price/<p>", json=…)`) para los 400 y el contrato.
     - R1: 400 con `field` para barrera ya tocada (arriba con spot ≥ B y abajo con spot ≤ B → `barrier`; spot fuera de (L, U) → `lower` o `upper`, el del lado tocado), `lower ≥ upper` (`upper`), `analytic` con `smile` (`method`), `payout_mxn` ≤ 0 o > `MAX_AMOUNT`, `days` fuera de [1, `MAX_DAYS`], `barrier`/`lower`/`upper` ≤ 0 o > `MAX_PRICE`, `barrier_type`/`model`/`method`/`side` fuera de opciones. Producto desconocido sigue en 404. `POST /api/trades` con `product: "fx_no_touch"` → 400 (no entra al portafolio). Respuesta 200 con las claves exactas del contrato y todo finito.
     - R3: ≥ 12 casos por producto con `model=flat` (no touch: los 12 del Contexto; double: los 13), `|pv − analytic_flat_pv| ≤ 3·std_error + 1e-9·payout`; mallas: el mismo caso con `monkeypatch.setattr(fx_exotics, "STEPS", 40)` vs. 10 dentro de `3·√(se₁² + se₂²)`.
     - R4: superficie plana, `smile` vs `flat` dentro de `3·√(se₁² + se₂²)`; MX-DEMO `smile` finito, `0 ≤ pv ≤ payout·df` y `smile_adjustment ≠ 0`.
     - R5: (a) `0 ≤ pv ≤ payout·df`; (b) con la misma semilla, alejar la barrera o ensanchar el corredor no baja el valor; (c) barrera 1e6 arriba, barrera 0.01 abajo y corredor (0.01, 1e6) → `|pv − payout·df| ≤ 1e-6·payout·df`; (d) **exacta**: `pv(DNT L,U) ≤ pv(NT abajo L)` y `≤ pv(NT arriba U)` sin tolerancia (mismas trayectorias); (e) `sell` = −`buy` en `pv`, `delta`, `vega`, `analytic_flat_pv`; (f) dos llamadas iguales → respuestas idénticas.
     - R6: tiempo de la función interna de resultado sin gráfica (paso 2) con valores por omisión ≤ 4.5 s y la petición HTTP completa ≤ 15 s (3× los objetivos), para los dos productos con `smile`; `std_error ≤ 0.005·payout` en los casos de R3.
  2. `fx_exotics.py` (≤ 180 líneas sin blancos ni docstrings; sin clases): constantes del Contexto; validación (un helper de campos comunes `side, payout_mxn, days, model` (por omisión `smile`), `method` (por omisión `mc`) + barreras de cada producto); una función que arma `(dom, proc, sigma, ks, tab)` desde `mkt`, `spot` y `dvol` (Contexto, «Traducción del mercado»); el motor único `(proc, sigma, ks, tab, barriers, T, n) -> (unit, se)`; el analítico por producto; una función de resultado (precio + delta + vega + analítico → dict del contrato sin `chart`) y `price` = resultado + `details["chart"]`. La barrera tocada se valida en `price` (necesita `mkt.spot`). Fijar `ql.Settings.instance().evaluationDate` en cada llamada. Comentarios de una línea: el puente (única matemática propia, con referencia) y la tabulación de la vol local.
  3. `PRICERS` en `__init__.py` y uso en la ruta; las pruebas guardia existentes no se tocan.
  4. Commit con porqué, rutas explícitas.
- **Verificación:** `cd /home/claudio/Git/qf-wt/fxexoticos && /home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q` → todo verde, el conteo previo + las nuevas. R7: `/home/claudio/anaconda3/bin/python -c "import ast,io,tokenize,sys; src=open('desk/api/pricing/fx_exotics.py').read(); doc={n.body[0].lineno for n in ast.walk(ast.parse(src)) if isinstance(n,(ast.Module,ast.FunctionDef)) and ast.get_docstring(n)}; print(sum(1 for i,l in enumerate(src.splitlines(),1) if l.strip() and i not in doc))"` ≤ 180 (docstrings de una línea; si hay multilínea, descontarlas).
- **R:** R1–R7. **Depende de:** T1.

### T3 — Interfaz: especificaciones, registro, resultado y gráfica (modelo: sonnet)
- **Objetivo:** los dos pricers en Pricers y en Ctrl+K reusando `PricerForm`/`PricerChart` sin componentes nuevos (R8).
- **Archivos:** `desk/ui/src/api/types.ts`, nuevos `desk/ui/src/screens/pricers/products/fx_no_touch.ts` y `fx_double_no_touch.ts`, `registry.ts`, `PricerChart.tsx`, `PricerForm.tsx`, `PricerChart.test.ts`, `PricerForm.test.tsx`, `desk/ui/src/components/Shell.test.tsx`.
- **Pasos:**
  1. `ProductId` += `'fx_no_touch' | 'fx_double_no_touch'`. Specs (`chart: 'payoff'`; títulos exactos «No touch USDMXN», «Double no touch USDMXN»): `side` (Compra/Venta, `buy`), `payout_mxn` («Pago (MXN)», 1000000), `days` («Días al vencimiento», 91), `model` (`smile` «Con sonrisa (vol local)» / `flat` «Plano», por omisión `smile`), `method` (`mc` «Monte Carlo» / `analytic` «Analítico (solo plano)», por omisión `mc`); no touch: `barrier` («Barrera», 19.5, help «MXN por USD.»), `barrier_type` (`up` «Arriba» / `down` «Abajo»); double: `lower` («Barrera inferior», 17.5), `upper` («Barrera superior», 19.8). Alta en `registry.ts`.
  2. `PricerChart.tsx`: `ChartData` payoff acepta `series?: PayoffSeries & { barriers?: number[] }`; `payoffFor` la usa tal cual si viene; la marca dibuja una línea vertical por cada `barriers` (si no hay, la de `strike` como hoy); `payoffText` con «Valor contra spot», eje «Spot (MXN por USD)», serie «Valor», marca «Barrera».
  3. `PricerForm.tsx`: `ResultView` pasa `response.details.chart` como `series`; junto al PV muestra `± <std_error>` cuando `std_error > 0`; filas de datos con un mapa de rótulos tipo `RISK_LABELS` para `no_touch_probability` («Probabilidad de no tocar», %), `price_pct` («Precio (% del pago)»), `analytic_flat_pv` («Referencia analítica (plano)»), `smile_adjustment` («Ajuste por sonrisa»), `paths` («Trayectorias»), `model`, `method`; el formulario «Agregar al portafolio» no se muestra para estos dos productos (lista `NOT_TRADABLE` con los dos ids).
  4. `Shell.test.tsx`: `toHaveLength(10)` y «diez pricers». Pruebas vitest: serie del backend usada sin recalcular, dos líneas de barrera en el double, error estándar visible, panel de portafolio ausente. Commit.
- **Verificación:** `cd /home/claudio/Git/qf-wt/fxexoticos/desk/ui && npm test && npm run build` → verde.
- **R:** R8. **Depende de:** el contrato del Contexto (puede ir en paralelo a T2; la integración real es T5).

### T4 — Metodología (modelo: haiku)
- **Objetivo:** sección «Exóticos de FX» (R9).
- **Archivos:** `desk/ui/src/screens/MethodologyScreen.tsx` (una entrada nueva al final de `PRODUCT_SECTIONS`, `id: 'fx-exoticos'`, `title: 'Exóticos de FX'`).
- **Pasos:** ítems `{label, text}`: «Qué paga» (no touch: monto fijo en MXN al vencimiento si el USDMXN nunca toca la barrera; double no touch: si nunca sale del corredor); «Barrera» (americana, vigilada de forma continua toda la vida: entre nodos de la malla se usa la probabilidad de cruce del puente browniano); «Modelos» (plano = vol de la superficie en spot y vencimiento; con sonrisa = volatilidad local de Dupire calculada por QuantLib desde la superficie del snapshot (bicúbica, extrapolación constante), tabulada en la malla del Monte Carlo; donde la varianza local sale negativa se usa la vol plana; diferencia frente a Dupire al vuelo del orden de 0.3–0.8 % del pago); «Cálculo» (QuantLib 1.42: trayectorias de `GaussianPathGenerator`; referencia analítica con `AnalyticBinaryBarrierEngine` y `AnalyticDoubleBarrierBinaryEngine`; la fórmula del puente es la única matemática propia); «Error de Monte Carlo» (20 000 trayectorias, 10 pasos, semilla fija 42: resultados reproducibles; error estándar en MXN; delta (+1 % de spot) y vega (+1 punto de vol) por reprecio con la misma semilla); «Límites» (pago solo en MXN; volatilidad local, no estocástica ni vanna-volga; superficie sintética; sin rebate ni one touch; no se registran como operaciones del portafolio; el snapshot siempre trae superficie, no hay caso «sin superficie»). Commit.
- **Verificación:** `cd /home/claudio/Git/qf-wt/fxexoticos/desk/ui && npm test && npm run build` → verde.
- **R:** R9. **Depende de:** —.

### T5 — Integración contra backend real y capturas (modelo: sonnet)
- **Objetivo:** demostrar R1–R10 de punta a punta.
- **Archivos:** ninguno del repo (fallos → se devuelven a T2/T3); capturas en `/tmp/fableorchestrate/qf-fxexoticos/shots/`.
- **Pasos:**
  1. Suites: `cd /home/claudio/Git/qf-wt/fxexoticos && /home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q` y `cd desk/ui && npm test && npm run build`. La única prueba previa que cambia es `Shell.test.tsx` (8 → 10).
  2. Backend en 5084 con base temporal (no 5070): `cd /home/claudio/Git/qf-wt/fxexoticos && D=$(mktemp -d) && /home/claudio/anaconda3/bin/python -c "from desk.api.app import create_app; create_app(db_path='$D/desk.db').run(port=5084)" &` (sirve `desk/ui/dist`).
  3. `curl -s -w '%{time_total}' -X POST localhost:5084/api/price/fx_no_touch -H 'Content-Type: application/json' -d '{"snapshot":"MX-DEMO","side":"buy","payout_mxn":1000000,"days":91,"barrier":19.5,"barrier_type":"up"}'` y equivalentes (double; `flat`/`smile`; `mc`/`analytic`); tiempo total ≤ 5 s; los 400 de R1 con su `field`; `POST /api/trades` con un exótico → 400.
  4. Chrome headless en 9344: `google-chrome --headless=new --remote-debugging-port=9344 --user-data-dir=$(mktemp -d) --window-size=1280,900 http://localhost:5084` (si no hay `google-chrome`, `chromium`). Por CDP: abrir Pricers → cada exótico, «Valuar» con valores por omisión, capturar `fx_no_touch.png`, `fx_double_no_touch.png` y `metodologia.png`; comprobar `document.documentElement.scrollWidth <= 1280`, consola sin errores, Ctrl+K lista los dos rótulos y no aparece «Agregar al portafolio» en los exóticos.
  5. Conteo R7 (comando de T2) y lista de funciones propias de `fx_exotics.py` con la pieza de QuantLib que la sustituiría (insumo del auditor).
  6. Apagar servidor y Chrome; borrar la base temporal.
- **Verificación:** suites verdes, 200/400 esperados, 3 capturas, `scrollWidth ≤ 1280`, consola vacía.
- **R:** R6, R8, R10 (más comprobación de R1–R9). **Depende de:** T1–T4.

### T6 — Capítulo 15 «Exóticos de FX» en el libro LaTeX (modelo: sonnet)
- **Objetivo:** documentar el corte en `docs/tex/capitulos/` (excepción explícita del coordinador a «sin `docs/`», solo para esta ruta).
- **Archivos:** nuevo `docs/tex/capitulos/15-exoticos-fx.tex` (o el nombre que pida `docs/tex/README.md`) y la línea de inclusión que indique ese README.
- **Pasos:**
  1. `cd /home/claudio/Git/qf-wt/fxexoticos && git merge feat/qf-desk` (sin `--no-verify`; si hay conflicto fuera de `docs/tex`, abortar con `git merge --abort` y reportar). Si tras el merge no existen `docs/tex/capitulos/_plantilla.tex` y `docs/tex/README.md`, **reportar BLOQUEADO** y no escribir nada.
  2. Leer `docs/tex/README.md` y `_plantilla.tex`; escribir el capítulo siguiendo su estructura y convenciones: productos y pago, barrera continua y puente browniano (fórmula y referencia), modelos plano y de volatilidad local (Dupire de QuantLib, tabulación y sustitución en varianza negativa), motor único de Monte Carlo y referencias analíticas, error estándar, semilla y griegas, validación (R3–R5 con las cifras medidas de este plan: |z| ≤ 1.12 y ≤ 1.35, se ≤ 0.32 %, tiempos ~1.0 s), límites y fuera de alcance del diseño.
  3. Compilar con el comando que indique el README (si no indica, `latexmk -pdf` en `docs/tex`) y comprobar que no hay errores.
  4. `GRAPHIFY_SKIP_HOOK=1 git commit -m "docs(tex): capítulo 15 de exóticos FX, porque …" -- <rutas del capítulo y la inclusión>`.
- **Verificación:** compilación del libro sin errores y el capítulo 15 presente en el índice del PDF; o salida «BLOQUEADO: falta el esqueleto docs/tex en feat/qf-desk».
- **R:** — (documentación pedida por el coordinador; complementa R9). **Depende de:** T5.

| tarea | modelo | depende de | R | archivos |
|---|---|---|---|---|
| T1 | haiku | — | R10 | `desk/README.md`, `desk/run.sh` |
| T2 | sonnet | T1 | R1–R7 | `desk/api/pricing/fx_exotics.py` (nuevo), `desk/api/pricing/__init__.py`, `desk/api/routes/price.py`, `desk/api/tests/test_price_fx_exotics.py` (nuevo) |
| T3 | sonnet | contrato del Contexto | R8 | `ui/src/api/types.ts`, `products/fx_no_touch.ts`, `products/fx_double_no_touch.ts`, `registry.ts`, `PricerChart.tsx`, `PricerForm.tsx`, `PricerChart.test.ts`, `PricerForm.test.tsx`, `components/Shell.test.tsx` |
| T4 | haiku | — | R9 | `ui/src/screens/MethodologyScreen.tsx` |
| T5 | sonnet | T1–T4 | R6, R8, R10 (+ comprobación R1–R9) | ninguno (capturas en `/tmp/fableorchestrate/qf-fxexoticos/shots/`) |
| T6 | sonnet | T5 | — (docs) | `docs/tex/capitulos/15-…tex` + inclusión según `docs/tex/README.md` |

### T4 (nota del implementador)
- Añadida entrada `fx-exoticos` («Exóticos de FX») al final de `PRODUCT_SECTIONS` en `desk/ui/src/screens/MethodologyScreen.tsx`. Forma: `{id, title, items: {label, text}[]}` (sin cambios de tipo ni de exports). Seis ítems: «Qué paga», «Barrera», «Modelos», «Cálculo», «Error de Monte Carlo», «Límites», con el texto del plan.
- Commit `cc6f42b` (solo ese archivo).
- Desviación de verificación: en vez de `npm test && npm run build`, se usó lo indicado por el encargo: `npx vitest run src/screens/MethodologyScreen.test.tsx` (34/34 verdes) y `npx tsc --noEmit -p .` (exit 0).
- No se añadió ni modificó test (la tarea no lo pide).

### T3 — nota del implementador (UI)
Commit `304510d` en `fx-exoticos`. Partida de `npm test` antes de empezar: 42 archivos, 634 pruebas verdes; después: 42 archivos, 645 verdes (+7 en `PricerForm.test.tsx`, +4 en `PricerChart.test.ts`, `Shell.test.tsx` 8→10 / «diez pricers»); `npm run build` verde.
Formas reales que deja la UI y que T5 debe encontrar en el backend:
- Lee `response.details.chart` como `PayoffSeries` (`{strike, barriers?, spots, pnl}`; `strike` llega `null` y la UI no lo usa si hay `barriers`), `details.std_error` (se muestra «± MXN x (error estándar)» solo si `> 0`) y, si existen, `price_pct`, `no_touch_probability` (fracción 0–1, se muestra ×100 %), `analytic_flat_pv`, `smile_adjustment`, `paths`, `model` (`flat` → «Plano», lo demás «Con sonrisa (vol local)»), `method` (`analytic` → «Analítico», lo demás «Monte Carlo») en un bloque «Detalle del cálculo». `risk.delta` y `risk.vega` usan los rótulos que ya existían.
- Petición enviada (claves, en el orden del formulario): `side, barrier, barrier_type, payout_mxn, days, model, method, snapshot` (no touch) y `side, lower, upper, payout_mxn, days, model, method, snapshot` (double). Por omisión: `buy`, 19.5 `up` / 17.5–19.8, 1000000, 91, `smile`, `mc`.
- Desviaciones menores: (1) `barriers?: number[]` se añadió a la propia interfaz `PayoffSeries` (no `PayoffSeries & {…}`) y `ChartData.series?: PayoffSeries`; (2) `buildOption` pasó a `export` para probar las líneas de barrera sin echarts; (3) el eje x de la gráfica ahora abarca `min/max` de spots ∪ marcas (idéntico para los demás productos), porque la barrera cae en el borde de la zona viva y una marca fuera del eje podía no dibujarse; (4) los campos comunes de los dos productos viven en `exoticFields(barriers)` exportada desde `products/fx_no_touch.ts` y reusada por `fx_double_no_touch.ts`; (5) `help: 'MXN por USD.'` solo en `barrier`. No se pudo comprobar el dibujo real de la gráfica (jsdom no mide); queda para las capturas de T5.

### T1 (nota del implementador)
- QuantLib 1.42.1 instalado en `/home/claudio/anaconda3/bin/python` (3.8.18) con `pip install "QuantLib==1.42.1"`. Dry-run previo: solo instalaba QuantLib, sin tocar numpy (1.24.3) ni otros paquetes.
- Verificado: `import QuantLib` → `1.42.1 1.24.3`; `QF_PYTHON=/usr/bin/false bash desk/run.sh` → mensaje `[run.sh] falta QuantLib…` y exit 1; `bash -n desk/run.sh` OK; `import desk.api.app` OK.
- Commit `e9e13c5` (solo `desk/README.md` y `desk/run.sh`).
- Desviación: la suite `pytest desk/api/tests -q` no terminó en 100 s, así que no está comprobada completa.
- `pip check` muestra conflictos preexistentes de spyder-kernels/tables (no relacionados con QuantLib, que no tiene dependencias).

### T2 (nota del implementador)
Commit `d33f3de` (rama `fx-exoticos`): `desk/api/pricing/fx_exotics.py` (nuevo), `desk/api/pricing/__init__.py`, `desk/api/routes/price.py`, `desk/api/tests/test_price_fx_exotics.py` (nuevo, 111 pruebas). `pytest desk/api/tests -q` → 3617 passed (3506 previas + 111), 286 s. R7: 130 líneas (fórmula del plan: sin blancos ni docstrings; 127 sin las 3 de comentario completo).
Firmas y formas reales:
- `PRODUCTS = {"fx_no_touch": Product(name, _nt_validate, _price, None, None), "fx_double_no_touch": ...}`. `validate` devuelve `{side, payout_mxn, days, model, method, product, barrier, barrier_type}` (no touch) o `{..., product, lower, upper}` (double). `_price(p, mkt)` = `_result(p, mkt)` + `details["chart"]`; `_result(p, mkt)` (sin nombre: el producto va en `p["product"]`) es la función que mide la prueba de R6. Internas: `_build(p, mkt, spot, dvol) -> (dom, proc, sigma, ks, tab)`, `_mc(proc, sigma, ks, tab, bars, T, n) -> (prob_sin_descontar, se_prob)`, `_analytic(p, proc)`, `_value(p, mkt, spot, dvol, n) -> (pv_signado, se_MXN, prob)`.
- Respuesta: exactamente el contrato del Contexto (`risk = {delta, vega}`; `details = {price_pct, no_touch_probability, std_error, paths, model, method, analytic_flat_pv, smile_adjustment, chart}`; `chart = {strike: None, barriers, spots[21], pnl[21]}`); `std_error` y `price_pct` sin signo; `smile_adjustment = 0.0` con `model=flat`.
- `PRICERS = ChainMap(PRODUCTS, fx_exotics.PRODUCTS)` (vista VIVA, no `{**PRODUCTS, **…}`): `test_finite_guard.py` parchea `PRODUCTS["fx_forward"]` con `monkeypatch.setitem` y espera que la ruta lo vea; la fusión en un dict nuevo rompía `test_la_guarda_central…[price-nan]`.
Desviaciones y hallazgos:
1. Curvas con `enableExtrapolation()` (el fragmento del plan no lo traía): los pilares llegan a 9.97 años y `MAX_DAYS` es 50; con `days=18250` QuantLib lanzaba «time (50) is past max curve time». Prueba `test_longest_valid_maturity_is_priced`.
2. La curva de descuento MXN pone un pilar en día 0 con df 1.0 literal (`discount_factor(0)` de qfpy lanza «maturity must be positive»).
3. **La referencia analítica del double no touch no converge con corredores muy anchos**: `AnalyticDoubleBarrierBinaryEngine` lanza «serie did not converge sufficiently fast» p. ej. con (10, 40) a 7 días, (1, 100) a 91 días, (15, 26) a 1–2 días y (0.01, 1e6) a cualquier plazo. Como `analytic_flat_pv` se calcula siempre, esa petición responde 400 «No se pudo valuar: serie did not converge…» (manejador genérico de `RuntimeError`), no 500. Por eso R5(c) se prueba con el corredor (5, 80) a 91 días en vez de (0.01, 1e6) (el no touch sí se prueba con 1e6 y 0.01); `test_extreme_corridor_is_a_clean_400` documenta el límite. Sugerencia para T4/Metodología «Límites»: corredores de varios cientos de por ciento de ancho no se valúan.
4. La gráfica usa los 21 puntos INTERIORES del lado vivo (`(0.85·B, B)`, `(B, 1.15·B)`, `(L, U)`), no `[0.85·B, B)`.
5. Los «12/13 casos del Contexto» no estaban enumerados; usé 12 de no touch y 13 de double (7–730 días, arriba/abajo, cerca/lejos, corredores 0.6–11): máx |z| = 1.14, máx se = 0.327 % del pago. Mallas 10 vs 40 pasos en 4 casos. Tiempos medidos: `_result` 1.03–1.20 s, petición completa 1.7–2.1 s (R6: 1.5 s / 5 s).

### T5 (nota del implementador)
Commit `9b8ba0d` (rama `fx-exoticos`; `fx_exotics.py`, `test_price_fx_exotics.py`, `PricerForm.tsx`, `PricerForm.test.tsx`): corrección del hallazgo 4 de T2, decidida por Fable.
- Backend: `_analytic` captura `RuntimeError` de `o.NPV()` y lanza `ApiError(400, "La fórmula cerrada no converge con este corredor; use Monte Carlo", _sides(p)[0][0])` (`field` = `barrier` en no touch, `lower` en double). `_result` envuelve la referencia en `try/except ApiError` → `ref = None`; con `method=mc` quedan `analytic_flat_pv = None` y `smile_adjustment = None` (también con `model=flat`) y el precio de Monte Carlo sale normal. Con `method=analytic` la primera llamada de `_value` ya falla → 400 (la referencia nunca se llega a calcular). Las claves del contrato no cambian.
- UI: la fila de «Detalle del cálculo» muestra «—» si el valor es `null` (antes `Number(null)` = `MXN 0.00`).
- Pruebas: `test_extreme_corridor_is_a_clean_400` reemplazada por `test_corridor_where_the_analytic_series_fails_is_still_priced_by_mc[flat|smile]` (200, `analytic_flat_pv`/`smile_adjustment` null, prob = 1, `paths` > 0) y `test_analytic_method_where_the_series_fails_is_a_400_in_spanish` (cuerpo exacto con `field: "lower"`); R5(c) vuelve al corredor original `(0.01, 1e6)` del plan (T2 lo había bajado a `(5, 80)`); vitest nuevo «sin referencia analítica … muestra «—»». Rojo antes (5 fallos backend, 1 vitest), verde después.
- Suites: backend `3619 passed` (3617 + 2 netas), 328 s; UI `646 passed` (645 + 1), `npm run build` verde.
- R7: 136 líneas con el comando del plan (130 antes de la corrección; +6).
- Integración real (servidor 5084 con base temporal, Chrome 137 headless en 9344; todo apagado y borrado al terminar):
  - Tiempos por HTTP (3 repeticiones, petición completa con gráfica): no touch smile/mc 1.99–2.11 s, flat/mc 1.97–2.05 s, analítico 0.01 s; double smile/mc 2.26–2.33 s, flat/mc 2.10–2.30 s, analítico 0.01 s. `_result` sin gráfica (5 corridas en proceso): 0.99–1.25 s (no touch) y 1.08–1.23 s (double); con gráfica 1.7–2.2 s. R6 (≤ 1.5 s y ≤ 5 s): cumple.
  - 400 de R1 con su `field` y mensaje en español: barrera ya tocada (`barrier`/`lower`/`upper`), `lower ≥ upper` (`upper`), analítico con sonrisa (`method`), `payout_mxn` 0 y > MAX, `days` 0 y > MAX, `barrier` ≤ 0 y > MAX_PRICE, `barrier_type`/`model`/`method`/`side` fuera de opciones, corredor ancho analítico (`lower`); producto desconocido 404; `POST /api/trades` con `fx_no_touch`/`fx_double_no_touch` → 400 `field: product`. Log completo: `t5_api_checks.txt`.
  - Capturas en `shots/` (1280 px, `scrollWidth = 1280`, sin desbordes, consola vacía en el recorrido de éxito; solo los 400 deliberados dejan `Failed to load resource … 400` en la consola de red): ver insumos y cifras en la respuesta del implementador y en `t5_shots_log.txt`.
- Observaciones sin corregir (fuera de la tarea): (1) Metodología «Límites» no menciona que con corredores muy anchos la referencia analítica no converge (se muestra «—»; el método analítico responde 400). (2) La gráfica usa los 21 puntos interiores: la curva termina cerca de la barrera, no en ella (≈ 74 000 MXN a 19.37 con barrera 19.5), y la barrera cae pegada al borde del eje. (3) Con el corredor (0.01, 1e6) la gráfica abarca spots hasta 1e6 (degenerada pero correcta). (4) Los mensajes de barrera tocada citan el nombre crudo del campo (`'barrier'`), igual que el estilo de validación existente; la paleta Ctrl+K muestra el id (`fx_no_touch`) a la derecha como en los demás pricers.
- Funciones propias de `fx_exotics.py` y qué las sustituiría (insumo del auditor): `_common`, `_nt_validate`, `_dnt_validate`: validación en frontera con los helpers del repo, sin pieza de QuantLib (no es matemática). `_sides`: geometría de barreras (lado vivo/campo), sin equivalente. `_build` (+ `curve`): adaptador qfpy → `ql.DiscountCurve`, `ql.BlackConstantVol`, `ql.BlackVarianceSurface` (bicúbica), `ql.NoExceptLocalVolSurface` (Dupire), `ql.FixedLocalVolSurface`; lo propio es traducir pilares y el bucle que tabula `localVol` en la malla (QuantLib no lee `qfpy`; el bucle sustituye a un Dupire al vuelo que es 15× más lento). `_mc`: trayectorias de `ql.GaussianPathGenerator`; el factor de puente browniano y la supervivencia son lo único de matemática propia: `ql.MCBarrierEngine` falla con pago en efectivo («non-plain payoff given», verificado) y no hay Monte Carlo de doble barrera en QuantLib 1.42.1 (`MCBarrierEngine`, `MCLDBarrierEngine`, `MCPRBarrierEngine` son de una barrera). `_analytic`: solo arma `BarrierOption`/`DoubleBarrierOption` y llama `AnalyticBinaryBarrierEngine`/`AnalyticDoubleBarrierBinaryEngine`. `_value`, `_result`, `_price`: pegamento y forma de la respuesta; delta y vega por reprecio con la misma semilla porque los motores analíticos de barrera binaria no dan griegas (`delta not provided`, verificado) y el Monte Carlo propio tampoco.

### correcciones-auditoria
Commit `6545548` (rama `fx-exoticos`; `fx_exotics.py`, `test_price_fx_exotics.py`, `MethodologyScreen.tsx/.test.tsx`, `PricerForm.tsx/.test.tsx`, `products/fx_no_touch.ts`, `desk/validation/ql_curves.py` solo el docstring). Pruebas primero: 21 pruebas nuevas/ajustadas en rojo antes de tocar el backend, todas verdes después.
- **D1**: `_build.curve` ahora arma `{"pillars": [{days, df}]}` con `mkt.pillars[c]` y los DF del desk y llama `desk.validation.ql_curves.build_curve` (ZeroCurve lineal en cero continuo, Actual/365, plana fuera de pilares; se importa, no se reescribe). Pruebas: DF QuantLib vs desk a ≤ 1e-9 en pilares, entre pilares, día 1 y 30 años para MXN y USD; R5(c) a 1e-6 relativo (`mc` y `analytic`, 91/182/3650 días) y `rel=1e-6` en la prueba previa que estaba en 1e-4. Efecto en precios: |Δpv| ≤ 1.5e-3 relativo (ruido de MC por otra deriva), referencia analítica ≤ 1.5e-4. Desviación: `ql_curves.py` hace `sys.path.insert(0, desk/validation)` al importarse y `import common` (copia top-level de `desk.validation.common`, que `routes/validation.py` ya importa); actualicé su docstring («el backend nunca importa este módulo» ya no era cierto).
- **D4**: `smile_adjustment` fuera del backend, de `DETAIL_LABELS` y de las pruebas (la prueba de contrato exige el conjunto exacto de `details`). Metodología → «Modelos»: «El efecto de la sonrisa se lee comparando el valor (± error estándar) con la referencia analítica plana.»
- **D3 (medido, no se suben los pasos)**: reprecio de vainillas con `smile`, 200 000–300 000 trayectorias con variable de control (E[S_T]=F), vol implícita del MC menos la de la superficie, en puntos de vol (error ≈ 0.02):

  | Plazo / pasos | −1σ√T | −0.5σ√T | ATM-fwd | +0.5σ√T | +1σ√T |
  |---|---|---|---|---|---|
  | 91 d, 10 pasos | −0.06 | −0.05 | −0.06 | −0.09 | −0.15 |
  | 91 d, 40 pasos | −0.04 | −0.03 | −0.01 | −0.01 | −0.07 |
  | 1 año, 10 pasos | −0.30 | −0.16 | −0.25 | −0.65 | −0.49 |
  | 1 año, 20 pasos | −0.27 | −0.14 | −0.22 | −0.60 | −0.44 |
  | 1 año, 40 pasos | −0.24 | −0.12 | −0.18 | −0.53 | −0.38 |
  | 2 años, 10 pasos | −0.30 | −0.18 | −0.40 | −0.47 | −0.33 |

  A 1 año con 20 pasos el ATM baja solo a −0.22 (no a < 0.1) y `_result` sin gráfica sube de 0.98 a 1.56–1.59 s (> 1.5 s de R6); con 40 pasos 3.5 s por 200 000 trayectorias (≈4×). Se dejan 10 pasos y la magnitud medida queda declarada en Metodología → «Límites» (ATM y alas a 91 días, 1 y 2 años; 20/40 pasos a 1 año).
- **Sobrantes 1, 2, 3, 5**: sin `alive` (el nodo al otro lado da supervivencia < 0), `np.maximum(surv, 0)` en lugar de `clip`, referencia = `pv` si `method == "analytic"` (equivale a plano+analítico: la validación prohíbe analítico con sonrisa), y la fecha duplicada desapareció con D1 (`curve` ya no calcula fechas). Comprobado ANTES de D1 con 19 casos de `_result` (no touch y double, flat/smile/analítico, compra/venta, 7–730 días), misma semilla: JSON idéntico byte a byte con y sin el cambio.
- **D8/D2/sobrante 6**: sin `+2` ni `[1:-1]`: `np.linspace(*sorted(bars o [B, spot²/B]), 21)`. Con una barrera el rango va de la barrera a su espejo geométrico respecto al spot (spot siempre dentro, al centro en log; con 19.5 y spot 18.6: 17.74–19.5; con 40: 8.65–40); con dos, de barrera a barrera. El valor en la barrera es exactamente 0 (MC y analítico; QuantLib devuelve 0 con spot = barrera).
- **D6**: `_LOCK = threading.Lock()` de módulo y `with _LOCK:` en `_price` alrededor de `_result` y de la serie de la gráfica (la validación queda fuera). Prueba con 2 hilos × 5 precios, fechas 400 días distintas, `sys.setswitchinterval(1e-6)`, método analítico: sin el candado falló antes del cambio (resultado 0.0 y «date before reference date»), con él iguala los resultados en serie.
- **D5**: una sola palabra: la vol de `_build` es `mkt.surface.vol(mkt.spot, T)`, no la del spot chocado. Con el demo (sonrisa) la delta plana cambia ~1 % (no touch) y mucho más en el double estrecho (15–34 % del valor pequeño, porque antes incluía vega×∂σ/∂S); la gráfica plana ahora es a vol constante y la sonrisa solo usa esa vol como respaldo del Dupire. Prueba: delta plana analítica en la superficie del demo = la de una superficie plana con esa vol (rel 1e-9). No hizo falta declararlo en Metodología.
- **D7**: `_sides` devuelve `(campo, signo, rótulo)` con «barrera», «barrera inferior», «barrera superior»; mensaje «El spot 18.6000 ya tocó la barrera inferior». Los usos de `_sides` desempaquetan con `f, *_`.
- Comentario del puente: una línea con lo de QuantLib 1.42 (sin probabilidad de cruce ni MC de doble barrera; `MCBarrierEngine` + diferencial de knock-outs para el no touch; un solo motor por decisión).
- UI: `help: 'MXN por USD.'` fuera de la barrera del no touch (menos código). `ChainMap` y `NOT_TRADABLE` intactos. Metodología → «Límites»: añadidos el sesgo de vainillas, que con corredores muy anchos la fórmula cerrada no converge (referencia «—», método analítico con error) y que la vigilancia continua del double usa 10 pasos y subvalúa con corredores más estrechos que ~1 σ√T; 2 pruebas nuevas en `MethodologyScreen.test.tsx`.
- Verificación: `pytest desk/api/tests -q -p no:cacheprovider` 3637 passed (3619 + 18) en 327 s; `npm test` 648 passed (646 + 2); `npm run build` verde. R7 con el criterio de la auditoría (ast + tokenize): `fx_exotics.py` 131 líneas (antes 133) + 9 de registro = **140** (antes 142). R6 en proceso, valores por omisión con sonrisa, 5 corridas: sin gráfica no touch 0.98–1.02 s y double 0.99–1.01 s; completo 1.71–1.76 s y 1.72–1.77 s (≤ 1.5 s sin gráfica).
- Navegador (backend 5084 con base temporal, Chrome headless 9344, ambos apagados): `shots/fx_no_touch_v2.png` y `shots/fx_double_no_touch_v2.png` revisadas: sin la fila «Ajuste por sonrisa», la curva baja a 0 en la barrera (una línea «Barrera» al borde derecho en el no touch, dos en el double), `overflowX` falso, consola sin errores; barrera 40 se valúa (98.27 %) y la barrera tocada muestra «El spot 18.6000 ya tocó la barrera inferior».

### correcciones-H23-H24
Commits `cc9344b` (H23: `fx_exotics.py`, `test_price_fx_exotics.py`), `dfce263` (H24: `LV_STRIKES`, Metodología) y el de documentación (capítulo 15, su script, `cap01`, `docs/tex/README.md`). Pruebas primero (rojo antes: 19 de las 26 nuevas; el resto pasaba por no cruzar el choque).
- **H23, causa confirmada (dos).** (a) `_mc` con el spot más allá de la barrera daba supervivencia 8.1 % (barrera superior en 18.5), 6.4 % (inferior en 18.7) y los mismos valores con sonrisa: con los dos extremos de un paso del lado muerto el puente da `p < 1`; solo el paso que cruza (producto de logaritmos < 0) se anula. Como el nodo inicial es común, basta con que todos los nodos estén vivos para que ninguna trayectoria quede del lado muerto. (b) El choque de 1 % pasaba la barrera: reproducido el MC +631 697.97 / +25 816.36 / −632 896.77 con barrera 18.62 / 18.70 / 18.80. Firma nueva: `_mc(proc, sigma, ks, tab, sides, T, n)` con `sides = [(barrera, +1 si queda arriba del spot)]` (el signo es el de `_sides`); `_value` lo arma. Delta: `h = min(SPOT_BUMP·spot, min|spot − b|/2)`, `(V(spot + h) − pv)/h`.
- **Precios sin cambio.** 57 casos (no touch y double, plano/sonrisa/analítico, 7–730 días) con el código de antes y el de después de H23: `pv`, error estándar, probabilidad, referencia y vega idénticos bit a bit; la delta cambia solo donde la barrera más cercana está a menos de 2 % del spot.
- **H24.** `LV_STRIKES` 161. Un precio sin gráfica (`_result`, defaults con sonrisa, 5 corridas, carga ~1.2): no touch 1.01–1.07 s y double 1.03–1.12 s con 161 (0.94–1.03 y 1.00–1.07 con 41); con gráfica 1.9–2.0 s (antes 1.7–1.8). Tabla menos Dupire al vuelo (% del pago, 40 000 trayectorias), 41 → 161: no touch 91 d −0.018 → −0.001, 1 año −0.018 → −0.011, 2 años −0.314 → −0.003; double 91 d −0.039 → −0.002, 1 año +0.315 → +0.029, 2 años −0.515 → +0.030. Los precios con sonrisa se mueven ≤ 0.29 % del pago (≤ 1.1 errores estándar) respecto a la tabla de 41; plano y analítico no cambian. Efecto colateral medido: el sesgo de vainillas con sonrisa cambia con la tabla (ATM −0.04 / −0.22 / −0.50 a 91 d / 1 año / 2 años; antes −0.03 / −0.24 / −0.39) y con 20 y 40 pasos a 1 año −0.18 / −0.15 con 1.7 s y 3.2 s por precio: Metodología y capítulo 15 actualizados. La «tabla 15× más rápida» del plan era 6.3× con 161 strikes (un Monte Carlo de 20 000 trayectorias: 0.36 s con tabla, ≈2.3 s al vuelo).
- **R7.** `fx_exotics.py` 133 líneas con el criterio de la auditoría (ast + tokenize; antes 131) + 9 de registro = **142 ≤ 180**.
- Verificación: `pytest desk/api/tests -q -p no:cacheprovider` 3797 passed (3762 de partida + 26 de este trabajo + 9 de pruebas ajenas) en 368 s; `npm test` 678 passed; `npm run build` verde; `cap15_exoticos_fx.py` rc=0 (100 valores), `referencias_codigo.py` rc=0 (0 fallos), documento compilado con `-outdir` privado rc=0 (0 referencias indefinidas, 0 overfull > 10 pt).
