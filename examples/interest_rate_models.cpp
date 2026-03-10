#include <qf/models/vasicek.hpp>
#include <qf/models/hullwhite.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <iostream>
#include <iomanip>

int main() {
    std::cout << std::fixed << std::setprecision(6);

    // ── Vasicek Model ────────────────────────────────────────────────────
    // dr = a(b - r) dt + sigma dW
    double a = 0.5, b = 0.05, sigma = 0.01, r0 = 0.03;
    qf::models::Vasicek vasicek(a, b, sigma, r0);

    std::cout << "=== Vasicek Model ===\n";
    std::cout << "Parameters: a=" << a << ", b=" << b
              << ", sigma=" << sigma << ", r0=" << r0 << "\n\n";

    std::cout << "  T     Bond Price   Zero Rate\n";
    for (double T : {0.5, 1.0, 2.0, 5.0, 10.0, 20.0}) {
        std::cout << std::setw(5) << T << "   "
                  << std::setw(10) << vasicek.bondPrice(T) << "   "
                  << std::setw(9) << vasicek.zeroRate(T) * 100 << "%\n";
    }

    // Simulate a rate path
    auto path = vasicek.simulate(5.0, 1000, 42);
    std::cout << "\nSimulated path (5yr, 1000 steps):\n";
    std::cout << "  r(0)   = " << path.front() * 100 << "%\n";
    std::cout << "  r(2.5) = " << path[500] * 100 << "%\n";
    std::cout << "  r(5)   = " << path.back() * 100 << "%\n";

    // ── Hull-White Model ─────────────────────────────────────────────────
    std::cout << "\n=== Hull-White Model ===\n";

    // Market yield curve
    qf::termstructure::YieldCurve marketCurve(
        {0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0},
        {0.03, 0.035, 0.04, 0.045, 0.05, 0.055, 0.058},
        qf::math::InterpolationMethod::CubicSpline);

    qf::models::HullWhite hw(0.1, 0.015, marketCurve);

    std::cout << "Calibrated to market curve (a=0.1, sigma=0.015)\n\n";
    std::cout << "  T     HW Price   Market DF   Match?\n";
    for (double T : {0.5, 1.0, 2.0, 5.0, 10.0, 20.0}) {
        double hwP = hw.bondPrice(T);
        double mktP = marketCurve.discountFactor(T);
        std::cout << std::setw(5) << T << "   "
                  << std::setw(9) << hwP << "   "
                  << std::setw(9) << mktP << "   "
                  << (std::abs(hwP - mktP) < 1e-10 ? "YES" : "NO") << "\n";
    }

    return 0;
}
