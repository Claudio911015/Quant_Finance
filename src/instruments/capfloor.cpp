#include <qf/instruments/capfloor.hpp>
#include <qf/math/statistics.hpp>
#include <qf/math/daycount.hpp>
#include <cmath>
#include <stdexcept>

namespace qf::instruments {

using qf::math::normCDF;

/// Hull-White zero-coupon bond option.
///
/// Prices a European option on a ZCB P(T_start, T_end) with:
///   option_type == Cap   → put on ZCB  (caplet)
///   option_type == Floor → call on ZCB (floorlet)
///
/// @param type       Cap ⇒ ZCB put; Floor ⇒ ZCB call.
/// @param P_start    Market discount factor P(0, T_start).
/// @param P_end      Market discount factor P(0, T_end).
/// @param X          Bond strike  = 1 / (1 + K·τ).
/// @param T_start     Option expiry (years).
/// @param periodLen   Calendar length of the accrual period: T_end − T_start (years).
///                    This is always 1/frequency (the schedule step), NOT the DCC
///                    accrual fraction tau. The HW σ_p formula depends on the
///                    time-calendar interval between the two bond cash-flow dates.
/// @param hw_a        Hull-White mean reversion speed.
/// @param hw_sigma    Hull-White volatility.
/// @return            Option value (unnormalised — caller multiplies by N·(1+K·τ_accrual)).
static double hwBondOption(CapFloorType type,
                           double P_start, double P_end,
                           double X, double T_start, double periodLen,
                           double hw_a, double hw_sigma)
{
    // When T_start = 0 the option is purely intrinsic (σ_p → 0).
    if (T_start < 1e-10) {
        double intrinsic = (type == CapFloorType::Cap)
                         ? std::max(X * P_start - P_end, 0.0)  // put intrinsic
                         : std::max(P_end - X * P_start, 0.0); // call intrinsic
        return intrinsic;
    }

    // σ_p: standard deviation of ln P(T_start, T_end) under the T_start-forward measure.
    // B(periodLen) = (1 - exp(-a * periodLen)) / a  — uses calendar length, not accrual tau.
    double B_len   = (1.0 - std::exp(-hw_a * periodLen)) / hw_a;
    double sigma_p = hw_sigma * B_len
                   * std::sqrt((1.0 - std::exp(-2.0 * hw_a * T_start)) / (2.0 * hw_a));

    if (sigma_p < 1e-12) {
        // Effectively zero vol — return intrinsic
        double intrinsic = (type == CapFloorType::Cap)
                         ? std::max(X * P_start - P_end, 0.0)
                         : std::max(P_end - X * P_start, 0.0);
        return intrinsic;
    }

    double h = std::log(P_end / (X * P_start)) / sigma_p + sigma_p / 2.0;

    if (type == CapFloorType::Cap) {
        // ZCB put:  X·P_start·N(σ_p−h) − P_end·N(−h)
        return X * P_start * normCDF(sigma_p - h) - P_end * normCDF(-h);
    } else {
        // ZCB call: P_end·N(h) − X·P_start·N(h−σ_p)
        return P_end * normCDF(h) - X * P_start * normCDF(h - sigma_p);
    }
}

// ─── CapFloor ────────────────────────────────────────────────────────────────

CapFloor::CapFloor(CapFloorType type, double notional, double strike,
                   double maturity, double frequency,
                   double hw_a, double hw_sigma,
                   math::DayCountConvention dcc)
    : Instrument(maturity),
      type_(type), notional_(notional), strike_(strike),
      frequency_(frequency), hw_a_(hw_a), hw_sigma_(hw_sigma), dcc_(dcc)
{
    if (notional <= 0.0)
        throw std::invalid_argument("CapFloor: notional must be positive");
    if (strike <= 0.0)
        throw std::invalid_argument("CapFloor: strike must be positive");
    if (maturity <= 0.0)
        throw std::invalid_argument("CapFloor: maturity must be positive");
    if (frequency <= 0.0)
        throw std::invalid_argument("CapFloor: frequency must be positive");
    if (hw_a <= 0.0)
        throw std::invalid_argument("CapFloor: Hull-White parameter a must be positive");
    if (hw_sigma <= 0.0)
        throw std::invalid_argument("CapFloor: Hull-White parameter sigma must be positive");
}

double CapFloor::price(const termstructure::YieldCurve& curve) const
{
    int n = static_cast<int>(std::round(maturity() * frequency_));

    // dt:  uniform time step between payment dates (calendar schedule, not affected by DCC).
    // tau: accrual fraction for interest calculation (affected by DCC).
    double dt  = 1.0 / frequency_;
    double tau = math::periodFraction(frequency_, dcc_);

    // Strike price of the embedded ZCB option: X = 1/(1+K*tau).
    // The caplet/floorlet payout is N*(1+K*tau) * hwBondOption(X, ...).
    double X     = 1.0 / (1.0 + strike_ * tau);
    double scale = notional_ * (1.0 + strike_ * tau);

    double total = 0.0;
    for (int i = 1; i <= n; ++i) {
        double T_start = (i - 1) * dt;  // option expiry: start of accrual period
        double T_end   = i * dt;        // bond maturity: end of accrual period

        double P_start = (i == 1) ? 1.0 : curve.discountFactor(T_start);
        double P_end   = curve.discountFactor(T_end);

        // Pass dt (the time interval T_end - T_start) as the bond tenor parameter,
        // since the HW σ_p formula depends on the length of the period in years,
        // not on the accrual fraction.
        total += hwBondOption(type_, P_start, P_end, X, T_start, dt,
                              hw_a_, hw_sigma_);
    }
    return scale * total;
}

double CapFloor::calculatePV(const core::MarketEnvironment& env) const
{
    return price(env.curve());
}

} // namespace qf::instruments
