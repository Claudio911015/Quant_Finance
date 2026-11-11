#include <gtest/gtest.h>
#include <qf/instruments/xccy_swap.hpp>
#include <qf/instruments/ois_swap.hpp>
#include <qf/termstructure/ois_bootstrap.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/core/market_environment.hpp>
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using namespace qf::instruments;
using qf::core::MarketEnvironment;
using qf::math::DayCountConvention;
using qf::math::InterpolationMethod;
using qf::termstructure::YieldCurve;
using qf::termstructure::oisPaymentDays;

namespace {
    constexpr double kNotionalUsd = 1e7;
    constexpr double kFx          = 18.5;   // rate fixed at inception
    constexpr double kSpot        = 18.0;   // spot at valuation: different on purpose
    constexpr double kSpread      = -0.0012;
    constexpr int    kPeriod      = 28;

    // Three curves with a pillar every 28 days up to 728 (linear zeros, t = days / 365).
    YieldCurve curve26(double base, double step) {
        std::vector<double> mats, zeros;
        for (int k = 1; k <= 26; ++k) {
            mats.push_back(28.0 * k / 365.0);
            zeros.push_back(base + step * k);
        }
        return YieldCurve(mats, zeros, InterpolationMethod::Linear);
    }
    YieldCurve sofr0()   { return curve26(0.0400, 0.00015); }
    YieldCurve tiief0()  { return curve26(0.0700, 0.00040); }
    YieldCurve mxnUsd0() { return curve26(0.0640, 0.00030); }   // USD-collateral MXN curve, below TIIE-F

    MarketEnvironment env3(double spot = kSpot) {
        MarketEnvironment env;
        env.addCurve("SOFR",    sofr0());
        env.addCurve("TIIE-F",  tiief0());
        env.addCurve("MXN-USD", mxnUsd0());
        env.setSpot("USDMXN", spot);
        return env;
    }

    double dfDay(const YieldCurve& c, int day) {
        return day == 0 ? 1.0 : c.discountFactor(day / 365.0);
    }

    XccySwap make(XccySide side, double spread = kSpread, bool initial = true, bool fin = true,
                  int start = 0, std::vector<int> pay = oisPaymentDays(364, kPeriod),
                  double fx = kFx, double accUsd = 1.0, double accMxn = 1.0) {
        return XccySwap(kNotionalUsd, fx, spread, start, std::move(pay), accUsd, accMxn, side,
                        initial, fin);
    }

    double nm() { return kNotionalUsd * kFx; }
    bool relNear(double a, double b, double rel = 1e-12) { return std::abs(a - b) <= rel * std::abs(b); }
}

TEST(XccySwap, ParSpreadMakesTheValueZero) {
    const MarketEnvironment env = env3();
    struct Case { int start; std::vector<int> pay; double accUsd, accMxn; bool initial; };
    const std::vector<Case> cases = {
        {0,   oisPaymentDays(364, kPeriod),  1.0,    1.0,    true},    // at inception
        {28,  {56, 84, 112},                 1.0,    1.0,    true},    // forward starting
        {-14, {14, 42, 70, 98},              1.0006, 1.0004, true},    // aged (initial exchange already happened)
    };
    for (const Case& c : cases) {
        for (XccySide side : {XccySide::PayUsd, XccySide::PayMxn}) {
            const XccySwap probe = make(side, 0.0, c.initial, true, c.start, c.pay, kFx, c.accUsd, c.accMxn);
            const double par = probe.parSpread(env);
            const XccySwap atPar = make(side, par, c.initial, true, c.start, c.pay, kFx, c.accUsd, c.accMxn);
            EXPECT_LT(std::abs(atPar.npv(env)), 1e-8 * nm()) << "start=" << c.start;
            // The par spread does not depend on the spread the swap was struck at nor on the side.
            const XccySwap other = make(XccySide::PayUsd, 0.0123, c.initial, true, c.start, c.pay,
                                        kFx, c.accUsd, c.accMxn);
            EXPECT_NEAR(other.parSpread(env), par, 1e-12) << "start=" << c.start;
            EXPECT_NEAR(atPar.parSpread(env), par, 1e-12);
        }
    }
}

TEST(XccySwap, ValueIsLinearInTheSpreadWithTheMxnAnnuity) {
    const MarketEnvironment env = env3();
    const YieldCurve md = mxnUsd0();
    double annuity = 0.0;
    int prev = 0;
    for (int d : oisPaymentDays(364, kPeriod)) { annuity += (d - prev) / 360.0 * dfDay(md, d); prev = d; }
    const double v0 = make(XccySide::PayUsd, 0.0).npv(env);
    const double v1 = make(XccySide::PayUsd, 0.0050).npv(env);
    EXPECT_NEAR(v1 - v0, nm() * 0.0050 * annuity, 1e-9 * nm());
}

TEST(XccySwap, PayUsdIsMinusPayMxn) {
    const MarketEnvironment env = env3();
    const XccySwap a = make(XccySide::PayUsd);
    const XccySwap b = make(XccySide::PayMxn);
    EXPECT_TRUE(relNear(a.npv(env), -b.npv(env)));
    const auto ra = a.cashFlows(env);
    const auto rb = b.cashFlows(env);
    ASSERT_EQ(ra.size(), rb.size());
    for (std::size_t i = 0; i < ra.size(); ++i) {
        EXPECT_EQ(ra[i].leg, rb[i].leg);
        EXPECT_EQ(ra[i].payDays, rb[i].payDays);
        EXPECT_TRUE(relNear(ra[i].amount, -rb[i].amount));
        EXPECT_TRUE(relNear(ra[i].presentValueMxn, -rb[i].presentValueMxn));
    }
}

TEST(XccySwap, FinalExchangeChangesTheValueByTheDiscountedNotionals) {
    const MarketEnvironment env = env3();
    const YieldCurve su = sofr0(), md = mxnUsd0();
    const int T = oisPaymentDays(364, kPeriod).back();
    const double legs = nm() * dfDay(md, T) - kSpot * kNotionalUsd * dfDay(su, T);
    for (XccySide side : {XccySide::PayUsd, XccySide::PayMxn}) {
        const double sign = side == XccySide::PayUsd ? 1.0 : -1.0;
        const double with    = make(side, kSpread, true, true).npv(env);
        const double without = make(side, kSpread, true, false).npv(env);
        EXPECT_NEAR(with - without, sign * legs, 1e-9 * nm());
    }
}

TEST(XccySwap, InitialExchangeChangesTheValueByTheNotionalsAtTheStartDate) {
    const MarketEnvironment env = env3();
    const YieldCurve su = sofr0(), md = mxnUsd0();
    for (int start : {0, 28}) {
        std::vector<int> pay;
        for (int d : oisPaymentDays(364, kPeriod)) if (d > start) pay.push_back(d);
        // The initial exchange pays N_M and receives S * N_U on the start date (PayUsd view).
        const double legs = -nm() * dfDay(md, start) + kSpot * kNotionalUsd * dfDay(su, start);
        for (XccySide side : {XccySide::PayUsd, XccySide::PayMxn}) {
            const double sign = side == XccySide::PayUsd ? 1.0 : -1.0;
            const double with    = make(side, kSpread, true,  true, start, pay).npv(env);
            const double without = make(side, kSpread, false, true, start, pay).npv(env);
            EXPECT_NEAR(with - without, sign * legs, 1e-9 * nm()) << "start=" << start;
        }
    }
    // Once the swap has started (startDays < 0) the initial exchange is in the past: the flag is moot.
    const std::vector<int> pay = {14, 42, 70};
    EXPECT_DOUBLE_EQ(make(XccySide::PayUsd, kSpread, true,  true, -14, pay, kFx, 1.0003, 1.0002).npv(env),
                     make(XccySide::PayUsd, kSpread, false, true, -14, pay, kFx, 1.0003, 1.0002).npv(env));
}

TEST(XccySwap, AtTheSpotWithOneCurvePerLegAndNoSpreadItIsWorthZero) {
    // fxRate = S, MXN leg projected and discounted on TIIE-F, no spread: each leg is a par floater.
    MarketEnvironment env = env3(kFx);
    for (XccySide side : {XccySide::PayUsd, XccySide::PayMxn}) {
        const XccySwap swap(kNotionalUsd, kFx, 0.0, 0, oisPaymentDays(364, kPeriod), 1.0, 1.0, side,
                            true, true, "SOFR", "TIIE-F", "TIIE-F");
        EXPECT_LT(std::abs(swap.npv(env)), 1e-8 * nm());
    }
}

TEST(XccySwap, ManualValueOfATwoPeriodSwap) {
    // Independent of the cash-flow table: the MXN leg projects on TIIE-F and discounts on MXN-USD.
    const MarketEnvironment env = env3();
    const YieldCurve su = sofr0(), tp = tiief0(), md = mxnUsd0();
    const double s = 0.0025;
    const XccySwap swap(kNotionalUsd, kFx, s, 0, {28, 56}, 1.0, 1.0, XccySide::PayUsd, true, true);
    const double t1 = 28.0 / 360.0, t2 = 28.0 / 360.0;
    const double mxn = -nm()
        + (nm() * (1.0 / dfDay(tp, 28) - 1.0) + nm() * s * t1) * dfDay(md, 28)
        + (nm() * (dfDay(tp, 28) / dfDay(tp, 56) - 1.0) + nm() * s * t2) * dfDay(md, 56)
        + nm() * dfDay(md, 56);
    const double usd = -kNotionalUsd
        + kNotionalUsd * (1.0 / dfDay(su, 28) - 1.0) * dfDay(su, 28)
        + kNotionalUsd * (dfDay(su, 28) / dfDay(su, 56) - 1.0) * dfDay(su, 56)
        + kNotionalUsd * dfDay(su, 56);
    EXPECT_NEAR(swap.npv(env), mxn - kSpot * usd, 1e-9 * nm());
    EXPECT_NEAR(usd, 0.0, 1e-9 * kNotionalUsd);   // the USD leg alone is a par floater
}

TEST(XccySwap, CashFlowTableSumsToNpvAndIsOrderedByDate) {
    const MarketEnvironment env = env3();
    const std::vector<int> pay = oisPaymentDays(364, kPeriod);
    const XccySwap swap = make(XccySide::PayUsd);
    const auto rows = swap.cashFlows(env);
    ASSERT_EQ(rows.size(), 2 * (pay.size() + 2));   // two legs x (initial + coupons + final)

    double sum = 0.0;
    for (std::size_t i = 0; i < rows.size(); ++i) {
        sum += rows[i].presentValueMxn;
        if (i > 0) EXPECT_GE(rows[i].payDays, rows[i - 1].payDays);
        EXPECT_TRUE(rows[i].leg == "USD" || rows[i].leg == "MXN");
        EXPECT_TRUE(rows[i].kind == "coupon" || rows[i].kind == "exchange");
        EXPECT_DOUBLE_EQ(rows[i].presentValue, rows[i].amount * rows[i].discountFactor);
        EXPECT_DOUBLE_EQ(rows[i].presentValueMxn,
                         rows[i].leg == "USD" ? rows[i].presentValue * kSpot : rows[i].presentValue);
        if (rows[i].kind == "exchange") EXPECT_DOUBLE_EQ(rows[i].accrual, 0.0);
        else                            EXPECT_GT(rows[i].accrual, 0.0);
    }
    EXPECT_NEAR(sum, swap.npv(env), 1e-12 * std::max(1.0, std::abs(swap.npv(env))) + 1e-6);
    EXPECT_DOUBLE_EQ(swap.calculatePV(env), swap.npv(env));

    // Layout: initial exchanges (USD then MXN) at day 0, then USD/MXN coupon pairs, then the final
    // exchanges at the last day after the last coupons.
    EXPECT_EQ(rows[0].leg, "USD");  EXPECT_EQ(rows[0].kind, "exchange");  EXPECT_EQ(rows[0].payDays, 0);
    EXPECT_EQ(rows[1].leg, "MXN");  EXPECT_EQ(rows[1].kind, "exchange");  EXPECT_EQ(rows[1].payDays, 0);
    EXPECT_EQ(rows[2].leg, "USD");  EXPECT_EQ(rows[2].kind, "coupon");    EXPECT_EQ(rows[2].payDays, 28);
    EXPECT_EQ(rows[3].leg, "MXN");  EXPECT_EQ(rows[3].kind, "coupon");    EXPECT_EQ(rows[3].payDays, 28);
    const std::size_t n = rows.size();
    EXPECT_EQ(rows[n - 4].leg, "USD");  EXPECT_EQ(rows[n - 4].kind, "coupon");
    EXPECT_EQ(rows[n - 3].leg, "USD");  EXPECT_EQ(rows[n - 3].kind, "exchange");
    EXPECT_EQ(rows[n - 2].leg, "MXN");  EXPECT_EQ(rows[n - 2].kind, "coupon");
    EXPECT_EQ(rows[n - 1].leg, "MXN");  EXPECT_EQ(rows[n - 1].kind, "exchange");
    EXPECT_EQ(rows[n - 1].payDays, pay.back());

    // Signs from the PayUsd holder: borrows USD (receives N_U) and lends MXN (pays N_M) at the start,
    // and the reverse at the end; USD coupons are paid (negative), MXN coupons received (positive).
    EXPECT_DOUBLE_EQ(rows[0].amount,  kNotionalUsd);
    EXPECT_DOUBLE_EQ(rows[1].amount, -nm());
    EXPECT_DOUBLE_EQ(rows[n - 3].amount, -kNotionalUsd);
    EXPECT_DOUBLE_EQ(rows[n - 1].amount,  nm());
    EXPECT_LT(rows[2].amount, 0.0);
    EXPECT_GT(rows[3].amount, 0.0);
    EXPECT_DOUBLE_EQ(rows[0].discountFactor, 1.0);
}

namespace {
    // Curve rolled forward by tau days so that its pillars sit exactly at the remaining payments.
    YieldCurve rolled(const YieldCurve& c0, const std::vector<int>& pay0, std::size_t first, int tau) {
        std::vector<double> mats, zeros;
        for (std::size_t i = first; i < pay0.size(); ++i) {
            const double d = pay0[i] / 365.0, t1 = (pay0[i] - tau) / 365.0;
            mats.push_back(t1);
            zeros.push_back((c0.zeroRate(d) * d - c0.zeroRate(tau / 365.0) * (tau / 365.0)) / t1);
        }
        return YieldCurve(mats, zeros, InterpolationMethod::Linear);
    }

    // Compounded overnight factor over [from, to) with the daily forwards implied by c0.
    double impliedFactor(const YieldCurve& c0, int from, int to) {
        std::vector<double> fixings;
        for (int k = from; k < to; ++k)
            fixings.push_back((dfDay(c0, k) / dfDay(c0, k + 1) - 1.0) * 360.0);
        return compoundOvernight(fixings, std::vector<int>(fixings.size(), 1));
    }

    double legPv(const std::vector<XccyCashFlow>& rows, const std::string& leg, int uptoDay = 100000) {
        double s = 0.0;
        for (const XccyCashFlow& r : rows) if (r.leg == leg && r.payDays <= uptoDay) s += r.presentValue;
        return s;
    }
}

TEST(XccySwap, AgedSwapMatchesTheOriginalValueRebasedToTheNewDatePerLeg) {
    // Same identity as the OisSwap R3 test, leg by leg in its own currency (no spot): with curves
    // rolled consistently and implied daily fixings, PV_D1 = (PV_D0 - PV_D0 of flows already paid) / DF0(tau).
    const YieldCurve su0 = sofr0(), tp0 = tiief0(), md0 = mxnUsd0();
    MarketEnvironment env0 = env3();
    const std::vector<int> pay0 = oisPaymentDays(364, kPeriod);

    for (XccySide side : {XccySide::PayUsd, XccySide::PayMxn}) {
        const XccySwap swap0 = make(side, kSpread);
        const auto rows0 = swap0.cashFlows(env0);

        for (int tau : {14, 28}) {
            std::size_t first = 0;
            while (pay0[first] <= tau) ++first;   // first payment strictly after tau
            const int periodStart = first == 0 ? 0 : pay0[first - 1];

            std::vector<int> pay1;
            for (std::size_t i = first; i < pay0.size(); ++i) pay1.push_back(pay0[i] - tau);
            MarketEnvironment env1;
            env1.addCurve("SOFR",    rolled(su0, pay0, first, tau));
            env1.addCurve("TIIE-F",  rolled(tp0, pay0, first, tau));
            env1.addCurve("MXN-USD", rolled(md0, pay0, first, tau));
            env1.setSpot("USDMXN", kSpot);

            // A period that starts exactly today carries no initial exchange (it is a roll, not a start).
            const XccySwap aged(kNotionalUsd, kFx, kSpread, periodStart - tau, pay1,
                                impliedFactor(su0, periodStart, tau), impliedFactor(tp0, periodStart, tau),
                                side, periodStart - tau < 0, true);
            const auto rows1 = aged.cashFlows(env1);

            const double expUsd = (legPv(rows0, "USD") - legPv(rows0, "USD", tau)) / dfDay(su0, tau);
            const double expMxn = (legPv(rows0, "MXN") - legPv(rows0, "MXN", tau)) / dfDay(md0, tau);
            EXPECT_NEAR(legPv(rows1, "USD"), expUsd, 1e-6 * kNotionalUsd) << "tau=" << tau;
            EXPECT_NEAR(legPv(rows1, "MXN"), expMxn, 1e-6 * nm())         << "tau=" << tau;
            EXPECT_EQ(aged.maturity() * 365.0, pay1.back());
        }
    }
}

TEST(XccySwap, Accessors) {
    const XccySwap swap = make(XccySide::PayMxn, 0.0015);
    EXPECT_DOUBLE_EQ(swap.notionalUsd(), kNotionalUsd);
    EXPECT_DOUBLE_EQ(swap.notionalMxn(), kNotionalUsd * kFx);
    EXPECT_DOUBLE_EQ(swap.fxRate(), kFx);
    EXPECT_DOUBLE_EQ(swap.spread(), 0.0015);
    EXPECT_EQ(swap.side(), XccySide::PayMxn);
    EXPECT_EQ(swap.payDays(), oisPaymentDays(364, kPeriod));
}

TEST(XccySwap, MissingCurveOrSpotThrows) {
    MarketEnvironment noSpot;
    noSpot.addCurve("SOFR", sofr0()); noSpot.addCurve("TIIE-F", tiief0()); noSpot.addCurve("MXN-USD", mxnUsd0());
    EXPECT_THROW(make(XccySide::PayUsd).npv(noSpot), std::out_of_range);
    MarketEnvironment noBasis;
    noBasis.addCurve("SOFR", sofr0()); noBasis.addCurve("TIIE-F", tiief0()); noBasis.setSpot("USDMXN", kSpot);
    EXPECT_THROW(make(XccySide::PayUsd).npv(noBasis), std::out_of_range);
    EXPECT_THROW(make(XccySide::PayUsd).parSpread(noBasis), std::out_of_range);
}

TEST(XccySwap, ConstructorValidates) {
    const auto build = [](double nu, double fx, double sp, int start, std::vector<int> pay,
                          double au, double am,
                          DayCountConvention dcc = DayCountConvention::ACT_360) {
        return XccySwap(nu, fx, sp, start, std::move(pay), au, am, XccySide::PayUsd, true, true,
                        "SOFR", "TIIE-F", "MXN-USD", "USDMXN", dcc);
    };
    EXPECT_NO_THROW(build(1e7, 18.5, 0.001, 0, {28, 56}, 1.0, 1.0));
    EXPECT_NO_THROW(build(1e7, 18.5, 0.001, -14, {14, 42}, 1.0007, 1.0003));
    EXPECT_NO_THROW(build(1e7, 18.5, -0.01, 28, {56}, 1.0, 1.0));
    EXPECT_THROW(build(0.0, 18.5, 0.0, 0, {28}, 1.0, 1.0),  std::invalid_argument);   // notionalUsd
    EXPECT_THROW(build(-1.0, 18.5, 0.0, 0, {28}, 1.0, 1.0), std::invalid_argument);
    EXPECT_THROW(build(std::nan(""), 18.5, 0.0, 0, {28}, 1.0, 1.0), std::invalid_argument);
    EXPECT_THROW(build(1e7, 0.0, 0.0, 0, {28}, 1.0, 1.0),   std::invalid_argument);   // fxRate
    EXPECT_THROW(build(1e7, -18.5, 0.0, 0, {28}, 1.0, 1.0), std::invalid_argument);
    EXPECT_THROW(build(1e7, 18.5, std::nan(""), 0, {28}, 1.0, 1.0), std::invalid_argument);   // spread
    EXPECT_THROW(build(1e7, 18.5, 0.0, 0, {}, 1.0, 1.0),    std::invalid_argument);   // payDays
    EXPECT_THROW(build(1e7, 18.5, 0.0, -30, {0, 28}, 1.0, 1.0),  std::invalid_argument);
    EXPECT_THROW(build(1e7, 18.5, 0.0, -30, {-5, 28}, 1.0, 1.0), std::invalid_argument);
    EXPECT_THROW(build(1e7, 18.5, 0.0, 0, {28, 28}, 1.0, 1.0),   std::invalid_argument);
    EXPECT_THROW(build(1e7, 18.5, 0.0, 0, {56, 28}, 1.0, 1.0),   std::invalid_argument);
    EXPECT_THROW(build(1e7, 18.5, 0.0, 28, {28}, 1.0, 1.0),      std::invalid_argument);   // startDays < payDays[0]
    EXPECT_THROW(build(1e7, 18.5, 0.0, -14, {14}, 0.0, 1.0),     std::invalid_argument);   // factors > 0
    EXPECT_THROW(build(1e7, 18.5, 0.0, -14, {14}, 1.0, -1.0),    std::invalid_argument);
    EXPECT_THROW(build(1e7, 18.5, 0.0, -14, {14}, std::nan(""), 1.0), std::invalid_argument);
    EXPECT_THROW(build(1e7, 18.5, 0.0, 0, {28}, 1.0001, 1.0),    std::invalid_argument);   // == 1 if startDays >= 0
    EXPECT_THROW(build(1e7, 18.5, 0.0, 7, {28}, 1.0, 1.0001),    std::invalid_argument);
    EXPECT_THROW(build(1e7, 18.5, 0.0, 0, {28}, 1.0, 1.0, DayCountConvention::THIRTY_360),
                 std::invalid_argument);
}
