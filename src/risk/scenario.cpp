#include <qf/risk/scenario.hpp>

#include <stdexcept>
#include <utility>

#include <qf/termstructure/yieldcurve.hpp>

namespace qf::risk {

ScenarioEngine::ScenarioEngine(std::string curveName, double bumpSizeBp)
    : curveName_(std::move(curveName)), bumpSizeBp_(bumpSizeBp)
{
    if (bumpSizeBp_ <= 0.0)
        throw std::invalid_argument("ScenarioEngine: bumpSizeBp must be positive");
}

namespace {

/// Price @p inst against a *copy* of @p env whose target curve has been replaced by
/// @p bumpedCurve. The copy's observers are detached first so that swapping the curve
/// never fires phantom onMarketChange notifications into live Observer-subscribed
/// instruments (the engine must not perturb the live book while measuring risk).
double priceWithCurve(const instruments::Instrument& inst,
                      const core::MarketEnvironment& env,
                      const std::string& curveName,
                      const termstructure::YieldCurve& bumpedCurve)
{
    core::MarketEnvironment scenarioEnv = env;   // copies curves/spots/vols (+ weak_ptr observers)
    scenarioEnv.unsubscribeAll();                // detach so the bump stays private to this run
    scenarioEnv.addCurve(curveName, bumpedCurve);
    return inst.pv(scenarioEnv);
}

} // namespace

double ScenarioEngine::parallelDV01(const instruments::Instrument& inst,
                                    const core::MarketEnvironment& env) const
{
    const auto& base = env.curve(curveName_);
    const double up   = priceWithCurve(inst, env, curveName_, base.parallelBump(+bumpSizeBp_));
    const double down = priceWithCurve(inst, env, curveName_, base.parallelBump(-bumpSizeBp_));
    // Central difference, normalised to the dollar value of a single 1 bp move.
    // Sign: positive when PV rises as rates fall (matches qf::risk::dv01()).
    return (down - up) / (2.0 * bumpSizeBp_);
}

std::vector<KeyRateDV01>
ScenarioEngine::keyRateDV01s(const instruments::Instrument& inst,
                             const core::MarketEnvironment& env) const
{
    const auto& base = env.curve(curveName_);
    const auto& mats = base.maturities();

    std::vector<KeyRateDV01> ladder;
    ladder.reserve(mats.size());
    for (std::size_t k = 0; k < mats.size(); ++k) {
        const double up   = priceWithCurve(inst, env, curveName_, base.bumped(k, +bumpSizeBp_));
        const double down = priceWithCurve(inst, env, curveName_, base.bumped(k, -bumpSizeBp_));
        ladder.push_back({mats[k], (down - up) / (2.0 * bumpSizeBp_)});
    }
    return ladder;
}

ScenarioResult
ScenarioEngine::runScenario(const instruments::Instrument& inst,
                            const core::MarketEnvironment& env,
                            const std::vector<double>& perPillarShiftsBp,
                            const std::string& label) const
{
    const auto& base = env.curve(curveName_);
    const auto& rates = base.rates();
    if (perPillarShiftsBp.size() != rates.size())
        throw std::invalid_argument(
            "ScenarioEngine::runScenario: shift vector size must equal the pillar count");

    // Build the shocked curve: rate_k += shift_k (bp) * 1e-4, method preserved.
    std::vector<double> shocked = rates;
    for (std::size_t k = 0; k < shocked.size(); ++k)
        shocked[k] += perPillarShiftsBp[k] * 1e-4;
    termstructure::YieldCurve shockedCurve(base.maturities(), std::move(shocked),
                                           base.interpolationMethod());

    const double basePV     = inst.pv(env);
    const double scenarioPV = priceWithCurve(inst, env, curveName_, shockedCurve);
    return ScenarioResult{label, basePV, scenarioPV, scenarioPV - basePV};
}

ScenarioResult
ScenarioEngine::parallelShock(const instruments::Instrument& inst,
                              const core::MarketEnvironment& env,
                              double magnitudeBp) const
{
    const auto& base = env.curve(curveName_);
    std::vector<double> shifts(base.rates().size(), magnitudeBp);
    return runScenario(inst, env, shifts, "parallel_shock");
}

namespace {

/// Linear ramp of per-pillar shifts from @p first (short end) to @p last (long end).
/// With a single pillar the ramp degenerates to that pillar's start value.
std::vector<double> rampShifts(std::size_t n, double first, double last)
{
    std::vector<double> shifts(n, first);
    if (n <= 1)
        return shifts;
    for (std::size_t k = 0; k < n; ++k) {
        const double w = static_cast<double>(k) / static_cast<double>(n - 1);
        shifts[k] = first + (last - first) * w;
    }
    return shifts;
}

} // namespace

ScenarioResult
ScenarioEngine::steepener(const instruments::Instrument& inst,
                          const core::MarketEnvironment& env,
                          double magnitudeBp) const
{
    const auto& base = env.curve(curveName_);
    // Short end down, long end up → curve steepens.
    auto shifts = rampShifts(base.rates().size(), -magnitudeBp, +magnitudeBp);
    return runScenario(inst, env, shifts, "steepener");
}

ScenarioResult
ScenarioEngine::flattener(const instruments::Instrument& inst,
                          const core::MarketEnvironment& env,
                          double magnitudeBp) const
{
    const auto& base = env.curve(curveName_);
    // Short end up, long end down → curve flattens.
    auto shifts = rampShifts(base.rates().size(), +magnitudeBp, -magnitudeBp);
    return runScenario(inst, env, shifts, "flattener");
}

} // namespace qf::risk
