#include <gtest/gtest.h>
#include <qf/risk/var.hpp>
#include <qf/risk/greeks.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <qf/instruments/option.hpp>
#include <cmath>
#include <random>
#include <numeric>

using namespace qf::risk;
using namespace qf::pricingengines;
using namespace qf::instruments;

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

// ═══════════════════════════════════════════════════════════════════════════
// Numerical Greeks — validated against Black-Scholes analytical values
// ═══════════════════════════════════════════════════════════════════════════

// ATM call: S=K=100, r=0.05, q=0, σ=0.20, T=1
static OptionParams atmCall() {
    return {100.0, 100.0, 0.05, 0.0, 0.20, 1.0, OptionType::Call, ExerciseType::European};
}

// Helper: reprice call after perturbing one parameter
static double bsPrice(OptionParams p) { return blackScholes(p).price; }

TEST(NumericalGreeks, DeltaMatchesBS) {
    auto p = atmCall();
    double analytical = blackScholes(p).delta;
    double numerical  = delta(
        [&](double S) { auto q = p; q.spot = S; return bsPrice(q); },
        p.spot, 0.01);
    EXPECT_NEAR(numerical, analytical, 1e-4);
}

TEST(NumericalGreeks, GammaMatchesBS) {
    auto p = atmCall();
    double analytical = blackScholes(p).gamma;
    double numerical  = gamma(
        [&](double S) { auto q = p; q.spot = S; return bsPrice(q); },
        p.spot, 0.01);
    EXPECT_NEAR(numerical, analytical, 1e-4);
}

TEST(NumericalGreeks, VegaMatchesBS) {
    auto p = atmCall();
    // BS vega is scaled: dV/dσ / 100 (per 1% vol move).
    // Numerical vega is raw dV/dσ, so divide by 100 to compare.
    double analytical = blackScholes(p).vega;
    double numerical  = vega(
        [&](double v) { auto q = p; q.volatility = v; return bsPrice(q); },
        p.volatility, 0.001) / 100.0;
    EXPECT_NEAR(numerical, analytical, 1e-4);
}

TEST(NumericalGreeks, ThetaMatchesBS) {
    auto p = atmCall();
    // BS theta is per calendar day. Numerical theta with h=1yr is per year;
    // divide by 365 to convert to per-day units.
    double analytical = blackScholes(p).theta;
    double numerical  = theta(
        [&](double T) { auto q = p; q.maturity = T; return bsPrice(q); },
        p.maturity, 1.0 / 365.0) / 365.0;
    EXPECT_NEAR(numerical, analytical, 1e-4);
}

TEST(NumericalGreeks, RhoMatchesBS) {
    auto p = atmCall();
    // BS rho is scaled: dV/dr / 100 (per 100bp move).
    // Numerical rho is raw dV/dr, so divide by 100 to compare.
    double analytical = blackScholes(p).rho;
    double numerical  = rho(
        [&](double r) { auto q = p; q.riskFreeRate = r; return bsPrice(q); },
        p.riskFreeRate, 0.0001) / 100.0;
    EXPECT_NEAR(numerical, analytical, 1e-4);
}

TEST(NumericalGreeks, DeltaPutBetweenMinusOneAndZero) {
    auto p = atmCall();
    p.type = OptionType::Put;
    double d = delta(
        [&](double S) { auto q = p; q.spot = S; return bsPrice(q); },
        p.spot, 0.01);
    EXPECT_LT(d, 0.0);
    EXPECT_GT(d, -1.0);
}

TEST(NumericalGreeks, GammaPositive) {
    auto p = atmCall();
    double g = gamma(
        [&](double S) { auto q = p; q.spot = S; return bsPrice(q); },
        p.spot, 0.01);
    EXPECT_GT(g, 0.0);
}

TEST(NumericalGreeks, VegaPositive) {
    auto p = atmCall();
    double v = vega(
        [&](double vol) { auto q = p; q.volatility = vol; return bsPrice(q); },
        p.volatility, 0.001);
    EXPECT_GT(v, 0.0);
}

TEST(NumericalGreeks, ThetaNegativeForLongCall) {
    auto p = atmCall();
    double t = theta(
        [&](double T) { auto q = p; q.maturity = T; return bsPrice(q); },
        p.maturity, 1.0 / 365.0);
    EXPECT_LT(t, 0.0);
}

TEST(NumericalGreeks, Dv01PositiveForBond) {
    // Simple zero-coupon bond: P = F * exp(-y * T)
    // DV01 = (P(y-h) - P(y+h)) / 2 > 0
    double F = 1000.0, T = 5.0;
    double y = 0.05;
    double d = dv01(
        [&](double yield) { return F * std::exp(-yield * T); },
        y, 0.0001);
    EXPECT_GT(d, 0.0);
}

TEST(NumericalGreeks, Dv01KnownValue) {
    // ZCB: P = 1000 * exp(-0.05 * 5) = 778.80
    // dP/dy = -T * P = -5 * 778.80 = -3894
    // DV01 = -dP/dy * 0.0001 = 0.3894 ... but our formula gives (P(y-h)-P(y+h))/2
    // = (1000*exp(-0.0499*5) - 1000*exp(-0.0501*5)) / 2 ≈ 0.3894
    double F = 1000.0, T = 5.0, y = 0.05;
    double expected = T * F * std::exp(-y * T) * 0.0001;
    double numerical = dv01(
        [&](double yield) { return F * std::exp(-yield * T); },
        y, 0.0001);
    EXPECT_NEAR(numerical, expected, 1e-6);
}

TEST(NumericalGreeks, InvalidParamsThrow) {
    auto fn = [](double x) { return x * x; };
    EXPECT_THROW(delta(fn, 100.0, -0.01), std::invalid_argument);
    EXPECT_THROW(delta(fn, -1.0, 0.01),   std::invalid_argument);
    EXPECT_THROW(gamma(fn, 100.0, 0.0),   std::invalid_argument);
    EXPECT_THROW(vega(fn, 0.20, -0.001),  std::invalid_argument);
    EXPECT_THROW(vega(fn, -0.1, 0.001),   std::invalid_argument);
    EXPECT_THROW(theta(fn, 0.5, 1.0),     std::invalid_argument); // T <= h
    EXPECT_THROW(rho(fn, 0.05, 0.0),      std::invalid_argument);
    EXPECT_THROW(dv01(fn, 0.05, -0.0001), std::invalid_argument);
}
