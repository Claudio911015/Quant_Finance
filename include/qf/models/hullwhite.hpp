#pragma once
#include <qf/termstructure/yieldcurve.hpp>

namespace qf::models {

// dr(t) = [theta(t) - a*r(t)]*dt + sigma*dW(t)
// theta(t) calibrated to fit the initial yield curve exactly
class HullWhite {
public:
    HullWhite(double a, double sigma, const termstructure::YieldCurve& curve);

    double bondPrice(double T) const;
    double zeroRate(double T) const;

private:
    double a_, sigma_;
    const termstructure::YieldCurve& curve_;

    double B(double T) const;
    double A(double T) const;
};

} // namespace qf::models
