#include <gtest/gtest.h>
#include <qf/models/irate_model.hpp>
#include <qf/models/vasicek.hpp>
#include <qf/models/hullwhite.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/interpolation.hpp>
#include <memory>
#include <cmath>
using namespace qf::models;
using namespace qf::termstructure;
using namespace qf::math;

namespace {
    YieldCurve testCurve() {
        return YieldCurve({0.5,1.0,2.0,5.0,10.0},
                          {0.03,0.035,0.04,0.045,0.05},
                          InterpolationMethod::CubicSpline);
    }
}

TEST(IRateModel, VasicekIsIRateModel) {
    std::shared_ptr<IRateModel> m = std::make_shared<Vasicek>(0.5, 0.05, 0.01, 0.03);
    EXPECT_GT(m->bondPrice(1.0), 0.0);
    EXPECT_GT(m->zeroRate(1.0), 0.0);
    EXPECT_EQ(m->simulate(1.0, 10, 42).size(), 11u);
}

TEST(IRateModel, HullWhiteIsIRateModel) {
    auto curve = testCurve();
    std::shared_ptr<IRateModel> m = std::make_shared<HullWhite>(0.1, 0.015, curve);
    EXPECT_NEAR(m->bondPrice(1.0), curve.discountFactor(1.0), 1e-12);
    EXPECT_GT(m->zeroRate(1.0), 0.0);
    EXPECT_EQ(m->simulate(1.0, 10, 42).size(), 11u);
}

TEST(IRateModel, PolymorphicDispatch) {
    auto curve = testCurve();
    std::vector<std::shared_ptr<IRateModel>> models;
    models.push_back(std::make_shared<Vasicek>(0.5, 0.05, 0.01, 0.03));
    models.push_back(std::make_shared<HullWhite>(0.1, 0.015, curve));
    for (auto& m : models) {
        EXPECT_GT(m->bondPrice(5.0), 0.0);
        EXPECT_LT(m->bondPrice(5.0), 1.0);
        auto path = m->simulate(1.0, 50, 42);
        EXPECT_EQ(path.size(), 51u);
    }
}
