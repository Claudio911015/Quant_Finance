#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <optional>
#include <qf/xva/credit_curve.hpp>
#include <qf/xva/piecewise_hazard_curve.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/xva/netting_set.hpp>
#include <qf/xva/cva_result.hpp>
#include <qf/xva/cva_calculator.hpp>
#include <qf/xva/exposure_profile.hpp>
#include <qf/xva/exposure_engine.hpp>
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

    // True si qf se compiló con XAD (QF_WITH_XAD): xva_sensitivities solo calcula en ese caso.
#ifdef QF_WITH_XAD
    m.attr("HAS_XAD") = true;
#else
    m.attr("HAS_XAD") = false;
#endif

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

    // ── PiecewiseHazardCurve / CDS bootstrap ──────────────────────
    py::class_<PiecewiseHazardCurve, ICreditCurve>(m, "PiecewiseHazardCurve")
        .def(py::init<std::vector<double>, std::vector<double>>(),
             py::arg("times"), py::arg("hazards"),
             "Piecewise-constant hazard curve: hazards[i] applies on (times[i-1], times[i]] "
             "(times[-1] = 0), flat beyond the last vertex. ValueError on invalid input.")
        .def("survival_probability", &PiecewiseHazardCurve::survivalProbability, py::arg("t"))
        .def("hazard_rate", &PiecewiseHazardCurve::hazardRate, py::arg("t"))
        .def("times", &PiecewiseHazardCurve::times)
        .def("hazards", &PiecewiseHazardCurve::hazards);

    py::class_<CdsQuote>(m, "CdsQuote")
        .def(py::init([](double tenorYears, double spread) { return CdsQuote{tenorYears, spread}; }),
             py::arg("tenor_years"), py::arg("spread"),
             "Par CDS quote: tenor in years and spread in decimal (0.0080 = 80 bp).")
        .def_readwrite("tenor_years", &CdsQuote::tenorYears)
        .def_readwrite("spread",      &CdsQuote::spread);

    // `discount` is a qfpy.YieldCurve: import qfpy BEFORE qfxva so both share the C++ type.
    m.def("bootstrap_cds_curve",
          [](const std::vector<CdsQuote>& quotes, double recovery,
             const qf::termstructure::YieldCurve& discount) {
              return bootstrapCdsCurve(quotes, recovery, discount);
          },
          py::arg("quotes"), py::arg("recovery"), py::arg("discount"),
          "Bootstrap a PiecewiseHazardCurve so that every CdsQuote reprices to zero. "
          "ValueError if the quotes imply a negative hazard rate or are invalid.");

    m.def("cds_value",
          [](const CdsQuote& quote, double recovery, const ICreditCurve& curve,
             const qf::termstructure::YieldCurve& discount, double notional) {
              return cdsValue(quote, recovery, curve, discount, notional);
          },
          py::arg("quote"), py::arg("recovery"), py::arg("curve"), py::arg("discount"),
          py::arg("notional") = 1.0,
          "Value of the CDS for the protection buyer (protection leg - premium leg), times notional.");

    // ── Multi-currency exposure engine ────────────────────────────
    // The curves are qfpy.YieldCurve objects: import qfpy BEFORE qfxva so both share the C++ type.
    // std::invalid_argument becomes ValueError.
    py::enum_<SwapCurrency>(m, "SwapCurrency")
        .value("MXN", SwapCurrency::MXN)
        .value("USD", SwapCurrency::USD);

    py::class_<RateSwapSpec>(m, "RateSwapSpec")
        .def(py::init([](SwapCurrency currency, double notional, double fixedRate, bool payer, int startDays,
                         std::vector<int> payDays, double accruedFactor, double dayBase, bool csaDiscount) {
                 return RateSwapSpec{currency, notional, fixedRate, payer, startDays, std::move(payDays),
                                     accruedFactor, dayBase, csaDiscount};
             }),
             py::arg("currency"), py::arg("notional"), py::arg("fixed_rate"), py::arg("payer"),
             py::arg("start_days"), py::arg("pay_days"), py::arg("accrued_factor"),
             py::arg("day_base") = 360.0, py::arg("csa_discount") = false,
             "OIS swap aged to today. Days are counted from today; MXN projects on TIIE-F, USD on SOFR; "
             "csa_discount (MXN only) discounts with MXN-USD.")
        .def_readwrite("currency",      &RateSwapSpec::currency)
        .def_readwrite("notional",      &RateSwapSpec::notional)
        .def_readwrite("fixed_rate",    &RateSwapSpec::fixedRate)
        .def_readwrite("payer",         &RateSwapSpec::payer)
        .def_readwrite("start_days",    &RateSwapSpec::startDays)
        .def_readwrite("pay_days",      &RateSwapSpec::payDays)
        .def_readwrite("accrued_factor", &RateSwapSpec::accruedFactor)
        .def_readwrite("day_base",      &RateSwapSpec::dayBase)
        .def_readwrite("csa_discount",  &RateSwapSpec::csaDiscount);

    py::class_<XccySwapSpec>(m, "XccySwapSpec")
        .def(py::init([](double notionalUsd, double fxRate, double spread, int startDays, std::vector<int> payDays,
                         double accruedFactorUsd, double accruedFactorMxn, bool payUsd, bool initialExchange,
                         bool finalExchange, double dayBase, bool csaDiscount) {
                 return XccySwapSpec{notionalUsd, fxRate, spread, startDays, std::move(payDays), accruedFactorUsd,
                                     accruedFactorMxn, payUsd, initialExchange, finalExchange, dayBase, csaDiscount};
             }),
             py::arg("notional_usd"), py::arg("fx_rate"), py::arg("spread"), py::arg("start_days"),
             py::arg("pay_days"), py::arg("accrued_factor_usd"), py::arg("accrued_factor_mxn"),
             py::arg("pay_usd"), py::arg("initial_exchange"), py::arg("final_exchange"),
             py::arg("day_base") = 360.0, py::arg("csa_discount") = true,
             "Cross currency swap aged to today (USD SOFR leg against MXN TIIE-F + spread leg). "
             "pay_usd = pays USD, receives MXN.")
        .def_readwrite("notional_usd",       &XccySwapSpec::notionalUsd)
        .def_readwrite("fx_rate",            &XccySwapSpec::fxRate)
        .def_readwrite("spread",             &XccySwapSpec::spread)
        .def_readwrite("start_days",         &XccySwapSpec::startDays)
        .def_readwrite("pay_days",           &XccySwapSpec::payDays)
        .def_readwrite("accrued_factor_usd", &XccySwapSpec::accruedFactorUsd)
        .def_readwrite("accrued_factor_mxn", &XccySwapSpec::accruedFactorMxn)
        .def_readwrite("pay_usd",            &XccySwapSpec::payUsd)
        .def_readwrite("initial_exchange",   &XccySwapSpec::initialExchange)
        .def_readwrite("final_exchange",     &XccySwapSpec::finalExchange)
        .def_readwrite("day_base",           &XccySwapSpec::dayBase)
        .def_readwrite("csa_discount",       &XccySwapSpec::csaDiscount);

    py::class_<NettingSetSpec>(m, "NettingSetSpec")
        .def(py::init([](std::vector<RateSwapSpec> swaps, std::vector<XccySwapSpec> xccys) {
                 return NettingSetSpec{std::move(swaps), std::move(xccys)};
             }),
             py::arg("swaps") = std::vector<RateSwapSpec>{}, py::arg("xccys") = std::vector<XccySwapSpec>{},
             "Netting set of swaps and cross currency swaps (all valued together, in MXN).")
        .def_readwrite("swaps",  &NettingSetSpec::swaps)
        .def_readwrite("xccys",  &NettingSetSpec::xccys);

    py::class_<ExposureMarket>(m, "ExposureMarket")
        .def(py::init([](const qf::termstructure::YieldCurve& tiie, const qf::termstructure::YieldCurve& sofr,
                         double spot, std::optional<qf::termstructure::YieldCurve> mxnUsd) {
                 return ExposureMarket{tiie, sofr, std::move(mxnUsd), spot};
             }),
             py::arg("tiie"), py::arg("sofr"), py::arg("spot"), py::arg("mxn_usd") = py::none(),
             "TIIE-F and SOFR curves (qfpy.YieldCurve), USDMXN spot (MXN per USD) and, if any spec uses "
             "csa_discount, the MXN-USD curve.");

    py::class_<ExposureModel>(m, "ExposureModel")
        .def(py::init([](double aMxn, double sigmaMxn, double aUsd, double sigmaUsd, double fxVol,
                         double rhoMxnUsd, double rhoMxnFx, double rhoUsdFx) {
                 return ExposureModel{aMxn, sigmaMxn, aUsd, sigmaUsd, fxVol, rhoMxnUsd, rhoMxnFx, rhoUsdFx};
             }),
             py::arg("a_mxn"), py::arg("sigma_mxn"), py::arg("a_usd"), py::arg("sigma_usd"), py::arg("fx_vol"),
             py::arg("rho_mxn_usd"), py::arg("rho_mxn_fx"), py::arg("rho_usd_fx"),
             "Hull-White one factor per currency plus lognormal USDMXN, risk-neutral MXN measure.");

    py::class_<SimConfig>(m, "SimConfig")
        .def(py::init([](std::size_t nPaths, unsigned seed, double pfeQuantile, std::vector<int> reportDays) {
                 return SimConfig{nPaths, seed, pfeQuantile, std::move(reportDays)};
             }),
             py::arg("n_paths"), py::arg("seed"), py::arg("pfe_quantile"), py::arg("report_days"),
             "Paths, seed, PFE quantile in (0,1) and report days (from today, increasing, first = 0).");

    // The path-by-path matrices of the C++ profile stay inside the object (compute_xva needs them for
    // the standard errors) but are not exposed.
    py::class_<ExposureProfile>(m, "ExposureProfile")
        .def_readonly("days",           &ExposureProfile::days)
        .def_readonly("times",          &ExposureProfile::times)
        .def_readonly("expected_value", &ExposureProfile::expectedValue)
        .def_readonly("epe",            &ExposureProfile::epe)
        .def_readonly("ene",            &ExposureProfile::ene)
        .def_readonly("pfe",            &ExposureProfile::pfe)
        .def_readonly("epe_disc",       &ExposureProfile::epeDisc)
        .def_readonly("ene_disc",       &ExposureProfile::eneDisc)
        .def_readonly("value_at_zero",  &ExposureProfile::valueAtZero);

    py::class_<ExposureEngine>(m, "ExposureEngine")
        .def(py::init<ExposureMarket, ExposureModel, SimConfig>(),
             py::arg("market"), py::arg("model"), py::arg("config"))
        // Seconds of pure C++: release the GIL so a threaded server keeps answering other requests.
        // The arguments are converted to C++ values before the guard, and the result is cast after it.
        .def("simulate", &ExposureEngine::simulate, py::arg("sets"), py::call_guard<py::gil_scoped_release>(),
             "Simulate every netting set on the same paths. Returns one ExposureProfile per set (MXN).")
        .def("trade_values_at_zero", &ExposureEngine::tradeValuesAtZero, py::arg("netting_set"),
             "Value in MXN at t = 0 of each trade (swaps first, then cross currency swaps).")
        .def("xva_sensitivities", &ExposureEngine::xvaSensitivities,
             py::arg("netting_set"), py::arg("counterparty"), py::arg("counterparty_lgd"),
             py::arg("own"), py::arg("own_lgd"), py::arg("funding_spread"), py::arg("max_threads") = 2,
             py::call_guard<py::gil_scoped_release>(),
             "CVA, DVA and FVA of a netting set and their derivatives with respect to every input, by "
             "adjoint differentiation (XAD), on at most max_threads threads (more do not speed it up). "
             "Raises RuntimeError when qf was built with QF_WITH_XAD=OFF.");

    py::class_<XvaResult>(m, "XvaResult")
        .def_readonly("cva",        &XvaResult::cva)
        .def_readonly("cva_stderr", &XvaResult::cvaStdErr)
        .def_readonly("dva",        &XvaResult::dva)
        .def_readonly("dva_stderr", &XvaResult::dvaStdErr)
        .def_readonly("fva",        &XvaResult::fva)
        .def_readonly("total",      &XvaResult::total);

    py::class_<XvaGreeks>(m, "XvaGreeks")
        .def_readonly("tiie",                &XvaGreeks::tiie)
        .def_readonly("sofr",                &XvaGreeks::sofr)
        .def_readonly("mxn_usd",             &XvaGreeks::mxnUsd)
        .def_readonly("spot",                &XvaGreeks::spot)
        .def_readonly("fx_vol",              &XvaGreeks::fxVol)
        .def_readonly("sigma_mxn",           &XvaGreeks::sigmaMxn)
        .def_readonly("a_mxn",               &XvaGreeks::aMxn)
        .def_readonly("sigma_usd",           &XvaGreeks::sigmaUsd)
        .def_readonly("a_usd",               &XvaGreeks::aUsd)
        .def_readonly("counterparty_hazard", &XvaGreeks::counterpartyHazard)
        .def_readonly("own_hazard",          &XvaGreeks::ownHazard)
        .def_readonly("funding_spread",      &XvaGreeks::fundingSpread);

    py::class_<XvaSensitivities>(m, "XvaSensitivities")
        .def_readonly("value", &XvaSensitivities::value)
        .def_readonly("cva",   &XvaSensitivities::cva)
        .def_readonly("dva",   &XvaSensitivities::dva)
        .def_readonly("fva",   &XvaSensitivities::fva);

    // A curve written in Python reacquires the GIL by itself inside its override (PYBIND11_OVERRIDE).
    m.def("compute_xva", &computeXva,
          py::arg("profile"), py::arg("counterparty"), py::arg("counterparty_lgd"),
          py::arg("own"), py::arg("own_lgd"), py::arg("funding_spread"),
          py::call_guard<py::gil_scoped_release>(),
          "CVA, DVA and FVA of a netting set from its discounted exposure, with the Monte Carlo standard "
          "errors of CVA and DVA. total = cva - dva + fva. ValueError on invalid LGD, spread or profile.");

    // ── SwapType enum ─────────────────────────────────────────────
    // qfpy registers the same C++ enum; registering it twice makes `import qfxva` fail with
    // "type SwapType is already registered". When qfpy was imported first, reuse its Python
    // type so both modules coexist in one process (import qfpy BEFORE qfxva).
    if (auto* known = py::detail::get_type_info(std::type_index(typeid(SwapType)))) {
        m.attr("SwapType") =
            py::reinterpret_borrow<py::object>(reinterpret_cast<PyObject*>(known->type));
    } else {
        py::enum_<SwapType>(m, "SwapType")
            .value("Payer",    SwapType::Payer)
            .value("Receiver", SwapType::Receiver);
    }

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

    // ── ExposurePoint / simulate_exposure ─────────────────────────
    py::class_<ExposurePoint>(m, "ExposurePoint")
        .def_readonly("t",   &ExposurePoint::t)
        .def_readonly("epe", &ExposurePoint::epe)
        .def_readonly("ene", &ExposurePoint::ene)
        .def_readonly("pfe", &ExposurePoint::pfe);

    m.def("simulate_exposure",
          [](const qf::models::HullWhite& hw, const NettingSet& ns,
             const SimParams& params, double pfeQuantile) {
              return simulateExposure(hw, ns, params, pfeQuantile);
          },
          py::arg("hw"), py::arg("netting_set"), py::arg("params"),
          py::arg("pfe_quantile") = 0.95,
          "Simulate EPE, ENE and PFE per monitor date on the same paths as CVACalculator. "
          "PFE is the empirical pfe_quantile (in (0,1)) of max(V,0). "
          "Returns a list of ExposurePoint(t, epe, ene, pfe).");
}
