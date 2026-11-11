#include <gtest/gtest.h>
#include <qf/instruments/fx_forward.hpp>
#include <qf/core/market_environment.hpp>
#include <cmath>
#include <stdexcept>

using namespace qf::instruments;
using qf::core::MarketEnvironment;
using qf::termstructure::YieldCurve;

namespace {
    constexpr double kNotionalUsd = 5e6;
    constexpr double kSpot        = 18.60;
    constexpr double kStrike      = 19.10;
    constexpr int    kDays        = 182;

    YieldCurve tiief() {
        return YieldCurve({0.0767, 0.2301, 0.4603, 0.9973, 1.9945},
                          {0.0710, 0.0715, 0.0722, 0.0730, 0.0750});
    }

    YieldCurve sofr() {
        return YieldCurve({0.0767, 0.2301, 0.4603, 0.9973, 1.9945},
                          {0.0430, 0.0428, 0.0425, 0.0420, 0.0415});
    }

    MarketEnvironment makeEnv(double spot = kSpot) {
        MarketEnvironment env;
        env.addCurve("TIIE-F", tiief());
        env.addCurve("SOFR", sofr());
        env.setSpot("USDMXN", spot);
        return env;
    }
}

TEST(FxForward, NpvMatchesCoveredParityFormulaWithCurveDiscountFactors) {
    const MarketEnvironment env = makeEnv();
    const double T   = kDays / 365.0;
    const double dfD = tiief().discountFactor(T);
    const double dfF = sofr().discountFactor(T);
    const double expected = kNotionalUsd * (kSpot * dfF - kStrike * dfD);

    FxForward fwd(kNotionalUsd, kStrike, kDays, FxSide::Buy);
    EXPECT_NEAR(fwd.npv(env), expected, 1e-12 * std::abs(expected) + 1e-12);
    EXPECT_NEAR(fwd.pv(env), expected, 1e-12 * std::abs(expected) + 1e-12);
}

TEST(FxForward, ForwardRateIsSpotTimesDfRatio) {
    const MarketEnvironment env = makeEnv();
    const double T = kDays / 365.0;
    const double expected = kSpot * sofr().discountFactor(T) / tiief().discountFactor(T);

    FxForward fwd(kNotionalUsd, kStrike, kDays, FxSide::Buy);
    EXPECT_NEAR(fwd.forwardRate(env), expected, 1e-12);
    // At a strike equal to the forward rate the contract is worth nothing.
    FxForward atForward(kNotionalUsd, expected, kDays, FxSide::Buy);
    EXPECT_NEAR(atForward.npv(env), 0.0, 1e-6);
}

TEST(FxForward, DeltaMatchesFiniteDifferenceOfSpot) {
    const double h = 1e-4;
    FxForward fwd(kNotionalUsd, kStrike, kDays, FxSide::Buy);
    const double fd = (fwd.npv(makeEnv(kSpot + h)) - fwd.npv(makeEnv(kSpot - h))) / (2.0 * h);
    EXPECT_NEAR(fwd.delta(makeEnv()), fd, 1e-6 * std::abs(fd));
}

TEST(FxForward, BuyIsMinusSell) {
    const MarketEnvironment env = makeEnv();
    FxForward buy (kNotionalUsd, kStrike, kDays, FxSide::Buy);
    FxForward sell(kNotionalUsd, kStrike, kDays, FxSide::Sell);
    EXPECT_DOUBLE_EQ(buy.npv(env), -sell.npv(env));
    EXPECT_DOUBLE_EQ(buy.delta(env), -sell.delta(env));
    EXPECT_DOUBLE_EQ(buy.forwardRate(env), sell.forwardRate(env));
}

TEST(FxForward, ReadsCurvesAndSpotByNameSoShocksAffectIt) {
    const MarketEnvironment base = makeEnv();
    FxForward fwd(kNotionalUsd, kStrike, kDays, FxSide::Buy);

    // A spot shock moves the value by delta * dS.
    MarketEnvironment spotUp = base;
    spotUp.setSpot("USDMXN", kSpot * 1.01);
    EXPECT_NEAR(fwd.npv(spotUp) - fwd.npv(base), fwd.delta(base) * kSpot * 0.01, 1e-6);

    // Raising the domestic curve lowers DF_d, so a buyer of USD (who pays K) gains.
    MarketEnvironment domUp = base;
    domUp.addCurve("TIIE-F", tiief().parallelBump(100.0));
    EXPECT_GT(fwd.npv(domUp), fwd.npv(base));

    // Raising the foreign curve lowers DF_f, so the same buyer loses.
    MarketEnvironment forUp = base;
    forUp.addCurve("SOFR", sofr().parallelBump(100.0));
    EXPECT_LT(fwd.npv(forUp), fwd.npv(base));
}

TEST(FxForward, CustomKeysAreUsed) {
    MarketEnvironment env;
    env.addCurve("MXN.CURVE", tiief());
    env.addCurve("USD.CURVE", sofr());
    env.setSpot("EURMXN", kSpot);
    FxForward custom(kNotionalUsd, kStrike, kDays, FxSide::Buy, "EURMXN", "MXN.CURVE", "USD.CURVE");
    FxForward standard(kNotionalUsd, kStrike, kDays, FxSide::Buy);
    EXPECT_DOUBLE_EQ(custom.npv(env), standard.npv(makeEnv()));
}

TEST(FxForward, MissingMarketDataThrows) {
    MarketEnvironment env;
    env.addCurve("TIIE-F", tiief());
    env.setSpot("USDMXN", kSpot);
    FxForward fwd(kNotionalUsd, kStrike, kDays, FxSide::Buy);
    EXPECT_THROW(fwd.npv(env), std::out_of_range);   // no SOFR curve
}

TEST(FxForward, ConstructorRejectsNonPositiveInputs) {
    EXPECT_THROW(FxForward(0.0, kStrike, kDays, FxSide::Buy), std::invalid_argument);
    EXPECT_THROW(FxForward(kNotionalUsd, 0.0, kDays, FxSide::Buy), std::invalid_argument);
    EXPECT_THROW(FxForward(kNotionalUsd, kStrike, 0, FxSide::Buy), std::invalid_argument);
}
