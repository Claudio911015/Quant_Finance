#pragma once
#include <string>
#include <qf/instruments/option.hpp>
#include <qf/pricingengines/ipricing_engine.hpp>

namespace qf::pricingengines {

enum class FDMethod { Explicit, Implicit, CrankNicolson };

/// Free function (preserved for backward-compat)
double finiteDifferenceBSPrice(const instruments::OptionParams& params,
                               int nS = 200, int nT = 200,
                               FDMethod method = FDMethod::CrankNicolson);

class FDMEngine : public IPricingEngine {
public:
    FDMEngine(instruments::OptionParams params,
              int nS = 200, int nT = 200,
              FDMethod method = FDMethod::CrankNicolson);
    double price(const core::MarketEnvironment& env) const override;
    std::string name() const override { return "FiniteDifference"; }
private:
    instruments::OptionParams params_;
    int nS_, nT_;
    FDMethod method_;
};

} // namespace qf::pricingengines
