#include <qf/math/rootfinding.hpp>
#include <cmath>
#include <stdexcept>

namespace qf::math {

double newtonRaphson(std::function<double(double)> f,
                     std::function<double(double)> df,
                     double x0, double tol, int maxIt)
{
    double x = x0;
    for (int i = 0; i < maxIt; ++i) {
        double fx  = f(x);
        double dfx = df(x);
        if (std::abs(dfx) < 1e-15)
            throw std::runtime_error("Newton-Raphson: zero derivative");
        double dx = fx / dfx;
        x -= dx;
        if (std::abs(dx) < tol)
            return x;
    }
    throw std::runtime_error("Newton-Raphson: did not converge");
}

double brent(std::function<double(double)> f,
             double a, double b, double tol, int maxIt)
{
    double fa = f(a), fb = f(b);
    if (fa * fb > 0.0)
        throw std::invalid_argument("Brent: f(a) and f(b) must have opposite signs");

    if (std::abs(fa) < std::abs(fb)) { std::swap(a, b); std::swap(fa, fb); }

    double c = a, fc = fa;
    double s = 0.0, d = 0.0;
    bool mflag = true;

    for (int i = 0; i < maxIt; ++i) {
        if (std::abs(b - a) < tol)
            return b;

        if (fa != fc && fb != fc) {
            // Inverse quadratic interpolation
            s = a*fb*fc / ((fa-fb)*(fa-fc))
              + b*fa*fc / ((fb-fa)*(fb-fc))
              + c*fa*fb / ((fc-fa)*(fc-fb));
        } else {
            // Secant method
            s = b - fb * (b - a) / (fb - fa);
        }

        // Conditions to fall back to bisection
        double tmp = (3.0*a + b) / 4.0;
        bool cond1 = !((s > std::min(tmp, b) && s < std::max(tmp, b)));
        bool cond2 = mflag  && std::abs(s - b) >= std::abs(b - c) / 2.0;
        bool cond3 = !mflag && std::abs(s - b) >= std::abs(c - d) / 2.0;
        bool cond4 = mflag  && std::abs(b - c) < tol;
        bool cond5 = !mflag && std::abs(c - d) < tol;

        if (cond1 || cond2 || cond3 || cond4 || cond5) {
            s = (a + b) / 2.0;
            mflag = true;
        } else {
            mflag = false;
        }

        double fs = f(s);
        d = c; c = b; fc = fb;

        if (fa * fs < 0.0) { b = s; fb = fs; }
        else               { a = s; fa = fs; }

        if (std::abs(fa) < std::abs(fb)) { std::swap(a, b); std::swap(fa, fb); }
    }
    throw std::runtime_error("Brent: did not converge");
}

} // namespace qf::math
