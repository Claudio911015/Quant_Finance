#pragma once

namespace qf::xva {

/// @brief Interface for counterparty credit curves.
/// Implementations return the survival probability SP(t) = P(no default in [0,t]).
class ICreditCurve {
public:
    virtual ~ICreditCurve() = default;
    /// @param t  Time in years (t >= 0).
    /// @return   Survival probability in [0,1].
    virtual double survivalProbability(double t) const = 0;
};

/// @brief Flat (constant) hazard rate credit curve.
/// SP(t) = exp(-lambda * t).
class FlatHazardRate : public ICreditCurve {
public:
    /// @param lambda  Hazard rate in decimal (e.g. 0.02 = 200 bps CDS spread / LGD).
    explicit FlatHazardRate(double lambda);
    double survivalProbability(double t) const override;
private:
    double lambda_;
};

} // namespace qf::xva
