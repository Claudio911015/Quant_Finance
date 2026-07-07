#pragma once
#include <cstddef>
#include <string>
#include <vector>

#include <qf/core/market_environment.hpp>
#include <qf/instruments/instrument.hpp>

namespace qf::risk {

/// @brief One rung of a key-rate DV01 ladder: sensitivity to a single curve pillar.
struct KeyRateDV01 {
    double maturity;  ///< Pillar maturity in years (from the curve's knots).
    double dv01;      ///< Dollar value of a 1 bp bump of this pillar only.
};

/// @brief Outcome of a full-revaluation curve scenario.
struct ScenarioResult {
    std::string label;      ///< Human-readable scenario name (e.g. "steepener").
    double basePV;          ///< PV under the unshocked environment.
    double scenarioPV;      ///< PV under the shocked (bumped-copy) environment.
    double pnl;             ///< scenarioPV − basePV.
};

/// @brief Curve rate-risk engine: parallel DV01, key-rate DV01 ladder, and named
///        curve scenarios for **any** instrument priced via Instrument::pv().
///
/// The engine is curve-name-agnostic: it targets one named curve in the
/// MarketEnvironment (default @c "default"), so when dual-curve support lands it
/// produces per-curve ladders (e.g. OIS delta vs projection delta) without rework.
///
/// **Conventions**
/// - Bump sizes are in **basis points** (1.0 == 1 bp == 1e-4 in the zero rate).
/// - DV01s follow qf::risk::dv01(): a DV01 is the *dollar value of a 1 bp move*,
///   computed by central difference and **positive when PV rises as rates fall**
///   ((pv(down) − pv(up)) / 2). Results are normalised per 1 bp, so they are
///   independent of the finite-difference step chosen.
///
/// **Non-mutating discipline (important):** the engine never mutates the live
/// environment. Every evaluation prices against a *copy* whose observer list has
/// been detached (unsubscribeAll), so Observer-subscribed instruments never see a
/// phantom curve change during a risk run.
///
/// **Quant subtlety:** under CubicSpline interpolation a single-pillar bump is
/// non-local (the spline second-derivative solve couples all knots), so the KRD
/// ladder does not sum exactly to the parallel DV01. Under Linear interpolation the
/// basis functions form a partition of unity, so the ladder sums to the parallel
/// DV01 to O(h²). Additivity acceptance tests therefore use Linear interpolation.
class ScenarioEngine {
public:
    /// @brief Construct an engine targeting a named curve with a bump step in bp.
    /// @param curveName   Curve to shock inside the MarketEnvironment (default "default").
    /// @param bumpSizeBp  Finite-difference step for DV01s, in basis points (default 1 bp).
    explicit ScenarioEngine(std::string curveName = "default",
                            double bumpSizeBp = 1.0);

    /// @brief Dollar value of a 1 bp parallel shift of the whole curve.
    /// @param inst  Instrument to reprice (any Instrument subclass).
    /// @param env   Live market environment (not mutated).
    /// @return      Parallel DV01 (per 1 bp), positive when PV rises as rates fall.
    double parallelDV01(const instruments::Instrument& inst,
                        const core::MarketEnvironment& env) const;

    /// @brief Key-rate DV01 ladder: one rung per curve pillar.
    /// @param inst  Instrument to reprice.
    /// @param env   Live market environment (not mutated).
    /// @return      Vector of {pillar maturity, DV01} aligned to the curve's knots.
    std::vector<KeyRateDV01> keyRateDV01s(const instruments::Instrument& inst,
                                          const core::MarketEnvironment& env) const;

    /// @brief Full revaluation under an arbitrary per-pillar shift (basis points).
    /// @param inst               Instrument to reprice.
    /// @param env                Live market environment (not mutated).
    /// @param perPillarShiftsBp  One shift (bp) per curve pillar; size must match the
    ///                           number of pillars.
    /// @param label              Scenario name recorded in the result.
    /// @return                   basePV, scenarioPV, and P&L.
    /// @throws std::invalid_argument if the shift vector size != pillar count.
    ScenarioResult runScenario(const instruments::Instrument& inst,
                               const core::MarketEnvironment& env,
                               const std::vector<double>& perPillarShiftsBp,
                               const std::string& label = "custom") const;

    /// @brief Convenience: uniform parallel shock of @p magnitudeBp bp on every pillar.
    ScenarioResult parallelShock(const instruments::Instrument& inst,
                                 const core::MarketEnvironment& env,
                                 double magnitudeBp) const;

    /// @brief Convenience: steepener — linear ramp from −mag (short end) to +mag (long end).
    ScenarioResult steepener(const instruments::Instrument& inst,
                             const core::MarketEnvironment& env,
                             double magnitudeBp) const;

    /// @brief Convenience: flattener — linear ramp from +mag (short end) to −mag (long end).
    ScenarioResult flattener(const instruments::Instrument& inst,
                             const core::MarketEnvironment& env,
                             double magnitudeBp) const;

    const std::string& curveName() const { return curveName_; }
    double bumpSizeBp() const { return bumpSizeBp_; }

private:
    std::string curveName_;
    double bumpSizeBp_;
};

} // namespace qf::risk
