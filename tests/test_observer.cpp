#include <gtest/gtest.h>
#include <memory>
#include <string>
#include <qf/core/imarket_observer.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/termstructure/yieldcurve.hpp>

using namespace qf::core;
using namespace qf::termstructure;

// Helper: creates a flat yield curve with rate r.
static YieldCurve flatCurve(double r) {
    return YieldCurve({0.5, 1.0, 2.0, 5.0}, {r, r, r, r});
}

// -----------------------------------------------------------------------------
// Concrete observer that counts how many times it was notified.
// -----------------------------------------------------------------------------
class CountingObserver : public IMarketObserver {
public:
    int callCount{0};
    ChangeType lastType{};
    std::string lastKey;

    void onMarketUpdate(const MarketEnvironment& /*env*/,
                        ChangeType type,
                        const std::string& key) override {
        ++callCount;
        lastType = type;
        lastKey  = key;
    }
};

// -----------------------------------------------------------------------------
// Tests
// -----------------------------------------------------------------------------

/// Subscribe an observer, call setSpot → observer is called exactly once.
TEST(MarketObserver, SetSpotNotifiesObserver) {
    MarketEnvironment env;
    auto obs = std::make_shared<CountingObserver>();
    env.subscribe(obs);

    env.setSpot("AAPL", 150.0);

    EXPECT_EQ(obs->callCount, 1);
    EXPECT_EQ(obs->lastType,  ChangeType::SpotChanged);
    EXPECT_EQ(obs->lastKey,   "AAPL");
}

/// Subscribe an observer, call setVolatility → observer is called exactly once.
TEST(MarketObserver, SetVolatilityNotifiesObserver) {
    MarketEnvironment env;
    auto obs = std::make_shared<CountingObserver>();
    env.subscribe(obs);

    env.setVolatility("AAPL", 0.25);

    EXPECT_EQ(obs->callCount, 1);
    EXPECT_EQ(obs->lastType,  ChangeType::VolatilityChanged);
    EXPECT_EQ(obs->lastKey,   "AAPL");
}

/// Subscribe an observer, call addCurve → observer is called exactly once.
TEST(MarketObserver, AddCurveNotifiesObserver) {
    MarketEnvironment env;
    auto obs = std::make_shared<CountingObserver>();
    env.subscribe(obs);

    env.addCurve("USD", flatCurve(0.05));

    EXPECT_EQ(obs->callCount, 1);
    EXPECT_EQ(obs->lastType,  ChangeType::CurveChanged);
    EXPECT_EQ(obs->lastKey,   "USD");
}

/// After the observer is destroyed (weak_ptr expires), setSpot must not crash
/// and the call count must reflect zero live calls.
TEST(MarketObserver, ExpiredObserverDoesNotCrash) {
    MarketEnvironment env;

    {
        auto obs = std::make_shared<CountingObserver>();
        env.subscribe(obs);
        // obs goes out of scope here → weak_ptr expires
    }

    // Must not throw or crash.
    EXPECT_NO_THROW(env.setSpot("AAPL", 100.0));
}

/// After unsubscribeAll(), a previously subscribed observer is no longer called.
TEST(MarketObserver, UnsubscribeAllPreventsNotification) {
    MarketEnvironment env;
    auto obs = std::make_shared<CountingObserver>();
    env.subscribe(obs);

    env.unsubscribeAll();
    env.setSpot("AAPL", 200.0);

    EXPECT_EQ(obs->callCount, 0);
}

/// Multiple observers all receive the notification.
TEST(MarketObserver, MultipleObserversAllNotified) {
    MarketEnvironment env;
    auto obs1 = std::make_shared<CountingObserver>();
    auto obs2 = std::make_shared<CountingObserver>();
    env.subscribe(obs1);
    env.subscribe(obs2);

    env.setVolatility("TSLA", 0.40);

    EXPECT_EQ(obs1->callCount, 1);
    EXPECT_EQ(obs2->callCount, 1);
}

/// Subscribing the same observer twice must not cause duplicate callbacks.
TEST(MarketObserver, DuplicateSubscribeNotifiesOnce) {
    MarketEnvironment env;
    auto obs = std::make_shared<CountingObserver>();
    env.subscribe(obs);
    env.subscribe(obs);  // duplicate — should be ignored
    env.setSpot("AAPL", 150.0);
    EXPECT_EQ(obs->callCount, 1);
}

/// unsubscribe() removes only the targeted observer; others continue receiving.
TEST(MarketObserver, UnsubscribeIndividual) {
    MarketEnvironment env;
    auto obs1 = std::make_shared<CountingObserver>();
    auto obs2 = std::make_shared<CountingObserver>();
    env.subscribe(obs1);
    env.subscribe(obs2);
    env.unsubscribe(obs1);
    env.setSpot("AAPL", 150.0);
    EXPECT_EQ(obs1->callCount, 0);
    EXPECT_EQ(obs2->callCount, 1);
}
