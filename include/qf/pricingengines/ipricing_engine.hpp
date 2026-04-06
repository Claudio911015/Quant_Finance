#pragma once
#include <string>
#include <qf/core/market_environment.hpp>

namespace qf::pricingengines {

/// Strategy interface for pricing engines.
class IPricingEngine {
public:
    virtual ~IPricingEngine() = default;

    /// @brief Compute price given the market environment.
    virtual double price(const core::MarketEnvironment& env) const = 0;

    /// @brief Human-readable engine identifier (for logging/debugging).
    virtual std::string name() const = 0;
};

} // namespace qf::pricingengines
