#include <qf/risk/var.hpp>
#include <qf/math/statistics.hpp>
#include <algorithm>
#include <cmath>
#include <numeric>
#include <stdexcept>

namespace qf::risk {

using qf::math::normInvCDF;
using qf::math::normPDF;

VaRResult parametricVaR(double portfolioValue,
                        double meanReturn,
                        double stddevReturn,
                        double confidence)
{
    if (portfolioValue <= 0.0)
        throw std::invalid_argument("parametricVaR: portfolioValue must be positive");
    if (stddevReturn <= 0.0)
        throw std::invalid_argument("parametricVaR: stddevReturn must be positive");
    if (confidence <= 0.0 || confidence >= 1.0)
        throw std::invalid_argument("parametricVaR: confidence must be in (0, 1)");

    double z = normInvCDF(confidence);

    // VaR = portfolio * (z * sigma - mean)
    double var = portfolioValue * (z * stddevReturn - meanReturn);

    // CVaR = portfolio * (sigma * phi(z) / (1 - confidence) - mean)
    double cvar = portfolioValue * (stddevReturn * normPDF(z) / (1.0 - confidence) - meanReturn);

    return {var, cvar};
}

VaRResult historicalVaR(const std::vector<double>& returns,
                        double portfolioValue,
                        double confidence)
{
    if (returns.empty())
        throw std::invalid_argument("historicalVaR: returns vector is empty");
    if (portfolioValue <= 0.0)
        throw std::invalid_argument("historicalVaR: portfolioValue must be positive");
    if (confidence <= 0.0 || confidence >= 1.0)
        throw std::invalid_argument("historicalVaR: confidence must be in (0, 1)");

    // Sort returns ascending (worst to best)
    std::vector<double> sorted = returns;
    std::sort(sorted.begin(), sorted.end());

    int n = static_cast<int>(sorted.size());
    int idx = static_cast<int>((1.0 - confidence) * n + 1e-9);
    if (idx < 0) idx = 0;
    if (idx >= n) idx = n - 1;

    // VaR: loss at the (1-confidence) percentile
    double var = -portfolioValue * sorted[idx];

    // CVaR: average of all losses worse than VaR
    double sumTail = 0.0;
    int count = idx + 1;
    for (int i = 0; i <= idx; ++i)
        sumTail += sorted[i];
    double cvar = -portfolioValue * sumTail / count;

    return {var, cvar};
}

VaRResult monteCarloVaR(const std::vector<double>& simulatedPnL,
                        double confidence)
{
    if (simulatedPnL.empty())
        throw std::invalid_argument("monteCarloVaR: simulatedPnL vector is empty");
    if (confidence <= 0.0 || confidence >= 1.0)
        throw std::invalid_argument("monteCarloVaR: confidence must be in (0, 1)");

    // Sort P&L ascending (worst to best)
    std::vector<double> sorted = simulatedPnL;
    std::sort(sorted.begin(), sorted.end());

    int n = static_cast<int>(sorted.size());
    int idx = static_cast<int>((1.0 - confidence) * n + 1e-9);
    if (idx < 0) idx = 0;
    if (idx >= n) idx = n - 1;

    // VaR: negative of the P&L at the quantile
    double var = -sorted[idx];

    // CVaR: average of losses in the tail
    double sumTail = 0.0;
    int count = idx + 1;
    for (int i = 0; i <= idx; ++i)
        sumTail += sorted[i];
    double cvar = -sumTail / count;

    return {var, cvar};
}

VaRResult portfolioVaR(const std::vector<PortfolioPosition>& positions,
                       const std::vector<std::vector<double>>& correlations,
                       double confidence)
{
    const std::size_t n = positions.size();
    // Validate inputs
    if (n == 0) throw std::invalid_argument("portfolioVaR: positions must be non-empty");
    if (correlations.size() != n)
        throw std::invalid_argument("portfolioVaR: correlation matrix rows != positions.size()");
    for (const auto& row : correlations)
        if (row.size() != n)
            throw std::invalid_argument("portfolioVaR: correlation matrix is not square");
    if (confidence <= 0.0 || confidence >= 1.0)
        throw std::invalid_argument("portfolioVaR: confidence must be in (0, 1)");

    // Portfolio mean return (sum of value-weighted means)
    double portfolioValue = 0.0;
    double portfolioMean  = 0.0;
    for (const auto& p : positions) {
        portfolioValue += p.value;
        portfolioMean  += p.value * p.meanReturn;
    }
    if (portfolioValue <= 0.0)
        throw std::invalid_argument("portfolioVaR: total portfolio value must be positive");

    // Portfolio variance: sigma_p^2 = sum_i sum_j w_i * w_j * corr_ij * sigma_i * sigma_j
    // where w_i = positions[i].value (not normalized — we keep dollar terms)
    double variance = 0.0;
    for (std::size_t i = 0; i < n; ++i)
        for (std::size_t j = 0; j < n; ++j)
            variance += positions[i].value * positions[j].value
                      * correlations[i][j]
                      * positions[i].stddev * positions[j].stddev;

    // Clamp near-zero or negative variance (e.g. perfectly hedged portfolio)
    if (variance < 0.0) variance = 0.0;
    const double sigma = std::sqrt(variance);

    // Edge case: perfectly hedged portfolio — VaR and CVaR are both zero
    // (or driven purely by the mean, which here would be a gain/loss without vol)
    if (sigma == 0.0) {
        double loss = -portfolioMean;  // positive = loss if mean < 0
        return {loss, loss};
    }

    // Reuse parametricVaR with the portfolio-level mean and sigma
    // portfolioValue is already the sum of all positions
    return parametricVaR(portfolioValue, portfolioMean / portfolioValue, sigma / portfolioValue, confidence);
}

} // namespace qf::risk
