"""Sensors for imported Hydro One Green Button data."""
from __future__ import annotations
from datetime import date, datetime
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from .const import CONF_MID_PEAK_RATE, CONF_OFF_PEAK_RATE, CONF_ON_PEAK_RATE, CONF_RATE_EFFECTIVE_DATE, DEFAULT_MID_PEAK_RATE, DEFAULT_OFF_PEAK_RATE, DEFAULT_ON_PEAK_RATE, DOMAIN
from .green_button import GreenButtonData
from .pricing import DEFAULT_RATE_EFFECTIVE_DATE, tou_rate_for_datetime

def _device_info() -> DeviceInfo:
    return DeviceInfo(identifiers={(DOMAIN, "hydro_one_account")}, name="Hydro One Green Button", manufacturer="Hydro One", model="Green Button XML import")

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Green Button sensors."""
    coordinator: DataUpdateCoordinator[GreenButtonData] = entry.runtime_data
    rates = {
        "off_peak": float(entry.options.get(CONF_OFF_PEAK_RATE, DEFAULT_OFF_PEAK_RATE)),
        "mid_peak": float(entry.options.get(CONF_MID_PEAK_RATE, DEFAULT_MID_PEAK_RATE)),
        "on_peak": float(entry.options.get(CONF_ON_PEAK_RATE, DEFAULT_ON_PEAK_RATE)),
    }
    effective_date = date.fromisoformat(entry.options.get(CONF_RATE_EFFECTIVE_DATE, DEFAULT_RATE_EFFECTIVE_DATE.isoformat()))
    async_add_entities([
        HydroOneLatestIntervalSensor(coordinator),
        HydroOneTotalEnergySensor(coordinator),
        HydroOneLatestReadingTimeSensor(coordinator),
        HydroOneIntervalCountSensor(coordinator),
        HydroOneTouRateSensor(coordinator, rates, hass.config.time_zone, effective_date),
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
        return {"interval_start": reading.start.isoformat(), "interval_duration_seconds": reading.duration_seconds}

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
        return {"interval_count": len(readings), "first_reading": readings[0].start.isoformat(), "last_reading": readings[-1].start.isoformat(), "note": "Sum of intervals in the currently imported XML file; overlapping periods can change this total."}

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

class HydroOneTouRateSensor(HydroOneSensorBase):
    """Current scheduled Ontario time-of-use electricity rate."""
    _attr_has_entity_name = False
    _attr_name = "Hydro One TOU Rate"
    _attr_native_unit_of_measurement = "CAD/kWh"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 3
    def __init__(self, coordinator, rates: dict[str, float], time_zone: str, effective_date: date) -> None:
        super().__init__(coordinator, "tou_rate")
        self._rates = rates
        self._time_zone = time_zone
        self._effective_date = effective_date
    @property
    def native_value(self) -> float:
        return round(tou_rate_for_datetime(dt_util.now(), self._rates, self._time_zone, self._effective_date), 6)
    @property
    def extra_state_attributes(self) -> dict[str, str | float]:
        return {"rate_cents_per_kwh": round(self.native_value * 100, 3), "effective_date": self._effective_date.isoformat(), "time_zone": self._time_zone}
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_track_time_change(self.hass, self._handle_hour_change, minute=0, second=0))
    @callback
    def _handle_hour_change(self, now: datetime) -> None:
        self.async_write_ha_state()
