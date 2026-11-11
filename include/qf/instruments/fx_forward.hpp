#pragma once
#include <string>
#include <qf/instruments/instrument.hpp>
#include <qf/core/market_environment.hpp>

namespace qf::instruments {

/// @brief Direction of an FX trade, seen from the holder: buy or sell the foreign currency.
enum class FxSide { Buy, Sell };

/// @brief FX forward priced by covered interest parity, reading market data by name.
///
/// The pair (e.g. "USDMXN") is quoted as units of domestic currency per unit of foreign
/// currency. Spot is read from the MarketEnvironment under the pair name, and the two
/// discount curves under their own keys, so any spot or curve shock applied to the
/// environment (for instance by risk::ScenarioEngine) flows through the price. With
/// T = maturityDays / 365:
///
///   npv     = s * N * (S * DF_f(T) - K * DF_d(T))     in domestic currency, s = +1 Buy / -1 Sell
///   forward = S * DF_f(T) / DF_d(T)
///   delta   = s * N * DF_f(T)                         = d npv / d S
class FxForward : public Instrument {
public:
    /// @param notionalForeign  Notional in foreign currency (> 0).
    /// @param strike           Agreed rate K, domestic per foreign (> 0).
    /// @param maturityDays     Days from today to delivery (> 0); T = days / 365.
    /// @param side             Buy (long foreign currency) or Sell.
    /// @param pair             Spot key in the environment (default "USDMXN").
    /// @param domesticCurve    Curve key of the domestic currency (default "TIIE-F").
    /// @param foreignCurve     Curve key of the foreign currency (default "SOFR").
    /// @throws std::invalid_argument if notionalForeign, strike or maturityDays is not positive.
    FxForward(double notionalForeign, double strike, int maturityDays, FxSide side,
              std::string pair = "USDMXN", std::string domesticCurve = "TIIE-F",
              std::string foreignCurve = "SOFR");

    /// @brief Present value in domestic currency, from the holder's side.
    /// @param env  Environment holding the spot, the domestic curve and the foreign curve.
    /// @return     s * N * (S * DF_f - K * DF_d).
    double npv(const core::MarketEnvironment& env) const;

    /// @brief Routes Instrument::pv() to npv() so the forward flows through ScenarioEngine.
    double calculatePV(const core::MarketEnvironment& env) const override { return npv(env); }

    /// @brief Fair forward rate S * DF_f / DF_d (independent of side, notional and strike).
    /// @param env  Environment holding the spot and both curves.
    /// @return     Forward rate, domestic per foreign.
    double forwardRate(const core::MarketEnvironment& env) const;

    /// @brief Sensitivity of npv() to the spot: s * N * DF_f.
    /// @param env  Environment holding both curves.
    /// @return     d npv / d S, in domestic currency per unit of spot.
    double delta(const core::MarketEnvironment& env) const;

    double notionalForeign() const { return notionalForeign_; }
    double strike() const { return strike_; }
    int maturityDays() const { return maturityDays_; }
    FxSide side() const { return side_; }
    const std::string& pair() const { return pair_; }
    const std::string& domesticCurve() const { return domesticCurve_; }
    const std::string& foreignCurve() const { return foreignCurve_; }

private:
    double notionalForeign_;
    double strike_;
    int maturityDays_;
    FxSide side_;
    std::string pair_;
    std::string domesticCurve_;
    std::string foreignCurve_;
};

} // namespace qf::instruments
