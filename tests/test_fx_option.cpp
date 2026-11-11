#include <gtest/gtest.h>
#include <qf/instruments/fx_forward.hpp>
#include <qf/instruments/fx_option.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <qf/core/market_environment.hpp>
#include <cmath>
#include <stdexcept>

using namespace qf::instruments;
using qf::core::MarketEnvironment;
using qf::termstructure::VolSurface;
using qf::termstructure::YieldCurve;

namespace {
    constexpr double kNotionalUsd = 5e6;
    constexpr double kSpot        = 18.60;
    constexpr double kStrike      = 19.10;
    constexpr int    kDays        = 182;
    constexpr double kFlatVol     = 0.14;

    YieldCurve tiief() {
        return YieldCurve({0.0767, 0.2301, 0.4603, 0.9973, 1.9945},
                          {0.0710, 0.0715, 0.0722, 0.0730, 0.0750});
    }

    YieldCurve sofr() {
        return YieldCurve({0.0767, 0.2301, 0.4603, 0.9973, 1.9945},
                          {0.0430, 0.0428, 0.0425, 0.0420, 0.0415});
    }

    MarketEnvironment makeEnv(double spot = kSpot, double flatVol = kFlatVol) {
        MarketEnvironment env;
        env.addCurve("TIIE-F", tiief());
        env.addCurve("SOFR", sofr());
        env.setSpot("USDMXN", spot);
        env.setVolatility("USDMXN", flatVol);
        return env;
    }

    // Smile with a clearly different level from the flat vol so the source is detectable.
    VolSurface smile() {
        return VolSurface({0.0822, 0.25, 0.5, 1.0},
                          {17.0, 18.0, 19.0, 20.0, 21.0},
                          {{0.12, 0.11, 0.115, 0.125, 0.135},
                           {0.13, 0.12, 0.125, 0.135, 0.145},
                           {0.14, 0.13, 0.135, 0.145, 0.155},
                           {0.15, 0.14, 0.145, 0.155, 0.165}});
    }
}

TEST(FxOption, CallMinusPutEqualsForwardNpvAtSameStrike) {
    const MarketEnvironment env = makeEnv();
    FxOption call(kNotionalUsd, kStrike, kDays, OptionType::Call, FxSide::Buy);
    FxOption put (kNotionalUsd, kStrike, kDays, OptionType::Put,  FxSide::Buy);
    FxForward fwd(kNotionalUsd, kStrike, kDays, FxSide::Buy);

    const double lhs = call.npv(env) - put.npv(env);
    const double rhs = fwd.npv(env);
    EXPECT_NEAR(lhs, rhs, 1e-10 * std::abs(rhs));
}

TEST(FxOption, ParityHoldsWithSurfaceVol) {
    MarketEnvironment env = makeEnv();
    env.setVolSurface("USDMXN", smile());
    FxOption call(kNotionalUsd, kStrike, kDays, OptionType::Call, FxSide::Buy);
    FxOption put (kNotionalUsd, kStrike, kDays, OptionType::Put,  FxSide::Buy);
    FxForward fwd(kNotionalUsd, kStrike, kDays, FxSide::Buy);
    EXPECT_NEAR(call.npv(env) - put.npv(env), fwd.npv(env), 1e-10 * std::abs(fwd.npv(env)));
}

TEST(FxOption, BuyIsMinusSell) {
    const MarketEnvironment env = makeEnv();
    for (OptionType t : {OptionType::Call, OptionType::Put}) {
        FxOption buy (kNotionalUsd, kStrike, kDays, t, FxSide::Buy);
        FxOption sell(kNotionalUsd, kStrike, kDays, t, FxSide::Sell);
        const FxOptionGreeks b = buy.greeks(env);
        const FxOptionGreeks s = sell.greeks(env);
        EXPECT_DOUBLE_EQ(b.price, -s.price);
        EXPECT_DOUBLE_EQ(b.delta, -s.delta);
        EXPECT_DOUBLE_EQ(b.gamma, -s.gamma);
        EXPECT_DOUBLE_EQ(b.vega,  -s.vega);
        EXPECT_DOUBLE_EQ(b.forward, s.forward);
        EXPECT_DOUBLE_EQ(b.vol, s.vol);
    }
}

TEST(FxOption, PriceMatchesBlackScholesWithForeignRateAsDividendYield) {
    const MarketEnvironment env = makeEnv();
    const double T = kDays / 365.0;
    qf::instruments::OptionParams p{};
    p.spot = kSpot;  p.strike = kStrike;  p.maturity = T;  p.volatility = kFlatVol;
    p.riskFreeRate  = -std::log(tiief().discountFactor(T)) / T;
    p.dividendYield = -std::log(sofr().discountFactor(T)) / T;
    p.type = OptionType::Call;  p.exercise = ExerciseType::European;
    const double expected = kNotionalUsd * qf::pricingengines::blackScholes(p).price;

    FxOption call(kNotionalUsd, kStrike, kDays, OptionType::Call, FxSide::Buy);
    EXPECT_NEAR(call.npv(env), expected, 1e-12 * expected);
    EXPECT_DOUBLE_EQ(call.greeks(env).price, call.npv(env));
    EXPECT_DOUBLE_EQ(call.pv(env), call.npv(env));
}

TEST(FxOption, DeltaAndGammaMatchFiniteDifferencesOfSpot) {
    const double h = 1e-3;
    FxOption call(kNotionalUsd, kStrike, kDays, OptionType::Call, FxSide::Buy);
    const double up   = call.npv(makeEnv(kSpot + h));
    const double mid  = call.npv(makeEnv(kSpot));
    const double down = call.npv(makeEnv(kSpot - h));
    const FxOptionGreeks g = call.greeks(makeEnv());
    EXPECT_NEAR(g.delta, (up - down) / (2.0 * h), 1e-6 * std::abs(g.delta));
    EXPECT_NEAR(g.gamma, (up - 2.0 * mid + down) / (h * h), 1e-4 * std::abs(g.gamma));
}

TEST(FxOption, VegaIsPerOneVolPoint) {
    FxOption put(kNotionalUsd, kStrike, kDays, OptionType::Put, FxSide::Buy);
    const double bumped = put.npv(makeEnv(kSpot, kFlatVol + 0.01));
    const double base   = put.npv(makeEnv(kSpot, kFlatVol));
    const double vega   = put.greeks(makeEnv()).vega;
    EXPECT_GT(vega, 0.0);
    // Exact change over a full point differs from vega only by volga (second order).
    EXPECT_NEAR(bumped - base, vega, 0.01 * std::abs(vega));
}

TEST(FxOption, ForwardAndVolFieldsAreReported) {
    const MarketEnvironment env = makeEnv();
    FxOption call(kNotionalUsd, kStrike, kDays, OptionType::Call, FxSide::Sell);
    FxForward fwd(kNotionalUsd, kStrike, kDays, FxSide::Buy);
    const FxOptionGreeks g = call.greeks(env);
    EXPECT_DOUBLE_EQ(g.forward, fwd.forwardRate(env));
    EXPECT_DOUBLE_EQ(g.vol, kFlatVol);
}

TEST(FxOption, VolIsTakenFromSurfaceWhenPresent) {
    MarketEnvironment env = makeEnv();
    env.setVolSurface("USDMXN", smile());
    const double T = kDays / 365.0;
    const double surfaceVol = smile().vol(kStrike, T);
    ASSERT_NE(surfaceVol, kFlatVol);

    FxOption call(kNotionalUsd, kStrike, kDays, OptionType::Call, FxSide::Buy);
    EXPECT_DOUBLE_EQ(call.greeks(env).vol, surfaceVol);

    // Price equals the flat-vol price evaluated at the surface vol.
    const double flatAtSurface = call.npv(makeEnv(kSpot, surfaceVol));
    EXPECT_NEAR(call.npv(env), flatAtSurface, 1e-12 * flatAtSurface);
    EXPECT_NE(call.npv(env), call.npv(makeEnv()));
}

TEST(FxOption, ReadsSpotAndCurvesByNameSoShocksAffectIt) {
    const MarketEnvironment base = makeEnv();
    FxOption call(kNotionalUsd, kStrike, kDays, OptionType::Call, FxSide::Buy);

    MarketEnvironment spotUp = base;
    spotUp.setSpot("USDMXN", kSpot * 1.02);
    EXPECT_GT(call.npv(spotUp), call.npv(base));

    MarketEnvironment domUp = base;
    domUp.addCurve("TIIE-F", tiief().parallelBump(100.0));
    EXPECT_NE(call.npv(domUp), call.npv(base));

    MarketEnvironment forUp = base;
    forUp.addCurve("SOFR", sofr().parallelBump(100.0));
    EXPECT_NE(call.npv(forUp), call.npv(base));
}

TEST(FxOption, ConstructorRejectsNonPositiveInputs) {
    EXPECT_THROW(FxOption(0.0, kStrike, kDays, OptionType::Call, FxSide::Buy), std::invalid_argument);
    EXPECT_THROW(FxOption(kNotionalUsd, 0.0, kDays, OptionType::Call, FxSide::Buy), std::invalid_argument);
    EXPECT_THROW(FxOption(kNotionalUsd, kStrike, 0, OptionType::Call, FxSide::Buy), std::invalid_argument);
}

TEST(FxOption, MissingVolatilityThrows) {
    MarketEnvironment env;
    env.addCurve("TIIE-F", tiief());
    env.addCurve("SOFR", sofr());
    env.setSpot("USDMXN", kSpot);
    FxOption call(kNotionalUsd, kStrike, kDays, OptionType::Call, FxSide::Buy);
    EXPECT_THROW(call.npv(env), std::out_of_range);
}
