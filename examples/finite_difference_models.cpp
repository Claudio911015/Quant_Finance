#include <qf/instruments/option.hpp>
#include <qf/pricingengines/finite_difference.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <iostream>
#include <iomanip>

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

    std::cout << std::fixed << std::setprecision(6);
    std::cout << "=== Finite Differences vs Black-Scholes (European Call) ===\n";
    std::cout << "Underlying: " << p.spot << " Strike: " << p.strike << " T= " << p.maturity << "\n\n";

    auto bs = qf::pricingengines::blackScholes(p);
    std::cout << "Black-Scholes price: " << bs.price << "\n\n";

    int nS = 300, nT = 300;

    double explicito = qf::pricingengines::finiteDifferenceBSPrice(p, nS, nT, qf::pricingengines::FDMethod::Explicit);
    double implicito = qf::pricingengines::finiteDifferenceBSPrice(p, nS, nT, qf::pricingengines::FDMethod::Implicit);
    double crankn    = qf::pricingengines::finiteDifferenceBSPrice(p, nS, nT, qf::pricingengines::FDMethod::CrankNicolson);

    std::cout << "nS=" << nS << " nT=" << nT << "\n";
    std::cout << "Explicit scheme:   " << explicito << "  (err=" << std::abs(explicito-bs.price) << ")\n";
    std::cout << "Implicit scheme:   " << implicito << "  (err=" << std::abs(implicito-bs.price) << ")\n";
    std::cout << "Crank-Nicolson:   " << crankn  << "  (err=" << std::abs(crankn-bs.price) << ")\n";

    return 0;
}
