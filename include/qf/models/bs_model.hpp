#pragma once
#include <vector>
#include <qf/models/iequity_model.hpp>

namespace qf::models {

/// Geometric Brownian Motion (Black-Scholes) equity model.
class BlackScholesModel : public IEquityModel {
public:
    /// @param r Risk-free rate, q dividend yield, sigma volatility.
    BlackScholesModel(double r, double q, double sigma);

    std::vector<double> simulate(double S0, double T,
                                  int steps,
                                  unsigned seed = 42) const override;

private:
    double r_, q_, sigma_;
};

} // namespace qf::models
