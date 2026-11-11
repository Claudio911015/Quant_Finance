#include <gtest/gtest.h>
#include <qf/instruments/bond.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <cmath>

using namespace qf::instruments;
using namespace qf::termstructure;

namespace {
YieldCurve upwardCurve() {
    return YieldCurve({0.5, 1.0, 2.0, 5.0, 10.0},
                      {0.040, 0.045, 0.050, 0.055, 0.060},
                      qf::math::InterpolationMethod::Linear);
}
}

TEST(BondCashFlowSchedule, DiscountedFlowsEqualPrice) {
    Bond bond(1000.0, 0.06, 8, 2.0);
    YieldCurve curve = upwardCurve();
    double sum = 0.0;
    for (const auto& [t, amount] : bond.cashFlowSchedule())
        sum += amount * curve.discountFactor(t);
    EXPECT_NEAR(sum, bond.price(curve), 1e-10);
}

TEST(BondCashFlowSchedule, TimesAndAmounts) {
    Bond bond(1000.0, 0.06, 4, 2.0);
    auto sched = bond.cashFlowSchedule();
    ASSERT_EQ(sched.size(), 4u);
    EXPECT_DOUBLE_EQ(sched[0].first, 0.5);
    EXPECT_DOUBLE_EQ(sched[3].first, 2.0);
    EXPECT_NEAR(sched[0].second, 30.0, 1e-12);
    EXPECT_NEAR(sched[3].second, 1030.0, 1e-12);
}

TEST(BondCashFlowSchedule, AnnualFrequency) {
    Bond bond(500.0, 0.04, 3, 1.0);
    YieldCurve curve = upwardCurve();
    auto sched = bond.cashFlowSchedule();
    ASSERT_EQ(sched.size(), 3u);
    double sum = 0.0;
    for (const auto& [t, amount] : sched)
        sum += amount * curve.discountFactor(t);
    EXPECT_NEAR(sum, bond.price(curve), 1e-10);
}
