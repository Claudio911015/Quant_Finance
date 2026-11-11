#include <gtest/gtest.h>
#include <qf/instruments/capfloor.hpp>
#include <qf/instruments/swap.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/interpolation.hpp>
#include <qf/core/market_environment.hpp>
#include <algorithm>
#include <cmath>
#include <utility>
#include <vector>

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

// ═══════════════════════════════════════════════════════════════════════════
// Guard: a maturity shorter than half a payment period rounds to zero periods
// ═══════════════════════════════════════════════════════════════════════════

TEST(CapFloor, PriceThrowsWhenMaturityCoversNoPeriods) {
    auto curve = flatCurve();
    // 0.1y maturity at 2 periods/year -> round(0.2) = 0 caplets (used to return 0 silently).
    CapFloor none(CapFloorType::Cap, 1e6, 0.05, 0.1, 2.0, 0.1, 0.01);
    EXPECT_THROW(none.price(curve), std::invalid_argument);
    EXPECT_THROW(none.calculatePV(MarketEnvironment(curve)), std::invalid_argument);

    // Exactly half a period rounds up to one caplet and still prices.
    CapFloor one(CapFloorType::Cap, 1e6, 0.05, 0.25, 2.0, 0.1, 0.01);
    EXPECT_NO_THROW(one.price(curve));
}

// ═══════════════════════════════════════════════════════════════════════════
// Explicit boundary calendar and dual-curve pricing (QF Desk, corte 3, R9)
// ═══════════════════════════════════════════════════════════════════════════

namespace {

double relDiffCap(double a, double b) { return std::fabs(a - b) / std::max(std::fabs(b), 1e-300); }

std::vector<double> evenBoundaries(int n, double dt) {
    std::vector<double> t(n + 1);
    for (int i = 0; i <= n; ++i) t[i] = i * dt;
    return t;
}

// Flat continuously-compounded curve; pillars below the first caplet end so nothing extrapolates.
YieldCurve flatZero(double r) {
    return YieldCurve({0.05, 0.5, 1.0, 2.0, 5.0, 10.0}, {r, r, r, r, r, r},
                      InterpolationMethod::Linear);
}

} // namespace

TEST(CapFloorSchedule, EvenBoundariesMatchThePeriodsConstructor) {
    YieldCurve curve = slopedCurve();
    const double a = 0.03, sigma = 0.01;
    for (CapFloorType type : {CapFloorType::Cap, CapFloorType::Floor}) {
        // 28-day caplets, ACT/360 (TIIE-F).
        const double dt28 = 28.0 / 365.0;
        CapFloor legacy28(type, 1e8, 0.045, 26 * dt28, 365.0 / 28.0, a, sigma, DayCountConvention::ACT_360);
        CapFloor sched28(type, 1e8, 0.045, evenBoundaries(26, dt28), a, sigma, DayCountConvention::ACT_360);
        EXPECT_LT(relDiffCap(sched28.price(curve), legacy28.price(curve)), 1e-12);
        EXPECT_DOUBLE_EQ(sched28.maturity(), 26 * dt28);

        // Semi-annual caplets, ACT/365.
        CapFloor legacy6m(type, 1e8, 0.05, 5.0, 2.0, a, sigma, DayCountConvention::ACT_365);
        CapFloor sched6m(type, 1e8, 0.05, evenBoundaries(10, 0.5), a, sigma, DayCountConvention::ACT_365);
        EXPECT_LT(relDiffCap(sched6m.price(curve), legacy6m.price(curve)), 1e-12);
    }
}

TEST(CapFloorSchedule, LegacyConstructorKeepsItsAccessors) {
    CapFloor cap(CapFloorType::Cap, 1e6, 0.05, 5.0, 4.0, 0.1, 0.01);
    EXPECT_DOUBLE_EQ(cap.frequency(), 4.0);
    // Explicit calendar: there is no single frequency; 0 flags it.
    CapFloor sched(CapFloorType::Cap, 1e6, 0.05, {0.0, 0.25, 0.75}, 0.1, 0.01);
    EXPECT_EQ(sched.frequency(), 0.0);
    EXPECT_DOUBLE_EQ(sched.maturity(), 0.75);
}

TEST(CapFloorSchedule, DroppingTheFirstCapletEqualsTheCapOfTheRest) {
    YieldCurve curve = slopedCurve();
    std::vector<double> full, rest;
    for (int k = 0; k <= 26; ++k) full.push_back(28.0 * k / 365.0);
    rest.assign(full.begin() + 1, full.end());
    std::vector<double> first = {full[0], full[1]};

    for (CapFloorType type : {CapFloorType::Cap, CapFloorType::Floor}) {
        CapFloor all (type, 1e8, 0.045, full, 0.03, 0.01, DayCountConvention::ACT_360);
        CapFloor one (type, 1e8, 0.045, first, 0.03, 0.01, DayCountConvention::ACT_360);
        CapFloor tail(type, 1e8, 0.045, rest, 0.03, 0.01, DayCountConvention::ACT_360);
        EXPECT_LT(relDiffCap(all.price(curve) - one.price(curve), tail.price(curve)), 1e-12);
        EXPECT_LT(relDiffCap(one.price(curve) + tail.price(curve), all.price(curve)), 1e-12);
    }
}

TEST(CapFloorSchedule, IrregularBoundariesPriceEachCapletOnItsOwnInterval) {
    YieldCurve curve = slopedCurve();
    // Caplets of unequal length: the sum of single-caplet caps must equal the whole cap.
    std::vector<double> t = {0.0, 0.04, 0.13, 0.31, 0.62, 1.0};
    CapFloor all(CapFloorType::Cap, 1e7, 0.04, t, 0.05, 0.012);
    double sum = 0.0;
    for (std::size_t i = 1; i < t.size(); ++i)
        sum += CapFloor(CapFloorType::Cap, 1e7, 0.04, {t[i - 1], t[i]}, 0.05, 0.012).price(curve);
    EXPECT_LT(relDiffCap(sum, all.price(curve)), 1e-12);
    EXPECT_GT(all.price(curve), 0.0);
}

TEST(CapFloorSchedule, InvalidBoundariesThrow) {
    auto make = [](std::vector<double> t) {
        return CapFloor(CapFloorType::Cap, 1e6, 0.05, std::move(t), 0.1, 0.01);
    };
    EXPECT_THROW(make({}), std::invalid_argument);
    EXPECT_THROW(make({0.5}), std::invalid_argument);                 // n = 0
    EXPECT_THROW(make({-0.1, 0.5}), std::invalid_argument);           // t_0 < 0
    EXPECT_THROW(make({0.0, 0.5, 0.5}), std::invalid_argument);       // not strictly increasing
    EXPECT_THROW(make({0.0, 1.0, 0.5}), std::invalid_argument);
    EXPECT_THROW(make({0.0, std::nan("")}), std::invalid_argument);
    EXPECT_NO_THROW(make({0.2, 0.7}));                                 // first caplet already in the future
    EXPECT_THROW(CapFloor(CapFloorType::Cap, 0.0, 0.05, {0.0, 0.5}, 0.1, 0.01), std::invalid_argument);
    EXPECT_THROW(CapFloor(CapFloorType::Cap, 1e6, 0.0, {0.0, 0.5}, 0.1, 0.01), std::invalid_argument);
    EXPECT_THROW(CapFloor(CapFloorType::Cap, 1e6, 0.05, {0.0, 0.5}, 0.0, 0.01), std::invalid_argument);
    EXPECT_THROW(CapFloor(CapFloorType::Cap, 1e6, 0.05, {0.0, 0.5}, 0.1, 0.0), std::invalid_argument);
}

TEST(CapFloorDual, SameCurveForBothGivesThePlainPrice) {
    YieldCurve curve = slopedCurve();
    for (CapFloorType type : {CapFloorType::Cap, CapFloorType::Floor}) {
        CapFloor legacy(type, 1e8, 0.045, 26 * 28.0 / 365.0, 365.0 / 28.0, 0.03, 0.01,
                        DayCountConvention::ACT_360);
        CapFloor sched(type, 1e8, 0.045, evenBoundaries(26, 28.0 / 365.0), 0.03, 0.01,
                       DayCountConvention::ACT_360);
        EXPECT_LT(relDiffCap(legacy.priceDualCurve(curve, curve), legacy.price(curve)), 1e-12);
        EXPECT_LT(relDiffCap(sched.priceDualCurve(curve, curve), sched.price(curve)), 1e-12);
    }
}

TEST(CapFloorDual, IsTheSumOfCapletsTimesTheDiscountRatio) {
    YieldCurve projection = flatZero(0.05);
    YieldCurve discount   = flatZero(0.048);   // 20 bp below: discounts less
    std::vector<double> t;
    for (int k = 0; k <= 26; ++k) t.push_back(28.0 * k / 365.0);

    CapFloor cap(CapFloorType::Cap, 1e8, 0.05, t, 0.03, 0.01, DayCountConvention::ACT_360);
    double expected = 0.0;
    for (std::size_t i = 1; i < t.size(); ++i) {
        CapFloor caplet(CapFloorType::Cap, 1e8, 0.05, {t[i - 1], t[i]}, 0.03, 0.01,
                        DayCountConvention::ACT_360);
        expected += caplet.price(projection) * discount.discountFactor(t[i]) / projection.discountFactor(t[i]);
    }
    EXPECT_LT(relDiffCap(cap.priceDualCurve(projection, discount), expected), 1e-12);
    EXPECT_GT(cap.priceDualCurve(projection, discount), cap.price(projection));

    // The constructor from periods goes through the same formula.
    CapFloor legacy(CapFloorType::Cap, 1e8, 0.05, 26 * 28.0 / 365.0, 365.0 / 28.0, 0.03, 0.01,
                    DayCountConvention::ACT_360);
    EXPECT_LT(relDiffCap(legacy.priceDualCurve(projection, discount), expected), 1e-10);
}
