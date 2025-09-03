"""The CheckWatt integration."""

from __future__ import annotations

from datetime import time, timedelta
import logging
import random
from typing import TypedDict

from pycheckwatt import CheckwattManager, CheckWattRankManager
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import config_validation as cv
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

UPDATE_HISTORY_SERVICE_NAME = "update_history"
UPDATE_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Required("start_date"): cv.date,
        vol.Required("end_date"): cv.date,
    }
)

PUSH_CWR_SERVICE_NAME = "push_checkwatt_rank"
PUSH_CWR_SCHEMA = None


CHECKWATTRANK_REPORTER = "HomeAssistantV2"


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
    monthly_grid_peak_power: float

    today_net_revenue: float
    tomorrow_net_revenue: float
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
    reseller_id: int


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

    async def update_history_items(call: ServiceCall) -> ServiceResponse:
        """Fetch historical data from EIB and Update CheckWattRank."""
        start_date = call.data["start_date"]
        end_date = call.data["end_date"]
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        _LOGGER.debug(
            "Calling update_history service with start date: %s and end date %s",
            start_date_str,
            end_date_str,
        )
        username = entry.data.get(CONF_USERNAME)
        password = entry.data.get(CONF_PASSWORD)
        cwr_name = entry.options.get(CONF_CWR_NAME)
        status = None
        stored_items = 0
        total_items = 0
        async with CheckwattManager(username, password, INTEGRATION_NAME) as cw:
            try:
                # Login to EnergyInBalance
                if await cw.login():
                    # Fetch customer detail
                    if not await cw.get_customer_details():
                        _LOGGER.error("Failed to fetch customer details")
                        return {
                            "status": "Failed to fetch customer details",
                        }

                    if not await cw.get_price_zone():
                        _LOGGER.error("Failed to fetch prize zone")
                        return {
                            "status": "Failed to fetch prize zone",
                        }

                    hd = await cw.fetch_and_return_net_revenue(
                        start_date_str, end_date_str
                    )
                    if hd is None:
                        _LOGGER.error("Failed to fetch revenue")
                        return {
                            "status": "Failed to fetch revenue",
                        }

                    energy_provider = await cw.get_energy_trading_company(
                        cw.energy_provider_id
                    )

                    async with CheckWattRankManager() as cwr:
                        dso = ""
                        if cw.battery_registration is not None:
                            if "Dso" in cw.battery_registration:
                                dso = cw.battery_registration["Dso"]

                        (
                            status,
                            stored_items,
                            total_items,
                        ) = await cwr.push_history_to_checkwatt_rank(
                            display_name=(
                                cwr_name if cwr_name != "" else cw.display_name
                            ),
                            dso=dso,
                            electricity_company=energy_provider,
                            electricity_area=cw.price_zone,
                            installed_power=min(
                                cw.battery_charge_peak_ac,
                                cw.battery_discharge_peak_ac,
                            ),
                            reseller_id=cw.reseller_id,
                            reporter=CHECKWATTRANK_REPORTER,
                            historical_data=hd,
                        )

                else:
                    status = "Failed to login."

            except InvalidAuth as err:
                raise ConfigEntryAuthFailed from err

            except CheckwattError as err:
                status = f"Failed to update CheckWattRank: {err}"

        return {
            "start_date": start_date_str,
            "end_date": end_date_str,
            "status": status,
            "stored_items": stored_items,
            "total_items": total_items,
        }

    async def push_cwr(call: ServiceCall) -> ServiceResponse:
        """Push data to CheckWattRank."""
        username = entry.data.get(CONF_USERNAME)
        password = entry.data.get(CONF_PASSWORD)
        cwr_name = entry.options.get(CONF_CWR_NAME)
        status = None
        async with CheckwattManager(username, password, INTEGRATION_NAME) as cw:
            try:
                # Login to EnergyInBalance
                if await cw.login():
                    # Fetch customer detail
                    if not await cw.get_customer_details():
                        _LOGGER.error("Failed to fetch customer details")
                        return {
                            "status": "Failed to fetch customer details",
                        }

                    if not await cw.get_price_zone():
                        _LOGGER.error("Failed to fetch prize zone")
                        return {
                            "status": "Failed to fetch prize zone",
                        }

                    if not await cw.get_fcrd_today_net_revenue():
                        raise UpdateFailed("Unknown error get_fcrd_revenue")

                    display_name = cwr_name if cwr_name != "" else cw.display_name
                    if await push_to_checkwatt_rank(
                        cw, display_name, cw.fcrd_today_net_revenue
                    ):
                        status = "Data successfully sent to CheckWattRank"
                    else:
                        status = "Failed to update to CheckWattRank"

                else:
                    status = "Failed to login."

            except InvalidAuth as err:
                raise ConfigEntryAuthFailed from err

            except CheckwattError as err:
                status = f"Failed to update CheckWattRank: {err}"

        return {
            "result": status,
        }

    hass.services.async_register(
        DOMAIN,
        UPDATE_HISTORY_SERVICE_NAME,
        update_history_items,
        schema=UPDATE_HISTORY_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        PUSH_CWR_SERVICE_NAME,
        push_cwr,
        schema=PUSH_CWR_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def push_to_checkwatt_rank(cw_inst, cwr_name, today_net_income):
    """Push data to CheckWattRank."""
    if cw_inst.fcrd_today_net_revenue is not None:
        energy_provider = await cw_inst.get_energy_trading_company(
            cw_inst.energy_provider_id
        )
        async with CheckWattRankManager() as cwr:
            dso = ""
            if cw_inst.battery_registration is not None:
                if "Dso" in cw_inst.battery_registration:
                    dso = cw_inst.battery_registration["Dso"]
            if await cwr.push_to_checkwatt_rank(
                display_name=(cwr_name if cwr_name != "" else cw_inst.display_name),
                dso=dso,
                electricity_company=energy_provider,
                electricity_area=cw_inst.price_zone,
                installed_power=min(
                    cw_inst.battery_charge_peak_ac, cw_inst.battery_discharge_peak_ac
                ),
                today_net_income=today_net_income,
                reseller_id=cw_inst.reseller_id,
                reporter=CHECKWATTRANK_REPORTER,
            ):
                return True
    return False


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
        self.fcrd_tomorrow_net_revenue = None
        self.fcrd_month_net_revenue = None
        self.fcrd_month_net_estimate = None
        self.fcrd_daily_net_average = None
        self.fcrd_year_net_revenue = None
        self.monthly_grid_peak_power = None

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

                    _LOGGER.debug("Fetching montly peak power")
                    if not await cw_inst.get_battery_month_peak_effect():
                        raise UpdateFailed(
                            "Unknown error get_battery_month_peak_effect"
                        )

                    self.fcrd_today_net_revenue = cw_inst.fcrd_today_net_revenue
                    self.fcrd_tomorrow_net_revenue = cw_inst.fcrd_tomorrow_net_revenue
                    self.fcrd_month_net_revenue = cw_inst.fcrd_month_net_revenue
                    self.fcrd_month_net_estimate = cw_inst.fcrd_month_net_estimate
                    self.fcrd_daily_net_average = cw_inst.fcrd_daily_net_average
                    self.fcrd_year_net_revenue = cw_inst.fcrd_year_net_revenue
                    self.monthly_grid_peak_power = cw_inst.month_peak_effect

                if not self.is_boot:
                    self.update_all -= 1

                if self.is_boot:
                    self.is_boot = False
                    self.energy_provider = await cw_inst.get_energy_trading_company(
                        cw_inst.energy_provider_id
                    )

                    # Store fcrd_state at boot, used to spark event
                    self.fcrd_state = cw_inst.fcrd_state
                    self._id = cw_inst.customer_details["Id"]

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
                        >= time(11, self.random_offset)  # Wait until 11am + 0-14 min
                        and dt_util.start_of_local_day(dt_util.now())
                        != dt_util.start_of_local_day(self.last_cw_rank_push)
                    ):
                        if self.fcrd_today_net_revenue is not None:
                            _LOGGER.debug("Pushing to CheckWattRank")
                            if await push_to_checkwatt_rank(
                                cw_inst, cwr_name, self.fcrd_today_net_revenue
                            ):
                                self.last_cw_rank_push = dt_util.now()

                resp: CheckwattResp = {
                    "id": cw_inst.customer_details["Id"],
                    "firstname": cw_inst.customer_details["FirstName"],
                    "lastname": cw_inst.customer_details["LastName"],
                    "address": cw_inst.customer_details["StreetAddress"],
                    "zip": cw_inst.customer_details["ZipCode"],
                    "city": cw_inst.customer_details["City"],
                    "display_name": cw_inst.display_name,
                    "energy_provider": self.energy_provider,
                    "reseller_id": cw_inst.reseller_id,
                }
                if cw_inst.battery_registration is not None:
                    if "Dso" in cw_inst.battery_registration:
                        resp["dso"] = cw_inst.battery_registration["Dso"]
                if cw_inst.energy_data is not None:
                    resp["battery_power"] = cw_inst.battery_power
                    resp["grid_power"] = cw_inst.grid_power
                    resp["solar_power"] = cw_inst.solar_power
                    resp["battery_soc"] = cw_inst.battery_soc
                    resp["charge_peak_ac"] = cw_inst.battery_charge_peak_ac
                    resp["charge_peak_dc"] = cw_inst.battery_charge_peak_dc
                    resp["discharge_peak_ac"] = cw_inst.battery_discharge_peak_ac
                    resp["discharge_peak_dc"] = cw_inst.battery_discharge_peak_dc
                    resp["monthly_grid_peak_power"] = self.monthly_grid_peak_power

                # Use self stored variant of revenue parameters as they are not always fetched
                if self.fcrd_today_net_revenue is not None:
                    resp["today_net_revenue"] = self.fcrd_today_net_revenue
                    resp["tomorrow_net_revenue"] = self.fcrd_tomorrow_net_revenue
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


class CheckwattError(HomeAssistantError):
    """Base error."""


class InvalidAuth(CheckwattError):
    """Raised when invalid authentication credentials are provided."""


class APIRatelimitExceeded(CheckwattError):
    """Raised when the API rate limit is exceeded."""


class UnknownError(CheckwattError):
    """Raised when an unknown error occurs."""
