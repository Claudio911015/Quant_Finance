#pragma once
#include <memory>
#include <qf/core/market_environment.hpp>
#include <qf/termstructure/yieldcurve.hpp>

// Forward declare to avoid circular dependency
namespace qf::pricingengines { class IPricingEngine; }

namespace qf::instruments {

class Instrument {
public:
    Instrument() = default;
    explicit Instrument(double maturity) : maturity_(maturity) {}
    virtual ~Instrument() = default;

    double maturity() const { return maturity_; }
    void setMaturity(double m) { maturity_ = m; }

    void setPricingEngine(std::shared_ptr<pricingengines::IPricingEngine> engine);

    /// Primary API: price against a full market environment.
    double pv(const core::MarketEnvironment& env) const;

    /// Legacy overload for backward-compat: wraps curve in MarketEnvironment("default").
    double pv(const termstructure::YieldCurve& curve) const;

    double currentPV() const { return pv_; }

protected:
    /// Subclasses implement pricing against MarketEnvironment.
    virtual double calculatePV(const core::MarketEnvironment& env) const = 0;

    double maturity_ = 0.0;
    mutable double pv_ = 0.0;

private:
    std::shared_ptr<pricingengines::IPricingEngine> engine_;
};

} // namespace qf::instruments
