#include <gtest/gtest.h>
#include <qf/instruments/swaption.hpp>
#include <qf/instruments/swap.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/interpolation.hpp>
#include <qf/core/market_environment.hpp>
#include <cmath>

using namespace qf::instruments;
using namespace qf::termstructure;
using namespace qf::math;
using namespace qf::core;

namespace {

YieldCurve flatCurve(double r = 0.05) {
    return YieldCurve({0.5, 1.0, 2.0, 5.0, 10.0},
                      {r, r, r, r, r},
                      InterpolationMethod::CubicSpline);
}

YieldCurve slopedCurve() {
    return YieldCurve({0.5, 1.0, 2.0, 5.0, 10.0},
                      {0.03, 0.035, 0.04, 0.05, 0.06},
                      InterpolationMethod::CubicSpline);
}

// IRS annuity starting at T_exp
static double annuity(const YieldCurve& curve,
                       double T_exp, double tenor, double frequency)
{
    double tau = 1.0 / frequency;
    int n = static_cast<int>(std::round(tenor * frequency));
    double A = 0.0;
    for (int i = 1; i <= n; ++i)
        A += tau * curve.discountFactor(T_exp + i * tau);
    return A;
}

// Payer IRS NPV starting at T_exp (forward starting)
static double irsNPV(const YieldCurve& curve, double notional,
                      double strike, double T_exp, double tenor, double frequency)
{
    double P_exp = curve.discountFactor(T_exp);
    double P_end = curve.discountFactor(T_exp + tenor);
    double A     = annuity(curve, T_exp, tenor, frequency);
    return notional * (P_exp - P_end - strike * A);
}

} // namespace

// ═══════════════════════════════════════════════════════════════════════════
// Construction and validation
// ═══════════════════════════════════════════════════════════════════════════

TEST(Swaption, InvalidParamsThrow) {
    EXPECT_THROW(Swaption(SwaptionType::Payer,    0.0, 0.05, 1.0, 5.0, 2.0, 0.1, 0.01),
                 std::invalid_argument); // zero notional
    EXPECT_THROW(Swaption(SwaptionType::Payer, 1e6,    0.0, 1.0, 5.0, 2.0, 0.1, 0.01),
                 std::invalid_argument); // zero strike
    EXPECT_THROW(Swaption(SwaptionType::Payer, 1e6, 0.05,   0.0, 5.0, 2.0, 0.1, 0.01),
                 std::invalid_argument); // zero expiry
    EXPECT_THROW(Swaption(SwaptionType::Payer, 1e6, 0.05, 1.0,   0.0, 2.0, 0.1, 0.01),
                 std::invalid_argument); // zero tenor
    EXPECT_THROW(Swaption(SwaptionType::Payer, 1e6, 0.05, 1.0, 5.0,   0.0, 0.1, 0.01),
                 std::invalid_argument); // zero frequency
    EXPECT_THROW(Swaption(SwaptionType::Payer, 1e6, 0.05, 1.0, 5.0, 2.0,   0.0, 0.01),
                 std::invalid_argument); // zero a
    EXPECT_THROW(Swaption(SwaptionType::Payer, 1e6, 0.05, 1.0, 5.0, 2.0, 0.1,   0.0),
                 std::invalid_argument); // zero sigma
}

TEST(Swaption, AccessorsReturnConstructedValues) {
    Swaption s(SwaptionType::Receiver, 1e6, 0.05, 1.0, 5.0, 2.0, 0.1, 0.01);
    EXPECT_EQ(s.type(),      SwaptionType::Receiver);
    EXPECT_DOUBLE_EQ(s.notional(),  1e6);
    EXPECT_DOUBLE_EQ(s.strike(),    0.05);
    EXPECT_DOUBLE_EQ(s.expiry(),    1.0);
    EXPECT_DOUBLE_EQ(s.swapTenor(), 5.0);
    EXPECT_DOUBLE_EQ(s.frequency(), 2.0);
    EXPECT_DOUBLE_EQ(s.hwA(),       0.1);
    EXPECT_DOUBLE_EQ(s.hwSigma(),   0.01);
}

// ═══════════════════════════════════════════════════════════════════════════
// Non-negativity
// ═══════════════════════════════════════════════════════════════════════════

TEST(Swaption, PayerPriceNonNegative) {
    auto curve = flatCurve();
    Swaption s(SwaptionType::Payer, 1e6, 0.05, 1.0, 5.0, 2.0, 0.1, 0.01);
    EXPECT_GE(s.price(curve), 0.0);
}

TEST(Swaption, ReceiverPriceNonNegative) {
    auto curve = flatCurve();
    Swaption s(SwaptionType::Receiver, 1e6, 0.05, 1.0, 5.0, 2.0, 0.1, 0.01);
    EXPECT_GE(s.price(curve), 0.0);
}

// ═══════════════════════════════════════════════════════════════════════════
// Payer-Receiver parity:
//   Payer(K) − Receiver(K) = PV of forward-starting payer IRS at rate K
// ═══════════════════════════════════════════════════════════════════════════

TEST(Swaption, PayerReceiverParityFlatCurve) {
    auto curve = flatCurve();
    const double N = 1e6, K = 0.05, T_exp = 1.0, tenor = 5.0, freq = 2.0;
    const double a = 0.1, sigma = 0.01;

    Swaption payer   (SwaptionType::Payer,    N, K, T_exp, tenor, freq, a, sigma);
    Swaption receiver(SwaptionType::Receiver, N, K, T_exp, tenor, freq, a, sigma);

    double diff     = payer.price(curve) - receiver.price(curve);
    double expected = irsNPV(curve, N, K, T_exp, tenor, freq);

    EXPECT_NEAR(diff, expected, 10.0); // within $10 on $1M
}

TEST(Swaption, PayerReceiverParitySlopedCurve) {
    auto curve = slopedCurve();
    const double N = 1e6, K = 0.04, T_exp = 2.0, tenor = 3.0, freq = 4.0;
    const double a = 0.15, sigma = 0.015;

    Swaption payer   (SwaptionType::Payer,    N, K, T_exp, tenor, freq, a, sigma);
    Swaption receiver(SwaptionType::Receiver, N, K, T_exp, tenor, freq, a, sigma);

    double diff     = payer.price(curve) - receiver.price(curve);
    double expected = irsNPV(curve, N, K, T_exp, tenor, freq);

    EXPECT_NEAR(diff, expected, 10.0);
}

// ═══════════════════════════════════════════════════════════════════════════
// ATM swaption: payer == receiver when strike == par rate of the fwd swap
// ═══════════════════════════════════════════════════════════════════════════

TEST(Swaption, ATMPayerEqualsReceiver) {
    auto curve = slopedCurve();
    const double N = 1e6, T_exp = 1.0, tenor = 3.0, freq = 2.0;
    const double a = 0.15, sigma = 0.015;

    // Compute par rate of the forward-starting swap
    double K_atm = irsNPV(curve, 1.0 /*unit*/, 0.0, T_exp, tenor, freq);
    // K_par: IRS NPV(K_par) = 0  =>  P(0,T_exp)-P(0,T_exp+tenor) = K_par * A
    double A = annuity(curve, T_exp, tenor, freq);
    double P_exp = curve.discountFactor(T_exp);
    double P_end = curve.discountFactor(T_exp + tenor);
    K_atm = (P_exp - P_end) / (A > 0 ? A : 1.0);

    Swaption payer   (SwaptionType::Payer,    N, K_atm, T_exp, tenor, freq, a, sigma);
    Swaption receiver(SwaptionType::Receiver, N, K_atm, T_exp, tenor, freq, a, sigma);

    // At par strike: payer - receiver = IRS NPV ≈ 0, so payer ≈ receiver
    double diff = std::abs(payer.price(curve) - receiver.price(curve));
    EXPECT_LT(diff, 5.0); // within $5 on $1M (IRS NPV at par rate is ~0)
}

// ═══════════════════════════════════════════════════════════════════════════
// Monotonicity in vol: higher σ → higher price
// ═══════════════════════════════════════════════════════════════════════════

TEST(Swaption, PayerPriceIncreasesWithVol) {
    auto curve = flatCurve();
    Swaption s1(SwaptionType::Payer, 1e6, 0.05, 1.0, 5.0, 2.0, 0.1, 0.005);
    Swaption s2(SwaptionType::Payer, 1e6, 0.05, 1.0, 5.0, 2.0, 0.1, 0.02);
    EXPECT_GT(s2.price(curve), s1.price(curve));
}

TEST(Swaption, ReceiverPriceIncreasesWithVol) {
    auto curve = flatCurve();
    Swaption s1(SwaptionType::Receiver, 1e6, 0.05, 1.0, 5.0, 2.0, 0.1, 0.005);
    Swaption s2(SwaptionType::Receiver, 1e6, 0.05, 1.0, 5.0, 2.0, 0.1, 0.02);
    EXPECT_GT(s2.price(curve), s1.price(curve));
}

// ═══════════════════════════════════════════════════════════════════════════
// Monotonicity in expiry: longer expiry → higher vol exposure → higher price
// ═══════════════════════════════════════════════════════════════════════════

TEST(Swaption, PayerPriceIncreasesWithExpiry) {
    auto curve = flatCurve();
    Swaption s1(SwaptionType::Payer, 1e6, 0.05, 0.5, 5.0, 2.0, 0.1, 0.01);
    Swaption s2(SwaptionType::Payer, 1e6, 0.05, 2.0, 5.0, 2.0, 0.1, 0.01);
    EXPECT_GT(s2.price(curve), s1.price(curve));
}

// ═══════════════════════════════════════════════════════════════════════════
// Deep OTM → near zero
// ═══════════════════════════════════════════════════════════════════════════

TEST(Swaption, DeepOTMPayerNearZero) {
    auto curve = flatCurve(0.05);
    // Strike 20% on a 5% curve — very deep OTM payer
    Swaption s(SwaptionType::Payer, 1e6, 0.20, 1.0, 5.0, 2.0, 0.1, 0.01);
    EXPECT_NEAR(s.price(curve), 0.0, 1.0); // less than $1
}

TEST(Swaption, DeepOTMReceiverNearZero) {
    auto curve = flatCurve(0.05);
    // Strike 0.5% on a 5% curve — very deep OTM receiver
    Swaption s(SwaptionType::Receiver, 1e6, 0.005, 1.0, 5.0, 2.0, 0.1, 0.01);
    EXPECT_NEAR(s.price(curve), 0.0, 1.0);
}

// ═══════════════════════════════════════════════════════════════════════════
// Notional scaling
// ═══════════════════════════════════════════════════════════════════════════

TEST(Swaption, PriceScalesWithNotional) {
    auto curve = flatCurve();
    Swaption s1(SwaptionType::Payer,  1e6, 0.05, 1.0, 5.0, 2.0, 0.1, 0.01);
    Swaption s2(SwaptionType::Payer,  2e6, 0.05, 1.0, 5.0, 2.0, 0.1, 0.01);
    EXPECT_NEAR(s2.price(curve), 2.0 * s1.price(curve), 1e-4);
}

// ═══════════════════════════════════════════════════════════════════════════
// MarketEnvironment interface
// ═══════════════════════════════════════════════════════════════════════════

TEST(Swaption, CalculatePVMatchesPrice) {
    auto curve = flatCurve();
    MarketEnvironment env(curve);
    Swaption s(SwaptionType::Payer, 1e6, 0.05, 1.0, 5.0, 2.0, 0.1, 0.01);
    EXPECT_DOUBLE_EQ(s.calculatePV(env), s.price(curve));
}
