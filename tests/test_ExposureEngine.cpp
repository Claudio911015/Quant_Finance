#include <gtest/gtest.h>
#include <qf/xva/exposure_engine.hpp>
#include <qf/xva/credit_curve.hpp>
#include <qf/xva/piecewise_hazard_curve.hpp>
#include <qf/xva/cva_calculator.hpp>
#include <qf/xva/netting_set.hpp>
#include <qf/models/hullwhite.hpp>
#include <qf/instruments/swap.hpp>
#include <qf/instruments/ois_swap.hpp>
#include <qf/instruments/xccy_swap.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/interpolation.hpp>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <optional>
#include <set>
#include <thread>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
#ifdef __linux__
#include <sched.h>
#endif

#include <array>

using namespace qf::xva;
using qf::core::MarketEnvironment;
using qf::instruments::OisSwap;
using qf::instruments::SwapType;
using qf::instruments::XccySide;
using qf::instruments::XccySwap;
using qf::math::DayCountConvention;
using qf::math::InterpolationMethod;
using qf::termstructure::YieldCurve;


// Internal helpers of exposure_engine.cpp (external linkage on purpose; not part of the public header).
namespace qf::xva::detail {
struct OuMoments {
    double y;
    double m;
    double mInt;
};
OuMoments ouMoments(double a, double sigma, double mu, double t);
std::array<std::array<double, 5>, 5> stepCovariance(const ExposureModel& model, double dt);
std::size_t aadTapeBytes();
std::size_t aadThreads();
} // namespace qf::xva::detail

namespace {

constexpr double kSpot = 18.6;

// ---- market: TIIE-F ~7 %, SOFR ~3.7 %, MXN-USD = TIIE-F shifted -10 bp ----------------------

YieldCurve tiieCurve(double shift = 0.0) {
    return YieldCurve({0.25, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 12.0},
                      {0.0690 + shift, 0.0700 + shift, 0.0705 + shift, 0.0710 + shift,
                       0.0715 + shift, 0.0720 + shift, 0.0725 + shift, 0.0728 + shift},
                      InterpolationMethod::Linear);
}
YieldCurve sofrCurve() {
    return YieldCurve({0.25, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 12.0},
                      {0.0365, 0.0368, 0.0370, 0.0372, 0.0375, 0.0380, 0.0385, 0.0388},
                      InterpolationMethod::Linear);
}
YieldCurve basisCurve() { return tiieCurve(-0.0010); }

ExposureMarket makeMarket(bool withBasis = true, double basisShift = -0.0010) {
    return ExposureMarket{tiieCurve(), sofrCurve(),
                          withBasis ? std::optional<YieldCurve>(tiieCurve(basisShift)) : std::nullopt, kSpot};
}

// Hull-White / FX parameters as MX-DEMO, correlations 0.35 / 0.30 / -0.10, fx vol 0.12.
ExposureModel demoModel() {
    return ExposureModel{0.05, 0.01, 0.03, 0.008, 0.12, 0.35, 0.30, -0.10};
}
ExposureModel zeroVolModel() {
    return ExposureModel{0.05, 0.0, 0.03, 0.0, 0.0, 0.35, 0.30, -0.10};
}

SimConfig makeConfig(std::size_t nPaths, std::vector<int> reportDays, unsigned seed = 20261110u,
                     double q = 0.95) {
    return SimConfig{nPaths, seed, q, std::move(reportDays)};
}

double dfDay(const YieldCurve& c, int day) { return day <= 0 ? 1.0 : c.discountFactor(day / 365.0); }

// ---- specs ----------------------------------------------------------------------------------

std::vector<int> schedule(int first, int step, int count) {
    std::vector<int> out;
    for (int k = 0; k < count; ++k) out.push_back(first + step * k);
    return out;
}

RateSwapSpec mxnSwap(bool payer, double fixed, int start, std::vector<int> pay, double accrued = 1.0,
                     bool csa = false, double notional = 100e6) {
    return RateSwapSpec{SwapCurrency::MXN, notional, fixed, payer, start, std::move(pay), accrued, 360.0, csa};
}
RateSwapSpec usdSwap(bool payer, double fixed, int start, std::vector<int> pay, double accrued = 1.0,
                     double notional = 10e6) {
    return RateSwapSpec{SwapCurrency::USD, notional, fixed, payer, start, std::move(pay), accrued, 360.0, false};
}
XccySwapSpec xccySwap(bool payUsd, int start, std::vector<int> pay, double fx, double spread,
                      bool initial, bool fin, double accUsd = 1.0, double accMxn = 1.0,
                      bool csa = true, double notionalUsd = 10e6) {
    return XccySwapSpec{notionalUsd, fx, spread, start, std::move(pay), accUsd, accMxn, payUsd,
                        initial, fin, 360.0, csa};
}

NettingSetSpec setOf(std::vector<RateSwapSpec> swaps, std::vector<XccySwapSpec> xccys = {}) {
    return NettingSetSpec{std::move(swaps), std::move(xccys)};
}

NettingSetSpec unite(const NettingSetSpec& a, const NettingSetSpec& b) {
    NettingSetSpec out = a;
    out.swaps.insert(out.swaps.end(), b.swaps.begin(), b.swaps.end());
    out.xccys.insert(out.xccys.end(), b.xccys.begin(), b.xccys.end());
    return out;
}

NettingSetSpec mirror(const NettingSetSpec& a) {
    NettingSetSpec out = a;
    for (auto& s : out.swaps) s.payer = !s.payer;
    for (auto& x : out.xccys) x.payUsd = !x.payUsd;
    return out;
}

// The trades used in the exact-start and zero-volatility tests (aged, future-start, csa, USD, xccy).
RateSwapSpec s0() { return mxnSwap(true, 0.0710, -10, schedule(18, 28, 39), 1.0007, false, 300e6); }
RateSwapSpec s1() { return usdSwap(false, 0.0375, -100, schedule(265, 365, 5), 1.009, 15e6); }
RateSwapSpec s2() { return mxnSwap(false, 0.0705, -20, schedule(8, 28, 52), 1.0011, true, 150e6); }
RateSwapSpec s3() { return mxnSwap(true, 0.0690, 0, schedule(28, 28, 13), 1.0, false, 200e6); }
RateSwapSpec s4() { return usdSwap(true, 0.0360, 20, schedule(385, 365, 3), 1.0, 12e6); }
XccySwapSpec x0() { return xccySwap(true, 5, schedule(33, 28, 26), 18.20, 0.0005, true, true); }
XccySwapSpec x1() {
    return xccySwap(false, -10, schedule(18, 28, 39), 18.60, 0.0010, true, true, 1.0004, 1.0008);
}
XccySwapSpec x2() {
    return xccySwap(true, 0, schedule(28, 28, 52), 17.90, 0.0, false, true, 1.0, 1.0, false, 8e6);
}
XccySwapSpec x3() { return xccySwap(true, 0, schedule(28, 28, 13), 18.00, 0.0003, true, true); }

// ---- desk valuation of the same instruments (the reference) ---------------------------------

MarketEnvironment deskEnv(const YieldCurve& tiie, const YieldCurve& sofr, const YieldCurve& basis,
                          double spot) {
    MarketEnvironment env;
    env.addCurve("TIIE-F", tiie);
    env.addCurve("SOFR", sofr);
    env.addCurve("MXN-USD", basis);
    env.setSpot("USDMXN", spot);
    return env;
}

double deskSwapMxn(const RateSwapSpec& s, int start, const std::vector<int>& pay, double accrued,
                   const MarketEnvironment& env, double spot) {
    const bool usd = s.currency == SwapCurrency::USD;
    OisSwap sw(s.notional, s.fixedRate, start, pay, accrued,
               s.payer ? SwapType::Payer : SwapType::Receiver, usd ? "SOFR" : "TIIE-F",
               DayCountConvention::ACT_360, (!usd && s.csaDiscount) ? "MXN-USD" : "");
    return sw.npv(env) * (usd ? spot : 1.0);
}

double deskXccyMxn(const XccySwapSpec& x, int start, const std::vector<int>& pay, double accUsd,
                   double accMxn, bool initial, const MarketEnvironment& env) {
    XccySwap sw(x.notionalUsd, x.fxRate, x.spread, start, pay, accUsd, accMxn,
                x.payUsd ? XccySide::PayUsd : XccySide::PayMxn, initial, x.finalExchange, "SOFR", "TIIE-F",
                x.csaDiscount ? "MXN-USD" : "TIIE-F", "USDMXN");
    return sw.npv(env);
}

double notionalMxn(const NettingSetSpec& set) {
    double n = 0.0;
    for (const auto& s : set.swaps) n += s.notional * (s.currency == SwapCurrency::USD ? kSpot : 1.0);
    for (const auto& x : set.xccys) n += x.notionalUsd * kSpot;
    return n;
}

// Instrument aged to day d: the first period still unpaid at d, its start relative to d and the
// compounded factor already fixed, from the projection curve (z(0,start)/z(0,d)).
struct Aged {
    bool alive = false;
    bool firstPeriod = false;     // the original first period (initial exchange still possible)
    int start = 0;
    std::vector<int> pay;
    double accrued = 1.0;
};
Aged ageTo(int startDays, const std::vector<int>& pay, double accrued, int d, const YieldCurve& proj) {
    Aged out;
    std::size_t k = 0;
    while (k < pay.size() && pay[k] <= d) ++k;
    if (k == pay.size()) return out;
    out.alive = true;
    out.firstPeriod = (k == 0);
    const int prev = (k == 0) ? startDays : pay[k - 1];
    const double a0 = (k == 0) ? accrued : 1.0;
    for (std::size_t i = k; i < pay.size(); ++i) out.pay.push_back(pay[i] - d);
    out.start = prev - d;
    out.accrued = (prev <= d) ? a0 * dfDay(proj, std::max(prev, 0)) / dfDay(proj, d) : 1.0;
    return out;
}

// Zero-rate curve of the forward discount factors P(0, d + tau) / P(0, d), daily pillars.
YieldCurve forwardCurve(const YieldCurve& base, int d, int maxDays) {
    std::vector<double> mats, zeros;
    const double p0 = dfDay(base, d);
    for (int k = 1; k <= maxDays; ++k) {
        const double tau = k / 365.0;
        mats.push_back(tau);
        zeros.push_back(-std::log(dfDay(base, d + k) / p0) / tau);
    }
    return YieldCurve(mats, zeros, InterpolationMethod::Linear);
}

int lastPayDay(const NettingSetSpec& set) {
    int m = 0;
    for (const auto& s : set.swaps) m = std::max(m, s.payDays.back());
    for (const auto& x : set.xccys) m = std::max(m, x.payDays.back());
    return m;
}

// CVA with a flat hazard on the discounted EPE of a profile, as the engine's XVA will define it.
double cvaFlat(const ExposureProfile& p, double hazard, double lgd) {
    FlatHazardRate credit(hazard);
    double cva = 0.0;
    for (std::size_t i = 1; i < p.times.size(); ++i)
        cva += lgd * p.epeDisc[i] * (credit.survivalProbability(p.times[i - 1]) - credit.survivalProbability(p.times[i]));
    return cva;
}

} // namespace

// ---- (a) exact start -------------------------------------------------------------------------

TEST(ExposureEngine, TradeValuesAtZeroEqualDeskNpv) {
    const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(10, {0, 28}));
    const MarketEnvironment env = deskEnv(tiieCurve(), sofrCurve(), basisCurve(), kSpot);
    const NettingSetSpec set = setOf({s0(), s1(), s2(), s3(), s4()}, {x0(), x1(), x2(), x3()});

    const std::vector<double> v = engine.tradeValuesAtZero(set);
    ASSERT_EQ(v.size(), 9u);
    std::size_t i = 0;
    for (const auto& s : set.swaps) {
        const double ref = deskSwapMxn(s, s.startDays, s.payDays, s.accruedFactor, env, kSpot);
        const double n = s.notional * (s.currency == SwapCurrency::USD ? kSpot : 1.0);
        EXPECT_NEAR(v[i], ref, 1e-6 * n) << "swap " << i;
        ++i;
    }
    for (const auto& x : set.xccys) {
        const double ref = deskXccyMxn(x, x.startDays, x.payDays, x.accruedFactorUsd, x.accruedFactorMxn,
                                       x.initialExchange, env);
        EXPECT_NEAR(v[i], ref, 1e-6 * x.notionalUsd * kSpot) << "xccy " << (i - set.swaps.size());
        ++i;
    }
    // The aged and the future-start instruments really are not trivial (guard against a vacuous match).
    EXPECT_GT(std::abs(v[0]), 1e4);
    EXPECT_GT(std::abs(v[5]), 1e4);
}

TEST(ExposureEngine, NoStepAfterOneDayWithoutVolatility) {
    const ExposureEngine engine(makeMarket(), zeroVolModel(), makeConfig(10, {0, 1}));
    constexpr double kOvernight = 0.08;   // generous bound on the one-day carry of any leg
    const std::vector<NettingSetSpec> sets = {
        setOf({s0()}), setOf({s1()}), setOf({s2()}), setOf({s3()}), setOf({s4()}),
        setOf({}, {x0()}), setOf({}, {x1()}), setOf({}, {x2()})};
    const auto profiles = engine.simulate(sets);
    ASSERT_EQ(profiles.size(), sets.size());
    for (std::size_t i = 0; i < sets.size(); ++i) {
        const double n = notionalMxn(sets[i]);
        const double rate = sets[i].swaps.empty() ? std::abs(sets[i].xccys[0].spread)
                                                  : std::abs(sets[i].swaps[0].fixedRate);
        const double bound = n * (rate + kOvernight) / 360.0;
        EXPECT_NEAR(profiles[i].expectedValue[0], profiles[i].valueAtZero, 1e-9 * n) << "set " << i;
        EXPECT_LE(std::abs(profiles[i].expectedValue[1] - profiles[i].expectedValue[0]), bound) << "set " << i;
    }
}

// ---- (b) martingale -------------------------------------------------------------------------

namespace {

void expectMartingale(const ExposureEngine& engine, const NettingSetSpec& set, Deflator deflator,
                      const std::vector<int>& days, const char* label) {
    const double v0 = engine.tradeValuesAtZero(set)[0];
    const std::vector<DeflatedStat> stats = engine.deflatedValueStats(set, days, deflator);
    ASSERT_EQ(stats.size(), days.size());
    for (std::size_t i = 0; i < days.size(); ++i) {
        ASSERT_GT(stats[i].stdErr, 0.0) << label;
        EXPECT_LE(std::abs(stats[i].mean - v0), 3.0 * stats[i].stdErr)
            << label << " day " << days[i] << " mean " << stats[i].mean << " v0 " << v0 << " se "
            << stats[i].stdErr << " z " << (stats[i].mean - v0) / stats[i].stdErr;
    }
}

const std::vector<int> kMartingaleDays = {365, 1095, 1825};

} // namespace

TEST(ExposureEngine, MartingaleMxnSwapTiieAccount) {
    const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(4000, {0}));
    expectMartingale(engine, setOf({mxnSwap(true, 0.0690, 0, schedule(28, 28, 78), 1.0, false, 100e6)}),
                     Deflator::TiieAccount, kMartingaleDays, "MXN swap, TIIE account");
}

TEST(ExposureEngine, MartingaleUsdSwapCollateralAccount) {
    const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(4000, {0}));
    expectMartingale(engine, setOf({usdSwap(false, 0.0375, 0, schedule(365, 365, 6), 1.0, 10e6)}),
                     Deflator::CollateralAccount, kMartingaleDays, "USD swap, collateral account");
}

TEST(ExposureEngine, MartingaleXccyCollateralAccount) {
    const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(4000, {0}));
    expectMartingale(engine, setOf({}, {xccySwap(true, 14, schedule(42, 28, 78), 18.20, 0.0010, true, true)}),
                     Deflator::CollateralAccount, kMartingaleDays, "xccy, collateral account");
}

TEST(ExposureEngine, MartingaleCsaSwapAndAgedSwapCollateralAccount) {
    const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(4000, {0}));
    // MXN swap discounted with the basis curve, mid-life with a compounded factor.
    expectMartingale(engine, setOf({mxnSwap(false, 0.0705, -20, schedule(8, 28, 80), 1.0011, true, 150e6)}),
                     Deflator::CollateralAccount, kMartingaleDays, "MXN csa swap, collateral account");
    expectMartingale(engine, setOf({mxnSwap(true, 0.0710, -10, schedule(18, 28, 80), 1.0007, false, 300e6)}),
                     Deflator::TiieAccount, kMartingaleDays, "aged MXN swap, TIIE account");
}

// A stronger version of the martingale test: large volatilities and correlations make the
// quanto drift, the FX drift and the basis term big enough for a wrong sign to be unmistakable.
TEST(ExposureEngine, MartingaleHoldsWithHighVolatilityAndCorrelation) {
    const ExposureModel hot{0.04, 0.02, 0.06, 0.02, 0.25, 0.5, 0.4, -0.5};
    const ExposureEngine engine(makeMarket(true, -0.0150), hot, makeConfig(4000, {0}));   // 150 bp of basis
    expectMartingale(engine, setOf({usdSwap(false, 0.0375, 0, schedule(365, 365, 6), 1.0, 10e6)}),
                     Deflator::CollateralAccount, kMartingaleDays, "hot USD swap");
    expectMartingale(engine, setOf({}, {xccySwap(false, 14, schedule(42, 28, 78), 18.20, 0.0010, true, true)}),
                     Deflator::CollateralAccount, kMartingaleDays, "hot xccy");
    expectMartingale(engine, setOf({mxnSwap(true, 0.0690, 0, schedule(28, 28, 78), 1.0, false, 100e6)}),
                     Deflator::TiieAccount, kMartingaleDays, "hot MXN swap");
}

// The convexity term of the affine bond price, -B^2 y / 2, is invisible at MX-DEMO volatilities;
// with a floating-only swap (rate 0) the value is N (F - P(t, T_end)), so a long bond at extreme
// volatility isolates it. The USD version also carries the quanto drift at a large scale.
TEST(ExposureEngine, MartingaleSeesBondConvexityAtExtremeVolatility) {
    const ExposureModel wild{0.05, 0.04, 0.05, 0.04, 0.15, 0.3, 0.2, -0.5};
    const ExposureEngine engine(makeMarket(), wild, makeConfig(2000, {0}));
    const std::vector<int> days = {1825, 2555};
    expectMartingale(engine, setOf({mxnSwap(true, 0.0, 0, schedule(28, 28, 130), 1.0, false, 100e6)}),
                     Deflator::TiieAccount, days, "long MXN floater");
    expectMartingale(engine, setOf({usdSwap(true, 0.0, 0, schedule(365, 365, 10), 1.0, 10e6)}),
                     Deflator::CollateralAccount, days, "long USD floater");
}

// ---- internals: moments and step covariance against independent numerics ------------------------

// ---- (c) zero-volatility limit ----------------------------------------------------------------

TEST(ExposureEngine, ZeroVolatilityLimitMatchesDeskOnForwardCurves) {
    const std::vector<int> report = {0, 28, 90, 365, 1000};
    const NettingSetSpec set = setOf({s0(), s1(), s2(), s3(), s4()}, {x0(), x1(), x2(), x3()});
    const ExposureEngine engine(makeMarket(), zeroVolModel(), makeConfig(64, report));
    const std::vector<ExposureProfile> profiles = engine.simulate({set});
    ASSERT_EQ(profiles.size(), 1u);
    const ExposureProfile& p = profiles[0];
    ASSERT_EQ(p.expectedValue.size(), report.size());

    const int maxDays = lastPayDay(set);
    const YieldCurve tiie = tiieCurve(), sofr = sofrCurve(), basis = basisCurve();
    for (std::size_t j = 0; j < report.size(); ++j) {
        const int d = report[j];
        // The model's forward FX and the forward curves implied by today's curves.
        const double spotFwd = kSpot * dfDay(sofr, d) / dfDay(basis, d);
        const MarketEnvironment env = deskEnv(forwardCurve(tiie, d, maxDays), forwardCurve(sofr, d, maxDays),
                                              forwardCurve(basis, d, maxDays), spotFwd);
        double expected = 0.0;
        for (const auto& s : set.swaps) {
            const Aged a = ageTo(s.startDays, s.payDays, s.accruedFactor,
                                 d, s.currency == SwapCurrency::USD ? sofr : tiie);
            if (a.alive) expected += deskSwapMxn(s, a.start, a.pay, a.accrued, env, spotFwd);
        }
        for (const auto& x : set.xccys) {
            const Aged au = ageTo(x.startDays, x.payDays, x.accruedFactorUsd, d, sofr);
            const Aged am = ageTo(x.startDays, x.payDays, x.accruedFactorMxn, d, tiie);
            if (!au.alive) continue;
            const bool initial = x.initialExchange && au.firstPeriod && (x.startDays > d || (d == 0 && x.startDays == 0));
            expected += deskXccyMxn(x, au.start, au.pay, au.accrued, am.accrued, initial, env);
        }
        EXPECT_NEAR(p.expectedValue[j], expected, 1e-6 * notionalMxn(set)) << "day " << d;
        EXPECT_NEAR(p.epe[j], std::max(p.expectedValue[j], 0.0), 1e-9 * notionalMxn(set)) << "day " << d;
        EXPECT_NEAR(p.ene[j], std::max(-p.expectedValue[j], 0.0), 1e-9 * notionalMxn(set)) << "day " << d;
    }
}

TEST(ExposureEngine, ZeroVolatilityLimitSingleInstruments) {
    // Each instrument alone, so an error in one cannot be hidden by another's offset.
    const std::vector<int> report = {0, 28, 365, 700};
    const std::vector<NettingSetSpec> sets = {
        setOf({s0()}), setOf({s1()}), setOf({s2()}), setOf({s4()}),
        setOf({}, {x0()}), setOf({}, {x1()}), setOf({}, {x2()})};
    const ExposureEngine engine(makeMarket(), zeroVolModel(), makeConfig(8, report));
    const auto profiles = engine.simulate(sets);
    const YieldCurve tiie = tiieCurve(), sofr = sofrCurve(), basis = basisCurve();
    for (std::size_t i = 0; i < sets.size(); ++i) {
        const int maxDays = lastPayDay(sets[i]);
        for (std::size_t j = 0; j < report.size(); ++j) {
            const int d = report[j];
            const double spotFwd = kSpot * dfDay(sofr, d) / dfDay(basis, d);
            const MarketEnvironment env = deskEnv(forwardCurve(tiie, d, maxDays), forwardCurve(sofr, d, maxDays),
                                                  forwardCurve(basis, d, maxDays), spotFwd);
            double expected = 0.0;
            for (const auto& s : sets[i].swaps) {
                const Aged a = ageTo(s.startDays, s.payDays, s.accruedFactor, d,
                                     s.currency == SwapCurrency::USD ? sofr : tiie);
                if (a.alive) expected += deskSwapMxn(s, a.start, a.pay, a.accrued, env, spotFwd);
            }
            for (const auto& x : sets[i].xccys) {
                const Aged au = ageTo(x.startDays, x.payDays, x.accruedFactorUsd, d, sofr);
                const Aged am = ageTo(x.startDays, x.payDays, x.accruedFactorMxn, d, tiie);
                if (!au.alive) continue;
                const bool initial = x.initialExchange && au.firstPeriod && (x.startDays > d || (d == 0 && x.startDays == 0));
                expected += deskXccyMxn(x, au.start, au.pay, au.accrued, am.accrued, initial, env);
            }
            EXPECT_NEAR(profiles[i].expectedValue[j], expected, 1e-6 * notionalMxn(sets[i]))
                << "set " << i << " day " << d;
        }
    }
}

// ---- (e) netting and mirror ----------------------------------------------------------------

TEST(ExposureEngine, NettingNeverCostsMoreThanTheSumOfTheParts) {
    const std::vector<int> report = schedule(0, 30, 70);
    const NettingSetSpec a = setOf({s0(), s3()}, {x0()});
    const NettingSetSpec b = setOf({s1(), s2()}, {x1()});
    const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(500, report));
    const auto p = engine.simulate({a, b, unite(a, b)});
    ASSERT_EQ(p.size(), 3u);
    const double cvaA = cvaFlat(p[0], 0.02, 0.6), cvaB = cvaFlat(p[1], 0.02, 0.6), cvaAB = cvaFlat(p[2], 0.02, 0.6);
    EXPECT_GT(cvaA, 0.0);
    EXPECT_GT(cvaB, 0.0);
    EXPECT_LE(cvaAB, cvaA + cvaB + 1e-9);
    for (std::size_t j = 0; j < report.size(); ++j) EXPECT_LE(p[2].epe[j], p[0].epe[j] + p[1].epe[j] + 1e-6);
}

namespace {

void expectNoExposure(const ExposureProfile& p) {
    EXPECT_EQ(p.valueAtZero, 0.0);
    for (std::size_t j = 0; j < p.days.size(); ++j) {
        EXPECT_EQ(p.expectedValue[j], 0.0) << j;
        EXPECT_EQ(p.epe[j], 0.0) << j;
        EXPECT_EQ(p.ene[j], 0.0) << j;
        EXPECT_EQ(p.pfe[j], 0.0) << j;
        EXPECT_EQ(p.epeDisc[j], 0.0) << j;
        EXPECT_EQ(p.eneDisc[j], 0.0) << j;
    }
}

} // namespace

TEST(ExposureEngine, ExactMirrorOfAnOperationLeavesNoExposure) {
    // One operation and its mirror cancel exactly (not just to rounding), whatever its kind.
    const std::vector<NettingSetSpec> singles = {setOf({s0()}), setOf({s1()}), setOf({s2()}),
                                                 setOf({}, {x0()}), setOf({}, {x1()})};
    const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(300, schedule(0, 30, 40)));
    for (std::size_t i = 0; i < singles.size(); ++i) {
        SCOPED_TRACE("single operation " + std::to_string(i));
        expectNoExposure(engine.simulate({unite(singles[i], mirror(singles[i]))})[0]);
    }
}

TEST(ExposureEngine, MirroredBookLeavesNoExposureUpToRounding) {
    // With several operations the sum of the book and of its mirror is only zero up to rounding.
    const NettingSetSpec a = setOf({s0(), s1(), s2()}, {x0(), x1()});
    const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(300, schedule(0, 30, 40)));
    const auto p = engine.simulate({unite(a, mirror(a))})[0];
    const double tol = 1e-6;   // MXN, against books worth tens of millions
    EXPECT_NEAR(p.valueAtZero, 0.0, tol);
    for (std::size_t j = 0; j < p.days.size(); ++j) {
        EXPECT_NEAR(p.epe[j], 0.0, tol) << j;
        EXPECT_NEAR(p.ene[j], 0.0, tol) << j;
        EXPECT_NEAR(p.pfe[j], 0.0, tol) << j;
    }
}

// ---- reproducibility and independence from the sets ----------------------------------------

TEST(ExposureEngine, SameInputsGiveIdenticalResults) {
    const NettingSetSpec a = setOf({s0(), s1()}, {x0()});
    const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(200, schedule(0, 30, 30)));
    const auto p1 = engine.simulate({a})[0];
    const auto p2 = engine.simulate({a})[0];
    EXPECT_EQ(p1.epe, p2.epe);
    EXPECT_EQ(p1.ene, p2.ene);
    EXPECT_EQ(p1.pfe, p2.pfe);
    EXPECT_EQ(p1.epeDisc, p2.epeDisc);
    EXPECT_EQ(p1.pathDiscPos, p2.pathDiscPos);
}

TEST(ExposureEngine, AnExtraSetDoesNotChangeAnotherSetsProfile) {
    const NettingSetSpec a = setOf({s0(), s1()}, {x0()});
    // The extra set is longer than A, so the fine grid is extended: A's profile must not move.
    const NettingSetSpec longer = setOf({mxnSwap(true, 0.07, 0, schedule(28, 28, 130))});
    const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(200, schedule(0, 30, 30)));
    const auto alone = engine.simulate({a})[0];
    const auto together = engine.simulate({longer, a})[1];
    EXPECT_EQ(alone.expectedValue, together.expectedValue);
    EXPECT_EQ(alone.epe, together.epe);
    EXPECT_EQ(alone.ene, together.ene);
    EXPECT_EQ(alone.pfe, together.pfe);
    EXPECT_EQ(alone.epeDisc, together.epeDisc);
    EXPECT_EQ(alone.eneDisc, together.eneDisc);
    EXPECT_EQ(alone.pathDiscPos, together.pathDiscPos);
    EXPECT_EQ(alone.pathDiscNeg, together.pathDiscNeg);
}

TEST(ExposureEngine, ThePathRowsDoNotDependOnHowPathsAreSplitAcrossThreads) {
    // simulate() cuts the paths into one chunk per hardware thread. A path draws from its own generator and writes
    // its own row, so row p must be the same whether 7, 11 or 64 paths are run (different chunk boundaries) and
    // with one path (the serial branch).
    const NettingSetSpec a = setOf({s0(), s1()}, {x0()});
    const std::vector<int> report = schedule(0, 17, 30);
    const auto rows = [&](std::size_t nPaths) {
        const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(nPaths, report));
        return engine.simulate({a})[0];
    };
    const std::size_t nDays = report.size();
    const auto big = rows(64);
    for (const std::size_t n : {std::size_t{1}, std::size_t{7}, std::size_t{11}}) {
        const auto small = rows(n);
        for (std::size_t i = 0; i < n * nDays; ++i) {
            ASSERT_EQ(small.pathDiscPos[i], big.pathDiscPos[i]) << "n = " << n << ", i = " << i;
            ASSERT_EQ(small.pathDiscNeg[i], big.pathDiscNeg[i]) << "n = " << n << ", i = " << i;
        }
    }
}

TEST(ExposureEngine, DifferentSeedsGiveDifferentPaths) {
    const NettingSetSpec a = setOf({s0()});
    const ExposureEngine e1(makeMarket(), demoModel(), makeConfig(200, schedule(0, 30, 20), 1u));
    const ExposureEngine e2(makeMarket(), demoModel(), makeConfig(200, schedule(0, 30, 20), 2u));
    EXPECT_NE(e1.simulate({a})[0].epe, e2.simulate({a})[0].epe);
}

// ---- profile shape ---------------------------------------------------------------------------

TEST(ExposureEngine, ProfileShapeAndExpiry) {
    const std::vector<int> report = {0, 30, 60, 400, 500};
    const NettingSetSpec a = setOf({mxnSwap(true, 0.065, 0, schedule(28, 28, 13), 1.0, false, 100e6)});   // ends day 364
    const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(400, report, 7u, 0.9));
    const auto p = engine.simulate({a})[0];
    ASSERT_EQ(p.days, report);
    ASSERT_EQ(p.times.size(), report.size());
    EXPECT_DOUBLE_EQ(p.times[1], 30.0 / 365.0);
    ASSERT_EQ(p.pathDiscPos.size(), 400u * report.size());
    ASSERT_EQ(p.pathDiscNeg.size(), 400u * report.size());
    // t = 0 is deterministic: every path agrees.
    const double tol0 = 1e-9 * std::abs(p.valueAtZero);   // the mean of 400 equal values, up to rounding
    EXPECT_NEAR(p.epe[0], std::max(p.valueAtZero, 0.0), tol0);
    EXPECT_NEAR(p.ene[0], std::max(-p.valueAtZero, 0.0), tol0);
    EXPECT_DOUBLE_EQ(p.pfe[0], std::max(p.valueAtZero, 0.0));
    EXPECT_NEAR(p.epeDisc[0], p.epe[0], tol0);
    // Past the last payment nothing is left.
    EXPECT_EQ(p.epe[3], 0.0);
    EXPECT_EQ(p.ene[4], 0.0);
    // PFE >= EPE (a quantile of the positive part above its mean for this payer) and positive in mid-life.
    EXPECT_GT(p.pfe[1], p.epe[1]);
    // pathDisc matrices average to the discounted profiles.
    for (std::size_t j = 0; j < report.size(); ++j) {
        double pos = 0.0, neg = 0.0;
        for (std::size_t k = 0; k < 400; ++k) {
            pos += p.pathDiscPos[k * report.size() + j];
            neg += p.pathDiscNeg[k * report.size() + j];
        }
        EXPECT_NEAR(pos / 400.0, p.epeDisc[j], 1e-9 * (1.0 + p.epeDisc[j]));
        EXPECT_NEAR(neg / 400.0, p.eneDisc[j], 1e-9 * (1.0 + p.eneDisc[j]));
    }
}

TEST(ExposureEngine, DiscountedExposureIsBelowUndiscountedForPositiveRates) {
    const NettingSetSpec a = setOf({mxnSwap(true, 0.065, 0, schedule(28, 28, 52), 1.0, false, 100e6)});
    const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(500, schedule(0, 60, 25)));
    const auto p = engine.simulate({a})[0];
    for (std::size_t j = 1; j < p.days.size(); ++j) {
        if (p.epe[j] > 0.0) {
            EXPECT_LT(p.epeDisc[j], p.epe[j]) << j;
            EXPECT_GT(p.epeDisc[j], 0.6 * p.epe[j]) << j;   // four years at ~7 % discount to ~0.75
        }
    }
}

// ---- validation ------------------------------------------------------------------------------

TEST(ExposureEngine, RejectsInvalidModelAndConfig) {
    const auto cfg = makeConfig(10, {0, 30});
    // Correlation matrix not positive definite.
    EXPECT_THROW(ExposureEngine(makeMarket(), ExposureModel{0.05, 0.01, 0.03, 0.008, 0.12, 0.9, 0.9, -0.9}, cfg),
                 std::invalid_argument);
    EXPECT_THROW(ExposureEngine(makeMarket(), ExposureModel{0.05, 0.01, 0.03, 0.008, 0.12, 1.0, 0.0, 0.0}, cfg),
                 std::invalid_argument);
    // Mean reversion must be positive, volatilities non-negative.
    EXPECT_THROW(ExposureEngine(makeMarket(), ExposureModel{0.0, 0.01, 0.03, 0.008, 0.12, 0.1, 0.1, 0.1}, cfg),
                 std::invalid_argument);
    EXPECT_THROW(ExposureEngine(makeMarket(), ExposureModel{0.05, -0.01, 0.03, 0.008, 0.12, 0.1, 0.1, 0.1}, cfg),
                 std::invalid_argument);
    // Config.
    EXPECT_THROW(ExposureEngine(makeMarket(), demoModel(), makeConfig(0, {0, 30})), std::invalid_argument);
    EXPECT_THROW(ExposureEngine(makeMarket(), demoModel(), makeConfig(10, {0, 30}, 1u, 1.0)), std::invalid_argument);
    EXPECT_THROW(ExposureEngine(makeMarket(), demoModel(), makeConfig(10, {0, 30}, 1u, 0.0)), std::invalid_argument);
    EXPECT_THROW(ExposureEngine(makeMarket(), demoModel(), makeConfig(10, {})), std::invalid_argument);
    EXPECT_THROW(ExposureEngine(makeMarket(), demoModel(), makeConfig(10, {30, 60})), std::invalid_argument);
    EXPECT_THROW(ExposureEngine(makeMarket(), demoModel(), makeConfig(10, {0, 30, 30})), std::invalid_argument);
    // Market.
    EXPECT_THROW(ExposureEngine(ExposureMarket{tiieCurve(), sofrCurve(), std::nullopt, 0.0}, demoModel(), cfg),
                 std::invalid_argument);
}

TEST(ExposureEngine, RejectsInvalidSpecs) {
    const ExposureEngine engine(makeMarket(false), demoModel(), makeConfig(10, {0, 30}));
    // csaDiscount needs the MXN-USD curve.
    EXPECT_THROW(engine.simulate({setOf({mxnSwap(true, 0.07, 0, schedule(28, 28, 5), 1.0, true)})}),
                 std::invalid_argument);
    EXPECT_THROW(engine.tradeValuesAtZero(setOf({}, {xccySwap(true, 0, schedule(28, 28, 5), 18.6, 0.0, true, true)})),
                 std::invalid_argument);
    // Without csaDiscount the same swap is fine without the curve.
    EXPECT_NO_THROW(engine.simulate({setOf({mxnSwap(true, 0.07, 0, schedule(28, 28, 5))})}));
    // Schedules and factors.
    EXPECT_THROW(engine.tradeValuesAtZero(setOf({mxnSwap(true, 0.07, 0, {})})), std::invalid_argument);
    EXPECT_THROW(engine.tradeValuesAtZero(setOf({mxnSwap(true, 0.07, 0, {28, 28})})), std::invalid_argument);
    EXPECT_THROW(engine.tradeValuesAtZero(setOf({mxnSwap(true, 0.07, 28, {28, 56})})), std::invalid_argument);
    EXPECT_THROW(engine.tradeValuesAtZero(setOf({mxnSwap(true, 0.07, 0, {28, 56}, 1.01)})), std::invalid_argument);
    EXPECT_THROW(engine.tradeValuesAtZero(setOf({mxnSwap(true, 0.07, -5, {28, 56}, -1.0)})), std::invalid_argument);
    EXPECT_THROW(engine.tradeValuesAtZero(setOf({mxnSwap(true, 0.07, 0, {28, 56}, 1.0, false, -1.0)})),
                 std::invalid_argument);
}

// ---- internals --------------------------------------------------------------------------------

TEST(ExposureEngineInternals, OuMomentsSolveTheirDifferentialEquations) {
    // y' = sigma^2 - 2 a y,  m' = y + mu - a m,  M' = m, integrated with RK4.
    const double a = 0.07, sigma = 0.015, mu = -0.0021;
    const double horizon = 7.0;
    const int steps = 70000;
    const double h = horizon / steps;
    double y = 0.0, m = 0.0, M = 0.0;
    const auto f = [&](double yy, double mm, double& dy, double& dm, double& dM) {
        dy = sigma * sigma - 2.0 * a * yy;
        dm = yy + mu - a * mm;
        dM = mm;
    };
    for (int i = 0; i < steps; ++i) {
        double k1y, k1m, k1M, k2y, k2m, k2M, k3y, k3m, k3M, k4y, k4m, k4M;
        f(y, m, k1y, k1m, k1M);
        f(y + 0.5 * h * k1y, m + 0.5 * h * k1m, k2y, k2m, k2M);
        f(y + 0.5 * h * k2y, m + 0.5 * h * k2m, k3y, k3m, k3M);
        f(y + h * k3y, m + h * k3m, k4y, k4m, k4M);
        y += h / 6.0 * (k1y + 2 * k2y + 2 * k3y + k4y);
        m += h / 6.0 * (k1m + 2 * k2m + 2 * k3m + k4m);
        M += h / 6.0 * (k1M + 2 * k2M + 2 * k3M + k4M);
    }
    const qf::xva::detail::OuMoments mo = qf::xva::detail::ouMoments(a, sigma, mu, horizon);
    EXPECT_NEAR(mo.y, y, 1e-10);
    EXPECT_NEAR(mo.m, m, 1e-10);
    EXPECT_NEAR(mo.mInt, M, 1e-9);
    const qf::xva::detail::OuMoments zero = qf::xva::detail::ouMoments(a, sigma, mu, 0.0);
    EXPECT_EQ(zero.y, 0.0);
    EXPECT_EQ(zero.m, 0.0);
    EXPECT_EQ(zero.mInt, 0.0);
}

TEST(ExposureEngineInternals, StepCovarianceMatchesNumericalQuadrature) {
    // Different mean reversions and non-trivial correlations, so every cross term is exercised.
    const ExposureModel model{0.05, 0.02, 0.30, 0.015, 0.20, 0.40, -0.30, 0.50};
    const std::array<double, 5> a = {model.aMxn, model.aMxn, model.aUsd, model.aUsd, 0.0};
    const std::array<double, 5> vol = {model.sigmaMxn, model.sigmaMxn, model.sigmaUsd, model.sigmaUsd, model.fxVol};
    const std::array<int, 5> factor = {0, 0, 1, 1, 2};   // MXN, MXN, USD, USD, FX
    const double rho[3][3] = {{1.0, model.rhoMxnUsd, model.rhoMxnFx},
                              {model.rhoMxnUsd, 1.0, model.rhoUsdFx},
                              {model.rhoMxnFx, model.rhoUsdFx, 1.0}};
    // kind: 0 = e^{-a tau}, 1 = (1 - e^{-a tau}) / a, 2 = 1
    const std::array<int, 5> kind = {0, 1, 0, 1, 2};
    const auto kernel = [&](std::size_t i, double tau) {
        if (kind[i] == 0) return std::exp(-a[i] * tau);
        if (kind[i] == 1) return (1.0 - std::exp(-a[i] * tau)) / a[i];
        return 1.0;
    };
    for (double dt : {1.0 / 365.0, 0.25, 2.0}) {
        const auto cov = qf::xva::detail::stepCovariance(model, dt);
        const int n = 4000;   // Simpson
        for (std::size_t i = 0; i < 5; ++i) {
            for (std::size_t j = 0; j < 5; ++j) {
                double acc = 0.0;
                for (int k = 0; k <= n; ++k) {
                    const double tau = dt * k / n;
                    const double w = (k == 0 || k == n) ? 1.0 : (k % 2 ? 4.0 : 2.0);
                    acc += w * kernel(i, tau) * kernel(j, tau);
                }
                acc *= dt / n / 3.0;
                const double expected = rho[factor[i]][factor[j]] * vol[i] * vol[j] * acc;
                const double scale = std::sqrt(cov[i][i] * cov[j][j]);
                EXPECT_NEAR(cov[i][j], expected, 1e-7 * scale) << "dt " << dt << " (" << i << "," << j << ")";
                EXPECT_NEAR(cov[i][j], cov[j][i], 1e-12 * scale) << "dt " << dt << " (" << i << "," << j << ")";
            }
        }
    }
}

// ---- computeXva -------------------------------------------------------------------------------

namespace {

constexpr std::size_t kSynthPaths = 4;
constexpr std::size_t kSynthDays = 4;

// A profile built by hand: 4 paths x 4 dates (days 0, 365, 730, 1095), row = path. The means are the
// profile's discounted exposures, so the expected XVA is computable without the engine.
ExposureProfile syntheticProfile() {
    const double pos[kSynthPaths][kSynthDays] = {{3, 10, 20, 30}, {3, 0, 5, 40}, {3, 30, 0, 10}, {3, 20, 15, 0}};
    const double neg[kSynthPaths][kSynthDays] = {{0, 0, 0, 5}, {0, 7, 0, 0}, {0, 0, 12, 0}, {0, 0, 0, 8}};
    ExposureProfile p;
    p.days = {0, 365, 730, 1095};
    for (int d : p.days) p.times.push_back(d / 365.0);
    p.expectedValue.assign(kSynthDays, 0.0);
    p.epe.assign(kSynthDays, 0.0);
    p.ene.assign(kSynthDays, 0.0);
    p.pfe.assign(kSynthDays, 0.0);
    p.epeDisc.assign(kSynthDays, 0.0);
    p.eneDisc.assign(kSynthDays, 0.0);
    for (std::size_t k = 0; k < kSynthPaths; ++k) {
        for (std::size_t j = 0; j < kSynthDays; ++j) {
            p.pathDiscPos.push_back(pos[k][j]);
            p.pathDiscNeg.push_back(neg[k][j]);
            p.epeDisc[j] += pos[k][j] / kSynthPaths;
            p.eneDisc[j] += neg[k][j] / kSynthPaths;
        }
    }
    p.valueAtZero = 3.0;
    return p;
}

// Standard error of the mean of per-path values, with the sample variance.
double stdErrOf(const std::vector<double>& v) {
    const double n = static_cast<double>(v.size());
    double mean = 0.0;
    for (double x : v) mean += x;
    mean /= n;
    double ss = 0.0;
    for (double x : v) ss += (x - mean) * (x - mean);
    return std::sqrt(ss / (n - 1.0) / n);
}

} // namespace

TEST(ComputeXva, ReproducesTheDefinitionsOnAKnownProfile) {
    const ExposureProfile p = syntheticProfile();
    const PiecewiseHazardCurve counterparty({1.0, 2.0, 3.0}, {0.010, 0.020, 0.040});
    const FlatHazardRate own(0.015);
    const double lgdC = 0.6, lgdO = 0.55, spread = 0.005;

    // The definitions, written out step by step against the survival values of each date.
    std::vector<double> sc, so;
    for (double t : p.times) {
        sc.push_back(counterparty.survivalProbability(t));
        so.push_back(own.survivalProbability(t));
    }
    double cva = 0.0, dva = 0.0, fva = 0.0;
    std::vector<double> cvaPath(kSynthPaths, 0.0), dvaPath(kSynthPaths, 0.0);
    for (std::size_t i = 1; i < kSynthDays; ++i) {
        cva += lgdC * p.epeDisc[i] * (sc[i - 1] - sc[i]);
        dva += lgdO * p.eneDisc[i] * (so[i - 1] - so[i]);
        fva += spread * (p.epeDisc[i] - p.eneDisc[i]) * sc[i] * so[i] * (p.times[i] - p.times[i - 1]);
        for (std::size_t k = 0; k < kSynthPaths; ++k) {
            cvaPath[k] += lgdC * p.pathDiscPos[k * kSynthDays + i] * (sc[i - 1] - sc[i]);
            dvaPath[k] += lgdO * p.pathDiscNeg[k * kSynthDays + i] * (so[i - 1] - so[i]);
        }
    }
    const XvaResult r = computeXva(p, counterparty, lgdC, own, lgdO, spread);
    EXPECT_NEAR(r.cva, cva, 1e-12 * cva);
    EXPECT_NEAR(r.dva, dva, 1e-12 * dva);
    EXPECT_NEAR(r.fva, fva, 1e-12 * std::abs(fva));
    EXPECT_NEAR(r.cvaStdErr, stdErrOf(cvaPath), 1e-12 * stdErrOf(cvaPath));
    EXPECT_NEAR(r.dvaStdErr, stdErrOf(dvaPath), 1e-12 * stdErrOf(dvaPath));
    EXPECT_DOUBLE_EQ(r.total, r.cva - r.dva + r.fva);
    // Not vacuous: the three adjustments and both errors are really there.
    EXPECT_GT(r.cva, 0.0);
    EXPECT_GT(r.dva, 0.0);
    EXPECT_NE(r.fva, 0.0);
    EXPECT_GT(r.cvaStdErr, 0.0);
    EXPECT_GT(r.dvaStdErr, 0.0);
    // The mean of the per-path sums is the CVA computed from the mean exposure.
    double mean = 0.0;
    for (double x : cvaPath) mean += x / kSynthPaths;
    EXPECT_NEAR(mean, r.cva, 1e-12 * r.cva);
}

TEST(ComputeXva, ZeroHazardGivesExactlyZeroCvaAndDvaAndKeepsFva) {
    const NettingSetSpec a = setOf({s0(), s3()}, {x0()});
    const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(300, schedule(0, 30, 40)));
    const ExposureProfile p = engine.simulate({a})[0];
    const FlatHazardRate none(0.0);
    const XvaResult r = computeXva(p, none, 0.6, none, 0.6, 0.005);
    EXPECT_EQ(r.cva, 0.0);
    EXPECT_EQ(r.dva, 0.0);
    EXPECT_EQ(r.cvaStdErr, 0.0);
    EXPECT_EQ(r.dvaStdErr, 0.0);
    // FVA does not depend on default: it is the funding cost of the expected exposure.
    double fva = 0.0;
    for (std::size_t i = 1; i < p.times.size(); ++i)
        fva += 0.005 * (p.epeDisc[i] - p.eneDisc[i]) * (p.times[i] - p.times[i - 1]);
    EXPECT_NEAR(r.fva, fva, 1e-12 * std::abs(fva));
    EXPECT_NE(r.fva, 0.0);
    EXPECT_DOUBLE_EQ(r.total, r.fva);
    // A zero LGD also kills the adjustment, whatever the curve.
    const FlatHazardRate some(0.05);
    const XvaResult noLoss = computeXva(p, some, 0.0, some, 0.0, 0.0);
    EXPECT_EQ(noLoss.cva, 0.0);
    EXPECT_EQ(noLoss.dva, 0.0);
    EXPECT_EQ(noLoss.fva, 0.0);
    EXPECT_EQ(noLoss.total, 0.0);
}

TEST(ComputeXva, NettingNeverCostsMoreThanTheSumOfTheParts) {
    const std::vector<int> report = schedule(0, 30, 70);
    const NettingSetSpec a = setOf({s0(), s3()}, {x0()});
    const NettingSetSpec b = setOf({s1(), s2()}, {x1()});
    const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(500, report));
    const auto p = engine.simulate({a, b, unite(a, b)});
    ASSERT_EQ(p.size(), 3u);
    const PiecewiseHazardCurve cp({1.0, 3.0, 6.0}, {0.008, 0.02, 0.03});
    const PiecewiseHazardCurve own({2.0, 6.0}, {0.01, 0.015});
    const XvaResult ra = computeXva(p[0], cp, 0.6, own, 0.6, 0.005);
    const XvaResult rb = computeXva(p[1], cp, 0.6, own, 0.6, 0.005);
    const XvaResult rab = computeXva(p[2], cp, 0.6, own, 0.6, 0.005);
    EXPECT_GT(ra.cva, 0.0);
    EXPECT_GT(rb.cva, 0.0);
    EXPECT_GT(ra.dva, 0.0);
    EXPECT_GT(rb.dva, 0.0);
    EXPECT_LE(rab.cva, ra.cva + rb.cva + 1e-9);
    EXPECT_LE(rab.dva, ra.dva + rb.dva + 1e-9);
    // FVA is linear in the value, so the funding cost of the union is the sum of the parts (to rounding).
    EXPECT_NEAR(rab.fva, ra.fva + rb.fva, 1e-9 * (std::abs(ra.fva) + std::abs(rb.fva)));
    // Netting really bites here (the sets partly offset), so the inequality is not an equality.
    EXPECT_LT(rab.cva, ra.cva + rb.cva);
}

TEST(ComputeXva, ExactMirrorLeavesNoXva) {
    const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(300, schedule(0, 30, 40)));
    const PiecewiseHazardCurve cp({1.0, 5.0}, {0.01, 0.02});
    for (const NettingSetSpec& single : {setOf({s0()}), setOf({s1()}), setOf({}, {x0()})}) {
        const ExposureProfile p = engine.simulate({unite(single, mirror(single))})[0];
        const XvaResult r = computeXva(p, cp, 0.6, cp, 0.6, 0.005);
        EXPECT_EQ(r.cva, 0.0);
        EXPECT_EQ(r.dva, 0.0);
        EXPECT_EQ(r.fva, 0.0);
        EXPECT_EQ(r.total, 0.0);
        EXPECT_EQ(r.cvaStdErr, 0.0);
        EXPECT_EQ(r.dvaStdErr, 0.0);
    }
}

TEST(ComputeXva, StandardErrorShrinksWithPathsAndCoversTheSeedToSeedSpread) {
    // The reported error is the sampling error of the CVA: the spread of CVAs over independent seeds
    // is of the same size as the error reported by one run.
    const NettingSetSpec a = setOf({s0()}, {x0()});
    const FlatHazardRate cp(0.02);
    const std::vector<int> report = schedule(0, 60, 25);
    std::vector<double> cvas;
    double meanStdErr = 0.0;
    for (unsigned seed = 1; seed <= 12; ++seed) {
        const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(400, report, seed));
        const XvaResult r = computeXva(engine.simulate({a})[0], cp, 0.6, cp, 0.6, 0.0);
        cvas.push_back(r.cva);
        meanStdErr += r.cvaStdErr / 12.0;
    }
    double mean = 0.0;
    for (double c : cvas) mean += c / cvas.size();
    double ss = 0.0;
    for (double c : cvas) ss += (c - mean) * (c - mean);
    const double spread = std::sqrt(ss / (cvas.size() - 1.0));
    EXPECT_GT(meanStdErr, 0.0);
    EXPECT_GT(spread, 0.5 * meanStdErr);
    EXPECT_LT(spread, 2.0 * meanStdErr);

    const ExposureEngine big(makeMarket(), demoModel(), makeConfig(1600, report, 1u));
    const ExposureEngine small(makeMarket(), demoModel(), makeConfig(400, report, 1u));
    const double seBig = computeXva(big.simulate({a})[0], cp, 0.6, cp, 0.6, 0.0).cvaStdErr;
    const double seSmall = computeXva(small.simulate({a})[0], cp, 0.6, cp, 0.6, 0.0).cvaStdErr;
    EXPECT_LT(seBig, 0.7 * seSmall);   // four times the paths: about half the error
}

TEST(ComputeXva, RejectsInvalidInput) {
    const ExposureProfile ok = syntheticProfile();
    const FlatHazardRate c(0.02);
    EXPECT_NO_THROW(computeXva(ok, c, 0.6, c, 0.6, 0.005));
    // LGD in [0,1], funding spread >= 0 and finite.
    EXPECT_THROW(computeXva(ok, c, -0.1, c, 0.6, 0.005), std::invalid_argument);
    EXPECT_THROW(computeXva(ok, c, 1.1, c, 0.6, 0.005), std::invalid_argument);
    EXPECT_THROW(computeXva(ok, c, 0.6, c, -0.1, 0.005), std::invalid_argument);
    EXPECT_THROW(computeXva(ok, c, 0.6, c, 1.1, 0.005), std::invalid_argument);
    EXPECT_THROW(computeXva(ok, c, std::nan(""), c, 0.6, 0.005), std::invalid_argument);
    EXPECT_THROW(computeXva(ok, c, 0.6, c, 0.6, -0.001), std::invalid_argument);
    EXPECT_THROW(computeXva(ok, c, 0.6, c, 0.6, std::nan("")), std::invalid_argument);
    // A profile that does not agree with itself.
    ExposureProfile bad = ok;
    bad.epeDisc.pop_back();
    EXPECT_THROW(computeXva(bad, c, 0.6, c, 0.6, 0.005), std::invalid_argument);
    bad = ok;
    bad.eneDisc.pop_back();
    EXPECT_THROW(computeXva(bad, c, 0.6, c, 0.6, 0.005), std::invalid_argument);
    bad = ok;
    bad.times.pop_back();
    EXPECT_THROW(computeXva(bad, c, 0.6, c, 0.6, 0.005), std::invalid_argument);
    bad = ok;
    bad.pathDiscPos.pop_back();
    EXPECT_THROW(computeXva(bad, c, 0.6, c, 0.6, 0.005), std::invalid_argument);
    bad = ok;
    bad.pathDiscNeg.clear();
    EXPECT_THROW(computeXva(bad, c, 0.6, c, 0.6, 0.005), std::invalid_argument);
    bad = ok;
    std::swap(bad.times[1], bad.times[2]);
    EXPECT_THROW(computeXva(bad, c, 0.6, c, 0.6, 0.005), std::invalid_argument);
    EXPECT_THROW(computeXva(ExposureProfile{}, c, 0.6, c, 0.6, 0.005), std::invalid_argument);
}

// ---- (d) coherence with the previous engine ----------------------------------------------------

namespace {

constexpr double kFreshNotional = 100e6;
constexpr double kFreshHazard = 0.02;
constexpr double kFreshLgd = 0.6;

YieldCurve flatTiieCurve(double rate) {
    return YieldCurve({0.25, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 12.0}, std::vector<double>(8, rate),
                      InterpolationMethod::Linear);
}

// Payments every 28 days for five years (1820 days); the report grid is the payment grid, so at every
// report day the swap is fresh: a new period starts exactly then.
std::vector<int> freshPayDays() { return schedule(28, 28, 65); }
std::vector<int> freshReportDays() { return schedule(0, 28, 66); }

// Par rate of an OIS swap on `pay` days from today, from OisSwap itself: the npv is linear in the fixed
// rate, so two evaluations (rate 0 and rate 1) give the rate that zeroes it.
double oisParRate(const YieldCurve& curve, const std::vector<int>& pay) {
    MarketEnvironment env;
    env.addCurve("TIIE-F", curve);
    const double floating = OisSwap(1.0, 0.0, 0, pay, 1.0, SwapType::Payer, "TIIE-F").npv(env);
    const double floatMinusFixedAtOne = OisSwap(1.0, 1.0, 0, pay, 1.0, SwapType::Payer, "TIIE-F").npv(env);
    return floating / (floating - floatMinusFixedAtOne);
}

// CVA = LGD * sum_{i>=1} epe_i [S(t_{i-1}) - S(t_i)] on the UNDISCOUNTED expected positive exposure,
// the same formula CVACalculator applies to its own (undiscounted) profile.
double cvaOnUndiscountedEpe(const std::vector<double>& times, const std::vector<double>& epe) {
    const FlatHazardRate credit(kFreshHazard);
    double cva = 0.0;
    for (std::size_t i = 1; i < times.size(); ++i)
        cva += kFreshLgd * epe[i] * (credit.survivalProbability(times[i - 1]) - credit.survivalProbability(times[i]));
    return cva;
}

struct BatchedCva {
    double mean;      // mean of the batch CVAs
    double stdErr;    // sd of the batch CVAs / sqrt(batches)
};

// Engine CVA of the fresh payer TIIE swap struck at `rate`: 10 engines with different seeds of
// 500 paths each; the CVA is their mean and its standard error the spread of the 10.
BatchedCva engineCvaInBatches(const YieldCurve& tiie, double rate) {
    constexpr int kBatches = 10;
    const NettingSetSpec swap = setOf({mxnSwap(true, rate, 0, freshPayDays(), 1.0, false, kFreshNotional)});
    std::vector<double> cvas;
    for (int b = 0; b < kBatches; ++b) {
        const ExposureEngine engine(ExposureMarket{tiie, sofrCurve(), std::nullopt, kSpot}, demoModel(),
                                    makeConfig(500, freshReportDays(), 20261110u + 7919u * static_cast<unsigned>(b)));
        const ExposureProfile p = engine.simulate({swap})[0];
        cvas.push_back(cvaOnUndiscountedEpe(p.times, p.epe));
    }
    double mean = 0.0;
    for (double c : cvas) mean += c / kBatches;
    double ss = 0.0;
    for (double c : cvas) ss += (c - mean) * (c - mean);
    return {mean, std::sqrt(ss / (kBatches - 1.0) / kBatches)};
}

// CVA of CVACalculator for the same swap (its own InterestRateSwap, struck at `rate`), the same report
// dates, hazard, LGD and Hull-White parameters (a = 0.05, sigma = 0.01 as MX-DEMO).
double legacyCva(const YieldCurve& tiie, double rate) {
    qf::models::HullWhite hw(0.05, 0.01, tiie);
    qf::xva::NettingSet set;
    set.add(kFreshNotional, rate, 5.0, 365.0 / 28.0, SwapType::Payer);
    SimParams params;
    params.nPaths = 5000;
    params.seed = 4242u;
    for (int d : freshReportDays())
        if (d > 0) params.monitorDates.push_back(d / 365.0);
    const FlatHazardRate credit(kFreshHazard);
    return CVACalculator(hw, credit, kFreshLgd, params).compute(set, MarketEnvironment(tiie)).cva;
}

// The same CVA without Monte Carlo. A fresh MXN swap depends on one factor, x(t) ~ N(m(t), y(t)), through
// P(t,T) = P(0,T)/P(0,t) exp(-B x - B^2 y / 2), so E[max(V,0)] at each report day is a one-dimensional
// integral (trapezoid rule over +-8 standard deviations).
double closedFormCva(const YieldCurve& tiie, double rate) {
    const double a = 0.05, sigma = 0.01, tau = 28.0 / 360.0;
    const std::vector<int> pay = freshPayDays();
    std::vector<double> times(1, 0.0), epe(1, 0.0);
    for (std::size_t k = 1; k < freshReportDays().size(); ++k) {
        const double t = pay[k - 1] / 365.0;
        const double em = 1.0 - std::exp(-a * t);
        const double m = sigma * sigma / (2.0 * a * a) * em * em;
        const double y = sigma * sigma * (1.0 - std::exp(-2.0 * a * t)) / (2.0 * a);
        const double sd = std::sqrt(y);
        constexpr int kSteps = 4000;
        double integral = 0.0;
        for (int n = 0; n <= kSteps; ++n) {
            const double z = -8.0 + 16.0 * n / kSteps;
            const double x = m + sd * z;
            const auto bond = [&](int day) {
                const double b = (1.0 - std::exp(-a * (day - pay[k - 1]) / 365.0)) / a;
                return tiie.discountFactor(day / 365.0) / tiie.discountFactor(t) * std::exp(-b * x - 0.5 * b * b * y);
            };
            double fixedLeg = 0.0;
            for (std::size_t j = k; j < pay.size(); ++j) fixedLeg += tau * bond(pay[j]);
            const double v = k < pay.size() ? kFreshNotional * ((1.0 - bond(pay.back())) - rate * fixedLeg) : 0.0;
            const double w = (n == 0 || n == kSteps) ? 0.5 : 1.0;
            integral += w * std::max(v, 0.0) * std::exp(-0.5 * z * z);
        }
        times.push_back(t);
        epe.push_back(integral * (16.0 / kSteps) / std::sqrt(2.0 * std::acos(-1.0)));
    }
    return cvaOnUndiscountedEpe(times, epe);
}

} // namespace

TEST(ExposureEngine, CvaMatchesCvaCalculatorForAFreshAtParSwapOnAFlatCurve) {
    // R2(d), tolerance max(5 % of the CVACalculator CVA, 3 standard errors) as specified.
    //
    // Two choices that the plan text did not fix, both needed for the comparison to be about the model:
    //  * Each engine prices the swap at ITS par rate. OisSwap accrues ACT/360; InterestRateSwap accrues 28/365
    //    and runs its floating leg to 5.0 years against fixed payments up to 4.986. With the OisSwap rate in
    //    CVACalculator the payer is worth +0.4 % of the notional from the start and the CVAs differ by 14 %
    //    (flat curve) and 17 % (sloped curve): a different swap, not a different model.
    //  * Flat 7 % curve. On a sloped curve CVACalculator drifts: its theta(t) takes a finite-difference
    //    derivative of the forward curve (piecewise linear zero rates), and its mean short rate ends up
    //    4.6 bp above the Hull-White mean at 2.2 years and 11 bp at 4.4 years (20000 paths), which
    //    inflates payer exposure. The new engine is exact there (next test), so on the sloped test
    //    curve the two differ by 6.5 % (engine 59 807 +- 645, CVACalculator 63 952, exact 59 595): R2(d)
    //    as worded is not met on it, and the cause is the old engine.
    // On the flat curve CVACalculator is still 3.5 % above the exact CVA (Euler steps overstate its
    // variance by ~1-2 %), so the margin against the 5 % criterion is thin by nature of the old engine.
    const YieldCurve flat = flatTiieCurve(0.07);
    const double engineRate = oisParRate(flat, freshPayDays());
    const double legacyRate = qf::instruments::InterestRateSwap::parRate(5.0, 365.0 / 28.0, flat);
    EXPECT_NE(engineRate, legacyRate);   // the conventions really differ, so the distinction matters

    const BatchedCva engine = engineCvaInBatches(flat, engineRate);
    const double legacy = legacyCva(flat, legacyRate);
    ASSERT_GT(legacy, 0.0);
    ASSERT_GT(engine.stdErr, 0.0);
    EXPECT_LT(std::abs(engine.mean - legacy), std::max(0.05 * legacy, 3.0 * engine.stdErr))
        << "engine " << engine.mean << " +- " << engine.stdErr << ", CVACalculator " << legacy;
}

TEST(ExposureEngine, CvaMatchesTheClosedFormOnFlatAndSlopedCurves) {
    // The exact CVA of the same swap, no Monte Carlo: the oracle that says which engine is right when the
    // two disagree. It also covers the sloped test curve that the CVACalculator comparison cannot use.
    for (const YieldCurve& curve : {flatTiieCurve(0.07), tiieCurve()}) {
        const double rate = oisParRate(curve, freshPayDays());
        const BatchedCva engine = engineCvaInBatches(curve, rate);
        const double exact = closedFormCva(curve, rate);
        ASSERT_GT(exact, 0.0);
        EXPECT_LT(std::abs(engine.mean - exact), 3.0 * engine.stdErr)
            << "engine " << engine.mean << " +- " << engine.stdErr << ", closed form " << exact;
        EXPECT_LT(std::abs(engine.mean - exact), 0.05 * exact);
    }
}

// Valores impresos con %.17g desde el motor ANTES de templarlo sobre el escalar: el refactor no puede cambiar
// ni el último bit de ningún número en double (por eso EXPECT_EQ y no EXPECT_DOUBLE_EQ). Dependen del
// compilador y de las banderas (sin FMA, como el build del proyecto): si cambian por eso, regenerarlos.
TEST(ExposureEngine, GoldenValuesUnchangedByTemplating) {
    const NettingSetSpec set = setOf({s0(), s1(), s2(), s4()}, {x0(), x1(), x2()});
    const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(300, schedule(0, 30, 61), 7u));
    const ExposureProfile p = engine.simulate({set})[0];
    const PiecewiseHazardCurve counterparty({1.0, 3.0, 5.0, 10.0}, {0.015, 0.020, 0.025, 0.030});
    const PiecewiseHazardCurve own({2.0, 5.0, 10.0}, {0.005, 0.008, 0.010});
    const XvaResult x = computeXva(p, counterparty, 0.6, own, 0.5, 0.005);
    const std::vector<double> atZero = engine.tradeValuesAtZero(set);
    const std::vector<DeflatedStat> stats = engine.deflatedValueStats(set, {30, 600}, Deflator::TiieAccount);
    EXPECT_EQ(x.cva, 145005.92850236702);
    EXPECT_EQ(x.dva, 196624.46090105936);
    EXPECT_EQ(x.fva, -235047.07041121286);
    EXPECT_EQ(p.valueAtZero, -5677890.6845265059);
    EXPECT_EQ(p.epeDisc[1], 67381.730257012416);
    EXPECT_EQ(p.eneDisc[1], 9826687.7737136222);
    EXPECT_EQ(p.epeDisc[20], 2504425.1006771205);
    EXPECT_EQ(p.eneDisc[20], 18039608.728857126);
    EXPECT_EQ(p.epeDisc[40], 4198788.658587303);
    EXPECT_EQ(p.eneDisc[40], 24470173.471444052);
    EXPECT_EQ(p.pfe[20], 17162140.475009084);
    const std::vector<double> expectedAtZero = {-1073803.6029754612, 207665.51015771384, 483608.42718216323,
                                                876795.59910860204, 510983.22526270151, -1083139.8432622254,
                                                -5600000.0};
    ASSERT_EQ(atZero.size(), expectedAtZero.size());
    for (std::size_t k = 0; k < atZero.size(); ++k) EXPECT_EQ(atZero[k], expectedAtZero[k]) << "operación " << k;
    ASSERT_EQ(stats.size(), 2u);
    EXPECT_EQ(stats[0].mean, -5853281.8703867383);
    EXPECT_EQ(stats[0].stdErr, 251431.65129316493);
    EXPECT_EQ(stats[1].mean, -4975112.3086613975);
    EXPECT_EQ(stats[1].stdErr, 1268798.828563269);
}

#ifndef QF_WITH_XAD
TEST(ExposureEngine, XvaSensitivitiesWithoutXadThrowsLogicError) {
    // Sin XAD el método existe (el binding y la API lo llaman) pero avisa en vez de devolver ceros.
    const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(10, schedule(0, 30, 3)));
    const FlatHazardRate hazard(0.02);
    EXPECT_THROW(engine.xvaSensitivities(setOf({s3()}), hazard, 0.6, hazard, 0.6, 0.005), std::logic_error);
}
#endif

#ifdef QF_WITH_XAD
// ---- sensitivities by adjoint differentiation (AAD) against central shocks on the same paths ----------------

namespace {

// Everything a bump can move: the market, the model, both credit curves (as vertices and hazards), LGDs, funding.
struct Scenario {
    ExposureMarket market = makeMarket();
    ExposureModel model = demoModel();
    std::vector<double> cpTimes{1.0, 3.0, 5.0, 10.0}, cpHazards{0.015, 0.020, 0.025, 0.030};
    std::vector<double> ownTimes{2.0, 5.0, 10.0}, ownHazards{0.005, 0.008, 0.010};
    double cpLgd = 0.6, ownLgd = 0.5, funding = 0.005;
};

using Triple = std::array<double, 3>;   // CVA, DVA, FVA

// Step of each kind of input. A bump moves the input by +-h and the derivative is (f(+h) - f(-h)) / 2h, with the
// same seed, so the paths are the same and the difference is the pathwise derivative the AAD computes.
constexpr double kRateBump = 1e-5;       // 0.1 bp of zero rate
constexpr double kModelBump = 1e-5;      // sigma, a, fx vol
constexpr double kSpotBump = 1e-3;       // MXN per USD
constexpr double kCreditBump = 1e-6;     // hazard and funding spread
// Tolerance on each derivative: |aad - fd| <= max(1 % of |fd|, kAbs), kAbs = 1 MXN per unit of input
// (= 1e-4 MXN per bp of a rate): it only absolves the pillars the set barely touches, where 1 % of nothing is nothing.
constexpr double kAbs = 1.0;

Triple valuesOf(const Scenario& s, const NettingSetSpec& set, const SimConfig& cfg) {
    const ExposureEngine engine(s.market, s.model, cfg);
    const PiecewiseHazardCurve cp(s.cpTimes, s.cpHazards), own(s.ownTimes, s.ownHazards);
    const XvaResult r = computeXva(engine.simulate({set})[0], cp, s.cpLgd, own, s.ownLgd, s.funding);
    return {r.cva, r.dva, r.fva};
}

XvaSensitivities aadOf(const Scenario& s, const NettingSetSpec& set, const SimConfig& cfg) {
    const ExposureEngine engine(s.market, s.model, cfg);
    const PiecewiseHazardCurve cp(s.cpTimes, s.cpHazards), own(s.ownTimes, s.ownHazards);
    return engine.xvaSensitivities(set, cp, s.cpLgd, own, s.ownLgd, s.funding);
}

// Central difference of CVA, DVA and FVA with respect to the input that move(scenario, shift) shifts.
template <class Move>
Triple bumpCentral(const Scenario& s, const NettingSetSpec& set, const SimConfig& cfg, Move move, double h) {
    Scenario up = s, down = s;
    move(up, h);
    move(down, -h);
    const Triple a = valuesOf(up, set, cfg), b = valuesOf(down, set, cfg);
    return {(a[0] - b[0]) / (2 * h), (a[1] - b[1]) / (2 * h), (a[2] - b[2]) / (2 * h)};
}

template <class Get>
Triple pick(const XvaSensitivities& s, Get get) { return {get(s.cva), get(s.dva), get(s.fva)}; }

void expectAgree(const Triple& aad, const Triple& fd, const std::string& what, double kAbsolute = kAbs) {
    const char* const names[3] = {"CVA", "DVA", "FVA"};
    for (std::size_t k = 0; k < 3; ++k)
        EXPECT_LE(std::abs(aad[k] - fd[k]), std::max(0.01 * std::abs(fd[k]), kAbsolute))
            << names[k] << " " << what << ": aad " << aad[k] << " bump " << fd[k];
}

YieldCurve& curveOf(Scenario& s, int which) {
    return which == 0 ? s.market.tiie : which == 1 ? s.market.sofr : *s.market.mxnUsd;
}

// Every pillar of one curve (0 = TIIE-F, 1 = SOFR, 2 = MXN-USD).
void expectCurveAgrees(const XvaSensitivities& aad, const Scenario& s, const NettingSetSpec& set,
                       const SimConfig& cfg, int which) {
    const char* const names[3] = {"TIIE-F", "SOFR", "MXN-USD"};
    const auto vec = [which](const XvaGreeks& g) -> const std::vector<double>& {
        return which == 0 ? g.tiie : which == 1 ? g.sofr : g.mxnUsd;
    };
    const std::size_t n = which == 0 ? s.market.tiie.maturities().size()
                          : which == 1 ? s.market.sofr.maturities().size()
                                       : s.market.mxnUsd->maturities().size();
    ASSERT_EQ(vec(aad.cva).size(), n);
    ASSERT_EQ(vec(aad.dva).size(), n);
    ASSERT_EQ(vec(aad.fva).size(), n);
    for (std::size_t i = 0; i < n; ++i) {
        const Triple fd = bumpCentral(s, set, cfg, [&](Scenario& sc, double h) {
            curveOf(sc, which) = curveOf(sc, which).bumped(i, h / 1e-4);
        }, kRateBump);
        expectAgree(pick(aad, [&](const XvaGreeks& g) { return vec(g)[i]; }), fd,
                    std::string(names[which]) + " pillar " + std::to_string(i));
    }
}

void expectSpotAgrees(const XvaSensitivities& aad, const Scenario& s, const NettingSetSpec& set,
                      const SimConfig& cfg) {
    const Triple fd = bumpCentral(s, set, cfg, [](Scenario& sc, double h) { sc.market.spot += h; }, kSpotBump);
    expectAgree(pick(aad, [](const XvaGreeks& g) { return g.spot; }), fd, "spot");
}

const SimConfig& monthly() {
    static const SimConfig cfg = makeConfig(400, schedule(0, 30, 61));   // days 0..1800
    return cfg;
}

}  // namespace

TEST(ExposureEngine, AadMatchesBumpTiieSwap) {
    const Scenario s;
    const NettingSetSpec set = setOf({mxnSwap(true, 0.0710, -10, schedule(18, 28, 65), 1.0007, false, 300e6)});
    const XvaSensitivities aad = aadOf(s, set, monthly());
    expectCurveAgrees(aad, s, set, monthly(), 0);
    // A TIIE-F swap valued in MXN without CSA does not see SOFR, MXN-USD or the spot.
    for (const XvaGreeks* g : {&aad.cva, &aad.dva, &aad.fva}) {
        for (double v : g->sofr) EXPECT_EQ(v, 0.0);
        for (double v : g->mxnUsd) EXPECT_EQ(v, 0.0);
        EXPECT_EQ(g->spot, 0.0);
    }
}

TEST(ExposureEngine, AadMatchesBumpSofrSwap) {
    const Scenario s;
    // USD swap valued in MXN: SOFR projects and discounts it, the spot converts it, TIIE-F is the bank account of the
    // deflator and MXN-USD sits in the drift of the spot.
    const NettingSetSpec set = setOf({usdSwap(false, 0.0375, -100, schedule(265, 365, 5), 1.009, 15e6),
                                      usdSwap(true, 0.0345, 0, schedule(91, 91, 20), 1.0, 10e6)});
    const XvaSensitivities aad = aadOf(s, set, monthly());
    for (int which = 0; which < 3; ++which) expectCurveAgrees(aad, s, set, monthly(), which);
    expectSpotAgrees(aad, s, set, monthly());
}

TEST(ExposureEngine, AadMatchesBumpXccySwap) {
    const Scenario s;
    const NettingSetSpec set = setOf({}, {x0(), x1()});   // CSA discounting on MXN-USD, both exchanges of notional
    const XvaSensitivities aad = aadOf(s, set, monthly());
    for (int which = 0; which < 3; ++which) expectCurveAgrees(aad, s, set, monthly(), which);
    expectSpotAgrees(aad, s, set, monthly());
}

TEST(ExposureEngine, AadMatchesBumpCombinedSet) {
    const Scenario s;
    const NettingSetSpec set = setOf({s0(), s1(), s2(), s4()}, {x0(), x1(), x2()});
    const XvaSensitivities aad = aadOf(s, set, monthly());
    for (int which = 0; which < 3; ++which) expectCurveAgrees(aad, s, set, monthly(), which);
    expectSpotAgrees(aad, s, set, monthly());

    // The five numbers of the model (the correlations are not inputs).
    const struct { const char* name; double XvaGreeks::*field; double ExposureModel::*param; } model[] = {
        {"fx vol", &XvaGreeks::fxVol, &ExposureModel::fxVol},
        {"sigma MXN", &XvaGreeks::sigmaMxn, &ExposureModel::sigmaMxn},
        {"a MXN", &XvaGreeks::aMxn, &ExposureModel::aMxn},
        {"sigma USD", &XvaGreeks::sigmaUsd, &ExposureModel::sigmaUsd},
        {"a USD", &XvaGreeks::aUsd, &ExposureModel::aUsd}};
    for (const auto& m : model) {
        const Triple fd = bumpCentral(s, set, monthly(), [&](Scenario& sc, double h) { sc.model.*m.param += h; },
                                      kModelBump);
        expectAgree(pick(aad, [&](const XvaGreeks& g) { return g.*m.field; }), fd, m.name);
    }

    // Hazards of both names (one derivative per tranche) and the funding spread.
    ASSERT_EQ(aad.cva.counterpartyHazard.size(), s.cpHazards.size());
    ASSERT_EQ(aad.cva.ownHazard.size(), s.ownHazards.size());
    for (std::size_t i = 0; i < s.cpHazards.size(); ++i) {
        const Triple fd = bumpCentral(s, set, monthly(), [&](Scenario& sc, double h) { sc.cpHazards[i] += h; },
                                      kCreditBump);
        expectAgree(pick(aad, [&](const XvaGreeks& g) { return g.counterpartyHazard[i]; }), fd,
                    "counterparty hazard " + std::to_string(i));
    }
    for (std::size_t i = 0; i < s.ownHazards.size(); ++i) {
        const Triple fd = bumpCentral(s, set, monthly(), [&](Scenario& sc, double h) { sc.ownHazards[i] += h; },
                                      kCreditBump);
        expectAgree(pick(aad, [&](const XvaGreeks& g) { return g.ownHazard[i]; }), fd,
                    "own hazard " + std::to_string(i));
    }
    const Triple fd = bumpCentral(s, set, monthly(), [](Scenario& sc, double h) { sc.funding += h; }, kCreditBump);
    expectAgree(pick(aad, [](const XvaGreeks& g) { return g.fundingSpread; }), fd, "funding spread");
}

TEST(ExposureEngine, AadValueMatchesComputeXva) {
    const Scenario s;
    const NettingSetSpec set = setOf({s0(), s1(), s2(), s4()}, {x0(), x1(), x2()});
    const XvaSensitivities aad = aadOf(s, set, monthly());
    const ExposureEngine engine(s.market, s.model, monthly());
    const PiecewiseHazardCurve cp(s.cpTimes, s.cpHazards), own(s.ownTimes, s.ownHazards);
    const XvaResult ref = computeXva(engine.simulate({set})[0], cp, s.cpLgd, own, s.ownLgd, s.funding);
    const auto close = [](double a, double b, const char* what) {
        EXPECT_LE(std::abs(a - b), 1e-12 * std::abs(b)) << what << ": " << a << " vs " << b;
    };
    close(aad.value.cva, ref.cva, "cva");
    close(aad.value.dva, ref.dva, "dva");
    close(aad.value.fva, ref.fva, "fva");
    close(aad.value.total, ref.total, "total");
    close(aad.value.cvaStdErr, ref.cvaStdErr, "cvaStdErr");
    close(aad.value.dvaStdErr, ref.dvaStdErr, "dvaStdErr");
}

TEST(ExposureEngine, AadZeroVolatilityMatchesDeterministicDerivative) {
    // Without volatility every path is the same one: the AAD derivative is the derivative of a deterministic
    // function of the curves, which a very small central bump reproduces to many digits.
    Scenario s;
    s.model = zeroVolModel();
    const NettingSetSpec set = setOf({s0(), s1(), s2(), s4()}, {x0(), x1(), x2()});
    const SimConfig cfg = makeConfig(8, schedule(0, 30, 61));
    const XvaSensitivities aad = aadOf(s, set, cfg);
    const double h = 1e-7;
    for (int which = 0; which < 3; ++which) {
        const auto vec = [which](const XvaGreeks& g) -> const std::vector<double>& {
            return which == 0 ? g.tiie : which == 1 ? g.sofr : g.mxnUsd;
        };
        for (std::size_t i = 0; i < vec(aad.cva).size(); ++i) {
            const Triple fd = bumpCentral(s, set, cfg, [&](Scenario& sc, double shift) {
                curveOf(sc, which) = curveOf(sc, which).bumped(i, shift / 1e-4);
            }, h);
            const Triple got = pick(aad, [&](const XvaGreeks& g) { return vec(g)[i]; });
            for (std::size_t k = 0; k < 3; ++k)
                EXPECT_LE(std::abs(got[k] - fd[k]), 1e-6 * std::abs(fd[k]) + 1e-3)   // 1e-3: rounding of the bump
                    << "measure " << k << " curve " << which << " pillar " << i << ": aad " << got[k]
                    << " bump " << fd[k];
        }
    }
}

TEST(ExposureEngine, AadFlatHazardHasOneTranche) {
    const NettingSetSpec set = setOf({s0(), s1()}, {x0()});
    const ExposureEngine engine(makeMarket(), demoModel(), monthly());
    const XvaSensitivities aad = engine.xvaSensitivities(set, FlatHazardRate(0.02), 0.6, FlatHazardRate(0.01), 0.5, 0.005);
    EXPECT_EQ(aad.cva.counterpartyHazard.size(), 1u);
    EXPECT_EQ(aad.cva.ownHazard.size(), 1u);
    // The exposure does not depend on credit, so one simulation serves the bumps.
    const ExposureProfile profile = engine.simulate({set})[0];
    const auto xva = [&](double lc, double lo) {
        const XvaResult r = computeXva(profile, FlatHazardRate(lc), 0.6, FlatHazardRate(lo), 0.5, 0.005);
        return Triple{r.cva, r.dva, r.fva};
    };
    const XvaResult ref = computeXva(profile, FlatHazardRate(0.02), 0.6, FlatHazardRate(0.01), 0.5, 0.005);
    EXPECT_LE(std::abs(aad.value.cva - ref.cva), 1e-12 * std::abs(ref.cva));
    EXPECT_LE(std::abs(aad.value.fva - ref.fva), 1e-12 * std::abs(ref.fva));
    const Triple c1 = xva(0.02 + kCreditBump, 0.01), c0 = xva(0.02 - kCreditBump, 0.01);
    const Triple o1 = xva(0.02, 0.01 + kCreditBump), o0 = xva(0.02, 0.01 - kCreditBump);
    Triple fdC, fdO;
    for (std::size_t k = 0; k < 3; ++k) {
        fdC[k] = (c1[k] - c0[k]) / (2 * kCreditBump);
        fdO[k] = (o1[k] - o0[k]) / (2 * kCreditBump);
    }
    expectAgree(pick(aad, [](const XvaGreeks& g) { return g.counterpartyHazard[0]; }), fdC, "flat counterparty hazard");
    expectAgree(pick(aad, [](const XvaGreeks& g) { return g.ownHazard[0]; }), fdO, "flat own hazard");
}

TEST(ExposureEngine, AadRejectsNonLinearCurves) {
    const NettingSetSpec set = setOf({s0()});
    const FlatHazardRate hazard(0.02);
    const YieldCurve cubic({0.25, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 12.0},
                           {0.0690, 0.0700, 0.0705, 0.0710, 0.0715, 0.0720, 0.0725, 0.0728},
                           InterpolationMethod::CubicSpline);
    const SimConfig cfg = makeConfig(10, schedule(0, 30, 5));
    // The double engine accepts any interpolation; the AAD replicates only Linear and refuses the rest.
    EXPECT_NO_THROW(ExposureEngine(ExposureMarket{cubic, sofrCurve(), std::nullopt, kSpot}, demoModel(), cfg)
                        .simulate({set}));
    EXPECT_THROW(ExposureEngine(ExposureMarket{cubic, sofrCurve(), std::nullopt, kSpot}, demoModel(), cfg)
                     .xvaSensitivities(set, hazard, 0.6, hazard, 0.6, 0.005), std::invalid_argument);
    EXPECT_THROW(ExposureEngine(ExposureMarket{tiieCurve(), cubic, std::nullopt, kSpot}, demoModel(), cfg)
                     .xvaSensitivities(set, hazard, 0.6, hazard, 0.6, 0.005), std::invalid_argument);
    EXPECT_THROW(ExposureEngine(ExposureMarket{tiieCurve(), sofrCurve(), std::optional<YieldCurve>(cubic), kSpot},
                                demoModel(), cfg).xvaSensitivities(set, hazard, 0.6, hazard, 0.6, 0.005),
                 std::invalid_argument);
    // A credit curve of another type has no tranches to differentiate.
    struct OtherCurve : ICreditCurve {
        double survivalProbability(double t) const override { return std::exp(-0.01 * t); }
    };
    EXPECT_THROW(ExposureEngine(makeMarket(), demoModel(), cfg).xvaSensitivities(set, OtherCurve{}, 0.6, hazard, 0.6, 0.005),
                 std::invalid_argument);
    EXPECT_NO_THROW(ExposureEngine(makeMarket(), demoModel(), cfg).xvaSensitivities(set, hazard, 0.6, hazard, 0.6, 0.005));
}

TEST(ExposureEngine, AadMaxThreadsCapsTheWorkersAndKeepsTheResult) {
    // One tape per worker thread. The cap bounds the tapes (memory); the paths are summed in order of their chunk, so
    // only the rounding of the sum depends on it.
    const NettingSetSpec set = setOf({s0(), s1()}, {x0()});
    const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(200, schedule(0, 30, 20)));
    const PiecewiseHazardCurve cp({1.0, 5.0}, {0.010, 0.020}), own({1.0, 5.0}, {0.004, 0.006});
    const unsigned hardware = std::max(1u, std::thread::hardware_concurrency());
    const auto run = [&](unsigned maxThreads, unsigned expectedThreads) {
        const XvaSensitivities r = engine.xvaSensitivities(set, cp, 0.6, own, 0.5, 0.005, maxThreads);
        EXPECT_EQ(qf::xva::detail::aadThreads(), expectedThreads) << "maxThreads " << maxThreads;
        return r;
    };
    const XvaSensitivities one = run(1, 1);
    const XvaSensitivities two = run(2, std::min(2u, hardware));
    const XvaSensitivities many = run(64, std::min(64u, hardware));
    const XvaSensitivities byDefault = engine.xvaSensitivities(set, cp, 0.6, own, 0.5, 0.005);
    EXPECT_EQ(qf::xva::detail::aadThreads(), std::min(2u, hardware));   // the default is two
    const auto flat = [](const XvaSensitivities& r) {
        std::vector<double> v = {r.value.cva, r.value.dva, r.value.fva};
        for (const XvaGreeks* g : {&r.cva, &r.dva, &r.fva})
            for (const auto* part : {&g->tiie, &g->sofr, &g->mxnUsd, &g->counterpartyHazard, &g->ownHazard})
                v.insert(v.end(), part->begin(), part->end());
        return v;
    };
    const std::vector<double> ref = flat(one);
    for (const XvaSensitivities* other : {&two, &many, &byDefault}) {
        const std::vector<double> got = flat(*other);
        ASSERT_EQ(got.size(), ref.size());
        for (std::size_t i = 0; i < ref.size(); ++i)
            EXPECT_LE(std::abs(got[i] - ref[i]), 1e-9 * std::abs(ref[i]) + 1e-9) << "entry " << i;
    }
    EXPECT_THROW(engine.xvaSensitivities(set, cp, 0.6, own, 0.5, 0.005, 0), std::invalid_argument);
}

// Pins the calling thread, and so the threads it starts afterwards, to the CPU it runs on for as long as it lives
// (Linux; `pinned` stays false elsewhere).
struct OneCpu {
    bool pinned = false;
#ifdef __linux__
    cpu_set_t saved{};
    OneCpu() {
        cpu_set_t one;
        CPU_ZERO(&one);
        CPU_SET(sched_getcpu(), &one);
        pinned = sched_getaffinity(0, sizeof saved, &saved) == 0 && sched_setaffinity(0, sizeof one, &one) == 0;
    }
    ~OneCpu() {
        if (pinned) sched_setaffinity(0, sizeof saved, &saved);
    }
#endif
};

// R5, run by hand: ctest skips it. Combined set of 3 trades (TIIE-F 10 y payer with CSA, SOFR 5 y receiver, 5 y
// cross currency swap with CSA), 2000 paths, integration grid of the desk (monthly U every 3 days U every payment
// and its eve). R5 (decision of Fable after measuring): ratio = t(xvaSensitivities with maxThreads = 1) /
// t(simulate + computeXva) with ONE core for both must be <= 10. simulate has no thread cap and
// hardware_concurrency ignores the affinity mask, so the double side still starts every thread but they share the
// one CPU the process is pinned to (OneCpu, Linux), which costs what one thread costs. (The process CPU time over
// all the threads is not a substitute: 8 threads on 4 hyperthreaded cores add up 2.4 times the work of one.)
// Also printed, unpinned: the wall times of the double on every thread and of the AAD with its default two
// threads, which is what the API pays, and the peak bytes of a tape (they must not depend on the number of paths).
TEST(ExposureEngine, DISABLED_AadTiming) {
    const NettingSetSpec set =
        setOf({mxnSwap(true, 0.0710, 0, schedule(28, 28, 130), 1.0, true, 300e6),
               usdSwap(false, 0.0375, 0, schedule(91, 91, 20), 1.0, 15e6)},
              {xccySwap(true, 0, schedule(91, 91, 20), 18.20, 0.0005, true, true)});
    std::set<int> days = {0};
    const int horizon = lastPayDay(set);
    for (int d = 30; d <= horizon; d += 30) days.insert(d);
    for (int d = 3; d <= horizon; d += 3) days.insert(d);
    const auto payments = [&](const std::vector<int>& pay) {
        for (int d : pay) { days.insert(d); days.insert(d - 1); }
    };
    for (const auto& sw : set.swaps) payments(sw.payDays);
    for (const auto& x : set.xccys) payments(x.payDays);
    const std::vector<int> grid(days.begin(), days.end());
    const PiecewiseHazardCurve cp({0.5, 1.0, 2.0, 3.0, 5.0, 10.0}, {0.010, 0.012, 0.015, 0.018, 0.020, 0.022});
    const PiecewiseHazardCurve own({0.5, 1.0, 2.0, 3.0, 5.0, 10.0}, {0.004, 0.005, 0.006, 0.007, 0.008, 0.009});
    const auto seconds = [](auto&& f) {
        const auto t0 = std::chrono::steady_clock::now();
        f();
        return std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    };
    double ratio = 0.0;
    std::size_t bytes500 = 0, bytes2000 = 0;
    for (std::size_t nPaths : {std::size_t{500}, std::size_t{2000}}) {
        const ExposureEngine engine(makeMarket(), demoModel(), makeConfig(nPaths, grid));
        const auto valuation = [&] { computeXva(engine.simulate({set})[0], cp, 0.6, own, 0.5, 0.005); };
        const double wallDouble = seconds(valuation);
        const double wallAad = seconds([&] { engine.xvaSensitivities(set, cp, 0.6, own, 0.5, 0.005); });
        const std::size_t aadThreads = qf::xva::detail::aadThreads();
        const OneCpu oneCpu;
        if (!oneCpu.pinned) GTEST_SKIP() << "the one-thread measurement needs sched_setaffinity (Linux)";
        double base = 1e300;
        for (int rep = 0; rep < 2; ++rep) base = std::min(base, seconds(valuation));
        const double aad = seconds([&] { engine.xvaSensitivities(set, cp, 0.6, own, 0.5, 0.005, 1); });
        (nPaths == 500 ? bytes500 : bytes2000) = qf::xva::detail::aadTapeBytes();
        ratio = aad / base;
        std::printf("paths %zu dates %zu: ONE core: double %.3f s, AAD %.3f s, ratio = %.2f; all cores: double %.3f s "
                    "on %u threads, AAD %.3f s on %zu threads (default); tape bytes per thread = %zu\n",
                    nPaths, grid.size(), base, aad, ratio, wallDouble, std::thread::hardware_concurrency(), wallAad,
                    aadThreads, qf::xva::detail::aadTapeBytes());
    }
    EXPECT_EQ(bytes500, bytes2000);
    EXPECT_LE(ratio, 10.0);
}
#endif
