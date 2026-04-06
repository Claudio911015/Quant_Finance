#include <qf/models/hullwhite.hpp>
#include <cmath>
#include <random>
#include <stdexcept>

namespace qf::models {

HullWhite::HullWhite(double a, double sigma, const termstructure::YieldCurve& curve)
    : a_(a), sigma_(sigma), curve_(curve)
{
    if (a <= 0.0)
        throw std::invalid_argument("HullWhite: mean reversion speed a must be positive");
    if (sigma <= 0.0)
        throw std::invalid_argument("HullWhite: volatility sigma must be positive");
}

double HullWhite::B(double T) const
{
    return (1.0 - std::exp(-a_ * T)) / a_;
}

double HullWhite::A(double T) const
{
    // Hull-White at t=0 is calibrated to match the market curve exactly:
    //   P_HW(0,T) = A(T) * exp(-B(T) * r0)
    // where r0 is the short rate from the market curve.
    // A(T) = P_market(0,T) * exp(B(T) * f(0,0) - sigma^2/(4a) * (1-exp(-2a*0)) * B(T)^2)
    // At t=0 the variance correction term vanishes, giving:
    //   A(T) = P_market(0,T) * exp(B(T) * r0)
    double r0 = curve_.zeroRate(1e-4);  // instantaneous rate approximation
    return curve_.discountFactor(T) * std::exp(B(T) * r0);
}

double HullWhite::bondPrice(double T) const
{
    if (T <= 0.0)
        throw std::invalid_argument("HullWhite::bondPrice: T must be positive");
    // By construction, Hull-White matches the market curve at t=0
    return curve_.discountFactor(T);
}

double HullWhite::zeroRate(double T) const
{
    if (T <= 0.0)
        throw std::invalid_argument("HullWhite::zeroRate: T must be positive");
    return curve_.zeroRate(T);
}

double HullWhite::theta(double t) const
{
    const double dt = 1e-5;
    // Ensure T1 > 0 for forwardRate calls (YieldCurve requires positive maturities)
    double t0 = std::max(t, dt);
    double f1 = curve_.forwardRate(t0, t0 + dt);
    double f0 = (t0 > dt) ? curve_.forwardRate(t0 - dt, t0) : f1;
    double dfdt = (f1 - f0) / dt;
    double ft = curve_.forwardRate(t0, t0 + 1e-4);
    return dfdt + a_ * ft + (sigma_ * sigma_ / (2.0 * a_)) * (1.0 - std::exp(-2.0 * a_ * t));
}

std::vector<double> HullWhite::simulate(double T, int steps, unsigned seed) const
{
    std::mt19937_64 rng(seed);
    std::normal_distribution<double> N(0.0, 1.0);
    double dt = T / steps;
    double sqdt = std::sqrt(dt);
    double r0 = curve_.zeroRate(1e-4);
    std::vector<double> path(steps + 1);
    path[0] = r0;
    for (int i = 0; i < steps; ++i) {
        double t = i * dt;
        path[i + 1] = path[i] + (theta(t) - a_ * path[i]) * dt + sigma_ * sqdt * N(rng);
    }
    return path;
}

} // namespace qf::models
