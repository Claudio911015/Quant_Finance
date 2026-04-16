#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <qf/core/market_environment.hpp>
#include <qf/instruments/bond.hpp>
#include <qf/instruments/option.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/interpolation.hpp>
#include <qf/pricingengines/ipricing_engine.hpp>
#include <qf/pricingengines/engine_factory.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <qf/pricingengines/binomialtree.hpp>
#include <qf/pricingengines/montecarlo.hpp>
#include <qf/pricingengines/finite_difference.hpp>
#include <qf/pricingengines/heston.hpp>
#include <qf/instruments/iunderlying.hpp>
#include <qf/models/hullwhite.hpp>

namespace py = pybind11;

// Trampoline for IPricingEngine subclasses defined in Python
class PyIPricingEngine : public qf::pricingengines::IPricingEngine {
public:
    using qf::pricingengines::IPricingEngine::IPricingEngine;
    double price(const qf::core::MarketEnvironment& env) const override {
        PYBIND11_OVERRIDE_PURE(double, qf::pricingengines::IPricingEngine, price, env);
    }
    std::string name() const override {
        PYBIND11_OVERRIDE_PURE(std::string, qf::pricingengines::IPricingEngine, name);
    }
};

PYBIND11_MODULE(qfpy, m) {
    m.doc() = "Quant_Finance C++ bindings";

    // ------------------------------------------------------------------ //
    // MarketEnvironment — container for live market data                  //
    // ------------------------------------------------------------------ //
    py::class_<qf::core::MarketEnvironment>(m, "MarketEnvironment")
        .def(py::init<>())
        .def(py::init<qf::termstructure::YieldCurve>(), py::arg("defaultCurve"))
        .def("add_curve",      &qf::core::MarketEnvironment::addCurve,
             py::arg("name"), py::arg("curve"))
        .def("set_spot",       &qf::core::MarketEnvironment::setSpot,
             py::arg("ticker"), py::arg("spot"))
        .def("set_volatility", &qf::core::MarketEnvironment::setVolatility,
             py::arg("ticker"), py::arg("vol"))
        .def("spot",           &qf::core::MarketEnvironment::spot,      py::arg("ticker"))
        .def("volatility",     &qf::core::MarketEnvironment::volatility, py::arg("ticker"))
        .def("curve",          &qf::core::MarketEnvironment::curve,
             py::arg("name") = "default",
             py::return_value_policy::reference_internal);

    // ------------------------------------------------------------------ //
    // IPricingEngine — Strategy interface (also usable as Python base)    //
    // ------------------------------------------------------------------ //
    py::class_<qf::pricingengines::IPricingEngine,
               PyIPricingEngine,
               std::shared_ptr<qf::pricingengines::IPricingEngine>>(m, "IPricingEngine")
        .def("price", &qf::pricingengines::IPricingEngine::price, py::arg("env"))
        .def("name",  &qf::pricingengines::IPricingEngine::name);

    // ------------------------------------------------------------------ //
    // EngineFactory — single entry point; adding a new engine in C++     //
    // automatically makes it available here without touching this file    //
    // ------------------------------------------------------------------ //
    py::class_<qf::pricingengines::EngineFactory>(m, "EngineFactory")
        .def_static("make_equity_engine",
                    &qf::pricingengines::EngineFactory::makeEquityEngine,
                    py::arg("method"), py::arg("params"),
                    py::arg("simPaths") = 100000, py::arg("seed") = 42,
                    py::arg("ticker") = "",
                    "Create a BS/MC/BT/FDM engine. Pass ticker to read market data from MarketEnvironment.")
        .def_static("make_heston_engine",
                    &qf::pricingengines::EngineFactory::makeHestonEngine,
                    py::arg("params"), py::arg("heston"), py::arg("ticker") = "",
                    "Create a Heston engine. Pass ticker to read spot/rate from MarketEnvironment.");

    // ------------------------------------------------------------------ //
    // IUnderlying hierarchy                                                //
    // ------------------------------------------------------------------ //
    py::class_<qf::instruments::IUnderlying,
               std::shared_ptr<qf::instruments::IUnderlying>>(m, "IUnderlying")
        .def("id", &qf::instruments::IUnderlying::id);

    py::class_<qf::instruments::EquityUnderlying,
               qf::instruments::IUnderlying,
               std::shared_ptr<qf::instruments::EquityUnderlying>>(m, "EquityUnderlying")
        .def(py::init<std::string>(), py::arg("ticker"))
        .def("id", &qf::instruments::EquityUnderlying::id);

    py::class_<qf::instruments::RateUnderlying,
               qf::instruments::IUnderlying,
               std::shared_ptr<qf::instruments::RateUnderlying>>(m, "RateUnderlying")
        .def(py::init<std::string>(), py::arg("curve_name"))
        .def("id", &qf::instruments::RateUnderlying::id);

    py::class_<qf::instruments::FxUnderlying,
               qf::instruments::IUnderlying,
               std::shared_ptr<qf::instruments::FxUnderlying>>(m, "FxUnderlying")
        .def(py::init<std::string>(), py::arg("pair"))
        .def("id", &qf::instruments::FxUnderlying::id);

    py::class_<qf::instruments::CommodityUnderlying,
               qf::instruments::IUnderlying,
               std::shared_ptr<qf::instruments::CommodityUnderlying>>(m, "CommodityUnderlying")
        .def(py::init<std::string>(), py::arg("code"))
        .def("id", &qf::instruments::CommodityUnderlying::id);

    py::enum_<qf::instruments::OptionType>(m, "OptionType")
        .value("Call", qf::instruments::OptionType::Call)
        .value("Put", qf::instruments::OptionType::Put)
        .export_values();

    py::enum_<qf::instruments::ExerciseType>(m, "ExerciseType")
        .value("European", qf::instruments::ExerciseType::European)
        .value("American", qf::instruments::ExerciseType::American)
        .export_values();

    py::class_<qf::instruments::OptionParams>(m, "OptionParams")
        .def(py::init<>())
        .def_readwrite("spot", &qf::instruments::OptionParams::spot)
        .def_readwrite("strike", &qf::instruments::OptionParams::strike)
        .def_readwrite("riskFreeRate", &qf::instruments::OptionParams::riskFreeRate)
        .def_readwrite("dividendYield", &qf::instruments::OptionParams::dividendYield)
        .def_readwrite("volatility", &qf::instruments::OptionParams::volatility)
        .def_readwrite("maturity", &qf::instruments::OptionParams::maturity)
        .def_readwrite("type", &qf::instruments::OptionParams::type)
        .def_readwrite("exercise", &qf::instruments::OptionParams::exercise);

    py::class_<qf::instruments::Bond>(m, "Bond")
        .def(py::init<double, double, int, double>(),
             py::arg("faceValue"), py::arg("couponRate"), py::arg("periods"), py::arg("frequency") = 2.0)
        .def("price", &qf::instruments::Bond::price)
        .def("yield", &qf::instruments::Bond::yield)
        .def("duration", &qf::instruments::Bond::duration)
        .def("convexity", &qf::instruments::Bond::convexity);

    py::enum_<qf::math::InterpolationMethod>(m, "InterpolationMethod")
        .value("Linear", qf::math::InterpolationMethod::Linear)
        .value("CubicSpline", qf::math::InterpolationMethod::CubicSpline)
        .value("LogLinear", qf::math::InterpolationMethod::LogLinear)
        .export_values();

    py::class_<qf::termstructure::YieldCurve>(m, "YieldCurve")
        .def(py::init<const std::vector<double>&, const std::vector<double>&, qf::math::InterpolationMethod>(),
             py::arg("maturities"), py::arg("zeroRates"), py::arg("method"))
        .def("zero_rate", &qf::termstructure::YieldCurve::zeroRate)
        .def("discount_factor", &qf::termstructure::YieldCurve::discountFactor)
        .def("forward_rate", &qf::termstructure::YieldCurve::forwardRate);

    py::enum_<qf::pricingengines::FDMethod>(m, "FDMethod")
        .value("Explicit", qf::pricingengines::FDMethod::Explicit)
        .value("Implicit", qf::pricingengines::FDMethod::Implicit)
        .value("CrankNicolson", qf::pricingengines::FDMethod::CrankNicolson)
        .export_values();

    m.def("black_scholes", [](const qf::instruments::OptionParams& params) {
        auto res = qf::pricingengines::blackScholes(params);
        py::dict d;
        d["price"] = res.price;
        d["delta"] = res.delta;
        d["gamma"] = res.gamma;
        d["vega"] = res.vega;
        d["theta"] = res.theta;
        d["rho"]   = res.rho;
        return d;
    }, "Black-Scholes pricing", py::arg("params"));
    m.def("implied_volatility", &qf::pricingengines::impliedVolatility, "Implied volatility via Brent", 
          py::arg("params"), py::arg("marketPrice"), py::arg("tol") = 1e-6, py::arg("maxIt") = 100);

    m.def("binomial_tree_price", &qf::pricingengines::binomialTreeBSPrice, "Binomial tree BS price",
          py::arg("params"), py::arg("nSteps") = 1000);

    m.def("montecarlo_price", &qf::pricingengines::monteCarloBSPrice, "Monte Carlo BS price",
          py::arg("params"), py::arg("N") = 100000, py::arg("seed") = 42);

    m.def("finite_difference_price", &qf::pricingengines::finiteDifferenceBSPrice, "Finite difference BS price",
          py::arg("params"), py::arg("nS") = 200, py::arg("nT") = 200, py::arg("method") = qf::pricingengines::FDMethod::CrankNicolson);

    py::class_<qf::pricingengines::HestonParams>(m, "HestonParams")
        .def(py::init<>())
        .def_readwrite("v0", &qf::pricingengines::HestonParams::v0)
        .def_readwrite("kappa", &qf::pricingengines::HestonParams::kappa)
        .def_readwrite("theta", &qf::pricingengines::HestonParams::theta)
        .def_readwrite("sigma", &qf::pricingengines::HestonParams::sigma)
        .def_readwrite("rho", &qf::pricingengines::HestonParams::rho);

    m.def("heston_price", &qf::pricingengines::hestonPrice, "Heston analytical price",
          py::arg("opt"), py::arg("heston"));
    m.def("heston_montecarlo", &qf::pricingengines::hestonMonteCarlo, "Heston Monte Carlo price",
          py::arg("opt"), py::arg("heston"), py::arg("nPaths") = 100000, py::arg("nSteps") = 252, py::arg("seed") = 42);

    // ------------------------------------------------------------------ //
    // HullWhite — short-rate model (needed by CVACalculator in qfxva)    //
    // ------------------------------------------------------------------ //
    py::class_<qf::models::HullWhite>(m, "HullWhite")
        .def(py::init<double, double, const qf::termstructure::YieldCurve&>(),
             py::arg("a"), py::arg("sigma"), py::arg("curve"),
             "Hull-White short-rate model. a = mean-reversion speed, sigma = volatility.")
        .def("bond_price",  &qf::models::HullWhite::bondPrice,  py::arg("T"))
        .def("zero_rate",   &qf::models::HullWhite::zeroRate,   py::arg("T"))
        .def("simulate",    &qf::models::HullWhite::simulate,
             py::arg("T"), py::arg("steps"), py::arg("seed") = 42)
        .def("conditional_bond_price", &qf::models::HullWhite::conditionalBondPrice,
             py::arg("t"), py::arg("T"), py::arg("r_t"));
}
