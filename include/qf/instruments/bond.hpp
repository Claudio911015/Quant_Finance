#pragma once
#include <vector>
#include <qf/instruments/instrument.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/daycount.hpp>

namespace qf::instruments {

class Bond : public Instrument {
public:
    /// @param faceValue  Principal amount (must be > 0).
    /// @param couponRate Annual coupon rate as a decimal (e.g. 0.05 = 5%).
    /// @param periods    Number of coupon periods (must be > 0).
    /// @param frequency  Coupon periods per year (default 2 = semi-annual).
    /// @param dcc        Day-count convention for accrual fractions (default ACT/365).
    Bond(double faceValue,
         double couponRate,
         int    periods,
         double frequency = 2.0,
         math::DayCountConvention dcc = math::DayCountConvention::ACT_365);

    double price(const termstructure::YieldCurve& curve) const;
    double calculatePV(const core::MarketEnvironment& env) const override;
    double yield(double marketPrice) const;  // YTM via root-finding
    double duration(const termstructure::YieldCurve& curve) const;
    double convexity(const termstructure::YieldCurve& curve) const;

    math::DayCountConvention dayCount() const { return dcc_; }

private:
    double faceValue_;
    double couponRate_;
    int    periods_;
    double frequency_;
    math::DayCountConvention dcc_;

    std::vector<double> cashflows() const;
    std::vector<double> maturities() const;
};

} // namespace qf::instruments
