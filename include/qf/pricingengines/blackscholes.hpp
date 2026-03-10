#pragma once
#include <qf/instruments/option.hpp>

namespace qf::pricingengines {

struct BSResult {
    double price;
    double delta;
    double gamma;
    double vega;
    double theta;
    double rho;
};

BSResult blackScholes(const instruments::OptionParams& params);

// Implied volatility via Brent
double impliedVolatility(const instruments::OptionParams& params,
                         double marketPrice,
                         double tol   = 1e-6,
                         int    maxIt = 100);

} // namespace qf::pricingengines
