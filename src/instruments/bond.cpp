#include <qf/instruments/bond.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/math/rootfinding.hpp>
#include <qf/math/daycount.hpp>
#include <cmath>
#include <stdexcept>
#include <numeric>

namespace qf::instruments {

Bond::Bond(double faceValue, double couponRate, int periods, double frequency,
           math::DayCountConvention dcc)
    : Instrument(static_cast<double>(periods) / frequency),
      faceValue_(faceValue), couponRate_(couponRate),
      periods_(periods), frequency_(frequency), dcc_(dcc)
{
    if (periods <= 0)
        throw std::invalid_argument("Bond: periods must be positive");
    if (frequency <= 0.0)
        throw std::invalid_argument("Bond: frequency must be positive");
}

std::vector<double> Bond::cashflows() const
{
    // tau: accrual fraction per period, determined by the day-count convention.
    double tau    = math::periodFraction(frequency_, dcc_);
    double coupon = faceValue_ * couponRate_ * tau;
    std::vector<double> cf(periods_, coupon);
    cf.back() += faceValue_; // principal at maturity
    return cf;
}

std::vector<double> Bond::maturities() const
{
    std::vector<double> t(periods_);
    for (int i = 0; i < periods_; ++i)
        t[i] = (i + 1.0) / frequency_;
    return t;
}

double Bond::price(const termstructure::YieldCurve& curve) const
{
    auto cf = cashflows();
    auto t  = maturities();
    double pv = 0.0;
    for (int i = 0; i < periods_; ++i)
        pv += cf[i] * curve.discountFactor(t[i]);
    return pv;
}

double Bond::calculatePV(const core::MarketEnvironment& env) const
{
    return price(env.curve());
}

double Bond::yield(double marketPrice) const
{
    // Find y such that sum(cf[i] * exp(-y * t[i])) = marketPrice
    auto cf = cashflows();
    auto t  = maturities();

    auto priceFn = [&](double y) {
        double pv = 0.0;
        for (int i = 0; i < periods_; ++i)
            pv += cf[i] * std::exp(-y * t[i]);
        return pv - marketPrice;
    };

    // Bracket: covers negative yields (distressed/sovereign) and very high yields.
    double lo = -0.30, hi = 0.10;
    // Extend hi until we bracket the root (price fn changes sign)
    while (priceFn(hi) > 0.0 && hi < 50.0) hi += 0.10;
    // Extend lo downward if needed (very negative yields)
    while (priceFn(lo) < 0.0 && lo > -5.0) lo -= 0.10;
    if (priceFn(lo) * priceFn(hi) > 0.0)
        throw std::runtime_error("Bond::yield: failed to bracket root — check market price");

    return math::brent(priceFn, lo, hi);
}

double Bond::duration(const termstructure::YieldCurve& curve) const
{
    // Modified duration: -dP/dy / P
    auto cf = cashflows();
    auto t  = maturities();
    double pv = 0.0, weighted = 0.0;
    for (int i = 0; i < periods_; ++i) {
        double df = curve.discountFactor(t[i]);
        pv       += cf[i] * df;
        weighted += t[i] * cf[i] * df;
    }
    // Under continuous compounding (the convention used throughout this library),
    // modified duration equals Macaulay duration: D_mod = D_mac / exp(y*dt) ≈ D_mac.
    // The periodic-compounding divisor (1 + y/freq) would mix conventions and
    // introduce a systematic error proportional to y/freq.
    return weighted / pv; // modified duration = macaulay duration (cc)
}

double Bond::convexity(const termstructure::YieldCurve& curve) const
{
    auto cf = cashflows();
    auto t  = maturities();
    double pv = price(curve);
    double conv = 0.0;
    for (int i = 0; i < periods_; ++i)
        conv += t[i] * t[i] * cf[i] * curve.discountFactor(t[i]);
    return conv / pv;
}

} // namespace qf::instruments
