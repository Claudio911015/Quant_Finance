#pragma once
#include <memory>
#include <string>
#include <qf/pricingengines/ipricing_engine.hpp>
#include <qf/pricingengines/heston.hpp>
#include <qf/instruments/option.hpp>

namespace qf::pricingengines {

class EngineFactory {
public:
    /// @param method    "BS" | "MC" | "BT" | "FDM"
    /// @param params    OptionParams (contractual + fallback market data)
    /// @param simPaths  Number of MC paths (MC only)
    /// @param seed      RNG seed (MC only)
    /// @param ticker    If non-empty, engine reads market data from MarketEnvironment
    static std::shared_ptr<IPricingEngine>
    makeEquityEngine(const std::string& method,
                     const instruments::OptionParams& params,
                     int simPaths = 100000,
                     unsigned seed = 42,
                     std::string ticker = "");

    /// @param params    OptionParams (contractual data + fallback spot/rate)
    /// @param heston    Calibrated Heston model parameters
    /// @param ticker    If non-empty, engine reads spot/rate from MarketEnvironment
    static std::shared_ptr<IPricingEngine>
    makeHestonEngine(const instruments::OptionParams& params,
                     const HestonParams& heston,
                     std::string ticker = "");
};

} // namespace qf::pricingengines
