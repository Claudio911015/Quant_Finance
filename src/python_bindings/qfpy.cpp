#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <tuple>
#include <vector>

#include <qf/core/market_environment.hpp>
#include <qf/instruments/bond.hpp>
#include <qf/instruments/option.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/termstructure/volsurface.hpp>
#include <qf/math/interpolation.hpp>
#include <qf/pricingengines/ipricing_engine.hpp>
#include <qf/pricingengines/engine_factory.hpp>
#include <qf/pricingengines/blackscholes.hpp>
#include <qf/pricingengines/binomialtree.hpp>
#include <qf/pricingengines/montecarlo.hpp>
#include <qf/pricingengines/finite_difference.hpp>
#include <qf/pricingengines/heston.hpp>
#include <qf/instruments/iunderlying.hpp>
#include <qf/instruments/instrument.hpp>
#include <qf/models/hullwhite.hpp>
#include <qf/models/heston_calibrator.hpp>
#include <qf/instruments/swap.hpp>
#include <qf/risk/scenario.hpp>

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
        .def("set_vol_surface", &qf::core::MarketEnvironment::setVolSurface,
             py::arg("ticker"), py::arg("surface"),
             "Register a VolSurface for a ticker (P4). Once set, the (strike, maturity) "
             "volatility() overload and all equity engines mark off the surface.")
        .def("has_vol_surface", &qf::core::MarketEnvironment::hasVolSurface,
             py::arg("ticker"))
        .def("spot",           &qf::core::MarketEnvironment::spot,      py::arg("ticker"))
        .def("volatility",
             static_cast<double (qf::core::MarketEnvironment::*)(const std::string&) const>(
                 &qf::core::MarketEnvironment::volatility),
             py::arg("ticker"), "Flat scalar implied vol for a ticker.")
        .def("volatility",
             static_cast<double (qf::core::MarketEnvironment::*)
                         (const std::string&, double, double) const>(
                 &qf::core::MarketEnvironment::volatility),
             py::arg("ticker"), py::arg("strike"), py::arg("maturity"),
             "Strike/maturity-aware implied vol: the ticker's VolSurface if set, else the flat scalar.")
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

    // ------------------------------------------------------------------ //
    // Instrument — abstract base; enables passing any instrument (e.g. a  //
    // Bond) to the ScenarioEngine, which takes a const Instrument&.        //
    // ------------------------------------------------------------------ //
    py::class_<qf::instruments::Instrument>(m, "Instrument")
        .def("pv",
             static_cast<double (qf::instruments::Instrument::*)
                         (const qf::core::MarketEnvironment&) const>(
                 &qf::instruments::Instrument::pv),
             py::arg("env"), "Present value against a MarketEnvironment.")
        .def("maturity", &qf::instruments::Instrument::maturity);

    py::class_<qf::instruments::Bond, qf::instruments::Instrument>(m, "Bond")
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
        .def("forward_rate", &qf::termstructure::YieldCurve::forwardRate)
        .def("maturities", &qf::termstructure::YieldCurve::maturities,
             py::return_value_policy::reference_internal,
             "Pillar maturities (years) the curve was built from.")
        .def("rates", &qf::termstructure::YieldCurve::rates,
             py::return_value_policy::reference_internal,
             "Pillar zero rates (decimal) aligned to maturities().")
        .def("interpolation_method", &qf::termstructure::YieldCurve::interpolationMethod)
        .def("parallel_bump", &qf::termstructure::YieldCurve::parallelBump,
             py::arg("bp_shift"),
             "Copy of the curve with every pillar shifted by bp_shift basis points.")
        .def("bumped", &qf::termstructure::YieldCurve::bumped,
             py::arg("pillar_index"), py::arg("bp_shift"),
             "Copy of the curve with a single pillar shifted by bp_shift basis points.");

    // ------------------------------------------------------------------ //
    // VolSurface (P4): per-ticker implied-vol surface                     //
    // ------------------------------------------------------------------ //
    py::class_<qf::termstructure::VolSurface>(m, "VolSurface")
        .def(py::init<std::vector<double>, std::vector<double>,
                      std::vector<std::vector<double>>, qf::math::InterpolationMethod>(),
             py::arg("maturities"), py::arg("strikes"), py::arg("vols"),
             py::arg("strike_method") = qf::math::InterpolationMethod::Linear,
             "Grid constructor: vols[i][j] is the implied vol at maturities[i] x strikes[j].")
        .def_static("from_quotes", &qf::termstructure::VolSurface::fromQuotes,
             py::arg("spot"), py::arg("r"), py::arg("q"), py::arg("quotes"),
             py::arg("strike_method") = qf::math::InterpolationMethod::Linear,
             "Build a surface from a complete rectangular chain of OptionQuote by inverting "
             "each quote with the Brent implied-vol solver.")
        .def("vol", &qf::termstructure::VolSurface::vol,
             py::arg("strike"), py::arg("maturity"),
             "Implied vol at (strike, maturity): smile-interp in strike, total-variance in T.")
        .def("maturities", &qf::termstructure::VolSurface::maturities,
             py::return_value_policy::reference_internal)
        .def("strikes", &qf::termstructure::VolSurface::strikes,
             py::return_value_policy::reference_internal)
        .def("to_grid", [](const qf::termstructure::VolSurface& s) {
                 return py::make_tuple(s.maturities(), s.strikes(), s.vols());
             },
             "Return (maturities, strikes, vols) pillar arrays for pandas/matplotlib plots.");

    // Bridge closing the P3 loop: price a strike x maturity grid through the
    // semi-analytic Heston, invert with the Brent solver, and return a smooth
    // arbitrage-consistent VolSurface. The standard way to regularize a sparse or
    // noisy listed chain into a full surface via the calibrated model.
    m.def("surface_from_heston",
          [](const qf::pricingengines::HestonParams& heston,
             double spot, double r, double q,
             const std::vector<double>& strikes,
             const std::vector<double>& maturities,
             qf::math::InterpolationMethod strike_method) {
              std::vector<std::vector<double>> vols(
                  maturities.size(), std::vector<double>(strikes.size(), 0.0));
              for (std::size_t i = 0; i < maturities.size(); ++i) {
                  for (std::size_t j = 0; j < strikes.size(); ++j) {
                      qf::instruments::OptionParams p;
                      p.spot          = spot;
                      p.strike        = strikes[j];
                      p.riskFreeRate  = r;
                      p.dividendYield = q;
                      p.volatility    = 0.0;
                      p.maturity      = maturities[i];
                      p.type          = qf::instruments::OptionType::Call;
                      p.exercise      = qf::instruments::ExerciseType::European;
                      double px = qf::pricingengines::hestonPrice(p, heston);
                      vols[i][j] = qf::pricingengines::impliedVolatility(p, px);
                  }
              }
              return qf::termstructure::VolSurface(maturities, strikes,
                                                   std::move(vols), strike_method);
          },
          py::arg("params"), py::arg("spot"), py::arg("r"), py::arg("q"),
          py::arg("strikes"), py::arg("maturities"),
          py::arg("strike_method") = qf::math::InterpolationMethod::Linear,
          "Build a smooth VolSurface by pricing a strike x maturity grid under calibrated "
          "HestonParams and inverting to Black-Scholes implied vols.");

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
    // Heston calibration (P3): fit HestonParams to listed vanilla quotes  //
    // ------------------------------------------------------------------ //
    py::class_<qf::models::OptionQuote>(m, "OptionQuote")
        .def(py::init<>())
        .def(py::init([](double strike, double maturity,
                         qf::instruments::OptionType type, double marketPrice) {
                 return qf::models::OptionQuote{strike, maturity, type, marketPrice};
             }),
             py::arg("strike"), py::arg("maturity"), py::arg("type"), py::arg("market_price"))
        .def_readwrite("strike",       &qf::models::OptionQuote::strike)
        .def_readwrite("maturity",     &qf::models::OptionQuote::maturity)
        .def_readwrite("type",         &qf::models::OptionQuote::type)
        .def_readwrite("market_price", &qf::models::OptionQuote::marketPrice);

    py::enum_<qf::models::CalibrationObjective>(m, "CalibrationObjective")
        .value("Price",      qf::models::CalibrationObjective::Price)
        .value("ImpliedVol", qf::models::CalibrationObjective::ImpliedVol);

    py::class_<qf::models::CalibrationResult>(m, "CalibrationResult")
        .def_readonly("params",          &qf::models::CalibrationResult::params)
        .def_readonly("rmse",            &qf::models::CalibrationResult::rmse)
        .def_readonly("per_quote_errors",&qf::models::CalibrationResult::perQuoteErrors)
        .def_readonly("converged",       &qf::models::CalibrationResult::converged)
        .def_readonly("iterations",      &qf::models::CalibrationResult::iterations);

    py::class_<qf::models::HestonCalibrator>(m, "HestonCalibrator")
        .def(py::init<double, double, double>(),
             py::arg("spot"), py::arg("r"), py::arg("q") = 0.0)
        .def("calibrate", &qf::models::HestonCalibrator::calibrate,
             py::arg("quotes"), py::arg("initial_guess"),
             py::arg("objective") = qf::models::CalibrationObjective::Price,
             py::arg("vega_weighted") = false,
             py::arg("tol") = 1e-8, py::arg("maxIt") = 2000,
             "Fit HestonParams to a set of OptionQuote against the semi-analytic price.");

    // DataFrame-friendly convenience: quotes as (strike, maturity, type, price)
    // tuples straight off a listed chain -> CalibrationResult whose .params
    // plug into make_heston_engine.
    m.def("calibrate_heston",
          [](double spot, double r, double q,
             const std::vector<std::tuple<double, double,
                     qf::instruments::OptionType, double>>& quotes,
             qf::models::CalibrationObjective objective,
             bool vega_weighted) {
              std::vector<qf::models::OptionQuote> qs;
              qs.reserve(quotes.size());
              for (const auto& t : quotes)
                  qs.push_back({std::get<0>(t), std::get<1>(t),
                                std::get<2>(t), std::get<3>(t)});
              qf::models::HestonCalibrator calib(spot, r, q);
              return calib.calibrate(qs, qf::pricingengines::HestonParams{
                                             0.04, 1.5, 0.04, 0.4, -0.5},
                                     objective, vega_weighted);
          },
          py::arg("spot"), py::arg("r"), py::arg("q"),
          py::arg("quotes"),
          py::arg("objective") = qf::models::CalibrationObjective::Price,
          py::arg("vega_weighted") = false,
          "Calibrate Heston to a list of (strike, maturity, OptionType, price) "
          "quotes. Returns a CalibrationResult; .params feed make_heston_engine.");

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

    // ── SwapType enum ─────────────────────────────────────────────────────
    py::enum_<qf::instruments::SwapType>(m, "SwapType")
        .value("Payer",    qf::instruments::SwapType::Payer)
        .value("Receiver", qf::instruments::SwapType::Receiver)
        .export_values();

    // ── CurveKeys (dual-curve, P5) ─────────────────────────────────────────
    py::class_<qf::instruments::CurveKeys>(m, "CurveKeys")
        .def(py::init([](std::string discount_key, std::string projection_key) {
                 return qf::instruments::CurveKeys{std::move(discount_key),
                                                   std::move(projection_key)};
             }),
             py::arg("discount_key") = "default",
             py::arg("projection_key") = "default",
             "Named discount + projection curves a swap prices against (dual-curve).\n"
             "Both default to 'default' → single-curve, output bit-identical to legacy.")
        .def_readwrite("discount_key",   &qf::instruments::CurveKeys::discountKey)
        .def_readwrite("projection_key", &qf::instruments::CurveKeys::projectionKey)
        .def("keys_equal", &qf::instruments::CurveKeys::keysEqual);

    // ── InterestRateSwap ───────────────────────────────────────────────────
    // Declares the Instrument base so an IRS can be passed to the bound
    // ScenarioEngine (which takes a const Instrument&) — impossible before P5.
    py::class_<qf::instruments::InterestRateSwap, qf::instruments::Instrument>(m, "InterestRateSwap")
        .def(py::init<double, double, double, double, qf::instruments::SwapType>(),
             py::arg("notional"), py::arg("fixed_rate"),
             py::arg("maturity"), py::arg("frequency"), py::arg("swap_type"),
             "Vanilla fixed-for-floating IRS with uniform payment schedule.\n"
             "swap_type: SwapType.Payer (pay fixed) or SwapType.Receiver (receive fixed).")
        .def(py::init<double, double, double, double, qf::instruments::SwapType,
                      qf::instruments::CurveKeys>(),
             py::arg("notional"), py::arg("fixed_rate"),
             py::arg("maturity"), py::arg("frequency"), py::arg("swap_type"),
             py::arg("curve_keys"),
             "Dual-curve IRS: project floating off curve_keys.projection_key,\n"
             "discount off curve_keys.discount_key.")
        .def("npv",
             static_cast<double (qf::instruments::InterestRateSwap::*)
                         (const qf::core::MarketEnvironment&) const>(
                 &qf::instruments::InterestRateSwap::npv),
             py::arg("env"), "Net present value from the swap_type perspective.")
        .def("curve_keys", &qf::instruments::InterestRateSwap::curveKeys,
             // COPY, not reference_internal: CurveKeys fields are def_readwrite, and pybind
             // drops the C++ const, so a reference would let Python mutate the swap's
             // internal pricing keys (swap.curve_keys().projection_key = ... silently
             // repoints the mark). A copy of two small strings is cheap and safe.
             py::return_value_policy::copy,
             "The discount/projection curve keys this swap prices against (a copy).")
        .def_static("par_rate",
             static_cast<double (*)(double, double, const qf::core::MarketEnvironment&)>(
                 &qf::instruments::InterestRateSwap::parRate),
             py::arg("maturity"), py::arg("frequency"), py::arg("env"),
             "Par (fair) fixed rate at which NPV = 0 (single-curve).")
        .def_static("par_rate",
             static_cast<double (*)(double, double, const qf::core::MarketEnvironment&,
                                    const std::string&, const std::string&)>(
                 &qf::instruments::InterestRateSwap::parRate),
             py::arg("maturity"), py::arg("frequency"), py::arg("env"),
             py::arg("discount_key"), py::arg("projection_key"),
             "Dual-curve par rate: floating projected off projection_key,\n"
             "discounted off discount_key; annuity off discount_key.")
        .def_static("annuity",
             static_cast<double (*)(double, double, const qf::core::MarketEnvironment&)>(
                 &qf::instruments::InterestRateSwap::annuity),
             py::arg("maturity"), py::arg("frequency"), py::arg("env"),
             "Annuity (DV01 per unit notional) of the swap (single-curve).")
        .def_static("annuity",
             static_cast<double (*)(double, double, const qf::core::MarketEnvironment&,
                                    const std::string&)>(
                 &qf::instruments::InterestRateSwap::annuity),
             py::arg("maturity"), py::arg("frequency"), py::arg("env"),
             py::arg("discount_key"),
             "Dual-curve annuity off the discount curve discount_key.");

    // ── PeriodSpec ─────────────────────────────────────────────────────────
    py::class_<qf::instruments::PeriodSpec>(m, "PeriodSpec")
        .def(py::init([](double pay_time, double accrual_frac, double notional) {
                 return qf::instruments::PeriodSpec{pay_time, accrual_frac, notional};
             }),
             py::arg("pay_time"), py::arg("accrual_frac"), py::arg("notional"),
             "Single coupon period: pay_time in years, accrual_frac (τᵢ), notional.")
        .def_readwrite("pay_time",     &qf::instruments::PeriodSpec::payTime)
        .def_readwrite("accrual_frac", &qf::instruments::PeriodSpec::accrualFrac)
        .def_readwrite("notional",     &qf::instruments::PeriodSpec::notional);

    // ── ScheduledLeg ───────────────────────────────────────────────────────
    py::class_<qf::instruments::ScheduledLeg>(m, "ScheduledLeg")
        .def(py::init<double, bool, std::vector<qf::instruments::PeriodSpec>>(),
             py::arg("fixed_rate"), py::arg("pays_fixed"), py::arg("schedule"),
             "ScheduledLeg from explicit PeriodSpec list.\n"
             "fixed_rate: coupon rate (ignored for floating legs).\n"
             "pays_fixed: True = fixed coupon; False = floating (replication identity).")
        .def(py::init<double, bool, std::vector<qf::instruments::PeriodSpec>,
                      qf::instruments::CurveKeys>(),
             py::arg("fixed_rate"), py::arg("pays_fixed"), py::arg("schedule"),
             py::arg("curve_keys"),
             "Dual-curve ScheduledLeg: project floating off curve_keys.projection_key,\n"
             "discount off curve_keys.discount_key.")
        .def_static("make_fixed",
             &qf::instruments::ScheduledLeg::makeFixed,
             py::arg("notional"), py::arg("fixed_rate"), py::arg("payment_times"),
             py::arg("curve_keys") = qf::instruments::CurveKeys{},
             "Build a fixed leg from payment times (accrual = year fractions).")
        .def_static("make_floating",
             &qf::instruments::ScheduledLeg::makeFloating,
             py::arg("notional"), py::arg("spread"), py::arg("payment_times"),
             py::arg("curve_keys") = qf::instruments::CurveKeys{},
             "Build a floating leg from payment times.")
        .def("calculate_pv",
             &qf::instruments::ScheduledLeg::calculatePV,
             py::arg("env"), "Present value of this leg.")
        .def("curve_keys", &qf::instruments::ScheduledLeg::curveKeys,
             // COPY, not reference_internal — see InterestRateSwap.curve_keys above:
             // def_readwrite fields + dropped const would let Python mutate internal keys.
             py::return_value_policy::copy,
             "The discount/projection curve keys this leg prices against (a copy).")
        .def("schedule",
             &qf::instruments::ScheduledLeg::schedule,
             "Returns the list of PeriodSpec entries.");

    // ── ScheduledSwap ──────────────────────────────────────────────────────
    // Declares the Instrument base so a ScheduledSwap (amortizing/stub schedules)
    // can be passed to the bound ScenarioEngine — impossible before P5.
    py::class_<qf::instruments::ScheduledSwap, qf::instruments::Instrument>(m, "ScheduledSwap")
        .def(py::init<qf::instruments::ScheduledLeg,
                      qf::instruments::ScheduledLeg>(),
             py::arg("pay_leg"), py::arg("receive_leg"),
             "ScheduledSwap: pay_leg = what you pay, receive_leg = what you receive.\n"
             "Instrument maturity = max over both legs' final payment dates.")
        .def("npv",
             &qf::instruments::ScheduledSwap::npv,
             py::arg("env"), "Net present value: PV(receive) - PV(pay).")
        .def("cash_flows",
             &qf::instruments::ScheduledSwap::cashFlows,
             py::arg("env"),
             "Undiscounted net cash flows: list of (time, net_cf) sorted by time.\n"
             "Positive = net receipt; negative = net payment.");

    // ------------------------------------------------------------------ //
    // qf::risk ScenarioEngine — curve rate risk (parallel/key-rate DV01, //
    // named curve scenarios) for any Instrument (P2c).                    //
    // ------------------------------------------------------------------ //
    py::class_<qf::risk::KeyRateDV01>(m, "KeyRateDV01")
        .def_readonly("maturity", &qf::risk::KeyRateDV01::maturity)
        .def_readonly("dv01",     &qf::risk::KeyRateDV01::dv01)
        .def("__repr__", [](const qf::risk::KeyRateDV01& r) {
            return "KeyRateDV01(maturity=" + std::to_string(r.maturity)
                 + ", dv01=" + std::to_string(r.dv01) + ")";
        });

    py::class_<qf::risk::ScenarioResult>(m, "ScenarioResult")
        .def_readonly("label",       &qf::risk::ScenarioResult::label)
        .def_readonly("base_pv",     &qf::risk::ScenarioResult::basePV)
        .def_readonly("scenario_pv", &qf::risk::ScenarioResult::scenarioPV)
        .def_readonly("pnl",         &qf::risk::ScenarioResult::pnl);

    py::class_<qf::risk::ScenarioEngine>(m, "ScenarioEngine")
        .def(py::init<std::string, double>(),
             py::arg("curve_name") = "default", py::arg("bump_size_bp") = 1.0,
             "Curve rate-risk engine. Bumps are in basis points; DV01s are the dollar\n"
             "value of a 1 bp move, positive when PV rises as rates fall.")
        .def("parallel_dv01", &qf::risk::ScenarioEngine::parallelDV01,
             py::arg("instrument"), py::arg("env"),
             "Dollar value of a 1 bp parallel shift of the target curve.")
        .def("key_rate_dv01s", &qf::risk::ScenarioEngine::keyRateDV01s,
             py::arg("instrument"), py::arg("env"),
             "Key-rate DV01 ladder: one KeyRateDV01 per curve pillar.")
        .def("run_scenario", &qf::risk::ScenarioEngine::runScenario,
             py::arg("instrument"), py::arg("env"), py::arg("per_pillar_shifts_bp"),
             py::arg("label") = "custom",
             "Full revaluation under an arbitrary per-pillar shift (bp). Returns a "
             "ScenarioResult (base_pv, scenario_pv, pnl).")
        .def("parallel_shock", &qf::risk::ScenarioEngine::parallelShock,
             py::arg("instrument"), py::arg("env"), py::arg("magnitude_bp"),
             "Uniform parallel shock of magnitude_bp on every pillar.")
        .def("steepener", &qf::risk::ScenarioEngine::steepener,
             py::arg("instrument"), py::arg("env"), py::arg("magnitude_bp"),
             "Steepener: linear ramp from -mag (short) to +mag (long).")
        .def("flattener", &qf::risk::ScenarioEngine::flattener,
             py::arg("instrument"), py::arg("env"), py::arg("magnitude_bp"),
             "Flattener: linear ramp from +mag (short) to -mag (long).");

    m.def("key_rate_dv01_dataframe",
          [](const qf::risk::ScenarioEngine& engine,
             const qf::instruments::Instrument& inst,
             const qf::core::MarketEnvironment& env) {
              auto ladder = engine.keyRateDV01s(inst, env);
              std::vector<double> mats, dv01s;
              mats.reserve(ladder.size());
              dv01s.reserve(ladder.size());
              for (const auto& rung : ladder) {
                  mats.push_back(rung.maturity);
                  dv01s.push_back(rung.dv01);
              }
              py::dict d;
              d["maturity"] = mats;
              d["dv01"]     = dv01s;
              py::object pd = py::module_::import("pandas");
              return pd.attr("DataFrame")(d);
          },
          py::arg("engine"), py::arg("instrument"), py::arg("env"),
          "Return the key-rate DV01 ladder as a pandas DataFrame with columns "
          "maturity, dv01 (follows CVAResult.to_dataframe() precedent).");
}
