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
    /// Legacy: all market data in params; env is ignored.
    explicit MonteCarloEngine(instruments::OptionParams params,
                              int N = 100000, unsigned seed = 42);

    /// Model-driven: model simulates the price path.
    MonteCarloEngine(std::shared_ptr<models::IEquityModel> model,
                     instruments::OptionParams params,
                     int N = 100000, int nSteps = 252, unsigned seed = 42);

    /// Env-aware: spot, vol, and riskFreeRate read from env using ticker.
    MonteCarloEngine(instruments::OptionParams params, std::string ticker,
                     int N = 100000, unsigned seed = 42);

    double price(const core::MarketEnvironment& env) const override;
    std::string name() const override { return "MonteCarlo"; }

private:
    instruments::OptionParams params_;
    std::string ticker_;
    std::shared_ptr<models::IEquityModel> model_;
    int N_;
    int nSteps_ = 1;
    unsigned seed_;
};

} // namespace qf::pricingengines
