"""Support for CheckWatt sensors."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
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
    ATTRIBUTION,
    C_ADR,
    C_ANNUAL_FEE_RATE,
    C_ANNUAL_FEES,
    C_ANNUAL_GROSS,
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

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)

CHECKWATT_MONETARY_SENSORS: dict[str, SensorEntityDescription] = {
    "daily": SensorEntityDescription(
        key="daily_yield",
        name="CheckWatt Daily Yield",
        icon="mdi:account-cash",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="SEK",
        state_class=SensorStateClass.TOTAL,
        translation_key="daily_yield_sensor",
    ),
    "annual": SensorEntityDescription(
        key="annual_yield",
        name="CheckWatt Annual Yield",
        icon="mdi:account-cash-outline",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="SEK",
        state_class=SensorStateClass.TOTAL,
        translation_key="annual_yield_sensor",
    ),
}


CHECKWATT_ENERGY_SENSORS: dict[str, SensorEntityDescription] = {
    "total_solar_energy": SensorEntityDescription(
        key="solar",
        name="Solar Energy",
        icon="mdi:solar-power-variant-outline",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="solar_sensor",
    ),
    "total_charging_energy": SensorEntityDescription(
        key="charging",
        name="Battery Charging Energy",
        icon="mdi:home-battery",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="charging_sensor",
    ),
    "total_discharging_energy": SensorEntityDescription(
        key="discharging",
        name="Battery Discharging Energy",
        icon="mdi:home-battery-outline",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="discharging_sensor",
    ),
    "total_import_energy": SensorEntityDescription(
        key="import",
        name="Import Energy",
        icon="mdi:transmission-tower-export",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="import_sensor",
    ),
    "total_export_energy": SensorEntityDescription(
        key="export",
        name="Export Energy",
        icon="mdi:transmission-tower-import",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key="export_sensor",
    ),
}


CHECKWATT_SPOTPRICE_SENSORS: dict[str, SensorEntityDescription] = {
    "excl_vat": SensorEntityDescription(
        key="spot_price",
        name="Spot Price",
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="SEK/kWh",
        state_class=SensorStateClass.TOTAL,
        translation_key="spot_price_sensor",
    ),
    "inc_vat": SensorEntityDescription(
        key="spot_price_vat",
        name="Spot Price VAT",
        icon="mdi:chart-multiple",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="SEK/kWh",
        state_class=SensorStateClass.TOTAL,
        translation_key="spot_price_vat_sensor",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the CheckWatt sensor."""
    coordinator: CheckwattCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[AbstractCheckwattSensor] = []
    checkwatt_data: CheckwattResp = coordinator.data
    use_detailed_sensors = entry.options.get(CONF_DETAILED_SENSORS)
    use_detailed_attributes = entry.options.get(CONF_DETAILED_ATTRIBUTES)

    _LOGGER.debug("Setting up CheckWatt sensor for %s", checkwatt_data["display_name"])
    for key, description in CHECKWATT_MONETARY_SENSORS.items():
        if key == "daily":
            entities.append(
                CheckwattSensor(coordinator, description, use_detailed_attributes)
            )
        elif key == "annual":
            entities.append(
                CheckwattAnnualSensor(coordinator, description, use_detailed_attributes)
            )

    if use_detailed_sensors:
        _LOGGER.debug(
            "Setting up detailed CheckWatt sensors for %s",
            checkwatt_data["display_name"],
        )
        for data_key, description in CHECKWATT_ENERGY_SENSORS.items():
            entities.append(CheckwattEnergySensor(coordinator, description, data_key))
        for vat_key, description in CHECKWATT_SPOTPRICE_SENSORS.items():
            entities.append(CheckwattSpotPriceSensor(coordinator, description, vat_key))

    async_add_entities(entities, True)


class AbstractCheckwattSensor(CoordinatorEntity[CheckwattCoordinator], SensorEntity):
    """Abstract class for an CheckWatt sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CheckwattCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._device_model = CHECKWATT_MODEL
        self._device_name = coordinator.data["display_name"]
        self._id = coordinator.data["id"]
        self.entity_description = description
        self._attr_unique_id = (
            f'checkwattUid_{description.key}_{coordinator.data["id"]}'
        )
        self._attr_extra_state_attributes = {}

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


class CheckwattSensor(AbstractCheckwattSensor):
    """Representation of a CheckWatt sensor."""

    def __init__(
        self,
        coordinator: CheckwattCoordinator,
        description: SensorEntityDescription,
        use_detailed_attributes,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator, description=description)
        self.use_detailed_attributes = use_detailed_attributes
        self._attr_unique_id = f'checkwattUid_{self._coordinator.data["id"]}'

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
                if revenue > 0:
                    self._attr_extra_state_attributes[
                        C_TODAY_FEE_RATE
                    ] = f"{round((fees / revenue) * 100, 2)} %"
                else:
                    self._attr_extra_state_attributes[C_TODAY_FEE_RATE] = "N/A %"

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
                if tomorrow_revenue > 0:
                    self._attr_extra_state_attributes[
                        C_TOMORROW_FEE_RATE
                    ] = f"{round((tomorrow_fees / tomorrow_revenue) * 100, 2 )} %"
                else:
                    self._attr_extra_state_attributes[C_TOMORROW_FEE_RATE] = "N/A %"

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
        # Update the native value
        if "revenue" in self._coordinator.data and "fees" in self._coordinator.data:
            revenue = self._coordinator.data["revenue"]
            fees = self._coordinator.data["fees"]
            self._attr_native_value = round((revenue - fees), 2)
            if self.use_detailed_attributes:  # Only show these at detailed attribues
                self._attr_extra_state_attributes[C_TODAY_GROSS] = round(revenue, 2)
                self._attr_extra_state_attributes[C_TODAY_FEES] = round(fees, 2)
                if revenue > 0:
                    self._attr_extra_state_attributes[
                        C_TODAY_FEE_RATE
                    ] = f"{round((fees / revenue) * 100, 2)} %"
                else:
                    self._attr_extra_state_attributes[C_TODAY_FEE_RATE] = "N/A %"

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
                if revenue > 0:
                    self._attr_extra_state_attributes[
                        C_TOMORROW_FEE_RATE
                    ] = f"{round((tomorrow_fees / tomorrow_revenue) * 100, 2)} %"
                else:
                    self._attr_extra_state_attributes[C_TOMORROW_FEE_RATE] = "N/A %"

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


class CheckwattAnnualSensor(AbstractCheckwattSensor):
    """Representation of a CheckWatt Annual Revenue sensor."""

    def __init__(
        self,
        coordinator: CheckwattCoordinator,
        description: SensorEntityDescription,
        use_detailed_attributes,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator, description=description)
        self.use_detailed_attributes = use_detailed_attributes
        self._attr_unique_id = f'checkwattUid_Annual_{self._coordinator.data["id"]}'
        self.total_annual_revenue = None
        self.total_annual_fee = None

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
        if (
            "annual_revenue" in self._coordinator.data
            and "annual_fees" in self._coordinator.data
            and "revenue" in self._coordinator.data
            and "fees" in self._coordinator.data
            and "tomorrow_revenue" in self._coordinator.data
            and "tomorrow_fees" in self._coordinator.data
        ):
            # Annual revenue does not contain today and tomorrow revenue
            # and is only fetched once daily.
            # To obtain Total Annual revenue, it needs to be calculated
            annual_revenue = self._coordinator.data["annual_revenue"]
            annual_fees = self._coordinator.data["annual_fees"]
            today_revenue = self._coordinator.data["revenue"]
            today_fees = self._coordinator.data["fees"]
            tomorrow_revenue = self._coordinator.data["tomorrow_revenue"]
            tomorrow_fees = self._coordinator.data["tomorrow_fees"]
            self.total_annual_revenue = (
                annual_revenue + today_revenue + tomorrow_revenue
            )
            self.total_annual_fee = annual_fees + today_fees + tomorrow_fees
            self._attr_native_value = round(
                (self.total_annual_revenue - self.total_annual_fee), 2
            )

            if self.use_detailed_attributes:  # Only show these at detailed attribues
                self._attr_extra_state_attributes[C_ANNUAL_GROSS] = round(
                    self.total_annual_revenue, 2
                )
                self._attr_extra_state_attributes[C_ANNUAL_FEES] = round(
                    self.total_annual_fee, 2
                )
                self._attr_extra_state_attributes[
                    C_ANNUAL_FEE_RATE
                ] = f"{round((self.total_annual_fee / self.total_annual_revenue) * 100, 2)} %"

        self._attr_available = False

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        self._attr_available = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the states."""
        # Update the native value
        if (
            "annual_revenue" in self._coordinator.data
            and "annual_fees" in self._coordinator.data
            and "revenue" in self._coordinator.data
            and "fees" in self._coordinator.data
            and "tomorrow_revenue" in self._coordinator.data
            and "tomorrow_fees" in self._coordinator.data
        ):
            # Annual revenue does not contain today and tomorrow revenue
            # and is only fetched once daily.
            # To obtain Total Annual revenue, it needs to be calculated
            annual_revenue = self._coordinator.data["annual_revenue"]
            annual_fees = self._coordinator.data["annual_fees"]
            today_revenue = self._coordinator.data["revenue"]
            today_fees = self._coordinator.data["fees"]
            tomorrow_revenue = self._coordinator.data["tomorrow_revenue"]
            tomorrow_fees = self._coordinator.data["tomorrow_fees"]

            self.total_annual_revenue = (
                annual_revenue + today_revenue + tomorrow_revenue
            )

            self.total_annual_fee = annual_fees + today_fees + tomorrow_fees

            self._attr_native_value = round(
                (self.total_annual_revenue - self.total_annual_fee), 2
            )
            if self.use_detailed_attributes:  # Only show these at detailed attribues
                self._attr_extra_state_attributes[C_ANNUAL_GROSS] = round(
                    self.total_annual_revenue, 2
                )
                self._attr_extra_state_attributes[C_ANNUAL_FEES] = round(
                    self.total_annual_fee, 2
                )
                self._attr_extra_state_attributes[
                    C_ANNUAL_FEE_RATE
                ] = f"{round((self.total_annual_fee / self.total_annual_revenue) * 100, 2)} %"

        super()._handle_coordinator_update()

    @property
    def native_value(self) -> str | None:
        """Get the latest state value."""
        if self.total_annual_revenue is not None and self.total_annual_fee is not None:
            return round(
                self.total_annual_revenue - self.total_annual_fee,
                2,
            )
        return None


class CheckwattEnergySensor(AbstractCheckwattSensor):
    """Representation of a CheckWatt Energy sensor."""

    def __init__(
        self,
        coordinator: CheckwattCoordinator,
        description: SensorEntityDescription,
        data_key,
    ) -> None:
        """Initialize the sensor."""
        _LOGGER.debug("Creating %s sensor", description.name)
        super().__init__(coordinator=coordinator, description=description)
        self.data_key = data_key

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        self._attr_available = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the states."""
        self._attr_native_value = round(self._coordinator.data[self.data_key] / 1000, 2)
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> str | None:
        """Get the latest state value."""
        return round(self._coordinator.data[self.data_key] / 1000, 2)


class CheckwattSpotPriceSensor(AbstractCheckwattSensor):
    """Representation of a CheckWatt Spot-price sensor."""

    def __init__(
        self,
        coordinator: CheckwattCoordinator,
        description: SensorEntityDescription,
        vat_key,
    ) -> None:
        """Initialize the sensor."""
        _LOGGER.debug("Creating %s sensor", description.name)
        super().__init__(coordinator=coordinator, description=description)
        self.vat_key = vat_key

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        if "price_zone" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_PRICE_ZONE: self._coordinator.data["price_zone"]}
            )
            if self.vat_key == "inc_vat":
                self._attr_extra_state_attributes.update({C_VAT: "25%"})
        self._attr_available = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the states."""
        if self.vat_key == "inc_vat":
            self._attr_native_value = round(
                self._coordinator.data["spot_price"] * 1.25, 3
            )
        else:
            self._attr_native_value = self._coordinator.data["spot_price"]
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> str | None:
        """Get the latest state value."""
        if self.vat_key == "inc_vat":
            return round(self._coordinator.data["spot_price"] * 1.25, 3)
        return round(self._coordinator.data["spot_price"], 3)
