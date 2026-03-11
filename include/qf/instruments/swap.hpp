#pragma once
#include <qf/instruments/instrument.hpp>
#include <qf/termstructure/yieldcurve.hpp>

namespace qf::instruments {

enum class SwapType { Payer, Receiver };

class InterestRateSwap : public Instrument {
public:
    // notional: nominal amount
    // fixedRate: annual fixed coupon rate
    // maturity: swap maturity in years
    // frequency: payments per year (e.g. 2 = semi-annual)
    InterestRateSwap(double notional, double fixedRate,
                     double maturity, double frequency,
                     SwapType type);

    // Net present value of the swap
    double npv(const termstructure::YieldCurve& curve) const;

    // Par swap rate (fixed rate that makes NPV = 0)
    static double parRate(double maturity, double frequency,
                          const termstructure::YieldCurve& curve);

    // Annuity (PV of fixed leg basis point streams)
    double annuity(const termstructure::YieldCurve& curve) const;

private:
    double notional_;
    double fixedRate_;
    double maturity_;
    double frequency_;
    SwapType type_;
};

} // namespace qf::instruments
