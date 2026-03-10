#pragma once
#include <vector>

namespace qf::math {

enum class InterpolationMethod { Linear, CubicSpline, LogLinear };

class Interpolator {
public:
    Interpolator(std::vector<double> x, std::vector<double> y,
                 InterpolationMethod method = InterpolationMethod::Linear);

    double operator()(double x) const;

private:
    std::vector<double> x_, y_;
    std::vector<double> spline_M_; // second derivatives for cubic spline
    InterpolationMethod method_;
};

} // namespace qf::math
