"""The CheckWatt integration."""
from __future__ import annotations

import asyncio
from datetime import time, timedelta
import logging
import random
import re
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
    CONF_DETAILED_SENSORS,
    CONF_PUSH_CW_TO_RANK,
    CONF_UPDATE_INTERVAL,
    CONF_UPDATE_INTERVAL_FCRD,
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
    revenue: float
    fees: float
    battery_charge_peak: float
    battery_discharge_peak: float
    tomorrow_revenue: float
    tomorrow_fees: float
    update_time: str
    next_update_time: str
    fcr_d_status: str
    fcr_d_info: str
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
    cm10_status: str
    cm10_version: str
    charge_peak_ac: float
    charge_peak_dc: float
    discharge_peak_ac: float
    discharge_peak_dc: float


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


def extract_fcrd_status(cw_inst):
    """Extract status from data and logbook."""

    if cw_inst.customer_details is None:
        return (None, None, None, None)

    pattern = re.compile(
        r"\[ FCR-D (ACTIVATED|DEACTIVATE|FAIL ACTIVATION) \](?:.*?(\d+,\d+/\d+,\d+/\d+,\d+ %))?(?:\s*(.*?))?(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
    )
    for entry in cw_inst.logbook_entries:
        match = pattern.search(entry)
        if match:
            fcrd_state = match.group(1)
            fcrd_percentage = (
                match.group(2)
                if fcrd_state in ["ACTIVATED", "FAIL ACTIVATION"]
                else None
            )
            error_info = match.group(3) if fcrd_state == "DEACTIVATE" else None
            fcrd_timestamp = match.group(4)
            if fcrd_percentage is not None:
                fcrd_info = fcrd_percentage
            elif error_info is not None:
                fcrd_info = error_info
            else:
                fcrd_info = None
            break

    return (fcrd_state, fcrd_info, fcrd_timestamp)


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
        self.fcrd_state = None
        self.fcrd_info = None
        self.fcrd_timestamp = None
        self._id = None
        self.update_no = 0
        _LOGGER.debug("Fetching annual revenue at 3:%02d am", self.random_offset)

    @property
    def entry_id(self) -> str:
        """Return entry ID."""
        return self._entry.entry_id

    async def _async_update_data(self) -> CheckwattResp:  # noqa: C901
        """Fetch the latest data from the source."""

        try:
            username = self._entry.data.get(CONF_USERNAME)
            password = self._entry.data.get(CONF_PASSWORD)
            use_detailed_sensors = self._entry.options.get(CONF_DETAILED_SENSORS)
            push_to_cw_rank = self._entry.options.get(CONF_PUSH_CW_TO_RANK)
            use_cm10_sensor = self._entry.options.get(CONF_CM10_SENSOR)

            async with CheckwattManager(
                username, password, INTEGRATION_NAME
            ) as cw_inst:
                if not await cw_inst.login():
                    _LOGGER.error("Failed to login, abort update")
                    raise UpdateFailed("Failed to login")
                if not await cw_inst.get_customer_details():
                    _LOGGER.error("Failed to obtain customer details, abort update")
                    raise UpdateFailed("Unknown error get_customer_details")
                if use_cm10_sensor:
                    if not await cw_inst.get_meter_status():
                        _LOGGER.error("Failed to obtain meter details, abort update")
                        raise UpdateFailed("Unknown error get_meter_status")
                if not await cw_inst.get_energy_flow():
                    _LOGGER.error("Failed to get energy flows, abort update")
                    raise UpdateFailed("Unknown error get_energy_flow")

                (
                    fcrd_state,
                    fcrd_info,
                    fcrd_timestamp,
                ) = extract_fcrd_status(cw_inst)

                # Prevent slow funcion to be called at boot.
                # The revenue sensors will be updated after ca 1 min
                self.update_no += 1
                if self.update_no > 2:
                    self.is_boot = False
                if self.is_boot:
                    if (
                        "Meter" in cw_inst.customer_details
                        and len(cw_inst.customer_details["Meter"]) > 0
                        and "ElhandelsbolagId" in cw_inst.customer_details["Meter"][0]
                    ):
                        self.energy_provider = await cw_inst.get_energy_trading_company(
                            cw_inst.customer_details["Meter"][0]["ElhandelsbolagId"]
                        )

                    # Store fcrd_state at boot, used to spark event
                    self.fcrd_state = fcrd_state
                    self._id = cw_inst.customer_details["Id"]

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
                    "fcr_d_status": fcrd_state,
                    "fcr_d_info": fcrd_info,
                    "fcr_d_date": fcrd_timestamp,
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
                    (
                        charge_peak_ac,
                        charge_peak_dc,
                        discharge_peak_ac,
                        discharge_peak_dc,
                    ) = await getPeakData(cw_inst)
                    resp["charge_peak_ac"] = charge_peak_ac
                    resp["charge_peak_dc"] = charge_peak_dc
                    resp["discharge_peak_ac"] = discharge_peak_ac
                    resp["discharge_peak_dc"] = discharge_peak_dc

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

                if cw_inst.meter_data is not None and use_cm10_sensor:
                    if cw_inst.meter_status == "offline":
                        resp["cm10_status"] = "Offline"
                    elif cw_inst.meter_under_test:
                        resp["cm10_status"] = "Test Pending"
                    else:
                        resp["cm10_status"] = "Active"

                    resp["cm10_version"] = cw_inst.meter_version

                # Check if FCR-D State has changed and dispatch it ACTIVATED/ DEACTIVATED
                old_state = self.fcrd_state
                new_state = fcrd_state

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
                                "info": fcrd_info,
                                "date": fcrd_timestamp,
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
                    self.fcrd_info = fcrd_info
                    self.fcrd_timestamp = fcrd_timestamp

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
                    "dso": cw_inst.battery_registration["Dso"],
                    "electricity_company": self.energy_provider,
                    "electricity_area": cw_inst.price_zone,
                    "installed_power": cw_inst.battery_charge_peak,
                    "today_gross_income": self.today_revenue,
                    "today_fee": self.today_fees,
                    "today_net_income": self.today_revenue - self.today_fees,
                    "reseller_id": cw_inst.customer_details["Meter"][0]["ResellerId"],
                }
                if BASIC_TEST:
                    payload["display_name"] = "xxTESTxx"
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
