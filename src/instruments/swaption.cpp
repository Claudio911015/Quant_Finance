#include <qf/instruments/swaption.hpp>
#include <cmath>
#include <stdexcept>
#include <vector>
#include <functional>

namespace qf::instruments {

// ─── helpers ─────────────────────────────────────────────────────────────────

static double normCDF(double x)
{
    return 0.5 * std::erfc(-x / std::sqrt(2.0));
}

/// Hull-White zero-coupon bond price P_HW(0, T) = exp(-B(T)*r) * A(T).
/// At t=0, the model is fitted to the market curve, so P_HW(0,T) = P_mkt(0,T).
/// For the Jamshidian decomposition we need P_HW(T_exp, T_i | r*),
/// the model bond price at expiry T_exp given short rate r*:
///
///   P_HW(T_exp, T_i | r*) = A(T_exp, T_i) · exp(-B(T_i - T_exp) · r*)
///
/// where:
///   B(τ)       = (1 - exp(-a·τ)) / a
///   A(T_exp,Ti)= P(0,Ti) / P(0,T_exp) · exp(B(Ti-T_exp)·f(0,T_exp)
///                - σ²/(4a) · B(Ti-T_exp)² · (1-exp(-2a·T_exp)))
///
/// Numerically, at t=0 the mean of r(T_exp) under Q is the forward rate f(0,T_exp),
/// so the critical rate r* lies near that value.

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
                   double hw_a, double hw_sigma)
    : Instrument(expiry + swapTenor),
      type_(type), notional_(notional), strike_(strike),
      expiry_(expiry), swapTenor_(swapTenor), frequency_(frequency),
      hw_a_(hw_a), hw_sigma_(hw_sigma)
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
    int    n   = static_cast<int>(std::round(swapTenor_ * frequency_));
    double tau = 1.0 / frequency_;

    // Payment dates of the underlying swap: T_exp + i*tau for i=1..n
    std::vector<double> T(n);
    std::vector<double> P0T(n);   // P(0, expiry + i*tau)
    std::vector<double> c(n);     // coupon weights

    double P0exp = curve.discountFactor(expiry_);

    for (int i = 0; i < n; ++i) {
        T[i]   = expiry_ + (i + 1) * tau;
        P0T[i] = curve.discountFactor(T[i]);
        c[i]   = notional_ * strike_ * tau;
    }
    // Last cash flow includes notional repayment
    c[n - 1] += notional_;

    // ── Jamshidian step 1: find r* such that swap NPV = 0 at T_exp ────────
    // Swap NPV at T_exp given r* : Σ c_i · P(T_exp, T_i | r*) - N·P(T_exp, T_exp)
    // where P(T_exp, T_exp)=1. But for a payer IRS starting at T_exp:
    //   swap_NPV(r*) = Σ_i c_i · P(T_exp, T_i | r*) - N  = 0
    // ⟹ Σ_i c_i · F_i · exp(-B_i · r*)  = N
    // We solve this via bisection on r*.

    auto swapNPV = [&](double r) -> double {
        double npv = 0.0;
        for (int i = 0; i < n; ++i) {
            double tau_i = (i + 1) * tau;  // T[i] - T_exp
            double B_i   = hwB(tau_i, hw_a_);
            double F_i   = P0T[i] / P0exp;
            npv += c[i] * F_i * std::exp(-B_i * r);
        }
        return npv - notional_;
    };

    // r* is close to the par swap rate; use the forward short rate as centre
    // Mean of r(T_exp) under Q ≈ f(0, T_exp)  (approximately for small sigma)
    double eps = 1e-5;
    double f0  = -std::log(P0exp / curve.discountFactor(expiry_ + eps)) / eps;
    double variance = hwVariance(expiry_, hw_a_, hw_sigma_);
    double rStd     = std::sqrt(variance);

    // Bisection on [f0 - 10*rStd, f0 + 10*rStd]
    double lo = f0 - 10.0 * rStd;
    double hi = f0 + 10.0 * rStd;

    // Ensure the root is bracketed (swap NPV is monotone in r* — decreasing)
    if (swapNPV(lo) < 0.0) return 0.0; // deep OTM
    if (swapNPV(hi) > 0.0) return 0.0; // deep OTM

    double r_star = lo;
    for (int iter = 0; iter < 100; ++iter) {
        double mid = 0.5 * (lo + hi);
        if (swapNPV(mid) > 0.0)
            lo = mid;
        else
            hi = mid;
        if (hi - lo < 1e-10) break;
    }
    r_star = 0.5 * (lo + hi);

    // ── Jamshidian step 2: price as portfolio of ZCB options ──────────────
    // X_i = P_HW(T_exp, T_i | r*) — the bond strike for caplet i
    double total = 0.0;
    for (int i = 0; i < n; ++i) {
        double tau_i = (i + 1) * tau;
        double B_i   = hwB(tau_i, hw_a_);
        double F_i   = P0T[i] / P0exp;
        double X_i   = F_i * std::exp(-B_i * r_star);

        total += c[i] * hwZCBOption(type_, P0exp, P0T[i],
                                    X_i, expiry_, tau_i,
                                    hw_a_, hw_sigma_);
    }
    return total;
}

double Swaption::calculatePV(const core::MarketEnvironment& env) const
{
    return price(env.curve());
}

} // namespace qf::instruments
