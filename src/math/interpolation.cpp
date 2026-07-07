#include <qf/math/interpolation.hpp>
#include <cmath>
#include <stdexcept>
#include <algorithm>

namespace qf::math {

Interpolator::Interpolator(std::vector<double> x, std::vector<double> y,
                           InterpolationMethod method)
    : x_(std::move(x)), y_(std::move(y)), method_(method)
{
    if (x_.size() != y_.size() || x_.size() < 2)
        throw std::invalid_argument("Interpolator: need at least 2 matching points");

    for (std::size_t i = 1; i < x_.size(); ++i)
        if (x_[i] <= x_[i-1])
            throw std::invalid_argument("Interpolator: x must be strictly increasing");

    // Log-linear: store log(y) internally, exponentiate on output
    if (method_ == InterpolationMethod::LogLinear)
        for (auto& v : y_)
            v = std::log(v);

    // Cubic spline: compute second derivatives via Thomas algorithm (natural BC)
    if (method_ == InterpolationMethod::CubicSpline) {
        std::size_t n = x_.size();
        // Natural boundary conditions pin the endpoint second derivatives to zero.
        // With exactly 2 points there are no interior nodes (m = n-2 = 0), the tridiagonal
        // system is empty, and the "spline" degenerates to the straight line between the two
        // points — so leaving spline_M_ all-zero is correct. Guarding on n >= 3 also avoids a
        // size_t underflow in `upper(m-1)` / `lower(m-1)` when m == 0 (was requesting SIZE_MAX
        // elements and throwing a spurious length_error), which VolSurface reaches whenever a
        // CubicSpline smile is built from the documented minimum of 2 strike pillars.
        spline_M_.resize(n, 0.0); // natural BC: M[0] = M[n-1] = 0
        if (n >= 3) {
            std::vector<double> h(n - 1);
            for (std::size_t i = 0; i < n - 1; ++i)
                h[i] = x_[i+1] - x_[i];

            std::size_t m = n - 2; // interior nodes
            std::vector<double> diag(m), upper(m-1), lower(m-1), rhs(m);

            for (std::size_t i = 0; i < m; ++i) {
                diag[i] = 2.0 * (h[i] + h[i+1]);
                rhs[i]  = 6.0 * ((y_[i+2] - y_[i+1]) / h[i+1]
                                - (y_[i+1] - y_[i])   / h[i]);
            }
            for (std::size_t i = 0; i < m - 1; ++i)
                upper[i] = lower[i] = h[i+1];

            // Forward sweep
            for (std::size_t i = 1; i < m; ++i) {
                double w = lower[i-1] / diag[i-1];
                diag[i] -= w * upper[i-1];
                rhs[i]  -= w * rhs[i-1];
            }

            // Back substitution
            spline_M_[m] = rhs[m-1] / diag[m-1];
            for (int i = (int)m - 2; i >= 0; --i)
                spline_M_[i+1] = (rhs[i] - upper[i] * spline_M_[i+2]) / diag[i];
        }
    }
}

double Interpolator::operator()(double x) const
{
    if (x <= x_.front()) return (method_ == InterpolationMethod::LogLinear) ? std::exp(y_.front()) : y_.front();
    if (x >= x_.back())  return (method_ == InterpolationMethod::LogLinear) ? std::exp(y_.back())  : y_.back();

    auto it = std::lower_bound(x_.begin(), x_.end(), x);
    std::size_t i = std::distance(x_.begin(), it) - 1;

    double h = x_[i+1] - x_[i];
    double t = (x - x_[i]) / h;
    double result = 0.0;

    switch (method_) {
        case InterpolationMethod::Linear:
        case InterpolationMethod::LogLinear:
            result = y_[i] * (1.0 - t) + y_[i+1] * t;
            break;

        case InterpolationMethod::CubicSpline: {
            double a = x_[i+1] - x;
            double b = x - x_[i];
            result = (spline_M_[i]   * a*a*a) / (6.0 * h)
                   + (spline_M_[i+1] * b*b*b) / (6.0 * h)
                   + (y_[i]   / h - spline_M_[i]   * h / 6.0) * a
                   + (y_[i+1] / h - spline_M_[i+1] * h / 6.0) * b;
            break;
        }
    }

    return (method_ == InterpolationMethod::LogLinear) ? std::exp(result) : result;
}

} // namespace qf::math
