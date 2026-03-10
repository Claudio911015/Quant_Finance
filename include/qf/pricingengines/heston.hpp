#pragma once
#include <qf/instruments/option.hpp>

namespace qf::pricingengines {

struct HestonParams {
    double v0;      // initial variance
    double kappa;   // mean reversion speed
    double theta;   // long-run variance
    double sigma;   // vol of vol
    double rho;     // correlation between spot and variance Brownian motions
};

// Semi-analytical pricing via characteristic function (Heston 1993, corrected formulation)
double hestonPrice(const instruments::OptionParams& opt, const HestonParams& heston);

// Monte Carlo pricing under Heston dynamics (Euler-Maruyama)
double hestonMonteCarlo(const instruments::OptionParams& opt,
                        const HestonParams& heston,
                        int nPaths = 100000,
                        int nSteps = 252,
                        unsigned seed = 42);

} // namespace qf::pricingengines
