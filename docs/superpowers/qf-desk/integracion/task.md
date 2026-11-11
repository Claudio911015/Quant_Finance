# Integración de los cortes 3, 5, 6 y 7 de QF Desk tras la fusión

Repositorio `/home/claudio/Git/Quant_Finance`, rama `feat/qf-desk`. Lee `CLAUDE.md` del repo. Diseños de cada corte: `docs/superpowers/qf-desk/corte{3,5,6,7}/design.md` (consúltalos solo para decidir qué comportamiento es el correcto).

Los cuatro cortes se construyeron en paralelo desde el mismo commit base, cada uno sin ver a los otros, y se acaban de fusionar. Cada uno pasó su auditoría por separado. Tu trabajo es que funcionen **juntos**.

## 1. Fallos conocidos tras la fusión (backend)

`/home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q -p no:cacheprovider` da 3 fallos:

- `test_ops_cashflows.py::test_projected_flows_discount_back_to_the_pv_of_the_trade[bond]`
- `test_ops_cashflows.py::test_only_irs_and_bonds_have_projected_rows_and_usd_rows_convert_at_the_spot`
- `test_ops_schema.py::test_context_at_keeps_the_market_and_changes_only_the_date`

Causa probable: el corte 3 cambió el envejecimiento del bono (cupón completo, flujos `redemption`), añadió el producto `xccy_swap` con flujos `exchange`, la curva `MXN-USD` y el colateral por contraparte en el contexto de mercado; el corte 5 (operaciones: `desk/api/ops*`, flujos del portafolio, confirmaciones, FpML, conciliación) se escribió contra el comportamiento anterior. Arregla la causa (código o prueba, según cuál esté mal respecto de los diseños); no relajes una aserción sin entender por qué.

## 2. Cruces que ninguna prueba cubre todavía

Revisa, y donde falte, corrige y añade una prueba por cruce:

- **xccy_swap en operaciones (corte 5):** `/api/cashflows` debe listar sus flujos (cupones de ambas patas e intercambios de nocional, cada uno en su moneda); la liquidación/confirmación de un flujo de xccy debe funcionar; el documento de confirmación debe describirlo con sentido o, si no se construyó plantilla, rechazarlo con un mensaje claro en español (no un 500); la exportación FpML debe rechazarlo con mensaje claro (solo irs, fx_forward y fx_option exportan); la conciliación debe tratarlo sin romperse.
- **xccy_swap y colateral USD en riesgo avanzado (corte 6):** la cascada de P&L explicado debe cerrar (residuo declarado, suma = `/api/pnl`) en un portafolio que incluya un xccy_swap y una contraparte con colateral en USD (curva `MXN-USD` y sus factores: si la cascada no tiene factor para los puntos forward/base, el efecto debe caer en un rubro nombrado o en el residuo, nunca perderse); VaR histórico y límites no deben romperse con ese portafolio; CVA: el xccy debe quedar excluido con el aviso que ya se usa para productos no cubiertos.
- **Validación (corte 7):** `GET /api/validation/report` y su prueba de humo deben seguir pasando; si el cambio de valuación del corte 3 hace que `desk_commit` ya no coincida, es el comportamiento diseñado (aviso), pero OJO: otro agente acaba de regenerar el reporte tras corregir un defecto de swaptions; NO toques `desk/validation/*.json` ni `src/`.
- **Interfaz:** con el backend real (puerto 5088; Chrome headless por CDP en 9348, hay un ejemplo de script en `/tmp/claude-1000/-home-claudio/1a002a83-9ce7-4c4e-b315-b09b1e001eba/scratchpad/tipo-shots/shoot.mjs`, adapta puertos), recorre todas las entradas del menú y todas las pestañas de Portafolio, Riesgo y Operaciones, y la ficha de un xccy_swap y de un bono: sin errores de consola, sin desborde horizontal a 1280 px, sin rótulos crudos (`xccy_swap`, `exchange`, `redemption`, `MXN-USD` sin explicar) donde los demás productos muestran rótulos en español. La paleta de comandos (Ctrl+K) debe listar las ocho pantallas y los ocho pricers. Crea por API un xccy_swap y cambia el colateral de una contraparte a USD para tener datos. Usa una base temporal (mira cómo `desk/api/app.py` resuelve la ruta de la base y cómo arrancan las pruebas), nunca la del puerto 5070.
- **Rótulos duplicados:** los cortes definieron por separado mapas de rótulos de producto y de tipo de flujo (`desk/ui/src/lib/csaLabels.ts`, `desk/ui/src/screens/ops/opsLabels.ts`, `desk/ui/src/lib/*Labels.ts`). No refactorices todo; solo asegúrate de que el mismo concepto no se llame distinto en dos pantallas, y corrige las diferencias.

## 3. Pendientes menores de las auditorías (hazlos, son pequeños)

- `desk/ui/src/screens/MethodologyScreen.tsx`: el enlace a Validación es `<a href="/validacion">`; cámbialo por `Link` de React Router.
- `desk/validation/compare.py`: «1 explicadas» sin concordancia de número en la salida de consola (solo el texto; no regeneres JSON).
- Corte 6, `desk/api/credit.py`: la simulación arranca un cupón diario por debajo del PV del desk (Alfa −86k MXN ≈ 9 % del PV); la prueba `test_simulated_swap_starts_at_the_desk_pv…` lo oculta con sigma=1e-7. Si la causa es acotada (un periodo de devengo al inicio), corrígela y endurece la prueba; si no lo es, deja el docstring y la Metodología diciendo la magnitud real y no «nace del PV».

## Reglas

- No cambies comportamiento que un diseño fijó para acomodar a otro corte sin decirlo en tu respuesta.
- Suites al terminar: `ctest --test-dir build` (no recompiles C++; no toques `src/` ni `include/`), `pytest desk/api/tests`, y en `desk/ui`: `npm test` y `npm run build`.
- Commits pequeños, en español, con el porqué, sin Co-Authored-By ni trailers: `GRAPHIFY_SKIP_HOOK=1 git commit -m "…" -- <rutas explícitas>`. Sin push, sin `git stash`, sin `graphify-out/` ni `docs/`. No toques el puerto 5070, Brave/9222 ni `~/Git/MarketDataFeed`. Apaga lo que levantes.

## Respuesta

`HECHO` o `BLOQUEADO`; por cada punto de §1–§3: qué encontraste (con evidencia: comando + salida o `archivo:línea`), qué corregiste y en qué commit; conteos reales de las suites; y la lista de lo que no pudiste comprobar o decidiste no tocar, con el motivo.
