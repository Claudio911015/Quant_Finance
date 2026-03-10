#include <qf/instruments/swap.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <iostream>
#include <iomanip>

int main() {
    std::cout << std::fixed << std::setprecision(6);

    // Market yield curve
    qf::termstructure::YieldCurve curve(
        {0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 30.0},
        {0.035, 0.038, 0.040, 0.042, 0.045, 0.047, 0.050, 0.052, 0.053, 0.054},
        qf::math::InterpolationMethod::CubicSpline);

    std::cout << "=== Interest Rate Swap Pricing ===\n\n";

    // Par swap rates for different maturities
    std::cout << "--- Par Swap Rates ---\n";
    std::cout << "Maturity   Par Rate\n";
    for (double T : {1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0}) {
        double pr = qf::instruments::InterestRateSwap::parRate(T, 2.0, curve);
        std::cout << std::setw(5) << T << " yr   "
                  << std::setw(8) << pr * 100 << "%\n";
    }

    // Price a 5-year payer swap at 4.5% fixed
    double notional = 10'000'000.0;
    double fixedRate = 0.045;
    qf::instruments::InterestRateSwap payer(notional, fixedRate, 5.0, 2.0,
                                            qf::instruments::SwapType::Payer);
    qf::instruments::InterestRateSwap receiver(notional, fixedRate, 5.0, 2.0,
                                               qf::instruments::SwapType::Receiver);

    double parR = qf::instruments::InterestRateSwap::parRate(5.0, 2.0, curve);

    std::cout << "\n--- 5Y Swap ($10M Notional, Fixed=" << fixedRate*100 << "%) ---\n";
    std::cout << "Par Rate 5Y:    " << parR * 100 << "%\n";
    std::cout << "Payer NPV:      $" << std::setprecision(2) << payer.npv(curve) << "\n";
    std::cout << "Receiver NPV:   $" << receiver.npv(curve) << "\n";
    std::cout << "Annuity:        $" << payer.annuity(curve) << "\n";
    std::cout << "Payer + Recv:   $" << payer.npv(curve) + receiver.npv(curve)
              << " (should be ~0)\n";

    // Swap at par rate → NPV ≈ 0
    std::cout << std::setprecision(6);
    qf::instruments::InterestRateSwap atPar(notional, parR, 5.0, 2.0,
                                            qf::instruments::SwapType::Payer);
    std::cout << "\n--- Swap at Par Rate ---\n";
    std::cout << "NPV at par:     $" << std::setprecision(4) << atPar.npv(curve)
              << " (should be ~0)\n";

    return 0;
}
