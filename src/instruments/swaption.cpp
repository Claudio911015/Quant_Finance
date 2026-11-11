#include <qf/instruments/swaption.hpp>
#include <qf/math/statistics.hpp>
#include <qf/math/daycount.hpp>
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <vector>
#include <functional>

namespace qf::instruments {

using qf::math::normCDF;

/// Hull-White zero-coupon bond price at the option expiry.
/// For the Jamshidian decomposition we need P_HW(T_exp, T_i | r), the model bond
/// price at expiry T_exp given the short rate r = r(T_exp):
///
///   P_HW(T_exp, T_i | r) = A(T_exp, T_i) · exp(-B(T_i - T_exp) · r)
///
/// where, with the model fitted to the market curve:
///   B(τ)       = (1 - exp(-a·τ)) / a
///   A(T_exp,Ti)= P(0,Ti) / P(0,T_exp) · exp(B(Ti-T_exp)·f(0,T_exp)
///                - σ²/(4a) · B(Ti-T_exp)² · (1-exp(-2a·T_exp)))
///
/// Writing r = f(0,T_exp) + x (x is the deviation of the short rate from the forward
/// rate, which is the mean of r(T_exp) under the T_exp-forward measure) the f(0,T_exp)
/// terms cancel and the bond price is
///
///   P_HW(T_exp, T_i | x) = F_i · exp(-B_i·x - ½·V·B_i²),
///   F_i = P(0,T_i)/P(0,T_exp),   V = σ²/(2a)·(1 - exp(-2a·T_exp)) = Var[r(T_exp)].
///
/// Dropping the ½·V·B_i² term (as the code did until the QuantLib validation) mis-states
/// every strike X_i; it is small for short swaps but grows with σ² and the swap's tenor.

static double hwB(double tau, double a)
{
    return (1.0 - std::exp(-a * tau)) / a;
}

/// Variance of r(T_exp): Var[r(T_exp)] = σ²/(2a) * (1 - exp(-2a*T_exp))
static double hwVariance(double T_exp, double hw_a, double hw_sigma)
{
    return (hw_sigma * hw_sigma / (2.0 * hw_a))
           * (1.0 - std::exp(-2.0 * hw_a * T_exp));
}

/// σ_p for a ZCB option on P(T_exp, T_i):
///   σ_p = σ/a * (1 - exp(-a*(T_i - T_exp))) * sqrt((1-exp(-2a*T_exp))/(2a))
static double hwSigmaP(double T_exp, double tau_i,
                       double hw_a, double hw_sigma)
{
    return (hw_sigma / hw_a)
           * (1.0 - std::exp(-hw_a * tau_i))
           * std::sqrt((1.0 - std::exp(-2.0 * hw_a * T_exp)) / (2.0 * hw_a));
}

/// Hull-White European ZCB put or call.
///   type == Payer   → ZCB put  (right to sell at X)
///   type == Receiver→ ZCB call (right to buy  at X)
static double hwZCBOption(SwaptionType stype,
                           double P0T_exp, double P0Ti,
                           double X_i, double T_exp, double tau_i,
                           double hw_a, double hw_sigma)
{
    double sigma_p = hwSigmaP(T_exp, tau_i, hw_a, hw_sigma);

    if (sigma_p < 1e-12) {
        // Intrinsic only
        return (stype == SwaptionType::Payer)
             ? std::max(X_i * P0T_exp - P0Ti, 0.0)
             : std::max(P0Ti - X_i * P0T_exp, 0.0);
    }

    double h = std::log(P0Ti / (X_i * P0T_exp)) / sigma_p + sigma_p / 2.0;

    if (stype == SwaptionType::Payer) {
        // ZCB put
        return X_i * P0T_exp * normCDF(sigma_p - h) - P0Ti * normCDF(-h);
    } else {
        // ZCB call
        return P0Ti * normCDF(h) - X_i * P0T_exp * normCDF(h - sigma_p);
    }
}

// ─── Swaption ────────────────────────────────────────────────────────────────

Swaption::Swaption(SwaptionType type, double notional, double strike,
                   double expiry, double swapTenor, double frequency,
                   double hw_a, double hw_sigma,
                   math::DayCountConvention dcc)
    : Instrument(expiry + swapTenor),
      type_(type), notional_(notional), strike_(strike),
      expiry_(expiry), swapTenor_(swapTenor), frequency_(frequency),
      hw_a_(hw_a), hw_sigma_(hw_sigma), dcc_(dcc)
{
    if (notional <= 0.0)
        throw std::invalid_argument("Swaption: notional must be positive");
    if (strike <= 0.0)
        throw std::invalid_argument("Swaption: strike must be positive");
    if (expiry <= 0.0)
        throw std::invalid_argument("Swaption: expiry must be positive");
    if (swapTenor <= 0.0)
        throw std::invalid_argument("Swaption: swapTenor must be positive");
    if (frequency <= 0.0)
        throw std::invalid_argument("Swaption: frequency must be positive");
    if (hw_a <= 0.0)
        throw std::invalid_argument("Swaption: Hull-White parameter a must be positive");
    if (hw_sigma <= 0.0)
        throw std::invalid_argument("Swaption: Hull-White parameter sigma must be positive");
}

double Swaption::price(const termstructure::YieldCurve& curve) const
{
    int n = static_cast<int>(std::round(swapTenor_ * frequency_));
    if (n < 1)
        throw std::invalid_argument(
            "Swaption: swapTenor must cover at least half a payment period "
            "(swapTenor * frequency rounds to zero payments)");

    // dt:  time step between payment dates in calendar years (drives the schedule).
    // tau: accrual fraction per period for interest calculation (driven by DCC).
    double dt  = 1.0 / frequency_;
    double tau = math::periodFraction(frequency_, dcc_);

    // Payment dates of the underlying swap: T_exp + i*dt for i=1..n
    std::vector<double> T(n);
    std::vector<double> P0T(n);   // P(0, expiry + i*dt)
    std::vector<double> c(n);     // coupon weights (use accrual tau for interest)

    double P0exp = curve.discountFactor(expiry_);

    for (int i = 0; i < n; ++i) {
        T[i]   = expiry_ + (i + 1) * dt;
        P0T[i] = curve.discountFactor(T[i]);
        c[i]   = notional_ * strike_ * tau;
    }
    // Last cash flow includes notional repayment
    c[n - 1] += notional_;

    // ── Jamshidian step 1: find x* such that swap NPV = 0 at T_exp ─────────
    // x is the deviation of r(T_exp) from f(0,T_exp) (see the header comment), and
    //   X_i(x) = P_HW(T_exp, T_i | x) = F_i · exp(-B_i·x - ½·V·B_i²).
    // The swap NPV at T_exp, Σ_i c_i · X_i(x) - N, is strictly decreasing in x, tends to
    // +inf as x → -inf and to -N as x → +inf: a root always exists and is unique.
    const double variance = hwVariance(expiry_, hw_a_, hw_sigma_);
    const double rStd     = std::sqrt(variance);

    auto swapNPV = [&](double x) -> double {
        double npv = 0.0;
        for (int i = 0; i < n; ++i) {
            double tau_i = (i + 1) * dt;  // T[i] - T_exp (time interval, not accrual tau)
            double B_i   = hwB(tau_i, hw_a_);
            double F_i   = P0T[i] / P0exp;
            npv += c[i] * F_i * std::exp(-B_i * x - 0.5 * variance * B_i * B_i);
        }
        return npv - notional_;
    };

    // Start from ±10 standard deviations of r(T_exp) and widen until the root is bracketed:
    // how far x* sits from 0 depends on the strike (and the curve's slope), not on σ, so a
    // short expiry (small σ_r) with a strike away from the forward swap rate leaves the root
    // outside any fixed multiple of σ_r.
    double halfWidth = std::max(10.0 * rStd, 1e-2);
    double lo = -halfWidth;
    double hi =  halfWidth;
    for (int widen = 0; swapNPV(lo) < 0.0; ++widen) {
        if (widen >= 60)
            throw std::runtime_error("Swaption: could not bracket the Jamshidian critical rate");
        lo *= 2.0;
    }
    for (int widen = 0; swapNPV(hi) > 0.0; ++widen) {
        if (widen >= 60)
            throw std::runtime_error("Swaption: could not bracket the Jamshidian critical rate");
        hi *= 2.0;
    }

    for (int iter = 0; iter < 200; ++iter) {
        double mid = 0.5 * (lo + hi);
        if (swapNPV(mid) > 0.0)
            lo = mid;
        else
            hi = mid;
        if (hi - lo < 1e-14) break;
    }
    const double x_star = 0.5 * (lo + hi);

    // ── Jamshidian step 2: price as portfolio of ZCB options ──────────────
    // X_i = P_HW(T_exp, T_i | x*) — the bond strike for caplet i
    double total = 0.0;
    for (int i = 0; i < n; ++i) {
        double tau_i = (i + 1) * dt;  // time interval from expiry to Ti (for HW formulas)
        double B_i   = hwB(tau_i, hw_a_);
        double F_i   = P0T[i] / P0exp;
        double X_i   = F_i * std::exp(-B_i * x_star - 0.5 * variance * B_i * B_i);

        total += c[i] * hwZCBOption(type_, P0exp, P0T[i],
                                    X_i, expiry_, tau_i,
                                    hw_a_, hw_sigma_);
    }
    return total;
}

double Swaption::priceDualCurve(const termstructure::YieldCurve& projection,
                                const termstructure::YieldCurve& discount) const
{
    // price() validates the tenor (n >= 1) and throws before the annuities are needed.
    double basePrice = price(projection);

    int n = static_cast<int>(std::round(swapTenor_ * frequency_));
    double dt  = 1.0 / frequency_;
    double tau = math::periodFraction(frequency_, dcc_);

    // Annuity of the underlying swap: Σ τ · DF(expiry + k·dt).
    double annProj = 0.0, annDisc = 0.0;
    for (int k = 1; k <= n; ++k) {
        double T = expiry_ + k * dt;
        annProj += tau * projection.discountFactor(T);
        annDisc += tau * discount.discountFactor(T);
    }
    return basePrice * annDisc / annProj;
}

double Swaption::calculatePV(const core::MarketEnvironment& env) const
{
    return price(env.curve());
}

} // namespace qf::instruments
