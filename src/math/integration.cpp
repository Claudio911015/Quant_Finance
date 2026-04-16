#include <qf/math/integration.hpp>
#include <cmath>
#include <stdexcept>
#include <vector>

namespace qf::math {

double simpson(std::function<double(double)> f, double a, double b, int n)
{
    if (n <= 0 || n % 2 != 0)
        throw std::invalid_argument("simpson: n must be a positive even integer");
    if (a >= b)
        throw std::invalid_argument("simpson: a must be less than b");

    double h = (b - a) / n;
    double sum = f(a) + f(b);

    for (int i = 1; i < n; ++i)
        sum += f(a + i * h) * ((i % 2 == 0) ? 2.0 : 4.0);

    return sum * h / 3.0;
}

// Compute Gauss-Legendre nodes and weights on [-1, 1] via Newton iteration
// on Legendre polynomial roots
static void glNodesWeights(int n, std::vector<double>& nodes, std::vector<double>& weights)
{
    nodes.resize(n);
    weights.resize(n);

    for (int i = 0; i < (n + 1) / 2; ++i) {
        // Initial guess (Tricomi approximation)
        double x = std::cos(M_PI * (i + 0.75) / (n + 0.5));

        for (int iter = 0; iter < 100; ++iter) {
            // Evaluate P_n(x) and P_{n-1}(x) via recurrence
            double p0 = 1.0, p1 = x;
            for (int j = 2; j <= n; ++j) {
                double p2 = ((2 * j - 1) * x * p1 - (j - 1) * p0) / j;
                p0 = p1;
                p1 = p2;
            }
            // p1 = P_n(x), p0 = P_{n-1}(x)
            double denom = x * x - 1.0;
            if (std::abs(denom) < 1e-14)
                denom = std::copysign(1e-14, denom);
            double dp = n * (x * p1 - p0) / denom;
            double dx = -p1 / dp;
            x += dx;
            if (std::abs(dx) < 1e-15) break;
        }

        double p0 = 1.0, p1 = x;
        for (int j = 2; j <= n; ++j) {
            double p2 = ((2 * j - 1) * x * p1 - (j - 1) * p0) / j;
            p0 = p1;
            p1 = p2;
        }
        double dp = n * (x * p1 - p0) / (x * x - 1.0);
        double w = 2.0 / ((1.0 - x * x) * dp * dp);

        nodes[i] = -x;
        nodes[n - 1 - i] = x;
        weights[i] = w;
        weights[n - 1 - i] = w;
    }
}

double gaussLegendre(std::function<double(double)> f, double a, double b, int n)
{
    if (n <= 0)
        throw std::invalid_argument("gaussLegendre: n must be positive");
    if (a >= b)
        throw std::invalid_argument("gaussLegendre: a must be less than b");

    std::vector<double> nodes, weights;
    glNodesWeights(n, nodes, weights);

    double mid = 0.5 * (a + b);
    double half = 0.5 * (b - a);
    double sum = 0.0;

    for (int i = 0; i < n; ++i)
        sum += weights[i] * f(mid + half * nodes[i]);

    return half * sum;
}

} // namespace qf::math
