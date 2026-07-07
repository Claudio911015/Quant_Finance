#include <gtest/gtest.h>
#include <qf/math/interpolation.hpp>
#include <qf/math/rootfinding.hpp>
#include <qf/math/integration.hpp>
#include <qf/math/optimization.hpp>
#include <cmath>
#include <vector>

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

TEST(Interpolation, CubicSplineTwoPointsIsLinear) {
    // Regression: with exactly 2 points the cubic setup had m = n-2 = 0 interior nodes and
    // requested a vector of size m-1 = SIZE_MAX, throwing a spurious length_error. A natural
    // cubic spline over 2 points is just the straight line between them.
    Interpolator interp({1.0, 3.0}, {10.0, 30.0}, InterpolationMethod::CubicSpline);
    EXPECT_NEAR(interp(1.0), 10.0, 1e-12);
    EXPECT_NEAR(interp(3.0), 30.0, 1e-12);
    EXPECT_NEAR(interp(2.0), 20.0, 1e-12);   // linear midpoint
}

TEST(Interpolation, CubicSplineThreePointsWorks) {
    // n=3 → m=1 interior node: exercised the m-1=0 empty-band boundary too.
    Interpolator interp({0.0, 1.0, 2.0}, {0.0, 1.0, 4.0}, InterpolationMethod::CubicSpline);
    EXPECT_NEAR(interp(0.0), 0.0, 1e-12);
    EXPECT_NEAR(interp(1.0), 1.0, 1e-12);
    EXPECT_NEAR(interp(2.0), 4.0, 1e-12);
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

// ═══════════════════════════════════════════════════════════════════════════
// Integration
// ═══════════════════════════════════════════════════════════════════════════

TEST(Integration, SimpsonPolynomial) {
    // ∫₀¹ x² dx = 1/3 (Simpson is exact for polynomials up to degree 3)
    auto f = [](double x) { return x * x; };
    EXPECT_NEAR(simpson(f, 0.0, 1.0, 100), 1.0 / 3.0, 1e-12);
}

TEST(Integration, SimpsonSine) {
    // ∫₀^π sin(x) dx = 2
    auto f = [](double x) { return std::sin(x); };
    EXPECT_NEAR(simpson(f, 0.0, M_PI, 1000), 2.0, 1e-10);
}

TEST(Integration, SimpsonExponential) {
    // ∫₀¹ e^x dx = e - 1
    auto f = [](double x) { return std::exp(x); };
    EXPECT_NEAR(simpson(f, 0.0, 1.0, 100), std::exp(1.0) - 1.0, 1e-10);
}

TEST(Integration, SimpsonInvalidN) {
    auto f = [](double x) { return x; };
    EXPECT_THROW(simpson(f, 0.0, 1.0, 3), std::invalid_argument);   // odd
    EXPECT_THROW(simpson(f, 0.0, 1.0, 0), std::invalid_argument);   // zero
}

TEST(Integration, GaussLegendrePolynomial) {
    // ∫₀¹ x³ dx = 1/4
    auto f = [](double x) { return x * x * x; };
    EXPECT_NEAR(gaussLegendre(f, 0.0, 1.0, 16), 0.25, 1e-12);
}

TEST(Integration, GaussLegendreSine) {
    // ∫₀^π sin(x) dx = 2
    auto f = [](double x) { return std::sin(x); };
    EXPECT_NEAR(gaussLegendre(f, 0.0, M_PI, 32), 2.0, 1e-12);
}

TEST(Integration, GaussLegendreGaussian) {
    // ∫₋₃³ e^(-x²) dx ≈ √π * erf(3) ≈ 1.7320...
    auto f = [](double x) { return std::exp(-x * x); };
    double expected = std::sqrt(M_PI) * std::erf(3.0);
    EXPECT_NEAR(gaussLegendre(f, -3.0, 3.0, 32), expected, 1e-10);
}

// ═══════════════════════════════════════════════════════════════════════════
// Nelder-Mead optimization
// ═══════════════════════════════════════════════════════════════════════════

TEST(NelderMead, ShiftedQuadraticMinimum) {
    // f(x,y) = (x-3)^2 + (y+2)^2, minimum at (3, -2) with f = 0.
    auto f = [](const std::vector<double>& v) {
        return (v[0] - 3.0) * (v[0] - 3.0) + (v[1] + 2.0) * (v[1] + 2.0);
    };
    auto res = nelderMead(f, {0.0, 0.0}, 1e-10, 2000);
    EXPECT_TRUE(res.converged);
    EXPECT_NEAR(res.x[0],  3.0, 1e-4);
    EXPECT_NEAR(res.x[1], -2.0, 1e-4);
    EXPECT_NEAR(res.fmin,  0.0, 1e-8);
}

TEST(NelderMead, RosenbrockRecovery) {
    // Classic banana valley; global min at (1, 1) with f = 0.
    auto rosen = [](const std::vector<double>& v) {
        double a = 1.0 - v[0];
        double b = v[1] - v[0] * v[0];
        return a * a + 100.0 * b * b;
    };
    auto res = nelderMead(rosen, {-1.2, 1.0}, 1e-12, 5000);
    EXPECT_TRUE(res.converged);
    EXPECT_NEAR(res.x[0], 1.0, 1e-3);
    EXPECT_NEAR(res.x[1], 1.0, 1e-3);
}

TEST(NelderMead, StarvedIterationsDoNotConverge) {
    auto rosen = [](const std::vector<double>& v) {
        double a = 1.0 - v[0];
        double b = v[1] - v[0] * v[0];
        return a * a + 100.0 * b * b;
    };
    auto res = nelderMead(rosen, {-1.2, 1.0}, 1e-12, 1);
    EXPECT_FALSE(res.converged);
    EXPECT_EQ(res.iterations, 1);
}

TEST(NelderMead, EmptyStartThrows) {
    auto f = [](const std::vector<double>& v) { return v.empty() ? 0.0 : v[0]; };
    EXPECT_THROW(nelderMead(f, {}, 1e-8, 100), std::invalid_argument);
}
