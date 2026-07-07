#include <qf/instruments/swap.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/math/daycount.hpp>
#include <cmath>
#include <map>
#include <stdexcept>
#include <vector>

namespace qf::instruments {

/// @brief Sum of discounted period fractions: Σ τ · P(0, i·dt).
///
/// @param maturity   Swap tenor in years.
/// @param frequency  Payment periods per year.
/// @param curve      Discount curve.
/// @param dcc        Day-count convention (determines τ per period; default ACT_365).
static double discountAnnuity(double maturity, double frequency,
                               const termstructure::YieldCurve& curve,
                               math::DayCountConvention dcc = math::DayCountConvention::ACT_365)
{
    double dt  = 1.0 / frequency;                       // calendar step (schedule)
    double tau = math::periodFraction(frequency, dcc);  // accrual fraction per period
    int nPayments = static_cast<int>(maturity * frequency);
    double sum = 0.0;

    for (int i = 1; i <= nPayments; ++i) {
        double t = i * dt;
        sum += tau * curve.discountFactor(t);
    }
    return sum;
}

namespace {

/// Undiscounted coupon cash flow for period @p i of a ScheduledLeg.
///
/// Fixed leg period i:   CF = Nᵢ · K · τᵢ                    (curve-independent)
/// Floating leg period i: CF = Nᵢ · (P_proj(t_{i-1})/P_proj(tᵢ) − 1) + Nᵢ · spread · τᵢ
///   where P_proj is the leg's *projection* curve (env.curve(projectionKey); the same
///   "default" curve when single-curve, so the flow is bit-identical then). The forward
///   accrual P_proj(t_{i-1})/P_proj(tᵢ) − 1 is projected off the index curve; discounting
///   is the caller's responsibility (off the discount curve). Final notional exchange is
///   excluded (coupon only).
double periodCouponCF(const ScheduledLeg& leg, std::size_t i,
                      const core::MarketEnvironment& env)
{
    const auto& sched = leg.schedule();
    const auto& p     = sched[i];
    const double N    = p.notional;
    const double tau  = p.accrualFrac;

    if (leg.paysFixed()) {
        return N * leg.fixedRate() * tau;
    }
    // Floating: forward accrual off the projection curve.
    // P(0,0) = 1 by definition (no curve lookup needed to avoid T=0 rejection).
    const auto& proj  = env.curve(leg.curveKeys().projectionKey);
    const double tPrev = (i == 0) ? 0.0 : sched[i - 1].payTime;
    const double Pprev = (i == 0) ? 1.0 : proj.discountFactor(tPrev);
    const double Pi    = proj.discountFactor(p.payTime);
    const double fwdAccrual = Pprev / Pi - 1.0;
    return N * (fwdAccrual + leg.spread() * tau);
}

} // anonymous namespace

// Leg implementation

double Leg::calculatePV(const core::MarketEnvironment& env) const
{
    const auto& curve = env.curve();
    // dt: uniform time step between payment dates (calendar time, unaffected by DCC).
    // tau: accrual fraction per period — the interest numerator in each payment.
    double dt  = 1.0 / frequency_;
    double tau = math::periodFraction(frequency_, dcc_);
    int    n   = static_cast<int>(std::round(maturity() * frequency_));

    if (floating_) {
        // Floating leg PV = N * (1 - P(0,T)) via the floating-leg replication identity.
        // Spread payments are N * spread * tau at each payment date i*dt.
        double floatPV = notional_ * (1.0 - curve.discountFactor(maturity()));
        for (int i = 1; i <= n; ++i)
            floatPV += notional_ * spread_ * tau * curve.discountFactor(i * dt);
        return floatPV;
    }

    // Fixed leg: N * K * tau at each payment date i*dt, plus notional at maturity.
    double fixedPV = 0.0;
    for (int i = 1; i <= n; ++i)
        fixedPV += notional_ * fixedRate_ * tau * curve.discountFactor(i * dt);
    fixedPV += notional_ * curve.discountFactor(maturity());
    return fixedPV;
}

InterestRateSwap::InterestRateSwap(double notional, double fixedRate,
                                   double maturity, double frequency,
                                   SwapType type, CurveKeys keys)
    : Swap(
          Leg("USD", math::DayCountConvention::ACT_365, notional, maturity, fixedRate, 0.0, false, frequency),
          Leg("USD", math::DayCountConvention::ACT_365, notional, maturity, 0.0,       0.0, true,  frequency),
          SwapLegType::FixedFloating),
      frequency_(frequency), type_(type), keys_(std::move(keys))
{
    if (notional <= 0.0)
        throw std::invalid_argument("InterestRateSwap: notional must be positive");
    if (maturity <= 0.0)
        throw std::invalid_argument("InterestRateSwap: maturity must be positive");
    if (frequency <= 0.0)
        throw std::invalid_argument("InterestRateSwap: frequency must be positive");
}

double InterestRateSwap::annuity(const core::MarketEnvironment& env) const {
    // Fixed-leg annuity always discounts off the discount curve (== "default" when
    // single-curve, so the legacy result is bit-identical).
    return discountAnnuity(maturity(), frequency_, env.curve(keys_.discountKey),
                           payLeg().dayCount());
}

double InterestRateSwap::npv(const core::MarketEnvironment& env) const {
    // Leg::calculatePV for fixed includes the notional repayment while floating
    // uses the replication identity N*(1-P(T)) which excludes it — they cannot
    // be subtracted directly.  Instead we compute coupon streams only:
    //   float (no notional) = N * (1 - P(0,T))           [replication identity]
    //   fixed (no notional) = N * K * discountAnnuity(...)
    // The DCC is read from the payLeg so npv honours the convention stored there.
    const double notional  = payLeg().notional();
    const double fixedRate = payLeg().fixedRate();
    const double mat       = maturity();

    double floatingLeg;
    const auto& discCurve = env.curve(keys_.discountKey);

    if (keys_.keysEqual()) {
        // Single-curve: replication identity runs verbatim ⇒ bit-identical to legacy.
        floatingLeg = notional * (1.0 - discCurve.discountFactor(mat));
    } else {
        // Dual-curve: project forwards off the projection curve, discount off the
        // discount curve — Σ N·(P_proj(t_{i-1})/P_proj(tᵢ) − 1)·P_dis(tᵢ). Spread is
        // zero for a vanilla IRS. When both curves carry the same pillar data this
        // telescopes back to N·(1 − P(0,T)), matching the replication path to ~1e-13.
        const auto& projCurve = env.curve(keys_.projectionKey);
        const double dt = 1.0 / frequency_;
        const int    n  = static_cast<int>(std::round(mat * frequency_));
        floatingLeg = 0.0;
        for (int i = 1; i <= n; ++i) {
            const double t     = i * dt;
            const double tPrev = (i - 1) * dt;
            const double Pprev = (i == 1) ? 1.0 : projCurve.discountFactor(tPrev);
            const double fwd   = Pprev / projCurve.discountFactor(t) - 1.0;
            floatingLeg += notional * fwd * discCurve.discountFactor(t);
        }
    }

    const double fixedLeg  = notional * fixedRate
                           * discountAnnuity(mat, frequency_, discCurve, payLeg().dayCount());
    const double payer_npv = floatingLeg - fixedLeg;
    return (type_ == SwapType::Payer) ? payer_npv : -payer_npv;
}

// Legacy YieldCurve overloads — delegate to MarketEnvironment
double InterestRateSwap::annuity(const termstructure::YieldCurve& curve) const {
    return annuity(core::MarketEnvironment(curve));
}

double InterestRateSwap::npv(const termstructure::YieldCurve& curve) const {
    return npv(core::MarketEnvironment(curve));
}

double InterestRateSwap::parRate(double maturity, double frequency,
                                  const core::MarketEnvironment& env) {
    return parRate(maturity, frequency, env.curve());
}

double InterestRateSwap::parRate(double maturity, double frequency,
                                  const termstructure::YieldCurve& curve) {
    if (maturity <= 0.0 || frequency <= 0.0)
        throw std::invalid_argument("InterestRateSwap::parRate: invalid parameters");
    double dt = 1.0 / frequency;
    int nPayments = static_cast<int>(maturity * frequency);
    double annuitySum = 0.0;
    for (int i = 1; i <= nPayments; ++i)
        annuitySum += dt * curve.discountFactor(i * dt);
    return (1.0 - curve.discountFactor(maturity)) / annuitySum;
}

double InterestRateSwap::annuity(double maturity, double frequency,
                                  const core::MarketEnvironment& env) {
    return discountAnnuity(maturity, frequency, env.curve());
}

double InterestRateSwap::annuity(double maturity, double frequency,
                                  const termstructure::YieldCurve& curve) {
    return discountAnnuity(maturity, frequency, curve);
}

double InterestRateSwap::parRate(double maturity, double frequency,
                                  const core::MarketEnvironment& env,
                                  const std::string& discountKey,
                                  const std::string& projectionKey) {
    if (maturity <= 0.0 || frequency <= 0.0)
        throw std::invalid_argument("InterestRateSwap::parRate: invalid parameters");

    // Single-curve fast path (also the only case where the 1−P(0,T) shortcut is valid).
    if (discountKey == projectionKey)
        return parRate(maturity, frequency, env.curve(discountKey));

    const auto& disc = env.curve(discountKey);
    const auto& proj = env.curve(projectionKey);
    const double dt = 1.0 / frequency;
    const int nPayments = static_cast<int>(maturity * frequency);

    double floatPV    = 0.0;   // Σ fwd_proj · P_dis
    double annuitySum = 0.0;   // Σ dt · P_dis
    for (int i = 1; i <= nPayments; ++i) {
        const double t     = i * dt;
        const double tPrev = (i - 1) * dt;
        const double Pprev = (i == 1) ? 1.0 : proj.discountFactor(tPrev);
        const double fwd   = Pprev / proj.discountFactor(t) - 1.0;
        const double Pdis  = disc.discountFactor(t);
        floatPV    += fwd * Pdis;
        annuitySum += dt * Pdis;
    }
    return floatPV / annuitySum;
}

double InterestRateSwap::annuity(double maturity, double frequency,
                                  const core::MarketEnvironment& env,
                                  const std::string& discountKey) {
    return discountAnnuity(maturity, frequency, env.curve(discountKey));
}

// ─── ScheduledLeg ────────────────────────────────────────────────────────────

ScheduledLeg::ScheduledLeg(double fixedRate, bool paysFixed, std::vector<PeriodSpec> schedule,
                            CurveKeys keys)
    : fixedRate_(fixedRate), paysFixed_(paysFixed), schedule_(std::move(schedule)),
      keys_(std::move(keys))
{
    if (schedule_.empty())
        throw std::invalid_argument("ScheduledLeg: schedule must not be empty");
    for (const auto& p : schedule_)
        if (p.notional <= 0.0)
            throw std::invalid_argument("ScheduledLeg: all notionals must be positive");
    for (std::size_t i = 1; i < schedule_.size(); ++i)
        if (schedule_[i].payTime <= schedule_[i-1].payTime)
            throw std::invalid_argument("ScheduledLeg: payTime must be strictly increasing");
}

ScheduledLeg::ScheduledLeg(double fixedRate, bool paysFixed, double spread,
                            std::vector<PeriodSpec> schedule, CurveKeys keys)
    : fixedRate_(fixedRate), spread_(spread), paysFixed_(paysFixed),
      schedule_(std::move(schedule)), keys_(std::move(keys))
{
    if (schedule_.empty())
        throw std::invalid_argument("ScheduledLeg: schedule must not be empty");
    for (const auto& p : schedule_)
        if (p.notional <= 0.0)
            throw std::invalid_argument("ScheduledLeg: all notionals must be positive");
    for (std::size_t i = 1; i < schedule_.size(); ++i)
        if (schedule_[i].payTime <= schedule_[i-1].payTime)
            throw std::invalid_argument("ScheduledLeg: payTime must be strictly increasing");
}

ScheduledLeg ScheduledLeg::makeFixed(double notional, double fixedRate,
                                      const std::vector<double>& paymentTimes,
                                      CurveKeys keys)
{
    if (paymentTimes.empty())
        throw std::invalid_argument("ScheduledLeg::makeFixed: paymentTimes must not be empty");
    std::vector<PeriodSpec> sched;
    sched.reserve(paymentTimes.size());
    double prevTime = 0.0;
    // accrualFrac = actual elapsed years per period (ACT/ACT simple approximation).
    // Users needing a specific DCC should build PeriodSpec manually.
    for (double t : paymentTimes) {
        double tau = t - prevTime;
        sched.push_back({t, tau, notional});
        prevTime = t;
    }
    return ScheduledLeg(fixedRate, /*paysFixed=*/true, std::move(sched), std::move(keys));
}

ScheduledLeg ScheduledLeg::makeFloating(double notional, double spread,
                                         const std::vector<double>& paymentTimes,
                                         CurveKeys keys)
{
    if (paymentTimes.empty())
        throw std::invalid_argument("ScheduledLeg::makeFloating: paymentTimes must not be empty");
    std::vector<PeriodSpec> sched;
    sched.reserve(paymentTimes.size());
    double prevTime = 0.0;
    // accrualFrac = actual elapsed years per period (ACT/ACT simple approximation).
    for (double t : paymentTimes) {
        double tau = t - prevTime;
        sched.push_back({t, tau, notional});
        prevTime = t;
    }
    return ScheduledLeg(0.0, /*paysFixed=*/false, spread, std::move(sched), std::move(keys));
}

double ScheduledLeg::calculatePV(const core::MarketEnvironment& env) const
{
    // Discounting is always off the discount curve (== "default" when single-curve, so
    // the legacy result is bit-identical).
    const auto& disc = env.curve(keys_.discountKey);
    const std::size_t n = schedule_.size();

    if (paysFixed_) {
        // Fixed leg: coupon cash flows + final notional repayment (projection-independent).
        double pv = 0.0;
        for (const auto& p : schedule_)
            pv += p.notional * fixedRate_ * p.accrualFrac * disc.discountFactor(p.payTime);
        // Final notional exchange at last payment date
        pv += schedule_.back().notional * disc.discountFactor(schedule_.back().payTime);
        return pv;
    }

    if (keys_.keysEqual()) {
        // Single-curve floating leg — generalized replication supporting amortizing
        // notionals (runs verbatim ⇒ bit-identical to legacy):
        //   PV = N_0 - Σᵢ (N_i − N_{i+1}) · P(0,tᵢ) − N_n · P(0,t_n)
        //       + Σᵢ spread · N_i · τᵢ · P(0,tᵢ)
        // For constant N this collapses to the standard: N · (1 − P(0,T)).
        // The initial notional is received at t=0 (no discounting).
        double pv = schedule_[0].notional;  // notional received at t = 0
        for (std::size_t i = 0; i < n; ++i) {
            const auto& p = schedule_[i];
            double nextNotional = (i + 1 < n) ? schedule_[i + 1].notional : 0.0;
            pv -= (p.notional - nextNotional) * disc.discountFactor(p.payTime);
            pv += spread_ * p.notional * p.accrualFrac * disc.discountFactor(p.payTime);
        }
        return pv;
    }

    // Dual-curve floating leg: Σᵢ periodCouponCF(proj) · P_dis(tᵢ). This is the explicit
    // form of the replication above — for equal pillar data it equals the replication
    // path term-for-term (including amortizing notionals), verified to ~1e-13.
    double pv = 0.0;
    for (std::size_t i = 0; i < n; ++i)
        pv += periodCouponCF(*this, i, env) * disc.discountFactor(schedule_[i].payTime);
    return pv;
}

double ScheduledLeg::calculateCouponPV(const core::MarketEnvironment& env) const
{
    if (paysFixed_) {
        // Fixed leg coupon PV: Σ N_i * K * tau_i * P_dis(t_i)  (no final notional)
        const auto& disc = env.curve(keys_.discountKey);
        double pv = 0.0;
        for (const auto& p : schedule_)
            pv += p.notional * fixedRate_ * p.accrualFrac * disc.discountFactor(p.payTime);
        return pv;
    }
    // Floating leg: calculatePV is already coupon-only (no net notional exchange) in both
    // the single-curve and dual-curve paths.
    return calculatePV(env);
}

// ─── ScheduledSwap ───────────────────────────────────────────────────────────

ScheduledSwap::ScheduledSwap(ScheduledLeg payLeg, ScheduledLeg receiveLeg)
    : Instrument(std::max(payLeg.lastPayTime(), receiveLeg.lastPayTime())),
      payLeg_(std::move(payLeg)), receiveLeg_(std::move(receiveLeg))
{}

double ScheduledSwap::npv(const core::MarketEnvironment& env) const
{
    // Use coupon-only PVs (no notional exchange) so that fixed and floating legs
    // are on equal footing. This mirrors the InterestRateSwap::npv() convention:
    //   NPV = PV(receive coupons) - PV(pay coupons)
    // For floating legs, calculateCouponPV() == calculatePV() (replication identity).
    // For fixed legs, calculateCouponPV() strips out the final notional repayment.
    return receiveLeg_.calculateCouponPV(env) - payLeg_.calculateCouponPV(env);
}

std::vector<std::pair<double, double>>
ScheduledSwap::cashFlows(const core::MarketEnvironment& env) const
{
    // Undiscounted coupon cash flows (no notional exchange) netted across both legs.
    // Each leg's floating forwards are projected off *its own* projection curve, so an
    // OIS-only bump leaves the flows unchanged while a projection bump moves them.
    // Positive = net receipt (receive > pay); negative = net payment.
    std::map<double, double> netFlows;

    const auto& paySched = payLeg_.schedule();
    for (std::size_t i = 0; i < paySched.size(); ++i)
        netFlows[paySched[i].payTime] -= periodCouponCF(payLeg_, i, env);

    const auto& recSched = receiveLeg_.schedule();
    for (std::size_t i = 0; i < recSched.size(); ++i)
        netFlows[recSched[i].payTime] += periodCouponCF(receiveLeg_, i, env);

    std::vector<std::pair<double, double>> result;
    result.reserve(netFlows.size());
    for (const auto& [t, cf] : netFlows)
        result.emplace_back(t, cf);
    return result;
}

} // namespace qf::instruments
