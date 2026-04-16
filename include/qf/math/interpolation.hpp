#pragma once
#include <vector>

namespace qf::math {

enum class InterpolationMethod { Linear, CubicSpline, LogLinear };

class Interpolator {
public:
    Interpolator(std::vector<double> x, std::vector<double> y,
                 InterpolationMethod method = InterpolationMethod::Linear);

    /// @brief Evaluate the interpolant at @p x.
    ///
    /// @note **Flat extrapolation**: if @p x is outside the grid range, the
    ///       value at the nearest endpoint is returned (clamped). No exception
    ///       is thrown. This matches the behaviour expected by YieldCurve for
    ///       short maturities just below the first knot.
    double operator()(double x) const;

private:
    std::vector<double> x_, y_;
    std::vector<double> spline_M_; // second derivatives for cubic spline
    InterpolationMethod method_;
};

} // namespace qf::math
