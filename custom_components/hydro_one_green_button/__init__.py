"""Hydro One Green Button XML integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    clear_statistics_range,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.recorder import get_instance
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_FILE_PATH,
    CONF_PRICING_PLAN,
    CONF_ULO_OVERNIGHT_RATE,
    CONF_ULO_WEEKEND_RATE,
    CONF_TIER1_RATE,
    CONF_TIER2_RATE,
    CONF_MID_PEAK_RATE,
    CONF_OFF_PEAK_RATE,
    CONF_ON_PEAK_RATE,
    CONF_RATE_EFFECTIVE_DATE,
    DEFAULT_MID_PEAK_RATE,
    DEFAULT_OFF_PEAK_RATE,
    DEFAULT_ULO_OVERNIGHT_RATE,
    DEFAULT_ULO_WEEKEND_RATE,
    DEFAULT_TIER1_RATE,
    DEFAULT_TIER2_RATE,
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
from .pricing import DEFAULT_RATE_EFFECTIVE_DATE, DEFAULT_PRICING_PLAN, PLAN_TOU, PLAN_ULO, PLAN_TIERED, build_cost_statistics

_LOGGER = logging.getLogger(__name__)
ENERGY_STATISTIC_ID = f"{DOMAIN}:historical_energy"
COST_STATISTIC_ID = f"{DOMAIN}:historical_cost"

# A one-time, persisted migration marker. The old energy points were stored at
# interval end; the corrected series uses interval start. Cost is also rebuilt
# so historical rates are corrected at the same time.
_STATISTICS_MIGRATION_KEY = "historical_statistics_rebuilt_v1"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from an XML file or a folder of exports."""
    source_path = entry.options.get(CONF_FILE_PATH, entry.data[CONF_FILE_PATH])
    pricing_plan = entry.options.get(CONF_PRICING_PLAN, DEFAULT_PRICING_PLAN)
    if pricing_plan == PLAN_ULO:
        rates = {
            "overnight": float(entry.options.get(CONF_ULO_OVERNIGHT_RATE, DEFAULT_ULO_OVERNIGHT_RATE)),
            "weekend_off_peak": float(entry.options.get(CONF_ULO_WEEKEND_RATE, DEFAULT_ULO_WEEKEND_RATE)),
            "mid_peak": float(entry.options.get(CONF_MID_PEAK_RATE, DEFAULT_MID_PEAK_RATE)),
            "on_peak": float(entry.options.get(CONF_ON_PEAK_RATE, DEFAULT_ON_PEAK_RATE)),
        }
    elif pricing_plan == PLAN_TIERED:
        rates = {
            "tier1": float(entry.options.get(CONF_TIER1_RATE, DEFAULT_TIER1_RATE)),
            "tier2": float(entry.options.get(CONF_TIER2_RATE, DEFAULT_TIER2_RATE)),
        }
    else:
        pricing_plan = PLAN_TOU
        rates = {
            "off_peak": float(entry.options.get(CONF_OFF_PEAK_RATE, DEFAULT_OFF_PEAK_RATE)),
            "mid_peak": float(entry.options.get(CONF_MID_PEAK_RATE, DEFAULT_MID_PEAK_RATE)),
            "on_peak": float(entry.options.get(CONF_ON_PEAK_RATE, DEFAULT_ON_PEAK_RATE)),
        }
    rate_effective_date = datetime.strptime(
        entry.options.get(
            CONF_RATE_EFFECTIVE_DATE, DEFAULT_RATE_EFFECTIVE_DATE.isoformat()
        ),
        "%Y-%m-%d",
    ).date()
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

        try:
            energy_statistics = build_energy_statistics(data.readings)
            cost_statistics = await hass.async_add_executor_job(
                build_cost_statistics,
                data.readings,
                rates,
                time_zone,
                rate_effective_date,
                pricing_plan,
            )

            if not entry.data.get(_STATISTICS_MIGRATION_KEY):
                # Clear only the two Hydro One series, and only over the
                # imported history. The extra margin catches the old
                # interval-end timestamps and the cost series' hour-end rows.
                first_reading = data.readings[0]
                last_reading = data.readings[-1]
                cleanup_start = first_reading.start - timedelta(days=1)
                cleanup_end = (
                    last_reading.start
                    + timedelta(seconds=last_reading.duration_seconds)
                    + timedelta(days=1)
                )
                await hass.async_add_executor_job(
                    clear_statistics_range,
                    get_instance(hass),
                    [ENERGY_STATISTIC_ID, COST_STATISTIC_ID],
                    cleanup_start,
                    cleanup_end,
                )
                _LOGGER.info(
                    "Cleared legacy Hydro One statistics from %s through %s "
                    "before rebuilding corrected energy and cost history",
                    cleanup_start,
                    cleanup_end,
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

            if not entry.data.get(_STATISTICS_MIGRATION_KEY):
                hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, _STATISTICS_MIGRATION_KEY: True},
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
