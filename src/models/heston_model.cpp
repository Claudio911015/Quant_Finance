#include <qf/models/heston_model.hpp>
#include <random>
#include <cmath>
#include <stdexcept>

namespace qf::models {

HestonModel::HestonModel(const HestonParams& p) : params_(p) {
    if (p.v0 <= 0.0 || p.theta <= 0.0 || p.kappa <= 0.0)
        throw std::invalid_argument("HestonModel: v0, theta, kappa must be positive");
    if (p.sigma <= 0.0)
        throw std::invalid_argument("HestonModel: sigma must be positive");
    if (std::abs(p.rho) > 1.0)
        throw std::invalid_argument("HestonModel: |rho| must be <= 1");
}

std::vector<double> HestonModel::simulate(double S0, double T,
                                           int steps, unsigned seed) const {
    if (S0 <= 0.0 || T <= 0.0 || steps <= 0)
        throw std::invalid_argument("HestonModel::simulate: invalid parameters");

    std::mt19937_64 rng(seed);
    std::normal_distribution<double> N(0.0, 1.0);

    double dt = T / steps;
    double sqdt = std::sqrt(dt);
    double rho2 = std::sqrt(1.0 - params_.rho * params_.rho);

    std::vector<double> path(steps + 1);
    path[0] = S0;
    double S = S0, v = params_.v0;

    for (int i = 0; i < steps; ++i) {
        double z1 = N(rng);
        double z2 = params_.rho * z1 + rho2 * N(rng);
        double vp = std::max(v, 0.0);  // reflection floor
        double svp = std::sqrt(vp);
        S *= std::exp(-0.5 * vp * dt + svp * sqdt * z1);
        v += params_.kappa * (params_.theta - vp) * dt + params_.sigma * svp * sqdt * z2;
        path[i + 1] = S;
    }
    return path;
}

} // namespace qf::models
