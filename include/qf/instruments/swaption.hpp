#pragma once
#include <qf/instruments/instrument.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/math/daycount.hpp>

namespace qf::instruments {

enum class SwaptionType { Payer, Receiver };

/// @brief European swaption priced analytically under Hull-White (Jamshidian decomposition).
///
/// A payer swaption gives the right to enter a payer IRS (pay fixed K, receive floating)
/// at expiry T_exp. A receiver swaption gives the right to receive fixed K.
///
/// Jamshidian (1989) decomposes the swaption into a portfolio of ZCB options:
///
///   Swaption_payer = Σ_i  c_i · ZCBPut(expiry=T_exp, maturity=T_i, strike=X_i)
///   Swaption_recv  = Σ_i  c_i · ZCBCall(expiry=T_exp, maturity=T_i, strike=X_i)
///
/// The strikes X_i satisfy: Σ_i c_i · P(r*, T_i) = 0, where r* is the critical
/// short rate at T_exp that makes the underlying swap NPV equal to zero.
///
/// Coupon weights:
///   c_i = N · K · τ        for i < N   (fixed coupon payments)
///   c_N = N · (1 + K·τ)               (final coupon + notional)
///
/// where τ = periodFraction(frequency, dcc) is the DCC-dependent accrual fraction,
/// and dt = 1/frequency is the calendar step between payment dates (used in HW formulas).
class Swaption : public Instrument {
public:
    /// @brief Construct a European swaption.
    /// @param type        Payer or Receiver.
    /// @param notional    Notional of the underlying swap (must be > 0).
    /// @param strike      Fixed rate K on the underlying IRS (must be > 0).
    /// @param expiry      Option expiry in years (must be > 0).
    /// @param swapTenor   Tenor of the underlying swap in years (must be > 0).
    /// @param frequency   Payment periods per year for the swap, e.g. 2 = semi-annual.
    /// @param hw_a        Hull-White mean-reversion speed a (must be > 0).
    /// @param hw_sigma    Hull-White volatility σ (must be > 0).
    /// @param dcc         Day-count convention for accrual fractions (default ACT/365).
    Swaption(SwaptionType type, double notional, double strike,
             double expiry, double swapTenor, double frequency,
             double hw_a, double hw_sigma,
             math::DayCountConvention dcc = math::DayCountConvention::ACT_365);

    /// @brief Analytical price via Jamshidian decomposition.
    /// @param curve  Market yield curve used for discounting.
    /// @return       Present value of the swaption.
    double price(const termstructure::YieldCurve& curve) const;

    /// @brief Implement Instrument interface — delegates to price(env.curve()).
    double calculatePV(const core::MarketEnvironment& env) const override;

    // Accessors
    SwaptionType             type()      const { return type_; }
    double                   notional()  const { return notional_; }
    double                   strike()    const { return strike_; }
    double                   expiry()    const { return expiry_; }
    double                   swapTenor() const { return swapTenor_; }
    double                   frequency() const { return frequency_; }
    double                   hwA()       const { return hw_a_; }
    double                   hwSigma()   const { return hw_sigma_; }
    math::DayCountConvention dayCount()  const { return dcc_; }

private:
    SwaptionType             type_;
    double notional_;
    double strike_;
    double expiry_;
    double swapTenor_;
    double frequency_;
    double hw_a_;
    double hw_sigma_;
    math::DayCountConvention dcc_;
};

} // namespace qf::instruments
