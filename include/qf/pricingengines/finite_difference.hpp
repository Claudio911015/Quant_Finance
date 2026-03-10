#pragma once

#include <qf/instruments/option.hpp>

namespace qf::pricingengines {

enum class FDMethod {
    Explicit,
    Implicit,
    CrankNicolson
};

// Finite-difference solver for Black-Scholes European (Call/Put) options.
// nS: number of underlying asset steps, nT: number of time steps.
// Smax relative to spot is internally set to 5.0.
// Returns approximate option price at spot.

double finiteDifferenceBSPrice(const instruments::OptionParams& params,
                               int nS = 200,
                               int nT = 200,
                               FDMethod method = FDMethod::CrankNicolson);

} // namespace qf::pricingengines
