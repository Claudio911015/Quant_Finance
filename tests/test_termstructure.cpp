#include <gtest/gtest.h>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/termstructure/bootstrap.hpp>
#include <qf/instruments/swap.hpp>
#include <qf/math/interpolation.hpp>
#include <cmath>

using namespace qf::termstructure;
using namespace qf::math;

namespace {
    // Flat curve at 5% — simple to verify analytically
    YieldCurve flatCurve() {
        return YieldCurve({0.5, 1.0, 2.0, 5.0, 10.0},
                          {0.05, 0.05, 0.05, 0.05, 0.05},
                          InterpolationMethod::Linear);
    }

    // Upward-sloping curve
    YieldCurve slopedCurve() {
        return YieldCurve({0.5, 1.0, 2.0, 5.0, 10.0},
                          {0.03, 0.035, 0.04, 0.05, 0.06},
                          InterpolationMethod::CubicSpline);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Zero rates
// ═══════════════════════════════════════════════════════════════════════════

TEST(YieldCurve, FlatCurveZeroRate) {
    auto curve = flatCurve();
    EXPECT_NEAR(curve.zeroRate(1.0),  0.05, 1e-10);
    EXPECT_NEAR(curve.zeroRate(5.0),  0.05, 1e-10);
    EXPECT_NEAR(curve.zeroRate(10.0), 0.05, 1e-10);
}

TEST(YieldCurve, ZeroRateAtKnots) {
    auto curve = slopedCurve();
    EXPECT_NEAR(curve.zeroRate(0.5),  0.03,  1e-10);
    EXPECT_NEAR(curve.zeroRate(1.0),  0.035, 1e-10);
    EXPECT_NEAR(curve.zeroRate(10.0), 0.06,  1e-10);
}

TEST(YieldCurve, InvalidMaturityThrows) {
    auto curve = flatCurve();
    EXPECT_THROW(curve.zeroRate(0.0),  std::invalid_argument);
    EXPECT_THROW(curve.zeroRate(-1.0), std::invalid_argument);
}

// ═══════════════════════════════════════════════════════════════════════════
// Discount factors
// ═══════════════════════════════════════════════════════════════════════════

TEST(YieldCurve, FlatCurveDiscountFactor) {
    auto curve = flatCurve();
    // P(0,T) = exp(-0.05 * T)
    EXPECT_NEAR(curve.discountFactor(1.0),  std::exp(-0.05),      1e-10);
    EXPECT_NEAR(curve.discountFactor(2.0),  std::exp(-0.10),      1e-10);
    EXPECT_NEAR(curve.discountFactor(5.0),  std::exp(-0.25),      1e-10);
    EXPECT_NEAR(curve.discountFactor(10.0), std::exp(-0.50),      1e-10);
}

TEST(YieldCurve, DiscountFactorLessThanOne) {
    auto curve = slopedCurve();
    for (double T : {0.5, 1.0, 2.0, 5.0, 10.0})
        EXPECT_LT(curve.discountFactor(T), 1.0);
}

TEST(YieldCurve, DiscountFactorDecreasingInMaturity) {
    auto curve = slopedCurve();
    double prev = 1.0;
    for (double T : {0.5, 1.0, 2.0, 5.0, 10.0}) {
        double df = curve.discountFactor(T);
        EXPECT_LT(df, prev);
        prev = df;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Forward rates
// ═══════════════════════════════════════════════════════════════════════════

TEST(YieldCurve, FlatCurveForwardRateEqualsSpot) {
    // On a flat curve, all forward rates equal the spot rate
    auto curve = flatCurve();
    EXPECT_NEAR(curve.forwardRate(1.0, 2.0), 0.05, 1e-10);
    EXPECT_NEAR(curve.forwardRate(2.0, 5.0), 0.05, 1e-10);
}

TEST(YieldCurve, ForwardRateConsistencyWithDiscountFactors) {
    // P(0,T1) / P(0,T2) = exp(f(T1,T2) * (T2-T1))
    auto curve = slopedCurve();
    double T1 = 1.0, T2 = 3.0;
    double fwd  = curve.forwardRate(T1, T2);
    double df1  = curve.discountFactor(T1);
    double df2  = curve.discountFactor(T2);
    double expected = std::log(df1 / df2) / (T2 - T1);
    EXPECT_NEAR(fwd, expected, 1e-10);
}

TEST(YieldCurve, ForwardRateInvalidOrderThrows) {
    auto curve = flatCurve();
    EXPECT_THROW(curve.forwardRate(3.0, 1.0), std::invalid_argument);
    EXPECT_THROW(curve.forwardRate(2.0, 2.0), std::invalid_argument);
}

// ═══════════════════════════════════════════════════════════════════════════
// Bootstrap
// ═══════════════════════════════════════════════════════════════════════════

using Inst = qf::termstructure::BootstrapInstrument;

TEST(Bootstrap, DepositsRecoverZeroRates) {
    // Pure deposit curve: bootstrapped zero rates should match inputs
    std::vector<Inst> instruments = {
        {0.25, 0.04, Inst::Deposit, 0},
        {0.50, 0.042, Inst::Deposit, 0},
        {1.00, 0.045, Inst::Deposit, 0},
    };
    auto curve = bootstrap(instruments);
    EXPECT_NEAR(curve.zeroRate(0.25), 0.04, 1e-8);
    EXPECT_NEAR(curve.zeroRate(0.50), 0.042, 1e-8);
    EXPECT_NEAR(curve.zeroRate(1.00), 0.045, 1e-8);
}

TEST(Bootstrap, DiscountFactorsPositive) {
    std::vector<Inst> instruments = {
        {0.25, 0.04, Inst::Deposit, 0},
        {0.50, 0.042, Inst::Deposit, 0},
        {1.00, 0.045, Inst::Deposit, 0},
        {2.00, 0.048, Inst::Swap, 2.0},
        {5.00, 0.050, Inst::Swap, 2.0},
    };
    auto curve = bootstrap(instruments);
    for (double T : {0.25, 0.5, 1.0, 2.0, 5.0}) {
        EXPECT_GT(curve.discountFactor(T), 0.0);
        EXPECT_LT(curve.discountFactor(T), 1.0);
    }
}

TEST(Bootstrap, SwapParRatesRecovered) {
    // After bootstrapping, par swap rates computed from the curve
    // should match the input swap rates
    std::vector<Inst> instruments = {
        {0.50, 0.040, Inst::Deposit, 0},
        {1.00, 0.045, Inst::Deposit, 0},
        {2.00, 0.048, Inst::Swap, 2.0},
        {3.00, 0.050, Inst::Swap, 2.0},
        {5.00, 0.052, Inst::Swap, 2.0},
    };
    auto curve = bootstrap(instruments);

    for (const auto& inst : instruments) {
        if (inst.type == Inst::Swap) {
            double recovered = qf::instruments::InterestRateSwap::parRate(
                inst.maturity, inst.frequency, curve);
            EXPECT_NEAR(recovered, inst.rate, 5e-4)
                << "Par rate mismatch at T=" << inst.maturity;
        }
    }
}

TEST(Bootstrap, FlatInputGivesFlatCurve) {
    double r = 0.05;
    std::vector<Inst> instruments = {
        {0.50, r, Inst::Deposit, 0},
        {1.00, r, Inst::Deposit, 0},
        {2.00, r, Inst::Deposit, 0},
    };
    auto curve = bootstrap(instruments, InterpolationMethod::Linear);
    EXPECT_NEAR(curve.zeroRate(0.75), r, 1e-8);
    EXPECT_NEAR(curve.zeroRate(1.50), r, 1e-8);
}

TEST(Bootstrap, MonotonicallyDecreasingDiscountFactors) {
    std::vector<Inst> instruments = {
        {0.25, 0.040, Inst::Deposit, 0},
        {0.50, 0.042, Inst::Deposit, 0},
        {1.00, 0.045, Inst::Deposit, 0},
        {2.00, 0.048, Inst::Swap, 2.0},
        {5.00, 0.052, Inst::Swap, 2.0},
        {10.0, 0.055, Inst::Swap, 2.0},
    };
    auto curve = bootstrap(instruments);
    double prevDF = 1.0;
    for (double T : {0.25, 0.5, 1.0, 2.0, 5.0, 10.0}) {
        double df = curve.discountFactor(T);
        EXPECT_LT(df, prevDF);
        prevDF = df;
    }
}

TEST(Bootstrap, EmptyInstrumentsThrows) {
    std::vector<Inst> empty;
    EXPECT_THROW(bootstrap(empty), std::invalid_argument);
}

TEST(Bootstrap, UnsortedInstrumentsThrows) {
    std::vector<Inst> unsorted = {
        {1.00, 0.05, Inst::Deposit, 0},
        {0.50, 0.04, Inst::Deposit, 0},
    };
    EXPECT_THROW(bootstrap(unsorted), std::invalid_argument);
}

// ═══════════════════════════════════════════════════════════════════════════
// Pillar access + bump construction (P2a)
// ═══════════════════════════════════════════════════════════════════════════

TEST(YieldCurve, PillarRoundTrip) {
    std::vector<double> mats  = {0.5, 1.0, 2.0, 5.0, 10.0};
    std::vector<double> rates = {0.03, 0.035, 0.04, 0.05, 0.06};
    YieldCurve curve(mats, rates, InterpolationMethod::Linear);
    EXPECT_EQ(curve.maturities(), mats);
    EXPECT_EQ(curve.rates(), rates);
    EXPECT_EQ(curve.interpolationMethod(), InterpolationMethod::Linear);
}

TEST(YieldCurve, ParallelBumpShiftsZeroRateUniformly) {
    auto base = slopedCurve();                 // CubicSpline sloped curve
    auto up   = base.parallelBump(10.0);       // +10 bp = +0.001 in rate
    for (double T : {0.5, 1.0, 2.0, 5.0, 10.0}) {
        EXPECT_NEAR(up.zeroRate(T), base.zeroRate(T) + 0.001, 1e-12);
    }
    // Original curve is untouched (non-mutating).
    EXPECT_NEAR(base.zeroRate(5.0), 0.05, 1e-10);
}

TEST(YieldCurve, SinglePillarBumpIsLocalUnderLinear) {
    std::vector<double> mats  = {0.5, 1.0, 2.0, 5.0, 10.0};
    std::vector<double> rates = {0.03, 0.035, 0.04, 0.05, 0.06};
    YieldCurve base(mats, rates, InterpolationMethod::Linear);
    const std::size_t k = 3;                   // 5Y pillar
    auto bumped = base.bumped(k, 5.0);         // +5 bp at 5Y only

    // The bumped pillar moves by exactly 5 bp.
    EXPECT_NEAR(bumped.zeroRate(mats[k]), base.zeroRate(mats[k]) + 0.0005, 1e-12);
    // A far-away pillar (0.5Y) is untouched under Linear interpolation.
    EXPECT_NEAR(bumped.zeroRate(mats[0]), base.zeroRate(mats[0]), 1e-12);
    // The other pillars themselves are unchanged.
    EXPECT_NEAR(bumped.zeroRate(mats[1]), base.zeroRate(mats[1]), 1e-12);
}

TEST(YieldCurve, BumpedRejectsBadPillarIndex) {
    auto curve = flatCurve();
    EXPECT_THROW(curve.bumped(99, 1.0), std::out_of_range);
}
