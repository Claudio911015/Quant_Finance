#include <gtest/gtest.h>

#include <cmath>
#include <memory>
#include <string>
#include <vector>

#include <qf/risk/scenario.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/core/imarket_observer.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/interpolation.hpp>
#include <qf/instruments/bond.hpp>
#include <qf/instruments/swap.hpp>
#include <qf/math/daycount.hpp>

using namespace qf::risk;
using qf::core::MarketEnvironment;
using qf::math::InterpolationMethod;
using qf::math::DayCountConvention;
using qf::termstructure::YieldCurve;
using qf::instruments::Bond;
using qf::instruments::Leg;

namespace {

// Upward-sloping curve, Linear interpolation (so single-pillar bumps are local
// and the KRD ladder is additive to the parallel DV01).
YieldCurve linearCurve() {
    return YieldCurve({0.5, 1.0, 2.0, 5.0, 10.0},
                      {0.03, 0.035, 0.04, 0.05, 0.06},
                      InterpolationMethod::Linear);
}

} // namespace

// ═══════════════════════════════════════════════════════════════════════════
// Parallel DV01 — independent analytic cross-check against Bond duration
// ═══════════════════════════════════════════════════════════════════════════

TEST(ScenarioEngine, BondParallelDV01MatchesDurationTimesPrice) {
    auto curve = linearCurve();
    MarketEnvironment env(curve);
    Bond bond(100.0, 0.05, 10, 2.0);   // 5Y semiannual 5% bond

    ScenarioEngine engine;             // "default" curve, 1 bp step
    double dv01 = engine.parallelDV01(bond, env);

    // Under continuous compounding, modified duration = Σ tᵢ·cfᵢ·DF / P, so the
    // dollar value of a 1 bp move is exactly duration·price·1e-4 (to O(h²)).
    double expected = bond.duration(curve) * bond.price(curve) * 1e-4;
    EXPECT_NEAR(dv01, expected, std::abs(expected) * 1e-5);
    EXPECT_GT(dv01, 0.0);              // long bond: PV rises as rates fall
}

// ═══════════════════════════════════════════════════════════════════════════
// Key-rate DV01 ladder — additivity under Linear interpolation
// ═══════════════════════════════════════════════════════════════════════════

TEST(ScenarioEngine, KeyRateLadderSumsToParallelUnderLinear) {
    auto curve = linearCurve();
    MarketEnvironment env(curve);
    Bond bond(100.0, 0.05, 10, 2.0);

    ScenarioEngine engine;
    auto ladder = engine.keyRateDV01s(bond, env);

    // One rung per pillar, maturities aligned to the curve knots.
    ASSERT_EQ(ladder.size(), curve.maturities().size());
    for (std::size_t k = 0; k < ladder.size(); ++k)
        EXPECT_DOUBLE_EQ(ladder[k].maturity, curve.maturities()[k]);

    double sum = 0.0;
    for (const auto& rung : ladder) sum += rung.dv01;

    double parallel = engine.parallelDV01(bond, env);
    // Partition-of-unity of the linear basis ⇒ additive to O(h²).
    EXPECT_NEAR(sum, parallel, std::abs(parallel) * 1e-6);
}

// ═══════════════════════════════════════════════════════════════════════════
// Fixed swap leg DV01 vs closed-form analytic derivative
//
// NOTE: the engine reprices whatever Instrument::pv() returns. For a fixed Leg,
// pv() is the economically correct discounted-coupon-plus-notional value, so a
// closed-form DV01 is a genuine independent cross-check. (An InterestRateSwap is
// deliberately NOT used here: Instrument::pv() on it dispatches to the base
// Swap::npv leg-difference, which mixes notional conventions and is not the
// swap's economic NPV — a pre-existing wart flagged for a separate fix.)
// ═══════════════════════════════════════════════════════════════════════════

TEST(ScenarioEngine, FixedLegDV01MatchesAnalyticDerivative) {
    YieldCurve flat({0.5, 1.0, 2.0, 5.0, 10.0},
                    {0.05, 0.05, 0.05, 0.05, 0.05},
                    InterpolationMethod::Linear);
    MarketEnvironment env(flat);

    const double notional  = 1.0e7;
    const double fixedRate = 0.04;
    const double maturity  = 5.0;
    const double frequency = 2.0;
    // Fixed leg (a single leg IS an Instrument with correct pv()).
    Leg leg("USD", DayCountConvention::ACT_365, notional, maturity,
            fixedRate, /*spread=*/0.0, /*floating=*/false, frequency);

    ScenarioEngine engine;
    double dv01 = engine.parallelDV01(leg, env);

    // Closed-form: pv = Σ N·K·τ·DF(tᵢ) + N·DF(T); the dollar value of a 1 bp rate
    // DOWN move (value rises) is 1e-4·[Σ N·K·τ·tᵢ·DF(tᵢ) + N·T·DF(T)].
    const double dt  = 1.0 / frequency;
    const double tau = qf::math::periodFraction(frequency, DayCountConvention::ACT_365);
    const int    n   = static_cast<int>(std::lround(maturity * frequency));
    double weighted = 0.0;
    for (int i = 1; i <= n; ++i) {
        double t = i * dt;
        weighted += notional * fixedRate * tau * t * flat.discountFactor(t);
    }
    weighted += notional * maturity * flat.discountFactor(maturity);
    double expected = weighted * 1e-4;

    EXPECT_GT(dv01, 0.0);   // long fixed cash flows gain as rates fall
    EXPECT_NEAR(dv01, expected, std::abs(expected) * 1e-4);
}

// ═══════════════════════════════════════════════════════════════════════════
// runScenario — P&L identity, validation, named scenarios
// ═══════════════════════════════════════════════════════════════════════════

TEST(ScenarioEngine, RunScenarioPnLIdentity) {
    auto curve = linearCurve();
    MarketEnvironment env(curve);
    Bond bond(100.0, 0.05, 10, 2.0);

    ScenarioEngine engine;
    std::vector<double> shifts = {10.0, 10.0, 10.0, 10.0, 10.0};  // +10 bp parallel
    auto r = engine.runScenario(bond, env, shifts, "up10bp");

    EXPECT_EQ(r.label, "up10bp");
    EXPECT_DOUBLE_EQ(r.pnl, r.scenarioPV - r.basePV);
    EXPECT_DOUBLE_EQ(r.basePV, bond.pv(env));
    EXPECT_LT(r.pnl, 0.0);   // rates up ⇒ bond PV falls
}

TEST(ScenarioEngine, RunScenarioRejectsSizeMismatch) {
    auto curve = linearCurve();
    MarketEnvironment env(curve);
    Bond bond(100.0, 0.05, 10, 2.0);

    ScenarioEngine engine;
    std::vector<double> wrong = {10.0, 10.0};   // curve has 5 pillars
    EXPECT_THROW(engine.runScenario(bond, env, wrong, "bad"), std::invalid_argument);
}

TEST(ScenarioEngine, SteepenerAndFlattenerHaveOppositePnL) {
    auto curve = linearCurve();
    MarketEnvironment env(curve);
    Bond bond(100.0, 0.05, 20, 2.0);   // 10Y bond: long-end dominated

    ScenarioEngine engine;
    auto steep = engine.steepener(bond, env, 25.0);
    auto flat  = engine.flattener(bond, env, 25.0);

    EXPECT_EQ(steep.label, "steepener");
    EXPECT_EQ(flat.label,  "flattener");
    // Long-end up (steepener) hurts a long bond; long-end down (flattener) helps.
    EXPECT_LT(steep.pnl, 0.0);
    EXPECT_GT(flat.pnl,  0.0);
    EXPECT_LT(steep.pnl * flat.pnl, 0.0);
}

TEST(ScenarioEngine, ParallelShockScalesWithDV01) {
    auto curve = linearCurve();
    MarketEnvironment env(curve);
    Bond bond(100.0, 0.05, 10, 2.0);

    ScenarioEngine engine;
    double dv01 = engine.parallelDV01(bond, env);
    auto shock = engine.parallelShock(bond, env, 100.0);   // +100 bp

    EXPECT_EQ(shock.label, "parallel_shock");
    // +100 bp lowers the bond PV; magnitude far exceeds a single 1 bp move.
    EXPECT_LT(shock.pnl, 0.0);
    EXPECT_GT(std::abs(shock.pnl), std::abs(dv01));
    // ΔPV ≈ −100 · DV01 up to convexity (tolerance covers the second-order term).
    EXPECT_NEAR(shock.pnl, -100.0 * dv01, std::abs(100.0 * dv01) * 0.05);
}

// ═══════════════════════════════════════════════════════════════════════════
// Observer safety — a live subscriber must NOT be notified during a risk run
// ═══════════════════════════════════════════════════════════════════════════

namespace {
class CountingObserver : public qf::core::IMarketObserver {
public:
    int count = 0;
    void onMarketUpdate(const MarketEnvironment&, qf::core::ChangeType,
                        const std::string&) override { ++count; }
};
} // namespace

TEST(ScenarioEngine, DoesNotNotifyLiveObservers) {
    auto curve = linearCurve();
    MarketEnvironment env(curve);
    Bond bond(100.0, 0.05, 10, 2.0);

    auto obs = std::make_shared<CountingObserver>();
    env.subscribe(obs);

    ScenarioEngine engine;
    engine.parallelDV01(bond, env);
    engine.keyRateDV01s(bond, env);
    engine.parallelShock(bond, env, 50.0);

    // No bump touched the live environment, so the observer saw nothing.
    EXPECT_EQ(obs->count, 0);

    // Positive control: the observer is genuinely live and would have fired.
    env.setSpot("XYZ", 100.0);
    EXPECT_EQ(obs->count, 1);
}
