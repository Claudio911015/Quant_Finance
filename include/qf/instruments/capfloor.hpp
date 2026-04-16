#pragma once
#include <qf/instruments/instrument.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/math/daycount.hpp>

namespace qf::instruments {

enum class CapFloorType { Cap, Floor };

/// @brief Interest-rate cap or floor priced analytically under the Hull-White model.
///
/// A cap (floor) is a portfolio of caplets (floorlets). Each caplet/floorlet is
/// an option on the simply-compounded LIBOR rate for one accrual period.
/// Under Hull-White, every caplet/floorlet reduces to a put (call) on a
/// zero-coupon bond, which has a closed-form solution.
///
/// Pricing formula (per caplet, period [T_{i-1}, T_i]):
///
///   dt     = 1/frequency           — calendar length of each period (years)
///   τ      = periodFraction(f,dcc) — accrual fraction per period (DCC-dependent)
///   σ_p    = (σ/a) · (1 − e^{−a·dt}) · √((1 − e^{−2a·T_{i-1}}) / (2a))
///   h      = ln(P(0,T_i) / (X · P(0,T_{i-1}))) / σ_p + σ_p/2
///   X      = 1 / (1 + K·τ)        — strike uses accrual τ (not dt)
///
///   Caplet  = N·(1+K·τ)·[X·P(0,T_{i-1})·N(σ_p−h) − P(0,T_i)·N(−h)]
///   Floorlet= N·(1+K·τ)·[P(0,T_i)·N(h)            − X·P(0,T_{i-1})·N(h−σ_p)]
///
/// Note: σ_p uses dt (calendar time between bond dates), not the accrual τ.
/// For ACT/365, dt = τ. For ACT/360, dt < τ.
///
/// Cap/floor parity: Cap(K) − Floor(K) = NPV of payer IRS at rate K.
class CapFloor : public Instrument {
public:
    /// @brief Construct a cap or floor.
    /// @param type       Cap or Floor.
    /// @param notional   Notional principal (must be > 0).
    /// @param strike     Fixed rate K (must be > 0).
    /// @param maturity   Total tenor in years (must be > 0).
    /// @param frequency  Payment periods per year, e.g. 4 = quarterly (must be > 0).
    /// @param hw_a       Hull-White mean-reversion speed a (must be > 0).
    /// @param hw_sigma   Hull-White volatility σ (must be > 0).
    /// @param dcc        Day-count convention for accrual fractions (default ACT/365).
    CapFloor(CapFloorType type, double notional, double strike,
             double maturity, double frequency,
             double hw_a, double hw_sigma,
             math::DayCountConvention dcc = math::DayCountConvention::ACT_365);

    /// @brief Analytical price using the stored Hull-White parameters.
    /// @param curve  Market yield curve P(0,T) used for discounting.
    /// @return       Present value of all caplets (or floorlets).
    double price(const termstructure::YieldCurve& curve) const;

    /// @brief Implement Instrument interface — delegates to price(env.curve()).
    double calculatePV(const core::MarketEnvironment& env) const override;

    // Accessors
    CapFloorType             type()      const { return type_; }
    double                   notional()  const { return notional_; }
    double                   strike()    const { return strike_; }
    double                   frequency() const { return frequency_; }
    double                   hwA()       const { return hw_a_; }
    double                   hwSigma()   const { return hw_sigma_; }
    math::DayCountConvention dayCount()  const { return dcc_; }

private:
    CapFloorType             type_;
    double notional_;
    double strike_;
    double frequency_;
    double hw_a_;
    double hw_sigma_;
    math::DayCountConvention dcc_;
};

} // namespace qf::instruments
