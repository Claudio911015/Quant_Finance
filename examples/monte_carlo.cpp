#include <qf/instruments/option.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <qf/pricingengines/binomialtree.hpp>
#include <iostream>
#include <iomanip>
#include <random>
#include <cmath>

// Simple Monte Carlo pricer for European options under GBM
double monteCarloBSPrice(const qf::instruments::OptionParams& p,
                         int N = 100000, unsigned seed = 42)
{
    std::mt19937_64 rng(seed);
    std::normal_distribution<double> Z(0.0, 1.0);

    const double S0  = p.spot;
    const double K   = p.strike;
    const double r   = p.riskFreeRate;
    const double q   = p.dividendYield;
    const double sig = p.volatility;
    const double T   = p.maturity;
    const double drift = (r - q - 0.5 * sig * sig) * T;
    const double diff  = sig * std::sqrt(T);

    double sum = 0.0;
    for (int i = 0; i < N; ++i) {
        double ST = S0 * std::exp(drift + diff * Z(rng));
        double payoff = (p.type == qf::instruments::OptionType::Call)
                      ? std::max(ST - K, 0.0)
                      : std::max(K - ST, 0.0);
        sum += payoff;
    }

    return std::exp(-r * T) * sum / N;
}

int main() {
    qf::instruments::OptionParams p{
        .spot          = 100.0,
        .strike        = 100.0,
        .riskFreeRate  = 0.05,
        .dividendYield = 0.0,
        .volatility    = 0.20,
        .maturity      = 1.0,
        .type          = qf::instruments::OptionType::Call,
        .exercise      = qf::instruments::ExerciseType::European
    };

    auto bs = qf::pricingengines::blackScholes(p);
    double mc = monteCarloBSPrice(p, 500000);
    double bt_eu = qf::pricingengines::binomialTreeBSPrice(p, 2000);

    auto p_am = p; p_am.exercise = qf::instruments::ExerciseType::American;
    double bt_am = qf::pricingengines::binomialTreeBSPrice(p_am, 2000);

    std::cout << std::fixed << std::setprecision(4);
    std::cout << "=== Monte Carlo vs Black-Scholes vs Binomial (ATM Call) ===\n";
    std::cout << "Black-Scholes:  " << bs.price << "\n";
    std::cout << "Monte Carlo:    " << mc       << "  (N=500,000)\n";
    std::cout << "Binomial (E):   " << bt_eu    << "  (n=2,000)\n";
    std::cout << "Binomial (A):   " << bt_am    << "  (n=2,000)\n";
    std::cout << "MC diff:        " << std::abs(bs.price - mc) << "\n";
    std::cout << "Binomial diff:  " << std::abs(bs.price - bt_eu) << "\n";

    return 0;
}
