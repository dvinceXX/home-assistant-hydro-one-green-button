"""Hydro One Green Button XML integration."""
from __future__ import annotations
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import CONF_FILE_PATH, DEFAULT_SCAN_INTERVAL, DOMAIN, PLATFORMS
from .green_button import GreenButtonData, GreenButtonParseError, parse_green_button_file

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    file_path = entry.data[CONF_FILE_PATH]
    async def async_update_data() -> GreenButtonData:
        try:
            return await hass.async_add_executor_job(parse_green_button_file, file_path)
        except (OSError, GreenButtonParseError) as err:
            raise UpdateFailed(f"Unable to read Green Button XML file: {err}") from err
    coordinator = DataUpdateCoordinator(hass, _LOGGER, name=DOMAIN, update_method=async_update_data, update_interval=DEFAULT_SCAN_INTERVAL)
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
