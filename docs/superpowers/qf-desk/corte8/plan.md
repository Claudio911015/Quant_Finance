# Plan: QF Desk — Corte 8 (alcance reducido): fijaciones reales, respaldo y carga por pantalla

Diseño: `/tmp/fableorchestrate/qf-corte8/design.md`. Repositorio **`/home/claudio/Git/Quant_Finance`**, rama **`feat/qf-desk`** (base `142f0c4`). Se trabaja en el árbol principal (no hay worktree de este corte).

## Contexto

Todo implementador lee esta sección completa y solo su tarea. Las respuestas de Fable a las preguntas del plan (final de `design.md`) ya están incorporadas aquí y mandan sobre cualquier otra lectura del diseño.

### Entorno y convivencia
- **Otro agente trabaja a la vez en este mismo árbol** sobre `src/instruments/swaption.cpp`, `tests/test_swaption.cpp` y `desk/validation/`. Nadie de este corte lee, edita, añade ni commitea esos archivos. `git status` mostrará cambios suyos (y de `graphify-out/`, `docs/`): ignóralos. T7 solo se lanza cuando ese agente ya terminó; para entonces no hay fallos ajenos aceptables.
- **Python del backend:** `/home/claudio/anaconda3/bin/python` (3.8; Flask vive en `~/.local`, ejecutar sin `-I`). Sintaxis 3.8: nada de `match`, `X | Y`, `list[int]` en tiempo de ejecución; usar `typing`. **Sin dependencias nuevas** (ni pip ni npm).
- **Node** 22 / npm 10; `desk/ui/node_modules` ya instalado. UI: Vite 8 (empaquetador rolldown), React 18, react-router-dom 7, vitest 5 + jsdom.
- **Puertos:** el desk de Claudio usa **5070**: nadie arranca nada ahí ni toca `~/Git/MarketDataFeed`. Backend de prueba en **5088** con base temporal; Chrome headless con CDP en **9348**. Todo proceso que se levante se apaga con `kill <PID>` (nunca `pkill -f`).
- **No tocar:** `desk/data/`, `graphify-out/`, `docs/`, `build/` (salvo que la tarea final lo compile), `src/instruments/swaption.cpp`, `desk/validation/`.

### Commits
- Un commit por tarea, solo tus rutas: `git add <rutas> && GRAPHIFY_SKIP_HOOK=1 git commit -m "<tipo>(desk): <por qué, en español>" -- <rutas explícitas>`. Nunca `git add -A`/`.`, nunca `git stash`, nunca push ni merge. Autor = configuración global. **Sin `Co-Authored-By`** ni otra línea de atribución. Sin `graphify-out/` ni `docs/`.
- Si falla por `.git/index.lock` (el otro agente también commitea), esperar y reintentar; no borrar el lock salvo > 1 min sin proceso git vivo.
- Archivos compartidos con cortes anteriores (`desk/api/app.py`, `desk/ui/src/App.tsx`, `client.ts`, `types.ts`, `MethodologyScreen.tsx`): añadir en bloques contiguos marcados `# corte 8` / `# fin corte 8` (`// corte 8` en TS), como los cortes 5–7. Excepción: T5 reescribe los `import` de pantallas de `App.tsx` (es el objeto de R5).

### Suites (desde la raíz del repo salvo vitest)
- Backend: `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q 2>&1 | grep -E "passed|failed"` → `N passed`, sin `failed` (no usar `tail`: un warning de pytest_asyncio sale tras el resumen).
- Bindings: `cmake --build build --target pytests 2>&1 | tail -3` → `OK`.
- C++: `cd build && ctest 2>&1 | tail -3` → `100% tests passed`. `build/` es compartido con el agente de swaption: solo T7 lo corre, cuando ese agente ya terminó.
- UI: `cd desk/ui && npm test 2>&1 | grep -E "Test Files|Tests "` sin `failed`, y `npm run build 2>&1 | tail -15` sin errores.
- Tamaño del trozo de entrada (R5): tras `npm run build`, `ls -l desk/ui/dist/assets/index-*.js` → el `.js` que referencia `desk/ui/dist/index.html` con `<script type="module">` pesa ≤ 512000 bytes (500 kB). Hoy pesa 2 676 138.

### Backend: lo existente que se reusa (firmas reales)
- `desk/api/fixings.py`: `INDICES = ("TIIE-F", "SOFR", "USDMXN")`; tabla `fixings (index_name TEXT, fixing_date TEXT, value REAL, PRIMARY KEY(index_name, fixing_date))`, **sin columna de fuente** (por diseño: no hay migración). Unidades: `TIIE-F` y `SOFR` en **decimal** (0.0389 = 3.89 %); `USDMXN` en MXN por USD. Validación por fila: `_validate(body) -> (index, date, value)` (tasas `MIN_RATE ≤ v ≤ MAX_RATE`, USDMXN `0 < v ≤ MAX_PRICE`). No hay regla de fines de semana y no se añade: las fechas que publique la fuente se aceptan tal cual. Patrón de carga atómica a reusar: `import_csv(conn, text)` (valida todo, detecta conflictos, `executemany` al final). `list_fixings(conn, index, start, end)`, `load_all(conn)`.
- `desk/api/routes/fixings.py`: blueprint `bp` ya registrado en `app.py`; rutas `GET /api/fixings`, `POST /api/fixings`, `POST /api/fixings/csv` (patrón: `body_object()`, `get_conn()`, lógica en el módulo, `conn.commit()` en la ruta, `jsonify(ensure_finite(...))`).
- `desk/api/fred.py`: estilo a copiar — constantes `URL`, `TIMEOUT_S = 20`; `parse_x(text)` puro (lanza `ValueError` si no hay observaciones válidas) separado de `fetch_x(url)` que hace `urllib.request.urlopen(url, timeout=TIMEOUT_S)` y llama al parser. Sus pruebas (`desk/api/tests/test_fred.py`) simulan HTTP con `monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)` y un `FakeResponse` con `__enter__/__exit__/read`.
- `desk/api/refresh.py`: patrón de mapeo de fallos de red → `ApiError(502, "… no respondió: <motivo>")` capturando `(OSError, ValueError, http.client.HTTPException)` y `_why(e)`.
- `desk/api/errors.py`: hoy `ApiError(status, error, field=None)` → cuerpo `{"error", "field"}`. **Corte 8 lo amplía (T2):** `ApiError(status, error, field=None, code=None)`; el handler incluye `"code"` en el JSON **solo si se dio**. Los errores existentes no cambian de cuerpo.
- `desk/api/validation.py`: `iso_date(d, name, required=True) -> date` (400 con `field`), `choice(d, name, options)`, `body_object()`, `ensure_finite(obj)`.
- `desk/api/db.py`: `DEFAULT_DB_PATH = desk/data/desk.db` (ruta que usa `python -m desk.api.app`), `connect(path)` (row_factory `sqlite3.Row`), `init_schema(conn)`. Tablas con disparadores de solo inserción, p. ej. `trade_events_no_update` / `trade_events_no_delete` (`RAISE(ABORT, 'trade_events es solo de inserción')`).
- `desk/api/tests/conftest.py`: fixtures `app(tmp_path)` (`create_app(db_path=tmp_path/"t.db")`, sin red) y `client(app)`.

### Fuentes externas (comprobado el 2026-11-11)
- **NY Fed**: `GET https://markets.newyorkfed.org/api/rates/secured/sofr/search.json?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD` responde 200 con urllib y `User-Agent` por omisión. Cuerpo: `{"refRates": [{"effectiveDate": "2026-11-06", "type": "SOFR", "percentRate": 3.89, "percentPercentile1": …, "volumeInBillions": 3174, "revisionIndicator": ""}, …]}`, **en orden descendente** de fecha. `percentRate` está en **por ciento** → decimal = `round(percentRate / 100, 10)`.
- **Banxico SIE**: `GET https://www.banxico.org.mx/SieAPIRest/service/v1/series/<id>/datos/<from>/<to>` con cabecera `Bmx-Token`. Con token inválido responde **HTTP 400** (no 401) con cuerpo `{"error": {"mensaje": "Token inválido", …}}`. Cualquier 400/401/403 de Banxico se trata como token rechazado (ver la forma del 502 abajo). TIIE-F a decimal = `round(dato / 100, 10)`; FIX tal cual.
- **Mismo valor:** un valor de la fuente es "igual" al guardado si `abs(fuente - guardado) <= 1e-9`; si no, es conflicto. Formato de éxito según la documentación pública de SIE: `{"bmx": {"series": [{"idSerie", "titulo", "datos": [{"fecha": "dd/mm/aaaa", "dato": "18.4567"}]}]}}`; un dato faltante viene como `"N/E"`. Los identificadores de serie **no están verificados**: los verifica T1 en el catálogo público y los cita con URL; si no se puede, se declaran "sin verificar" en el README (R2).
- Las peticiones salientes solo llevan fechas e identificador de serie (y el token en cabecera para Banxico). El token se lee **solo** de `os.environ["BANXICO_TOKEN"]` y nunca se escribe en base, respuestas, excepciones ni logs (cuidado con mensajes de error que incluyan la `Request` o sus cabeceras).

### Forma de las respuestas nuevas
- `POST /api/fixings/fetch`, cuerpo `{"index": "SOFR"|"TIIE-F"|"USDMXN", "from": "YYYY-MM-DD", "to": "YYYY-MM-DD"}`:
  - 200: `{"index", "source", "from", "to", "fetched", "inserted", "unchanged", "conflicts": [{"date", "stored", "source"}]}`. `source` (de la respuesta) = `"Fed de Nueva York"` (SOFR) o `"Banxico (SIE)"` (TIIE-F, USDMXN). `fetched` = observaciones válidas que devolvió la fuente en el rango (tras omitir `N/E`) = `inserted + unchanged + len(conflicts)`. En cada conflicto, `stored` y `source` van en la unidad de la tabla (decimal para tasas).
  - Idempotente; un conflicto **no** sobrescribe y no aborta el resto: se inserta lo nuevo, se cuenta lo igual (tolerancia 1e-9), se lista lo distinto.
  - 400: `index` fuera de `INDICES`, fechas no ISO, `from > to`, rango > 366 días (con `field`).
  - 502: red, HTTP de error de la fuente o cuerpo ilegible → mensaje en español y **nada** insertado (todo o nada: descargar y parsear todo antes de escribir).
  - 502 de token rechazado (Banxico responde 400, 401 o 403): `{"error": "Banxico rechazó el token (BANXICO_TOKEN)", "field": null, "code": "banxico_token_rejected"}`.
  - 409 (solo Banxico sin `BANXICO_TOKEN`): `{"error": "Falta el token de Banxico (variable BANXICO_TOKEN)", "field": null, "code": "banxico_token_missing"}` (sin `field` culpable).
- `GET /api/fixings/sources` → `{"sources": [{"index", "source", "available", "reason", "last_date"}]}` en el orden de `fixings.INDICES` (`TIIE-F`, `SOFR`, `USDMXN`). `source` con los mismos textos de arriba; `available` = SOFR siempre `true`, Banxico `true` solo si hay `BANXICO_TOKEN`; `reason` = `null` si está disponible, si no `"Falta el token de Banxico (variable BANXICO_TOKEN)"`; `last_date` = `MAX(fixing_date)` del índice o `null`.
- `python -m desk.api.backup <destino_dir> [--keep N]` y `python -m desk.api.backup --restore <archivo> [--force]`; el CLI usa siempre `db.DEFAULT_DB_PATH` (**sin** flag `--db`); las funciones aceptan rutas para probarlas. Nombre de copia `qfdesk-YYYYMMDD-HHMMSS.sqlite`. Copia previa a restaurar: `<base>.antes-de-restaurar-YYYYMMDD-HHMMSS` junto a la base (p. ej. `desk.db.antes-de-restaurar-20261111-153000`). No se detecta si el servidor está encendido: el README indica restaurar con el servidor apagado.

### UI: lo existente que se reusa
- `desk/ui/src/App.tsx`: rutas `/mercado` (`MarketScreen`, export nombrado), `/pricers/:product` (`PricersScreen`, nombrado), `/portafolio` (`PortfolioScreen`, nombrado), `/portafolio/:id` (`TradeScreen`, default), `/riesgo` (`RiskScreen`, nombrado), `/coberturas` (`HedgesScreen`, default), `/coberturas/:id` (`HedgeScreen`, default), `/coberturas/:id/reporte` (`HedgeReportScreen`, default), `/metodologia` (`MethodologyScreen`, nombrado), `/operaciones` (`OpsScreen`, default), `/portafolio/:id/confirmacion` (`ConfirmationScreen`, default), `/validacion` (`ValidationScreen`, default). Envuelto en `<Shell>`. Menú (`Shell.tsx`, `NAV_ITEMS`): Mercado, Pricers, Portafolio, Riesgo, Coberturas, Operaciones, Metodología, Validación.
- Pesados: `echarts` (vía `src/components/EChart.tsx`, usado por Market, Risk, Portfolio, PnlPanel, pricers, risk/*), `ag-grid-community` (Pnl, Portfolio, Risk, Market, PricerForm).
- `desk/ui/src/App.test.tsx` hoy usa `getByRole` síncrono para `/metodologia`; con `React.lazy` pasa a `findByRole` (cambio justificado por R7).
- Fijaciones: `src/screens/FixingsPanel.tsx` (default export, montado sin props al final de `MarketScreen.tsx`), su `.css` y `.test.tsx` (mockea `../api/client`). Cliente `src/api/client.ts`: `request<T>(method, path, body?)` lanza `ApiError(status, message, field)` leyendo `error`/`field`. Tipos `FixingIndex`, `Fixing`, `FixingsCsvResult` en `src/api/types.ts`. `fmtDate`, `fmtRate`, `fmtNumber` en `src/lib/format.ts`. **Fecha de valuación activa** = `snapshot.as_of` del snapshot seleccionado, que el panel lee él mismo con `useSnapshot()` de `src/state/SnapshotContext.tsx` (`MarketScreen.tsx` no cambia). Si el rango queda vacío (última fijación ≥ fecha de valuación), el botón se muestra deshabilitado con el texto "Al día".
- Metodología → "Fuentes de datos": sección `id: 'fuentes'` en `src/screens/MethodologyScreen.tsx` (~línea 205), con `items: [{label, text}]`.

## Tareas

Paralelismo: **T1, T4 y T5 arrancan juntas** (archivos disjuntos). **T2** tras T1. **T3** tras T2 (y en paralelo con T4/T5 si siguen corriendo; archivos disjuntos con ambas). **T6** tras T1, T2 y T4. **T7** al final.

### T1 — Clientes NY Fed y Banxico (modelo: sonnet)
- **Objetivo:** dos módulos cliente con el estilo de `fred.py`: parser puro + fetch, sin dependencias. Capturar una respuesta real de la NY Fed como fixture.
- **Archivos:** `desk/api/nyfed.py`, `desk/api/banxico.py`, `desk/api/tests/test_nyfed.py`, `desk/api/tests/test_banxico.py`, `desk/api/tests/fixtures/nyfed_sofr.json` (nuevo), `desk/api/tests/fixtures/banxico_*.json` (simulados, forma de la doc SIE).
- **Pasos:**
  1. Guardar una vez una respuesta real (red autorizada para esto): `curl -s "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json?startDate=2026-10-27&endDate=2026-11-06" > desk/api/tests/fixtures/nyfed_sofr.json` (rango corto; comprobar que trae `refRates`).
  2. `nyfed.py`: constante de URL base, `TIMEOUT_S = 20`, `parse_sofr(text) -> List[Tuple[str, float]]` (fecha ISO, valor decimal `round(percentRate / 100, 10)`, ascendente; descarta filas sin `effectiveDate`/`percentRate` válidos o `type != "SOFR"`; cuerpo sin la clave `refRates` o ilegible → `ValueError`; lista vacía válida = sin datos en el rango) y `fetch_sofr(start, end)` que arma la URL solo con las dos fechas.
  3. `banxico.py`: constantes con los IDs de serie de TIIE de Fondeo a un día y FIX, **cada uno con comentario y URL del catálogo público de Banxico donde se verificó**; si no se pudo verificar, comentario `# sin verificar` y anotarlo en el reporte de la tarea. `parse_series(text)` (convierte `dd/mm/aaaa` → ISO, omite `"N/E"`, TIIE-F a decimal `round(dato / 100, 10)`, FIX tal cual, ascendente; cuerpo ilegible → `ValueError`) y `fetch_series(series_id, start, end, token)` que pone `Bmx-Token` en la cabecera. Ningún mensaje de excepción propio incluye el token.
  4. Pruebas con `urlopen` simulado (patrón de `test_fred.py`): parseo del fixture real (conteo, primera/última fecha, conversión a decimal redondeada a 10 decimales, p. ej. 3.89 → 0.0389 exacto, orden ascendente), URL exacta con fechas, timeout 20, cuerpo ilegible → `ValueError`, `N/E` omitido, cabecera `Bmx-Token` enviada, el token no aparece en `str()` de ninguna excepción propia. Sin red en la suite.
- **Verificación:** `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests/test_nyfed.py desk/api/tests/test_banxico.py -q 2>&1 | grep -E "passed|failed"` → `N passed`, sin `failed`; `grep -rn "urlopen" desk/api/tests/test_nyfed.py desk/api/tests/test_banxico.py | head -3` muestra el monkeypatch.
- **R:** R1 (cliente + fixture real), R2 (cliente, IDs citados).
- **Depende de:** nada.

### T2 — Orquestación `fetch` y rutas `fetch` / `sources` (modelo: sonnet)
- **Objetivo:** `POST /api/fixings/fetch` y `GET /api/fixings/sources` con la forma exacta de `## Contexto`.
- **Archivos:** `desk/api/fixings_fetch.py` (nuevo), `desk/api/routes/fixings.py` (añadir al final, bloque `# corte 8`), `desk/api/errors.py` (añadido mínimo), `desk/api/tests/test_fixings_fetch.py` (nuevo).
- **Pasos:**
  0. `errors.py`: `ApiError.__init__(self, status, error, field=None, code=None)` guarda `self.code`; el handler de `ApiError` añade `"code"` al JSON solo si `e.code` no es `None`. Prueba en `test_fixings_fetch.py` de que un error sin `code` sigue siendo exactamente `{"error", "field"}`.
  1. Validar cuerpo (`body_object`, `choice` con `fixings.INDICES`, `iso_date` para `from`/`to`; `from > to` o `(to - from).days > 366` → 400 con `field`).
  2. Despachar por índice: SOFR → `nyfed.fetch_sofr`; TIIE-F/USDMXN → si falta `os.environ.get("BANXICO_TOKEN")` → `ApiError(409, "Falta el token de Banxico (variable BANXICO_TOKEN)", code="banxico_token_missing")`; si no, `banxico.fetch_series`. `HTTPError` 400/401/403 de Banxico → `ApiError(502, "Banxico rechazó el token (BANXICO_TOKEN)", code="banxico_token_rejected")`. Otros fallos de red/HTTP/parseo → 502 en español (patrón `refresh._fetch_fx` + `_why`), sin tocar la base.
  3. Escribir: validar cada valor con `fixings._validate` (no duplicar rangos; fechas de la fuente tal cual), comparar con lo guardado con tolerancia `abs(a - b) <= 1e-9`, insertar solo lo nuevo en un `executemany`, contar `unchanged`, listar conflictos `{"date", "stored", "source"}` sin sobrescribir; `fetched = inserted + unchanged + len(conflicts)`; `conn.commit()` en la ruta. Ninguna escritura si algo falla antes.
  4. `sources`: `{"sources": [...]}` con un elemento por índice en el orden de `INDICES`, claves y valores exactos de `## Contexto`.
  5. Pruebas por la API con `client` y `urlopen` simulado sirviendo `fixtures/nyfed_sofr.json`: éxito, repetir = `inserted 0` y mismos valores, igualdad con tolerancia (fijación manual `0.0389` vs fuente 3.89 → `unchanged`), conflicto (fijación manual previa con otro valor → listada con `stored`/`source` y sin sobrescribir), `fetched` = suma, 400 por rango invertido / > 366 días / índice malo, 502 por `URLError` y por cuerpo ilegible con conteo de `fixings` sin cambio; Banxico: éxito con token (`monkeypatch.setenv`), token ausente (409, `code`, `field` null), 400 y 401 de Banxico (502 `banxico_token_rejected`, sin cambios en la base), `N/E` omitido, conflicto; el valor del token no aparece en ninguna respuesta (`assert token not in resp.get_data(as_text=True)`); `sources` con y sin token (forma exacta).
- **Verificación:** `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests/test_fixings_fetch.py desk/api/tests/test_fixings.py -q 2>&1 | grep -E "passed|failed"` → sin `failed`; después la suite backend completa sin `failed`.
- **R:** R1, R2, R3 (backend `sources`).
- **Depende de:** después de T1.

### T3 — Botón "Traer de la fuente" en Fijaciones (modelo: sonnet)
- **Objetivo:** en `FixingsPanel`, por índice, un botón "Traer de la fuente" (o, para Banxico sin token, el motivo en lugar del botón activo) que llama a `fetch` y muestra insertadas / sin cambio / conflictos.
- **Archivos:** `desk/ui/src/api/client.ts` y `desk/ui/src/api/types.ts` (bloques `// corte 8`: `fixingSources()`, `fetchFixings(body)` y sus tipos con la forma exacta de `## Contexto`), `desk/ui/src/screens/FixingsPanel.tsx`, `FixingsPanel.css`, `FixingsPanel.test.tsx`. `MarketScreen.tsx` no cambia.
- **Pasos:**
  1. Cargar `sources` al montar. Rango del botón: `to` = `useSnapshot().snapshot.as_of`; `from` = día siguiente a `last_date` del índice (o 30 días antes de `to` si `last_date` es `null`). Si `from > to`: botón deshabilitado con el texto "Al día". Si `available` es `false`: mostrar `reason` en lugar del botón activo.
  2. Al pulsar: deshabilitar mientras corre, mostrar `inserted`, `unchanged` y la lista de conflictos (fecha, guardado, fuente; tasas con `fmtRate`, USDMXN con `fmtNumber(v, 4)`); errores (`ApiError.message`) en el mismo patrón `Message` del panel; recargar la tabla y `sources` tras éxito.
  3. CSS sin anchos fijos que desborden; nada de desborde horizontal a 1280 px.
  4. Pruebas (vitest, mock de `../api/client` como el archivo actual; ahora el panel necesita contexto: envolver en `SnapshotProvider` con el cliente mockeado o mockear `../state/SnapshotContext` para dar un `snapshot.as_of` fijo): botón por índice disponible, motivo en vez de botón activo para Banxico sin token, rango enviado correcto (con y sin fijaciones previas), "Al día" deshabilitado cuando `last_date ≥ as_of`, resumen y conflictos visibles, error 502 mostrado tal cual. Las pruebas existentes del panel deben seguir pasando sin cambiar su resultado.
- **Verificación:** `cd desk/ui && npx vitest run src/screens/FixingsPanel.test.tsx 2>&1 | grep -E "Tests "` sin `failed`; `npx tsc -b 2>&1 | tail -3` sin errores.
- **R:** R3.
- **Depende de:** después de T2 (forma real de las respuestas). En paralelo con T4/T5.

### T4 — Respaldo y restauración (modelo: sonnet)
- **Objetivo:** `python -m desk.api.backup` según R4.
- **Archivos:** `desk/api/backup.py` (nuevo), `desk/api/tests/test_backup.py` (nuevo).
- **Pasos:**
  1. Funciones con la ruta de la base como parámetro (por omisión `db.DEFAULT_DB_PATH`) para poder probarlas con `tmp_path`; el `__main__` usa `argparse` solo con lo que pide R4 (`destino_dir`, `--keep N`, `--restore <archivo>`, `--force`).
  2. Respaldo: `sqlite3.connect(origen).backup(sqlite3.connect(copia))` a `qfdesk-YYYYMMDD-HHMMSS.sqlite` en `destino_dir` (crearlo si falta); `PRAGMA integrity_check` sobre la copia ≠ `ok` → mensaje a stderr y salida ≠ 0. `--keep N`: tras respaldar, borrar las `qfdesk-*.sqlite` más viejas de ese directorio que excedan N; sin `--keep` no borra nada. `N < 1` → error de uso.
  3. Restaurar: si la base destino existe y no hay `--force` → mensaje y salida ≠ 0 sin tocar nada; con `--force`, primero copia de la actual junto a ella como `<base>.antes-de-restaurar-YYYYMMDD-HHMMSS`, luego restaurar con la API de respaldo; comprobar `integrity_check` del archivo origen antes de pisar.
  4. Prueba: crear base con `create_app(db_path=…)` (siembra operaciones y eventos) + fijaciones; respaldar; restaurar a otra ruta; mismos conteos por tabla (`SELECT name FROM sqlite_master WHERE type='table'`); `UPDATE trade_events …` en la restaurada lanza `sqlite3.IntegrityError`/`DatabaseError` con "solo de inserción"; `--keep 2` con 3 copias deja 2; restaurar sin `--force` sobre base existente sale ≠ 0 y no cambia el archivo; con `--force` deja la copia previa. Además, un caso por subprocess (`python -m desk.api.backup`) para el código de salida.
- **Verificación:** `/home/claudio/anaconda3/bin/python -m pytest desk/api/tests/test_backup.py -q 2>&1 | grep -E "passed|failed"` → sin `failed`.
- **R:** R4.
- **Depende de:** nada (paralelo con T1 y T5).

### T5 — Carga por pantalla (modelo: sonnet)
- **Objetivo:** `React.lazy` por ruta + gráficas en su propio trozo; trozo de entrada ≤ 500 kB; estado de carga accesible.
- **Archivos:** `desk/ui/src/App.tsx`, `desk/ui/src/App.test.tsx`, `desk/ui/vite.config.ts`, `desk/ui/src/components/ScreenLoading.tsx` (nuevo, fallback de `Suspense`). No editar las pantallas (los exports nombrados se adaptan con `.then(m => ({ default: m.X }))`).
- **Pasos:**
  1. Medir antes: `npm run build` y anotar tamaños de `dist/assets/*.js`.
  2. Cada `element` de ruta con `lazy(...)` y un único `<Suspense fallback={<ScreenLoading />}>` dentro de `<Shell>` (el menú sigue visible mientras carga). `ScreenLoading`: texto "Cargando…" con `role="status"` y `aria-live="polite"`.
  3. Separar `echarts` (y, si hace falta para el límite, `ag-grid-community`) en trozos propios con la opción de Vite 8/rolldown que corresponda (`build.rollupOptions.output.manualChunks` o su equivalente; comprobar en la documentación de la versión instalada `node_modules/vite/package.json`).
  4. `App.test.tsx`: `findByRole` para `/metodologia`; añadir prueba de que el fallback tiene `role="status"`.
- **Verificación:** `cd desk/ui && npm run build 2>&1 | tail -15` sin errores; `grep -o 'assets/index-[^"]*\.js' dist/index.html` y `ls -l` de ese archivo ≤ 512000 bytes; `npm test 2>&1 | grep -E "Test Files|Tests "` sin `failed`.
- **R:** R5 (parte de construcción y pruebas), R7 (justificación de `App.test.tsx`).
- **Depende de:** nada (paralelo con T1 y T4).

### T6 — Documentación y metodología (modelo: haiku)
- **Objetivo:** R6 con todo ya decidido por T1/T2/T4.
- **Archivos:** `desk/README.md`, `desk/ui/src/screens/MethodologyScreen.tsx` (solo la sección `id: 'fuentes'`, ítems nuevos en bloque `// corte 8`).
- **Pasos:**
  1. README, sección nueva "Variables de entorno": `BANXICO_TOKEN` (para qué, que se lee solo del entorno, cómo obtenerla: registro en el portal SIE API de Banxico con captcha, lo genera Claudio) junto a las existentes (`MDF_DB`, `MDF_FETCH`).
  2. README, "Fijaciones desde la fuente": ejemplo `curl -X POST localhost:5070/api/fixings/fetch -H 'Content-Type: application/json' -d '{"index":"SOFR","from":"…","to":"…"}'`, respuesta de ejemplo con la forma real de T2, códigos 400/409/502, y `GET /api/fixings/sources`. IDs de serie de Banxico tal como los dejó T1 (o "sin verificar").
  3. README, "Respaldo y restauración": comandos de R4 (el CLI siempre actúa sobre `desk/data/desk.db`), nota de que **se restaura con el servidor apagado** y de la copia `<base>.antes-de-restaurar-YYYYMMDD-HHMMSS`, y un ejemplo de cron (p. ej. `30 2 * * * cd /home/claudio/Git/Quant_Finance && /home/claudio/anaconda3/bin/python -m desk.api.backup /ruta/respaldos --keep 14`).
  4. README, "Lo que el corte 8 NO hace": la lista de "Fuera de alcance" del diseño, literal. Solo en el README: el roadmap (`docs/`) lo actualiza Fable al cerrar.
  5. Metodología → Fuentes de datos: ítem "Fijaciones SOFR" (Fed de Nueva York, fijaciones reales, botón Traer de la fuente) e ítem "Banxico (TIIE de Fondeo, FIX)" (cliente listo, inactivo hasta tener token; las curvas de TIIE-F siguen sintéticas). No presentar nada sintético como real.
- **Verificación:** `grep -nE "BANXICO_TOKEN|fixings/fetch|desk.api.backup|NO hace" desk/README.md | head -8` muestra las cuatro; `cd desk/ui && npx vitest run src/screens/MethodologyScreen.test.tsx 2>&1 | grep -E "Tests "` sin `failed`.
- **R:** R6.
- **Depende de:** después de T1, T2 y T4.

### T7 — Integración contra el backend real (modelo: sonnet)
- **Objetivo:** probar R1–R7 de punta a punta y dejar evidencia.
- **Archivos:** ninguno del repo salvo correcciones mínimas de defectos encontrados (cada una con su commit y nombrada en el reporte). Artefactos en `/tmp/fableorchestrate/qf-corte8/it/` (base `it.db`, logs, capturas, scripts CDP).
- **Pasos:**
  1. Precondición: el agente de swaption ya terminó (lo garantiza quien lanza T7). Suites completas (ver `## Contexto`), todas verdes; no hay fallos ajenos aceptables: cualquier fallo se reporta como fallo.
  2. `cd desk/ui && npm run build`; medir el trozo de entrada (≤ 512000 bytes).
  3. Backend: `cd /home/claudio/Git/Quant_Finance && /home/claudio/anaconda3/bin/python -c "from desk.api.app import create_app; create_app(db_path='/tmp/fableorchestrate/qf-corte8/it/it.db').run(host='127.0.0.1', port=5088)" > /tmp/fableorchestrate/qf-corte8/it/backend.log 2>&1 &` y guardar el PID.
  4. Con red real: `POST /api/fixings/fetch` SOFR de los últimos ~10 días hábiles → 200 con `inserted > 0`; repetir → `inserted 0`, `unchanged` igual; TIIE-F sin `BANXICO_TOKEN` → 409 con `code: "banxico_token_missing"`; un error sin `code` (p. ej. el 400) sigue siendo `{"error", "field"}`; rango de 400 días → 400; `GET /api/fixings/sources` coherente.
  5. Chrome headless: `google-chrome --headless=new --disable-gpu --remote-debugging-port=9348 --user-data-dir=/tmp/fableorchestrate/qf-corte8/it/chrome-profile --window-size=1280,900 about:blank &` (guardar PID). Por CDP (script Node 22 sin dependencias en `/tmp/fableorchestrate/qf-corte8/it/`): visitar `/mercado`, `/pricers/irs`, `/portafolio`, `/portafolio/<id real>` (ficha de una operación), `/riesgo`, `/coberturas`, `/operaciones`, `/metodologia`, `/validacion`; en cada una: título/encabezado presente, cero `Runtime.exceptionThrown` y cero `console.error`, `document.documentElement.scrollWidth <= 1280`; comprobar que las peticiones de red cargan trozos distintos por pantalla. En `/mercado`: pulsar "Traer de la fuente" de SOFR y ver el resumen (o "Al día" deshabilitado si ya está al día respecto de `as_of`); TIIE-F/USDMXN muestran el motivo. Capturas (`Page.captureScreenshot`) de Mercado→Fijaciones y Metodología→Fuentes de datos, revisadas con `Read`.
  6. Respaldo **con el backend encendido** sobre `it.db`: como el CLI solo usa `desk/data/desk.db` (que no se toca), llamar a la función de respaldo de `desk.api.backup` con ruta `it.db` y destino `/tmp/fableorchestrate/qf-corte8/it/bk`, `keep=2`; después restaurar la copia a otra ruta de `/tmp/fableorchestrate/qf-corte8/it/` y comparar conteos por tabla. Comprobar además `python -m desk.api.backup --help` (sin ejecutar sobre la base real).
  7. `kill` de backend y Chrome por PID; `git status --short` sin archivos de este corte sin commitear.
- **Verificación:** reporte con: salida resumida de las 4 suites, tamaño del trozo de entrada, tabla pantalla → (errores de consola, scrollWidth), respuestas de `fetch`/`sources`, rutas de capturas.
- **R:** R1, R2 (409 real), R3, R4, R5, R7.
- **Depende de:** después de T1–T6.

## Cobertura de requisitos

| R | Tareas |
|---|---|
| R1 | T1, T2, T7 |
| R2 | T1, T2, T7 |
| R3 | T2, T3, T7 |
| R4 | T4, T7 |
| R5 | T5, T7 |
| R6 | T6 |
| R7 | T5 (justificación), T7 |


### T4
Hecho en el commit `0aee761`. Archivos: `desk/api/backup.py`, `desk/api/tests/test_backup.py` (12 pruebas).

Firmas reales (`desk.api.backup`):
- `class BackupError(Exception)`: fallo esperado; el CLI lo imprime en stderr y sale con 1.
- `backup(db_path, dest_dir, keep: Optional[int] = None, now: Optional[datetime] = None) -> Path`: crea `dest_dir/qfdesk-YYYYMMDD-HHMMSS.sqlite` (hora local; `now` solo para pruebas). Escribe a `*.parcial`, verifica `PRAGMA integrity_check` y renombra; si no es `ok` lanza `BackupError` y no deja copia. `keep` borra las `qfdesk-*.sqlite` más viejas por nombre; `keep < 1` lanza `ValueError`; base origen inexistente lanza `BackupError` sin crearla (se abre en solo lectura por URI).
- `restore(archive, db_path, force=False, now=None) -> Optional[Path]`: valida que exista y que `integrity_check` del origen sea `ok` antes de tocar nada; si `db_path` existe y no hay `force` lanza `BackupError` sin cambios; con `force` guarda la actual como `<base>.antes-de-restaurar-YYYYMMDD-HHMMSS` (la devuelve; `None` si no había base) y restaura con la API de respaldo. Si la base actual está ilegible, la copia previa es byte a byte y se retira antes de restaurar.
- `main(argv=None) -> int`: usa `db.DEFAULT_DB_PATH` leído al llamar (sin `--db`).

CLI (desde la raíz del repo): `python -m desk.api.backup <destino_dir> [--keep N]` imprime `Respaldo creado: <ruta>`; `python -m desk.api.backup --restore <archivo> [--force]` imprime `Base restaurada en <ruta>` y, si hubo, `Copia de la base anterior: <ruta>`. Códigos: 0 ok; 1 fallo esperado (stderr `Error: ...`); 2 error de uso (ni destino ni `--restore`, ambos, o `--keep < 1`). Restaurar exige el servidor apagado (no se detecta); respaldar es válido con el servidor encendido.
Para T6 (README): la base por omisión es `desk/data/desk.db`; los nombres de copia usan hora local.

### T5
HECHO (commit `1c70e6d`). Archivos: `desk/ui/src/App.tsx` (todas las rutas con `React.lazy`, exports nombrados con `.then(m => ({ default: m.X }))`, un único `<Suspense fallback={<ScreenLoading />}>` dentro de `<Shell>`; marcadores corte 5/7 conservados), `desk/ui/src/components/ScreenLoading.tsx` (nuevo; `<p role="status" aria-live="polite">Cargando…</p>`), `desk/ui/vite.config.ts` (`build.rolldownOptions.output.codeSplitting.groups`: `echarts` = echarts+zrender, `ag-grid` = ag-grid-community; Vite 8.3.8 / rolldown 1.2.18, `rollupOptions` está deprecado), `desk/ui/src/App.test.tsx` (`findByRole` para `/metodologia` + prueba del `role="status"`).
Tamaños (bytes): antes `index-*.js` 2 772 588 (el plan decía 2 676 138; otros cortes lo habían engordado); después `index-BKNU6A8x.js` 250 581 (≤ 512 000), `echarts-*.js` 1 117 109, `ag-grid-*.js` 1 168 576, RiskScreen 56 294, resto de pantallas 4–27 kB. `dist/index.html` solo precarga `rolldown-runtime` (726 B); el entry no importa estáticamente echarts ni ag-grid.
Aviso restante del build: "chunks larger than 500 kB" para los trozos `echarts` y `ag-grid` (son librerías de terceros ya aisladas; no se subió `chunkSizeWarningLimit`, no estaba pedido). `npm test`: 37 archivos / 552 pruebas, sin fallos; `tsc --noEmit` limpio.

### T1
Hecho en `7c8c4c8`. Firmas reales (todas puras salvo `fetch_*`; fechas como cadenas ISO `YYYY-MM-DD`, ambas incluidas; el fetch las revalida con `date.fromisoformat` y lanza `ValueError` antes de pedir nada):
- `desk/api/nyfed.py`: `SOFR_URL`, `TIMEOUT_S = 20`; `parse_sofr(text) -> List[Tuple[str, float]]` (fecha ISO, tasa **decimal** `round(percentRate/100, 10)`, ascendente, sin fechas repetidas; cuerpo ilegible o sin `refRates` → `ValueError`; lista vacía válida → `[]`); `fetch_sofr(start, end) -> List[Tuple[str, float]]`. Llama `urllib.request.urlopen(url_str, timeout=20)`.
- `desk/api/banxico.py`: `BASE_URL`, `TIMEOUT_S = 20`, `TIIE_F_SERIES = "SF331451"`, `FIX_SERIES = "SF43718"`; `parse_series(text) -> List[Tuple[str, float]]` (misma forma: ISO, ascendente; **la conversión la decide el `idSerie` del cuerpo**: SF331451 → decimal `round(dato/100, 10)`, SF43718 tal cual; `N/E` y filas ilegibles se omiten; serie sin `datos` → `[]`; cuerpo ilegible, sin `bmx.series` o con `idSerie` desconocido → `ValueError`); `fetch_series(series_id, start, end, token) -> List[Tuple[str, float]]` (token vacío/None → `ValueError` sin petición; token solo en cabecera `Bmx-Token` de un `urllib.request.Request`).
- Errores que **se propagan sin envolver** (T2 los mapea a 502 / código): `urllib.error.HTTPError` (`.code`: Banxico 400/401/403 = token rechazado), `URLError`, `socket.timeout`, `ValueError` (ilegible). Ningún `str()` de estos incluye el token. En `HTTPError`, `.read()` no está garantizado: mapear por `.code`, no por el cuerpo.
- IDs de serie verificados el 2026-11-11 en el catálogo público del SIE (no pide token): `.../v1/cat/series/SF331451` → "TIIE de Fondeo a Un Día Hábil Bancario, Mediana ponderada por volumen" (diaria, porcentajes); `.../v1/cat/series/SF43718` → "Tipo de cambio ... Fecha de determinación (FIX)" (diaria, pesos por dólar); SF43718 también listada en `.../v1/doc/catalogoSeries`. NO verificado: el cuerpo de éxito real de `.../series/<id>/datos/<from>/<to>` (requiere token); los fixtures `banxico_*.json` son simulados con la forma de la doc SIE y las fechas del fixture NY Fed (27/10–06/11/2026, N/E el 02/11).
- Fixtures: `desk/api/tests/fixtures/nyfed_sofr.json` (respuesta real, 9 observaciones 2026-10-27..2026-11-06, 3.95 … 3.89 %), `banxico_tiie_f.json`, `banxico_fix.json`, `banxico_sin_datos.json`. Pruebas: `test_nyfed.py`, `test_banxico.py` (48 en total, sin red).

### T2
Hecho en `75a4f15`. Archivos: `desk/api/fixings_fetch.py` (nuevo: `fetch_fixings(conn, body)`, `list_sources(conn)`), `desk/api/routes/fixings.py` (bloque `# corte 8` al final + import), `desk/api/errors.py` (`ApiError(status, error, field=None, code=None)`; `_response` agrega `"code"` solo si se dio), `desk/api/tests/test_fixings_fetch.py` (38 pruebas, sin red). Suite backend: 3421 passed, 3 failed (los 3 ajenos conocidos).

`POST /api/fixings/fetch` cuerpo `{"index","from","to"}` (la ruta hace `conn.commit()`):
- 200 (siempre `jsonify` plano, sin envoltorio): `{"index","source","from","to","fetched","inserted","unchanged","conflicts":[{"date","stored","source"}]}`. `source` = `"Fed de Nueva York"` (SOFR) o `"Banxico (SIE)"` (TIIE-F, USDMXN). `from`/`to` son eco del cuerpo. `stored` y `source` de cada conflicto en la unidad de la tabla (decimal en tasas). Conflictos en orden ascendente de fecha. Rango sin datos en la fuente = 200 con todo en 0 y `conflicts: []`.
- 400 (`{"error","field"}`, sin `code`): `index` fuera de INDICES o ausente (`field: "index"`), `from`/`to` ausente o no ISO (`"from"`/`"to"`), `from > to` (`field: "from"`), rango > 366 días, es decir `(to-from).days > 366` (`field: "to"`; 366 exactos se aceptan), cuerpo no objeto/no JSON (`field: null`).
- 409 solo Banxico sin token (variable ausente **o vacía**): `{"error": "Falta el token de Banxico (variable BANXICO_TOKEN)", "field": null, "code": "banxico_token_missing"}`; no se hace petición.
- 502 token rechazado (HTTP 400, 401 o 403 de Banxico): `{"error": "Banxico rechazó el token (BANXICO_TOKEN)", "field": null, "code": "banxico_token_rejected"}`.
- 502 sin `code` (`field: null`): `"La Fed de Nueva York no respondió: <motivo>"` o `"Banxico no respondió: <motivo>"` (URLError/timeout/HTTP de error/cuerpo ilegible; el motivo es `str(e.reason)` o `str(e)`, p. ej. `HTTP Error 500: Server Error`); y `"<La Fed de Nueva York|Banxico> devolvió un valor inválido (<fecha>): <motivo de _validate>"` si la fuente trae un valor fuera de rango (decisión de T2: es fallo de la fuente, no del cuerpo, por eso 502 y no 400). En todo 502 y 409 no se escribe nada. Un 404 de Banxico se deja como 502 genérico: la documentación pública del SIE accesible (`.../doc/consultaDatosSerieRango`) no dice qué responde con un rango sin datos, y sin token no se puede probar; si el uso real revela que un rango sin datos da 404, hay que tratarlo como "sin observaciones" en `_download` (cambio de 2 líneas).

`GET /api/fixings/sources` → `{"sources": [{"index","source","available","reason","last_date"}]}` en orden `TIIE-F`, `SOFR`, `USDMXN`. `available`: SOFR siempre `true`; Banxico `true` solo con `BANXICO_TOKEN` no vacío; `reason` = `null` o `"Falta el token de Banxico (variable BANXICO_TOKEN)"`; `last_date` = `MAX(fixing_date)` ISO o `null`.

Para T3: `desk/ui/src/api/client.ts` debe leer `code` del cuerpo de error (hoy `request` solo toma `error`/`field`) para distinguir `banxico_token_missing` / `banxico_token_rejected`; `sources` ya trae `available`/`reason` para deshabilitar el botón sin hacer petición. Para T6 (README): variable de entorno `BANXICO_TOKEN` (solo lectura del entorno del proceso del backend; nunca se guarda ni se devuelve); la TIIE-F de Banxico es la "TIIE de Fondeo a un día hábil bancario" (SF331451) y USDMXN es el FIX (SF43718). No comprobado: el cuerpo de éxito real de Banxico (requiere token); los fixtures son simulados.

### T3
HECHO (commit `905f036`). Archivos: `desk/ui/src/api/client.ts` (bloques `// corte 8`: `ApiError` gana `code: string | null` como 4.º argumento del constructor, `request()` lee `code` del cuerpo de error; `fixingSources(): Promise<FixingSource[]>` desenvuelve `{sources}`; `fetchFixings(body): Promise<FetchFixingsResult>`), `desk/ui/src/api/types.ts` (bloque `// corte 8`: `FixingSource`, `FetchFixingsBody`, `FixingConflict`, `FetchFixingsResult`), `desk/ui/src/screens/FixingsPanel.tsx`/`.css`/`.test.tsx`, y `desk/ui/src/api/client.test.ts` (4 pruebas nuevas en bloque `// corte 8`: `code` conservado/null, cuerpo de `fetchFixings`, `fixingSources`; no estaba listado en la tarea, se añadió para cubrir la lectura de `code`).
Panel: sección `aria-label="Traer de la fuente"` entre la tabla y los formularios; un `role="group"` `aria-label="Fuente de <ÍNDICE>"` por índice con fuente, última fecha y: botón "Traer de la fuente" / texto "Al día" (botón deshabilitado) / el `reason` sin botón si `available` es false. Rango: `to = useSnapshot().snapshot.as_of`; `from` = día siguiente a `last_date` (suma en UTC) o `to - 30 días`; `from > to` -> "Al día". Sin snapshot cargado el botón queda deshabilitado. Mientras corre una petición, todos los botones se deshabilitan (el pulsado dice "Trayendo…"). Éxito: `role="status"` "Insertadas: N · Sin cambio: M[ · Conflictos: K]" y, si hay conflictos, tabla `aria-label="Conflictos de <ÍNDICE>"` (Fecha / Guardado / Fuente; tasas con `fmtRate`, USDMXN `fmtNumber(v, 4)`); luego recarga `listFixings` y `fixingSources`. Error: `role="alert"` con `ApiError.message` tal cual (no se ramifica por `code`; el 409 `banxico_token_missing` no debería ocurrir con el botón porque `sources` ya oculta el botón). Fallo al cargar `sources`: `role="alert"` propio, el resto del panel sigue.
Pruebas existentes del panel: sin cambios de resultado; solo se añadió al `beforeEach` el mock de `fixingSources` y de `../state/SnapshotContext` (`useSnapshot` -> `as_of` fijo 2026-11-11). `MarketScreen.test.tsx` ya mockea `./FixingsPanel`, no se tocó.
Verificación: panel 27 pruebas OK (14 nuevas), `client.test.ts` OK, `npx tsc -b` limpio, `npm test` 37 archivos / 570 pruebas sin fallos.
No comprobado: desborde horizontal a 1280 px en navegador real (solo CSS sin anchos fijos, `flex-wrap` y `overflow-wrap`); rango > 366 días (si `last_date` es muy antigua el backend responde 400 y se muestra tal cual; no se recorta el rango porque no estaba pedido).
