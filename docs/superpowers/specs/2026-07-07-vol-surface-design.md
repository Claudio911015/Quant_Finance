# Implied-Vol Surface in MarketEnvironment (P4) — Design Spec

**Date:** 2026-07-07
**Project:** Quant_Finance (`~/Git/Quant_Finance`)
**Status:** Approved (P4 of the roadmap — ships after P1 DVA/FVA `6ec9f06`, P2 ScenarioEngine `a23e1eb`, P3 Heston calibration `6382d29`)
**Scope:** Give `MarketEnvironment` a real per-ticker implied-vol surface so that the four
equity engines (BS/MC/BT/FDM) mark every option at its own strike/maturity vol instead of
one flat scalar per ticker. Ships as three sequenced, independently-committable pieces
(P4a surface object, P4b environment + resolver integration, P4c Python bindings +
Heston-to-surface bridge).

---

## 1. Context and Motivation

Today `MarketEnvironment` holds one scalar vol per ticker (`vols_` map). `env_resolver.hpp`
feeds that single number to all four equity engines even though `params.strike` and
`params.maturity` are available at the lookup site. Consequences:

- An OTM put and an ATM call on the same ticker are forced to the same vol → skew
  positions cannot be marked and smile P&L is invisible.
- P3's calibrated Heston smiles have nowhere to live in the environment.

Everything needed to close this already shipped earlier this round:

- `qf::math::Interpolator` — 1-D linear/cubic with **flat extrapolation** (documented in
  `interpolation.hpp`). Requires ≥2 points and strictly increasing x.
- `qf::pricingengines::impliedVolatility` — Brent inverter (`blackscholes.cpp:107`).
- `qf::models::OptionQuote` — `{strike, maturity, type, marketPrice}` (P3).
- `ChangeType::VolatilityChanged` — observer event already defined in `imarket_observer.hpp`.
- qfpy binding patterns (P2c KRD ladder, P3 `calibrate_heston`).

## 2. P4a — `qf::termstructure::VolSurface`

Lives next to `YieldCurve` (module convention: hpp/cpp/test triple). Two constructors:

1. **Grid**: `VolSurface(maturities, strikes, vols, strikeMethod)` where `vols[i][j]` is the
   implied vol at `maturities[i] × strikes[j]`.
2. **Quotes**: `VolSurface::fromQuotes(spot, r, q, quotes, strikeMethod)` — inverts each
   `models::OptionQuote` with the existing Brent `impliedVolatility` and lays the results on
   the grid of distinct strikes × maturities found in the quotes. The quotes must form a
   **complete rectangular grid** (every strike×maturity cell present exactly once); a missing
   or duplicate cell throws `std::invalid_argument`. This is the same chain a desk feeds
   `HestonCalibrator`, so one data set builds both the calibration and the mark-to-market
   surface.

**Lookup `vol(strike, maturity)`** — the standard calendar-consistent recipe:

1. Per maturity pillar `i`, interpolate the smile in strike (`strikeMethod`, linear/cubic,
   flat extrapolation) → a vol at the requested strike for that pillar.
2. Convert each to **total variance** `w_i = σ_i² · T_i` and interpolate `w` **linearly in
   maturity** (flat extrapolation on `w`). Return `σ = √(w(T) / T)`.

Interpolating in total variance rather than raw vol is the standard choice that avoids the
calendar-arbitrage artifacts of interpolating vols directly, and makes an interpolated
mid-curve mark auditable when risk control asks where it came from.

**Construction guards** (throw `std::invalid_argument`, consistent with how `hestonPrice`
validates its inputs):

- ≥2 maturities and ≥2 strikes; both strictly increasing.
- `vols` dimensions match `maturities.size() × strikes.size()`.
- All vols strictly positive.
- **Non-decreasing total variance in T at each fixed strike pillar** (`σ_{i,j}² T_i`
  non-decreasing in `i`) — the calendar-arbitrage sanity guard.

**Out of scope** (stated in the header, mirroring P3's scope note): SVI / parametric fits,
dividend term structures, local vol / Dupire, American de-Americanization.

## 3. P4b — MarketEnvironment + env_resolver integration

- `MarketEnvironment` gains `setVolSurface(ticker, VolSurface)` (fires
  `ChangeType::VolatilityChanged`, so Observer-subscribed instruments reprice on a surface
  update exactly as on a flat-vol update) and a new overload
  `volatility(ticker, strike, maturity)` that **prefers the surface** and **falls back to the
  existing flat `vols_` entry** when no surface is set.
- The scalar `setVolatility` / `volatility(ticker)` API is **untouched**.
- One edit in `detail::resolveEquityParams` (`env_resolver.hpp:20`) switches the lookup to
  the new overload (strike and maturity are already in hand there). That single choke point
  makes all four equity engines smile-consistent automatically — no engine code changes,
  mirroring how P2's ScenarioEngine achieved instrument-agnostic coverage through
  `Instrument::pv()`.

**Backward compatibility (hard constraint):** with no surface set, `volatility(ticker,K,T)`
returns exactly the flat scalar `volatility(ticker)` returns today, so every existing test and
every qfpy notebook keeps working unmodified. The mandatory build → ctest → commit workflow,
with all pre-existing tests passing untouched, is the proof.

## 4. P4c — qfpy bindings + Heston-to-surface bridge

Follows the established binding patterns. Bind: `VolSurface` (both constructors),
`env.set_vol_surface`, the `(strike, maturity)` `volatility` overload, and `to_grid()`
returning `(maturities, strikes, vols)` for direct pandas/matplotlib plots. Plus one
convenience closing the P3 loop:

`surface_from_heston(params, spot, r, q, strikes, maturities)` — prices the grid through the
existing semi-analytic `hestonPrice`, inverts with the existing `impliedVolatility`, and
returns a smooth arbitrage-consistent `VolSurface`. Full workflow, entirely in Python:
pull listed quotes → `calibrate_heston` → smooth surface → `set_vol_surface` → mark and risk
anything.

`tests/test_volsurface_py.py` mirrors `test_calibration_py.py` (loads the real built qfpy,
skips gracefully when not built).

## 5. Deferred (per plan): parallel surface vega

`risk::surfaceVega` (copy env, detach observers, parallel-shift the surface, reprice) is
explicitly deferrable and is **cut this round**. A uniform vol shift can push a low-vol pillar
below the calendar-arbitrage guard, which would require a validation-bypass path on
`VolSurface`; that is not worth weakening the guard for in the core deliverable. It ships next
round as one small commit once a trusted-bump path is designed. P4a/b/c stand alone without it.

## 6. Testing gate

- **P4a** (`tests/test_volsurface.cpp`): grid recovery at pillars; interpolation sanity
  between pillars (total-variance monotonic, positive); `fromQuotes` round-trip against known
  BS prices; validation throws (non-positive vol, calendar-arbitrage, ragged grid, incomplete
  quote grid).
- **P4b** (`tests/test_market_environment.cpp`): surface preferred over flat; flat fallback
  identical to today; observer notification fires on `setVolSurface`.
- **P4c** (`tests/test_volsurface_py.py`): grid round-trip and `surface_from_heston` smoke.
- Full suite green via `cd build && ctest --output-on-failure` before each commit.
