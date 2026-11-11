# QF Desk — Corte 7: validación independiente

Repo `/home/claudio/Git/Quant_Finance`. Este corte se trabaja en un worktree propio (rama `corte7`, creada desde `feat/qf-desk`); se fusiona al final. Base: cortes 1, 2 y 4. Claudio delegó todas las decisiones en Fable.

## Intención

"Mi número contra el de una referencia conocida" es lo que convierte una demo en algo creíble. Este corte compara la valuación de QF Desk con **QuantLib** producto por producto, con las mismas curvas y convenciones, declara tolerancias y muestra el resultado en la interfaz.

## Decisiones de arquitectura

- **D1 Referencia y entorno.** QuantLib para Python **no** se añade al backend (Python 3.8 de anaconda, sin dependencias nuevas). El arnés corre aparte, en un entorno conda que ya tenga QuantLib (buscar en `conda env list`: `pyfinance`, `qlib`, `openbb`, `base`; si ninguno lo tiene, crear el entorno `qfvalid` con `pip install QuantLib` — es una herramienta de desarrollo, no una dependencia del producto). Se anota en el README qué entorno se usó y la versión de QuantLib.
- **D2 Arnés** (`desk/validation/`): `export_cases.py` (corre con el Python del backend: toma el portafolio de ejemplo más una batería de casos por producto —lados, plazos, dentro/fuera del dinero— y escribe `cases.json` con términos, curvas del snapshot como factores de descuento por pilar, spot, volatilidades y el PV de QF Desk); `run_quantlib.py` (corre con el entorno de QuantLib: reconstruye cada curva a partir de los mismos factores de descuento con la misma interpolación —o la más cercana disponible, declarada—, valúa cada caso y escribe `reference.json`); `compare.py` (une ambos y escribe `desk/validation/report.json` con, por caso: PV propio, PV de referencia, diferencia absoluta, relativa al nocional, tolerancia del producto y veredicto). `make_report.sh` encadena los tres.
- **D3 Productos y tolerancias (relativas al nocional).** `irs` OIS (TIIE-F 28 días y SOFR anual): 1e-6. `fx_forward`: 1e-8. `fx_option` Garman-Kohlhagen: 1e-6. `equity_option` Black-Scholes: 1e-6. `bond`: 1e-6. `cap_floor` y `swaption` con Hull-White: 5e-4 (modelo y convenciones de implementación distintos; la diferencia se explica caso por caso). Toda diferencia mayor a su tolerancia queda **explicada** en `desk/validation/known_differences.json` (causa, magnitud esperada) o es un defecto que se corrige en el propio corte si es del desk (con su test) o se documenta si es de convención.
- **D4 Backend e interfaz.** `GET /api/validation/report` sirve el `report.json` versionado en el repo (con fecha de generación, versión de QuantLib, commit del desk y resumen por producto: casos, dentro de tolerancia, peor diferencia). Pantalla nueva **Validación** en la navegación: resumen por producto, tabla por caso filtrable, diferencias conocidas con su explicación, y cómo reproducir. Si el reporte se generó con un commit distinto del actual, la pantalla lo avisa.
- **D5 Prueba de humo en la suite del backend:** un test que lee `report.json` y falla si algún caso excede su tolerancia sin estar en `known_differences.json`, o si el reporte no existe.
- **D6 Metodología:** enlace a Validación; qué se compara y qué no (riesgo y contabilidad no se validan contra QuantLib).

## Requisitos

- **R1** `make_report.sh` corre de principio a fin en esta máquina y deja `report.json` con al menos 60 casos que cubren los 7 productos, con ≥ 5 casos por producto.
- **R2** Todos los casos están dentro de la tolerancia de D3 o listados en `known_differences.json` con una causa concreta y verificable (no "diferencia de modelo" a secas: qué convención difiere y cuánto explica).
- **R3** Curvas idénticas: para cada curva, los factores de descuento reconstruidos en QuantLib coinciden con los del desk en los pilares (1e-12) y en 10 fechas intermedias (1e-8, o se declara la diferencia de interpolación).
- **R4** `GET /api/validation/report` y la pantalla Validación muestran resumen, tabla, diferencias conocidas, fecha, versión y aviso de commit distinto; sin desbordes a 1280 px; textos en español.
- **R5** El test de humo de D5 existe y pasa; modificar a mano un PV del reporte lo hace fallar.
- **R6** README de `desk/validation/` explica cómo regenerar (entorno, comandos) y Metodología enlaza a Validación.
- **R7** Sin regresión: las cuatro suites pasan (QuantLib no se importa en ninguna de ellas).

## Fuera de alcance (se declara)

ORE como segunda referencia; validación de XVA, VaR, DV01 y contabilidad de coberturas; validación con datos de mercado reales de un proveedor.

## Restricciones

Las de los cortes anteriores (sin dependencias nuevas en backend ni interfaz, commits por tarea con `GRAPHIFY_SKIP_HOOK=1 git commit ... -- <rutas>`, autor Claudio sin `Co-Authored-By`, sin `git stash`, sin push). Si la validación destapa un defecto real de valuación en el desk, se corrige aquí con su test y se reporta. Otros cortes avanzan en paralelo en otros worktrees: **minimizar cambios en archivos compartidos** (`app.py`, `Shell.tsx`, `App.tsx`, `api/types.ts`, `api/client.ts`, `MethodologyScreen.tsx`): añadir al final, en bloques contiguos delimitados por un comentario `corte 7`; lo propio va en módulos nuevos (`desk/validation/`, `desk/api/routes/validation.py`, `desk/ui/src/screens/ValidationScreen.tsx`).
