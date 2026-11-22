"""Ontario TOU, ULO and residential Tiered electricity pricing."""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from .green_button import IntervalReading

PLAN_TOU = "tou"
PLAN_ULO = "ulo"
PLAN_TIERED = "tiered"
DEFAULT_PRICING_PLAN = PLAN_TOU
DEFAULT_RATE_EFFECTIVE_DATE = date(2026, 11, 1)

# Rates are CAD/kWh. OEB historical schedules; effective dates are November 1
# except the initial ULO launch in May 2023.
TOU_RATE_SCHEDULE = (
    (date(2022, 11, 1), {"off_peak": .074, "mid_peak": .102, "on_peak": .151}),
    (date(2023, 11, 1), {"off_peak": .087, "mid_peak": .122, "on_peak": .182}),
    (date(2024, 11, 1), {"off_peak": .076, "mid_peak": .122, "on_peak": .158}),
    (date(2025, 11, 1), {"off_peak": .098, "mid_peak": .157, "on_peak": .203}),
    (date(2026, 11, 1), {"off_peak": .091, "mid_peak": .146, "on_peak": .189}),
)
ULO_RATE_SCHEDULE = (
    (date(2023, 5, 1), {"overnight": .024, "weekend_off_peak": .074, "mid_peak": .102, "on_peak": .240}),
    (date(2023, 11, 1), {"overnight": .028, "weekend_off_peak": .087, "mid_peak": .122, "on_peak": .286}),
    (date(2024, 11, 1), {"overnight": .028, "weekend_off_peak": .076, "mid_peak": .122, "on_peak": .284}),
    (date(2025, 11, 1), {"overnight": .039, "weekend_off_peak": .098, "mid_peak": .157, "on_peak": .391}),
    (date(2026, 11, 1), {"overnight": .037, "weekend_off_peak": .091, "mid_peak": .146, "on_peak": .377}),
)
TIERED_RATE_SCHEDULE = (
    (date(2022, 11, 1), {"tier1": .087, "tier2": .103}),
    (date(2023, 11, 1), {"tier1": .103, "tier2": .125}),
    (date(2024, 11, 1), {"tier1": .093, "tier2": .110}),
    (date(2025, 11, 1), {"tier1": .120, "tier2": .142}),
    (date(2026, 11, 1), {"tier1": .112, "tier2": .132}),
)

DEFAULT_TOU_RATES = {"off_peak": .091, "mid_peak": .146, "on_peak": .189}
DEFAULT_ULO_RATES = {"overnight": .037, "weekend_off_peak": .091, "mid_peak": .146, "on_peak": .377}
DEFAULT_TIERED_RATES = {"tier1": .112, "tier2": .132}


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (occurrence - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    first_next = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    last = first_next - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _easter_sunday(year: int) -> date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def ontario_tou_holidays(year: int) -> set[date]:
    """Ontario OEB TOU/ULO holidays, including Civic Holiday."""
    easter = _easter_sunday(year)
    return {
        date(year, 1, 1), _nth_weekday(year, 2, 0, 3),
        easter - timedelta(days=2), _last_weekday(year, 5, 0),
        date(year, 7, 1), _nth_weekday(year, 8, 0, 1),
        _nth_weekday(year, 9, 0, 1), _nth_weekday(year, 10, 0, 2),
        date(year, 12, 25), date(year, 12, 26),
    }


def _scheduled_rates(local_date: date, schedule, configured: dict[str, float] | None,
                     effective_date: date) -> dict[str, float]:
    entries = dict(schedule)
    if configured:
        entries[effective_date] = {key: float(value) for key, value in configured.items()}
    selected_date = min(entries)
    for effective in sorted(entries):
        if effective > local_date:
            break
        selected_date = effective
    return entries[selected_date]


def tou_rate_for_datetime(instant: datetime, rates: dict[str, float] | None = None,
                          time_zone: str = "America/Toronto",
                          rate_effective_date: date = DEFAULT_RATE_EFFECTIVE_DATE) -> float:
    if instant.tzinfo is None:
        raise ValueError("Pricing requires a timezone-aware datetime")
    local = instant.astimezone(ZoneInfo(time_zone))
    prices = _scheduled_rates(local.date(), TOU_RATE_SCHEDULE, rates, rate_effective_date)
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


def ulo_rate_for_datetime(instant: datetime, rates: dict[str, float] | None = None,
                          time_zone: str = "America/Toronto",
                          rate_effective_date: date = DEFAULT_RATE_EFFECTIVE_DATE) -> float:
    if instant.tzinfo is None:
        raise ValueError("Pricing requires a timezone-aware datetime")
    local = instant.astimezone(ZoneInfo(time_zone))
    prices = _scheduled_rates(local.date(), ULO_RATE_SCHEDULE, rates, rate_effective_date)
    if local.hour >= 23 or local.hour < 7:
        return float(prices["overnight"])
    if local.weekday() >= 5 or local.date() in ontario_tou_holidays(local.year):
        return float(prices["weekend_off_peak"])
    if 16 <= local.hour < 21:
        return float(prices["on_peak"])
    return float(prices["mid_peak"])


def tiered_threshold(local_date: date) -> float:
    """Residential monthly Tier 1 threshold, kWh."""
    return 1000.0 if local_date.month >= 11 or local_date.month <= 4 else 600.0


def _tiered_prices(local_date: date, rates: dict[str, float] | None,
                   rate_effective_date: date) -> dict[str, float]:
    return _scheduled_rates(local_date, TIERED_RATE_SCHEDULE, rates, rate_effective_date)


def _build_tiered_costs(readings, rates, time_zone, rate_effective_date):
    """Price chronologically against each calendar month's residential threshold."""
    zone = ZoneInfo(time_zone)
    monthly_usage: dict[tuple[int, int], float] = defaultdict(float)
    hourly_costs: dict[datetime, float] = defaultdict(float)
    for reading in sorted(readings, key=lambda item: item.start):
        cursor = reading.start.astimezone(UTC)
        end = cursor + timedelta(seconds=reading.duration_seconds)
        while cursor < end:
            local = cursor.astimezone(zone)
            hour_start = cursor.replace(minute=0, second=0, microsecond=0)
            next_hour = hour_start + timedelta(hours=1)
            local_month_end = datetime.combine(
                (local.date().replace(day=28) + timedelta(days=4)).replace(day=1),
                datetime.min.time(), tzinfo=zone
            ).astimezone(UTC)
            segment_end = min(end, next_hour, local_month_end)
            seconds = (segment_end - cursor).total_seconds()
            energy = reading.energy_kwh * seconds / reading.duration_seconds
            month_key = (local.year, local.month)
            used = monthly_usage[month_key]
            threshold = tiered_threshold(local.date())
            tier1_energy = min(energy, max(0.0, threshold - used))
            tier2_energy = energy - tier1_energy
            prices = _tiered_prices(local.date(), rates, rate_effective_date)
            hourly_costs[hour_start] += tier1_energy * prices["tier1"] + tier2_energy * prices["tier2"]
            monthly_usage[month_key] += energy
            cursor = segment_end
    return hourly_costs


def _statistics_from_hourly_costs(hourly_costs: dict[datetime, float]) -> list[dict[str, object]]:
    if not hourly_costs:
        return []
    first_hour = min(hourly_costs)
    cumulative = 0.0
    result: list[dict[str, object]] = [{"start": first_hour, "state": 0.0, "sum": 0.0}]
    for hour in sorted(hourly_costs):
        cumulative = round(cumulative + hourly_costs[hour], 6)
        result.append({"start": hour + timedelta(hours=1), "state": cumulative, "sum": cumulative})
    return result


def build_cost_statistics(readings, rates: dict[str, float] | None = None,
                          time_zone: str = "America/Toronto",
                          rate_effective_date: date = DEFAULT_RATE_EFFECTIVE_DATE,
                          pricing_plan: str = PLAN_TOU) -> list[dict[str, object]]:
    """Build cumulative CAD cost statistics for the selected Ontario plan."""
    if not readings:
        return []
    if pricing_plan == PLAN_TIERED:
        return _statistics_from_hourly_costs(
            _build_tiered_costs(readings, rates, time_zone, rate_effective_date)
        )
    hourly_costs: dict[datetime, float] = defaultdict(float)
    rate_function = ulo_rate_for_datetime if pricing_plan == PLAN_ULO else tou_rate_for_datetime
    for reading in readings:
        start = reading.start.astimezone(UTC)
        end = start + timedelta(seconds=reading.duration_seconds)
        cursor = start
        while cursor < end:
            hour_start = cursor.replace(minute=0, second=0, microsecond=0)
            segment_end = min(end, hour_start + timedelta(hours=1))
            seconds = (segment_end - cursor).total_seconds()
            energy = reading.energy_kwh * seconds / reading.duration_seconds
            hourly_costs[hour_start] += energy * rate_function(cursor, rates, time_zone, rate_effective_date)
            cursor = segment_end
    return _statistics_from_hourly_costs(hourly_costs)
