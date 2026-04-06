#include <gtest/gtest.h>
#include <qf/pricingengines/ipricing_engine.hpp>
#include <qf/pricingengines/engine_factory.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <qf/pricingengines/montecarlo.hpp>
#include <qf/pricingengines/binomialtree.hpp>
#include <qf/pricingengines/finite_difference.hpp>
#include <qf/pricingengines/heston.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/instruments/option.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/models/iequity_model.hpp>
#include <qf/models/bs_model.hpp>
#include <qf/models/heston_model.hpp>
#include <memory>
#include <cmath>

using namespace qf::pricingengines;
using namespace qf::instruments;
using namespace qf::core;

namespace {
    OptionParams atm() {
        return {100.0, 100.0, 0.05, 0.0, 0.20, 1.0,
                OptionType::Call, ExerciseType::European};
    }
    MarketEnvironment emptyEnv() { return MarketEnvironment{}; }
}

TEST(BlackScholesEngine, IsIPricingEngine) {
    std::shared_ptr<IPricingEngine> e = std::make_shared<BlackScholesEngine>(atm());
    EXPECT_EQ(e->name(), "BlackScholes");
    double p = e->price(emptyEnv());
    EXPECT_NEAR(p, blackScholes(atm()).price, 1e-10);
}

TEST(MonteCarloEngine, IsIPricingEngine) {
    std::shared_ptr<IPricingEngine> e = std::make_shared<MonteCarloEngine>(atm(), 200000, 42);
    EXPECT_EQ(e->name(), "MonteCarlo");
    double p = e->price(emptyEnv());
    EXPECT_NEAR(p, monteCarloBSPrice(atm(), 200000, 42), 1e-10);
}

TEST(BinomialTreeEngine, IsIPricingEngine) {
    std::shared_ptr<IPricingEngine> e = std::make_shared<BinomialTreeEngine>(atm(), 500);
    EXPECT_EQ(e->name(), "BinomialTree");
    double p = e->price(emptyEnv());
    EXPECT_NEAR(p, binomialTreeBSPrice(atm(), 500), 1e-10);
}

TEST(FDMEngine, IsIPricingEngine) {
    std::shared_ptr<IPricingEngine> e =
        std::make_shared<FDMEngine>(atm(), 200, 200, FDMethod::CrankNicolson);
    EXPECT_EQ(e->name(), "FiniteDifference");
    double p = e->price(emptyEnv());
    EXPECT_NEAR(p, finiteDifferenceBSPrice(atm(), 200, 200, FDMethod::CrankNicolson), 1e-10);
}

TEST(HestonEngine, IsIPricingEngine) {
    OptionParams opt = {100, 100, 0.05, 0.0, 0.0, 1.0,
                        OptionType::Call, ExerciseType::European};
    HestonParams hp{0.04, 2.0, 0.04, 0.3, -0.7};
    std::shared_ptr<IPricingEngine> e = std::make_shared<HestonEngine>(opt, hp);
    EXPECT_EQ(e->name(), "Heston");
    double p = e->price(emptyEnv());
    EXPECT_NEAR(p, hestonPrice(opt, hp), 1e-10);
}

TEST(EngineFactory, MakesBlackScholesEngine) {
    auto e = EngineFactory::makeEquityEngine("BS", atm());
    EXPECT_EQ(e->name(), "BlackScholes");
    EXPECT_GT(e->price(emptyEnv()), 0.0);
}

TEST(EngineFactory, MakesMonteCarloEngine) {
    auto e = EngineFactory::makeEquityEngine("MC", atm(), 50000, 42);
    EXPECT_EQ(e->name(), "MonteCarlo");
    EXPECT_GT(e->price(emptyEnv()), 0.0);
}

TEST(EngineFactory, MakesBinomialTreeEngine) {
    auto e = EngineFactory::makeEquityEngine("BT", atm());
    EXPECT_EQ(e->name(), "BinomialTree");
    EXPECT_GT(e->price(emptyEnv()), 0.0);
}

TEST(EngineFactory, MakesFDMEngine) {
    auto e = EngineFactory::makeEquityEngine("FDM", atm());
    EXPECT_EQ(e->name(), "FiniteDifference");
    EXPECT_GT(e->price(emptyEnv()), 0.0);
}

TEST(EngineFactory, UnknownMethodThrows) {
    EXPECT_THROW(EngineFactory::makeEquityEngine("UNKNOWN", atm()), std::invalid_argument);
}

TEST(PricingEngines, PutCallParityAcrossEngines) {
    OptionParams callP = atm();
    OptionParams putP  = {100, 100, 0.05, 0.0, 0.20, 1.0,
                          OptionType::Put, ExerciseType::European};
    double parity = 100.0 * std::exp(0.0) - 100.0 * std::exp(-0.05 * 1.0);

    std::vector<std::pair<std::shared_ptr<IPricingEngine>,
                          std::shared_ptr<IPricingEngine>>> pairs = {
        {std::make_shared<BlackScholesEngine>(callP), std::make_shared<BlackScholesEngine>(putP)},
        {std::make_shared<BinomialTreeEngine>(callP, 500), std::make_shared<BinomialTreeEngine>(putP, 500)},
    };
    for (auto& [ec, ep] : pairs) {
        double c = ec->price(emptyEnv());
        double p = ep->price(emptyEnv());
        EXPECT_NEAR(c - p, parity, 0.05);
    }
}

// ── Task 1: IEquityModel injection into MonteCarloEngine ─────────────────────

TEST(MonteCarloEngine, BSModelDrivenMatchesLegacy) {
    auto params = atm();  // S=100, K=100, r=0.05, q=0, sigma=0.20, T=1, Call
    auto model = std::make_shared<qf::models::BlackScholesModel>(
        params.riskFreeRate, params.dividendYield, params.volatility);

    auto legacyEngine = std::make_shared<MonteCarloEngine>(params, 200000, 42);
    auto modelEngine  = std::make_shared<MonteCarloEngine>(model, params, 200000, 1, 42);

    double legacyPrice = legacyEngine->price(emptyEnv());
    double modelPrice  = modelEngine->price(emptyEnv());

    EXPECT_EQ(modelEngine->name(), "MonteCarlo");
    EXPECT_NEAR(modelPrice, legacyPrice, 0.10);
    EXPECT_GT(modelPrice, 0.0);
}

TEST(MonteCarloEngine, HestonModelDrivenGivesPositivePrice) {
    auto params = atm();
    qf::models::HestonParams hp{0.04, 2.0, 0.04, 0.3, -0.7};
    auto model  = std::make_shared<qf::models::HestonModel>(hp, params.riskFreeRate, params.dividendYield);

    auto engine = std::make_shared<MonteCarloEngine>(model, params, 50000, 252, 42);

    EXPECT_EQ(engine->name(), "MonteCarlo");
    double p = engine->price(emptyEnv());
    EXPECT_GT(p, 0.0);
    EXPECT_LT(p, params.spot);
}

TEST(MonteCarloEngine, HestonModelDrivenAgreesWithHestonEngine) {
    auto params = atm();
    qf::models::HestonParams hp{0.04, 2.0, 0.04, 0.3, -0.7};
    auto model  = std::make_shared<qf::models::HestonModel>(hp, params.riskFreeRate, params.dividendYield);

    HestonParams hpEngine{0.04, 2.0, 0.04, 0.3, -0.7};
    double analytical = hestonPrice(params, hpEngine);

    auto mcEngine = std::make_shared<MonteCarloEngine>(model, params, 200000, 252, 42);
    double mcPrice = mcEngine->price(emptyEnv());

    EXPECT_NEAR(mcPrice, analytical, analytical * 0.03);
}

// ── Task 3: BlackScholesEngine env-aware ─────────────────────────────────────

static MarketEnvironment atmEnv() {
    // Matches atm() params: S=100, sigma=0.20, r=0.05
    MarketEnvironment env;
    env.setSpot("AAPL", 100.0);
    env.setVolatility("AAPL", 0.20);
    env.addCurve("default",
        qf::termstructure::YieldCurve({0.5,1.0,2.0,5.0},{0.05,0.05,0.05,0.05}));
    return env;
}

TEST(BlackScholesEngine, EnvAwareMatchesParamsBased) {
    auto paramsEngine = BlackScholesEngine(atm());
    auto envEngine    = BlackScholesEngine(atm(), "AAPL");

    double expected = paramsEngine.price(emptyEnv());
    double actual   = envEngine.price(atmEnv());
    EXPECT_NEAR(actual, expected, 1e-8);
}

TEST(BlackScholesEngine, EnvAwareReadsDifferentSpot) {
    auto envEngine = BlackScholesEngine(atm(), "AAPL");
    MarketEnvironment env;
    env.setSpot("AAPL", 110.0);
    env.setVolatility("AAPL", 0.20);
    env.addCurve("default",
        qf::termstructure::YieldCurve({0.5,1.0,2.0,5.0},{0.05,0.05,0.05,0.05}));

    double priceS100 = BlackScholesEngine(atm()).price(emptyEnv());
    double priceS110 = envEngine.price(env);
    EXPECT_GT(priceS110, priceS100);
}

TEST(BlackScholesEngine, EnvAwareMissingSpotThrows) {
    auto engine = BlackScholesEngine(atm(), "AAPL");
    MarketEnvironment emptyNamed;
    EXPECT_THROW(engine.price(emptyNamed), std::out_of_range);
}

TEST(BlackScholesEngine, LegacyConstructorStillIgnoresEnv) {
    auto engine = BlackScholesEngine(atm());
    double p1 = engine.price(emptyEnv());
    double p2 = engine.price(atmEnv());
    EXPECT_DOUBLE_EQ(p1, p2);
}

// ── Task 4: MonteCarloEngine env-aware ───────────────────────────────────────

TEST(MonteCarloEngine, EnvAwareReadsDifferentSpot) {
    MarketEnvironment env;
    env.setSpot("AAPL", 110.0);
    env.setVolatility("AAPL", 0.20);
    env.addCurve("default",
        qf::termstructure::YieldCurve({0.5,1.0,2.0,5.0},{0.05,0.05,0.05,0.05}));

    auto envEngine    = MonteCarloEngine(atm(), "AAPL", 100000, 42);
    auto legacyEngine = MonteCarloEngine(atm(), 100000, 42);

    double priceS110 = envEngine.price(env);
    double priceS100 = legacyEngine.price(emptyEnv());
    EXPECT_GT(priceS110, priceS100);
}

TEST(MonteCarloEngine, EnvAwareMissingTickerThrows) {
    auto engine = MonteCarloEngine(atm(), "AAPL", 100000, 42);
    EXPECT_THROW(engine.price(emptyEnv()), std::out_of_range);
}

TEST(MonteCarloEngine, LegacyConstructorIgnoresEnv) {
    auto engine = MonteCarloEngine(atm(), 100000, 42);
    double p1 = engine.price(emptyEnv());
    double p2 = engine.price(atmEnv());
    EXPECT_DOUBLE_EQ(p1, p2);

}

// ── Task 5: BinomialTreeEngine and FDMEngine env-aware ───────────────────────

TEST(BinomialTreeEngine, EnvAwareReadsDifferentVol) {
    // Construct with vol=0.20 in params; env has vol=0.30 — env wins
    auto envEngine = BinomialTreeEngine(atm(), "AAPL", 500);
    MarketEnvironment env;
    env.setSpot("AAPL", 100.0);
    env.setVolatility("AAPL", 0.30);
    env.addCurve("default",
        qf::termstructure::YieldCurve({0.5,1.0,2.0,5.0},{0.05,0.05,0.05,0.05}));

    double priceVol20 = BinomialTreeEngine(atm(), 500).price(emptyEnv());
    double priceVol30 = envEngine.price(env);
    EXPECT_GT(priceVol30, priceVol20);
}

TEST(BinomialTreeEngine, EnvAwareMissingTickerThrows) {
    auto engine = BinomialTreeEngine(atm(), "AAPL", 500);
    EXPECT_THROW(engine.price(emptyEnv()), std::out_of_range);
}

TEST(FDMEngine, EnvAwareReadsDifferentSpot) {
    auto envEngine = FDMEngine(atm(), "AAPL");
    MarketEnvironment env;
    env.setSpot("AAPL", 90.0);
    env.setVolatility("AAPL", 0.20);
    env.addCurve("default",
        qf::termstructure::YieldCurve({0.5,1.0,2.0,5.0},{0.05,0.05,0.05,0.05}));

    double priceATM = FDMEngine(atm()).price(emptyEnv());
    double priceOTM = envEngine.price(env);
    EXPECT_LT(priceOTM, priceATM);
}

TEST(FDMEngine, EnvAwareMissingTickerThrows) {
    auto engine = FDMEngine(atm(), "AAPL");
    EXPECT_THROW(engine.price(emptyEnv()), std::out_of_range);
}

// ── Task 6: HestonEngine env-aware ───────────────────────────────────────────

TEST(HestonEngine, EnvAwareReadsDifferentSpot) {
    OptionParams opt = {100, 100, 0.05, 0.0, 0.0, 1.0,
                        OptionType::Call, ExerciseType::European};
    HestonParams hp{0.04, 2.0, 0.04, 0.3, -0.7};

    auto envEngine = HestonEngine(opt, hp, "AAPL");

    MarketEnvironment env;
    env.setSpot("AAPL", 110.0);
    env.addCurve("default",
        qf::termstructure::YieldCurve({0.5,1.0,2.0,5.0},{0.05,0.05,0.05,0.05}));

    double priceS100 = HestonEngine(opt, hp).price(emptyEnv());
    double priceS110 = envEngine.price(env);
    EXPECT_GT(priceS110, priceS100);
}

TEST(HestonEngine, EnvAwareMissingSpotThrows) {
    OptionParams opt = {100, 100, 0.05, 0.0, 0.0, 1.0,
                        OptionType::Call, ExerciseType::European};
    HestonParams hp{0.04, 2.0, 0.04, 0.3, -0.7};
    auto engine = HestonEngine(opt, hp, "AAPL");
    EXPECT_THROW(engine.price(emptyEnv()), std::out_of_range);
}

// ── Task 7: EngineFactory ticker support ─────────────────────────────────────

TEST(EngineFactory, EnvAwareEngineReadsMktData) {
    auto engine = EngineFactory::makeEquityEngine("BS", atm(), 0, 0, "AAPL");

    MarketEnvironment env;
    env.setSpot("AAPL", 110.0);
    env.setVolatility("AAPL", 0.20);
    env.addCurve("default",
        qf::termstructure::YieldCurve({0.5,1.0,2.0,5.0},{0.05,0.05,0.05,0.05}));

    double priceS100 = EngineFactory::makeEquityEngine("BS", atm())->price(emptyEnv());
    double priceS110 = engine->price(env);
    EXPECT_GT(priceS110, priceS100);
}

TEST(EngineFactory, NoTickerStillWorks) {
    auto engine = EngineFactory::makeEquityEngine("MC", atm(), 50000, 42);
    EXPECT_GT(engine->price(emptyEnv()), 0.0);
}

// ── Task 8: Bump-and-reprice integration ─────────────────────────────────────

TEST(PricingEngines, BumpAndReprice) {
    // Build env-aware engines once via factory
    auto bs  = EngineFactory::makeEquityEngine("BS",  atm(), 0,      0,  "AAPL");
    auto mc  = EngineFactory::makeEquityEngine("MC",  atm(), 100000, 42, "AAPL");
    auto bt  = EngineFactory::makeEquityEngine("BT",  atm(), 0,      0,  "AAPL");

    // Base scenario: S=100, sigma=0.20, r=0.05
    MarketEnvironment base;
    base.setSpot("AAPL", 100.0);
    base.setVolatility("AAPL", 0.20);
    base.addCurve("default",
        qf::termstructure::YieldCurve({0.5,1.0,2.0,5.0},{0.05,0.05,0.05,0.05}));

    double bsBase  = bs->price(base);
    double mcBase  = mc->price(base);
    double btBase  = bt->price(base);

    // Bump spot +10 (modify env, NOT the engine)
    MarketEnvironment bumped = base;
    bumped.setSpot("AAPL", 110.0);

    double bsBumped = bs->price(bumped);
    double mcBumped = mc->price(bumped);
    double btBumped = bt->price(bumped);

    // All engines must show higher call price after spot bump
    EXPECT_GT(bsBumped, bsBase);
    EXPECT_GT(mcBumped, mcBase);
    EXPECT_GT(btBumped, btBase);

    // Numerical delta (BS): (price_up - price_down) / (S_up - S_down)
    MarketEnvironment down = base;
    down.setSpot("AAPL", 99.0);
    double bsDown = bs->price(down);
    double numericalDelta = (bsBumped - bsDown) / (110.0 - 99.0);
    double analyticalDelta = blackScholes(atm()).delta;
    // Tolerance 0.08: bump interval [99,110] is asymmetric (midpoint=104.5, not 100).
    // Numerical delta is evaluated at S~104.5; analytical delta at S=100.
    // The difference is dominated by gamma*(104.5-100) ≈ 0.019*4.5 ≈ 0.085.
    EXPECT_NEAR(numericalDelta, analyticalDelta, 0.08);
}
