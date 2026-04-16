#include <qf/risk/greeks.hpp>
#include <stdexcept>

namespace qf::risk {

// All numerical Greeks use central finite differences unless noted.
// The caller supplies a lambda that reprices under the perturbed parameter.

double delta(std::function<double(double)> priceFn, double spot, double h)
{
    if (h <= 0.0)
        throw std::invalid_argument("delta: h must be positive");
    if (spot <= 0.0)
        throw std::invalid_argument("delta: spot must be positive");
    return (priceFn(spot + h) - priceFn(spot - h)) / (2.0 * h);
}

double gamma(std::function<double(double)> priceFn, double spot, double h)
{
    if (h <= 0.0)
        throw std::invalid_argument("gamma: h must be positive");
    if (spot <= 0.0)
        throw std::invalid_argument("gamma: spot must be positive");
    return (priceFn(spot + h) - 2.0 * priceFn(spot) + priceFn(spot - h)) / (h * h);
}

double vega(std::function<double(double)> priceFn, double vol, double h)
{
    if (h <= 0.0)
        throw std::invalid_argument("vega: h must be positive");
    if (vol <= 0.0)
        throw std::invalid_argument("vega: vol must be positive");
    return (priceFn(vol + h) - priceFn(vol - h)) / (2.0 * h);
}

/// theta — forward difference on time-to-maturity:
///   (V(T - h) - V(T)) / h
/// Gives the change in value per unit of elapsed time (negative for long options).
double theta(std::function<double(double)> priceFn, double T, double h)
{
    if (h <= 0.0)
        throw std::invalid_argument("theta: h must be positive");
    if (T <= h)
        throw std::invalid_argument("theta: T must be greater than h");
    return (priceFn(T - h) - priceFn(T)) / h;
}

double rho(std::function<double(double)> priceFn, double rate, double h)
{
    if (h <= 0.0)
        throw std::invalid_argument("rho: h must be positive");
    return (priceFn(rate + h) - priceFn(rate - h)) / (2.0 * h);
}

/// DV01 — dollar value of 1 basis point (h = 0.0001 by default).
/// Central difference on yield; result is positive when price rises as yield falls.
double dv01(std::function<double(double)> priceFn, double yield, double h)
{
    if (h <= 0.0)
        throw std::invalid_argument("dv01: h must be positive");
    return (priceFn(yield - h) - priceFn(yield + h)) / 2.0;
}

} // namespace qf::risk
