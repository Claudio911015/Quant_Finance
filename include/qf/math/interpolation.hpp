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
    InterpolationMethod method_;
};

} // namespace qf::math
