# Auditoría — QF Desk corte 8 + integración de cortes 3/5/6/7

Rama `feat/qf-desk`, HEAD `1abca0f`. Auditado el 2026-11-11, sin leer `plan.md` ni los reportes de los implementadores.
Backend real en 127.0.0.1:5098 con base temporal (scratchpad `audit8/db/audit.db`), Chrome headless por CDP en 9358. Los dos ya están apagados. No toqué nada en el repo: `git status` solo muestra `graphify-out/` y `docs/`, que ya estaban así antes.

## Suites (corridas por mí)

| Suite | Resultado |
|---|---|
| `cmake --build build -j3` | OK |
| `ctest --test-dir build` | **463/463** pasan |
| `cmake --build build --target pytests` | **83** OK |
| `pytest desk/api/tests -q -p no:cacheprovider` | **3438 passed** (158 s) |
| `npm test` (desk/ui) | **575 pruebas en 37 archivos**, todas pasan |
| `npm run build` | OK. Trozo de entrada `index-CTcPk4rB.js` = **250 951 B**; echarts (1.12 MB) y ag-grid (1.17 MB) van en trozos propios |

## Veredictos — diseño del corte 8 (A)

| Req | Veredicto | Evidencia |
|---|---|---|
| R1 SOFR real | CUMPLE | Contra la NY Fed real, `{"SOFR","2026-10-01","2026-10-31"}` → 200 `fetched 21, inserted 21`. Al repetirla → `inserted 0, unchanged 21`. El 2026-10-30 se guardó como 0.0395 frente a `percentRate` 3.95 de la fuente. Lo cambié por SQL a 0.0999 y volví a traer → `conflicts:[{"date":"2026-10-30","stored":0.0999,"source":0.0395}]`; el valor guardado sigue en 0.0999 y las demás fechas sí se insertaron. Un rango de 367 días → 400 `field:"to"`; uno de 366 → 200 con 250 fijaciones. `from>to`, una fecha inválida o un índice desconocido → 400 con `field`. Con 500, cuerpo ilegible o conexión rechazada → 502 en español, y la base no cambia (4 filas antes, 4 después). Las pruebas usan `urlopen` simulado y un fixture real: `tests/fixtures/nyfed_sofr.json`, `test_fixings_fetch.py`. Todo o nada: `fixings_fetch.py:85-121` descarga y valida todo antes de llamar a `executemany`, y la ruta hace el commit solo al final. |
| R2 Banxico inactivo sin token | CUMPLE (las series no se verificaron contra Banxico) | Sin token: TIIE-F y USDMXN → 409 `{"code":"banxico_token_missing","error":"Falta el token de Banxico (variable BANXICO_TOKEN)","field":null}`. Probé con un SIE falso local y `BANXICO_TOKEN=SECRETTOKEN123`. En éxito, 7.25 se guarda como 0.0725, «N/E» se omite y una diferencia sale como conflicto. 400, 401 y 403 → 502 `banxico_token_rejected`. 500, basura o red caída → 502 sin `code`. El token solo viaja en la cabecera `Bmx-Token`. No aparece en ninguna respuesta, en los logs (handler raíz más `app.logger`) ni en los bytes de la base: `TOKEN IN OUTPUTS/LOGS: False`, `db contains token: False`. Las series están citadas con la URL de catálogo en `banxico.py:16-23` (SF331451, SF43718). No las comprobé contra Banxico porque solo estaba autorizada la NY Fed. SF43718 = FIX es conocido; SF331451 lo tomo de la cita. |
| R3 Procedencia visible | CUMPLE | `GET /api/fixings/sources` respeta el orden de `INDICES` y devuelve `reason`/`last_date` nulos cuando no aplican. En el navegador, el panel «Traer de la fuente» de Mercado muestra el motivo en vez del botón para TIIE-F y USDMXN, y el botón para SOFR. Al pulsarlo aparece «Insertadas: 0 · Sin cambio: 0». A 1280 px: `scrollWidth 1280`, sin desborde. El rango (última+1 o 30 días atrás, hasta `as_of`) y «Al día» están en `FixingsPanel.tsx:24-26` y en `FixingsPanel.test.tsx:249,276,320`. |
| R4 Respaldo y restauración | CUMPLE | Respaldé la base viva del servidor 5098 tres veces con `--keep 2` y quedaron 2 copias `qfdesk-YYYYMMDD-HHMMSS.sqlite`. La restauración en una ruta nueva da los mismos conteos (trades 9, events 11, fixings 326, snapshots 4, cp_events 1). Restaurar sobre una base existente sin `--force` → rc 1 y el md5 del destino no cambia. Con `--force` → rc 0 y queda `target.db.antes-de-restaurar-20261111-163038` con la fila que añadí. En la base restaurada, UPDATE o DELETE sobre `trade_events`/`counterparty_events` → «es solo de inserción», así que los disparadores siguen activos. Un respaldo truncado → rc 1, «no pasó integrity_check», y no toca el destino. `--keep 0` → rc 2. La prueba pedida está en `test_backup.py:49`. |
| R5 Carga por pantalla | CUMPLE | `App.tsx:7-27` usa `lazy` y `Suspense` con `ScreenLoading` (`role="status" aria-live="polite"`). Trozo de entrada: 251 kB ≤ 500 kB. Recorrí en Chrome las 8 entradas del menú, todas las pestañas, las fichas #8 (xccy) y #9 (bono) y dos confirmaciones contra el backend real: `errores finales []`. |
| R6 Documentación | CUMPLE | En `desk/README.md`: variables de entorno con `BANXICO_TOKEN` y cómo obtenerlo (l.32-36), `fetch` (l.40-57, declara que Banxico no está probado con token real), respaldo con ejemplo de cron (l.63-77) y «Lo que el corte 8 NO hace» (l.99-101). En Metodología, «Fuentes de datos» presenta SOFR de la NY Fed como real y Banxico como «listo, inactivo… sin probar»; TIIE-F se declara sintética (`MethodologyScreen.tsx:247,260-264`). |
| R7 Suites | CUMPLE | Ver arriba: todo verde. Las pruebas previas que cambiaron lo hicieron con motivo: `App.test` pasa a async por el lazy; `test_pnl_explain` y `test_risk_adv_schema` reciben la clave `curve:MXN-USD`; las de confirmación pasan a clave (fecha, moneda); los rótulos se toman de una constante o de nombres concordados. Ninguna aserción se relajó sin razón. |

## Veredictos — integración (B)

| I | Viñeta | Veredicto | Evidencia |
|---|---|---|---|
| I1 | §1 `test_projected_flows…[bond]` | CUMPLE | Pasa sin cambiar la prueba. La causa estaba en el código: `settlement._projected_bond` se había movido a `aging` (commit `d1f04cd`). |
| I2 | §1 `test_only_irs_and_bonds_have_projected_rows…` | CUMPLE | Igual que I1: pasa y la prueba no se tocó. |
| I3 | §1 `test_context_at_keeps_the_market…` | CUMPLE | Pasa sin cambiar la prueba. `ops_recon.context_at` ahora copia el contexto original. |
| I4 | §2 xccy en operaciones | CUMPLE | En vivo, `/api/cashflows` da 56 filas del #8: intercambios USD/MXN, cupones de cada pata en su moneda y `redemption`/`exchange` con rótulo en español en la UI. Confirmé el USD y el MXN del 2026-12-08 por separado (201/201). La segunda confirmación MXN → 409 «ya está confirmado». El intercambio → 409 «no se confirma». EUR → 400. La confirmación del documento → 400 «No hay plantilla de confirmación para Cross currency swap USDMXN». FpML → 400 con un mensaje claro. La conciliación tiene su prueba en `test_integration_cortes.py:200`. |
| I5 | §2 P&L explicado con xccy y colateral USD | CUMPLE (con un defecto de atribución, D1) | Escenario en vivo: Alfa con colateral USD, xccy #8, bono #9, rodado 35 días, puntos ×1.25, base −10 pb, spot +0.30, SOFR +20 pb. Resultado: `pnl 7386417.3999` = suma de componentes; `events 0.0`, `residual 0.0`; ninguna fila con error. `curve:MXN-USD` = 899 926 en total: fx_forward de Alfa 565 k, bono de Alfa 266 k, xccy 64 k; contrapartes sin colateral USD, 0. Económicamente tiene sentido: es el efecto de los puntos y la base con el spot y las curvas de las que depende ya movidos, antes del paso de FX (`explain.py:28-41,72-80`). |
| I6 | §2 VaR histórico y límites | CUMPLE | En D1 con el escenario anterior: VaR histórico 2.05 M, `errors []`. `limits/check` → 200 y `usage errors []`. |
| I7 | §2 CVA excluye el xccy | CUMPLE | `excluded` de Alfa contiene `(8, "…solo cubre swaps de tasas (IRS): Cross currency swap USDMXN se excluye")`. |
| I8 | §2 Validación | CUMPLE | `/api/validation/report` → 62/62 dentro, `commit_matches True`. Los JSON de `desk/validation/*` no se tocaron en la integración. `1abca0f` es un commit de datos posterior, propio del cierre del corte 8. |
| I9 | §2 Interfaz | CUMPLE (con un defecto visual, D2) | Recorrido CDP: 8 pantallas, pestañas de Portafolio (3), Riesgo (6) y Operaciones (2), fichas del xccy y del bono, sin errores de consola y con `scrollWidth 1280` en todas. No quedan rótulos crudos `xccy_swap|exchange|redemption|fx_forward|cap_floor` en el texto visible; solo IDs de caso en Validación y `settlement_confirmed` dentro de una explicación de Metodología. Donde aparece MXN-USD va explicado. Ctrl+K lista 8 pantallas y 8 pricers. |
| I10 | §2 Rótulos duplicados | CUMPLE | `opsLabels.ts` reexporta `FLOW_KIND_LABEL` de `lib/csaLabels.ts`, los productos salen de `productTitle` y el backend usa `pricing.PRODUCT_LABEL`. El recorrido no encontró el mismo concepto con dos nombres. |
| I11 | §3 Link en Metodología | CUMPLE | `MethodologyScreen.tsx:2,483` usa `<Link to="/validacion">`. |
| I12 | §3 compare.py concordancia | CUMPLE | `96af075` toca solo `compare.py` y su prueba; ningún JSON. |
| I13 | §3 credit.py | CUMPLE (no se corrigió: se documentó la magnitud) | El docstring de `d1f04cd` declara −86 k en Alfa (9 % del PV) y el motivo: el calendario vive en C++, que no se puede tocar. `test_credit.py` ahora mide que el escalón sea ≤ un cupón diario en vez de ocultarlo. Metodología se corrigió en `20d0279`. |

## Swaption (`2f5b733`)

- **Matemática**: es correcta. La raíz se busca en x = r − f(0,T) y con eso se cancela f0. El factor A recupera −½·V·B², y es el término que hace que E^T[P(T,Ti)] = F_i. El intervalo de bisección se ensancha hasta encerrar la raíz, que existe por monotonía.
- **¿La prueba es independiente?** Lo es solo en parte. La cuadratura evita la descomposición de Jamshidian y `hwZCBOption`, pero usa la misma fórmula del bono HW que el código, término de varianza incluido. Esa fórmula queda fijada por la propiedad de martingala (E[exp(−B√V z − ½VB²)] = 1), así que no es circular, pero un error compartido en el modelo pasaría. La prueba de verdad independiente es QuantLib: volví a correr `run_quantlib.py` → diferencia máxima 0.0 con `reference.json`, y `export_cases` con el código actual → diferencia máxima 0.0 con `cases.json`.
- **Regresiones**: no hay. Las 8 swaptions quedan más cerca de QuantLib que antes. swaption-04 pasa de 0 a 92 158.634 (QL 92 158.633). swaption-03 pasa de un error de 38.5 MXN a 0.60 MXN. Las demás, de entre 0.2 y 5 MXN a menos de 1e-3. Todas las pruebas de swaption anteriores siguen pasando y no se modificaron; el diff solo añade.

## Defectos encontrados

| # | Sev. | Defecto |
|---|---|---|
| D1 | media | En el P&L explicado, el FX de los flujos USD liquidados cae en «Paso del tiempo y liquidaciones» y no en «Tipo de cambio». `explain.py:115` valúa `settled_flows` al spot de `to` dentro de `carry`. Lo reproduje: con solo el spot +0.30 (D2) frente a sin cambios (D3), el carry del xccy pasa de 523 726 a 3 514 276 y fx queda en −2 987 231. Son unos 3 M de efecto FX que se compensan entre dos rubros por el intercambio inicial de 10 M USD. El total cierra, pero la atribución engaña. Viene del corte 6, y con el xccy se vuelve grande. |
| D2 | baja | Flujos de Operaciones a 1280 px: con filas de xccy, los rótulos largos («Cross currency swap USDMXN», «Intercambio de nocional») hacen que la tabla pida desplazamiento interno. La columna fija «Confirmar liquidación» tapa «Monto MXN»: se lee «189,000,0» o «-186,000,0» en vez del monto completo. La página no se desborda, pero el comentario de `CashflowsPanel.css:129` («las doce columnas caben sin desplazar») ya no se cumple. |
| D3 | baja | `FixingsPanel` arma el rango desde la última fijación + 1 sin tope. Si esa fijación tiene más de 366 días, el botón recibe un 400 «El rango no puede pasar de 366 días» y Claudio no tiene cómo resolverlo desde la pantalla (`FixingsPanel.tsx:24-26`). |
| D4 | baja | `fixings_fetch.py:115` inserta con `INSERT` simple tras leer lo guardado. Dos `fetch` concurrentes del mismo rango pueden chocar con la PK y dar un 500 genérico en vez de «sin cambio». No hay escritura parcial. |
| D5 | baja | `backup()` pisa en silencio una copia del mismo segundo (`os.replace`, `backup.py:84`), y `--keep` borra cualquier `qfdesk-*.sqlite` del directorio aunque no la haya creado el desk. |
| D6 | baja | La confirmación por (fecha, moneda) del xccy compara con el cupón, sin el intercambio. Al vencimiento, un banco que confirme el neto (cupón + nocional) en MXN verá una diferencia enorme y no podrá confirmar el intercambio (409 «no se confirma»). Esto es por diseño, pero el README de operaciones no lo dice. |
| D7 | baja | Un rango sin observaciones en Banxico (posible 404) daría un 502 genérico. Está declarado en el README (l.57), así que no es oculto. |

## Construido sin que ningún requisito lo pidiera

- `backup()` escribe primero a `.parcial` y solo renombra si pasa `integrity_check`. `restore --force` sobre una base dañada la copia byte a byte y la retira. Las dos cosas son razonables, pero nadie las pidió.
- La UI oculta la acción de confirmación del xccy (`NO_CONFIRMATION_PRODUCTS`), además del 400 del backend.
- La paleta Ctrl+K muestra la ruta o el código del pricer (`/mercado`, `fx_forward`) como texto secundario. Ya venía de antes.
- Commit `1abca0f`: la validación se regeneró otra vez «al final del corte 8», solo para mover `desk_commit` a `d1f04cd`. No es un requisito; los datos no cambian.

## Cierre (Fable, 2026-11-11)

Tras esta auditoría un agente corrigió D1–D6 (commits `8f88e39`, `b180efe`, `3802de3`, `e438b6f`, `6801b46`, `6d89475`), cada uno con una prueba que fallaba antes. Esa ronda de correcciones no pasó por una nueva auditoría independiente; se verificó con las suites completas: ctest 463, bindings 83, backend 3 442, interfaz 579, `npm run build` correcto, validación 62/62 dentro con `commit_matches: true`.

Siguen abiertos y declarados: D7 (un rango sin datos en Banxico podría verse como 502; no se puede comprobar sin token); `POST /api/fixings/csv` conserva el patrón de leer e insertar que D4 corrigió solo en `fetch`; dos procesos que respaldan en el mismo segundo pueden competir; la tabla de Flujos vuelve a desplazarse por debajo de 1280 px.
