#include <qf/instruments/bond.hpp>
#include <qf/math/rootfinding.hpp>
#include <cmath>
#include <stdexcept>
#include <numeric>

namespace qf::instruments {

Bond::Bond(double faceValue, double couponRate, int periods, double frequency)
    : Instrument(static_cast<double>(periods) / frequency),
      faceValue_(faceValue), couponRate_(couponRate),
      periods_(periods), frequency_(frequency)
{
    if (periods <= 0)
        throw std::invalid_argument("Bond: periods must be positive");
    if (frequency <= 0.0)
        throw std::invalid_argument("Bond: frequency must be positive");
}

std::vector<double> Bond::cashflows() const
{
    double coupon = faceValue_ * couponRate_ / frequency_;
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

double Bond::calculatePV(const termstructure::YieldCurve& curve) const
{
    return price(curve);
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

    // Bracket: search for sign change
    double lo = 1e-6, hi = 1.0;
    while (priceFn(hi) > 0.0 && hi < 10.0) hi += 0.1;

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
    double macaulay = weighted / pv;
    double ytm = yield(pv);
    return macaulay / (1.0 + ytm / frequency_); // modified duration
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
