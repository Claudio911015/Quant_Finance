# Quant_Finance

A C++ quantitative finance library for pricing, risk management and financial derivatives.

## About

This library is being built from scratch as an alternative to QuantLib, focused on clarity, modern C++ (C++17/20), and practical use cases in fixed income, derivatives, and risk.

## Planned Modules

- **Instruments**: Bonds, Swaps, Options, Futures, FRAs
- **Term Structure**: Yield curve bootstrapping, interpolation (linear, cubic spline, Nelson-Siegel)
- **Pricing Engines**: Black-Scholes, Binomial trees, Monte Carlo, FD methods
- **Rate Models**: Vasicek, Hull-White, HJM, LMM (LIBOR/SOFR)
- **Risk**: DV01, Greeks, VaR, CVA/DVA/FVA
- **Math**: Linear algebra, root finding (Newton-Raphson, Brent), numerical integration

## Requirements

- C++17 or later
- CMake 3.15+

## Build

```bash
mkdir build && cd build
cmake ..
make
```

## Python Web UI and CMake Integration

The project includes a Python web UI that uses `pybind11` bindings to expose C++ pricing engines through Flask (in `python_web/app.py`).

### Required packages

```bash
sudo apt update
sudo apt install -y build-essential cmake python3 python3-pip python3-venv pybind11-dev doxygen graphviz
python3 -m pip install -r python_web/requirements.txt
```

The `python_web/requirements.txt` file includes:

```text
flask
pybind11
```

### Build and test pipeline (CMake)

```bash
# from repository root
cmake -S . -B build
cmake --build build --target test         # builds C++ tests (GoogleTest)
cmake --build build --target qfpy         # builds Python extension qfpy (pybind11)
cmake --build build --target doxygen      # optional docs (if doxygen installed)
cmake --build build --target pytests      # Python unittest discover for python_web/app.py
```

Con esta configuración, el pipeline puede ejecutarse directamente desde la raíz con rutas relativas:

1. `cmake -S . -B build`
2. `cmake --build build --target test`
3. `cmake --build build --target pytests`
4. `cmake --build build --target qfpy`
5. `cmake --build build --target run_web_ui` (o `python3 python_web/app.py`)

### Run web UI

```bash
# from repository root
python3 python_web/app.py
```

Open `http://127.0.0.1:5000` and use the form. The app queries:
- `qfpy.black_scholes` (C++ API)
- `qfpy.binomial_tree_price`
- `qfpy.montecarlo_price`
- `qfpy.finite_difference_price`

## Status

Work in progress.
