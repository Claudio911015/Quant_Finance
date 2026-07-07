#pragma once
#include <functional>
#include <vector>

namespace qf::math {

/// Result of a multi-dimensional minimization.
struct OptimResult {
    std::vector<double> x;    ///< Argmin (best vertex found).
    double fmin = 0.0;        ///< Objective value at @ref x.
    int    iterations = 0;    ///< Simplex iterations performed.
    bool   converged = false; ///< True if the tolerance was met before @c maxIt.
};

/// Derivative-free downhill-simplex minimization (Nelder & Mead, 1965).
///
/// Minimizes an arbitrary scalar objective @p f over an unconstrained vector
/// argument, using only function evaluations — no gradient required. This is
/// the N-dimensional counterpart to the 1-D solvers in rootfinding.hpp and is
/// the workhorse behind multi-parameter model calibration (e.g. Heston).
///
/// The initial simplex is @p x0 plus one extra vertex per dimension, each
/// offset by @p initialStep (relative to the coordinate when it is non-zero,
/// absolute otherwise). Textbook coefficients are used: reflection α=1,
/// expansion γ=2, contraction ρ=0.5, shrink σ=0.5.
///
/// Convergence is declared when the relative spread of objective values across
/// the simplex, @c 2·|f_hi − f_lo| / (|f_hi| + |f_lo| + eps), drops below
/// @p tol. If @p maxIt iterations are exhausted first, the best vertex is still
/// returned with @c converged == false.
///
/// @param f           Objective to minimize.
/// @param x0          Starting point (its length defines the dimensionality).
/// @param tol         Relative convergence tolerance on the objective spread.
/// @param maxIt       Maximum simplex iterations.
/// @param initialStep Simplex construction step (see above).
/// @throws std::invalid_argument if @p x0 is empty.
OptimResult nelderMead(std::function<double(const std::vector<double>&)> f,
                       const std::vector<double>& x0,
                       double tol         = 1e-8,
                       int    maxIt       = 2000,
                       double initialStep = 0.05);

} // namespace qf::math
