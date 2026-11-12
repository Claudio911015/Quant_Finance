# Plan — QF Desk, corte 11: documentación técnica en LaTeX

Diseño: `/tmp/fableorchestrate/qf-docs/design.md` (requisitos R1–R8). Repo `/home/claudio/Git/Quant_Finance`, rama `feat/qf-desk`.

## Contexto

Todo redactor lee esta sección completa y su tarea. Nada más es obligatorio, salvo el código y los documentos que su tarea enumera.

### 1. Reglas del corte (no negociables)

- **Solo se escribe en `docs/tex/`.** No se modifica código, pruebas, `CLAUDE.md`, `graphify-out/` ni nada fuera de `docs/tex/`. Otros agentes están cambiando código de XVA (`src/xva/`, `include/qf/xva/`, `src/python_bindings/xva_bindings.cpp`, `desk/api/risk/credit*.py`, `desk/api/seed_trades.py`, etc.) en el mismo árbol: ignorar sus cambios, no tocarlos, no incluirlos en commits, no documentarlos (XVA es el capítulo 14, marcador).
- No levantar servidores (`desk/run.sh`, Flask, Vite). No `git stash`, no `git push`, no `git checkout`/`reset` de nada.
- Documentar **lo que el código hace**, no la teoría del libro. Cada fórmula corresponde a una función concreta y dice sus convenciones reales (base de días, composición, interpolación, signo, unidades, fecha de valuación). Si el código se aparta del libro: recuadro `diferencia` (§4). Si el código hace algo incorrecto o distinto de lo que declara la Metodología de la aplicación: **no se corrige ni se maquilla**, se anota en `docs/tex/HALLAZGOS.md` (archivo, símbolo, explicación) y el capítulo describe lo que el código hace.
- No describir como hecho nada que el código no haga (R6).
- **Prohibido inventar referencias** (§6).

### 2. Estructura de `docs/tex/` (la crea T1; nombres exactos)

```
docs/tex/
  qfdesk.tex                 documento maestro: \documentclass{report}, \input{preambulo}, portada, \tableofcontents, \include de cada capítulo, \appendix, apéndice, bibliografía
  preambulo.tex              paquetes, macros, notación, entornos (único lugar con \newcommand)
  referencias.bib            bibliografía (compartida; regla de §6)
  README.md                  cómo compilar, cómo correr las dos verificaciones, lista de comprobación para añadir un capítulo (R7)
  HALLAZGOS.md               discrepancias código ↔ Metodología encontradas al documentar (compartido; añadir al final)
  .gitignore                 productos de compilación (*.aux, *.log, *.toc, *.out, *.bbl, *.blg, *.fls, *.fdb_latexmk, *.lof, *.lot, *.synctex.gz, qfdesk.pdf, capitulos/*.aux, __pycache__/)
  capitulos/
    _plantilla.tex           plantilla obligatoria de capítulo (R7); NO se incluye en qfdesk.tex
    cap01_introduccion.tex   (1) Introducción, arquitectura y convenciones           \label{cap:introduccion}
    cap02_curvas.tex         (2) Curvas                                               \label{cap:curvas}
    cap03_swaps_ois.tex      (3) Swaps de tasa OIS                                    \label{cap:swaps-ois}
    cap04_fx.tex             (4) Derivados de FX y opción sobre acción                \label{cap:fx}
    cap05_hull_white.tex     (5) Hull–White: bono, cap/floor, swaption                \label{cap:hull-white}
    cap06_bonos.tex          (6) Bonos                                                \label{cap:bonos}
    cap07_xccy.tex           (7) Cross currency swap                                  \label{cap:xccy}
    cap08_ciclo_vida.tex     (8) Ciclo de vida, liquidaciones y P&L                   \label{cap:ciclo-vida}
    cap09_riesgo.tex         (9) Riesgo                                               \label{cap:riesgo}
    cap10_coberturas.tex     (10) Contabilidad de coberturas IFRS 9                   \label{cap:coberturas}
    cap11_operaciones.tex    (11) Operaciones: conciliación                           \label{cap:operaciones}
    cap12_validacion.tex     (12) Validación contra QuantLib                          \label{cap:validacion}
    cap13_datos.tex          (13) Fuentes de datos y procedencia                      \label{cap:datos}
    cap14_xva.tex            (14) XVA y curvas de crédito — MARCADOR                  \label{cap:xva}
    cap15_exoticos_fx.tex    (15) Exóticos de FX — MARCADOR                           \label{cap:exoticos-fx}
    apendice_simbolos.tex    Apéndice A: tabla de símbolos (tabla común + \input de simbolos/capNN.tex)
  simbolos/
    cap01.tex … cap15.tex    filas de la tabla de símbolos propias de cada capítulo (cada redactor solo toca las suyas)
  verificacion/
    comun.py                 utilidades de los scripts de ejemplo (rutas, lectura del valor impreso, comparación)
    correr.py                corre todos los capNN_*.py; código 0 si todo pasa (≤ 60 líneas)
    referencias_codigo.py    comprueba todas las \codigo{…}{…} (≤ 60 líneas)
  plainnat-es.bst            copia de plainnat.bst con cadenas en español («y» entre autores)
    cap02_curvas.py … cap12_validacion.py   un script por capítulo 2–12 (nombre = nombre del .tex con .py)
```

Cada capítulo empieza con `\chapter{<título>}\label{cap:…}` (las etiquetas de arriba, fijas). Un redactor **solo** referencia con `\ref` etiquetas de su propio capítulo o las etiquetas `cap:…` de esta tabla; nunca etiquetas internas de otro capítulo. Etiquetas internas con prefijo del capítulo: `eq:capNN-…`, `sec:capNN-…`, `tab:capNN-…`.

### 3. Compilación

Paquetes verificados instalados: `natbib` + `plainnat.bst`, `amsmath`, `amsthm`, `booktabs`, `hyperref`, `listings`, `todonotes`, `tcolorbox`, `xcolor`, `geometry`, `lmodern`, `siunitx`, `cleveref`, `csquotes`, `microtype`, `doi`. **`babel` no tiene la opción `spanish` instalada** (`\usepackage[spanish]{babel}` falla con «Unknown option 'spanish'»). Lo que sí compila (probado): 

```latex
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[english]{babel}
\babelprovide[import,main]{spanish}   % títulos «Capítulo», «Índice» en español; partición de palabras con patrones ingleses
```

La partición con patrones ingleses está aceptada (el README la declara e indica instalar `texlive-lang-spanish` para quien quiera partición correcta). Estilo bibliográfico: `docs/tex/plainnat-es.bst`, copia de `plainnat.bst` con «and» → «y» (y «editor(s)», «edition», etc. en español cuando sea un cambio de cadena igual de simple); el documento usa `\bibliographystyle{plainnat-es}`.

Compilación oficial (R1), desde el repo:

```bash
cd docs/tex && latexmk -pdf -interaction=nonstopmode -halt-on-error qfdesk.tex; echo rc=$?
```

**Compilación privada durante las tareas paralelas** (para no pisar los `.aux` de otros redactores; probado con `\include` en subdirectorio y `bibtex`):

```bash
cd /home/claudio/Git/Quant_Finance/docs/tex && OUT=/tmp/qfdocs-$TAREA && rm -rf $OUT && mkdir -p $OUT/capitulos && \
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=$OUT qfdesk.tex >/dev/null 2>&1; echo rc=$?
```

Comprobaciones sobre el log (`$OUT/qfdesk.log` o `docs/tex/qfdesk.log`):

```bash
grep -cE "(Citation|Reference) .* undefined" $LOG                                     # esperado 0
grep -oE 'Overfull \\[hv]box \(([0-9.]+)pt' $LOG | grep -oE '[0-9.]+' | awk '$1>10' | wc -l   # esperado 0
```

Citas usadas vs entradas del `.bib` (con `\include` las citas quedan en `capitulos/*.aux`):

```bash
cd $OUT && cat qfdesk.aux capitulos/*.aux | grep -oP '\\citation\{\K[^}]+' | tr ',' '\n' | sort -u > /tmp/citadas-$TAREA.txt
grep -oP '^@\w+\{\K[^,]+' /home/claudio/Git/Quant_Finance/docs/tex/referencias.bib | sort -u > /tmp/bib-$TAREA.txt
comm -13 /tmp/citadas-$TAREA.txt /tmp/bib-$TAREA.txt   # entradas sin citar
comm -23 /tmp/citadas-$TAREA.txt /tmp/bib-$TAREA.txt   # citas sin entrada
grep -oP '\\citation\{\K[^}]+' $OUT/capitulos/capNN_*.aux | tr ',' '\n' | sort -u | wc -l   # citas distintas de un capítulo (≥ 2 en caps 2–12)
```

Mientras los capítulos se escriben en paralelo, las entradas de otros redactores pueden quedar sin citar y otros capítulos pueden estar a medias: el redactor solo exige 0 errores de compilación, 0 undefined y 0 cajas > 10 pt **atribuibles a su capítulo**; la tarea final exige el total.

### 4. Preámbulo: macros, notación y entornos (los fija T1; los redactores los usan y no definen otros)

Ningún capítulo usa `\newcommand`, `\renewcommand`, `\def` ni `\DeclareMathOperator`. Si un redactor necesita un símbolo que no está aquí, lo escribe con LaTeX explícito (`\Delta_i`, `w_k`), lo declara en la sección «Notación» de su capítulo y añade su fila a `simbolos/capNN.tex`. Macros que T1 define con estos nombres y significados (T1 puede ajustar el tipografiado, no los nombres ni el número de argumentos):

| Macro | Salida | Significado |
|---|---|---|
| `\codigo{ruta}{símbolo}` | `ruta`: `símbolo` en monoespaciada, partible en `/`, `_` y `.` | referencia al código (R4); ruta relativa a la raíz del repo, sin números de línea |
| `\verif{id}{valor}` | el `valor` tal cual (vía `\num`) | número de un ejemplo verificable; `id` = `capNN-nombre` único en todo el documento; `valor` en notación decimal con punto, sin separadores de miles, opcional signo y exponente `e` |
| `\DF{c}{T}` | $P_{c}(T)$ | factor de descuento de la curva `c` del valor (fecha $t_0$) a `T` |
| `\DFt{c}{t}{T}` | $P_{c}(t,T)$ | factor de descuento de `t` a `T` |
| `\zr{c}{T}` | $z_{c}(T)$ | tasa cero (la composición la dice el capítulo según el código) |
| `\fwd{c}{t_1}{t_2}` | $F_{c}(t_1,t_2)$ | tasa forward simple de la curva `c` |
| `\yf{t_1}{t_2}` | $\tau(t_1,t_2)$ | fracción de año (base explícita en el texto) |
| `\Nom` | $N$ | nocional |
| `\K` | $K$ | tasa fija / precio de ejercicio |
| `\ON{j}` | $r_{j}$ | fijación overnight del día hábil $j$ |
| `\Rcomp{i}` | $R_{i}$ | tasa compuesta del periodo $i$ |
| `\Ann` | $A$ | anualidad (PV01 sin escalar) |
| `\Spar` | $S$ | tasa par |
| `\Spot` | $X_0$ | tipo de cambio spot USDMXN (MXN por USD) |
| `\FxF{T}` | $X(T)$ | tipo de cambio forward USDMXN |
| `\vol` | $\sigma$ | volatilidad |
| `\Ncdf` | $\Phi$ | distribución normal estándar acumulada |
| `\PV` | $V$ | valor presente |
| `\PnL` | $\mathrm{P\&L}$ | resultado |
| `\DVO` | $\mathrm{DV01}$ | sensibilidad a 1 pb |
| `\VaR{\alpha}` | $\mathrm{VaR}_{\alpha}$ | valor en riesgo |
| `\ES{\alpha}` | $\mathrm{ES}_{\alpha}$ | déficit esperado |
| `\hwa`, `\hwsig`, `\hwtheta` | $a$, $\sigma$, $\theta(t)$ | parámetros de Hull–White |
| `\basis` | $b$ | base de cross currency |
| `\E`, `\Q` | $\mathbb{E}$, $\mathbb{Q}$ | esperanza, medida |
| `\cTIIE`, `\cSOFR`, `\cMXNcol` | etiquetas de curva (subíndices) | curva OIS TIIE-F, curva OIS SOFR, curva de descuento MXN colateralizada en USD |
| `\MXN`, `\USD` | MXN, USD (texto) | monedas |
| `\pb` | pb | punto base |

Entornos (con `tcolorbox`): `\begin{diferencia}…\end{diferencia}` = recuadro «Diferencia con la referencia» (R3); `\begin{limites}…\end{limites}` = recuadro «Límites y supuestos» (R6); `\begin{aviso}…\end{aviso}` = aviso destacado (IFRS 9). Ecuaciones numeradas con `equation`/`align`; teoremas no se usan. `\todo[inline]{…}` (todonotes) solo en los capítulos 14 y 15.

### 5. Estructura obligatoria de un capítulo (la de `_plantilla.tex`, R7)

1. **Propósito** (qué calcula el código y para qué). 2. **Notación** (solo los símbolos nuevos del capítulo; los comunes remiten al apéndice). 3. **Modelo y fórmulas** (numeradas, con convenciones explícitas). 4. **Implementación** (cada cálculo con al menos un `\codigo`; en la práctica `\codigo` va junto a cada fórmula). 5. **Ejemplo numérico verificable** (≥ 2 en capítulos 2–12; §7). 6. **Validación** (pruebas del repo y, si aplica, casos contra QuantLib del capítulo 12). 7. **Límites y supuestos** (entorno `limites`; R6). 8. **Referencias** (citas `\citet`/`\citep` dentro del texto; la bibliografía es única al final).

Cuotas mínimas por capítulo: `\codigo` ≥ 11 en cada capítulo 2–12 y ≥ 5 en los capítulos 1 y 13 (total ≥ 131 > 120 de R4); al menos una por sección que exponga un cálculo. Citas distintas ≥ 2 en cada capítulo 2–12 (R5).

### 6. Bibliografía (`referencias.bib`) — regla de no inventar

- Solo obras **reales**. Libros y artículos: autores, año, título, editorial o revista y **`doi` o `isbn`** (obligatorio). Estilo `plainnat-es` (imprime DOI e ISBN). Claves `apellidoAAAA` en minúsculas sin acentos (`hull1990`, `brigo2006`); si choca, sufijo `a`, `b`.
- **Antes de añadir** una entrada se confirma contra una fuente externa y el redactor guarda la evidencia en su informe: DOI → `curl -s https://api.crossref.org/works/<doi> | python -c "import json,sys;m=json.load(sys.stdin)['message'];print(m['title'],m.get('container-title'),m['issued'])"`; ISBN → `curl -sL https://openlibrary.org/isbn/<isbn>.json | python -c "import json,sys;m=json.load(sys.stdin);print(m.get('title'),m.get('publishers'),m.get('publish_date'))"` (o WebSearch/WebFetch a la editorial). Si no se confirma existencia y DOI/ISBN, **no se añade**. Nunca completar un DOI o ISBN «de memoria».
- **Excepción declarada (en el README):** normas, documentación institucional y estándares sin DOI ni ISBN (IFRS 9 del IASB, documentación de SOFR de la Fed de Nueva York, TIIE de Fondeo de Banxico, definiciones ISDA, FpML) entran como `@manual` (o `@misc`) con el organismo emisor como autor entre llaves dobles (`author = {{International Accounting Standards Board}}`), `year`, `title`, `organization`/`publisher` y **`url` oficial** (más `note = {Consultado el AAAA-MM-DD}`). Antes de añadirla se comprueba que la URL responde y es el documento citado: `curl -sL -o /dev/null -w '%{http_code}' <url>` → 200 y el título de la página coincide. Claves `iasb2014`, `nyfed2018` u organismo+año análogo.
- **Archivo compartido**: releer `referencias.bib` justo antes de editar, buscar si la obra ya está (por DOI/ISBN y por título) y reutilizar su clave; añadir solo **al final** del archivo con `Edit` (sustituyendo la última entrada por ella misma + la nueva) o anexando; commit inmediato y pequeño (§9). Nunca reordenar ni reformatear entradas ajenas.
- Claves base que T1 intenta añadir (solo las que confirme; los redactores comprueban en el `.bib` antes de citarlas): `hull1990` (Hull y White, RFS 1990), `jamshidian1989` (J. Finance 1989), `garman1983` (Garman y Kohlhagen, JIMF 1983), `black1976` (JFE 1976), `black1973` (Black y Scholes, JPE 1973), `brigo2006` (Brigo y Mercurio, Springer, 2.ª ed.), `andersen2010` (Andersen y Piterbarg, vol. 1), `hull2018` (Hull, *Options, Futures, and Other Derivatives*, 10.ª ed.), `gregory2015` (*The xVA Challenge*), `glasserman2003` (*Monte Carlo Methods in Financial Engineering*), `jorion2007` (*Value at Risk*, 3.ª ed.), `mcneil2015` (*Quantitative Risk Management*, ed. revisada), `hagan2006` (Hagan y West, Applied Mathematical Finance 2006, interpolación de curvas).
- `HALLAZGOS.md`: mismo régimen que el `.bib` (releer, añadir al final, commit inmediato). Formato de entrada: `## HNN — <título corto>` + `Archivo:`, `Símbolo:`, `Qué hace el código:`, `Qué declara la Metodología/el diseño:`, `Impacto:`, `Capítulo:`.

### 7. Ejemplos numéricos verificables (R3)

En el `.tex`: insumos concretos, fórmula aplicada y resultado con `\verif{id}{valor}`, más la tolerancia en el texto («se reproduce con `docs/tex/verificacion/capNN_….py`, tolerancia absoluta $10^{-6}$»). El valor impreso tiene los dígitos suficientes y la tolerancia es ≥ media unidad del último dígito impreso.

`verificacion/comun.py` (lo escribe T1) expone exactamente:

```python
RAIZ        # Path de la raíz del repo; al importarse añade RAIZ y RAIZ/"build"/"src" a sys.path
def impreso(id: str) -> float          # busca \verif{id}{valor} en docs/tex/capitulos/cap*.tex; error si 0 o >1 apariciones
def comprobar(id: str, calculado: float, tol: float) -> bool   # imprime "OK <id> calculado=… impreso=… tol=…" o "FALLA …"
def terminar() -> None                 # sys.exit(1) si hubo alguna FALLA, si no sys.exit(0)
```

Forma de un script de capítulo (`verificacion/cap03_swaps_ois.py`):

```python
"""Ejemplos verificables del capítulo 3 (swaps OIS)."""
import comun                      # primero: arregla sys.path
from desk.api.qf import qfpy      # o funciones de desk.api.*

def tasa_par():
    ...                           # insumos idénticos a los del texto, construidos en el script
    return swap.par_rate(env)

comun.comprobar("cap03-tasa-par", tasa_par(), 1e-8)
comun.comprobar("cap03-pv-envejecido", ..., 0.01)
comun.terminar()
```

Reglas: el cálculo llama al **código del proyecto** (`qfpy` o `desk.api.*`), nunca reimplementa la fórmula (sí puede, además, recalcular a mano para el texto). Solo stdlib + código del proyecto. Insumos construidos dentro del script; **no leer `desk/data/desk.db`** ni red. Si una función exige conexión SQLite: base temporal (`tempfile`) con `desk.api.db.connect(ruta)` + `desk.api.db.init_schema(conn)` y siembra determinista (`desk.api.seed_market.seed_market`, `desk.api.seed_trades.seed_trades`, o inserción explícita); nunca la base real. Cada `id` del texto se comprueba en exactamente un script.

`correr.py` (T1): corre con `sys.executable` cada `verificacion/cap[0-9][0-9]_*.py` (cwd = `verificacion/`), recoge las líneas `OK <id>` de su salida y termina con código 0 solo si: todos los scripts terminan con 0; cada `\verif{id}` de `capitulos/cap*.tex` aparece como `OK` en algún script; y cada capítulo 02–12 tiene ≥ 2 `\verif`. Imprime `N scripts, M valores verificados` y, si falla, qué falta. En el arranque vacío (sin capítulos escritos) sigue terminando con 0 con un modo `--parcial` que omite la cuota por capítulo; sin `--parcial` exige la cuota (la usa la tarea final).

`referencias_codigo.py` (T1): extrae con regex `\\codigo\{([^}]*)\}\{([^}]*)\}` de todos los `docs/tex/**/*.tex` salvo los que empiezan por `_`; para cada par comprueba que `RAIZ/ruta` existe y que el símbolo está **definido** en ese archivo: en `.py`, `^\s*(def|class)\s+NOMBRE\b` o `^NOMBRE\s*(:|=)` (constante de módulo); `Clase.metodo` en `.py` exige `class Clase` y `def metodo`; en C++ (`.hpp`/`.cpp`/`.h`), `Clase::metodo` exige `Clase::metodo\s*\(` en el archivo, o `(class|struct)\s+Clase\b` y `\bmetodo\s*\(`; un nombre simple exige `(class|struct|enum class|enum|namespace|using)\s+NOMBRE\b` o `\bNOMBRE\s*\(` o `\bNOMBRE\s*=`; en `.ts/.tsx`, `(function|const|class|interface|type)\s+NOMBRE\b`; en `.json`/`.md`/`.sh`/`.txt`, que el texto aparezca. Imprime cada fallo y `N referencias, F fallos`; código 0 si F = 0 y N ≥ 120 (con `--min K` se cambia el mínimo; en el arranque vacío se usa `--min 0`).

### 8. Dónde está el código de cada tema (mapa capítulo → archivos)

Líneas aproximadas entre paréntesis. «Metodología» = `desk/ui/src/screens/MethodologyScreen.tsx` (597 líneas; localizar la sección con `grep -n "title: '" …`) y `desk/ui/src/screens/ops/opsMethodology.ts`; es la fuente de los límites declarados (R6). Documentos del corte 1: `docs/superpowers/qf-desk/design.md`, `plan.md`, `roadmap.md`; de los demás: `docs/superpowers/qf-desk/corteN/{design,plan,audit}.md`. El binding Python de todo C++ está en `src/python_bindings/qfpy.cpp` (852; buscar el nombre Python, p. ej. `"par_rate"`).

| Cap. | C++ (`include/qf/…` + `src/…`) | Backend (`desk/api/…`) | Validación / docs |
|---|---|---|---|
| 1 Intro, convenciones | `math/daycount` (65+83), `core/market_environment` (141+128), `pricingengines/detail/env_resolver.hpp` (41), `instruments/instrument` (41+20) | `calendars.py` (145), `db.py` (134, solo esquema), `pricing/base.py`, `pricing/__init__.py`, `portfolio.py` (352: signos y moneda de reporte), `app.py` (110, solo arquitectura) | `desk/README.md`, `CLAUDE.md` del repo, Metodología «Convenciones generales» y «Límites», `docs/superpowers/qf-desk/design.md`, `roadmap.md` |
| 2 Curvas | `termstructure/ois_bootstrap` (56+117), `termstructure/bootstrap` (22+82), `termstructure/yieldcurve` (59+63), `math/interpolation` (27+98), `termstructure/xccy_bootstrap` (64+132), `core/market_environment` | `market.py` (582: construcción de curvas desde el snapshot, contexto de valuación), `collateral.py` (170) | corte 3 (`corte3/`), Metodología «Curvas» y «Colateral y curvas MXN»; casos de curvas en `desk/validation/ql_curves.py` |
| 3 Swaps OIS | `instruments/ois_swap` (144+162: `OisSwap`, `compoundOvernight`), `termstructure/ois_bootstrap` (`oisPaymentDays`) | `pricing/rates.py` (353, parte `irs`), `valuation.py` (259), `fixings.py` (153), `settlement.py` (323, solo fijaciones compuestas del periodo en curso) | corte 1 y corte 2, Metodología «IRS TIIE-F», «IRS SOFR», «Ciclo de vida y valuación a fecha»; `desk/validation/ql_rates.py` |
| 4 FX y opción sobre acción | `instruments/fx_forward` (72+53), `instruments/fx_option` (80+65), `termstructure/volsurface` (94+202), `pricingengines/blackscholes` (47+131), `instruments/option` (63+22) | `pricing/fx.py` (204: fx_forward, fx_option, equity_option), `market.py` (solo superficie y forwards FX, spot de acción) | corte 1, Metodología «Forward FX», «Opción FX», «Opción sobre acción»; `desk/validation/ql_fx.py` |
| 5 Hull–White | `models/hullwhite` (33+92), `instruments/capfloor` (116+190), `instruments/swaption` (92+228) | `pricing/rates.py` (cap_floor, swaption), `aging.py` (214, parte cap/floor) | corte 1, corte 3 (T9 envejecimiento), Metodología «Cap / Floor», «Swaption»; `desk/validation/ql_hw.py` |
| 6 Bonos | `instruments/bond` (83+167) | `pricing/rates.py` (bond), `aging.py` (parte bono) | corte 1, corte 3 (T9), Metodología «Bono»; `desk/validation/ql_rates.py` (bond) |
| 7 Cross currency swap | `instruments/xccy_swap` (115+170), `termstructure/xccy_bootstrap` (solo para remitir a cap. 2) | `xccy.py` (233), `pricing/xccy.py` (98), `collateral.py` (solo lo que afecte al xccy) | corte 3, Metodología «Colateral y curvas MXN» |
| 8 Ciclo de vida y P&L | — | `lifecycle.py` (73), `events.py` (216), `settlement.py` (323), `pnl.py` (81), `valuation.py` (259), `calendars.py` (regla de fin de semana / día hábil) | corte 2, Metodología «Ciclo de vida y valuación a fecha» |
| 9 Riesgo | `risk/scenario` (107+138), `risk/var` (51+149), `risk/delta_normal_var` (27+44) | `risk/dv01.py` (93), `risk/scenarios.py` (199), `risk/var.py` (130), `risk/hist_var.py` (109), `risk/factor_history.py` (316), `risk/explain.py` (182), `risk/limits.py` (290), `risk/scenario_sets.py` (154) | corte 1, corte 6 (excepto CVA: solo una frase que remite a `\ref{cap:xva}`), Metodología «Riesgo» y «Riesgo avanzado»; `desk/ui/src/screens/risk/PnlExplainTab.tsx` (solo textos) |
| 10 Coberturas IFRS 9 | — | `hedges.py` (605), `hedge_measure.py` (427), `hedge_effectiveness.py` (142), `hedge_report.py` (175) | corte 4 (`corte4/`, incl. la advertencia del contador), Metodología «Coberturas» |
| 11 Operaciones | — | `ops_recon.py` (506), `ops_cashflows.py` (179), `ops_settlements.py` (102), `ops_confirm.py` (294), `ops_settings.py` (108), `fpml.py` (503, solo lo que entra en la conciliación/confirmación) | corte 5, `opsMethodology.ts` |
| 12 Validación QuantLib | — | `desk/validation/` completo (~1 300: `common.py`, `compare.py`, `export_cases.py`, `ql_*.py`, `run_quantlib.py`, `known_differences.json`, `report.json`, `README.md`) | corte 7, Metodología «Validación contra QuantLib» |
| 13 Datos | — | `banxico.py` (79), `nyfed.py` (57), `fred.py` (50), `fixings.py`, `fixings_fetch.py` (148), `live_market.py` (180), `marketdata.py` (76), `refresh.py` (87), `seed_market.py` (135), `seed_trades.py` (80), `market.py` (snapshots), `backup.py` (185, solo procedencia) | corte 2, corte 8, Metodología «Fuentes de datos», `desk/README.md` |
| 14 XVA | (marcador) `include/qf/xva/`, `desk/api/risk/credit.py` — **no leer, en cambio** | | |
| 15 Exóticos FX | (marcador) | | |

Pruebas que sirven de validación por capítulo: `desk/api/tests/test_*.py` (por nombre: `test_price_rates.py`, `test_price_fx.py`, `test_market*.py`, `test_risk_*.py`, `test_hist_var.py`, `test_pnl*.py`, `test_hedges_*.py`, `test_ops_*.py`, `test_aging_exact.py`, `test_flows.py`, `test_lifecycle.py`, …) y `tests/` (GoogleTest). Se citan por ruta en el texto con `\codigo` (símbolo = nombre de la función de prueba).

### 9. Python, commits y verificación

- Python: `/home/claudio/anaconda3/bin/python` (3.8; es el `python` del PATH). `qfpy` se carga desde `build/src/qfpy.cpython-38-x86_64-linux-gnu.so` vía `from desk.api.qf import qfpy`. **No recompilar** (`cmake`) — si el import falla porque otro agente está recompilando, esperar y reintentar; si persiste, reportarlo.
- Commits en español, con el porqué, **sin `Co-Authored-By` ni trailers**, solo rutas explícitas bajo `docs/tex`:
  `cd /home/claudio/Git/Quant_Finance && git add <rutas> && GRAPHIFY_SKIP_HOOK=1 git commit -m "docs(tex): <qué y por qué>" -- <rutas>`
  (`git add` previo es necesario para archivos nuevos; `-- <rutas>` hace que el commit no arrastre lo que otros agentes tengan en el índice). Nunca `git add -A`/`.`, nunca `graphify-out/`.
- Verificaciones del corte (desde la raíz del repo):
  - `python docs/tex/verificacion/correr.py` → código 0.
  - `python docs/tex/verificacion/referencias_codigo.py` → código 0, `N ≥ 120`.
  - compilación de §3.
  - R8: `for c in $(git log --format=%h feat/qf-desk -- docs/tex); do git show --name-only --format= $c | grep -v '^docs/tex/' ; done` → sin salida (ningún commit de este corte toca algo fuera de `docs/tex/`).

## Tareas

Orden: T1 → (T2 … T10 en paralelo) → T11.

### T1 — Esqueleto: preámbulo, notación, plantilla, scripts y capítulos marcador

- **Modelo:** sonnet
- **Depende de:** —
- **Cubre:** R1 (compilación vacía, `.gitignore`, README), R2 (estructura completa, marcadores 14 y 15, apéndice), R3 (infraestructura: `comun.py`, `correr.py`), R4 (`\codigo`, `referencias_codigo.py`), R5 (bibliografía base), R7 (plantilla y README), R8
- **Archivos (crear):** todos los de §2 excepto los scripts `capNN_*.py`: `docs/tex/plainnat-es.bst`, `docs/tex/qfdesk.tex`, `preambulo.tex`, `referencias.bib`, `README.md`, `HALLAZGOS.md`, `.gitignore`, `capitulos/_plantilla.tex`, `capitulos/cap01_introduccion.tex` … `capitulos/cap15_exoticos_fx.tex`, `capitulos/apendice_simbolos.tex`, `simbolos/cap01.tex` … `simbolos/cap15.tex`, `verificacion/comun.py`, `verificacion/correr.py`, `verificacion/referencias_codigo.py`.
- **Pasos:**
  1. `preambulo.tex`: paquetes de §3 (babel con `\babelprovide`, `natbib` con `authoryear,round`, `hyperref` + `cleveref` en ese orden, `siunitx` con punto decimal, `tcolorbox`, `todonotes`, `booktabs`, `geometry`, `microtype`, `amsmath`, `amssymb`, `xurl` o `url` para partir rutas); todas las macros y entornos de §4 con esos nombres y aridades; `\codigo` debe partir línea en `/`, `_` y `.` sin cajas desbordadas (probar con `\codigo{desk/api/risk/factor_history.py}{build_factor_history}` en medio de un párrafo y con un símbolo C++ largo `qf::termstructure::bootstrapXccyDiscount`); `\verif` imprime el valor con `\num`. Crear `docs/tex/plainnat-es.bst`: copiar `$(kpsewhich plainnat.bst)` y cambiar las cadenas `" and "` → `" y "`, `" et~al."` se deja, y «editor»/«editors»/«edition»/«pages»/«volume»/«number»/«Technical Report» al español solo cuando sea sustitución de cadena literal; comprobar que el PDF muestra «Hull y White (1990)» en cita y bibliografía.
  2. `qfdesk.tex`: `report`, portada (título «QF Desk — Documentación técnica», subtítulo con la rama y la fecha `\today`), `\tableofcontents`, `\include` de los 15 capítulos en orden de §2, `\appendix` + `\include{capitulos/apendice_simbolos}`, `\bibliographystyle{plainnat-es}` + `\bibliography{referencias}`.
  3. Capítulos 1–13 marcador: `\chapter{<título de R2>}\label{cap:…}` (el 4 se titula «Derivados de FX y opción sobre acción») + una frase de alcance. Capítulos 14 y 15 (definitivos para este corte): título, una frase (14: «Exposición, CVA/DVA/FVA y curvas de crédito por CDS; lo escribe el corte de XVA al cerrar, con `capitulos/_plantilla.tex`.»; 15: análogo para exóticos de FX) y `\todo[inline]{…}` visible.
  4. `apendice_simbolos.tex`: tabla `booktabs` (longtable si hace falta y está instalado; si no, `tabular` partida) con todos los símbolos de §4 (macro, símbolo, significado, unidad) y, debajo, `\input{simbolos/capNN}` para NN = 01…15 (cada uno vacío, con un comentario `% filas del capítulo NN: símbolo & significado & unidad \\`), con la estructura necesaria para que filas añadidas por los redactores compilen dentro de la tabla.
  5. `_plantilla.tex`: las 8 secciones de §5 con comentarios que digan qué va en cada una, un ejemplo de `\codigo` real (p. ej. `\codigo{include/qf/instruments/ois_swap.hpp}{OisSwap}`), un ejemplo de ecuación numerada, de `\verif`, de `diferencia` y de `limites`.
  6. `verificacion/comun.py`, `correr.py`, `referencias_codigo.py` según §7 (stdlib; `correr.py` y `referencias_codigo.py` ≤ 60 líneas cada uno). Probar `referencias_codigo.py` contra un `.tex` temporal fuera del repo (`/tmp/qfdocs-T1/`) con casos buenos y malos de cada lenguaje, y `comun.impreso`/`correr.py` con un script y un `.tex` de juguete en `/tmp/qfdocs-T1/` (no dejar archivos de juguete en el repo).
  7. `referencias.bib`: las claves base de §6, **cada una confirmada** con crossref/openlibrary (más, si se confirman sus URL oficiales, `@manual` de IFRS 9, SOFR de la Fed de Nueva York y TIIE de Fondeo de Banxico según la excepción de §6) (guardar en el informe la salida que lo confirma). La que no se confirme no entra. Como aún no están citadas, citarlas temporalmente con `\nocite{…}` en `qfdesk.tex` dentro de un bloque comentado `% T1: \nocite provisional, lo quita T11`.
  8. `README.md`: compilar (§3, incluida la variante `-outdir`), las dos verificaciones con su salida esperada, requisitos (paquetes, `\babelprovide` con partición inglesa y la instrucción de instalar `texlive-lang-spanish` para partición correcta, `plainnat-es.bst`, Python), la excepción bibliográfica de §6 (normas e instituciones como `@manual` con URL oficial; libros y artículos siempre con DOI/ISBN), y la lista de comprobación para añadir un capítulo (plantilla, `\label{cap:…}`, `\include` en `qfdesk.tex`, `simbolos/capNN.tex`, ≥ 11 `\codigo`, ≥ 2 `\verif` con script `verificacion/capNN_*.py`, ≥ 2 citas confirmadas con DOI/ISBN, recuadros `diferencia` y `limites`, sin macros nuevas, `HALLAZGOS.md`, correr las verificaciones, commit solo de `docs/tex`). `HALLAZGOS.md`: título, propósito y formato de entrada de §6, sin entradas. `.gitignore` de §2.
  9. Commit (§9): `docs(tex): esqueleto de la documentación técnica …`.
- **Verificación:**
  - `cd docs/tex && latexmk -pdf -interaction=nonstopmode -halt-on-error qfdesk.tex; echo rc=$?` → `rc=0`; en `qfdesk.log` 0 undefined y 0 cajas > 10 pt (comandos §3); `pdftotext qfdesk.pdf - | grep -c ' y White'` ≥ 1 (estilo en español); `pdftotext qfdesk.pdf - | grep -c "Capítulo"` ≥ 15.
  - `python docs/tex/verificacion/referencias_codigo.py --min 0` → código 0, `F = 0` (cuenta las de la plantilla excluida = 0; las de los marcadores si las hay).
  - `python docs/tex/verificacion/correr.py --parcial` → código 0, `0 scripts, 0 valores verificados`.
  - `python docs/tex/verificacion/correr.py` (sin `--parcial`) → código ≠ 0 diciendo que faltan ejemplos en caps 02–12 (prueba de que la cuota se exige).
  - `wc -l docs/tex/verificacion/correr.py docs/tex/verificacion/referencias_codigo.py` → ≤ 60 cada uno.
  - `git status --short docs/tex` → vacío tras el commit; `.aux`/`.pdf` ignorados.

### Instrucciones comunes a T2–T10 (redactores de capítulo)

Cada redactor: (a) lee su fila del mapa de §8 (código, pruebas, docs del corte, sección de la Metodología) y nada de XVA; (b) escribe su capítulo con la estructura de §5 sobre el marcador que dejó T1 (conserva `\chapter{…}\label{cap:…}`); (c) escribe `verificacion/capNN_<nombre>.py` (nombre = nombre del `.tex`) con ≥ 2 ejemplos (§7); (d) añade filas a `simbolos/capNN.tex`; (e) añade sus referencias al final de `referencias.bib` confirmándolas (§6) y, si encuentra discrepancias, entradas al final de `HALLAZGOS.md`; (f) verifica; (g) hace commits pequeños solo de sus archivos (el `.bib` y `HALLAZGOS.md` en commits separados e inmediatos). No toca `qfdesk.tex`, `preambulo.tex`, `README.md`, `_plantilla.tex`, `apendice_simbolos.tex` ni archivos de otro capítulo; si cree que el preámbulo necesita algo, lo pide en su informe. Informe final: cuántas `\codigo`, `\verif` y citas tiene, entradas del `.bib` añadidas con la evidencia de confirmación, hallazgos y cualquier cosa que T11 deba arreglar.

**Verificación común** (con `TAREA=Tk` y `NN` del capítulo):
- compilación privada de §3 → `rc=0`; en `$OUT/qfdesk.log`: 0 «undefined» de etiquetas/citas propias, 0 cajas > 10 pt en su capítulo (`grep -B2 -A2 Overfull $OUT/qfdesk.log` muestra el archivo de origen).
- `cd docs/tex/verificacion && python capNN_<nombre>.py; echo rc=$?` → todas las líneas `OK`, `rc=0`, ≥ 2 ids `capNN-…`.
- `python docs/tex/verificacion/referencias_codigo.py --min 0 | tail -3` → 0 fallos; `grep -o '\\codigo{' docs/tex/capitulos/capNN_*.tex | wc -l` ≥ cuota de §5.
- citas distintas del capítulo ≥ 2 (comando de §3) y ninguna `comm -23` (cita sin entrada) propia.
- `grep -nE '\\(re)?newcommand|\\def\\|\\todo' docs/tex/capitulos/capNN_*.tex` → sin salida.
- `git show --name-only --format= HEAD~k..HEAD` de sus commits → solo rutas bajo `docs/tex/`.

### T2 — Capítulos 1 (introducción, arquitectura, convenciones) y 13 (fuentes de datos y procedencia)

- **Modelo:** sonnet
- **Depende de:** T1
- **Cubre:** R2 (contenido de 1 y 13), R4, R6 (límites generales y de datos: datos sintéticos `MX-DEMO`, falta token de Banxico, `MKT-LIVE`), R5 (citas de fuentes de datos como `@manual` con URL oficial)
- **Archivos:** `docs/tex/capitulos/cap01_introduccion.tex`, `docs/tex/capitulos/cap13_datos.tex`, `docs/tex/simbolos/cap01.tex`, `docs/tex/simbolos/cap13.tex`; añadir al final de `referencias.bib` y `HALLAZGOS.md` si aplica.
- **Pasos:** 1) Cap. 1: arquitectura (motor C++ `qf`, bindings `qfpy`, backend Flask `desk/api`, UI, base SQLite, snapshots), convenciones con su `\codigo`: monedas y moneda de reporte, bases de días que existen en `DayCountConvention` y cuál usa cada producto, signos (pagar/recibir, compra/venta, signo del PV desde la óptica de la empresa), fechas (`as_of`, snapshot, fecha de valuación, días hábiles de `calendars.py`), unidades (tasas en decimal, pb, nocionales), mapa del documento (con `\ref{cap:…}`). ≥ 5 `\codigo`. 2) Cap. 13: cada fuente (Banxico SIE: series y token; NY Fed SOFR; FRED DEXMXUS; MarketDataFeed), qué se guarda y dónde (fijaciones, snapshots `MX-DEMO` sintético vs `MKT-LIVE`), procedencia y respaldo, qué dato es sintético. ≥ 5 `\codigo`. Sin ejemplos `\verif` obligatorios (capítulos fuera de 2–12). Documentación institucional sin DOI/ISBN (Banxico, Fed de Nueva York, FRED): entrada `@manual` con URL oficial según la excepción de §6.
- **Verificación:** la común (sin script `capNN`; cuotas `\codigo` ≥ 5 por capítulo).

### T3 — Capítulo 2: curvas

- **Modelo:** sonnet
- **Depende de:** T1
- **Cubre:** R3, R4, R5, R6
- **Archivos:** `docs/tex/capitulos/cap02_curvas.tex`, `docs/tex/verificacion/cap02_curvas.py`, `docs/tex/simbolos/cap02.tex`; final de `referencias.bib`/`HALLAZGOS.md`.
- **Pasos:** documentar con fórmulas numeradas: bootstrap OIS de TIIE-F y SOFR (tipos de cotización `OisQuoteType`, calendario de pagos `oisPaymentDays`, ecuación que se resuelve por pilar y cómo), representación de la curva y su interpolación (`InterpolationMethod`, sobre qué cantidad interpola, extrapolación), tasa cero y forward tal como las calcula `YieldCurve`, curva MXN–USD por puntos forward y base de cross currency (`bootstrapXccyDiscount`, `FxForwardQuote`, `XccyBasisQuote`), cómo `market.py` arma el contexto y elige la curva de descuento según la moneda de colateral (`collateral.py`). Recuadro `diferencia` donde aplique. ≥ 2 ejemplos `\verif` (sugeridos: un factor de descuento tras bootstrap de 2–3 cotizaciones; el factor de descuento MXN colateralizado en USD en un pilar). Límites de la Metodología «Curvas» y «Colateral y curvas MXN». Citas sugeridas (si están confirmadas): `hagan2006`, `andersen2010`, `brigo2006` y fuentes de multicurva/colateral que el redactor confirme.
- **Verificación:** la común.

### T4 — Capítulo 3: swaps OIS

- **Modelo:** sonnet
- **Depende de:** T1
- **Cubre:** R3, R4, R5, R6
- **Archivos:** `docs/tex/capitulos/cap03_swaps_ois.tex`, `docs/tex/verificacion/cap03_swaps_ois.py`, `docs/tex/simbolos/cap03.tex`; final de `referencias.bib`/`HALLAZGOS.md`.
- **Pasos:** valuación de `OisSwap` (pata fija, pata flotante compuesta, `npv`, `annuity`, `par_rate`, `cash_flows`), fijaciones compuestas (`compoundOvernight`: ponderación por días, base, redondeo si existe), periodo en curso (parte fijada + parte proyectada, y cómo se compone: si es continua, recuadro `diferencia`), envejecimiento a fecha de snapshot (`valuation.py`), origen de fijaciones (`fixings.py`), diferencias TIIE-F vs SOFR (base, lag/lookback si existen en el código; si no existen, decirlo en `limites`). ≥ 2 `\verif` (sugeridos: tasa par de un swap nuevo; PV de un swap envejecido con fijaciones conocidas o una tasa compuesta de periodo). Citas sugeridas: `andersen2010`, `brigo2006`, `hull2018`, ISDA como `@manual` con URL oficial (excepción de §6) si se cita.
- **Verificación:** la común.

### T5 — Capítulos 4 (derivados de FX y opción sobre acción) y 7 (cross currency swap)

- **Modelo:** sonnet
- **Depende de:** T1
- **Cubre:** R3, R4, R5, R6
- **Archivos:** `docs/tex/capitulos/cap04_fx.tex`, `docs/tex/capitulos/cap07_xccy.tex`, `docs/tex/verificacion/cap04_fx.py`, `docs/tex/verificacion/cap07_xccy.py`, `docs/tex/simbolos/cap04.tex`, `docs/tex/simbolos/cap07.tex`; final de `referencias.bib`/`HALLAZGOS.md`.
- **Pasos:** Cap. 4: forward FX (`FxForward::forwardRate` — paridad cubierta con qué curvas —, `npv`, `delta`, signo por `FxSide`), opción FX Garman–Kohlhagen (`FxOption::npv`, `greeks`: qué griegas y en qué unidades), superficie de volatilidad (`VolSurface::vol`: interpolación en plazo y en strike, extrapolación), y cómo `pricing/fx.py` las usa. Sección propia «Opción sobre acción» (`equity_option` en `pricing/fx.py` → `qfpy.black_scholes`/`OptionParams`, `pricingengines/blackscholes`: fórmula de Black–Scholes que se aplica, dividendos/tasa usados, griegas si las hay, límites de la Metodología «Opción sobre acción»). El capítulo conserva el título «Derivados de FX y opción sobre acción» que dejó T1. ≥ 2 `\verif` de FX (forward y prima GK) y se recomienda un tercero de la opción sobre acción. Citas: `garman1983`, `black1973`, `hull2018`. Cap. 7: `XccySwap` (patas, intercambio de nocionales, `npv`, `parSpread`, `notionalMxn`, flujos), curvas que usa (remitir a `\ref{cap:curvas}` sin repetir el bootstrap), backend `xccy.py`/`pricing/xccy.py`, efecto de la moneda de colateral. ≥ 2 `\verif` (PV y spread par). Citas confirmadas sobre cross currency (p. ej. Fujii–Shimada–Takahashi si se confirma con DOI) y `andersen2010`. Límites de la Metodología (confirmación imprimible sin plantilla para xccy, etc.).
- **Verificación:** la común, para los dos capítulos.

### T6 — Capítulos 5 (Hull–White) y 6 (bonos)

- **Modelo:** sonnet
- **Depende de:** T1
- **Cubre:** R3, R4, R5, R6
- **Archivos:** `docs/tex/capitulos/cap05_hull_white.tex`, `docs/tex/capitulos/cap06_bonos.tex`, `docs/tex/verificacion/cap05_hull_white.py`, `docs/tex/verificacion/cap06_bonos.py`, `docs/tex/simbolos/cap05.tex`, `docs/tex/simbolos/cap06.tex`; final de `referencias.bib`/`HALLAZGOS.md`.
- **Pasos:** Cap. 5: modelo (`HullWhite`: ajuste a la curva inicial, `bondPrice`, `conditionalBondPrice`, `zeroRate`), cap/floor (fórmula de caplet como opción sobre bono cupón cero o Black según lo que haga `capfloor.cpp`; `price` y `priceDualCurve`), swaption europea por Jamshidian (`swaption.cpp`: búsqueda de $r^*$, suma de opciones sobre bonos; `priceDualCurve`), parámetros que usa el desk y de dónde salen, envejecimiento del cap/floor (`aging.py`) y su límite declarado. ≥ 2 `\verif` (caplet o cap; swaption). Citas: `hull1990`, `jamshidian1989`, `black1976`, `brigo2006`. Cap. 6: `Bond` (`price`, `cleanPrice`, `accruedInterest`, `cashFlowSchedule`, `yield`, `duration`, `convexity`): convención de cupón, base de días, composición del rendimiento, devengado; si el cupón o el rendimiento difiere del de mercado/libro, recuadro `diferencia`; envejecimiento exacto (`aging.py`). ≥ 2 `\verif` (precio sucio/limpio y rendimiento o duración). Citas confirmadas (p. ej. `hull2018` y un texto de renta fija con ISBN).
- **Verificación:** la común, para los dos capítulos.

### T7 — Capítulos 8 (ciclo de vida, liquidaciones y P&L) y 11 (operaciones: conciliación)

- **Modelo:** sonnet
- **Depende de:** T1
- **Cubre:** R3, R4, R5, R6
- **Archivos:** `docs/tex/capitulos/cap08_ciclo_vida.tex`, `docs/tex/capitulos/cap11_operaciones.tex`, `docs/tex/verificacion/cap08_ciclo_vida.py`, `docs/tex/verificacion/cap11_operaciones.py`, `docs/tex/simbolos/cap08.tex`, `docs/tex/simbolos/cap11.tex`; final de `referencias.bib`/`HALLAZGOS.md`.
- **Pasos:** Cap. 8: eventos y estado derivado (`lifecycle.py`, `events.py`), flujos liquidados (`settlement.py`), regla de fin de semana / día hábil (exacta, con `\codigo` a `calendars.py`/`settlement.py`), identidad de P&L $\PnL = V_{\text{to}} - V_{\text{from}} + \text{liquidado}$ (`pnl.py`: moneda, signos, qué entra en «liquidado»), valuación a fecha (`valuation.py`, solo lo que no cubra el cap. 3; remitir con `\ref{cap:swaps-ois}`). ≥ 2 `\verif` (P&L entre dos snapshots de una operación sencilla; un flujo liquidado o la fecha ajustada no es número → usar un monto). Cap. 11: conciliación del PV propio contra el del banco (`ops_recon.py`: `reconcile_trade`, descomposición de la diferencia — `_date_factor`, `_newton` y lo que expliquen —, tolerancias y clasificación), flujos del portafolio (`ops_cashflows.py`), liquidaciones confirmadas (`ops_settlements.py`), confirmación y FpML solo en lo que afecta a los números. ≥ 2 `\verif` (componentes de una conciliación). Citas confirmadas (p. ej. `gregory2015` si aplica a conciliación de colateral/PV, textos de operaciones con ISBN; ISDA/FpML como `@manual` con URL oficial, excepción de §6). Límite «conciliación indicativa», FpML solo de irs/fx_forward/fx_option.
- **Verificación:** la común, para los dos capítulos.

### T8 — Capítulo 9: riesgo

- **Modelo:** sonnet
- **Depende de:** T1
- **Cubre:** R3, R4, R5, R6
- **Archivos:** `docs/tex/capitulos/cap09_riesgo.tex`, `docs/tex/verificacion/cap09_riesgo.py`, `docs/tex/simbolos/cap09.tex`; final de `referencias.bib`/`HALLAZGOS.md`.
- **Pasos:** DV01 por curva y pilar (`risk/dv01.py`, `ScenarioEngine::parallelDV01`, `keyRateDV01s`: tamaño y signo del choque, diferencia finita usada, qué se re-bootstrapea), escenarios (paralelo, steepener, spot; `scenario_sets.py`), VaR paramétrico delta-normal (`risk/var.py` + `deltaNormalVaR`: factores TIIE-F, SOFR, USDMXN, covarianza, horizonte, nivel), VaR histórico y ES (`hist_var.py`, `factor_history.py`: ventana, cuantil exacto/interpolación, revaluación completa o por sensibilidades), P&L explicado (`explain.py`: orden de la cascada y residuo), límites (`limits.py`: uso, exceso, bitácora). CVA: **solo una frase** que diga que el CVA informativo existe y remita a `\ref{cap:xva}`; no se documenta aquí. ≥ 2 `\verif` (DV01 paralelo de un swap; VaR paramétrico de un vector de sensibilidades; opcional cuantil histórico). Citas: `jorion2007`, `mcneil2015` y las que confirme.
- **Verificación:** la común.

### T9 — Capítulo 10: contabilidad de coberturas IFRS 9

- **Modelo:** sonnet
- **Depende de:** T1
- **Cubre:** R3, R4, R5, R6 (incluido el aviso de revisión pendiente por un contador IFRS 9)
- **Archivos:** `docs/tex/capitulos/cap10_coberturas.tex`, `docs/tex/verificacion/cap10_coberturas.py`, `docs/tex/simbolos/cap10.tex`; final de `referencias.bib`/`HALLAZGOS.md`.
- **Pasos:** entorno `aviso` al inicio del capítulo: «pendiente de revisión por un contador con experiencia en IFRS 9» (texto de la advertencia del corte 4 y de la Metodología). Relación de cobertura y sus eventos (`hedges.py`), derivado hipotético (cómo se construye), efectividad prospectiva (`hedge_effectiveness.py`: términos críticos, escenarios), medición del periodo (`hedge_measure.py`: regla del menor — fórmula exacta con signos —, porción efectiva a la reserva OCI, inefectividad a resultados, reciclaje, discontinuación), asientos (cuentas, signos; `hedge_report.py`). ≥ 2 `\verif` (regla del menor en un periodo; monto reciclado o reserva acumulada). Citas: la norma IFRS 9 del IASB (`@manual` con URL oficial, excepción de §6; reutilizar la clave si T1 ya la añadió) y textos confirmados con ISBN (p. ej. un libro de contabilidad de derivados y coberturas).
- **Verificación:** la común, más `grep -c 'begin{aviso}' docs/tex/capitulos/cap10_coberturas.tex` ≥ 1.

### T10 — Capítulo 12: validación contra QuantLib

- **Modelo:** sonnet
- **Depende de:** T1
- **Cubre:** R3, R4, R5, R6
- **Archivos:** `docs/tex/capitulos/cap12_validacion.tex`, `docs/tex/verificacion/cap12_validacion.py`, `docs/tex/simbolos/cap12.tex`; final de `referencias.bib`/`HALLAZGOS.md`.
- **Pasos:** método (curvas reconstruidas en QuantLib desde los factores de descuento del desk: `ql_curves.py`; pricers de referencia por producto: `ql_rates.py`, `ql_fx.py`, `ql_hw.py`; flujo `export_cases.py` → `run_quantlib.py` → `compare.py`), métrica de diferencia y tolerancias (`common.py`, `known_differences.json`: cada diferencia conocida y su explicación), resultados (tabla resumen leída de `desk/validation/report.json`: casos, dentro de tolerancia; QuantLib 1.44 **no** está en el Python del backend; vive en el entorno `/home/claudio/anaconda3/envs/quantsuite-oracle/bin/python` (ver `desk/validation/README.md`); el redactor puede correr `make_report.sh`/`run_quantlib.py` para leer resultados **solo si no escribe en archivos versionados** — por defecto, documentar con `report.json`/`reference.json` versionados). ≥ 2 `\verif` que el script reproduce con el Python del backend llamando al código del proyecto: p. ej. el PV del desk de un caso de `cases.json` recalculado con `qfpy`/`desk.api`, y la diferencia de ese caso contra el PV de QuantLib leído de `reference.json` calculada con la función de `desk/validation/compare.py`/`common.py`. Citas: documentación de QuantLib solo si tiene ISBN (p. ej. Ballabio, *Implementing QuantLib*, si se confirma) y una referencia de validación de modelos confirmada.
- **Verificación:** la común.

### T11 — Ensamblaje y verificación final

- **Modelo:** sonnet
- **Depende de:** T1–T10
- **Cubre:** R1, R2, R3, R4, R5, R6, R7, R8 (comprobación total)
- **Archivos:** `docs/tex/qfdesk.tex` (quitar el `\nocite` provisional), `docs/tex/preambulo.tex` y `docs/tex/capitulos/apendice_simbolos.tex` (tabla de símbolos final), `docs/tex/referencias.bib` (limpieza), `docs/tex/README.md` (ajustes), y arreglos mínimos de forma en `capitulos/*.tex` (cajas desbordadas, etiquetas) sin cambiar contenido técnico.
- **Pasos:**
  1. Quitar el bloque `\nocite` provisional de T1. Compilación oficial (§3) en `docs/tex/`.
  2. Undefined: 0. Cajas > 10 pt: 0 (arreglar partiendo ecuaciones, `\codigo` en línea propia, tablas más estrechas; no cambiar fórmulas).
  3. Bibliografía: `comm` de §3 → 0 citas sin entrada; entradas sin citar: si la obra pertenece claramente a un capítulo, se informa y se elimina (no se escribe contenido técnico nuevo para citarla); ≥ 25 entradas finales; cada capítulo 2–12 con ≥ 2 citas distintas; cada libro/artículo con `doi` o `isbn` y cada `@manual`/`@misc` con `url` oficial que responde (`curl -sL -o /dev/null -w '%{http_code}'` → 200), y re-confirmación de cada DOI (`curl -s -o /dev/null -w '%{http_code}' https://api.crossref.org/works/<doi>` → 200) y cada ISBN (openlibrary → título coherente); la que no confirme se elimina y su cita se retira (informar).
  4. Tabla de símbolos: revisar que todo símbolo de las filas `simbolos/capNN.tex` sea coherente con §4 (sin duplicados con distinto significado); duplicados → informar y unificar la fila, sin tocar el texto técnico.
  5. Comprobaciones de estructura: orden y títulos de los 15 capítulos según R2; `\todo` solo en cap. 14 y 15 (`grep -l '\\todo' docs/tex/capitulos/*.tex`); ningún `\newcommand` fuera del preámbulo; cada capítulo 2–12 con al menos un `diferencia` o una frase explícita de que no hay diferencia, y un `limites`; cap. 10 con `aviso`.
  6. `python docs/tex/verificacion/correr.py` (sin `--parcial`) y `python docs/tex/verificacion/referencias_codigo.py` (mínimo 120).
  7. R8 (§9). Commit final.
- **Verificación:**
  - `cd docs/tex && latexmk -pdf -interaction=nonstopmode -halt-on-error qfdesk.tex; echo rc=$?` → `rc=0`, `qfdesk.pdf` existe; `grep -cE "(Citation|Reference) .* undefined" qfdesk.log` → `0`; cajas > 10 pt → `0`.
  - `python docs/tex/verificacion/correr.py; echo rc=$?` → `rc=0`, ≥ 22 valores verificados (2 × 11 capítulos).
  - `python docs/tex/verificacion/referencias_codigo.py; echo rc=$?` → `rc=0`, `N ≥ 120, 0 fallos`.
  - `grep -c '^@' docs/tex/referencias.bib` ≥ 25; `comm` de §3 → ambas vacías.
  - `git check-ignore docs/tex/qfdesk.pdf` → lo imprime (no versionado).
  - comando R8 de §9 → sin salida.

### T1 — nota de cierre (commit 356ce1a, 43 archivos, todos bajo `docs/tex/`)

Dejado: `preambulo.tex`, `qfdesk.tex`, `referencias.bib` (13 claves base + 3 `@manual`), `plainnat-es.bst`, `README.md`, `HALLAZGOS.md` (sin entradas), `.gitignore`, `capitulos/_plantilla.tex`, `capitulos/cap01…cap15`, `capitulos/apendice_simbolos.tex`, `simbolos/cap01…cap15.tex`, `verificacion/{comun,correr,referencias_codigo}.py`. Compilación oficial y privada: rc=0, 0 undefined, 0 cajas desbordadas.

Cosas que los redactores deben saber (y desviaciones respecto del plan):
- **`docs/tex/latexmkrc` (archivo extra, no estaba en §2).** Con `-outdir` bibtex corre en el directorio de salida y no encontraba `plainnat-es.bst`; el `latexmkrc` fija `BSTINPUTS`/`BIBINPUTS` al directorio actual. Por eso `latexmk` se lanza siempre desde `docs/tex` (como ya dicen §3 y el README).
- **Claves de manuales**: `iasb2014` (IFRS 9), `nyfed2026` (página de datos de SOFR; año = año de consulta porque la página no trae fecha), `banxico2021` (nota técnica «Determinación de la tasa TIIE de Fondeo»; el PDF no imprime fecha, 2021 es la fecha de creación del PDF, dicho en su `note`). Claves base de libros/artículos: hull1990, jamshidian1989, garman1983, black1976, black1973, hagan2006, brigo2006, andersen2010, hull2018, gregory2015, glasserman2003, jorion2007, mcneil2015. Edición se escribe con palabra en español (`edition = {segunda}`): el estilo añade «edición».
- **`\nocite{...}` provisional está activo en `qfdesk.tex` justo después de `\begin{document}`** (en el preámbulo no escribe `\citation`); lo quita T11. `\citet{hull1990}` ya aparece en la frase marcador del cap. 5 (T6 la reemplaza).
- **Comentarios del `.bib` sin `@`** (BibTeX lo toma como inicio de entrada).
- **Macros**: los símbolos sin argumento (`\Nom`, `\K`, `\Ann`…) se usan en modo matemático (`$\Nom$`); `\MXN`, `\USD`, `\pb` son texto (`\pb` se escribe `1~\pb`). `\cMXNcol` = `\mathrm{MXN|USD}`. `\codigo` y `\verif` se escriben con `_` normal (nunca `\_`). Añadí un helper `\simbolosinput` (solo lo usa el apéndice; `\input` normal rompe la tabla `longtable`). `\todo` solo en 14 y 15.
- **Tabla de símbolos**: cada `simbolos/capNN.tex` trae una fila «Sin símbolos propios por ahora.» que el redactor sustituye por sus filas (`símbolo & significado & unidad \\`, 4.ª columna macro opcional; toda fila termina en `\\`; el archivo nunca debe quedar sin filas).
- **`referencias_codigo.py`**: para C++ acepto además el literal `"NOMBRE"` (nombres de binding pybind11, p. ej. `\codigo{src/python_bindings/qfpy.cpp}{par_rate}`), que la regla de §7 no cubría; `ns::Clase::metodo` y `ns::funcion` se validan con el calificador (`class|struct|namespace`). Las rutas deben ser archivos (no directorios).
- **`correr.py`** además exige que el `id` de cada `\verif` empiece por `capNN-` del archivo donde está. `comun.comprobar` avisa por stderr si la tolerancia es menor que media unidad del último dígito impreso.
- En esta instalación `longtable` imprime en el log «ignored error: Infinite glue shrinkage found in box being split» al partir una tabla (ocurre también con un `longtable` mínimo sin nuestro preámbulo); es inofensivo (rc=0, salida correcta).
- Partición de palabras con patrones ingleses (`\babelprovide`), declarado en el README. `plainnat-es.bst` imprime la bibliografía con nombres completos («John Hull y Alan White»); en la cita sale «Hull y White (1990)».

### T3 — nota de cierre (capítulo 2, Curvas; commits d369951 `.bib`, 9e06fea H01, 9acadbe capítulo)

Dejado: `capitulos/cap02_curvas.tex` (8 secciones de §5; 15 ecuaciones numeradas; 75 `\codigo`; 16 `\verif`; 6 citas distintas: hagan2006, ametrano2013, fujii2009, andersen2010, brigo2006, hull2018), `verificacion/cap02_curvas.py` (16 ids `cap02-…`, todos OK, rc=0), `simbolos/cap02.tex` (12 filas). `referencias_codigo.py --min 0`: 0 fallos. Entrada nueva en `referencias.bib`: `ametrano2013` (DOI 10.2139/ssrn.2219548, confirmado con crossref); `fujii2009` ya la había añadido otro redactor con el mismo DOI y se reutilizó. Hallazgo anotado: H01 (`bootstrapOis` con `LogLinear` devuelve una curva sin reprecio y sin error; el contrato en C++ dice que reprecia).

Compilación: la oficial/privada del árbol completo falla hoy por capítulos AJENOS en curso (cap09: `\cTIIE` usado en modo texto, «\mathrm allowed only in math mode», línea 28; antes cap10: `hedge_events` con `_` en `\texttt`). Para comprobar el mío compilé una copia en `/tmp/qfdocs-T3-src` con los demás capítulos sustituidos por los marcadores de T1: rc=0, 0 undefined, 0 cajas desbordadas, 0 citas sin entrada. T11 debe recompilar el árbol completo.

Para T11 / T1 (preámbulo, no lo toqué):
- `\codigo` permite salto entre los dos `:` de `Clase::metodo` («YieldCurve:» / «:parallelBump» en el PDF). Conviene no insertar `\allowbreak` tras un `:` seguido de otro `:`.
- Un `TEST(Suite, Nombre)` de GoogleTest no se puede citar por nombre con `referencias_codigo.py` (`Nombre` va seguido de `)`). Cité funciones auxiliares de los archivos de prueba (`parRate`, `basisSwapNpv`) y puse los nombres de las pruebas en `\texttt`.
- Los macros `\cTIIE`, `\cSOFR`, `\cMXNcol` solo funcionan en modo matemático y `\cMXNcol` imprime «MXN|USD» (no «MXN-USD»); en el texto el nombre de la curva va como `\texttt{MXN-USD}`.
- Párrafos/listas con muchas `\codigo` seguidas producen cajas desbordadas (>30 pt) con la justificación normal; las envolví en `\raggedright` (comando estándar, no macro nueva).

No pude comprobar: (1) la compilación del documento completo; (2) las convenciones de la nota de Banorte / CME (la Metodología las declara supuesto); (3) que Brigo–Mercurio, Andersen–Piterbarg y Hull contengan exactamente la tasa par de una sola curva y la paridad cubierta: se citan en general, sin páginas, como resultados estándar; Hagan–West y Ametrano–Bianchetti solo por su tema (interpolación y su efecto en las forwards; curvas múltiples), no por resultados concretos; (4) «9 pb anualizados» (puntos del demo vs paridad) es cuenta propia de este capítulo (0.00129546/18.60·365/28), no un dato del semilla. El bootstrap en sí no está contrastado con QuantLib (el README de `desk/validation` lo dice); el capítulo lo declara.

### T4 — nota de cierre (commits a4a0d27 capítulo/script/símbolos, 3b31744 `isda2021` en el `.bib`, 787319a H02 en `HALLAZGOS.md`; todo bajo `docs/tex/`)

Dejado: `capitulos/cap03_swaps_ois.tex` (18 ecuaciones numeradas + 1 sin número en el recuadro `diferencia`; 82 `\codigo`; 32 `\verif`; 8 citas distintas: andersen2010, brigo2006, hull2018, ametrano2013 (la añadió T3), fujii2009 (la añadió otro redactor), banxico2021, nyfed2026, isda2021), `verificacion/cap03_swaps_ois.py` (32 `OK`, rc=0), `simbolos/cap03.tex`. Entrada nueva en el `.bib`: `isda2021` (`@manual`, página de la biblioteca de ISDA, 200 y título coincide; el texto completo no se abrió, la existencia de lookback/observation period shift/lockout se contrastó con notas de ISDA vía búsqueda). Hallazgo: H02 (`portfolio._at_par`: el alta a la par de un swap que empieza antes del snapshot guarda la par del swap envejecido, sin fijaciones y sin aviso).

Para T11 / quien toque otros capítulos:
- Compilación privada con el árbol completo falló con `rc=12` por un error ajeno (`cap09_riesgo.tex` línea ~28: `\cTIIE` usado en texto fuera de modo matemático, «\mathrm allowed only in math mode»; `\cTIIE` es solo para modo matemático). Para aislar mi capítulo compilé una copia en `/tmp/qfdocs-T4-src` con los demás capítulos tomados de `HEAD`: rc=0, 0 undefined, 0 cajas > 10 pt (2 cajas de 7.2 y 2.1 pt en mi capítulo, párrafos con `\codigo` largos).
- `correr.py --parcial` de todo el árbol hoy falla solo por `\verif` de capítulos aún no escritos (cap11), no por el 3.
- Los símbolos de la 3.ª columna de `simbolos/cap03.tex` usan macros comunes; la anualidad $\Ann$ en el capítulo 3 incluye el nocional (moneda), a diferencia del apéndice A que dice «años»: el capítulo lo declara en «Notación».
- Gtest no se puede citar por nombre de prueba con `referencias_codigo.py` (`TEST(Suite, Nombre)` no casa con ninguna regla); cité `tests/test_ois_swap.cpp` con símbolos que sí aparecen (`compoundOvernight`, `tiiefCurve26`) y nombré las suites/pruebas en `\texttt`.
- Desviaciones del plan: ninguna; `docs/tex/verificacion/cap03_swaps_ois.py` usa un `SimpleNamespace` (stdlib) como `mkt` mínimo (`curves`, `as_of`, `env`) para llamar a `valuation.aged_swap`/`accrued_factor` sin base de datos.

### T10 — nota de cierre (commits dbd8810 `.bib`, 6418ab0 `HALLAZGOS.md`, 33a9f73 capítulo; todo bajo `docs/tex/`)

Dejado: `capitulos/cap12_validacion.tex` (11 ecuaciones numeradas + 2 sin numerar en el ejemplo, 82 `\codigo`, 12 `\verif`, 8 citas distintas, 2 recuadros `diferencia`, 1 `limites`), `verificacion/cap12_validacion.py` (12 ids `cap12-…`, rc=0), `simbolos/cap12.tex`. Bibliografía añadida al final del `.bib`: `morini2011` (Wiley 2011; confirmado con Open Library, ISBN 9780470977613, y con Crossref, DOI 10.1002/9781118467312) y `fed2011` (`@manual`, anexo PDF de SR 11-7 en federalreserve.gov, 200 y título «Supervisory Guidance on Model Risk Management»). Ballabio (*Implementing QuantLib*) NO se añadió: Leanpub no da ISBN ni DOI. Hallazgos: H05 (tolerancia 5e-4 de Hull–White frente a diferencias ≤ 3e-9) y H06 (la Metodología omite bootstrap, superficie, xccy y calendarios en «Qué no se compara»).

Cosas que T11 debe saber:
- **Compilación privada con otros capítulos a medias**: al escribir esto `cap10_coberturas.tex` tenía un `_` sin escapar (`hedge_events`, error «Missing $») y la compilación completa fallaba con rc=1 por su culpa, no por cap12. Compilé solo cap12 con `latexmk … -outdir=$OUT -pdflatex='pdflatex %O "\includeonly{capitulos/cap12_validacion}\input{%S}"' qfdesk.tex`: rc=0, 0 undefined, 0 cajas > 10 pt. La compilación completa de cap12 junto con los demás no se pudo comprobar.
- **«Cuadro» frente a «tabla»**: `\babelprovide{spanish}` rotula los pies de tabla como «Cuadro 12.1», mientras `\crefname{table}` y el texto de cap12 dicen «tabla». Cap12 escribe «tabla~\ref{…}» (la elección de T1). Si T11 prefiere «Tabla» en los pies, basta `\addto\captionsspanish{\renewcommand\tablename{Tabla}}` en el preámbulo; si prefiere «cuadro», hay que cambiar el texto de los capítulos.
- `correr.py --parcial` exige ahora `\verif` de capítulos aún sin escribir (cap11); no es de cap12 (sus 12 ids salen OK).
- Los valores impresos de cap12 que dependen de `desk/validation/reference.json` (PV de QuantLib de `bond-08`, diferencias de `bond-08` y `swaption-03`) se reproducen con `run_quantlib.py --out <scratchpad>` (comprobado: 62 PV idénticos a los versionados, sin tocar archivos versionados). Si alguien cambia las baterías o el pricer de QuantLib, hay que actualizar esos `\verif`. El texto no cita `generated_at` ni `desk_commit`.
- La tabla de resultados (`tab:cap12-resultados`, `tab:cap12-curvas`) y la afirmación «62 casos, 62 dentro, 0 explicados, 0 fuera» son la lectura de `report.json` hoy; no tienen `\verif` (no hay `\verif` por celda). Si se regenera el reporte con PV distintos, hay que releerlas.
- Desviación del plan: no se citó a Ballabio (sin ISBN) ni documentación de QuantLib; la referencia de validación de modelos es SR 11-7 (+ Morini). No se corrió `make_report.sh` (escribe archivos versionados).

### T9 — nota de cierre (commits 0a2ba47, 65ba35a, 8c4e674; todos bajo `docs/tex/`)

Dejado: `capitulos/cap10_coberturas.tex` (aviso IFRS 9 al inicio, las 8 secciones de §5, recuadro `diferencia` y `limites`), `verificacion/cap10_coberturas.py` (30 ids `cap10-…`, ~0.7 s, 0 avisos de tolerancia), `simbolos/cap10.tex` (15 filas), `ramirez2015` al final de `referencias.bib` (Wiley 2015; DOI 10.1002/9781119065876 e ISBN electrónico 978-1-119-06587-6 confirmados en Crossref y Open Library; sin número de edición porque Crossref dice 1 y no se pudo contrastar con la editorial) y H07–H12 al final de `HALLAZGOS.md` (hedge_ratio no entra en la medición; aviso `forecast_date_holiday` no está en la Metodología; `concluida` también con vencimiento conjunto; identidad de control de valor razonable nula por construcción; término `moneda` constante; residuo de redondeo en valor razonable). Cuotas: 65 `\codigo`, 30 `\verif`, 17 ecuaciones numeradas, 3 citas (`iasb2014`, `ramirez2015`, `hull2018`).

Desviaciones y cosas para T11:
- **La compilación completa del documento falla hoy por un capítulo ajeno** (`Double subscript` en `\Spot_{d_1}` dentro de un `cases`, hacia la p. 49 del PDF, capítulo 8; antes, en otra pasada, `\cTIIE` fuera de modo matemático en otro capítulo). Mi capítulo se verificó con un maestro privado reducido en `/tmp/qfdocs-T9-src/` (preámbulo y `.bib` reales, `cap10` + apéndice con filas de `cap10` y las de HEAD de los demás, etiquetas ajenas como capítulos vacíos): `rc=0`, 0 undefined propios, 0 cajas desbordadas, 0 underfull. T11 debe repetir la compilación completa.
- El script no usa Flask ni `create_app`: base temporal con `db.connect` + `db.init_schema` + `seed_market`, `market.roll_snapshot` (rueda MX-DEMO a +35, +70 y +364 días), `fixings.import_csv` (TIIE-F 7 %), `portfolio.create_trade` y llama directamente a `hedges.create_hedge`, `hedge_measure.close_period`, `hedge_effectiveness.effectiveness` y `hedge_measure.journal`. Los valores dependen de la semilla de MX-DEMO; si cambia `seed_market`, cambian.
- Los `\verif` monetarios llevan 4 decimales y tolerancia `1e-4` (los de asientos, 2 decimales y `5e-3`; razones, 6 decimales y `5e-7`; conteos, tolerancia 0.5).
- Se añadió la etiqueta `eq:cap10-reciclaje` (la ecuación de la reserva se partió en `align` por una caja de 141 pt).
- Si el script se corre otro día, el alta emite además el aviso `designation_backdated` (reloj real frente a la fecha de designación 2026-11-10); no altera ninguna cifra.
- El capítulo no cita `hagan2006`, `brigo2006` ni otras; para el `nocite` provisional no hace falta nada nuevo. `\codigo{docs/tex/verificacion/correr.py}{main}` se resuelve (existe `def main`).

### T6 — nota de cierre (commits f1c25c7 tuckman2012 en el .bib, 0d1594d + a521470 capítulo 5, 8b20e5e H13/H14, 6dabf5c capítulo 6; todo bajo `docs/tex/`)

Dejado: `capitulos/cap05_hull_white.tex` (48 `\codigo`, 8 `\verif`, 4 citas: hull1990, jamshidian1989, black1976, brigo2006), `capitulos/cap06_bonos.tex` (43 `\codigo`, 9 `\verif`, 2 citas: hull2018, tuckman2012), `verificacion/cap05_hull_white.py`, `verificacion/cap06_bonos.py`, `simbolos/cap05.tex`, `simbolos/cap06.tex`. Nuevo en el `.bib`: `tuckman2012` (ISBN 978-0-470-89169-8 confirmado contra openlibrary.org/isbn/9780470891698: título, autores, Wiley, 2012, 3.ª ed., serie y lugar). HALLAZGOS: H13 (el cupón del bono no devenga ACT/360, contra la frase general de la Metodología) y H14 (docstring y ramas muertas de `valuation.shortened`); el cap. 5 remite además a H05 (de T10).
Desviaciones y cosas para T11/otros:
- El cap. 5 explica que `CapFloor`/`Swaption` NO instancian `HullWhite` (fórmulas cerradas escritas aparte en `capfloor.cpp::hwBondOption` y `swaption.cpp::hwZCBOption`); la clase solo la usan `simulate`/`conditionalBondPrice` del XVA (remite a `\ref{cap:xva}`, sin documentar XVA).
- Dos `\verif` del cap. 5 (`cap05-caplet-sigma-p`, `cap05-swaption-x`) se comprueban contra un recálculo en stdlib del propio script porque `qfpy` no expone σ_p ni x*; el texto lo dice, y el script exige además que el recálculo completo reproduzca el precio de `qfpy` (1e-6). `cap06-rendimiento-semestral` es la fórmula 2(e^{y/2}−1) aplicada al y de `qfpy`.
- Los scripts llaman a `desk.api.aging` con un `types.SimpleNamespace` como `mkt` (as_of, hw, curves, mxn_discount, spot) y curvas planas de `qfpy.YieldCurve`: no tocan `desk.db`, ni snapshots, ni red.
- `referencias_codigo.py` no reconoce los casos `TEST(Suite, Nombre)` de GoogleTest (la regla de nombre simple exige `NOMBRE(`): cité funciones auxiliares de las pruebas C++ (`quadraturePrice`, `irsNPV`, `agedBond`, `upwardCurve`, `flatCurve`) y pruebas Python por nombre; si T11 quiere citar casos gtest, añadir el patrón `TEST(_F)?\(\w+,\s*NOMBRE\)`.
- La frase marcador del cap. 5 y el marcador del cap. 6 («bonos de tasa fija y flotante») se sustituyeron: no hay bonos flotantes en el código y el capítulo lo dice.
- `\citealp[cap.~3]{brigo2006}`: el capítulo 3 de Brigo–Mercurio («One-factor short-rate models», pp. 51–136) se confirmó con Crossref (10.1007/978-3-540-34604-3_3). No se citan secciones de Hull 2018 ni de Tuckman–Serrat (no se pudieron confirmar sin el libro).
- Compilación oficial privada con todos los capítulos escritos hasta ese momento: rc=0, 0 undefined, 0 cajas > 10 pt; `referencias_codigo.py --min 0`: 707 referencias, 0 fallos; `correr.py --parcial`: sin fallos de cap05/cap06.

### T8 — nota de cierre (commits dbfd085 `.bib`, 3a4e7d8 `HALLAZGOS.md`, 5a72522 capítulo; todos bajo `docs/tex/`)

Dejado: `capitulos/cap09_riesgo.tex` (8 secciones de la plantilla; 27 ecuaciones numeradas; 83 `\codigo`; 29 `\verif`; 5 citas distintas: `jorion2007`, `mcneil2015`, `ho1992`, `acerbi2002`, `hyndman1996`; 2 recuadros `diferencia`, 1 `limites`, sin `\todo` ni macros nuevas), `verificacion/cap09_riesgo.py` (29 `OK`, rc=0), `simbolos/cap09.tex`; en `referencias.bib` 3 entradas nuevas (Ho 1992, Acerbi–Tasche 2002, Hyndman–Fan 1996, DOI confirmados en Crossref); en `HALLAZGOS.md` H03 (el residuo de la cascada es cero por construcción y «Eventos» es el componente de cierre) y H04 (VaR histórico/ES en Python con convención de cuantil distinta de `historicalVaR`).

Cosas que T11 y los demás deben saber:
- `\cTIIE`, `\cSOFR` y `\cMXNcol` son `\mathrm{…}`: solo valen en modo matemático (en prosa escribí «TIIE-F», «SOFR», «MXN-USD»; `\cMXNcol` imprime «MXN|USD»). Usarlas en texto da «\mathrm allowed only in math mode».
- `qfdesk.log` es latin-1: los `grep` del plan sobre el log necesitan `grep -a` (sin `-a`, `grep -c` no imprime nada). Para atribuir cajas desbordadas a un capítulo, leer el log y llevar el último `(./capitulos/capNN_….tex` abierto.
- Evité choques con los símbolos comunes de §4: liquidado = $\Omega$ (no $S$, que es `\Spar`), cuantil normal = $q_\alpha$ (no $z_\alpha$, que choca con `\zr`), índice de factor = $f,g$ (no $a,b$: `\hwa`, `\basis`), índice del cuantil histórico = $\kappa$, operaciones vivas = $\mathcal O$, mercados de la cascada = $\mathcal C_s$, componentes = $\Delta_s$, choque de escenario = $\Gamma_s$. Dentro de `simbolos/cap09.tex` hay filas con dos o tres símbolos en la misma celda.
- Desviaciones respecto del plan: (1) el backend **no** usa `ScenarioEngine` de C++ (DV01 paralelo unilateral y por pilar central, ambos sobre `MarketContext.shifted`); el capítulo documenta ambos y lo declara en un recuadro `diferencia`. (2) `parametricVaR`, `portfolioVaR`, `historicalVaR` y `monteCarloVaR` de C++ no están en `qfpy` ni los usa el backend: una sola mención, sin fórmulas. (3) CVA: solo la frase que remite a `\ref{cap:xva}`; no se leyó `credit.py`, `xva.py` ni `src/xva/`.
- Referencias cruzadas que usa el capítulo: `cap:ciclo-vida`, `cap:swaps-ois`, `cap:xccy`, `cap:curvas`, `cap:coberturas`, `cap:datos`, `cap:validacion`, `cap:xva`, `ap:simbolos`.
- Compilación del árbol de trabajo a las 20:3x: rc=0, 0 undefined, 1 caja desbordada en el cap. 9 (3.2 pt); las demás cajas > 10 pt del documento son de los caps. 3–6 de otros redactores.
