#pragma once
#include <cstddef>
#include <vector>
#include <qf/math/interpolation.hpp>

namespace qf::termstructure {

class YieldCurve {
public:
    YieldCurve(std::vector<double> maturities,
               std::vector<double> rates,
               math::InterpolationMethod method = math::InterpolationMethod::CubicSpline);

    // Zero rate for maturity T
    double zeroRate(double T) const;

    // Discount factor: P(0, T) = exp(-r(T) * T)
    double discountFactor(double T) const;

    // Forward rate between T1 and T2
    double forwardRate(double T1, double T2) const;

    // ── Pillar access (P2a): read back the knots the curve was built from ──────

    /// @brief Pillar maturities (years) in strictly increasing order.
    const std::vector<double>& maturities() const { return maturities_; }

    /// @brief Pillar zero rates (continuously compounded, decimal) aligned to maturities().
    const std::vector<double>& rates() const { return rates_; }

    /// @brief Interpolation method the curve was constructed with.
    math::InterpolationMethod interpolationMethod() const { return method_; }

    // ── Bump construction (P2a): non-mutating what-if curves for rate risk ─────
    //
    // Bump sizes are in **basis points**: 1.0 == 1 bp == 1e-4 in the zero rate.
    // The interpolation method is preserved. These are the building blocks for
    // the qf::risk ScenarioEngine (parallel DV01, key-rate DV01, curve scenarios).

    /// @brief Return a copy of this curve with every pillar rate shifted by @p bpShift bp.
    /// @param bpShift  Parallel shift in basis points (may be negative).
    /// @return         A new YieldCurve; this curve is left unchanged.
    YieldCurve parallelBump(double bpShift) const;

    /// @brief Return a copy of this curve with a single pillar rate shifted by @p bpShift bp.
    /// @param pillarIndex  Index into maturities()/rates() to bump.
    /// @param bpShift      Shift in basis points applied to that pillar only (may be negative).
    /// @return             A new YieldCurve; this curve is left unchanged.
    /// @throws std::out_of_range if @p pillarIndex is not a valid pillar.
    YieldCurve bumped(std::size_t pillarIndex, double bpShift) const;

private:
    std::vector<double> maturities_;
    std::vector<double> rates_;
    math::InterpolationMethod method_;
    math::Interpolator interp_;
};

} // namespace qf::termstructure
