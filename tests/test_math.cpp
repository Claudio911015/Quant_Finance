#include <gtest/gtest.h>
#include <qf/math/interpolation.hpp>
#include <qf/math/rootfinding.hpp>
#include <cmath>

using namespace qf::math;

// ═══════════════════════════════════════════════════════════════════════════
// Interpolation
// ═══════════════════════════════════════════════════════════════════════════

TEST(Interpolation, LinearExactAtKnots) {
    Interpolator interp({0.0, 1.0, 2.0}, {0.0, 1.0, 4.0}, InterpolationMethod::Linear);
    EXPECT_DOUBLE_EQ(interp(0.0), 0.0);
    EXPECT_DOUBLE_EQ(interp(1.0), 1.0);
    EXPECT_DOUBLE_EQ(interp(2.0), 4.0);
}

TEST(Interpolation, LinearMidpoint) {
    Interpolator interp({0.0, 2.0}, {0.0, 4.0}, InterpolationMethod::Linear);
    EXPECT_NEAR(interp(1.0), 2.0, 1e-12);
}

TEST(Interpolation, LinearClampsBelowLowerBound) {
    Interpolator interp({1.0, 2.0}, {10.0, 20.0}, InterpolationMethod::Linear);
    EXPECT_DOUBLE_EQ(interp(0.0), 10.0);
}

TEST(Interpolation, LinearClampsAboveUpperBound) {
    Interpolator interp({1.0, 2.0}, {10.0, 20.0}, InterpolationMethod::Linear);
    EXPECT_DOUBLE_EQ(interp(5.0), 20.0);
}

TEST(Interpolation, CubicSplineExactAtKnots) {
    std::vector<double> x = {0.0, 1.0, 2.0, 3.0, 4.0};
    std::vector<double> y = {0.0, 1.0, 4.0, 9.0, 16.0};  // y = x^2
    Interpolator interp(x, y, InterpolationMethod::CubicSpline);
    for (std::size_t i = 0; i < x.size(); ++i)
        EXPECT_NEAR(interp(x[i]), y[i], 1e-10);
}

TEST(Interpolation, CubicSplineSmoothBetweenKnots) {
    // For a quadratic y=x^2 the cubic spline should be very accurate
    std::vector<double> x = {0.0, 1.0, 2.0, 3.0, 4.0};
    std::vector<double> y = {0.0, 1.0, 4.0, 9.0, 16.0};
    Interpolator interp(x, y, InterpolationMethod::CubicSpline);
    EXPECT_NEAR(interp(1.5), 2.25, 0.05);   // 1.5^2 = 2.25
    EXPECT_NEAR(interp(2.5), 6.25, 0.05);   // 2.5^2 = 6.25
}

TEST(Interpolation, LogLinearExactAtKnots) {
    std::vector<double> x = {1.0, 2.0, 3.0};
    std::vector<double> y = {1.0, std::exp(1.0), std::exp(2.0)};
    Interpolator interp(x, y, InterpolationMethod::LogLinear);
    EXPECT_NEAR(interp(1.0), y[0], 1e-10);
    EXPECT_NEAR(interp(2.0), y[1], 1e-10);
    EXPECT_NEAR(interp(3.0), y[2], 1e-10);
}

TEST(Interpolation, InvalidInputThrows) {
    EXPECT_THROW(Interpolator({1.0}, {1.0}), std::invalid_argument);          // < 2 points
    EXPECT_THROW(Interpolator({2.0, 1.0}, {1.0, 2.0}), std::invalid_argument); // not sorted
    EXPECT_THROW(Interpolator({1.0, 1.0}, {1.0, 2.0}), std::invalid_argument); // duplicate x
}

// ═══════════════════════════════════════════════════════════════════════════
// Root finding
// ═══════════════════════════════════════════════════════════════════════════

TEST(RootFinding, NewtonRaphsonSquareRoot) {
    // f(x) = x^2 - 2, root = sqrt(2)
    auto f  = [](double x) { return x*x - 2.0; };
    auto df = [](double x) { return 2.0*x; };
    double root = newtonRaphson(f, df, 1.0);
    EXPECT_NEAR(root, std::sqrt(2.0), 1e-8);
}

TEST(RootFinding, NewtonRaphsonCubic) {
    // f(x) = x^3 - x - 2, root ≈ 1.5214
    auto f  = [](double x) { return x*x*x - x - 2.0; };
    auto df = [](double x) { return 3.0*x*x - 1.0; };
    double root = newtonRaphson(f, df, 1.5);
    EXPECT_NEAR(f(root), 0.0, 1e-8);
}

TEST(RootFinding, BrentSquareRoot) {
    auto f = [](double x) { return x*x - 2.0; };
    double root = brent(f, 1.0, 2.0);
    EXPECT_NEAR(root, std::sqrt(2.0), 1e-8);
}

TEST(RootFinding, BrentSine) {
    // sin(x) = 0 near x = π
    auto f = [](double x) { return std::sin(x); };
    double root = brent(f, 3.0, 4.0);
    EXPECT_NEAR(root, M_PI, 1e-8);
}

TEST(RootFinding, BrentRequiresBracket) {
    auto f = [](double x) { return x*x + 1.0; }; // no real root
    EXPECT_THROW(brent(f, 0.0, 1.0), std::invalid_argument);
}
