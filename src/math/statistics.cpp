#include <qf/math/statistics.hpp>
#include <cmath>
#include <stdexcept>

namespace qf::math {

double normCDF(double x)
{
    return 0.5 * std::erfc(-x / std::sqrt(2.0));
}

double normPDF(double x)
{
    return std::exp(-0.5 * x * x) / std::sqrt(2.0 * M_PI);
}

double normInvCDF(double p)
{
    if (p <= 0.0 || p >= 1.0)
        throw std::invalid_argument("normInvCDF: p must be in (0, 1)");

    bool negate = (p < 0.5);
    if (negate) p = 1.0 - p;

    double t = std::sqrt(-2.0 * std::log(1.0 - p));

    // Rational approximation (Beasley-Springer-Moro)
    const double c0 = 2.515517, c1 = 0.802853, c2 = 0.010328;
    const double d1 = 1.432788, d2 = 0.189269, d3 = 0.001308;

    double x = t - (c0 + c1 * t + c2 * t * t)
                 / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t);

    return negate ? -x : x;
}

} // namespace qf::math
