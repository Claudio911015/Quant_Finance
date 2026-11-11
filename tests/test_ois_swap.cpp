#include <gtest/gtest.h>
#include <qf/instruments/ois_swap.hpp>
#include <qf/termstructure/ois_bootstrap.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/risk/scenario.hpp>
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <utility>
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

// ---------------------------------------------------------------------------
// Aged / forward-starting swap and compoundOvernight
// ---------------------------------------------------------------------------

namespace {
    using qf::termstructure::oisPaymentDays;

    // Two flat-ish curves: TIIE-F (28-day) up to 1820 days and SOFR (annual) up to 5 years.
    MarketEnvironment twoCurveEnv() {
        MarketEnvironment env;
        env.addCurve("TIIE-F", bootstrapOis(quotes(), kPeriod));
        env.addCurve("SOFR", bootstrapOis({{365,  0.0400, OisQuote::Ois},
                                           {730,  0.0420, OisQuote::Ois},
                                           {1825, 0.0440, OisQuote::Ois}}, 365));
        return env;
    }

    // DF on a curve at an integer day; the valuation date has DF = 1.
    double dfDay(const YieldCurve& c, int day) {
        return day == 0 ? 1.0 : c.discountFactor(day / 365.0);
    }

    // 26 TIIE-F quotes, one every 28 days from 28 to 728 (deposit first, then par OIS).
    YieldCurve tiiefCurve26() {
        std::vector<OisQuote> q;
        for (int k = 1; k <= 26; ++k)
            q.push_back({28 * k, 0.0700 + 0.0004 * k,
                         k == 1 ? OisQuote::Deposit : OisQuote::Ois});
        return bootstrapOis(q, kPeriod);
    }
}

TEST(OisSwapAged, NewConstructorAtStartZeroMatchesTheOldOne) {
    const MarketEnvironment env = twoCurveEnv();
    struct Case { int maturity, period; const char* key; };
    for (const Case& c : {Case{364, 28, "TIIE-F"}, Case{1825, 365, "SOFR"}}) {
        for (SwapType side : {SwapType::Payer, SwapType::Receiver}) {
            const OisSwap oldSwap(kNotional, 0.0690, c.maturity, c.period, side, c.key);
            const OisSwap newSwap(kNotional, 0.0690, 0, oisPaymentDays(c.maturity, c.period), 1.0,
                                  side, c.key);
            const auto rel = [](double a, double b) { return std::abs(a - b) <= 1e-12 * std::abs(b); };
            EXPECT_TRUE(rel(newSwap.npv(env),     oldSwap.npv(env)))     << c.key;
            EXPECT_TRUE(rel(newSwap.parRate(env), oldSwap.parRate(env))) << c.key;
            EXPECT_TRUE(rel(newSwap.annuity(env), oldSwap.annuity(env))) << c.key;
            const auto a = oldSwap.cashFlows(env);
            const auto b = newSwap.cashFlows(env);
            ASSERT_EQ(a.size(), b.size());
            for (std::size_t i = 0; i < a.size(); ++i) {
                EXPECT_EQ(a[i].payDays, b[i].payDays);
                EXPECT_TRUE(rel(b[i].accrual,        a[i].accrual));
                EXPECT_TRUE(rel(b[i].fixedAmount,    a[i].fixedAmount));
                EXPECT_TRUE(rel(b[i].floatAmount,    a[i].floatAmount));
                EXPECT_TRUE(rel(b[i].netAmount,      a[i].netAmount));
                EXPECT_TRUE(rel(b[i].discountFactor, a[i].discountFactor));
                EXPECT_TRUE(rel(b[i].presentValue,   a[i].presentValue));
            }
            EXPECT_EQ(newSwap.maturityDays(), oldSwap.maturityDays());
            EXPECT_DOUBLE_EQ(newSwap.maturity(), oldSwap.maturity());
        }
    }
}

TEST(OisSwapAged, ParRateEqualsTelescopedClosedForm) {
    // Old constructor: sum(float * DF) / annuity must still be N * (1 - DF(T)) / annuity.
    const MarketEnvironment env = twoCurveEnv();
    const OisSwap swap(kNotional, 0.0, 364, kPeriod, SwapType::Payer, "TIIE-F");
    const double dfT = env.curve("TIIE-F").discountFactor(364.0 / 365.0);
    const double expected = kNotional * (1.0 - dfT) / swap.annuity(env);
    EXPECT_NEAR(swap.parRate(env), expected, 1e-12 * expected);
}

TEST(OisSwapAged, CompoundOvernight) {
    EXPECT_DOUBLE_EQ(compoundOvernight({}, {}), 1.0);
    EXPECT_DOUBLE_EQ(compoundOvernight({0.07}, {1}), 1.0 + 0.07 / 360.0);
    EXPECT_DOUBLE_EQ(compoundOvernight({0.07, 0.08}, {1, 2}),
                     (1.0 + 0.07 / 360.0) * (1.0 + 0.08 * 2.0 / 360.0));
    EXPECT_DOUBLE_EQ(compoundOvernight({0.07}, {1}, 365.0), 1.0 + 0.07 / 365.0);
    EXPECT_THROW(compoundOvernight({0.07, 0.07}, {1}), std::invalid_argument);
    EXPECT_THROW(compoundOvernight({0.07}, {0}),       std::invalid_argument);
    EXPECT_THROW(compoundOvernight({0.07}, {-1}),      std::invalid_argument);
    EXPECT_THROW(compoundOvernight({0.07}, {1}, 0.0),  std::invalid_argument);
    EXPECT_THROW(compoundOvernight({0.07}, {1}, -360.0), std::invalid_argument);
    EXPECT_THROW(compoundOvernight({-361.0}, {1}),     std::invalid_argument);   // factor <= 0
}

TEST(OisSwapAged, RolledSwapMatchesOriginalValueRebasedToTheNewDate) {
    // R3. Value at D0 a 364/28 payer struck at par on a 26-pillar TIIE-F curve; age it tau days.
    // Daily fixings are the D0 forwards, so the aged swap on the shifted curve must be worth
    // (npv_D0 - PV_D0 of the flows already paid) / DF0(tau).
    const YieldCurve c0 = tiiefCurve26();
    MarketEnvironment env0;
    env0.addCurve("TIIE-F", c0);

    const OisSwap probe(kNotional, 0.0, 364, kPeriod, SwapType::Payer, "TIIE-F");
    const double par = probe.parRate(env0);
    const OisSwap swap0(kNotional, par + 0.0010, 364, kPeriod, SwapType::Payer, "TIIE-F");
    const std::vector<int> pay0 = oisPaymentDays(364, kPeriod);
    const auto rows0 = swap0.cashFlows(env0);
    const double npv0 = swap0.npv(env0);

    for (int tau : {28, 14}) {
        // Period in course at tau: first payment strictly after tau; it starts at the previous one.
        std::size_t first = 0;
        while (pay0[first] <= tau) ++first;
        const int periodStart = first == 0 ? 0 : pay0[first - 1];

        std::vector<double> fixings;
        for (int k = periodStart; k < tau; ++k)
            fixings.push_back((dfDay(c0, k) / dfDay(c0, k + 1) - 1.0) * 360.0);
        const double accrued = compoundOvernight(fixings, std::vector<int>(fixings.size(), 1));

        double settledPv = 0.0;
        for (std::size_t i = 0; i < first; ++i) settledPv += rows0[i].presentValue;

        // D1 curve with pillars exactly at the remaining payments, shifted by tau.
        std::vector<double> mats, zeros;
        std::vector<int> pay1;
        for (std::size_t i = first; i < pay0.size(); ++i) {
            const double d = pay0[i] / 365.0, t1 = (pay0[i] - tau) / 365.0;
            mats.push_back(t1);
            zeros.push_back((c0.zeroRate(d) * d - c0.zeroRate(tau / 365.0) * (tau / 365.0)) / t1);
            pay1.push_back(pay0[i] - tau);
        }
        MarketEnvironment env1;
        env1.addCurve("TIIE-F", YieldCurve(mats, zeros, qf::math::InterpolationMethod::Linear));

        const OisSwap aged(kNotional, par + 0.0010, periodStart - tau, pay1, accrued,
                           SwapType::Payer, "TIIE-F");
        const double expected = (npv0 - settledPv) / dfDay(c0, tau);
        EXPECT_NEAR(aged.npv(env1), expected, 1e-6 * kNotional) << "tau=" << tau;
        EXPECT_EQ(aged.maturityDays(), 364 - tau);
        EXPECT_EQ(aged.periodDays(), pay1.front() - (periodStart - tau));
    }
}

TEST(OisSwapAged, ForwardStartingSwapDiscountsPeriodOneFromItsStart) {
    const MarketEnvironment env = twoCurveEnv();
    const YieldCurve& c = env.curve("TIIE-F");
    const OisSwap swap(kNotional, 0.0690, 28, {56, 84, 112}, 1.0, SwapType::Payer, "TIIE-F");
    const auto rows = swap.cashFlows(env);
    ASSERT_EQ(rows.size(), 3u);
    EXPECT_EQ(rows[0].payDays, 56);
    EXPECT_DOUBLE_EQ(rows[0].accrual, 28.0 / 360.0);
    EXPECT_NEAR(rows[0].floatAmount, kNotional * (dfDay(c, 28) / dfDay(c, 56) - 1.0), 1e-6);
    EXPECT_NEAR(rows[1].floatAmount, kNotional * (dfDay(c, 56) / dfDay(c, 84) - 1.0), 1e-6);
    EXPECT_EQ(swap.periodDays(), 28);
    EXPECT_EQ(swap.maturityDays(), 112);
}

TEST(OisSwapAged, NewConstructorValidates) {
    const auto make = [](double n, int start, std::vector<int> pay, double acc,
                         DayCountConvention dcc = DayCountConvention::ACT_360) {
        return OisSwap(n, 0.07, start, std::move(pay), acc, SwapType::Payer, "TIIE-F", dcc);
    };
    EXPECT_NO_THROW(make(kNotional, -14, {14, 42}, 1.0007));
    EXPECT_NO_THROW(make(kNotional, 0, {28}, 1.0));
    EXPECT_NO_THROW(make(kNotional, 28, {56}, 1.0));
    EXPECT_THROW(make(0.0, 0, {28}, 1.0),                   std::invalid_argument);   // notional
    EXPECT_THROW(make(-1.0, 0, {28}, 1.0),                  std::invalid_argument);
    EXPECT_THROW(make(kNotional, 0, {}, 1.0),               std::invalid_argument);   // no payments
    EXPECT_THROW(make(kNotional, -30, {0, 28}, 1.0),        std::invalid_argument);   // payDays > 0
    EXPECT_THROW(make(kNotional, -30, {-5, 28}, 1.0),       std::invalid_argument);
    EXPECT_THROW(make(kNotional, 0, {28, 28}, 1.0),         std::invalid_argument);   // strictly increasing
    EXPECT_THROW(make(kNotional, 0, {56, 28}, 1.0),         std::invalid_argument);
    EXPECT_THROW(make(kNotional, 28, {28}, 1.0),            std::invalid_argument);   // startDays < payDays[0]
    EXPECT_THROW(make(kNotional, 40, {28}, 1.0),            std::invalid_argument);
    EXPECT_THROW(make(kNotional, -14, {14}, 0.0),           std::invalid_argument);   // accruedFactor > 0
    EXPECT_THROW(make(kNotional, -14, {14}, -1.0),          std::invalid_argument);
    EXPECT_THROW(make(kNotional, -14, {14}, std::nan("")),  std::invalid_argument);
    EXPECT_THROW(make(kNotional, 0, {28}, 1.0001),          std::invalid_argument);   // == 1 if startDays >= 0
    EXPECT_THROW(make(kNotional, 7, {28}, 1.0001),          std::invalid_argument);
    EXPECT_THROW(make(kNotional, 0, {28}, 1.0, DayCountConvention::THIRTY_360), std::invalid_argument);
}

// ---------------------------------------------------------------------------
// Separate discount curve (QF Desk, corte 3): projection on curveKey, discounting on another curve
// ---------------------------------------------------------------------------

namespace {
    bool relNear(double a, double b, double rel = 1e-12) {
        return std::abs(a - b) <= rel * std::abs(b);
    }

    // Environment the goldens below were captured on: 26-pillar TIIE-F and the SOFR of twoCurveEnv().
    MarketEnvironment goldenEnv() {
        MarketEnvironment env = twoCurveEnv();
        env.addCurve("TIIE-F", tiiefCurve26());
        return env;
    }

    // npv / parRate / annuity of the swaps below, captured from the build that predates the
    // discount-curve key (goldenEnv(), K = 6.90 %, N = 1e8; aged: start -10, factor 1.0003): the old behaviour, to 1e-12.
    struct Golden { const char* key; int maturity, period; SwapType side;
                    double npv, par, annuity, agedNpv, agedPar, agedAnnuity; };
    const Golden kGolden[] = {
        {"TIIE-F", 364,  28,  SwapType::Payer,
         602467.95619263477, 0.075199999999999975, 97172250.998812735,
         441845.05580718879, 0.073421328766652597, 99934901.72903657},
        {"TIIE-F", 364,  28,  SwapType::Receiver,
         -602467.95619263477, 0.075199999999999975, 97172250.998812735,
         -441845.05580718879, 0.073421328766652597, 99934901.72903657},
        {"SOFR",   1825, 365, SwapType::Payer,
         -11169260.695901666, 0.043999999999999997, 446770427.83606654,
         -11323457.172142982, 0.043805405318128786, 449439941.98449153},
        {"SOFR",   1825, 365, SwapType::Receiver,
         11169260.695901666, 0.043999999999999997, 446770427.83606654,
         11323457.172142982, 0.043805405318128786, 449439941.98449153},
    };

    // Expected value of an OIS swap by hand: sum of (projected floating - fixed) * DF of the discount curve.
    double handNpv(const YieldCurve& proj, const YieldCurve& disc, SwapType side, double rate,
                   int startDays, const std::vector<int>& pay, double accrued) {
        const double sign = side == SwapType::Payer ? 1.0 : -1.0;
        double total = 0.0;
        int prev = startDays;
        for (std::size_t i = 0; i < pay.size(); ++i) {
            const double tau   = (pay[i] - prev) / 360.0;
            const double fl    = kNotional * ((i == 0 ? accrued : 1.0) * dfDay(proj, std::max(prev, 0))
                                              / dfDay(proj, pay[i]) - 1.0);
            total += sign * (fl - kNotional * rate * tau) * dfDay(disc, pay[i]);
            prev = pay[i];
        }
        return total;
    }
}

TEST(OisSwapDiscountCurve, NoKeyEmptyKeyOrSameKeyReproduceTheSingleCurveSwap) {
    // R4 retrocompat: golden values from before the change, and the three spellings agree.
    const MarketEnvironment env = goldenEnv();
    for (const Golden& g : kGolden) {
        const std::string key = g.key;
        const auto pay = oisPaymentDays(g.maturity, g.period);
        const OisSwap plain(kNotional, 0.0690, g.maturity, g.period, g.side, key);
        const OisSwap empty(kNotional, 0.0690, g.maturity, g.period, g.side, key,
                            DayCountConvention::ACT_360, "");
        const OisSwap same (kNotional, 0.0690, g.maturity, g.period, g.side, key,
                            DayCountConvention::ACT_360, key);
        const OisSwap agedPlain(kNotional, 0.0690, -10, pay, 1.0003, g.side, key);
        const OisSwap agedSame (kNotional, 0.0690, -10, pay, 1.0003, g.side, key,
                                DayCountConvention::ACT_360, key);
        EXPECT_EQ(plain.discountCurveKey(), key);
        EXPECT_EQ(empty.discountCurveKey(), key);
        EXPECT_EQ(same.discountCurveKey(),  key);
        for (const OisSwap* s : {&plain, &empty, &same}) {
            EXPECT_TRUE(relNear(s->npv(env),     g.npv))     << key;
            EXPECT_TRUE(relNear(s->parRate(env), g.par))     << key;
            EXPECT_TRUE(relNear(s->annuity(env), g.annuity)) << key;
        }
        for (const OisSwap* s : {&agedPlain, &agedSame}) {
            EXPECT_TRUE(relNear(s->npv(env),     g.agedNpv))     << key;
            EXPECT_TRUE(relNear(s->parRate(env), g.agedPar))     << key;
            EXPECT_TRUE(relNear(s->annuity(env), g.agedAnnuity)) << key;
        }
        const auto a = plain.cashFlows(env);
        const auto b = same.cashFlows(env);
        ASSERT_EQ(a.size(), b.size());
        for (std::size_t i = 0; i < a.size(); ++i) {
            EXPECT_EQ(a[i].payDays, b[i].payDays);
            EXPECT_TRUE(relNear(b[i].floatAmount,    a[i].floatAmount))    << key << " row " << i;
            EXPECT_TRUE(relNear(b[i].discountFactor, a[i].discountFactor)) << key << " row " << i;
            EXPECT_TRUE(relNear(b[i].presentValue,   a[i].presentValue))   << key << " row " << i;
        }
    }
}

TEST(OisSwapDiscountCurve, OtherDiscountCurveDiscountsEveryFlowAndKeepsTheProjection) {
    MarketEnvironment env = twoCurveEnv();
    env.addCurve("TIIE-F-30", env.curve("TIIE-F").parallelBump(-30.0));   // TIIE-F - 30 bp
    const YieldCurve& proj = env.curve("TIIE-F");
    const YieldCurve& disc = env.curve("TIIE-F-30");
    const std::vector<int> pay = oisPaymentDays(364, kPeriod);

    for (SwapType side : {SwapType::Payer, SwapType::Receiver}) {
        const OisSwap two (kNotional, 0.0690, 364, kPeriod, side, "TIIE-F",
                           DayCountConvention::ACT_360, "TIIE-F-30");
        const OisSwap one (kNotional, 0.0690, 364, kPeriod, side, "TIIE-F");
        EXPECT_EQ(two.curveKey(), "TIIE-F");
        EXPECT_EQ(two.discountCurveKey(), "TIIE-F-30");
        EXPECT_NEAR(two.npv(env), handNpv(proj, disc, side, 0.0690, 0, pay, 1.0), 1e-10 * kNotional);
        EXPECT_GT(std::abs(two.npv(env) - one.npv(env)), 1.0);   // the discount curve matters

        // Rows: floating coupons come from the projection curve, DFs from the discount curve.
        const auto rows2 = two.cashFlows(env);
        const auto rows1 = one.cashFlows(env);
        ASSERT_EQ(rows2.size(), rows1.size());
        double sum = 0.0;
        for (std::size_t i = 0; i < rows2.size(); ++i) {
            EXPECT_TRUE(relNear(rows2[i].floatAmount, rows1[i].floatAmount));
            EXPECT_TRUE(relNear(rows2[i].discountFactor, dfDay(disc, rows2[i].payDays)));
            sum += rows2[i].presentValue;
        }
        EXPECT_NEAR(sum, two.npv(env), 1e-12 * std::abs(two.npv(env)));

        // Annuity on the discount curve; par rate = discounted floating / annuity, and a swap at that rate is worth 0.
        double ann = 0.0, floatPv = 0.0;
        int prev = 0;
        for (int d : pay) {
            ann += kNotional * ((d - prev) / 360.0) * dfDay(disc, d);
            floatPv += kNotional * (dfDay(proj, prev) / dfDay(proj, d) - 1.0) * dfDay(disc, d);
            prev = d;
        }
        EXPECT_TRUE(relNear(two.annuity(env), ann));
        EXPECT_NEAR(two.parRate(env), floatPv / ann, 1e-12);
        const OisSwap atPar(kNotional, two.parRate(env), 364, kPeriod, side, "TIIE-F",
                            DayCountConvention::ACT_360, "TIIE-F-30");
        EXPECT_LT(std::abs(atPar.npv(env)), 1e-10 * kNotional);
    }
}

TEST(OisSwapDiscountCurve, AgedConstructorAcceptsTheDiscountCurve) {
    MarketEnvironment env = twoCurveEnv();
    env.addCurve("TIIE-F-30", env.curve("TIIE-F").parallelBump(-30.0));
    const std::vector<int> pay = {14, 42, 70, 98};
    const OisSwap aged(kNotional, 0.0690, -14, pay, 1.0007, SwapType::Receiver, "TIIE-F",
                       DayCountConvention::ACT_360, "TIIE-F-30");
    EXPECT_EQ(aged.discountCurveKey(), "TIIE-F-30");
    EXPECT_NEAR(aged.npv(env),
                handNpv(env.curve("TIIE-F"), env.curve("TIIE-F-30"), SwapType::Receiver, 0.0690,
                        -14, pay, 1.0007),
                1e-10 * kNotional);
}

TEST(OisSwapDiscountCurve, MissingDiscountCurveThrows) {
    const MarketEnvironment env = twoCurveEnv();
    const OisSwap swap(kNotional, 0.0690, 364, kPeriod, SwapType::Payer, "TIIE-F",
                       DayCountConvention::ACT_360, "NOPE");
    EXPECT_THROW(swap.npv(env),      std::out_of_range);
    EXPECT_THROW(swap.annuity(env),  std::out_of_range);
    EXPECT_THROW(swap.parRate(env),  std::out_of_range);
}
