#include <qf/xva/exposure_engine.hpp>
#include <qf/math/interpolation.hpp>
#include <qf/xva/piecewise_hazard_curve.hpp>
#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <exception>
#include <limits>
#include <map>
#include <mutex>
#include <random>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#ifdef QF_WITH_XAD
#include <XAD/XAD.hpp>
#endif

namespace qf::xva {

namespace detail {

/// Closed-form moments of the Hull-White factor x under the simulation measure at time t (years):
/// y(t) = sigma^2 (1 - e^{-2at}) / (2a), m(t) = E[x(t)], mInt(t) = E[int_0^t x] with
/// dx = (y - a x + mu) dt + sigma dW. Exposed (outside the public header) so tests can check them.
struct OuMoments {
    double y;
    double m;
    double mInt;
};
OuMoments ouMoments(double a, double sigma, double mu, double t);

/// Covariance of the stochastic integrals of one step dt, ordered (xi_MXN, eta_MXN, xi_USD, eta_USD, zeta):
/// xi = sigma int e^{-a(dt-s)} dW, eta = sigma int (1 - e^{-a(dt-s)})/a dW, zeta = sigma_X int dW.
std::array<std::array<double, 5>, 5> stepCovariance(const ExposureModel& model, double dt);

/// Peak bytes held by one AAD tape during the last xvaSensitivities() call (0 without XAD). Diagnostic for the
/// timing test: it must not grow with the number of paths.
std::size_t aadTapeBytes();

/// Number of tapes (worker threads) of the last xvaSensitivities() call (0 without XAD). Diagnostic for the
/// test of the `maxThreads` cap.
std::size_t aadThreads();

} // namespace detail

namespace {

// ---------------------------------------------------------------------------------------------
// Model (all times are days / 365, measure = MXN risk neutral)
//
//   r_c(t) = f_c(0,t) + x_c(t),    dx_c = (y_c(t) - a_c x_c + mu_c) dt + sigma_c dW_c
//   y_c(t) = sigma_c^2 (1 - e^{-2 a_c t}) / (2 a_c),   mu_MXN = 0,  mu_USD = -rho_{USD,X} sigma_USD sigma_X
//   d ln X = (r_MXN + b(t) - r_USD - sigma_X^2 / 2) dt + sigma_X dW_X,   b = -d ln q / dt
//
// The pair (x_c, int x_c) is simulated with its exact Gaussian transition: x = xTilde + m with
// xTilde a zero-mean Ornstein-Uhlenbeck process and m, M = int m deterministic (closed form), so a
// step needs only the (constant) covariance of the stochastic integrals of xi, eta, zeta below.
// ---------------------------------------------------------------------------------------------

constexpr double kDaysPerYear = 365.0;
constexpr int kMxn = 0;
constexpr int kUsd = 1;

// The numbers the model depends on (curves, spot, volatilities, mean reversions) live in `Real`: double for
// simulate() and friends, an XAD scalar when the same code is differentiated. Everything that is not an
// input (days, notionals, rates of the trades, correlations, the normals) stays double. The math functions
// are called unqualified so XAD finds its own overloads by ADL; for double they are the std ones.
using std::exp;
using std::expm1;
using std::log;
using std::max;
using std::sqrt;

template <class Real>
struct ModelT {
    Real aMxn, sigmaMxn, aUsd, sigmaUsd, fxVol;
    double rhoMxnUsd, rhoMxnFx, rhoUsdFx;
};

// A curve is YieldCurve for double and PillarCurve<Real> when its zero rates are inputs.
template <class Real, class Curve>
struct MarketT {
    const Curve* tiie;
    const Curve* sofr;
    const Curve* mxnUsd;     // nullptr without basis
    Real spot;
};

ModelT<double> modelOf(const ExposureModel& m)
{
    return {m.aMxn, m.sigmaMxn, m.aUsd, m.sigmaUsd, m.fxVol, m.rhoMxnUsd, m.rhoMxnFx, m.rhoUsdFx};
}

MarketT<double, termstructure::YieldCurve> marketOf(const ExposureMarket& m)
{
    return {&m.tiie, &m.sofr, m.mxnUsd ? &*m.mxnUsd : nullptr, m.spot};
}

template <class Real>
using Mat5 = std::array<std::array<Real, 5>, 5>;

// int_0^dt e^{-k tau} dtau
template <class Real>
Real expIntegral(Real k, double dt)
{
    return k == 0.0 ? Real(dt) : Real(-expm1(-k * dt) / k);
}

// A kernel f(tau) = c0 + c1 e^{-a tau} on tau in [0, dt] (tau = time to the end of the step).
template <class Real>
struct Kernel {
    Real c0;
    Real c1;
    Real a;
};

template <class Real> Kernel<Real> uKernel(Real a) { return {0.0, 1.0, a}; }              // e^{-a tau}
template <class Real> Kernel<Real> vKernel(Real a) { return {1.0 / a, -1.0 / a, a}; }     // (1 - e^{-a tau}) / a
template <class Real> Kernel<Real> oneKernel() { return {1.0, 0.0, 0.0}; }                // 1

template <class Real>
Real kernelIntegral(const Kernel<Real>& f, const Kernel<Real>& g, double dt)
{
    Real s = f.c0 * g.c0 * dt;
    if (g.c1 != 0.0) s += f.c0 * g.c1 * expIntegral(g.a, dt);
    if (f.c1 != 0.0) s += f.c1 * g.c0 * expIntegral(f.a, dt);
    if (f.c1 != 0.0 && g.c1 != 0.0) s += f.c1 * g.c1 * expIntegral(Real(f.a + g.a), dt);
    return s;
}

// Lower Cholesky factor of a positive semidefinite matrix; a zero pivot gives a zero column
// (a zero volatility removes that factor instead of failing).
template <class Real>
Mat5<Real> choleskySemidefinite(const Mat5<Real>& A)
{
    Mat5<Real> L{};
    for (std::size_t j = 0; j < 5; ++j) {
        Real s = A[j][j];
        for (std::size_t k = 0; k < j; ++k) s -= L[j][k] * L[j][k];
        const Real scale = max(A[j][j], 0.0);
        if (!(s > 1e-12 * scale) || scale == 0.0) {
            L[j][j] = 0.0;
            continue;
        }
        L[j][j] = sqrt(s);
        for (std::size_t i = j + 1; i < 5; ++i) {
            Real t = A[i][j];
            for (std::size_t k = 0; k < j; ++k) t -= L[i][k] * L[j][k];
            L[i][j] = t / L[j][j];
        }
    }
    return L;
}

// ---------------------------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------------------------

void validateModel(const ExposureModel& m)
{
    const auto finite = [](double v) { return std::isfinite(v); };
    if (!finite(m.aMxn) || !(m.aMxn > 0.0) || !finite(m.aUsd) || !(m.aUsd > 0.0))
        throw std::invalid_argument("ExposureEngine: mean reversion speeds must be positive");
    if (!finite(m.sigmaMxn) || m.sigmaMxn < 0.0 || !finite(m.sigmaUsd) || m.sigmaUsd < 0.0 ||
        !finite(m.fxVol) || m.fxVol < 0.0)
        throw std::invalid_argument("ExposureEngine: volatilities must be non-negative");
    const double r12 = m.rhoMxnUsd, r13 = m.rhoMxnFx, r23 = m.rhoUsdFx;
    for (double r : {r12, r13, r23})
        if (!finite(r) || !(std::abs(r) < 1.0))
            throw std::invalid_argument("ExposureEngine: correlations must lie in (-1, 1)");
    const double det = 1.0 + 2.0 * r12 * r13 * r23 - r12 * r12 - r13 * r13 - r23 * r23;
    if (!(det > 1e-12))
        throw std::invalid_argument("ExposureEngine: correlation matrix is not positive definite");
}

void validateConfig(const SimConfig& c)
{
    if (c.nPaths == 0)
        throw std::invalid_argument("ExposureEngine: nPaths must be positive");
    if (!(c.pfeQuantile > 0.0 && c.pfeQuantile < 1.0))   // also rejects NaN
        throw std::invalid_argument("ExposureEngine: pfeQuantile must be in (0,1)");
    if (c.reportDays.empty() || c.reportDays.front() != 0)
        throw std::invalid_argument("ExposureEngine: reportDays must start at 0");
    for (std::size_t i = 1; i < c.reportDays.size(); ++i)
        if (c.reportDays[i] <= c.reportDays[i - 1])
            throw std::invalid_argument("ExposureEngine: reportDays must be strictly increasing");
}

void validateIncreasingPayDays(const std::vector<int>& payDays, int startDays, const char* who)
{
    if (payDays.empty())
        throw std::invalid_argument(std::string(who) + ": payDays must not be empty");
    if (payDays.front() <= 0)
        throw std::invalid_argument(std::string(who) + ": payDays must be positive");
    for (std::size_t i = 1; i < payDays.size(); ++i)
        if (payDays[i] <= payDays[i - 1])
            throw std::invalid_argument(std::string(who) + ": payDays must be strictly increasing");
    if (startDays >= payDays.front())
        throw std::invalid_argument(std::string(who) + ": startDays must precede the first payment");
}

void validateSwap(const RateSwapSpec& s)
{
    if (!std::isfinite(s.notional) || s.notional <= 0.0)
        throw std::invalid_argument("RateSwapSpec: notional must be positive");
    if (!std::isfinite(s.fixedRate))
        throw std::invalid_argument("RateSwapSpec: fixedRate must be finite");
    validateIncreasingPayDays(s.payDays, s.startDays, "RateSwapSpec");
    if (!(s.accruedFactor > 0.0))
        throw std::invalid_argument("RateSwapSpec: accruedFactor must be positive");
    if (s.startDays >= 0 && s.accruedFactor != 1.0)
        throw std::invalid_argument("RateSwapSpec: accruedFactor must be 1 when the period has not started");
    if (!(s.dayBase > 0.0))
        throw std::invalid_argument("RateSwapSpec: dayBase must be positive");
}

void validateXccy(const XccySwapSpec& x)
{
    if (!std::isfinite(x.notionalUsd) || x.notionalUsd <= 0.0)
        throw std::invalid_argument("XccySwapSpec: notionalUsd must be positive");
    if (!std::isfinite(x.fxRate) || x.fxRate <= 0.0)
        throw std::invalid_argument("XccySwapSpec: fxRate must be positive");
    if (!std::isfinite(x.spread))
        throw std::invalid_argument("XccySwapSpec: spread must be finite");
    validateIncreasingPayDays(x.payDays, x.startDays, "XccySwapSpec");
    if (!(x.accruedFactorUsd > 0.0) || !(x.accruedFactorMxn > 0.0))
        throw std::invalid_argument("XccySwapSpec: accrued factors must be positive");
    if (x.startDays >= 0 && (x.accruedFactorUsd != 1.0 || x.accruedFactorMxn != 1.0))
        throw std::invalid_argument("XccySwapSpec: accrued factors must be 1 when the period has not started");
    if (!(x.dayBase > 0.0))
        throw std::invalid_argument("XccySwapSpec: dayBase must be positive");
}

// ---------------------------------------------------------------------------------------------
// Compiled instruments
//
// Every swap or swap leg is a "leg": a currency that projects the floating coupons (and whose short
// rate compounds the period in progress), a discount curve, a sign, and its periods. The value at
// t of a leg, in its own currency, is
//
//   sum_unpaid  floatSign N (F_i(t) - Pproj(t,pay_i)) g_i  +  rateSign N rate tau_i Pdisc(t,pay_i)
//             + exchanges,
//
// with F_i(t) the compounded factor of period i (accrued * exp(int r) when it has started,
// Pproj(t,start) when it has not) and g_i = Pdisc/Pproj (1, or q(pay)/q(t) with the MXN-USD basis).
// ---------------------------------------------------------------------------------------------

enum DiscKind { DiscTiie = 0, DiscCsa = 1, DiscSofr = 2 };

struct LegPeriod {
    int         payDay;
    int         prevDay;     // start of the period (negative if it began before today)
    std::size_t payIdx;      // index of payDay in the day table
    std::size_t prevIdx;     // index of prevDay (only meaningful for prevDay >= 0)
    double      tau;
};

struct Leg {
    int         proj = kMxn;          // currency of the projection curve and the compounding rate
    int         disc = DiscTiie;
    bool        toMxn = false;        // multiply by X(t)
    double      notional = 0.0;
    double      floatSign = 0.0;
    double      rate = 0.0;           // fixed rate or spread
    double      rateSign = 0.0;
    double      accrued = 1.0;        // accrued factor of the first period
    double      exSign = 0.0;
    int         startDays = 0;
    bool        initEx = false;
    bool        finalEx = false;
    std::size_t startIdx = 0;
    std::size_t lastIdx = 0;
    std::vector<LegPeriod> periods;
};

struct Trade {
    std::vector<Leg> legs;
};

struct CompiledSet {
    std::vector<Trade> trades;
};

// ---------------------------------------------------------------------------------------------
// Per-day tables
// ---------------------------------------------------------------------------------------------

template <class Real>
struct CurrencyGrid {
    Real a = 0.0;
    Real sigma = 0.0;
    Real eStep = 0.0;                 // e^{-a dt}
    Real vStep = 0.0;                 // (1 - e^{-a dt}) / a
    std::vector<Real> p0;             // P(0, d/365)
    std::vector<Real> lnP0;
    std::vector<Real> expAt;          // e^{-a d/365}
    std::vector<Real> y;              // y(d/365)
    std::vector<Real> m;              // mean of x
    std::vector<Real> mInt;           // mean of int x
};

template <class Real>
struct Grid {
    int horizon = 0;
    double dt = 1.0 / kDaysPerYear;
    Real spot = 0.0;
    Real fxVar = 0.0;
    CurrencyGrid<Real> ccy[2];
    std::vector<Real> q;
    std::vector<Real> lnq;
    Mat5<Real> chol{};
};

// Moments of the Hull-White factor (see detail::ouMoments), on Real.
template <class Real>
struct OuMomentsT {
    Real y;
    Real m;
    Real mInt;
};

template <class Real>
OuMomentsT<Real> ouMomentsT(Real a, Real sigma, Real mu, double t)
{
    const Real s2 = sigma * sigma;
    const Real em = -expm1(-a * t);                          // 1 - e^{-a t}
    const Real e2 = -expm1(-2.0 * a * t);                    // 1 - e^{-2 a t}
    OuMomentsT<Real> out;
    out.y = s2 * e2 / (2.0 * a);
    out.m = s2 / (2.0 * a * a) * em * em + mu * em / a;
    out.mInt = s2 / (2.0 * a * a) * (t - 2.0 * em / a + e2 / (2.0 * a)) + mu / a * (t - em / a);
    return out;
}

// Covariance of the stochastic integrals of one step dt (see detail::stepCovariance), on Real.
template <class Real>
Mat5<Real> stepCovarianceT(const ModelT<Real>& model, double dt)
{
    const std::array<Kernel<Real>, 5> kernel = {uKernel(model.aMxn), vKernel(model.aMxn), uKernel(model.aUsd),
                                                vKernel(model.aUsd), oneKernel<Real>()};
    const std::array<Real, 5> vol = {model.sigmaMxn, model.sigmaMxn, model.sigmaUsd, model.sigmaUsd,
                                     model.fxVol};
    const std::array<int, 5> factor = {0, 0, 1, 1, 2};   // which Brownian drives each integral
    const double rho[3][3] = {{1.0, model.rhoMxnUsd, model.rhoMxnFx},
                              {model.rhoMxnUsd, 1.0, model.rhoUsdFx},
                              {model.rhoMxnFx, model.rhoUsdFx, 1.0}};
    Mat5<Real> cov{};
    for (std::size_t i = 0; i < 5; ++i)
        for (std::size_t j = 0; j < 5; ++j)
            cov[i][j] = rho[factor[i]][factor[j]] * vol[i] * vol[j] * kernelIntegral(kernel[i], kernel[j], dt);
    return cov;
}

// P(0,T) of a curve. For double the curve is a YieldCurve, whatever its interpolation.
inline double discountAt(const termstructure::YieldCurve& curve, double T) { return curve.discountFactor(T); }

// Zero-rate pillars as differentiable inputs. discountAt replicates the Linear branch of math::Interpolator
// (flat outside the range, y[i](1-t) + y[i+1]t on the bracketing pillars, then exp(-r T)) instead of templating
// Interpolator/YieldCurve, which the whole repository uses; it only stands in for curves built with Linear.
template <class Real>
struct PillarCurve {
    std::vector<double> t;   // pillar maturities, years
    std::vector<Real> z;     // pillar zero rates
};

template <class Real>
Real discountAt(const PillarCurve<Real>& curve, double T)
{
    Real r;
    if (T <= curve.t.front()) {
        r = curve.z.front();
    } else if (T >= curve.t.back()) {
        r = curve.z.back();
    } else {
        const std::size_t i = static_cast<std::size_t>(std::lower_bound(curve.t.begin(), curve.t.end(), T) -
                                                       curve.t.begin()) - 1;
        const double w = (T - curve.t[i]) / (curve.t[i + 1] - curve.t[i]);
        r = curve.z[i] * (1.0 - w) + curve.z[i + 1] * w;
    }
    return exp(-r * T);
}

template <class Real, class Curve>
void fillCurrencyGrid(CurrencyGrid<Real>& g, const Curve& curve, Real a, Real sigma, Real mu, int horizon)
{
    g.a = a;
    g.sigma = sigma;
    const double dt = 1.0 / kDaysPerYear;
    g.eStep = exp(-a * dt);
    g.vStep = -expm1(-a * dt) / a;
    const std::size_t n = static_cast<std::size_t>(horizon) + 1;
    g.p0.assign(n, 1.0);
    g.lnP0.assign(n, 0.0);
    g.expAt.assign(n, 1.0);
    g.y.assign(n, 0.0);
    g.m.assign(n, 0.0);
    g.mInt.assign(n, 0.0);
    for (std::size_t d = 0; d < n; ++d) {
        const double t = static_cast<double>(d) / kDaysPerYear;
        if (d > 0) {
            g.p0[d] = discountAt(curve, t);
            g.lnP0[d] = log(g.p0[d]);
        }
        g.expAt[d] = exp(-a * t);
        const OuMomentsT<Real> mo = ouMomentsT(a, sigma, mu, t);
        g.y[d] = mo.y;
        g.m[d] = mo.m;
        g.mInt[d] = mo.mInt;
    }
}

template <class Real, class Curve>
Grid<Real> buildGrid(const MarketT<Real, Curve>& market, const ModelT<Real>& model, int horizon)
{
    Grid<Real> g;
    g.horizon = horizon;
    g.spot = market.spot;
    g.fxVar = model.fxVol * model.fxVol;
    // Quanto drift of the USD short rate under the MXN measure.
    const Real muUsd = -model.rhoUsdFx * model.sigmaUsd * model.fxVol;
    fillCurrencyGrid(g.ccy[kMxn], *market.tiie, model.aMxn, model.sigmaMxn, Real(0.0), horizon);
    fillCurrencyGrid(g.ccy[kUsd], *market.sofr, model.aUsd, model.sigmaUsd, muUsd, horizon);

    const std::size_t n = static_cast<std::size_t>(horizon) + 1;
    g.q.assign(n, 1.0);
    g.lnq.assign(n, 0.0);
    if (market.mxnUsd) {
        for (std::size_t d = 1; d < n; ++d) {
            const double t = static_cast<double>(d) / kDaysPerYear;
            g.q[d] = discountAt(*market.mxnUsd, t) / g.ccy[kMxn].p0[d];
            g.lnq[d] = log(g.q[d]);
        }
    }

    const Mat5<Real> cov = stepCovarianceT(model, g.dt);
    g.chol = choleskySemidefinite(cov);
    return g;
}

// ---------------------------------------------------------------------------------------------
// Context: grid + sorted day table + compiled sets
// ---------------------------------------------------------------------------------------------

template <class Real>
struct Context {
    Grid<Real> grid;
    std::vector<int> days;                    // sorted unique days (0 included) any instrument refers to
    std::vector<Real> p0[2];                  // P_c(0, day) per table entry
    std::vector<Real> expAt[2];               // e^{-a_c day/365} per table entry
    std::vector<Real> qAt;                    // q(day) per table entry
    std::vector<char> need[2];                // bond of currency c needed at this entry
    bool anyNeed[2] = {false, false};
    std::vector<CompiledSet> sets;
};

void collectDays(const NettingSetSpec& set, std::vector<int>& out)
{
    for (const auto& s : set.swaps) {
        out.insert(out.end(), s.payDays.begin(), s.payDays.end());
        if (s.startDays >= 0) out.push_back(s.startDays);
    }
    for (const auto& x : set.xccys) {
        out.insert(out.end(), x.payDays.begin(), x.payDays.end());
        if (x.startDays >= 0) out.push_back(x.startDays);
    }
}

int maxPayDay(const NettingSetSpec& set)
{
    int m = 0;
    for (const auto& s : set.swaps) m = std::max(m, s.payDays.back());
    for (const auto& x : set.xccys) m = std::max(m, x.payDays.back());
    return m;
}

std::size_t indexOf(const std::vector<int>& days, int day)
{
    return static_cast<std::size_t>(std::lower_bound(days.begin(), days.end(), day) - days.begin());
}

template <class Real>
void markNeed(Context<Real>& c, int ccy, std::size_t idx)
{
    c.need[ccy][idx] = 1;
    c.anyNeed[ccy] = true;
}

template <class Real>
Leg makeLeg(Context<Real>& c, int proj, int disc, bool toMxn, double notional, double floatSign, double rate,
            double rateSign, double accrued, double exSign, int startDays, const std::vector<int>& payDays,
            double dayBase, bool initEx, bool finalEx)
{
    Leg leg;
    leg.proj = proj;
    leg.disc = disc;
    leg.toMxn = toMxn;
    leg.notional = notional;
    leg.floatSign = floatSign;
    leg.rate = rate;
    leg.rateSign = rateSign;
    leg.accrued = accrued;
    leg.exSign = exSign;
    leg.startDays = startDays;
    leg.initEx = initEx && startDays >= 0;     // an initial exchange already behind is not a cash flow
    leg.finalEx = finalEx;
    const int discCcy = disc == DiscSofr ? kUsd : kMxn;
    int prev = startDays;
    for (int pay : payDays) {
        LegPeriod p;
        p.payDay = pay;
        p.prevDay = prev;
        p.payIdx = indexOf(c.days, pay);
        p.prevIdx = prev >= 0 ? indexOf(c.days, prev) : 0;
        p.tau = static_cast<double>(pay - prev) / dayBase;
        markNeed(c, proj, p.payIdx);
        if (prev >= 0) markNeed(c, proj, p.prevIdx);
        markNeed(c, discCcy, p.payIdx);
        leg.periods.push_back(p);
        prev = pay;
    }
    leg.lastIdx = leg.periods.back().payIdx;
    if (leg.initEx) {
        leg.startIdx = indexOf(c.days, startDays);
        markNeed(c, discCcy, leg.startIdx);
    }
    return leg;
}

template <class Real>
CompiledSet compileSet(Context<Real>& c, const NettingSetSpec& set)
{
    CompiledSet out;
    for (const auto& s : set.swaps) {
        const bool usd = s.currency == SwapCurrency::USD;
        const double sign = s.payer ? 1.0 : -1.0;       // payer: receives floating, pays fixed
        Trade t;
        t.legs.push_back(makeLeg(c, usd ? kUsd : kMxn, usd ? DiscSofr : (s.csaDiscount ? DiscCsa : DiscTiie),
                                 usd, s.notional, sign, s.fixedRate, -sign, s.accruedFactor, 0.0,
                                 s.startDays, s.payDays, s.dayBase, false, false));
        out.trades.push_back(std::move(t));
    }
    for (const auto& x : set.xccys) {
        const double mxnSign = x.payUsd ? 1.0 : -1.0;   // PayUsd receives the MXN leg
        Trade t;
        t.legs.push_back(makeLeg(c, kMxn, x.csaDiscount ? DiscCsa : DiscTiie, false, x.notionalUsd * x.fxRate,
                                 mxnSign, x.spread, mxnSign, x.accruedFactorMxn, mxnSign, x.startDays,
                                 x.payDays, x.dayBase, x.initialExchange, x.finalExchange));
        t.legs.push_back(makeLeg(c, kUsd, DiscSofr, true, x.notionalUsd, -mxnSign, 0.0, -mxnSign,
                                 x.accruedFactorUsd, -mxnSign, x.startDays, x.payDays, x.dayBase,
                                 x.initialExchange, x.finalExchange));
        out.trades.push_back(std::move(t));
    }
    return out;
}

template <class Real, class Curve>
Context<Real> buildContext(const MarketT<Real, Curve>& market, const ModelT<Real>& model,
                           const std::vector<NettingSetSpec>& sets, int minHorizon)
{
    bool needsBasis = false;
    int horizon = std::max(minHorizon, 0);
    std::vector<int> days = {0};
    for (const NettingSetSpec& set : sets) {
        for (const auto& s : set.swaps) {
            validateSwap(s);
            if (s.currency == SwapCurrency::MXN && s.csaDiscount) needsBasis = true;
        }
        for (const auto& x : set.xccys) {
            validateXccy(x);
            if (x.csaDiscount) needsBasis = true;
        }
        if (!set.swaps.empty() || !set.xccys.empty()) horizon = std::max(horizon, maxPayDay(set));
        collectDays(set, days);
    }
    if (needsBasis && !market.mxnUsd)
        throw std::invalid_argument("ExposureEngine: csaDiscount requires the MXN-USD curve (market.mxnUsd)");
    std::sort(days.begin(), days.end());
    days.erase(std::unique(days.begin(), days.end()), days.end());

    Context<Real> c;
    c.grid = buildGrid(market, model, horizon);
    c.days = std::move(days);
    const std::size_t n = c.days.size();
    for (int k = 0; k < 2; ++k) {
        c.p0[k].resize(n);
        c.expAt[k].resize(n);
        c.need[k].assign(n, 0);
        for (std::size_t i = 0; i < n; ++i) {
            const std::size_t d = static_cast<std::size_t>(c.days[i]);
            c.p0[k][i] = c.grid.ccy[k].p0[d];
            c.expAt[k][i] = c.grid.ccy[k].expAt[d];
        }
    }
    c.qAt.resize(n);
    for (std::size_t i = 0; i < n; ++i) c.qAt[i] = c.grid.q[static_cast<std::size_t>(c.days[i])];
    for (const NettingSetSpec& set : sets) c.sets.push_back(compileSet(c, set));
    return c;
}

// ---------------------------------------------------------------------------------------------
// One simulated path
// ---------------------------------------------------------------------------------------------

template <class Real>
struct PathData {
    std::vector<Real> x[2];     // short-rate factor x_c(d)
    std::vector<Real> I[2];     // int_0^t r_c
    std::vector<Real> X;        // MXN per USD

    void resize(int horizon)
    {
        const std::size_t n = static_cast<std::size_t>(horizon) + 1;
        for (int k = 0; k < 2; ++k) {
            x[k].assign(n, 0.0);
            I[k].assign(n, 0.0);
        }
        X.assign(n, 0.0);
    }
};

// Path p draws its normals from a generator seeded with (seed, p), day after day, so a path never
// depends on the instruments or on how far the horizon goes: a longer horizon only appends normals.
template <class Real>
void simulatePath(const Grid<Real>& g, unsigned seed, std::uint64_t p, PathData<Real>& path)
{
    std::seed_seq seq{static_cast<std::uint32_t>(seed), static_cast<std::uint32_t>(p & 0xffffffffu),
                      static_cast<std::uint32_t>(p >> 32)};
    std::mt19937_64 gen(seq);
    std::normal_distribution<double> normal(0.0, 1.0);

    const CurrencyGrid<Real>& cm = g.ccy[kMxn];
    const CurrencyGrid<Real>& cu = g.ccy[kUsd];
    Real xtM = 0.0, xtU = 0.0, jtM = 0.0, jtU = 0.0;   // centred OU states and their integrals
    path.x[kMxn][0] = 0.0;
    path.x[kUsd][0] = 0.0;
    path.I[kMxn][0] = 0.0;
    path.I[kUsd][0] = 0.0;
    path.X[0] = g.spot;

    for (int d = 0; d < g.horizon; ++d) {
        double z[5];
        for (double& v : z) v = normal(gen);
        Real w[5];
        for (std::size_t i = 0; i < 5; ++i) {
            Real s = 0.0;
            for (std::size_t k = 0; k <= i; ++k) s += g.chol[i][k] * z[k];
            w[i] = s;
        }
        const std::size_t n = static_cast<std::size_t>(d) + 1;
        jtM += xtM * cm.vStep + w[1];
        jtU += xtU * cu.vStep + w[3];
        xtM = xtM * cm.eStep + w[0];
        xtU = xtU * cu.eStep + w[2];
        path.x[kMxn][n] = xtM + cm.m[n];
        path.x[kUsd][n] = xtU + cu.m[n];
        path.I[kMxn][n] = -cm.lnP0[n] + jtM + cm.mInt[n];
        path.I[kUsd][n] = -cu.lnP0[n] + jtU + cu.mInt[n];
        const Real dlnX = (path.I[kMxn][n] - path.I[kMxn][n - 1]) - (path.I[kUsd][n] - path.I[kUsd][n - 1])
                          + (g.lnq[n - 1] - g.lnq[n]) - 0.5 * g.fxVar * g.dt + w[4];
        path.X[n] = path.X[n - 1] * exp(dlnX);
    }
}

// ---------------------------------------------------------------------------------------------
// Valuation of compiled instruments at (path, day)
// ---------------------------------------------------------------------------------------------

template <class Real>
struct Bonds {
    std::vector<Real> P[2];     // P_c(t, day) per table entry (valid for entries with day >= t)
    void resize(std::size_t n)
    {
        P[0].assign(n, 0.0);
        P[1].assign(n, 0.0);
    }
};

// P_c(t,T) = P_c(0,T)/P_c(0,t) exp(-B x - B^2 y / 2), B = (1 - e^{-a(T-t)}) / a
template <class Real>
void computeBonds(const Context<Real>& c, int d, Real xMxn, Real xUsd, Bonds<Real>& b)
{
    const std::size_t first = indexOf(c.days, d);
    const std::size_t n = c.days.size();
    const std::size_t dd = static_cast<std::size_t>(d);
    for (int k = 0; k < 2; ++k) {
        if (!c.anyNeed[k]) continue;
        const CurrencyGrid<Real>& cg = c.grid.ccy[k];
        const Real invP0d = 1.0 / cg.p0[dd];
        const Real ed = cg.expAt[dd];
        const Real yd = cg.y[dd];
        const Real invA = 1.0 / cg.a;
        const Real x = k == kMxn ? xMxn : xUsd;
        for (std::size_t i = first; i < n; ++i) {
            if (!c.need[k][i]) continue;
            const Real B = (1.0 - c.expAt[k][i] / ed) * invA;
            b.P[k][i] = c.p0[k][i] * invP0d * exp(-B * x - 0.5 * B * B * yd);
        }
    }
}

template <class Real>
struct PathView {
    const Real* I[2];
    Real        X;
};

// A cash flow at `day` is still unpaid at d if it falls strictly after d; today (d = 0) a flow dated
// today, which only an initial exchange can be, belongs to the value (as in the desk's npv).
inline bool unpaid(int day, int d) { return day > d || (d == 0 && day == 0); }

// Discount factor of the leg's discount curve at table entry idx.
template <class Real>
inline Real discountAt(const Leg& L, const Context<Real>& c, const Bonds<Real>& b, std::size_t idx, Real qd)
{
    switch (L.disc) {
        case DiscTiie: return b.P[kMxn][idx];
        case DiscCsa:  return b.P[kMxn][idx] * (c.qAt[idx] / qd);
        default:       return b.P[kUsd][idx];
    }
}

template <class Real>
Real legValue(const Leg& L, const Context<Real>& c, int d, const Bonds<Real>& b, Real qd, const PathView<Real>& pv)
{
    const std::vector<Real>& proj = b.P[L.proj];
    Real v = 0.0;
    for (std::size_t i = 0; i < L.periods.size(); ++i) {
        const LegPeriod& per = L.periods[i];
        if (per.payDay <= d) continue;                            // already paid
        Real fa;                                                  // compounded factor of the period
        if (per.prevDay <= d) {
            const Real a0 = i == 0 ? Real(L.accrued) : Real(1.0);
            fa = a0 * exp(pv.I[L.proj][d] - pv.I[L.proj][std::max(per.prevDay, 0)]);
        } else {
            fa = proj[per.prevIdx];
        }
        const Real pd = discountAt(L, c, b, per.payIdx, qd);
        const Real g = L.disc == DiscCsa ? Real(c.qAt[per.payIdx] / qd) : Real(1.0);
        v += L.floatSign * L.notional * (fa - proj[per.payIdx]) * g
           + L.rateSign * L.notional * L.rate * per.tau * pd;
    }
    if (L.initEx && unpaid(L.startDays, d))
        v += L.exSign * (-L.notional) * discountAt(L, c, b, L.startIdx, qd);
    if (L.finalEx && L.periods.back().payDay > d)
        v += L.exSign * L.notional * discountAt(L, c, b, L.lastIdx, qd);
    return v;
}

template <class Real>
Real setValue(const CompiledSet& set, const Context<Real>& c, int d, const Bonds<Real>& b, Real qd,
              const PathView<Real>& pv)
{
    Real total = 0.0;
    for (const Trade& t : set.trades) {
        Real tv = 0.0;
        for (const Leg& L : t.legs) tv += legValue(L, c, d, b, qd, pv) * (L.toMxn ? pv.X : Real(1.0));
        total += tv;
    }
    return total;
}

// Cash flows paid in (0, d], deflated by D(day), for the martingale statistic (double only).
double paidFlowsDeflated(const CompiledSet& set, int d, const PathData<double>& path, Deflator deflator,
                         const Grid<double>& g)
{
    const auto deflate = [&](int day) {
        const double bank = std::exp(path.I[kMxn][static_cast<std::size_t>(day)]);
        return deflator == Deflator::CollateralAccount ? bank / g.q[static_cast<std::size_t>(day)] : bank;
    };
    double total = 0.0;
    for (const Trade& t : set.trades) {
        for (const Leg& L : t.legs) {
            const double* I = path.I[L.proj].data();
            const auto convert = [&](double amount, int day) {
                return (L.toMxn ? amount * path.X[static_cast<std::size_t>(day)] : amount) / deflate(day);
            };
            for (std::size_t i = 0; i < L.periods.size(); ++i) {
                const LegPeriod& per = L.periods[i];
                if (per.payDay <= 0 || per.payDay > d) continue;
                const double a0 = i == 0 ? L.accrued : 1.0;
                const double factor = a0 * std::exp(I[per.payDay] - I[std::max(per.prevDay, 0)]);
                total += convert(L.floatSign * L.notional * (factor - 1.0)
                                 + L.rateSign * L.notional * L.rate * per.tau, per.payDay);
            }
            if (L.initEx && L.startDays > 0 && L.startDays <= d)
                total += convert(L.exSign * (-L.notional), L.startDays);
            if (L.finalEx && L.periods.back().payDay <= d)
                total += convert(L.exSign * L.notional, L.periods.back().payDay);
        }
    }
    return total;
}

// Runs body(first, last) over [0, nPaths) cut into one contiguous chunk per hardware thread. A path draws its
// normals from its own generator and writes only its own rows, so the result does not depend on the number of
// threads. At most `maxThreads` workers run (all the hardware threads by default). The first exception a worker
// throws is rethrown here once every worker has finished.
template <class Body>
void forEachPathChunk(std::size_t nPaths, Body body, unsigned maxThreads = std::numeric_limits<unsigned>::max())
{
    const std::size_t threads = std::min<std::size_t>(
        {std::max(1u, std::thread::hardware_concurrency()), std::max(1u, maxThreads), nPaths});
    if (threads <= 1) {
        body(std::size_t{0}, nPaths);
        return;
    }
    std::exception_ptr failure;
    std::mutex failureMutex;
    std::vector<std::thread> workers;
    for (std::size_t w = 0; w < threads; ++w)
        workers.emplace_back([&, w] {
            try {
                body(nPaths * w / threads, nPaths * (w + 1) / threads);
            } catch (...) {
                const std::lock_guard<std::mutex> lock(failureMutex);
                if (!failure) failure = std::current_exception();
            }
        });
    for (std::thread& t : workers) t.join();
    if (failure) std::rethrow_exception(failure);
}

} // namespace

namespace detail {

OuMoments ouMoments(double a, double sigma, double mu, double t)
{
    const OuMomentsT<double> m = ouMomentsT(a, sigma, mu, t);
    return {m.y, m.m, m.mInt};
}

std::array<std::array<double, 5>, 5> stepCovariance(const ExposureModel& model, double dt)
{
    return stepCovarianceT(modelOf(model), dt);
}

} // namespace detail

// ---------------------------------------------------------------------------------------------
// ExposureEngine
// ---------------------------------------------------------------------------------------------

ExposureEngine::ExposureEngine(ExposureMarket market, ExposureModel model, SimConfig config)
    : market_(std::move(market)), model_(model), config_(std::move(config))
{
    if (!std::isfinite(market_.spot) || market_.spot <= 0.0)
        throw std::invalid_argument("ExposureEngine: spot must be positive");
    validateModel(model_);
    validateConfig(config_);
}

std::vector<double> ExposureEngine::tradeValuesAtZero(const NettingSetSpec& set) const
{
    const Context<double> c = buildContext(marketOf(market_), modelOf(model_), {set}, 0);
    Bonds<double> bonds;
    bonds.resize(c.days.size());
    computeBonds(c, 0, 0.0, 0.0, bonds);
    const double zero[1] = {0.0};
    const PathView<double> pv{{zero, zero}, market_.spot};
    std::vector<double> out;
    for (const Trade& t : c.sets[0].trades) {
        double tv = 0.0;
        for (const Leg& L : t.legs) tv += legValue(L, c, 0, bonds, 1.0, pv) * (L.toMxn ? pv.X : 1.0);
        out.push_back(tv);
    }
    return out;
}

std::vector<ExposureProfile> ExposureEngine::simulate(const std::vector<NettingSetSpec>& sets) const
{
    std::vector<ExposureProfile> out;
    if (sets.empty()) return out;

    const std::vector<int>& report = config_.reportDays;
    const Context<double> c = buildContext(marketOf(market_), modelOf(model_), sets, report.back());
    const std::size_t nPaths = config_.nPaths;
    const std::size_t nDays = report.size();
    const std::size_t nSets = sets.size();

    // Value of every set on every path at every report day, and the inverse bank account.
    std::vector<std::vector<double>> values(nSets, std::vector<double>(nPaths * nDays));
    std::vector<double> invBank(nPaths * nDays);

    forEachPathChunk(nPaths, [&](std::size_t first, std::size_t last) {
        PathData<double> path;
        path.resize(c.grid.horizon);
        Bonds<double> bonds;
        bonds.resize(c.days.size());
        for (std::size_t p = first; p < last; ++p) {
            simulatePath(c.grid, config_.seed, p, path);
            const PathView<double> pv0{{path.I[kMxn].data(), path.I[kUsd].data()}, 0.0};
            for (std::size_t j = 0; j < nDays; ++j) {
                const int d = report[j];
                const std::size_t dd = static_cast<std::size_t>(d);
                computeBonds(c, d, path.x[kMxn][dd], path.x[kUsd][dd], bonds);
                PathView<double> pv = pv0;
                pv.X = path.X[dd];
                const double qd = c.grid.q[dd];
                for (std::size_t s = 0; s < nSets; ++s)
                    values[s][p * nDays + j] = setValue(c.sets[s], c, d, bonds, qd, pv);
                invBank[p * nDays + j] = std::exp(-path.I[kMxn][dd]);
            }
        }
    });

    // Quantile index: ceil(q n) - 1, clamped, with the same rounding guard as simulateExposure.
    const double scaled = std::round(config_.pfeQuantile * static_cast<double>(nPaths) * 1e9) / 1e9;
    const long long rank = static_cast<long long>(std::ceil(scaled));
    const std::size_t qIdx = static_cast<std::size_t>(
        std::clamp<long long>(rank - 1, 0, static_cast<long long>(nPaths) - 1));

    const double n = static_cast<double>(nPaths);
    std::vector<double> positive(nPaths);
    for (std::size_t s = 0; s < nSets; ++s) {
        ExposureProfile prof;
        prof.days = report;
        prof.times.resize(nDays);
        prof.expectedValue.assign(nDays, 0.0);
        prof.epe.assign(nDays, 0.0);
        prof.ene.assign(nDays, 0.0);
        prof.pfe.assign(nDays, 0.0);
        prof.epeDisc.assign(nDays, 0.0);
        prof.eneDisc.assign(nDays, 0.0);
        prof.pathDiscPos.assign(nPaths * nDays, 0.0);
        prof.pathDiscNeg.assign(nPaths * nDays, 0.0);
        prof.valueAtZero = values[s][0];
        for (std::size_t j = 0; j < nDays; ++j) {
            prof.times[j] = static_cast<double>(report[j]) / kDaysPerYear;
            double sumV = 0.0, sumPos = 0.0, sumNeg = 0.0, sumPosD = 0.0, sumNegD = 0.0;
            for (std::size_t p = 0; p < nPaths; ++p) {
                const double v = values[s][p * nDays + j];
                const double pos = std::max(v, 0.0);
                const double neg = std::max(-v, 0.0);
                const double ib = invBank[p * nDays + j];
                const double posD = pos * ib;
                const double negD = neg * ib;
                prof.pathDiscPos[p * nDays + j] = posD;
                prof.pathDiscNeg[p * nDays + j] = negD;
                positive[p] = pos;
                sumV += v;
                sumPos += pos;
                sumNeg += neg;
                sumPosD += posD;
                sumNegD += negD;
            }
            std::nth_element(positive.begin(), positive.begin() + static_cast<std::ptrdiff_t>(qIdx), positive.end());
            prof.expectedValue[j] = sumV / n;
            prof.epe[j] = sumPos / n;
            prof.ene[j] = sumNeg / n;
            prof.pfe[j] = positive[qIdx];
            prof.epeDisc[j] = sumPosD / n;
            prof.eneDisc[j] = sumNegD / n;
        }
        out.push_back(std::move(prof));
        std::vector<double>().swap(values[s]);   // release before the next set's matrices are allocated
    }
    return out;
}

std::vector<DeflatedStat> ExposureEngine::deflatedValueStats(const NettingSetSpec& set,
                                                             const std::vector<int>& days,
                                                             Deflator deflator) const
{
    if (days.empty()) return {};
    for (int d : days)
        if (d < 0) throw std::invalid_argument("ExposureEngine: deflatedValueStats days must be >= 0");
    const int last = *std::max_element(days.begin(), days.end());
    const Context<double> c = buildContext(marketOf(market_), modelOf(model_), {set}, last);
    const std::size_t nPaths = config_.nPaths;

    std::vector<std::vector<double>> samples(days.size(), std::vector<double>(nPaths));
    PathData<double> path;
    path.resize(c.grid.horizon);
    Bonds<double> bonds;
    bonds.resize(c.days.size());
    for (std::size_t p = 0; p < nPaths; ++p) {
        simulatePath(c.grid, config_.seed, p, path);
        for (std::size_t k = 0; k < days.size(); ++k) {
            const int d = days[k];
            const std::size_t dd = static_cast<std::size_t>(d);
            computeBonds(c, d, path.x[kMxn][dd], path.x[kUsd][dd], bonds);
            const PathView<double> pv{{path.I[kMxn].data(), path.I[kUsd].data()}, path.X[dd]};
            const double value = setValue(c.sets[0], c, d, bonds, c.grid.q[dd], pv);
            const double bank = std::exp(path.I[kMxn][dd]);
            const double deflate = deflator == Deflator::CollateralAccount ? bank / c.grid.q[dd] : bank;
            samples[k][p] = value / deflate + paidFlowsDeflated(c.sets[0], d, path, deflator, c.grid);
        }
    }

    std::vector<DeflatedStat> out;
    const double n = static_cast<double>(nPaths);
    for (const std::vector<double>& s : samples) {
        double mean = 0.0;
        for (double v : s) mean += v;
        mean /= n;
        double ss = 0.0;
        for (double v : s) ss += (v - mean) * (v - mean);
        const double var = nPaths > 1 ? ss / (n - 1.0) : 0.0;
        out.push_back({mean, std::sqrt(var / n)});
    }
    return out;
}

// ---------------------------------------------------------------------------------------------
// XVA
// ---------------------------------------------------------------------------------------------

namespace {

void validateLgd(double lgd, const char* who)
{
    if (!(lgd >= 0.0 && lgd <= 1.0))   // also rejects NaN
        throw std::invalid_argument(std::string("computeXva: ") + who + " LGD must be in [0,1]");
}

// Standard error of the mean of `values` (sample variance; 0 for a single path).
double standardError(const std::vector<double>& values)
{
    const std::size_t n = values.size();
    if (n < 2) return 0.0;
    double mean = 0.0;
    for (double v : values) mean += v;
    mean /= static_cast<double>(n);
    double ss = 0.0;
    for (double v : values) ss += (v - mean) * (v - mean);
    return std::sqrt(ss / (static_cast<double>(n) - 1.0) / static_cast<double>(n));
}

} // namespace

XvaResult computeXva(const ExposureProfile& profile, const ICreditCurve& counterparty, double counterpartyLgd,
                     const ICreditCurve& own, double ownLgd, double fundingSpread)
{
    validateLgd(counterpartyLgd, "counterparty");
    validateLgd(ownLgd, "own");
    if (!std::isfinite(fundingSpread) || fundingSpread < 0.0)
        throw std::invalid_argument("computeXva: funding spread must be finite and >= 0");

    const std::size_t nDays = profile.days.size();
    if (nDays == 0 || profile.times.size() != nDays || profile.epeDisc.size() != nDays ||
        profile.eneDisc.size() != nDays)
        throw std::invalid_argument("computeXva: profile vectors must be non-empty and of equal length");
    if (profile.pathDiscPos.empty() || profile.pathDiscPos.size() != profile.pathDiscNeg.size() ||
        profile.pathDiscPos.size() % nDays != 0)
        throw std::invalid_argument("computeXva: pathDiscPos/pathDiscNeg must be nPaths x nDays");
    if (!(profile.times[0] >= 0.0))
        throw std::invalid_argument("computeXva: profile times must start at >= 0");
    for (std::size_t j = 1; j < nDays; ++j)
        if (!(profile.times[j] > profile.times[j - 1]))
            throw std::invalid_argument("computeXva: profile times must be strictly increasing");

    const std::size_t nPaths = profile.pathDiscPos.size() / nDays;

    // Survival at every date and the default probability of each interval (t_{i-1}, t_i].
    std::vector<double> survC(nDays), survO(nDays);
    for (std::size_t j = 0; j < nDays; ++j) {
        survC[j] = counterparty.survivalProbability(profile.times[j]);
        survO[j] = own.survivalProbability(profile.times[j]);
    }

    XvaResult out{};
    for (std::size_t i = 1; i < nDays; ++i) {
        out.cva += counterpartyLgd * profile.epeDisc[i] * (survC[i - 1] - survC[i]);
        out.dva += ownLgd * profile.eneDisc[i] * (survO[i - 1] - survO[i]);
        out.fva += fundingSpread * (profile.epeDisc[i] - profile.eneDisc[i]) * survC[i] * survO[i] *
                   (profile.times[i] - profile.times[i - 1]);
    }
    out.total = out.cva - out.dva + out.fva;

    // Sampling error: the CVA (DVA) is the mean over paths of the per-path sum of discounted exposure
    // times the default probabilities, so its standard error is that of the per-path sums.
    std::vector<double> cvaPath(nPaths), dvaPath(nPaths);
    for (std::size_t p = 0; p < nPaths; ++p) {
        double c = 0.0, d = 0.0;
        for (std::size_t i = 1; i < nDays; ++i) {
            c += profile.pathDiscPos[p * nDays + i] * (survC[i - 1] - survC[i]);
            d += profile.pathDiscNeg[p * nDays + i] * (survO[i - 1] - survO[i]);
        }
        cvaPath[p] = counterpartyLgd * c;
        dvaPath[p] = ownLgd * d;
    }
    out.cvaStdErr = standardError(cvaPath);
    out.dvaStdErr = standardError(dvaPath);
    return out;
}

#ifdef QF_WITH_XAD

namespace {

using AD = xad::AReal<double, 4>;      // three adjoints (CVA, DVA, FVA); XAD has no N = 3 and the fourth stays free
using ADTape = xad::Tape<double, 4>;

std::atomic<std::size_t> gTapeBytes{0};
std::atomic<std::size_t> gTapeThreads{0};

// A credit curve as piecewise-constant hazards: the only two curve types the AAD understands.
struct Hazards {
    std::vector<double> times;
    std::vector<double> rates;
};

Hazards hazardsOf(const ICreditCurve& curve, int lastDay)
{
    if (const auto* piecewise = dynamic_cast<const PiecewiseHazardCurve*>(&curve))
        return {piecewise->times(), piecewise->hazards()};
    if (const auto* flat = dynamic_cast<const FlatHazardRate*>(&curve))
        return {{std::max(lastDay / kDaysPerYear, 1.0)}, {flat->hazardRate()}};
    throw std::invalid_argument(
        "ExposureEngine::xvaSensitivities: credit curves must be PiecewiseHazardCurve or FlatHazardRate");
}

void requireLinear(const termstructure::YieldCurve& curve, const char* name)
{
    if (curve.interpolationMethod() != math::InterpolationMethod::Linear)
        throw std::invalid_argument(std::string("ExposureEngine::xvaSensitivities: the ") + name +
                                    " curve must use Linear interpolation");
}

} // namespace

XvaSensitivities ExposureEngine::xvaSensitivities(const NettingSetSpec& set, const ICreditCurve& counterparty,
                                                  double counterpartyLgd, const ICreditCurve& own, double ownLgd,
                                                  double fundingSpread, unsigned maxThreads) const
{
    if (maxThreads == 0) throw std::invalid_argument("ExposureEngine::xvaSensitivities: maxThreads must be >= 1");
    validateLgd(counterpartyLgd, "counterparty");
    validateLgd(ownLgd, "own");
    if (!std::isfinite(fundingSpread) || fundingSpread < 0.0)
        throw std::invalid_argument("computeXva: funding spread must be finite and >= 0");
    requireLinear(market_.tiie, "TIIE-F");
    requireLinear(market_.sofr, "SOFR");
    if (market_.mxnUsd) requireLinear(*market_.mxnUsd, "MXN-USD");

    const std::vector<int>& report = config_.reportDays;
    const Hazards hazC = hazardsOf(counterparty, report.back());
    const Hazards hazO = hazardsOf(own, report.back());
    const std::size_t nPaths = config_.nPaths;
    const std::size_t nDays = report.size();

    // The inputs, in one vector: pillars of the three curves, spot, the five model numbers (in XvaGreeks order),
    // hazards of both names, funding spread. The correlations are not inputs.
    std::vector<double> x0;
    const auto append = [&x0](const std::vector<double>& v) {
        const std::size_t offset = x0.size();
        x0.insert(x0.end(), v.begin(), v.end());
        return offset;
    };
    const std::vector<double> noRates;
    const std::size_t oTiie = append(market_.tiie.rates());
    const std::size_t oSofr = append(market_.sofr.rates());
    const std::size_t oMxn = append(market_.mxnUsd ? market_.mxnUsd->rates() : noRates);
    const std::size_t oSpot = append({market_.spot});
    const std::size_t oModel = append({model_.fxVol, model_.sigmaMxn, model_.aMxn, model_.sigmaUsd, model_.aUsd});
    const std::size_t oHazC = append(hazC.rates);
    const std::size_t oHazO = append(hazO.rates);
    const std::size_t oFund = append({fundingSpread});
    const std::size_t nIn = x0.size();
    const std::size_t nTiie = market_.tiie.rates().size(), nSofr = market_.sofr.rates().size();
    const std::size_t nMxn = market_.mxnUsd ? market_.mxnUsd->rates().size() : 0;

    struct Partial {
        std::vector<double> d[3];   // adjoints of CVA, DVA, FVA with respect to the inputs
        std::size_t tapeBytes = 0;
    };
    std::map<std::size_t, Partial> partials;   // by first path, so the final sum does not depend on thread timing
    std::mutex partialsMutex;
    std::vector<double> cvaPath(nPaths), dvaPath(nPaths), fvaPath(nPaths);   // each already divided by nPaths

    forEachPathChunk(nPaths, [&](std::size_t first, std::size_t last) {
        ADTape tape;                                   // one tape per thread; declared first, destroyed last
        std::vector<AD> in(x0.begin(), x0.end());
        tape.registerInputs(in);
        tape.newRecording();
        const auto take = [&in](std::size_t offset, std::size_t count) {
            return std::vector<AD>(in.begin() + static_cast<std::ptrdiff_t>(offset),
                                   in.begin() + static_cast<std::ptrdiff_t>(offset + count));
        };
        const PillarCurve<AD> tiie{market_.tiie.maturities(), take(oTiie, nTiie)};
        const PillarCurve<AD> sofr{market_.sofr.maturities(), take(oSofr, nSofr)};
        PillarCurve<AD> mxnUsd;
        if (nMxn > 0) mxnUsd = PillarCurve<AD>{market_.mxnUsd->maturities(), take(oMxn, nMxn)};
        const MarketT<AD, PillarCurve<AD>> market{&tiie, &sofr, nMxn > 0 ? &mxnUsd : nullptr, in[oSpot]};
        const ModelT<AD> model{in[oModel + 2], in[oModel + 1], in[oModel + 4], in[oModel + 3], in[oModel],
                               model_.rhoMxnUsd, model_.rhoMxnFx, model_.rhoUsdFx};
        const Context<AD> c = buildContext(market, model, {set}, report.back());

        // Weights of each date in the three measures (they already carry the 1 / nPaths of the mean), recorded
        // once. This is computeXva's weighted sum in another order: the sum over dates happens inside each path
        // and the mean over paths last, whereas computeXva averages the dates first. Reusing computeXva would
        // change its double numbers by rounding, so the formula is repeated here on purpose.
        const std::vector<AD> hC = take(oHazC, hazC.rates.size());
        const std::vector<AD> hO = take(oHazO, hazO.rates.size());
        std::vector<AD> survC(nDays), survO(nDays), wC(nDays), wO(nDays), wF(nDays);
        for (std::size_t j = 0; j < nDays; ++j) {
            const double t = report[j] / kDaysPerYear;
            survC[j] = survivalFromHazards(hazC.times, hC, t);
            survO[j] = survivalFromHazards(hazO.times, hO, t);
        }
        const double invN = 1.0 / static_cast<double>(nPaths);
        for (std::size_t j = 1; j < nDays; ++j) {
            wC[j] = counterpartyLgd * (survC[j - 1] - survC[j]) * invN;
            wO[j] = ownLgd * (survO[j - 1] - survO[j]) * invN;
            wF[j] = in[oFund] * survC[j] * survO[j] * (report[j] / kDaysPerYear - report[j - 1] / kDaysPerYear) * invN;
        }
        const auto common = tape.getPosition();        // everything above is shared by the paths of this thread

        // This loop over paths runs parallel to simulate()'s on purpose: sharing it would change the order of
        // operations of simulate(), whose double results must not move.
        std::size_t peakBytes = 0;
        for (std::size_t p = first; p < last; ++p) {
            PathData<AD> path;                         // no active variable may outlive resetTo below
            path.resize(c.grid.horizon);
            Bonds<AD> bonds;
            bonds.resize(c.days.size());
            simulatePath(c.grid, config_.seed, p, path);
            const PathView<AD> pv0{{path.I[kMxn].data(), path.I[kUsd].data()}, AD(0.0)};
            AD cva = 0.0, dva = 0.0, fva = 0.0;
            for (std::size_t j = 1; j < nDays; ++j) {
                const int d = report[j];
                const std::size_t dd = static_cast<std::size_t>(d);
                computeBonds(c, d, path.x[kMxn][dd], path.x[kUsd][dd], bonds);
                PathView<AD> pv = pv0;
                pv.X = path.X[dd];
                const AD v = setValue(c.sets[0], c, d, bonds, c.grid.q[dd], pv);
                const AD invBank = exp(-path.I[kMxn][dd]);
                const AD posD = max(v, 0.0) * invBank, negD = max(-v, 0.0) * invBank;
                cva += posD * wC[j];
                dva += negD * wO[j];
                fva += (posD - negD) * wF[j];
            }
            tape.registerOutput(cva);
            tape.registerOutput(dva);
            tape.registerOutput(fva);
            derivative(cva)[0] = 1.0;
            derivative(dva)[1] = 1.0;
            derivative(fva)[2] = 1.0;
            cvaPath[p] = xad::value(cva);
            dvaPath[p] = xad::value(dva);
            fvaPath[p] = xad::value(fva);
            peakBytes = std::max(peakBytes, tape.getMemory());
            tape.computeAdjointsTo(common);            // down to the shared part, whose adjoints accumulate
            tape.clearDerivativesAfter(common);
            tape.resetTo(common);                      // the tape never grows past one path
        }
        tape.computeAdjoints();                        // from the shared part to the inputs

        Partial out;
        out.tapeBytes = peakBytes;
        for (int k = 0; k < 3; ++k) {
            out.d[k].resize(nIn);
            for (std::size_t i = 0; i < nIn; ++i) out.d[k][i] = derivative(in[i])[static_cast<std::size_t>(k)];
        }
        const std::lock_guard<std::mutex> lock(partialsMutex);
        partials[first] = std::move(out);
    }, maxThreads);

    std::array<std::vector<double>, 3> d;
    for (auto& v : d) v.assign(nIn, 0.0);
    std::size_t tapeBytes = 0;
    for (const auto& entry : partials) {
        for (std::size_t k = 0; k < 3; ++k)
            for (std::size_t i = 0; i < nIn; ++i) d[k][i] += entry.second.d[k][i];
        tapeBytes = std::max(tapeBytes, entry.second.tapeBytes);
    }
    gTapeBytes = tapeBytes;
    gTapeThreads = partials.size();

    XvaSensitivities out{};
    const double n = static_cast<double>(nPaths);
    for (std::size_t p = 0; p < nPaths; ++p) {
        out.value.cva += cvaPath[p];
        out.value.dva += dvaPath[p];
        out.value.fva += fvaPath[p];
    }
    out.value.total = out.value.cva - out.value.dva + out.value.fva;
    out.value.cvaStdErr = n * standardError(cvaPath);   // the paths carry 1/n: the sum of their own is n times larger
    out.value.dvaStdErr = n * standardError(dvaPath);
    XvaGreeks* const greeks[3] = {&out.cva, &out.dva, &out.fva};
    for (std::size_t k = 0; k < 3; ++k) {
        const auto slice = [&](std::size_t offset, std::size_t count) {
            return std::vector<double>(d[k].begin() + static_cast<std::ptrdiff_t>(offset),
                                       d[k].begin() + static_cast<std::ptrdiff_t>(offset + count));
        };
        XvaGreeks& g = *greeks[k];
        g.tiie = slice(oTiie, nTiie);
        g.sofr = slice(oSofr, nSofr);
        g.mxnUsd = slice(oMxn, nMxn);
        g.spot = d[k][oSpot];
        g.fxVol = d[k][oModel];
        g.sigmaMxn = d[k][oModel + 1];
        g.aMxn = d[k][oModel + 2];
        g.sigmaUsd = d[k][oModel + 3];
        g.aUsd = d[k][oModel + 4];
        g.counterpartyHazard = slice(oHazC, hazC.rates.size());
        g.ownHazard = slice(oHazO, hazO.rates.size());
        g.fundingSpread = d[k][oFund];
    }
    return out;
}

namespace detail {
std::size_t aadTapeBytes() { return gTapeBytes; }
std::size_t aadThreads() { return gTapeThreads; }
} // namespace detail

#else

XvaSensitivities ExposureEngine::xvaSensitivities(const NettingSetSpec&, const ICreditCurve&, double,
                                                  const ICreditCurve&, double, double, unsigned) const
{
    throw std::logic_error("ExposureEngine::xvaSensitivities: qf se compiló sin XAD (QF_WITH_XAD=OFF)");
}

namespace detail {
std::size_t aadTapeBytes() { return 0; }
std::size_t aadThreads() { return 0; }
} // namespace detail

#endif

} // namespace qf::xva
