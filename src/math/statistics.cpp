#include <qf/math/statistics.hpp>
#include <cmath>
#include <stdexcept>

namespace qf::math {

// C++17 doesn't guarantee M_PI — define our own constant.
static constexpr double kPi = 3.14159265358979323846;

double normCDF(double x)
{
    return 0.5 * std::erfc(-x / std::sqrt(2.0));
}

double normPDF(double x)
{
    return std::exp(-0.5 * x * x) / std::sqrt(2.0 * kPi);
}

/// Inverse normal CDF via Acklam's rational approximation (2010).
/// Max absolute error < 1.15e-9 across the full domain (0, 1).
/// Source: Peter J. Acklam, "An algorithm for computing the inverse
/// normal cumulative distribution function", 2010.
double normInvCDF(double p)
{
    if (p <= 0.0 || p >= 1.0)
        throw std::invalid_argument("normInvCDF: p must be in (0, 1)");

    // Rational approximation coefficients
    static constexpr double a[] = {
        -3.969683028665376e+01,  2.209460984245205e+02,
        -2.759285104469687e+02,  1.383577518672690e+02,
        -3.066479806614716e+01,  2.506628277459239e+00
    };
    static constexpr double b[] = {
        -5.447609879822406e+01,  1.615858368580409e+02,
        -1.556989798598866e+02,  6.680131188771972e+01,
        -1.328068155288572e+01
    };
    static constexpr double c[] = {
        -7.784894002430293e-03, -3.223964580411365e-01,
        -2.400758277161838e+00, -2.549732539343734e+00,
         4.374664141464968e+00,  2.938163982698783e+00
    };
    static constexpr double d[] = {
         7.784695709041462e-03,  3.224671290700398e-01,
         2.445134137142996e+00,  3.754408661907416e+00
    };

    static constexpr double p_low  = 0.02425;
    static constexpr double p_high = 1.0 - p_low;

    double x;
    if (p < p_low) {
        // Lower tail region
        double q = std::sqrt(-2.0 * std::log(p));
        x = (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) /
             ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1.0);
    } else if (p <= p_high) {
        // Central region
        double q = p - 0.5;
        double r = q * q;
        x = (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5]) * q /
             (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1.0);
    } else {
        // Upper tail region (symmetry)
        double q = std::sqrt(-2.0 * std::log(1.0 - p));
        x = -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) /
              ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1.0);
    }
    return x;
}

} // namespace qf::math
