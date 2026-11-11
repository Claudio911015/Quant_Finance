#include <gtest/gtest.h>
#include <qf/xva/exposure_profile.hpp>
#include <qf/xva/cva_calculator.hpp>
#include <qf/xva/credit_curve.hpp>
#include <qf/xva/netting_set.hpp>
#include <qf/models/hullwhite.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <algorithm>
#include <cmath>
#include <stdexcept>

using qf::instruments::SwapType;

namespace {

qf::termstructure::YieldCurve flatCurve(double r) {
    return qf::termstructure::YieldCurve({0.5, 1.0, 2.0, 5.0, 10.0}, {r, r, r, r, r});
}

std::vector<double> quarterlyDates(double maturity) {
    std::vector<double> d;
    for (double t = 0.25; t <= maturity + 1e-9; t += 0.25)
        d.push_back(t);
    return d;
}

// Two swaps of different maturity and direction: exposure has both a positive and a
// negative side, so EPE, ENE and PFE are all non-trivial.
qf::xva::NettingSet mixedNettingSet() {
    qf::xva::NettingSet ns;
    ns.add(1e6, 0.05, 5.0, 1.0, SwapType::Payer);
    ns.add(5e5, 0.03, 3.0, 2.0, SwapType::Receiver);
    return ns;
}

} // namespace

TEST(ExposureProfile, EpeAndEneMatchCVACalculatorProfile) {
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.01, curve);
    qf::xva::FlatHazardRate credit(0.02);
    qf::xva::SimParams params{500, quarterlyDates(5.0), 42u};
    const auto ns = mixedNettingSet();

    qf::core::MarketEnvironment env(curve);
    const auto cva = qf::xva::CVACalculator(hw, credit, 0.6, params).compute(ns, env);
    const auto pts = qf::xva::simulateExposure(hw, ns, params);

    ASSERT_EQ(pts.size(), cva.profile.size());
    for (std::size_t k = 0; k < pts.size(); ++k) {
        EXPECT_DOUBLE_EQ(pts[k].t, cva.profile[k].t);
        EXPECT_NEAR(pts[k].epe, cva.profile[k].epe, 1e-12 * std::max(1.0, std::abs(cva.profile[k].epe)));
        EXPECT_NEAR(pts[k].ene, cva.profile[k].ene, 1e-12 * std::max(1.0, std::abs(cva.profile[k].ene)));
    }
}

TEST(ExposureProfile, PfeIsNonNegativeAndMonotoneInQuantile) {
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.01, curve);
    qf::xva::SimParams params{500, quarterlyDates(5.0), 42u};
    const auto ns = mixedNettingSet();

    const auto p50 = qf::xva::simulateExposure(hw, ns, params, 0.5);
    const auto p95 = qf::xva::simulateExposure(hw, ns, params, 0.95);
    const auto p99 = qf::xva::simulateExposure(hw, ns, params, 0.99);

    ASSERT_EQ(p50.size(), p95.size());
    ASSERT_EQ(p95.size(), p99.size());
    bool someExposure = false;
    for (std::size_t k = 0; k < p95.size(); ++k) {
        EXPECT_GE(p50[k].pfe, 0.0);
        EXPECT_GE(p95[k].pfe, p50[k].pfe);
        EXPECT_GE(p99[k].pfe, p95[k].pfe);
        if (p99[k].pfe > 0.0) someExposure = true;
    }
    EXPECT_TRUE(someExposure); // guards against a vacuous all-zero profile
}

TEST(ExposureProfile, DefaultQuantileIs95Percent) {
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.01, curve);
    qf::xva::SimParams params{200, quarterlyDates(2.0), 7u};
    const auto ns = mixedNettingSet();

    const auto byDefault = qf::xva::simulateExposure(hw, ns, params);
    const auto explicit95 = qf::xva::simulateExposure(hw, ns, params, 0.95);
    ASSERT_EQ(byDefault.size(), explicit95.size());
    for (std::size_t k = 0; k < byDefault.size(); ++k)
        EXPECT_DOUBLE_EQ(byDefault[k].pfe, explicit95[k].pfe);
}

TEST(ExposureProfile, SinglePathPfeEqualsEpe) {
    // With one path the quantile index is ceil(q*1)-1 = 0: pfe is that single sample = epe.
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.01, curve);
    qf::xva::SimParams params{1, quarterlyDates(2.0), 42u};
    const auto ns = mixedNettingSet();

    for (double q : {0.01, 0.5, 0.95, 0.99}) {
        const auto pts = qf::xva::simulateExposure(hw, ns, params, q);
        for (const auto& pt : pts)
            EXPECT_DOUBLE_EQ(pt.pfe, pt.epe);
    }
}

TEST(ExposureProfile, SameSeedIsReproducible) {
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.01, curve);
    qf::xva::SimParams params{100, quarterlyDates(2.0), 123u};
    const auto ns = mixedNettingSet();

    const auto a = qf::xva::simulateExposure(hw, ns, params);
    const auto b = qf::xva::simulateExposure(hw, ns, params);
    ASSERT_EQ(a.size(), b.size());
    for (std::size_t k = 0; k < a.size(); ++k) {
        EXPECT_DOUBLE_EQ(a[k].epe, b[k].epe);
        EXPECT_DOUBLE_EQ(a[k].ene, b[k].ene);
        EXPECT_DOUBLE_EQ(a[k].pfe, b[k].pfe);
    }
}

TEST(ExposureProfile, EmptyNettingSetIsAllZero) {
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.01, curve);
    qf::xva::SimParams params{50, quarterlyDates(1.0), 42u};
    const qf::xva::NettingSet ns;

    const auto pts = qf::xva::simulateExposure(hw, ns, params);
    ASSERT_EQ(pts.size(), params.monitorDates.size());
    for (std::size_t k = 0; k < pts.size(); ++k) {
        EXPECT_DOUBLE_EQ(pts[k].t, params.monitorDates[k]);
        EXPECT_DOUBLE_EQ(pts[k].epe, 0.0);
        EXPECT_DOUBLE_EQ(pts[k].ene, 0.0);
        EXPECT_DOUBLE_EQ(pts[k].pfe, 0.0);
    }
}

TEST(ExposureProfile, InvalidQuantileThrows) {
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.01, curve);
    qf::xva::SimParams params{50, quarterlyDates(1.0), 42u};
    const auto ns = mixedNettingSet();

    EXPECT_THROW(qf::xva::simulateExposure(hw, ns, params, 0.0), std::invalid_argument);
    EXPECT_THROW(qf::xva::simulateExposure(hw, ns, params, 1.0), std::invalid_argument);
    EXPECT_THROW(qf::xva::simulateExposure(hw, ns, params, -0.1), std::invalid_argument);
    EXPECT_THROW(qf::xva::simulateExposure(hw, ns, params, 1.5), std::invalid_argument);
    EXPECT_THROW(qf::xva::simulateExposure(hw, ns, params, std::nan("")), std::invalid_argument);
}

TEST(ExposureProfile, InvalidSimParamsThrow) {
    auto curve = flatCurve(0.04);
    qf::models::HullWhite hw(0.1, 0.01, curve);
    const auto ns = mixedNettingSet();

    qf::xva::SimParams noDates{50, {}, 42u};
    EXPECT_THROW(qf::xva::simulateExposure(hw, ns, noDates), std::invalid_argument);

    qf::xva::SimParams zeroDate{50, {0.0, 1.0}, 42u};
    EXPECT_THROW(qf::xva::simulateExposure(hw, ns, zeroDate), std::invalid_argument);

    qf::xva::SimParams negativeDate{50, {-1.0, 1.0}, 42u};
    EXPECT_THROW(qf::xva::simulateExposure(hw, ns, negativeDate), std::invalid_argument);

    qf::xva::SimParams unsorted{50, {2.0, 1.0}, 42u};
    EXPECT_THROW(qf::xva::simulateExposure(hw, ns, unsorted), std::invalid_argument);

    qf::xva::SimParams noPaths{0, quarterlyDates(1.0), 42u};
    EXPECT_THROW(qf::xva::simulateExposure(hw, ns, noPaths), std::invalid_argument);
}
