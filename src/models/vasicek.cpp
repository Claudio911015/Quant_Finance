#include <qf/models/vasicek.hpp>
#include <cmath>
#include <random>
#include <stdexcept>
#include <vector>

namespace qf::models {

Vasicek::Vasicek(double a, double b, double sigma, double r0)
    : a_(a), b_(b), sigma_(sigma), r0_(r0)
{
    if (a <= 0.0)
        throw std::invalid_argument("Vasicek: mean reversion speed a must be positive");
    if (sigma <= 0.0)
        throw std::invalid_argument("Vasicek: volatility sigma must be positive");
}

double Vasicek::bondPrice(double T) const
{
    if (T <= 0.0)
        throw std::invalid_argument("Vasicek::bondPrice: T must be positive");

    double B = (1.0 - std::exp(-a_ * T)) / a_;
    double A = std::exp(
        (B - T) * (a_ * a_ * b_ - 0.5 * sigma_ * sigma_) / (a_ * a_)
        - sigma_ * sigma_ * B * B / (4.0 * a_));

    return A * std::exp(-B * r0_);
}

double Vasicek::zeroRate(double T) const
{
    if (T <= 0.0)
        throw std::invalid_argument("Vasicek::zeroRate: T must be positive");
    return -std::log(bondPrice(T)) / T;
}

std::vector<double> Vasicek::simulate(double T, int steps, unsigned seed) const
{
    if (T <= 0.0 || steps <= 0)
        throw std::invalid_argument("Vasicek::simulate: T and steps must be positive");

    std::mt19937_64 rng(seed);
    std::normal_distribution<double> N(0.0, 1.0);

    double dt = T / steps;
    double sqdt = std::sqrt(dt);

    std::vector<double> path(steps + 1);
    path[0] = r0_;

    for (int i = 0; i < steps; ++i)
        path[i + 1] = path[i] + a_ * (b_ - path[i]) * dt + sigma_ * sqdt * N(rng);

    return path;
}

double Vasicek::conditionalBondPrice(double t, double T, double r_t) const {
    if (T <= t) throw std::invalid_argument("Vasicek::conditionalBondPrice: T must be > t");
    double tau = T - t;
    double B   = (1.0 - std::exp(-a_ * tau)) / a_;
    double lnA = ((B - tau) * (a_ * a_ * b_ - 0.5 * sigma_ * sigma_)) / (a_ * a_)
               - (sigma_ * sigma_ * B * B) / (4.0 * a_);
    return std::exp(lnA - B * r_t);
}

} // namespace qf::models
