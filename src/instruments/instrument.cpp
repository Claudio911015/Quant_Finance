#include <qf/instruments/instrument.hpp>
#include <qf/pricingengines/ipricing_engine.hpp>

namespace qf::instruments {

void Instrument::setPricingEngine(
        std::shared_ptr<pricingengines::IPricingEngine> engine) {
    engine_ = std::move(engine);
}

double Instrument::pv(const core::MarketEnvironment& env) const {
    pv_ = engine_ ? engine_->price(env) : calculatePV(env);
    return pv_;
}

double Instrument::pv(const termstructure::YieldCurve& curve) const {
    return pv(core::MarketEnvironment(curve));
}

} // namespace qf::instruments
