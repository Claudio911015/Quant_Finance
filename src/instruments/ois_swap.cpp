#include <qf/instruments/ois_swap.hpp>
#include <qf/termstructure/ois_bootstrap.hpp>
#include <stdexcept>
#include <utility>

namespace qf::instruments {

namespace {

constexpr double kDaysPerYear = 365.0;   // payment time t = days / 365

// One coupon period: its payment day, the previous payment day (0 for the first)
// and the accrual fraction under the swap's day-count.
struct Period {
    int    day;
    int    prevDay;
    double tau;
};

std::vector<Period> buildPeriods(int maturityDays, int periodDays, math::DayCountConvention dcc)
{
    std::vector<Period> periods;
    int prev = 0;
    for (int d : termstructure::oisPaymentDays(maturityDays, periodDays)) {
        periods.push_back({d, prev, math::yearFraction(d - prev, dcc)});
        prev = d;
    }
    return periods;
}

// DF at a payment day; the valuation date itself has DF = 1 by definition.
double discountAt(const termstructure::YieldCurve& curve, int day)
{
    return day == 0 ? 1.0 : curve.discountFactor(day / kDaysPerYear);
}

} // namespace

OisSwap::OisSwap(double notional, double fixedRate, int maturityDays, int periodDays,
                 SwapType type, std::string curveKey, math::DayCountConvention dcc)
    : Instrument(maturityDays / kDaysPerYear),
      notional_(notional), fixedRate_(fixedRate),
      maturityDays_(maturityDays), periodDays_(periodDays),
      type_(type), curveKey_(std::move(curveKey)), dcc_(dcc)
{
    if (notional_ <= 0.0)
        throw std::invalid_argument("OisSwap: notional must be positive");
    if (maturityDays_ <= 0)
        throw std::invalid_argument("OisSwap: maturityDays must be positive");
    if (periodDays_ <= 0)
        throw std::invalid_argument("OisSwap: periodDays must be positive");
    if (dcc_ == math::DayCountConvention::THIRTY_360)
        throw std::invalid_argument("OisSwap: 30/360 needs calendar dates and is not supported");
}

std::vector<OisCashFlow> OisSwap::cashFlows(const core::MarketEnvironment& env) const
{
    const termstructure::YieldCurve& curve = env.curve(curveKey_);
    const double sign = (type_ == SwapType::Payer) ? 1.0 : -1.0;   // Payer: float - fixed

    std::vector<OisCashFlow> rows;
    for (const Period& p : buildPeriods(maturityDays_, periodDays_, dcc_)) {
        const double dfPrev = discountAt(curve, p.prevDay);
        const double df     = discountAt(curve, p.day);

        OisCashFlow row;
        row.payDays        = p.day;
        row.payTime        = p.day / kDaysPerYear;
        row.accrual        = p.tau;
        row.fixedAmount    = notional_ * fixedRate_ * p.tau;
        row.floatAmount    = notional_ * (dfPrev / df - 1.0);
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
    const termstructure::YieldCurve& curve = env.curve(curveKey_);
    double sum = 0.0;
    for (const Period& p : buildPeriods(maturityDays_, periodDays_, dcc_))
        sum += notional_ * p.tau * discountAt(curve, p.day);
    return sum;
}

double OisSwap::parRate(const core::MarketEnvironment& env) const
{
    const termstructure::YieldCurve& curve = env.curve(curveKey_);
    const double floatPv = notional_ * (1.0 - discountAt(curve, maturityDays_));
    return floatPv / annuity(env);
}

} // namespace qf::instruments
