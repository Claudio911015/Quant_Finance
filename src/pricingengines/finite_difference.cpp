#include <qf/pricingengines/finite_difference.hpp>
#include <qf/pricingengines/detail/env_resolver.hpp>
#include <cmath>
#include <stdexcept>
#include <vector>

namespace qf::pricingengines {

namespace {
    inline double optionIntrinsic(double S, double K, instruments::OptionType type) {
        if (type == instruments::OptionType::Call) return std::max(S - K, 0.0);
        return std::max(K - S, 0.0);
    }
}

static void solveTriangular(std::vector<double>& a,
                            std::vector<double>& b,
                            std::vector<double>& c,
                            std::vector<double>& d,
                            int n)
{
    // Thomas algorithm for tridiagonal system (interior nodes 1..n-1)
    std::vector<double> c_star(n + 1);
    std::vector<double> d_star(n + 1);

    c_star[1] = c[1] / b[1];
    d_star[1] = d[1] / b[1];

    for (int i = 2; i < n; ++i) {
        double m = b[i] - a[i] * c_star[i - 1];
        c_star[i] = c[i] / m;
        d_star[i] = (d[i] - a[i] * d_star[i - 1]) / m;
    }

    d[n - 1] = (d[n - 1] - a[n - 1] * d_star[n - 2]) / (b[n - 1] - a[n - 1] * c_star[n - 2]);
    for (int i = n - 2; i > 0; --i) {
        d[i] = d_star[i] - c_star[i] * d[i + 1];
    }
}

double finiteDifferenceBSPrice(const instruments::OptionParams& params,
                               int nS,
                               int nT,
                               FDMethod method)
{
    if (nS < 5 || nT < 5)
        throw std::invalid_argument("finiteDifferenceBSPrice: nS and nT must be >= 5");

    if (params.spot <= 0.0 || params.strike <= 0.0 || params.maturity <= 0.0 || params.volatility <= 0.0)
        throw std::invalid_argument("finiteDifferenceBSPrice: invalid parameters");

    if (params.exercise != instruments::ExerciseType::European)
        throw std::invalid_argument("finiteDifferenceBSPrice: only European supported");

    const double S0 = params.spot;
    const double K = params.strike;
    const double r = params.riskFreeRate;
    const double q = params.dividendYield;
    const double sigma = params.volatility;
    const double T = params.maturity;
    const bool isCall = (params.type == instruments::OptionType::Call);

    const double Smax = 5.0 * S0;
    const double dS = Smax / nS;
    const double dt = T / nT;

    std::vector<double> v_old(nS + 1), v_new(nS + 1);

    // Terminal condition (payoff at maturity)
    for (int i = 0; i <= nS; ++i) {
        double Si = i * dS;
        v_old[i] = optionIntrinsic(Si, K, params.type);
    }

    // Boundary conditions at time t
    auto boundaryLow = [&](double t) -> double {
        if (isCall) return 0.0;
        return K * std::exp(-r * (T - t));
    };
    auto boundaryHigh = [&](double t) -> double {
        if (isCall) return Smax * std::exp(-q * (T - t)) - K * std::exp(-r * (T - t));
        return 0.0;
    };

    for (int j = nT - 1; j >= 0; --j) {
        double t = j * dt;

        v_new[0]  = boundaryLow(t);
        v_new[nS] = boundaryHigh(t);

        if (method == FDMethod::Explicit) {
            for (int i = 1; i < nS; ++i) {
                double i_d = static_cast<double>(i);
                double a = 0.5 * dt * (sigma*sigma*i_d*i_d - (r - q)*i_d);
                double b = 1.0 - dt * (sigma*sigma*i_d*i_d + r);
                double c = 0.5 * dt * (sigma*sigma*i_d*i_d + (r - q)*i_d);

                v_new[i] = a * v_old[i-1] + b * v_old[i] + c * v_old[i+1];
            }
            std::swap(v_new, v_old);
        }
        else {
            // theta = 1.0 for Implicit, 0.5 for Crank-Nicolson
            double theta = (method == FDMethod::Implicit) ? 1.0 : 0.5;

            std::vector<double> a(nS + 1), b(nS + 1), c(nS + 1), d(nS + 1);
            for (int i = 1; i < nS; ++i) {
                double i_d = static_cast<double>(i);
                double sig2i2 = sigma * sigma * i_d * i_d;
                double rqi = (r - q) * i_d;

                // LHS (implicit side) tridiagonal coefficients
                a[i] = -0.5 * theta * dt * (sig2i2 - rqi);
                b[i] =  1.0 + theta * dt * (sig2i2 + r);
                c[i] = -0.5 * theta * dt * (sig2i2 + rqi);

                if (method == FDMethod::Implicit) {
                    d[i] = v_old[i];
                } else {
                    // RHS (explicit side) for Crank-Nicolson
                    double omt = 1.0 - theta;
                    double ae =  0.5 * omt * dt * (sig2i2 - rqi);
                    double be =  1.0 - omt * dt * (sig2i2 + r);
                    double ce =  0.5 * omt * dt * (sig2i2 + rqi);
                    d[i] = ae * v_old[i-1] + be * v_old[i] + ce * v_old[i+1];
                }
            }

            // Incorporate known boundary values into the RHS
            d[1]      -= a[1] * v_new[0];
            d[nS - 1] -= c[nS - 1] * v_new[nS];

            solveTriangular(a, b, c, d, nS);
            for (int i = 1; i < nS; ++i) v_new[i] = d[i];

            std::swap(v_new, v_old);
        }
    }

    int idx0 = static_cast<int>(S0 / dS);
    if (idx0 < 0) idx0 = 0;
    if (idx0 >= nS) return v_old[nS];
    if (idx0 == 0) return v_old[0];

    double s1 = idx0 * dS;
    double s2 = (idx0 + 1) * dS;
    double w = (S0 - s1) / (s2 - s1);
    return v_old[idx0] * (1.0 - w) + v_old[idx0 + 1] * w;
}

FDMEngine::FDMEngine(instruments::OptionParams params, int nS, int nT, FDMethod method)
    : params_(std::move(params)), nS_(nS), nT_(nT), method_(method) {}

FDMEngine::FDMEngine(instruments::OptionParams params, std::string ticker,
                     int nS, int nT, FDMethod method)
    : params_(std::move(params)), ticker_(std::move(ticker)),
      nS_(nS), nT_(nT), method_(method) {}

double FDMEngine::price(const core::MarketEnvironment& env) const {
    auto p = detail::resolveEquityParams(params_, ticker_, env);
    return finiteDifferenceBSPrice(p, nS_, nT_, method_);
}

} // namespace qf::pricingengines
