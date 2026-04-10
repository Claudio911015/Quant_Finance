#pragma once
#include <string>
#include <unordered_map>
#include <qf/termstructure/yieldcurve.hpp>

namespace qf::core {

/// @brief Container for live market data consumed by pricing engines.
///
/// Stores named yield curves, per-ticker spot prices, and per-ticker
/// implied volatilities. Pricing engines query this object at runtime so
/// that a single environment update reprices all attached instruments.
///
/// @note Not thread-safe. External synchronization is required for
///       concurrent reads and writes.
class MarketEnvironment {
public:
    /// @brief Construct an empty environment with no curves or market data.
    MarketEnvironment() noexcept = default;

    /// @brief Construct an environment pre-populated with a default yield curve.
    /// @param defaultCurve  Curve registered under the key @c "default".
    explicit MarketEnvironment(termstructure::YieldCurve defaultCurve);

    /// @brief Register or replace a named yield curve.
    /// @param name   Lookup key (e.g. @c "USD.OIS", @c "default").
    /// @param curve  YieldCurve to store (copied into the environment).
    void addCurve(const std::string& name, termstructure::YieldCurve curve);

    /// @brief Retrieve a yield curve by name.
    /// @param name  Lookup key; defaults to @c "default".
    /// @return      Const reference to the stored YieldCurve.
    /// @throws      std::out_of_range if @p name is not found.
    const termstructure::YieldCurve& curve(const std::string& name = "default") const;

    /// @brief Set or update the spot price for a ticker.
    /// @param ticker  Asset identifier matching IUnderlying::id().
    /// @param spot    Current spot price (same currency as the instrument).
    void setSpot(const std::string& ticker, double spot);

    /// @brief Set or update the implied volatility for a ticker.
    /// @param ticker  Asset identifier matching IUnderlying::id().
    /// @param vol     Implied volatility as a decimal (e.g. 0.20 for 20 %).
    void setVolatility(const std::string& ticker, double vol);

    /// @brief Retrieve the spot price for a ticker.
    /// @param ticker  Asset identifier.
    /// @return        Spot price previously stored via setSpot().
    /// @throws        std::out_of_range if @p ticker is not found.
    double spot(const std::string& ticker) const;

    /// @brief Retrieve the implied volatility for a ticker.
    /// @param ticker  Asset identifier.
    /// @return        Volatility previously stored via setVolatility().
    /// @throws        std::out_of_range if @p ticker is not found.
    double volatility(const std::string& ticker) const;

private:
    std::unordered_map<std::string, termstructure::YieldCurve> curves_;
    std::unordered_map<std::string, double> spots_;
    std::unordered_map<std::string, double> vols_;
};

} // namespace qf::core
