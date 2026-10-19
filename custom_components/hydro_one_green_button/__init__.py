"""Hydro One Green Button XML integration."""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_FILE_PATH, DEFAULT_SCAN_INTERVAL, DOMAIN, PLATFORMS
from .green_button import (
    GreenButtonData,
    GreenButtonParseError,
    build_energy_statistics,
    parse_green_button_source,
)

_LOGGER = logging.getLogger(__name__)
STATISTIC_ID = f"{DOMAIN}:historical_energy"
STORAGE_VERSION = 1


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from an XML file or a folder of exports."""
    source_path = entry.options.get(CONF_FILE_PATH, entry.data[CONF_FILE_PATH])
    store: Store[dict] = Store(
        hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}_import_state"
    )
    saved = await store.async_load() or {}
    imported_days: set[str] = set(saved.get("imported_days", []))
    cumulative_sum_kwh = float(saved.get("cumulative_sum_kwh", 0.0))
    last_import_signature: tuple[tuple[datetime, int, float], ...] | None = None

    async def async_update_data() -> GreenButtonData:
        nonlocal last_import_signature, cumulative_sum_kwh, imported_days
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

        zone = ZoneInfo(hass.config.time_zone)
        readings_by_day: dict[str, list] = {}
        for reading in data.readings:
            local_day = reading.start.astimezone(zone).date().isoformat()
            readings_by_day.setdefault(local_day, []).append(reading)

        new_days = sorted(day for day in readings_by_day if day not in imported_days)
        new_readings = tuple(
            sorted(
                (
                    reading
                    for day in new_days
                    for reading in readings_by_day[day]
                ),
                key=lambda item: item.start,
            )
        )

        if not new_readings:
            _LOGGER.debug("No new Hydro One history days found; existing days were skipped")
            last_import_signature = signature
            return data

        try:
            statistics = build_energy_statistics(
                new_readings,
                initial_sum_kwh=cumulative_sum_kwh,
                include_baseline=not imported_days,
            )
            async_add_external_statistics(
                hass,
                {
                    "has_mean": False,
                    "has_sum": True,
                    "mean_type": 0,
                    "name": "Hydro One Historical Energy",
                    "source": DOMAIN,
                    "statistic_id": STATISTIC_ID,
                    "unit_class": "energy",
                    "unit_of_measurement": "kWh",
                },
                statistics,
            )

            new_cumulative_sum = round(
                cumulative_sum_kwh
                + sum(reading.energy_kwh for reading in new_readings),
                6,
            )
            new_imported_days = imported_days.union(new_days)
            await store.async_save(
                {
                    "imported_days": sorted(new_imported_days),
                    "cumulative_sum_kwh": new_cumulative_sum,
                }
            )
            cumulative_sum_kwh = new_cumulative_sum
            imported_days = new_imported_days
            last_import_signature = signature
            _LOGGER.info(
                "Imported %d new intervals across %d days; skipped %d previously imported days",
                len(new_readings),
                len(new_days),
                len(readings_by_day) - len(new_days),
            )
        except Exception:
            # Do not mark days as imported unless statistics submission and state
            # persistence both succeed; the next poll can retry.
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
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the integration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)



async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when its watched source path changes."""
    await hass.config_entries.async_reload(entry.entry_id)
