# Scenario Engine — Curve Rate-Risk Tooling (P2) — Design Spec

**Date:** 2026-07-07
**Project:** Quant_Finance (`~/Git/Quant_Finance`)
**Status:** Approved (P2 of the rates roadmap — ships after P1 DVA/FVA, commit `6ec9f06`)
**Scope:** Add first-class curve rate-risk tooling — parallel DV01, a key-rate DV01
(KRD) ladder, and named curve scenarios (steepener / flattener / parallel shock) —
that reprices **any** `qf::instruments::Instrument` against a bumped copy of the
`MarketEnvironment`. Ships as three sequenced, individually-committable pieces
(P2a curve prerequisite, P2b core engine, P2c Python bindings).

---

## 1. Context and Motivation

Today the only rate-risk primitive is the flat scalar-yield `qf::risk::dv01()` in
`include/qf/risk/greeks.hpp`, which takes a `std::function<double(double)>` and forces
the caller to hand-roll a repricing lambda over a single scalar yield. There is **no
scenario / bump machinery** anywhere: no per-pillar bump, no key-rate ladder, no
named curve shocks. A desk hedging a rates book needs to know *which tenor bucket*
(2Y / 5Y / 10Y) carries the risk — a single flat DV01 cannot answer that.

A concrete blocker exists: `YieldCurve` (`include/qf/termstructure/yieldcurve.hpp`)
moves its pillar `maturities`/`rates` into a private `math::Interpolator` and exposes
**no accessors**, so no code can bump pillar *k* of an existing curve. P2 therefore
needs a small pillar-access prerequisite (P2a) before the engine (P2b) is possible.

De-risking facts that make P2 cheap and safe:

- `Instrument::pv(MarketEnvironment)` is a uniform pricing API across Bond / Swap /
  CapFloor / Swaption — one engine covers all instruments.
- Independent analytic cross-checks already exist for tests: `Bond::duration()` (modified
  duration under continuous compounding = `Σ tᵢ·cfᵢ·DF(tᵢ) / P`) gives
  `Bond DV01 = duration · price · 1bp` exactly to O(h²); `InterestRateSwap::annuity()`
  gives the fixed-rate PV01 that a par swap's parallel-curve DV01 matches in magnitude
  to a few percent (see §5).
- `qf::risk` is entirely absent from `qfpy` today — Python users have zero rate-risk
  tooling, so P2c adds strictly new surface.

Deliberately **excluded** (future proposals, no rework needed): dual-curve (P5) and
vol scenarios (P4). The engine is curve-name-agnostic, so when P5 lands it produces
per-curve ladders (OIS delta vs projection delta) with zero changes here.

---

## 2. Chosen Approach

### Conventions

- **All bump sizes are expressed in basis points** (`1.0 == 1 bp == 1e-4 in the
  continuously-compounded zero rate`), matching the desk mental model and the plan's
  `bpShift` / `perPillarShiftsBp` naming. This is the single convention used throughout
  P2a/P2b/P2c.
- **DV01 sign convention follows the existing `qf::risk::dv01()`**: a DV01 is the
  *dollar value of a 1 bp move*, computed by central difference and **positive when PV
  rises as rates fall** (`(pv(down) − pv(up)) / 2`). All P2 DV01s are normalised
  *per 1 bp* by dividing the central difference by the bump size in bp, so the reported
  number is independent of the finite-difference step chosen.

### P2a — YieldCurve pillar access + bump construction (prerequisite, small)

`YieldCurve` retains its pillar vectors (`maturities_`, `rates_`) and interpolation
method alongside the existing `interp_`. New **purely additive** const surface:

- `const std::vector<double>& maturities() const;`
- `const std::vector<double>& rates() const;`
- `math::InterpolationMethod interpolationMethod() const;`
- `YieldCurve parallelBump(double bpShift) const;` — every pillar rate shifted by
  `bpShift·1e-4`, interpolation method preserved.
- `YieldCurve bumped(std::size_t pillarIndex, double bpShift) const;` — only pillar
  `pillarIndex` shifted (throws `std::out_of_range` if out of range).

No existing signature changes → the 291 ctest cases and `qfpy` backward-compat are
untouched.

### P2b — qf::risk ScenarioEngine (core, medium)

New three-file feature `include/qf/risk/scenario.hpp`, `src/risk/scenario.cpp`,
`tests/test_scenario.cpp`, namespace `qf::risk`.

Result structs:

```cpp
struct KeyRateDV01 { double maturity; double dv01; };   // per-pillar ladder rung
struct ScenarioResult { std::string label; double basePV; double scenarioPV; double pnl; };
```

`ScenarioEngine` holds a target curve name (default `"default"`) and a finite-difference
bump size in bp (default `1.0`). API:

- `double parallelDV01(const Instrument&, const MarketEnvironment&) const;`
  central difference of `pv()` under `YieldCurve::parallelBump(±bump)`, normalised per 1 bp.
- `std::vector<KeyRateDV01> keyRateDV01s(const Instrument&, const MarketEnvironment&) const;`
  one central-difference rung per curve pillar via `YieldCurve::bumped(k, ±bump)`.
- `ScenarioResult runScenario(const Instrument&, const MarketEnvironment&,
  const std::vector<double>& perPillarShiftsBp, const std::string& label) const;`
  full revaluation (one-sided) under an arbitrary per-pillar shift vector
  (throws if its size ≠ pillar count). Returns base PV, scenario PV, and P&L.
- Convenience wrappers building shift vectors, then delegating to `runScenario`:
  `parallelShock(inst, env, magnitudeBp)`, `steepener(inst, env, magnitudeBp)`
  (linear ramp −mag→+mag across pillars), `flattener(...)` (+mag→−mag).

**Bumped-copy discipline (critical):** the engine never mutates the live environment.
It copies the `MarketEnvironment`, calls `unsubscribeAll()` on the copy (the copy inherits
weak_ptr observers, which must be detached so a bump never fires phantom `onMarketChange`
notifications into Observer-subscribed instruments), then `addCurve()` the bumped curve
on the copy and prices against it. All other curves / spots / vols are preserved by the copy.

Works unchanged on Bond, Swap, CapFloor, Swaption because all price via
`Instrument::pv(MarketEnvironment)`.

### P2c — qfpy bindings (small)

Bind, in `src/python_bindings/qfpy.cpp`: the new `YieldCurve.maturities()/rates()/bumped()/
parallel_bump()`; `KeyRateDV01` and `ScenarioResult` value types; and `ScenarioEngine`
with `parallel_dv01`, `key_rate_dv01s`, `run_scenario`, `parallel_shock`, `steepener`,
`flattener`. The KRD ladder additionally gets a free helper
`key_rate_dv01_dataframe(engine, inst, env)` returning a pandas `DataFrame` with columns
`maturity`, `dv01` — following the precedent of `CVAResult.to_dataframe()` in
`xva_bindings.cpp` — so `pd.DataFrame` ingestion is one line. Additive only; no existing
binding changes.

---

## 3. Backward-compatibility constraints

- No existing public signature changes anywhere. P2a adds const accessors + const
  factory methods; P2b is a brand-new module; P2c adds new bindings only.
- Existing `qf::risk::dv01()` (scalar-yield) is left untouched.
- `qfxva` is not touched.

---

## 4. Quant subtlety (must be in Doxygen)

Under **CubicSpline** interpolation a single-pillar bump is **non-local** (the spline's
second-derivative solve couples all knots), so the KRD ladder does **not** sum exactly to
the parallel DV01. Under **Linear** interpolation the linear basis functions form a
partition of unity, so single-pillar bumps are local and the ladder sums to the parallel
DV01 to O(h²) (verified numerically: relative error ~1e-9). Therefore **KRD-additivity
acceptance tests run under Linear interpolation** with a tight tolerance; spline mode is
documented as approximate.

---

## 5. Testing gate

`tests/test_scenario.cpp` (GoogleTest, added to `tests/CMakeLists.txt`):

- **Bond parallel DV01 == `duration(curve)·price(curve)·1e-4`** (tight, exact to O(h²)).
- **Bond KRD ladder sums to parallel DV01 under Linear** (tight, ~1e-6 relative);
  ladder maturities equal the curve pillars.
- **Par payer-swap parallel DV01 matches `annuity·notional·1bp` in magnitude** with a
  documented ~5 % tolerance (they are related but distinct measures — annuity is the
  fixed-rate PV01, the engine reports the parallel-curve DV01; ratio ≈ −1.025 for a flat
  5 % 5Y swap), and its sign is negative for a payer.
- **`runScenario` P&L identity**: `pnl == scenarioPV − basePV`; a size-mismatched shift
  vector throws.
- **Steepener vs flattener** produce opposite-signed P&L on a directional book;
  `parallelShock(+100bp)` P&L has the same sign as (and larger magnitude than) `parallelDV01`.
- **Observer safety**: an instrument subscribed to the live env as an `IMarketObserver`
  receives **no** notification during a scenario run (bumped-copy discipline).

`tests/test_app.py`-style Python test (real built `qfpy`, `unittest.skipUnless` if the
module can't be imported so the `pytests` target stays green without a build):
`ScenarioEngine.key_rate_dv01s` returns one rung per pillar and
`key_rate_dv01_dataframe` yields a 2-column frame.

**Regression gate:** full `ctest` suite (currently 291 tests) stays green; each of P2a/P2b/P2c
ships as its own commit only after `cmake --build build --target all && ctest` is clean.
