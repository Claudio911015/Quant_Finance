#pragma once
#include <string>
#include <qf/instruments/option.hpp>
#include <qf/pricingengines/ipricing_engine.hpp>

namespace qf::pricingengines {

struct HestonParams {
    double v0;      // initial variance
    double kappa;   // mean reversion speed
    double theta;   // long-run variance
    double sigma;   // vol of vol
    double rho;     // correlation between spot and variance Brownian motions
};

/// Free functions (preserved for backward-compat and qfpy)
double hestonPrice(const instruments::OptionParams& opt, const HestonParams& heston);
double hestonMonteCarlo(const instruments::OptionParams& opt,
                        const HestonParams& heston,
                        int nPaths = 100000, int nSteps = 252, unsigned seed = 42);

class HestonEngine : public IPricingEngine {
public:
    /// Legacy: all market data in params; env is ignored.
    HestonEngine(instruments::OptionParams opt, HestonParams heston);

    /// Env-aware: spot and riskFreeRate read from env using ticker.
    /// HestonParams are model calibration data — not read from env.
    HestonEngine(instruments::OptionParams opt, HestonParams heston,
                 std::string ticker);

    double price(const core::MarketEnvironment& env) const override;
    std::string name() const override { return "Heston"; }

private:
    instruments::OptionParams opt_;
    HestonParams heston_;
    std::string ticker_;
};

} // namespace qf::pricingengines
