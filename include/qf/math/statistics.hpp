#pragma once
#include <stdexcept>

namespace qf::math {

/// @brief Standard normal CDF: Φ(x) = P(Z ≤ x), Z ~ N(0,1).
double normCDF(double x);

/// @brief Standard normal PDF: φ(x) = exp(-x²/2) / √(2π).
double normPDF(double x);

/// @brief Inverse standard normal CDF (quantile function): Φ⁻¹(p).
/// @param p  Probability in (0, 1).
/// @throws std::invalid_argument if p ≤ 0 or p ≥ 1.
double normInvCDF(double p);

} // namespace qf::math
