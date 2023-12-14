"""Config flow for Checkwatt integration."""
from __future__ import annotations

import logging
from typing import Any

import requests
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    CONF_DETAILED_SENSORS,
)
from .checkwatt import checkwatt_autenticate

CONF_TITLE = "Checkwatt"

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

class CheckwattHub:
    """Checkwatt configuration validations."""

    def __init__(self) -> None:
        """Initialize."""
        
    def autenticate(self, username: str, password: str) -> bool:
        """Login to EnergyInBalance to validate."""
        try:
            checkwatt_autenticate(username, password)

        except requests.exceptions.HTTPError:
            _LOGGER.error("Login: HTTPError")
            return False
        except requests.exceptions.ConnectionError:
            _LOGGER.error("Login: ConnectionError")
            return False
        except requests.exceptions.Timeout:
            _LOGGER.error("Login: Timeout")
            return False
        except requests.exceptions.RequestException:
            _LOGGER.error("Login: RequestException")
            return False
        
        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate that the user input allows us to connect."""

    hub = CheckwattHub()
    if not await hass.async_add_executor_job(
        hub.autenticate,
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
    ):
        raise InvalidAuth


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Checkwatt."""

    VERSION = 1

    def __init__(self):
        """Set up the the config flow."""
        self.data = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step. Username and password."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}
        self.data = user_input
        try:
            await validate_input(self.hass, self.data)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title=CONF_TITLE,
                data=self.data,
                options={
                    CONF_DETAILED_SENSORS: False,
                },
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a options flow for Checkwatt."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title=CONF_TITLE, data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DETAILED_SENSORS,
                        default=self.config_entry.options.get(CONF_DETAILED_SENSORS),
                    ): bool
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
