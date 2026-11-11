#include <gtest/gtest.h>
#include <qf/termstructure/ois_bootstrap.hpp>
#include <qf/math/daycount.hpp>
#include <cmath>
#include <vector>

using namespace qf::termstructure;
using qf::math::DayCountConvention;

namespace {
    constexpr int kPeriod = 28;

    std::vector<OisQuote> mixedQuotes(double bump = 0.0) {
        return {
            {28,   0.0710 + bump, OisQuote::Deposit},
            {84,   0.0715 + bump, OisQuote::Ois},
            {168,  0.0720 + bump, OisQuote::Ois},
            {364,  0.0730 + bump, OisQuote::Ois},
            {728,  0.0750 + bump, OisQuote::Ois},
            {1820, 0.0780 + bump, OisQuote::Ois},
            {3640, 0.0800 + bump, OisQuote::Ois},
            {7280, 0.0810 + bump, OisQuote::Ois},
        };
    }

    // Par rate implied by the curve for an OIS of `days` days paying every `period` days (ACT/360).
    double parRate(const YieldCurve& curve, int days, int period) {
        double annuity = 0.0;
        int prev = 0;
        for (int d : oisPaymentDays(days, period)) {
            annuity += (d - prev) / 360.0 * curve.discountFactor(d / 365.0);
            prev = d;
        }
        return (1.0 - curve.discountFactor(days / 365.0)) / annuity;
    }
}

TEST(OisBootstrap, EveryOisRepricesToItsQuote) {
    const auto quotes = mixedQuotes();
    const YieldCurve curve = bootstrapOis(quotes, kPeriod);
    for (const auto& q : quotes) {
        if (q.type != OisQuote::Ois) continue;
        EXPECT_NEAR(parRate(curve, q.days, kPeriod), q.rate, 1e-10) << "days=" << q.days;
    }
}

TEST(OisBootstrap, OisAsFirstQuoteRepricesToo) {
    const std::vector<OisQuote> quotes = {
        {84,  0.0715, OisQuote::Ois},
        {364, 0.0730, OisQuote::Ois},
    };
    const YieldCurve curve = bootstrapOis(quotes, kPeriod);
    for (const auto& q : quotes)
        EXPECT_NEAR(parRate(curve, q.days, kPeriod), q.rate, 1e-10) << "days=" << q.days;
}

TEST(OisBootstrap, DepositRepricesToItsQuote) {
    const auto quotes = mixedQuotes();
    const YieldCurve curve = bootstrapOis(quotes, kPeriod);
    const double expectedDf = 1.0 / (1.0 + 0.0710 * 28.0 / 360.0);
    EXPECT_NEAR(curve.discountFactor(28.0 / 365.0), expectedDf, 1e-12);
}

TEST(OisBootstrap, PillarsAreDaysOver365) {
    const YieldCurve curve = bootstrapOis(mixedQuotes(), kPeriod);
    ASSERT_EQ(curve.maturities().size(), 8u);
    EXPECT_DOUBLE_EQ(curve.maturities().front(), 28.0 / 365.0);
    EXPECT_DOUBLE_EQ(curve.maturities().back(), 7280.0 / 365.0);
}

TEST(OisBootstrap, ParallelBumpOf10bpLowersEveryDiscountFactor) {
    const YieldCurve base = bootstrapOis(mixedQuotes(0.0), kPeriod);
    const YieldCurve up   = bootstrapOis(mixedQuotes(0.0010), kPeriod);
    for (double t = 0.01; t <= 25.0; t += 0.25)
        EXPECT_LT(up.discountFactor(t), base.discountFactor(t)) << "t=" << t;
}

TEST(OisBootstrap, PaymentDaysSchedule) {
    const auto full = oisPaymentDays(364, 28);
    ASSERT_EQ(full.size(), 13u);
    EXPECT_EQ(full.front(), 28);
    EXPECT_EQ(full.back(), 364);

    EXPECT_EQ(oisPaymentDays(90, 365), (std::vector<int>{90}));
    EXPECT_EQ(oisPaymentDays(400, 365), (std::vector<int>{365, 400}));
}

TEST(OisBootstrap, InvalidInputsThrow) {
    EXPECT_THROW(bootstrapOis({}, kPeriod), std::invalid_argument);
    EXPECT_THROW(bootstrapOis(mixedQuotes(), 0), std::invalid_argument);
    EXPECT_THROW(bootstrapOis(mixedQuotes(), -28), std::invalid_argument);

    std::vector<OisQuote> notIncreasing = mixedQuotes();
    notIncreasing[2].days = notIncreasing[1].days;
    EXPECT_THROW(bootstrapOis(notIncreasing, kPeriod), std::invalid_argument);

    std::vector<OisQuote> zeroDays = mixedQuotes();
    zeroDays[0].days = 0;
    EXPECT_THROW(bootstrapOis(zeroDays, kPeriod), std::invalid_argument);

    EXPECT_THROW(oisPaymentDays(0, 28), std::invalid_argument);
    EXPECT_THROW(oisPaymentDays(364, 0), std::invalid_argument);
}
