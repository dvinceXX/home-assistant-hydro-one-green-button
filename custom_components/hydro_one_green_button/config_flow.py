"""Config and options flows for Hydro One Green Button XML imports."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry

from .const import CONF_FILE_PATH, DOMAIN
from .green_button import GreenButtonParseError, parse_green_button_source


class HydroOneGreenButtonConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up Hydro One Green Button from an XML file or watched folder."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Ask for the XML file path or dedicated folder path."""
        errors: dict[str, str] = {}
        if user_input is not None:
            source_path = user_input[CONF_FILE_PATH].strip()
            try:
                await self.hass.async_add_executor_job(
                    parse_green_button_source, source_path
                )
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
                    title="Hydro One Green Button",
                    data={CONF_FILE_PATH: source_path},
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
    """Allow changing the XML file or watched folder without removing the entry."""

    async def async_step_init(self, user_input: dict | None = None):
        """Choose a new XML source path."""
        errors: dict[str, str] = {}
        if user_input is not None:
            source_path = user_input[CONF_FILE_PATH].strip()
            try:
                await self.hass.async_add_executor_job(
                    parse_green_button_source, source_path
                )
            except FileNotFoundError:
                errors["base"] = "file_not_found"
            except PermissionError:
                errors["base"] = "permission_denied"
            except (OSError, GreenButtonParseError):
                errors["base"] = "invalid_file"
            else:
                return self.async_create_entry(title="", data={CONF_FILE_PATH: source_path})

        current_path = self.config_entry.options.get(
            CONF_FILE_PATH, self.config_entry.data[CONF_FILE_PATH]
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_FILE_PATH, default=current_path): str
            }),
            errors=errors,
            description_placeholders={"example_path": "/config/hydro-one-xml"},
        )
