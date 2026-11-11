# Diseño: QF Desk — workstation de valuación de derivados para tesorerías mexicanas

Repo: `/home/claudio/Git/Quant_Finance` (leer su `CLAUDE.md`). Rama de trabajo: `feat/qf-desk` (crearla desde `main`; no hacer push).

## Intención
Convertir la biblioteca C++ `Quant_Finance` en un producto vendible: una workstation web donde la tesorería de una empresa mexicana valúa de forma independiente del banco sus derivados (swaps TIIE de Fondeo y SOFR, forwards y opciones USDMXN, caps/floors), los guarda en un portafolio y ve su riesgo. Referencia de experiencia: las pantallas de pricing de Bloomberg (SWPM, OVML) y el blotter de Murex/Calypso: densa, oscura, rápida, operable con teclado. La biblioteca ya calcula casi todo; hoy la web solo enseña opciones, bonos y swaps en tres páginas Jinja. Este corte es el núcleo de un solo usuario, sin login.

## Arquitectura (decidida; no cambiar)
- Todo lo nuevo vive en `desk/`: `desk/api/` (backend) y `desk/ui/` (frontend). `python_web/` no se toca.
- Backend: Flask sobre los bindings `qfpy` (el `.so` de `build/src/` está compilado para el Python 3.8 de anaconda: el backend corre con ese intérprete y su sintaxis). Persistencia con `sqlite3` de la stdlib en `desk/data/desk.db` (ignorado por git). Sin ORM.
- Toda la matemática financiera vive en C++ y se expone por `qfpy`. El backend Python solo orquesta, valida y serializa; no reimplementa fórmulas de pricing. Lo que falte en la biblioteca se añade en C++ siguiendo la convención de tres archivos del `CLAUDE.md` (hpp + cpp + test GoogleTest) y se expone en `qfpy`.
- Frontend: React 18 + TypeScript + Vite. Dependencias permitidas: `ag-grid-community` (tablas), `echarts` (gráficas), `cmdk` (paleta de comandos), `react-router-dom`, y para pruebas `vitest` + `@testing-library/react`. CSS propio con variables (tokens de color, espaciado, tipografía); sin Tailwind ni librerías de componentes. Tipografía: Inter para texto, JetBrains Mono para cifras.
- En producción el backend sirve el `dist/` del frontend: un solo puerto, 5070.
- Interfaz en español. Montos con separador de miles y moneda; tasas en % con 4 decimales; fechas ISO.

## Convenciones de mercado (decididas)
- TIIE de Fondeo: swap OIS, cupones cada 28 días, ACT/360, tasa flotante compuesta diaria. Descuento y proyección con la curva `TIIE-F`.
- SOFR: swap OIS, cupones anuales, ACT/360, curva `SOFR`.
- USDMXN: forward por paridad cubierta de tasas con las curvas `TIIE-F` (MXN) y `SOFR` (USD). Opciones vainilla europeas con Garman-Kohlhagen y vol tomada de la superficie por plazo y strike.
- Moneda de reporte del portafolio: MXN. Lo denominado en USD se convierte al spot del snapshot.
- Datos de mercado: sintéticos pero realistas, en un snapshot sembrado `MX-DEMO`. Todo dato sintético se etiqueta como tal.

## Requisitos

### Backend
- R1 **Mercado.** Existe el snapshot `MX-DEMO` con cotizaciones de las curvas `TIIE-F` y `SOFR`, spot USDMXN y una superficie de vol USDMXN. `GET /api/market/snapshots` lo lista; `GET /api/market/snapshots/<id>` devuelve cotizaciones y, por curva, puntos con plazo, tasa cero, factor de descuento y forward. `PUT /api/market/snapshots/<id>` cambia cotizaciones y las curvas se recalculan: tras subir 10 pb todas las cotizaciones de `TIIE-F`, todo factor de descuento de esa curva a plazo > 0 baja.
- R2 **Pricers.** `POST /api/price/<producto>` para `irs` (TIIE-F y SOFR), `fx_forward`, `fx_option`, `cap_floor`, `swaption`, `bond` y `equity_option`. Cada respuesta trae `pv`, `currency`, medidas de riesgo propias del producto (DV01 para tasas; delta, gamma, vega para opciones) y, para `irs` y `bond`, la tabla de flujos (fecha, monto, factor de descuento, valor presente). Comprobaciones con pytest:
  - un `irs` pactado a su tasa par vale |PV| < 1e-6 × nocional;
  - `fx_forward` coincide con `N·(S·DF_usd − K·DF_mxn)` calculado en el test, a 1e-8 relativo;
  - `fx_option` cumple paridad put-call contra el forward a 1e-8 relativo;
  - la suma de PV de los flujos de un `irs` iguala su `pv` a 1e-8 relativo.
- R3 **Portafolio.** CRUD de operaciones en `/api/trades` (crear, listar, borrar), persistidas en SQLite: sobreviven a reiniciar el backend. `GET /api/portfolio/valuation?snapshot=<id>` devuelve PV por operación, PV total en MXN y, si una operación falla al valuar, su error sin tumbar al resto.
- R4 **Riesgo.** Sobre el portafolio y un snapshot:
  - `POST /api/risk/dv01`: DV01 por plazo y por curva (key-rate), más el total;
  - `POST /api/risk/scenarios`: P&L por operación y total ante choques paralelo ±N pb por curva, empinamiento y spot USDMXN ±X %;
  - `POST /api/risk/var`: VaR paramétrico delta-normal con horizonte y confianza dados, usando volatilidades y correlaciones de factores guardadas en el snapshot.
  Comprobaciones: la suma del DV01 por plazo difiere menos de 2 % del DV01 por desplazamiento paralelo de 1 pb; el escenario paralelo +1 pb difiere menos de 2 % del DV01 total; para un portafolio con un solo `fx_forward`, el VaR individual del factor USDMXN coincide con `|delta|·S·σ·z·√h` a 1e-6 relativo, y el VaR total coincide con ese mismo valor cuando las volatilidades de los factores de tasa se ponen en cero (ver Aclaraciones P2).
- R5 **Errores.** Toda entrada inválida (campo faltante, número negativo donde no cabe, producto o snapshot inexistente) responde 400 o 404 con JSON `{"error": ..., "field": ...}`; ningún endpoint responde 500 ante entrada inválida. Hay tests que lo recorren por endpoint.

### Interfaz
- R6 **Marco.** Tema oscuro denso tipo terminal. Navegación lateral con Mercado, Pricers, Portafolio, Riesgo y Metodología. Barra superior con selector global de snapshot y distintivo visible "Datos sintéticos" cuando el snapshot lo es. Paleta de comandos con Ctrl+K que lleva a cualquier pantalla y a cada pricer. Usable a 1280×800 sin scroll horizontal.
- R7 **Mercado.** Por curva: gráfica de tasa cero y forward, y tabla de cotizaciones editable; al editar se guarda y la gráfica se actualiza. Superficie de vol como mapa de calor plazo × strike. Spot USDMXN editable.
- R8 **Pricers.** Un formulario por producto de R2 con valores por defecto sensatos para México; el resultado muestra PV, medidas de riesgo, tabla de flujos donde aplique y una gráfica (perfil de flujos para tasas; payoff para opciones). Botón "Agregar al portafolio" que crea la operación. Los errores del backend se muestran junto al campo que los causa.
- R9 **Portafolio.** Blotter con columnas ordenables y filtrables (id, producto, contraparte, nocional, moneda, vencimiento, PV en MXN), fila de total, borrar operación y exportar a CSV. Revalúa al cambiar de snapshot.
- R10 **Riesgo.** Escalera de DV01 por plazo (barras, una serie por curva), tabla de escenarios con P&L por operación y total, y tarjeta de VaR con horizonte y confianza editables.
- R11 **Metodología.** Página que documenta, por producto, modelo, convenciones y curvas usadas, y declara los límites del corte (datos sintéticos, sin XVA, un usuario).

### Entrega
- R12 **Arranque y pruebas.** `desk/run.sh` construye la interfaz y levanta todo en el puerto 5070; `desk/README.md` explica instalación y uso. Pasan: `ctest` completo (ningún test existente roto), `pytest desk/api/tests` y `npm test` y `npm run build` en `desk/ui` sin errores de TypeScript. Con el servidor arriba, `curl localhost:5070/` devuelve la app y `curl localhost:5070/api/market/snapshots` devuelve `MX-DEMO`.
- R13 **Semilla de demostración.** Primer arranque con base vacía: se siembran `MX-DEMO` y un portafolio de ejemplo de al menos 6 operaciones que cubre `irs` TIIE-F, `irs` SOFR, `fx_forward`, `fx_option` y `cap_floor`, de modo que las cuatro pantallas muestran contenido sin capturar nada.

## Fuera de alcance
Login, usuarios y permisos; XVA/CVA en la interfaz; reportes PDF; pruebas de efectividad de coberturas; datos de mercado reales o en vivo; TIIE a 28 días (la tasa vieja); despliegue en ThinkCentre; licencia y precio; borrar o modificar `python_web/`; push o PR.

## Restricciones
- Commits pequeños por tarea en `feat/qf-desk`, sin `Co-Authored-By`, mensaje que explica el porqué.
- Sin dependencias fuera de las listadas. Sin flags, opciones ni pantallas no pedidas.
- Validación en la frontera del API; nunca confiar en el frontend.

## Aclaraciones (respuestas a Opus)
- P1: se aprueba `jsdom` como dependencia de desarrollo. Fuentes empaquetadas con `@fontsource/inter` y `@fontsource/jetbrains-mono` (aprobadas); nada de CDN externos: la app debe funcionar sin internet.
- P2: factores de riesgo del VaR: exactamente tres, `USDMXN` (rendimiento relativo del spot), `TIIE-F` paralelo y `SOFR` paralelo (en pb). No hay factores por plazo. Exposición por factor: delta FX × spot para `USDMXN`; DV01 paralelo por curva para los de tasa. El snapshot guarda volatilidad diaria de cada factor y la matriz de correlación 3×3. La respuesta trae el VaR total y el VaR individual de cada factor. `/api/risk/var` acepta opcionalmente volatilidades de factores que sustituyen a las del snapshot (así se cumple la comprobación de R4).
- P3: correcto. Cap/floor y swaption con Hull-White; `a` y `σ` por curva viven en el snapshot, se muestran de solo lectura en Mercado y se declaran en Metodología.
- P4: aceptado (`as_of` 2026-11-10, días naturales, t = días/365, SOFR en periodos de 365 días). Se declara en Metodología como límite.
- P5: `bond` usa la clase `Bond` uniforme con curva elegible, por defecto `TIIE-F`. La convención de M-Bono de 182 días queda fuera de alcance y se declara en Metodología.
- P6: correcto: `MXN 1,234,567.89`.
- P7: aceptado: el payoff al vencimiento es cálculo de presentación y puede vivir en el frontend. PV y griegas siempre vienen del backend.
- P8: correcto. `equity_option` aporta su PV al portafolio; en DV01, escenarios y VaR su contribución es cero y Metodología lo dice.
- P9: basta con derivarlos de los parámetros y el `as_of` del snapshot. Que las operaciones no envejecen entre snapshots se declara en Metodología como límite.
- P10: aceptado: rama desde `master` y commits con `GRAPHIFY_SKIP_HOOK=1`; el último commit de T15 va sin esa variable para que el grafo se regenere una vez.
- P11 (hueco detectado en T8): una operación `irs` guardada no puede quedar sin tasa fija, porque se revaluaría siempre a la par y su PV, DV01, escenarios y VaR darían cero. `POST /api/trades` con `irs` sin `fixed_rate` responde 400 con `field: "fixed_rate"`. En el pricer, tras valuar un `irs` con la tasa en blanco, el campo se rellena con la tasa par devuelta (`details.fixed_rate`) para que "Agregar al portafolio" la guarde. Las operaciones de la semilla llevan `fixed_rate` explícito.
- P12: cotas de entrada para que ningún valor absurdo cuelgue el cálculo: `periods` ≤ 1200, días de vencimiento ≤ 18250, años ≤ 50; fuera de eso, 400 con el campo.
