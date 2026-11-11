#pragma once
#include <qf/instruments/instrument.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/math/daycount.hpp>
#include <vector>

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

    /// @brief Construct a cap or floor over an explicit caplet calendar (aged cap/floor).
    ///
    /// Caplet i covers [t_{i-1}, t_i] with accrual τ_i = periodFraction(1/(t_i − t_{i-1}), dcc),
    /// so a calendar of {0, dt, …, n·dt} reproduces the regular constructor. The first caplet may
    /// start in the future (t_0 > 0): it is then an option with expiry t_0, not an intrinsic value.
    /// @param type           Cap or Floor.
    /// @param notional       Notional principal (must be > 0).
    /// @param strike         Fixed rate K (must be > 0).
    /// @param boundaryTimes  t_0 < t_1 < … < t_n in years from the valuation date; t_0 >= 0, n >= 1,
    ///                       finite.
    /// @param hw_a           Hull-White mean-reversion speed a (must be > 0).
    /// @param hw_sigma       Hull-White volatility σ (must be > 0).
    /// @param dcc            Day-count convention for accrual fractions (default ACT/365).
    /// @throws std::invalid_argument if any argument breaks the conditions above.
    /// @note frequency() is 0 for this constructor: the periods need not be uniform.
    CapFloor(CapFloorType type, double notional, double strike,
             std::vector<double> boundaryTimes,
             double hw_a, double hw_sigma,
             math::DayCountConvention dcc = math::DayCountConvention::ACT_365);

    /// @brief Analytical price using the stored Hull-White parameters.
    /// @param curve  Market yield curve P(0,T) used for discounting.
    /// @return       Present value of all caplets (or floorlets).
    /// @throws std::invalid_argument if maturity * frequency rounds to zero payments.
    double price(const termstructure::YieldCurve& curve) const;

    /// @brief Price with a projection curve (caplet values) apart from the discount curve.
    ///
    /// Deterministic basis, not a two-curve Hull-White model: each caplet is valued on the
    /// projection curve and carried to the discount curve with its discount-factor ratio,
    ///   Σ_i caplet_i(projection) · DF_d(t_i) / DF_p(t_i),
    /// where t_i is the end (payment) of caplet i.
    /// @param projection  Curve the caplets are priced on (the index curve).
    /// @param discount    Curve the payments are discounted with (e.g. the collateral curve).
    /// @return            Present value; equals price(projection) when discount == projection.
    /// @throws std::invalid_argument as price().
    double priceDualCurve(const termstructure::YieldCurve& projection,
                          const termstructure::YieldCurve& discount) const;

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
    std::vector<double> boundaryTimes_;   ///< empty = regular calendar from maturity/frequency

    struct Caplet { double tEnd; double value; };
    /// Value (notional and strike scaling included) and end time of every caplet on `curve`.
    std::vector<Caplet> caplets(const termstructure::YieldCurve& curve) const;
};

} // namespace qf::instruments
