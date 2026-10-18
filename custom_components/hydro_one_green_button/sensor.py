"""Sensors for imported Hydro One Green Button data."""
from __future__ import annotations
from datetime import datetime
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from .const import DOMAIN
from .green_button import GreenButtonData

def _device_info() -> DeviceInfo:
    return DeviceInfo(identifiers={(DOMAIN, "hydro_one_account")}, name="Hydro One Green Button", manufacturer="Hydro One", model="Green Button XML import")

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Green Button sensors."""
    coordinator: DataUpdateCoordinator[GreenButtonData] = entry.runtime_data
    async_add_entities([HydroOneLatestIntervalSensor(coordinator), HydroOneTotalEnergySensor(coordinator), HydroOneLatestReadingTimeSensor(coordinator), HydroOneIntervalCountSensor(coordinator)])

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
    def __init__(self, coordinator): super().__init__(coordinator, "latest_interval_energy")
    @property
    def native_value(self) -> float: return round(self.coordinator.data.latest_reading.energy_kwh, 6)
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
    def __init__(self, coordinator): super().__init__(coordinator, "imported_energy_total")
    @property
    def native_value(self) -> float: return round(self.coordinator.data.total_energy_kwh, 3)
    @property
    def extra_state_attributes(self) -> dict[str, int | str]:
        readings = self.coordinator.data.readings
        return {"interval_count": len(readings), "first_reading": readings[0].start.isoformat(), "last_reading": readings[-1].start.isoformat(), "note": "Sum of intervals in the currently imported XML file; overlapping periods can change this total."}

class HydroOneLatestReadingTimeSensor(HydroOneSensorBase):
    """Start time of the latest interval."""
    _attr_name = "Latest reading time"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    def __init__(self, coordinator): super().__init__(coordinator, "latest_reading_time")
    @property
    def native_value(self) -> datetime: return self.coordinator.data.latest_reading.start

class HydroOneIntervalCountSensor(HydroOneSensorBase):
    """Number of imported intervals."""
    _attr_name = "Imported interval count"
    _attr_state_class = SensorStateClass.MEASUREMENT
    def __init__(self, coordinator): super().__init__(coordinator, "imported_interval_count")
    @property
    def native_value(self) -> int: return len(self.coordinator.data.readings)
