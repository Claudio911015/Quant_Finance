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

## Status

Work in progress.
