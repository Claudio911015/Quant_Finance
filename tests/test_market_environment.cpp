#include <gtest/gtest.h>
#include <stdexcept>
#include <qf/core/market_environment.hpp>
#include <qf/termstructure/yieldcurve.hpp>

using namespace qf::core;
using namespace qf::termstructure;

// Helper: crea una YieldCurve simple con tasa plana r
static YieldCurve flatCurve(double r) {
    return YieldCurve({0.5, 1.0, 2.0, 5.0}, {r, r, r, r});
}

// 1. DefaultCurveRoundTrip
TEST(MarketEnvironment, DefaultCurveRoundTrip) {
    double rate = 0.05;
    MarketEnvironment env(flatCurve(rate));
    // La curva por defecto debe devolver la tasa correcta
    EXPECT_NEAR(env.curve().zeroRate(1.0), rate, 1e-10);
    EXPECT_NEAR(env.curve().zeroRate(2.0), rate, 1e-10);
}

// 2. NamedCurveRoundTrip
TEST(MarketEnvironment, NamedCurveRoundTrip) {
    MarketEnvironment env;
    env.addCurve("USD", flatCurve(0.04));
    env.addCurve("MXN", flatCurve(0.10));

    EXPECT_NEAR(env.curve("USD").zeroRate(1.0), 0.04, 1e-10);
    EXPECT_NEAR(env.curve("MXN").zeroRate(1.0), 0.10, 1e-10);
}

// 3. MissingCurveThrows
TEST(MarketEnvironment, MissingCurveThrows) {
    MarketEnvironment env;
    EXPECT_THROW(env.curve("USD"), std::out_of_range);
    // También la curva "default" lanza si no fue configurada
    EXPECT_THROW(env.curve("default"), std::out_of_range);
    EXPECT_THROW(env.curve(), std::out_of_range);
}

// 4. SpotAndVolRoundTrip
TEST(MarketEnvironment, SpotAndVolRoundTrip) {
    MarketEnvironment env;
    env.setSpot("AAPL", 175.0);
    env.setVolatility("AAPL", 0.25);
    env.setSpot("MSFT", 310.0);
    env.setVolatility("MSFT", 0.20);

    EXPECT_DOUBLE_EQ(env.spot("AAPL"), 175.0);
    EXPECT_DOUBLE_EQ(env.volatility("AAPL"), 0.25);
    EXPECT_DOUBLE_EQ(env.spot("MSFT"), 310.0);
    EXPECT_DOUBLE_EQ(env.volatility("MSFT"), 0.20);
}

// 5. MissingSpotThrows
TEST(MarketEnvironment, MissingSpotThrows) {
    MarketEnvironment env;
    EXPECT_THROW(env.spot("AAPL"), std::out_of_range);
    EXPECT_THROW(env.volatility("AAPL"), std::out_of_range);
}

// 6. DefaultCurveAccessibleByName — acceder a "default" también funciona
TEST(MarketEnvironment, DefaultCurveAccessibleByName) {
    MarketEnvironment env(flatCurve(0.03));
    EXPECT_NEAR(env.curve("default").zeroRate(1.0), 0.03, 1e-10);
}

// 7. OverwriteCurve — addCurve sobreescribe una clave existente
TEST(MarketEnvironment, OverwriteCurve) {
    MarketEnvironment env;
    env.addCurve("USD", flatCurve(0.04));
    env.addCurve("USD", flatCurve(0.05));
    EXPECT_NEAR(env.curve("USD").zeroRate(1.0), 0.05, 1e-10);
}

// 8. OverwriteSpotAndVol — setSpot/setVol sobreescriben valores anteriores
TEST(MarketEnvironment, OverwriteSpotAndVol) {
    MarketEnvironment env;
    env.setSpot("TSLA", 200.0);
    env.setSpot("TSLA", 250.0);
    EXPECT_DOUBLE_EQ(env.spot("TSLA"), 250.0);

    env.setVolatility("TSLA", 0.40);
    env.setVolatility("TSLA", 0.35);
    EXPECT_DOUBLE_EQ(env.volatility("TSLA"), 0.35);
}
