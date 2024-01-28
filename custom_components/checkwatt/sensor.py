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
from homeassistant.const import PERCENTAGE, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CheckwattCoordinator, CheckwattResp
from .const import (
    ATTRIBUTION,
    C_ADR,
    C_BATTERY_POWER,
    C_CHARGE_PEAK_AC,
    C_CHARGE_PEAK_DC,
    C_CITY,
    C_CM10_VERSION,
    C_DAILY_AVERAGE,
    C_DISCHARGE_PEAK_AC,
    C_DISCHARGE_PEAK_DC,
    C_DISPLAY_NAME,
    C_DSO,
    C_ENERGY_PROVIDER,
    C_FCRD_DATE,
    C_FCRD_INFO,
    C_FCRD_STATUS,
    C_GRID_POWER,
    C_MONTH_ESITIMATE,
    C_NEXT_UPDATE_TIME,
    C_PRICE_ZONE,
    C_SOLAR_POWER,
    C_UPDATE_TIME,
    C_VAT,
    C_ZIP,
    CHECKWATT_MODEL,
    CONF_CM10_SENSOR,
    CONF_POWER_SENSORS,
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
    "monthly": SensorEntityDescription(
        key="monthly_yield",
        name="CheckWatt Monthly Yield",
        icon="mdi:account-cash-outline",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="SEK",
        state_class=SensorStateClass.TOTAL,
        translation_key="monthly_yield_sensor",
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
    "battery": SensorEntityDescription(
        key="battery_soc",
        name="CheckWatt Battery SoC",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="battery_soc_sensor",
    ),
    "cm10": SensorEntityDescription(
        key="cm10",
        name="CheckWatt CM10 Status",
        icon="mdi:raspberry-pi",
        translation_key="cm10_sensor",
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
        name="Spot Price incl. VAT",
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
    use_power_sensors = entry.options.get(CONF_POWER_SENSORS)
    use_cm10_sensor = entry.options.get(CONF_CM10_SENSOR)

    _LOGGER.debug("Setting up CheckWatt sensor for %s", checkwatt_data["display_name"])
    for key, description in CHECKWATT_MONETARY_SENSORS.items():
        if key == "daily":
            entities.append(CheckwattSensor(coordinator, description))
        elif key == "monthly":
            entities.append(CheckwattMonthlySensor(coordinator, description))
        elif key == "annual":
            entities.append(CheckwattAnnualSensor(coordinator, description))
        elif key == "battery":
            entities.append(CheckwattBatterySoCSensor(coordinator, description))
        elif key == "cm10" and use_cm10_sensor:
            entities.append(CheckwattCM10Sensor(coordinator, description))

    if use_power_sensors:
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
        _LOGGER.debug("Creating %s sensor", description.name)
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
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator, description=description)
        self._attr_unique_id = f'checkwattUid_{self._coordinator.data["id"]}'

        self._attr_extra_state_attributes = {}
        if "display_name" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_DISPLAY_NAME: self._coordinator.data["display_name"]}
            )
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
        if "dso" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_DSO: self._coordinator.data["dso"]}
            )
        if "energy_provider" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_ENERGY_PROVIDER: self._coordinator.data["energy_provider"]}
            )
        if "update_time" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_UPDATE_TIME: self._coordinator.data["update_time"]}
            )
        if "next_update_time" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_NEXT_UPDATE_TIME: self._coordinator.data["next_update_time"]}
            )

        self._attr_available = False

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        self._attr_available = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the states."""
        if "update_time" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_UPDATE_TIME: self._coordinator.data["update_time"]}
            )
        if "next_update_time" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_NEXT_UPDATE_TIME: self._coordinator.data["next_update_time"]}
            )
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> str | None:
        """Get the latest state value."""
        if "today_net_revenue" in self._coordinator.data:
            return round(self._coordinator.data["today_net_revenue"], 2)
        return None


class CheckwattMonthlySensor(AbstractCheckwattSensor):
    """Representation of a CheckWatt Monthly Revenue sensor."""

    def __init__(
        self,
        coordinator: CheckwattCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator, description=description)
        self._attr_unique_id = f'checkwattUid_Monthly_{self._coordinator.data["id"]}'
        self._attr_extra_state_attributes = {}
        self._attr_available = False

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        if "month_estimate" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_MONTH_ESITIMATE: round(self._coordinator.data["month_estimate"], 2)}
            )
        if "daily_average" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_DAILY_AVERAGE: round(self._coordinator.data["daily_average"], 2)}
            )
        self._attr_available = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the states."""
        self._attr_native_value = round(
            self._coordinator.data["monthly_net_revenue"], 2
        )
        if "month_estimate" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_MONTH_ESITIMATE: round(self._coordinator.data["month_estimate"], 2)}
            )
        if "daily_average" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_DAILY_AVERAGE: round(self._coordinator.data["daily_average"], 2)}
            )
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> str | None:
        """Get the latest state value."""
        if "monthly_net_revenue" in self._coordinator.data:
            return round(self._coordinator.data["monthly_net_revenue"], 2)
        return None


class CheckwattAnnualSensor(AbstractCheckwattSensor):
    """Representation of a CheckWatt Annual Revenue sensor."""

    def __init__(
        self,
        coordinator: CheckwattCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator, description=description)
        self._attr_unique_id = f'checkwattUid_Annual_{self._coordinator.data["id"]}'
        self._attr_extra_state_attributes = {}
        self._attr_available = False

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        self._attr_available = False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the states."""
        self._attr_native_value = round(self._coordinator.data["annual_net_revenue"], 2)
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> str | None:
        """Get the latest state value."""
        if "annual_net_revenue" in self._coordinator.data:
            return round(self._coordinator.data["annual_net_revenue"], 2)
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


class CheckwattBatterySoCSensor(AbstractCheckwattSensor):
    """Representation of a CheckWatt Battery SoC sensor."""

    def __init__(
        self,
        coordinator: CheckwattCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator, description=description)

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        if "battery_power" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_BATTERY_POWER: self._coordinator.data["battery_power"]}
            )
        if "grid_power" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_GRID_POWER: self._coordinator.data["grid_power"]}
            )
        if "solar_power" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_SOLAR_POWER: self._coordinator.data["solar_power"]}
            )
        if "charge_peak_ac" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_CHARGE_PEAK_AC: self._coordinator.data["charge_peak_ac"]}
            )
        if "charge_peak_dc" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_CHARGE_PEAK_DC: self._coordinator.data["charge_peak_dc"]}
            )
        if "discharge_peak_ac" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_DISCHARGE_PEAK_AC: self._coordinator.data["discharge_peak_ac"]}
            )
        if "discharge_peak_dc" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_DISCHARGE_PEAK_DC: self._coordinator.data["discharge_peak_dc"]}
            )
        self._attr_available = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the states."""
        if "battery_soc" in self._coordinator.data:
            self._attr_native_value = self._coordinator.data["battery_soc"]
        if "battery_power" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_BATTERY_POWER: self._coordinator.data["battery_power"]}
            )
        if "grid_power" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_GRID_POWER: self._coordinator.data["grid_power"]}
            )
        if "solar_power" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_SOLAR_POWER: self._coordinator.data["solar_power"]}
            )
        if "charge_peak_ac" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_CHARGE_PEAK_AC: self._coordinator.data["charge_peak_ac"]}
            )
        if "charge_peak_dc" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_CHARGE_PEAK_DC: self._coordinator.data["charge_peak_dc"]}
            )
        if "discharge_peak_ac" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_DISCHARGE_PEAK_AC: self._coordinator.data["discharge_peak_ac"]}
            )
        if "discharge_peak_dc" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_DISCHARGE_PEAK_DC: self._coordinator.data["discharge_peak_dc"]}
            )
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> str | None:
        """Get the latest state value."""
        return self._coordinator.data["battery_soc"]


class CheckwattCM10Sensor(AbstractCheckwattSensor):
    """Representation of a CheckWatt CM10 sensor."""

    def __init__(
        self,
        coordinator: CheckwattCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator, description=description)

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        if "cm10_version" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_CM10_VERSION: self._coordinator.data["cm10_version"]}
            )
        if "fcr_d_status" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_FCRD_STATUS: self._coordinator.data["fcr_d_status"]}
            )
        if "fcr_d_info" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_FCRD_INFO: self._coordinator.data["fcr_d_info"]}
            )
        if "fcr_d_date" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_FCRD_DATE: self._coordinator.data["fcr_d_date"]}
            )
        self._attr_available = True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the states."""
        if "cm10_status" in self._coordinator.data:
            cm10_status = self._coordinator.data["cm10_status"]
            if cm10_status is not None:
                self._attr_native_value = cm10_status.capitalize()
            else:
                self._attr_native_value = None
        if "cm10_version" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_CM10_VERSION: self._coordinator.data["cm10_version"]}
            )
        if "fcr_d_status" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_FCRD_STATUS: self._coordinator.data["fcr_d_status"]}
            )
        if "fcr_d_info" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_FCRD_INFO: self._coordinator.data["fcr_d_info"]}
            )
        if "fcr_d_date" in self._coordinator.data:
            self._attr_extra_state_attributes.update(
                {C_FCRD_DATE: self._coordinator.data["fcr_d_date"]}
            )
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> str | None:
        """Get the latest state value."""
        if "cm10_status" in self._coordinator.data:
            cm10_status = self._coordinator.data["cm10_status"]
            if cm10_status is not None:
                return cm10_status.capitalize()
        return None
