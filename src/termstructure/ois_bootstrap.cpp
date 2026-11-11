#include <qf/termstructure/ois_bootstrap.hpp>
#include <qf/math/rootfinding.hpp>
#include <cmath>
#include <stdexcept>
#include <string>

namespace qf::termstructure {

namespace {

constexpr double kDaysPerYear = 365.0;   // pillar time t = days / 365
constexpr double kSolveTol    = 1e-14;
constexpr int    kSolveMaxIt  = 200;
constexpr double kZeroLo      = -0.5;    // search range for the new pillar's zero rate
constexpr double kZeroHi      = 2.0;

// Discount factors at the given times for the pillars known so far plus a trial
// pillar (T, z). With no earlier pillar the curve is flat at z.
std::vector<double> trialDiscountFactors(const std::vector<double>& mats,
                                         const std::vector<double>& zeros,
                                         double T, double z,
                                         const std::vector<double>& times,
                                         math::InterpolationMethod method)
{
    std::vector<double> out;
    out.reserve(times.size());
    if (mats.empty()) {
        for (double t : times) out.push_back(std::exp(-z * t));
        return out;
    }
    std::vector<double> m = mats, r = zeros;
    m.push_back(T);
    r.push_back(z);
    YieldCurve curve(std::move(m), std::move(r), method);
    for (double t : times) out.push_back(curve.discountFactor(t));
    return out;
}

} // namespace

std::vector<int> oisPaymentDays(int maturityDays, int periodDays)
{
    if (maturityDays <= 0)
        throw std::invalid_argument("oisPaymentDays: maturityDays must be > 0");
    if (periodDays <= 0)
        throw std::invalid_argument("oisPaymentDays: periodDays must be > 0");

    std::vector<int> days;
    for (long long d = periodDays; d < maturityDays; d += periodDays)
        days.push_back(static_cast<int>(d));
    days.push_back(maturityDays);
    return days;
}

YieldCurve bootstrapOis(const std::vector<OisQuote>& quotes, int periodDays,
                        math::DayCountConvention accrualDcc,
                        math::InterpolationMethod method)
{
    if (quotes.empty())
        throw std::invalid_argument("bootstrapOis: quotes vector is empty");
    if (periodDays <= 0)
        throw std::invalid_argument("bootstrapOis: periodDays must be > 0");
    if (quotes.front().days <= 0)
        throw std::invalid_argument("bootstrapOis: quote days must be > 0");
    for (std::size_t i = 1; i < quotes.size(); ++i)
        if (quotes[i].days <= quotes[i - 1].days)
            throw std::invalid_argument("bootstrapOis: quote days must be strictly increasing");

    std::vector<double> mats, zeros;
    mats.reserve(quotes.size());
    zeros.reserve(quotes.size());

    for (const auto& q : quotes) {
        const double T = q.days / kDaysPerYear;
        double z = 0.0;

        if (q.type == OisQuote::Deposit) {
            const double denom = 1.0 + q.rate * math::yearFraction(q.days, accrualDcc);
            if (denom <= 0.0)
                throw std::runtime_error("bootstrapOis: non-positive discount factor for deposit at "
                                         + std::to_string(q.days) + " days");
            z = std::log(denom) / T;  // DF = 1/denom, z = -ln(DF)/T
        } else {
            const std::vector<int> payDays = oisPaymentDays(q.days, periodDays);
            std::vector<double> times, taus;
            times.reserve(payDays.size());
            taus.reserve(payDays.size());
            int prev = 0;
            for (int d : payDays) {
                times.push_back(d / kDaysPerYear);
                taus.push_back(math::yearFraction(d - prev, accrualDcc));
                prev = d;
            }

            auto residual = [&](double zTrial) {
                const std::vector<double> dfs =
                    trialDiscountFactors(mats, zeros, T, zTrial, times, method);
                double annuity = 0.0;
                for (std::size_t i = 0; i < dfs.size(); ++i)
                    annuity += taus[i] * dfs[i];
                return q.rate * annuity - (1.0 - dfs.back());
            };

            if (residual(kZeroLo) * residual(kZeroHi) > 0.0)
                throw std::runtime_error("bootstrapOis: no zero rate solves the OIS at "
                                         + std::to_string(q.days) + " days");
            z = math::brent(residual, kZeroLo, kZeroHi, kSolveTol, kSolveMaxIt);
        }

        mats.push_back(T);
        zeros.push_back(z);
    }

    return YieldCurve(std::move(mats), std::move(zeros), method);
}

} // namespace qf::termstructure
