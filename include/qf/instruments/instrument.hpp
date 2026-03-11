#pragma once

#include <qf/termstructure/yieldcurve.hpp>

namespace qf::instruments {

class Instrument {
public:
    Instrument() = default;
    explicit Instrument(double maturity) : maturity_(maturity) {}
    virtual ~Instrument() = default;

    double maturity() const { return maturity_; }
    void setMaturity(double m) { maturity_ = m; }

    double pv(const termstructure::YieldCurve& curve) const {
        pv_ = calculatePV(curve);
        return pv_;
    }

    double currentPV() const { return pv_; }

protected:
    virtual double calculatePV(const termstructure::YieldCurve& curve) const = 0;

    double maturity_ = 0.0;
    mutable double pv_ = 0.0;
};

} // namespace qf::instruments
