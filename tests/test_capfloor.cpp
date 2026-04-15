#include <gtest/gtest.h>
#include <qf/instruments/capfloor.hpp>
#include <qf/instruments/swap.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/interpolation.hpp>
#include <qf/core/market_environment.hpp>
#include <cmath>

using namespace qf::instruments;
using namespace qf::termstructure;
using namespace qf::math;
using namespace qf::core;

namespace {

// Flat 5% curve — easy to verify analytically
YieldCurve flatCurve() {
    return YieldCurve({0.5, 1.0, 2.0, 5.0, 10.0},
                      {0.05, 0.05, 0.05, 0.05, 0.05},
                      InterpolationMethod::CubicSpline);
}

// Upward-sloping curve
YieldCurve slopedCurve() {
    return YieldCurve({0.5, 1.0, 2.0, 5.0, 10.0},
                      {0.03, 0.035, 0.04, 0.05, 0.06},
                      InterpolationMethod::CubicSpline);
}

// IRS annuity: Σ τ · P(0, T_i)
static double annuity(const YieldCurve& curve, double maturity, double frequency) {
    double tau = 1.0 / frequency;
    int n = static_cast<int>(std::round(maturity * frequency));
    double A = 0.0;
    for (int i = 1; i <= n; ++i)
        A += tau * curve.discountFactor(i * tau);
    return A;
}

// IRS payer NPV at fixed rate K:  N · [1 − P(0,T) − K · A(T)]
static double irsNPV(const YieldCurve& curve, double notional,
                     double strike, double maturity, double frequency) {
    return notional * (1.0 - curve.discountFactor(maturity)
                       - strike * annuity(curve, maturity, frequency));
}

} // namespace

// ═══════════════════════════════════════════════════════════════════════════
// Basic construction and validation
// ═══════════════════════════════════════════════════════════════════════════

TEST(CapFloor, InvalidParamsThrow) {
    EXPECT_THROW(CapFloor(CapFloorType::Cap,    0.0, 0.05, 5.0, 4.0, 0.1, 0.01),
                 std::invalid_argument); // zero notional
    EXPECT_THROW(CapFloor(CapFloorType::Cap, 1e6,   0.0, 5.0, 4.0, 0.1, 0.01),
                 std::invalid_argument); // zero strike
    EXPECT_THROW(CapFloor(CapFloorType::Cap, 1e6, 0.05,  0.0, 4.0, 0.1, 0.01),
                 std::invalid_argument); // zero maturity
    EXPECT_THROW(CapFloor(CapFloorType::Cap, 1e6, 0.05, 5.0,  0.0, 0.1, 0.01),
                 std::invalid_argument); // zero frequency
    EXPECT_THROW(CapFloor(CapFloorType::Cap, 1e6, 0.05, 5.0, 4.0,  0.0, 0.01),
                 std::invalid_argument); // zero a
    EXPECT_THROW(CapFloor(CapFloorType::Cap, 1e6, 0.05, 5.0, 4.0, 0.1,  0.0),
                 std::invalid_argument); // zero sigma
}

TEST(CapFloor, AccessorsReturnConstructedValues) {
    CapFloor cap(CapFloorType::Cap, 1e6, 0.05, 5.0, 4.0, 0.1, 0.01);
    EXPECT_EQ(cap.type(),      CapFloorType::Cap);
    EXPECT_DOUBLE_EQ(cap.notional(),  1e6);
    EXPECT_DOUBLE_EQ(cap.strike(),    0.05);
    EXPECT_DOUBLE_EQ(cap.maturity(),  5.0);
    EXPECT_DOUBLE_EQ(cap.frequency(), 4.0);
    EXPECT_DOUBLE_EQ(cap.hwA(),       0.1);
    EXPECT_DOUBLE_EQ(cap.hwSigma(),   0.01);
}

// ═══════════════════════════════════════════════════════════════════════════
// Cap-Floor parity:  Cap(K) − Floor(K) = IRS payer NPV at rate K
// This is the fundamental model-independent identity.
// ═══════════════════════════════════════════════════════════════════════════

TEST(CapFloor, CapFloorParityFlatCurve) {
    auto curve = flatCurve();
    const double N = 1e6, K = 0.05, T = 5.0, freq = 4.0;
    const double a = 0.1, sigma = 0.01;

    CapFloor cap  (CapFloorType::Cap,   N, K, T, freq, a, sigma);
    CapFloor floor(CapFloorType::Floor, N, K, T, freq, a, sigma);

    double parity   = cap.price(curve) - floor.price(curve);
    double expected = irsNPV(curve, N, K, T, freq);

    EXPECT_NEAR(parity, expected, 1.0); // within $1 on $1M notional
}

TEST(CapFloor, CapFloorParitySlopedCurve) {
    auto curve = slopedCurve();
    const double N = 1e6, K = 0.04, T = 5.0, freq = 2.0;
    const double a = 0.15, sigma = 0.015;

    CapFloor cap  (CapFloorType::Cap,   N, K, T, freq, a, sigma);
    CapFloor floor(CapFloorType::Floor, N, K, T, freq, a, sigma);

    double parity   = cap.price(curve) - floor.price(curve);
    double expected = irsNPV(curve, N, K, T, freq);

    EXPECT_NEAR(parity, expected, 1.0);
}

TEST(CapFloor, CapFloorParityAnnualPayments) {
    auto curve = flatCurve();
    const double N = 5e5, K = 0.06, T = 3.0, freq = 1.0;
    const double a = 0.2, sigma = 0.02;

    CapFloor cap  (CapFloorType::Cap,   N, K, T, freq, a, sigma);
    CapFloor floor(CapFloorType::Floor, N, K, T, freq, a, sigma);

    double parity   = cap.price(curve) - floor.price(curve);
    double expected = irsNPV(curve, N, K, T, freq);

    EXPECT_NEAR(parity, expected, 1.0);
}

// ═══════════════════════════════════════════════════════════════════════════
// Prices are non-negative and finite
// ═══════════════════════════════════════════════════════════════════════════

TEST(CapFloor, CapPriceNonNegative) {
    auto curve = flatCurve();
    CapFloor cap(CapFloorType::Cap, 1e6, 0.05, 5.0, 4.0, 0.1, 0.01);
    EXPECT_GE(cap.price(curve), 0.0);
}

TEST(CapFloor, FloorPriceNonNegative) {
    auto curve = flatCurve();
    CapFloor floor(CapFloorType::Floor, 1e6, 0.05, 5.0, 4.0, 0.1, 0.01);
    EXPECT_GE(floor.price(curve), 0.0);
}

// ═══════════════════════════════════════════════════════════════════════════
// Monotonicity in volatility: higher σ → higher option price
// ═══════════════════════════════════════════════════════════════════════════

TEST(CapFloor, CapPriceIncreasesWithVol) {
    auto curve = flatCurve();
    CapFloor cap1(CapFloorType::Cap, 1e6, 0.05, 5.0, 4.0, 0.1, 0.005);
    CapFloor cap2(CapFloorType::Cap, 1e6, 0.05, 5.0, 4.0, 0.1, 0.02);
    EXPECT_GT(cap2.price(curve), cap1.price(curve));
}

TEST(CapFloor, FloorPriceIncreasesWithVol) {
    auto curve = flatCurve();
    CapFloor f1(CapFloorType::Floor, 1e6, 0.05, 5.0, 4.0, 0.1, 0.005);
    CapFloor f2(CapFloorType::Floor, 1e6, 0.05, 5.0, 4.0, 0.1, 0.02);
    EXPECT_GT(f2.price(curve), f1.price(curve));
}

// ═══════════════════════════════════════════════════════════════════════════
// Monotonicity in strike: higher K → lower cap, higher floor
// ═══════════════════════════════════════════════════════════════════════════

TEST(CapFloor, CapPriceDecreasesWithStrike) {
    auto curve = flatCurve();
    CapFloor cap1(CapFloorType::Cap, 1e6, 0.03, 5.0, 4.0, 0.1, 0.01);
    CapFloor cap2(CapFloorType::Cap, 1e6, 0.07, 5.0, 4.0, 0.1, 0.01);
    EXPECT_GT(cap1.price(curve), cap2.price(curve));
}

TEST(CapFloor, FloorPriceIncreasesWithStrike) {
    auto curve = flatCurve();
    CapFloor f1(CapFloorType::Floor, 1e6, 0.03, 5.0, 4.0, 0.1, 0.01);
    CapFloor f2(CapFloorType::Floor, 1e6, 0.07, 5.0, 4.0, 0.1, 0.01);
    EXPECT_LT(f1.price(curve), f2.price(curve));
}

// ═══════════════════════════════════════════════════════════════════════════
// Monotonicity in maturity: longer cap → higher price (more caplets)
// ═══════════════════════════════════════════════════════════════════════════

TEST(CapFloor, CapPriceIncreasesWithMaturity) {
    auto curve = flatCurve();
    CapFloor cap1(CapFloorType::Cap, 1e6, 0.05, 2.0, 4.0, 0.1, 0.01);
    CapFloor cap2(CapFloorType::Cap, 1e6, 0.05, 5.0, 4.0, 0.1, 0.01);
    EXPECT_GT(cap2.price(curve), cap1.price(curve));
}

// ═══════════════════════════════════════════════════════════════════════════
// MarketEnvironment interface
// ═══════════════════════════════════════════════════════════════════════════

TEST(CapFloor, CalculatePVMatchesPrice) {
    auto curve = flatCurve();
    MarketEnvironment env(curve);
    CapFloor cap(CapFloorType::Cap, 1e6, 0.05, 5.0, 4.0, 0.1, 0.01);
    EXPECT_DOUBLE_EQ(cap.calculatePV(env), cap.price(curve));
}

// ═══════════════════════════════════════════════════════════════════════════
// Notional scaling: double notional → double price
// ═══════════════════════════════════════════════════════════════════════════

TEST(CapFloor, PriceScalesWithNotional) {
    auto curve = flatCurve();
    CapFloor cap1(CapFloorType::Cap,  1e6, 0.05, 5.0, 4.0, 0.1, 0.01);
    CapFloor cap2(CapFloorType::Cap,  2e6, 0.05, 5.0, 4.0, 0.1, 0.01);
    EXPECT_NEAR(cap2.price(curve), 2.0 * cap1.price(curve), 1e-6);
}
