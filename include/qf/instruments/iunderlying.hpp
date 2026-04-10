#pragma once
#include <string>

namespace qf::instruments {

/// @brief Abstract base for any underlying asset or rate reference.
///
/// Provides the string key used to look up market data (spot, vol, or curve)
/// in a MarketEnvironment. Instrument constructors accept an IUnderlying so
/// that the same Option class can represent equity or rate-linked payoffs.
class IUnderlying {
public:
    virtual ~IUnderlying() = default;

    /// @brief Return the unique identifier used as a MarketEnvironment key.
    /// @return  String key, e.g. a ticker symbol or curve name.
    virtual std::string id() const = 0;
};

/// @brief IUnderlying implementation for a single equity or ETF.
///
/// The id() method returns the ticker symbol, which must match the key
/// used in MarketEnvironment::setSpot() and MarketEnvironment::setVolatility().
class EquityUnderlying : public IUnderlying {
public:
    /// @brief Construct an equity underlying.
    /// @param ticker  Exchange ticker symbol (e.g. @c "AAPL").
    explicit EquityUnderlying(std::string ticker);

    /// @brief Return the ticker symbol.
    /// @return  Ticker string passed at construction.
    std::string id() const override;

private:
    std::string ticker_;
};

/// @brief IUnderlying implementation for an interest-rate curve reference.
///
/// The id() method returns the curve name, which must match the key used in
/// MarketEnvironment::addCurve() and MarketEnvironment::curve().
class RateUnderlying : public IUnderlying {
public:
    /// @brief Construct a rate underlying.
    /// @param curveName  Named yield curve identifier (e.g. @c "USD.OIS").
    explicit RateUnderlying(std::string curveName);

    /// @brief Return the curve name.
    /// @return  Curve name string passed at construction.
    std::string id() const override;

private:
    std::string curveName_;
};

} // namespace qf::instruments
