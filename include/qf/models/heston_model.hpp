#pragma once
#include <vector>
#include <qf/models/iequity_model.hpp>

namespace qf::models {

struct HestonParams {
    double v0;      ///< Initial variance
    double kappa;   ///< Mean reversion speed
    double theta;   ///< Long-run variance
    double sigma;   ///< Vol of vol
    double rho;     ///< Spot-variance correlation
};

/// Heston (1993) stochastic volatility model.
class HestonModel : public IEquityModel {
public:
    explicit HestonModel(const HestonParams& params);

    std::vector<double> simulate(double S0, double T,
                                  int steps,
                                  unsigned seed = 42) const override;

    const HestonParams& params() const { return params_; }

private:
    HestonParams params_;
};

} // namespace qf::models
