# DVA/FVA on the CVA Exposure Engine — Design Spec

**Date:** 2026-07-07
**Project:** Quant_Finance (`~/Git/Quant_Finance`)
**Status:** Approved (P1 of the XVA roadmap — ship first)
**Scope:** Extend the existing `qf::xva::CVACalculator` to produce a full bilateral
valuation adjustment (CVA + DVA + FVA) from the same Hull-White Monte Carlo paths.

---

## 1. Context and Motivation

`CVACalculator::compute()` already simulates netting-set exposure under a Hull-White
short-rate model, rebuilds the conditional yield curve at each monitor date, prices the
residual swaps, and accumulates the Expected Positive Exposure (EPE). It then folds EPE
against the counterparty survival curve to produce unilateral CVA.

The expensive machinery (path simulation, conditional-curve rebuild, residual repricing)
therefore already exists. What is missing is bilateral completeness:

- **DVA (Debit Valuation Adjustment)** — the symmetric benefit from the firm's *own*
  default risk, driven by Expected Negative Exposure (ENE) against the firm's own
  survival curve. Today `CVAResult::TimeStep` stores only `epe`, so ENE is never recorded.
- **FVA (Funding Valuation Adjustment)** — the cost/benefit of funding the uncollateralised
  net expected exposure at a funding spread over the risk-free rate.

All three adjustments can be read off the *same* simulated paths at marginal compute cost,
which is why this is the best-ROI, independently-shippable item on the roadmap.

### Constraints

- **Backward compatible.** The existing 4-argument `CVACalculator` constructor, all existing
  `CVAResult`/`TimeStep` fields read by the 286 GoogleTest cases and by `qfxva`, and the
  existing `to_dataframe()` columns must keep working unchanged. DVA/FVA are *additive*:
  when neither is configured, results are byte-for-byte the previous CVA behaviour.
- **User-supplied data only.** DVA needs an own-credit `ICreditCurve` (same type CVA already
  uses); FVA needs a scalar funding spread. No new market-data feed is introduced.
- C++20, existing namespaces, three-file convention, CMake build preserved.

---

## 2. Chosen Approach

Keep the single-pass MC loop. Accumulate **ENE** alongside EPE inside the path loop
(`ene += max(-netValue, 0)`), then in the post-simulation assembly compute the three
adjustments from the exposure profile and the relevant survival curves.

Configuration is done through **setters** rather than new constructor overloads, so the
existing constructor and every existing test constructing a `CVACalculator` with 4 args
remain valid:

```cpp
CVACalculator calc(hw, cptyCredit, lgd, params);   // unchanged — CVA only
calc.setOwnCredit(ownCredit, ownLgd);              // opt in to DVA
calc.setFundingSpread(fundingSpread);              // opt in to FVA
auto r = calc.compute(ns, env);                    // r.cva, r.dva, r.fva, r.bcva
```

### Definitions (consistent with the existing undiscounted CVA convention)

The existing engine folds *undiscounted* EPE against survival increments; DVA/FVA follow
the same convention for internal consistency (discounting is a separate future concern).

Let `t_0 = 0`, monitor dates `t_1 < … < t_n`, `SP_c`/`SP_o` the counterparty/own survival
probabilities, `Δt_k = t_k − t_{k-1}`.

- **CVA** (unchanged): `Σ_k LGD_c · EPE(t_k) · [SP_c(t_{k-1}) − SP_c(t_k)]`
- **DVA**: `Σ_k LGD_o · ENE(t_k) · [SP_o(t_{k-1}) − SP_o(t_k)]`
- **FVA**: `Σ_k s_f · [EPE(t_k) − ENE(t_k)] · SP_c(t_k) · SP_o(t_k) · Δt_k`
  (funding cost on net expected exposure, earned only while both names survive;
  reduces to `s_f · Σ EPE · SP_c · Δt_k` when no own curve is configured).
- **BCVA** (bilateral CVA to the firm): `CVA − DVA`.

`EPE(t_k) = E[max(V_k, 0)]`, `ENE(t_k) = E[max(−V_k, 0)]`, both from the same path set.

---

## 3. Data Structures

`TimeStep` gains `ene`, `ownSurvProb`, `dvaContribution`, `fvaContribution`; existing
fields (`t`, `epe`, `survProb`, `contribution` = CVA contribution) keep their meaning.

`CVAResult` gains `dva`, `fva`, `bcva`; existing `cva` and `profile` unchanged.

`CVACalculator` gains private `const ICreditCurve* ownCredit_ = nullptr`,
`double ownLgd_ = 0.0`, `double fundingSpread_ = 0.0`, plus `setOwnCredit(curve, lgd)`
(validates `lgd ∈ [0,1]`) and `setFundingSpread(s)` (validates `s ≥ 0`).

---

## 4. Consumers

- `qfxva` bindings: expose `set_own_credit` / `set_funding_spread` (with `keep_alive`),
  new read-only fields on `TimeStep`/`CVAResult`, and extend `to_dataframe()` with
  `ene`, `dva_contribution`, `fva_contribution` columns.
- Flask UI: **out of scope** for this proposal.

---

## 5. Testing

Extend `tests/test_CVACalculator.cpp`:

- Deep OTM payer swap → `ENE > 0`, `DVA > 0` (symmetric to the existing receiver/CVA test).
- Own credit not configured → `dva == 0`, `bcva == cva` (backward compatibility).
- Funding spread configured on a positive-exposure book → `fva > 0`; `s_f = 0` → `fva == 0`.
- `bcva == cva − dva` identity.
- Validation: `setOwnCredit` with `lgd ∉ [0,1]` throws; `setFundingSpread(<0)` throws.

Regression gate: full `ctest` suite stays green.
