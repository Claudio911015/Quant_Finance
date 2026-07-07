#include <qf/termstructure/yieldcurve.hpp>
#include <cmath>
#include <stdexcept>

namespace qf::termstructure {

YieldCurve::YieldCurve(std::vector<double> maturities,
                       std::vector<double> rates,
                       math::InterpolationMethod method)
    : maturities_(std::move(maturities)),
      rates_(std::move(rates)),
      method_(method),
      // interp_ is built from copies so the pillar vectors remain readable.
      interp_(maturities_, rates_, method)
{}

// Basis-point → decimal-rate conversion for the bump helpers.
static constexpr double kBpToRate = 1e-4;

YieldCurve YieldCurve::parallelBump(double bpShift) const
{
    std::vector<double> shifted = rates_;
    const double dr = bpShift * kBpToRate;
    for (double& r : shifted)
        r += dr;
    return YieldCurve(maturities_, std::move(shifted), method_);
}

YieldCurve YieldCurve::bumped(std::size_t pillarIndex, double bpShift) const
{
    if (pillarIndex >= rates_.size())
        throw std::out_of_range("YieldCurve::bumped: pillarIndex out of range");
    std::vector<double> shifted = rates_;
    shifted[pillarIndex] += bpShift * kBpToRate;
    return YieldCurve(maturities_, std::move(shifted), method_);
}

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
