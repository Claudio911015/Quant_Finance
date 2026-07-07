#include <qf/termstructure/volsurface.hpp>

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <utility>

#include <qf/instruments/option.hpp>
#include <qf/models/heston_calibrator.hpp>       // qf::models::OptionQuote
#include <qf/pricingengines/blackscholes.hpp>    // impliedVolatility

namespace qf::termstructure {

VolSurface::VolSurface(std::vector<double> maturities,
                       std::vector<double> strikes,
                       std::vector<std::vector<double>> vols,
                       math::InterpolationMethod strikeMethod)
    : maturities_(std::move(maturities)),
      strikes_(std::move(strikes)),
      vols_(std::move(vols)),
      strikeMethod_(strikeMethod)
{
    validate();
    buildSmiles();
}

void VolSurface::validate() const
{
    if (maturities_.size() < 2 || strikes_.size() < 2)
        throw std::invalid_argument(
            "VolSurface: need at least 2 maturity pillars and 2 strike pillars");

    for (std::size_t i = 1; i < maturities_.size(); ++i)
        if (maturities_[i] <= maturities_[i - 1])
            throw std::invalid_argument("VolSurface: maturities must be strictly increasing");
    if (maturities_.front() <= 0.0)
        throw std::invalid_argument("VolSurface: maturities must be positive");

    for (std::size_t j = 1; j < strikes_.size(); ++j)
        if (strikes_[j] <= strikes_[j - 1])
            throw std::invalid_argument("VolSurface: strikes must be strictly increasing");

    if (vols_.size() != maturities_.size())
        throw std::invalid_argument("VolSurface: vols row count must match maturities");
    for (const auto& row : vols_) {
        if (row.size() != strikes_.size())
            throw std::invalid_argument("VolSurface: each vols row must match strikes");
        for (double v : row)
            if (v <= 0.0)
                throw std::invalid_argument("VolSurface: all vols must be positive");
    }

    // Calendar-arbitrage guard: total variance σ²·T must be non-decreasing in T at each
    // fixed strike pillar (a tiny tolerance absorbs floating-point noise / flat smiles).
    constexpr double kTol = 1e-12;
    for (std::size_t j = 0; j < strikes_.size(); ++j) {
        for (std::size_t i = 1; i < maturities_.size(); ++i) {
            const double wPrev = vols_[i - 1][j] * vols_[i - 1][j] * maturities_[i - 1];
            const double wCurr = vols_[i][j] * vols_[i][j] * maturities_[i];
            if (wCurr < wPrev - kTol)
                throw std::invalid_argument(
                    "VolSurface: total variance must be non-decreasing in maturity "
                    "(calendar-arbitrage guard) at a strike pillar");
        }
    }
}

void VolSurface::buildSmiles()
{
    smiles_.clear();
    smiles_.reserve(maturities_.size());
    for (std::size_t i = 0; i < maturities_.size(); ++i)
        smiles_.emplace_back(strikes_, vols_[i], strikeMethod_);
}

double VolSurface::vol(double strike, double maturity) const
{
    if (maturity <= 0.0)
        throw std::invalid_argument("VolSurface::vol: maturity must be positive");

    // 1. Smile in strike: vol at the requested strike for each maturity pillar, then
    //    convert to total variance w_i = σ_i² · T_i.
    std::vector<double> totalVar(maturities_.size());
    for (std::size_t i = 0; i < maturities_.size(); ++i) {
        const double sigma = smiles_[i](strike);
        totalVar[i] = sigma * sigma * maturities_[i];
    }

    // 2. Term structure: interpolate total variance linearly in maturity, but with
    //    calendar-consistent extrapolation at BOTH ends rather than flat-in-w (which would
    //    explode σ = √(w/T) as T→0 below the first pillar and collapse it above the last):
    //
    //      • Short end: anchor the curve at (T=0, w=0). Linear-in-w between (0,0) and the
    //        first pillar (T₀, w₀) is exactly flat-in-VOL — a sub-pillar option marks at the
    //        first pillar's vol, the standard short-end treatment (cf. QuantLib
    //        BlackVarianceCurve inserting the (0,0) node). Still calendar-consistent.
    //      • Long end: extrapolate flat-in-VOL, i.e. hold σ at the last pillar's level so
    //        w = σ_last²·T keeps growing linearly. A long option marks at the last pillar's
    //        vol instead of decaying toward zero.
    const double Tmax = maturities_.back();
    if (maturity >= Tmax) {
        const double sigmaMax = std::sqrt(totalVar.back() / Tmax);
        return sigmaMax;  // flat-in-vol beyond the last maturity pillar
    }

    std::vector<double> matNodes;
    std::vector<double> varNodes;
    matNodes.reserve(maturities_.size() + 1);
    varNodes.reserve(maturities_.size() + 1);
    matNodes.push_back(0.0);
    varNodes.push_back(0.0);  // (T=0, w=0) anchor: flat-in-vol at the short end
    for (std::size_t i = 0; i < maturities_.size(); ++i) {
        matNodes.push_back(maturities_[i]);
        varNodes.push_back(totalVar[i]);
    }

    math::Interpolator tvar(matNodes, varNodes, math::InterpolationMethod::Linear);
    double w = tvar(maturity);
    if (w < 0.0) w = 0.0;  // guard against tiny negative from extrapolation edge cases
    return std::sqrt(w / maturity);
}

VolSurface VolSurface::fromQuotes(double spot, double r, double q,
                                  const std::vector<models::OptionQuote>& quotes,
                                  math::InterpolationMethod strikeMethod)
{
    if (quotes.empty())
        throw std::invalid_argument("VolSurface::fromQuotes: no quotes");

    // Distinct, sorted maturity and strike pillars found in the chain, merged with a
    // relative tolerance so that two quotes whose pillar differs only by floating-point
    // noise (e.g. a maturity computed as a day-count fraction via two different code paths,
    // 0.5 vs 0.5000000000000001) collapse to one pillar instead of spawning a phantom column
    // that then fails the complete-grid check on an economically full chain.
    constexpr double kPillarTol = 1e-9;  // relative
    auto samePillar = [](double a, double b) {
        return std::abs(a - b) <= kPillarTol * std::max(1.0, std::max(std::abs(a), std::abs(b)));
    };
    auto distinctPillars = [&](std::vector<double> vals) {
        std::sort(vals.begin(), vals.end());
        std::vector<double> pillars;
        for (double v : vals)
            if (pillars.empty() || !samePillar(v, pillars.back()))
                pillars.push_back(v);
        return pillars;
    };
    // Nearest pillar to v (pillars sorted); merge tolerance guarantees an exact hit.
    auto pillarIndex = [](const std::vector<double>& pillars, double v) -> std::size_t {
        auto it = std::lower_bound(pillars.begin(), pillars.end(), v);
        std::size_t idx = (it == pillars.end()) ? pillars.size() - 1
                                                : static_cast<std::size_t>(it - pillars.begin());
        if (idx > 0 && std::abs(pillars[idx - 1] - v) <= std::abs(pillars[idx] - v))
            --idx;
        return idx;
    };

    std::vector<double> allMats, allStrikes;
    allMats.reserve(quotes.size());
    allStrikes.reserve(quotes.size());
    for (const auto& qt : quotes) { allMats.push_back(qt.maturity); allStrikes.push_back(qt.strike); }
    std::vector<double> maturities = distinctPillars(std::move(allMats));
    std::vector<double> strikes    = distinctPillars(std::move(allStrikes));

    const std::size_t nMat = maturities.size();
    const std::size_t nStrike = strikes.size();

    // Invert each quote to a BS implied vol and drop it in its grid cell.
    std::vector<std::vector<double>> vols(nMat, std::vector<double>(nStrike, 0.0));
    std::vector<std::vector<bool>>   filled(nMat, std::vector<bool>(nStrike, false));

    for (const auto& qt : quotes) {
        const std::size_t i = pillarIndex(maturities, qt.maturity);
        const std::size_t j = pillarIndex(strikes, qt.strike);
        if (filled[i][j])
            throw std::invalid_argument(
                "VolSurface::fromQuotes: duplicate quote for a (strike, maturity) cell");

        instruments::OptionParams p;
        p.spot          = spot;
        p.strike        = qt.strike;
        p.riskFreeRate  = r;
        p.dividendYield = q;
        p.volatility    = 0.0;  // unused; solved for
        p.maturity      = qt.maturity;
        p.type          = qt.type;
        p.exercise      = instruments::ExerciseType::European;

        vols[i][j]   = pricingengines::impliedVolatility(p, qt.marketPrice);
        filled[i][j] = true;
    }

    for (std::size_t i = 0; i < nMat; ++i)
        for (std::size_t j = 0; j < nStrike; ++j)
            if (!filled[i][j])
                throw std::invalid_argument(
                    "VolSurface::fromQuotes: quotes must form a complete rectangular "
                    "strike × maturity grid (missing cell)");

    return VolSurface(std::move(maturities), std::move(strikes), std::move(vols), strikeMethod);
}

} // namespace qf::termstructure
