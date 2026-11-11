#include <qf/xva/exposure_profile.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/interpolation.hpp>
#include <algorithm>
#include <cmath>
#include <random>
#include <stdexcept>

namespace qf::xva {

std::vector<ExposurePoint> simulateExposure(const qf::models::IRateModel& model,
                                            const NettingSet& ns,
                                            const SimParams& params,
                                            double pfeQuantile)
{
    // Same SimParams checks as the CVACalculator constructor.
    const auto& dates = params.monitorDates;
    if (dates.empty())
        throw std::invalid_argument("simulateExposure: monitorDates must not be empty");
    if (params.nPaths == 0)
        throw std::invalid_argument("simulateExposure: nPaths must be > 0");
    if (dates.front() <= 0.0)
        throw std::invalid_argument("simulateExposure: all monitorDates must be positive");
    if (!std::is_sorted(dates.begin(), dates.end()))
        throw std::invalid_argument("simulateExposure: monitorDates must be sorted ascending");
    if (!(pfeQuantile > 0.0 && pfeQuantile < 1.0)) // also rejects NaN
        throw std::invalid_argument("simulateExposure: pfeQuantile must be in (0,1)");

    const std::size_t nDates = dates.size();
    const std::size_t nPaths = params.nPaths;
    const double T_max = dates.back();

    // The simulation below mirrors CVACalculator::compute step for step (grid, seeding,
    // conditional curve, interpolation) so both see identical trajectories.
    const int totalSteps = std::max(static_cast<int>(std::ceil(T_max * 252)), 10);
    const double dt = T_max / static_cast<double>(totalSteps);

    const std::vector<double> baseTenors =
        {1.0/12, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 30.0};

    std::vector<double> epeAccum(nDates, 0.0);
    std::vector<double> eneAccum(nDates, 0.0);
    // positive[k][p] = max(V,0) of path p at date k; stays 0 for degenerate paths.
    std::vector<std::vector<double>> positive(nDates, std::vector<double>(nPaths, 0.0));

    const unsigned seed = params.seed.has_value()
                        ? params.seed.value()
                        : static_cast<unsigned>(std::random_device{}());

    for (std::size_t p = 0; p < nPaths; ++p) {
        auto path = model.simulate(T_max, totalSteps, seed + static_cast<unsigned>(p));

        for (std::size_t k = 0; k < nDates; ++k) {
            const double t_k = dates[k];

            int idx = static_cast<int>(std::round(t_k / dt));
            idx = std::clamp(idx, 0, totalSteps);
            const double r_tk = path[static_cast<std::size_t>(idx)];

            std::vector<double> tenors, zeroRates;
            tenors.reserve(baseTenors.size());
            zeroRates.reserve(baseTenors.size());
            for (double tau : baseTenors) {
                const double P = model.conditionalBondPrice(t_k, t_k + tau, r_tk);
                if (P > 0.0 && P < 1.0) {
                    tenors.push_back(tau);
                    zeroRates.push_back(-std::log(P) / tau);
                }
            }
            if (tenors.size() < 2) continue; // degenerate path: V = 0

            qf::termstructure::YieldCurve simCurve(tenors, zeroRates,
                qf::math::InterpolationMethod::Linear);
            qf::core::MarketEnvironment simEnv(simCurve);

            const double netVal = ns.netValue(simEnv, t_k);
            const double pos = std::max(netVal, 0.0);
            epeAccum[k] += pos;
            eneAccum[k] += std::max(-netVal, 0.0);
            positive[k][p] = pos;
        }
    }

    // Quantile index: ceil(q * n) - 1, clamped to the sample range.
    const double scaled = std::round(pfeQuantile * static_cast<double>(nPaths) * 1e9) / 1e9;
    const long long rank = static_cast<long long>(std::ceil(scaled));
    const std::size_t qIdx = static_cast<std::size_t>(
        std::clamp<long long>(rank - 1, 0, static_cast<long long>(nPaths) - 1));

    std::vector<ExposurePoint> out(nDates);
    for (std::size_t k = 0; k < nDates; ++k) {
        std::sort(positive[k].begin(), positive[k].end());
        out[k] = {dates[k],
                  epeAccum[k] / static_cast<double>(nPaths),
                  eneAccum[k] / static_cast<double>(nPaths),
                  positive[k][qIdx]};
    }
    return out;
}

} // namespace qf::xva
