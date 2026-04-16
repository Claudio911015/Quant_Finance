#include <qf/termstructure/yieldcurve.hpp>
#include <cmath>
#include <stdexcept>

namespace qf::termstructure {

YieldCurve::YieldCurve(std::vector<double> maturities,
                       std::vector<double> rates,
                       math::InterpolationMethod method)
    : interp_(std::move(maturities), std::move(rates), method)
{}

double YieldCurve::zeroRate(double T) const
{
    if (T <= 0.0)
        throw std::invalid_argument("YieldCurve: maturity must be positive");
    return interp_(T);
}

double YieldCurve::discountFactor(double T) const
{
    return std::exp(-zeroRate(T) * T);
}

double YieldCurve::forwardRate(double T1, double T2) const
{
    if (T1 < 0.0)
        throw std::invalid_argument("YieldCurve: T1 must be non-negative");
    if (T1 >= T2)
        throw std::invalid_argument("YieldCurve: T1 must be less than T2");
    // f(T1, T2) = (r2*T2 - r1*T1) / (T2 - T1)
    // When T1 = 0: P(0,0) = 1 and r1*T1 = 0, so f(0,T2) = r2 = zeroRate(T2).
    double r1T1 = (T1 > 0.0) ? zeroRate(T1) * T1 : 0.0;
    double r2   = zeroRate(T2);
    return (r2 * T2 - r1T1) / (T2 - T1);
}

} // namespace qf::termstructure
