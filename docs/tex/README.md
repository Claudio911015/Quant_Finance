# Documentación técnica de QF Desk (LaTeX)

Documento en español (`report`) con las fórmulas que el código de QF Desk implementa de verdad, las
referencias académicas que las respaldan y la referencia al código (archivo y símbolo) de cada cálculo. El
lector previsto es un quant o un auditor de modelos: debe poder comprobar, fórmula por fórmula, qué se
calcula y dónde está en el código. **Se documenta lo que el código hace, no la teoría del libro**; lo que se
aparta del libro va en un recuadro «Diferencia con la referencia» y lo que contradice la Metodología de la
aplicación, en [`HALLAZGOS.md`](HALLAZGOS.md).

Regla vigente (`CLAUDE.md` del repo): todo corte que añada o cambie un modelo, un producto o un cálculo
entrega su capítulo aquí, en el mismo corte.

## Estructura

```
docs/tex/
  qfdesk.tex             documento maestro (portada, índice, \include de los 15 capítulos, apéndice, bibliografía)
  preambulo.tex          paquetes, macros, notación y entornos (ÚNICO lugar con \newcommand)
  referencias.bib        bibliografía única
  plainnat-es.bst        estilo bibliográfico (plainnat con las cadenas en español)
  latexmkrc              hace que bibtex encuentre plainnat-es.bst y referencias.bib con -outdir
  HALLAZGOS.md           discrepancias código <-> Metodología encontradas al documentar
  capitulos/             un archivo por capítulo (cap01_… cap15_…), apendice_simbolos.tex y _plantilla.tex
  simbolos/capNN.tex     filas de la tabla de símbolos propias de cada capítulo
  verificacion/          comun.py, correr.py, referencias_codigo.py y un capNN_<tema>.py por capítulo 2-12
```

Capítulos: 1 Introducción, arquitectura y convenciones · 2 Curvas · 3 Swaps de tasa OIS · 4 Derivados de FX
y opción sobre acción · 5 Hull–White · 6 Bonos · 7 Cross currency swap · 8 Ciclo de vida, liquidaciones y
P&L · 9 Riesgo · 10 Contabilidad de coberturas IFRS 9 · 11 Operaciones: conciliación · 12 Validación contra
QuantLib · 13 Fuentes de datos y procedencia · 14 XVA y curvas de crédito (marcador) · 15 Exóticos de FX
(marcador) · Apéndice A: tabla de símbolos. Las etiquetas de capítulo son fijas: `cap:introduccion`,
`cap:curvas`, `cap:swaps-ois`, `cap:fx`, `cap:hull-white`, `cap:bonos`, `cap:xccy`, `cap:ciclo-vida`,
`cap:riesgo`, `cap:coberturas`, `cap:operaciones`, `cap:validacion`, `cap:datos`, `cap:xva`,
`cap:exoticos-fx` y `ap:simbolos` (apéndice). Un capítulo solo referencia con `\ref` sus propias etiquetas
internas (`eq:capNN-…`, `sec:capNN-…`, `tab:capNN-…`) o estas etiquetas fijas.

## Requisitos

- `pdflatex`, `latexmk` y `bibtex` (TeX Live). No hay `biber`; la bibliografía usa `natbib` + `bibtex`.
- Paquetes: `natbib`, `amsmath`, `amssymb`, `amsthm`, `booktabs`, `longtable`, `array`, `hyperref`,
  `cleveref`, `doi`, `xurl`, `listings`, `todonotes`, `tcolorbox`, `xcolor`, `xspace`, `geometry`, `lmodern`,
  `siunitx`, `csquotes`, `microtype`. No hay nada que instalar en esta máquina.
- **Idioma.** `babel` no tiene instalada la opción `spanish` aquí: el preámbulo usa
  `\usepackage[english]{babel}` + `\babelprovide[import,main]{spanish}`. Los títulos («Capítulo», «Índice»,
  «Bibliografía») salen en español, pero **la partición de palabras usa patrones ingleses**. Quien quiera
  partición correcta puede instalar `texlive-lang-spanish` y cambiar esas dos líneas del preámbulo por
  `\usepackage[spanish]{babel}`.
- **Estilo bibliográfico.** `plainnat-es.bst` es una copia de `plainnat.bst` (natbib) con «and» → «y» entre
  autores (sin coma de Oxford), «editor(es)», «edición», «vol.», «pp.», «En», meses, etc. Los cambios son solo
  de cadenas literales y están listados en el encabezado del archivo.
- Python para las verificaciones: el del backend, `/home/claudio/anaconda3/bin/python` (3.8), con `qfpy`
  compilado en `build/src/` (no se recompila desde aquí). Los scripts usan solo la stdlib y el código del
  proyecto.

## Compilar

Compilación oficial (desde la raíz del repo):

```bash
cd docs/tex && latexmk -pdf -interaction=nonstopmode -halt-on-error qfdesk.tex; echo rc=$?
```

Debe terminar con `rc=0` y producir `qfdesk.pdf`. El PDF y los auxiliares **no se versionan** (`.gitignore`).
Comprobaciones sobre `qfdesk.log` (ambas deben dar `0`):

```bash
grep -cE "(Citation|Reference) .* undefined" qfdesk.log
grep -oE 'Overfull \\[hv]box \(([0-9.]+)pt' qfdesk.log | grep -oE '[0-9.]+' | awk '$1>10' | wc -l
```

Compilación privada (varios redactores en paralelo sin pisar los `.aux` unos de otros; `TAREA` = un nombre
cualquiera):

```bash
cd docs/tex && OUT=/tmp/qfdocs-$TAREA && rm -rf $OUT && mkdir -p $OUT/capitulos && \
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=$OUT qfdesk.tex >/dev/null 2>&1; echo rc=$?
```

(el `latexmkrc` de este directorio hace que `bibtex`, que corre dentro de `$OUT`, encuentre
`plainnat-es.bst` y `referencias.bib`; por eso `latexmk` se lanza siempre desde `docs/tex`).
Citas usadas frente a entradas del `.bib`:

```bash
cd $OUT && cat qfdesk.aux capitulos/*.aux | grep -oP '\\citation\{\K[^}]+' | tr ',' '\n' | sort -u > /tmp/citadas.txt
grep -oP '^@\w+\{\K[^,]+' /home/claudio/Git/Quant_Finance/docs/tex/referencias.bib | sort -u > /tmp/bib.txt
comm -13 /tmp/citadas.txt /tmp/bib.txt   # entradas sin citar
comm -23 /tmp/citadas.txt /tmp/bib.txt   # citas sin entrada
```

Nota: en esta instalación `longtable` imprime en el log `ignored error: Infinite glue shrinkage found in box
being split` al partir una tabla entre páginas (también con un `longtable` mínimo, sin nuestro preámbulo); es
un mensaje conocido que no afecta al resultado ni al código de salida.

## Verificaciones (desde la raíz del repo)

```bash
python docs/tex/verificacion/correr.py              # ejemplos numéricos; código 0 si todo cuadra
python docs/tex/verificacion/referencias_codigo.py  # referencias \codigo; código 0, N >= 120, 0 fallos
```

- `correr.py` corre cada `verificacion/capNN_*.py`, y exige: todos terminan con 0; cada `\verif{id}{valor}`
  de `capitulos/cap*.tex` sale como `OK id` en algún script; el `id` empieza por `capNN-` del archivo donde
  está; y (sin `--parcial`) cada capítulo 02-12 tiene al menos 2 `\verif`. Salida: `N scripts, M valores
  verificados` y, si falla, qué falta. `--parcial` omite la cuota por capítulo (mientras se escribe).
- `referencias_codigo.py` extrae todas las `\codigo{ruta}{símbolo}` de `docs/tex/**/*.tex` (menos los
  archivos que empiezan por `_` y los comentarios LaTeX) y comprueba que la ruta existe (relativa a la raíz
  del repo) y que el símbolo está **definido** en ese archivo: `def`/`class`/constante de módulo en `.py`
  (`Clase.metodo` exige la clase y el método); en C++ `Clase::metodo(`, o `class|struct Clase` más
  `metodo(`, o el nombre simple como `class|struct|enum|namespace|using NOMBRE`, `NOMBRE(`, `NOMBRE =` o el
  literal `"NOMBRE"` de un binding pybind11; en `.ts/.tsx`, `function|const|class|interface|type NOMBRE`; en
  `.json/.md/.sh/.txt`, que el texto aparezca. Imprime cada fallo y `N referencias, F fallos`; código 0 si
  `F = 0` y `N >= 120` (`--min K` cambia el mínimo). No se citan números de línea (caducan). Las rutas
  deben ser archivos, no directorios, y el símbolo se escribe con `_` normal (no `\_`).

Ejemplo de un script de capítulo, `verificacion/cap03_swaps_ois.py`:

```python
"""Ejemplos verificables del capítulo 3 (swaps OIS)."""
import comun                      # primero: arregla sys.path (RAIZ y build/src)
from desk.api.qf import qfpy      # o funciones de desk.api.*

def tasa_par():
    ...                           # insumos idénticos a los del texto, construidos aquí
    return swap.par_rate(env)

comun.comprobar("cap03-tasa-par", tasa_par(), 1e-8)   # compara contra \verif{cap03-tasa-par}{...} del .tex
comun.terminar()                                       # código 1 si hubo alguna FALLA
```

`comun.py` expone `RAIZ`, `impreso(id)`, `comprobar(id, calculado, tol)` y `terminar()`. Reglas: el cálculo
llama al código del proyecto (`qfpy` o `desk.api.*`), nunca reimplementa la fórmula; solo stdlib + proyecto;
insumos construidos dentro del script; **no se lee `desk/data/desk.db` ni la red** (si hace falta SQLite,
una base temporal con `desk.api.db.connect` + `init_schema` y siembra determinista); cada `id` aparece en
exactamente un `\verif` y en exactamente un script. El valor impreso lleva los dígitos suficientes y la
tolerancia es al menos media unidad del último dígito impreso (`comprobar` avisa por `stderr` si no).

## Macros y entornos (todas en `preambulo.tex`; los capítulos no definen otras)

| Macro | Uso |
|---|---|
| `\codigo{ruta}{símbolo}` | referencia al código; imprime `ruta: símbolo` en monoespaciada y parte la línea en `/`, `_`, `.`, `:`, `-` |
| `\verif{id}{valor}` | número de un ejemplo verificable (`id` = `capNN-nombre`, único en el documento; `valor` decimal con punto, signo y exponente `e` opcionales) |
| `\DF`, `\DFt`, `\zr`, `\fwd`, `\yf` | factor de descuento, tasa cero, forward simple, fracción de año |
| `\Nom \K \ON \Rcomp \Ann \Spar \Spot \FxF \vol \Ncdf \PV \PnL \DVO \VaR \ES \hwa \hwsig \hwtheta \basis \E \Q` | símbolos comunes (apéndice A) |
| `\cTIIE \cSOFR \cMXNcol` | etiquetas de curva (subíndices; modo matemático) |
| `\MXN \USD \pb` | texto; punto base se escribe `1~\pb` |

Los símbolos sin argumento se usan en modo matemático (`$\Nom$`). Entornos: `diferencia` (recuadro «Diferencia
con la referencia»), `limites` (recuadro «Límites y supuestos») y `aviso` (aviso destacado; título opcional
`\begin{aviso}[Aviso IFRS 9]`). Ecuaciones con `equation`/`align`, numeradas por capítulo; sin teoremas.
`\todo[inline]{…}` solo en los capítulos marcador 14 y 15. `\cref`/`\Cref` y `\eqref` están disponibles.

## Bibliografía

Solo obras reales. **Libros y artículos**: autores, año, título, editorial o revista y `doi` o `isbn`
**confirmados** contra crossref.org u openlibrary.org (o la página de la editorial); nunca completar un DOI
o ISBN «de memoria». **Excepción declarada**: normas, documentación institucional y estándares sin DOI ni
ISBN (IFRS 9 del IASB, documentación de SOFR de la Fed de Nueva York, TIIE de Fondeo de Banxico, definiciones
ISDA, FpML) entran como `@manual` (o `@misc`) con el organismo emisor como autor entre llaves dobles
(`author = {{International Accounting Standards Board}}`), `year`, `title`, `url` oficial que responda (200) y
`note = {Consultado el AAAA-MM-DD}`. Claves `apellidoAAAA` en minúsculas sin acentos (`hull1990`); si chocan,
sufijo `a`, `b`. Edición en `edition` con palabra en español (`segunda`, `tercera`): el estilo añade «edición».
`referencias.bib` es compartido: releer antes de editar, añadir solo al final, no reordenar ni reformatear
entradas ajenas, y no escribir `@` dentro de los comentarios del archivo (BibTeX lo lee como inicio de
entrada).

## Añadir un capítulo (lista de comprobación)

1. Copiar `capitulos/_plantilla.tex` a `capitulos/capNN_<tema>.tex` y mantener `\chapter{…}\label{cap:…}`.
2. Dar de alta el `\include{capitulos/capNN_<tema>}` en `qfdesk.tex` (en su orden) si el capítulo es nuevo.
3. Cubrir las 8 secciones de la plantilla: propósito, notación, modelo y fórmulas, implementación,
   ejemplo numérico verificable, validación, límites y supuestos, referencias.
4. Al menos 11 `\codigo` (5 en los capítulos 1 y 13), y al menos uno por sección que exponga un cálculo.
5. Al menos 2 `\verif` con su script `verificacion/capNN_<tema>.py` (tolerancia declarada en el texto).
6. Al menos 2 citas distintas, cada obra confirmada con DOI/ISBN (o `@manual` con URL oficial).
7. Un recuadro `diferencia` donde el código se aparta del libro (o una frase explícita de que no hay
   diferencia) y un recuadro `limites` con los límites que ya declara la Metodología (R6); el capítulo 10
   lleva además un `aviso` de revisión pendiente por un contador IFRS 9.
8. Sin macros nuevas (`\newcommand`, `\def`, `\DeclareMathOperator`); símbolos propios declarados en la
   sección «Notación» y como filas de `simbolos/capNN.tex` (`símbolo & significado & unidad \\`; borrar la
   fila «Sin símbolos propios por ahora»).
9. Discrepancias código <-> Metodología: entrada nueva al final de `HALLAZGOS.md` (no se corrige el código).
10. Correr las dos verificaciones y la compilación de arriba (0 *undefined*, 0 cajas > 10 pt).
11. Commit solo de rutas bajo `docs/tex/`, en español y explicando el porqué:
    `GRAPHIFY_SKIP_HOOK=1 git commit -m "docs(tex): …" -- <rutas explícitas>`.
