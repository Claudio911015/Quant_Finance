#pragma once
#include <string>
#include <vector>
#include <qf/instruments/instrument.hpp>
#include <qf/instruments/swap.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/math/daycount.hpp>

namespace qf::instruments {

/// @brief One row of an OIS swap cash-flow table (amounts are undiscounted unless noted).
struct OisCashFlow {
    int    payDays;          ///< Payment date, in calendar days from today.
    double payTime;          ///< Payment time in years, payDays / 365.
    double accrual;          ///< Accrual fraction tau of the period under the swap's day-count.
    double fixedAmount;      ///< Fixed coupon N * K * tau.
    double floatAmount;      ///< Compounded floating coupon N * (DF(t_prev) / DF(t) - 1).
    double netAmount;        ///< Float - fixed for a Payer, fixed - float for a Receiver.
    double discountFactor;   ///< DF(payTime) on the swap's curve.
    double presentValue;     ///< netAmount * discountFactor.
};

/// @brief Overnight-index swap (TIIE de Fondeo 28-day, SOFR annual) with a day-based schedule.
///
/// The floating leg is the daily-compounded overnight rate, priced by replication:
/// each coupon is N * (DF(t_{i-1}) / DF(t_i) - 1) with t_0 = 0, so the floating
/// leg's PV telescopes to N * (1 - DF(T)). Fixed coupons accrue N * K * tau_i with
/// tau_i from the actual days of the period under the day-count convention. Payment
/// dates come from termstructure::oisPaymentDays and times are t = days / 365, the
/// same conventions as termstructure::bootstrapOis, so a swap struck at a bootstrapped
/// quote prices to zero on the bootstrapped curve. Discounting and projection use the
/// single curve stored under @c curveKey.
class OisSwap : public Instrument {
public:
    /// @param notional      Notional principal (> 0).
    /// @param fixedRate     Fixed rate (decimal, e.g. 0.07 = 7 %).
    /// @param maturityDays  Days from today to the last payment (> 0).
    /// @param periodDays    Days between coupons (> 0): 28 for TIIE-F, 365 for SOFR.
    /// @param type          Payer (pays fixed, receives floating) or Receiver.
    /// @param curveKey      Name of the curve in the MarketEnvironment used to project and discount.
    /// @param dcc           Accrual convention; ACT/360 (default), ACT/365 or ACT/ACT (not 30/360).
    /// @throws std::invalid_argument if notional, maturityDays or periodDays is not positive,
    ///         or @p dcc is THIRTY_360 (it needs calendar dates, which this swap does not carry).
    OisSwap(double notional, double fixedRate, int maturityDays, int periodDays, SwapType type,
            std::string curveKey,
            math::DayCountConvention dcc = math::DayCountConvention::ACT_360);

    /// @brief Net present value: the sum of the presentValue column of cashFlows().
    /// @param env  Market environment holding the curve @c curveKey().
    /// @return     NPV in the curve's currency, from the holder's side (Payer or Receiver).
    double npv(const core::MarketEnvironment& env) const;

    /// @brief Routes Instrument::pv() to npv() so the swap flows through ScenarioEngine.
    double calculatePV(const core::MarketEnvironment& env) const override { return npv(env); }

    /// @brief Fixed rate that makes npv() zero: (1 - DF(T)) / sum(tau_i * DF(t_i)).
    /// @param env  Market environment holding the curve @c curveKey().
    /// @return     Par rate (decimal).
    double parRate(const core::MarketEnvironment& env) const;

    /// @brief Annuity sum(N * tau_i * DF(t_i)): PV of receiving 1.0 of fixed rate per year.
    /// @param env  Market environment holding the curve @c curveKey().
    /// @return     Annuity in currency units.
    double annuity(const core::MarketEnvironment& env) const;

    /// @brief Full cash-flow table, one row per period.
    /// @param env  Market environment holding the curve @c curveKey().
    /// @return     Rows in payment order; the sum of presentValue equals npv().
    std::vector<OisCashFlow> cashFlows(const core::MarketEnvironment& env) const;

    double      notional()     const { return notional_; }
    double      fixedRate()    const { return fixedRate_; }
    int         maturityDays() const { return maturityDays_; }
    int         periodDays()   const { return periodDays_; }
    SwapType    type()         const { return type_; }
    const std::string& curveKey() const { return curveKey_; }

private:
    double                   notional_;
    double                   fixedRate_;
    int                      maturityDays_;
    int                      periodDays_;
    SwapType                 type_;
    std::string              curveKey_;
    math::DayCountConvention dcc_;
};

} // namespace qf::instruments
