#pragma once
#include <string_view>

namespace qf::math {

/// @brief Industry-standard day-count conventions.
enum class DayCountConvention {
    ACT_360,        ///< Actual/360 — money-market instruments (LIBOR, Euribor, OIS)
    ACT_365,        ///< Actual/365 Fixed — GBP, JPY fixed-income; current library default
    ACT_ACT_ISDA,   ///< Actual/Actual (ISDA) — government bond standard
    THIRTY_360,     ///< 30/360 Bond Basis — US and EUR corporate bonds
};

/// @brief Accrual-period fraction τ for a single uniform coupon period.
///
/// Since the library works with fractional years and payment frequency rather
/// than calendar dates, actual days per period are approximated as 365/frequency.
///
/// | Convention   | τ formula                        |
/// |--------------|----------------------------------|
/// | ACT/360      | 365 / (360 × frequency)          |
/// | ACT/365      | 1   / frequency                  |
/// | ACT/ACT ISDA | 1   / frequency  (≈ 365/365/f)  |
/// | 30/360       | 1   / frequency  (30-day months) |
///
/// @param frequency  Coupon periods per year (e.g. 2 = semi-annual, 4 = quarterly).
/// @param dcc        Day-count convention to apply.
/// @return           Accrual fraction τ in years.
[[nodiscard]] double periodFraction(double frequency, DayCountConvention dcc);

/// @brief Year fraction from actual calendar-day counts.
///
/// Use this overload when you have real start/end dates and know the
/// actual number of calendar days in the accrual period.
///
/// For ACT_ACT_ISDA pass the actual days in the relevant calendar year
/// (365 or 366) as @p daysInYear. For all other conventions it is ignored.
///
/// @note THIRTY_360 requires calendar dates (year/month/day) for the
///       30-day-per-month adjustment. Calling this overload with THIRTY_360
///       throws std::logic_error. Use periodFraction() for uniform schedules.
///
/// @param actualDays  Number of calendar days in the accrual period.
/// @param dcc         Day-count convention (THIRTY_360 not supported here).
/// @param daysInYear  Days in the reference year (default 365; only used by ACT_ACT_ISDA).
/// @return            Year fraction τ.
/// @throws std::invalid_argument if daysInYear <= 0 (ACT_ACT_ISDA only).
/// @throws std::logic_error if dcc == THIRTY_360.
double yearFraction(int actualDays, DayCountConvention dcc, int daysInYear = 365);

/// @brief Parse a day-count convention from its canonical string name.
///
/// Recognised strings (case-insensitive):
///   "ACT/360", "ACTUAL/360"
///   "ACT/365", "ACTUAL/365", "ACT/365 FIXED", "ACTUAL/365 FIXED"
///   "ACT/ACT", "ACT/ACT ISDA", "ACTUAL/ACTUAL", "ACTUAL/ACTUAL ISDA"
///   "30/360", "THIRTY/360", "30E/360", "BOND BASIS"
///
/// @throws std::invalid_argument if the string is not recognised.
DayCountConvention dayCountFromString(std::string_view s);

/// @brief Return the canonical name string for a day-count convention.
[[nodiscard]] const char* dayCountName(DayCountConvention dcc);

} // namespace qf::math
