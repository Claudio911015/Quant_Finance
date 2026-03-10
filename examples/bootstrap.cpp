#include <qf/termstructure/bootstrap.hpp>
#include <qf/instruments/swap.hpp>
#include <iostream>
#include <iomanip>

int main() {
    std::cout << std::fixed << std::setprecision(6);
    std::cout << "=== Yield Curve Bootstrapping ===\n\n";

    // Market instruments (typical USD curve)
    using Inst = qf::termstructure::BootstrapInstrument;
    std::vector<Inst> instruments = {
        // Money market deposits (zero rates, continuous compounding)
        {0.25, 0.0420, Inst::Deposit, 0},
        {0.50, 0.0435, Inst::Deposit, 0},
        {1.00, 0.0450, Inst::Deposit, 0},
        // Interest rate swaps (par coupon rates, semi-annual)
        {2.00, 0.0460, Inst::Swap, 2.0},
        {3.00, 0.0475, Inst::Swap, 2.0},
        {5.00, 0.0500, Inst::Swap, 2.0},
        {7.00, 0.0515, Inst::Swap, 2.0},
        {10.0, 0.0530, Inst::Swap, 2.0},
        {15.0, 0.0540, Inst::Swap, 2.0},
        {20.0, 0.0545, Inst::Swap, 2.0},
        {30.0, 0.0550, Inst::Swap, 2.0},
    };

    // Bootstrap the curve
    auto curve = qf::termstructure::bootstrap(instruments);

    // Display bootstrapped zero rates and discount factors
    std::cout << "--- Bootstrapped Zero Curve ---\n";
    std::cout << "Maturity   Zero Rate   Discount Factor\n";
    for (double T : {0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 30.0}) {
        std::cout << std::setw(7) << T << "yr   "
                  << std::setw(8) << curve.zeroRate(T) * 100 << "%     "
                  << std::setw(10) << curve.discountFactor(T) << "\n";
    }

    // Verify: compute par swap rates from bootstrapped curve
    std::cout << "\n--- Par Swap Rate Verification ---\n";
    std::cout << "Maturity   Input Rate   Recovered Rate   Match?\n";
    for (const auto& inst : instruments) {
        if (inst.type == Inst::Swap) {
            double recovered = qf::instruments::InterestRateSwap::parRate(
                inst.maturity, inst.frequency, curve);
            bool match = std::abs(recovered - inst.rate) < 1e-4;
            std::cout << std::setw(7) << inst.maturity << "yr   "
                      << std::setw(8) << inst.rate * 100 << "%       "
                      << std::setw(8) << recovered * 100 << "%       "
                      << (match ? "YES" : "NO") << "\n";
        }
    }

    // Forward rates
    std::cout << "\n--- Forward Rates ---\n";
    std::cout << "Period        Forward Rate\n";
    for (auto [t1, t2] : std::vector<std::pair<double,double>>{
            {1,2}, {2,3}, {3,5}, {5,7}, {7,10}, {10,15}, {15,20}, {20,30}}) {
        std::cout << std::setw(2) << t1 << "y - " << std::setw(2) << t2 << "y    "
                  << std::setw(8) << curve.forwardRate(t1, t2) * 100 << "%\n";
    }

    return 0;
}
