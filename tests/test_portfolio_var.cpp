#include <gtest/gtest.h>
#include <qf/risk/var.hpp>
#include <cmath>

using namespace qf::risk;

// Helpers
static std::vector<std::vector<double>> identityCorr(int n) {
    std::vector<std::vector<double>> m(n, std::vector<double>(n, 0.0));
    for (int i = 0; i < n; ++i) m[i][i] = 1.0;
    return m;
}

// 1-asset portfolio must match single-asset parametricVaR
TEST(PortfolioVaR, SingleAssetMatchesParametric) {
    PortfolioPosition p{1e6, 0.0, 0.01};
    auto r = portfolioVaR({p}, identityCorr(1), 0.99);
    auto ref = parametricVaR(1e6, 0.0, 0.01, 0.99);
    EXPECT_NEAR(r.var, ref.var, 1.0);
    EXPECT_NEAR(r.cvar, ref.cvar, 1.0);
}

// Perfect positive correlation → portfolio vol = weighted sum of individual vols
TEST(PortfolioVaR, PerfectPositiveCorrelation) {
    // Two positions of $500k each, sigma=0.01, corr=1.0
    // Portfolio vol = 0.5*0.01 + 0.5*0.01 = 0.01 (same as single $1M position)
    std::vector<PortfolioPosition> pos = {{5e5, 0.0, 0.01}, {5e5, 0.0, 0.01}};
    std::vector<std::vector<double>> corr = {{1.0, 1.0}, {1.0, 1.0}};
    auto r = portfolioVaR(pos, corr, 0.99);
    auto ref = parametricVaR(1e6, 0.0, 0.01, 0.99);
    EXPECT_NEAR(r.var, ref.var, 1.0);
}

// Perfect negative correlation → portfolio vol approaches 0
TEST(PortfolioVaR, PerfectNegativeCorrelationReducesVaR) {
    std::vector<PortfolioPosition> pos = {{5e5, 0.0, 0.01}, {5e5, 0.0, 0.01}};
    std::vector<std::vector<double>> corr = {{1.0, -1.0}, {-1.0, 1.0}};
    auto r = portfolioVaR(pos, corr, 0.99);
    EXPECT_NEAR(r.var, 0.0, 1.0);  // nearly zero VaR
}

// Diversification effect: uncorrelated assets reduce VaR vs perfect correlation
TEST(PortfolioVaR, DiversificationReducesVaR) {
    std::vector<PortfolioPosition> pos = {{5e5, 0.0, 0.01}, {5e5, 0.0, 0.01}};
    auto uncorr = portfolioVaR(pos, identityCorr(2), 0.99);
    std::vector<std::vector<double>> fullcorr = {{1.0, 1.0}, {1.0, 1.0}};
    auto corr   = portfolioVaR(pos, fullcorr, 0.99);
    EXPECT_LT(uncorr.var, corr.var);
}

// CVaR > VaR
TEST(PortfolioVaR, CVaRGreaterThanVaR) {
    std::vector<PortfolioPosition> pos = {{5e5, 0.0, 0.01}, {5e5, 0.0, 0.01}};
    auto r = portfolioVaR(pos, identityCorr(2), 0.99);
    EXPECT_GT(r.cvar, r.var);
}

// Invalid inputs throw
TEST(PortfolioVaR, EmptyPositionsThrows) {
    EXPECT_THROW(portfolioVaR({}, {}, 0.99), std::invalid_argument);
}

TEST(PortfolioVaR, MismatchedCorrelationMatrixThrows) {
    PortfolioPosition p{1e6, 0.0, 0.01};
    // 1 position but 2x2 corr matrix
    EXPECT_THROW(portfolioVaR({p}, {{1.0, 0.0}, {0.0, 1.0}}, 0.99), std::invalid_argument);
}
