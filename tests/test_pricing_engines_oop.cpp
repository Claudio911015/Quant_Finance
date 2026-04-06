#include <gtest/gtest.h>
#include <qf/pricingengines/ipricing_engine.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <qf/pricingengines/montecarlo.hpp>
#include <qf/pricingengines/binomialtree.hpp>
#include <qf/pricingengines/finite_difference.hpp>
#include <qf/pricingengines/heston.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/instruments/option.hpp>
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
