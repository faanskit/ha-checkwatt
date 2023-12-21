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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CheckwattCoordinator, CheckwattResp
from .const import (
    C_ADR,
    C_CITY,
    C_FCRD_DATE,
    C_FCRD_STATE,
    C_FCRD_STATUS,
    C_NEXT_UPDATE_TIME,
    C_TOMORROW,
    C_UPDATE_TIME,
    C_ZIP,
    CHECKWATT_MODEL,
    CONF_DETAILED_ATTRIBUTES,
    CONF_DETAILED_SENSORS,
    DOMAIN,
    MANUFACTURER,
)

ICON_CASH = "mdi:account-cash"

SCAN_INTERVAL = timedelta(minutes=1)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)
PARALLEL_UPDATES = 0

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
    async_add_entities(entities, True)

    if use_detailed_sensors:
        _LOGGER.debug(
            "Setting up detailed Checkwatt sensors for %s",
            checkwatt_data["display_name"],
        )
        # TODO
        # Add additional sensors required


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

        self._attr_extra_state_attributes = {
            C_ADR: self._coordinator.data["address"],
            C_ZIP: self._coordinator.data["zip"],
            C_CITY: self._coordinator.data["city"],
            C_TOMORROW: self._coordinator.data["tomorrow_revenue"],
        }
        if use_detailed_attributes:
            # Add extra attributes as required
            self._attr_extra_state_attributes.update(
                {C_UPDATE_TIME: self._coordinator.data["update_time"]}
            )
            self._attr_extra_state_attributes.update(
                {C_NEXT_UPDATE_TIME: self._coordinator.data["next_update_time"]}
            )
            self._attr_extra_state_attributes.update(
                {C_FCRD_STATUS: self._coordinator.data["fcr_d_status"]}
            )
            self._attr_extra_state_attributes.update(
                {C_FCRD_STATE: self._coordinator.data["fcr_d_state"]}
            )
            self._attr_extra_state_attributes.update(
                {C_FCRD_DATE: self._coordinator.data["fcr_d_date"]}
            )

        self._attr_available = True

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        self._attr_available = True
        self._attr_extra_state_attributes[C_ADR] = self._coordinator.data["address"]
        self._attr_extra_state_attributes[C_ZIP] = self._coordinator.data["zip"]
        self._attr_extra_state_attributes[C_CITY] = self._coordinator.data["city"]
        self._attr_extra_state_attributes[C_TOMORROW] = self._coordinator.data[
            "tomorrow_revenue"
        ]
        if self.use_detailed_attributes:
            self._attr_extra_state_attributes.update(
                {C_UPDATE_TIME: self._coordinator.data["update_time"]}
            )
            self._attr_extra_state_attributes.update(
                {C_NEXT_UPDATE_TIME: self._coordinator.data["next_update_time"]}
            )
            self._attr_extra_state_attributes.update(
                {C_FCRD_STATUS: self._coordinator.data["fcr_d_status"]}
            )
            self._attr_extra_state_attributes.update(
                {C_FCRD_STATE: self._coordinator.data["fcr_d_state"]}
            )
            self._attr_extra_state_attributes.update(
                {C_FCRD_DATE: self._coordinator.data["fcr_d_date"]}
            )

    @property
    def native_value(self) -> str | None:
        """Get the latest state value."""
        return self._coordinator.data["revenue"]
