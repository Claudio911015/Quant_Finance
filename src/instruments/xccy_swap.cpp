#include <qf/instruments/xccy_swap.hpp>
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <utility>

namespace qf::instruments {

namespace {

constexpr double kDaysPerYear = 365.0;   // payment time t = days / 365, as in OisSwap

// One coupon period: payment day, the day it starts (negative if it began before the valuation
// date) and its accrual fraction under the swap's day-count (same as OisSwap's schedule).
struct Period {
    int    day;
    int    prevDay;
    double tau;
};

std::vector<Period> buildPeriods(int startDays, const std::vector<int>& payDays,
                                 math::DayCountConvention dcc)
{
    std::vector<Period> periods;
    int prev = startDays;
    for (int d : payDays) {
        periods.push_back({d, prev, math::yearFraction(d - prev, dcc)});
        prev = d;
    }
    return periods;
}

// DF at a day; the valuation date has DF = 1 and a period that began earlier is projected from it.
double discountAt(const termstructure::YieldCurve& curve, int day)
{
    return day <= 0 ? 1.0 : curve.discountFactor(day / kDaysPerYear);
}

// A leg row as seen by whoever receives the leg (before the holder's sign), in the leg's currency.
struct LegRow {
    const char* kind;
    int         day;
    double      accrual;
    double      amount;
    double      df;
};

std::vector<LegRow> legRows(double notional, double accruedFactor, double spread, int startDays,
                            const std::vector<Period>& periods,
                            const termstructure::YieldCurve& projection,
                            const termstructure::YieldCurve& discount,
                            bool initialExchange, bool finalExchange)
{
    std::vector<LegRow> rows;
    if (initialExchange && startDays >= 0)
        rows.push_back({"exchange", startDays, 0.0, -notional, discountAt(discount, startDays)});
    for (std::size_t i = 0; i < periods.size(); ++i) {
        const Period& p = periods[i];
        const double accrued = i == 0 ? accruedFactor : 1.0;   // only period 1 has elapsed fixings
        const double coupon  = notional * (accrued * discountAt(projection, p.prevDay)
                                           / discountAt(projection, p.day) - 1.0)
                             + notional * spread * p.tau;
        rows.push_back({"coupon", p.day, p.tau, coupon, discountAt(discount, p.day)});
    }
    if (finalExchange)
        rows.push_back({"exchange", periods.back().day, 0.0, notional,
                        discountAt(discount, periods.back().day)});
    return rows;
}

} // namespace

XccySwap::XccySwap(double notionalUsd, double fxRate, double spread, int startDays,
                   std::vector<int> payDays, double accruedFactorUsd, double accruedFactorMxn,
                   XccySide side, bool initialExchange, bool finalExchange,
                   std::string usdCurve, std::string mxnProjectionCurve,
                   std::string mxnDiscountCurve, std::string pair,
                   math::DayCountConvention dcc)
    : Instrument(payDays.empty() ? 0.0 : payDays.back() / kDaysPerYear),
      notionalUsd_(notionalUsd), fxRate_(fxRate), spread_(spread), startDays_(startDays),
      payDays_(std::move(payDays)), accruedFactorUsd_(accruedFactorUsd),
      accruedFactorMxn_(accruedFactorMxn), side_(side),
      initialExchange_(initialExchange), finalExchange_(finalExchange),
      usdCurve_(std::move(usdCurve)), mxnProjectionCurve_(std::move(mxnProjectionCurve)),
      mxnDiscountCurve_(std::move(mxnDiscountCurve)), pair_(std::move(pair)), dcc_(dcc)
{
    if (!std::isfinite(notionalUsd_) || notionalUsd_ <= 0.0)
        throw std::invalid_argument("XccySwap: notionalUsd must be positive");
    if (!std::isfinite(fxRate_) || fxRate_ <= 0.0)
        throw std::invalid_argument("XccySwap: fxRate must be positive");
    if (!std::isfinite(spread_))
        throw std::invalid_argument("XccySwap: spread must be finite");
    if (payDays_.empty())
        throw std::invalid_argument("XccySwap: payDays must not be empty");
    if (payDays_.front() <= 0)
        throw std::invalid_argument("XccySwap: payDays must be positive");
    for (std::size_t i = 1; i < payDays_.size(); ++i)
        if (payDays_[i] <= payDays_[i - 1])
            throw std::invalid_argument("XccySwap: payDays must be strictly increasing");
    if (startDays_ >= payDays_.front())
        throw std::invalid_argument("XccySwap: startDays must precede the first payment");
    if (!(accruedFactorUsd_ > 0.0) || !(accruedFactorMxn_ > 0.0))
        throw std::invalid_argument("XccySwap: accrued factors must be positive");
    if (startDays_ >= 0 && (accruedFactorUsd_ != 1.0 || accruedFactorMxn_ != 1.0))
        throw std::invalid_argument("XccySwap: accrued factors must be 1 when the period has not started");
    if (dcc_ == math::DayCountConvention::THIRTY_360)
        throw std::invalid_argument("XccySwap: 30/360 needs calendar dates and is not supported");
}

std::vector<XccyCashFlow> XccySwap::cashFlows(const core::MarketEnvironment& env) const
{
    const termstructure::YieldCurve& usd     = env.curve(usdCurve_);
    const termstructure::YieldCurve& mxnProj = env.curve(mxnProjectionCurve_);
    const termstructure::YieldCurve& mxnDisc = env.curve(mxnDiscountCurve_);
    const double spot = env.spot(pair_);
    const std::vector<Period> periods = buildPeriods(startDays_, payDays_, dcc_);

    // Holder's sign: PayUsd receives MXN and pays USD; PayMxn is the mirror image.
    const double mxnSign = side_ == XccySide::PayUsd ? 1.0 : -1.0;

    std::vector<XccyCashFlow> out;
    const auto append = [&](const char* leg, double sign, double fx, const std::vector<LegRow>& rows) {
        for (const LegRow& r : rows) {
            XccyCashFlow cf;
            cf.leg             = leg;
            cf.kind            = r.kind;
            cf.payDays         = r.day;
            cf.accrual         = r.accrual;
            cf.amount          = sign * r.amount;
            cf.discountFactor  = r.df;
            cf.presentValue    = cf.amount * r.df;
            cf.presentValueMxn = cf.presentValue * fx;
            out.push_back(cf);
        }
    };
    append("USD", -mxnSign, spot,
           legRows(notionalUsd_, accruedFactorUsd_, 0.0, startDays_, periods, usd, usd,
                   initialExchange_, finalExchange_));
    const std::size_t usdRows = out.size();
    append("MXN", mxnSign, 1.0,
           legRows(notionalMxn(), accruedFactorMxn_, spread_, startDays_, periods, mxnProj, mxnDisc,
                   initialExchange_, finalExchange_));

    // Merge the two legs by payment day, USD first on ties; each leg is already in date order and
    // keeps its coupon-before-exchange order.
    std::inplace_merge(out.begin(), out.begin() + static_cast<std::ptrdiff_t>(usdRows), out.end(),
                       [](const XccyCashFlow& a, const XccyCashFlow& b) { return a.payDays < b.payDays; });
    return out;
}

double XccySwap::npv(const core::MarketEnvironment& env) const
{
    double total = 0.0;
    for (const XccyCashFlow& cf : cashFlows(env))
        total += cf.presentValueMxn;
    return total;
}

double XccySwap::parSpread(const core::MarketEnvironment& env) const
{
    const termstructure::YieldCurve& mxnDisc = env.curve(mxnDiscountCurve_);
    double annuity = 0.0;   // sum of tau_i * DFd(e_i) over the MXN coupons
    for (const Period& p : buildPeriods(startDays_, payDays_, dcc_))
        annuity += p.tau * discountAt(mxnDisc, p.day);
    // The value is linear in the spread; express it from the PayUsd side whatever the holder's side.
    const double npvPayUsd = side_ == XccySide::PayUsd ? npv(env) : -npv(env);
    return spread_ - npvPayUsd / (notionalMxn() * annuity);
}

} // namespace qf::instruments
