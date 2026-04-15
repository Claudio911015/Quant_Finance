#include <qf/math/daycount.hpp>
#include <stdexcept>
#include <cctype>
#include <algorithm>
#include <string>

namespace qf::math {

double periodFraction(double frequency, DayCountConvention dcc)
{
    switch (dcc) {
    case DayCountConvention::ACT_360:
        // Approximate actual days per period as 365/frequency, then divide by 360.
        return 365.0 / (360.0 * frequency);
    case DayCountConvention::ACT_365:
    case DayCountConvention::ACT_ACT_ISDA:
    case DayCountConvention::THIRTY_360:
        // ACT/365: (365/frequency)/365 = 1/frequency.
        // ACT/ACT: approximated as ACT/365 (identical under uniform schedules).
        // 30/360:  30-day months give equal periods: (30*(12/freq))/360 = 1/frequency.
        return 1.0 / frequency;
    }
    // Unreachable — exhaustive switch guards against new unhandled enum values at compile time.
    throw std::logic_error("periodFraction: unhandled DayCountConvention");
}

double yearFraction(int actualDays, DayCountConvention dcc, int daysInYear)
{
    switch (dcc) {
    case DayCountConvention::ACT_360:
        return static_cast<double>(actualDays) / 360.0;
    case DayCountConvention::ACT_365:
        return static_cast<double>(actualDays) / 365.0;
    case DayCountConvention::ACT_ACT_ISDA:
        if (daysInYear <= 0)
            throw std::invalid_argument("yearFraction: daysInYear must be positive");
        return static_cast<double>(actualDays) / static_cast<double>(daysInYear);
    case DayCountConvention::THIRTY_360:
        // Exact 30/360 requires start and end calendar dates (year, month, day)
        // to apply the 30-day-per-month adjustment. Accepting only an actual day
        // count is inherently incorrect for this convention — use periodFraction()
        // with a known frequency instead, or supply real dates.
        throw std::logic_error(
            "yearFraction: THIRTY_360 requires calendar dates (year/month/day). "
            "Use periodFraction(frequency, THIRTY_360) for uniform schedules.");
    }
    throw std::logic_error("yearFraction: unhandled DayCountConvention");
}

DayCountConvention dayCountFromString(std::string_view s)
{
    std::string upper(s);
    std::transform(upper.begin(), upper.end(), upper.begin(),
                   [](unsigned char c) { return static_cast<char>(std::toupper(c)); });

    if (upper == "ACT/360" || upper == "ACTUAL/360")
        return DayCountConvention::ACT_360;
    if (upper == "ACT/365" || upper == "ACTUAL/365" ||
        upper == "ACT/365 FIXED" || upper == "ACTUAL/365 FIXED")
        return DayCountConvention::ACT_365;
    if (upper == "ACT/ACT" || upper == "ACT/ACT ISDA" ||
        upper == "ACTUAL/ACTUAL" || upper == "ACTUAL/ACTUAL ISDA")
        return DayCountConvention::ACT_ACT_ISDA;
    if (upper == "30/360" || upper == "THIRTY/360" ||
        upper == "30E/360" || upper == "BOND BASIS")
        return DayCountConvention::THIRTY_360;

    throw std::invalid_argument(
        std::string("dayCountFromString: unrecognised convention '") + std::string(s) + "'");
}

const char* dayCountName(DayCountConvention dcc)
{
    switch (dcc) {
    case DayCountConvention::ACT_360:       return "ACT/360";
    case DayCountConvention::ACT_365:       return "ACT/365";
    case DayCountConvention::ACT_ACT_ISDA:  return "ACT/ACT ISDA";
    case DayCountConvention::THIRTY_360:    return "30/360";
    }
    throw std::logic_error("dayCountName: unhandled DayCountConvention");
}

} // namespace qf::math
