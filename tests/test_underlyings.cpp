#include <gtest/gtest.h>
#include <qf/instruments/iunderlying.hpp>
#include <qf/instruments/option.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/interpolation.hpp>
#include <memory>

using namespace qf::instruments;
using namespace qf::core;

TEST(IUnderlying, EquityUnderlyingId) {
    EquityUnderlying u("AAPL");
    EXPECT_EQ(u.id(), "AAPL");
}

TEST(IUnderlying, RateUnderlyingId) {
    RateUnderlying u("USD");
    EXPECT_EQ(u.id(), "USD");
}

TEST(IUnderlying, PolymorphicId) {
    std::shared_ptr<IUnderlying> u = std::make_shared<EquityUnderlying>("GOOG");
    EXPECT_EQ(u->id(), "GOOG");
}

TEST(Option, NewConstructorWithUnderlying) {
    auto u = std::make_shared<EquityUnderlying>("AAPL");
    Option opt(u, 100.0, 1.0, OptionType::Call, ExerciseType::European);
    EXPECT_EQ(opt.underlying().id(), "AAPL");
    EXPECT_DOUBLE_EQ(opt.strikeValue(), 100.0);
    EXPECT_EQ(opt.optionType(), OptionType::Call);
    EXPECT_EQ(opt.exerciseType(), ExerciseType::European);
}

TEST(Option, NewConstructorPricingViaEngine) {
    auto u = std::make_shared<EquityUnderlying>("AAPL");
    Option opt(u, 100.0, 1.0, OptionType::Call, ExerciseType::European);

    MarketEnvironment env;
    env.setSpot("AAPL", 100.0);
    env.setVolatility("AAPL", 0.20);

    OptionParams params{100, 100, 0.05, 0.0, 0.20, 1.0,
                        OptionType::Call, ExerciseType::European};
    auto engine = std::make_shared<qf::pricingengines::BlackScholesEngine>(params);
    opt.setPricingEngine(engine);
    double p = opt.pv(env);
    EXPECT_GT(p, 0.0);
    EXPECT_NEAR(p, qf::pricingengines::blackScholes(params).price, 1e-6);
}

TEST(Option, LegacyConstructorStillWorks) {
    Option opt;
    opt.spot = 100.0; opt.strike = 100.0; opt.riskFreeRate = 0.05;
    opt.dividendYield = 0.0; opt.volatility = 0.20;
    opt.type = OptionType::Call; opt.exercise = ExerciseType::European;
    opt.setMaturity(1.0);

    qf::termstructure::YieldCurve curve(
        {0.5, 1.0, 2.0}, {0.05, 0.05, 0.05},
        qf::math::InterpolationMethod::Linear);
    double p = opt.pv(curve);  // uses legacy overload
    EXPECT_GT(p, 0.0);
}
