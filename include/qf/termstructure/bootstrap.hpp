#pragma once
#include <vector>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/interpolation.hpp>

namespace qf::termstructure {

struct BootstrapInstrument {
    double maturity;
    double rate;        // quoted rate (zero rate for deposits, par coupon for swaps)
    enum Type { Deposit, Swap } type;
    double frequency;   // payments per year (for swaps, e.g. 2 = semi-annual)
};

// Bootstrap a yield curve from market instruments.
// Instruments must be sorted by maturity.
// Deposits give zero rates directly; swap par rates are iteratively stripped
// to extract discount factors and zero rates at each maturity.
YieldCurve bootstrap(const std::vector<BootstrapInstrument>& instruments,
                     math::InterpolationMethod method = math::InterpolationMethod::CubicSpline);

} // namespace qf::termstructure
