#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <qf/instruments/bond.hpp>
#include <qf/instruments/option.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <qf/pricingengines/binomialtree.hpp>
#include <qf/pricingengines/montecarlo.hpp>
#include <qf/pricingengines/finite_difference.hpp>

namespace py = pybind11;

PYBIND11_MODULE(qfpy, m) {
    m.doc() = "Quant_Finance C++ bindings";

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

    py::class_<qf::termstructure::YieldCurve>(m, "YieldCurve")
        .def(py::init<const std::vector<double>&, const std::vector<double>&, qf::math::InterpolationMethod>(),
             py::arg("maturities"), py::arg("zeroRates"), py::arg("method"));

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
}
