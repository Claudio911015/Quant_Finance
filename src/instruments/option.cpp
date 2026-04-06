#include <qf/instruments/option.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/pricingengines/blackscholes.hpp>

namespace qf::instruments {

double Option::calculatePV(const core::MarketEnvironment& /*env*/) const
{
    // For simple Black-Scholes European option pricing, term structure is not used directly
    // because we rely on constant rates in Option object.
    qf::instruments::OptionParams params{
        spot,
        strike,
        riskFreeRate,
        dividendYield,
        volatility,
        maturity(),
        type,
        exercise
    };
    return qf::pricingengines::blackScholes(params).price;
}

} // namespace qf::instruments

