#include <gtest/gtest.h>
#include <qf/termstructure/volsurface.hpp>
#include <qf/models/heston_calibrator.hpp>       // OptionQuote
#include <qf/pricingengines/blackscholes.hpp>
#include <qf/instruments/option.hpp>
#include <cmath>
#include <stdexcept>
#include <vector>

using qf::termstructure::VolSurface;
using qf::math::InterpolationMethod;
using qf::models::OptionQuote;
using qf::instruments::OptionParams;
using qf::instruments::OptionType;
using qf::instruments::ExerciseType;

namespace {

// A well-formed 3x3 grid whose total variance is non-decreasing in maturity.
VolSurface makeGrid(InterpolationMethod m = InterpolationMethod::Linear)
{
    std::vector<double> maturities = {0.5, 1.0, 2.0};
    std::vector<double> strikes    = {90.0, 100.0, 110.0};
    // Rows are maturity pillars; a mild skew per row, rising slightly with T.
    std::vector<std::vector<double>> vols = {
        {0.24, 0.20, 0.22},
        {0.25, 0.21, 0.23},
        {0.26, 0.22, 0.24},
    };
    return VolSurface(maturities, strikes, vols, m);
}

} // namespace

// ── Grid recovery: querying exactly at a (strike, maturity) pillar returns the input ──
TEST(VolSurface, RecoversGridValuesAtPillars)
{
    VolSurface s = makeGrid();
    const auto& mats = s.maturities();
    const auto& ks   = s.strikes();
    const auto& v    = s.vols();
    for (std::size_t i = 0; i < mats.size(); ++i)
        for (std::size_t j = 0; j < ks.size(); ++j)
            EXPECT_NEAR(s.vol(ks[j], mats[i]), v[i][j], 1e-12)
                << "pillar (" << i << "," << j << ")";
}

// ── Interpolation sanity: a mid-strike, mid-maturity mark lies in a sensible band ──
TEST(VolSurface, InterpolatesBetweenPillars)
{
    VolSurface s = makeGrid();
    // Strike 95 at maturity 0.75 — between pillars in both dimensions.
    double v = s.vol(95.0, 0.75);
    EXPECT_GT(v, 0.18);
    EXPECT_LT(v, 0.27);
    // Total variance must be monotone in maturity at a fixed strike (calendar-consistent).
    double w05 = s.vol(100.0, 0.5) * s.vol(100.0, 0.5) * 0.5;
    double w10 = s.vol(100.0, 1.0) * s.vol(100.0, 1.0) * 1.0;
    double w20 = s.vol(100.0, 2.0) * s.vol(100.0, 2.0) * 2.0;
    EXPECT_LE(w05, w10 + 1e-12);
    EXPECT_LE(w10, w20 + 1e-12);
}

// ── Flat strike extrapolation beyond the strike pillars (Interpolator semantics) ──
TEST(VolSurface, FlatStrikeExtrapolation)
{
    VolSurface s = makeGrid();
    // Below the lowest strike pillar, the smile is flat at the first strike's vol.
    EXPECT_NEAR(s.vol(50.0, 1.0), s.vol(90.0, 1.0), 1e-12);
    // Above the highest strike pillar, flat at the last strike's vol.
    EXPECT_NEAR(s.vol(200.0, 1.0), s.vol(110.0, 1.0), 1e-12);
}

// ── fromQuotes round-trip: build BS prices from a known vol grid, invert, recover ──
TEST(VolSurface, FromQuotesRoundTrip)
{
    const double spot = 100.0, r = 0.03, q = 0.01;
    std::vector<double> maturities = {0.5, 1.0, 2.0};
    std::vector<double> strikes    = {90.0, 100.0, 110.0};
    std::vector<std::vector<double>> trueVols = {
        {0.24, 0.20, 0.22},
        {0.25, 0.21, 0.23},
        {0.26, 0.22, 0.24},
    };

    std::vector<OptionQuote> quotes;
    for (std::size_t i = 0; i < maturities.size(); ++i)
        for (std::size_t j = 0; j < strikes.size(); ++j) {
            OptionParams p;
            p.spot = spot; p.strike = strikes[j]; p.riskFreeRate = r;
            p.dividendYield = q; p.volatility = trueVols[i][j];
            p.maturity = maturities[i]; p.type = OptionType::Call;
            p.exercise = ExerciseType::European;
            double px = qf::pricingengines::blackScholes(p).price;
            quotes.push_back({strikes[j], maturities[i], OptionType::Call, px});
        }

    VolSurface s = VolSurface::fromQuotes(spot, r, q, quotes);
    for (std::size_t i = 0; i < maturities.size(); ++i)
        for (std::size_t j = 0; j < strikes.size(); ++j)
            EXPECT_NEAR(s.vol(strikes[j], maturities[i]), trueVols[i][j], 1e-4)
                << "recovered vol at (" << i << "," << j << ")";
}

// ── Validation: non-positive vol is rejected ──
TEST(VolSurface, RejectsNonPositiveVol)
{
    std::vector<double> maturities = {0.5, 1.0};
    std::vector<double> strikes    = {90.0, 100.0};
    std::vector<std::vector<double>> vols = {{0.2, -0.1}, {0.2, 0.2}};
    EXPECT_THROW(VolSurface(maturities, strikes, vols), std::invalid_argument);
}

// ── Validation: decreasing total variance in T (calendar arbitrage) is rejected ──
TEST(VolSurface, RejectsCalendarArbitrage)
{
    std::vector<double> maturities = {1.0, 2.0};
    std::vector<double> strikes    = {90.0, 100.0};
    // At strike 90: w(1)=0.30²·1=0.09, w(2)=0.20²·2=0.08 < 0.09 → arbitrage.
    std::vector<std::vector<double>> vols = {{0.30, 0.20}, {0.20, 0.22}};
    EXPECT_THROW(VolSurface(maturities, strikes, vols), std::invalid_argument);
}

// ── Validation: ragged grid and too-few pillars are rejected ──
TEST(VolSurface, RejectsBadDimensions)
{
    std::vector<double> maturities = {0.5, 1.0};
    std::vector<double> strikes    = {90.0, 100.0};
    std::vector<std::vector<double>> ragged = {{0.2, 0.2}, {0.2}};
    EXPECT_THROW(VolSurface(maturities, strikes, ragged), std::invalid_argument);

    std::vector<double> oneMat = {1.0};
    std::vector<std::vector<double>> oneRow = {{0.2, 0.2}};
    EXPECT_THROW(VolSurface(oneMat, strikes, oneRow), std::invalid_argument);
}

// ── Validation: fromQuotes rejects an incomplete rectangular grid ──
TEST(VolSurface, FromQuotesRejectsIncompleteGrid)
{
    // Two maturities, two strikes, but one cell missing.
    std::vector<OptionQuote> quotes = {
        {90.0, 0.5, OptionType::Call, 12.0},
        {100.0, 0.5, OptionType::Call, 6.0},
        {90.0, 1.0, OptionType::Call, 15.0},
        // (100, 1.0) missing
    };
    EXPECT_THROW(VolSurface::fromQuotes(100.0, 0.03, 0.0, quotes), std::invalid_argument);
}

// ── vol() rejects non-positive maturity ──
TEST(VolSurface, VolRejectsNonPositiveMaturity)
{
    VolSurface s = makeGrid();
    EXPECT_THROW(s.vol(100.0, 0.0), std::invalid_argument);
    EXPECT_THROW(s.vol(100.0, -1.0), std::invalid_argument);
}
