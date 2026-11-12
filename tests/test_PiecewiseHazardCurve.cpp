#include <gtest/gtest.h>
#include <qf/xva/piecewise_hazard_curve.hpp>
#include <qf/xva/credit_curve.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/interpolation.hpp>
#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

using qf::xva::CdsQuote;
using qf::xva::FlatHazardRate;
using qf::xva::PiecewiseHazardCurve;
using qf::xva::bootstrapCdsCurve;
using qf::xva::cdsValue;

namespace {

// Linear zero curve around 7 %, extended to 15 years so 10y CDS quotes stay inside the pillars.
qf::termstructure::YieldCurve sevenPercent() {
    return qf::termstructure::YieldCurve(
        {0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0},
        {0.0680, 0.0685, 0.0690, 0.0700, 0.0705, 0.0710, 0.0715, 0.0720, 0.0730},
        qf::math::InterpolationMethod::Linear);
}

std::vector<CdsQuote> upwardSlope() {
    return {{1.0, 0.0050}, {2.0, 0.0080}, {3.0, 0.0110}, {5.0, 0.0150}, {7.0, 0.0180}, {10.0, 0.0200}};
}

std::vector<CdsQuote> highSpreads() {
    return {{1.0, 0.0800}, {2.0, 0.0900}, {3.0, 0.1000}, {5.0, 0.1100}, {7.0, 0.1150}, {10.0, 0.1200}};
}

std::vector<CdsQuote> nearlyFlat() {
    return {{1.0, 0.0100}, {2.0, 0.0100}, {3.0, 0.0101}, {5.0, 0.0101}, {7.0, 0.0102}, {10.0, 0.0102}};
}

void expectRepricesToZero(const std::vector<CdsQuote>& quotes, double recovery) {
    const auto yc = sevenPercent();
    const double notional = 1.0e6;
    const auto curve = bootstrapCdsCurve(quotes, recovery, yc);
    ASSERT_EQ(curve.hazards().size(), quotes.size());
    for (const auto& q : quotes) {
        EXPECT_LE(std::abs(cdsValue(q, recovery, curve, yc, notional)), 1e-8 * notional)
            << "tenor " << q.tenorYears << "y";
    }
}

} // namespace

TEST(PiecewiseHazardCurve, SurvivalAndHazardFollowPiecewiseConstantIntensity) {
    const PiecewiseHazardCurve c({1.0, 3.0}, {0.02, 0.05});
    EXPECT_DOUBLE_EQ(c.survivalProbability(0.0), 1.0);
    EXPECT_DOUBLE_EQ(c.survivalProbability(-1.0), 1.0);
    EXPECT_NEAR(c.survivalProbability(0.5), std::exp(-0.02 * 0.5), 1e-15);
    EXPECT_NEAR(c.survivalProbability(1.0), std::exp(-0.02), 1e-15);
    EXPECT_NEAR(c.survivalProbability(2.0), std::exp(-0.02 - 0.05), 1e-15);
    EXPECT_NEAR(c.survivalProbability(3.0), std::exp(-0.02 - 0.10), 1e-15);
    // Flat extrapolation of the last hazard past the last vertex.
    EXPECT_NEAR(c.survivalProbability(5.0), std::exp(-0.02 - 0.10 - 0.10), 1e-15);

    EXPECT_DOUBLE_EQ(c.hazardRate(0.5), 0.02);
    EXPECT_DOUBLE_EQ(c.hazardRate(1.0), 0.02);   // (times[i-1], times[i]] includes the right edge
    EXPECT_DOUBLE_EQ(c.hazardRate(1.0001), 0.05);
    EXPECT_DOUBLE_EQ(c.hazardRate(10.0), 0.05);
    ASSERT_EQ(c.times().size(), 2u);
    EXPECT_DOUBLE_EQ(c.times()[1], 3.0);
    EXPECT_DOUBLE_EQ(c.hazards()[0], 0.02);
}

TEST(PiecewiseHazardCurve, ConstructorRejectsInvalidInput) {
    EXPECT_THROW(PiecewiseHazardCurve({}, {}), std::invalid_argument);
    EXPECT_THROW(PiecewiseHazardCurve({1.0, 2.0}, {0.01}), std::invalid_argument);
    EXPECT_THROW(PiecewiseHazardCurve({0.0}, {0.01}), std::invalid_argument);
    EXPECT_THROW(PiecewiseHazardCurve({-1.0}, {0.01}), std::invalid_argument);
    EXPECT_THROW(PiecewiseHazardCurve({2.0, 1.0}, {0.01, 0.01}), std::invalid_argument);
    EXPECT_THROW(PiecewiseHazardCurve({1.0, 1.0}, {0.01, 0.01}), std::invalid_argument);
    EXPECT_THROW(PiecewiseHazardCurve({1.0}, {-0.001}), std::invalid_argument);
    EXPECT_THROW(PiecewiseHazardCurve({1.0}, {std::nan("")}), std::invalid_argument);
    EXPECT_NO_THROW(PiecewiseHazardCurve({1.0}, {0.0}));
}

// (i) Every input CDS reprices to zero with the bootstrapped curve.
TEST(PiecewiseHazardCurve, BootstrapRepricesUpwardSlopingQuotes) { expectRepricesToZero(upwardSlope(), 0.40); }
TEST(PiecewiseHazardCurve, BootstrapRepricesHighSpreadQuotes)     { expectRepricesToZero(highSpreads(), 0.40); }
TEST(PiecewiseHazardCurve, BootstrapRepricesNearlyFlatQuotes)     { expectRepricesToZero(nearlyFlat(), 0.40); }

TEST(PiecewiseHazardCurve, BootstrapRepricesWithOtherRecoveryAndNonQuarterlyTenors) {
    // 0.3y and 1.3y are not multiples of a quarter: the schedule ends in a stub at round(365 T).
    // 0.5y has its last premium on day 183 (182.5 rounded), a fraction of a day past the tenor.
    expectRepricesToZero({{0.5, 0.0040}, {1.3, 0.0070}, {2.0, 0.0090}, {4.5, 0.0130}}, 0.25);
    expectRepricesToZero({{0.3, 0.0060}, {1.0, 0.0070}}, 0.0);
}

// The tramo of each quote ends at the CDS's last premium date, which is the tenor itself for whole years.
TEST(PiecewiseHazardCurve, BootstrapVerticesAreLastPremiumDates) {
    const auto yc = sevenPercent();
    const auto whole = bootstrapCdsCurve(upwardSlope(), 0.40, yc);
    ASSERT_EQ(whole.times().size(), 6u);
    const double tenors[] = {1.0, 2.0, 3.0, 5.0, 7.0, 10.0};
    for (std::size_t i = 0; i < 6; ++i) EXPECT_DOUBLE_EQ(whole.times()[i], tenors[i]);

    const auto half = bootstrapCdsCurve({{0.5, 0.0040}, {1.0, 0.0050}}, 0.40, yc);
    EXPECT_DOUBLE_EQ(half.times()[0], 183.0 / 365.0);
    EXPECT_DOUBLE_EQ(half.times()[1], 1.0);

    // Two tenors that share the same last premium day cannot define two tramos.
    EXPECT_THROW(bootstrapCdsCurve({{0.5, 0.0040}, {0.5005, 0.0041}}, 0.40, yc), std::invalid_argument);
}

// (ii) A single quote is a flat curve: hazard ~ spread / (1 - R).
TEST(PiecewiseHazardCurve, SingleFlatQuoteGivesSpreadOverLgd) {
    const auto yc = sevenPercent();
    const double recovery = 0.40, spread = 0.0100;
    const auto curve = bootstrapCdsCurve({{5.0, spread}}, recovery, yc);
    ASSERT_EQ(curve.hazards().size(), 1u);
    EXPECT_DOUBLE_EQ(curve.times()[0], 5.0);
    const double expected = spread / (1.0 - recovery);
    EXPECT_NEAR(curve.hazards()[0], expected, 0.02 * expected);
}

// (iii) Survival is non-increasing on a 0..15y grid and stays in (0, 1].
TEST(PiecewiseHazardCurve, BootstrappedSurvivalIsDecreasingInUnitInterval) {
    const auto yc = sevenPercent();
    for (const auto& quotes : {upwardSlope(), highSpreads(), nearlyFlat()}) {
        const auto curve = bootstrapCdsCurve(quotes, 0.40, yc);
        EXPECT_DOUBLE_EQ(curve.survivalProbability(0.0), 1.0);
        double prev = 1.0;
        for (int k = 1; k <= 300; ++k) {                 // 0.05y steps up to 15y
            const double s = curve.survivalProbability(0.05 * k);
            EXPECT_GT(s, 0.0);
            EXPECT_LE(s, 1.0);
            EXPECT_LT(s, prev) << "t=" << 0.05 * k;
            prev = s;
        }
    }
}

// (iv) Quotes that need a negative hazard in a segment are rejected with a clear message.
TEST(PiecewiseHazardCurve, BootstrapRejectsQuotesImplyingNegativeHazard) {
    const auto yc = sevenPercent();
    try {
        bootstrapCdsCurve({{1.0, 0.0300}, {2.0, 0.0050}}, 0.40, yc);
        FAIL() << "expected std::invalid_argument";
    } catch (const std::invalid_argument& e) {
        const std::string msg = e.what();
        EXPECT_NE(msg.find("negative hazard"), std::string::npos) << msg;
        EXPECT_NE(msg.find("2y"), std::string::npos) << msg;
    }
}

// (v) Invalid inputs.
TEST(PiecewiseHazardCurve, BootstrapRejectsInvalidInput) {
    const auto yc = sevenPercent();
    EXPECT_THROW(bootstrapCdsCurve({}, 0.40, yc), std::invalid_argument);
    EXPECT_THROW(bootstrapCdsCurve({{1.0, 0.01}}, -0.1, yc), std::invalid_argument);
    EXPECT_THROW(bootstrapCdsCurve({{1.0, 0.01}}, 1.0, yc), std::invalid_argument);
    EXPECT_THROW(bootstrapCdsCurve({{1.0, 0.01}}, std::nan(""), yc), std::invalid_argument);
    EXPECT_THROW(bootstrapCdsCurve({{2.0, 0.01}, {1.0, 0.012}}, 0.40, yc), std::invalid_argument);  // not increasing
    EXPECT_THROW(bootstrapCdsCurve({{1.0, 0.01}, {1.0, 0.012}}, 0.40, yc), std::invalid_argument);  // repeated tenor
    EXPECT_THROW(bootstrapCdsCurve({{0.0, 0.01}}, 0.40, yc), std::invalid_argument);                // tenor <= 0
    EXPECT_THROW(bootstrapCdsCurve({{-1.0, 0.01}}, 0.40, yc), std::invalid_argument);
    EXPECT_THROW(bootstrapCdsCurve({{1.0, 0.0}}, 0.40, yc), std::invalid_argument);                 // spread <= 0
    EXPECT_THROW(bootstrapCdsCurve({{1.0, -0.01}}, 0.40, yc), std::invalid_argument);
    EXPECT_THROW(bootstrapCdsCurve({{1.0, std::nan("")}}, 0.40, yc), std::invalid_argument);
}

TEST(PiecewiseHazardCurve, CdsValueScalesWithNotionalAndHasProtectionBuyerSign) {
    const auto yc = sevenPercent();
    const FlatHazardRate flat(0.02);
    const CdsQuote q{5.0, 0.0120};                 // par spread would be ~ 0.02 * 0.6 = 0.012
    const double v1 = cdsValue(q, 0.40, flat, yc);
    EXPECT_NEAR(cdsValue(q, 0.40, flat, yc, 2.5e6), 2.5e6 * v1, 1e-9 * 2.5e6);
    EXPECT_NEAR(v1, 0.0, 5e-4);                    // near par: small value

    // Paying more than par makes the protection buyer's value negative; less than par, positive.
    EXPECT_LT(cdsValue({5.0, 0.0200}, 0.40, flat, yc), 0.0);
    EXPECT_GT(cdsValue({5.0, 0.0050}, 0.40, flat, yc), 0.0);
    // A riskless counterparty gives no protection value: only the premium is left.
    EXPECT_LT(cdsValue(q, 0.40, FlatHazardRate(0.0), yc), 0.0);
}

TEST(PiecewiseHazardCurve, CdsValueRejectsInvalidInput) {
    const auto yc = sevenPercent();
    const FlatHazardRate flat(0.02);
    EXPECT_THROW(cdsValue({5.0, 0.01}, 1.0, flat, yc), std::invalid_argument);
    EXPECT_THROW(cdsValue({5.0, 0.01}, -0.5, flat, yc), std::invalid_argument);
    EXPECT_THROW(cdsValue({0.0, 0.01}, 0.40, flat, yc), std::invalid_argument);
    EXPECT_THROW(cdsValue({-2.0, 0.01}, 0.40, flat, yc), std::invalid_argument);
    EXPECT_THROW(cdsValue({5.0, std::nan("")}, 0.40, flat, yc), std::invalid_argument);
}
