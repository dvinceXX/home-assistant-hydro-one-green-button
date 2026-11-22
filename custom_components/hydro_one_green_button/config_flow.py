"""Config and options flows for Hydro One Green Button XML imports."""
from __future__ import annotations

from datetime import date

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_FILE_PATH, CONF_PRICING_PLAN, CONF_OFF_PEAK_RATE, CONF_MID_PEAK_RATE,
    CONF_ON_PEAK_RATE, CONF_ULO_OVERNIGHT_RATE, CONF_ULO_WEEKEND_RATE,
    CONF_TIER1_RATE, CONF_TIER2_RATE, CONF_RATE_EFFECTIVE_DATE,
    DEFAULT_OFF_PEAK_RATE, DEFAULT_MID_PEAK_RATE, DEFAULT_ON_PEAK_RATE,
    DEFAULT_ULO_OVERNIGHT_RATE, DEFAULT_ULO_WEEKEND_RATE,
    DEFAULT_TIER1_RATE, DEFAULT_TIER2_RATE, DOMAIN,
)
from .green_button import GreenButtonParseError, parse_green_button_source
from .pricing import DEFAULT_RATE_EFFECTIVE_DATE, PLAN_TOU, PLAN_ULO, PLAN_TIERED


def _validate_effective_date(value: str) -> str:
    """Validate an ISO date used as the effective date for configured rates."""
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError) as err:
        raise vol.Invalid("Enter a date in YYYY-MM-DD format") from err
    return value


class HydroOneGreenButtonConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up Hydro One Green Button from an XML file or a watched folder."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Ask for the XML file path or dedicated folder path."""
        errors: dict[str, str] = {}
        if user_input is not None:
            source_path = user_input[CONF_FILE_PATH].strip()
            try:
                await self.hass.async_add_executor_job(parse_green_button_source, source_path)
            except FileNotFoundError:
                errors["base"] = "file_not_found"
            except PermissionError:
                errors["base"] = "permission_denied"
            except (OSError, GreenButtonParseError):
                errors["base"] = "invalid_file"
            else:
                await self.async_set_unique_id(source_path)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Hydro One Green Button", data={CONF_FILE_PATH: source_path}
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_FILE_PATH): str}),
            errors=errors,
            description_placeholders={"example_path": "/config/hydro-one-xml"},
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry):
        """Create the options flow for an existing integration entry."""
        return HydroOneGreenButtonOptionsFlow()


class HydroOneGreenButtonOptionsFlow(config_entries.OptionsFlow):
    """Configure the XML source, Ontario pricing plan and plan rates."""

    async def async_step_init(self, user_input: dict | None = None):
        """Choose a source path and electricity pricing plan."""
        errors: dict[str, str] = {}
        if user_input is not None:
            source_path = user_input[CONF_FILE_PATH].strip()
            try:
                await self.hass.async_add_executor_job(parse_green_button_source, source_path)
            except FileNotFoundError:
                errors["base"] = "file_not_found"
            except PermissionError:
                errors["base"] = "permission_denied"
            except (OSError, GreenButtonParseError):
                errors["base"] = "invalid_file"
            else:
                values = {key: value for key, value in user_input.items()}
                values[CONF_FILE_PATH] = source_path
                for key in (
                    CONF_OFF_PEAK_RATE, CONF_MID_PEAK_RATE, CONF_ON_PEAK_RATE,
                    CONF_ULO_OVERNIGHT_RATE, CONF_ULO_WEEKEND_RATE,
                    CONF_TIER1_RATE, CONF_TIER2_RATE,
                ):
                    values[key] = float(values[key])
                return self.async_create_entry(title="", data=values)

        options = self.config_entry.options
        schema = vol.Schema({
            vol.Required(
                CONF_FILE_PATH,
                default=options.get(CONF_FILE_PATH, self.config_entry.data[CONF_FILE_PATH]),
            ): str,
            vol.Required(
                CONF_PRICING_PLAN, default=options.get(CONF_PRICING_PLAN, PLAN_TOU)
            ): vol.In({
                PLAN_TOU: "Time-of-Use (TOU)",
                PLAN_ULO: "Ultra-Low Overnight (ULO)",
                PLAN_TIERED: "Tiered (residential)",
            }),
            vol.Required(CONF_OFF_PEAK_RATE, default=options.get(CONF_OFF_PEAK_RATE, DEFAULT_OFF_PEAK_RATE)): vol.All(vol.Coerce(float), vol.Range(min=0)),
            vol.Required(CONF_MID_PEAK_RATE, default=options.get(CONF_MID_PEAK_RATE, DEFAULT_MID_PEAK_RATE)): vol.All(vol.Coerce(float), vol.Range(min=0)),
            vol.Required(CONF_ON_PEAK_RATE, default=options.get(CONF_ON_PEAK_RATE, DEFAULT_ON_PEAK_RATE)): vol.All(vol.Coerce(float), vol.Range(min=0)),
            vol.Required(CONF_ULO_OVERNIGHT_RATE, default=options.get(CONF_ULO_OVERNIGHT_RATE, DEFAULT_ULO_OVERNIGHT_RATE)): vol.All(vol.Coerce(float), vol.Range(min=0)),
            vol.Required(CONF_ULO_WEEKEND_RATE, default=options.get(CONF_ULO_WEEKEND_RATE, DEFAULT_ULO_WEEKEND_RATE)): vol.All(vol.Coerce(float), vol.Range(min=0)),
            vol.Required(CONF_TIER1_RATE, default=options.get(CONF_TIER1_RATE, DEFAULT_TIER1_RATE)): vol.All(vol.Coerce(float), vol.Range(min=0)),
            vol.Required(CONF_TIER2_RATE, default=options.get(CONF_TIER2_RATE, DEFAULT_TIER2_RATE)): vol.All(vol.Coerce(float), vol.Range(min=0)),
            vol.Required(
                CONF_RATE_EFFECTIVE_DATE,
                default=options.get(CONF_RATE_EFFECTIVE_DATE, DEFAULT_RATE_EFFECTIVE_DATE.isoformat()),
            ): vol.All(str, _validate_effective_date),
        })
        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors,
            description_placeholders={"example_path": "/config/hydro-one-xml"},
        )
