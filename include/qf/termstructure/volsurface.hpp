#pragma once
#include <cstddef>
#include <vector>
#include <qf/math/interpolation.hpp>

// Forward declaration: fromQuotes() reuses P3's quote type verbatim, but the
// header only needs it as an incomplete type in a by-reference signature, so we
// avoid pulling the whole pricingengines/models stack into this term-structure
// header. The full definition is included in volsurface.cpp.
namespace qf::models { struct OptionQuote; }

namespace qf::termstructure {

/// @brief Per-ticker implied-volatility surface: vol as a function of strike and maturity.
///
/// Replaces the single flat vol per ticker that MarketEnvironment carried before P4.
/// The surface is stored as a grid of maturity pillars × strike pillars of implied
/// vols. Lookups are calendar-consistent:
///
///  1. **Strike (smile):** interpolate each maturity pillar's smile in strike using
///     qf::math::Interpolator (linear or cubic, flat extrapolation beyond the pillars).
///  2. **Maturity (term structure):** convert the per-pillar smile vols at the requested
///     strike to **total variance** w = σ²·T and interpolate w **linearly in T** (flat
///     extrapolation on w), returning σ = √(w(T)/T).
///
/// Interpolating in total variance rather than raw vol is the standard choice that avoids
/// the calendar-arbitrage artifacts of interpolating vols directly, so an interpolated
/// mid-curve mark is auditable.
///
/// **Scope (deliberately excluded, mirroring the P3 calibration scope note):** SVI /
/// parametric fits, dividend term structures, local vol / Dupire, American
/// de-Americanization. This is a marking object built from a European vanilla chain.
class VolSurface {
public:
    /// @brief Build directly from a grid of implied vols.
    /// @param maturities  Maturity pillars (years), strictly increasing, size ≥ 2.
    /// @param strikes     Strike pillars, strictly increasing, size ≥ 2.
    /// @param vols        vols[i][j] = implied vol at maturities[i] × strikes[j] (decimal).
    /// @param strikeMethod Interpolation across strike per smile (default Linear).
    /// @throws std::invalid_argument if dimensions mismatch, pillars are not strictly
    ///         increasing, any vol is non-positive, or total variance σ²·T is decreasing
    ///         in T at any fixed strike (a calendar-arbitrage guard).
    VolSurface(std::vector<double> maturities,
               std::vector<double> strikes,
               std::vector<std::vector<double>> vols,
               math::InterpolationMethod strikeMethod = math::InterpolationMethod::Linear);

    /// @brief Build a surface from a listed European option chain by inverting each quote.
    ///
    /// Each quote is inverted to a Black-Scholes implied vol with the existing Brent
    /// impliedVolatility, then laid on the grid of distinct strikes × maturities present
    /// in @p quotes. The quotes must form a **complete rectangular grid**: every
    /// strike×maturity cell present exactly once.
    ///
    /// @param spot   Underlying spot (shared across quotes).
    /// @param r      Flat continuously-compounded risk-free rate.
    /// @param q      Flat continuous dividend yield.
    /// @param quotes European vanilla quotes forming a full strike×maturity grid.
    /// @param strikeMethod Interpolation across strike per smile (default Linear).
    /// @throws std::invalid_argument if @p quotes is empty, does not form a complete
    ///         rectangular grid, or any quote is not invertible / yields a bad surface.
    static VolSurface fromQuotes(double spot, double r, double q,
                                 const std::vector<models::OptionQuote>& quotes,
                                 math::InterpolationMethod strikeMethod
                                     = math::InterpolationMethod::Linear);

    /// @brief Implied vol at an arbitrary (strike, maturity).
    /// @param strike    Strike to mark (extrapolated flat beyond the strike pillars).
    /// @param maturity  Maturity in years, must be positive.
    /// @return          Implied vol (decimal), calendar-consistent via total-variance interp.
    /// @throws std::invalid_argument if @p maturity is not positive.
    double vol(double strike, double maturity) const;

    /// @brief Maturity pillars (years), strictly increasing.
    const std::vector<double>& maturities() const { return maturities_; }
    /// @brief Strike pillars, strictly increasing.
    const std::vector<double>& strikes() const { return strikes_; }
    /// @brief Grid of implied vols, vols()[i][j] at maturities()[i] × strikes()[j].
    const std::vector<std::vector<double>>& vols() const { return vols_; }
    /// @brief Interpolation method used across strike per smile.
    math::InterpolationMethod strikeMethod() const { return strikeMethod_; }

private:
    void validate() const;
    void buildSmiles();

    std::vector<double> maturities_;
    std::vector<double> strikes_;
    std::vector<std::vector<double>> vols_;
    math::InterpolationMethod strikeMethod_;
    std::vector<math::Interpolator> smiles_;  // one strike-interpolant per maturity pillar
};

} // namespace qf::termstructure
