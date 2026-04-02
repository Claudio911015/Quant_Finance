#include <qf/core/market_environment.hpp>
#include <stdexcept>

namespace qf::core {

MarketEnvironment::MarketEnvironment(termstructure::YieldCurve defaultCurve) {
    curves_.emplace("default", std::move(defaultCurve));
}

void MarketEnvironment::addCurve(const std::string& name, termstructure::YieldCurve curve) {
    curves_.insert_or_assign(name, std::move(curve));
}

const termstructure::YieldCurve& MarketEnvironment::curve(const std::string& name) const {
    auto it = curves_.find(name);
    if (it == curves_.end()) {
        throw std::out_of_range("MarketEnvironment: curve not found: " + name);
    }
    return it->second;
}

void MarketEnvironment::setSpot(const std::string& ticker, double spot) {
    spots_.insert_or_assign(ticker, spot);
}

void MarketEnvironment::setVolatility(const std::string& ticker, double vol) {
    vols_.insert_or_assign(ticker, vol);
}

double MarketEnvironment::spot(const std::string& ticker) const {
    auto it = spots_.find(ticker);
    if (it == spots_.end()) {
        throw std::out_of_range("MarketEnvironment: spot not found for ticker: " + ticker);
    }
    return it->second;
}

double MarketEnvironment::volatility(const std::string& ticker) const {
    auto it = vols_.find(ticker);
    if (it == vols_.end()) {
        throw std::out_of_range("MarketEnvironment: volatility not found for ticker: " + ticker);
    }
    return it->second;
}

} // namespace qf::core
