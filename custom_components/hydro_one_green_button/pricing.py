"""Ontario time-of-use pricing for Hydro One interval readings."""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from .green_button import IntervalReading

DEFAULT_OFF_PEAK_RATE = 0.091
DEFAULT_MID_PEAK_RATE = 0.146
DEFAULT_ON_PEAK_RATE = 0.189


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    """Return the nth weekday in a month (Monday=0)."""
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (occurrence - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """Return the last weekday in a month."""
    if month == 12:
        first_next = date(year + 1, 1, 1)
    else:
        first_next = date(year, month + 1, 1)
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
    """Ontario TOU holidays: OEB statutory holidays, not the Civic Holiday."""
    easter = _easter_sunday(year)
    return {
        date(year, 1, 1),                         # New Year's Day
        _nth_weekday(year, 2, 0, 3),              # Family Day
        easter - timedelta(days=2),               # Good Friday
        _last_weekday(year, 5, 0),                # Victoria Day
        date(year, 7, 1),                         # Canada Day
        _nth_weekday(year, 9, 0, 1),              # Labour Day
        _nth_weekday(year, 10, 0, 2),             # Thanksgiving
        date(year, 12, 25),                       # Christmas Day
        date(year, 12, 26),                       # Boxing Day
    }


def tou_rate_for_datetime(
    instant: datetime,
    rates: dict[str, float] | None = None,
    time_zone: str = "America/Toronto",
) -> float:
    """Return the Ontario TOU price for an aware instant."""
    if instant.tzinfo is None:
        raise ValueError("TOU pricing requires a timezone-aware datetime")
    prices = rates or {
        "off_peak": DEFAULT_OFF_PEAK_RATE,
        "mid_peak": DEFAULT_MID_PEAK_RATE,
        "on_peak": DEFAULT_ON_PEAK_RATE,
    }
    local = instant.astimezone(ZoneInfo(time_zone))
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
) -> list[dict[str, object]]:
    """Build cumulative CAD cost statistics, grouped into UTC hourly periods.

    Interval energy is apportioned evenly over its duration. This also handles
    intervals that overlap a TOU boundary or a UTC hour boundary.
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
            next_boundary = hour_start + timedelta(hours=1)
            segment_end = min(end, next_boundary)
            seconds = (segment_end - cursor).total_seconds()
            energy = reading.energy_kwh * seconds / reading.duration_seconds
            hourly_costs[hour_start] += energy * tou_rate_for_datetime(
                cursor, rates, time_zone
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
