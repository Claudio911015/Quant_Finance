#pragma once
#include <functional>

namespace qf::risk {

// Numerical Greeks via finite differences
double delta(std::function<double(double)> priceFn, double spot, double h = 0.01);
double gamma(std::function<double(double)> priceFn, double spot, double h = 0.01);
double vega(std::function<double(double)> priceFn,  double vol,  double h = 0.001);
double theta(std::function<double(double)> priceFn, double T,    double h = 1.0/365.0);
double rho(std::function<double(double)>   priceFn, double rate, double h = 0.0001);

// DV01 for fixed income
double dv01(std::function<double(double)> priceFn, double yield, double h = 0.0001);

} // namespace qf::risk
