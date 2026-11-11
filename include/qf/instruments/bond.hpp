#pragma once
#include <utility>
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

    /// @brief Construct a bond from an explicit payment calendar (aged bond with accrued coupon).
    ///
    /// Every payment is faceValue·couponRate·τ with τ = periodFraction(frequency, dcc), the same
    /// coupon as the regular constructor (1/frequency under ACT/365); the last one also repays the
    /// face value. With payTimes = {i/frequency} and prevCouponTime = 0 it is identical to the
    /// regular constructor.
    /// @param faceValue       Principal amount (must be > 0).
    /// @param couponRate      Annual coupon rate as a decimal (e.g. 0.05 = 5%).
    /// @param frequency       Coupon periods per year (must be > 0); sizes the coupon.
    /// @param payTimes        Remaining payment times in years from the valuation date; non-empty,
    ///                        finite, strictly increasing and > 0.
    /// @param prevCouponTime  Time of the last coupon already paid, in years from the valuation
    ///                        date (<= 0; 0 = a coupon is paid today, so nothing has accrued).
    /// @param dcc             Day-count convention for accrual fractions (default ACT/365).
    /// @throws std::invalid_argument if any argument breaks the conditions above.
    Bond(double faceValue,
         double couponRate,
         double frequency,
         std::vector<double> payTimes,
         double prevCouponTime,
         math::DayCountConvention dcc = math::DayCountConvention::ACT_365);

    /// @brief Dirty price: present value of every remaining cash flow (accrued coupon included).
    double price(const termstructure::YieldCurve& curve) const;

    /// @brief Coupon accrued since the previous coupon date, linear in time.
    /// @return coupon · (−prevCouponTime) / (payTimes[0] − prevCouponTime); 0 for the
    ///         constructor from periods/frequency, which starts on a coupon date.
    double accruedInterest() const;

    /// @brief Clean price.
    /// @param curve  Discount curve.
    /// @return price(curve) − accruedInterest().
    double cleanPrice(const termstructure::YieldCurve& curve) const;

    double calculatePV(const core::MarketEnvironment& env) const override;
    double yield(double marketPrice) const;  // YTM via root-finding
    double duration(const termstructure::YieldCurve& curve) const;
    double convexity(const termstructure::YieldCurve& curve) const;

    /// @brief Coupon and principal schedule used by price().
    /// @return Pairs (time in years, cash flow amount), one per coupon period;
    ///         the last amount includes the principal.
    std::vector<std::pair<double, double>> cashFlowSchedule() const;

    math::DayCountConvention dayCount() const { return dcc_; }

private:
    double faceValue_;
    double couponRate_;
    double frequency_;
    std::vector<double> payTimes_;   ///< remaining payment times (years from valuation)
    double prevCouponTime_ = 0.0;    ///< last paid coupon, <= 0; 0 for the regular constructor
    math::DayCountConvention dcc_;

    std::vector<double> cashflows() const;
    std::vector<double> maturities() const;
};

} // namespace qf::instruments
