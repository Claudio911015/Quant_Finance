#pragma once

namespace qf::instruments {

enum class OptionType   { Call, Put };
enum class ExerciseType { European, American };

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
