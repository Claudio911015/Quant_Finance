#include <gtest/gtest.h>
#include <qf/xva/credit_curve.hpp>
#include <cmath>

using namespace qf::xva;

TEST(FlatHazardRate, SurvivalAtZeroIsOne) {
    FlatHazardRate cr(0.02);
    EXPECT_NEAR(cr.survivalProbability(0.0), 1.0, 1e-12);
}

TEST(FlatHazardRate, SurvivalDecaysExponentially) {
    double lambda = 0.05;
    FlatHazardRate cr(lambda);
    for (double t : {1.0, 2.0, 5.0, 10.0}) {
        EXPECT_NEAR(cr.survivalProbability(t), std::exp(-lambda * t), 1e-12);
    }
}

TEST(FlatHazardRate, ZeroLambdaAlwaysOne) {
    FlatHazardRate cr(0.0);
    for (double t : {0.0, 1.0, 10.0})
        EXPECT_NEAR(cr.survivalProbability(t), 1.0, 1e-12);
}

TEST(FlatHazardRate, NegativeLambdaThrows) {
    EXPECT_THROW(FlatHazardRate(-0.01), std::invalid_argument);
}

TEST(FlatHazardRate, NegativeTimeThrows) {
    FlatHazardRate cr(0.02);
    EXPECT_THROW(cr.survivalProbability(-1.0), std::invalid_argument);
}

#include <qf/xva/netting_set.hpp>
#include <qf/termstructure/yieldcurve.hpp>

using namespace qf::instruments;
using namespace qf::termstructure;

TEST(NettingSet, EmptySetNetValueIsZero) {
    qf::xva::NettingSet ns;
    YieldCurve curve({0.5,1,2,5,10}, {0.04,0.04,0.04,0.04,0.04});
    qf::core::MarketEnvironment env(curve);
    EXPECT_NEAR(ns.netValue(env, 0.0), 0.0, 1e-12);
}

TEST(NettingSet, MaturedSwapSkipped) {
    qf::xva::NettingSet ns;
    ns.add(1e6, 0.05, 2.0, 1.0, SwapType::Payer);
    YieldCurve curve({0.5,1,2,5,10}, {0.04,0.04,0.04,0.04,0.04});
    qf::core::MarketEnvironment env(curve);
    // At t=3 the swap matured at T=2, so net value must be 0
    EXPECT_NEAR(ns.netValue(env, 3.0), 0.0, 1e-12);
}

TEST(NettingSet, PayerReceiverNetToZero) {
    // Identical payer + receiver same params -> net ~= 0
    qf::xva::NettingSet ns;
    ns.add(1e6, 0.04, 5.0, 1.0, SwapType::Payer);
    ns.add(1e6, 0.04, 5.0, 1.0, SwapType::Receiver);
    YieldCurve curve({0.5,1,2,5,10}, {0.04,0.04,0.04,0.04,0.04});
    qf::core::MarketEnvironment env(curve);
    EXPECT_NEAR(ns.netValue(env, 0.0), 0.0, 1e-6);
}

TEST(NettingSet, InvalidNotionalThrows) {
    qf::xva::NettingSet ns;
    EXPECT_THROW(ns.add(-1e6, 0.05, 5.0, 1.0, SwapType::Payer), std::invalid_argument);
}

TEST(NettingSet, InvalidMaturityThrows) {
    qf::xva::NettingSet ns;
    EXPECT_THROW(ns.add(1e6, 0.05, -1.0, 1.0, SwapType::Payer), std::invalid_argument);
}

#include <qf/xva/cva_calculator.hpp>
#include <qf/models/hullwhite.hpp>
#include <qf/models/vasicek.hpp>

// ── Shared helpers ──────────────────────────────────────────────────────────

static qf::termstructure::YieldCurve flatCurve(double r) {
    return qf::termstructure::YieldCurve(
        {0.5, 1.0, 2.0, 5.0, 10.0}, {r, r, r, r, r});
}

static std::vector<double> quarterlyDates(double maturity) {
    std::vector<double> d;
    for (double t = 0.25; t <= maturity + 1e-9; t += 0.25)
        d.push_back(t);
    return d;
}

// ── Constructor validation ──────────────────────────────────────────────────

TEST(CVACalculator, UnsortedDatesThrows) {
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.01, curve);
    qf::xva::FlatHazardRate credit(0.02);
    qf::xva::SimParams params{100, {5.0, 1.0, 2.0}, 42u}; // unsorted
    EXPECT_THROW(qf::xva::CVACalculator(hw, credit, 0.6, params), std::invalid_argument);
}

TEST(CVACalculator, NonPositiveDateThrows) {
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.01, curve);
    qf::xva::FlatHazardRate credit(0.02);
    qf::xva::SimParams params{100, {-1.0, 1.0, 2.0}, 42u}; // negative first date
    EXPECT_THROW(qf::xva::CVACalculator(hw, credit, 0.6, params), std::invalid_argument);
}

// ── TEST 1: Zero LGD → CVA == 0 ────────────────────────────────────────────

TEST(CVACalculator, ZeroLGDGivesZeroCVA) {
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.01, curve);
    qf::xva::FlatHazardRate credit(0.02);
    qf::xva::SimParams params{1000, quarterlyDates(5.0), 42u};
    qf::xva::CVACalculator calc(hw, credit, /*lgd=*/0.0, params);

    qf::xva::NettingSet ns;
    ns.add(1e6, 0.05, 5.0, 1.0, qf::instruments::SwapType::Payer);

    qf::core::MarketEnvironment env(curve);
    auto result = calc.compute(ns, env);
    EXPECT_NEAR(result.cva, 0.0, 1e-10);
}

// ── TEST 2: Deep ITM receiver swap → CVA > 0 ───────────────────────────────

TEST(CVACalculator, DeepITMReceiverSwapPositiveCVA) {
    // Receiver paying 4% float, receiving 10% fixed on a 4% flat curve → deeply ITM
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.005, curve); // low vol for stable EPE
    qf::xva::FlatHazardRate credit(0.02);
    qf::xva::SimParams params{5000, quarterlyDates(5.0), 42u};
    qf::xva::CVACalculator calc(hw, credit, /*lgd=*/0.6, params);

    qf::xva::NettingSet ns;
    ns.add(1e6, 0.10, 5.0, 1.0, qf::instruments::SwapType::Receiver);

    qf::core::MarketEnvironment env(curve);
    auto result = calc.compute(ns, env);

    EXPECT_GT(result.cva, 0.0);
    for (const auto& step : result.profile)
        EXPECT_GE(step.contribution, -1e-8);
    EXPECT_GT(result.cva, 3000.0);
    EXPECT_LT(result.cva, 50000.0);
}

// ── TEST 3: Netting — payer + receiver same params → CVA ≈ 0 ───────────────

TEST(CVACalculator, NettingReducesExposureToNearZero) {
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.01, curve);
    qf::xva::FlatHazardRate credit(0.02);
    qf::xva::SimParams params{2000, quarterlyDates(5.0), 42u};
    qf::xva::CVACalculator calc(hw, credit, /*lgd=*/0.6, params);

    qf::xva::NettingSet ns;
    ns.add(1e6, 0.05, 5.0, 1.0, qf::instruments::SwapType::Payer);
    ns.add(1e6, 0.05, 5.0, 1.0, qf::instruments::SwapType::Receiver);

    qf::core::MarketEnvironment env(curve);
    auto result = calc.compute(ns, env);

    EXPECT_NEAR(result.cva, 0.0, 1e-6); // payer+receiver cancel exactly at every path
}

// ── Bilateral XVA: DVA / FVA (P1) ──────────────────────────────────────────

// Own credit not configured → DVA == 0 and BCVA == CVA (backward compatibility).
TEST(CVACalculator, NoOwnCreditGivesZeroDVAAndBCVAEqualsCVA) {
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.005, curve);
    qf::xva::FlatHazardRate credit(0.02);
    qf::xva::SimParams params{2000, quarterlyDates(5.0), 42u};
    qf::xva::CVACalculator calc(hw, credit, 0.6, params);

    qf::xva::NettingSet ns;
    ns.add(1e6, 0.10, 5.0, 1.0, qf::instruments::SwapType::Receiver);

    qf::core::MarketEnvironment env(curve);
    auto r = calc.compute(ns, env);

    EXPECT_NEAR(r.dva, 0.0, 1e-12);
    EXPECT_NEAR(r.fva, 0.0, 1e-12);
    EXPECT_NEAR(r.bcva, r.cva, 1e-12);
    for (const auto& s : r.profile)
        EXPECT_NEAR(s.ownSurvProb, 1.0, 1e-12);
}

// Deep OTM payer swap → negative exposure → ENE > 0 → DVA > 0.
// Symmetric to DeepITMReceiverSwapPositiveCVA (which drives CVA via EPE).
TEST(CVACalculator, DeepOTMPayerSwapPositiveDVA) {
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.005, curve);
    qf::xva::FlatHazardRate credit(0.02);      // counterparty
    qf::xva::FlatHazardRate ownCredit(0.02);   // own
    qf::xva::SimParams params{5000, quarterlyDates(5.0), 42u};
    qf::xva::CVACalculator calc(hw, credit, 0.6, params);
    calc.setOwnCredit(ownCredit, 0.6);

    // Payer paying 10% fixed, receiving 4% float on a 4% curve → deeply out of money
    qf::xva::NettingSet ns;
    ns.add(1e6, 0.10, 5.0, 1.0, qf::instruments::SwapType::Payer);

    qf::core::MarketEnvironment env(curve);
    auto r = calc.compute(ns, env);

    EXPECT_GT(r.dva, 0.0);
    EXPECT_LT(r.cva, 0.1 * r.dva);             // negative-exposure book → ENE dominates
    EXPECT_NEAR(r.bcva, r.cva - r.dva, 1e-9);  // identity
    EXPECT_LT(r.bcva, 0.0);                     // DVA dominates → benefit to firm
    for (const auto& s : r.profile) {
        EXPECT_GE(s.ene, 0.0);
        EXPECT_GE(s.dvaContribution, -1e-8);
    }
    EXPECT_GT(r.dva, 3000.0);
    EXPECT_LT(r.dva, 50000.0);
}

// Symmetric book: DVA of a payer ≈ CVA of the mirror receiver (same magnitudes).
TEST(CVACalculator, DVAOfPayerMatchesCVAOfReceiver) {
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.005, curve);
    qf::xva::FlatHazardRate credit(0.02);
    qf::xva::SimParams params{5000, quarterlyDates(5.0), 42u};

    // CVA of the ITM receiver
    qf::xva::CVACalculator cvaCalc(hw, credit, 0.6, params);
    qf::xva::NettingSet nsRecv;
    nsRecv.add(1e6, 0.10, 5.0, 1.0, qf::instruments::SwapType::Receiver);
    qf::core::MarketEnvironment env(curve);
    double cvaRecv = cvaCalc.compute(nsRecv, env).cva;

    // DVA of the mirror payer (own credit == that same counterparty curve)
    qf::xva::CVACalculator dvaCalc(hw, credit, 0.6, params);
    dvaCalc.setOwnCredit(credit, 0.6);
    qf::xva::NettingSet nsPay;
    nsPay.add(1e6, 0.10, 5.0, 1.0, qf::instruments::SwapType::Payer);
    double dvaPay = dvaCalc.compute(nsPay, env).dva;

    EXPECT_NEAR(dvaPay, cvaRecv, 0.05 * cvaRecv); // within 5%
}

// Funding spread on a positive-exposure book → FVA > 0; zero spread → FVA == 0.
TEST(CVACalculator, FundingSpreadDrivesPositiveFVA) {
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.005, curve);
    qf::xva::FlatHazardRate credit(0.02);
    qf::xva::SimParams params{2000, quarterlyDates(5.0), 42u};

    qf::xva::NettingSet ns;
    ns.add(1e6, 0.10, 5.0, 1.0, qf::instruments::SwapType::Receiver); // positive exposure
    qf::core::MarketEnvironment env(curve);

    qf::xva::CVACalculator noFva(hw, credit, 0.6, params);
    EXPECT_NEAR(noFva.compute(ns, env).fva, 0.0, 1e-12);

    qf::xva::CVACalculator withFva(hw, credit, 0.6, params);
    withFva.setFundingSpread(0.01); // 100 bps
    auto r = withFva.compute(ns, env);
    EXPECT_GT(r.fva, 0.0); // net positive expected exposure → net funding cost
    // FVA scales linearly with the funding spread (same paths, same seed).
    qf::xva::CVACalculator withFva2(hw, credit, 0.6, params);
    withFva2.setFundingSpread(0.02); // double the spread
    EXPECT_NEAR(withFva2.compute(ns, env).fva, 2.0 * r.fva, 1e-6 * r.fva);
}

// Validation: own LGD out of range and negative funding spread throw.
TEST(CVACalculator, BilateralConfigValidation) {
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.005, curve);
    qf::xva::FlatHazardRate credit(0.02);
    qf::xva::SimParams params{100, quarterlyDates(2.0), 42u};
    qf::xva::CVACalculator calc(hw, credit, 0.6, params);

    EXPECT_THROW(calc.setOwnCredit(credit, -0.1), std::invalid_argument);
    EXPECT_THROW(calc.setOwnCredit(credit, 1.5), std::invalid_argument);
    EXPECT_THROW(calc.setFundingSpread(-0.001), std::invalid_argument);
}

TEST(Vasicek, ConditionalBondPricePositive) {
    qf::models::Vasicek v(0.1, 0.05, 0.01, 0.04);
    double P = v.conditionalBondPrice(1.0, 5.0, 0.04);
    EXPECT_GT(P, 0.0);
    EXPECT_LT(P, 1.0);
}

TEST(Vasicek, ConditionalBondPriceInvalidThrows) {
    qf::models::Vasicek v(0.1, 0.05, 0.01, 0.04);
    EXPECT_THROW(v.conditionalBondPrice(5.0, 3.0, 0.04), std::invalid_argument);
}
