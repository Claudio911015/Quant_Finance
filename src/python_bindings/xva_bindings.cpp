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
        .def_readonly("t",                &TimeStep::t)
        .def_readonly("epe",              &TimeStep::epe)
        .def_readonly("ene",              &TimeStep::ene)
        .def_readonly("surv_prob",        &TimeStep::survProb)
        .def_readonly("own_surv_prob",    &TimeStep::ownSurvProb)
        .def_readonly("contribution",     &TimeStep::contribution)
        .def_readonly("dva_contribution", &TimeStep::dvaContribution)
        .def_readonly("fva_contribution", &TimeStep::fvaContribution);

    // ── CVAResult ─────────────────────────────────────────────────
    py::class_<CVAResult>(m, "CVAResult")
        .def_readonly("cva",     &CVAResult::cva)
        .def_readonly("dva",     &CVAResult::dva)
        .def_readonly("fva",     &CVAResult::fva)
        .def_readonly("bcva",    &CVAResult::bcva)
        .def_readonly("profile", &CVAResult::profile)
        .def("to_dataframe", [](const CVAResult& r) {
            py::dict d;
            std::vector<double> ts, epes, enes, sps, ownSps, contribs, dvaContribs, fvaContribs;
            const auto n = r.profile.size();
            ts.reserve(n); epes.reserve(n); enes.reserve(n);
            sps.reserve(n); ownSps.reserve(n);
            contribs.reserve(n); dvaContribs.reserve(n); fvaContribs.reserve(n);
            for (const auto& step : r.profile) {
                ts.push_back(step.t);
                epes.push_back(step.epe);
                enes.push_back(step.ene);
                sps.push_back(step.survProb);
                ownSps.push_back(step.ownSurvProb);
                contribs.push_back(step.contribution);
                dvaContribs.push_back(step.dvaContribution);
                fvaContribs.push_back(step.fvaContribution);
            }
            d["t"]                = ts;
            d["epe"]              = epes;
            d["ene"]              = enes;
            d["surv_prob"]        = sps;
            d["own_surv_prob"]    = ownSps;
            d["contribution"]     = contribs;
            d["dva_contribution"] = dvaContribs;
            d["fva_contribution"] = fvaContribs;
            py::object pd = py::module_::import("pandas");
            return pd.attr("DataFrame")(d);
        }, "Return profile as a pandas DataFrame with columns: t, epe, ene, surv_prob, "
           "own_surv_prob, contribution, dva_contribution, fva_contribution.");

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
        .def("set_own_credit", &CVACalculator::setOwnCredit,
             py::arg("own_credit"), py::arg("own_lgd"),
             py::keep_alive<1,2>(),   // calculator keeps own_credit alive
             "Enable DVA using the firm's own credit curve and own LGD in [0,1].")
        .def("set_funding_spread", &CVACalculator::setFundingSpread,
             py::arg("funding_spread"),
             "Enable FVA using a scalar funding spread (decimal, >= 0).")
        .def("compute", &CVACalculator::compute,
             py::arg("netting_set"), py::arg("env"),
             "Run the exposure simulation. Returns CVAResult with cva, dva, fva, bcva.");
}
