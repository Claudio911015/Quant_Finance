#include <qf/pricingengines/blackscholes.hpp>
#include <qf/pricingengines/detail/env_resolver.hpp>
#include <qf/math/rootfinding.hpp>
#include <qf/math/statistics.hpp>
#include <cmath>
#include <stdexcept>

namespace qf::pricingengines {

using qf::math::normCDF;
using qf::math::normPDF;

// ── Black-Scholes formula ─────────────────────────────────────────────────────

BSResult blackScholes(const instruments::OptionParams& p)
{
    if (p.maturity <= 0.0 || p.spot <= 0.0)
        throw std::invalid_argument("BlackScholes: spot and maturity must be positive");
    if (p.strike < 0.0)
        throw std::invalid_argument("BlackScholes: strike must be non-negative");
    if (p.volatility < 0.0)
        throw std::invalid_argument("BlackScholes: volatility must be non-negative");

    const double S   = p.spot;
    const double K   = p.strike;
    const double r   = p.riskFreeRate;
    const double q   = p.dividendYield;
    const double sig = p.volatility;
    const double T   = p.maturity;
    const double eqT = std::exp(-q * T);
    const double erT = std::exp(-r * T);
    const bool isCall = (p.type == instruments::OptionType::Call);

    // ── vol = 0: intrinsic value only ─────────────────────────────────────────
    // When σ = 0 there is no optionality; the option is worth its forward intrinsic.
    // The formula diverges (d₁ = ±∞) so we handle this case explicitly.
    if (sig == 0.0) {
        BSResult res{};
        double fwd = S * eqT - K * erT; // forward intrinsic (positive if ITM call)
        res.price = isCall ? std::max(fwd, 0.0) : std::max(-fwd, 0.0);
        // Delta is a step function; at-the-money we use 0.5 * e^{-qT} by convention.
        res.delta = isCall
            ? (fwd > 0.0 ? eqT : (fwd < 0.0 ? 0.0 : 0.5 * eqT))
            : (fwd < 0.0 ? -eqT : (fwd > 0.0 ? 0.0 : -0.5 * eqT));
        res.gamma = 0.0;
        res.vega  = 0.0;
        // Theta: decay of the forward intrinsic only for ITM options.
        if (isCall && fwd > 0.0)
            res.theta = (-q * S * eqT + r * K * erT) / 365.0;
        else if (!isCall && fwd < 0.0)
            res.theta = (q * S * eqT - r * K * erT) / 365.0;
        else
            res.theta = 0.0;
        // Rho: rate sensitivity of forward intrinsic (ITM options only, /100 for 1% convention).
        res.rho = isCall
            ? (fwd > 0.0 ?  K * T * erT / 100.0 : 0.0)
            : (fwd < 0.0 ? -K * T * erT / 100.0 : 0.0);
        return res;
    }

    const double sqT  = std::sqrt(T);
    const double d1 = (std::log(S / K) + (r - q + 0.5 * sig * sig) * T) / (sig * sqT);
    const double d2 = d1 - sig * sqT;

    const double Nd1  = normCDF(d1);
    const double Nd2  = normCDF(d2);
    const double Nnd1 = normCDF(-d1);
    const double Nnd2 = normCDF(-d2);
    const double nd1  = normPDF(d1);

    BSResult res{};

    // Price
    if (isCall)
        res.price = S * eqT * Nd1 - K * erT * Nd2;
    else
        res.price = K * erT * Nnd2 - S * eqT * Nnd1;

    // Delta
    res.delta = isCall ?  eqT * Nd1
                       : -eqT * Nnd1;

    // Gamma (same for call and put)
    res.gamma = eqT * nd1 / (S * sig * sqT);

    // Vega (same for call and put, per 1% move in vol → divide by 100)
    res.vega = S * eqT * nd1 * sqT / 100.0;

    // Theta (per calendar day)
    double theta_common = -(S * eqT * nd1 * sig) / (2.0 * sqT);
    if (isCall)
        res.theta = (theta_common - r * K * erT * Nd2  + q * S * eqT * Nd1)  / 365.0;
    else
        res.theta = (theta_common + r * K * erT * Nnd2 - q * S * eqT * Nnd1) / 365.0;

    // Rho (per 1% move in rate → divide by 100)
    if (isCall)
        res.rho =  K * T * erT * Nd2  / 100.0;
    else
        res.rho = -K * T * erT * Nnd2 / 100.0;

    return res;
}

// ── Implied Volatility ────────────────────────────────────────────────────────

double impliedVolatility(const instruments::OptionParams& p,
                         double marketPrice, double tol, int maxIt)
{
    auto priceFn = [&](double vol) {
        instruments::OptionParams q = p;
        q.volatility = vol;
        return blackScholes(q).price - marketPrice;
    };

    // Bracket: vol in (1e-6, 5.0) covers 0.01% to 500%
    return math::brent(priceFn, 1e-6, 5.0, tol, maxIt);
}

BlackScholesEngine::BlackScholesEngine(instruments::OptionParams params)
    : params_(std::move(params)) {}

BlackScholesEngine::BlackScholesEngine(instruments::OptionParams params, std::string ticker)
    : params_(std::move(params)), ticker_(std::move(ticker)) {}

double BlackScholesEngine::price(const core::MarketEnvironment& env) const {
    auto p = detail::resolveEquityParams(params_, ticker_, env);
    return blackScholes(p).price;
}

} // namespace qf::pricingengines
