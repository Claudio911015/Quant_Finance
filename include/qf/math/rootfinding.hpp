#pragma once
#include <functional>

namespace qf::math {

// Newton-Raphson: finds x such that f(x) = 0
double newtonRaphson(std::function<double(double)> f,
                     std::function<double(double)> df,
                     double x0,
                     double tol   = 1e-8,
                     int    maxIt = 100);

// Brent's method: bracket [a, b] required
double brent(std::function<double(double)> f,
             double a, double b,
             double tol   = 1e-8,
             int    maxIt = 100);

} // namespace qf::math
