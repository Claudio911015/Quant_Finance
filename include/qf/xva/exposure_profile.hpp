#pragma once
#include <vector>
#include <qf/models/irate_model.hpp>
#include <qf/xva/cva_calculator.hpp>
#include <qf/xva/netting_set.hpp>

namespace qf::xva {

/// @brief Exposure statistics of a netting set at one monitor date.
struct ExposurePoint {
    double t;   ///< Monitor date in years.
    double epe; ///< Expected Positive Exposure E[max(V,0)].
    double ene; ///< Expected Negative Exposure E[max(-V,0)].
    double pfe; ///< Potential Future Exposure: empirical quantile of max(V,0).
};

/// @brief Simulate the exposure profile (EPE, ENE, PFE) of a netting set.
///
/// Values the netting set on the SAME paths as @ref CVACalculator::compute: grid of
/// max(ceil(T_max * 252), 10) steps, path p seeded with `seed + p`, conditional
/// Hull-White curve rebuilt at the same tenors and interpolated Linear. Degenerate
/// paths (fewer than two usable tenors) count as V = 0. Hence `epe` and `ene` equal the
/// `CVACalculator` profile for the same inputs, and `pfe` is read off those paths.
///
/// `pfe` is the empirical quantile of max(V,0): samples sorted ascending, element at
/// index ceil(q * n) - 1 (the product is rounded to 9 decimals before `ceil` so that
/// floating-point noise such as 0.07 * 100 = 7.000000000000001 does not shift the index).
///
/// @param model        Rate model that simulates the short rate (e.g. HullWhite).
/// @param ns           Netting set to revalue at each monitor date.
/// @param params       Simulation parameters (same validation as CVACalculator).
/// @param pfeQuantile  Quantile in (0,1) for the PFE (default 0.95).
/// @throws std::invalid_argument if `params.monitorDates` is empty, not strictly
///         positive at the start, or unsorted; if `params.nPaths` is 0; or if
///         `pfeQuantile` is not in (0,1).
std::vector<ExposurePoint> simulateExposure(const qf::models::IRateModel& model,
                                            const NettingSet& ns,
                                            const SimParams& params,
                                            double pfeQuantile = 0.95);

} // namespace qf::xva
