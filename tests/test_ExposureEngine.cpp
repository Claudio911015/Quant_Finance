#include <gtest/gtest.h>
#include <qf/xva/exposure_engine.hpp>
#include <qf/xva/credit_curve.hpp>
#include <qf/instruments/ois_swap.hpp>
#include <qf/instruments/xccy_swap.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/interpolation.hpp>
#include <algorithm>
#include <cmath>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

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
