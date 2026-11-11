#include <qf/instruments/fx_forward.hpp>
#include <stdexcept>
#include <utility>

namespace qf::instruments {

namespace {
constexpr double kDaysPerYear = 365.0;   // T = days / 365, same as the OIS curves
}

FxForward::FxForward(double notionalForeign, double strike, int maturityDays, FxSide side,
                     std::string pair, std::string domesticCurve, std::string foreignCurve)
    : Instrument(maturityDays / kDaysPerYear),
      notionalForeign_(notionalForeign),
      strike_(strike),
      maturityDays_(maturityDays),
      side_(side),
      pair_(std::move(pair)),
      domesticCurve_(std::move(domesticCurve)),
      foreignCurve_(std::move(foreignCurve))
{
    if (notionalForeign_ <= 0.0)
        throw std::invalid_argument("FxForward: notional must be positive");
    if (strike_ <= 0.0)
        throw std::invalid_argument("FxForward: strike must be positive");
    if (maturityDays_ <= 0)
        throw std::invalid_argument("FxForward: maturityDays must be positive");
}

double FxForward::npv(const core::MarketEnvironment& env) const
{
    const double T   = maturityDays_ / kDaysPerYear;
    const double dfD = env.curve(domesticCurve_).discountFactor(T);
    const double dfF = env.curve(foreignCurve_).discountFactor(T);
    const double s   = (side_ == FxSide::Buy) ? 1.0 : -1.0;
    return s * notionalForeign_ * (env.spot(pair_) * dfF - strike_ * dfD);
}

double FxForward::forwardRate(const core::MarketEnvironment& env) const
{
    const double T = maturityDays_ / kDaysPerYear;
    return env.spot(pair_) * env.curve(foreignCurve_).discountFactor(T)
         / env.curve(domesticCurve_).discountFactor(T);
}

double FxForward::delta(const core::MarketEnvironment& env) const
{
    const double T = maturityDays_ / kDaysPerYear;
    const double s = (side_ == FxSide::Buy) ? 1.0 : -1.0;
    return s * notionalForeign_ * env.curve(foreignCurve_).discountFactor(T);
}

} // namespace qf::instruments
