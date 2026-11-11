#include <gtest/gtest.h>
#include <qf/instruments/swaption.hpp>
#include <qf/instruments/swap.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/interpolation.hpp>
#include <qf/core/market_environment.hpp>
#include <algorithm>
#include <cmath>
#include <vector>

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

// ═══════════════════════════════════════════════════════════════════════════
// Guard: a swap tenor shorter than half a payment period rounds to zero payments
// ═══════════════════════════════════════════════════════════════════════════

TEST(Swaption, PriceThrowsWhenTenorCoversNoPayments) {
    auto curve = flatCurve();
    // 0.1y tenor at 2 payments/year -> round(0.2) = 0 payments (used to write c[-1]).
    Swaption none(SwaptionType::Payer, 1e6, 0.05, 1.0, 0.1, 2.0, 0.1, 0.01);
    EXPECT_THROW(none.price(curve), std::invalid_argument);
    EXPECT_THROW(none.calculatePV(MarketEnvironment(curve)), std::invalid_argument);

    // Exactly half a period rounds up to one payment and still prices.
    Swaption one(SwaptionType::Payer, 1e6, 0.05, 1.0, 0.25, 2.0, 0.1, 0.01);
    EXPECT_NO_THROW(one.price(curve));
}

// ═══════════════════════════════════════════════════════════════════════════
// Dual-curve pricing (QF Desk, corte 3): price(projection) x annuity ratio
// ═══════════════════════════════════════════════════════════════════════════

TEST(SwaptionDual, SameCurveForBothGivesThePlainPrice) {
    auto curve = slopedCurve();
    for (SwaptionType type : {SwaptionType::Payer, SwaptionType::Receiver}) {
        Swaption s(type, 1e8, 0.05, 1.0, 5.0, 2.0, 0.03, 0.01);
        double plain = s.price(curve);
        EXPECT_LT(std::fabs(s.priceDualCurve(curve, curve) - plain) / std::fabs(plain), 1e-12);
    }
}

TEST(SwaptionDual, IsThePriceTimesTheAnnuityRatio) {
    auto projection = flatCurve(0.05);
    auto discount   = flatCurve(0.048);   // 20 bp below: discounts less
    for (SwaptionType type : {SwaptionType::Payer, SwaptionType::Receiver}) {
        const double expiry = 1.0, tenor = 5.0, freq = 2.0;
        Swaption s(type, 1e8, 0.05, expiry, tenor, freq, 0.03, 0.01);
        double ratio = annuity(discount, expiry, tenor, freq) / annuity(projection, expiry, tenor, freq);
        double expected = s.price(projection) * ratio;
        EXPECT_LT(std::fabs(s.priceDualCurve(projection, discount) - expected) / std::fabs(expected), 1e-12);
        EXPECT_GT(ratio, 1.0);
        EXPECT_GT(s.priceDualCurve(projection, discount), s.price(projection));
    }
}

TEST(SwaptionDual, ThrowsWhenTheTenorCoversNoPayments) {
    auto curve = flatCurve();
    Swaption none(SwaptionType::Payer, 1e6, 0.05, 1.0, 0.1, 2.0, 0.1, 0.01);
    EXPECT_THROW(none.priceDualCurve(curve, curve), std::invalid_argument);
}

// ═══════════════════════════════════════════════════════════════════════════
// Short expiry / strike away from the forward swap rate (found by the desk's
// independent validation against QuantLib, swaption-04).
//
// The Jamshidian root r* used to be solved in "deviation" coordinates while the
// bisection bracket was centred on f(0,T_exp); with a short expiry the bracket
// is narrow (10·σ_r ≈ 7 %) and, on a 6.8 % curve, did not contain the root, so
// price() returned 0.0 for an option worth ≈ 0.2 % of the notional.
// ═══════════════════════════════════════════════════════════════════════════

namespace {

// Price independent of Jamshidian: P(0,T_exp) · E^{T_exp}[ max(±(N − Σ c_i P(T_exp,T_i)), 0) ],
// integrating the payoff over the Hull-White short rate at expiry. Under the T_exp-forward
// measure r(T_exp) ~ N(f(0,T_exp), V) with V = σ²/(2a)·(1 − e^{−2a·T_exp}), and
//   P(T_exp,T_i | r) = F_i · exp(B_i·(f0 − r) − V/2·B_i²),  F_i = P(0,T_i)/P(0,T_exp)
// so, writing r = f0 + √V·z, f0 cancels: P_i(z) = F_i · exp(−V/2·B_i² − B_i·√V·z).
// No Jamshidian decomposition and no bond-option formula: a direct numerical integral over z ∈ [−12, 12].
double quadraturePrice(const YieldCurve& curve, SwaptionType type, double N, double K,
                       double T_exp, double tenor, double freq, double a, double sigma)
{
    const int    n   = static_cast<int>(std::round(tenor * freq));
    const double dt  = 1.0 / freq;
    const double V   = sigma * sigma / (2.0 * a) * (1.0 - std::exp(-2.0 * a * T_exp));
    const double P0e = curve.discountFactor(T_exp);

    std::vector<double> F(n), B(n), c(n, N * K * dt);
    c[n - 1] += N;
    for (int i = 0; i < n; ++i) {
        F[i] = curve.discountFactor(T_exp + (i + 1) * dt) / P0e;
        B[i] = (1.0 - std::exp(-a * (i + 1) * dt)) / a;
    }

    auto fixedBondValue = [&](double z) {
        double v = 0.0;
        for (int i = 0; i < n; ++i)
            v += c[i] * F[i] * std::exp(-0.5 * V * B[i] * B[i] - B[i] * std::sqrt(V) * z);
        return v;
    };
    auto payoffDensity = [&](double z) {
        double bond = fixedBondValue(z);
        double payoff = (type == SwaptionType::Payer) ? std::max(N - bond, 0.0)
                                                      : std::max(bond - N, 0.0);
        return payoff * std::exp(-0.5 * z * z) / std::sqrt(2.0 * M_PI);
    };

    // The payoff has a kink where the fixed bond is worth N (decreasing in z): find it by
    // bisection and integrate each side separately, where the integrand is smooth, with Simpson.
    const double zMax = 12.0;
    double zl = -zMax, zh = zMax;
    for (int it = 0; it < 200; ++it) {
        double zm = 0.5 * (zl + zh);
        (fixedBondValue(zm) > N ? zl : zh) = zm;
    }
    const double zKink = 0.5 * (zl + zh);

    auto simpson = [&](double lo, double hi) {
        const int m = 4000;                      // even number of intervals
        const double h = (hi - lo) / m;
        double sum = payoffDensity(lo) + payoffDensity(hi);
        for (int k = 1; k < m; ++k)
            sum += payoffDensity(lo + k * h) * (k % 2 ? 4.0 : 2.0);
        return sum * h / 3.0;
    };
    return P0e * (simpson(-zMax, zKink) + simpson(zKink, zMax));
}

} // namespace

TEST(SwaptionShortExpiry, ReceiverOutOfTheMoneyIsPositive) {
    // The desk's swaption-04: receiver K = 6.5 % expiring in 182 days on a 6.8 % curve,
    // 1y tenor paid every 28 days. Forward swap rate ≈ 6.8 % > K, so the receiver is OTM
    // but alive (QuantLib: ≈ 0.18 % of the notional on the real curve); price() gave 0.0.
    auto curve = flatCurve(0.068);
    const double freq = 365.0 / 28.0;
    Swaption s(SwaptionType::Receiver, 50e6, 0.065, 182.0 / 365.0, 1.0, freq, 0.05, 0.01);
    double p = s.price(curve);
    EXPECT_GT(p, 0.0);
    EXPECT_GT(p / 50e6, 1e-4);   // far from a numerical zero
    EXPECT_LT(p / 50e6, 1e-2);   // and far from intrinsic-sized values
}

TEST(SwaptionShortExpiry, PayerOutOfTheMoneyIsPositiveToo) {
    auto curve = flatCurve(0.068);
    const double freq = 365.0 / 28.0;
    Swaption s(SwaptionType::Payer, 50e6, 0.072, 182.0 / 365.0, 1.0, freq, 0.05, 0.01);
    EXPECT_GT(s.price(curve) / 50e6, 1e-4);
}

TEST(SwaptionShortExpiry, ParityHoldsWhenTheStrikeIsFarFromTheForwardRate) {
    // Payer − Receiver = forward payer IRS, for any strike. With the defect both legs
    // returned 0.0 here, so the difference was 0 instead of the (large) swap value.
    auto curve = flatCurve(0.068);
    const double N = 1e6, T_exp = 0.25, tenor = 1.0, freq = 2.0, a = 0.05, sigma = 0.01;
    for (double K : {0.045, 0.055, 0.065, 0.068, 0.075, 0.09}) {
        Swaption payer   (SwaptionType::Payer,    N, K, T_exp, tenor, freq, a, sigma);
        Swaption receiver(SwaptionType::Receiver, N, K, T_exp, tenor, freq, a, sigma);
        double diff     = payer.price(curve) - receiver.price(curve);
        double expected = irsNPV(curve, N, K, T_exp, tenor, freq);
        EXPECT_NEAR(diff, expected, 1e-3) << "K = " << K;   // $0.001 on $1M
    }
}

TEST(SwaptionShortExpiry, MatchesTheQuadratureReference) {
    struct Case { double rate, K, T_exp, tenor, freq, a, sigma; };
    const Case cases[] = {
        {0.068, 0.065, 182.0 / 365.0, 1.0, 365.0 / 28.0, 0.05, 0.010},  // swaption-04
        {0.068, 0.070, 1.0,           2.0, 365.0 / 28.0, 0.05, 0.010},
        {0.050, 0.050, 0.25,          1.0, 4.0,          0.10, 0.012},
        {0.050, 0.030, 0.25,          3.0, 2.0,          0.10, 0.012},  // strike 2 % below
        {0.050, 0.080, 0.10,          2.0, 4.0,          0.10, 0.012},  // very short, 3 % above
        {0.036, 0.040, 5.0,          10.0, 1.0,          0.03, 0.030},  // long, large σ: A's variance term matters
    };
    for (const Case& c : cases) {
        auto curve = flatCurve(c.rate);
        for (SwaptionType type : {SwaptionType::Payer, SwaptionType::Receiver}) {
            const double N = 1e8;
            Swaption s(type, N, c.K, c.T_exp, c.tenor, c.freq, c.a, c.sigma);
            double ref = quadraturePrice(curve, type, N, c.K, c.T_exp, c.tenor, c.freq, c.a, c.sigma);
            EXPECT_NEAR(s.price(curve) / N, ref / N, 1e-9)
                << (type == SwaptionType::Payer ? "payer" : "receiver")
                << " rate=" << c.rate << " K=" << c.K << " T=" << c.T_exp << " tenor=" << c.tenor;
        }
    }
}

TEST(SwaptionShortExpiry, MatchesTheQuadratureReferenceOnASlopedCurve) {
    auto curve = slopedCurve();
    for (SwaptionType type : {SwaptionType::Payer, SwaptionType::Receiver}) {
        for (double K : {0.02, 0.04, 0.07}) {
            const double N = 1e8, T_exp = 0.4, tenor = 2.0, freq = 4.0, a = 0.15, sigma = 0.015;
            Swaption s(type, N, K, T_exp, tenor, freq, a, sigma);
            double ref = quadraturePrice(curve, type, N, K, T_exp, tenor, freq, a, sigma);
            EXPECT_NEAR(s.price(curve) / N, ref / N, 1e-9)
                << (type == SwaptionType::Payer ? "payer" : "receiver") << " K=" << K;
        }
    }
}

TEST(SwaptionShortExpiry, DualCurveInheritsTheFix) {
    auto projection = flatCurve(0.068);
    auto discount   = flatCurve(0.066);
    const double freq = 365.0 / 28.0;
    Swaption s(SwaptionType::Receiver, 50e6, 0.065, 182.0 / 365.0, 1.0, freq, 0.05, 0.01);
    EXPECT_GT(s.priceDualCurve(projection, discount), 0.0);
}
