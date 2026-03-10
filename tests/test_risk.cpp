#include <gtest/gtest.h>
#include <qf/risk/var.hpp>
#include <cmath>
#include <random>
#include <numeric>

using namespace qf::risk;

// ═══════════════════════════════════════════════════════════════════════════
// Parametric VaR
// ═══════════════════════════════════════════════════════════════════════════

TEST(ParametricVaR, KnownValue99) {
    // 99% VaR with mean=0, sigma=0.01, portfolio=$1M
    // VaR = 1M * 2.3263 * 0.01 = $23,263
    auto r = parametricVaR(1e6, 0.0, 0.01, 0.99);
    EXPECT_NEAR(r.var, 23263.0, 50.0);
}

TEST(ParametricVaR, KnownValue95) {
    // 95% VaR with mean=0, sigma=0.01, portfolio=$1M
    // VaR = 1M * 1.6449 * 0.01 = $16,449
    auto r = parametricVaR(1e6, 0.0, 0.01, 0.95);
    EXPECT_NEAR(r.var, 16449.0, 50.0);
}

TEST(ParametricVaR, CVaRGreaterThanVaR) {
    auto r = parametricVaR(1e6, 0.0, 0.01, 0.99);
    EXPECT_GT(r.cvar, r.var);
}

TEST(ParametricVaR, VaRIncreasesWithVolatility) {
    auto r1 = parametricVaR(1e6, 0.0, 0.01, 0.99);
    auto r2 = parametricVaR(1e6, 0.0, 0.02, 0.99);
    EXPECT_GT(r2.var, r1.var);
}

TEST(ParametricVaR, VaRScalesWithPortfolioValue) {
    auto r1 = parametricVaR(1e6, 0.0, 0.01, 0.99);
    auto r2 = parametricVaR(2e6, 0.0, 0.01, 0.99);
    EXPECT_NEAR(r2.var, 2.0 * r1.var, 1e-6);
}

TEST(ParametricVaR, PositiveMeanReducesVaR) {
    auto r1 = parametricVaR(1e6, 0.0, 0.01, 0.99);
    auto r2 = parametricVaR(1e6, 0.001, 0.01, 0.99);
    EXPECT_LT(r2.var, r1.var);
}

TEST(ParametricVaR, InvalidParamsThrow) {
    EXPECT_THROW(parametricVaR(0.0, 0.0, 0.01, 0.99), std::invalid_argument);
    EXPECT_THROW(parametricVaR(1e6, 0.0, 0.0, 0.99), std::invalid_argument);
    EXPECT_THROW(parametricVaR(1e6, 0.0, 0.01, 0.0), std::invalid_argument);
    EXPECT_THROW(parametricVaR(1e6, 0.0, 0.01, 1.0), std::invalid_argument);
}

// ═══════════════════════════════════════════════════════════════════════════
// Historical VaR
// ═══════════════════════════════════════════════════════════════════════════

TEST(HistoricalVaR, SimpleKnownCase) {
    // 10 returns sorted: worst = -5%, percentile at (1-0.9)*10 = index 1
    std::vector<double> returns = {-0.05, -0.03, -0.01, 0.0, 0.005,
                                    0.01, 0.015, 0.02, 0.03, 0.04};
    auto r = historicalVaR(returns, 1e6, 0.90);
    // VaR at 90% = -portfolio * returns[1] = -1M*(-0.03) = 30000
    EXPECT_NEAR(r.var, 30000.0, 1.0);
}

TEST(HistoricalVaR, CVaRGreaterOrEqualToVaR) {
    std::mt19937_64 rng(42);
    std::normal_distribution<double> dist(0.0, 0.01);
    std::vector<double> returns(1000);
    for (auto& r : returns) r = dist(rng);

    auto result = historicalVaR(returns, 1e6, 0.99);
    EXPECT_GE(result.cvar, result.var);
}

TEST(HistoricalVaR, ConsistentWithParametric) {
    // With enough normal samples, historical VaR should be close to parametric
    std::mt19937_64 rng(123);
    double sigma = 0.01;
    std::normal_distribution<double> dist(0.0, sigma);

    std::vector<double> returns(100000);
    for (auto& r : returns) r = dist(rng);

    auto hist = historicalVaR(returns, 1e6, 0.99);
    auto param = parametricVaR(1e6, 0.0, sigma, 0.99);

    EXPECT_NEAR(hist.var, param.var, 1000.0); // within $1000
}

TEST(HistoricalVaR, InvalidParamsThrow) {
    std::vector<double> empty;
    std::vector<double> returns = {0.01, -0.01};
    EXPECT_THROW(historicalVaR(empty, 1e6, 0.99), std::invalid_argument);
    EXPECT_THROW(historicalVaR(returns, 0.0, 0.99), std::invalid_argument);
}

// ═══════════════════════════════════════════════════════════════════════════
// Monte Carlo VaR
// ═══════════════════════════════════════════════════════════════════════════

TEST(MonteCarloVaR, CVaRGreaterOrEqualToVaR) {
    std::mt19937_64 rng(42);
    std::normal_distribution<double> dist(0.0, 10000.0);
    std::vector<double> pnl(50000);
    for (auto& p : pnl) p = dist(rng);

    auto result = monteCarloVaR(pnl, 0.99);
    EXPECT_GE(result.cvar, result.var);
}

TEST(MonteCarloVaR, VaRPositiveForSymmetricDist) {
    std::mt19937_64 rng(42);
    std::normal_distribution<double> dist(0.0, 10000.0);
    std::vector<double> pnl(50000);
    for (auto& p : pnl) p = dist(rng);

    auto result = monteCarloVaR(pnl, 0.95);
    EXPECT_GT(result.var, 0.0);
}

TEST(MonteCarloVaR, InvalidParamsThrow) {
    std::vector<double> empty;
    EXPECT_THROW(monteCarloVaR(empty, 0.99), std::invalid_argument);
}
