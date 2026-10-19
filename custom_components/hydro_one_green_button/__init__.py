"""Hydro One Green Button XML integration."""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_FILE_PATH, DEFAULT_SCAN_INTERVAL, DOMAIN, PLATFORMS
from .green_button import (
    GreenButtonData,
    GreenButtonParseError,
    build_energy_statistics,
    parse_green_button_file,
)

_LOGGER = logging.getLogger(__name__)
STATISTIC_ID = f"{DOMAIN}:historical_energy"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    file_path = entry.data[CONF_FILE_PATH]
    last_import_signature: tuple[tuple[datetime, int, float], ...] | None = None

    async def async_update_data() -> GreenButtonData:
        nonlocal last_import_signature
        try:
            data = await hass.async_add_executor_job(parse_green_button_file, file_path)
        except (OSError, GreenButtonParseError) as err:
            raise UpdateFailed(f"Unable to read Green Button XML file: {err}") from err

        signature = tuple(
            (reading.start, reading.duration_seconds, reading.energy_kwh)
            for reading in data.readings
        )
        if signature != last_import_signature:
            try:
                async_add_external_statistics(
                    hass,
                    {
                        "has_mean": False,
                        "has_sum": True,
                        "name": "Hydro One Historical Energy",
                        "source": DOMAIN,
                        "statistic_id": STATISTIC_ID,
                        "unit_class": "energy",
                        "unit_of_measurement": "kWh",
                    },
                    build_energy_statistics(data.readings),
                )
                last_import_signature = signature
                _LOGGER.info(
                    "Submitted %d Hydro One historical energy intervals to Home Assistant statistics",
                    len(data.readings),
                )
            except Exception:
                # Keep the live sensors available even if statistics import fails.
                # Leaving the signature unchanged allows the next refresh to retry.
                _LOGGER.exception("Unable to import Hydro One historical energy statistics")

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
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the integration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
