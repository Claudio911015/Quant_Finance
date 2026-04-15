#pragma once
#include <string>

namespace qf::core {

class MarketEnvironment;

/// @brief Type of market data change that triggered a notification.
enum class ChangeType {
    SpotChanged,        ///< A spot price was added or updated.
    VolatilityChanged,  ///< An implied volatility was added or updated.
    CurveChanged        ///< A yield curve was added or replaced.
};

/// @brief Pure interface for objects that observe MarketEnvironment changes.
///
/// Implementors are notified via onMarketUpdate() whenever spot prices,
/// volatilities, or yield curves are mutated in a MarketEnvironment to
/// which they have subscribed.
class IMarketObserver {
public:
    virtual ~IMarketObserver() = default;

    /// @brief Called by MarketEnvironment after any data mutation.
    /// @param env   The environment that changed (post-mutation snapshot).
    /// @param type  Indicates which category of data was modified.
    /// @param key   The ticker or curve name that was changed.
    virtual void onMarketUpdate(const MarketEnvironment& env,
                                ChangeType type,
                                const std::string& key) = 0;
};

} // namespace qf::core
