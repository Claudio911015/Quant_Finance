#include <qf/termstructure/xccy_bootstrap.hpp>
#include <qf/termstructure/ois_bootstrap.hpp>
#include <qf/instruments/xccy_swap.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/math/rootfinding.hpp>
#include <cmath>
#include <stdexcept>
#include <string>
#include <utility>

namespace qf::termstructure {

namespace {

constexpr double kDaysPerYear = 365.0;   // pillar time t = days / 365
constexpr double kSolveTol    = 1e-14;
constexpr int    kSolveMaxIt  = 200;
constexpr double kZeroLo      = -0.5;    // search range for the new pillar's zero rate
constexpr double kZeroHi      = 2.0;

// Curve keys the basis swap is valued under (the XccySwap defaults).
const char* const kUsdKey  = "SOFR";
const char* const kProjKey = "TIIE-F";
const char* const kDiscKey = "MXN-USD";
const char* const kPair    = "USDMXN";

// Curve made of the pillars solved so far plus a trial pillar (T, z). A YieldCurve needs two
// pillars, so with none solved yet the trial curve is flat at z.
YieldCurve trialCurve(const std::vector<double>& mats, const std::vector<double>& zeros,
                      double T, double z, math::InterpolationMethod method)
{
    std::vector<double> m = mats, r = zeros;
    if (m.empty()) {
        m = {0.5 * T};
        r = {z};
    }
    m.push_back(T);
    r.push_back(z);
    return YieldCurve(std::move(m), std::move(r), method);
}

void validate(const std::vector<FxForwardQuote>& forwards, const std::vector<XccyBasisQuote>& basis,
              double spot, int periodDays)
{
    if (forwards.size() + basis.size() < 2)
        throw std::invalid_argument("bootstrapXccyDiscount: need at least two quotes between forwards and basis");
    if (periodDays <= 0)
        throw std::invalid_argument("bootstrapXccyDiscount: periodDays must be > 0");
    if (!std::isfinite(spot) || spot <= 0.0)
        throw std::invalid_argument("bootstrapXccyDiscount: spot must be positive");

    for (std::size_t i = 0; i < forwards.size(); ++i) {
        if (forwards[i].days <= 0)
            throw std::invalid_argument("bootstrapXccyDiscount: forward days must be > 0");
        if (i > 0 && forwards[i].days <= forwards[i - 1].days)
            throw std::invalid_argument("bootstrapXccyDiscount: forward days must be strictly increasing");
        const double outright = spot + forwards[i].points;
        if (!std::isfinite(outright) || outright <= 0.0)
            throw std::invalid_argument("bootstrapXccyDiscount: spot + points must be positive at "
                                        + std::to_string(forwards[i].days) + " days");
    }
    for (std::size_t i = 0; i < basis.size(); ++i) {
        if (basis[i].days <= 0)
            throw std::invalid_argument("bootstrapXccyDiscount: basis days must be > 0");
        if (i > 0 && basis[i].days <= basis[i - 1].days)
            throw std::invalid_argument("bootstrapXccyDiscount: basis days must be strictly increasing");
        if (!std::isfinite(basis[i].spread))
            throw std::invalid_argument("bootstrapXccyDiscount: basis spread must be finite");
    }
    if (!forwards.empty() && !basis.empty() && basis.front().days <= forwards.back().days)
        throw std::invalid_argument("bootstrapXccyDiscount: the first basis quote must lie after the last forward");
}

} // namespace

YieldCurve bootstrapXccyDiscount(const std::vector<FxForwardQuote>& forwards,
                                 const std::vector<XccyBasisQuote>& basis,
                                 double spot, const YieldCurve& usdDiscount, const YieldCurve& mxnProjection,
                                 int periodDays, math::DayCountConvention accrualDcc,
                                 math::InterpolationMethod method)
{
    validate(forwards, basis, spot, periodDays);

    std::vector<double> mats, zeros;
    mats.reserve(forwards.size() + basis.size());
    zeros.reserve(forwards.size() + basis.size());

    // Covered-interest parity: DF_MXN(t) = S * DFu(t) / (S + points).
    for (const auto& q : forwards) {
        const double T  = q.days / kDaysPerYear;
        const double df = spot * usdDiscount.discountFactor(T) / (spot + q.points);
        if (!std::isfinite(df) || df <= 0.0)
            throw std::runtime_error("bootstrapXccyDiscount: non-positive discount factor for the forward at "
                                     + std::to_string(q.days) + " days");
        mats.push_back(T);
        zeros.push_back(-std::log(df) / T);
    }

    core::MarketEnvironment env;
    env.addCurve(kUsdKey, usdDiscount);
    env.addCurve(kProjKey, mxnProjection);
    env.setSpot(kPair, spot);

    for (const auto& q : basis) {
        const double T = q.days / kDaysPerYear;
        const std::vector<int> payDays = oisPaymentDays(q.days, periodDays);

        // Unit USD notional, MXN notional fixed at spot, quoted spread, both exchanges: its value
        // as a function of the new pillar's zero rate must vanish.
        const instruments::XccySwap swap(1.0, spot, q.spread, 0, payDays, 1.0, 1.0,
                                         instruments::XccySide::PayUsd, true, true,
                                         kUsdKey, kProjKey, kDiscKey, kPair, accrualDcc);
        auto residual = [&](double zTrial) {
            env.addCurve(kDiscKey, trialCurve(mats, zeros, T, zTrial, method));
            return swap.npv(env);
        };

        const double lo = residual(kZeroLo);
        const double hi = residual(kZeroHi);
        if (!std::isfinite(lo) || !std::isfinite(hi) || lo * hi > 0.0)
            throw std::runtime_error("bootstrapXccyDiscount: no zero rate solves the basis swap at "
                                     + std::to_string(q.days) + " days");
        const double z = math::brent(residual, kZeroLo, kZeroHi, kSolveTol, kSolveMaxIt);

        mats.push_back(T);
        zeros.push_back(z);
    }

    return YieldCurve(std::move(mats), std::move(zeros), method);
}

} // namespace qf::termstructure
