#pragma once
#include <string>
#include <qf/instruments/option.hpp>
#include <qf/pricingengines/ipricing_engine.hpp>

namespace qf::pricingengines {

struct BSResult {
    double price;
    double delta;
    double gamma;
    /// Change in option price per 1 percentage-point move in implied vol
    /// (e.g. if vol goes from 20% to 21%). Equals S·e^{-qT}·N'(d₁)·√T / 100.
    /// @note risk::vega() returns dV/dσ per *unit* vol (100× larger convention).
    double vega;
    /// Change in option price per calendar day (negative for long options).
    double theta;
    /// Change in option price per 1 percentage-point move in risk-free rate.
    double rho;
};

/// Free function (preserved for backward-compat)
BSResult blackScholes(const instruments::OptionParams& params);

/// Implied volatility via Brent (preserved)
double impliedVolatility(const instruments::OptionParams& params,
                         double marketPrice,
                         double tol = 1e-6, int maxIt = 100);

/// Strategy engine wrapping blackScholes()
class BlackScholesEngine : public IPricingEngine {
public:
    /// Legacy: all market data in params; env is ignored.
    explicit BlackScholesEngine(instruments::OptionParams params);

    /// Env-aware: spot, vol, and riskFreeRate are read from env using ticker.
    BlackScholesEngine(instruments::OptionParams params, std::string ticker);

    double price(const core::MarketEnvironment& env) const override;
    std::string name() const override { return "BlackScholes"; }

private:
    instruments::OptionParams params_;
    std::string ticker_;   // empty => legacy (ignore env)
};

} // namespace qf::pricingengines
