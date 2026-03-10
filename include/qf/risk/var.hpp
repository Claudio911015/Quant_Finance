#pragma once
#include <vector>

namespace qf::risk {

struct VaRResult {
    double var;    // Value at Risk (positive number = loss)
    double cvar;   // Conditional VaR / Expected Shortfall
};

// Parametric VaR assuming normal distribution of returns
VaRResult parametricVaR(double portfolioValue,
                        double meanReturn,
                        double stddevReturn,
                        double confidence = 0.99);

// Historical VaR from a vector of historical returns (e.g. daily log-returns)
VaRResult historicalVaR(const std::vector<double>& returns,
                        double portfolioValue,
                        double confidence = 0.99);

// Monte Carlo VaR from a vector of simulated P&L scenarios
VaRResult monteCarloVaR(const std::vector<double>& simulatedPnL,
                        double confidence = 0.99);

} // namespace qf::risk
