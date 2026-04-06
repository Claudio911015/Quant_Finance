#pragma once
#include <qf/instruments/option.hpp>
#include <qf/core/market_environment.hpp>
#include <string>
#include <utility>

namespace qf::pricingengines::detail {

/// For equity engines (BS, MC, BT, FDM):
/// If ticker is non-empty, reads spot / volatility / riskFreeRate from env.
/// If ticker is empty, returns params unchanged (backward-compat path).
/// Throws std::out_of_range if ticker is set but any required datum is missing from env.
inline instruments::OptionParams resolveEquityParams(
    instruments::OptionParams params,
    const std::string& ticker,
    const core::MarketEnvironment& env)
{
    if (ticker.empty()) return params;
    params.spot         = env.spot(ticker);
    params.volatility   = env.volatility(ticker);
    params.riskFreeRate = env.curve("default").zeroRate(params.maturity);
    return params;
}

/// For HestonEngine: only spot and riskFreeRate come from env
/// (HestonParams are model calibration data — not observable market data).
inline std::pair<double,double> resolveSpotAndRate(
    double defaultSpot, double defaultRate, double maturity,
    const std::string& ticker,
    const core::MarketEnvironment& env)
{
    if (ticker.empty()) return {defaultSpot, defaultRate};
    return {env.spot(ticker),
            env.curve("default").zeroRate(maturity)};
}

} // namespace qf::pricingengines::detail
