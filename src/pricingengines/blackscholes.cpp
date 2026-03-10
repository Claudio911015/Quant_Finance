#include <qf/pricingengines/blackscholes.hpp>
#include <qf/math/rootfinding.hpp>
#include <cmath>
#include <stdexcept>

namespace qf::pricingengines {

// ── Normal distribution helpers ───────────────────────────────────────────────

static double normCDF(double x) {
    return 0.5 * std::erfc(-x / std::sqrt(2.0));
}

static double normPDF(double x) {
    return std::exp(-0.5 * x * x) / std::sqrt(2.0 * M_PI);
}

// ── Black-Scholes formula ─────────────────────────────────────────────────────

BSResult blackScholes(const instruments::OptionParams& p)
{
    if (p.volatility <= 0.0 || p.maturity <= 0.0 || p.spot <= 0.0 || p.strike <= 0.0)
        throw std::invalid_argument("BlackScholes: invalid parameters");

    const double S    = p.spot;
    const double K    = p.strike;
    const double r    = p.riskFreeRate;
    const double q    = p.dividendYield;
    const double sig  = p.volatility;
    const double T    = p.maturity;
    const double sqT  = std::sqrt(T);

    const double d1 = (std::log(S / K) + (r - q + 0.5 * sig * sig) * T) / (sig * sqT);
    const double d2 = d1 - sig * sqT;

    const double Nd1  = normCDF(d1);
    const double Nd2  = normCDF(d2);
    const double Nnd1 = normCDF(-d1);
    const double Nnd2 = normCDF(-d2);
    const double nd1  = normPDF(d1);

    const double eqT  = std::exp(-q * T);
    const double erT  = std::exp(-r * T);

    BSResult res{};

    bool isCall = (p.type == instruments::OptionType::Call);

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

} // namespace qf::pricingengines
