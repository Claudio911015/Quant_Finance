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

// ── Maturity extrapolation must be calendar-consistent (flat-in-vol), not flat-in-w ──
// Regression for the review finding: flat total-variance extrapolation blows σ = √(w/T) up
// as T→0 below the first pillar and collapses it above the last. The correct behaviour
// anchors (T=0, w=0) at the short end (→ first-pillar vol) and holds vol flat at the long end.
TEST(VolSurface, MaturityExtrapolationIsFlatInVol)
{
    // Flat 20% ATM surface: first pillar 6M, last pillar 2Y. Every mark should stay ~20%.
    std::vector<double> maturities = {0.5, 2.0};
    std::vector<double> strikes    = {90.0, 100.0, 110.0};
    std::vector<std::vector<double>> vols = {
        {0.20, 0.20, 0.20},
        {0.20, 0.20, 0.20},
    };
    VolSurface s(maturities, strikes, vols);

    // Below the first pillar: a 1-week and 1-month option must mark at ~20%, not 100%/49%.
    EXPECT_NEAR(s.vol(100.0, 1.0 / 52.0), 0.20, 1e-9);
    EXPECT_NEAR(s.vol(100.0, 1.0 / 12.0), 0.20, 1e-9);
    // At the first pillar exactly.
    EXPECT_NEAR(s.vol(100.0, 0.5), 0.20, 1e-12);
    // Above the last pillar: a 10Y option must mark at ~20%, not decay to ~9%.
    EXPECT_NEAR(s.vol(100.0, 10.0), 0.20, 1e-9);
    // At the last pillar exactly.
    EXPECT_NEAR(s.vol(100.0, 2.0), 0.20, 1e-12);
}

// ── With a non-flat term structure the short-end anchor gives exactly the first pillar vol ──
TEST(VolSurface, ShortEndAnchorReturnsFirstPillarVol)
{
    VolSurface s = makeGrid();  // first maturity pillar 0.5
    // Any maturity strictly inside (0, 0.5) marks flat-in-vol at the 0.5 pillar's smile vol.
    for (double T : {0.01, 0.1, 0.25, 0.49}) {
        EXPECT_NEAR(s.vol(100.0, T), s.vol(100.0, 0.5), 1e-12) << "T=" << T;
        EXPECT_NEAR(s.vol(95.0,  T), s.vol(95.0,  0.5), 1e-12) << "T=" << T;
    }
}

// ── CubicSpline strike interpolation with exactly 2 strike pillars must not throw ──
// Regression: the Interpolator cubic setup underflowed (m=0 → upper(SIZE_MAX)) and threw a
// spurious length_error. Two strike pillars is the documented minimum; a cubic smile over
// two points degenerates to the straight line between them.
TEST(VolSurface, CubicSplineWithTwoStrikesIsLinear)
{
    std::vector<double> maturities = {0.5, 1.0};
    std::vector<double> strikes    = {90.0, 110.0};
    std::vector<std::vector<double>> vols = {
        {0.20, 0.24},
        {0.21, 0.25},
    };
    VolSurface s(maturities, strikes, vols, InterpolationMethod::CubicSpline);
    // Recovers the pillars.
    EXPECT_NEAR(s.vol(90.0, 0.5), 0.20, 1e-12);
    EXPECT_NEAR(s.vol(110.0, 0.5), 0.24, 1e-12);
    // Midpoint strike 100 at maturity 0.5 is the linear midpoint of the two-point smile.
    EXPECT_NEAR(s.vol(100.0, 0.5), 0.22, 1e-9);
}

// ── fromQuotes tolerates floating-point noise in pillar values ──
// Regression: exact-double pillar dedup split noisy-but-equal maturities into phantom columns
// and then threw "missing cell" on an economically complete grid.
TEST(VolSurface, FromQuotesMergesFloatingPointNoisyPillars)
{
    const double spot = 100.0, r = 0.03, q = 0.01;
    // Two maturities, but the "0.5" pillar arrives with a 1-ULP wobble across quotes, and
    // likewise the "100" strike. A complete 2x2 grid economically.
    const double half     = 0.5;
    const double halfNoisy = std::nextafter(0.5, 1.0);   // 0.5000000000000001
    const double k100      = 100.0;
    const double k100Noisy = std::nextafter(100.0, 200.0);

    std::vector<std::pair<double,double>> grid = {
        {90.0, half}, {k100, halfNoisy},
        {90.0, 1.0},  {k100Noisy, 1.0},
    };

    const double trueVol = 0.22;
    std::vector<OptionQuote> quotes;
    for (auto& [K, T] : grid) {
        OptionParams p;
        p.spot = spot; p.strike = K; p.riskFreeRate = r; p.dividendYield = q;
        p.volatility = trueVol; p.maturity = T; p.type = OptionType::Call;
        p.exercise = ExerciseType::European;
        double px = qf::pricingengines::blackScholes(p).price;
        quotes.push_back({K, T, OptionType::Call, px});
    }

    // Must build (2 maturities x 2 strikes), not throw on a phantom split.
    VolSurface s = VolSurface::fromQuotes(spot, r, q, quotes);
    EXPECT_EQ(s.maturities().size(), 2u);
    EXPECT_EQ(s.strikes().size(), 2u);
    EXPECT_NEAR(s.vol(100.0, 0.5), trueVol, 1e-3);
}
