"""Support for Checkwatt sensors."""
from __future__ import annotations

import datetime
from datetime import timedelta
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CheckwattCoordinator, CheckwattResp
from .const import (
    C_ADR,
    C_CHARGE_PEAK,
    C_CITY,
    C_DISCHARGE_PEAK,
    C_FCRD_DATE,
    C_FCRD_STATE,
    C_FCRD_STATUS,
    C_NEXT_UPDATE_TIME,
    C_PRICE_ZONE,
    C_TODAY_FEE_RATE,
    C_TODAY_FEES,
    C_TODAY_GROSS,
    C_TOMORROW_FEE_RATE,
    C_TOMORROW_FEES,
    C_TOMORROW_GROSS,
    C_TOMORROW_NET,
    C_UPDATE_TIME,
    C_VAT,
    C_ZIP,
    CHECKWATT_MODEL,
    CONF_DETAILED_ATTRIBUTES,
    CONF_DETAILED_SENSORS,
    DOMAIN,
    MANUFACTURER,
)

ICON_CASH = "mdi:account-cash"
ICON_SOLAR_PANEL = "mdi:solar-power-variant-outline"
ICON_BATTERY_CHARGE = "mdi:home-battery"
ICON_BATTERY_DISCHARGE = "mdi:home-battery-outline"
ICON_ENERGY_IMPORT = "mdi:transmission-tower-export"
ICON_ENERGY_EXPORT = "mdi:transmission-tower-import"
ICON_SPOT_PRICE = "mdi:chart-line"
ICON_SPOT_PRICE_VAT = "mdi:chart-multiple"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Checkwatt sensor."""
    coordinator: CheckwattCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[CheckwattTemplateSensor] = []
    checkwatt_data: CheckwattResp = coordinator.data
    use_detailed_sensors = entry.options.get(CONF_DETAILED_SENSORS)
    use_detailed_attributes = entry.options.get(CONF_DETAILED_ATTRIBUTES)

    _LOGGER.debug("Setting up Checkwatt sensor for %s", checkwatt_data["display_name"])
    entities.append(CheckwattSensor(coordinator, use_detailed_attributes))

    if use_detailed_sensors:
        _LOGGER.debug(
            "Setting up detailed Checkwatt sensors for %s",
            checkwatt_data["display_name"],
        )
        # Add additional sensors required
        entities.append(CheckwattSolarSensor(coordinator, use_detailed_attributes))
        entities.append(
            CheckwattBatteryChargingSensor(coordinator, use_detailed_attributes)
        )
        entities.append(
            CheckwattBatteryDischargingSensor(coordinator, use_detailed_attributes)
        )
        entities.append(
            CheckwattImportEnergySensor(coordinator, use_detailed_attributes)
        )
        entities.append(
            CheckwattExportEnergySensor(coordinator, use_detailed_attributes)
        )
        entities.append(CheckwattSpotPriceSensor(coordinator, use_detailed_attributes))
        entities.append(
            CheckwattSpotPriceVATSensor(coordinator, use_detailed_attributes)
        )

    async_add_entities(entities, True)


class CheckwattTemplateSensor(CoordinatorEntity[CheckwattCoordinator], SensorEntity):
    """Representation of a generic Checkwatt sensor."""

    def __init__(
        self, coordinator: CheckwattCoordinator, use_detailed_attributes
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self.use_detailed_attributes = use_detailed_attributes
        self._id = self._coordinator.data["id"]
        self._device_model = CHECKWATT_MODEL
        self._device_name = self._coordinator.data["display_name"]

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        device_info = DeviceInfo(
            identifiers={(DOMAIN, self._id)},
            manufacturer=MANUFACTURER,
            model=self._device_model,
            name=self._device_name,
        )
        return device_info


class CheckwattSensor(CheckwattTemplateSensor):
    """Representation of a Checkwatt sensor."""

    def __init__(
        self, coordinator: CheckwattCoordinator, use_detailed_attributes
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator, use_detailed_attributes=use_detailed_attributes
        )
        self._last_updated: datetime.datetime | None = None
        self._attr_icon = ICON_CASH
        self._attr_unique_id = f'checkwattUid_{self._coordinator.data["id"]}'
        self._attr_name = f"Checkwatt {self._device_name}"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "SEK"

        self._attr_extra_state_attributes = {}
        if "address" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_ADR: self._coordinator.data["address"]}
            )
        if "zip" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_ZIP: self._coordinator.data["zip"]}
            )
        if "city" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_CITY: self._coordinator.data["city"]}
            )
        if "revenue" in self._coordinator.data and "fees" in self._coordinator.data:
            revenue = self._coordinator.data["revenue"]
            fees = self._coordinator.data["fees"]
            if self.use_detailed_attributes:  # Only show these at detailed attribues
                self._attr_extra_state_attributes[C_TODAY_GROSS] = round(revenue, 2)
                self._attr_extra_state_attributes[C_TODAY_FEES] = round(fees, 2)
                self._attr_extra_state_attributes[
                    C_TODAY_FEE_RATE
                ] = f"{round((fees / revenue) * 100, 2)} %"
        if (
            "tomorrow_revenue" in self._coordinator.data
            and "tomorrow_fees" in self._coordinator.data
        ):
            tomorrow_revenue = self._coordinator.data["tomorrow_revenue"]
            tomorrow_fees = self._coordinator.data["tomorrow_fees"]
            self._attr_extra_state_attributes[C_TOMORROW_NET] = round(
                (tomorrow_revenue - tomorrow_fees), 2
            )
            if self.use_detailed_attributes:  # Only show these at detailed attribues
                self._attr_extra_state_attributes[C_TOMORROW_GROSS] = round(
                    tomorrow_revenue, 2
                )
                self._attr_extra_state_attributes[C_TOMORROW_FEES] = round(
                    tomorrow_fees, 2
                )
                self._attr_extra_state_attributes[
                    C_TOMORROW_FEE_RATE
                ] = f"{round((tomorrow_fees / tomorrow_revenue) * 100, 2 )} %"

        if use_detailed_attributes:
            # Add extra attributes as required
            if "update_time" in self._coordinator.data:
                self._attr_extra_state_attributes.update(
                    {C_UPDATE_TIME: self._coordinator.data["update_time"]}
                )
            if "next_update_time" in self._coordinator.data:
                self._attr_extra_state_attributes.update(
                    {C_NEXT_UPDATE_TIME: self._coordinator.data["next_update_time"]}
                )
            if "fcr_d_status" in self._coordinator.data:
                self._attr_extra_state_attributes.update(
                    {C_FCRD_STATUS: self._coordinator.data["fcr_d_status"]}
                )
            if "fcr_d_state" in self._coordinator.data:
                self._attr_extra_state_attributes.update(
                    {C_FCRD_STATE: self._coordinator.data["fcr_d_state"]}
                )
            if "fcr_d_date" in self._coordinator.data:
                self._attr_extra_state_attributes.update(
                    {C_FCRD_DATE: self._coordinator.data["fcr_d_date"]}
                )
            if "battery_charge_peak" in self._coordinator.data:
                self._attr_extra_state_attributes.update(
                    {C_CHARGE_PEAK: self._coordinator.data["battery_charge_peak"]}
                )
            if "battery_discharge_peak" in self._coordinator.data:
                self._attr_extra_state_attributes.update(
                    {C_DISCHARGE_PEAK: self._coordinator.data["battery_discharge_peak"]}
                )

        self._attr_available = False

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        self._attr_available = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the states."""

        _LOGGER.debug("Updating sensor values (_handle_coordinator_update)")

        # Update the native value
        if "revenue" in self._coordinator.data and "fees" in self._coordinator.data:
            revenue = self._coordinator.data["revenue"]
            fees = self._coordinator.data["fees"]
            self._attr_native_value = round((revenue - fees), 2)
            if self.use_detailed_attributes:  # Only show these at detailed attribues
                self._attr_extra_state_attributes[C_TODAY_GROSS] = round(revenue, 2)
                self._attr_extra_state_attributes[C_TODAY_FEES] = round(fees, 2)
                self._attr_extra_state_attributes[
                    C_TODAY_FEE_RATE
                ] = f"{round((fees / revenue) * 100, 2)} %"

        # Update the normal attributes
        if (
            "tomorrow_revenue" in self._coordinator.data
            and "tomorrow_fees" in self._coordinator.data
        ):
            tomorrow_revenue = self._coordinator.data["tomorrow_revenue"]
            tomorrow_fees = self._coordinator.data["tomorrow_fees"]
            self._attr_extra_state_attributes[C_TOMORROW_NET] = round(
                (tomorrow_revenue - tomorrow_fees), 2
            )
            if self.use_detailed_attributes:  # Only show these at detailed attribues
                self._attr_extra_state_attributes[C_TOMORROW_GROSS] = round(
                    tomorrow_revenue, 2
                )
                self._attr_extra_state_attributes[C_TOMORROW_FEES] = round(
                    tomorrow_fees, 2
                )
                self._attr_extra_state_attributes[
                    C_TOMORROW_FEE_RATE
                ] = f"{round((tomorrow_fees / tomorrow_revenue) * 100, 2)} %"

        # Update the extra attributes
        if self.use_detailed_attributes:
            if "update_time" in self._coordinator.data:
                self._attr_extra_state_attributes.update(
                    {C_UPDATE_TIME: self._coordinator.data["update_time"]}
                )
            if "next_update_time" in self._coordinator.data:
                self._attr_extra_state_attributes.update(
                    {C_NEXT_UPDATE_TIME: self._coordinator.data["next_update_time"]}
                )
            if "fcr_d_status" in self._coordinator.data:
                self._attr_extra_state_attributes.update(
                    {C_FCRD_STATUS: self._coordinator.data["fcr_d_status"]}
                )
            if "fcr_d_state" in self._coordinator.data:
                self._attr_extra_state_attributes.update(
                    {C_FCRD_STATE: self._coordinator.data["fcr_d_state"]}
                )
            if "fcr_d_date" in self._coordinator.data:
                self._attr_extra_state_attributes.update(
                    {C_FCRD_DATE: self._coordinator.data["fcr_d_date"]}
                )
            if "battery_charge_peak" in self._coordinator.data:
                self._attr_extra_state_attributes.update(
                    {C_CHARGE_PEAK: self._coordinator.data["battery_charge_peak"]}
                )
            if "battery_discharge_peak" in self._coordinator.data:
                self._attr_extra_state_attributes.update(
                    {C_DISCHARGE_PEAK: self._coordinator.data["battery_discharge_peak"]}
                )
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> str | None:
        """Get the latest state value."""
        if "revenue" in self._coordinator.data and "fees" in self._coordinator.data:
            return round(
                self._coordinator.data["revenue"] - self._coordinator.data["fees"], 2
            )
        return None


class CheckwattSolarSensor(CheckwattTemplateSensor):
    """Representation of a Checkwatt Solar sensor."""

    def __init__(
        self, coordinator: CheckwattCoordinator, use_detailed_attributes
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator, use_detailed_attributes=use_detailed_attributes
        )
        self._last_updated: datetime.datetime | None = None
        self._attr_icon = ICON_SOLAR_PANEL
        self._attr_unique_id = f'checkwattUid_solar_{self._coordinator.data["id"]}'
        self._attr_name = f"Solar Energy {self._device_name}"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_available = False

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug("Solar panel energy update")
        self._attr_available = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug("Solar panel energy update via coordinator")
        self._attr_native_value = round(
            self._coordinator.data["total_solar_energy"] / 1000, 2
        )
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> str | None:
        """Get the latest state value."""
        return round(self._coordinator.data["total_solar_energy"] / 1000, 2)


class CheckwattBatteryChargingSensor(CheckwattTemplateSensor):
    """Representation of a Checkwatt Battery Charge sensor."""

    def __init__(
        self, coordinator: CheckwattCoordinator, use_detailed_attributes
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator, use_detailed_attributes=use_detailed_attributes
        )
        self._last_updated: datetime.datetime | None = None
        self._attr_icon = ICON_BATTERY_CHARGE
        self._attr_unique_id = f'checkwattUid_charging_{self._coordinator.data["id"]}'
        self._attr_name = f"Battery Charging Energy {self._device_name}"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_available = False

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug("Battery charging energy update")
        self._attr_available = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug("Battery charging energy update via coordinator")
        self._attr_native_value = round(
            self._coordinator.data["total_charging_energy"] / 1000, 2
        )
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> str | None:
        """Get the latest state value."""
        return round(self._coordinator.data["total_charging_energy"] / 1000, 2)


class CheckwattBatteryDischargingSensor(CheckwattTemplateSensor):
    """Representation of a Checkwatt Battery Discharge sensor."""

    def __init__(
        self, coordinator: CheckwattCoordinator, use_detailed_attributes
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator, use_detailed_attributes=use_detailed_attributes
        )
        self._last_updated: datetime.datetime | None = None
        self._attr_icon = ICON_BATTERY_DISCHARGE
        self._attr_unique_id = (
            f'checkwattUid_discharging_{self._coordinator.data["id"]}'
        )
        self._attr_name = f"Battery Discharging Energy {self._device_name}"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_available = False

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug("Battery discharging energy update")
        self._attr_available = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug("Battery discharging energy update via coordinator")
        self._attr_native_value = round(
            self._coordinator.data["total_discharging_energy"] / 1000, 2
        )
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> str | None:
        """Get the latest state value."""
        return round(self._coordinator.data["total_discharging_energy"] / 1000, 2)


class CheckwattImportEnergySensor(CheckwattTemplateSensor):
    """Representation of a Checkwatt Import Energy sensor."""

    def __init__(
        self, coordinator: CheckwattCoordinator, use_detailed_attributes
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator, use_detailed_attributes=use_detailed_attributes
        )
        self._last_updated: datetime.datetime | None = None
        self._attr_icon = ICON_ENERGY_IMPORT
        self._attr_unique_id = f'checkwattUid_import_{self._coordinator.data["id"]}'
        self._attr_name = f"Import Energy {self._device_name}"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_available = False

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug("Import energy update")
        self._attr_available = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug("Import energy update via coordinator")
        self._attr_native_value = round(
            self._coordinator.data["total_import_energy"] / 1000, 2
        )
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> str | None:
        """Get the latest state value."""
        return round(self._coordinator.data["total_import_energy"] / 1000, 2)


class CheckwattExportEnergySensor(CheckwattTemplateSensor):
    """Representation of a Checkwatt Export Energy sensor."""

    def __init__(
        self, coordinator: CheckwattCoordinator, use_detailed_attributes
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator, use_detailed_attributes=use_detailed_attributes
        )
        self._last_updated: datetime.datetime | None = None
        self._attr_icon = ICON_ENERGY_EXPORT
        self._attr_unique_id = f'checkwattUid_export_{self._coordinator.data["id"]}'
        self._attr_name = f"Export Energy {self._device_name}"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_available = False

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug("Export energy update")
        self._attr_available = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug("Export energy update via coordinator")
        self._attr_native_value = round(
            self._coordinator.data["total_export_energy"] / 1000, 2
        )
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> str | None:
        """Get the latest state value."""
        return round(self._coordinator.data["total_export_energy"] / 1000, 2)


class CheckwattSpotPriceSensor(CheckwattTemplateSensor):
    """Representation of a Checkwatt Spot Price sensor."""

    def __init__(
        self, coordinator: CheckwattCoordinator, use_detailed_attributes
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator, use_detailed_attributes=use_detailed_attributes
        )
        self._last_updated: datetime.datetime | None = None
        self._attr_icon = ICON_SPOT_PRICE
        self._attr_unique_id = f'checkwattUid_spot_price_{self._coordinator.data["id"]}'
        self._attr_name = f"Spot Price {self._device_name}"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "SEK/kWh"
        self._attr_available = False
        self._attr_extra_state_attributes = {}

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug("Spot Price update")
        if "price_zone" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_PRICE_ZONE: self._coordinator.data["price_zone"]}
            )
        self._attr_available = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug("Spot Price update via coordinator")
        self._attr_native_value = round(self._coordinator.data["spot_price"], 3)
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> str | None:
        """Get the latest state value."""
        return round(self._coordinator.data["spot_price"], 3)


class CheckwattSpotPriceVATSensor(CheckwattTemplateSensor):
    """Representation of a Checkwatt Spot Price sensor."""

    def __init__(
        self, coordinator: CheckwattCoordinator, use_detailed_attributes
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator, use_detailed_attributes=use_detailed_attributes
        )
        self._last_updated: datetime.datetime | None = None
        self._attr_icon = ICON_SPOT_PRICE_VAT
        self._attr_unique_id = (
            f'checkwattUid_spot_price_vat_{self._coordinator.data["id"]}'
        )
        self._attr_name = f"Spot Price VAT {self._device_name}"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "SEK/kWh"
        self._attr_available = False
        self._attr_extra_state_attributes = {}

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug("Spot Price VAT update")
        if "price_zone" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_PRICE_ZONE: self._coordinator.data["price_zone"]}
            )
            self._attr_extra_state_attributes.update({C_VAT: "25%"})
        self._attr_available = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug("Spot Price VAT update via coordinator")
        self._attr_native_value = round(self._coordinator.data["spot_price"] * 1.25, 3)
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> str | None:
        """Get the latest state value."""
        return round(self._coordinator.data["spot_price"] * 1.25, 3)
