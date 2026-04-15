#include <qf/instruments/swap.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/math/daycount.hpp>
#include <cmath>
#include <stdexcept>

namespace qf::instruments {

/// @brief Sum of discounted period fractions: Σ τ · P(0, i·dt).
///
/// @param maturity   Swap tenor in years.
/// @param frequency  Payment periods per year.
/// @param curve      Discount curve.
/// @param dcc        Day-count convention (determines τ per period; default ACT_365).
static double discountAnnuity(double maturity, double frequency,
                               const termstructure::YieldCurve& curve,
                               math::DayCountConvention dcc = math::DayCountConvention::ACT_365)
{
    double dt  = 1.0 / frequency;                       // calendar step (schedule)
    double tau = math::periodFraction(frequency, dcc);  // accrual fraction per period
    int nPayments = static_cast<int>(maturity * frequency);
    double sum = 0.0;

    for (int i = 1; i <= nPayments; ++i) {
        double t = i * dt;
        sum += tau * curve.discountFactor(t);
    }
    return sum;
}

// Leg implementation

double Leg::calculatePV(const core::MarketEnvironment& env) const
{
    const auto& curve = env.curve();
    // dt: uniform time step between payment dates (calendar time, unaffected by DCC).
    // tau: accrual fraction per period — the interest numerator in each payment.
    double dt  = 1.0 / frequency_;
    double tau = math::periodFraction(frequency_, dcc_);
    int    n   = static_cast<int>(std::round(maturity() * frequency_));

    if (floating_) {
        // Floating leg PV = N * (1 - P(0,T)) via the floating-leg replication identity.
        // Spread payments are N * spread * tau at each payment date i*dt.
        double floatPV = notional_ * (1.0 - curve.discountFactor(maturity()));
        for (int i = 1; i <= n; ++i)
            floatPV += notional_ * spread_ * tau * curve.discountFactor(i * dt);
        return floatPV;
    }

    // Fixed leg: N * K * tau at each payment date i*dt, plus notional at maturity.
    double fixedPV = 0.0;
    for (int i = 1; i <= n; ++i)
        fixedPV += notional_ * fixedRate_ * tau * curve.discountFactor(i * dt);
    fixedPV += notional_ * curve.discountFactor(maturity());
    return fixedPV;
}

InterestRateSwap::InterestRateSwap(double notional, double fixedRate,
                                   double maturity, double frequency,
                                   SwapType type)
    : Swap(
          Leg("USD", math::DayCountConvention::ACT_365, notional, maturity, fixedRate, 0.0, false, frequency),
          Leg("USD", math::DayCountConvention::ACT_365, notional, maturity, 0.0,       0.0, true,  frequency),
          SwapLegType::FixedFloating),
      frequency_(frequency), type_(type)
{
    if (notional <= 0.0)
        throw std::invalid_argument("InterestRateSwap: notional must be positive");
    if (maturity <= 0.0)
        throw std::invalid_argument("InterestRateSwap: maturity must be positive");
    if (frequency <= 0.0)
        throw std::invalid_argument("InterestRateSwap: frequency must be positive");
}

double InterestRateSwap::annuity(const core::MarketEnvironment& env) const {
    return discountAnnuity(maturity(), frequency_, env.curve(), payLeg().dayCount());
}

double InterestRateSwap::npv(const core::MarketEnvironment& env) const {
    // Leg::calculatePV for fixed includes the notional repayment while floating
    // uses the replication identity N*(1-P(T)) which excludes it — they cannot
    // be subtracted directly.  Instead we compute coupon streams only:
    //   float (no notional) = N * (1 - P(0,T))           [replication identity]
    //   fixed (no notional) = N * K * discountAnnuity(...)
    // The DCC is read from the payLeg so npv honours the convention stored there.
    const auto& curve    = env.curve();
    double notional  = payLeg().notional();
    double fixedRate = payLeg().fixedRate();
    double mat       = maturity();
    double floatingLeg = notional * (1.0 - curve.discountFactor(mat));
    double fixedLeg    = notional * fixedRate
                       * discountAnnuity(mat, frequency_, curve, payLeg().dayCount());
    double payer_npv   = floatingLeg - fixedLeg;
    return (type_ == SwapType::Payer) ? payer_npv : -payer_npv;
}

// Legacy YieldCurve overloads — delegate to MarketEnvironment
double InterestRateSwap::annuity(const termstructure::YieldCurve& curve) const {
    return annuity(core::MarketEnvironment(curve));
}

double InterestRateSwap::npv(const termstructure::YieldCurve& curve) const {
    return npv(core::MarketEnvironment(curve));
}

double InterestRateSwap::parRate(double maturity, double frequency,
                                  const core::MarketEnvironment& env) {
    return parRate(maturity, frequency, env.curve());
}

double InterestRateSwap::parRate(double maturity, double frequency,
                                  const termstructure::YieldCurve& curve) {
    if (maturity <= 0.0 || frequency <= 0.0)
        throw std::invalid_argument("InterestRateSwap::parRate: invalid parameters");
    double dt = 1.0 / frequency;
    int nPayments = static_cast<int>(maturity * frequency);
    double annuitySum = 0.0;
    for (int i = 1; i <= nPayments; ++i)
        annuitySum += dt * curve.discountFactor(i * dt);
    return (1.0 - curve.discountFactor(maturity)) / annuitySum;
}

double InterestRateSwap::annuity(double maturity, double frequency,
                                  const core::MarketEnvironment& env) {
    return discountAnnuity(maturity, frequency, env.curve());
}

double InterestRateSwap::annuity(double maturity, double frequency,
                                  const termstructure::YieldCurve& curve) {
    return discountAnnuity(maturity, frequency, curve);
}

} // namespace qf::instruments
