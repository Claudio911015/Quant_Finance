#pragma once

#include <qf/instruments/option.hpp>

namespace qf::pricingengines {

// Cox-Ross-Rubinstein binomial tree pricer for European/American options.
// - nSteps is the number of time steps in the tree (default 1000).
// - American exercise uses early exercise in backward induction.

double binomialTreeBSPrice(const instruments::OptionParams& params,
                           int nSteps = 1000);

} // namespace qf::pricingengines
