#pragma once
#include <vector>

namespace qf::xva {

/// @brief Per-date contribution to CVA.
struct TimeStep {
    double t;            ///< Monitor date in years.
    double epe;          ///< Expected Positive Exposure E[max(V,0)] at t.
    double survProb;     ///< Survival probability SP(t).
    double contribution; ///< LGD * EPE(t) * [SP(t-1) - SP(t)].
};

/// @brief Output of CVACalculator::compute().
struct CVAResult {
    double cva;                    ///< Total CVA scalar (sum of contributions).
    std::vector<TimeStep> profile; ///< Per-date breakdown.
};

} // namespace qf::xva
