#include <qf/instruments/fx_option.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <cmath>
#include <stdexcept>
#include <utility>

namespace qf::instruments {

namespace {
constexpr double kDaysPerYear = 365.0;   // T = days / 365, same as the OIS curves
}

FxOption::FxOption(double notionalForeign, double strike, int maturityDays, OptionType type,
                   FxSide side, std::string pair, std::string domesticCurve,
                   std::string foreignCurve)
    : Instrument(maturityDays / kDaysPerYear),
      notionalForeign_(notionalForeign),
      strike_(strike),
      maturityDays_(maturityDays),
      type_(type),
      side_(side),
      pair_(std::move(pair)),
      domesticCurve_(std::move(domesticCurve)),
      foreignCurve_(std::move(foreignCurve))
{
    if (notionalForeign_ <= 0.0)
        throw std::invalid_argument("FxOption: notional must be positive");
    if (strike_ <= 0.0)
        throw std::invalid_argument("FxOption: strike must be positive");
    if (maturityDays_ <= 0)
        throw std::invalid_argument("FxOption: maturityDays must be positive");
}

double FxOption::npv(const core::MarketEnvironment& env) const
{
    return greeks(env).price;
}

FxOptionGreeks FxOption::greeks(const core::MarketEnvironment& env) const
{
    const double T   = maturityDays_ / kDaysPerYear;
    const double dfD = env.curve(domesticCurve_).discountFactor(T);
    const double dfF = env.curve(foreignCurve_).discountFactor(T);
    const double S   = env.spot(pair_);
    const double vol = env.volatility(pair_, strike_, T);

    // Garman-Kohlhagen = Black-Scholes with the foreign rate as dividend yield.
    // blackScholes() already returns vega per 1 vol point, so no rescaling here.
    OptionParams p{};
    p.spot          = S;
    p.strike        = strike_;
    p.riskFreeRate  = -std::log(dfD) / T;
    p.dividendYield = -std::log(dfF) / T;
    p.volatility    = vol;
    p.maturity      = T;
    p.type          = type_;
    p.exercise      = ExerciseType::European;
    const pricingengines::BSResult bs = pricingengines::blackScholes(p);

    const double scale = ((side_ == FxSide::Buy) ? 1.0 : -1.0) * notionalForeign_;
    return {scale * bs.price, scale * bs.delta, scale * bs.gamma, scale * bs.vega,
            S * dfF / dfD, vol};
}

} // namespace qf::instruments
