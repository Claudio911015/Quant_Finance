#include <qf/pricingengines/montecarlo.hpp>
#include <cmath>
#include <random>
#include <stdexcept>

namespace qf::pricingengines {

double monteCarloBSPrice(const instruments::OptionParams& p,
                         int N,
                         unsigned seed)
{
    if (N <= 0)
        throw std::invalid_argument("monteCarloBSPrice: N must be positive");

    if (p.spot <= 0.0 || p.strike <= 0.0 || p.maturity <= 0.0 || p.volatility <= 0.0)
        throw std::invalid_argument("monteCarloBSPrice: invalid option parameters");

    if (p.exercise != instruments::ExerciseType::European)
        throw std::invalid_argument("monteCarloBSPrice: only European options supported");

    std::mt19937_64 rng(seed);
    std::normal_distribution<double> Z(0.0, 1.0);

    const double S0  = p.spot;
    const double K   = p.strike;
    const double r   = p.riskFreeRate;
    const double q   = p.dividendYield;
    const double sig = p.volatility;
    const double T   = p.maturity;

    const double drift = (r - q - 0.5 * sig * sig) * T;
    const double diff  = sig * std::sqrt(T);

    double sum = 0.0;
    for (int i = 0; i < N; ++i) {
        double ST = S0 * std::exp(drift + diff * Z(rng));
        double payoff = (p.type == instruments::OptionType::Call)
                      ? std::max(ST - K, 0.0)
                      : std::max(K - ST, 0.0);
        sum += payoff;
    }

    return std::exp(-r * T) * sum / static_cast<double>(N);
}

MonteCarloEngine::MonteCarloEngine(instruments::OptionParams params, int N, unsigned seed)
    : params_(std::move(params)), N_(N), seed_(seed) {}

double MonteCarloEngine::price(const core::MarketEnvironment& /*env*/) const {
    return monteCarloBSPrice(params_, N_, seed_);
}

} // namespace qf::pricingengines

