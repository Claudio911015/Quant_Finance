#pragma once
#include <string>
#include <qf/instruments/option.hpp>
#include <qf/pricingengines/ipricing_engine.hpp>

namespace qf::pricingengines {

/// Free function (preserved for backward-compat)
double binomialTreeBSPrice(const instruments::OptionParams& params, int nSteps = 1000);

class BinomialTreeEngine : public IPricingEngine {
public:
    /// Legacy: all market data in params; env is ignored.
    explicit BinomialTreeEngine(instruments::OptionParams params, int nSteps = 1000);

    /// Env-aware: spot, vol, and riskFreeRate read from env using ticker.
    BinomialTreeEngine(instruments::OptionParams params, std::string ticker,
                       int nSteps = 1000);

    double price(const core::MarketEnvironment& env) const override;
    std::string name() const override { return "BinomialTree"; }

private:
    instruments::OptionParams params_;
    std::string ticker_;
    int nSteps_;
};

} // namespace qf::pricingengines
