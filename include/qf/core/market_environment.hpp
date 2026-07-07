#pragma once
#include <memory>
#include <string>
#include <unordered_map>
#include <vector>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/termstructure/volsurface.hpp>
#include <qf/core/imarket_observer.hpp>

namespace qf::core {

/// @brief Container for live market data consumed by pricing engines.
///
/// Stores named yield curves, per-ticker spot prices, and per-ticker
/// implied volatilities. Pricing engines query this object at runtime so
/// that a single environment update reprices all attached instruments.
///
/// Observers can subscribe via subscribe() to receive notifications
/// whenever market data is mutated (Observer pattern). Observers are held
/// as weak_ptr so that they can be destroyed independently; expired entries
/// are cleaned up automatically on each notification cycle.
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

    // -------------------------------------------------------------------------
    // Observer interface
    // -------------------------------------------------------------------------

    /// @brief Subscribe an observer to market-data change notifications.
    ///
    /// The environment holds a weak_ptr, so the observer's lifetime is
    /// managed entirely by the caller. Expired observers are silently
    /// removed on the next notification cycle.
    ///
    /// @param observer  Shared pointer to an IMarketObserver implementation.
    void subscribe(std::weak_ptr<IMarketObserver> observer);

    /// @brief Unsubscribe a specific observer.
    ///
    /// No-op if the observer is not currently subscribed or has expired.
    /// @param observer  The observer to remove.
    void unsubscribe(const std::shared_ptr<IMarketObserver>& observer);

    /// @brief Remove all current subscribers.
    void unsubscribeAll();

    // -------------------------------------------------------------------------
    // Mutating accessors (each triggers a notification)
    // -------------------------------------------------------------------------

    /// @brief Register or replace a named yield curve.
    /// @param name   Lookup key (e.g. @c "USD.OIS", @c "default").
    /// @param curve  YieldCurve to store (copied into the environment).
    void addCurve(const std::string& name, termstructure::YieldCurve curve);

    /// @brief Set or update the spot price for a ticker.
    /// @param ticker  Asset identifier matching IUnderlying::id().
    /// @param spot    Current spot price (same currency as the instrument).
    void setSpot(const std::string& ticker, double spot);

    /// @brief Set or update the implied volatility for a ticker.
    /// @param ticker  Asset identifier matching IUnderlying::id().
    /// @param vol     Implied volatility as a decimal (e.g. 0.20 for 20 %).
    void setVolatility(const std::string& ticker, double vol);

    /// @brief Set or update the implied-vol surface for a ticker (P4).
    ///
    /// Once a surface is registered, the strike/maturity-aware volatility() overload
    /// prefers it over any flat scalar vol. Fires a VolatilityChanged notification, so
    /// Observer-subscribed instruments reprice on a surface update exactly as they do on
    /// a flat-vol update. The scalar setVolatility/volatility API is left untouched.
    ///
    /// @param ticker   Asset identifier matching IUnderlying::id().
    /// @param surface  VolSurface to store (copied into the environment).
    void setVolSurface(const std::string& ticker, termstructure::VolSurface surface);

    // -------------------------------------------------------------------------
    // Read-only accessors
    // -------------------------------------------------------------------------

    /// @brief Retrieve a yield curve by name.
    /// @param name  Lookup key; defaults to @c "default".
    /// @return      Const reference to the stored YieldCurve.
    /// @throws      std::out_of_range if @p name is not found.
    const termstructure::YieldCurve& curve(const std::string& name = "default") const;

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

    /// @brief Strike/maturity-aware implied volatility for a ticker (P4).
    ///
    /// Prefers a VolSurface registered via setVolSurface(); when none is set, falls back
    /// to the flat scalar returned by volatility(ticker) — so the flat-vol workflow is
    /// bit-for-bit unchanged when no surface exists.
    ///
    /// @param ticker    Asset identifier.
    /// @param strike    Option strike to mark.
    /// @param maturity  Option maturity in years.
    /// @return          Surface vol if a surface is set, else the flat scalar vol.
    /// @throws          std::out_of_range if neither a surface nor a flat vol is set.
    double volatility(const std::string& ticker, double strike, double maturity) const;

    /// @brief True if a VolSurface has been registered for @p ticker.
    bool hasVolSurface(const std::string& ticker) const;

private:
    /// @brief Notify all live subscribers of a market-data change.
    ///
    /// Expired weak_ptrs are removed before iterating so that the
    /// observer list stays clean over time.
    ///
    /// @param type  Category of change.
    /// @param key   Ticker or curve name that was modified.
    void notify(ChangeType type, const std::string& key);

    std::unordered_map<std::string, termstructure::YieldCurve> curves_;
    std::unordered_map<std::string, double> spots_;
    std::unordered_map<std::string, double> vols_;
    std::unordered_map<std::string, termstructure::VolSurface> volSurfaces_;
    std::vector<std::weak_ptr<IMarketObserver>> observers_;
};

} // namespace qf::core
