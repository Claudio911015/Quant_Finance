#include <qf/risk/var.hpp>
#include <iostream>
#include <iomanip>
#include <random>
#include <vector>

int main() {
    std::cout << std::fixed << std::setprecision(2);

    double portfolioValue = 1'000'000.0;

    // ── Parametric VaR ───────────────────────────────────────────────────
    std::cout << "=== Parametric VaR (Normal Distribution) ===\n";
    double dailyMean = 0.0005;    // 0.05% daily return
    double dailyStddev = 0.015;   // 1.5% daily volatility

    for (double conf : {0.95, 0.99}) {
        auto result = qf::risk::parametricVaR(portfolioValue, dailyMean, dailyStddev, conf);
        std::cout << conf * 100 << "% VaR:  $" << std::setw(12) << result.var
                  << "   CVaR: $" << std::setw(12) << result.cvar << "\n";
    }

    // ── Historical VaR ───────────────────────────────────────────────────
    std::cout << "\n=== Historical VaR (Simulated 2-Year Daily Returns) ===\n";

    std::mt19937_64 rng(42);
    std::normal_distribution<double> dist(dailyMean, dailyStddev);

    std::vector<double> historicalReturns(504);
    for (auto& r : historicalReturns)
        r = dist(rng);

    for (double conf : {0.95, 0.99}) {
        auto result = qf::risk::historicalVaR(historicalReturns, portfolioValue, conf);
        std::cout << conf * 100 << "% VaR:  $" << std::setw(12) << result.var
                  << "   CVaR: $" << std::setw(12) << result.cvar << "\n";
    }

    // ── Monte Carlo VaR ──────────────────────────────────────────────────
    std::cout << "\n=== Monte Carlo VaR (100k Scenarios) ===\n";

    std::vector<double> pnl(100000);
    for (auto& p : pnl)
        p = portfolioValue * dist(rng);

    for (double conf : {0.95, 0.99}) {
        auto result = qf::risk::monteCarloVaR(pnl, conf);
        std::cout << conf * 100 << "% VaR:  $" << std::setw(12) << result.var
                  << "   CVaR: $" << std::setw(12) << result.cvar << "\n";
    }

    return 0;
}
