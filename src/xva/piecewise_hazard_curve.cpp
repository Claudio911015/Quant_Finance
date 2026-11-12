#include <qf/xva/piecewise_hazard_curve.hpp>
#include <qf/math/rootfinding.hpp>
#include <algorithm>
#include <cmath>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>

namespace qf::xva {

namespace {

constexpr double kDaysPerYear    = 365.0;   // time axis: t = days / 365
constexpr double kAccrualBase    = 360.0;   // premium accrual: tau = days / 360
constexpr double kHazardTol      = 1e-14;
constexpr int    kSolverMaxIter  = 200;
constexpr int    kMaxBracketDoublings = 60;

std::string yearsText(double years) {
    std::ostringstream os;
    os << years;
    return os.str();
}

void requireRecovery(const char* who, double recovery) {
    if (!(recovery >= 0.0 && recovery < 1.0))   // also rejects NaN
        throw std::invalid_argument(std::string(who) + ": recovery must be in [0, 1)");
}

// Premium payment days d_k = round(k * 365 / 4), k = 1..4T. A tenor that is not a whole number
// of quarters ends in a stub payment on round(365 * T).
std::vector<long> premiumDays(const char* who, double tenorYears) {
    if (!(tenorYears > 0.0) || !std::isfinite(tenorYears))
        throw std::invalid_argument(std::string(who) + ": tenor must be a positive finite number of years");
    const long quarters = static_cast<long>(std::floor(4.0 * tenorYears + 1e-9));
    std::vector<long> days;
    days.reserve(static_cast<std::size_t>(quarters) + 1);
    for (long k = 1; k <= quarters; ++k)
        days.push_back(std::lround(k * kDaysPerYear / 4.0));
    const long last = std::lround(tenorYears * kDaysPerYear);
    if (days.empty() || last > days.back())
        days.push_back(last);
    if (days.back() < 1)
        throw std::invalid_argument(std::string(who) + ": tenor is shorter than one day");
    return days;
}

} // namespace

PiecewiseHazardCurve::PiecewiseHazardCurve(std::vector<double> times, std::vector<double> hazards)
    : times_(std::move(times)), hazards_(std::move(hazards))
{
    if (times_.empty() || times_.size() != hazards_.size())
        throw std::invalid_argument("PiecewiseHazardCurve: times and hazards must have the same size >= 1");
    double prev = 0.0;
    for (std::size_t i = 0; i < times_.size(); ++i) {
        if (!(times_[i] > prev) || !std::isfinite(times_[i]))
            throw std::invalid_argument("PiecewiseHazardCurve: times must be > 0 and strictly increasing");
        if (!(hazards_[i] >= 0.0) || !std::isfinite(hazards_[i]))
            throw std::invalid_argument("PiecewiseHazardCurve: hazards must be non-negative");
        prev = times_[i];
    }
}

double PiecewiseHazardCurve::survivalProbability(double t) const
{
    return survivalFromHazards(times_, hazards_, t);
}

double PiecewiseHazardCurve::hazardRate(double t) const
{
    // First vertex >= t: the tramo (times[i-1], times[i]] that contains t; flat past the last one.
    const auto it = std::lower_bound(times_.begin(), times_.end(), t);
    if (it == times_.end())
        return hazards_.back();
    return hazards_[static_cast<std::size_t>(it - times_.begin())];
}

const std::vector<double>& PiecewiseHazardCurve::times() const   { return times_; }
const std::vector<double>& PiecewiseHazardCurve::hazards() const { return hazards_; }

double cdsValue(const CdsQuote& quote, double recovery, const ICreditCurve& curve,
                const termstructure::YieldCurve& discount, double notional)
{
    constexpr const char* kWho = "cdsValue";
    requireRecovery(kWho, recovery);
    if (!std::isfinite(quote.spread) || !std::isfinite(notional))
        throw std::invalid_argument("cdsValue: spread and notional must be finite");
    const std::vector<long> days = premiumDays(kWho, quote.tenorYears);

    double protection = 0.0;   // sum of default-probability mass * DF at mid-period
    double premium    = 0.0;   // sum of tau * S(t_k) * DF(t_k)
    double accrued    = 0.0;   // premium accrued at default, half a period on average
    long   prevDay    = 0;
    double prevT      = 0.0;
    double prevSurv   = 1.0;
    for (const long day : days) {
        const double t    = static_cast<double>(day) / kDaysPerYear;
        const double tau  = static_cast<double>(day - prevDay) / kAccrualBase;
        const double surv = curve.survivalProbability(t);
        const double dfMid = discount.discountFactor(0.5 * (prevT + t));
        const double defaultMass = prevSurv - surv;
        protection += defaultMass * dfMid;
        premium    += tau * surv * discount.discountFactor(t);
        accrued    += 0.5 * tau * defaultMass * dfMid;
        prevDay = day;
        prevT = t;
        prevSurv = surv;
    }
    return notional * ((1.0 - recovery) * protection - quote.spread * (premium + accrued));
}

PiecewiseHazardCurve bootstrapCdsCurve(const std::vector<CdsQuote>& quotes, double recovery,
                                       const termstructure::YieldCurve& discount)
{
    constexpr const char* kWho = "bootstrapCdsCurve";
    if (quotes.empty())
        throw std::invalid_argument("bootstrapCdsCurve: quotes must not be empty");
    requireRecovery(kWho, recovery);
    double prevTenor = 0.0;
    for (const CdsQuote& q : quotes) {
        if (!(q.tenorYears > prevTenor) || !std::isfinite(q.tenorYears))
            throw std::invalid_argument("bootstrapCdsCurve: tenors must be positive and strictly increasing");
        if (!(q.spread > 0.0) || !std::isfinite(q.spread))
            throw std::invalid_argument("bootstrapCdsCurve: spread must be positive");
        prevTenor = q.tenorYears;
    }

    std::vector<double> times;
    std::vector<double> hazards;
    times.reserve(quotes.size());
    hazards.reserve(quotes.size());

    for (const CdsQuote& q : quotes) {
        // The tramo ends at the CDS's last premium date (= the tenor whenever 365 T is a whole
        // number of days). Ending it any earlier would let a later tramo move this CDS's value
        // through a final payment that falls a fraction of a day past the tenor (e.g. 6m = day 183).
        const double vertex = static_cast<double>(premiumDays(kWho, q.tenorYears).back()) / kDaysPerYear;
        if (!times.empty() && !(vertex > times.back()))
            throw std::invalid_argument("bootstrapCdsCurve: tenors must be at least one day apart");
        times.push_back(vertex);
        hazards.push_back(0.0);
        // Value of this CDS as a function of the hazard of the tramo that ends at its tenor.
        auto value = [&](double h) {
            hazards.back() = h;
            return cdsValue(q, recovery, PiecewiseHazardCurve(times, hazards), discount);
        };

        const double atZero = value(0.0);
        if (atZero > 0.0)
            throw std::invalid_argument("bootstrapCdsCurve: quote at " + yearsText(q.tenorYears)
                                        + "y implies a negative hazard rate");
        double h = 0.0;
        if (atZero < 0.0) {
            double hi = std::max(1e-3, 2.0 * q.spread / (1.0 - recovery));
            int doublings = 0;
            while (value(hi) <= 0.0) {
                if (++doublings > kMaxBracketDoublings)
                    throw std::invalid_argument("bootstrapCdsCurve: no hazard rate reprices the quote at "
                                                + yearsText(q.tenorYears) + "y");
                hi *= 2.0;
            }
            h = std::max(0.0, math::brent(value, 0.0, hi, kHazardTol, kSolverMaxIter));
        }
        hazards.back() = h;
    }
    return PiecewiseHazardCurve(std::move(times), std::move(hazards));
}

} // namespace qf::xva
