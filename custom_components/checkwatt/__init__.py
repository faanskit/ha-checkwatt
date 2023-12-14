"""The Checkwatt integration."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any, TypedDict, cast

import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, CONF_UPDATE_INTERVAL, CONF_DETAILED_SENSORS
from .checkwatt import get_checkwatt_data

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

class CheckwattList(TypedDict):
    """API response for checkwattList."""
    inverter_make: str
    inverter_model: str
    battery_make: str
    battery_model: str

class CheckwattResponse(TypedDict):
    """API response."""

    checkwattList: list[CheckwattList]


async def update_listener(hass, entry):
    """Handle options update."""
    _LOGGER.debug(entry.options)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Checkwayy from a config entry."""
    coordinator = CheckwattCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class CheckwattCoordinator(DataUpdateCoordinator[CheckwattResponse]):
    """Data update coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=CONF_UPDATE_INTERVAL),
            # update_interval=timedelta(seconds=20),
        )
        self._entry = entry
        self.temp = 3

    @property
    def entry_id(self) -> str:
        """Return entry ID."""
        return self._entry.entry_id

    async def _async_update_data(self) -> CheckwattResponse:
        """Fetch the latest data from the source."""
        try:
            data = await self.hass.async_add_executor_job(
                get_data, self.hass, self._entry.data, self._entry.options
            )
        except InvalidAuth as err:
            raise ConfigEntryAuthFailed from err
        except CheckwattError as err:
            raise UpdateFailed(str(err)) from err

        return data


class CheckwattError(HomeAssistantError):
    """Base error."""


class InvalidAuth(CheckwattError):
    """Raised when invalid authentication credentials are provided."""


class APIRatelimitExceeded(CheckwattError):
    """Raised when the API rate limit is exceeded."""


class UnknownError(CheckwattError):
    """Raised when an unknown error occurs."""


def get_data(
    hass: HomeAssistant, config: Mapping[str, Any], options: Mapping[str, Any]
) -> CheckwattResponse:
    """Get data from the API."""

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    detailed_sensors = options.get(CONF_DETAILED_SENSORS)

    try:
        _LOGGER.debug(
            "Fetching data with username %s with detailed sensors option set to %s",
            username,
            detailed_sensors,
        )
        checkwatt_info = get_checkwatt_data(username, password, detailed_sensors)

    except requests.exceptions.HTTPError as errh:
        raise requests.exceptions.HTTPError(errh)
    except requests.exceptions.ConnectionError as errc:
        raise requests.exceptions.ConnectionError(errc)
    except requests.exceptions.Timeout as errt:
        raise requests.exceptions.Timeout(errt)
    except requests.exceptions.RequestException as errr:
        raise requests.exceptions.RequestException(errr)
    except ValueError as err:
        err_str = str(err)

        if "Invalid authentication credentials" in err_str:
            raise InvalidAuth from err
        if "API rate limit exceeded." in err_str:
            raise APIRatelimitExceeded from err

        _LOGGER.exception("Unexpected exception")
        raise UnknownError from err

    else:
        if "error" in checkwatt_info:
            raise UnknownError(checkwatt_info["error"])

        if checkwatt_info.get("status") != "success":
            _LOGGER.exception("Unexpected response: %s", checkwatt_info)
            raise UnknownError
    return cast(CheckwattResponse, checkwatt_info)
