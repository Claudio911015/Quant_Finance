#pragma once
#include <optional>
#include <vector>
#include <qf/models/hullwhite.hpp>
#include <qf/xva/credit_curve.hpp>
#include <qf/xva/netting_set.hpp>
#include <qf/xva/cva_result.hpp>
#include <qf/core/market_environment.hpp>

namespace qf::xva {

struct SimParams {
    std::size_t nPaths;                  ///< Number of Monte Carlo paths.
    std::vector<double> monitorDates;    ///< Observation times in years (sorted, all > 0).
    std::optional<unsigned int> seed;    ///< RNG seed; random if absent.
};

class CVACalculator {
public:
    /// @brief Construct the CVA engine.
    /// @param hw      Hull-White model (calibrated to the initial yield curve).
    /// @param credit  Counterparty credit curve.
    /// @param lgd     Loss Given Default in [0,1] (e.g. 0.6 = 40% recovery).
    /// @param params  Simulation parameters.
    CVACalculator(const qf::models::HullWhite& hw,
                  const ICreditCurve& credit,
                  double lgd,
                  SimParams params);

    /// @brief Run the CVA simulation over the netting set.
    /// @param ns   Portfolio of swaps with the same counterparty.
    /// @param env  Initial market environment (used to seed the initial curve).
    CVAResult compute(const NettingSet& ns,
                      const qf::core::MarketEnvironment& env) const;

private:
    const qf::models::HullWhite& hw_;
    const ICreditCurve& credit_;
    double lgd_;
    SimParams params_;
};

} // namespace qf::xva
