// Bond with an explicit payment calendar (QF Desk, corte 3, R9): accrued interest, clean price
// and day-by-day aging. The constructor from payTimes must reproduce the periods/frequency one.
#include <gtest/gtest.h>
#include <qf/instruments/bond.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <algorithm>
#include <cmath>
#include <vector>

using namespace qf::instruments;
using namespace qf::termstructure;

namespace {

YieldCurve upwardCurve() {
    return YieldCurve({0.25, 0.5, 1.0, 2.0, 5.0, 10.0},
                      {0.040, 0.042, 0.045, 0.050, 0.055, 0.060},
                      qf::math::InterpolationMethod::Linear);
}

YieldCurve flatCurve(double r) {
    return YieldCurve({0.5, 1.0, 5.0, 10.0}, {r, r, r, r}, qf::math::InterpolationMethod::Linear);
}

std::vector<double> regularTimes(int periods, double frequency) {
    std::vector<double> t(periods);
    for (int i = 0; i < periods; ++i) t[i] = (i + 1.0) / frequency;
    return t;
}

double relDiff(double a, double b) { return std::fabs(a - b) / std::max(std::fabs(b), 1e-300); }

// Bond aged `elapsed` days the way the desk does it: coupon i falls on day round(i*365/f) from
// the start, the remaining ones have payTimes = i/f - elapsed/365 and the previous coupon sits at
// (i0-1)/f - elapsed/365 (clamped to 0: the rounded pay day can leave it a hair above zero).
Bond agedBond(double face, double c, int periods, double f, int elapsed) {
    std::vector<double> pay;
    int i0 = 0;
    for (int i = 1; i <= periods; ++i) {
        if (std::lround(i * 365.0 / f) > elapsed) {
            if (i0 == 0) i0 = i;
            pay.push_back(i / f - elapsed / 365.0);
        }
    }
    double prev = std::min(0.0, (i0 - 1) / f - elapsed / 365.0);
    return Bond(face, c, f, pay, prev);
}

} // namespace

// ── Retrocompatibilidad: calendario regular y sin cupón corrido = constructor actual ──

TEST(BondSchedule, RegularCalendarMatchesPeriodsConstructor) {
    YieldCurve curve = upwardCurve();
    for (double f : {1.0, 2.0, 4.0}) {
        Bond legacy(1000.0, 0.06, 8, f);
        Bond explicitB(1000.0, 0.06, f, regularTimes(8, f), 0.0);

        EXPECT_LT(relDiff(explicitB.price(curve), legacy.price(curve)), 1e-12);
        EXPECT_LT(relDiff(explicitB.duration(curve), legacy.duration(curve)), 1e-12);
        EXPECT_LT(relDiff(explicitB.convexity(curve), legacy.convexity(curve)), 1e-12);
        EXPECT_LT(relDiff(explicitB.yield(1010.0), legacy.yield(1010.0)), 1e-12);
        EXPECT_DOUBLE_EQ(explicitB.maturity(), legacy.maturity());

        auto a = explicitB.cashFlowSchedule();
        auto b = legacy.cashFlowSchedule();
        ASSERT_EQ(a.size(), b.size());
        for (std::size_t i = 0; i < a.size(); ++i) {
            EXPECT_LT(relDiff(a[i].first, b[i].first), 1e-12);
            EXPECT_LT(relDiff(a[i].second, b[i].second), 1e-12);
        }
        EXPECT_EQ(legacy.accruedInterest(), 0.0);
        EXPECT_EQ(explicitB.accruedInterest(), 0.0);
        EXPECT_LT(relDiff(explicitB.cleanPrice(curve), legacy.price(curve)), 1e-12);
    }
}

TEST(BondSchedule, LegacyConstructorStillMatchesTheHandComputedPrice) {
    YieldCurve curve = upwardCurve();
    Bond b(1000.0, 0.06, 8, 2.0);
    double pv = 0.0;
    for (int i = 1; i <= 8; ++i) pv += (i == 8 ? 1030.0 : 30.0) * curve.discountFactor(i / 2.0);
    EXPECT_NEAR(b.price(curve), pv, 1e-10);
}

// ── Calendario irregular y cupón corrido ──

TEST(BondSchedule, IrregularCalendarPricesItsOwnFlows) {
    YieldCurve curve = upwardCurve();
    // Aged 100 days of a semi-annual bond: the first coupon is 82/365 y away, previous one at -100/365.
    std::vector<double> pay = {82.5 / 365.0, 82.5 / 365.0 + 0.5, 82.5 / 365.0 + 1.0};
    Bond b(1000.0, 0.06, 2.0, pay, -100.0 / 365.0);
    double pv = 0.0;
    for (std::size_t i = 0; i < pay.size(); ++i)
        pv += (i + 1 == pay.size() ? 1030.0 : 30.0) * curve.discountFactor(pay[i]);
    EXPECT_NEAR(b.price(curve), pv, 1e-10);
    EXPECT_DOUBLE_EQ(b.maturity(), pay.back());
    auto sched = b.cashFlowSchedule();
    ASSERT_EQ(sched.size(), 3u);
    EXPECT_DOUBLE_EQ(sched[0].first, pay[0]);
    EXPECT_NEAR(sched[2].second, 1030.0, 1e-12);
}

TEST(BondSchedule, AccruedInterestIsTheElapsedShareOfTheCoupon) {
    // Previous coupon 0.1 y ago, next in 0.4 y: 0.1 of the 0.5 y period has elapsed.
    Bond b(1000.0, 0.06, 2.0, {0.4, 0.9}, -0.1);
    EXPECT_NEAR(b.accruedInterest(), 30.0 * 0.2, 1e-12);
    // Just paid: previous coupon today.
    Bond fresh(1000.0, 0.06, 2.0, {0.5, 1.0}, 0.0);
    EXPECT_EQ(fresh.accruedInterest(), 0.0);
}

TEST(BondSchedule, CleanPlusAccruedIsTheDirtyPrice) {
    YieldCurve curve = upwardCurve();
    for (double prev : {-0.45, -0.3, -0.1, -1e-9}) {
        Bond b(1000.0, 0.06, 2.0, {0.5 + prev, 1.0 + prev, 1.5 + prev, 2.0 + prev}, prev);
        EXPECT_LT(relDiff(b.cleanPrice(curve) + b.accruedInterest(), b.price(curve)), 1e-12);
        EXPECT_GT(b.accruedInterest(), 0.0);
        EXPECT_LT(b.cleanPrice(curve), b.price(curve));
    }
}

// ── R9: envejecimiento día a día ──

TEST(BondSchedule, DirtyPriceMovesByTheDailyCarryBetweenCoupons) {
    YieldCurve curve = flatCurve(0.05);
    for (double f : {1.0, 2.0}) {
        const double face = 1000.0, c = 0.06, coupon = face * c / f;
        const int periods = 4;
        std::vector<long> payDay;
        for (int i = 1; i <= periods; ++i) payDay.push_back(std::lround(i * 365.0 / f));
        int checked = 0;
        for (int e = 0; e + 1 < payDay.back(); ++e) {
            bool couponInBetween = std::find(payDay.begin(), payDay.end(), e + 1) != payDay.end();
            if (couponInBetween) continue;
            double p0 = agedBond(face, c, periods, f, e).price(curve);
            double p1 = agedBond(face, c, periods, f, e + 1).price(curve);
            EXPECT_LT(std::fabs(p1 - p0), 0.01 * coupon) << "f=" << f << " elapsed=" << e;
            EXPECT_GT(p1, p0) << "carry is positive with a positive flat rate";
            ++checked;
        }
        EXPECT_GT(checked, 300);
    }
}

TEST(BondSchedule, CleanPriceDoesNotJumpWhenACouponIsPaid) {
    YieldCurve curve = flatCurve(0.05);
    const double face = 1000.0, c = 0.06, f = 1.0, coupon = face * c / f;
    // Day before and day of the first coupon (day 365 of an annual bond).
    Bond before = agedBond(face, c, 3, f, 364);
    Bond after  = agedBond(face, c, 3, f, 365);
    // The dirty price loses the coupon, the clean price only moves by one day of carry.
    EXPECT_GT(before.price(curve) - after.price(curve), 0.9 * coupon);
    EXPECT_LT(std::fabs(after.cleanPrice(curve) - before.cleanPrice(curve)), 0.01 * coupon);
    EXPECT_EQ(after.accruedInterest(), 0.0);
}

// ── Validación ──

TEST(BondSchedule, InvalidCalendarsThrow) {
    EXPECT_THROW(Bond(1000.0, 0.06, 2.0, {}, 0.0), std::invalid_argument);                 // empty
    EXPECT_THROW(Bond(1000.0, 0.06, 2.0, {0.0, 0.5}, 0.0), std::invalid_argument);          // payTimes[0] = 0
    EXPECT_THROW(Bond(1000.0, 0.06, 2.0, {-0.1, 0.4}, -0.6), std::invalid_argument);        // negative pay time
    EXPECT_THROW(Bond(1000.0, 0.06, 2.0, {0.5, 0.5}, 0.0), std::invalid_argument);          // not strictly increasing
    EXPECT_THROW(Bond(1000.0, 0.06, 2.0, {1.0, 0.5}, 0.0), std::invalid_argument);          // decreasing
    EXPECT_THROW(Bond(1000.0, 0.06, 2.0, {0.5, 1.0}, 0.1), std::invalid_argument);          // prev > 0
    EXPECT_THROW(Bond(1000.0, 0.06, 2.0, {0.5, 1.0}, std::nan("")), std::invalid_argument); // prev not finite
    EXPECT_THROW(Bond(1000.0, 0.06, 2.0, {0.5, std::nan("")}, 0.0), std::invalid_argument); // pay time not finite
    EXPECT_THROW(Bond(0.0, 0.06, 2.0, {0.5, 1.0}, 0.0), std::invalid_argument);             // face
    EXPECT_THROW(Bond(1000.0, 0.06, 0.0, {0.5, 1.0}, 0.0), std::invalid_argument);          // frequency
    EXPECT_NO_THROW(Bond(1000.0, 0.06, 2.0, {0.3}, -0.2));                                  // single flow
}
