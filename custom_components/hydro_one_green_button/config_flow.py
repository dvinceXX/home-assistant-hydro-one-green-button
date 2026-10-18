"""Config flow for Hydro One Green Button XML imports."""
from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from .const import CONF_FILE_PATH, DOMAIN
from .green_button import GreenButtonParseError, parse_green_button_file

class HydroOneGreenButtonConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up Hydro One Green Button from an exported XML file."""
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Ask for the absolute path to a Green Button XML file."""
        errors: dict[str, str] = {}
        if user_input is not None:
            file_path = user_input[CONF_FILE_PATH].strip()
            try:
                await self.hass.async_add_executor_job(parse_green_button_file, file_path)
            except FileNotFoundError:
                errors["base"] = "file_not_found"
            except PermissionError:
                errors["base"] = "permission_denied"
            except (OSError, GreenButtonParseError):
                errors["base"] = "invalid_file"
            else:
                await self.async_set_unique_id(file_path)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Hydro One Green Button", data={CONF_FILE_PATH: file_path})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({vol.Required(CONF_FILE_PATH): str}), errors=errors, description_placeholders={"example_path": "/config/hydro-one-green-button.xml"})
