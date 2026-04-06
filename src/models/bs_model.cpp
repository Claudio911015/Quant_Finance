#include <qf/models/bs_model.hpp>
#include <random>
#include <cmath>
#include <stdexcept>

namespace qf::models {

BlackScholesModel::BlackScholesModel(double r, double q, double sigma)
    : r_(r), q_(q), sigma_(sigma) {
    if (sigma <= 0.0)
        throw std::invalid_argument("BlackScholesModel: sigma must be positive");
}

std::vector<double> BlackScholesModel::simulate(double S0, double T,
                                                 int steps, unsigned seed) const {
    if (S0 <= 0.0 || T <= 0.0 || steps <= 0)
        throw std::invalid_argument("BlackScholesModel::simulate: invalid parameters");

    std::mt19937_64 rng(seed);
    std::normal_distribution<double> N(0.0, 1.0);

    double dt = T / steps;
    double drift = (r_ - q_ - 0.5 * sigma_ * sigma_) * dt;
    double diffusion = sigma_ * std::sqrt(dt);

    std::vector<double> path(steps + 1);
    path[0] = S0;
    for (int i = 0; i < steps; ++i)
        path[i + 1] = path[i] * std::exp(drift + diffusion * N(rng));
    return path;
}

} // namespace qf::models
