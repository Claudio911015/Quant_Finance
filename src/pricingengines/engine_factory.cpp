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
                                int simPaths, unsigned seed)
{
    if (method == "BS")
        return std::make_shared<BlackScholesEngine>(params);
    if (method == "MC")
        return std::make_shared<MonteCarloEngine>(params, simPaths, seed);
    if (method == "BT")
        return std::make_shared<BinomialTreeEngine>(params);
    if (method == "FDM")
        return std::make_shared<FDMEngine>(params);
    throw std::invalid_argument("EngineFactory: unknown method '" + method + "'");
}

} // namespace qf::pricingengines
