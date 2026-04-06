#pragma once
#include <memory>
#include <qf/instruments/instrument.hpp>
#include <qf/instruments/iunderlying.hpp>
#include <qf/core/market_environment.hpp>

namespace qf::instruments {

enum class OptionType   { Call, Put };
enum class ExerciseType { European, American };

class Option : public Instrument {
public:
    // ── Legacy constructor (backward-compat) ─────────────────────────────
    Option() = default;
    Option(double spot_, double strike_, double riskFreeRate_, double dividendYield_,
           double volatility_, double maturity_, OptionType type_, ExerciseType exercise_)
        : Instrument(maturity_), spot(spot_), strike(strike_),
          riskFreeRate(riskFreeRate_), dividendYield(dividendYield_),
          volatility(volatility_), type(type_), exercise(exercise_)
    {}

    // ── New constructor (with IUnderlying) ────────────────────────────────
    Option(std::shared_ptr<IUnderlying> underlying,
           double strike, double maturity,
           OptionType type, ExerciseType exercise);

    // Legacy public fields (preserved for backward-compat)
    double spot = 0.0;
    double strike = 0.0;
    double riskFreeRate = 0.0;
    double dividendYield = 0.0;
    double volatility = 0.0;
    OptionType type = OptionType::Call;
    ExerciseType exercise = ExerciseType::European;

    // New accessors (meaningful when constructed with IUnderlying)
    double strikeValue() const { return strike_; }
    OptionType optionType() const { return type_; }
    ExerciseType exerciseType() const { return exercise_; }
    const IUnderlying& underlying() const { return *underlying_; }

    double calculatePV(const core::MarketEnvironment& env) const override;

private:
    std::shared_ptr<IUnderlying> underlying_;
    double strike_ = 0.0;
    OptionType type_ = OptionType::Call;
    ExerciseType exercise_ = ExerciseType::European;
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
