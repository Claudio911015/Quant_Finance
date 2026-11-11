#include <qf/instruments/ois_swap.hpp>
#include <qf/termstructure/ois_bootstrap.hpp>
#include <stdexcept>
#include <utility>

namespace qf::instruments {

namespace {

constexpr double kDaysPerYear = 365.0;   // payment time t = days / 365

// One coupon period: its payment day, the day it starts (the valuation date or the previous
// payment; negative when the period began before the valuation date) and the accrual fraction
// under the swap's day-count.
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

// DF at a day; the valuation date itself has DF = 1 by definition, and a period that started
// before it is projected from the valuation date (the elapsed part sits in the accrued factor).
double discountAt(const termstructure::YieldCurve& curve, int day)
{
    return day <= 0 ? 1.0 : curve.discountFactor(day / kDaysPerYear);
}

// Payment schedule of the first constructor, validated with that constructor's messages.
std::vector<int> scheduleFor(int maturityDays, int periodDays)
{
    if (maturityDays <= 0)
        throw std::invalid_argument("OisSwap: maturityDays must be positive");
    if (periodDays <= 0)
        throw std::invalid_argument("OisSwap: periodDays must be positive");
    return termstructure::oisPaymentDays(maturityDays, periodDays);
}

} // namespace

double compoundOvernight(const std::vector<double>& rates, const std::vector<int>& days,
                         double dayBase)
{
    if (rates.size() != days.size())
        throw std::invalid_argument("compoundOvernight: rates and days must have the same size");
    if (!(dayBase > 0.0))
        throw std::invalid_argument("compoundOvernight: dayBase must be positive");
    double factor = 1.0;
    for (std::size_t i = 0; i < rates.size(); ++i) {
        if (days[i] <= 0)
            throw std::invalid_argument("compoundOvernight: days must be positive");
        const double f = 1.0 + rates[i] * days[i] / dayBase;
        if (!(f > 0.0))
            throw std::invalid_argument("compoundOvernight: a daily factor is not positive");
        factor *= f;
    }
    return factor;
}

OisSwap::OisSwap(double notional, double fixedRate, int maturityDays, int periodDays,
                 SwapType type, std::string curveKey, math::DayCountConvention dcc,
                 std::string discountCurveKey)
    : OisSwap(notional, fixedRate, 0, scheduleFor(maturityDays, periodDays), 1.0,
              type, std::move(curveKey), dcc, std::move(discountCurveKey))
{
    periodDays_ = periodDays;
}

OisSwap::OisSwap(double notional, double fixedRate, int startDays, std::vector<int> payDays,
                 double accruedFactor, SwapType type, std::string curveKey,
                 math::DayCountConvention dcc, std::string discountCurveKey)
    : Instrument(payDays.empty() ? 0.0 : payDays.back() / kDaysPerYear),
      notional_(notional), fixedRate_(fixedRate),
      type_(type), curveKey_(std::move(curveKey)),
      discountCurveKey_(std::move(discountCurveKey)), dcc_(dcc),
      startDays_(startDays), payDays_(std::move(payDays)), accruedFactor_(accruedFactor)
{
    if (notional_ <= 0.0)
        throw std::invalid_argument("OisSwap: notional must be positive");
    if (payDays_.empty())
        throw std::invalid_argument("OisSwap: payDays must not be empty");
    if (payDays_.front() <= 0)
        throw std::invalid_argument("OisSwap: payDays must be positive");
    for (std::size_t i = 1; i < payDays_.size(); ++i)
        if (payDays_[i] <= payDays_[i - 1])
            throw std::invalid_argument("OisSwap: payDays must be strictly increasing");
    if (startDays_ >= payDays_.front())
        throw std::invalid_argument("OisSwap: startDays must precede the first payment");
    if (!(accruedFactor_ > 0.0))
        throw std::invalid_argument("OisSwap: accruedFactor must be positive");
    if (startDays_ >= 0 && accruedFactor_ != 1.0)
        throw std::invalid_argument("OisSwap: accruedFactor must be 1 when the period has not started");
    if (dcc_ == math::DayCountConvention::THIRTY_360)
        throw std::invalid_argument("OisSwap: 30/360 needs calendar dates and is not supported");
    maturityDays_ = payDays_.back();
    periodDays_   = payDays_.front() - startDays_;
}

std::vector<OisCashFlow> OisSwap::cashFlows(const core::MarketEnvironment& env) const
{
    const termstructure::YieldCurve& curve = env.curve(curveKey_);                 // projection
    const termstructure::YieldCurve& disc  = env.curve(discountCurveKey());        // discounting
    const double sign = (type_ == SwapType::Payer) ? 1.0 : -1.0;   // Payer: float - fixed

    std::vector<OisCashFlow> rows;
    for (const Period& p : buildPeriods(startDays_, payDays_, dcc_)) {
        const double dfPrev  = discountAt(curve, p.prevDay);
        const double dfProj  = discountAt(curve, p.day);
        const double df      = discountAt(disc, p.day);
        const double accrued = rows.empty() ? accruedFactor_ : 1.0;   // only period 1 has elapsed fixings

        OisCashFlow row;
        row.payDays        = p.day;
        row.payTime        = p.day / kDaysPerYear;
        row.accrual        = p.tau;
        row.fixedAmount    = notional_ * fixedRate_ * p.tau;
        row.floatAmount    = notional_ * (accrued * dfPrev / dfProj - 1.0);
        row.netAmount      = sign * (row.floatAmount - row.fixedAmount);
        row.discountFactor = df;
        row.presentValue   = row.netAmount * df;
        rows.push_back(row);
    }
    return rows;
}

double OisSwap::npv(const core::MarketEnvironment& env) const
{
    double total = 0.0;
    for (const OisCashFlow& row : cashFlows(env))
        total += row.presentValue;
    return total;
}

double OisSwap::annuity(const core::MarketEnvironment& env) const
{
    const termstructure::YieldCurve& disc = env.curve(discountCurveKey());
    double sum = 0.0;
    for (const Period& p : buildPeriods(startDays_, payDays_, dcc_))
        sum += notional_ * p.tau * discountAt(disc, p.day);
    return sum;
}

double OisSwap::parRate(const core::MarketEnvironment& env) const
{
    double floatPv = 0.0;
    for (const OisCashFlow& row : cashFlows(env))
        floatPv += row.floatAmount * row.discountFactor;
    return floatPv / annuity(env);
}

} // namespace qf::instruments
