"""Sensors for imported Hydro One Green Button data."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_FILE_PATH, CONF_PRICING_PLAN, CONF_OFF_PEAK_RATE, CONF_MID_PEAK_RATE,
    CONF_ON_PEAK_RATE, CONF_ULO_OVERNIGHT_RATE, CONF_ULO_WEEKEND_RATE,
    CONF_TIER1_RATE, CONF_TIER2_RATE, CONF_RATE_EFFECTIVE_DATE,
    DEFAULT_OFF_PEAK_RATE, DEFAULT_MID_PEAK_RATE, DEFAULT_ON_PEAK_RATE,
    DEFAULT_ULO_OVERNIGHT_RATE, DEFAULT_ULO_WEEKEND_RATE,
    DEFAULT_TIER1_RATE, DEFAULT_TIER2_RATE, DOMAIN,
)
from .green_button import GreenButtonData
from .pricing import (
    DEFAULT_PRICING_PLAN, DEFAULT_RATE_EFFECTIVE_DATE, PLAN_TOU, PLAN_ULO,
    PLAN_TIERED, rate_for_datetime, tiered_threshold,
)


def _device_info() -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, "hydro_one_account")},
        name="Hydro One Green Button",
        manufacturer="Hydro One",
        model="Green Button XML import",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Green Button sensors."""
    coordinator: DataUpdateCoordinator[GreenButtonData] = entry.runtime_data
    plan = entry.options.get(CONF_PRICING_PLAN, DEFAULT_PRICING_PLAN)
    if plan == PLAN_ULO:
        rates = {
            "overnight": float(entry.options.get(CONF_ULO_OVERNIGHT_RATE, DEFAULT_ULO_OVERNIGHT_RATE)),
            "weekend_off_peak": float(entry.options.get(CONF_ULO_WEEKEND_RATE, DEFAULT_ULO_WEEKEND_RATE)),
            "mid_peak": float(entry.options.get(CONF_MID_PEAK_RATE, DEFAULT_MID_PEAK_RATE)),
            "on_peak": float(entry.options.get(CONF_ON_PEAK_RATE, DEFAULT_ON_PEAK_RATE)),
        }
    elif plan == PLAN_TIERED:
        rates = {
            "tier1": float(entry.options.get(CONF_TIER1_RATE, DEFAULT_TIER1_RATE)),
            "tier2": float(entry.options.get(CONF_TIER2_RATE, DEFAULT_TIER2_RATE)),
        }
    else:
        plan = PLAN_TOU
        rates = {
            "off_peak": float(entry.options.get(CONF_OFF_PEAK_RATE, DEFAULT_OFF_PEAK_RATE)),
            "mid_peak": float(entry.options.get(CONF_MID_PEAK_RATE, DEFAULT_MID_PEAK_RATE)),
            "on_peak": float(entry.options.get(CONF_ON_PEAK_RATE, DEFAULT_ON_PEAK_RATE)),
        }
    effective_date = date.fromisoformat(
        entry.options.get(CONF_RATE_EFFECTIVE_DATE, DEFAULT_RATE_EFFECTIVE_DATE.isoformat())
    )
    async_add_entities([
        HydroOneLatestIntervalSensor(coordinator),
        HydroOneTotalEnergySensor(coordinator),
        HydroOneLatestReadingTimeSensor(coordinator),
        HydroOneIntervalCountSensor(coordinator),
        HydroOneElectricityRateSensor(coordinator, plan, rates, hass.config.time_zone, effective_date),
    ])


class HydroOneSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for Green Button sensors."""

    _attr_has_entity_name = True
    _attr_device_info = _device_info()

    def __init__(self, coordinator: DataUpdateCoordinator[GreenButtonData], key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"hydro_one_{key}"


class HydroOneLatestIntervalSensor(HydroOneSensorBase):
    """Energy in the most recent interval."""

    _attr_name = "Latest interval energy"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator):
        super().__init__(coordinator, "latest_interval_energy")

    @property
    def native_value(self) -> float:
        return round(self.coordinator.data.latest_reading.energy_kwh, 6)

    @property
    def extra_state_attributes(self) -> dict[str, str | int]:
        reading = self.coordinator.data.latest_reading
        return {
            "interval_start": reading.start.isoformat(),
            "interval_duration_seconds": reading.duration_seconds,
        }


class HydroOneTotalEnergySensor(HydroOneSensorBase):
    """Sum of intervals in the imported file, not a lifetime meter register."""

    _attr_name = "Imported energy total"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator):
        super().__init__(coordinator, "imported_energy_total")

    @property
    def native_value(self) -> float:
        return round(self.coordinator.data.total_energy_kwh, 3)

    @property
    def extra_state_attributes(self) -> dict[str, int | str]:
        readings = self.coordinator.data.readings
        return {
            "interval_count": len(readings),
            "first_reading": readings[0].start.isoformat(),
            "last_reading": readings[-1].start.isoformat(),
            "note": "Sum of intervals in the currently imported XML file; overlapping periods can change this total.",
        }


class HydroOneLatestReadingTimeSensor(HydroOneSensorBase):
    """Start time of the latest interval."""

    _attr_name = "Latest reading time"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator):
        super().__init__(coordinator, "latest_reading_time")

    @property
    def native_value(self) -> datetime:
        return self.coordinator.data.latest_reading.start


class HydroOneIntervalCountSensor(HydroOneSensorBase):
    """Number of imported intervals."""

    _attr_name = "Imported interval count"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator):
        super().__init__(coordinator, "imported_interval_count")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.readings)


class HydroOneElectricityRateSensor(HydroOneSensorBase):
    """Current scheduled or marginal Ontario electricity rate."""

    _attr_has_entity_name = False
    _attr_native_unit_of_measurement = "CAD/kWh"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator, plan: str, rates: dict[str, float],
                 time_zone: str, effective_date: date) -> None:
        super().__init__(coordinator, "tou_rate")
        self._plan = plan
        self._rates = rates
        self._time_zone = time_zone
        self._effective_date = effective_date
        self._attr_name = {
            PLAN_TOU: "Hydro One TOU Rate",
            PLAN_ULO: "Hydro One ULO Rate",
            PLAN_TIERED: "Hydro One Tiered Rate",
        }[plan]

    @property
    def _current_month_usage(self) -> float:
        zone = ZoneInfo(self._time_zone)
        now = dt_util.now().astimezone(zone)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
        now_utc = now.astimezone(UTC)
        total = 0.0
        for reading in self.coordinator.data.readings:
            start = reading.start.astimezone(UTC)
            end = start + timedelta(seconds=reading.duration_seconds)
            overlap_start = max(start, month_start)
            overlap_end = min(end, now_utc)
            if overlap_end > overlap_start:
                seconds = (overlap_end - overlap_start).total_seconds()
                total += reading.energy_kwh * seconds / reading.duration_seconds
        return total

    @property
    def native_value(self) -> float:
        return round(rate_for_datetime(
            dt_util.now(), self._plan, self._rates, self._time_zone,
            self._effective_date, self._current_month_usage,
        ), 6)

    @property
    def extra_state_attributes(self) -> dict[str, str | float]:
        attributes: dict[str, str | float] = {
            "pricing_plan": self._plan,
            "rate_cents_per_kwh": round(self.native_value * 100, 3),
            "effective_date": self._effective_date.isoformat(),
            "time_zone": self._time_zone,
        }
        if self._plan == PLAN_TIERED:
            attributes["month_to_date_usage_kwh"] = round(self._current_month_usage, 3)
            attributes["tier1_threshold_kwh"] = tiered_threshold(
                dt_util.now().astimezone(ZoneInfo(self._time_zone)).date()
            )
        return attributes

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_track_time_change(
            self.hass, self._handle_hour_change, minute=0, second=0
        ))

    @callback
    def _handle_hour_change(self, now: datetime) -> None:
        self.async_write_ha_state()
