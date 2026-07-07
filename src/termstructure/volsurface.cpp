#include <qf/termstructure/volsurface.hpp>

#include <algorithm>
#include <cmath>
#include <map>
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

    // 2. Term structure: interpolate total variance linearly in maturity (flat
    //    extrapolation on w beyond the pillars), then back out the vol.
    math::Interpolator tvar(maturities_, totalVar, math::InterpolationMethod::Linear);
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

    // Distinct, sorted maturity and strike pillars found in the chain.
    std::map<double, std::size_t> matIndex;
    std::map<double, std::size_t> strikeIndex;
    for (const auto& qt : quotes) {
        matIndex.emplace(qt.maturity, 0);
        strikeIndex.emplace(qt.strike, 0);
    }
    std::vector<double> maturities;
    maturities.reserve(matIndex.size());
    for (auto& kv : matIndex) { kv.second = maturities.size(); maturities.push_back(kv.first); }
    std::vector<double> strikes;
    strikes.reserve(strikeIndex.size());
    for (auto& kv : strikeIndex) { kv.second = strikes.size(); strikes.push_back(kv.first); }

    const std::size_t nMat = maturities.size();
    const std::size_t nStrike = strikes.size();

    // Invert each quote to a BS implied vol and drop it in its grid cell.
    std::vector<std::vector<double>> vols(nMat, std::vector<double>(nStrike, 0.0));
    std::vector<std::vector<bool>>   filled(nMat, std::vector<bool>(nStrike, false));

    for (const auto& qt : quotes) {
        const std::size_t i = matIndex.at(qt.maturity);
        const std::size_t j = strikeIndex.at(qt.strike);
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
