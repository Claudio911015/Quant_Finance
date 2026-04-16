#pragma once
#include <vector>

namespace qf::risk {

struct VaRResult {
    double var;    // Value at Risk (positive number = loss)
    double cvar;   // Conditional VaR / Expected Shortfall
};

// Parametric VaR assuming normal distribution of returns
VaRResult parametricVaR(double portfolioValue,
                        double meanReturn,
                        double stddevReturn,
                        double confidence = 0.99);

// Historical VaR from a vector of historical returns (e.g. daily log-returns)
VaRResult historicalVaR(const std::vector<double>& returns,
                        double portfolioValue,
                        double confidence = 0.99);

// Monte Carlo VaR from a vector of simulated P&L scenarios
VaRResult monteCarloVaR(const std::vector<double>& simulatedPnL,
                        double confidence = 0.99);

/// @brief Input descriptor for a single position in a portfolio.
struct PortfolioPosition {
    double value;       ///< Current market value of the position (same currency).
    double meanReturn;  ///< Expected daily return (e.g. 0.0005 for 0.05%).
    double stddev;      ///< Daily return standard deviation.
};

/// @brief Parametric portfolio VaR using a full correlation matrix.
///
/// Computes the portfolio-level parametric VaR and CVaR under the assumption
/// of multivariate normality, using the standard formula:
///   sigma_p = sqrt(w^T * Sigma * w)
/// where w is the vector of position values and Sigma is the covariance matrix
/// built from the per-asset stddevs and the correlation matrix.
///
/// @param positions      Vector of portfolio positions.
/// @param correlations   NxN correlation matrix (row-major, N = positions.size()).
///                       Must be square with 1.0 on the diagonal.
/// @param confidence     Confidence level in (0, 1), e.g. 0.99.
/// @return               VaRResult with portfolio-level var and cvar.
/// @throws std::invalid_argument if inputs are inconsistent or invalid.
VaRResult portfolioVaR(const std::vector<PortfolioPosition>& positions,
                       const std::vector<std::vector<double>>& correlations,
                       double confidence = 0.99);

} // namespace qf::risk
