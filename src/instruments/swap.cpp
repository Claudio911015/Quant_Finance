#include <qf/instruments/swap.hpp>
#include <qf/core/market_environment.hpp>
#include <cmath>
#include <stdexcept>

namespace qf::instruments {

static double discountAnnuity(double maturity, double frequency, const termstructure::YieldCurve& curve)
{
    double dt = 1.0 / frequency;
    int nPayments = static_cast<int>(maturity * frequency);
    double sum = 0.0;

    for (int i = 1; i <= nPayments; ++i) {
        double t = i * dt;
        sum += dt * curve.discountFactor(t);
    }
    return sum;
}

// Leg implementation

double Leg::calculatePV(const core::MarketEnvironment& env) const
{
    const auto& curve = env.curve();
    if (floating_) {
        double floatPV = notional_ * (1.0 - curve.discountFactor(maturity()));
        if (spread_ != 0.0) {
            double dt = maturity();
            floatPV += notional_ * spread_ * dt * curve.discountFactor(maturity());
        }
        return floatPV;
    }

    // Fixed leg: fixed coupon + notional at maturity
    int nPayments = static_cast<int>(std::max(1.0, maturity()));
    double fixedPV = 0.0;
    for (int i = 1; i <= nPayments; ++i) {
        double t = std::min(maturity(), static_cast<double>(i));
        fixedPV += notional_ * fixedRate_ * curve.discountFactor(t);
    }
    fixedPV += notional_ * curve.discountFactor(maturity());
    return fixedPV;
}

InterestRateSwap::InterestRateSwap(double notional, double fixedRate,
                                   double maturity, double frequency,
                                   SwapType type)
    : Swap(
          Leg("USD", "ACT/365", notional, maturity, fixedRate, 0.0, false),
          Leg("USD", "ACT/365", notional, maturity, 0.0,       0.0, true),
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
    return discountAnnuity(maturity(), frequency_, env.curve());
}

double InterestRateSwap::npv(const core::MarketEnvironment& env) const {
    const auto& curve = env.curve();
    double notional  = payLeg().notional();
    double fixedRate = payLeg().fixedRate();
    double mat       = maturity();
    double floatingLeg = notional * (1.0 - curve.discountFactor(mat));
    double fixedLeg    = notional * fixedRate * discountAnnuity(mat, frequency_, curve);
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
