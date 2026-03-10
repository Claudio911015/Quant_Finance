#include <qf/instruments/option.hpp>
#include <qf/pricingengines/heston.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <iostream>
#include <iomanip>

int main() {
    qf::instruments::OptionParams opt{
        .spot          = 100.0,
        .strike        = 100.0,
        .riskFreeRate  = 0.05,
        .dividendYield = 0.0,
        .volatility    = 0.20,
        .maturity      = 1.0,
        .type          = qf::instruments::OptionType::Call,
        .exercise      = qf::instruments::ExerciseType::European
    };

    qf::pricingengines::HestonParams heston{
        .v0    = 0.04,    // initial variance (vol = 20%)
        .kappa = 2.0,     // mean reversion speed
        .theta = 0.04,    // long-run variance
        .sigma = 0.3,     // vol of vol
        .rho   = -0.7     // negative correlation (typical for equities)
    };

    std::cout << std::fixed << std::setprecision(6);
    std::cout << "=== Heston Model vs Black-Scholes ===\n\n";

    // Black-Scholes reference
    double bsPrice = qf::pricingengines::blackScholes(opt).price;
    std::cout << "Black-Scholes Call:     " << bsPrice << "\n";

    // Heston semi-analytical
    double hestonAnalytic = qf::pricingengines::hestonPrice(opt, heston);
    std::cout << "Heston Analytical Call: " << hestonAnalytic << "\n";

    // Heston Monte Carlo
    double hestonMC = qf::pricingengines::hestonMonteCarlo(opt, heston, 500000, 252, 42);
    std::cout << "Heston MC Call:         " << hestonMC << "\n";

    std::cout << "\n--- Volatility Smile (Heston vs BS) ---\n";
    std::cout << "Strike   Heston    BS(20%)\n";
    for (double K : {80.0, 90.0, 95.0, 100.0, 105.0, 110.0, 120.0}) {
        opt.strike = K;
        double hp = qf::pricingengines::hestonPrice(opt, heston);
        double bp = qf::pricingengines::blackScholes(opt).price;
        std::cout << std::setw(6) << K << "   "
                  << std::setw(9) << hp << "  "
                  << std::setw(9) << bp << "\n";
    }

    return 0;
}
