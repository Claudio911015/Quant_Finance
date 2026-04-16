#pragma once
#include <vector>
#include <qf/models/irate_model.hpp>
#include <qf/termstructure/yieldcurve.hpp>

namespace qf::models {

// dr(t) = [theta(t) - a*r(t)]*dt + sigma*dW(t)
// theta(t) calibrated to fit the initial yield curve exactly
class HullWhite : public IRateModel {
public:
    HullWhite(double a, double sigma, const termstructure::YieldCurve& curve);

    double bondPrice(double T) const override;
    double zeroRate(double T) const override;
    std::vector<double> simulate(double T, int steps, unsigned seed = 42) const override;

    /// @brief Compute the zero-coupon bond price P(t,T) conditional on r(t).
    /// @param t    Observation time in years (0 ≤ t < T).
    /// @param T    Maturity in years.
    /// @param r_t  Simulated short rate at time t.
    /// @return     Risk-neutral conditional discount factor P(t,T|r(t)).
    double conditionalBondPrice(double t, double T, double r_t) const;

private:
    double a_, sigma_;
    termstructure::YieldCurve curve_; // owned copy — avoids dangling-reference UB

    double B(double T) const;
    double theta(double t) const;
};

} // namespace qf::models
