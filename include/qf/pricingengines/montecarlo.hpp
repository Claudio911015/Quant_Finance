#pragma once
#include <string>
#include <qf/instruments/option.hpp>
#include <qf/pricingengines/ipricing_engine.hpp>

namespace qf::pricingengines {

/// Free function (preserved for backward-compat)
double monteCarloBSPrice(const instruments::OptionParams& params,
                         int N = 100000, unsigned seed = 42);

class MonteCarloEngine : public IPricingEngine {
public:
    MonteCarloEngine(instruments::OptionParams params, int N = 100000, unsigned seed = 42);
    double price(const core::MarketEnvironment& env) const override;
    std::string name() const override { return "MonteCarlo"; }
private:
    instruments::OptionParams params_;
    int N_;
    unsigned seed_;
};

} // namespace qf::pricingengines
