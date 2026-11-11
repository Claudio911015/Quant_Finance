#include <qf/instruments/bond.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/math/rootfinding.hpp>
#include <qf/math/daycount.hpp>
#include <cmath>
#include <stdexcept>
#include <numeric>
#include <utility>

namespace qf::instruments {

Bond::Bond(double faceValue, double couponRate, int periods, double frequency,
           math::DayCountConvention dcc)
    : Instrument(static_cast<double>(periods) / frequency),
      faceValue_(faceValue), couponRate_(couponRate),
      frequency_(frequency), dcc_(dcc)
{
    if (faceValue <= 0.0)
        throw std::invalid_argument("Bond: faceValue must be positive");
    if (periods <= 0)
        throw std::invalid_argument("Bond: periods must be positive");
    if (frequency <= 0.0)
        throw std::invalid_argument("Bond: frequency must be positive");

    payTimes_.resize(periods);
    for (int i = 0; i < periods; ++i)
        payTimes_[i] = (i + 1.0) / frequency;
}

Bond::Bond(double faceValue, double couponRate, double frequency,
           std::vector<double> payTimes, double prevCouponTime,
           math::DayCountConvention dcc)
    : Instrument(payTimes.empty() ? 0.0 : payTimes.back()),
      faceValue_(faceValue), couponRate_(couponRate),
      frequency_(frequency), payTimes_(std::move(payTimes)),
      prevCouponTime_(prevCouponTime), dcc_(dcc)
{
    if (!(faceValue > 0.0) || !std::isfinite(faceValue))
        throw std::invalid_argument("Bond: faceValue must be positive");
    if (!std::isfinite(couponRate))
        throw std::invalid_argument("Bond: couponRate must be finite");
    if (!(frequency > 0.0) || !std::isfinite(frequency))
        throw std::invalid_argument("Bond: frequency must be positive");
    if (payTimes_.empty())
        throw std::invalid_argument("Bond: payTimes must not be empty");
    if (!std::isfinite(prevCouponTime))
        throw std::invalid_argument("Bond: prevCouponTime must be finite");
    for (std::size_t i = 0; i < payTimes_.size(); ++i) {
        if (!std::isfinite(payTimes_[i]) || !(payTimes_[i] > 0.0))
            throw std::invalid_argument("Bond: payTimes must be finite and positive");
        if (i > 0 && !(payTimes_[i] > payTimes_[i - 1]))
            throw std::invalid_argument("Bond: payTimes must be strictly increasing");
    }
    if (prevCouponTime > 0.0)
        throw std::invalid_argument("Bond: prevCouponTime must be <= 0 (not after the valuation date)");
}

std::vector<double> Bond::cashflows() const
{
    // tau: accrual fraction per period, determined by the day-count convention.
    double tau    = math::periodFraction(frequency_, dcc_);
    double coupon = faceValue_ * couponRate_ * tau;
    std::vector<double> cf(payTimes_.size(), coupon);
    cf.back() += faceValue_; // principal at maturity
    return cf;
}

std::vector<double> Bond::maturities() const
{
    return payTimes_;
}

std::vector<std::pair<double, double>> Bond::cashFlowSchedule() const
{
    auto cf = cashflows();
    auto t  = maturities();
    std::vector<std::pair<double, double>> schedule;
    schedule.reserve(cf.size());
    for (std::size_t i = 0; i < cf.size(); ++i)
        schedule.emplace_back(t[i], cf[i]);
    return schedule;
}

double Bond::price(const termstructure::YieldCurve& curve) const
{
    auto cf = cashflows();
    auto t  = maturities();
    double pv = 0.0;
    for (std::size_t i = 0; i < payTimes_.size(); ++i)
        pv += cf[i] * curve.discountFactor(t[i]);
    return pv;
}

double Bond::accruedInterest() const
{
    if (prevCouponTime_ == 0.0)
        return 0.0;
    // Same coupon as cashflows(); the share of the current period already elapsed is linear in time.
    double coupon = faceValue_ * couponRate_ * math::periodFraction(frequency_, dcc_);
    return coupon * (-prevCouponTime_) / (payTimes_.front() - prevCouponTime_);
}

double Bond::cleanPrice(const termstructure::YieldCurve& curve) const
{
    return price(curve) - accruedInterest();
}

double Bond::calculatePV(const core::MarketEnvironment& env) const
{
    return price(env.curve());
}

double Bond::yield(double marketPrice) const
{
    // Find y such that sum(cf[i] * exp(-y * t[i])) = marketPrice
    auto cf = cashflows();
    auto t  = maturities();

    auto priceFn = [&](double y) {
        double pv = 0.0;
        for (std::size_t i = 0; i < payTimes_.size(); ++i)
            pv += cf[i] * std::exp(-y * t[i]);
        return pv - marketPrice;
    };

    // Bracket: covers negative yields (distressed/sovereign) and very high yields.
    double lo = -0.30, hi = 0.10;
    // Extend hi until we bracket the root (price fn changes sign)
    while (priceFn(hi) > 0.0 && hi < 50.0) hi += 0.10;
    // Extend lo downward if needed (very negative yields)
    while (priceFn(lo) < 0.0 && lo > -5.0) lo -= 0.10;
    if (priceFn(lo) * priceFn(hi) > 0.0)
        throw std::runtime_error("Bond::yield: failed to bracket root — check market price");

    return math::brent(priceFn, lo, hi);
}

double Bond::duration(const termstructure::YieldCurve& curve) const
{
    // Modified duration: -dP/dy / P
    auto cf = cashflows();
    auto t  = maturities();
    double pv = 0.0, weighted = 0.0;
    for (std::size_t i = 0; i < payTimes_.size(); ++i) {
        double df = curve.discountFactor(t[i]);
        pv       += cf[i] * df;
        weighted += t[i] * cf[i] * df;
    }
    // Under continuous compounding (the convention used throughout this library),
    // modified duration equals Macaulay duration: D_mod = D_mac / exp(y*dt) ≈ D_mac.
    // The periodic-compounding divisor (1 + y/freq) would mix conventions and
    // introduce a systematic error proportional to y/freq.
    return weighted / pv; // modified duration = macaulay duration (cc)
}

double Bond::convexity(const termstructure::YieldCurve& curve) const
{
    auto cf = cashflows();
    auto t  = maturities();
    double pv = price(curve);
    double conv = 0.0;
    for (std::size_t i = 0; i < payTimes_.size(); ++i)
        conv += t[i] * t[i] * cf[i] * curve.discountFactor(t[i]);
    return conv / pv;
}

} // namespace qf::instruments
