#pragma once
#include <vector>

namespace qf::models {

class IRateModel {
public:
    virtual ~IRateModel() = default;
    virtual double bondPrice(double T) const = 0;
    virtual double zeroRate(double T) const = 0;
    virtual std::vector<double> simulate(double T, int steps, unsigned seed = 42) const = 0;
};

} // namespace qf::models
