#include <qf/xva/netting_set.hpp>
#include <qf/instruments/swap.hpp>
#include <stdexcept>

namespace qf::xva {

void NettingSet::add(double notional, double fixedRate, double maturity,
                     double frequency, qf::instruments::SwapType type)
{
    if (notional  <= 0.0) throw std::invalid_argument("NettingSet::add: notional must be positive");
    if (maturity  <= 0.0) throw std::invalid_argument("NettingSet::add: maturity must be positive");
    if (frequency <= 0.0) throw std::invalid_argument("NettingSet::add: frequency must be positive");
    entries_.push_back({notional, fixedRate, maturity, frequency, type});
}

double NettingSet::netValue(const qf::core::MarketEnvironment& env, double t) const
{
    double net = 0.0;
    for (const auto& e : entries_) {
        double rem = e.maturity - t;
        if (rem <= 0.0) continue;   // swap has already matured
        qf::instruments::InterestRateSwap residual(
            e.notional, e.fixedRate, rem, e.frequency, e.type);
        net += residual.npv(env);
    }
    return net;
}

std::size_t NettingSet::size() const { return entries_.size(); }

} // namespace qf::xva
