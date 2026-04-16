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
