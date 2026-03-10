#pragma once
#include <vector>

namespace qf::models {

// dr(t) = a*(b - r(t))*dt + sigma*dW(t)
class Vasicek {
public:
    Vasicek(double a, double b, double sigma, double r0);

    // Analytical zero coupon bond price P(0, T)
    double bondPrice(double T) const;

    // Zero rate
    double zeroRate(double T) const;

    // Simulate path (Euler-Maruyama)
    // returns vector of rates at each time step
    std::vector<double> simulate(double T, int steps, unsigned seed = 42) const;

private:
    double a_, b_, sigma_, r0_;
};

} // namespace qf::models
