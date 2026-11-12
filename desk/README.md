# QF Desk

Aplicación local para valuar y medir riesgo de una cartera demo (`MX-DEMO`, datos sintéticos) con el motor C++ de Quant_Finance. El backend Flask llama a `qfpy` para toda la matemática financiera; la UI (React + TypeScript) consume la API.

## Requisitos

- Python 3.8 de Anaconda con Flask 2.3.3 y pytest 8.2.0 (`/home/claudio/anaconda3/bin/python`).
- Node 22 y npm 10.
- CMake y compilador C++20.
- GoogleTest (tests C++) y pybind11 (bindings `qfpy`).
- QuantLib 1.42.1 para Python (pricers de exóticos FX).

## Instalación

Desde la raíz del repo `Quant_Finance`:

```bash
/home/claudio/anaconda3/bin/python -m pip install "QuantLib==1.42.1"
cmake -S . -B build
cmake --build build -j4
cd desk/ui && npm ci && cd ../..
```

## Ejecutar

```bash
./desk/run.sh
```

El script compila `qfpy` si falta `build/src/qfpy*.so`, construye la UI con `npm run build` y levanta el servidor. Abrir `http://localhost:5070`.

Para usar otro intérprete de Python: `QF_PYTHON=/ruta/a/python ./desk/run.sh`.

## Variables de entorno

- `BANXICO_TOKEN`: token de la API SIE de Banxico, necesario solo para traer TIIE de Fondeo (SF331451) y FIX (SF43718) desde la fuente. Se lee solo del entorno del proceso del backend; nunca se guarda en base ni se devuelve en respuestas. Se obtiene registrándose en el portal SIE API de Banxico (https://www.banxico.org.mx/SieAPIRest/service/v1/token), que pide captcha; lo genera el usuario. Sin ella, el resto de la aplicación funciona igual.
- `MDF_DB`: base de MarketDataFeed (por omisión `~/Git/MarketDataFeed/build/sofr.db`).
- `MDF_FETCH`: ejecutable `fetch_sofr` de MarketDataFeed (por omisión `examples/fetch_sofr` dentro del directorio de `MDF_DB`: con `MDF_DB` sin definir es `~/Git/MarketDataFeed/build/examples/fetch_sofr`, pero si solo se define `MDF_DB` el ejecutable que se busca cambia con ella).

## Fijaciones desde la fuente

`POST /api/fixings/fetch` trae fijaciones de la fuente y las guarda para el índice indicado. Cuerpo `{"index": "SOFR" | "TIIE-F" | "USDMXN", "from": "YYYY-MM-DD", "to": "YYYY-MM-DD"}`, rango máximo de 366 días.

```bash
curl -X POST localhost:5070/api/fixings/fetch -H 'Content-Type: application/json' -d '{"index":"SOFR","from":"2026-11-02","to":"2026-11-06"}'
```

Respuesta de ejemplo (200):

```json
{"index": "SOFR", "source": "Fed de Nueva York", "from": "2026-11-02", "to": "2026-11-06",
 "fetched": 4, "inserted": 3, "unchanged": 1, "conflicts": []}
```

- No sobrescribe lo guardado: un valor distinto del almacenado se lista en `conflicts` (`date`, `stored`, `source`) y no se cambia. Las tasas se guardan en decimal (0.0389 = 3.89 %).
- Errores: 400 (índice, fechas o rango inválidos, con `field`); 409 con `code: "banxico_token_missing"` (falta `BANXICO_TOKEN`, solo TIIE-F y USDMXN); 502 (la fuente no respondió, devolvió un valor inválido, o Banxico rechazó el token con `code: "banxico_token_rejected"`). En 409 y 502 no se escribe nada.
- Un rango sin datos en la fuente responde 200 con todo en cero.
- `GET /api/fixings/sources` indica para cada índice la fuente, si está disponible (`available`, y `reason` si no), y su última fecha (`last_date`).
- SOFR viene de la Fed de Nueva York y son fijaciones reales. La integración con Banxico está lista pero **sin probar contra un token real**: el formato de respuesta de éxito no está verificado. Los identificadores de serie se comprobaron en el catálogo público del SIE (SF331451 y SF43718). Un rango sin observaciones en Banxico podría responder 404; hoy ese caso se vería como 502 genérico.

## Respaldo y restauración

```bash
# Respaldo (válido con el servidor encendido)
/home/claudio/anaconda3/bin/python -m desk.api.backup /ruta/respaldos --keep 14

# Restauración (con el servidor APAGADO; el CLI no lo detecta)
/home/claudio/anaconda3/bin/python -m desk.api.backup --restore /ruta/respaldos/qfdesk-20261111-153000.sqlite --force
```

- El CLI siempre actúa sobre `desk/data/desk.db`; no hay flag `--db`.
- Las copias llevan la hora local en el nombre: `qfdesk-YYYYMMDD-HHMMSS.sqlite`; si ya hay una de ese segundo, la nueva lleva `-2`, `-3`... y la anterior no se toca.
- Al restaurar con `--force`, la base actual se guarda antes como `<base>.antes-de-restaurar-YYYYMMDD-HHMMSS` (hora local) y el CLI indica la ruta.
- `--keep N` borra las copias más viejas y conserva N; solo cuenta y borra archivos cuyo nombre es exactamente `qfdesk-YYYYMMDD-HHMMSS.sqlite` (con `-N` opcional), nunca otros del directorio.

Ejemplo de cron (respaldo diario a las 02:30):

```
30 2 * * * cd /home/claudio/Git/Quant_Finance && /home/claudio/anaconda3/bin/python -m desk.api.backup /ruta/respaldos --keep 14
```

## Datos

- Base SQLite: `desk/data/desk.db` (no versionada; se crea y siembra al arrancar).
- `MX-DEMO` es una cartera sintética generada por el seed; no representa posiciones reales.

## Datos de mercado reales

- `MKT-LIVE` se construye desde la base de MarketDataFeed (SOFR y Treasuries) y FRED (DEXMXUS). Se actualiza con el botón "Actualizar datos" de la pantalla Mercado o con `POST /api/market/refresh`. Es de solo lectura y cada actualización lo reescribe por completo. `MX-DEMO` no cambia.
- Rutas por omisión (sobrescribibles con variables de entorno):
  - `MDF_DB`: `~/Git/MarketDataFeed/build/sofr.db`
  - `MDF_FETCH`: `<directorio de MDF_DB>/examples/fetch_sofr` (con `MDF_DB` por omisión, `~/Git/MarketDataFeed/build/examples/fetch_sofr`)
- Actualizar la base a mano:

  ```bash
  ~/Git/MarketDataFeed/build/examples/fetch_sofr --latest --treasury --db ~/Git/MarketDataFeed/build/sofr.db
  ```

- Sigue sintético: TIIE-F, superficie de volatilidad, parámetros Hull-White y correlaciones. El detalle de fuentes está en la pantalla Metodología.

## Lo que el corte 8 NO hace

Quedan fuera hasta tener un cliente piloto, cuyos requisitos mandan: usuarios, roles y aprobación de dos personas; empresas separadas; contenedores; licencia y términos de uso; importación de archivos de PiP, Valmer o Bloomberg; curvas reales de TIIE-F (siguen sintéticas); y la carga automática programada de fijaciones (hoy se piden con el botón o con `POST /api/fixings/fetch`).

## XAD y su licencia

Las sensibilidades del XVA se calculan por diferenciación adjunta con [XAD](https://github.com/auto-differentiation/xad) (Xcelerit Computing Ltd.), que CMake descarga con `FetchContent` y compila junto con `qf` (opción `QF_WITH_XAD`, activa por omisión).

- **Licencia.** XAD es software libre bajo la **GNU AGPL-3.0 (o posterior)**. Xcelerit la ofrece además con licencia comercial aparte para uso en producción sin las obligaciones de la AGPL.
- **Implicación.** Quien use el servicio a través de la red tiene derecho al código fuente completo de la aplicación, salvo que exista una licencia comercial de XAD. El repositorio es hoy público, así que no hay conflicto inmediato. Si QF Desk se ofrece a un cliente sin publicar su código, hace falta la licencia comercial: es una decisión de negocio pendiente de Claudio.
- **Versión fijada.** v2.2.0, commit `aaf4e9cad59cf1bfe9728b491f95f011db687f18`, publicada el 2026-11-11. Es una versión recién publicada: revisar su estabilidad al actualizarla. v2.1.0 no sirve, porque `resetTo` y `clearDerivativesAfter` degradan la cinta por trayectoria (el tiempo por trayectoria crece con el número de trayectorias).
- **Apagarla.** `cmake -S . -B build -DQF_WITH_XAD=OFF`: todo compila sin XAD, `qfxva.HAS_XAD` vale `False` y la ruta de sensibilidades del XVA responde 501.

## Tests

Desde la raíz del repo:

```bash
# C++ (518 tests con XAD, 510 con -DQF_WITH_XAD=OFF)
cmake --build build -j4 2>&1 | tail -3 && cd build && ctest --output-on-failure 2>&1 | tail -3; cd ..

# Bindings Python existentes
cmake --build build --target pytests 2>&1 | tail -3

# Backend
/home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q 2>&1 | tail -3

# Frontend
cd desk/ui && npm test 2>&1 | tail -5 && npm run build 2>&1 | tail -5
```
