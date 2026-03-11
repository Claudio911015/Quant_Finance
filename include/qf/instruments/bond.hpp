#pragma once
#include <vector>
#include <qf/instruments/instrument.hpp>
#include <qf/termstructure/yieldcurve.hpp>

namespace qf::instruments {

class Bond : public Instrument {
public:
    Bond(double faceValue,
         double couponRate,
         int    periods,
         double frequency = 2.0); // semi-annual by default

    double price(const termstructure::YieldCurve& curve) const;
    double yield(double marketPrice) const;  // YTM via root-finding
    double duration(const termstructure::YieldCurve& curve) const;
    double convexity(const termstructure::YieldCurve& curve) const;

private:
    double faceValue_;
    double couponRate_;
    int    periods_;
    double frequency_;

    std::vector<double> cashflows() const;
    std::vector<double> maturities() const;
};

} // namespace qf::instruments
