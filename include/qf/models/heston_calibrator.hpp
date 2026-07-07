#pragma once
#include <vector>
#include <qf/instruments/option.hpp>
#include <qf/pricingengines/heston.hpp>

namespace qf::models {

/// A single listed European option quote to calibrate against.
///
/// Flat @c r and @c q live on the owning HestonCalibrator (they are market-wide,
/// not per-quote), so a quote carries only its contract terms and market premium.
struct OptionQuote {
    double strike;                    ///< Strike price.
    double maturity;                  ///< Time to expiry in years.
    instruments::OptionType type;     ///< Call or Put.
    double marketPrice;               ///< Observed (undiscounted) option premium.
};

/// Loss space for the calibration objective.
enum class CalibrationObjective {
    Price,        ///< RMSE of (model − market) premia.
    ImpliedVol    ///< RMSE of (model − market) Black-Scholes implied vols.
};

/// Outcome of a Heston calibration.
struct CalibrationResult {
    pricingengines::HestonParams params;   ///< Fitted parameters (plug into HestonEngine).
    double rmse = 0.0;                      ///< Weighted RMSE in the chosen objective space.
    std::vector<double> perQuoteErrors;     ///< Unweighted (model − market) per quote, chosen space.
    bool   converged = false;               ///< Optimizer convergence flag.
    int    iterations = 0;                  ///< Simplex iterations performed.
};

/// Calibrates Heston parameters to a set of listed European option quotes.
///
/// The Heston stochastic-volatility model exposes five parameters
/// (@c v0, @c kappa, @c theta, @c sigma, @c rho) that must be marked to the
/// vanilla market before the model can price exotics or run risk consistently
/// with listed quotes. This class fits those five scalars by minimizing the
/// pricing error against a chain of quotes, using the semi-analytic
/// pricingengines::hestonPrice under a derivative-free Nelder-Mead search
/// (math::nelderMead).
///
/// **Constraint handling.** The optimizer runs unconstrained in a transformed
/// space: @c v0/kappa/theta/sigma are searched in log-space (guaranteeing
/// positivity) and @c rho through @c tanh (guaranteeing |rho| < 1). Every
/// candidate therefore satisfies the validation guards hestonPrice throws on,
/// and the returned params are always priceable.
///
/// **Feller condition** (@c 2·kappa·theta ≥ sigma²) is deliberately *not*
/// enforced: listed equity smiles routinely calibrate to a violated Feller
/// condition, and forcing it degrades the fit. The semi-analytic price tolerates
/// mild violation.
///
/// Scope: European vanillas on one underlying with flat @c r and @c q. No
/// dividend term structure, no American quotes, no surface object.
class HestonCalibrator {
public:
    /// @param spot Underlying spot price (shared across all quotes).
    /// @param r    Flat continuously-compounded risk-free rate.
    /// @param q    Flat continuous dividend yield (default 0).
    HestonCalibrator(double spot, double r, double q = 0.0);

    /// Fit HestonParams to @p quotes starting from @p initialGuess.
    ///
    /// @param objective    Price-space or implied-vol-space RMSE (default Price).
    /// @param vegaWeighted  In Price space, divide each error by BS vega (per unit
    ///                      vol) to approximate an IV-space fit. Ignored in
    ///                      ImpliedVol space. Default false.
    /// @param tol          Nelder-Mead convergence tolerance.
    /// @param maxIt        Nelder-Mead maximum iterations.
    /// @return Fitted params, weighted RMSE, per-quote errors, convergence flag.
    /// @throws std::invalid_argument if @p quotes is empty.
    CalibrationResult calibrate(
        const std::vector<OptionQuote>& quotes,
        const pricingengines::HestonParams& initialGuess,
        CalibrationObjective objective = CalibrationObjective::Price,
        bool   vegaWeighted = false,
        double tol   = 1e-8,
        int    maxIt = 2000) const;

private:
    double spot_;
    double r_;
    double q_;
};

} // namespace qf::models
