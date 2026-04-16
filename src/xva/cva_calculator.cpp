#include <qf/xva/cva_calculator.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/interpolation.hpp>
#include <algorithm>
#include <cmath>
#include <random>
#include <stdexcept>

namespace qf::xva {

CVACalculator::CVACalculator(const qf::models::HullWhite& hw,
                             const ICreditCurve& credit,
                             double lgd,
                             SimParams params)
    : hw_(hw), credit_(credit), lgd_(lgd), params_(std::move(params))
{
    if (lgd < 0.0 || lgd > 1.0)
        throw std::invalid_argument("CVACalculator: LGD must be in [0,1]");
    if (params_.monitorDates.empty())
        throw std::invalid_argument("CVACalculator: monitorDates must not be empty");
    if (params_.nPaths == 0)
        throw std::invalid_argument("CVACalculator: nPaths must be > 0");
    if (params_.monitorDates.front() <= 0.0)
        throw std::invalid_argument("CVACalculator: all monitorDates must be positive");
    if (!std::is_sorted(params_.monitorDates.begin(), params_.monitorDates.end()))
        throw std::invalid_argument("CVACalculator: monitorDates must be sorted ascending");
}

CVAResult CVACalculator::compute(const NettingSet& ns,
                                  const qf::core::MarketEnvironment&) const
{
    const auto& dates = params_.monitorDates;
    const std::size_t nDates = dates.size();
    double T_max = dates.back();

    // Simulate on a grid fine enough to cover all monitor dates (~daily)
    int totalSteps = std::max(static_cast<int>(std::ceil(T_max * 252)), 10);
    double dt = T_max / static_cast<double>(totalSteps);

    // Tenors used to rebuild the conditional yield curve at each simulation node
    const std::vector<double> baseTenors =
        {1.0/12, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 30.0};

    // Accumulate EPE per monitor date across paths
    std::vector<double> epeAccum(nDates, 0.0);

    unsigned seed = params_.seed.has_value()
                  ? params_.seed.value()
                  : static_cast<unsigned>(std::random_device{}());

    for (std::size_t p = 0; p < params_.nPaths; ++p) {
        // Simulate one HW short-rate path over [0, T_max]; returns steps+1 values
        auto path = hw_.simulate(T_max, totalSteps, seed + static_cast<unsigned>(p));

        for (std::size_t k = 0; k < nDates; ++k) {
            double t_k = dates[k];

            // Map t_k to the nearest grid index in [0, totalSteps]
            int idx = static_cast<int>(std::round(t_k / dt));
            idx = std::clamp(idx, 0, totalSteps);
            double r_tk = path[static_cast<std::size_t>(idx)];

            // Build conditional zero rates from Hull-White bond prices P(t_k, t_k+tau | r_tk)
            std::vector<double> tenors, zeroRates;
            tenors.reserve(baseTenors.size());
            zeroRates.reserve(baseTenors.size());
            for (double tau : baseTenors) {
                double P = hw_.conditionalBondPrice(t_k, t_k + tau, r_tk);
                if (P > 0.0 && P < 1.0) {
                    tenors.push_back(tau);
                    zeroRates.push_back(-std::log(P) / tau);
                }
            }
            if (tenors.size() < 2) continue; // degenerate path — skip

            // Use Linear interpolation: safer with few knots than CubicSpline
            qf::termstructure::YieldCurve simCurve(tenors, zeroRates,
                qf::math::InterpolationMethod::Linear);

            qf::core::MarketEnvironment simEnv(simCurve);

            double netVal = ns.netValue(simEnv, t_k);
            epeAccum[k] += std::max(netVal, 0.0);
        }
    }

    // Assemble CVAResult
    CVAResult result;
    result.profile.resize(nDates);
    result.cva = 0.0;
    double sp_prev = 1.0;

    for (std::size_t k = 0; k < nDates; ++k) {
        double epe     = epeAccum[k] / static_cast<double>(params_.nPaths);
        double sp      = credit_.survivalProbability(dates[k]);
        double contrib = lgd_ * epe * (sp_prev - sp);
        result.profile[k] = {dates[k], epe, sp, contrib};
        result.cva += contrib;
        sp_prev = sp;
    }

    return result;
}

} // namespace qf::xva
