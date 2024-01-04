"""The CheckWatt integration."""
from __future__ import annotations

import asyncio
from datetime import time, timedelta
import logging
import random
from typing import TypedDict

import aiohttp
from pycheckwatt import CheckwattManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DETAILED_SENSORS,
    CONF_PUSH_CW_TO_RANK,
    CONF_UPDATE_INTERVAL,
    CONF_UPDATE_INTERVAL_FCRD,
    DOMAIN,
)

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
    fees: float
    battery_charge_peak: float
    battery_discharge_peak: float
    tomorrow_revenue: float
    tomorrow_fees: float
    update_time: str
    next_update_time: str
    fcr_d_status: str
    fcr_d_state: str
    fcr_d_date: str
    total_solar_energy: float
    total_charging_energy: float
    total_discharging_energy: float
    total_import_energy: float
    total_export_energy: float
    spot_price: float
    price_zone: str
    annual_revenue: float
    annual_fees: float
    grid_power: float
    solar_power: float
    battery_power: float
    battery_soc: float
    dso: str
    energy_provider: str


async def update_listener(hass: HomeAssistant, entry):
    """Handle options update."""
    _LOGGER.debug(entry.options)
    if not hass:  # Not sure, to remove warning
        await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CheckWatt from a config entry."""
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
        )
        self._entry = entry
        self.update_monetary = 0
        self.update_time = None
        self.next_update_time = None
        self.today_revenue = None
        self.today_fees = None
        self.tomorrow_revenue = None
        self.tomorrow_fees = None
        self.annual_revenue = None
        self.annual_fees = None
        self.last_annual_update = None
        self.last_cw_rank_push = None
        self.is_boot = True
        self.energy_provider = None
        self.random_offset = random.randint(0, 14)
        _LOGGER.debug("Fetching annual revenue at 3:%02d am", self.random_offset)

    @property
    def entry_id(self) -> str:
        """Return entry ID."""
        return self._entry.entry_id

    async def _async_update_data(self) -> CheckwattResp:
        """Fetch the latest data from the source."""

        try:
            username = self._entry.data.get(CONF_USERNAME)
            password = self._entry.data.get(CONF_PASSWORD)
            use_detailed_sensors = self._entry.options.get(CONF_DETAILED_SENSORS)
            push_to_cw_rank = self._entry.options.get(CONF_PUSH_CW_TO_RANK)

            async with CheckwattManager(username, password) as cw_inst:
                if not await cw_inst.login():
                    _LOGGER.error("Failed to login, abort update")
                    raise UpdateFailed("Failed to login")
                if not await cw_inst.get_customer_details():
                    _LOGGER.error("Failed to obtain customer details, abort update")
                    raise UpdateFailed("Unknown error get_customer_details")
                if not await cw_inst.get_energy_flow():
                    _LOGGER.error("Failed to get energy flows, abort update")
                    raise UpdateFailed("Unknown error get_energy_flow")

                # Prevent slow funcion to be called at boot.
                # The revenue sensors will be updated after ca 1 min
                if self.is_boot:
                    self.is_boot = False
                    if (
                        "Meter" in cw_inst.customer_details
                        and len(cw_inst.customer_details["Meter"]) > 0
                        and "ElhandelsbolagId" in cw_inst.customer_details["Meter"][0]
                    ):
                        self.energy_provider = await cw_inst.get_energy_trading_company(
                            cw_inst.customer_details["Meter"][0]["ElhandelsbolagId"]
                        )
                else:
                    if self.update_monetary == 0:
                        _LOGGER.debug("Fetching FCR-D data from CheckWatt")
                        self.update_time = dt_util.now().strftime("%Y-%m-%d %H:%M:%S")
                        end_date = dt_util.now() + timedelta(
                            minutes=CONF_UPDATE_INTERVAL_FCRD
                        )
                        self.next_update_time = end_date.strftime("%Y-%m-%d %H:%M:%S")
                        self.update_monetary = CONF_UPDATE_INTERVAL_FCRD
                        if not await cw_inst.get_fcrd_revenue():
                            raise UpdateFailed("Unknown error get_fcrd_revenue")
                        self.today_revenue, self.today_fees = cw_inst.today_revenue
                        (
                            self.tomorrow_revenue,
                            self.tomorrow_fees,
                        ) = cw_inst.tomorrow_revenue

                    if self.last_annual_update is None or (
                        dt_util.now().time()
                        >= time(3, self.random_offset)  # Wait until 3am +- 15 min
                        and dt_util.start_of_local_day(dt_util.now())
                        != dt_util.start_of_local_day(self.last_annual_update)
                    ):
                        _LOGGER.debug("Fetching annual revenue")
                        if not await cw_inst.get_fcrd_revenueyear():
                            raise UpdateFailed("Unknown error get_fcrd_revenueyear")
                        self.annual_revenue, self.annual_fees = cw_inst.year_revenue
                        self.last_annual_update = dt_util.now()

                    self.update_monetary -= 1

                # Price Zone is used both as Detailed Sensor and by Push to CheckWattRank
                if push_to_cw_rank or use_detailed_sensors:
                    if not await cw_inst.get_price_zone():
                        raise UpdateFailed("Unknown error get_price_zone")
                if use_detailed_sensors:
                    if not await cw_inst.get_power_data():
                        raise UpdateFailed("Unknown error get_power_data")
                    if not await cw_inst.get_spot_price():
                        raise UpdateFailed("Unknown error get_spot_price")

                if push_to_cw_rank:
                    if self.last_cw_rank_push is None or (
                        dt_util.now().time()
                        >= time(8, self.random_offset)  # Wait until 7am +- 15 min
                        and dt_util.start_of_local_day(dt_util.now())
                        != dt_util.start_of_local_day(self.last_cw_rank_push)
                    ):
                        _LOGGER.debug("Pushing to CheckWattRank")
                        if await self.push_to_checkwatt_rank(cw_inst):
                            self.last_cw_rank_push = dt_util.now()

                resp: CheckwattResp = {
                    "id": cw_inst.customer_details["Id"],
                    "firstname": cw_inst.customer_details["FirstName"],
                    "lastname": cw_inst.customer_details["LastName"],
                    "address": cw_inst.customer_details["StreetAddress"],
                    "zip": cw_inst.customer_details["ZipCode"],
                    "city": cw_inst.customer_details["City"],
                    "display_name": cw_inst.customer_details["Meter"][0]["DisplayName"],
                    "update_time": self.update_time,
                    "next_update_time": self.next_update_time,
                    "fcr_d_status": cw_inst.fcrd_state,
                    "fcr_d_state": cw_inst.fcrd_percentage,
                    "fcr_d_date": cw_inst.fcrd_timestamp,
                    "battery_charge_peak": cw_inst.battery_charge_peak,
                    "battery_discharge_peak": cw_inst.battery_discharge_peak,
                    "dso": cw_inst.battery_registration["Dso"],
                    "energy_provider": self.energy_provider,
                }
                if cw_inst.energy_data is not None:
                    resp["battery_power"] = cw_inst.battery_power
                    resp["grid_power"] = cw_inst.grid_power
                    resp["solar_power"] = cw_inst.solar_power
                    resp["battery_soc"] = cw_inst.battery_soc

                # Use self stored variant of revenue parameters as they are not always fetched
                if self.today_revenue is not None:
                    resp["revenue"] = self.today_revenue
                    resp["fees"] = self.today_fees
                    resp["tomorrow_revenue"] = self.tomorrow_revenue
                    resp["tomorrow_fees"] = self.tomorrow_fees

                if self.annual_revenue is not None:
                    resp["annual_revenue"] = self.annual_revenue
                    resp["annual_fees"] = self.annual_fees

                if use_detailed_sensors:
                    resp["total_solar_energy"] = cw_inst.total_solar_energy
                    resp["total_charging_energy"] = cw_inst.total_charging_energy
                    resp["total_discharging_energy"] = cw_inst.total_discharging_energy
                    resp["total_import_energy"] = cw_inst.total_import_energy
                    resp["total_export_energy"] = cw_inst.total_export_energy
                    time_hour = int(dt_util.now().strftime("%H"))
                    resp["spot_price"] = cw_inst.get_spot_price_excl_vat(time_hour)
                    resp["price_zone"] = cw_inst.price_zone

                return resp

        except InvalidAuth as err:
            raise ConfigEntryAuthFailed from err
        except CheckwattError as err:
            raise UpdateFailed(str(err)) from err

    async def push_to_checkwatt_rank(self, cw_inst):
        """Push data to CheckWattRank."""
        if self.today_revenue is not None:
            if (
                "Meter" in cw_inst.customer_details
                and len(cw_inst.customer_details["Meter"]) > 0
            ):
                url = "https://checkwattrank.netlify.app/.netlify/functions/publishToSheet"
                headers = {
                    "Content-Type": "application/json",
                }
                payload = {
                    "display_name": cw_inst.customer_details["Meter"][0]["DisplayName"],
                    # "display_name": "xxTESTxx",
                    "dso": cw_inst.battery_registration["Dso"],
                    "electricity_company": self.energy_provider,
                    "electricity_area": cw_inst.price_zone,
                    "installed_power": cw_inst.battery_charge_peak,
                    "today_gross_income": self.today_revenue,
                    "today_fee": self.today_fees,
                    "today_net_income": self.today_revenue - self.today_fees,
                    "reseller_id": cw_inst.customer_details["Meter"][0]["ResellerId"],
                }

                # Specify a timeout value (in seconds)
                timeout_seconds = 10

                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.post(
                            url, headers=headers, json=payload, timeout=timeout_seconds
                        ) as response:
                            response.raise_for_status()  # Raise an exception for HTTP errors
                            content_type = response.headers.get(
                                "Content-Type", ""
                            ).lower()
                            _LOGGER.debug(
                                "CheckWattRank Push Response Content-Type: %s",
                                content_type,
                            )

                            if "application/json" in content_type:
                                result = await response.json()
                                _LOGGER.debug("CheckWattRank Push Response: %s", result)
                                return True
                            elif "text/plain" in content_type:
                                result = await response.text()
                                _LOGGER.debug("CheckWattRank Push Response: %s", result)
                                return True
                            else:
                                _LOGGER.warning(
                                    "Unexpected Content-Type: %s", content_type
                                )
                                result = await response.text()
                                _LOGGER.debug("CheckWattRank Push Response: %s", result)

                    except aiohttp.ClientError as e:
                        _LOGGER.error("Error pushing data to CheckWattRank: %s", e)
                    except asyncio.TimeoutError:
                        _LOGGER.error(
                            "Request to CheckWattRank timed out after %s seconds",
                            timeout_seconds,
                        )

        return False


class CheckwattError(HomeAssistantError):
    """Base error."""


class InvalidAuth(CheckwattError):
    """Raised when invalid authentication credentials are provided."""


class APIRatelimitExceeded(CheckwattError):
    """Raised when the API rate limit is exceeded."""


class UnknownError(CheckwattError):
    """Raised when an unknown error occurs."""
