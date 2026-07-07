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

/// @brief The pair of named curves a swap object consumes at pricing time (dual-curve, P5).
///
/// @c discountKey names the curve used to discount cash flows (typically OIS);
/// @c projectionKey names the curve off which floating forwards are implied
/// (typically a term index curve). Both default to @c "default", in which case the
/// object prices exactly as it did before dual-curve support existed — the legacy
/// single-curve replication path runs verbatim, so output is bit-identical.
///
/// When the two keys differ, floating legs are projected off @c projectionKey and
/// discounted off @c discountKey via the explicit dual-curve sum
/// Σ Nᵢ·(P_proj(t_{i-1})/P_proj(tᵢ) − 1 + spread·τᵢ)·P_dis(tᵢ).
struct CurveKeys {
    std::string discountKey  {"default"};
    std::string projectionKey{"default"};

    /// @brief True when discount and projection curves are the same name (single-curve).
    bool keysEqual() const { return discountKey == projectionKey; }
};

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
    /// @param notional   Notional principal (> 0).
    /// @param fixedRate  Fixed coupon rate (annual).
    /// @param maturity   Tenor in fractional years (> 0).
    /// @param frequency  Payment periods per year (> 0).
    /// @param type       Payer (pay fixed) or Receiver (receive fixed).
    /// @param keys       Discount/projection curve keys (default single-curve "default").
    InterestRateSwap(double notional, double fixedRate,
                     double maturity, double frequency, SwapType type,
                     CurveKeys keys = {});

    // Primary API (MarketEnvironment)
    double npv(const core::MarketEnvironment& env) const;
    double annuity(const core::MarketEnvironment& env) const;

    /// @brief Route Instrument::pv() to the economically correct InterestRateSwap::npv.
    ///
    /// Without this override, Instrument::pv() dispatches to Swap::calculatePV →
    /// Swap::npv (a leg-difference that mixes notional conventions and ignores
    /// Payer/Receiver). This override makes the flagship IRS class return its true
    /// economic NPV through the generic Instrument interface (P5a wart fix).
    double calculatePV(const core::MarketEnvironment& env) const override { return npv(env); }

    /// @brief The discount/projection curve keys this swap prices against.
    const CurveKeys& curveKeys() const { return keys_; }

    // Legacy overloads (backward-compat)
    double npv(const termstructure::YieldCurve& curve) const;
    double annuity(const termstructure::YieldCurve& curve) const;

    // Single-curve statics (backward-compat: delegate with equal keys)
    static double parRate(double maturity, double frequency,
                          const core::MarketEnvironment& env);
    static double parRate(double maturity, double frequency,
                          const termstructure::YieldCurve& curve);
    static double annuity(double maturity, double frequency,
                          const core::MarketEnvironment& env);
    static double annuity(double maturity, double frequency,
                          const termstructure::YieldCurve& curve);

    /// @brief Dual-curve par rate: floating PV projected off @p projectionKey,
    ///        discounted off @p discountKey; annuity off @p discountKey.
    /// @note When the two keys are equal this reproduces the single-curve par rate
    ///       (the 1−P(0,T) shortcut is valid only in that case).
    static double parRate(double maturity, double frequency,
                          const core::MarketEnvironment& env,
                          const std::string& discountKey,
                          const std::string& projectionKey);

    /// @brief Dual-curve annuity: Σ τ·P_dis off @p discountKey.
    static double annuity(double maturity, double frequency,
                          const core::MarketEnvironment& env,
                          const std::string& discountKey);

private:
    // Only state not derivable from Leg objects
    double frequency_;
    SwapType type_;
    CurveKeys keys_;
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
    /// @param keys       Discount/projection curve keys (default single-curve "default").
    ScheduledLeg(double fixedRate, bool paysFixed, std::vector<PeriodSpec> schedule,
                 CurveKeys keys = {});

    /// @brief Construct with an explicit spread (for floating legs).
    /// @param fixedRate  Coupon rate (unused for floating legs, set to 0).
    /// @param paysFixed  True = fixed coupon; false = floating.
    /// @param spread     Spread over floating index (used only when paysFixed = false).
    /// @param schedule   Ordered list of periods.
    /// @param keys       Discount/projection curve keys (default single-curve "default").
    ScheduledLeg(double fixedRate, bool paysFixed, double spread, std::vector<PeriodSpec> schedule,
                 CurveKeys keys = {});

    /// @brief Build a fixed leg from payment times. Accrual fractions are computed as
    /// actual year fractions (payTime_i - payTime_{i-1}). For specific DCC, build
    /// PeriodSpec manually.
    static ScheduledLeg makeFixed(double notional, double fixedRate,
                                   const std::vector<double>& paymentTimes,
                                   CurveKeys keys = {});

    /// @brief Build a floating leg from payment times. Accrual fractions are actual
    /// year fractions. For specific DCC, build PeriodSpec manually.
    static ScheduledLeg makeFloating(double notional, double spread,
                                      const std::vector<double>& paymentTimes,
                                      CurveKeys keys = {});

    /// @brief Present value of this leg (fixed: coupons + final notional; floating: replication identity).
    double calculatePV(const core::MarketEnvironment& env) const;

    /// @brief Present value of coupon cash flows only, excluding notional exchange.
    ///
    /// For fixed legs this is N·K·Σ(τᵢ·P(0,tᵢ)); for floating legs it equals
    /// N·(1−P(0,T)) (replication identity, which is already coupon-only).
    double calculateCouponPV(const core::MarketEnvironment& env) const;

    /// @brief The explicit schedule used by this leg.
    const std::vector<PeriodSpec>& schedule() const { return schedule_; }

    double fixedRate()  const { return fixedRate_; }
    double spread()     const { return spread_; }
    bool   paysFixed()  const { return paysFixed_; }

    /// @brief The discount/projection curve keys this leg prices against.
    const CurveKeys& curveKeys() const { return keys_; }
    /// @brief Set the discount/projection curve keys (fluent; returns *this).
    ScheduledLeg& setCurveKeys(CurveKeys keys) { keys_ = std::move(keys); return *this; }

    /// @brief Last payment date in fractional years (used for Instrument maturity).
    double lastPayTime() const { return schedule_.back().payTime; }

private:
    double fixedRate_;
    double spread_{0.0};
    bool paysFixed_;
    std::vector<PeriodSpec> schedule_;
    CurveKeys keys_{};
};

/// @brief A swap built from two explicit ScheduledLeg objects.
///
/// The pay leg is what the portfolio pays; the receive leg is what it receives.
/// Supports any combination of fixed and floating legs, amortizing notionals,
/// and broken periods.
class ScheduledSwap : public Instrument {
public:
    /// @param payLeg      Leg whose cash flows are paid (outflows).
    /// @param receiveLeg  Leg whose cash flows are received (inflows).
    ///
    /// @note The Instrument maturity is the max of both legs' final payment dates,
    ///       since amortizing/stub legs may terminate on different dates (P5b).
    ScheduledSwap(ScheduledLeg payLeg, ScheduledLeg receiveLeg);

    /// @brief Net present value: PV(receive) - PV(pay).
    double npv(const core::MarketEnvironment& env) const;

    /// @brief Route Instrument::pv() to npv() so ScheduledSwap can flow through the
    ///        ScenarioEngine and any polymorphic Instrument consumer (P5b).
    double calculatePV(const core::MarketEnvironment& env) const override { return npv(env); }

    /// @brief Undiscounted net cash flows per unique payment date.
    ///
    /// Returns a vector of (time, net_cashflow) pairs covering all payment
    /// dates from both legs. Dates that appear in only one leg have zero on
    /// the other. Positive values = net receipt; negative = net payment.
    std::vector<std::pair<double, double>> cashFlows(const core::MarketEnvironment& env) const;

    const ScheduledLeg& payLeg()     const { return payLeg_; }
    const ScheduledLeg& receiveLeg() const { return receiveLeg_; }

private:
    ScheduledLeg payLeg_;
    ScheduledLeg receiveLeg_;
};

} // namespace qf::instruments
