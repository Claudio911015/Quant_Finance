#pragma once
#include <vector>

namespace qf::xva {

/// @brief Per-date contribution to the bilateral valuation adjustment.
struct TimeStep {
    double t;               ///< Monitor date in years.
    double epe;             ///< Expected Positive Exposure E[max(V,0)] at t.
    double ene;             ///< Expected Negative Exposure E[max(-V,0)] at t.
    double survProb;        ///< Counterparty survival probability SP_c(t).
    double ownSurvProb;     ///< Own survival probability SP_o(t) (1.0 if no own curve).
    double contribution;    ///< CVA contribution: LGD_c * EPE(t) * [SP_c(t-1) - SP_c(t)].
    double dvaContribution; ///< DVA contribution: LGD_o * ENE(t) * [SP_o(t-1) - SP_o(t)].
    double fvaContribution; ///< FVA contribution: s_f * [EPE-ENE](t) * SP_c(t)*SP_o(t) * dt.
};

/// @brief Output of CVACalculator::compute().
///
/// Always carries a valid unilateral @ref cva. @ref dva and @ref fva are non-zero
/// only when an own-credit curve / funding spread were configured on the calculator;
/// otherwise they are 0 and @ref bcva equals @ref cva (backward-compatible behaviour).
struct CVAResult {
    double cva;                    ///< Unilateral CVA (cost to the firm), sum of contributions.
    double dva;                    ///< Debit Valuation Adjustment (benefit), sum of DVA contributions.
    double fva;                    ///< Funding Valuation Adjustment, sum of FVA contributions.
    double bcva;                   ///< Bilateral CVA to the firm = cva - dva.
    std::vector<TimeStep> profile; ///< Per-date breakdown.
};

} // namespace qf::xva
