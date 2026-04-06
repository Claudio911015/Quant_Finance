#pragma once
#include <memory>
#include <string>
#include <qf/pricingengines/ipricing_engine.hpp>
#include <qf/instruments/option.hpp>

namespace qf::pricingengines {

class EngineFactory {
public:
    /// @brief Create an equity pricing engine by method name.
    /// @param method "BS" | "MC" | "BT" | "FDM" | "Heston"
    /// @param params OptionParams used by all equity engines.
    /// @param simPaths Number of simulation paths (MC/Heston only).
    /// @param seed RNG seed (MC/Heston only).
    /// @throws std::invalid_argument for unknown method.
    static std::shared_ptr<IPricingEngine>
    makeEquityEngine(const std::string& method,
                     const instruments::OptionParams& params,
                     int simPaths = 100000,
                     unsigned seed = 42);
};

} // namespace qf::pricingengines
