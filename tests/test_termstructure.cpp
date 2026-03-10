#include <gtest/gtest.h>
#include <qf/termstructure/yieldcurve.hpp>
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
