#include <qf/pricingengines/finite_difference.hpp>
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
    // Thomas algorithm for tridiagonal system (size n+1, 0..n)
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

    const double Smax = 5.0 * S0;
    const double dS = Smax / nS;
    const double dt = T / nT;

    std::vector<double> v_old(nS + 1), v_new(nS + 1);

    for (int i = 0; i <= nS; ++i) {
        double Si = i * dS;
        v_old[i] = optionIntrinsic(Si, K, params.type);
    }

    for (int j = nT - 1; j >= 0; --j) {
        double t = j * dt;

        if (method == FDMethod::Explicit) {
            v_new[0] = optionIntrinsic(0.0, K, params.type);
            v_new[nS] = optionIntrinsic(Smax, K, params.type) * std::exp(-q * (T - t));

            for (int i = 1; i < nS; ++i) {
                double Si = i * dS;
                double delta = (v_old[i+1] - v_old[i-1]) / (2.0 * dS);
                double gamma = (v_old[i+1] - 2.0*v_old[i] + v_old[i-1]) / (dS*dS);

                double a = 0.5 * dt * (sigma * sigma * i * i - (r - q) * i);
                double b = 1.0 - dt * (sigma * sigma * i * i + r);
                double c = 0.5 * dt * (sigma * sigma * i * i + (r - q) * i);

                v_new[i] = a * v_old[i-1] + b * v_old[i] + c * v_old[i+1];
            }
            std::swap(v_new, v_old);
        }
        else {
            std::vector<double> a(nS + 1), b(nS + 1), c(nS + 1), d(nS + 1);
            for (int i = 1; i < nS; ++i) {
                double i_d = static_cast<double>(i);
                double alpha = 0.5 * dt * (sigma*sigma * i_d * i_d - (r - q) * i_d);
                double beta  = 1.0 + dt * (sigma*sigma * i_d * i_d + r);
                double gamma = -0.5 * dt * (sigma*sigma * i_d * i_d + (r - q) * i_d);

                a[i] = -alpha;
                b[i] = beta;
                c[i] = -gamma;

                if (method == FDMethod::Implicit) {
                    d[i] = v_old[i];
                } else {
                    double alpha_e = -alpha;
                    double beta_e  = 1.0 - dt * (sigma*sigma * i_d * i_d + r);
                    double gamma_e = -gamma;
                    d[i] = alpha_e * v_old[i-1] + beta_e * v_old[i] + gamma_e * v_old[i+1];
                }
            }
            v_new[0] = optionIntrinsic(0.0, K, params.type);
            v_new[nS] = optionIntrinsic(Smax, K, params.type) * std::exp(-q * (T - t));

            solveTriangular(a, b, c, d, nS);
            for (int i = 1; i < nS; ++i) v_new[i] = d[i];

            std::swap(v_new, v_old);
        }
    }

    int idx0 = static_cast<int>(S0 / dS);
    if (idx0 < 0) idx0 = 0;
    if (idx0 > nS) idx0 = nS;

    double s1 = idx0 * dS;
    double s2 = (idx0 + 1) * dS;
    if (idx0 == nS) return v_old[nS];
    if (idx0 == 0) return v_old[0];

    double w = (S0 - s1) / (s2 - s1);
    return v_old[idx0] * (1.0 - w) + v_old[idx0 + 1] * w;
}

} // namespace qf::pricingengines
