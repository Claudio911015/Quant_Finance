#include <qf/instruments/capfloor.hpp>
#include <cmath>
#include <stdexcept>

namespace qf::instruments {

// ─── helpers ─────────────────────────────────────────────────────────────────

static double normCDF(double x)
{
    return 0.5 * std::erfc(-x / std::sqrt(2.0));
}

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
/// @param T_start    Option expiry (years).
/// @param tau        Accrual period length T_end − T_start.
/// @param hw_a       Hull-White mean reversion speed.
/// @param hw_sigma   Hull-White volatility.
/// @return           Option value (unnormalised — caller multiplies by N·(1+K·τ)).
static double hwBondOption(CapFloorType type,
                           double P_start, double P_end,
                           double X, double T_start, double tau,
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
    double B_tau   = (1.0 - std::exp(-hw_a * tau)) / hw_a;
    double sigma_p = hw_sigma * B_tau
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
                   double hw_a, double hw_sigma)
    : Instrument(maturity),
      type_(type), notional_(notional), strike_(strike),
      frequency_(frequency), hw_a_(hw_a), hw_sigma_(hw_sigma)
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
    int    n   = static_cast<int>(std::round(maturity() * frequency_));
    double tau = 1.0 / frequency_;
    double X   = 1.0 / (1.0 + strike_ * tau);
    double scale = notional_ * (1.0 + strike_ * tau);

    double total = 0.0;
    for (int i = 1; i <= n; ++i) {
        double T_start = (i - 1) * tau;
        double T_end   = i * tau;

        double P_start = (i == 1) ? 1.0 : curve.discountFactor(T_start);
        double P_end   = curve.discountFactor(T_end);

        total += hwBondOption(type_, P_start, P_end, X, T_start, tau,
                              hw_a_, hw_sigma_);
    }
    return scale * total;
}

double CapFloor::calculatePV(const core::MarketEnvironment& env) const
{
    return price(env.curve());
}

} // namespace qf::instruments
