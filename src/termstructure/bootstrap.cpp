#include <qf/termstructure/bootstrap.hpp>
#include <cmath>
#include <stdexcept>
#include <map>

namespace qf::termstructure {

YieldCurve bootstrap(const std::vector<BootstrapInstrument>& instruments,
                     math::InterpolationMethod method)
{
    if (instruments.empty())
        throw std::invalid_argument("bootstrap: instruments vector is empty");

    // Verify sorted by maturity
    for (std::size_t i = 1; i < instruments.size(); ++i)
        if (instruments[i].maturity <= instruments[i - 1].maturity)
            throw std::invalid_argument("bootstrap: instruments must be sorted by increasing maturity");

    // Map from maturity to discount factor (built incrementally)
    std::map<double, double> dfMap;

    std::vector<double> maturities;
    std::vector<double> zeroRates;

    for (const auto& inst : instruments) {
        double T = inst.maturity;

        if (inst.type == BootstrapInstrument::Deposit) {
            // Deposit gives zero rate directly (continuous compounding)
            double r = inst.rate;
            double df = std::exp(-r * T);
            dfMap[T] = df;
            maturities.push_back(T);
            zeroRates.push_back(r);
        }
        else { // Swap
            // Par swap rate = R. The swap equation:
            //   sum_{i=1}^{n} R * dt * P(0, t_i) + P(0, T) = 1
            // Solve for P(0, T):
            //   P(0, T) = (1 - R * sum_{i=1}^{n-1} dt * P(0, t_i)) / (1 + R * dt)
            double R = inst.rate;
            double freq = inst.frequency;
            double dt = 1.0 / freq;
            int nPayments = static_cast<int>(T * freq + 0.5);

            double knownSum = 0.0;
            for (int i = 1; i < nPayments; ++i) {
                double ti = i * dt;
                // Look up or interpolate discount factor at ti
                auto it = dfMap.lower_bound(ti - 1e-10);
                if (it != dfMap.end() && std::abs(it->first - ti) < 1e-8) {
                    knownSum += dt * it->second;
                } else {
                    // Interpolate from known zero rates
                    if (maturities.size() >= 2) {
                        math::Interpolator interp(maturities, zeroRates,
                                                  math::InterpolationMethod::Linear);
                        double ri = interp(ti);
                        knownSum += dt * std::exp(-ri * ti);
                    } else if (!maturities.empty()) {
                        // Use flat extrapolation from the single known rate
                        knownSum += dt * std::exp(-zeroRates.back() * ti);
                    }
                }
            }

            double dfT = (1.0 - R * knownSum) / (1.0 + R * dt);
            if (dfT <= 0.0)
                throw std::runtime_error("bootstrap: negative discount factor at T="
                                         + std::to_string(T));

            double r = -std::log(dfT) / T;
            dfMap[T] = dfT;
            maturities.push_back(T);
            zeroRates.push_back(r);
        }
    }

    return YieldCurve(maturities, zeroRates, method);
}

} // namespace qf::termstructure
