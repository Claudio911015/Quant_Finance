#include <gtest/gtest.h>
#include <qf/models/heston_calibrator.hpp>
#include <qf/pricingengines/heston.hpp>
#include <qf/instruments/option.hpp>
#include <cmath>
#include <vector>

using namespace qf::models;
using qf::pricingengines::HestonParams;
using qf::pricingengines::hestonPrice;
using qf::instruments::OptionParams;
using qf::instruments::OptionType;
using qf::instruments::ExerciseType;

namespace {

// Generate synthetic call quotes from a known parameter set on a strike x
// maturity grid, so calibration can be checked as an exact round-trip.
std::vector<OptionQuote> makeSyntheticQuotes(
    double spot, double r, double q, const HestonParams& truth)
{
    std::vector<OptionQuote> quotes;
    const std::vector<double> strikes    = {90, 100, 110};
    const std::vector<double> maturities = {0.5, 1.0, 2.0};
    for (double T : maturities) {
        for (double K : strikes) {
            OptionParams p;
            p.spot          = spot;
            p.strike        = K;
            p.riskFreeRate  = r;
            p.dividendYield = q;
            p.volatility    = 0.0;
            p.maturity      = T;
            p.type          = OptionType::Call;
            p.exercise      = ExerciseType::European;
            double px = hestonPrice(p, truth);
            quotes.push_back({K, T, OptionType::Call, px});
        }
    }
    return quotes;
}

} // namespace

TEST(HestonCalibration, SyntheticRoundTripRecoversParams) {
    const double spot = 100.0, r = 0.03, q = 0.0;
    HestonParams truth{0.04, 1.5, 0.05, 0.4, -0.6};

    auto quotes = makeSyntheticQuotes(spot, r, q, truth);

    // Perturb the initial guess well away from truth.
    HestonParams guess{0.06, 1.0, 0.06, 0.5, -0.3};

    HestonCalibrator calib(spot, r, q);
    auto res = calib.calibrate(quotes, guess, CalibrationObjective::Price,
                               /*vegaWeighted=*/false, 1e-10, 5000);

    EXPECT_TRUE(res.converged);
    EXPECT_LT(res.rmse, 1e-3);
    EXPECT_EQ(res.perQuoteErrors.size(), quotes.size());

    // Loose recovery tolerances: Heston objectives are shallow in some params.
    EXPECT_NEAR(res.params.v0,    truth.v0,    5e-3);
    EXPECT_NEAR(res.params.theta, truth.theta, 5e-3);
    EXPECT_NEAR(res.params.rho,   truth.rho,   0.1);
    EXPECT_NEAR(res.params.sigma, truth.sigma, 0.15);
    EXPECT_GT(res.params.kappa,   0.0);
}

TEST(HestonCalibration, RepricesQuotesWithinTolerance) {
    const double spot = 100.0, r = 0.03, q = 0.0;
    HestonParams truth{0.04, 2.0, 0.04, 0.3, -0.7};
    auto quotes = makeSyntheticQuotes(spot, r, q, truth);
    HestonParams guess{0.05, 1.5, 0.05, 0.4, -0.5};

    HestonCalibrator calib(spot, r, q);
    auto res = calib.calibrate(quotes, guess);

    // Every fitted price should reproduce its quote to sub-cent accuracy.
    for (double e : res.perQuoteErrors)
        EXPECT_LT(std::abs(e), 0.05);
}

TEST(HestonCalibration, ImpliedVolObjectiveRoundTrip) {
    const double spot = 100.0, r = 0.03, q = 0.0;
    HestonParams truth{0.04, 1.5, 0.05, 0.4, -0.6};
    auto quotes = makeSyntheticQuotes(spot, r, q, truth);
    HestonParams guess{0.05, 1.2, 0.06, 0.5, -0.4};

    HestonCalibrator calib(spot, r, q);
    auto res = calib.calibrate(quotes, guess, CalibrationObjective::ImpliedVol,
                               false, 1e-10, 5000);
    EXPECT_TRUE(res.converged);
    EXPECT_LT(res.rmse, 1e-3);   // IV-space RMSE
}

TEST(HestonCalibration, EmptyQuotesThrows) {
    HestonCalibrator calib(100.0, 0.03, 0.0);
    HestonParams guess{0.04, 1.5, 0.05, 0.4, -0.6};
    EXPECT_THROW(calib.calibrate({}, guess), std::invalid_argument);
}

TEST(HestonCalibration, SingleQuoteRunsAndSizesErrors) {
    const double spot = 100.0, r = 0.03, q = 0.0;
    HestonParams truth{0.04, 1.5, 0.05, 0.4, -0.6};
    OptionParams p;
    p.spot = spot; p.strike = 100.0; p.riskFreeRate = r; p.dividendYield = q;
    p.volatility = 0.0; p.maturity = 1.0; p.type = OptionType::Call;
    p.exercise = ExerciseType::European;
    double px = hestonPrice(p, truth);

    std::vector<OptionQuote> quotes{{100.0, 1.0, OptionType::Call, px}};
    HestonCalibrator calib(spot, r, q);
    auto res = calib.calibrate(quotes, HestonParams{0.05, 1.2, 0.06, 0.5, -0.4});
    EXPECT_EQ(res.perQuoteErrors.size(), 1u);
}
