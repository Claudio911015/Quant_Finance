#include <qf/risk/delta_normal_var.hpp>
#include <qf/math/statistics.hpp>
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace qf::risk {

double deltaNormalVaR(const std::vector<double>& exposures,
                      const std::vector<double>& dailyVols,
                      const std::vector<std::vector<double>>& correlations,
                      double confidence,
                      double horizonDays)
{
    const std::size_t n = exposures.size();
    if (n == 0)
        throw std::invalid_argument("deltaNormalVaR: exposures must not be empty");
    if (dailyVols.size() != n)
        throw std::invalid_argument("deltaNormalVaR: dailyVols size must match exposures");
    if (correlations.size() != n)
        throw std::invalid_argument("deltaNormalVaR: correlations must be NxN");
    for (const auto& row : correlations)
        if (row.size() != n)
            throw std::invalid_argument("deltaNormalVaR: correlations must be NxN");
    if (!(confidence > 0.0 && confidence < 1.0))
        throw std::invalid_argument("deltaNormalVaR: confidence must be in (0, 1)");
    if (!(horizonDays > 0.0))
        throw std::invalid_argument("deltaNormalVaR: horizonDays must be positive");
    for (double v : dailyVols)
        if (!(v >= 0.0))
            throw std::invalid_argument("deltaNormalVaR: dailyVols must be non-negative");

    double variance = 0.0;
    for (std::size_t i = 0; i < n; ++i)
        for (std::size_t j = 0; j < n; ++j)
            variance += exposures[i] * exposures[j] * dailyVols[i] * dailyVols[j]
                        * correlations[i][j];

    // Rounding can leave a tiny negative value for perfectly offsetting exposures.
    const double sigma = std::sqrt(std::max(variance, 0.0));
    return math::normInvCDF(confidence) * std::sqrt(horizonDays) * sigma;
}

} // namespace qf::risk
