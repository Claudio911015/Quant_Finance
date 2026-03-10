#include <qf/pricingengines/binomialtree.hpp>
#include <cmath>
#include <stdexcept>
#include <vector>

namespace qf::pricingengines {

double binomialTreeBSPrice(const instruments::OptionParams& p,
                           int nSteps)
{
    if (nSteps <= 0)
        throw std::invalid_argument("binomialTreeBSPrice: nSteps must be positive");

    if (p.spot <= 0.0 || p.strike <= 0.0 || p.maturity <= 0.0 || p.volatility <= 0.0)
        throw std::invalid_argument("binomialTreeBSPrice: invalid option parameters");

    const double S0 = p.spot;
    const double K  = p.strike;
    const double r  = p.riskFreeRate;
    const double q  = p.dividendYield;
    const double sigma = p.volatility;
    const double T = p.maturity;

    const double dt = T / nSteps;
    const double u  = std::exp(sigma * std::sqrt(dt));
    const double d  = 1.0 / u;
    const double disc = std::exp(-r * dt);
    const double pUp = (std::exp((r - q) * dt) - d) / (u - d);
    const double pDn = 1.0 - pUp;

    if (pUp < 0.0 || pUp > 1.0)
        throw std::runtime_error("binomialTreeBSPrice: unstable tree probabilities");

    std::vector<double> values(nSteps + 1);

    // Terminal payoffs
    for (int i = 0; i <= nSteps; ++i) {
        double ST = S0 * std::pow(u, i) * std::pow(d, nSteps - i);
        values[i] = (p.type == instruments::OptionType::Call)
            ? std::max(ST - K, 0.0)
            : std::max(K - ST, 0.0);
    }

    // Backward induction
    for (int step = nSteps - 1; step >= 0; --step) {
        for (int i = 0; i <= step; ++i) {
            double cont = disc * (pUp * values[i + 1] + pDn * values[i]);
            if (p.exercise == instruments::ExerciseType::American) {
                double ST = S0 * std::pow(u, i) * std::pow(d, step - i);
                double intrinsic = (p.type == instruments::OptionType::Call)
                    ? std::max(ST - K, 0.0)
                    : std::max(K - ST, 0.0);
                values[i] = std::max(cont, intrinsic);
            } else {
                values[i] = cont;
            }
        }
    }

    return values[0];
}

} // namespace qf::pricingengines

