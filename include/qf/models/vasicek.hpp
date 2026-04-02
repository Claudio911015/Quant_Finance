#pragma once
#include <vector>
#include <qf/models/irate_model.hpp>

namespace qf::models {

// dr(t) = a*(b - r(t))*dt + sigma*dW(t)
class Vasicek : public IRateModel {
public:
    Vasicek(double a, double b, double sigma, double r0);

    // Analytical zero coupon bond price P(0, T)
    double bondPrice(double T) const override;

    // Zero rate
    double zeroRate(double T) const override;

    // Simulate path (Euler-Maruyama)
    // returns vector of rates at each time step
    std::vector<double> simulate(double T, int steps, unsigned seed = 42) const override;

private:
    double a_, b_, sigma_, r0_;
};

} // namespace qf::models
