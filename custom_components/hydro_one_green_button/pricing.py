"""Ontario time-of-use pricing for Hydro One interval readings."""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from .green_button import IntervalReading

DEFAULT_OFF_PEAK_RATE = 0.091
DEFAULT_MID_PEAK_RATE = 0.146
DEFAULT_ON_PEAK_RATE = 0.189
DEFAULT_RATE_EFFECTIVE_DATE = date(2026, 11, 1)

# Ontario Energy Board Regulated Price Plan TOU prices, in CAD/kWh.
# Each set takes effect on November 1 and remains in force until the next
# November 1 price change.
HISTORICAL_RATE_SCHEDULE: tuple[tuple[date, dict[str, float]], ...] = (
    (date(2022, 11, 1), {"off_peak": 0.074, "mid_peak": 0.102, "on_peak": 0.151}),
    (date(2023, 11, 1), {"off_peak": 0.087, "mid_peak": 0.122, "on_peak": 0.182}),
    (date(2024, 11, 1), {"off_peak": 0.076, "mid_peak": 0.122, "on_peak": 0.158}),
    (date(2025, 11, 1), {"off_peak": 0.098, "mid_peak": 0.157, "on_peak": 0.203}),
    (date(2026, 11, 1), {"off_peak": 0.091, "mid_peak": 0.146, "on_peak": 0.189}),
)


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    """Return the nth weekday in a month (Monday=0)."""
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (occurrence - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """Return the last weekday in a month."""
    first_next = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    last = first_next - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _easter_sunday(year: int) -> date:
    """Calculate Gregorian Easter Sunday."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def ontario_tou_holidays(year: int) -> set[date]:
    """Ontario TOU holidays used by the OEB; Civic Holiday is not included."""
    easter = _easter_sunday(year)
    return {
        date(year, 1, 1),
        _nth_weekday(year, 2, 0, 3),
        easter - timedelta(days=2),
        _last_weekday(year, 5, 0),
        date(year, 7, 1),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 10, 0, 2),
        date(year, 12, 25),
        date(year, 12, 26),
    }


def _rates_for_date(
    local_date: date,
    rates: dict[str, float] | None,
    rate_effective_date: date,
) -> dict[str, float]:
    """Select the latest OEB rate set effective on or before a local date.

    The configurable rates replace the schedule entry on rate_effective_date.
    Dates earlier than the first bundled schedule use the earliest bundled
    rates rather than incorrectly applying today's prices to old readings.
    """
    configured_rates = rates or {
        "off_peak": DEFAULT_OFF_PEAK_RATE,
        "mid_peak": DEFAULT_MID_PEAK_RATE,
        "on_peak": DEFAULT_ON_PEAK_RATE,
    }
    schedule = dict(HISTORICAL_RATE_SCHEDULE)
    schedule[rate_effective_date] = {
        key: float(value) for key, value in configured_rates.items()
    }
    effective_dates = sorted(schedule)
    selected = schedule[effective_dates[0]]
    for effective in effective_dates:
        if effective > local_date:
            break
        selected = schedule[effective]
    return selected


def tou_rate_for_datetime(
    instant: datetime,
    rates: dict[str, float] | None = None,
    time_zone: str = "America/Toronto",
    rate_effective_date: date = DEFAULT_RATE_EFFECTIVE_DATE,
) -> float:
    """Return the Ontario TOU price for an aware instant."""
    if instant.tzinfo is None:
        raise ValueError("TOU pricing requires a timezone-aware datetime")
    local = instant.astimezone(ZoneInfo(time_zone))
    prices = _rates_for_date(local.date(), rates, rate_effective_date)
    if local.weekday() >= 5 or local.date() in ontario_tou_holidays(local.year):
        return float(prices["off_peak"])

    hour = local.hour
    winter = local.month <= 4 or local.month >= 11
    if 7 <= hour < 11:
        period = "on_peak" if winter else "mid_peak"
    elif 11 <= hour < 17:
        period = "mid_peak" if winter else "on_peak"
    elif 17 <= hour < 19:
        period = "on_peak" if winter else "mid_peak"
    else:
        period = "off_peak"
    return float(prices[period])


def build_cost_statistics(
    readings: tuple[IntervalReading, ...],
    rates: dict[str, float] | None = None,
    time_zone: str = "America/Toronto",
    rate_effective_date: date = DEFAULT_RATE_EFFECTIVE_DATE,
) -> list[dict[str, object]]:
    """Build cumulative CAD cost statistics grouped into UTC hourly periods.

    Energy is apportioned evenly across each interval. Ontario's TOU boundaries
    occur on local whole hours, which align with UTC hour boundaries.
    """
    if not readings:
        return []

    hourly_costs: dict[datetime, float] = defaultdict(float)
    for reading in readings:
        start = reading.start.astimezone(UTC)
        end = start + timedelta(seconds=reading.duration_seconds)
        cursor = start
        while cursor < end:
            hour_start = cursor.replace(minute=0, second=0, microsecond=0)
            segment_end = min(end, hour_start + timedelta(hours=1))
            seconds = (segment_end - cursor).total_seconds()
            energy = reading.energy_kwh * seconds / reading.duration_seconds
            hourly_costs[hour_start] += energy * tou_rate_for_datetime(
                cursor, rates, time_zone, rate_effective_date
            )
            cursor = segment_end

    first_hour = min(hourly_costs)
    cumulative_cost = 0.0
    statistics: list[dict[str, object]] = [{
        "start": first_hour,
        "state": cumulative_cost,
        "sum": cumulative_cost,
    }]
    for hour_start in sorted(hourly_costs):
        cumulative_cost = round(cumulative_cost + hourly_costs[hour_start], 6)
        statistics.append({
            "start": hour_start + timedelta(hours=1),
            "state": cumulative_cost,
            "sum": cumulative_cost,
        })
    return statistics
