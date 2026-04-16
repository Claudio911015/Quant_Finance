#include <gtest/gtest.h>
#include <qf/instruments/option.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <qf/pricingengines/montecarlo.hpp>
#include <qf/pricingengines/binomialtree.hpp>
#include <qf/pricingengines/finite_difference.hpp>
#include <qf/pricingengines/heston.hpp>
#include <cmath>

using namespace qf::instruments;
using namespace qf::pricingengines;

namespace {
    OptionParams makeCall(double S, double K, double r, double q, double vol, double T) {
        return {S, K, r, q, vol, T, OptionType::Call, ExerciseType::European};
    }
    OptionParams makePut(double S, double K, double r, double q, double vol, double T) {
        return {S, K, r, q, vol, T, OptionType::Put, ExerciseType::European};
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Boundary & sanity checks
// ═══════════════════════════════════════════════════════════════════════════

TEST(BlackScholes, CallPriceNonNegative) {
    auto res = blackScholes(makeCall(100, 100, 0.05, 0.0, 0.20, 1.0));
    EXPECT_GE(res.price, 0.0);
}

TEST(BlackScholes, PutPriceNonNegative) {
    auto res = blackScholes(makePut(100, 100, 0.05, 0.0, 0.20, 1.0));
    EXPECT_GE(res.price, 0.0);
}

TEST(BlackScholes, CallPriceAboveIntrinsicValue) {
    // C >= max(S - K*exp(-rT), 0)
    double S = 110, K = 100, r = 0.05, T = 1.0;
    auto res = blackScholes(makeCall(S, K, r, 0.0, 0.20, T));
    double intrinsic = S - K * std::exp(-r * T);
    EXPECT_GE(res.price, intrinsic);
}

TEST(BlackScholes, PutCallParity) {
    // C - P = S*exp(-qT) - K*exp(-rT)
    double S = 100, K = 100, r = 0.05, q = 0.02, vol = 0.20, T = 1.0;
    auto call = blackScholes(makeCall(S, K, r, q, vol, T));
    auto put  = blackScholes(makePut (S, K, r, q, vol, T));
    double lhs = call.price - put.price;
    double rhs = S * std::exp(-q * T) - K * std::exp(-r * T);
    EXPECT_NEAR(lhs, rhs, 1e-8);
}

TEST(BlackScholes, DeepITMCallApproachesForwardPrice) {
    // Very deep ITM call ≈ S*exp(-qT) - K*exp(-rT)
    double S = 200, K = 50, r = 0.05, q = 0.0, T = 1.0;
    auto res = blackScholes(makeCall(S, K, r, q, 0.20, T));
    double forward = S * std::exp(-q*T) - K * std::exp(-r*T);
    EXPECT_NEAR(res.price, forward, 1.0); // within $1
}

TEST(BlackScholes, DeepOTMCallNearZero) {
    auto res = blackScholes(makeCall(50, 200, 0.05, 0.0, 0.20, 1.0));
    EXPECT_NEAR(res.price, 0.0, 1e-4);
}

// ═══════════════════════════════════════════════════════════════════════════
// Known analytical values (benchmarked against external BS calculators)
// ═══════════════════════════════════════════════════════════════════════════

TEST(BlackScholes, ATMCallKnownValue) {
    // S=K=100, r=5%, q=0%, vol=20%, T=1yr → ≈ 10.4506
    auto res = blackScholes(makeCall(100, 100, 0.05, 0.0, 0.20, 1.0));
    EXPECT_NEAR(res.price, 10.4506, 1e-3);
}

TEST(BlackScholes, ATMPutKnownValue) {
    // S=K=100, r=5%, q=0%, vol=20%, T=1yr → ≈ 5.5735
    auto res = blackScholes(makePut(100, 100, 0.05, 0.0, 0.20, 1.0));
    EXPECT_NEAR(res.price, 5.5735, 1e-3);
}

TEST(MonteCarlo, ATMCallApproachesBlackScholes) {
    auto p = makeCall(100, 100, 0.05, 0.0, 0.20, 1.0);
    auto bs = blackScholes(p).price;
    auto mc = monteCarloBSPrice(p, 500000, 12345);
    EXPECT_NEAR(mc, bs, 5e-1); // Monte Carlo std error ~ 0.1 so tolerance 0.5 is safe in CI
}

TEST(MonteCarlo, InvalidParametersThrows) {
    auto invalid = makeCall(0.0, 100, 0.05, 0.0, 0.20, 1.0);
    EXPECT_THROW(monteCarloBSPrice(invalid), std::invalid_argument);
}

TEST(BinomialTree, ConvergesToBlackScholes) {
    auto p = makeCall(100, 100, 0.05, 0.0, 0.20, 1.0);
    double bs = blackScholes(p).price;

    double lowN  = binomialTreeBSPrice(p, 50);
    double midN  = binomialTreeBSPrice(p, 250);
    double highN = binomialTreeBSPrice(p, 2000);

    EXPECT_NEAR(lowN, bs, 3.0);
    EXPECT_NEAR(midN, bs, 1.0);
    EXPECT_NEAR(highN, bs, 0.25);
    EXPECT_LT(std::abs(highN - bs), std::abs(lowN - bs));
}

TEST(BinomialTree, PutConvergesToBlackScholes) {
    auto p = makePut(100, 110, 0.05, 0.0, 0.20, 1.0);
    double bs = blackScholes(p).price;

    double lowN  = binomialTreeBSPrice(p, 50);
    double midN  = binomialTreeBSPrice(p, 250);
    double highN = binomialTreeBSPrice(p, 2000);

    EXPECT_NEAR(lowN, bs, 3.0);
    EXPECT_NEAR(midN, bs, 1.0);
    EXPECT_NEAR(highN, bs, 0.25);
    EXPECT_LT(std::abs(highN - bs), std::abs(lowN - bs));
}

TEST(BinomialTree, AmericanPutAboveEuropean) {
    // American put should be >= European put
    auto american = makePut(100, 110, 0.05, 0.0, 0.20, 1.0);
    american.exercise = ExerciseType::American;

    auto european = makePut(100, 110, 0.05, 0.0, 0.20, 1.0);

    double amPrice = binomialTreeBSPrice(american, 2000);
    double euPrice = binomialTreeBSPrice(european, 2000);

    EXPECT_GE(amPrice, euPrice);
}

TEST(FiniteDifference, ExplicitImplicitCrankConverge) {
    auto p = makeCall(100, 100, 0.05, 0.0, 0.20, 1.0);
    double bsPrice = blackScholes(p).price;

    // Explicit needs finer time grid for CFL stability (dt < 1/(sigma^2*nS^2))
    double expPrice = finiteDifferenceBSPrice(p, 100, 5000, FDMethod::Explicit);
    double impPrice = finiteDifferenceBSPrice(p, 500, 1000, FDMethod::Implicit);
    double cnPrice  = finiteDifferenceBSPrice(p, 500, 1000, FDMethod::CrankNicolson);

    EXPECT_NEAR(cnPrice, bsPrice, 5e-3);    // Crank-Nicolson: O(dt^2 + dS^2)
    EXPECT_NEAR(impPrice, bsPrice, 5e-2);   // Implicit: O(dt + dS^2)
    EXPECT_NEAR(expPrice, bsPrice, 5e-1);   // Explicit: coarser spatial grid
    EXPECT_LT(std::abs(cnPrice - bsPrice), std::abs(impPrice - bsPrice));
}

// ═══════════════════════════════════════════════════════════════════════════
// Greeks
// ═══════════════════════════════════════════════════════════════════════════

TEST(BlackScholes, CallDeltaBetweenZeroAndOne) {
    auto res = blackScholes(makeCall(100, 100, 0.05, 0.0, 0.20, 1.0));
    EXPECT_GT(res.delta, 0.0);
    EXPECT_LT(res.delta, 1.0);
}

TEST(BlackScholes, PutDeltaBetweenMinusOneAndZero) {
    auto res = blackScholes(makePut(100, 100, 0.05, 0.0, 0.20, 1.0));
    EXPECT_LT(res.delta, 0.0);
    EXPECT_GT(res.delta, -1.0);
}

TEST(BlackScholes, GammaPositive) {
    auto res = blackScholes(makeCall(100, 100, 0.05, 0.0, 0.20, 1.0));
    EXPECT_GT(res.gamma, 0.0);
}

TEST(BlackScholes, VegaPositive) {
    auto res = blackScholes(makeCall(100, 100, 0.05, 0.0, 0.20, 1.0));
    EXPECT_GT(res.vega, 0.0);
}

TEST(BlackScholes, CallThetaNegative) {
    // Time decay is negative for long options
    auto res = blackScholes(makeCall(100, 100, 0.05, 0.0, 0.20, 1.0));
    EXPECT_LT(res.theta, 0.0);
}

TEST(BlackScholes, CallRhoPositive) {
    // Call gains value as rate rises
    auto res = blackScholes(makeCall(100, 100, 0.05, 0.0, 0.20, 1.0));
    EXPECT_GT(res.rho, 0.0);
}

TEST(BlackScholes, PutRhoNegative) {
    // Put loses value as rate rises
    auto res = blackScholes(makePut(100, 100, 0.05, 0.0, 0.20, 1.0));
    EXPECT_LT(res.rho, 0.0);
}

TEST(BlackScholes, PutCallDeltaParity) {
    // delta_call - delta_put = exp(-qT)
    double S = 100, K = 100, r = 0.05, q = 0.02, vol = 0.20, T = 1.0;
    auto call = blackScholes(makeCall(S, K, r, q, vol, T));
    auto put  = blackScholes(makePut (S, K, r, q, vol, T));
    EXPECT_NEAR(call.delta - put.delta, std::exp(-q * T), 1e-8);
}

TEST(BlackScholes, CallPutSameGammaAndVega) {
    double S = 100, K = 100, r = 0.05, q = 0.0, vol = 0.20, T = 1.0;
    auto call = blackScholes(makeCall(S, K, r, q, vol, T));
    auto put  = blackScholes(makePut (S, K, r, q, vol, T));
    EXPECT_NEAR(call.gamma, put.gamma, 1e-10);
    EXPECT_NEAR(call.vega,  put.vega,  1e-10);
}

// ═══════════════════════════════════════════════════════════════════════════
// Implied Volatility
// ═══════════════════════════════════════════════════════════════════════════

TEST(BlackScholes, ImpliedVolRoundTrip) {
    double vol = 0.25;
    auto params = makeCall(100, 100, 0.05, 0.0, vol, 1.0);
    double price = blackScholes(params).price;
    double iv    = impliedVolatility(params, price);
    EXPECT_NEAR(iv, vol, 1e-5);
}

TEST(BlackScholes, ImpliedVolOTMCall) {
    double vol = 0.30;
    auto params = makeCall(100, 120, 0.05, 0.0, vol, 1.0);
    double price = blackScholes(params).price;
    double iv    = impliedVolatility(params, price);
    EXPECT_NEAR(iv, vol, 1e-5);
}

TEST(BlackScholes, ImpliedVolITMPut) {
    double vol = 0.18;
    auto params = makePut(100, 110, 0.05, 0.0, vol, 0.5);
    double price = blackScholes(params).price;
    double iv    = impliedVolatility(params, price);
    EXPECT_NEAR(iv, vol, 1e-5);
}

// ═══════════════════════════════════════════════════════════════════════════
// Invalid inputs
// ═══════════════════════════════════════════════════════════════════════════

TEST(BlackScholes, InvalidParamsThrow) {
    // spot <= 0 and maturity <= 0 must throw
    EXPECT_THROW(blackScholes(makeCall(0.0, 100, 0.05, 0.0, 0.20, 1.0)), std::invalid_argument);
    EXPECT_THROW(blackScholes(makeCall(100, 100, 0.05, 0.0, 0.20, 0.0)), std::invalid_argument);
    // strike = 0 is valid: call = S*exp(-qT), put = 0
    EXPECT_NO_THROW(blackScholes(makeCall(100, 0.0, 0.05, 0.0, 0.20, 1.0)));
    // vol = 0 is valid: returns forward intrinsic
    EXPECT_NO_THROW(blackScholes(makeCall(100, 100, 0.05, 0.0, 0.0,  1.0)));
    // negative inputs must throw
    EXPECT_THROW(blackScholes(makeCall(100, -1.0, 0.05, 0.0, 0.20, 1.0)), std::invalid_argument);
    EXPECT_THROW(blackScholes(makeCall(100, 100, 0.05, 0.0, -0.01, 1.0)), std::invalid_argument);
}

// ═══════════════════════════════════════════════════════════════════════════
// Heston Model
// ═══════════════════════════════════════════════════════════════════════════

namespace {
    HestonParams makeHeston(double v0, double kappa, double theta,
                            double sigma, double rho) {
        return {v0, kappa, theta, sigma, rho};
    }
}

TEST(Heston, ConvergesToBSWhenVolOfVolNearZero) {
    // When sigma (vol of vol) ≈ 0, Heston → Black-Scholes with vol = sqrt(v0)
    auto opt = makeCall(100, 100, 0.05, 0.0, 0.20, 1.0);
    auto h = makeHeston(0.04, 2.0, 0.04, 0.001, 0.0);  // sigma≈0, v0=theta=0.04
    double bsPrice = blackScholes(opt).price;
    double hPrice = hestonPrice(opt, h);
    EXPECT_NEAR(hPrice, bsPrice, 0.05);
}

TEST(Heston, PutCallParity) {
    auto call = makeCall(100, 100, 0.05, 0.0, 0.20, 1.0);
    auto put  = makePut (100, 100, 0.05, 0.0, 0.20, 1.0);
    auto h = makeHeston(0.04, 2.0, 0.04, 0.3, -0.7);
    double C = hestonPrice(call, h);
    double P = hestonPrice(put, h);
    double parity = C - P - (100.0 * std::exp(-0.0) - 100.0 * std::exp(-0.05));
    EXPECT_NEAR(parity, 0.0, 1e-4);
}

TEST(Heston, CallPricePositive) {
    auto opt = makeCall(100, 100, 0.05, 0.0, 0.20, 1.0);
    auto h = makeHeston(0.04, 2.0, 0.04, 0.3, -0.7);
    EXPECT_GT(hestonPrice(opt, h), 0.0);
}

TEST(Heston, PutPricePositive) {
    auto opt = makePut(100, 100, 0.05, 0.0, 0.20, 1.0);
    auto h = makeHeston(0.04, 2.0, 0.04, 0.3, -0.7);
    EXPECT_GT(hestonPrice(opt, h), 0.0);
}

TEST(Heston, HigherVolOfVolWidensSmile) {
    // Higher vol of vol increases OTM put prices (fatter left tail)
    auto otmPut = makePut(100, 80, 0.05, 0.0, 0.20, 1.0);
    auto hLow  = makeHeston(0.04, 2.0, 0.04, 0.1, -0.5);
    auto hHigh = makeHeston(0.04, 2.0, 0.04, 0.8, -0.5);
    EXPECT_GT(hestonPrice(otmPut, hHigh), hestonPrice(otmPut, hLow));
}

TEST(Heston, MonteCarloApproachesAnalytical) {
    auto opt = makeCall(100, 100, 0.05, 0.0, 0.20, 1.0);
    auto h = makeHeston(0.04, 2.0, 0.04, 0.3, -0.5);
    double analytic = hestonPrice(opt, h);
    double mc = hestonMonteCarlo(opt, h, 200000, 252, 42);
    EXPECT_NEAR(mc, analytic, 1.0);  // MC has variance; 1.0 tolerance is safe
}

TEST(Heston, InvalidParamsThrow) {
    auto opt = makeCall(100, 100, 0.05, 0.0, 0.20, 1.0);
    EXPECT_THROW(hestonPrice(opt, makeHeston(0.04, 2.0, 0.04, 0.0, -0.5)),
                 std::invalid_argument);  // sigma = 0
    EXPECT_THROW(hestonPrice(opt, makeHeston(0.04, 2.0, 0.04, 0.3, 1.5)),
                 std::invalid_argument);  // |rho| > 1
}
