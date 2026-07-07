# Dual-Curve Pricing — Phase 1 (P5) — Design Spec

**Date:** 2026-07-07
**Project:** Quant_Finance (`~/Git/Quant_Finance`)
**Status:** Approved (P5 of the rates roadmap — ships after P1 DVA/FVA `6ec9f06`, P2 ScenarioEngine, P3 Heston calibration, P4 VolSurface)
**Scope:** Dual-curve **pricing** given two exogenously supplied curves (an OIS discount
curve and a separate projection/index curve). This is *not* dual-curve bootstrapping —
both curves are supplied by the caller. Ships as three sequenced, individually-committable
pieces (P5a pricing core + `InterestRateSwap::calculatePV` wart fix, P5b dual-curve risk,
P5c Python bindings + scope doc).

---

## 1. Context and Motivation

Every swap in the library today prices single-curve: the floating leg is projected off
the same curve used to discount it, via the replication identity `N·(1−P(0,T))`. Post-2008
market practice discounts collateralised trades off the OIS curve while projecting the
floating index (e.g. 3M term SOFR / LIBOR-legacy) off a *separate* forward curve. A swap
marked single-curve silently embeds the OIS/index basis as P&L error — tens of thousands
of dollars on a 100M 10y swap at a 20–30 bp basis.

Two verified blockers this phase removes:

1. **No curve keys on the pricing objects.** `InterestRateSwap`, `ScheduledLeg`, and
   `ScheduledSwap` all read `env.curve()` (the `"default"` curve) for both projection and
   discounting. There is no way to say "discount off `USD.OIS`, project off `USD.3M`".

2. **`InterestRateSwap` is unreachable through `Instrument::pv()`.** `Swap::calculatePV`
   (`swap.hpp:101-103`) dispatches to `Swap::npv` — the base leg-difference
   `payLeg.pv() − receiveLeg.pv()` — which mixes notional conventions (fixed leg includes
   the final notional repayment; floating leg uses the notional-free replication identity)
   and ignores `Payer`/`Receiver`. `InterestRateSwap::npv` (`swap.cpp:82-97`) is the
   economically correct value but is a non-virtual method the generic `Instrument`
   interface never reaches. Flagged as a wart in `tests/test_scenario.cpp:82-89`. A repo
   grep confirms **no** existing test pins the old leg-difference behaviour for
   `InterestRateSwap`, so fixing it is safe.

`ScheduledLeg`/`ScheduledSwap` are also plain classes, not `Instrument` subclasses, so the
modern schedule-explicit primitives cannot go through the P2 `ScenarioEngine` at all
(`scenario.hpp` already anticipates per-curve ladders under dual-curve).

---

## 2. Definitions and Conventions

### CurveKeys

```cpp
struct CurveKeys {
    std::string discountKey  {"default"};   // curve used to discount cash flows
    std::string projectionKey{"default"};   // curve used to imply floating forwards
    bool keysEqual() const { return discountKey == projectionKey; }
};
```

Stored at construction on `InterestRateSwap`, `ScheduledLeg`, and (per-leg via its legs)
`ScheduledSwap`. Defaults to `{"default","default"}`.

### Pricing dispatch (the backward-compat guarantee)

Pricing dispatches on **key equality**:

- **`discountKey == projectionKey`** (including the default `{"default","default"}`):
  the existing single-curve code path runs **verbatim**, reading `env.curve(discountKey)`.
  Because the default key is `"default"`, `env.curve("default") == env.curve()`, so the
  result is **bit-identical** to today's output. No floating-point telescoping argument is
  needed — the same code executes.

- **`discountKey != projectionKey`**: the floating leg uses the explicit dual-curve form

  ```
  PV_float = Σ_i N_i · ( P_proj(t_{i-1})/P_proj(t_i) − 1 + spread·τ_i ) · P_dis(t_i)
  ```

  projected off `P_proj` and discounted off `P_dis`. The fixed leg discounts off `P_dis`:
  `PV_fixed = Σ_i N_i·K·τ_i·P_dis(t_i)`.

### Equivalence of the two paths (tested to ~1e-13 relative)

When the same pillar data is registered under two distinct curve names, the explicit
dual-curve sum equals the replication path, because for `P_proj == P_dis == P`:

```
Σ_i N_i·(P(t_{i-1})/P(t_i) − 1)·P(t_i) = Σ_i N_i·(P(t_{i-1}) − P(t_i))
```

which telescopes (constant N) to `N·(1 − P(T))` and, for amortizing N, equals the existing
generalized replication term-for-term (verified algebraically in the plan; pinned by a
~1e-13 relative-tolerance test).

### Dual-curve statics

```cpp
static double parRate(maturity, frequency, env, discountKey, projectionKey);
static double annuity(maturity, frequency, env, discountKey);
```

- `parRate` fair fixed rate `K` s.t. `Σ fwd_proj_i·P_dis(t_i) = K·Σ dt·P_dis(t_i)`
  (floating PV projected off projection, discounted off discount; annuity off discount).
  The `1 − P_dis(T)` shortcut is valid **only** in the key-equal path.
- `annuity` is the discount-curve annuity `Σ τ·P_dis`.
- Single-arg overloads (`parRate(m,f,env)`, `parRate(m,f,curve)`, etc.) are preserved and
  delegate with equal keys.

### Phase-1 projection-convention caveat (honest boundary)

Phase-1 forwards are **pseudo-discount-factor ratios** `P_proj(t_{i-1})/P_proj(t_i) − 1`
with **no fixing lag, reset gap, or payment delay**. They are not convention-correct
against SWPM-grade term-structure setups. Convention-correct forwards are phase 2.

---

## 3. Work Breakdown

### P5a — Dual-curve pricing core + `InterestRateSwap::calculatePV` wart fix

- Add `CurveKeys` to `swap.hpp`. Thread onto `InterestRateSwap` (ctor gains optional
  trailing `CurveKeys`), `ScheduledLeg` (ctors/factories gain optional trailing
  `CurveKeys`), with `curveKeys()` accessors.
- `InterestRateSwap::npv` / `annuity` / dual-curve `parRate`/`annuity` statics dispatch on
  key equality as above.
- `ScheduledLeg::calculatePV` / `calculateCouponPV` and `ScheduledSwap::cashFlows`
  (`periodCouponCF`) read the **projection** curve for floating forwards and the
  **discount** curve for discounting; key-equal path unchanged.
- **Wart fix:** add `InterestRateSwap::calculatePV` override delegating to
  `InterestRateSwap::npv(env)`, so `Instrument::pv()` reaches the economic NPV. Update the
  wart comment at `tests/test_scenario.cpp:82-89`.
- Missing curve keys fail at pricing time with `std::out_of_range` naming the curve
  (already the behaviour of `MarketEnvironment::curve`).

### P5b — Dual-curve risk

- Derive `ScheduledSwap` from `Instrument`: `calculatePV = npv`, `maturity =
  max(payLeg last payTime, receiveLeg last payTime)` (max over **both** legs).
- `ScenarioEngine("USD.OIS")` and `ScenarioEngine("USD.3M")` against the same swap yield
  the two ladders with zero engine changes.

### P5c — Python bindings + scope doc

- `qfpy.cpp`: `py::class_<InterestRateSwap, Instrument>` and
  `py::class_<ScheduledSwap, Instrument>`; bind dual-curve ctors, curve-key accessors,
  dual-curve `parRate`/`annuity`.
- Scope documentation of the honest phase-1 boundary (exogenous curves, pseudo-forward
  convention, single-curve caps/swaptions/XVA).

---

## 4. Backward-Compatibility Constraints

- Default keys `{"default","default"}` ⇒ existing code path runs verbatim ⇒ bit-identical
  output for every current caller and binding.
- All existing constructors/overloads preserved; new `CurveKeys` params are trailing and
  defaulted.
- `ScheduledSwap` gains an `Instrument` base and a `pv()` but keeps `npv()`/`cashFlows()`;
  existing construction is unchanged.
- The `InterestRateSwap::calculatePV` change is a **deliberate behavioural fix** of a
  documented wart (no test pins the old value); called out loudly in the commit message.

---

## 5. Testing Gate

`cd build && cmake --build . --target all && ctest --output-on-failure` — all pre-existing
tests plus new cases must pass. New GoogleTest coverage:

1. **Key-equal bit-identity / ~1e-13 equivalence:** same pillars under two names, dual-path
   NPV == single-curve NPV to ~1e-13 relative.
2. **Wart fix:** `irs.pv(env) == irs.npv(env)` for both `Payer` and `Receiver`.
3. **Cash-flow invariance:** `ScheduledSwap::cashFlows` undiscounted flows invariant under
   an OIS-only bump, changed under a projection bump.
4. **Positive basis:** projection 25–30 bp above OIS moves payer NPV in the correct
   direction, hand-checked magnitude.
5. **Amortizing floating leg** priced under dual curves equals the replication form when
   keys collapse.
6. **Dual- vs single-curve par-rate spread.**
7. **DV01 additivity (P5b):** identical pillars under `USD.OIS`/`USD.3M`, swap keyed across
   both, `ScenarioEngine("USD.OIS").parallelDV01 + ScenarioEngine("USD.3M").parallelDV01 ≈
   single-curve parallel DV01` to O(h²) under Linear interpolation.
8. **Both swap families through `ScenarioEngine`** (C++ and Python).
9. **Python:** both swaps through the bound `ScenarioEngine`; basis-spread NPV/par-rate
   demo vs hand computation.

---

## 6. Honest Phase-1 Scope & Phase-2 Backlog (P5c deliverable)

Phase 1 ships dual-curve **pricing and risk given two exogenous curves**. The following
are deliberately **out of scope** and must not be mistaken for shipped capability:

1. **Exogenous curves only — no dual-curve bootstrapping.** Stripping a projection curve
   consistent with exogenous OIS discounting is phase 2. The supported construction path
   is the existing single-curve `bootstrap()` building the OIS curve from OIS quotes
   (legitimate, since OIS swaps project and discount on the same curve); a separate
   projection curve must be supplied by the caller via `MarketEnvironment::addCurve`.

2. **Projection convention.** Phase-1 forwards are pseudo-discount-factor ratios
   `P_proj(t_{i-1})/P_proj(t_i) − 1` with **no fixing lag, reset gap, or payment delay**.
   They are not convention-correct against SWPM-grade term-structure setups. Fixing
   conventions are phase 2.

3. **Caps/floors and swaptions remain single-curve** (`capfloor.cpp`, `swaption.cpp`).
   Dual-curve Black caplets need a projection-forward + OIS-annuity rewrite (phase 2).

4. **`CVACalculator`'s Hull-White exposure simulation stays single-curve.** Dual-curve
   XVA is a separate project.

**Roadmap-drift check:** nothing shipped in P2–P4 touched swap pricing or curve
consumption, so P5 is neither redundant nor blocked by earlier work.
