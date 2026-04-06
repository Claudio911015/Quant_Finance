#pragma once
#include <qf/instruments/instrument.hpp>
#include <qf/core/market_environment.hpp>

namespace qf::instruments {

enum class OptionType   { Call, Put };
enum class ExerciseType { European, American };

class Option : public Instrument {
public:
    Option() = default;
    Option(double spot_, double strike_, double riskFreeRate_, double dividendYield_,
           double volatility_, double maturity_, OptionType type_, ExerciseType exercise_)
        : Instrument(maturity_), spot(spot_), strike(strike_), riskFreeRate(riskFreeRate_),
          dividendYield(dividendYield_), volatility(volatility_), type(type_), exercise(exercise_)
    {}

    double spot = 0.0;
    double strike = 0.0;
    double riskFreeRate = 0.0;
    double dividendYield = 0.0;
    double volatility = 0.0;
    OptionType type = OptionType::Call;
    ExerciseType exercise = ExerciseType::European;

    double calculatePV(const core::MarketEnvironment& env) const override;
};

struct OptionParams {
    double      spot;
    double      strike;
    double      riskFreeRate;
    double      dividendYield;
    double      volatility;
    double      maturity;
    OptionType  type;
    ExerciseType exercise;
};

} // namespace qf::instruments
