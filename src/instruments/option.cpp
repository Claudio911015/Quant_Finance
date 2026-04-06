#include <qf/instruments/option.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/pricingengines/blackscholes.hpp>

namespace qf::instruments {

Option::Option(std::shared_ptr<IUnderlying> underlying,
               double strikeVal, double maturity,
               OptionType optType, ExerciseType exer)
    : Instrument(maturity),
      underlying_(std::move(underlying)),
      strike_(strikeVal), type_(optType), exercise_(exer)
{}

double Option::calculatePV(const core::MarketEnvironment& /*env*/) const {
    // Legacy path: uses fields stored directly on Option
    OptionParams params{spot, strike, riskFreeRate, dividendYield,
                        volatility, maturity(), type, exercise};
    return pricingengines::blackScholes(params).price;
}

} // namespace qf::instruments
