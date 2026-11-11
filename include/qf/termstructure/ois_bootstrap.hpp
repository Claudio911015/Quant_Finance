#pragma once
#include <vector>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/daycount.hpp>
#include <qf/math/interpolation.hpp>

namespace qf::termstructure {

/// @brief One market quote for the OIS bootstrap, expressed in calendar days.
struct OisQuote {
    int    days;   ///< Days from valuation date to maturity (> 0).
    double rate;   ///< Simple deposit rate or par OIS fixed rate (decimal, e.g. 0.07 = 7%).
    enum Type { Deposit, Ois } type; ///< Deposit: single-period simple rate. Ois: par swap rate.
};

/// @brief Payment schedule (in days from today) of an OIS paying every @p periodDays.
///
/// Payments fall at k*periodDays (k = 1, 2, ...) and @p maturityDays is always
/// the last one; if it is not a multiple of @p periodDays the final period is short.
///
/// @param maturityDays  Days to maturity (> 0).
/// @param periodDays    Days between coupons (> 0).
/// @return              Strictly increasing payment days; the last element is @p maturityDays.
/// @throws std::invalid_argument if @p maturityDays <= 0 or @p periodDays <= 0.
std::vector<int> oisPaymentDays(int maturityDays, int periodDays);

/// @brief Bootstrap a zero curve from money-market deposits and par OIS swaps.
///
/// Unlike bootstrap(), time and accrual are decoupled: pillar time is
/// t = days/365 and zero rates are continuously compounded, while coupons accrue
/// by actual days under @p accrualDcc (ACT/360 by default).
///
/// - Deposit: DF = 1 / (1 + r * tau), tau = accrual fraction of `days`.
/// - OIS: par equation  R * sum_i tau_i * DF(t_i) = 1 - DF(T)  over the payment
///   schedule oisPaymentDays(days, periodDays). Intermediate DFs come from the
///   curve being built (including the new pillar); the new pillar's zero rate is
///   solved with Brent (tolerance 1e-14).
///
/// Every quote reprices exactly when @p method is local (Linear, LogLinear);
/// with CubicSpline a later pillar can move earlier segments, so earlier quotes
/// reprice only approximately.
///
/// @param quotes       Quotes sorted by strictly increasing `days`, all > 0.
/// @param periodDays   OIS coupon period in days (> 0).
/// @param accrualDcc   Day-count convention for accrual periods (default ACT/360).
/// @param method       Interpolation of the zero rate between pillars (default Linear).
/// @return             YieldCurve with one pillar per quote at t = days/365.
/// @throws std::invalid_argument if @p quotes is empty, has fewer than two entries
///         (a YieldCurve needs two pillars), `days` is not strictly increasing and
///         positive, or @p periodDays <= 0.
/// @throws std::runtime_error    if a pillar cannot be solved (non-positive DF or no root in the search range).
YieldCurve bootstrapOis(const std::vector<OisQuote>& quotes, int periodDays,
                        math::DayCountConvention accrualDcc = math::DayCountConvention::ACT_360,
                        math::InterpolationMethod method = math::InterpolationMethod::Linear);

} // namespace qf::termstructure
