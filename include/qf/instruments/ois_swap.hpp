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
    double discountFactor;   ///< DF(payTime) on the swap's discount curve.
    double presentValue;     ///< netAmount * discountFactor.
};

/// @brief Accrual factor of a daily-compounded overnight rate: product of (1 + r_i * d_i / dayBase).
///
/// @param rates    Overnight rates (decimal), one per fixing.
/// @param days     Days each rate applies for (> 0), same length as @p rates.
/// @param dayBase  Day-count base of the rates (> 0); 360 for ACT/360 (default).
/// @return         The compounded factor; 1 when there are no fixings.
/// @throws std::invalid_argument if the sizes differ, any day is not positive, @p dayBase is not
///         positive, or any single factor (1 + r_i * d_i / dayBase) is not positive.
double compoundOvernight(const std::vector<double>& rates, const std::vector<int>& days,
                         double dayBase = 360.0);

/// @brief Overnight-index swap (TIIE de Fondeo 28-day, SOFR annual) with a day-based schedule.
///
/// The floating leg is the daily-compounded overnight rate, priced by replication:
/// each coupon is N * (DF(t_{i-1}) / DF(t_i) - 1) with t_0 = 0, so the floating
/// leg's PV telescopes to N * (1 - DF(T)). Fixed coupons accrue N * K * tau_i with
/// tau_i from the actual days of the period under the day-count convention. Payment
/// dates come from termstructure::oisPaymentDays and times are t = days / 365, the
/// same conventions as termstructure::bootstrapOis, so a swap struck at a bootstrapped
/// quote prices to zero on the bootstrapped curve. By default discounting and projection use
/// the single curve stored under @c curveKey; an optional @c discountCurveKey discounts every
/// cash flow on another curve while the floating coupons are still projected on @c curveKey
/// (collateralised discounting).
///
/// A swap can also be valued mid-life or before it starts (second constructor): days are
/// then relative to the valuation date, the current period may have started in the past
/// (its fixings already compounded into an accrued factor) or lie in the future.
class OisSwap : public Instrument {
public:
    /// @param notional      Notional principal (> 0).
    /// @param fixedRate     Fixed rate (decimal, e.g. 0.07 = 7 %).
    /// @param maturityDays  Days from today to the last payment (> 0).
    /// @param periodDays    Days between coupons (> 0): 28 for TIIE-F, 365 for SOFR.
    /// @param type          Payer (pays fixed, receives floating) or Receiver.
    /// @param curveKey      Name of the curve in the MarketEnvironment used to project the floating
    ///                      coupons (and to discount them unless @p discountCurveKey is given).
    /// @param dcc           Accrual convention; ACT/360 (default), ACT/365 or ACT/ACT (not 30/360).
    /// @param discountCurveKey  Name of the curve that discounts every cash flow; empty (default)
    ///                      or equal to @p curveKey means the same curve as the projection.
    /// @throws std::invalid_argument if notional, maturityDays or periodDays is not positive,
    ///         or @p dcc is THIRTY_360 (it needs calendar dates, which this swap does not carry).
    OisSwap(double notional, double fixedRate, int maturityDays, int periodDays, SwapType type,
            std::string curveKey,
            math::DayCountConvention dcc = math::DayCountConvention::ACT_360,
            std::string discountCurveKey = "");

    /// @brief Swap valued on a date other than its start: current period already running
    ///        (@p startDays < 0, fixings compounded into @p accruedFactor) or starting later.
    ///
    /// Days are relative to the valuation date. Period 1 runs from @p startDays to
    /// @p payDays[0] with accrual tau = yearFraction(payDays[0] - startDays, dcc) and floating
    /// coupon N * (accruedFactor * DF(max(startDays, 0)) / DF(payDays[0]) - 1); later periods
    /// are the replication coupons of the first constructor.
    ///
    /// @param notional       Notional principal (> 0).
    /// @param fixedRate      Fixed rate (decimal).
    /// @param startDays      Start of the first period in days from valuation (negative if already started).
    /// @param payDays        Remaining payment days, strictly increasing, all > 0.
    /// @param accruedFactor  Compounded overnight factor of the days of period 1 already elapsed (> 0);
    ///                       must be exactly 1 when @p startDays >= 0.
    /// @param type           Payer (pays fixed, receives floating) or Receiver.
    /// @param curveKey       Name of the curve in the MarketEnvironment used to project the floating
    ///                       coupons (and to discount them unless @p discountCurveKey is given).
    /// @param dcc            Accrual convention; ACT/360 (default), ACT/365 or ACT/ACT (not 30/360).
    /// @param discountCurveKey  Name of the curve that discounts every cash flow; empty (default)
    ///                       or equal to @p curveKey means the same curve as the projection.
    /// @throws std::invalid_argument if notional <= 0, @p payDays is empty, not strictly increasing
    ///         or starts at <= 0, @p startDays >= payDays[0], @p accruedFactor <= 0, @p accruedFactor != 1
    ///         with @p startDays >= 0, or @p dcc is THIRTY_360.
    OisSwap(double notional, double fixedRate, int startDays, std::vector<int> payDays,
            double accruedFactor, SwapType type, std::string curveKey,
            math::DayCountConvention dcc = math::DayCountConvention::ACT_360,
            std::string discountCurveKey = "");

    /// @brief Net present value: the sum of the presentValue column of cashFlows().
    /// @param env  Market environment holding the curves @c curveKey() and @c discountCurveKey().
    /// @return     NPV in the curve's currency, from the holder's side (Payer or Receiver).
    double npv(const core::MarketEnvironment& env) const;

    /// @brief Routes Instrument::pv() to npv() so the swap flows through ScenarioEngine.
    double calculatePV(const core::MarketEnvironment& env) const override { return npv(env); }

    /// @brief Fixed rate that makes npv() zero: sum(floatAmount_i * DF(t_i)) / annuity.
    ///        For a swap starting today this is N * (1 - DF(T)) / annuity.
    /// @param env  Market environment holding the curves @c curveKey() and @c discountCurveKey().
    /// @return     Par rate (decimal).
    double parRate(const core::MarketEnvironment& env) const;

    /// @brief Annuity sum(N * tau_i * DF(t_i)): PV of receiving 1.0 of fixed rate per year.
    /// @param env  Market environment holding the curve @c discountCurveKey().
    /// @return     Annuity in currency units.
    double annuity(const core::MarketEnvironment& env) const;

    /// @brief Full cash-flow table, one row per period.
    /// @param env  Market environment holding the curves @c curveKey() and @c discountCurveKey().
    /// @return     Rows in payment order; the sum of presentValue equals npv().
    std::vector<OisCashFlow> cashFlows(const core::MarketEnvironment& env) const;

    double      notional()     const { return notional_; }
    double      fixedRate()    const { return fixedRate_; }
    int         maturityDays() const { return maturityDays_; }   ///< Last payment day.
    int         periodDays()   const { return periodDays_; }     ///< Coupon period; for the second constructor, the length of period 1.
    SwapType    type()         const { return type_; }
    const std::string& curveKey() const { return curveKey_; }   ///< Projection curve.
    /// @brief Effective discount curve key: the one given, or curveKey() when none was given.
    const std::string& discountCurveKey() const { return discountCurveKey_.empty() ? curveKey_ : discountCurveKey_; }

private:
    double                   notional_;
    double                   fixedRate_;
    int                      maturityDays_ = 0;
    int                      periodDays_   = 0;
    SwapType                 type_;
    std::string              curveKey_;
    std::string              discountCurveKey_;   // empty = same as curveKey_
    math::DayCountConvention dcc_;
    int                      startDays_;
    std::vector<int>         payDays_;
    double                   accruedFactor_;
};

} // namespace qf::instruments
