"""Tests for Ontario TOU cost statistics."""
from datetime import UTC, datetime
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PARSER_PATH = ROOT / "custom_components" / "hydro_one_green_button" / "green_button.py"
PARSER_SPEC = importlib.util.spec_from_file_location("green_button_parser_for_pricing", PARSER_PATH)
assert PARSER_SPEC and PARSER_SPEC.loader
PARSER = importlib.util.module_from_spec(PARSER_SPEC)
sys.modules[PARSER_SPEC.name] = PARSER
PARSER_SPEC.loader.exec_module(PARSER)

PRICING_PATH = ROOT / "custom_components" / "hydro_one_green_button" / "pricing.py"
PRICING_SPEC = importlib.util.spec_from_file_location("green_button_pricing", PRICING_PATH)
assert PRICING_SPEC and PRICING_SPEC.loader
PRICING = importlib.util.module_from_spec(PRICING_SPEC)
sys.modules[PRICING_SPEC.name] = PRICING
PRICING_SPEC.loader.exec_module(PRICING)

IntervalReading = PARSER.IntervalReading
build_cost_statistics = PRICING.build_cost_statistics
tou_rate_for_datetime = PRICING.tou_rate_for_datetime

RATES = {"off_peak": 0.091, "mid_peak": 0.146, "on_peak": 0.189}


def dt(value: str) -> datetime:
    """Create a UTC timestamp from an ISO string."""
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def test_winter_weekday_tou_periods():
    assert tou_rate_for_datetime(dt("2026-01-12T13:00:00"), RATES) == 0.189  # 8 a.m.
    assert tou_rate_for_datetime(dt("2026-01-12T18:00:00"), RATES) == 0.146  # 1 p.m.
    assert tou_rate_for_datetime(dt("2026-01-12T23:00:00"), RATES) == 0.189  # 6 p.m.
    assert tou_rate_for_datetime(dt("2026-01-13T01:00:00"), RATES) == 0.091  # 8 p.m.


def test_summer_weekday_tou_periods():
    assert tou_rate_for_datetime(dt("2026-07-13T12:00:00"), RATES) == 0.146  # 8 a.m.
    assert tou_rate_for_datetime(dt("2026-07-13T17:00:00"), RATES) == 0.189  # 1 p.m.
    assert tou_rate_for_datetime(dt("2026-07-13T22:00:00"), RATES) == 0.146  # 6 p.m.


def test_weekends_and_ontario_tou_holidays_are_off_peak():
    assert tou_rate_for_datetime(dt("2026-01-10T18:00:00"), RATES) == 0.091
    assert tou_rate_for_datetime(dt("2026-02-16T18:00:00"), RATES) == 0.091
    assert tou_rate_for_datetime(dt("2026-12-25T18:00:00"), RATES) == 0.091


def test_builds_cumulative_cost_statistics_for_hourly_readings():
    readings = (
        IntervalReading(dt("2026-01-12T18:00:00"), 3600, 2.0),
        IntervalReading(dt("2026-01-12T19:00:00"), 3600, 1.0),
    )
    stats = build_cost_statistics(readings, RATES)
    assert len(stats) == 3
    assert stats[0]["sum"] == 0.0
    assert stats[1]["sum"] == 0.292
    assert stats[2]["sum"] == 0.438


def test_cost_interval_crossing_tou_boundary_is_split_by_duration():
    # Winter weekday 10:30–11:30: half an hour on-peak, half an hour mid-peak.
    readings = (IntervalReading(dt("2026-01-12T15:30:00"), 3600, 2.0),)
    stats = build_cost_statistics(readings, RATES)
    assert stats[-1]["sum"] == 0.335


def test_custom_rates_are_applied():
    readings = (IntervalReading(dt("2026-01-12T18:00:00"), 3600, 2.0),)
    custom = {"off_peak": 0.10, "mid_peak": 0.20, "on_peak": 0.30}
    stats = build_cost_statistics(readings, custom)
    assert stats[-1]["sum"] == 0.40


def test_dst_fall_back_hours_are_priced_by_local_clock():
    # On the 2026 fall-back Sunday both repeated 01:00 hours are off-peak.
    readings = (
        IntervalReading(dt("2026-11-01T05:00:00"), 3600, 1.0),
        IntervalReading(dt("2026-11-01T06:00:00"), 3600, 1.0),
    )
    stats = build_cost_statistics(readings, RATES)
    assert stats[-1]["sum"] == 0.182
