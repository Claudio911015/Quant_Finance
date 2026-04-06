#pragma once
#include <string>
#include <unordered_map>
#include <qf/termstructure/yieldcurve.hpp>

namespace qf::core {

class MarketEnvironment {
    // Not thread-safe. External synchronization required for concurrent access.
public:
    MarketEnvironment() noexcept = default;
    explicit MarketEnvironment(termstructure::YieldCurve defaultCurve);

    void addCurve(const std::string& name, termstructure::YieldCurve curve);
    const termstructure::YieldCurve& curve(const std::string& name = "default") const;

    void setSpot(const std::string& ticker, double spot);
    void setVolatility(const std::string& ticker, double vol);
    double spot(const std::string& ticker) const;
    double volatility(const std::string& ticker) const;

private:
    std::unordered_map<std::string, termstructure::YieldCurve> curves_;
    std::unordered_map<std::string, double> spots_;
    std::unordered_map<std::string, double> vols_;
};

} // namespace qf::core
