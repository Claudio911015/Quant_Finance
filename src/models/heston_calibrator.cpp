#include <qf/models/heston_calibrator.hpp>
#include <qf/math/optimization.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <cmath>
#include <stdexcept>

namespace qf::models {

namespace {

using pricingengines::HestonParams;

// ── Parameter transforms ─────────────────────────────────────────────────────
// Unconstrained search vector y (size 5) <-> constrained HestonParams.
//   v0,kappa,theta,sigma > 0  via exp/log
//   rho in (-1,1)             via tanh/atanh

std::vector<double> toUnconstrained(const HestonParams& h)
{
    // Clamp rho strictly inside (-1,1) so atanh is finite.
    double rho = std::max(-0.999999, std::min(0.999999, h.rho));
    return {
        std::log(h.v0),
        std::log(h.kappa),
        std::log(h.theta),
        std::log(h.sigma),
        std::atanh(rho)
    };
}

HestonParams fromUnconstrained(const std::vector<double>& y)
{
    HestonParams h;
    h.v0    = std::exp(y[0]);
    h.kappa = std::exp(y[1]);
    h.theta = std::exp(y[2]);
    h.sigma = std::exp(y[3]);
    h.rho   = std::tanh(y[4]);
    return h;
}

// Safe BS implied vol: returns false if the price is un-invertible (e.g. below
// intrinsic / above the no-arb bound), where impliedVolatility's Brent bracket
// has no sign change and would throw.
bool tryImpliedVol(const instruments::OptionParams& base, double price, double& ivOut)
{
    try {
        ivOut = pricingengines::impliedVolatility(base, price);
        return true;
    } catch (...) {
        return false;
    }
}

} // namespace

HestonCalibrator::HestonCalibrator(double spot, double r, double q)
    : spot_(spot), r_(r), q_(q) {}

CalibrationResult HestonCalibrator::calibrate(
    const std::vector<OptionQuote>& quotes,
    const HestonParams& initialGuess,
    CalibrationObjective objective,
    bool vegaWeighted,
    double tol,
    int maxIt) const
{
    if (quotes.empty())
        throw std::invalid_argument("HestonCalibrator::calibrate: no quotes");

    const std::size_t n = quotes.size();

    // Build a reusable OptionParams template per quote.
    auto makeParams = [&](const OptionQuote& qte) {
        instruments::OptionParams p;
        p.spot          = spot_;
        p.strike        = qte.strike;
        p.riskFreeRate  = r_;
        p.dividendYield = q_;
        p.volatility    = 0.0;   // set per-use for BS helpers
        p.maturity      = qte.maturity;
        p.type          = qte.type;
        p.exercise      = instruments::ExerciseType::European;
        return p;
    };

    // Precompute, per quote: market IV (for IV objective) and vega weight.
    std::vector<double> marketIV(n, 0.0);
    std::vector<bool>   marketIVok(n, false);
    std::vector<double> weight(n, 1.0);

    for (std::size_t i = 0; i < n; ++i) {
        instruments::OptionParams p = makeParams(quotes[i]);
        double iv = 0.0;
        if (tryImpliedVol(p, quotes[i].marketPrice, iv)) {
            marketIV[i]   = iv;
            marketIVok[i] = true;
            if (vegaWeighted && objective == CalibrationObjective::Price) {
                // BS vega per unit vol at the market IV; blackScholes returns
                // vega per 1 pct-point (÷100), so multiply back by 100.
                instruments::OptionParams pv = p;
                pv.volatility = iv;
                double vega = pricingengines::blackScholes(pv).vega * 100.0;
                weight[i] = 1.0 / std::max(vega, 1e-4);
            }
        }
    }

    // Large-but-finite penalty steers the simplex away from un-priceable regions.
    constexpr double kPenalty = 1e6;

    auto objectiveFn = [&](const std::vector<double>& y) -> double {
        HestonParams h = fromUnconstrained(y);
        double sse = 0.0;
        for (std::size_t i = 0; i < n; ++i) {
            instruments::OptionParams p = makeParams(quotes[i]);
            double modelPrice;
            try {
                modelPrice = pricingengines::hestonPrice(p, h);
            } catch (...) {
                return kPenalty;   // should not happen given transforms
            }

            double err;
            if (objective == CalibrationObjective::ImpliedVol) {
                if (!marketIVok[i]) continue;   // un-invertible market quote: skip
                double modelIV = 0.0;
                if (!tryImpliedVol(p, modelPrice, modelIV)) {
                    sse += kPenalty;            // model price off the IV manifold
                    continue;
                }
                err = modelIV - marketIV[i];
            } else {
                err = (modelPrice - quotes[i].marketPrice) * weight[i];
            }
            sse += err * err;
        }
        return sse;
    };

    // ── Optimize in transformed space ────────────────────────────────────────
    std::vector<double> y0 = toUnconstrained(initialGuess);
    math::OptimResult opt = math::nelderMead(objectiveFn, y0, tol, maxIt);

    HestonParams fitted = fromUnconstrained(opt.x);

    // ── Assemble result: recompute unweighted per-quote errors + RMSE ─────────
    CalibrationResult result;
    result.params     = fitted;
    result.converged  = opt.converged;
    result.iterations = opt.iterations;
    result.perQuoteErrors.reserve(n);

    double weightedSSE = 0.0;
    std::size_t counted = 0;
    for (std::size_t i = 0; i < n; ++i) {
        instruments::OptionParams p = makeParams(quotes[i]);
        double modelPrice = pricingengines::hestonPrice(p, fitted);

        double rawErr;    // unweighted error, chosen space (for reporting)
        double wErr;      // weighted error, chosen space (for RMSE)
        if (objective == CalibrationObjective::ImpliedVol) {
            double modelIV = 0.0;
            if (marketIVok[i] && tryImpliedVol(p, modelPrice, modelIV)) {
                rawErr = modelIV - marketIV[i];
                wErr   = rawErr;
                ++counted;
                weightedSSE += wErr * wErr;
            } else {
                rawErr = std::nan("");   // undefined IV for this quote
            }
        } else {
            rawErr = modelPrice - quotes[i].marketPrice;
            wErr   = rawErr * weight[i];
            ++counted;
            weightedSSE += wErr * wErr;
        }
        result.perQuoteErrors.push_back(rawErr);
    }

    result.rmse = (counted > 0)
                ? std::sqrt(weightedSSE / static_cast<double>(counted))
                : 0.0;
    return result;
}

} // namespace qf::models
