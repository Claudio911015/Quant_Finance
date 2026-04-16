#include <qf/core/market_environment.hpp>
#include <algorithm>
#include <stdexcept>

namespace qf::core {

MarketEnvironment::MarketEnvironment(termstructure::YieldCurve defaultCurve) {
    curves_.emplace("default", std::move(defaultCurve));
}

// -----------------------------------------------------------------------------
// Observer management
// -----------------------------------------------------------------------------

void MarketEnvironment::subscribe(std::weak_ptr<IMarketObserver> observer) {
    auto sp = observer.lock();
    if (!sp) return;  // already expired
    // Check for duplicates
    for (auto& wp : observers_) {
        if (wp.lock() == sp) return;  // already subscribed
    }
    observers_.push_back(std::move(observer));
}

void MarketEnvironment::unsubscribe(const std::shared_ptr<IMarketObserver>& observer) {
    observers_.erase(
        std::remove_if(observers_.begin(), observers_.end(),
            [&observer](const std::weak_ptr<IMarketObserver>& wp) {
                auto sp = wp.lock();
                return !sp || sp == observer;
            }),
        observers_.end());
}

void MarketEnvironment::unsubscribeAll() {
    observers_.clear();
}

void MarketEnvironment::notify(ChangeType type, const std::string& key) {
    // Remove expired weak_ptrs first, then notify remaining live observers.
    observers_.erase(
        std::remove_if(observers_.begin(), observers_.end(),
                       [](const std::weak_ptr<IMarketObserver>& wp) {
                           return wp.expired();
                       }),
        observers_.end());

    for (auto& wp : observers_) {
        if (auto sp = wp.lock()) {
            sp->onMarketUpdate(*this, type, key);
        }
    }
}

// -----------------------------------------------------------------------------
// Mutating accessors
// -----------------------------------------------------------------------------

void MarketEnvironment::addCurve(const std::string& name, termstructure::YieldCurve curve) {
    curves_.insert_or_assign(name, std::move(curve));
    notify(ChangeType::CurveChanged, name);
}

void MarketEnvironment::setSpot(const std::string& ticker, double spot) {
    if (spot < 0.0) {
        throw std::invalid_argument("MarketEnvironment: spot cannot be negative: " + ticker);
    }
    spots_.insert_or_assign(ticker, spot);
    notify(ChangeType::SpotChanged, ticker);
}

void MarketEnvironment::setVolatility(const std::string& ticker, double vol) {
    if (vol < 0.0) {
        throw std::invalid_argument("MarketEnvironment: volatility cannot be negative: " + ticker);
    }
    vols_.insert_or_assign(ticker, vol);
    notify(ChangeType::VolatilityChanged, ticker);
}

// -----------------------------------------------------------------------------
// Read-only accessors
// -----------------------------------------------------------------------------

const termstructure::YieldCurve& MarketEnvironment::curve(const std::string& name) const {
    auto it = curves_.find(name);
    if (it == curves_.end()) {
        throw std::out_of_range("MarketEnvironment: curve not found: " + name);
    }
    return it->second;
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
