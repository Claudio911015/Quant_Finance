#include <qf/pricingengines/engine_factory.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <qf/pricingengines/montecarlo.hpp>
#include <qf/pricingengines/binomialtree.hpp>
#include <qf/pricingengines/finite_difference.hpp>
#include <stdexcept>

namespace qf::pricingengines {

std::shared_ptr<IPricingEngine>
EngineFactory::makeEquityEngine(const std::string& method,
                                const instruments::OptionParams& params,
                                int simPaths, unsigned seed,
                                std::string ticker)
{
    if (method == "BS") {
        if (ticker.empty()) return std::make_shared<BlackScholesEngine>(params);
        return std::make_shared<BlackScholesEngine>(params, std::move(ticker));
    }
    if (method == "MC") {
        if (ticker.empty()) return std::make_shared<MonteCarloEngine>(params, simPaths, seed);
        return std::make_shared<MonteCarloEngine>(params, std::move(ticker), simPaths, seed);
    }
    if (method == "BT") {
        if (ticker.empty()) return std::make_shared<BinomialTreeEngine>(params);
        return std::make_shared<BinomialTreeEngine>(params, std::move(ticker));
    }
    if (method == "FDM") {
        if (ticker.empty()) return std::make_shared<FDMEngine>(params);
        return std::make_shared<FDMEngine>(params, std::move(ticker));
    }
    throw std::invalid_argument("EngineFactory: unknown method '" + method + "'");
}

} // namespace qf::pricingengines
