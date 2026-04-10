#pragma once
#include <string>
#include <qf/core/market_environment.hpp>

namespace qf::pricingengines {

/// @brief Strategy interface for all pricing engines.
///
/// Every concrete engine (Black-Scholes, Monte Carlo, Binomial Tree, FDM,
/// Heston, …) implements this interface so that calling code can price any
/// instrument through a uniform API regardless of the underlying method.
class IPricingEngine {
public:
    virtual ~IPricingEngine() = default;

    /// @brief Compute the fair value of the instrument.
    /// @param env  Live market data container (spots, vols, yield curves).
    /// @return     Present value in the currency of the instrument.
    virtual double price(const core::MarketEnvironment& env) const = 0;

    /// @brief Human-readable engine identifier used for logging and debugging.
    /// @return Short string label, e.g. @c "BlackScholes" or @c "MonteCarlo".
    virtual std::string name() const = 0;
};

} // namespace qf::pricingengines
