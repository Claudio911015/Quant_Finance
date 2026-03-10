#include <qf/pricingengines/heston.hpp>
#include <qf/math/integration.hpp>
#include <cmath>
#include <complex>
#include <random>
#include <stdexcept>

namespace qf::pricingengines {

// ── Heston characteristic function (corrected formulation, Albrecher et al.) ─

static std::complex<double> charFunc(
    double phi, int j,
    double S, double r, double q, double tau,
    const HestonParams& h)
{
    using cx = std::complex<double>;
    const cx I(0.0, 1.0);

    double u_j = (j == 1) ? 0.5 : -0.5;
    double b_j = (j == 1) ? h.kappa - h.rho * h.sigma : h.kappa;

    cx rsi = h.rho * h.sigma * I * phi;
    cx d = std::sqrt(
        (rsi - b_j) * (rsi - b_j)
        - h.sigma * h.sigma * (2.0 * u_j * I * phi - phi * phi));

    // Corrected: use -d to ensure |g| < 1
    cx gminus = b_j - rsi - d;
    cx gplus  = b_j - rsi + d;
    cx g = gminus / gplus;

    cx edt = std::exp(-d * tau);

    cx D = (gminus / (h.sigma * h.sigma)) * (1.0 - edt) / (1.0 - g * edt);

    cx C = (r - q) * I * phi * tau
         + (h.kappa * h.theta / (h.sigma * h.sigma))
           * (gminus * tau - 2.0 * std::log((1.0 - g * edt) / (1.0 - g)));

    return std::exp(C + D * h.v0 + I * phi * std::log(S));
}

// ── Semi-analytical Heston price ─────────────────────────────────────────────

double hestonPrice(const instruments::OptionParams& opt, const HestonParams& heston)
{
    if (opt.spot <= 0.0 || opt.strike <= 0.0 || opt.maturity <= 0.0)
        throw std::invalid_argument("hestonPrice: invalid option parameters");
    if (heston.v0 <= 0.0 || heston.theta <= 0.0 || heston.kappa <= 0.0)
        throw std::invalid_argument("hestonPrice: invalid Heston parameters");
    if (heston.sigma <= 0.0)
        throw std::invalid_argument("hestonPrice: vol of vol must be positive");
    if (std::abs(heston.rho) > 1.0)
        throw std::invalid_argument("hestonPrice: |rho| must be <= 1");

    using cx = std::complex<double>;
    const cx I(0.0, 1.0);

    double S = opt.spot, K = opt.strike;
    double r = opt.riskFreeRate, q = opt.dividendYield;
    double tau = opt.maturity;
    double lnK = std::log(K);

    // Integrate via Simpson's rule on [epsilon, umax]
    auto integrand = [&](int j) {
        return [&, j](double phi) -> double {
            auto fj = charFunc(phi, j, S, r, q, tau, heston);
            cx val = std::exp(-I * phi * lnK) * fj / (I * phi);
            return val.real();
        };
    };

    double P1 = 0.5 + (1.0 / M_PI) * math::simpson(integrand(1), 1e-8, 200.0, 4000);
    double P2 = 0.5 + (1.0 / M_PI) * math::simpson(integrand(2), 1e-8, 200.0, 4000);

    double call = S * std::exp(-q * tau) * P1 - K * std::exp(-r * tau) * P2;

    if (opt.type == instruments::OptionType::Call)
        return call;
    else
        return call - S * std::exp(-q * tau) + K * std::exp(-r * tau);
}

// ── Monte Carlo under Heston dynamics ────────────────────────────────────────

double hestonMonteCarlo(const instruments::OptionParams& opt,
                        const HestonParams& h,
                        int nPaths, int nSteps, unsigned seed)
{
    if (nPaths <= 0 || nSteps <= 0)
        throw std::invalid_argument("hestonMonteCarlo: nPaths and nSteps must be positive");
    if (opt.spot <= 0.0 || opt.strike <= 0.0 || opt.maturity <= 0.0)
        throw std::invalid_argument("hestonMonteCarlo: invalid option parameters");

    std::mt19937_64 rng(seed);
    std::normal_distribution<double> N(0.0, 1.0);

    double S0 = opt.spot, K = opt.strike;
    double r = opt.riskFreeRate, q = opt.dividendYield;
    double T = opt.maturity;
    double dt = T / nSteps;
    double sqdt = std::sqrt(dt);
    double rho2 = std::sqrt(1.0 - h.rho * h.rho);

    double sum = 0.0;
    for (int p = 0; p < nPaths; ++p) {
        double S = S0, v = h.v0;
        for (int t = 0; t < nSteps; ++t) {
            double z1 = N(rng);
            double z2 = h.rho * z1 + rho2 * N(rng);

            double vp = std::max(v, 0.0); // absorption at zero
            double svp = std::sqrt(vp);
            S *= std::exp((r - q - 0.5 * vp) * dt + svp * sqdt * z1);
            v += h.kappa * (h.theta - vp) * dt + h.sigma * svp * sqdt * z2;
        }
        double payoff = (opt.type == instruments::OptionType::Call)
                       ? std::max(S - K, 0.0)
                       : std::max(K - S, 0.0);
        sum += payoff;
    }

    return std::exp(-r * T) * sum / static_cast<double>(nPaths);
}

} // namespace qf::pricingengines
