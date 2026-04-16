#pragma once
#include <vector>
#include <qf/core/market_environment.hpp>
#include <qf/instruments/swap.hpp>

namespace qf::xva {

/// @brief Collection of vanilla IRS sharing the same counterparty.
///
/// Stores swap parameters and builds residual instruments at each
/// simulation date so that only future cash flows are priced.
class NettingSet {
public:
    /// @brief Register a vanilla interest-rate swap in this netting set.
    /// @param notional   Notional principal.
    /// @param fixedRate  Fixed coupon rate (annual, decimal).
    /// @param maturity   Original maturity in years from t = 0.
    /// @param frequency  Payment periods per year (e.g. 2 = semi-annual).
    /// @param type       Payer or Receiver from the portfolio's perspective.
    void add(double notional, double fixedRate, double maturity,
             double frequency, qf::instruments::SwapType type);

    /// @brief Net mark-to-market at simulation time t.
    ///
    /// Builds residual swaps (remaining maturity = original - t) and sums
    /// their NPVs. Swaps that have matured (maturity <= t) are skipped.
    /// @param env  MarketEnvironment containing the conditional yield curve.
    /// @param t    Current simulation time in years.
    double netValue(const qf::core::MarketEnvironment& env, double t = 0.0) const;

    std::size_t size() const;

private:
    struct Entry {
        double notional, fixedRate, maturity, frequency;
        qf::instruments::SwapType type;
    };
    std::vector<Entry> entries_;
};

} // namespace qf::xva
