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
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    BASIC_TEST,
    CONF_CM10_SENSOR,
    CONF_CWR_NAME,
    CONF_POWER_SENSORS,
    CONF_PUSH_CW_TO_RANK,
    CONF_UPDATE_INTERVAL_ALL,
    CONF_UPDATE_INTERVAL_MONETARY,
    DOMAIN,
    EVENT_SIGNAL_FCRD,
    INTEGRATION_NAME,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.EVENT]


class CheckwattResp(TypedDict):
    """API response."""

    id: str
    firstname: str
    lastname: str
    address: str
    zip: str
    city: str
    display_name: str
    dso: str
    energy_provider: str

    battery_power: float
    grid_power: float
    solar_power: float
    battery_soc: float
    charge_peak_ac: float
    charge_peak_dc: float
    discharge_peak_ac: float
    discharge_peak_dc: float

    today_net_revenue: float
    monthly_net_revenue: float
    annual_net_revenue: float
    month_estimate: float
    daily_average: float

    update_time: str
    next_update_time: str

    total_solar_energy: float
    total_charging_energy: float
    total_discharging_energy: float
    total_import_energy: float
    total_export_energy: float
    spot_price: float
    price_zone: str

    cm10_status: str
    cm10_version: str
    fcr_d_status: str
    fcr_d_info: str
    fcr_d_date: str


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


async def getPeakData(cw_inst):
    """Extract PeakAcDC Power."""
    charge_peak_ac = 0
    charge_peak_dc = 0
    discharge_peak_ac = 0
    discharge_peak_dc = 0

    if cw_inst is None:
        return (None, None, None, None)

    if cw_inst.customer_details is None:
        return (None, None, None, None)

    if "Meter" in cw_inst.customer_details:
        for meter in cw_inst.customer_details["Meter"]:
            if "InstallationType" in meter:
                if meter["InstallationType"] == "Charging":
                    if "PeakAcKw" in meter and "PeakDcKw" in meter:
                        charge_peak_ac += meter["PeakAcKw"]
                        charge_peak_dc += meter["PeakDcKw"]
                if meter["InstallationType"] == "Discharging":
                    if "PeakAcKw" in meter and "PeakDcKw" in meter:
                        discharge_peak_ac += meter["PeakAcKw"]
                        discharge_peak_dc += meter["PeakDcKw"]

    return (charge_peak_ac, charge_peak_dc, discharge_peak_ac, discharge_peak_dc)


class CheckwattCoordinator(DataUpdateCoordinator[CheckwattResp]):
    """Data update coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=CONF_UPDATE_INTERVAL_ALL),
        )
        self._entry = entry
        self.last_cw_rank_push = None
        self.is_boot = True
        self.energy_provider = None
        self.fcrd_state = None
        self.fcrd_info = None
        self.fcrd_timestamp = None
        self._id = None
        self.update_all = 0
        self.random_offset = random.randint(0, 14)
        self.fcrd_today_net_revenue = None
        self.fcrd_month_net_revenue = None
        self.fcrd_month_net_estimate = None
        self.fcrd_daily_net_average = None
        self.fcrd_year_net_revenue = None

    @property
    def entry_id(self) -> str:
        """Return entry ID."""
        return self._entry.entry_id

    async def _async_update_data(self) -> CheckwattResp:  # noqa: C901
        """Fetch the latest data from the source."""

        try:
            username = self._entry.data.get(CONF_USERNAME)
            password = self._entry.data.get(CONF_PASSWORD)
            use_power_sensors = self._entry.options.get(CONF_POWER_SENSORS)
            push_to_cw_rank = self._entry.options.get(CONF_PUSH_CW_TO_RANK)
            use_cm10_sensor = self._entry.options.get(CONF_CM10_SENSOR)
            cwr_name = self._entry.options.get(CONF_CWR_NAME)

            async with CheckwattManager(
                username, password, INTEGRATION_NAME
            ) as cw_inst:
                if not await cw_inst.login():
                    _LOGGER.error("Failed to login, abort update")
                    raise UpdateFailed("Failed to login")

                if not await cw_inst.get_customer_details():
                    _LOGGER.error("Failed to obtain customer details, abort update")
                    raise UpdateFailed("Unknown error get_customer_details")

                if not await cw_inst.get_energy_flow():
                    _LOGGER.error("Failed to get energy flows, abort update")
                    raise UpdateFailed("Unknown error get_energy_flow")

                if use_cm10_sensor:
                    if not await cw_inst.get_meter_status():
                        _LOGGER.error("Failed to obtain meter details, abort update")
                        raise UpdateFailed("Unknown error get_meter_status")

                # Only fetch some parameters every 15 min
                if self.update_all == 0 and not self.is_boot:
                    self.update_all = CONF_UPDATE_INTERVAL_MONETARY
                    _LOGGER.debug("Fetching daily revenue")
                    if not await cw_inst.get_fcrd_today_net_revenue():
                        raise UpdateFailed("Unknown error get_fcrd_revenue")

                    _LOGGER.debug("Fetching monthly revenue")
                    if not await cw_inst.get_fcrd_month_net_revenue():
                        raise UpdateFailed("Unknown error get_revenue_month")

                    _LOGGER.debug("Fetching annual revenue")
                    if not await cw_inst.get_fcrd_year_net_revenue():
                        raise UpdateFailed("Unknown error get_revenue_year")

                    self.fcrd_today_net_revenue = cw_inst.fcrd_today_net_revenue
                    self.fcrd_month_net_revenue = cw_inst.fcrd_month_net_revenue
                    self.fcrd_month_net_estimate = cw_inst.fcrd_month_net_estimate
                    self.fcrd_daily_net_average = cw_inst.fcrd_daily_net_average
                    self.fcrd_year_net_revenue = cw_inst.fcrd_year_net_revenue

                if not self.is_boot:
                    self.update_all -= 1

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

                    # Store fcrd_state at boot, used to spark event
                    self.fcrd_state = cw_inst.fcrd_state
                    self._id = cw_inst.customer_details["Id"]
                (
                    charge_peak_ac,
                    charge_peak_dc,
                    discharge_peak_ac,
                    discharge_peak_dc,
                ) = await getPeakData(cw_inst)

                # Price Zone is used both as Detailed Sensor and by Push to CheckWattRank
                if push_to_cw_rank or use_power_sensors:
                    if not await cw_inst.get_price_zone():
                        raise UpdateFailed("Unknown error get_price_zone")
                if use_power_sensors:
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
                        if await self.push_to_checkwatt_rank(
                            cw_inst, charge_peak_ac, cwr_name
                        ):
                            self.last_cw_rank_push = dt_util.now()

                resp: CheckwattResp = {
                    "id": cw_inst.customer_details["Id"],
                    "firstname": cw_inst.customer_details["FirstName"],
                    "lastname": cw_inst.customer_details["LastName"],
                    "address": cw_inst.customer_details["StreetAddress"],
                    "zip": cw_inst.customer_details["ZipCode"],
                    "city": cw_inst.customer_details["City"],
                    "display_name": cw_inst.customer_details["Meter"][0]["DisplayName"],
                    "dso": cw_inst.battery_registration["Dso"],
                    "energy_provider": self.energy_provider,
                }
                if cw_inst.energy_data is not None:
                    resp["battery_power"] = cw_inst.battery_power
                    resp["grid_power"] = cw_inst.grid_power
                    resp["solar_power"] = cw_inst.solar_power
                    resp["battery_soc"] = cw_inst.battery_soc
                    resp["charge_peak_ac"] = charge_peak_ac
                    resp["charge_peak_dc"] = charge_peak_dc
                    resp["discharge_peak_ac"] = discharge_peak_ac
                    resp["discharge_peak_dc"] = discharge_peak_dc

                # Use self stored variant of revenue parameters as they are not always fetched
                if self.fcrd_today_net_revenue is not None:
                    resp["today_net_revenue"] = self.fcrd_today_net_revenue
                if self.fcrd_month_net_revenue is not None:
                    resp["monthly_net_revenue"] = self.fcrd_month_net_revenue
                    resp["month_estimate"] = self.fcrd_month_net_estimate
                    resp["daily_average"] = self.fcrd_daily_net_average
                if self.fcrd_year_net_revenue is not None:
                    resp["annual_net_revenue"] = self.fcrd_year_net_revenue

                update_time = dt_util.now().strftime("%Y-%m-%d %H:%M:%S")
                next_update = dt_util.now() + timedelta(
                    minutes=CONF_UPDATE_INTERVAL_MONETARY
                )
                next_update_time = next_update.strftime("%Y-%m-%d %H:%M:%S")
                resp["update_time"] = update_time
                resp["next_update_time"] = next_update_time

                if use_power_sensors:
                    resp["total_solar_energy"] = cw_inst.total_solar_energy
                    resp["total_charging_energy"] = cw_inst.total_charging_energy
                    resp["total_discharging_energy"] = cw_inst.total_discharging_energy
                    resp["total_import_energy"] = cw_inst.total_import_energy
                    resp["total_export_energy"] = cw_inst.total_export_energy
                    resp["spot_price"] = cw_inst.get_spot_price_excl_vat(
                        int(dt_util.now().strftime("%H"))
                    )
                    resp["price_zone"] = cw_inst.price_zone

                if cw_inst.meter_data is not None and use_cm10_sensor:
                    if cw_inst.meter_status == "offline":
                        resp["cm10_status"] = "Offline"
                    elif cw_inst.meter_under_test:
                        resp["cm10_status"] = "Test Pending"
                    else:
                        resp["cm10_status"] = "Active"

                    resp["cm10_version"] = cw_inst.meter_version
                    resp["fcr_d_status"] = cw_inst.fcrd_state
                    resp["fcr_d_info"] = cw_inst.fcrd_info
                    resp["fcr_d_date"] = cw_inst.fcrd_timestamp

                # Check if FCR-D State has changed and dispatch it ACTIVATED/ DEACTIVATED
                old_state = self.fcrd_state
                new_state = cw_inst.fcrd_state

                # During test, toggle (every minute)
                if BASIC_TEST is True:
                    if old_state == "ACTIVATED":
                        new_state = "DEACTIVATE"
                    if old_state == "DEACTIVATE":
                        new_state = "FAIL ACTIVATION"
                    if old_state == "FAIL ACTIVATION":
                        new_state = "ACTIVATED"

                if old_state != new_state:
                    signal_payload = {
                        "signal": EVENT_SIGNAL_FCRD,
                        "data": {
                            "current_fcrd": {
                                "state": old_state,
                                "info": self.fcrd_info,
                                "date": self.fcrd_timestamp,
                            },
                            "new_fcrd": {
                                "state": new_state,
                                "info": cw_inst.fcrd_info,
                                "date": cw_inst.fcrd_timestamp,
                            },
                        },
                    }

                    # Dispatch it to subscribers
                    async_dispatcher_send(
                        self.hass,
                        f"checkwatt_{self._id}_signal",
                        signal_payload,
                    )

                    # Update self to discover next change
                    self.fcrd_state = new_state
                    self.fcrd_info = cw_inst.fcrd_info
                    self.fcrd_timestamp = cw_inst.fcrd_timestamp

                return resp

        except InvalidAuth as err:
            raise ConfigEntryAuthFailed from err
        except CheckwattError as err:
            raise UpdateFailed(str(err)) from err

    async def push_to_checkwatt_rank(self, cw_inst, charge_peak, cwr_name):
        """Push data to CheckWattRank."""
        if self.fcrd_today_net_revenue is not None:
            if (
                "Meter" in cw_inst.customer_details
                and len(cw_inst.customer_details["Meter"]) > 0
            ):
                url = "https://checkwattrank.netlify.app/.netlify/functions/publishToSheet"
                headers = {
                    "Content-Type": "application/json",
                }
                payload = {
                    "dso": cw_inst.battery_registration["Dso"],
                    "electricity_company": self.energy_provider,
                    "electricity_area": cw_inst.price_zone,
                    "installed_power": charge_peak,
                    "today_gross_income": 0,
                    "today_fee": 0,
                    "today_net_income": self.fcrd_today_net_revenue,
                    "reseller_id": cw_inst.customer_details["Meter"][0]["ResellerId"],
                    "reporter": "HomeAssistantV2",
                }
                if BASIC_TEST:
                    payload["display_name"] = "xxTESTxx"
                elif cwr_name != "":
                    payload["display_name"] = cwr_name
                else:
                    payload["display_name"] = cw_inst.customer_details["Meter"][0][
                        "DisplayName"
                    ]

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
