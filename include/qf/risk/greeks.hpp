#pragma once
#include <functional>

namespace qf::risk {

// Numerical Greeks via finite differences.
// All return raw derivatives (dV/d·param per unit of that parameter).
//
// Convention note for vega:
//   risk::vega() returns dV/dσ where σ is in decimal form (e.g. 0.20 = 20%).
//   BSResult.vega is scaled to "per 1 percentage-point" (divide by 100).
//   To convert: BSResult.vega = risk::vega(...) / 100.
double delta(std::function<double(double)> priceFn, double spot, double h = 0.01);
double gamma(std::function<double(double)> priceFn, double spot, double h = 0.01);
/// @brief dV/dσ per unit of volatility (decimal). Divide by 100 to get per vol-point.
double vega(std::function<double(double)> priceFn,  double vol,  double h = 0.001);
double theta(std::function<double(double)> priceFn, double T,    double h = 1.0/365.0);
double rho(std::function<double(double)>   priceFn, double rate, double h = 0.0001);

// DV01 for fixed income
double dv01(std::function<double(double)> priceFn, double yield, double h = 0.0001);

} // namespace qf::risk
