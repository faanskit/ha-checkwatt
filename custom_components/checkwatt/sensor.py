"""Support for Checkwatt sensors."""
from __future__ import annotations

import datetime
from datetime import timedelta
import logging

from homeassistant.components.sensor import (
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CheckwattCoordinator, CheckwattResponse
from .const import (
    DOMAIN,
    MANUFACTURER,
    CHECKWATT_MODEL,
    CONF_DETAILED_SENSORS,
    C_ADR,
    C_ZIP,
    C_CITY,
)

ICON_POWER = "mdi:solar-power"  #TODO
ICON_PANEL = "mdi:solar-panel"

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
    checkwatt_data: CheckwattResponse = coordinator.data
    use_detailed_sensors = entry.options.get(CONF_DETAILED_SENSORS)

    _LOGGER.debug(
        "Setting up Checkwatt sensor for %s", checkwatt_data["plantname"]
    )
    entities.append(
        CheckwattSensor(coordinator, use_detailed_sensors)
    )
    async_add_entities(entities, True)


class CheckwattTemplateSensor(CoordinatorEntity[CheckwattCoordinator], SensorEntity):
    """Representation of a generic Checkwatt sensor."""

    def __init__(self, coordinator: CheckwattCoordinator, use_detailed_sensors) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._use_detailed_sensors = use_detailed_sensors
        self._id = self._coordinator.data["Meter"][0]["Id"]
        self._attr_unique_id = f"checkwattUid_{self._coordinator.data['Meter'][0]['FacilityId']}"
        self._device_name = f"{self._coordinator.data['Meter'][0]['DisplayName']}"
        self._device_model = CHECKWATT_MODEL

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
    """Representation of a eSolar sensor for the plant."""

    def __init__(self, coordinator: CheckwattCoordinator, plant_name, plant_uid) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator, plant_name=plant_name, plant_uid=plant_uid
        )
        self._last_updated: datetime.datetime | None = None

        self._attr_icon = ICON_PANEL
        self._attr_name = f"Checkwatt {self._device_name} Status"

        self._attr_extra_state_attributes = {
            C_ADR: f"{self._coordinator.data['Meter'][0]['StreetAddress']}",
            C_ZIP: f"{self._coordinator.data['Meter'][0]['ZipCode']}",
            C_CITY: f"{self._coordinator.data['Meter'][0]['City']}",
        }
        self._attr_available = True

    async def async_update(self) -> None:
        """Get the latest data and updates the states."""
        # Setup static attributes
        self._attr_available = True
        self._attr_extra_state_attributes[C_ADR] = f"{self._coordinator.data['Meter'][0]['StreetAddress']}"
        self._attr_extra_state_attributes[C_ZIP] = f"{self._coordinator.data['Meter'][0]['ZipCode']}"
        self._attr_extra_state_attributes[C_CITY] = f"{self._coordinator.data['Meter'][0]['City']}"

    @property
    def native_value(self) -> str | None:
        return f"{self._coordinator.data['Meter'][0]['ProcessStatus']}"
