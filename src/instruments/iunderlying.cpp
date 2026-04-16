#include <qf/instruments/iunderlying.hpp>

namespace qf::instruments {

EquityUnderlying::EquityUnderlying(std::string ticker) : ticker_(std::move(ticker)) {}
std::string EquityUnderlying::id() const { return ticker_; }

RateUnderlying::RateUnderlying(std::string curveName) : curveName_(std::move(curveName)) {}
std::string RateUnderlying::id() const { return curveName_; }

FxUnderlying::FxUnderlying(std::string pair) : pair_(std::move(pair)) {}
std::string FxUnderlying::id() const { return pair_; }

CommodityUnderlying::CommodityUnderlying(std::string code) : code_(std::move(code)) {}
std::string CommodityUnderlying::id() const { return code_; }

} // namespace qf::instruments
