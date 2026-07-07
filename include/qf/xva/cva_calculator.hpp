#pragma once
#include <optional>
#include <vector>
#include <qf/models/irate_model.hpp>
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
    /// @param model   Interest rate model implementing IRateModel.
    /// @param credit  Counterparty credit curve.
    /// @param lgd     Loss Given Default in [0,1] (e.g. 0.6 = 40% recovery).
    /// @param params  Simulation parameters.
    CVACalculator(const qf::models::IRateModel& model,
                  const ICreditCurve& credit,
                  double lgd,
                  SimParams params);

    /// @brief Enable DVA by supplying the firm's own credit curve.
    ///
    /// Opt-in: when not called, @ref CVAResult::dva is 0 and @ref CVAResult::bcva
    /// equals @ref CVAResult::cva (backward-compatible unilateral behaviour).
    /// @param ownCredit  The firm's own survival curve (must outlive this calculator).
    /// @param ownLgd     Own Loss Given Default in [0,1].
    void setOwnCredit(const ICreditCurve& ownCredit, double ownLgd);

    /// @brief Enable FVA by supplying a scalar funding spread.
    ///
    /// Opt-in: when not called (or set to 0), @ref CVAResult::fva is 0.
    /// @param fundingSpread  Funding spread over risk-free, in decimal (e.g. 0.005 = 50 bps), >= 0.
    void setFundingSpread(double fundingSpread);

    /// @brief Run the exposure simulation over the netting set.
    ///
    /// Always computes CVA. Also computes DVA if an own-credit curve was set via
    /// @ref setOwnCredit, and FVA if a funding spread was set via @ref setFundingSpread.
    /// All adjustments are read off the same simulated paths.
    /// @param ns   Portfolio of swaps with the same counterparty.
    /// @param env  Initial market environment (used to seed the initial curve).
    CVAResult compute(const NettingSet& ns,
                      const qf::core::MarketEnvironment& env) const;

private:
    const qf::models::IRateModel& model_;
    const ICreditCurve& credit_;
    double lgd_;
    SimParams params_;
    const ICreditCurve* ownCredit_ = nullptr; ///< Own credit for DVA; null = DVA disabled.
    double ownLgd_ = 0.0;                      ///< Own LGD used when ownCredit_ is set.
    double fundingSpread_ = 0.0;               ///< Funding spread for FVA; 0 = FVA disabled.
};

} // namespace qf::xva
