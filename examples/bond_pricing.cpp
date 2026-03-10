#include <qf/termstructure/yieldcurve.hpp>
#include <qf/instruments/bond.hpp>
#include <iostream>
#include <iomanip>

int main() {
    // Flat yield curve at 5%
    qf::termstructure::YieldCurve curve(
        {0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0},
        {0.04, 0.045, 0.05, 0.052, 0.055, 0.057, 0.06},
        qf::math::InterpolationMethod::CubicSpline
    );

    // 5-year bond, 6% annual coupon, semi-annual, face = 1000
    qf::instruments::Bond bond(1000.0, 0.06, 10, 2.0);

    double price     = bond.price(curve);
    double ytm       = bond.yield(price);
    double duration  = bond.duration(curve);
    double convexity = bond.convexity(curve);

    std::cout << std::fixed << std::setprecision(4);
    std::cout << "=== Bond Pricing ===\n";
    std::cout << "Face Value:  1000.00\n";
    std::cout << "Coupon:      6.00%  semi-annual\n";
    std::cout << "Maturity:    5 years\n\n";
    std::cout << "Price:       " << price     << "\n";
    std::cout << "YTM:         " << ytm * 100 << "%\n";
    std::cout << "Duration:    " << duration  << " years  (modified)\n";
    std::cout << "Convexity:   " << convexity << "\n\n";

    // Discount factors from curve
    std::cout << "=== Yield Curve ===\n";
    for (double T : {0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0}) {
        std::cout << "T=" << std::setw(4) << T
                  << "  r=" << curve.zeroRate(T) * 100 << "%"
                  << "  DF=" << curve.discountFactor(T)
                  << "  Fwd(T-1,T)=" << (T > 0.5 ? curve.forwardRate(T - 0.5, T) * 100 : 0.0) << "%\n";
    }

    return 0;
}
