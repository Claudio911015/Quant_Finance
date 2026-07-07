#include <gtest/gtest.h>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include <qf/core/market_environment.hpp>
#include <qf/core/imarket_observer.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/termstructure/volsurface.hpp>

using namespace qf::core;
using namespace qf::termstructure;

// Helper: crea una YieldCurve simple con tasa plana r
static YieldCurve flatCurve(double r) {
    return YieldCurve({0.5, 1.0, 2.0, 5.0}, {r, r, r, r});
}

// Helper: 2x2 vol surface with a mild skew, calendar-consistent.
static VolSurface makeSurface() {
    std::vector<double> maturities = {0.5, 1.0};
    std::vector<double> strikes    = {90.0, 110.0};
    std::vector<std::vector<double>> vols = {{0.24, 0.20}, {0.25, 0.21}};
    return VolSurface(maturities, strikes, vols);
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

// 9. NegativeVolThrows — volatilidad negativa lanza invalid_argument
TEST(MarketEnvironment, NegativeVolThrows) {
    MarketEnvironment env;
    EXPECT_THROW(env.setVolatility("AAPL", -0.1), std::invalid_argument);
}

// 10. NegativeSpotThrows — spot negativo lanza invalid_argument
TEST(MarketEnvironment, NegativeSpotThrows) {
    MarketEnvironment env;
    EXPECT_THROW(env.setSpot("AAPL", -100.0), std::invalid_argument);
}

// ── P4b: vol surface integration ─────────────────────────────────────────────

// 11. SurfacePreferredOverFlat — the (strike,maturity) overload uses the surface.
TEST(MarketEnvironment, SurfacePreferredOverFlat) {
    MarketEnvironment env;
    env.setVolatility("AAPL", 0.99);       // flat scalar the surface must override
    env.setVolSurface("AAPL", makeSurface());
    EXPECT_TRUE(env.hasVolSurface("AAPL"));
    // At a strike pillar / maturity pillar the surface returns its grid vol, not 0.99.
    EXPECT_NEAR(env.volatility("AAPL", 90.0, 0.5), 0.24, 1e-12);
    EXPECT_NEAR(env.volatility("AAPL", 110.0, 1.0), 0.21, 1e-12);
    // The scalar accessor is untouched by the surface.
    EXPECT_DOUBLE_EQ(env.volatility("AAPL"), 0.99);
}

// 12. FlatFallbackWhenNoSurface — overload returns the flat scalar unchanged.
TEST(MarketEnvironment, FlatFallbackWhenNoSurface) {
    MarketEnvironment env;
    env.setVolatility("MSFT", 0.20);
    EXPECT_FALSE(env.hasVolSurface("MSFT"));
    // Any (strike, maturity) resolves to the flat scalar — the pre-P4 behaviour.
    EXPECT_DOUBLE_EQ(env.volatility("MSFT", 80.0, 0.25), 0.20);
    EXPECT_DOUBLE_EQ(env.volatility("MSFT", 150.0, 3.0), 0.20);
}

// 13. FlatFallbackThrowsWhenMissing — overload throws like the scalar when nothing set.
TEST(MarketEnvironment, FlatFallbackThrowsWhenMissing) {
    MarketEnvironment env;
    EXPECT_THROW(env.volatility("NADA", 100.0, 1.0), std::out_of_range);
}

// 14. SurfaceSetNotifiesObservers — setVolSurface fires VolatilityChanged.
namespace {
struct RecordingObserver : IMarketObserver {
    int count = 0;
    ChangeType lastType = ChangeType::SpotChanged;
    std::string lastKey;
    void onMarketUpdate(const MarketEnvironment&, ChangeType type,
                        const std::string& key) override {
        ++count; lastType = type; lastKey = key;
    }
};
} // namespace

TEST(MarketEnvironment, SurfaceSetNotifiesObservers) {
    MarketEnvironment env;
    auto obs = std::make_shared<RecordingObserver>();
    env.subscribe(obs);
    env.setVolSurface("AAPL", makeSurface());
    EXPECT_EQ(obs->count, 1);
    EXPECT_EQ(obs->lastType, ChangeType::VolatilityChanged);
    EXPECT_EQ(obs->lastKey, "AAPL");
}
