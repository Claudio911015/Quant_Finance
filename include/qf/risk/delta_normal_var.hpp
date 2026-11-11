#pragma once
#include <vector>

namespace qf::risk {

/// @brief Delta-normal (parametric) VaR over signed factor exposures.
///
/// Unlike portfolioVaR, exposures may be negative or zero (derivatives), since
/// they are P&L sensitivities per unit move of each risk factor rather than
/// position values. Computes
///   VaR = Phi^-1(confidence) * sqrt(horizonDays) * sqrt(sum_ij e_i e_j s_i s_j rho_ij)
///
/// @param exposures    P&L per unit move of each factor (may be negative).
/// @param dailyVols    Daily volatility of each factor, in the factor's own unit.
/// @param correlations NxN correlation matrix (N = exposures.size()).
/// @param confidence   Confidence level in (0, 1), e.g. 0.99.
/// @param horizonDays  Horizon in days (> 0); volatility scales with its square root.
/// @return             VaR as a non-negative loss amount.
/// @throws std::invalid_argument if sizes do not match, confidence is outside (0, 1),
///         horizonDays <= 0, or any volatility is negative.
double deltaNormalVaR(const std::vector<double>& exposures,
                      const std::vector<double>& dailyVols,
                      const std::vector<std::vector<double>>& correlations,
                      double confidence,
                      double horizonDays);

} // namespace qf::risk
