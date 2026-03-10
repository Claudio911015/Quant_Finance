#pragma once
#include <functional>

namespace qf::math {

// Simpson's 1/3 rule on [a, b] with n subintervals (n must be even)
double simpson(std::function<double(double)> f, double a, double b, int n = 1000);

// Gauss-Legendre quadrature on [a, b] with n points
double gaussLegendre(std::function<double(double)> f, double a, double b, int n = 32);

} // namespace qf::math
