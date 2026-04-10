#pragma once
#include <vector>

namespace qf::models {

/// @brief Strategy interface for short-rate and term-structure models.
///
/// Concrete implementations (Vasicek, Hull-White, …) derive from this
/// interface so that pricing engines and risk analytics are decoupled from
/// any specific interest-rate model.
class IRateModel {
public:
    virtual ~IRateModel() = default;

    /// @brief Compute the zero-coupon bond price P(0, T).
    /// @param T  Maturity in years.
    /// @return   Risk-neutral discount factor for maturity @p T.
    virtual double bondPrice(double T) const = 0;

    /// @brief Compute the continuously-compounded zero rate r(T).
    /// @param T  Maturity in years.
    /// @return   Zero rate such that P(0,T) = exp(-r(T) * T).
    virtual double zeroRate(double T) const = 0;

    /// @brief Simulate a single short-rate path over [0, T].
    /// @param T     Horizon in years.
    /// @param steps Number of discrete time steps.
    /// @param seed  RNG seed for reproducibility.
    /// @return      Vector of size (@p steps + 1): path[0] = r(0).
    virtual std::vector<double> simulate(double T, int steps, unsigned seed = 42) const = 0;
};

} // namespace qf::models
