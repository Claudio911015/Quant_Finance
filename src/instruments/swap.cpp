#include <qf/instruments/swap.hpp>
#include <cmath>
#include <stdexcept>

namespace qf::instruments {

InterestRateSwap::InterestRateSwap(double notional, double fixedRate,
                                   double maturity, double frequency,
                                   SwapType type)
    : Instrument(maturity),
      notional_(notional), fixedRate_(fixedRate),
      maturity_(maturity), frequency_(frequency), type_(type)
{
    if (notional <= 0.0)
        throw std::invalid_argument("InterestRateSwap: notional must be positive");
    if (maturity <= 0.0)
        throw std::invalid_argument("InterestRateSwap: maturity must be positive");
    if (frequency <= 0.0)
        throw std::invalid_argument("InterestRateSwap: frequency must be positive");
}

double InterestRateSwap::annuity(const termstructure::YieldCurve& curve) const
{
    double dt = 1.0 / frequency_;
    int nPayments = static_cast<int>(maturity_ * frequency_);
    double sum = 0.0;

    for (int i = 1; i <= nPayments; ++i) {
        double t = i * dt;
        sum += dt * curve.discountFactor(t);
    }

    return notional_ * sum;
}

double InterestRateSwap::npv(const termstructure::YieldCurve& curve) const
{
    // Floating leg value = N * (P(0, t_start) - P(0, t_end))
    // For spot-starting swap: t_start = 0, so P(0,0) = 1
    double floatingLeg = notional_ * (1.0 - curve.discountFactor(maturity_));

    // Fixed leg value = R * Annuity
    double fixedLeg = fixedRate_ * annuity(curve);

    // Payer swap: pay fixed, receive floating
    double payer_npv = floatingLeg - fixedLeg;

    return (type_ == SwapType::Payer) ? payer_npv : -payer_npv;
}

double InterestRateSwap::calculatePV(const termstructure::YieldCurve& curve) const
{
    return npv(curve);
}

double InterestRateSwap::parRate(double maturity, double frequency,
                                 const termstructure::YieldCurve& curve)
{
    if (maturity <= 0.0 || frequency <= 0.0)
        throw std::invalid_argument("InterestRateSwap::parRate: invalid parameters");

    double dt = 1.0 / frequency;
    int nPayments = static_cast<int>(maturity * frequency);
    double annuitySum = 0.0;

    for (int i = 1; i <= nPayments; ++i)
        annuitySum += dt * curve.discountFactor(i * dt);

    // Par rate: R = (1 - P(0,T)) / Annuity
    return (1.0 - curve.discountFactor(maturity)) / annuitySum;
}

} // namespace qf::instruments
