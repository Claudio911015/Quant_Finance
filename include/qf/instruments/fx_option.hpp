#pragma once
#include <string>
#include <qf/instruments/instrument.hpp>
#include <qf/instruments/fx_forward.hpp>
#include <qf/instruments/option.hpp>
#include <qf/core/market_environment.hpp>

namespace qf::instruments {

/// @brief Price and Greeks of an FX option position, in domestic currency, already scaled by s * N.
struct FxOptionGreeks {
    double price;     ///< Position value.
    double delta;     ///< d price / d spot.
    double gamma;     ///< d2 price / d spot2.
    double vega;      ///< Change in price for a 1 volatility point (sigma + 0.01).
    double forward;   ///< Forward rate S * DF_f / DF_d at the option's expiry.
    double vol;       ///< Implied volatility used, read from the environment at (K, T).
};

/// @brief European FX option priced with Garman-Kohlhagen, reading market data by name.
///
/// Garman-Kohlhagen is Black-Scholes with the foreign rate as dividend yield, so the price
/// is delegated to pricingengines::blackScholes with riskFreeRate = r_d and dividendYield =
/// r_f. With T = maturityDays / 365:
///
///   r_d = -ln DF_d(T) / T,   r_f = -ln DF_f(T) / T,   sigma = env.volatility(pair, K, T)
///
/// Spot, both curves and the volatility (surface if registered, else the flat scalar) come
/// from the MarketEnvironment, so spot and curve shocks applied to it reprice the option.
/// The calls are options on the foreign currency: a Call gives the right to buy it at K.
class FxOption : public Instrument {
public:
    /// @param notionalForeign  Notional in foreign currency (> 0).
    /// @param strike           Strike K, domestic per foreign (> 0).
    /// @param maturityDays     Days from today to expiry (> 0); T = days / 365.
    /// @param type             Call or Put on the foreign currency.
    /// @param side             Buy (long the option) or Sell (short it).
    /// @param pair             Spot and volatility key in the environment (default "USDMXN").
    /// @param domesticCurve    Curve key of the domestic currency (default "TIIE-F").
    /// @param foreignCurve     Curve key of the foreign currency (default "SOFR").
    /// @throws std::invalid_argument if notionalForeign, strike or maturityDays is not positive.
    FxOption(double notionalForeign, double strike, int maturityDays, OptionType type, FxSide side,
             std::string pair = "USDMXN", std::string domesticCurve = "TIIE-F",
             std::string foreignCurve = "SOFR");

    /// @brief Position value in domestic currency: s * N * Garman-Kohlhagen price.
    /// @param env  Environment holding the spot, both curves and the volatility.
    /// @return     Same value as greeks(env).price.
    double npv(const core::MarketEnvironment& env) const;

    /// @brief Routes Instrument::pv() to npv() so the option flows through ScenarioEngine.
    double calculatePV(const core::MarketEnvironment& env) const override { return npv(env); }

    /// @brief Price, delta, gamma, vega, forward and volatility of the position.
    /// @param env  Environment holding the spot, both curves and the volatility.
    /// @return     Price and Greeks multiplied by s * N (forward and vol are not scaled);
    ///             vega is per 1 volatility point (sigma + 0.01).
    FxOptionGreeks greeks(const core::MarketEnvironment& env) const;

    double notionalForeign() const { return notionalForeign_; }
    double strike() const { return strike_; }
    int maturityDays() const { return maturityDays_; }
    OptionType optionType() const { return type_; }
    FxSide side() const { return side_; }
    const std::string& pair() const { return pair_; }
    const std::string& domesticCurve() const { return domesticCurve_; }
    const std::string& foreignCurve() const { return foreignCurve_; }

private:
    double notionalForeign_;
    double strike_;
    int maturityDays_;
    OptionType type_;
    FxSide side_;
    std::string pair_;
    std::string domesticCurve_;
    std::string foreignCurve_;
};

} // namespace qf::instruments
