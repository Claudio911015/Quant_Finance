#pragma once
#include <memory>
#include <string>
#include <vector>
#include <qf/instruments/instrument.hpp>
#include <qf/core/market_environment.hpp>
#include <qf/termstructure/yieldcurve.hpp>
#include <qf/math/daycount.hpp>

namespace qf::instruments {

enum class SwapType { Payer, Receiver };
enum class SwapLegType { FixedFloating, FixedFixed, FixedInflation };

class Leg : public Instrument {
public:
    /// @brief Construct a Leg with an explicit day-count convention enum.
    /// @param currency   ISO currency code (e.g. "USD").
    /// @param dcc        Day-count convention (default ACT_365, the historical library default).
    /// @param notional   Notional principal (must be > 0).
    /// @param maturity   Tenor in fractional years (must be > 0).
    /// @param fixedRate  Fixed coupon rate (annual, used only for fixed legs).
    /// @param spread     Spread over floating index (used only for floating legs).
    /// @param floating   True for a floating-rate leg; false for fixed.
    /// @param frequency  Payment periods per year (default 1 = annual).
    Leg(std::string currency,
        math::DayCountConvention dcc,
        double notional,
        double maturity,
        double fixedRate  = 0.0,
        double spread     = 0.0,
        bool   floating   = false,
        double frequency  = 1.0)
        : Instrument(maturity),
          currency_(std::move(currency)),
          dcc_(dcc),
          notional_(notional), fixedRate_(fixedRate),
          spread_(spread), floating_(floating), frequency_(frequency)
    {
        if (notional_ <= 0.0)  throw std::invalid_argument("Leg: notional must be positive");
        if (maturity  <= 0.0)  throw std::invalid_argument("Leg: maturity must be positive");
        if (frequency_ <= 0.0) throw std::invalid_argument("Leg: frequency must be positive");
    }

    /// @brief Backward-compatible constructor that accepts a string convention name.
    /// @throws std::invalid_argument if the string is not recognised.
    Leg(std::string currency,
        std::string_view dccStr,
        double notional,
        double maturity,
        double fixedRate  = 0.0,
        double spread     = 0.0,
        bool   floating   = false,
        double frequency  = 1.0)
        : Leg(std::move(currency),
              math::dayCountFromString(dccStr),
              notional, maturity,
              fixedRate, spread, floating, frequency)
    {}

    const std::string& currency()           const { return currency_; }
    /// @brief Returns the canonical name of the day-count convention (e.g. "ACT/365").
    const char*        dayCountConvention() const { return math::dayCountName(dcc_); }
    /// @brief Returns the day-count convention enum.
    math::DayCountConvention dayCount()     const { return dcc_; }
    double notional()  const { return notional_; }
    double fixedRate() const { return fixedRate_; }
    double frequency() const { return frequency_; }

    double calculatePV(const core::MarketEnvironment& env) const override;

private:
    std::string currency_;
    math::DayCountConvention dcc_;
    double notional_;
    double fixedRate_;
    double spread_;
    bool   floating_;
    double frequency_;
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

// ─── Explicit-schedule swap primitives ───────────────────────────────────────

/// @brief Single coupon period used by ScheduledLeg.
struct PeriodSpec {
    double payTime;      ///< Payment date in fractional years from today.
    double accrualFrac;  ///< Day-count fraction τᵢ for this period (broken periods allowed).
    double notional;     ///< Outstanding notional for this period (enables amortization).
};

/// @brief A swap leg with an explicit payment schedule.
///
/// Supports broken (stub) periods, amortizing notionals, and arbitrary
/// payment dates. Does not modify the existing Leg or InterestRateSwap classes.
class ScheduledLeg {
public:
    /// @brief Construct from an explicit list of periods (fixed or floating).
    /// @param fixedRate  Coupon rate (used only when paysFixed = true).
    /// @param paysFixed  True = fixed coupon; false = floating (replication identity).
    /// @param schedule   Ordered list of periods (payTime must be strictly increasing).
    ScheduledLeg(double fixedRate, bool paysFixed, std::vector<PeriodSpec> schedule);

    /// @brief Construct with an explicit spread (for floating legs).
    /// @param fixedRate  Coupon rate (unused for floating legs, set to 0).
    /// @param paysFixed  True = fixed coupon; false = floating.
    /// @param spread     Spread over floating index (used only when paysFixed = false).
    /// @param schedule   Ordered list of periods.
    ScheduledLeg(double fixedRate, bool paysFixed, double spread, std::vector<PeriodSpec> schedule);

    /// @brief Build a fixed leg from payment times. Accrual fractions are computed as
    /// actual year fractions (payTime_i - payTime_{i-1}). For specific DCC, build
    /// PeriodSpec manually.
    static ScheduledLeg makeFixed(double notional, double fixedRate,
                                   const std::vector<double>& paymentTimes);

    /// @brief Build a floating leg from payment times. Accrual fractions are actual
    /// year fractions. For specific DCC, build PeriodSpec manually.
    static ScheduledLeg makeFloating(double notional, double spread,
                                      const std::vector<double>& paymentTimes);

    /// @brief Present value of this leg.
    double calculatePV(const core::MarketEnvironment& env) const;

    /// @brief The explicit schedule used by this leg.
    const std::vector<PeriodSpec>& schedule() const { return schedule_; }

private:
    double fixedRate_;
    double spread_{0.0};
    bool paysFixed_;
    std::vector<PeriodSpec> schedule_;
};

} // namespace qf::instruments
