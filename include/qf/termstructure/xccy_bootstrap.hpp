#pragma once
#include <vector>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/daycount.hpp>
#include <qf/math/interpolation.hpp>

namespace qf::termstructure {

/// @brief One USDMXN forward-points quote for the MXN-USD discount bootstrap.
struct FxForwardQuote {
    int    days;     ///< Days from valuation date to delivery (> 0).
    double points;   ///< Forward points in MXN per USD: the outright forward is F = spot + points.
};

/// @brief One cross-currency basis quote (constant-notional USD SOFR flat vs MXN TIIE-F + spread).
struct XccyBasisQuote {
    int    days;     ///< Days from valuation date to maturity (> 0).
    double spread;   ///< Par spread over the TIIE-F coupons (decimal, e.g. -0.0010 = -10 bp).
};

/// @brief Bootstrap the MXN discount curve under USD collateral ("MXN-USD") from FX forwards and
///        cross-currency basis swaps.
///
/// One pillar per quote, at t = days/365, with continuously compounded zero rates, in the order
/// forwards first and basis after:
///
/// - Forward pillar (short end): covered-interest parity solved for the MXN discount factor,
///   DF = S * DFu(t) / (S + points), with DFu the USD discount curve.
/// - Basis pillar (long end): the zero rate of the new pillar is solved with Brent (tolerance
///   1e-14) so that a constant-notional XccySwap (PayUsd, N_U = 1, fxRate = spot, the quoted
///   spread, startDays = 0, payment days oisPaymentDays(days, periodDays), both notional
///   exchanges) is worth zero. The swap is valued with the USD curve for the USD leg (projection
///   and discount), the MXN projection curve for the floating MXN coupons and the curve under
///   construction (including the new pillar) as MXN discount curve.
///
/// With zero points on parity and a zero basis the result equals the MXN projection curve; a
/// negative basis lifts the MXN discount factors above it. Every quote reprices exactly with
/// Linear (a local method); with CubicSpline a later pillar can move earlier segments, so earlier
/// quotes reprice only approximately. LogLinear is not usable: Interpolator applies it to the log
/// of the zero rate, which is NaN for non-positive rates, and the solve fails with
/// std::runtime_error.
///
/// @param forwards       Forward quotes sorted by strictly increasing `days`, all > 0 (may be empty).
/// @param basis          Basis quotes sorted by strictly increasing `days`, all > 0 (may be empty); the
///                       first one must lie strictly after the last forward.
/// @param spot           USDMXN spot, MXN per USD (> 0).
/// @param usdDiscount    USD discount (and projection) curve, e.g. the SOFR bootstrap.
/// @param mxnProjection  MXN projection curve of the floating TIIE-F coupons.
/// @param periodDays     Coupon period of the basis swap in days (> 0, 28 in the market convention).
/// @param accrualDcc     Day-count convention of the coupon accruals (default ACT/360).
/// @param method         Interpolation of the zero rate between pillars: Linear (default) or CubicSpline.
/// @return               YieldCurve with one pillar per quote, forwards then basis.
/// @throws std::invalid_argument if forwards and basis together have fewer than two quotes, `days`
///         is not strictly increasing and positive within each list, the first basis `days` is not
///         after the last forward `days`, @p spot is not positive and finite, a quoted spread is not
///         finite, spot + points is not positive and finite, or @p periodDays <= 0.
/// @throws std::runtime_error    if a pillar cannot be solved (non-positive discount factor or no
///         root in the search range).
YieldCurve bootstrapXccyDiscount(const std::vector<FxForwardQuote>& forwards,
                                 const std::vector<XccyBasisQuote>& basis,
                                 double spot, const YieldCurve& usdDiscount, const YieldCurve& mxnProjection,
                                 int periodDays = 28,
                                 math::DayCountConvention accrualDcc = math::DayCountConvention::ACT_360,
                                 math::InterpolationMethod method = math::InterpolationMethod::Linear);

} // namespace qf::termstructure
