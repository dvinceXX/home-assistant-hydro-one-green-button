"""Hydro One Green Button XML integration."""
from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_FILE_PATH,
    CONF_MID_PEAK_RATE,
    CONF_OFF_PEAK_RATE,
    CONF_ON_PEAK_RATE,
    DEFAULT_MID_PEAK_RATE,
    DEFAULT_OFF_PEAK_RATE,
    DEFAULT_ON_PEAK_RATE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .green_button import (
    GreenButtonData,
    GreenButtonParseError,
    build_energy_statistics,
    parse_green_button_source,
)
from .pricing import build_cost_statistics

_LOGGER = logging.getLogger(__name__)
ENERGY_STATISTIC_ID = f"{DOMAIN}:historical_energy"
COST_STATISTIC_ID = f"{DOMAIN}:historical_cost"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from an XML file or a folder of exports."""
    source_path = entry.options.get(CONF_FILE_PATH, entry.data[CONF_FILE_PATH])
    rates = {
        "off_peak": float(entry.options.get(CONF_OFF_PEAK_RATE, DEFAULT_OFF_PEAK_RATE)),
        "mid_peak": float(entry.options.get(CONF_MID_PEAK_RATE, DEFAULT_MID_PEAK_RATE)),
        "on_peak": float(entry.options.get(CONF_ON_PEAK_RATE, DEFAULT_ON_PEAK_RATE)),
    }
    time_zone = hass.config.time_zone
    last_import_signature: tuple[tuple[datetime, int, float], ...] | None = None

    async def async_update_data() -> GreenButtonData:
        nonlocal last_import_signature
        try:
            data = await hass.async_add_executor_job(
                parse_green_button_source, source_path
            )
        except (OSError, GreenButtonParseError) as err:
            raise UpdateFailed(f"Unable to read Green Button XML source: {err}") from err

        signature = tuple(
            (reading.start, reading.duration_seconds, reading.energy_kwh)
            for reading in data.readings
        )
        if signature == last_import_signature:
            return data

        # Rebuild both complete cumulative series whenever source data changes.
        # This also allows a later export to fill gaps in an earlier partial day.
        try:
            energy_statistics = build_energy_statistics(data.readings)
            cost_statistics = await hass.async_add_executor_job(
                build_cost_statistics, data.readings, rates, time_zone
            )
            async_add_external_statistics(
                hass,
                {
                    "has_mean": False,
                    "has_sum": True,
                    "mean_type": 0,
                    "name": "Hydro One Historical Energy",
                    "source": DOMAIN,
                    "statistic_id": ENERGY_STATISTIC_ID,
                    "unit_class": "energy",
                    "unit_of_measurement": "kWh",
                },
                energy_statistics,
            )
            async_add_external_statistics(
                hass,
                {
                    "has_mean": False,
                    "has_sum": True,
                    "mean_type": 0,
                    "name": "Hydro One Historical Electricity Cost",
                    "source": DOMAIN,
                    "statistic_id": COST_STATISTIC_ID,
                    "unit_class": None,
                    "unit_of_measurement": "CAD",
                },
                cost_statistics,
            )
            last_import_signature = signature
            _LOGGER.info(
                "Submitted %d Hydro One interval readings, %d energy statistics "
                "and %d hourly cost statistics",
                len(data.readings),
                len(energy_statistics),
                len(cost_statistics),
            )
        except Exception:
            _LOGGER.exception("Unable to import Hydro One energy/cost statistics")

        return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=DEFAULT_SCAN_INTERVAL,
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except UpdateFailed as err:
        raise ConfigEntryNotReady from err

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the integration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when its watched source path changes."""
    await hass.config_entries.async_reload(entry.entry_id)
