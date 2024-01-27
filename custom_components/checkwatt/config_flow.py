"""Config flow for CheckWatt integration."""

from __future__ import annotations

import logging
from typing import Any

from pycheckwatt import CheckwattManager
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_CM10_SENSOR,
    CONF_CWR_NAME,
    CONF_POWER_SENSORS,
    CONF_PUSH_CW_TO_RANK,
    DOMAIN,
)

CONF_TITLE = "CheckWatt"

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate that the user input allows us to connect to CheckWatt."""
    async with CheckwattManager(
        data[CONF_USERNAME], data[CONF_PASSWORD]
    ) as check_watt_instance:
        if not await check_watt_instance.login():
            raise InvalidAuth


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CheckWatt."""

    VERSION = 1

    def __init__(self) -> None:
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
                    CONF_POWER_SENSORS: False,
                    CONF_PUSH_CW_TO_RANK: False,
                    CONF_CM10_SENSOR: True,
                    CONF_CWR_NAME: "",
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
    """Handle a options flow for CheckWatt."""

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
                        CONF_POWER_SENSORS,
                        default=self.config_entry.options.get(CONF_POWER_SENSORS),
                    ): bool,
                    vol.Required(
                        CONF_PUSH_CW_TO_RANK,
                        default=self.config_entry.options.get(CONF_PUSH_CW_TO_RANK),
                    ): bool,
                    vol.Required(
                        CONF_CM10_SENSOR,
                        default=self.config_entry.options.get(CONF_CM10_SENSOR),
                    ): bool,
                    vol.Optional(
                        CONF_CWR_NAME,
                        default=self.config_entry.options.get(CONF_CWR_NAME),
                    ): str,
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
