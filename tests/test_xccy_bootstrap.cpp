#include <gtest/gtest.h>
#include <qf/termstructure/xccy_bootstrap.hpp>
#include <qf/termstructure/ois_bootstrap.hpp>
#include <qf/instruments/xccy_swap.hpp>
#include <qf/instruments/fx_forward.hpp>
#include <qf/core/market_environment.hpp>
#include <cmath>
#include <stdexcept>
#include <vector>

using namespace qf::termstructure;
using qf::core::MarketEnvironment;
using qf::instruments::FxForward;
using qf::instruments::FxSide;
using qf::instruments::XccySide;
using qf::instruments::XccySwap;
using qf::math::InterpolationMethod;

namespace {
    constexpr double kSpot = 18.60;

    // MX-DEMO quotes (desk/api/seed_market.py): a 1-day deposit and par OIS for the rest.
    YieldCurve tiieF() {
        const std::vector<OisQuote> q = {
            {1,      0.0700, OisQuote::Deposit}, {28,   0.0698, OisQuote::Ois},
            {84,     0.0692, OisQuote::Ois},     {168,  0.0685, OisQuote::Ois},
            {364,    0.0675, OisQuote::Ois},     {728,  0.0670, OisQuote::Ois},
            {1092,   0.0672, OisQuote::Ois},     {1820, 0.0680, OisQuote::Ois},
            {2548,   0.0690, OisQuote::Ois},     {3640, 0.0705, OisQuote::Ois},
        };
        return bootstrapOis(q, 28);
    }
    YieldCurve sofr() {
        const std::vector<OisQuote> q = {
            {1,      0.0390, OisQuote::Deposit}, {30,   0.0385, OisQuote::Ois},
            {91,     0.0380, OisQuote::Ois},     {182,  0.0375, OisQuote::Ois},
            {365,    0.0370, OisQuote::Ois},     {730,  0.0355, OisQuote::Ois},
            {1095,   0.0350, OisQuote::Ois},     {1825, 0.0355, OisQuote::Ois},
            {2555,   0.0365, OisQuote::Ois},     {3650, 0.0380, OisQuote::Ois},
        };
        return bootstrapOis(q, 365);
    }

    std::vector<FxForwardQuote> demoForwards() {
        return {{28, 0.0438}, {84, 0.1317}, {168, 0.2637}, {364, 0.5745}};
    }
    std::vector<XccyBasisQuote> demoBasis() {
        return {{728, -0.0010}, {1092, -0.0012}, {1820, -0.0015}, {2548, -0.0017}, {3640, -0.0020}};
    }

    MarketEnvironment envWith(const YieldCurve& usd, const YieldCurve& proj, const YieldCurve& xccy) {
        MarketEnvironment env;
        env.addCurve("SOFR", usd);
        env.addCurve("TIIE-F", proj);
        env.addCurve("MXN-USD", xccy);
        env.setSpot("USDMXN", kSpot);
        return env;
    }

    // Value of the constant-notional swap a basis quote refers to, N_U = 1e6, PayUsd.
    double basisSwapNpv(const MarketEnvironment& env, const XccyBasisQuote& q) {
        const XccySwap swap(1e6, kSpot, q.spread, 0, oisPaymentDays(q.days, 28), 1.0, 1.0,
                            XccySide::PayUsd, true, true);
        return swap.npv(env);
    }
}

// ---------------------------------------------------------------------------
// R1: every quote reprices
// ---------------------------------------------------------------------------

TEST(XccyBootstrap, EveryForwardRepricesToItsQuote) {
    const YieldCurve usd = sofr(), proj = tiieF();
    const YieldCurve xccy = bootstrapXccyDiscount(demoForwards(), demoBasis(), kSpot, usd, proj);
    const MarketEnvironment env = envWith(usd, proj, xccy);
    for (const auto& q : demoForwards()) {
        const double t = q.days / 365.0;
        EXPECT_NEAR(kSpot * usd.discountFactor(t) / xccy.discountFactor(t), kSpot + q.points, 1e-8)
            << "days=" << q.days;
        const FxForward fwd(1.0, 1.0, q.days, FxSide::Buy, "USDMXN", "MXN-USD", "SOFR");
        EXPECT_NEAR(fwd.forwardRate(env), kSpot + q.points, 1e-8) << "days=" << q.days;
    }
}

TEST(XccyBootstrap, EveryBasisSwapRepricesToZero) {
    const YieldCurve usd = sofr(), proj = tiieF();
    const YieldCurve xccy = bootstrapXccyDiscount(demoForwards(), demoBasis(), kSpot, usd, proj);
    const MarketEnvironment env = envWith(usd, proj, xccy);
    const double notionalMxn = 1e6 * kSpot;
    for (const auto& q : demoBasis())
        EXPECT_LE(std::abs(basisSwapNpv(env, q)), 1e-8 * notionalMxn) << "days=" << q.days;
}

TEST(XccyBootstrap, PillarsAreDaysOver365InQuoteOrder) {
    const YieldCurve xccy = bootstrapXccyDiscount(demoForwards(), demoBasis(), kSpot, sofr(), tiieF());
    const std::vector<int> days = {28, 84, 168, 364, 728, 1092, 1820, 2548, 3640};
    ASSERT_EQ(xccy.maturities().size(), days.size());
    for (std::size_t i = 0; i < days.size(); ++i)
        EXPECT_DOUBLE_EQ(xccy.maturities()[i], days[i] / 365.0);
}

TEST(XccyBootstrap, PositiveBasisPutsMxnDiscountFactorsBelowTheProjectionCurve) {
    const YieldCurve usd = sofr(), proj = tiieF();
    std::vector<XccyBasisQuote> basis = demoBasis();
    for (auto& q : basis) q.spread = 0.0015;
    const YieldCurve xccy = bootstrapXccyDiscount({}, basis, kSpot, usd, proj);
    const MarketEnvironment env = envWith(usd, proj, xccy);
    for (const auto& q : basis) {
        EXPECT_LT(xccy.discountFactor(q.days / 365.0), proj.discountFactor(q.days / 365.0)) << "days=" << q.days;
        EXPECT_LE(std::abs(basisSwapNpv(env, q)), 1e-8 * 1e6 * kSpot) << "days=" << q.days;
    }
}

TEST(XccyBootstrap, BasisOnlyCurveStartsFlatAndStillRepricesEveryQuote) {
    // No forwards: the first basis pillar has no earlier pillar to interpolate from.
    const YieldCurve usd = sofr(), proj = tiieF();
    const YieldCurve xccy = bootstrapXccyDiscount({}, demoBasis(), kSpot, usd, proj);
    const MarketEnvironment env = envWith(usd, proj, xccy);
    ASSERT_EQ(xccy.maturities().size(), demoBasis().size());
    for (const auto& q : demoBasis())
        EXPECT_LE(std::abs(basisSwapNpv(env, q)), 1e-8 * 1e6 * kSpot) << "days=" << q.days;
}

TEST(XccyBootstrap, ForwardsOnlyCurveRepricesEveryForward) {
    const YieldCurve usd = sofr(), proj = tiieF();
    const YieldCurve xccy = bootstrapXccyDiscount(demoForwards(), {}, kSpot, usd, proj);
    for (const auto& q : demoForwards())
        EXPECT_NEAR(kSpot * usd.discountFactor(q.days / 365.0) / xccy.discountFactor(q.days / 365.0),
                    kSpot + q.points, 1e-8) << "days=" << q.days;
}

// ---------------------------------------------------------------------------
// R2: parity forwards and zero basis give back the TIIE-F curve
// ---------------------------------------------------------------------------

TEST(XccyBootstrap, ParityForwardsAndZeroBasisReproduceTheTiieFCurve) {
    const YieldCurve usd = sofr(), proj = tiieF();
    std::vector<FxForwardQuote> forwards;
    for (int d : {1, 28, 84, 168, 364}) {
        const double t = d / 365.0;
        forwards.push_back({d, kSpot * usd.discountFactor(t) / proj.discountFactor(t) - kSpot});
    }
    std::vector<XccyBasisQuote> basis;
    for (int d : {728, 1092, 1820, 2548, 3640}) basis.push_back({d, 0.0});

    const YieldCurve xccy = bootstrapXccyDiscount(forwards, basis, kSpot, usd, proj);
    for (int d = 1; d <= 3640; d += 7) {
        const double t = d / 365.0;
        EXPECT_NEAR(xccy.discountFactor(t), proj.discountFactor(t), 1e-8) << "days=" << d;
    }
}

// ---------------------------------------------------------------------------
// R3 (base): a negative basis lifts the MXN discount factors
// ---------------------------------------------------------------------------

TEST(XccyBootstrap, NegativeBasisPutsMxnUsdAboveTiieFAtTheBasisPillars) {
    const YieldCurve proj = tiieF();
    const YieldCurve xccy = bootstrapXccyDiscount(demoForwards(), demoBasis(), kSpot, sofr(), proj);
    for (const auto& q : demoBasis())
        EXPECT_GT(xccy.discountFactor(q.days / 365.0), proj.discountFactor(q.days / 365.0))
            << "days=" << q.days;
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

TEST(XccyBootstrap, RejectsFewerThanTwoQuotesInTotal) {
    const YieldCurve usd = sofr(), proj = tiieF();
    EXPECT_THROW(bootstrapXccyDiscount({}, {}, kSpot, usd, proj), std::invalid_argument);
    EXPECT_THROW(bootstrapXccyDiscount({{28, 0.0438}}, {}, kSpot, usd, proj), std::invalid_argument);
    EXPECT_THROW(bootstrapXccyDiscount({}, {{728, -0.001}}, kSpot, usd, proj), std::invalid_argument);
    EXPECT_NO_THROW(bootstrapXccyDiscount({{28, 0.0438}}, {{728, -0.001}}, kSpot, usd, proj));
}

TEST(XccyBootstrap, RejectsNonPositiveOrNonIncreasingDays) {
    const YieldCurve usd = sofr(), proj = tiieF();
    EXPECT_THROW(bootstrapXccyDiscount({{0, 0.0}, {28, 0.0438}}, {}, kSpot, usd, proj), std::invalid_argument);
    EXPECT_THROW(bootstrapXccyDiscount({{-5, 0.0}, {28, 0.0438}}, {}, kSpot, usd, proj), std::invalid_argument);
    EXPECT_THROW(bootstrapXccyDiscount({{84, 0.13}, {28, 0.0438}}, {}, kSpot, usd, proj), std::invalid_argument);
    EXPECT_THROW(bootstrapXccyDiscount({{28, 0.0438}, {28, 0.0440}}, {}, kSpot, usd, proj), std::invalid_argument);
    EXPECT_THROW(bootstrapXccyDiscount({}, {{0, -0.001}, {728, -0.001}}, kSpot, usd, proj), std::invalid_argument);
    EXPECT_THROW(bootstrapXccyDiscount({}, {{1092, -0.001}, {728, -0.001}}, kSpot, usd, proj), std::invalid_argument);
    EXPECT_THROW(bootstrapXccyDiscount({}, {{728, -0.001}, {728, -0.002}}, kSpot, usd, proj), std::invalid_argument);
}

TEST(XccyBootstrap, RejectsABasisThatDoesNotStartAfterTheLastForward) {
    const YieldCurve usd = sofr(), proj = tiieF();
    EXPECT_THROW(bootstrapXccyDiscount({{28, 0.0438}, {364, 0.5745}}, {{364, -0.001}}, kSpot, usd, proj),
                 std::invalid_argument);
    EXPECT_THROW(bootstrapXccyDiscount({{28, 0.0438}, {364, 0.5745}}, {{200, -0.001}, {728, -0.001}},
                                       kSpot, usd, proj), std::invalid_argument);
    EXPECT_NO_THROW(bootstrapXccyDiscount({{28, 0.0438}, {364, 0.5745}}, {{365, -0.001}}, kSpot, usd, proj));
}

TEST(XccyBootstrap, RejectsBadSpotPointsPeriodOrSpread) {
    const YieldCurve usd = sofr(), proj = tiieF();
    const auto fwd = demoForwards();
    const auto bas = demoBasis();
    EXPECT_THROW(bootstrapXccyDiscount(fwd, bas, 0.0, usd, proj), std::invalid_argument);
    EXPECT_THROW(bootstrapXccyDiscount(fwd, bas, -18.6, usd, proj), std::invalid_argument);
    EXPECT_THROW(bootstrapXccyDiscount(fwd, bas, std::nan(""), usd, proj), std::invalid_argument);
    EXPECT_THROW(bootstrapXccyDiscount({{28, -kSpot}, {84, 0.13}}, {}, kSpot, usd, proj), std::invalid_argument);
    EXPECT_THROW(bootstrapXccyDiscount({{28, -kSpot - 1.0}, {84, 0.13}}, {}, kSpot, usd, proj), std::invalid_argument);
    EXPECT_THROW(bootstrapXccyDiscount(fwd, bas, kSpot, usd, proj, 0), std::invalid_argument);
    EXPECT_THROW(bootstrapXccyDiscount(fwd, bas, kSpot, usd, proj, -28), std::invalid_argument);
    EXPECT_THROW(bootstrapXccyDiscount({}, {{728, std::nan("")}, {1092, -0.001}}, kSpot, usd, proj),
                 std::invalid_argument);
}

TEST(XccyBootstrap, ThrowsWhenABasisPillarHasNoSolution) {
    // A 500% spread cannot be offset by any zero rate in the search range.
    const YieldCurve usd = sofr(), proj = tiieF();
    EXPECT_THROW(bootstrapXccyDiscount(demoForwards(), {{728, 5.0}}, kSpot, usd, proj), std::runtime_error);
}
