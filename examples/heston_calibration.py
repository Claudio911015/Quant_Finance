#!/usr/bin/env python3
"""Calibrate the Heston model to a listed European call chain (P3 example).

Workflow demonstrated:
    synthetic listed quotes  ->  calibrate_heston  ->  reprice chain  ->
    report per-quote fit error in implied-vol terms.

Run after building the qfpy bindings:
    cmake --build build --target qfpy
    python3 examples/heston_calibration.py
"""
import glob
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for d in (os.path.join(_REPO, "build", "src"), os.path.join(_REPO, "build")):
    if glob.glob(os.path.join(d, "qfpy*.so")):
        sys.path.insert(0, d)
        break

import qfpy  # noqa: E402

SPOT, R, Q = 100.0, 0.03, 0.0

# --- 1. Build a synthetic "listed" chain from known ground-truth params. ------
truth = qfpy.HestonParams()
truth.v0, truth.kappa, truth.theta, truth.sigma, truth.rho = 0.04, 1.5, 0.05, 0.4, -0.6

strikes = [80.0, 90.0, 100.0, 110.0, 120.0]
maturities = [0.25, 0.5, 1.0, 2.0]


def make_opt(strike, maturity, vol=0.0):
    o = qfpy.OptionParams()
    o.spot, o.strike, o.riskFreeRate, o.dividendYield = SPOT, strike, R, Q
    o.volatility, o.maturity = vol, maturity
    o.type, o.exercise = qfpy.OptionType.Call, qfpy.ExerciseType.European
    return o


quotes = []  # (strike, maturity, type, price) tuples — the DataFrame-friendly form
for T in maturities:
    for K in strikes:
        px = qfpy.heston_price(make_opt(K, T), truth)
        quotes.append((K, T, qfpy.OptionType.Call, px))

# --- 2. Calibrate from a deliberately-wrong starting point. -------------------
print("Calibrating Heston to %d listed quotes..." % len(quotes))
res = qfpy.calibrate_heston(SPOT, R, Q, quotes,
                            objective=qfpy.CalibrationObjective.ImpliedVol)

p = res.params
print("\nConverged: %s   iterations: %d   RMSE(IV): %.2e"
      % (res.converged, res.iterations, res.rmse))
print("Fitted params:")
print("  v0=%.4f  kappa=%.4f  theta=%.4f  sigma=%.4f  rho=%.4f"
      % (p.v0, p.kappa, p.theta, p.sigma, p.rho))
print("Truth  params:")
print("  v0=%.4f  kappa=%.4f  theta=%.4f  sigma=%.4f  rho=%.4f"
      % (truth.v0, truth.kappa, truth.theta, truth.sigma, truth.rho))

# --- 3. Reprice the chain with fitted params, report fit error in IV terms. ---
print("\n  K      T     mktIV    modelIV    diff(bp)")
for (K, T, _, mkt_px) in quotes:
    model_px = qfpy.heston_price(make_opt(K, T), p)
    mkt_iv = qfpy.implied_volatility(make_opt(K, T), mkt_px)
    model_iv = qfpy.implied_volatility(make_opt(K, T), model_px)
    print("%5.0f  %4.2f  %7.4f  %8.4f  %+8.2f"
          % (K, T, mkt_iv, model_iv, (model_iv - mkt_iv) * 1e4))
