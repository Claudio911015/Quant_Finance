#include <qf/xva/credit_curve.hpp>
#include <cmath>
#include <stdexcept>

namespace qf::xva {

FlatHazardRate::FlatHazardRate(double lambda) : lambda_(lambda)
{
    if (lambda < 0.0)
        throw std::invalid_argument("FlatHazardRate: lambda must be non-negative");
}

double FlatHazardRate::survivalProbability(double t) const
{
    if (t < 0.0)
        throw std::invalid_argument("FlatHazardRate::survivalProbability: t must be >= 0");
    return std::exp(-lambda_ * t);
}

} // namespace qf::xva
