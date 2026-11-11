# QF Desk — Corte 8 (alcance reducido): fijaciones reales, respaldo y carga por pantalla

Repositorio `/home/claudio/Git/Quant_Finance`, rama `feat/qf-desk`. Leer `CLAUDE.md` del repo y `desk/README.md`.

## Intención

El roadmap dice que el corte 8 (usuarios, empresas separadas, datos reales, despliegue) "no se dimensiona hasta tener un primer cliente piloto". Sin piloto, se construye solo lo que ya tiene respuesta única y no depende de requisitos de un cliente: (a) fijaciones reales de SOFR desde la Fed de Nueva York, que es pública y sin token; (b) el cliente de Banxico para TIIE de Fondeo y FIX, listo y probado con respuestas simuladas, que se activa cuando exista el token (lo genera Claudio: lleva captcha); (c) respaldo y restauración de la base; (d) la deuda del corte 1 de cargar la interfaz por pantalla. Usuarios, roles, aprobación de dos personas, empresas separadas, contenedores, licencia e importación de archivos de PiP/Valmer quedan fuera y declarados.

## Requisitos

- **R1 — SOFR real.** `POST /api/fixings/fetch` con `{"index": "SOFR", "from": "YYYY-MM-DD", "to": "YYYY-MM-DD"}` descarga las fijaciones de SOFR de la API pública de la Fed de Nueva York (`https://markets.newyorkfed.org/api/rates/secured/sofr/search.json?startDate=…&endDate=…`), las convierte a la unidad que ya usa la tabla `fixings` y las inserta. Es idempotente: repetir la llamada no duplica ni cambia nada. Si ya existe una fijación de esa fecha con otro valor, NO la sobrescribe: la cuenta y la lista en `conflicts` (fecha, valor guardado, valor de la fuente). Respuesta 200: `{index, source, from, to, fetched, inserted, unchanged, conflicts: [...]}`. Rango inválido o mayor a 366 días → 400. Fallo de red o respuesta ilegible → 502 con mensaje en español y sin cambios en la base (todo o nada). Pruebas con HTTP simulado (sin red en la suite) usando una respuesta real guardada como fixture.
- **R2 — Banxico listo, inactivo sin token.** Mismo endpoint con `index` `TIIE-F` (TIIE de Fondeo a un día) y `USDMXN` (FIX) contra la API SIE de Banxico (`https://www.banxico.org.mx/SieAPIRest/service/v1/series/<id>/datos/<from>/<to>`, token en la cabecera `Bmx-Token`). El token se lee solo de la variable de entorno `BANXICO_TOKEN`; nunca se escribe en la base, en respuestas ni en logs. Sin token → 409 con `{"error": "Falta el token de Banxico (variable BANXICO_TOKEN)", "code": "banxico_token_missing"}`. Los identificadores de serie deben verificarse en el catálogo público de Banxico y quedar citados en un comentario con la URL de donde salieron; si alguno no se puede verificar, se deja declarado en el README como "sin verificar", no inventado. Pruebas con HTTP simulado: éxito, token ausente, 401 de Banxico, dato "N/E" (se omite), conflicto.
- **R3 — Procedencia visible.** `GET /api/fixings/sources` devuelve por índice: fuente, si está disponible (`available`), motivo si no, y la última fecha guardada. La pantalla de fijaciones existente gana, por índice, un botón "Traer de la fuente" (rango: desde el día siguiente a la última fijación guardada, o 30 días atrás si no hay, hasta la fecha de valuación activa) que muestra el resultado (insertadas, sin cambio, conflictos) y, para Banxico sin token, el motivo en vez del botón activo. Sin desborde horizontal a 1280 px.
- **R4 — Respaldo y restauración.** `python -m desk.api.backup <destino_dir> [--keep N]` hace una copia consistente de la base SQLite con la API de respaldo en línea de `sqlite3` (válida con el servidor encendido), con nombre `qfdesk-YYYYMMDD-HHMMSS.sqlite`, corre `PRAGMA integrity_check` sobre la copia y sale ≠ 0 si falla; `--keep N` borra las copias más viejas que excedan N (por omisión no borra nada). `python -m desk.api.backup --restore <archivo> ` restaura SOLO si la base destino no existe o se pasa `--force`, y antes de pisar hace una copia de la actual junto a ella. Prueba: respaldar una base con operaciones, eventos y fijaciones, restaurar en otra ruta y comprobar mismos conteos por tabla y que los disparadores de solo inserción siguen activos.
- **R5 — Carga por pantalla.** Las pantallas se cargan con `React.lazy` por ruta y la biblioteca de gráficas queda en su propio trozo, de modo que el trozo de entrada de `npm run build` pese ≤ 500 kB (minificado, sin gzip). Navegar a cada una de las pantallas del menú y a la ficha de una operación sigue funcionando (comprobado en navegador contra el backend real, sin errores de consola), con un estado de carga accesible mientras llega el trozo.
- **R6 — Documentación.** `desk/README.md` documenta: variables de entorno (incluida `BANXICO_TOKEN` y cómo obtenerla), `fetch` de fijaciones, respaldo/restauración con un ejemplo de cron, y la lista de lo que el corte 8 NO hace. Metodología → "Fuentes de datos" declara SOFR (Fed de Nueva York, fijaciones reales) y Banxico (pendiente de token), sin presentar nada sintético como real.
- **R7 — Suites.** Pasan `ctest`, `cmake --build build --target pytests`, `pytest desk/api/tests` y `npm test` + `npm run build`; ninguna prueba anterior cambia de resultado salvo las que cuentan pantallas o trozos, justificadas.

## Decisiones de arquitectura

- Módulos nuevos `desk/api/nyfed.py` y `desk/api/banxico.py`, con el mismo estilo que `desk/api/fred.py` (urllib de la stdlib, `User-Agent` por omisión, timeout, parser separado del fetch). Sin dependencias nuevas.
- Orquestación en `desk/api/fixings_fetch.py`; rutas nuevas en `desk/api/routes/fixings.py`. Reusar `fixings.py` para validar e insertar; no duplicar reglas (fines de semana, índices).
- La tabla `fixings` no cambia de esquema salvo que ya tenga columna de fuente; si no la tiene, la procedencia se informa en la respuesta y en `/api/fixings/sources`, sin migración.
- Las peticiones salientes no llevan ningún dato del usuario ni del portafolio (solo fechas y serie).
- `backup.py` usa `sqlite3.Connection.backup`; ruta de la base como la resuelve `desk/api/db.py`.
- No tocar el puerto 5070 ni `~/Git/MarketDataFeed`; backend de prueba en 5088, Chrome headless en 9348.

## Fuera de alcance (declarar en README y roadmap)

Usuarios, roles y aprobación de dos personas; empresas separadas; contenedores; licencia y términos; importación de PiP/Valmer/Bloomberg; curvas reales de TIIE-F (siguen sintéticas); carga automática programada de fijaciones.

## Restricciones

`lean-dev-workflow` §2–§3: sin flags ni opciones no pedidas, validación en fronteras. Commits en español con el porqué, sin Co-Authored-By: `GRAPHIFY_SKIP_HOOK=1 git commit -m "…" -- <rutas explícitas>`; sin push, sin `git stash`, sin `graphify-out/` ni `docs/` en commits de tareas. Python del backend: `/home/claudio/anaconda3/bin/python` (3.8).

## Respuestas de Fable a las preguntas del plan

- **P1.** Ampliar `errors.py`: `ApiError` acepta un `code` opcional que se incluye en el JSON solo si se da. El 409 del token no lleva `field`.
- **P2.** `conflicts`: `[{"date", "stored", "source"}]` (valores en la unidad de la tabla). `source` de la respuesta: `"Fed de Nueva York"` o `"Banxico (SIE)"`. `fetched` = número de observaciones válidas que devolvió la fuente en el rango (= inserted + unchanged + len(conflicts)). `GET /api/fixings/sources` → `{"sources": [{"index", "source", "available", "reason", "last_date"}]}` en el orden de `fixings.INDICES`; `reason` y `last_date` son `null` cuando no aplican.
- **P3.** El valor de la fuente se redondea a 10 decimales tras convertir (`round(x/100, 10)`), y "mismo valor" se decide con tolerancia absoluta 1e-9.
- **P4.** Cualquier respuesta 400/401/403 de Banxico → el desk responde 502 con `"Banxico rechazó el token (BANXICO_TOKEN)"` y `code: "banxico_token_rejected"`. La prueba cubre 400 (el caso real observado) y 401.
- **P5.** La copia previa se llama `<base>.antes-de-restaurar-YYYYMMDD-HHMMSS`. No se detecta si el servidor está encendido: el README dice que se restaura con el servidor apagado. Las funciones aceptan rutas; el CLI no gana `--db`.
- **P6.** Sí, `snapshot.as_of` de `useSnapshot`, leído del contexto por el panel.
- **P7.** Botón deshabilitado con el texto "Al día".
- **P8.** T7 se lanza cuando el agente de swaption ya terminó; no hay fallos ajenos aceptables.
- **P9.** Sí: se aceptan tal cual las fechas que publique la fuente. Se retira la mención a fines de semana.
- **P10.** Las tareas declaran lo fuera de alcance solo en `desk/README.md`; Fable actualiza el roadmap al cerrar.
- **P11.** Sí, T1 puede hacer una petición real a la NY Fed para guardar el fixture.
