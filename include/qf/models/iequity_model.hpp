#pragma once
#include <vector>

namespace qf::models {

/// @brief Strategy interface for equity and asset-price models.
///
/// Concrete models (Black-Scholes GBM, Heston, …) implement this interface
/// so that Monte Carlo engines and other path-dependent pricers can be
/// parameterised by model without knowing the specific dynamics.
class IEquityModel {
public:
    virtual ~IEquityModel() = default;

    /// @brief Simulate a single risk-neutral price path S(0) … S(T).
    /// @param S0    Initial spot price.
    /// @param T     Horizon in years.
    /// @param steps Number of discrete time steps.
    /// @param seed  RNG seed for reproducibility.
    /// @return      Vector of size (@p steps + 1): path[0] = @p S0.
    virtual std::vector<double> simulate(double S0, double T,
                                          int steps,
                                          unsigned seed = 42) const = 0;

    /// @brief Evaluate the risk-neutral transition density p(S, T).
    ///
    /// Optional analytical density. The default implementation returns 0,
    /// indicating that the model does not provide a closed-form density.
    /// @param S  Asset price at maturity @p T.
    /// @param T  Horizon in years.
    /// @return   Probability density value, or 0.0 if not implemented.
    virtual double riskNeutralDensity(double /*S*/, double /*T*/) const { return 0.0; }
};

} // namespace qf::models
