#pragma once
#include <vector>
#include <qf/math/interpolation.hpp>

namespace qf::termstructure {

class YieldCurve {
public:
    YieldCurve(std::vector<double> maturities,
               std::vector<double> rates,
               math::InterpolationMethod method = math::InterpolationMethod::CubicSpline);

    // Zero rate for maturity T
    double zeroRate(double T) const;

    // Discount factor: P(0, T) = exp(-r(T) * T)
    double discountFactor(double T) const;

    // Forward rate between T1 and T2
    double forwardRate(double T1, double T2) const;

private:
    math::Interpolator interp_;
};

} // namespace qf::termstructure
