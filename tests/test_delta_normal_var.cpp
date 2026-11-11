#include <gtest/gtest.h>
#include <qf/risk/delta_normal_var.hpp>
#include <qf/math/statistics.hpp>
#include <cmath>

using namespace qf::risk;

TEST(DeltaNormalVaR, SingleFactorMatchesClosedForm) {
    const double e = -2.5e6, s = 0.01, h = 10.0, c = 0.99;
    double v = deltaNormalVaR({e}, {s}, {{1.0}}, c, h);
    double expected = std::fabs(e) * s * qf::math::normInvCDF(c) * std::sqrt(h);
    EXPECT_NEAR(v, expected, 1e-12 * expected);
}

TEST(DeltaNormalVaR, PerfectPositiveCorrelationAddsSignedExposures) {
    // rho = 1, same-sign exposures: sigma_p = |e1 s1 + e2 s2|
    const double c = 0.95, h = 1.0;
    double v = deltaNormalVaR({100.0, 200.0}, {0.02, 0.01}, {{1.0, 1.0}, {1.0, 1.0}}, c, h);
    double expected = qf::math::normInvCDF(c) * (100.0 * 0.02 + 200.0 * 0.01);
    EXPECT_NEAR(v, expected, 1e-12 * expected);
}

TEST(DeltaNormalVaR, PerfectNegativeCorrelationOffsets) {
    // rho = -1, same-sign exposures: sigma_p = |e1 s1 - e2 s2|
    const double c = 0.95, h = 4.0;
    double v = deltaNormalVaR({100.0, 200.0}, {0.03, 0.01}, {{1.0, -1.0}, {-1.0, 1.0}}, c, h);
    double expected = qf::math::normInvCDF(c) * 2.0 * std::fabs(100.0 * 0.03 - 200.0 * 0.01);
    EXPECT_NEAR(v, expected, 1e-12 * expected + 1e-15);
}

TEST(DeltaNormalVaR, OpposingExposuresWithPositiveCorrelationOffset) {
    // Signed exposures: long one factor, short the other, rho = 1 -> |e1 s1 - |e2| s2|
    const double c = 0.99, h = 1.0;
    double v = deltaNormalVaR({100.0, -200.0}, {0.03, 0.01}, {{1.0, 1.0}, {1.0, 1.0}}, c, h);
    double expected = qf::math::normInvCDF(c) * std::fabs(100.0 * 0.03 - 200.0 * 0.01);
    EXPECT_NEAR(v, expected, 1e-12 * expected + 1e-15);
}

TEST(DeltaNormalVaR, ZeroExposureGivesZero) {
    EXPECT_EQ(deltaNormalVaR({0.0, 0.0}, {0.01, 0.02}, {{1.0, 0.3}, {0.3, 1.0}}, 0.99, 1.0), 0.0);
}

TEST(DeltaNormalVaR, InvalidInputsThrow) {
    const std::vector<std::vector<double>> I2 = {{1.0, 0.0}, {0.0, 1.0}};
    EXPECT_THROW(deltaNormalVaR({1.0, 2.0}, {0.01}, I2, 0.99, 1.0), std::invalid_argument);
    EXPECT_THROW(deltaNormalVaR({1.0, 2.0}, {0.01, 0.01}, {{1.0}}, 0.99, 1.0), std::invalid_argument);
    EXPECT_THROW(deltaNormalVaR({1.0, 2.0}, {0.01, 0.01}, {{1.0, 0.0}, {0.0}}, 0.99, 1.0), std::invalid_argument);
    EXPECT_THROW(deltaNormalVaR({1.0, 2.0}, {0.01, 0.01}, I2, 0.0, 1.0), std::invalid_argument);
    EXPECT_THROW(deltaNormalVaR({1.0, 2.0}, {0.01, 0.01}, I2, 1.0, 1.0), std::invalid_argument);
    EXPECT_THROW(deltaNormalVaR({1.0, 2.0}, {0.01, 0.01}, I2, 0.99, 0.0), std::invalid_argument);
    EXPECT_THROW(deltaNormalVaR({1.0, 2.0}, {0.01, -0.01}, I2, 0.99, 1.0), std::invalid_argument);
}
