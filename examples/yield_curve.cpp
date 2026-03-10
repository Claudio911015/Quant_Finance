#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/interpolation.hpp>
#include <iostream>
#include <iomanip>

int main() {
    // US Treasury-like curve (maturities in years, rates as decimals)
    std::vector<double> maturities = {0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 20.0, 30.0};
    std::vector<double> rates      = {0.052, 0.054, 0.055, 0.052, 0.050, 0.048, 0.047, 0.046, 0.045, 0.044};

    qf::termstructure::YieldCurve curve(maturities, rates,
                                        qf::math::InterpolationMethod::CubicSpline);

    std::cout << std::fixed << std::setprecision(4);
    std::cout << "=== Yield Curve ===\n";
    std::cout << std::setw(10) << "Maturity"
              << std::setw(12) << "Zero Rate"
              << std::setw(14) << "Disc. Factor"
              << std::setw(16) << "Fwd Rate\n";
    std::cout << std::string(52, '-') << "\n";

    std::vector<double> tenors = {0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 20.0, 30.0};
    for (double T : tenors) {
        double fwd = (T > 0.25) ? curve.forwardRate(T - 0.25, T) * 100.0 : 0.0;
        std::cout << std::setw(10) << T
                  << std::setw(11) << curve.zeroRate(T) * 100 << "%"
                  << std::setw(13) << curve.discountFactor(T)
                  << std::setw(14) << fwd << "%\n";
    }

    return 0;
}
