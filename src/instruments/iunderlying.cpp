#include <qf/instruments/iunderlying.hpp>

namespace qf::instruments {

EquityUnderlying::EquityUnderlying(std::string ticker) : ticker_(std::move(ticker)) {}
std::string EquityUnderlying::id() const { return ticker_; }

RateUnderlying::RateUnderlying(std::string curveName) : curveName_(std::move(curveName)) {}
std::string RateUnderlying::id() const { return curveName_; }

} // namespace qf::instruments
