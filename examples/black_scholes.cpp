#include <qf/instruments/option.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <iostream>
#include <iomanip>

int main() {
    // Example: European Call on AAPL-like stock
    qf::instruments::OptionParams p{
        .spot          = 150.0,
        .strike        = 155.0,
        .riskFreeRate  = 0.05,
        .dividendYield = 0.01,
        .volatility    = 0.25,
        .maturity      = 1.0,
        .type          = qf::instruments::OptionType::Call,
        .exercise      = qf::instruments::ExerciseType::European
    };

    auto res = qf::pricingengines::blackScholes(p);

    std::cout << std::fixed << std::setprecision(6);
    std::cout << "=== Black-Scholes European Call ===\n";
    std::cout << "Spot:       " << p.spot     << "\n";
    std::cout << "Strike:     " << p.strike   << "\n";
    std::cout << "Rate:       " << p.riskFreeRate * 100 << "%\n";
    std::cout << "Vol:        " << p.volatility  * 100 << "%\n";
    std::cout << "Maturity:   " << p.maturity    << " yr\n\n";
    std::cout << "Price:      " << res.price  << "\n";
    std::cout << "Delta:      " << res.delta  << "\n";
    std::cout << "Gamma:      " << res.gamma  << "\n";
    std::cout << "Vega:       " << res.vega   << "  (per 1% vol)\n";
    std::cout << "Theta:      " << res.theta  << "  (per day)\n";
    std::cout << "Rho:        " << res.rho    << "  (per 1% rate)\n\n";

    // Implied vol from computed price
    double iv = qf::pricingengines::impliedVolatility(p, res.price);
    std::cout << "Impl. Vol:  " << iv * 100 << "%  (should match input)\n";

    return 0;
}
