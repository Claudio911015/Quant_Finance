#include <gtest/gtest.h>
#include <qf/instruments/ois_swap.hpp>
#include <qf/termstructure/ois_bootstrap.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/risk/scenario.hpp>
#include <cmath>
#include <vector>

using namespace qf::instruments;
using qf::core::MarketEnvironment;
using qf::math::DayCountConvention;
using qf::termstructure::OisQuote;
using qf::termstructure::YieldCurve;
using qf::termstructure::bootstrapOis;

namespace {
    constexpr double kNotional = 100e6;
    constexpr int    kPeriod   = 28;

    std::vector<OisQuote> quotes() {
        return {
            {28,   0.0710, OisQuote::Deposit},
            {84,   0.0715, OisQuote::Ois},
            {168,  0.0720, OisQuote::Ois},
            {364,  0.0730, OisQuote::Ois},
            {728,  0.0750, OisQuote::Ois},
            {1820, 0.0780, OisQuote::Ois},
        };
    }

    MarketEnvironment tiiefEnv() {
        MarketEnvironment env;
        env.addCurve("TIIE-F", bootstrapOis(quotes(), kPeriod));
        return env;
    }
}

TEST(OisSwap, NpvAtParRateIsZero) {
    const MarketEnvironment env = tiiefEnv();
    for (int days : {28, 100, 364, 1820}) {
        const OisSwap probe(kNotional, 0.0, days, kPeriod, SwapType::Payer, "TIIE-F");
        const double par = probe.parRate(env);
        const OisSwap payer(kNotional, par, days, kPeriod, SwapType::Payer, "TIIE-F");
        const OisSwap receiver(kNotional, par, days, kPeriod, SwapType::Receiver, "TIIE-F");
        EXPECT_LT(std::abs(payer.npv(env)),    1e-10 * kNotional) << "days=" << days;
        EXPECT_LT(std::abs(receiver.npv(env)), 1e-10 * kNotional) << "days=" << days;
    }
}

TEST(OisSwap, SwapStruckAtBootstrapQuoteIsWorthZero) {
    // Closes the loop with bootstrapOis: same schedule, same ACT/360 accrual, same t = days/365.
    const MarketEnvironment env = tiiefEnv();
    for (const OisQuote& q : quotes()) {
        if (q.type != OisQuote::Ois) continue;
        const OisSwap swap(kNotional, q.rate, q.days, kPeriod, SwapType::Payer, "TIIE-F");
        EXPECT_LT(std::abs(swap.npv(env)), 1e-10 * kNotional) << "days=" << q.days;
        EXPECT_NEAR(swap.parRate(env), q.rate, 1e-10) << "days=" << q.days;
    }
}

TEST(OisSwap, CashFlowPresentValuesSumToNpv) {
    const MarketEnvironment env = tiiefEnv();
    const OisSwap swap(kNotional, 0.0690, 364, kPeriod, SwapType::Payer, "TIIE-F");
    double sum = 0.0;
    for (const OisCashFlow& row : swap.cashFlows(env)) sum += row.presentValue;
    const double npv = swap.npv(env);
    EXPECT_NEAR(sum, npv, 1e-12 * std::abs(npv));
}

TEST(OisSwap, NpvMatchesClosedFormFloatMinusFixed) {
    // Independent of the cash-flow table: payer NPV = N*(1 - DF(T)) - K*annuity.
    const MarketEnvironment env = tiiefEnv();
    const double K = 0.0690;
    const OisSwap payer(kNotional, K, 364, kPeriod, SwapType::Payer, "TIIE-F");
    const double dfT = env.curve("TIIE-F").discountFactor(364.0 / 365.0);
    const double expected = kNotional * (1.0 - dfT) - K * payer.annuity(env);
    EXPECT_NEAR(payer.npv(env), expected, 1e-12 * std::abs(expected));
}

TEST(OisSwap, PayerIsMinusReceiver) {
    const MarketEnvironment env = tiiefEnv();
    const OisSwap payer(kNotional, 0.0690, 728, kPeriod, SwapType::Payer, "TIIE-F");
    const OisSwap receiver(kNotional, 0.0690, 728, kPeriod, SwapType::Receiver, "TIIE-F");
    EXPECT_NEAR(payer.npv(env), -receiver.npv(env), 1e-9);
    const auto p = payer.cashFlows(env);
    const auto r = receiver.cashFlows(env);
    ASSERT_EQ(p.size(), r.size());
    for (std::size_t i = 0; i < p.size(); ++i)
        EXPECT_DOUBLE_EQ(p[i].netAmount, -r[i].netAmount);
}

TEST(OisSwap, ThirteenFlowsFor364Days) {
    const MarketEnvironment env = tiiefEnv();
    const OisSwap swap(kNotional, 0.0690, 364, kPeriod, SwapType::Payer, "TIIE-F");
    const auto rows = swap.cashFlows(env);
    ASSERT_EQ(rows.size(), 13u);
    EXPECT_EQ(rows.front().payDays, 28);
    EXPECT_EQ(rows.back().payDays, 364);
    EXPECT_DOUBLE_EQ(rows.front().payTime, 28.0 / 365.0);
    EXPECT_DOUBLE_EQ(rows.front().accrual, 28.0 / 360.0);
    EXPECT_DOUBLE_EQ(rows.front().fixedAmount, kNotional * 0.0690 * 28.0 / 360.0);
    EXPECT_DOUBLE_EQ(swap.maturity(), 364.0 / 365.0);
}

TEST(OisSwap, FloatCouponIsReplicationForwardRatio) {
    const MarketEnvironment env = tiiefEnv();
    const OisSwap swap(kNotional, 0.0690, 84, kPeriod, SwapType::Payer, "TIIE-F");
    const auto rows = swap.cashFlows(env);
    const YieldCurve& c = env.curve("TIIE-F");
    // First period: previous DF is 1 (valuation date).
    EXPECT_NEAR(rows[0].floatAmount, kNotional * (1.0 / c.discountFactor(28.0 / 365.0) - 1.0), 1e-6);
    EXPECT_NEAR(rows[1].floatAmount,
                kNotional * (c.discountFactor(28.0 / 365.0) / c.discountFactor(56.0 / 365.0) - 1.0), 1e-6);
}

TEST(OisSwap, ShortFinalPeriodAccruesActualDays) {
    // SOFR-style annual coupons with a 400-day maturity: 365 days then a 35-day stub.
    MarketEnvironment env;
    env.addCurve("SOFR", bootstrapOis({{365, 0.04, OisQuote::Ois}, {730, 0.042, OisQuote::Ois}}, 365));
    const OisSwap swap(kNotional, 0.04, 400, 365, SwapType::Payer, "SOFR");
    const auto rows = swap.cashFlows(env);
    ASSERT_EQ(rows.size(), 2u);
    EXPECT_EQ(rows[0].payDays, 365);
    EXPECT_EQ(rows[1].payDays, 400);
    EXPECT_DOUBLE_EQ(rows[0].accrual, 365.0 / 360.0);
    EXPECT_DOUBLE_EQ(rows[1].accrual, 35.0 / 360.0);
}

TEST(OisSwap, AccrualConventionChangesFixedLeg) {
    const MarketEnvironment env = tiiefEnv();
    const OisSwap act360(kNotional, 0.0690, 364, kPeriod, SwapType::Payer, "TIIE-F",
                         DayCountConvention::ACT_360);
    const OisSwap act365(kNotional, 0.0690, 364, kPeriod, SwapType::Payer, "TIIE-F",
                         DayCountConvention::ACT_365);
    EXPECT_DOUBLE_EQ(act365.cashFlows(env).front().accrual, 28.0 / 365.0);
    EXPECT_LT(act365.annuity(env), act360.annuity(env));
}

TEST(OisSwap, ReceiverHasPositiveParallelDv01AndPayerNegative) {
    const MarketEnvironment env = tiiefEnv();
    const OisSwap receiver(kNotional, 0.0690, 728, kPeriod, SwapType::Receiver, "TIIE-F");
    const OisSwap payer(kNotional, 0.0690, 728, kPeriod, SwapType::Payer, "TIIE-F");
    const qf::risk::ScenarioEngine engine("TIIE-F");
    EXPECT_GT(engine.parallelDV01(receiver, env), 0.0);
    EXPECT_LT(engine.parallelDV01(payer, env), 0.0);
}

TEST(OisSwap, MissingCurveThrows) {
    const OisSwap swap(kNotional, 0.0690, 364, kPeriod, SwapType::Payer, "SOFR");
    EXPECT_THROW(swap.npv(tiiefEnv()), std::out_of_range);
}

TEST(OisSwap, InvalidInputsThrow) {
    EXPECT_THROW(OisSwap(0.0,       0.07, 364, 28, SwapType::Payer, "TIIE-F"), std::invalid_argument);
    EXPECT_THROW(OisSwap(-1.0,      0.07, 364, 28, SwapType::Payer, "TIIE-F"), std::invalid_argument);
    EXPECT_THROW(OisSwap(kNotional, 0.07, 0,   28, SwapType::Payer, "TIIE-F"), std::invalid_argument);
    EXPECT_THROW(OisSwap(kNotional, 0.07, -28, 28, SwapType::Payer, "TIIE-F"), std::invalid_argument);
    EXPECT_THROW(OisSwap(kNotional, 0.07, 364, 0,  SwapType::Payer, "TIIE-F"), std::invalid_argument);
    EXPECT_THROW(OisSwap(kNotional, 0.07, 364, 28, SwapType::Payer, "TIIE-F",
                         DayCountConvention::THIRTY_360), std::invalid_argument);
}
