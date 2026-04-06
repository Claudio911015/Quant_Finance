#include <qf/pricingengines/montecarlo.hpp>
#include <qf/pricingengines/detail/env_resolver.hpp>
#include <cmath>
#include <random>
#include <stdexcept>

namespace qf::pricingengines {

double monteCarloBSPrice(const instruments::OptionParams& p, int N, unsigned seed)
{
    if (N <= 0)
        throw std::invalid_argument("monteCarloBSPrice: N must be positive");
    if (p.spot <= 0.0 || p.strike <= 0.0 || p.maturity <= 0.0 || p.volatility <= 0.0)
        throw std::invalid_argument("monteCarloBSPrice: invalid option parameters");
    if (p.exercise != instruments::ExerciseType::European)
        throw std::invalid_argument("monteCarloBSPrice: only European options supported");

    std::mt19937_64 rng(seed);
    std::normal_distribution<double> Z(0.0, 1.0);

    const double drift = (p.riskFreeRate - p.dividendYield - 0.5*p.volatility*p.volatility)*p.maturity;
    const double diff  = p.volatility * std::sqrt(p.maturity);

    double sum = 0.0;
    for (int i = 0; i < N; ++i) {
        double ST = p.spot * std::exp(drift + diff * Z(rng));
        double payoff = (p.type == instruments::OptionType::Call)
                      ? std::max(ST - p.strike, 0.0)
                      : std::max(p.strike - ST, 0.0);
        sum += payoff;
    }
    return std::exp(-p.riskFreeRate * p.maturity) * sum / static_cast<double>(N);
}

MonteCarloEngine::MonteCarloEngine(instruments::OptionParams params, int N, unsigned seed)
    : params_(std::move(params)), N_(N), seed_(seed) {}

MonteCarloEngine::MonteCarloEngine(std::shared_ptr<models::IEquityModel> model,
                                   instruments::OptionParams params,
                                   int N, int nSteps, unsigned seed)
    : params_(std::move(params)), model_(std::move(model)),
      N_(N), nSteps_(nSteps), seed_(seed)
{
    if (!model_)
        throw std::invalid_argument("MonteCarloEngine: model must not be null");
    if (N_ <= 0)
        throw std::invalid_argument("MonteCarloEngine: N must be positive");
    if (nSteps_ <= 0)
        throw std::invalid_argument("MonteCarloEngine: nSteps must be positive");
}

MonteCarloEngine::MonteCarloEngine(instruments::OptionParams params, std::string ticker,
                                   int N, unsigned seed)
    : params_(std::move(params)), ticker_(std::move(ticker)), N_(N), seed_(seed) {}

double MonteCarloEngine::price(const core::MarketEnvironment& env) const {
    if (model_) {
        // Model-driven: resolve params then simulate via model
        auto p = detail::resolveEquityParams(params_, ticker_, env);
        double sum = 0.0;
        for (int i = 0; i < N_; ++i) {
            auto path = model_->simulate(p.spot, p.maturity, nSteps_,
                                         seed_ + static_cast<unsigned>(i));
            double ST = path.back();
            double payoff = (p.type == instruments::OptionType::Call)
                          ? std::max(ST - p.strike, 0.0)
                          : std::max(p.strike - ST, 0.0);
            sum += payoff;
        }
        return std::exp(-p.riskFreeRate * p.maturity) * sum / static_cast<double>(N_);
    }
    // Legacy / env-aware: resolve params (ticker_ empty = pass-through) then free function
    auto p = detail::resolveEquityParams(params_, ticker_, env);
    return monteCarloBSPrice(p, N_, seed_);
}

} // namespace qf::pricingengines
