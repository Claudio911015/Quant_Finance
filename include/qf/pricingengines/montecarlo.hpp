#pragma once
#include <memory>
#include <string>
#include <qf/instruments/option.hpp>
#include <qf/pricingengines/ipricing_engine.hpp>
#include <qf/models/iequity_model.hpp>

namespace qf::pricingengines {

/// Free function (preserved for backward-compat)
double monteCarloBSPrice(const instruments::OptionParams& params,
                         int N = 100000, unsigned seed = 42);

class MonteCarloEngine : public IPricingEngine {
public:
    /// Legacy: params carry all market data; env is ignored.
    explicit MonteCarloEngine(instruments::OptionParams params,
                              int N = 100000, unsigned seed = 42);

    /// Model-driven: model simulates the price path.
    /// nSteps = number of steps per path (relevant for Heston mean reversion).
    MonteCarloEngine(std::shared_ptr<models::IEquityModel> model,
                     instruments::OptionParams params,
                     int N = 100000, int nSteps = 252, unsigned seed = 42);

    double price(const core::MarketEnvironment& env) const override;
    std::string name() const override { return "MonteCarlo"; }

private:
    instruments::OptionParams params_;
    std::shared_ptr<models::IEquityModel> model_;   // null => legacy path
    int N_;
    int nSteps_ = 1;
    unsigned seed_;
};

} // namespace qf::pricingengines
