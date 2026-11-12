# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test

```bash
# Configure (once)
cmake -S . -B build

# Build everything
cmake --build build --target all 2>&1

# Run C++ tests (GoogleTest) — 463 tests, must all pass before commit
cd build && ctest --output-on-failure 2>&1

# Single test file
cd build && ctest -R CVACalculator --output-on-failure

# Build Python bindings
cmake --build build --target qfpy

# Run Python tests
cmake --build build --target pytests

# Web UI (port 5001)
python3 python_web/app.py
```

**Mandatory workflow per task:** build → ctest → commit. Never advance if any step fails.

## Architecture

### Core abstractions

| Interface | Namespace | Implementations |
|---|---|---|
| `IRateModel` | `qf::models` | `Vasicek`, `HullWhite` |
| `IEquityModel` | `qf::models` | `BlackScholesModel`, `HestonModel` |
| `IPricingEngine` | `qf::pricingengines` | `BlackScholesEngine`, `MonteCarloEngine`, `BinomialTreeEngine`, `FDMEngine`, `HestonEngine` |
| `IUnderlying` | `qf::instruments` | equity underlyings |
| `IMarketObserver` | `qf::core` | instruments that reprice on market data change |

**`MarketEnvironment`** (`qf::core`) is the central market data container. It holds named yield curves, spot prices, and implied vols. Instruments query it at pricing time; it notifies subscribers (Observer pattern) on any mutation.

**`EngineFactory::makeEquityEngine("BS"/"MC"/"BT"/"FDM")`** decouples engine selection from calling code.

**`Instrument::pv(MarketEnvironment)`** is the primary pricing API. The legacy `pv(YieldCurve)` overload is preserved for backward-compat with `qfpy`.

### Important distinction

`HestonModel` (in `qf::models`) ≠ `HestonParams` (in `qf::pricingengines::heston.hpp`) — different namespaces. `HestonParams` is preserved for `qfpy` backward-compat.

### XVA module (`qf::xva`)

`CVACalculator` takes an `IRateModel&` (not a concrete type), `ICreditCurve`, LGD, and `SimParams`. Runs Hull-White Monte Carlo over a `NettingSet`. Python bindings in `src/python_bindings/xva_bindings.cpp` expose `qfxva` module.

### Python bindings

- `qfpy` — main bindings (`src/python_bindings/qfpy.cpp`): options, bonds, swaps, curves
- `qfxva` — XVA bindings (`src/python_bindings/xva_bindings.cpp`): `CVAResult.to_dataframe()`

Web UI (`python_web/app.py`, Flask port 5001) imports `qfpy` from `build/src/`. Build `qfpy` target before running.

### Web UI pages

2 pages, 8 JSON endpoints: Options (BS/MC/BT/FDM) and Bonds/Swaps/IRS tab.

## QF Desk (`desk/`)

Workstation local de valuación y riesgo sobre `qfpy` (rama `feat/qf-desk`): backend Flask + SQLite en `desk/api` (Python 3.8 de Anaconda: sin `match` ni `X | Y`) y UI React + TypeScript + Vite en `desk/ui`. Toda la matemática financiera vive en C++ y se llama por `qfpy`; Python valida, orquesta fechas y fijaciones, y persiste.

```bash
./desk/run.sh   # compila qfpy si falta, construye la UI y sirve en http://localhost:5070
```

Las cuatro suites (todas verdes antes de commit; `desk/api` y vitest crecen con cada corte, la cuenta vigente la da su propia salida):

```bash
cmake --build build -j4 && (cd build && ctest --output-on-failure)   # C++ (463)
cmake --build build --target pytests                                  # bindings qfpy (unittest)
/home/claudio/anaconda3/bin/python -m pytest desk/api/tests -q        # backend
cd desk/ui && npm test && npm run build                               # UI (vitest + tsc -b && vite build)
```

Diseño, plan y hoja de ruta: `docs/superpowers/qf-desk/` (`design.md`, `plan.md`, `roadmap.md`) y, por corte, `corte2/` … `corte8/` e `integracion/` (`design.md`, `plan.md`, `audit.md`). El estado y lo pendiente están en la sección 6 de `roadmap.md`. Fijaciones reales: `POST /api/fixings/fetch` (SOFR de la Fed de Nueva York; Banxico requiere `BANXICO_TOKEN`). Respaldo: `python -m desk.api.backup`. Validación contra QuantLib: `desk/validation/make_report.sh` (regenerar tras tocar valuación). Para pruebas con servidor, usar otro puerto que 5070 y una base temporal.

### Reglas vigentes desde 2026-11-11 (pedidas por Claudio)

- **QuantLib primero.** El código nuevo se apoya en QuantLib (`QuantLib==1.42.1` en el Python del backend) o en el `qfpy` existente; no se escribe matemática financiera propia en Python. Debe ser eficiente y con el menor código posible: cada diseño fija un presupuesto de líneas y la auditoría lo revisa.
- **Documentar lo realizado.** Todo trabajo que añada o cambie un modelo, un producto o un cálculo se documenta en LaTeX en `docs/tex/` en el mismo corte: fórmulas matemáticas de lo que el código hace de verdad, referencias académicas verificables (libro o artículo con autor, año y DOI/ISBN) y referencias al código (archivo y símbolo). Un corte no está terminado sin su capítulo; `docs/tex/README.md` dice cómo compilar y cómo comprobar las referencias al código.

## File Conventions

**For each new feature, create three files:**
```
include/qf/<module>/MyClass.hpp
src/<module>/MyClass.cpp
tests/test_MyClass.cpp
```
Update `CMakeLists.txt` if adding new source files or test targets.

**Namespaces:** `qf::instruments`, `qf::pricingengines`, `qf::models`, `qf::math`, `qf::risk`, `qf::termstructure`, `qf::xva`, `qf::core`

**Naming:** `PascalCase` classes · `camelCase` methods/variables · `UPPER_SNAKE_CASE` constants

**Doxygen** all public methods: `@brief`, `@param`, `@return`.

## Plans & Specs

Implementation plans and design specs live in `docs/superpowers/plans/` and `docs/superpowers/specs/`. Read the relevant spec before working on any existing feature area. Active plan: `2026-04-19-quantengine-merge.md` (merging QF + MarketDataFeed into QuantEngine).

## Maintenance log

- 2026-07-07: repo audit — fixed `.gitignore`/tracking inconsistency for `graphify-out/` (324 tracked files), removed overly broad `*.cmake`/`Makefile` ignore lines, anchored `sys` to `/sys`, deleted a stray empty `CMakeFiles/` dir, and moved `docs/plans/2026-06-07-market-feed-tests.md` into `docs/superpowers/plans/` for convention consistency (commit `0f81591`).
