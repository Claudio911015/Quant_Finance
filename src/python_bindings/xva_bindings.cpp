#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <qf/xva/credit_curve.hpp>
#include <qf/xva/netting_set.hpp>
#include <qf/xva/cva_result.hpp>
#include <qf/xva/cva_calculator.hpp>
#include <qf/models/hullwhite.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/instruments/swap.hpp>

namespace py = pybind11;
using namespace qf::xva;
using namespace qf::instruments;

// ── Trampoline so Python subclasses can override survivalProbability ──────
class PyICreditCurve : public ICreditCurve {
public:
    using ICreditCurve::ICreditCurve;
    double survivalProbability(double t) const override {
        PYBIND11_OVERRIDE_PURE(double, ICreditCurve, survivalProbability, t);
    }
};

PYBIND11_MODULE(qfxva, m) {
    m.doc() = "qf::xva — CVA calculator Python bindings";

    // ── ICreditCurve (abstract base — subclassable from Python) ──────────
    py::class_<ICreditCurve, PyICreditCurve>(m, "ICreditCurve")
        .def(py::init<>())
        .def("survival_probability", &ICreditCurve::survivalProbability, py::arg("t"));

    // ── FlatHazardRate ────────────────────────────────────────────
    py::class_<FlatHazardRate, ICreditCurve>(m, "FlatHazardRate")
        .def(py::init<double>(), py::arg("lambda_"),
             "Flat hazard rate: SP(t) = exp(-lambda * t). "
             "lambda_ in decimal (e.g. 0.02 = 200 bps).")
        .def("survival_probability", &FlatHazardRate::survivalProbability, py::arg("t"));

    // ── SwapType enum ─────────────────────────────────────────────
    py::enum_<SwapType>(m, "SwapType")
        .value("Payer",    SwapType::Payer)
        .value("Receiver", SwapType::Receiver);

    // ── NettingSet ────────────────────────────────────────────────
    py::class_<NettingSet>(m, "NettingSet")
        .def(py::init<>())
        .def("add", &NettingSet::add,
             py::arg("notional"), py::arg("fixed_rate"), py::arg("maturity"),
             py::arg("frequency"), py::arg("swap_type"),
             "Add a vanilla IRS to the netting set.")
        .def("size", &NettingSet::size);

    // ── SimParams ─────────────────────────────────────────────────
    py::class_<SimParams>(m, "SimParams")
        .def(py::init([](std::size_t nPaths,
                         std::vector<double> monitorDates,
                         py::object seed) {
            SimParams p;
            p.nPaths       = nPaths;
            p.monitorDates = std::move(monitorDates);
            if (!seed.is_none())
                p.seed = seed.cast<unsigned int>();
            return p;
        }),
        py::arg("n_paths"), py::arg("monitor_dates"), py::arg("seed") = py::none())
        .def_readwrite("n_paths",       &SimParams::nPaths)
        .def_readwrite("monitor_dates", &SimParams::monitorDates);

    // ── TimeStep ──────────────────────────────────────────────────
    py::class_<TimeStep>(m, "TimeStep")
        .def_readonly("t",            &TimeStep::t)
        .def_readonly("epe",          &TimeStep::epe)
        .def_readonly("surv_prob",    &TimeStep::survProb)
        .def_readonly("contribution", &TimeStep::contribution);

    // ── CVAResult ─────────────────────────────────────────────────
    py::class_<CVAResult>(m, "CVAResult")
        .def_readonly("cva",     &CVAResult::cva)
        .def_readonly("profile", &CVAResult::profile)
        .def("to_dataframe", [](const CVAResult& r) {
            py::dict d;
            std::vector<double> ts, epes, sps, contribs;
            ts.reserve(r.profile.size());
            epes.reserve(r.profile.size());
            sps.reserve(r.profile.size());
            contribs.reserve(r.profile.size());
            for (const auto& step : r.profile) {
                ts.push_back(step.t);
                epes.push_back(step.epe);
                sps.push_back(step.survProb);
                contribs.push_back(step.contribution);
            }
            d["t"]            = ts;
            d["epe"]          = epes;
            d["surv_prob"]    = sps;
            d["contribution"] = contribs;
            py::object pd = py::module_::import("pandas");
            return pd.attr("DataFrame")(d);
        }, "Return profile as a pandas DataFrame with columns: t, epe, surv_prob, contribution.");

    // ── CVACalculator ─────────────────────────────────────────────
    py::class_<CVACalculator>(m, "CVACalculator")
        .def(py::init([](const qf::models::HullWhite& hw,
                         const ICreditCurve& credit,
                         double lgd,
                         SimParams params) {
                 return new CVACalculator(hw, credit, lgd, std::move(params));
             }),
             py::arg("hw"), py::arg("credit"), py::arg("lgd"), py::arg("params"),
             py::keep_alive<1,2>(),   // calculator keeps hw alive
             py::keep_alive<1,3>())   // calculator keeps credit alive
        .def("compute", &CVACalculator::compute,
             py::arg("netting_set"), py::arg("env"),
             "Run CVA simulation. Returns CVAResult.");
}
