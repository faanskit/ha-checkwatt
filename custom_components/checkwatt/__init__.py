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

from .checkwatt import get_checkwatt_data
from .const import CONF_DETAILED_SENSORS, CONF_UPDATE_INTERVAL, DOMAIN
from .pycheckwatt import CheckwattManager

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


class CheckwattResp(TypedDict):
    """API response."""

    id: str
    firstname: str
    lastname: str
    address: str
    zip: str
    city: str
    display_name: str
    revenue: float


async def update_listener(hass: HomeAssistant, entry):
    """Handle options update."""
    _LOGGER.debug(entry.options)
    if not hass:  # Not sure, to remove warning
        await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Checkwatt from a config entry."""
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


class CheckwattCoordinator(DataUpdateCoordinator[CheckwattResp]):
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

    async def _async_update_data(self) -> CheckwattResp:
        """Fetch the latest data from the source."""

        try:
            # data = await self.hass.async_add_executor_job(
            #     get_data, self.hass, self._entry.data, self._entry.options
            # )
            username = self._entry.data.get(CONF_USERNAME)
            password = self._entry.data.get(CONF_PASSWORD)

            async with CheckwattManager(username, password) as cw_inst:
                if not await cw_inst.login():
                    raise InvalidAuth
                if not await cw_inst.get_customer_details():
                    raise UpdateFailed("Unknown error get_customer_details")
                if not await cw_inst.get_fcrd_revenue():
                    raise UpdateFailed("Unknown error get_fcrd_revenue")

                response_data: CheckwattResp = {
                    "id": cw_inst.customer_details["Id"],
                    "firstname": cw_inst.customer_details["FirstName"],
                    "lastname": cw_inst.customer_details["LastName"],
                    "address": cw_inst.customer_details["StreetAddress"],
                    "zip": cw_inst.customer_details["ZipCode"],
                    "city": cw_inst.customer_details["City"],
                    "display_name": cw_inst.customer_details["Meter"][0]["DisplayName"],
                    "revenue": cw_inst.today_revenue,
                }
                return response_data

        except InvalidAuth as err:
            raise ConfigEntryAuthFailed from err
        except CheckwattError as err:
            raise UpdateFailed(str(err)) from err


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
) -> CheckwattResp:
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
        raise requests.exceptions.HTTPError(errh) from errh
    except requests.exceptions.ConnectionError as errc:
        raise requests.exceptions.ConnectionError(errc) from errc
    except requests.exceptions.Timeout as errt:
        raise requests.exceptions.Timeout(errt) from errt
    except requests.exceptions.RequestException as errr:
        raise requests.exceptions.RequestException(errr) from errr
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

        if checkwatt_info.get("Status") != "Success":
            _LOGGER.exception("Unexpected response: %s", checkwatt_info)
            raise UnknownError
    return cast(CheckwattResp, checkwatt_info)
