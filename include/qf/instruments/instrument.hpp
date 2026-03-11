#pragma once

namespace qf::instruments {

class Instrument {
public:
    Instrument() = default;
    explicit Instrument(double maturity) : maturity_(maturity) {}
    ~Instrument() = default;

    double maturity() const { return maturity_; }
    void setMaturity(double m) { maturity_ = m; }

protected:
    double maturity_ = 0.0;
};

} // namespace qf::instruments
