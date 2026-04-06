#pragma once
#include <memory>
#include <string>
#include <qf/instruments/instrument.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/termstructure/yieldcurve.hpp>

namespace qf::instruments {

enum class SwapType { Payer, Receiver };
enum class SwapLegType { FixedFloating, FixedFixed, FixedInflation };

class Leg : public Instrument {
public:
    Leg(std::string currency,
        std::string dayCountConvention,
        double notional,
        double maturity,
        double fixedRate = 0.0,
        double spread = 0.0,
        bool floating = false)
        : Instrument(maturity), currency_(std::move(currency)), dayCountConvention_(std::move(dayCountConvention)),
          notional_(notional), fixedRate_(fixedRate), spread_(spread), floating_(floating)
    {
        if (notional_ <= 0.0) throw std::invalid_argument("Leg: notional must be positive");
        if (maturity <= 0.0) throw std::invalid_argument("Leg: maturity must be positive");
    }

    const std::string& currency() const { return currency_; }
    const std::string& dayCountConvention() const { return dayCountConvention_; }
    double notional() const { return notional_; }
    double fixedRate() const { return fixedRate_; }

    double calculatePV(const core::MarketEnvironment& env) const override;

private:
    std::string currency_;
    std::string dayCountConvention_;
    double notional_;
    double fixedRate_;
    double spread_;
    bool floating_;
};

class Swap : public Instrument {
public:
    Swap(Leg payLeg, Leg receiveLeg, SwapLegType type)
        : Instrument(std::max(payLeg.maturity(), receiveLeg.maturity())),
          payLeg_(std::move(payLeg)), receiveLeg_(std::move(receiveLeg)), type_(type)
    {
        if (payLeg_.maturity() <= 0.0 || receiveLeg_.maturity() <= 0.0)
            throw std::invalid_argument("Swap: leg maturities must be positive");
    }

    double npv(const core::MarketEnvironment& env) const {
        return payLeg_.pv(env) - receiveLeg_.pv(env);
    }

    /// Legacy overload for backward-compat
    double npv(const termstructure::YieldCurve& curve) const {
        return npv(core::MarketEnvironment(curve));
    }

    double calculatePV(const core::MarketEnvironment& env) const override {
        return npv(env);
    }

    const Leg& payLeg() const { return payLeg_; }
    const Leg& receiveLeg() const { return receiveLeg_; }
    SwapLegType type() const { return type_; }

private:
    Leg payLeg_;
    Leg receiveLeg_;
    SwapLegType type_;
};

class InterestRateSwap : public Swap {
public:
    InterestRateSwap(double notional, double fixedRate,
                     double maturity, double frequency, SwapType type);

    // Primary API (MarketEnvironment)
    double npv(const core::MarketEnvironment& env) const;
    double annuity(const core::MarketEnvironment& env) const;

    // Legacy overloads (backward-compat)
    double npv(const termstructure::YieldCurve& curve) const;
    double annuity(const termstructure::YieldCurve& curve) const;

    static double parRate(double maturity, double frequency,
                          const core::MarketEnvironment& env);
    static double parRate(double maturity, double frequency,
                          const termstructure::YieldCurve& curve);
    static double annuity(double maturity, double frequency,
                          const core::MarketEnvironment& env);
    static double annuity(double maturity, double frequency,
                          const termstructure::YieldCurve& curve);

private:
    // Only state not derivable from Leg objects
    double frequency_;
    SwapType type_;
};

} // namespace qf::instruments
