#pragma once
#include <memory>
#include <string>
#include <qf/pricingengines/ipricing_engine.hpp>
#include <qf/pricingengines/heston.hpp>
#include <qf/instruments/option.hpp>

namespace qf::pricingengines {

/// @brief Factory that constructs IPricingEngine instances by string key.
///
/// Decouples engine selection from the rest of the pricing pipeline.
/// All returned engines satisfy the IPricingEngine strategy interface and
/// can be used interchangeably by any instrument pricer.
class EngineFactory {
public:
    /// @brief Create a standard equity option engine by method key.
    /// @param method    Pricing method: @c "BS" (Black-Scholes), @c "MC" (Monte Carlo),
    ///                  @c "BT" (Binomial Tree), or @c "FDM" (Finite Difference).
    /// @param params    Contract specification and fallback market data.
    /// @param simPaths  Number of simulation paths (Monte Carlo only).
    /// @param seed      RNG seed for reproducibility (Monte Carlo only).
    /// @param ticker    If non-empty, spot/vol/rate are sourced from the
    ///                  MarketEnvironment at pricing time instead of @p params.
    /// @return          Shared pointer to a newly constructed IPricingEngine.
    static std::shared_ptr<IPricingEngine>
    makeEquityEngine(const std::string& method,
                     const instruments::OptionParams& params,
                     int simPaths = 100000,
                     unsigned seed = 42,
                     std::string ticker = "");

    /// @brief Create a Heston stochastic-volatility pricing engine.
    /// @param params    Contract specification and fallback spot/rate.
    /// @param heston    Calibrated Heston model parameters (kappa, theta, xi, rho, v0).
    /// @param ticker    If non-empty, spot and risk-free rate are sourced from the
    ///                  MarketEnvironment at pricing time instead of @p params.
    /// @return          Shared pointer to a newly constructed IPricingEngine.
    static std::shared_ptr<IPricingEngine>
    makeHestonEngine(const instruments::OptionParams& params,
                     const HestonParams& heston,
                     std::string ticker = "");
};

} // namespace qf::pricingengines
