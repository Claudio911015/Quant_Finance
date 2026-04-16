#include <gtest/gtest.h>
#include <qf/models/vasicek.hpp>
#include <qf/models/hullwhite.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/interpolation.hpp>
#include <cmath>

using namespace qf::models;
using namespace qf::termstructure;
using namespace qf::math;

// ═══════════════════════════════════════════════════════════════════════════
// Vasicek Model
// ═══════════════════════════════════════════════════════════════════════════

TEST(Vasicek, BondPricePositiveAndLessThanOne) {
    Vasicek model(0.5, 0.05, 0.01, 0.03);
    for (double T : {0.5, 1.0, 2.0, 5.0, 10.0}) {
        double P = model.bondPrice(T);
        EXPECT_GT(P, 0.0);
        EXPECT_LT(P, 1.0);
    }
}

TEST(Vasicek, BondPriceDecreasingInMaturity) {
    Vasicek model(0.5, 0.05, 0.01, 0.03);
    double prev = 1.0;
    for (double T : {0.5, 1.0, 2.0, 5.0, 10.0}) {
        double P = model.bondPrice(T);
        EXPECT_LT(P, prev);
        prev = P;
    }
}

TEST(Vasicek, ZeroRateConvergesToLongRunMean) {
    // For large T, Vasicek zero rate → b - sigma^2/(2*a^2)
    double a = 0.5, b = 0.05, sigma = 0.01, r0 = 0.03;
    Vasicek model(a, b, sigma, r0);
    double longRate = b - sigma * sigma / (2.0 * a * a);
    double rateAtT50 = model.zeroRate(50.0);
    EXPECT_NEAR(rateAtT50, longRate, 1e-3);
}

TEST(Vasicek, ZeroRateConsistentWithBondPrice) {
    Vasicek model(0.5, 0.05, 0.01, 0.03);
    for (double T : {1.0, 5.0, 10.0}) {
        double P = model.bondPrice(T);
        double r = model.zeroRate(T);
        EXPECT_NEAR(P, std::exp(-r * T), 1e-12);
    }
}

TEST(Vasicek, AnalyticalBondPriceKnownValue) {
    // Manual computation: a=1, b=0.05, sigma=0.02, r0=0.05, T=1
    // B(1) = (1-exp(-1))/1 = 0.6321206
    // A(1) = exp((B-1)(a^2*b - sigma^2/2)/a^2 - sigma^2*B^2/(4a))
    double a = 1.0, b = 0.05, sig = 0.02, r0 = 0.05;
    double T = 1.0;
    Vasicek model(a, b, sig, r0);

    double B = (1.0 - std::exp(-a * T)) / a;
    double A = std::exp((B - T) * (a*a*b - 0.5*sig*sig)/(a*a) - sig*sig*B*B/(4.0*a));
    double expected = A * std::exp(-B * r0);

    EXPECT_NEAR(model.bondPrice(T), expected, 1e-12);
}

TEST(Vasicek, SimulatePathLength) {
    Vasicek model(0.5, 0.05, 0.01, 0.03);
    auto path = model.simulate(1.0, 100, 42);
    EXPECT_EQ(path.size(), 101u);
    EXPECT_DOUBLE_EQ(path[0], 0.03);
}

TEST(Vasicek, SimulatePathMeanReverts) {
    // Over many paths, the average terminal rate should approach b
    double a = 2.0, b = 0.05, sigma = 0.01, r0 = 0.10;
    Vasicek model(a, b, sigma, r0);

    double sum = 0.0;
    int nPaths = 10000;
    for (int i = 0; i < nPaths; ++i) {
        auto path = model.simulate(5.0, 500, i);
        sum += path.back();
    }
    double avgTerminal = sum / nPaths;
    // E[r(T)] = b + (r0-b)*exp(-a*T) = 0.05 + 0.05*exp(-10) ≈ 0.05
    double expected = b + (r0 - b) * std::exp(-a * 5.0);
    EXPECT_NEAR(avgTerminal, expected, 0.005);
}

TEST(Vasicek, InvalidParamsThrow) {
    EXPECT_THROW(Vasicek(0.0, 0.05, 0.01, 0.03), std::invalid_argument);   // a=0
    EXPECT_THROW(Vasicek(-1.0, 0.05, 0.01, 0.03), std::invalid_argument);  // a<0
    EXPECT_THROW(Vasicek(0.5, 0.05, 0.0, 0.03), std::invalid_argument);    // sigma=0
}

// ═══════════════════════════════════════════════════════════════════════════
// Hull-White Model
// ═══════════════════════════════════════════════════════════════════════════

namespace {
    YieldCurve testCurve() {
        return YieldCurve({0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0},
                          {0.03, 0.035, 0.04, 0.045, 0.05, 0.055, 0.058},
                          InterpolationMethod::CubicSpline);
    }
}

TEST(HullWhite, ExactlyMatchesMarketCurve) {
    auto curve = testCurve();
    HullWhite hw(0.1, 0.015, curve);
    for (double T : {0.5, 1.0, 2.0, 5.0, 10.0, 20.0}) {
        EXPECT_NEAR(hw.bondPrice(T), curve.discountFactor(T), 1e-12);
        EXPECT_NEAR(hw.zeroRate(T), curve.zeroRate(T), 1e-12);
    }
}

TEST(HullWhite, BondPriceDecreasing) {
    auto curve = testCurve();
    HullWhite hw(0.1, 0.015, curve);
    double prev = 1.0;
    for (double T : {0.5, 1.0, 2.0, 5.0, 10.0, 20.0}) {
        double P = hw.bondPrice(T);
        EXPECT_LT(P, prev);
        prev = P;
    }
}

TEST(HullWhite, InvalidParamsThrow) {
    auto curve = testCurve();
    EXPECT_THROW(HullWhite(0.0, 0.015, curve), std::invalid_argument);
    EXPECT_THROW(HullWhite(0.1, 0.0, curve), std::invalid_argument);
}

// ═══════════════════════════════════════════════════════════════════════════
// HullWhite::conditionalBondPrice
// ═══════════════════════════════════════════════════════════════════════════

TEST(HullWhiteConditionalBondPrice, AtT0MatchesInitialCurve) {
    YieldCurve curve({0.5,1,2,5,10}, {0.04,0.04,0.04,0.04,0.04});
    HullWhite hw(0.1, 0.01, curve);
    // At t≈0, conditionalBondPrice should equal bondPrice (initial curve)
    for (double T : {1.0, 3.0, 5.0, 10.0}) {
        EXPECT_NEAR(hw.conditionalBondPrice(0.0, T, 0.04),
                    hw.bondPrice(T), 1e-8);
    }
}

TEST(HullWhiteConditionalBondPrice, PositiveAndLessThanOne) {
    YieldCurve curve({0.5,1,2,5,10}, {0.04,0.04,0.04,0.04,0.04});
    HullWhite hw(0.1, 0.01, curve);
    for (double t : {1.0, 2.0, 3.0}) {
        for (double T : {t+0.5, t+2.0, t+5.0}) {
            double P = hw.conditionalBondPrice(t, T, 0.04);
            EXPECT_GT(P, 0.0) << "t=" << t << " T=" << T;
            EXPECT_LT(P, 1.0) << "t=" << t << " T=" << T;
        }
    }
}

TEST(HullWhiteConditionalBondPrice, HigherRateLowerPrice) {
    YieldCurve curve({0.5,1,2,5,10}, {0.04,0.04,0.04,0.04,0.04});
    HullWhite hw(0.1, 0.01, curve);
    double P_low  = hw.conditionalBondPrice(1.0, 5.0, 0.02);
    double P_high = hw.conditionalBondPrice(1.0, 5.0, 0.08);
    EXPECT_GT(P_low, P_high);
}
