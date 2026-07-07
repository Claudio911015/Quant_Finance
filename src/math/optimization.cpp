#include <qf/math/optimization.hpp>
#include <algorithm>
#include <cmath>
#include <numeric>
#include <stdexcept>

namespace qf::math {

namespace {

// Centroid of all vertices except the worst (index n, the last after sorting).
std::vector<double> centroid(const std::vector<std::vector<double>>& simplex,
                             std::size_t n)
{
    std::vector<double> c(n, 0.0);
    for (std::size_t i = 0; i < n; ++i) {           // all but the worst vertex
        for (std::size_t k = 0; k < n; ++k)
            c[k] += simplex[i][k];
    }
    for (std::size_t k = 0; k < n; ++k)
        c[k] /= static_cast<double>(n);
    return c;
}

// c + coeff * (c - worst)
std::vector<double> extrapolate(const std::vector<double>& c,
                                const std::vector<double>& worst,
                                double coeff)
{
    std::vector<double> out(c.size());
    for (std::size_t k = 0; k < c.size(); ++k)
        out[k] = c[k] + coeff * (c[k] - worst[k]);
    return out;
}

} // namespace

OptimResult nelderMead(std::function<double(const std::vector<double>&)> f,
                       const std::vector<double>& x0,
                       double tol, int maxIt, double initialStep)
{
    const std::size_t n = x0.size();
    if (n == 0)
        throw std::invalid_argument("nelderMead: empty starting point");

    // Nelder-Mead coefficients.
    constexpr double kReflect  = 1.0;
    constexpr double kExpand   = 2.0;
    constexpr double kContract = 0.5;
    constexpr double kShrink   = 0.5;

    // ── Build the initial simplex: n+1 vertices ──────────────────────────────
    std::vector<std::vector<double>> simplex(n + 1, x0);
    for (std::size_t i = 0; i < n; ++i) {
        double step = (std::abs(x0[i]) > 1e-12) ? initialStep * x0[i]
                                                : initialStep;
        if (step == 0.0) step = initialStep;   // guard x0[i] == 0 and step==0
        simplex[i + 1][i] += step;
    }

    std::vector<double> fval(n + 1);
    for (std::size_t i = 0; i <= n; ++i)
        fval[i] = f(simplex[i]);

    // Index vector sorted so simplex[order[0]] is best, order[n] is worst.
    std::vector<std::size_t> order(n + 1);

    OptimResult result;
    int it = 0;
    for (; it < maxIt; ++it) {
        // Sort vertices ascending by objective.
        std::iota(order.begin(), order.end(), 0);
        std::sort(order.begin(), order.end(),
                  [&](std::size_t a, std::size_t b) { return fval[a] < fval[b]; });

        // Reorder simplex/fval physically so best..worst is contiguous.
        {
            std::vector<std::vector<double>> s2(n + 1);
            std::vector<double> f2(n + 1);
            for (std::size_t i = 0; i <= n; ++i) {
                s2[i] = simplex[order[i]];
                f2[i] = fval[order[i]];
            }
            simplex.swap(s2);
            fval.swap(f2);
        }

        const double fBest  = fval[0];
        const double fWorst = fval[n];

        // Convergence: relative spread of objective across the simplex. The
        // TINY floor in the denominator turns the test absolute near a zero
        // minimum (where |f_hi|+|f_lo| → 0), avoiding a divide-by-noise blow-up.
        constexpr double kTiny = 1e-12;
        double spread = 2.0 * std::abs(fWorst - fBest) /
                        (std::abs(fWorst) + std::abs(fBest) + kTiny);
        if (spread < tol) {
            result.converged = true;
            break;
        }

        std::vector<double> cen = centroid(simplex, n);

        // ── Reflection ───────────────────────────────────────────────────────
        std::vector<double> xr = extrapolate(cen, simplex[n], kReflect);
        double fr = f(xr);

        if (fr < fBest) {
            // ── Expansion ────────────────────────────────────────────────────
            std::vector<double> xe = extrapolate(cen, simplex[n], kExpand);
            double fe = f(xe);
            if (fe < fr) { simplex[n] = xe; fval[n] = fe; }
            else         { simplex[n] = xr; fval[n] = fr; }
        }
        else if (fr < fval[n - 1]) {
            // Reflection better than second-worst: accept.
            simplex[n] = xr; fval[n] = fr;
        }
        else {
            // ── Contraction ──────────────────────────────────────────────────
            bool doShrink = false;
            if (fr < fWorst) {
                // Outside contraction.
                std::vector<double> xc = extrapolate(cen, simplex[n], kContract);
                double fc = f(xc);
                if (fc <= fr) { simplex[n] = xc; fval[n] = fc; }
                else          { doShrink = true; }
            } else {
                // Inside contraction.
                std::vector<double> xc = extrapolate(cen, simplex[n], -kContract);
                double fc = f(xc);
                if (fc < fWorst) { simplex[n] = xc; fval[n] = fc; }
                else             { doShrink = true; }
            }

            if (doShrink) {
                // ── Shrink toward the best vertex ────────────────────────────
                for (std::size_t i = 1; i <= n; ++i) {
                    for (std::size_t k = 0; k < n; ++k)
                        simplex[i][k] = simplex[0][k]
                                      + kShrink * (simplex[i][k] - simplex[0][k]);
                    fval[i] = f(simplex[i]);
                }
            }
        }
    }

    // Final sort so the reported best is index 0.
    std::iota(order.begin(), order.end(), 0);
    std::sort(order.begin(), order.end(),
              [&](std::size_t a, std::size_t b) { return fval[a] < fval[b]; });

    result.x          = simplex[order[0]];
    result.fmin       = fval[order[0]];
    result.iterations = it;
    return result;
}

} // namespace qf::math
