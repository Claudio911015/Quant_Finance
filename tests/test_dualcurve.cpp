#include <gtest/gtest.h>

#include <cmath>
#include <string>
#include <vector>

#include <qf/risk/scenario.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/interpolation.hpp>
#include <qf/instruments/swap.hpp>

using namespace qf::risk;
using qf::core::MarketEnvironment;
using qf::math::InterpolationMethod;
using qf::termstructure::YieldCurve;
using qf::instruments::InterestRateSwap;
using qf::instruments::ScheduledLeg;
using qf::instruments::ScheduledSwap;
using qf::instruments::SwapType;
using qf::instruments::CurveKeys;

namespace {

// Upward-sloping OIS curve, Linear interpolation (so single-pillar bumps stay local
// and DV01 additivity holds to O(h²)).
YieldCurve oisCurve() {
    return YieldCurve({0.5, 1.0, 2.0, 5.0, 10.0},
                      {0.030, 0.032, 0.035, 0.038, 0.040},
                      InterpolationMethod::Linear);
}

// Projection curve = OIS + a flat basis (bp), same pillars.
YieldCurve projCurve(double basisBp) {
    const double b = basisBp * 1e-4;
    return YieldCurve({0.5, 1.0, 2.0, 5.0, 10.0},
                      {0.030 + b, 0.032 + b, 0.035 + b, 0.038 + b, 0.040 + b},
                      InterpolationMethod::Linear);
}

// Environment carrying the same OIS data under "default", "USD.OIS", and (optionally)
// a projection curve under "USD.3M".
MarketEnvironment makeEnv(double projBasisBp) {
    MarketEnvironment env(oisCurve());        // "default"
    env.addCurve("USD.OIS", oisCurve());
    env.addCurve("USD.3M", projCurve(projBasisBp));
    return env;
}

} // namespace

// ─── P5a: key-equal path equivalence (bit-identical single-curve) ─────────────

TEST(DualCurve, KeyEqualMatchesSingleCurveToMachinePrecision) {
    // Identical pillar data under two distinct names must reproduce the single-curve
    // NPV, because the explicit dual-curve sum telescopes to the replication identity.
    MarketEnvironment env(oisCurve());
    env.addCurve("USD.OIS", oisCurve());
    env.addCurve("USD.3M", oisCurve());   // SAME data as OIS ⇒ zero basis

    InterestRateSwap single(1'000'000, 0.035, 5.0, 2.0, SwapType::Payer);
    InterestRateSwap dual  (1'000'000, 0.035, 5.0, 2.0, SwapType::Payer,
                            CurveKeys{"USD.OIS", "USD.3M"});

    EXPECT_NEAR(dual.npv(env), single.npv(env),
                std::abs(single.npv(env)) * 1e-12 + 1e-8);
}

TEST(DualCurve, DefaultKeysReplicateReplicationIdentity) {
    // A default-keyed swap equals floatLeg − fixedLeg with floatLeg = N·(1−P(0,T))
    // and fixedLeg = N·K·annuity (the legacy replication decomposition).
    YieldCurve c = oisCurve();
    MarketEnvironment env(c);
    const double N = 1'000'000, K = 0.035, T = 5.0;
    InterestRateSwap irs(N, K, T, 2.0, SwapType::Payer);

    const double floatLeg = N * (1.0 - c.discountFactor(T));
    const double fixedLeg = N * K * irs.annuity(env);
    EXPECT_NEAR(irs.npv(env), floatLeg - fixedLeg, 1e-6);
}

TEST(DualCurve, KeyEqualMatchesSingleCurveForFractionalMaturities) {
    // Regression: the dual floating loop once used round(mat·freq) periods while the fixed
    // annuity / par rate truncated, so on a NON-period-aligned maturity the dual NPV
    // diverged from the single-curve NPV (~44% at mat=4.75) instead of matching to ~1e-13.
    // The projection grid now ends exactly at `mat`, so equivalence holds for any maturity.
    MarketEnvironment env(oisCurve());
    env.addCurve("USD.OIS", oisCurve());
    env.addCurve("USD.3M", oisCurve());   // identical data ⇒ zero basis

    for (double mat : {0.4, 4.6, 4.75, 7.3}) {
        InterestRateSwap single(1'000'000, 0.035, mat, 2.0, SwapType::Payer);
        InterestRateSwap dual  (1'000'000, 0.035, mat, 2.0, SwapType::Payer,
                                CurveKeys{"USD.OIS", "USD.3M"});
        EXPECT_NEAR(dual.npv(env), single.npv(env),
                    std::abs(single.npv(env)) * 1e-11 + 1e-6)
            << "mat=" << mat;
    }
}

TEST(DualCurve, DualParRateZeroesDualNpvForFractionalMaturity) {
    // A swap struck at the dual par rate must have ~zero dual NPV — even off the period
    // grid. This pins the npv/parRate period-count consistency (they share one grid and
    // one discount annuity).
    MarketEnvironment env = makeEnv(25.0);   // real 25 bp basis, keys differ
    const CurveKeys keys{"USD.OIS", "USD.3M"};
    for (double mat : {4.6, 4.75, 7.3}) {
        const double par = InterestRateSwap::parRate(mat, 2.0, env, "USD.OIS", "USD.3M");
        InterestRateSwap atPar(1'000'000, par, mat, 2.0, SwapType::Payer, keys);
        // Scale tolerance by a representative leg magnitude, not the (near-zero) NPV.
        const double annuityScale = 1'000'000 * InterestRateSwap::annuity(mat, 2.0, env, "USD.OIS");
        EXPECT_NEAR(atPar.npv(env), 0.0, annuityScale * 1e-10) << "mat=" << mat;
    }
}

// ─── P5a: InterestRateSwap::calculatePV wart fix ──────────────────────────────

TEST(DualCurve, InstrumentPvEqualsEconomicNpv_Payer) {
    MarketEnvironment env(oisCurve());
    InterestRateSwap irs(1'000'000, 0.035, 5.0, 2.0, SwapType::Payer);
    EXPECT_DOUBLE_EQ(irs.pv(env), irs.npv(env));
}

TEST(DualCurve, InstrumentPvEqualsEconomicNpv_Receiver) {
    MarketEnvironment env(oisCurve());
    InterestRateSwap irs(1'000'000, 0.035, 5.0, 2.0, SwapType::Receiver);
    EXPECT_DOUBLE_EQ(irs.pv(env), irs.npv(env));
    // Receiver is the exact negative of the payer.
    InterestRateSwap payer(1'000'000, 0.035, 5.0, 2.0, SwapType::Payer);
    EXPECT_DOUBLE_EQ(irs.npv(env), -payer.npv(env));
}

// ─── P5a: positive basis moves payer NPV in the right direction ───────────────

TEST(DualCurve, PositiveBasisRaisesPayerNpv) {
    MarketEnvironment env = makeEnv(30.0);   // projection 30 bp above OIS

    InterestRateSwap payerSingle(1'000'000, 0.035, 5.0, 2.0, SwapType::Payer);
    InterestRateSwap payerDual  (1'000'000, 0.035, 5.0, 2.0, SwapType::Payer,
                                 CurveKeys{"USD.OIS", "USD.3M"});

    const double single = payerSingle.npv(env);          // OIS projects+discounts
    const double dual   = payerDual.npv(env);            // 3M projects, OIS discounts

    // A payer receives floating: higher projected forwards ⇒ higher NPV.
    EXPECT_GT(dual, single);

    // Hand-checked magnitude: raising every forward by ~30 bp lifts the floating PV by
    // ≈ N · 0.0030 · annuity(OIS). Match to within 5% (forwards are on the 3M discount
    // ratios, annuity on OIS, so this is an approximation).
    const double approx = 1'000'000 * 0.0030 * payerDual.annuity(env);
    EXPECT_NEAR(dual - single, approx, approx * 0.05);
}

TEST(DualCurve, DualParRateExceedsSingleWhenProjectionAboveOis) {
    MarketEnvironment env = makeEnv(25.0);
    const double single = InterestRateSwap::parRate(5.0, 2.0, env.curve("USD.OIS"));
    const double dual   = InterestRateSwap::parRate(5.0, 2.0, env, "USD.OIS", "USD.3M");
    EXPECT_GT(dual, single);
    // Par rate spread ≈ the projection basis (25 bp) to first order.
    EXPECT_NEAR(dual - single, 25e-4, 25e-4 * 0.10);
}

TEST(DualCurve, DualParRateReducesToSingleWhenKeysEqual) {
    MarketEnvironment env = makeEnv(0.0);  // 3M == OIS data
    const double viaEqualKeys = InterestRateSwap::parRate(5.0, 2.0, env, "USD.OIS", "USD.3M");
    const double single       = InterestRateSwap::parRate(5.0, 2.0, env.curve("USD.OIS"));
    EXPECT_NEAR(viaEqualKeys, single, std::abs(single) * 1e-12 + 1e-12);
}

// ─── P5a: ScheduledSwap dual-curve cash-flow invariance ───────────────────────

namespace {
// Dual-curve scheduled swap: pay fixed (default keys), receive floating keyed to 3M
// projection + OIS discount. Semi-annual, 3y.
ScheduledSwap makeScheduledSwap() {
    std::vector<double> times{0.5, 1.0, 1.5, 2.0, 2.5, 3.0};
    CurveKeys floatKeys{"USD.OIS", "USD.3M"};
    CurveKeys fixedKeys{"USD.OIS", "USD.OIS"};
    ScheduledLeg fixed = ScheduledLeg::makeFixed(1'000'000, 0.035, times, fixedKeys);
    ScheduledLeg floating = ScheduledLeg::makeFloating(1'000'000, 0.0, times, floatKeys);
    return ScheduledSwap(std::move(fixed), std::move(floating));  // pay fixed, receive float
}
}  // namespace

TEST(DualCurve, CashFlowsInvariantUnderOisBumpChangeUnderProjectionBump) {
    MarketEnvironment base = makeEnv(20.0);
    ScheduledSwap swap = makeScheduledSwap();
    auto flows0 = swap.cashFlows(base);

    // Bump only the OIS (discount) curve — undiscounted flows must not move.
    MarketEnvironment oisBumped = base;
    oisBumped.addCurve("USD.OIS", base.curve("USD.OIS").parallelBump(50.0));
    auto flowsOis = swap.cashFlows(oisBumped);
    ASSERT_EQ(flows0.size(), flowsOis.size());
    for (std::size_t i = 0; i < flows0.size(); ++i) {
        EXPECT_DOUBLE_EQ(flows0[i].first, flowsOis[i].first);
        EXPECT_NEAR(flows0[i].second, flowsOis[i].second, std::abs(flows0[i].second) * 1e-12 + 1e-9);
    }

    // Bump only the projection curve — floating flows must move.
    MarketEnvironment projBumped = base;
    projBumped.addCurve("USD.3M", base.curve("USD.3M").parallelBump(50.0));
    auto flowsProj = swap.cashFlows(projBumped);
    bool anyChanged = false;
    for (std::size_t i = 0; i < flows0.size(); ++i)
        if (std::abs(flows0[i].second - flowsProj[i].second) > 1.0) anyChanged = true;
    EXPECT_TRUE(anyChanged);
}

TEST(DualCurve, ScheduledSwapMaturityIsMaxOverBothLegs) {
    // Legs with different final dates ⇒ maturity is the later one.
    ScheduledLeg shortFixed = ScheduledLeg::makeFixed(1'000'000, 0.03, {1.0, 2.0});
    ScheduledLeg longFloat  = ScheduledLeg::makeFloating(1'000'000, 0.0, {1.0, 2.0, 3.0, 4.0});
    ScheduledSwap swap(std::move(shortFixed), std::move(longFloat));
    EXPECT_DOUBLE_EQ(swap.maturity(), 4.0);
}

// ─── P5a: amortizing floating leg dual-curve equals replication when keys collapse ─

TEST(DualCurve, AmortizingFloatingDualEqualsReplicationWhenDataEqual) {
    MarketEnvironment env(oisCurve());
    env.addCurve("USD.OIS", oisCurve());
    env.addCurve("USD.3M", oisCurve());   // identical data

    std::vector<qf::instruments::PeriodSpec> sched{
        {0.5, 0.5, 1'000'000}, {1.0, 0.5, 800'000},
        {1.5, 0.5, 600'000},   {2.0, 0.5, 400'000}};

    ScheduledLeg legSingle(0.0, /*paysFixed=*/false, 0.0015, sched);
    ScheduledLeg legDual  (0.0, /*paysFixed=*/false, 0.0015, sched,
                           CurveKeys{"USD.OIS", "USD.3M"});

    EXPECT_NEAR(legDual.calculatePV(env), legSingle.calculatePV(env),
                std::abs(legSingle.calculatePV(env)) * 1e-11 + 1e-6);
}

// ─── P5b: dual-curve risk via the unchanged ScenarioEngine ────────────────────

TEST(DualCurve, InterestRateSwapFlowsThroughScenarioEngine) {
    MarketEnvironment env = makeEnv(25.0);
    InterestRateSwap irs(1'000'000, 0.035, 5.0, 2.0, SwapType::Payer,
                         CurveKeys{"USD.OIS", "USD.3M"});
    ScenarioEngine oisEngine("USD.OIS");
    ScenarioEngine projEngine("USD.3M");
    const double oisDV01  = oisEngine.parallelDV01(irs, env);
    const double projDV01 = projEngine.parallelDV01(irs, env);
    // Both legs carry real risk, so neither DV01 is zero.
    EXPECT_GT(std::abs(oisDV01), 1.0);
    EXPECT_GT(std::abs(projDV01), 1.0);
}

TEST(DualCurve, PerCurveDV01sSumToSingleCurveDV01) {
    // Additivity construction (per review): identical pillar data under two names,
    // swap keyed across both; the two per-curve parallel DV01s must sum to the single-
    // curve parallel DV01 to O(h²) under Linear interpolation.
    MarketEnvironment env(oisCurve());     // "default"
    env.addCurve("USD.OIS", oisCurve());
    env.addCurve("USD.3M", oisCurve());    // SAME data ⇒ clean additivity

    InterestRateSwap dual(1'000'000, 0.035, 7.0, 2.0, SwapType::Payer,
                          CurveKeys{"USD.OIS", "USD.3M"});
    InterestRateSwap single(1'000'000, 0.035, 7.0, 2.0, SwapType::Payer);  // default keys

    const double oisDV01  = ScenarioEngine("USD.OIS").parallelDV01(dual, env);
    const double projDV01 = ScenarioEngine("USD.3M").parallelDV01(dual, env);
    const double singleDV01 = ScenarioEngine("default").parallelDV01(single, env);

    EXPECT_NEAR(oisDV01 + projDV01, singleDV01, std::abs(singleDV01) * 1e-4);
}

TEST(DualCurve, ScheduledSwapFlowsThroughScenarioEngine) {
    MarketEnvironment env = makeEnv(20.0);
    ScheduledSwap swap = makeScheduledSwap();
    const double projDV01 = ScenarioEngine("USD.3M").parallelDV01(swap, env);
    const double oisDV01  = ScenarioEngine("USD.OIS").parallelDV01(swap, env);
    EXPECT_GT(std::abs(projDV01), 1.0);
    EXPECT_GT(std::abs(oisDV01), 1.0);
}

// ─── Missing curve key fails loudly at pricing time ───────────────────────────

TEST(DualCurve, MissingProjectionKeyThrows) {
    MarketEnvironment env(oisCurve());   // only "default"
    InterestRateSwap irs(1'000'000, 0.035, 5.0, 2.0, SwapType::Payer,
                         CurveKeys{"USD.OIS", "USD.3M"});
    EXPECT_THROW(irs.npv(env), std::out_of_range);
}
