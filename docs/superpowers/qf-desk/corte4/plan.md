# Plan: QF Desk — Corte 4 (contabilidad de coberturas IFRS 9)

Diseño: `/tmp/fableorchestrate/qf-corte4/design.md` (en el repo: `docs/superpowers/qf-desk/` tras el corte). Repo: `/home/claudio/Git/Quant_Finance`, rama `feat/qf-desk`. Base: cortes 1 y 2 auditados (último commit de código `4566e13`, diseño del corte 4 `c2c3529`).

## Contexto

Todo implementador lee esta sección completa y solo su tarea. Las respuestas de Fable a P1–P15 (sección "Aclaraciones de Fable al plan" del diseño) ya están incorporadas: lo que sigue es decisión, no supuesto. Cambio respecto del diseño original: existe un tercer `item_kind`, `fixed_loan`, y `fair_value` solo se admite con él (P4).

**Actualizado por T8 (correcciones C1–C7 de la auditoría):** las reglas de cálculo, el contrato HTTP y la interfaz Python de abajo ya incluyen los cambios de backend; los cambios respecto del texto original están marcados con (C1)…(C6) y detallados al final del plan en "Anotado tras T8".

### Entorno
- Repo `/home/claudio/Git/Quant_Finance`, rama **`feat/qf-desk`**. **Nunca** push, merge ni `git stash`.
- **Python del backend:** `/home/claudio/anaconda3/bin/python` (3.8.18; Flask 2.3.3, pytest 8.2.0; Flask vive en `~/.local`: ejecutar sin `-I`). Sintaxis 3.8: nada de `match`, `X | Y`, `list[int]`/`dict[str, x]` evaluados en tiempo de ejecución; usar `typing`. **Sin paquetes nuevos** (ni Python ni npm).
- **Node** 22, **npm** 10. Interfaz en `desk/ui` (Vite + React 18 + TS, AG Grid, ECharts, react-router-dom, vitest + jsdom).
- **No hay C++ en este corte.** Nadie compila ni toca `include/`, `src/`, `tests/*.cpp`, `build/`. Todo se valúa con el motor existente: `valuation.value_trade`, `valuation.aged_swap`, `settlement.settled_flows`, `PRODUCTS[...]`.
- **Las cuatro suites** (desde la raíz del repo salvo vitest):
  - C++: `cmake --build build -j4 2>&1 | tail -3 && (cd build && ctest --output-on-failure 2>&1 | tail -3)` → `100% tests passed` (402). Solo la corre T7 (nada cambia en C++).
  - Bindings: `cmake --build build --target pytests 2>&1 | tail -3` → `OK`. Solo T7.
  - Backend: `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q 2>&1 | grep -E "passed|failed"` → `N passed`, sin `failed` (hoy se recolectan **2164**; no usar `tail`: un warning de pytest_asyncio sale tras el resumen).
  - Interfaz: `cd desk/ui && npm test 2>&1 | tail -5` (vitest run) y `npm run build 2>&1 | tail -5` (`tsc -b && vite build`) sin errores. La cuenta la da su salida.
- **Puertos:** el desk de Claudio usa **5070**: nadie arranca nada ahí. Backend de prueba en **5071** con base temporal: `cd /home/claudio/Git/Quant_Finance && /home/claudio/anaconda3/bin/python -c "from desk.api.app import create_app; create_app(db_path='/tmp/fableorchestrate/qf-corte4/it.db').run(host='127.0.0.1', port=5071)"`. La interfaz construida (`desk/ui/dist`) la sirve el mismo Flask.
- **No tocar** `~/Git/MarketDataFeed`, `desk/data/`, `graphify-out/`.

### Reglas de ejecución y commits
- Un commit por tarea, solo de tus rutas: `git add <rutas> && GRAPHIFY_SKIP_HOOK=1 git commit -m "<tipo>(desk): <por qué>" -- <rutas>`. Nunca `git add -A`/`.`. Autor: configuración global (Claudio). **Sin `Co-Authored-By`** ni otra línea de atribución. Mensaje en español que explique el porqué.
- Si `git commit` falla por `.git/index.lock`, esperar y reintentar; no borrar el lock salvo > 1 min sin proceso git vivo.
- Python valida, orquesta, suma/resta y persiste; no hay fórmulas de pricing nuevas. TS solo presenta.
- Validación en la frontera con `desk/api/validation.py`: `body_object()`, `number(d, name, gt=, ge=, lt=, le=, required=, default=)`, `integer(d, name, ge=, le=, required=)`, `choice(d, name, options, default=)`, `text(d, name, required=)`, `iso_date(d, name, required=True) -> date | None`, `finite_number(v)`, `has_non_finite(obj)`, `ensure_finite(payload)` (400 si hay no finitos), `MAX_AMOUNT = 1e13`, `NON_FINITE_MESSAGE`. Toda respuesta JSON numérica pasa por `ensure_finite`.
- Errores: `ApiError(status, mensaje_en_español, field)` (`desk/api/errors.py`) → `{"error", "field"}`; `field` = la clave tal como va en el cuerpo/consulta, sin prefijos (una clave de `item_terms` o `documentation` se reporta con su propio nombre, p. ej. `"notional"`, `"hedged_risk"`). `NotImplementedError` → 501 (handler existente); `ValueError`/`RuntimeError` → 400 "No se pudo valuar: …".
- Sin flags, opciones, columnas ni pantallas no pedidas. Textos de interfaz en español.

### Convenciones heredadas del corte 2 (fijas)
- Fechas ISO `YYYY-MM-DD`, días naturales. **Fecha de valuación = `as_of` del snapshot.** Ventana de flujos liquidados: `(d0, d1]`.
- Estado de una operación a la fecha `D` (`lifecycle.state`): `no_pactada` > `terminada` > `ejercida` > `vencida` (`D ≥ maturity_date`) > `viva`. Solo `viva` tiene PV ≠ 0.
- `irs`: índice = su `curve` (`TIIE-F` periodo 28 días, MXN; `SOFR` periodo 365, USD). Un `irs` creado por `POST /api/trades` sin `fixed_rate` nace a la par en el snapshot de la petición. Con `maturity_date`, el `irs` ajusta `periods = max(1, round(días/period_days))` y `maturity_date = start + periods × period_days` (para que un swap tenga exactamente las fechas de un crédito, el crédito debe vencer en `start + k × period_days`).
- `fx_forward`: `params = {side: "buy"|"sell", notional_usd, strike, days}`, PV en MXN. El forward de mercado sale de `PRODUCTS["fx_forward"].price(params, mkt)["risk"]["forward"]`.
- `irs`: `params = {curve, side: "payer"|"receiver", notional, periods, fixed_rate}` (`payer` = paga fija).
- **Combinaciones válidas (P4):** `cash_flow` con `floating_loan` o `forecast_fx`; `fair_value` solo con `fixed_loan`.

### Firmas existentes que se usan (reales)
- `desk/api/db.py`: `SCHEMA` (script con `CREATE TABLE IF NOT EXISTS`/`CREATE TRIGGER IF NOT EXISTS`), `init_schema(conn)` (ejecuta `SCHEMA` en cada arranque: tablas nuevas aparecen solas en bases existentes), `get_conn()`, `now_iso()`.
- `desk/api/portfolio.py`: `load_trades(conn)` y `get_trade(conn, id)` (404 `field:"id"`) → `{"id","product","counterparty","trade_date","start_date","maturity_date" (date),"params","created_at","events"}`; `public_trade(trade)`; `trade_pv_mxn(trade, mkt, fixings=None)`; `fit_to_maturity(product, params, start, maturity) -> (params, maturity)`.
- `desk/api/lifecycle.py`: `state(trade, events, on: date) -> {"status","terms","notional"}`.
- `desk/api/valuation.py`: `value_trade(trade, mkt, fixings=None) -> {"status","notional","currency","pv","pv_mxn","warnings"}` (`pv_mxn` siempre MXN, 0 si no `viva`); `aged_swap(trade, terms, mkt, fixings, warnings) -> qfpy.OisSwap` (`.npv(mkt.env)`, `.par_rate(mkt.env)`); `normalized(trade)`; `is_live(trade, on)`. `trade` puede ser un dict en memoria con la forma de `load_trades` (`events: []`).
- `desk/api/settlement.py`: `settled_flows(trade, fixings, d0, d1, fallback_spot, mkt=None) -> (flows, warnings)`; cada flujo `{"date","kind","amount","currency","amount_mxn"}`; `merge_warnings(*groups)`.
- `desk/api/pnl.py`: `compute_pnl(conn, from_id, to_id)` (filas con `id`, `pnl`, …). Ruta `GET /api/pnl?from=&to=`.
- `desk/api/market.py`: `load_context(conn, snapshot_id) -> MarketContext` (404 `field:"snapshot"`; atributos `as_of` (date), `spot`, `env`, `curves`, `pillars`, `shifted(...)`); `sources_of(data)`, `data_quality(sources) -> "synthetic"|"live"|"mixed"`; `list_snapshots(conn)` (cada uno trae `data_quality`); `roll_snapshot(conn, source_id, {"id","as_of"})`; `CURVES`.
- `desk/api/fixings.py`: `load_all(conn) -> Dict[str, Dict[date, float]]` (los tres índices siempre presentes).
- `desk/api/risk/scenarios.py`: `_shock(mkt, spec) -> MarketContext` (privada), `_validate(body)`. Las especificaciones de escenario son `{"name","type":"parallel"|"steepener","curve","bp"}` o `{"name","type":"fx_spot","pct"}`.
- Pruebas: fixtures `app`, `client` de `desk/api/tests/conftest.py` (base temporal sembrada con `MX-DEMO`, `as_of = 2026-11-10`, y 7 operaciones); `empty_portfolio(client)`, `insert_raw_trade(app, product, terms_text)`. Rodar snapshot por API: `POST /api/market/MX-DEMO/roll {"id":"D1","as_of":"2026-12-15"}`. Fijaciones: `POST /api/fixings/csv {"csv":"index,date,value\nTIIE-F,2026-11-10,0.07\n..."}` (solo días hábiles; fines de semana no avisan).
- Interfaz: `src/api/client.ts` (`request<T>(method, path, body?)` privada, `ApiError {status, field}`), `src/api/types.ts`, `src/lib/format.ts` (`fmtNumber(v, dec)`, `fmtMoney(v, ccy)`, `fmtRate(dec)`, `fmtDate(iso)`), `src/lib/provenance.ts` (`qualityText(DataQuality)`), `src/state/SnapshotContext.tsx` (`useSnapshot() -> {snapshotId, setSnapshotId, snapshot, snapshots, reload, error}`), `src/components/Shell.tsx` (`NAV_ITEMS` con `{to, label, icon}`; la paleta de comandos los toma de ahí; clases `shell__sidebar`, `shell__topbar`, `shell__main`), `src/screens/MethodologyScreen.tsx` (secciones `{id, title, items: {label, text}[]}` con `SectionBlock`; test con helper `row(label)` sobre `<dt>`). Tests de UI con `vi.mock('../api/client')` como en `PortfolioScreen.test.tsx`/`TradeScreen.test.tsx`.

### Esquema SQLite nuevo (lo agrega T1 al final de `db.SCHEMA`)
```sql
CREATE TABLE IF NOT EXISTS hedge_relationships (id INTEGER PRIMARY KEY AUTOINCREMENT,
  trade_id INTEGER NOT NULL REFERENCES trades(id), fraction REAL NOT NULL, hedge_type TEXT NOT NULL,
  item_kind TEXT NOT NULL, item_terms TEXT NOT NULL, hedge_ratio REAL NOT NULL, designation_date TEXT NOT NULL,
  designation_snapshot TEXT NOT NULL, documentation TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS hedge_relationships_no_update BEFORE UPDATE ON hedge_relationships BEGIN SELECT RAISE(ABORT, 'hedge_relationships no se modifica'); END;
CREATE TRIGGER IF NOT EXISTS hedge_relationships_no_delete BEFORE DELETE ON hedge_relationships BEGIN SELECT RAISE(ABORT, 'hedge_relationships no se modifica'); END;
CREATE TABLE IF NOT EXISTS hedge_events (id INTEGER PRIMARY KEY AUTOINCREMENT,
  relationship_id INTEGER NOT NULL REFERENCES hedge_relationships(id), type TEXT NOT NULL, event_date TEXT NOT NULL,
  data TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS hedge_events_no_update BEFORE UPDATE ON hedge_events BEGIN SELECT RAISE(ABORT, 'hedge_events es solo de inserción'); END;
CREATE TRIGGER IF NOT EXISTS hedge_events_no_delete BEFORE DELETE ON hedge_events BEGIN SELECT RAISE(ABORT, 'hedge_events es solo de inserción'); END;
CREATE TABLE IF NOT EXISTS hedge_periods (id INTEGER PRIMARY KEY AUTOINCREMENT,
  relationship_id INTEGER NOT NULL REFERENCES hedge_relationships(id), snapshot_id TEXT NOT NULL, as_of TEXT NOT NULL,
  result TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE (relationship_id, as_of));
CREATE TRIGGER IF NOT EXISTS hedge_periods_no_update BEFORE UPDATE ON hedge_periods BEGIN SELECT RAISE(ABORT, 'hedge_periods es solo de inserción'); END;
CREATE TRIGGER IF NOT EXISTS hedge_periods_no_delete BEFORE DELETE ON hedge_periods BEGIN SELECT RAISE(ABORT, 'hedge_periods es solo de inserción'); END;
```
(Disparadores también en `hedge_relationships`: P15.) `item_terms`, `documentation`, `data` y `result` son JSON. Ninguna migración: `init_schema` los crea en bases existentes.

### Constantes y vocabulario (fijos; los define T1 en `desk/api/hedges.py`)
```python
HEDGE_TYPES = ("cash_flow", "fair_value")
ITEM_KINDS = ("floating_loan", "fixed_loan", "forecast_fx")
INSTRUMENT_FOR = {"floating_loan": "irs", "fixed_loan": "irs", "forecast_fx": "fx_forward"}
VALID_COMBINATIONS = {"cash_flow": ("floating_loan", "forecast_fx"), "fair_value": ("fixed_loan",)}
LOAN_INDICES = ("TIIE-F", "SOFR")
LOAN_SIDES = ("pays_floating", "receives_floating")
FIXED_LOAN_SIDES = ("pays_fixed", "receives_fixed")
FX_SIDES = ("buy_usd", "sell_usd")
HEDGE_EVENT_TYPES = ("designation", "period_close", "dedesignation", "reserve_release")  # (C5)
DEDESIGNATION_CAUSES = ("instrument_ended", "criteria_not_met", "risk_objective_changed")  # (C2)
RELEASE_CAUSES = ("flow_occurred", "flow_no_longer_expected")  # (C5)
OFF_MARKET_TOLERANCE = 1e-6  # (C6) |PV| / nocional del instrumento al designar
STATUS_ACTIVE, STATUS_DEDESIGNATED = "activa", "desdesignada"
DOC_FIELDS = ("risk_management_objective", "hedged_risk", "effectiveness_method", "ineffectiveness_sources")
NOTICE = "Asientos sugeridos. Metodología pendiente de revisión por un contador con experiencia en IFRS 9"
ACC_DERIVATIVE = "Derivado (valor razonable)"
ACC_OCI = "ORI — reserva de cobertura"
ACC_INEFFECTIVENESS = "Resultados — inefectividad de cobertura"
ACC_RECYCLING = "Resultados — partida cubierta (reciclaje)"
ACC_CASH = "Efectivo"
ACC_ITEM_ADJ = "Partida cubierta — ajuste de valor razonable"
ACC_FV_RESULT = "Resultados — cobertura de valor razonable"
ACCOUNTS = (ACC_DERIVATIVE, ACC_OCI, ACC_INEFFECTIVENESS, ACC_RECYCLING, ACC_FV_RESULT, ACC_CASH, ACC_ITEM_ADJ)  # orden de presentación
MAIN_RESULT_ACCOUNT = {"cash_flow": ACC_INEFFECTIVENESS, "fair_value": ACC_FV_RESULT}  # recibe el residuo de redondeo (P5)
FAIR_VALUE_LEVEL = 2
FAIR_VALUE_BASIS = "Nivel 2: insumos observables (curvas, tipo de cambio y volatilidades del snapshot)"
FROZEN_NOTE = "Reserva congelada al desdesignar: se reciclará a resultados cuando ocurra el flujo cubierto"
```

### Reglas de cálculo (D3–D7 transcritas; fijas)
**Derivado hipotético** (`hedges.build_hypothetical`, lo guarda la designación; `hedges.hypothetical_trade` lo reconstruye como dict de operación en memoria, nunca en `trades`):
- `floating_loan` → `{"product":"irs","trade_date": designation_date,"start_date": item.start_date,"maturity_date": item.maturity_date,"params":{"curve": item.index,"side": "payer" si pays_floating / "receiver" si receives_floating,"notional": item.notional,"periods": max(1, round(días/period_days)),"fixed_rate": K}}` con `K = valuation.aged_swap(hyp, {**params, "fixed_rate": 0.0}, mkt_designación, fixings, []).par_rate(mkt.env)` (mismo patrón que `portfolio._at_par`). Las fechas del crédito se usan **tal cual** (sin ajuste a periodos: `qfpy.ois_payment_days` arma el periodo final corto).
- `fixed_loan` → igual que `floating_loan` (índice, nocional, fechas de la deuda, `K` = tasa par a la designación) salvo el lado: `"receiver"` (recibe fija) si `pays_fixed`, `"payer"` si `receives_fixed`.
- `forecast_fx` → `{"product":"fx_forward","trade_date": designation_date,"start_date": designation_date,"maturity_date": item.date,"params":{"side": "buy" si buy_usd / "sell" si sell_usd,"notional_usd": item.amount_usd,"strike": forward,"days": (item.date − designation_date).days}}` con `forward = PRODUCTS["fx_forward"].price({…,"strike": 1.0}, mkt_designación)["risk"]["forward"]`.
- Dict en memoria: `{"id": None, "product", "counterparty": "Hipotético", "trade_date", "start_date", "maturity_date" (date), "params", "created_at": None, "events": []}`.
- Se guarda en el evento `designation` (P2): `data = {"snapshot", "as_of", "data_quality", "pv_inst", "pv_hypo", "hypothetical": {"product","trade_date","start_date","maturity_date" (ISO),"params"}, "warnings": [{"code","message"}]}` (C6); `pv_inst` = `value_trade(operación, mkt_designación, fixings)["pv_mxn"]` (operación completa, sin × F), `pv_hypo` = idem sobre el hipotético (≈ 0).

**Cierre de periodo** (`hedge_measure.close_period`; regla del menor y redondeo según C3 y C4), todo en MXN, `F = fraction`, `prev` = último cierre o la designación (sus `pv_inst`, `pv_hypo`, `inst_cum`, `hypo_cum`, `inst_total`, `hypo_total`, `effective_cum`, `oci` y `as_of`; en la designación todos en 0 salvo el `as_of`):
- `pv_inst = value_trade(trade, mkt, fixings)["pv_mxn"]`; `pv_hypo = value_trade(hypothetical_trade(rel), mkt, fixings)["pv_mxn"]`.
- `inst_cum = F × (pv_inst − pv_inst_designación)`; `hypo_cum = pv_hypo − pv_hypo_designación` (PV limpio de lo liquidado); `d_inst_cum = inst_cum − prev.inst_cum`; `d_hypo_cum = hypo_cum − prev.hypo_cum`.
- `settled_flows, w = settlement.settled_flows(trade, fixings, prev.as_of, mkt.as_of, mkt.spot, mkt)`; `settled_period = F × Σ amount_mxn`. (C3) `hypo_settled_period = Σ amount_mxn` de `settled_flows(hypothetical_trade(rel), …)` con la misma ventana, **sin** × F.
- (C3) `inst_total = inst_cum + Σ settled_period` de todos los cierres hasta éste (= `F × (PV − PV_desig + Σ liquidado)`); `hypo_total = hypo_cum + Σ hypo_settled_period` de todos los cierres hasta éste.
- **Flujo de efectivo (C3):** `effective_cum = sign(inst_total) × min(|inst_total|, |hypo_total|)` si `inst_total × hypo_total > 0`, si no `0`; `ineffectiveness = (inst_total − prev.inst_total) − (effective_cum − prev.effective_cum)`; `recycled` = `sign(settled_period) × min(|settled_period|, |hypo_settled_period|)` si `settled_period × hypo_settled_period > 0`, si no `0` (la parte efectiva de lo liquidado en el periodo); si `trade_status == "vencida"` (cierre final) `recycled = effective_cum − (prev.effective_cum − prev.oci)` para que la reserva quede exactamente en 0; `oci = effective_cum − Σ recycled` (con `Σ recycled` previo = `prev.effective_cum − prev.oci`); `d_oci = oci − prev.oci`; `item_adjustment = 0`. Identidad: `identity_residual = (d_inst_cum + settled_period) − (d_oci + ineffectiveness + recycled)` (siempre 0 salvo flotante).
- **Valor razonable** (solo `fixed_loan`; sin cambios): `oci = d_oci = effective_cum = 0`; `item_adjustment = −d_hypo_cum`; `ineffectiveness = d_inst_cum + item_adjustment` (neto de `ACC_FV_RESULT` sin la línea de efectivo; R6 se prueba sobre esta cifra); `recycled = 0`; `fv_result = d_inst_cum + item_adjustment + settled_period` (neto total de `ACC_FV_RESULT`); `identity_residual = (d_inst_cum + settled_period) − (ineffectiveness − item_adjustment + settled_period)`. En flujo de efectivo `fv_result = 0`.
- `instrument_pnl = d_inst_cum + settled_period` (debe igualar `F ×` el `pnl` de `/api/pnl?from=prev.snapshot&to=snapshot` para esa operación).

**Asientos** (`hedge_measure.journal(hedge_type, figures, balances, booked=None) -> List[entry]`; mapeo confirmado en P4 y P14): cada línea se arma con un importe con signo (`+` = cargo) y luego `debit = max(x, 0)`, `credit = max(−x, 0)`. No hay reclasificación explícita desde ORI.
- (C4) **Cuentas de balance** (`Derivado`, `ORI`, `Efectivo`, y `Partida cubierta` en valor razonable): importe de la línea = `centavos(saldo con signo al cierre) − centavos ya asentados en esa cuenta` (suma de cargos − abonos de los cierres anteriores). Saldos con signo (`+` = cargo): `Derivado = +inst_cum`; `ORI = −oci`; `Efectivo = +Σ settled_period` hasta el cierre; `Partida cubierta = −hypo_cum`. El acumulado de asientos de cada cuenta de balance coincide así al centavo con el saldo redondeado.
- Flujo de efectivo: `ACC_DERIVATIVE` (saldo `inst_cum`, "Cambio de valor razonable del derivado (fracción designada)"); `ACC_OCI` (saldo `−oci`, "Porción efectiva a la reserva de cobertura"); `ACC_INEFFECTIVENESS −ineffectiveness` ("Inefectividad del periodo"); `ACC_CASH` (saldo `Σ settled_period`, "Liquidación del derivado en el periodo"); `ACC_RECYCLING −recycled` ("Reciclaje: flujo cubierto ocurrido en el periodo").
- Valor razonable: las contrapartidas son el **negativo exacto** de cada línea de balance ya redondeada: `ACC_DERIVATIVE` ("Cambio de valor razonable del derivado (fracción designada)") y `ACC_FV_RESULT` ("Cambio del derivado a resultados"); `ACC_ITEM_ADJ` ("Ajuste de valor razonable de la partida cubierta") y `ACC_FV_RESULT` ("Ajuste de la partida contra resultados"); `ACC_CASH` ("Liquidación del derivado en el periodo") y `ACC_FV_RESULT` ("Liquidación del derivado a resultados").
- Redondeo: cada importe a centavos con `Decimal(repr(x)).quantize(Decimal("0.01"), ROUND_HALF_UP)`; se omiten líneas que redondean a 0; `residual = Σcargos − Σabonos` (en centavos) se resta del importe con signo de la **última** línea de `MAIN_RESULT_ACCOUNT[hedge_type]` (inefectividad en flujo de efectivo, `ACC_FV_RESULT` en valor razonable; se crea con memo "Residuo de redondeo" si no existe) (P5); luego `Σdebit == Σcredit` exacto en centavos. En valor razonable el residuo es siempre 0. En JSON, `debit`/`credit` son `float` con 2 decimales.
- (C5) **Liberación de la reserva** (`hedge_measure.release_reserve`): `ACC_OCI` (cargo si el saldo de la reserva es positivo; abono si es negativo) contra `ACC_RECYCLING` (`flow_occurred`, "Reciclaje de la reserva congelada: el flujo cubierto ocurrió") o `ACC_INEFFECTIVENESS` (`flow_no_longer_expected`, "Reserva a resultados: el flujo cubierto ya no se espera"); la línea de `ORI` lleva el memo "Liberación de la reserva de cobertura congelada". Una liberación total deja `ORI` en 0.00 exacto sobre lo asentado.

**Efectividad prospectiva** (`hedge_effectiveness.effectiveness`):
- Términos críticos (con `terms`/`notional` vigentes de la operación a `as_of` por `lifecycle.state`; un `quantity_change` posterior a la designación no tiene tratamiento especial, P13): `floating_loan` y `fixed_loan` → `notional` (`F × notional_inst` vs `hedge_ratio × item.notional`), `index` (`curve` vs `item.index`), `start_date`, `maturity_date` (fechas de la operación vs de la deuda) y (C6) `side` (`instrument` = `side` del swap `payer|receiver`, `item` = `side` de la deuda; `match` si el swap es el que compensa: `pays_floating`→`payer`, `receives_floating`→`receiver`, `pays_fixed`→`receiver`, `receives_fixed`→`payer`). `forecast_fx` (P11) → `notional` (`F × notional_usd` vs `hedge_ratio × amount_usd`), `currency` (`"USD"` vs `"USD"`), `maturity_date` (vencimiento del forward vs `item.date`), `side` (`side` del forward vs el esperado: `buy_usd` → `"buy"`, `sell_usd` → `"sell"`; se muestran `instrument` = `side` del forward e `item` = `side` de la partida). Montos coinciden si `|a − b| ≤ 1e-9 × max(|a|, |b|, 1)`; textos y fechas, igualdad exacta.
- Escenarios (P6): `scenarios.DEFAULT_SCENARIOS` (los 8 de `RiskScreen.tsx`, ver T4); `d_inst = F × (pv_inst(choque) − pv_inst(base))`, `d_hypo = pv_hypo(choque) − pv_hypo(base)` (`value_trade(...)["pv_mxn"]`); `ratio = d_inst / d_hypo`, o `null` si `|d_hypo| ≤ 1e-9 × max(1, item_notional)` (escenario que no mueve la partida, p. ej. un choque SOFR sobre un crédito TIIE-F). `economic_relationship = True` si hay ≥ 1 razón no nula y todas las no nulas son `> 0`. `in_reference_range` = cuántas no nulas caen en `[0.8, 1.25]`.
- Si la operación o el hipotético no están `viva` al `as_of` → 409 `field:"snapshot"` (P7).

### Contrato HTTP nuevo (backend ↔ interfaz)
Nada existente cambia de forma. Rutas nuevas en `desk/api/routes/hedges.py` (blueprint `hedges`, registrado en `app.py`). Id de ruta no entero o fuera de rango → 404 `field:"id"` (mismo patrón que `routes/trades._trade_id`).

**`POST /api/hedges`** → 201 detalle de relación.
```json
{"trade_id": 8, "snapshot": "MX-DEMO", "designation_date": "2026-11-10",
 "hedge_type": "cash_flow", "item_kind": "floating_loan",
 "item_terms": {"index": "TIIE-F", "notional": 500000000, "start_date": "2026-11-10",
                "maturity_date": "2027-11-09", "side": "pays_floating"},
 "fraction": 1.0, "hedge_ratio": 1.0,
 "documentation": {"risk_management_objective": "Fijar el costo del crédito sindicado",
                   "hedged_risk": "Variabilidad de los intereses por TIIE de Fondeo",
                   "effectiveness_method": "Términos críticos y escenarios con derivado hipotético",
                   "ineffectiveness_sources": "Diferencias de fechas y nocional; riesgo de crédito no medido"}}
```
`item_terms` de `fixed_loan` (con `"hedge_type": "fair_value"`): `{"index": "TIIE-F", "notional": 300000000, "start_date": "2026-11-10", "maturity_date": "2028-11-03", "side": "pays_fixed"}`. `item_terms` de `forecast_fx`: `{"amount_usd": 10000000, "date": "2027-05-11", "side": "buy_usd"}`.
Validación (en este orden; primer error gana):
1. `trade_id` entero ≥ 1 → 400 `trade_id`; inexistente → 404 `trade_id`.
2. `snapshot` texto obligatorio → 400; inexistente → 404 `snapshot`.
3. `designation_date` opcional ISO (400); ausente = `as_of` del snapshot; distinta del `as_of` → 400 `designation_date` (P1).
4. `hedge_type` ∈ `HEDGE_TYPES`, `item_kind` ∈ `ITEM_KINDS` (`choice`, 400 con su campo).
5. `item_terms` objeto → si no, 400 `item_terms`. `floating_loan` y `fixed_loan`: `index` ∈ `LOAN_INDICES`, `notional` (`gt=0, le=MAX_AMOUNT`), `start_date`/`maturity_date` ISO, `maturity_date > start_date` y `maturity_date > designation_date` (400 `maturity_date`), `side` ∈ `LOAN_SIDES` (`floating_loan`) o `FIXED_LOAN_SIDES` (`fixed_loan`). `forecast_fx`: `amount_usd` (`gt=0, le=MAX_AMOUNT`), `date` ISO `> designation_date` (400 `date`), `side` ∈ `FX_SIDES`. Claves desconocidas se ignoran; se guarda la forma normalizada.
6. Combinaciones (P4, P10): `item_kind` ∉ `VALID_COMBINATIONS[hedge_type]` → 400 `hedge_type`; producto de la operación ≠ `INSTRUMENT_FOR[item_kind]` → 400 `item_kind`; `floating_loan`/`fixed_loan` con `curve` de la operación ≠ `index` → 400 `index`.
7. `fraction` `gt=0, le=1` → 400 `fraction`; `hedge_ratio` opcional (default 1) `gt=0, le=MAX_AMOUNT` → 400 `hedge_ratio` (P3: no entra a la medición, solo a términos críticos).
8. `documentation` objeto con los cuatro `DOC_FIELDS` como `text` obligatorio → 400 con la clave (o `documentation` si no es objeto) (P9).
9. Operación no `viva` en `designation_date` → **409** `trade_id`.
10. (C1) `designation_date` anterior a la fecha del último evento (cualquier tipo, `designation`/`period_close`/`dedesignation`/`reserve_release`) de **cualquier** relación —también desdesignada— de la misma operación → **409** `snapshot` (la fecha igual al último evento se admite).
11. (C1) Σ `fraction` de las relaciones **vigentes a `designation_date`** (designadas en o antes de esa fecha y no desdesignadas en o antes de ella) + nueva > 1 + 1e-12 → **409** `fraction`.
(C6) Después de validar, calcula `warnings` (abajo). Inserta la relación y el evento `designation` (`event_date = designation_date`, `data` del Contexto, con `warnings`) en una transacción; la ruta hace `commit`; la respuesta 201 es el detalle (que lleva `warnings`).

**Avisos al designar (C6)** `warnings: [{"code","message"}]`, no bloquean, en este orden: `no_economic_relationship` (la prueba prospectiva al snapshot de designación da `economic_relationship = false`); `instrument_off_market` (`|pv_mxn del instrumento completo| > OFF_MARKET_TOLERANCE × nocional en MXN` — nocional × spot si la moneda es USD; el mensaje cita el valor); `forecast_date_weekend` (`forecast_fx` con `date` en sábado o domingo: se liquidará con el spot del snapshot).

**Detalle de relación** (respuesta de `POST /api/hedges`, `GET /api/hedges/<id>`, `POST …/dedesignate`, `POST …/release`):
```json
{"id": 1, "trade_id": 8, "product": "irs", "counterparty": "Banco Alfa (sintético)",
 "fraction": 1.0, "hedge_type": "cash_flow", "item_kind": "floating_loan",
 "item_terms": {"index": "TIIE-F", "notional": 500000000.0, "start_date": "2026-11-10", "maturity_date": "2027-11-09", "side": "pays_floating"},
 "hedge_ratio": 1.0, "designation_date": "2026-11-10", "designation_snapshot": "MX-DEMO",
 "documentation": {"risk_management_objective": "…", "hedged_risk": "…", "effectiveness_method": "…", "ineffectiveness_sources": "…"},
 "hypothetical": {"product": "irs", "trade_date": "2026-11-10", "start_date": "2026-11-10", "maturity_date": "2027-11-09",
                  "params": {"curve": "TIIE-F", "side": "payer", "notional": 500000000.0, "periods": 13, "fixed_rate": 0.0712}},
 "designation": {"snapshot": "MX-DEMO", "as_of": "2026-11-10", "data_quality": "synthetic", "pv_inst": 0.0, "pv_hypo": 0.0},
 "status": "activa", "dedesignation": null, "warnings": [], "oci_balance": 0.0, "last_close": null,
 "events": [{"id": 1, "relationship_id": 1, "type": "designation", "event_date": "2026-11-10", "data": {"…": "…"}, "created_at": "2026-11-11T18:00:00+00:00"}],
 "periods": [], "created_at": "2026-11-11T18:00:00+00:00"}
```
`status` = `desdesignada` si existe evento `dedesignation`; `dedesignation` = `{"date","reason","cause","snapshot","frozen_oci"}` o `null` (C2; `cause` y `snapshot` son `null` en eventos anteriores a C2); `warnings` = los de la designación (C6; `[]` si el evento no los trae); `oci_balance` = reserva **vigente** = `reserve_after` de la última liberación (C5) o, si no hay, `oci` del último periodo (0 si no hay periodos); `last_close` = `as_of` del último periodo o `null`; `events` por `(event_date, id)`; `periods` por `as_of` en su forma pública (abajo).

**`GET /api/hedges[?trade_id=<int>]`** → `{"hedges": [resumen…]}` por id; `trade_id` no entero → 400 `trade_id`. Resumen:
```json
{"id": 1, "trade_id": 8, "product": "irs", "counterparty": "Banco Alfa (sintético)", "hedge_type": "cash_flow",
 "item_kind": "floating_loan", "fraction": 1.0, "hedge_ratio": 1.0, "designation_date": "2026-11-10",
 "status": "activa", "oci_balance": 0.0, "last_close": null, "periods_count": 0}
```

**`POST /api/hedges/<id>/periods`** `{"snapshot": "D1"}` → 201 periodo (forma pública). Errores: `snapshot` falta → 400; inexistente → 404 `snapshot`; relación `desdesignada` → 409 `id`; `as_of ≤ last_close` (o `≤ designation_date`) → 409 `snapshot`; operación `terminada`/`ejercida` al `as_of` → 409 `snapshot` ("La operación ya no está viva al <as_of>: desdesigna la relación"); `vencida` se admite una sola vez: es el cierre final (PV 0); si el último cierre ya se hizo con la operación `vencida` (`trade_status` del último periodo), todo cierre posterior → 409 `snapshot` (P12). Inserta `hedge_periods` y evento `period_close` `{"period_id","snapshot","as_of"}` (`event_date = as_of`).
Periodo, forma pública (`{"id","snapshot","as_of","created_at"}` + todo `result`):
```json
{"id": 1, "snapshot": "D1", "as_of": "2026-12-15", "created_at": "…",
 "prev_snapshot": "MX-DEMO", "prev_as_of": "2026-11-10", "data_quality": "synthetic", "trade_status": "viva",
 "hedge_type": "cash_flow", "fraction": 1.0,
 "pv_inst": -125000.0, "pv_hypo": -125000.0, "inst_cum": -125000.0, "hypo_cum": -125000.0,
 "d_inst_cum": -125000.0, "d_hypo_cum": -125000.0,
 "inst_total": -94000.0, "hypo_total": -94000.0, "effective_cum": -94000.0,
 "settled_period": 31000.0, "hypo_settled_period": 31000.0, "settled_flows": [{"date": "2026-12-08", "kind": "coupon", "amount": 31000.0, "currency": "MXN", "amount_mxn": 31000.0}],
 "oci": -125000.0, "d_oci": -125000.0, "ineffectiveness": 0.0, "recycled": 31000.0, "item_adjustment": 0.0, "fv_result": 0.0,
 "instrument_pnl": -94000.0, "identity_residual": 0.0,
 "entries": [{"account": "Efectivo", "debit": 31000.0, "credit": 0.0, "memo": "Liquidación del derivado en el periodo"}],
 "warnings": []}
```
`warnings` = `merge_warnings` de los de `value_trade` (operación e hipotético) y de `settled_flows` (operación e hipotético). (C3) Campos nuevos: `inst_total`, `hypo_total`, `effective_cum` y `hypo_settled_period` (ver "Cierre de periodo"); `settled_flows` sigue siendo solo el del instrumento. En valor razonable `effective_cum = 0` y `inst_total`/`hypo_total` son informativos.

**`POST /api/hedges/<id>/dedesignate`** `{"snapshot": "D2", "reason": "Prepago del crédito", "cause": "instrument_ended"}` → 201 detalle (C2: ya no recibe `date`; la fecha es el `as_of` del snapshot). Orden de validación: 404 `id` → 400 `snapshot` / `reason` / `cause` (`cause` ∈ `DEDESIGNATION_CAUSES`) → 404 `snapshot` → 409 `id` (ya `desdesignada`) → 409 `snapshot` si `as_of < último cierre` (o `< designación`). Si `as_of >` último cierre (o designación) **primero cierra el periodo** con ese snapshot (mismas reglas que `POST …/periods`: 409 `snapshot` si la operación ya no está `viva` ni `vencida`, o si el último cierre ya fue el final; el mensaje manda a usar el snapshot del último cierre) y luego inserta el evento `dedesignation` (`event_date = as_of`) con `{"reason","cause","snapshot","frozen_oci"}`, `frozen_oci = oci_balance` tras ese cierre. Si `as_of ==` último cierre (o designación) no mide de nuevo. La respuesta incluye el periodo nuevo en `periods`. No hay desdesignación voluntaria sin causa (IFRS 9 6.5.6).

**`POST /api/hedges/<id>/release`** `{"snapshot": "D2", "amount": 1000.0, "cause": "flow_occurred"}` → 201 detalle (C5). `amount` opcional con el **signo del saldo** (`oci_balance`; por omisión, todo el saldo). Orden: 404 `id` → 400 `snapshot` / `cause` (`cause` ∈ `RELEASE_CAUSES`) / `amount` (no número) → 404 `snapshot` → 409 `id` (relación no `desdesignada`, o reserva vigente |saldo| < 0.005) → 409 `snapshot` (`as_of` anterior al último evento de la relación) → 400 `amount` (|amount| < 0.005) → 409 `amount` (signo contrario al saldo, o |amount| > |saldo| + 0.005). Un `amount` a media centésima del saldo cuenta como liberación total. Inserta el evento `reserve_release` (`event_date = as_of`) con `data = {"snapshot","cause","amount","reserve_before","reserve_after","entries":[ORI, contrapartida]}`; una liberación total deja `reserve_after = 0.0` y `ORI` en 0.00 exacto sobre lo asentado. `frozen_oci` de `dedesignation` no cambia: reserva vigente = congelado − liberado.

**`GET /api/hedges/<id>/effectiveness?snapshot=<id>`** → 200. `snapshot` falta → 400; inexistente → 404 `snapshot`; no viva → 409 `snapshot`.
```json
{"id": 1, "snapshot": "MX-DEMO", "as_of": "2026-11-10",
 "critical_terms": [
   {"term": "notional", "label": "Nocional", "instrument": 500000000.0, "item": 500000000.0, "result": "match"},
   {"term": "index", "label": "Índice", "instrument": "TIIE-F", "item": "TIIE-F", "result": "match"},
   {"term": "start_date", "label": "Inicio", "instrument": "2026-11-10", "item": "2026-11-10", "result": "match"},
   {"term": "maturity_date", "label": "Vencimiento", "instrument": "2027-11-09", "item": "2027-12-07", "result": "mismatch"},
   {"term": "side", "label": "Sentido", "instrument": "payer", "item": "pays_floating", "result": "match"}],
 "scenarios": [{"name": "TIIE-F +50 pb", "d_inst": 2400000.0, "d_hypo": 2400000.0, "ratio": 1.0},
               {"name": "SOFR +50 pb", "d_inst": 0.0, "d_hypo": 0.0, "ratio": null}],
 "economic_relationship": true, "in_reference_range": 4, "scenarios_counted": 4,
 "reference_note": "IFRS 9 no fija un umbral de efectividad: el rango 80 %–125 % se informa solo como referencia",
 "warnings": []}
```
`label`: `notional` "Nocional", `index` "Índice", `currency` "Moneda", `start_date` "Inicio", `maturity_date` "Vencimiento", `side` "Sentido". `scenarios_counted` = razones no nulas.

**`GET /api/hedges/<id>/report[?snapshot=<id>][&format=json|csv]`** → JSON (default) o CSV. `format` distinto → 400 `format`. `snapshot` de la prueba prospectiva: por omisión el de designación (P8).
```json
{"id": 1, "generated_at": "2026-11-11T18:00:00+00:00",
 "notice": "Asientos sugeridos. Metodología pendiente de revisión por un contador con experiencia en IFRS 9",
 "relationship": {"…detalle sin events ni periods…": "…"},
 "documentation": {"risk_management_objective": "…", "hedged_risk": "…",
   "hedged_item": {"item_kind": "floating_loan", "item_terms": {"…": "…"}},
   "hedging_instrument": {"trade_id": 8, "product": "irs", "counterparty": "…", "fraction": 1.0, "notional": 500000000.0, "currency": "MXN", "start_date": "2026-11-10", "maturity_date": "2027-11-09"},
   "hedge_ratio": 1.0, "effectiveness_method": "…", "ineffectiveness_sources": "…"},
 "prospective": {"…respuesta de effectiveness…": "…"},
 "periods": [{"id": 1, "snapshot": "D1", "as_of": "2026-12-15", "data_quality": "synthetic", "inst_cum": 0.0, "hypo_cum": 0.0,
              "oci": 0.0, "d_oci": 0.0, "ineffectiveness": 0.0, "recycled": 0.0, "item_adjustment": 0.0, "fv_result": 0.0, "settled_period": 0.0}],
 "entries_by_period": [{"period_id": 1, "as_of": "2026-12-15", "entries": [{"account": "…", "debit": 0.0, "credit": 0.0, "memo": "…"}]}],
 "reserve_releases": [{"id": 9, "snapshot": "D2", "as_of": "2027-01-10", "cause": "flow_occurred", "amount": 1000.0, "reserve_after": 0.0, "entries": [{"account": "ORI — reserva de cobertura", "debit": 1000.0, "credit": 0.0, "memo": "…"}]}],
 "entries_total": [{"account": "Efectivo", "debit": 31000.0, "credit": 0.0}],
 "fair_value_hierarchy": {"level": 2, "basis": "Nivel 2: insumos observables (…)",
   "snapshots": [{"role": "designation", "snapshot": "MX-DEMO", "as_of": "2026-11-10", "data_quality": "synthetic"},
                 {"role": "period", "snapshot": "D1", "as_of": "2026-12-15", "data_quality": "synthetic"}]},
 "reserve": {"balance": 0.0, "frozen": false, "note": null, "released": 0.0}}
```
`entries_total`: por cuenta en el orden de `ACCOUNTS`, sumas de cargos y abonos de todos los periodos (solo cuentas con algún importe). `reserve.balance` = reserva vigente (C5); `reserve.frozen` = relación desdesignada; `note` = `FROZEN_NOTE` si congelada **y** |balance| ≥ 0.005; `reserve.released` = Σ `amount` liberado. (C5) `reserve_releases` = liberaciones en orden de fecha (en el detalle son los eventos `reserve_release`); `entries_total` suma también sus asientos. `hedging_instrument.notional`/`currency` = `public_trade` de la operación. Si la prueba prospectiva da 409 (operación ya no viva en ese snapshot), `prospective` = `{"error": <mensaje>}` y el reporte responde 200.
CSV (`text/csv; charset=utf-8`, `Content-Disposition: attachment; filename="cobertura-<id>-asientos.csv"`): encabezado `period_id,as_of,snapshot,account,debit,credit,memo`, una fila por asiento en orden de periodo y de línea y, después, una por asiento de cada liberación de reserva (C5) con `period_id` **vacío** y el `snapshot`/`as_of` de la liberación, importes con `"%.2f"`, sin fila de totales; `csv.writer` estándar.

### Interfaz Python interna (fija)
- `desk/api/hedges.py` (T1; T2 y T5 rellenan stubs): constantes del Contexto; `load_relationship(conn, hedge_id) -> dict` (404 `field:"id"`; dict interno con `designation_date` y fechas de `item_terms` como `date`, `item_terms`/`documentation` dict, `events` con `event_date` `date` y `data` dict, `periods` ordenados por `as_of` con `as_of` `date` y `result` dict, `designation` = `data` del evento `designation`); `load_relationships(conn, trade_id=None) -> List[dict]`; `status(rel)`, `oci_balance(rel)` (vigente, C5), `last_close(rel) -> Optional[date]`, `last_event_date(rel) -> date` (C1/C5); `public_relationship(rel)`, `public_summary(rel)`, `public_period(period)`; `insert_event(conn, hedge_id, type, event_date: date, data) -> dict` (sin commit); `insert_period(conn, hedge_id, snapshot_id, as_of: date, result) -> dict` (sin commit); `hypothetical_trade(rel) -> dict` (desde `rel["designation"]["hypothetical"]`). **Stubs** que lanzan `NotImplementedError`: `build_hypothetical(item_kind, item_terms, designation_date, mkt, fixings) -> dict` (T2), `create_hedge(conn, body) -> dict` detalle (T2; T8 añade C1 y `warnings` C6). **T8:** `dedesignate` ya no vive aquí: pasó a `hedge_measure.dedesignate` (necesita cerrar el periodo y `hedge_measure` importa `hedges`); `hedges` solo guarda las constantes `DEDESIGNATION_CAUSES`/`RELEASE_CAUSES`.
- `desk/api/hedge_measure.py` (T1 stub, T3; T8): `close_period(conn, hedge_id, body) -> dict` periodo público; `measure(rel, trade, mkt, fixings) -> dict` (`result` sin escribir); `journal(hedge_type, figures, balances, booked=None) -> List[dict]` (C4: `balances` = saldo con signo por cuenta de balance, `booked` = centavos ya asentados); `dedesignate(conn, hedge_id, body) -> dict` detalle (C2, sin commit); `release_reserve(conn, hedge_id, body) -> dict` detalle (C5, sin commit). Rutas `POST …/dedesignate` y `POST …/release` en `routes/hedges.py`.
- `desk/api/hedge_effectiveness.py` (T1 stub, T4; T8): `effectiveness(conn, hedge_id, snapshot_id) -> dict`; `assess(rel, trade, mkt, fixings) -> dict` (la prueba sin `id`/`snapshot`; acepta una relación aún sin guardar, la usa el alta para el aviso C6); `critical_terms(rel, trade, on: date) -> List[dict]`.
- `desk/api/hedge_report.py` (T1 stub, T6): `build_report(conn, hedge_id, snapshot_id=None) -> dict`; `report_csv(report) -> str`.
- `desk/api/risk/scenarios.py` (T4): agrega `DEFAULT_SCENARIOS` y `shock(mkt, spec)` pública (= `_shock`); nada más cambia.
- `desk/api/tests/hedge_fixture.py` (T1; ayudas compartidas, sin tests): `DOC` (documentación válida), `roll(client, source, new_id, days) -> str` (as_of ISO del nuevo), `load_fixings(client, index, start: date, end: date, value: float)` (CSV con un valor por día hábil en `[start, end)`), `par_irs(client, curve, notional, start, maturity, side="payer", snapshot="MX-DEMO") -> dict` (POST `/api/trades` sin `fixed_rate`), `market_forward(client, side, notional_usd, maturity, snapshot="MX-DEMO") -> dict` (strike = forward de `/api/price/fx_forward`), `designate(client, trade_id, item_kind, item_terms, **overrides) -> Response` (POST `/api/hedges` con `snapshot="MX-DEMO"`, `hedge_type="cash_flow"`, `fraction=1.0`, `DOC`).

### Interfaz: piezas fijas (las crea U1)
- Rutas: `/coberturas` → `screens/HedgesScreen.tsx` (lista + alta), `/coberturas/:id` → `screens/HedgeScreen.tsx` (detalle), `/coberturas/:id/reporte` → `screens/HedgeReportScreen.tsx` (vista imprimible). Todas `export default`.
- `Shell.tsx` `NAV_ITEMS`: entrada `{to: '/coberturas', label: 'Coberturas'}` entre Riesgo y Metodología (icono SVG de 16 px en el estilo de los demás).
- `components/AccountingNotice.tsx` (`export function AccountingNotice()`): banda `role="note"` con el texto exacto de `NOTICE`; la montan las tres pantallas de coberturas, siempre visible (también al imprimir).
- `src/lib/hedgeLabels.ts`: `HEDGE_TYPE_LABEL` (`cash_flow` "Flujo de efectivo", `fair_value` "Valor razonable"), `ITEM_KIND_LABEL` (`floating_loan` "Crédito a tasa variable", `fixed_loan` "Crédito a tasa fija", `forecast_fx` "Flujo pronosticado en USD"), `SIDE_LABEL` (`pays_floating` "Paga variable", `receives_floating` "Cobra variable", `pays_fixed` "Paga fija", `receives_fixed` "Cobra fija", `buy_usd` "Compra de USD", `sell_usd` "Venta de USD", `buy` "Compra", `sell` "Venta"), `VALID_ITEM_KINDS` (`cash_flow` → `['floating_loan','forecast_fx']`, `fair_value` → `['fixed_loan']`), `HEDGE_STATUS_LABEL` (`activa` "Activa", `desdesignada` "Desdesignada"), `HEDGE_EVENT_LABEL` (`designation` "Designación", `period_close` "Cierre de periodo", `dedesignation` "Desdesignación"), `TERM_RESULT_LABEL` (`match` "Coincide", `mismatch` "No coincide"), `DOC_FIELD_LABEL` (`risk_management_objective` "Objetivo de gestión de riesgo", `hedged_risk` "Riesgo cubierto", `effectiveness_method` "Método de efectividad", `ineffectiveness_sources` "Fuentes de inefectividad"), `DEFAULT_EFFECTIVENESS_METHOD = 'Coincidencia de términos críticos y análisis de escenarios con derivado hipotético'`.
- `types.ts`: `HedgeType`, `ItemKind`, `HedgeStatus`, `FloatingLoanTerms`, `FixedLoanTerms`, `ForecastFxTerms`, `ItemTerms`, `HedgeDocumentation`, `HedgeEvent`, `JournalEntry {account, debit, credit, memo}`, `HedgePeriod`, `HedgeSummary`, `HedgeDetail`, `CriticalTerm`, `ScenarioRatio`, `EffectivenessResponse`, `HedgeReport`, `CreateHedgeBody` (transcripción exacta del contrato).
- `client.ts`: `listHedges(q?: {trade_id?: number}) -> HedgeSummary[]`, `getHedge(id)`, `createHedge(body)`, `closeHedgePeriod(id, snapshot) -> HedgePeriod`, `dedesignateHedge(id, {date, reason}) -> HedgeDetail`, `hedgeEffectiveness(id, snapshot)`, `hedgeReport(id, snapshot?)`, `hedgeReportCsvUrl(id) -> string` (`/api/hedges/<id>/report?format=csv`, para un `<a download>`).
- Montos en MXN con `fmtMoney(v, 'MXN')`, fechas con `fmtDate`, cifras con clase `.num`; nada de `-0.00` (ya lo garantiza `fmtNumber`).

---

### Anotado tras U1 (interfaz, commit 75d7d83; vitest = 181)
- Tipos en `src/api/types.ts` tal como el contrato: `HedgeType`, `ItemKind`, `HedgeStatus`, `FloatingLoanTerms`, `FixedLoanTerms`, `ForecastFxTerms`, `ItemTerms`, `HedgeDocumentation`, `HedgeEvent`, `JournalEntry`, `HedgePeriod` (+ `HedgePeriodFlow`), `HedgeSummary`, `HedgeDetail`, `CriticalTerm`, `ScenarioRatio`, `EffectivenessResponse`, `HedgeReport` (`prospective: EffectivenessResponse | {error}`), `CreateHedgeBody`.
- Cliente `src/api/client.ts` (devuelven lo ya desenvuelto): `listHedges(q?: {trade_id?})`, `getHedge(id)`, `createHedge(body)`, `closeHedgePeriod(id, snapshot) → HedgePeriod`, `dedesignateHedge(id, {date, reason}) → HedgeDetail`, `hedgeEffectiveness(id, snapshot)`, `hedgeReport(id, snapshot?)`, `hedgeReportCsvUrl(id): string`.
- `lib/hedgeLabels.ts`: `HEDGE_TYPE_LABEL`, `ITEM_KIND_LABEL`, `SIDE_LABEL`, `VALID_ITEM_KINDS`, `HEDGE_STATUS_LABEL`, `HEDGE_EVENT_LABEL`, `TERM_RESULT_LABEL`, `DOC_FIELD_LABEL`, `DEFAULT_EFFECTIVENESS_METHOD`.
- `components/AccountingNotice.tsx`: `AccountingNotice()` (`role="note"`, clase `accounting-notice`) y `ACCOUNTING_NOTICE` (texto exacto).
- Stubs `export default`: `screens/HedgesScreen.tsx` (`/coberturas`), `screens/HedgeScreen.tsx` (`/coberturas/:id`), `screens/HedgeReportScreen.tsx` (`/coberturas/:id/reporte`). `Shell` ya tiene la entrada "Coberturas".

### Anotado tras T1 (backend, commit cc76458; `desk/api` = 2188 tests)
- `hedges.py` real: `load_relationship(conn, hedge_id)` (404 `field:"id"`), `load_relationships(conn, trade_id=None)`, `status(rel)`, `oci_balance(rel)`, `last_close(rel)`, `public_relationship`, `public_summary`, `public_period` (`{id, snapshot, as_of, created_at, **result}`), `public_event`, `insert_event(conn, hedge_id, type, event_date: date, data)` (sin commit), `insert_period(conn, hedge_id, snapshot_id, as_of: date, result)` (sin commit; `as_of` repetido → `sqlite3.IntegrityError`: validar antes con 409), `hypothetical_trade(rel)`.
- Forma interna de la relación: `id, trade_id, product, counterparty, fraction, hedge_type, item_kind, item_terms (fechas como date), hedge_ratio, designation_date (date), designation_snapshot, documentation, created_at, events (ordenados por (event_date, id)), periods (ordenados por as_of; cada uno {id, relationship_id, snapshot_id, as_of, result, created_at}), designation (data del evento designation)`.
- Stubs a implementar: `hedges.build_hypothetical(item_kind, item_terms, designation_date, mkt, fixings)` y `hedges.create_hedge(conn, body)` (T2); `hedges.dedesignate(conn, hedge_id, body)` (T5); `hedge_measure.close_period(conn, hedge_id, body)`, `measure(rel, trade, mkt, fixings)`, `journal(hedge_type, figures)` (T3); `hedge_effectiveness.effectiveness(conn, hedge_id, snapshot_id)`, `critical_terms(rel, trade, on)` (T4); `hedge_report.build_report(conn, hedge_id, snapshot_id=None)`, `report_csv(report)` (T6).
- Las rutas (`routes/hedges.py`) ya validan, delegan, hacen commit y fijan el código; basta implementar los stubs. `tests/test_hedges_schema.py::STUB_ROUTES`: cada tarea borra solo su fila, releyendo el archivo antes.
- Ayudas de prueba en `tests/hedge_fixture.py`: `DOC`, `roll(client, source, new_id, days)`, `load_fixings(client, index, start, end, value)`, `par_irs(client, curve, notional, start, maturity, side="payer", snapshot="MX-DEMO")`, `market_forward(client, side, notional_usd, maturity, snapshot="MX-DEMO")`, `designate(client, trade_id, item_kind, item_terms, **overrides)`.

### Anotado tras T2 (commit 6a5c290; `desk/api` = 2237 tests)
- `hedges.build_hypothetical(item_kind, item_terms, designation_date: date, mkt, fixings) -> {"product","trade_date","start_date","maturity_date" (ISO),"params"}` (`item_terms` en forma interna, fechas como `date`). `hedges.create_hedge(conn, body) -> public_relationship(...)` (sin commit).
- `rel["designation"]` = `{"snapshot", "as_of" (ISO), "data_quality", "pv_inst" (pv_mxn de la operación COMPLETA, sin × F), "pv_hypo", "hypothetical": {...}}`. `hypothetical_trade(rel)` devuelve la operación sintética lista para `value_trade`.
- Hipotético de créditos: `irs` con `params = {curve, side, notional, periods, fixed_rate}` (`fixed_rate` = par con `aged_swap` y fijaciones); de `forecast_fx`: `fx_forward` con `params = {side, notional_usd, strike, days}`.

### Anotado tras T3 (commit 74df020)
- `hedge_measure.close_period(conn, hedge_id, body) -> hedges.public_period(period)` (inserta `hedge_periods` y el evento `period_close` `{"period_id","snapshot","as_of"}`, sin commit); `measure(rel, trade, mkt, fixings) -> result` (sin `data_quality`, que añade `close_period`); `journal(hedge_type, figures) -> [{"account","debit","credit","memo"}]`.
- Orden de validación del cierre: 404 `id` → 400 `snapshot` → 404 `snapshot` → 409 `id` (desdesignada) → 409 `snapshot` (no posterior al último cierre o a la designación) → 409 `snapshot` (ya hubo cierre final con `vencida`) → 409 `snapshot` (operación terminada o ejercida: "desdesigna la relación").
- `result` de un periodo: `prev_snapshot, prev_as_of, data_quality, trade_status, hedge_type, fraction, pv_inst, pv_hypo, inst_cum, hypo_cum, d_inst_cum, d_hypo_cum, settled_period, settled_flows, oci, d_oci, ineffectiveness, recycled, item_adjustment, fv_result, instrument_pnl, identity_residual, entries, warnings`. Asientos en `period["result"]["entries"]`; periodos ordenados por `as_of`; `hedges.oci_balance(rel)` usa `result["oci"]` del último.

## Tareas

### T1 — Esquema, módulos y rutas de coberturas como contrato
- **Modelo:** sonnet · **Depende de:** — · **R:** R1 (disparadores), base de R1–R9, R12
- **Objetivo:** dejar tablas, lecturas, ayudas de prueba y todas las rutas registradas; lo que falta responde 501 con el contrato, para que T2–T6 solo rellenen funciones.
- **Archivos:** `desk/api/db.py` (solo añadir al final de `SCHEMA`), `desk/api/hedges.py` (nuevo), `desk/api/hedge_measure.py` (nuevo, stub), `desk/api/hedge_effectiveness.py` (nuevo, stub), `desk/api/hedge_report.py` (nuevo, stub), `desk/api/routes/hedges.py` (nuevo), `desk/api/app.py` (registrar blueprint), `desk/api/tests/hedge_fixture.py` (nuevo), `desk/api/tests/test_hedges_schema.py` (nuevo).
- **Pasos:**
  1. Esquema del Contexto en `db.SCHEMA`.
  2. `hedges.py`: constantes, lecturas, `public_*`, `insert_event`, `insert_period`, `hypothetical_trade` reales; stubs `build_hypothetical`, `create_hedge`, `dedesignate`. Los demás módulos con sus firmas lanzando `NotImplementedError`.
  3. `routes/hedges.py`: las siete rutas del contrato; cada una parsea id (404 `id`), valida parámetros de consulta obligatorios (`snapshot` en effectiveness → 400; `trade_id` de la lista entero → 400; `format` ∈ `json|csv` → 400), delega, hace `conn.commit()` en las escrituras, `ensure_finite` en JSON, y para `format=csv` devuelve `Response(report_csv(...), mimetype="text/csv")` con `Content-Disposition` del contrato y `charset=utf-8`.
  4. `hedge_fixture.py` con las ayudas del Contexto (sin tests; no importa nada de los stubs).
  5. Tests: `UPDATE`/`DELETE` por SQL directo sobre `hedge_events`, `hedge_periods` y `hedge_relationships` (filas insertadas por SQL) → `sqlite3.DatabaseError`; una base del corte 2 (crear la app, borrar por SQL las tres tablas nuevas y sus disparadores, volver a llamar `create_app` sobre la misma ruta) recupera las tres tablas sin perder operaciones; `GET /api/hedges` → `{"hedges": []}`; con una relación y un evento `designation` insertados por SQL, `GET /api/hedges/<id>` devuelve la forma de detalle con `status` `activa`, `oci_balance` 0 y `last_close` null, y `GET /api/hedges?trade_id=<otro>` la excluye; id `abc` → 404 `field:"id"`; `STUB_ROUTES`: lista de rutas que dan 501 JSON mientras sus módulos sean stub (`POST /api/hedges`, `POST …/periods`, `POST …/dedesignate`, `GET …/effectiveness?snapshot=MX-DEMO`, `GET …/report`) — **quien implemente una ruta borra solo su fila** (releer el archivo antes de editar).
- **Verificación:** `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests/test_hedges_schema.py -q 2>&1 | grep -E "passed|failed"` y suite backend completa sin `failed`.
- **Commit:** las nueve rutas.

### T2 — Designación y derivado hipotético
- **Modelo:** sonnet · **Depende de:** T1 · **R:** R1, base de R2 (hipotético vale 0 al designar)
- **Objetivo:** `POST /api/hedges` completo según el contrato, con el hipotético de D3 guardado en el evento `designation`.
- **Archivos:** `desk/api/hedges.py` (solo `build_hypothetical` y `create_hedge` y sus auxiliares privados), `desk/api/tests/test_hedges_designation.py` (nuevo), `desk/api/tests/test_hedges_schema.py` (solo borrar la fila de `POST /api/hedges` en `STUB_ROUTES`).
- **Pasos:** validación en el orden del contrato; `fixings.load_all` una vez; `build_hypothetical` según "Derivado hipotético"; `pv_inst`/`pv_hypo` con `value_trade`; `data_quality` del snapshot (`market.data_quality(market.sources_of(json.loads(row["data"])))` o de `list_snapshots`); insertar relación (`created_at = db.now_iso()`) y evento `designation`; devolver `public_relationship(load_relationship(...))`.
- **Tests:** alta válida `floating_loan` (operación nueva `par_irs` TIIE-F, crédito con las mismas fechas) → 201, un evento `designation`, `hypothetical.params.fixed_rate` = `par_rate`, `side` `payer` y `|pv_hypo| < 1e-6 × notional`; `fixed_loan` `pays_fixed` con `hedge_type` `fair_value` → 201, hipotético `receiver` a la par y `|pv_hypo| < 1e-6 × notional`; combinaciones inválidas → 400 `hedge_type` (`fair_value` + `floating_loan`, `fair_value` + `forecast_fx`, `cash_flow` + `fixed_loan`); `fixed_loan` con `side` `pays_floating` → 400 `side`; `forecast_fx` con `market_forward` → `|pv_hypo| < 1e-6 × amount_usd × spot`, `strike` = forward; SOFR también; cada error del contrato con su status y `field` (`trade_id` 404, `snapshot` 404, `designation_date` distinta 400, `hedge_type`/`item_kind` inválidos, `item_terms` no objeto, `notional` 0, `maturity_date ≤ start_date`, `date ≤ designation_date`, `irs` con `forecast_fx` → 400 `item_kind`, curva SOFR con índice TIIE-F → 400 `index`, `fraction` 0 / 1.0001 / `"x"`, `hedge_ratio` 0, `documentation` sin `hedged_risk` → 400 `hedged_risk`); operación `terminada` antes de la designación → 409 `trade_id`; operación con `trade_date` posterior al `as_of` → 409 `trade_id`; fracciones 0.6 + 0.5 → 409 `fraction` y 0.6 + 0.4 → 201; nada se inserta en un 4xx.
- **Verificación:** `… -m pytest desk/api/tests/test_hedges_designation.py -q | grep -E "passed|failed"`; suite completa sin `failed`.
- **Commit:** las tres rutas.

### T3 — Cierre de periodo: medición y asientos
- **Modelo:** sonnet · **Depende de:** T2 · **Paralela con:** T4 · **R:** R2, R3, R4, R5, R6, R8 (409 de cierre)
- **Objetivo:** `POST /api/hedges/<id>/periods` con la medición de D4 y los asientos de D5 guardados en `hedge_periods`.
- **Archivos:** `desk/api/hedge_measure.py`, `desk/api/tests/test_hedges_periods.py` (nuevo), `desk/api/tests/test_hedges_schema.py` (solo su fila de `STUB_ROUTES`).
- **Pasos:** reglas de "Cierre de periodo" y "Asientos" del Contexto; validaciones y 409 del contrato (estado por `lifecycle.state(trade, trade["events"], as_of)`); `data_quality` del snapshot en `result`; `insert_period` + evento `period_close` en una transacción; responde `public_period`.
- **Tests:**
  - **R2:** crédito TIIE-F `2026-11-10`→`+364 días` y `par_irs` idéntico; `D1 = roll(+35)`, `D2 = roll(+70)` con fijaciones TIIE-F cargadas; cierres en D1 y D2 → `ineffectiveness == 0` y `d_oci == d_inst_cum` (1e-6 × nocional) en ambos. Igual con `forecast_fx` + `market_forward` idéntico (cierre antes y en el vencimiento).
  - **R3:** sobrecubierto (`par_irs` nocional 1.2 × crédito, `hedge_ratio` 1) → `|oci| == |hypo_cum|` y `ineffectiveness == d_inst_cum − d_oci ≠ 0`; subcubierto (0.8) → `|oci| == |inst_cum|`, `ineffectiveness == 0`; signos opuestos (`par_irs` `receiver` contra crédito `pays_floating`) → `oci == 0`.
  - **R4:** `fraction = 0.5`; dos cierres; en cada periodo `Σdebit == Σcredit` al centavo (comparar `round(x*100)`), también el acumulado; `|identity_residual| ≤ 1e-6`; `d_inst_cum + settled_period == 0.5 × pnl` de la fila de esa operación en `GET /api/pnl?from=<prev>&to=<snap>` (1e-6).
  - **R5:** periodo con cupón del swap (D1 = +35 cruza el pago del día 28) → hay líneas `Efectivo` y `Resultados — partida cubierta (reciclaje)` por `round(settled_period, 2)`; forward de 20 días designado a mercado con FIX `USDMXN` cargado en su vencimiento, cierres en +10 y +35 → `oci == 0` al final y `Σ(ineffectiveness + recycled)` de los periodos == liquidación total `notional × (FIX − strike)` con signo (1e-6).
  - **R6:** `fixed_loan` `pays_fixed` cubierto en `fair_value` con un `par_irs` `receiver` idéntico; cierres en D1 (cruza un cupón) y D2 → `ineffectiveness == 0` (1e-6 × nocional) = neto de `Resultados — cobertura de valor razonable` sin la línea de liquidación; líneas `Derivado (valor razonable)`, `Partida cubierta — ajuste de valor razonable` y `Efectivo` contra `Resultados — cobertura de valor razonable` presentes; ninguna línea de ORI, inefectividad ni reciclaje; `oci == 0`; `Σdebit == Σcredit` al centavo.
  - **R8 (cierre):** snapshot con `as_of` igual o anterior al último cierre → 409 `snapshot`; operación con `termination` antes del `as_of` → 409 `snapshot`; `fx_forward` `vencida` → 201 con `pv_inst == 0` y `trade_status` `vencida`; un cierre posterior a ese cierre final → 409 `snapshot` (P12); snapshot inexistente → 404.
- **Verificación:** `… -m pytest desk/api/tests/test_hedges_periods.py -q | grep -E "passed|failed"`; suite completa sin `failed`.
- **Commit:** las tres rutas.

### T4 — Efectividad prospectiva
- **Modelo:** sonnet · **Depende de:** T2 · **Paralela con:** T3, T5 · **R:** R7
- **Objetivo:** `GET /api/hedges/<id>/effectiveness` con términos críticos y razones por escenario.
- **Archivos:** `desk/api/hedge_effectiveness.py`, `desk/api/risk/scenarios.py` (solo añadir `DEFAULT_SCENARIOS` y `shock`), `desk/api/tests/test_hedges_effectiveness.py` (nuevo), `desk/api/tests/test_hedges_schema.py` (solo su fila de `STUB_ROUTES`).
- **Pasos:** `DEFAULT_SCENARIOS` = exactamente los 8 de `desk/ui/src/screens/RiskScreen.tsx` (`TIIE-F ±50 pb` paralelo, `SOFR ±50 pb` paralelo, `TIIE-F steepener 25 pb`, `SOFR steepener 25 pb`, `USDMXN ±10 %` `fx_spot`), con esos `name`. `shock = _shock`. Reglas de "Efectividad prospectiva" del Contexto; respuesta del contrato.
- **Tests:** hipotético idéntico (`irs` TIIE-F y `fx_forward`) → todos `match` y todas las razones no nulas == 1 (1e-6), `economic_relationship` true; crédito con vencimiento distinto del swap → `maturity_date` `mismatch` con ambos valores y los demás `match`; `forecast_fx` `buy_usd` cubierto con un forward `sell` → `side` `mismatch` (y razones negativas, `economic_relationship` false); `fixed_loan` con swap idéntico → todos `match`, razones 1; `fraction = 0.5` con swap de nocional doble → `notional` `match`; escenarios SOFR sobre crédito TIIE-F → `ratio` null y fuera de `scenarios_counted`; signos opuestos → `economic_relationship` false; `snapshot` falta → 400; inexistente → 404; snapshot rodado tras el vencimiento → 409 `snapshot`.
- **Verificación:** `… -m pytest desk/api/tests/test_hedges_effectiveness.py desk/api/tests/test_risk_dv01_scenarios.py -q | grep -E "passed|failed"`; suite completa sin `failed`.
- **Commit:** las cuatro rutas.

### T5 — Desdesignación
- **Modelo:** sonnet · **Depende de:** T3 · **Paralela con:** T4 · **R:** R8, R1 (fracciones activas tras desdesignar)
- **Archivos:** `desk/api/hedges.py` (solo `dedesignate` y auxiliares privados), `desk/api/tests/test_hedges_dedesignation.py` (nuevo), `desk/api/tests/test_hedges_schema.py` (solo su fila de `STUB_ROUTES`).
- **Pasos:** reglas de `POST …/dedesignate` del contrato; `frozen_oci = oci_balance(rel)`; evento `dedesignation` con `event_date = date`; responde detalle.
- **Tests:** tras un cierre, desdesignar → 201, `status` `desdesignada`, evento con `frozen_oci` == `oci` del último cierre, `oci_balance` igual; nuevo cierre → 409 `id`; segunda desdesignación → 409 `id`; `date` anterior al último cierre → 409 `date`; `reason` vacío → 400 `reason`; fracción 1.0 desdesignada libera la operación: nueva designación con 1.0 → 201; `GET /api/hedges` refleja el estado.
- **Verificación:** `… -m pytest desk/api/tests/test_hedges_dedesignation.py -q | grep -E "passed|failed"`; suite completa sin `failed`.
- **Commit:** las tres rutas.

### T6 — Reporte por relación y CSV de asientos
- **Modelo:** sonnet · **Depende de:** T3, T4, T5 · **R:** R9
- **Archivos:** `desk/api/hedge_report.py`, `desk/api/tests/test_hedges_report.py` (nuevo), `desk/api/tests/test_hedges_schema.py` (borrar la última fila de `STUB_ROUTES` y, si queda vacía, el test esqueleto).
- **Pasos:** `build_report` con todas las secciones del contrato (documentación, prospectiva, periodos, asientos por periodo y totales, jerarquía con la procedencia de cada snapshot usado, reserva y `notice`); `report_csv` del contrato.
- **Tests:** relación con dos cierres → todas las claves del contrato presentes, `notice` exacto, `fair_value_hierarchy.level == 2` y un `data_quality` por snapshot (designación + periodos); `entries_total` cuadra; CSV: encabezado exacto, `Content-Type` `text/csv`, `Content-Disposition` con el nombre, Σdebit == Σcredit al centavo leyendo con `csv.reader`, filas == número de asientos; desdesignada → `reserve.frozen` true con `FROZEN_NOTE`; `format=xml` → 400 `format`; con un snapshot posterior al vencimiento en `?snapshot=` → 200 con `prospective.error`.
- **Verificación:** `… -m pytest desk/api/tests/test_hedges_report.py desk/api/tests/test_hedges_schema.py -q | grep -E "passed|failed"`; suite completa sin `failed`.
- **Commit:** las tres rutas.

### U1 — Contrato en la interfaz: tipos, cliente, rutas, navegación y stubs
- **Modelo:** sonnet · **Depende de:** — (en paralelo con T1) · **R:** R10 (base)
- **Archivos:** `desk/ui/src/api/types.ts`, `desk/ui/src/api/client.ts`, `desk/ui/src/api/client.test.ts`, `desk/ui/src/App.tsx`, `desk/ui/src/components/Shell.tsx`, `desk/ui/src/components/Shell.test.tsx`, `desk/ui/src/components/AccountingNotice.tsx` (nuevo, real), `desk/ui/src/components/AccountingNotice.css` (nuevo), `desk/ui/src/lib/hedgeLabels.ts` (nuevo), `desk/ui/src/screens/HedgesScreen.tsx`, `desk/ui/src/screens/HedgeScreen.tsx`, `desk/ui/src/screens/HedgeReportScreen.tsx` (los tres stubs `export default function X() { return <section data-testid="x-stub"><AccountingNotice /></section> }`).
- **Pasos:** transcribir "Interfaz: piezas fijas" y el contrato HTTP; tres rutas; entrada de navegación; la banda con el texto exacto.
- **Tests:** `client.test.ts`: `listHedges({trade_id: 3})` llama `/api/hedges?trade_id=3`; `createHedge(b)` envía `POST /api/hedges` con el cuerpo; `closeHedgePeriod(1,'D1')` envía `{"snapshot":"D1"}` a `/api/hedges/1/periods`; `dedesignateHedge` y `hedgeEffectiveness(1,'MX-DEMO')` con su URL; `hedgeReportCsvUrl(2)` == `/api/hedges/2/report?format=csv`; 409 → `ApiError` con `status 409` y `field`. `Shell.test.tsx`: la lista de enlaces pasa a seis con 'Coberturas' antes de 'Metodología' (renombrar el `it` a "las seis pantallas").
- **Verificación:** `cd desk/ui && npm test 2>&1 | tail -5 && npm run build 2>&1 | tail -5` sin errores.
- **Commit:** las rutas listadas.

### U2 — Lista y alta de relaciones
- **Modelo:** sonnet · **Depende de:** U1 · **Paralela con:** U3–U6 · **R:** R10 (lista, alta, banda)
- **Archivos:** `desk/ui/src/screens/HedgesScreen.tsx`, `desk/ui/src/screens/HedgesScreen.css` (nuevo), `desk/ui/src/screens/HedgesScreen.test.tsx` (nuevo).
- **Pasos:** encabezado "Coberturas" + `<AccountingNotice />`; tabla (`listHedges()`): id (enlace a `/coberturas/<id>`), operación (`#trade_id · producto · contraparte`, enlace a `/portafolio/<trade_id>`), tipo, partida, fracción (%), estado, último cierre, saldo de reserva (`fmtMoney`); vacío: "Sin relaciones de cobertura". Botón "Nueva relación" abre formulario en línea: operación (select de `listTrades()`: `#id · producto · contraparte`), tipo, partida (`item_kind`, solo las de `VALID_ITEM_KINDS[tipo]`; al cambiar el tipo se elige la primera válida) y sus términos según la partida (`floating_loan`/`fixed_loan`: índice, nocional, inicio, vencimiento, lado con sus opciones de `SIDE_LABEL`; `forecast_fx`: monto USD, fecha, lado), fracción (en %, envía decimal), razón (default 1), los cuatro campos de documentación (método prellenado con `DEFAULT_EFFECTIVENESS_METHOD`); envía `snapshot` = snapshot activo. Errores 400/404/409 bajo el campo cuyo `field` coincida (incluidas claves de `item_terms` y `documentation`); sin campo, como banda. Al crear, navega a `/coberturas/<id>`.
- **Tests:** la lista muestra estado y saldo; el formulario `floating_loan` envía `{trade_id, snapshot, hedge_type, item_kind:'floating_loan', item_terms:{index, notional, start_date, maturity_date, side}, fraction:0.5 (al capturar 50), hedge_ratio:1, documentation:{…}}`; cambiar a `forecast_fx` muestra sus campos; elegir tipo "Valor razonable" deja solo "Crédito a tasa fija" con lados Paga fija / Cobra fija; 409 `field:"fraction"` aparece bajo Fracción; la banda está presente.
- **Verificación:** `npm test` y `npm run build` sin errores.
- **Commit:** las tres rutas.

### U3 — Detalle de relación: términos, escenarios, periodos, asientos, cierre, desdesignación, exportar
- **Modelo:** sonnet · **Depende de:** U1 · **Paralela con:** U2, U4–U6 · **R:** R10 (detalle, cierre, desdesignación, exportación)
- **Archivos:** `desk/ui/src/screens/HedgeScreen.tsx`, `desk/ui/src/screens/HedgeScreen.css` (nuevo), `desk/ui/src/screens/HedgeScreen.test.tsx` (nuevo).
- **Pasos:** lee `:id`; carga `getHedge(id)` y `hedgeEffectiveness(id, snapshotId)` (se recarga al cambiar de snapshot; un 409 se muestra en la sección como texto, no rompe la pantalla). `<AccountingNotice />` arriba. Cabecera: tipo, partida, operación (enlace), fracción, razón, fecha de designación, estado, saldo de reserva (si desdesignada: "Reserva congelada" y la fecha y motivo). Secciones: Documentación (cuatro campos con `DOC_FIELD_LABEL`); Términos críticos (tabla término / instrumento / partida / resultado con `TERM_RESULT_LABEL`); Escenarios (nombre, Δ instrumento, Δ partida, razón con 4 decimales o "—", fila resumen "Relación económica: sí/no" y "En 80 %–125 %: n de m" con `reference_note`); Periodos: en `cash_flow` (as_of, snapshot, Δ instrumento, Δ ORI, inefectividad, reciclaje, saldo ORI); en `fair_value` (as_of, snapshot, Δ instrumento, ajuste de partida, inefectividad, liquidado, resultado del periodo = `fv_result`), sin columnas de ORI; Asientos por periodo (cuenta, cargo, abono, memo; total por periodo). Acciones si `activa`: "Cerrar periodo" (select de snapshots `label · as_of`, default el activo) → `closeHedgePeriod` → recarga; "Desdesignar" (fecha + motivo) → `dedesignateHedge` → recarga; errores por campo o banda. Siempre: "Exportar asientos (CSV)" = `<a href={hedgeReportCsvUrl(id)} download>` y "Vista imprimible" enlace a `/coberturas/<id>/reporte`. Tablas sin desborde horizontal a 1280 px (contenedor con `overflow-x: auto` solo en la tabla).
- **Tests:** con mocks: términos con un `mismatch` rotulado "No coincide"; razón `null` muestra "—"; cerrar periodo llama `closeHedgePeriod(1, 'D1')`; desdesignar llama `dedesignateHedge(1, {date, reason})`; relación `desdesignada` no muestra acciones y sí "Reserva congelada"; una `fair_value` no muestra columnas de ORI; el enlace CSV apunta a `/api/hedges/1/report?format=csv`; la banda está.
- **Verificación:** `npm test` y `npm run build` sin errores.
- **Commit:** las tres rutas.

### U4 — Vista imprimible del reporte
- **Modelo:** sonnet · **Depende de:** U1 · **Paralela con:** U2, U3, U5, U6 · **R:** R10 (vista imprimible), R9 (presentación)
- **Archivos:** `desk/ui/src/screens/HedgeReportScreen.tsx`, `desk/ui/src/screens/HedgeReportScreen.css` (nuevo), `desk/ui/src/screens/HedgeReportScreen.test.tsx` (nuevo).
- **Pasos:** `hedgeReport(id)`; documento en una columna: título "Reporte de relación de cobertura #id", `<AccountingNotice />`, Documentación de designación (incluye partida e instrumento descritos con `hedgeLabels`), Prueba prospectiva (o su `error`), Periodos, Asientos por periodo y Acumulado (`entries_total`), Jerarquía de valor razonable ("Nivel 2" + `basis` + tabla snapshot/rol/fecha/`qualityText(data_quality)`), Reserva (saldo y nota si congelada), fecha de generación. Botón "Imprimir" (`window.print()`, oculto al imprimir) y enlace "Volver". CSS `@media print` en este archivo: oculta `.shell__sidebar` y `.shell__topbar`, `.shell__main` a ancho completo, fondo blanco, tablas sin cortes de fila (`break-inside: avoid`).
- **Tests:** con mock: aparecen las secciones (encabezados), "Nivel 2" y la procedencia; la banda está; el botón llama `window.print` (espía); un reporte con `prospective.error` lo muestra como texto.
- **Verificación:** `npm test` y `npm run build` sin errores.
- **Commit:** las tres rutas.

### U5 — La ficha de operación indica la designación
- **Modelo:** haiku · **Depende de:** U1 · **Paralela con:** U2–U4, U6 · **R:** R10 (ficha indica designación)
- **Archivos:** `desk/ui/src/screens/TradeScreen.tsx`, `desk/ui/src/screens/TradeScreen.test.tsx`.
- **Pasos:** además de lo que ya carga, `listHedges({trade_id: id})`; si hay relaciones, en la cabecera una línea por relación: "Designada como cobertura #<id> · <HEDGE_TYPE_LABEL> · <fracción en %> · <HEDGE_STATUS_LABEL>" enlazada a `/coberturas/<id>`; si no hay, nada. Un error de esa llamada no rompe la ficha (no se muestra la línea). No cambiar nada más.
- **Tests:** con mock de una relación activa aparece el texto y el enlace a `/coberturas/1`; sin relaciones no aparece "Designada"; ajustar los mocks existentes para que `listHedges` devuelva `[]`.
- **Verificación:** `npm test` y `npm run build` sin errores.
- **Commit:** las dos rutas.

### U6 — Metodología de coberturas
- **Modelo:** haiku · **Depende de:** — (solo toca `MethodologyScreen`; en paralelo con todo) · **R:** R11, D10
- **Archivos:** `desk/ui/src/screens/MethodologyScreen.tsx`, `desk/ui/src/screens/MethodologyScreen.test.tsx`.
- **Pasos:** nuevo grupo `<h2 className="meth-group">Contabilidad de coberturas (IFRS 9)</h2>` con una sección (`SectionBlock`, id `coberturas`) cuyos ítems (label → texto en español) son: **Revisión contable** (el texto exacto de `NOTICE` y que nadie la ha hecho aún); **Asientos sugeridos** (el sistema no es el libro mayor ni sustituye al contador; cuentas fijas; redondeo a centavos con el residuo en resultados por inefectividad); **Derivado hipotético** (la partida se representa con un swap a la par del crédito o un forward al forward de mercado del flujo, valuados con el mismo motor y en 0 al designar); **Regla del menor** (la reserva ORI es el menor en valor absoluto entre el cambio acumulado del instrumento —por la fracción— y el del hipotético, si tienen el mismo signo; si no, 0; el resto es inefectividad); **Reciclaje** (las liquidaciones del derivado en el periodo se reconocen en resultados como el flujo cubierto ocurrido; al vencer, el PV es 0 y la reserva queda en 0); **Valor razonable** (solo para crédito o deuda a tasa fija cubierto con un swap; el cambio del instrumento, el ajuste de la partida —cambio del hipotético con signo contrario— y lo liquidado van a la cuenta Resultados — cobertura de valor razonable; sin reserva); **Combinaciones admitidas** (flujo de efectivo: crédito a tasa variable con swap del mismo índice o flujo pronosticado en USD con forward; valor razonable: crédito a tasa fija con swap del mismo índice); **Cambios de nocional** (un cambio de nocional del instrumento después de designar no tiene tratamiento especial: la medición usa el nocional vigente); **Efectividad prospectiva** (términos críticos y escenarios del escritorio; relación económica si todas las razones son positivas; el rango 80 %–125 % es solo referencia, IFRS 9 no fija umbral); **Jerarquía de valor razonable** (Nivel 2 para todos los instrumentos, con la procedencia del snapshot); **Desdesignación** (congela la reserva, que se recicla cuando ocurra el flujo cubierto; no admite más cierres); **Simplificaciones** (sin costo de cobertura ni valor temporal de opciones; sin riesgo de crédito en la medición; sin ajuste de base para partidas no financieras; sin reequilibrio de la razón de cobertura); **Fuera de alcance** (opciones como instrumento, coberturas de inversión neta, designación de componentes de riesgo, libro mayor y pólizas reales, revelaciones de IFRS 7).
- **Tests:** con el helper `row(label)`: "Regla del menor" contiene "menor"; "Valor razonable" contiene "tasa fija"; "Cambios de nocional" existe; "Reciclaje" contiene "liquidaciones"; "Simplificaciones" contiene "costo de cobertura", "riesgo de crédito", "ajuste de base" y "reequilibrio"; "Revisión contable" contiene el texto exacto de la banda; "Derivado hipotético" existe.
- **Verificación:** `npm test` y `npm run build` sin errores.
- **Commit:** las dos rutas.

### T7 — Integración contra el backend real y capturas
- **Modelo:** sonnet · **Depende de:** todas · **R:** R10 (1280 px, textos), R12, verificación de R1–R11 de punta a punta
- **Archivos:** ninguno nuevo; solo correcciones puntuales donde falle algo (commit de esas rutas). Respuestas en `/tmp/fableorchestrate/qf-corte4/it/`, capturas en `/tmp/fableorchestrate/qf-corte4/shots/` (no se commitean).
- **Pasos:**
  1. Las cuatro suites → verde; reportar conteos.
  2. `rm -f /tmp/fableorchestrate/qf-corte4/it.db`; `cd desk/ui && npm run build`; backend en **5071** con esa base (comando del Contexto) en segundo plano, guardar el PID; esperar el puerto.
  3. Recorrido por `curl`: rodar `MX-DEMO` a `+35` (`D1`) y `+70` (`D2`); fijaciones TIIE-F diarias hábiles de `MX-DEMO.as_of` a `D2.as_of − 1` y un FIX `USDMXN` en el vencimiento de un forward de 20 días; crear un `irs` TIIE-F a la par con fechas de crédito y un `fx_forward` a mercado; designar ambos (`cash_flow`); `effectiveness?snapshot=MX-DEMO` (todas `match`, razones 1); cerrar en `D1` y `D2`; comprobar Σcargos = Σabonos por periodo y la identidad contra `/api/pnl`; desdesignar el swap y comprobar 409 al cerrar otra vez; `report` JSON y `?format=csv` (sumas iguales); designar un `fixed_loan` en `fair_value` con un swap `receiver` a la par y cerrarlo (inefectividad 0); comprobar que `fair_value` + `floating_loan` da 400 `hedge_type`; cerrar el forward en su vencimiento y comprobar 409 al cerrar otra vez.
  4. Capturas a 1280×800 con Chrome headless propio: `google-chrome --headless=new --disable-gpu --window-size=1280,800 --screenshot=<png> http://127.0.0.1:5071/<ruta>` de `/coberturas`, `/coberturas/<id>` (con periodos y asientos), `/coberturas/<id>/reporte`, `/portafolio/<trade_id>` (línea "Designada…"), `/metodologia` (desplazarse no es posible en headless: además una captura con `--window-size=1280,3000`). Si hace falta el alta en pantalla, usar Claude in Chrome solo para recorrerla, sin dependencias nuevas. Revisar cada captura con `Read`: banda visible, textos en español, sin desborde horizontal ni texto cortado; lo no comprobable se reporta como no verificado. Imprimir a PDF la vista de reporte (`--print-to-pdf=<pdf>`) y confirmar que no salen la barra lateral ni la superior.
  5. Detener el servidor con `kill <PID>` (nunca `pkill -f`). `git status --short` limpio salvo `graphify-out/`.
  6. Último commit (correcciones o `git commit --allow-empty -m "test(desk): integración del corte 4 …"`) **sin** `GRAPHIFY_SKIP_HOOK` para que el hook regenere el grafo una vez; no añadir `graphify-out/` salvo que Fable lo pida.
- **Verificación:** reporte con cada comando y su resultado, rutas de capturas y PDF, y lista de correcciones.

---

## Orden y paralelismo

```
T1 ── T2 ──┬─ T3 ── T5 ──┐
           └─ T4 ────────┴─ T6 ──┐
U1 ──┬─ U2, U3, U4, U5 (paralelas, archivos disjuntos)  ├─ T7 (tras todo)
U6 (en cualquier momento) ───────────────────────────────┘
```
- Grupo A (inmediato): **T1, U1, U6**.
- Grupo B: **T2** (tras T1) junto con **U2, U3, U4, U5** (tras U1).
- Grupo C: **T3 y T4** (tras T2). T4 y T5 también pueden coincidir.
- Grupo D: **T5** (tras T3), **T6** (tras T3, T4, T5).
- **T7** al final, sola.
Archivos compartidos: `test_hedges_schema.py` (cada tarea borra solo su fila de `STUB_ROUTES`, releyendo antes); `hedges.py` lo tocan T1, T2 y T5 en serie (T5 tras T3, que no lo toca).

## Cobertura de requisitos

| R | Tareas |
|---|---|
| R1 | T1 (disparadores), T2, T5 (fracciones activas) |
| R2 | T2 (hipotético en 0), T3 |
| R3 | T3 |
| R4 | T3 |
| R5 | T3 |
| R6 | T3 (`fixed_loan`), T2 (combinaciones) |
| R7 | T4 |
| R8 | T3 (cierres 409), T5 |
| R9 | T6, U4 |
| R10 | U1–U5, T7 |
| R11 | U6 |
| R12 | todas (suite verde por tarea), T7 |

## Preguntas para Fable

P1–P15 respondidas en "Aclaraciones de Fable al plan" del diseño e incorporadas al Contexto y a T2, T3, T4, U1, U2, U3, U6 y T7 (P4: `fixed_loan` y cuenta `Resultados — cobertura de valor razonable`; P11: se compara el sentido; P12: nada después del cierre final). No queda nada abierto.

## T8 — Correcciones de backend tras la auditoría — modelo sonnet

Implementa C1–C7 (lo que toque backend) de la sección "Correcciones tras la auditoría (decisiones de Fable)" de `/tmp/fableorchestrate/qf-corte4/design.md`. Archivos: `desk/api/hedges.py`, `hedge_measure.py`, `hedge_effectiveness.py`, `hedge_report.py`, `routes/hedges.py`, `db.py` (solo si hace falta ampliar el catálogo de tipos de evento en un CHECK; con migración idempotente si la tabla ya existe), `tests/hedge_fixture.py` y los tests de coberturas. Cada punto con sus tests (incluidos: designación con fecha anterior al último evento → 409; el caso 150 % del auditor ya no es posible; desdesignar con snapshot posterior al último cierre crea el cierre y congela ese saldo; sobrecubierto 120 % con cupones liquidados: `reciclaje` = lo liquidado del hipotético y el exceso en inefectividad; subcubierto 80 %; cierre final deja reserva 0 y acumulado de asientos de `ORI` y `Derivado` exactamente 0.00; liberación total y parcial, tope y signo; cada aviso de designación; término `side` en créditos). Actualiza los ejemplos y contratos del `## Contexto` de este plan que cambien (ruta de desdesignación, ruta nueva de liberación, campos nuevos del periodo: `inst_total`, `hypo_total`, `effective_cum`, `hypo_settled_period`, y `warnings` de designación) y anota al final del plan, en una sección "Anotado tras T8", las formas reales para la tarea de interfaz. Verificación: `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q | grep -E "passed|failed"` sin `failed`.

## U7 — Correcciones de interfaz tras la auditoría — modelo sonnet (después de T8)

Implementa C8 y la parte de interfaz de C2, C5, C6 y C7 (Metodología y reporte) según el diseño y la nota "Anotado tras T8": tipos y cliente (`dedesignateHedge(id, {snapshot, reason, cause})`, `releaseHedgeReserve(id, {snapshot, amount?, cause})`), `HedgeScreen`, `HedgesScreen`, `HedgeReportScreen`, `MethodologyScreen`, `hedgeLabels.ts` y sus tests. Verificación: `npm test` y `npm run build` sin fallos; después levanta el backend real en 5071 con base temporal y comprueba con Chrome headless propio (no el 9222) el alta con avisos, un cierre, desdesignar con snapshot y liberar la reserva, a 1280 px y sin errores de consola; apaga todo.


### Anotado tras T8 (backend, commit bf8f948; `desk/api` = 2335 tests)
Formas reales para U7 (el `## Contexto` ya trae los contratos actualizados; esto resume lo que la interfaz debe cambiar).

**Rutas y cuerpos**
- `POST /api/hedges/<id>/dedesignate` cuerpo **`{snapshot, reason, cause}`** (ya no `date`; un `date` suelto sin `snapshot` da 400 `snapshot`). `cause` ∈ `instrument_ended` | `criteria_not_met` | `risk_objective_changed`. 201 → detalle; si el snapshot es posterior al último cierre, `periods` trae un periodo nuevo y `dedesignation.frozen_oci` es el de ese cierre. Errores: 400 `snapshot`/`reason`/`cause`; 404 `snapshot`/`id`; 409 `id` (ya desdesignada); 409 `snapshot` (anterior al último cierre o a la designación; operación terminada/ejercida o último cierre ya final: el mensaje manda a usar el snapshot del último cierre). Con el snapshot del último cierre (o el de la designación) no se mide de nuevo.
- `POST /api/hedges/<id>/release` cuerpo **`{snapshot, amount?, cause}`**, `cause` ∈ `flow_occurred` (ORI contra "Resultados — partida cubierta (reciclaje)") | `flow_no_longer_expected` (ORI contra "Resultados — inefectividad de cobertura"). `amount` **con el signo del saldo** (`oci_balance`; el saldo puede ser negativo); omitido = todo el saldo; un monto a ±0.005 del saldo cuenta como todo. 201 → detalle. Errores: 400 `snapshot`/`cause`/`amount` (no número, o < 0.005 en valor absoluto); 404 `snapshot`/`id`; 409 `id` (relación no desdesignada, o sin reserva vigente); 409 `snapshot` (anterior al último evento); 409 `amount` (signo contrario o mayor que el saldo). Mostrar el botón solo en `status == "desdesignada"` con `|oci_balance| ≥ 0.005`.
- `POST /api/hedges`: nuevo 409 con `field: "snapshot"` (fecha de designación anterior al último evento de una relación de la misma operación; el mensaje cita la fecha y la cobertura `#n`) además del 409 `fraction`. La respuesta 201 y el detalle traen **`warnings: [{code, message}]`** (`no_economic_relationship`, `instrument_off_market`, `forecast_date_weekend`; `message` ya está en español y se puede mostrar tal cual; puede ser `[]`). Los avisos viven también en `events[0].data.warnings`.

**Detalle** (`GET /api/hedges/<id>` y las tres respuestas de escritura)
- `dedesignation`: `{date, reason, cause, snapshot, frozen_oci}` (`cause`/`snapshot` pueden ser `null` solo en datos anteriores a C2).
- `oci_balance` es la reserva **vigente** (congelado − liberado); `dedesignation.frozen_oci` queda como lo congelado. También en el resumen de `GET /api/hedges`.
- `events` puede traer `type: "reserve_release"` con `data = {snapshot, cause, amount, reserve_before, reserve_after, entries: [{account, debit, credit, memo}, …]}` y `event_date` = `as_of` del snapshot. Agregar `reserve_release` a `HEDGE_EVENT_LABEL` ("Liberación de reserva") y a los tipos TS.
- Periodo: campos nuevos `inst_total`, `hypo_total`, `effective_cum`, `hypo_settled_period` (todos MXN; en valor razonable `effective_cum = 0`). `recycled` ahora es la parte efectiva de lo liquidado (puede ser menor que `settled_period` en sobrecubiertos); `ineffectiveness` incluye el exceso liquidado; en el cierre final (`trade_status: "vencida"`) `oci = 0`.

**Efectividad** (`critical_terms`): los créditos (`floating_loan`/`fixed_loan`) traen un quinto término `side` ("Sentido") con `instrument` = `"payer"` | `"receiver"` (lado del swap) e `item` = `pays_floating` | `receives_floating` | `pays_fixed` | `receives_fixed`. `SIDE_LABEL` necesita `payer` ("Paga fija") y `receiver` ("Cobra fija"). En `forecast_fx` el término `side` ya existía (`buy|sell` frente a `buy_usd|sell_usd`).

**Reporte** (`GET …/report`): claves nuevas `reserve_releases: [{id, snapshot, as_of, cause, amount, reserve_after, entries}]` y `reserve.released` (Σ liberado); `reserve.balance` es la vigente; `reserve.note` solo si desdesignada **y** |saldo| ≥ 0.005 (tras liberar todo ya no sale). `entries_total` incluye las liberaciones. `relationship` (detalle sin events/periods) lleva `warnings` y `dedesignation.cause`. CSV: mismas columnas; las filas de liberación van al final con `period_id` vacío.

**Decisiones que la especificación no cerraba (conservadoras; ver también el reporte de T8)**
1. Desdesignar con un snapshot posterior al último cierre cuando la operación ya terminó/se ejerció, o cuando el último cierre ya fue el final (`vencida`): 409 `snapshot` en vez de congelar un saldo sin medir; siempre existe la salida de desdesignar con el snapshot del último cierre (o de la designación). La interfaz debería ofrecer esos snapshots si recibe ese 409.
2. `amount` de la liberación es con signo del saldo (la especificación dice "no puede cambiarle el signo"); fuera de rango es 409 `amount`, no 400.
3. Cierre final (`vencida`) con el hipotético aún vivo (partida más larga que el instrumento): el reciclaje se ajusta igualmente para dejar la reserva en 0 (C3 literal).
4. Una relación con periodos guardados antes de T8 (sin `inst_total`/`hypo_total`/`effective_cum`/`hypo_settled_period`) no puede cerrar periodos nuevos (KeyError): no se migró porque el corte 4 no está publicado.
5. C7 (declaraciones) es solo de interfaz: el backend no devuelve textos de metodología; el aviso `instrument_off_market` ya dice que el valor inicial ya está en libros y es fuente de inefectividad.
