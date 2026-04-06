#pragma once
#include <string>

namespace qf::instruments {

/// Abstract underlying asset — key for MarketEnvironment lookup.
class IUnderlying {
public:
    virtual ~IUnderlying() = default;
    virtual std::string id() const = 0;
};

class EquityUnderlying : public IUnderlying {
public:
    explicit EquityUnderlying(std::string ticker);
    std::string id() const override;
private:
    std::string ticker_;
};

class RateUnderlying : public IUnderlying {
public:
    explicit RateUnderlying(std::string curveName);
    std::string id() const override;
private:
    std::string curveName_;
};

} // namespace qf::instruments
