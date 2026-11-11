#pragma once
#include <string>
#include <vector>
#include <qf/instruments/instrument.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/math/daycount.hpp>

namespace qf::instruments {

/// @brief Which leg the holder of an XccySwap pays.
enum class XccySide {
    PayUsd,   ///< Pays the USD leg (SOFR flat) and receives the MXN leg (TIIE-F + spread).
    PayMxn    ///< Pays the MXN leg (TIIE-F + spread) and receives the USD leg (SOFR flat).
};

/// @brief One row of an XccySwap cash-flow table: a coupon or a notional exchange of one leg.
struct XccyCashFlow {
    std::string leg;         ///< "USD" or "MXN".
    std::string kind;        ///< "coupon" or "exchange".
    int    payDays;          ///< Payment date, in calendar days from the valuation date.
    double accrual;          ///< Accrual fraction tau of the period under the swap's day-count (0 for exchanges).
    double amount;           ///< Undiscounted amount in the leg's currency, signed from the holder's side.
    double discountFactor;   ///< DF on the leg's discount curve.
    double presentValue;     ///< amount * discountFactor, in the leg's currency.
    double presentValueMxn;  ///< presentValue converted at the spot (USD leg: presentValue * spot; MXN leg: as is).
};

/// @brief Constant-notional cross-currency basis swap USD (SOFR flat) against MXN (TIIE-F + spread).
///
/// Both legs pay every period of the same day-based schedule (28 days in the market convention),
/// with an optional exchange of notionals at the start and at the end. The USD notional is
/// @c N_U and the MXN notional is fixed at inception as @c N_M = N_U * fxRate; it never resets to
/// market. Each floating coupon is the daily-compounded overnight rate priced by replication,
/// exactly as in OisSwap: period 1 is @c N * (accruedFactor * DF(max(startDays, 0)) / DF(e_1) - 1)
/// and later periods @c N * (DF(e_{i-1}) / DF(e_i) - 1); the MXN coupons add @c N_M * spread * tau_i.
/// The USD leg is projected and discounted on @c usdCurve. The MXN leg is projected on
/// @c mxnProjectionCurve and discounted on @c mxnDiscountCurve (the USD-collateral curve
/// "MXN-USD"), which is what makes the basis spread visible in the value.
///
/// The value is in MXN: @c npv = PV_MXN_leg - S * PV_USD_leg for PayUsd (S = spot of @c pair),
/// and its negative for PayMxn. Like OisSwap it can be valued mid-life: @c startDays may be
/// negative (the period in course already started, its fixings compounded into the accrued
/// factors) or lie in the future.
class XccySwap : public Instrument {
public:
    /// @param notionalUsd       USD notional N_U (> 0, finite).
    /// @param fxRate            MXN per USD fixed at inception (> 0); N_M = notionalUsd * fxRate.
    /// @param spread            Spread over the TIIE-F coupons (decimal, e.g. -0.0025 = -25 bp).
    /// @param startDays         Start of the first period in days from valuation (negative if already started).
    /// @param payDays           Remaining payment days, strictly increasing, all > 0, shared by both legs.
    /// @param accruedFactorUsd  Compounded SOFR factor of the elapsed days of period 1 (> 0); exactly 1 when @p startDays >= 0.
    /// @param accruedFactorMxn  Compounded TIIE-F factor of the elapsed days of period 1 (> 0); exactly 1 when @p startDays >= 0.
    /// @param side              PayUsd or PayMxn.
    /// @param initialExchange   Exchange the notionals at @p startDays (only when @p startDays >= 0; otherwise it already happened).
    /// @param finalExchange     Exchange the notionals back at the last payment.
    /// @param usdCurve          Curve key that projects and discounts the USD leg.
    /// @param mxnProjectionCurve  Curve key that projects the MXN floating coupons.
    /// @param mxnDiscountCurve  Curve key that discounts the MXN leg.
    /// @param pair              Spot key of MXN per USD in the MarketEnvironment.
    /// @param dcc               Accrual convention; ACT/360 (default), ACT/365 or ACT/ACT (not 30/360).
    /// @throws std::invalid_argument if a notional or the fx rate is not positive and finite, the spread is
    ///         not finite, @p payDays is empty, not strictly increasing or starts at <= 0, @p startDays >=
    ///         payDays[0], an accrued factor is <= 0 or differs from 1 with @p startDays >= 0, or @p dcc is THIRTY_360.
    XccySwap(double notionalUsd, double fxRate, double spread, int startDays, std::vector<int> payDays,
             double accruedFactorUsd, double accruedFactorMxn, XccySide side,
             bool initialExchange, bool finalExchange,
             std::string usdCurve = "SOFR", std::string mxnProjectionCurve = "TIIE-F",
             std::string mxnDiscountCurve = "MXN-USD", std::string pair = "USDMXN",
             math::DayCountConvention dcc = math::DayCountConvention::ACT_360);

    /// @brief Net present value in MXN from the holder's side: the sum of presentValueMxn of cashFlows().
    /// @param env  Market environment holding the three curves and the spot of @c pair.
    /// @return     NPV in MXN.
    double npv(const core::MarketEnvironment& env) const;

    /// @brief Routes Instrument::pv() to npv().
    double calculatePV(const core::MarketEnvironment& env) const override { return npv(env); }

    /// @brief Spread that makes npv() zero, all else equal. The value is linear in the spread, so it is
    ///        exact: spread - npv(PayUsd) / (N_M * sum(tau_i * DFd(e_i))).
    /// @param env  Market environment holding the three curves and the spot of @c pair.
    /// @return     Par spread (decimal), the same for both sides.
    double parSpread(const core::MarketEnvironment& env) const;

    /// @brief Cash-flow table of both legs, by payment day (USD rows before MXN rows on the same day).
    /// @param env  Market environment holding the three curves and the spot of @c pair.
    /// @return     Rows with the holder's sign; the sum of presentValueMxn equals npv().
    std::vector<XccyCashFlow> cashFlows(const core::MarketEnvironment& env) const;

    double      notionalUsd() const { return notionalUsd_; }
    double      notionalMxn() const { return notionalUsd_ * fxRate_; }   ///< N_U * fxRate.
    double      fxRate()      const { return fxRate_; }
    double      spread()      const { return spread_; }
    XccySide    side()        const { return side_; }
    const std::vector<int>& payDays() const { return payDays_; }

private:
    double                   notionalUsd_;
    double                   fxRate_;
    double                   spread_;
    int                      startDays_;
    std::vector<int>         payDays_;
    double                   accruedFactorUsd_;
    double                   accruedFactorMxn_;
    XccySide                 side_;
    bool                     initialExchange_;
    bool                     finalExchange_;
    std::string              usdCurve_;
    std::string              mxnProjectionCurve_;
    std::string              mxnDiscountCurve_;
    std::string              pair_;
    math::DayCountConvention dcc_;
};

} // namespace qf::instruments
