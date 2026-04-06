#pragma once
#include <vector>

namespace qf::models {

/// Abstract interface for equity/asset price models.
class IEquityModel {
public:
    virtual ~IEquityModel() = default;

    /// @brief Simulate risk-neutral price path S(0)...S(T).
    /// @return Vector of size (steps+1): path[0] = S0.
    virtual std::vector<double> simulate(double S0, double T,
                                          int steps,
                                          unsigned seed = 42) const = 0;

    /// @brief Risk-neutral density p(S, T) — optional, default 0.
    virtual double riskNeutralDensity(double /*S*/, double /*T*/) const { return 0.0; }
};

} // namespace qf::models
