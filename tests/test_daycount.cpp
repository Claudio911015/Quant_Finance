#include <gtest/gtest.h>
#include <qf/math/daycount.hpp>
#include <qf/instruments/bond.hpp>
#include <qf/instruments/swap.hpp>
#include <qf/instruments/capfloor.hpp>
#include <qf/instruments/swaption.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <stdexcept>
#include <cmath>

using namespace qf::math;
using namespace qf::instruments;
using namespace qf::termstructure;

namespace {

YieldCurve flatCurve(double rate) {
    return YieldCurve({0.5, 1.0, 2.0, 5.0, 10.0},
                      {rate, rate, rate, rate, rate},
                      InterpolationMethod::Linear);
}

} // namespace

// ═══════════════════════════════════════════════════════════════════════════
// periodFraction
// ═══════════════════════════════════════════════════════════════════════════

TEST(DayCount, PeriodFractionACT365IsOneOverFreq) {
    // ACT/365 with any frequency → 1/frequency
    EXPECT_DOUBLE_EQ(periodFraction(1.0, DayCountConvention::ACT_365), 1.0);
    EXPECT_DOUBLE_EQ(periodFraction(2.0, DayCountConvention::ACT_365), 0.5);
    EXPECT_DOUBLE_EQ(periodFraction(4.0, DayCountConvention::ACT_365), 0.25);
    EXPECT_DOUBLE_EQ(periodFraction(12.0, DayCountConvention::ACT_365), 1.0 / 12.0);
}

TEST(DayCount, PeriodFractionACT360IsLargerThanACT365) {
    // ACT/360 denominator is smaller, so τ is larger than ACT/365
    double tau_365 = periodFraction(2.0, DayCountConvention::ACT_365);
    double tau_360 = periodFraction(2.0, DayCountConvention::ACT_360);
    EXPECT_GT(tau_360, tau_365);
    // Exact: 365/(360*2) = 0.506944...
    EXPECT_NEAR(tau_360, 365.0 / 720.0, 1e-12);
}

TEST(DayCount, PeriodFractionACTACTEqualsACT365) {
    // Under uniform schedules ACT/ACT ≈ ACT/365
    EXPECT_DOUBLE_EQ(periodFraction(2.0, DayCountConvention::ACT_ACT_ISDA),
                     periodFraction(2.0, DayCountConvention::ACT_365));
}

TEST(DayCount, PeriodFraction30360EqualsACT365) {
    // 30-day months give equal periods: 1/frequency
    EXPECT_DOUBLE_EQ(periodFraction(4.0, DayCountConvention::THIRTY_360),
                     periodFraction(4.0, DayCountConvention::ACT_365));
}

// ═══════════════════════════════════════════════════════════════════════════
// yearFraction (from actual days)
// ═══════════════════════════════════════════════════════════════════════════

TEST(DayCount, YearFractionACT360) {
    // 180 actual days / 360 = 0.5
    EXPECT_DOUBLE_EQ(yearFraction(180, DayCountConvention::ACT_360), 0.5);
}

TEST(DayCount, YearFractionTHIRTY360Throws) {
    // THIRTY_360 requires calendar dates — must throw rather than return wrong value
    EXPECT_THROW(yearFraction(180, DayCountConvention::THIRTY_360), std::logic_error);
}

TEST(DayCount, YearFractionACT365) {
    // 365 days / 365 = 1.0
    EXPECT_DOUBLE_EQ(yearFraction(365, DayCountConvention::ACT_365), 1.0);
    // 182 days / 365
    EXPECT_NEAR(yearFraction(182, DayCountConvention::ACT_365), 182.0 / 365.0, 1e-12);
}

TEST(DayCount, YearFractionACTACT_LeapYear) {
    // 366 days in a leap year / 366 = 1.0
    EXPECT_DOUBLE_EQ(yearFraction(366, DayCountConvention::ACT_ACT_ISDA, 366), 1.0);
    // 90 days in a non-leap year
    EXPECT_NEAR(yearFraction(90, DayCountConvention::ACT_ACT_ISDA, 365), 90.0 / 365.0, 1e-12);
}

TEST(DayCount, YearFractionACTACT_BadDaysInYear) {
    EXPECT_THROW(yearFraction(90, DayCountConvention::ACT_ACT_ISDA, 0),
                 std::invalid_argument);
}

// ═══════════════════════════════════════════════════════════════════════════
// dayCountFromString
// ═══════════════════════════════════════════════════════════════════════════

TEST(DayCount, ParseACT360) {
    EXPECT_EQ(dayCountFromString("ACT/360"),      DayCountConvention::ACT_360);
    EXPECT_EQ(dayCountFromString("act/360"),      DayCountConvention::ACT_360);
    EXPECT_EQ(dayCountFromString("ACTUAL/360"),   DayCountConvention::ACT_360);
}

TEST(DayCount, ParseACT365) {
    EXPECT_EQ(dayCountFromString("ACT/365"),           DayCountConvention::ACT_365);
    EXPECT_EQ(dayCountFromString("ACT/365 FIXED"),     DayCountConvention::ACT_365);
    EXPECT_EQ(dayCountFromString("ACTUAL/365 FIXED"),  DayCountConvention::ACT_365);
}

TEST(DayCount, ParseACTACT) {
    EXPECT_EQ(dayCountFromString("ACT/ACT"),       DayCountConvention::ACT_ACT_ISDA);
    EXPECT_EQ(dayCountFromString("ACT/ACT ISDA"),  DayCountConvention::ACT_ACT_ISDA);
    EXPECT_EQ(dayCountFromString("ACTUAL/ACTUAL"), DayCountConvention::ACT_ACT_ISDA);
}

TEST(DayCount, Parse30360) {
    EXPECT_EQ(dayCountFromString("30/360"),       DayCountConvention::THIRTY_360);
    EXPECT_EQ(dayCountFromString("THIRTY/360"),   DayCountConvention::THIRTY_360);
    EXPECT_EQ(dayCountFromString("BOND BASIS"),   DayCountConvention::THIRTY_360);
}

TEST(DayCount, ParseUnknownThrows) {
    EXPECT_THROW(dayCountFromString("ACT/252"),   std::invalid_argument);
    EXPECT_THROW(dayCountFromString(""),          std::invalid_argument);
}

TEST(DayCount, DayCountName) {
    EXPECT_STREQ(dayCountName(DayCountConvention::ACT_360),      "ACT/360");
    EXPECT_STREQ(dayCountName(DayCountConvention::ACT_365),      "ACT/365");
    EXPECT_STREQ(dayCountName(DayCountConvention::ACT_ACT_ISDA), "ACT/ACT ISDA");
    EXPECT_STREQ(dayCountName(DayCountConvention::THIRTY_360),   "30/360");
}

// ═══════════════════════════════════════════════════════════════════════════
// Bond — ACT/360 vs ACT/365
// ═══════════════════════════════════════════════════════════════════════════

TEST(DayCount, BondACT360CouponLargerThanACT365) {
    // Same coupon rate, ACT/360 → τ > 1/freq → higher periodic coupon → higher price
    auto curve = flatCurve(0.05);
    Bond b365(1000.0, 0.06, 4, 2.0, DayCountConvention::ACT_365);
    Bond b360(1000.0, 0.06, 4, 2.0, DayCountConvention::ACT_360);
    EXPECT_GT(b360.price(curve), b365.price(curve));
}

TEST(DayCount, BondACT365DefaultIsUnchanged) {
    // Constructing without DCC arg uses ACT/365 (historical default)
    auto curve = flatCurve(0.05);
    Bond bDefault(1000.0, 0.06, 4, 2.0);
    Bond b365   (1000.0, 0.06, 4, 2.0, DayCountConvention::ACT_365);
    EXPECT_NEAR(bDefault.price(curve), b365.price(curve), 1e-12);
}

TEST(DayCount, BondACT360CouponRatio) {
    // ACT/360 coupon = face * rate * 365/(360*freq).
    // Price ratio ACT360/ACT365 should match coupon ratio for a single-period ZCB-like bond.
    double rate = 0.05, face = 1000.0, freq = 2.0;
    auto curve = flatCurve(rate);
    Bond b365(face, rate, 2, freq, DayCountConvention::ACT_365);
    Bond b360(face, rate, 2, freq, DayCountConvention::ACT_360);
    // Coupon ratio
    double ratio = (365.0 / (360.0 * freq)) / (1.0 / freq); // = 365/360
    // Price of ACT/360 should be higher by roughly ratio (up to discount effects)
    EXPECT_GT(b360.price(curve) / b365.price(curve), 1.0);
    EXPECT_LT(b360.price(curve) / b365.price(curve), ratio + 0.01);
}

// ═══════════════════════════════════════════════════════════════════════════
// Leg — string constructor backward compatibility
// ═══════════════════════════════════════════════════════════════════════════

TEST(DayCount, LegStringConstructorACT365) {
    Leg leg("USD", "ACT/365", 1000.0, 2.0, 0.05, 0.0, false, 2.0);
    EXPECT_EQ(leg.dayCount(), DayCountConvention::ACT_365);
    EXPECT_STREQ(leg.dayCountConvention(), "ACT/365");
}

TEST(DayCount, LegStringConstructorACT360) {
    Leg leg("USD", "ACT/360", 1000.0, 2.0, 0.05, 0.0, false, 2.0);
    EXPECT_EQ(leg.dayCount(), DayCountConvention::ACT_360);
}

TEST(DayCount, LegEnumConstructor) {
    Leg leg("USD", DayCountConvention::THIRTY_360, 1000.0, 2.0, 0.05, 0.0, false, 2.0);
    EXPECT_EQ(leg.dayCount(), DayCountConvention::THIRTY_360);
}

TEST(DayCount, LegUnknownStringThrows) {
    EXPECT_THROW(
        (Leg("USD", "ACT/252", 1000.0, 2.0, 0.05, 0.0, false, 2.0)),
        std::invalid_argument);
}

TEST(DayCount, LegACT360FixedLegPVHigher) {
    // Fixed leg with ACT/360 pays more per period → higher PV
    auto curve = flatCurve(0.04);
    auto makeEnv = [&]() { return qf::core::MarketEnvironment(curve); };

    Leg fixed365("USD", DayCountConvention::ACT_365, 1000.0, 2.0, 0.05, 0.0, false, 2.0);
    Leg fixed360("USD", DayCountConvention::ACT_360, 1000.0, 2.0, 0.05, 0.0, false, 2.0);

    auto env = makeEnv();
    EXPECT_GT(fixed360.pv(env), fixed365.pv(env));
}

// ═══════════════════════════════════════════════════════════════════════════
// CapFloor — DCC affects accrual tau (X, scale) but not HW sigma_p (dt)
// ═══════════════════════════════════════════════════════════════════════════

TEST(DayCount, CapFloorDCCDefaultIsACT365) {
    // Constructor without DCC arg must match explicit ACT/365
    auto curve = flatCurve(0.05);
    CapFloor capDefault(CapFloorType::Cap, 1000.0, 0.05, 2.0, 4.0, 0.1, 0.01);
    CapFloor cap365   (CapFloorType::Cap, 1000.0, 0.05, 2.0, 4.0, 0.1, 0.01,
                       DayCountConvention::ACT_365);
    EXPECT_NEAR(capDefault.price(curve), cap365.price(curve), 1e-12);
}

TEST(DayCount, CapFloorACT360CapLowerFloorHigher) {
    // ACT/360: τ > 1/freq → larger effective fixed rate per period.
    // For a cap (right to receive float - fixed), a higher fixed tau → cap value LOWER.
    // For a floor (right to receive fixed - float), a higher fixed tau → floor value HIGHER.
    // Both verify that DCC changes the price in the correct direction.
    auto curve = flatCurve(0.05);
    CapFloor cap365  (CapFloorType::Cap,   1000.0, 0.05, 2.0, 4.0, 0.1, 0.01,
                      DayCountConvention::ACT_365);
    CapFloor cap360  (CapFloorType::Cap,   1000.0, 0.05, 2.0, 4.0, 0.1, 0.01,
                      DayCountConvention::ACT_360);
    CapFloor floor365(CapFloorType::Floor, 1000.0, 0.05, 2.0, 4.0, 0.1, 0.01,
                      DayCountConvention::ACT_365);
    CapFloor floor360(CapFloorType::Floor, 1000.0, 0.05, 2.0, 4.0, 0.1, 0.01,
                      DayCountConvention::ACT_360);
    // Cap price lower with ACT/360: X = 1/(1+K*tau) is smaller → ZCB put more OTM
    EXPECT_LT(cap360.price(curve), cap365.price(curve));
    // Floor price higher with ACT/360: ZCB call more ITM at the same ZCB level
    EXPECT_GT(floor360.price(curve), floor365.price(curve));
    // Verify prices are distinct (not degenerate)
    EXPECT_GT(cap365.price(curve), 0.0);
    EXPECT_GT(floor365.price(curve), 0.0);
}

TEST(DayCount, CapFloorACT360CapFloorParity) {
    // Cap-Floor parity must hold under both DCC conventions:
    //   Cap(K) - Floor(K) = NPV of payer IRS at K
    // We test that the difference changes consistently with DCC (not zero arb).
    auto curve = flatCurve(0.04);
    CapFloor cap365  (CapFloorType::Cap,   1.0, 0.05, 2.0, 2.0, 0.1, 0.01,
                      DayCountConvention::ACT_365);
    CapFloor floor365(CapFloorType::Floor, 1.0, 0.05, 2.0, 2.0, 0.1, 0.01,
                      DayCountConvention::ACT_365);
    CapFloor cap360  (CapFloorType::Cap,   1.0, 0.05, 2.0, 2.0, 0.1, 0.01,
                      DayCountConvention::ACT_360);
    CapFloor floor360(CapFloorType::Floor, 1.0, 0.05, 2.0, 2.0, 0.1, 0.01,
                      DayCountConvention::ACT_360);
    double diff365 = cap365.price(curve) - floor365.price(curve);
    double diff360 = cap360.price(curve) - floor360.price(curve);
    // Both differences should be finite and negative at K=5% > par~4%
    EXPECT_LT(diff365, 0.0);
    EXPECT_LT(diff360, 0.0);
    // ACT/360 makes the fixed leg "higher" so payer NPV is more negative → diff360 < diff365
    EXPECT_LT(diff360, diff365);
}

// ═══════════════════════════════════════════════════════════════════════════
// Swaption — DCC affects coupon weights c_i (accrual tau), not r* bisection
// ═══════════════════════════════════════════════════════════════════════════

TEST(DayCount, SwaptionPayerACT360LowerReceiverHigher) {
    // ACT/360: τ > 1/freq → higher effective fixed coupons per period.
    // Payer swaption (pay fixed) worth LESS with ACT/360 at same strike K
    //   (fixed coupons are more expensive, underlying payer IRS is less attractive).
    // Receiver swaption (receive fixed) worth MORE with ACT/360.
    auto curve = flatCurve(0.05);
    Swaption payer365(SwaptionType::Payer,    1000.0, 0.05, 1.0, 2.0, 2.0, 0.1, 0.01,
                      DayCountConvention::ACT_365);
    Swaption payer360(SwaptionType::Payer,    1000.0, 0.05, 1.0, 2.0, 2.0, 0.1, 0.01,
                      DayCountConvention::ACT_360);
    Swaption recv365 (SwaptionType::Receiver, 1000.0, 0.05, 1.0, 2.0, 2.0, 0.1, 0.01,
                      DayCountConvention::ACT_365);
    Swaption recv360 (SwaptionType::Receiver, 1000.0, 0.05, 1.0, 2.0, 2.0, 0.1, 0.01,
                      DayCountConvention::ACT_360);
    EXPECT_LT(payer360.price(curve), payer365.price(curve));
    EXPECT_GT(recv360.price(curve),  recv365.price(curve));
}

TEST(DayCount, SwaptionDCCDefaultIsACT365) {
    auto curve = flatCurve(0.05);
    Swaption swDefault(SwaptionType::Payer, 1000.0, 0.05, 1.0, 2.0, 2.0, 0.1, 0.01);
    Swaption sw365    (SwaptionType::Payer, 1000.0, 0.05, 1.0, 2.0, 2.0, 0.1, 0.01,
                       DayCountConvention::ACT_365);
    EXPECT_NEAR(swDefault.price(curve), sw365.price(curve), 1e-12);
}
