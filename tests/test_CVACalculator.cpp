#include <gtest/gtest.h>
#include <qf/xva/credit_curve.hpp>
#include <cmath>

using namespace qf::xva;

TEST(FlatHazardRate, SurvivalAtZeroIsOne) {
    FlatHazardRate cr(0.02);
    EXPECT_NEAR(cr.survivalProbability(0.0), 1.0, 1e-12);
}

TEST(FlatHazardRate, SurvivalDecaysExponentially) {
    double lambda = 0.05;
    FlatHazardRate cr(lambda);
    for (double t : {1.0, 2.0, 5.0, 10.0}) {
        EXPECT_NEAR(cr.survivalProbability(t), std::exp(-lambda * t), 1e-12);
    }
}

TEST(FlatHazardRate, ZeroLambdaAlwaysOne) {
    FlatHazardRate cr(0.0);
    for (double t : {0.0, 1.0, 10.0})
        EXPECT_NEAR(cr.survivalProbability(t), 1.0, 1e-12);
}

TEST(FlatHazardRate, NegativeLambdaThrows) {
    EXPECT_THROW(FlatHazardRate(-0.01), std::invalid_argument);
}

TEST(FlatHazardRate, NegativeTimeThrows) {
    FlatHazardRate cr(0.02);
    EXPECT_THROW(cr.survivalProbability(-1.0), std::invalid_argument);
}

#include <qf/xva/netting_set.hpp>
#include <qf/termstructure/yieldcurve.hpp>

using namespace qf::instruments;
using namespace qf::termstructure;

TEST(NettingSet, EmptySetNetValueIsZero) {
    qf::xva::NettingSet ns;
    YieldCurve curve({0.5,1,2,5,10}, {0.04,0.04,0.04,0.04,0.04});
    qf::core::MarketEnvironment env(curve);
    EXPECT_NEAR(ns.netValue(env, 0.0), 0.0, 1e-12);
}

TEST(NettingSet, MaturedSwapSkipped) {
    qf::xva::NettingSet ns;
    ns.add(1e6, 0.05, 2.0, 1.0, SwapType::Payer);
    YieldCurve curve({0.5,1,2,5,10}, {0.04,0.04,0.04,0.04,0.04});
    qf::core::MarketEnvironment env(curve);
    // At t=3 the swap matured at T=2, so net value must be 0
    EXPECT_NEAR(ns.netValue(env, 3.0), 0.0, 1e-12);
}

TEST(NettingSet, PayerReceiverNetToZero) {
    // Identical payer + receiver same params -> net ~= 0
    qf::xva::NettingSet ns;
    ns.add(1e6, 0.04, 5.0, 1.0, SwapType::Payer);
    ns.add(1e6, 0.04, 5.0, 1.0, SwapType::Receiver);
    YieldCurve curve({0.5,1,2,5,10}, {0.04,0.04,0.04,0.04,0.04});
    qf::core::MarketEnvironment env(curve);
    EXPECT_NEAR(ns.netValue(env, 0.0), 0.0, 1e-6);
}

TEST(NettingSet, InvalidNotionalThrows) {
    qf::xva::NettingSet ns;
    EXPECT_THROW(ns.add(-1e6, 0.05, 5.0, 1.0, SwapType::Payer), std::invalid_argument);
}

TEST(NettingSet, InvalidMaturityThrows) {
    qf::xva::NettingSet ns;
    EXPECT_THROW(ns.add(1e6, 0.05, -1.0, 1.0, SwapType::Payer), std::invalid_argument);
}
