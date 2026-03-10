#pragma once

#include <qf/instruments/option.hpp>

namespace qf::pricingengines {

// Monte Carlo pricer for European options under Black-Scholes dynamics.
// - N is the number of Monte Carlo paths (default 100000)
// - seed gives deterministic reproducible runs
// - throws std::invalid_argument for invalid parameters

double monteCarloBSPrice(const instruments::OptionParams& params,
                         int N = 100000,
                         unsigned seed = 42);

} // namespace qf::pricingengines
