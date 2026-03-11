#include <gtest/gtest.h>
#include <qf/instruments/bond.hpp>
#include <qf/instruments/swap.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <cmath>

using namespace qf::instruments;
using namespace qf::termstructure;
using namespace qf::math;

namespace {
    // Flat curve helper
    YieldCurve flatCurve(double rate) {
        return YieldCurve({0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0},
                          {rate, rate, rate, rate, rate, rate, rate},
                          InterpolationMethod::Linear);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Bond pricing
// ═══════════════════════════════════════════════════════════════════════════

TEST(Bond, ParPriceWhenCouponEqualsYield) {
    // Under continuous discounting, par pricing holds when coupon_rate = freq*(exp(r/freq)-1),
    // not when coupon_rate == r.  Verify with the analytically correct par coupon.
    double r = 0.05, freq = 2.0;
    double par_coupon_rate = freq * (std::exp(r / freq) - 1.0); // ≈ 0.050626
    auto curve = flatCurve(r);
    Bond bond(1000.0, par_coupon_rate, 10, freq);
    EXPECT_NEAR(bond.price(curve), 1000.0, 1e-6);
}

TEST(Bond, PremiumWhenCouponAboveYield) {
    // Coupon 6% > yield 5% → price > par
    auto curve = flatCurve(0.05);
    Bond bond(1000.0, 0.06, 10, 2.0);
    EXPECT_GT(bond.price(curve), 1000.0);
}

TEST(Bond, DiscountWhenCouponBelowYield) {
    // Coupon 4% < yield 5% → price < par
    auto curve = flatCurve(0.05);
    Bond bond(1000.0, 0.04, 10, 2.0);
    EXPECT_LT(bond.price(curve), 1000.0);
}

TEST(Bond, ZeroCouponBondAnalytical) {
    // Zero coupon bond: price = face * exp(-r * T)
    double r = 0.05, T = 5.0, face = 1000.0;
    auto curve = flatCurve(r);
    Bond zcb(face, 0.0, 1, 1.0 / T);  // 1 period at T years
    double expected = face * std::exp(-r * T);
    EXPECT_NEAR(zcb.price(curve), expected, 1e-4);
}

TEST(Bond, PriceDecreaseAsYieldIncrease) {
    Bond bond(1000.0, 0.05, 10, 2.0);
    double p1 = bond.price(flatCurve(0.04));
    double p2 = bond.price(flatCurve(0.06));
    EXPECT_GT(p1, p2);
}

// ═══════════════════════════════════════════════════════════════════════════
// YTM round-trip
// ═══════════════════════════════════════════════════════════════════════════

TEST(Bond, YTMRoundTrip) {
    // Price a bond then recover YTM — must match original yield curve rate
    double rate = 0.055;
    auto curve = flatCurve(rate);
    Bond bond(1000.0, 0.06, 10, 2.0);
    double price = bond.price(curve);
    double ytm   = bond.yield(price);
    // Re-price using flat curve at recovered YTM
    double reprice = bond.price(flatCurve(ytm));
    EXPECT_NEAR(reprice, price, 1e-4);
}

TEST(Bond, YTMEqualsRateAtPar) {
    double rate = 0.05;
    auto curve = flatCurve(rate);
    Bond bond(1000.0, rate, 10, 2.0);
    double ytm = bond.yield(bond.price(curve));
    EXPECT_NEAR(ytm, rate, 1e-6);
}

// ═══════════════════════════════════════════════════════════════════════════
// Duration & Convexity
// ═══════════════════════════════════════════════════════════════════════════

TEST(Bond, DurationPositive) {
    auto curve = flatCurve(0.05);
    Bond bond(1000.0, 0.05, 10, 2.0);
    EXPECT_GT(bond.duration(curve), 0.0);
}

TEST(Bond, DurationLessThanMaturity) {
    // Modified duration < maturity (coupon bond)
    auto curve = flatCurve(0.05);
    Bond bond(1000.0, 0.05, 10, 2.0); // 5yr
    EXPECT_LT(bond.duration(curve), 5.0);
}

TEST(Bond, LongerBondHasHigherDuration) {
    auto curve = flatCurve(0.05);
    Bond short_bond(1000.0, 0.05, 4,  2.0); // 2yr
    Bond long_bond (1000.0, 0.05, 10, 2.0); // 5yr
    EXPECT_GT(long_bond.duration(curve), short_bond.duration(curve));
}

TEST(Bond, ConvexityPositive) {
    auto curve = flatCurve(0.05);
    Bond bond(1000.0, 0.05, 10, 2.0);
    EXPECT_GT(bond.convexity(curve), 0.0);
}

// ═══════════════════════════════════════════════════════════════════════════
// Invalid inputs
// ═══════════════════════════════════════════════════════════════════════════

TEST(Bond, InvalidPeriodsThrows) {
    EXPECT_THROW(Bond(1000.0, 0.05, 0, 2.0), std::invalid_argument);
    EXPECT_THROW(Bond(1000.0, 0.05, -1, 2.0), std::invalid_argument);
}

TEST(Bond, InvalidFrequencyThrows) {
    EXPECT_THROW(Bond(1000.0, 0.05, 10, 0.0), std::invalid_argument);
}

// ═══════════════════════════════════════════════════════════════════════════
// Interest Rate Swap
// ═══════════════════════════════════════════════════════════════════════════

namespace {
    YieldCurve swapCurve() {
        return YieldCurve({0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 30.0},
                          {0.03, 0.035, 0.04, 0.042, 0.045, 0.05, 0.053, 0.054},
                          InterpolationMethod::CubicSpline);
    }
}

TEST(Swap, ParRateGivesZeroNPV) {
    auto curve = swapCurve();
    double parR = InterestRateSwap::parRate(5.0, 2.0, curve);
    InterestRateSwap swap(1e6, parR, 5.0, 2.0, SwapType::Payer);
    EXPECT_NEAR(swap.npv(curve), 0.0, 1e-6);
}

TEST(Swap, PayerReceiverSymmetry) {
    auto curve = swapCurve();
    InterestRateSwap payer(1e6, 0.04, 5.0, 2.0, SwapType::Payer);
    InterestRateSwap receiver(1e6, 0.04, 5.0, 2.0, SwapType::Receiver);
    EXPECT_NEAR(payer.npv(curve) + receiver.npv(curve), 0.0, 1e-10);
}

TEST(Swap, PayerPositiveWhenFixedBelowPar) {
    auto curve = swapCurve();
    double parR = InterestRateSwap::parRate(5.0, 2.0, curve);
    InterestRateSwap swap(1e6, parR - 0.01, 5.0, 2.0, SwapType::Payer);
    EXPECT_GT(swap.npv(curve), 0.0);
}

TEST(Swap, PayerNegativeWhenFixedAbovePar) {
    auto curve = swapCurve();
    double parR = InterestRateSwap::parRate(5.0, 2.0, curve);
    InterestRateSwap swap(1e6, parR + 0.01, 5.0, 2.0, SwapType::Payer);
    EXPECT_LT(swap.npv(curve), 0.0);
}

TEST(Swap, AnnuityPositive) {
    auto curve = swapCurve();
    InterestRateSwap swap(1e6, 0.04, 5.0, 2.0, SwapType::Payer);
    EXPECT_GT(swap.annuity(curve), 0.0);
}

TEST(Swap, LongerSwapHasLargerAnnuity) {
    auto curve = swapCurve();
    InterestRateSwap short_swap(1e6, 0.04, 2.0, 2.0, SwapType::Payer);
    InterestRateSwap long_swap(1e6, 0.04, 10.0, 2.0, SwapType::Payer);
    EXPECT_GT(long_swap.annuity(curve), short_swap.annuity(curve));
}

TEST(Swap, ParRateOnFlatCurve) {
    // On a flat curve, par rate ≈ the zero rate (approximately for continuous)
    auto flat = flatCurve(0.05);
    double parR = InterestRateSwap::parRate(5.0, 2.0, flat);
    EXPECT_NEAR(parR, 0.05, 0.005); // within 50bps due to compounding convention
}

TEST(Swap, NPVScalesWithNotional) {
    auto curve = swapCurve();
    InterestRateSwap s1(1e6, 0.04, 5.0, 2.0, SwapType::Payer);
    InterestRateSwap s2(2e6, 0.04, 5.0, 2.0, SwapType::Payer);
    EXPECT_NEAR(s2.npv(curve), 2.0 * s1.npv(curve), 1e-8);
}

TEST(Swap, InvalidParamsThrow) {
    EXPECT_THROW(InterestRateSwap(0.0, 0.04, 5.0, 2.0, SwapType::Payer),
                 std::invalid_argument);
    EXPECT_THROW(InterestRateSwap(1e6, 0.04, 0.0, 2.0, SwapType::Payer),
                 std::invalid_argument);
    EXPECT_THROW(InterestRateSwap(1e6, 0.04, 5.0, 0.0, SwapType::Payer),
                 std::invalid_argument);
}

TEST(Swap, LegAndSwapPV) {
    auto curve = swapCurve();
    Leg payLeg("USD", "ACT/365", 1e6, 5.0, 0.04, 0.0, false);
    Leg receiveLeg("USD", "ACT/365", 1e6, 5.0, 0.0, 0.0, true);
    Swap swap(payLeg, receiveLeg, SwapLegType::FixedFloating);

    double expected = payLeg.pv(curve) - receiveLeg.pv(curve);
    EXPECT_NEAR(swap.npv(curve), expected, 1e-8);
    EXPECT_NEAR(swap.pv(curve), expected, 1e-8);
}
