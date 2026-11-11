# Validación independiente del desk contra QuantLib

Comprueba que los siete pricers del desk (swap OIS, forward y opción USDMXN, opción sobre acción, bono, cap/floor y
swaption) dan el mismo PV que una implementación ajena, **QuantLib 1.44**, a partir de las mismas curvas y de los mismos
parámetros. El resultado es `report.json`, que el backend sirve en `GET /api/validation/report` y la pantalla
**Validación** de la interfaz muestra.

## Qué valida y qué no

Valida:

- **Curvas**: QuantLib reconstruye cada curva desde los factores de descuento (DF) que exporta el desk y se comparan en los
  pilares y en diez fechas intermedias. Es la prueba de que la interpolación (lineal sobre la tasa cero continua, plana
  fuera de los pilares) es la misma.
- **PV** de 62 casos: las 7 operaciones del portafolio de ejemplo y una batería fija (de 8 a 12 casos por producto).
  Diferencia relativa = `|PV_desk − PV_ref| / nocional`, comparada con la tolerancia del producto.

No valida: el bootstrap de las curvas (QuantLib recibe los DF ya armados), la interpolación de la superficie de
volatilidad (las opciones USDMXN usan la σ que el desk leyó, así se comprueba la fórmula), envejecimiento de operaciones,
fijaciones, riesgos y griegas, coberturas ni XVA. El portafolio se valúa solo en el `as_of` del snapshot `MX-DEMO`.
QuantLib trabaja con fechas enteras: los plazos de la batería caen en días enteros (el bono semestral por omisión, de
182.5 días, es el caso que prueba esa convención).

## Entorno

- **Backend** (`export_cases`, `compare`): el Python del backend (`/home/claudio/anaconda3/bin/python`, 3.8). No importa
  QuantLib: ninguna suite del repo lo necesita.
- **Referencia** (`run_quantlib.py`): entorno conda `quantsuite-oracle`, Python 3.12 y QuantLib 1.44
  (`/home/claudio/anaconda3/envs/quantsuite-oracle/bin/python`). En otra máquina basta un entorno equivalente:
  `python -m venv ql && ql/bin/pip install QuantLib==1.44`, y apuntar `QL_PY` a su `python`.

## Regenerar

```bash
desk/validation/make_report.sh
```

Corre los tres pasos y termina con código 0 si ningún caso queda fuera de tolerancia y las curvas coinciden (con 1 si no,
pero `report.json` se escribe igual). Variables opcionales para otra máquina: `BACKEND_PY` y `QL_PY`.

Los pasos sueltos, desde la raíz del repositorio:

```bash
python -m desk.validation.export_cases          # → cases.json   (Python del backend)
$QL_PY desk/validation/run_quantlib.py          # → reference.json (Python de QuantLib; admite --cases y --out)
python -m desk.validation.compare               # → report.json  (Python del backend)
```

## Archivos

| Archivo | Quién lo escribe | Qué contiene |
|---|---|---|
| `common.py` | a mano | constantes, tolerancias, rutas, `desk_commit`/`desk_dirty`, `diffs`, `classify` |
| `export_cases.py` | a mano | la batería de casos y el PV del desk; escribe `cases.json` |
| `cases.json` | `export_cases` | snapshot, curvas con sus DF, Hull-White, casos (`params`, `inputs`, `pv_desk`) y procedencia |
| `ql_curves.py`, `ql_rates.py`, `ql_hw.py`, `ql_fx.py`, `run_quantlib.py` | a mano | curvas y pricers de QuantLib |
| `reference.json` | `run_quantlib` | DF y PV de QuantLib por caso, y el método usado por producto |
| `known_differences.json` | a mano | diferencias que exceden la tolerancia y su explicación |
| `compare.py` | a mano | compara, clasifica y escribe `report.json` |
| `report.json` | `compare` | lo que sirve el backend: totales, resumen por producto, curvas, casos y diferencias conocidas |

`cases.json` y `reference.json` se versionan junto al reporte para que un tercero repita la comparación (`compare`) sin
QuantLib.

## Tolerancias

Diferencia relativa al nocional (para `fx_*` es `notional_usd × spot` en MXN; para `equity_option`, `quantity × spot`):
`irs` 1e-6, `fx_forward` 1e-8, `fx_option` 1e-6, `equity_option` 1e-6, `bond` 1e-6, `cap_floor` 5e-4, `swaption` 5e-4.
Curvas: 1e-12 en pilares y 1e-8 en fechas intermedias (diferencia absoluta de DF). Están en `common.py`.

Veredicto por caso: `ok` (dentro de tolerancia), `explained` (la excede pero la acota una entrada de
`known_differences.json`) y `fail`.

## Diferencias conocidas

Una entrada por caso que excede su tolerancia, nunca por casos que ya están dentro. Campos: `case_id`,
`kind` (`convention`, `interpolation` o `defect`), `convention` (título corto), `cause` (qué difiere y cuánto explica, con
el procedimiento para reproducirlo), `expected_rel_diff` (calculado con ese procedimiento; debe quedar a ±10 % de la
diferencia observada) y `max_rel_diff` (cota con la que se clasifica el caso). `defect` es un defecto del desk que sigue
abierto.

Hoy no hay ninguna: `known_differences.json` está vacío y los 62 casos quedan dentro de su tolerancia. La última que hubo
fue **`swaption-04`** (receptora TIIE-F, expira en 182 días), un defecto de `Swaption::price` en C++: la raíz de Jamshidian
quedaba fuera del intervalo de bisección y el desk devolvía 0.0 donde QuantLib da 92,158.63 MXN, y además omitía el
término de varianza del factor A de Hull-White. Se corrigió en C++ (commit `2f5b733`, con pruebas en
`tests/test_swaption.cpp`) y la entrada se borró; desde entonces las ocho swaptions coinciden con QuantLib a 3e-9 del
nocional o menos.

## Agregar un caso

1. Añadir una fila a la tabla de su producto en `export_cases.py` (`_IRS_BATTERY`, `_FX_FORWARD_BATTERY`,
   `_FX_OPTION_BATTERY`, `_EQUITY_BATTERY`, `_BOND_BATTERY`, `_CAP_FLOOR_BATTERY`, `_SWAPTION_BATTERY`) al final, para no
   renumerar los ids. Con plazos en días enteros.
2. Commitear (ver abajo) y correr `desk/validation/make_report.sh`.
3. Si el caso excede su tolerancia, entender por qué: un defecto en Python del desk se corrige con su test; una convención
   o un defecto en C++ va a `known_differences.json`.

Un producto nuevo necesita además su pricer en `ql_*.py` (`PRICERS` y `METHODS`) y su entrada en `common.py`
(`PRODUCTS`, `PRODUCT_LABELS`, `TOLERANCES`).

## Aviso de commit y `desk_dirty`

`report.json` guarda `desk_commit`: el último commit que tocó el código de valuación (`VALUATION_PATHS` en `common.py`:
`src`, `include`, `CMakeLists.txt`, los pricers, el mercado, la valuación, los datos de ejemplo y `export_cases.py`). No es
`HEAD`, porque commitear el reporte lo cambiaría y el aviso saldría siempre. El backend lo vuelve a calcular en cada
petición: si difiere del guardado, la pantalla avisa de que la valuación cambió después de generar el reporte.
`desk_dirty` indica si había cambios sin commitear en esas rutas al generarlo.

Por eso **hay que commitear el código antes de regenerar**: así `desk_commit` es el definitivo y `desk_dirty` queda en
`false`. Tras fusionar cambios que toquen la valuación (por ejemplo, otro corte de curvas), el aviso aparecerá, y es lo
correcto: se regenera.

## Prueba de humo

`desk/api/tests/test_validation_report.py` forma parte de la suite del backend (no usa QuantLib): recalcula las
diferencias y los veredictos de `report.json`, comprueba que cuadren los totales y el resumen, que haya al menos 60 casos y
5 por producto, que las diferencias conocidas estén explicadas y acotadas, y que ningún caso falle. Si alguien edita un PV a
mano o deja el reporte sin regenerar, falla.
