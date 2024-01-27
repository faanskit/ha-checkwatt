"""Events for CheckWatt."""

from __future__ import annotations

import logging

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CheckwattCoordinator, CheckwattResp
from .const import ATTRIBUTION, CHECKWATT_MODEL, DOMAIN, EVENT_SIGNAL_FCRD, MANUFACTURER

EVENT_FCRD_ACTIVATED = "fcrd_activated"
EVENT_FCRD_DEACTIVATED = "fcrd_deactivated"
EVENT_FCRD_FAILED = "fcrd_failed"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the CheckWatt event platform."""
    coordinator: CheckwattCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[AbstractCheckwattEvent] = []
    checkwatt_data: CheckwattResp = coordinator.data
    _LOGGER.debug(
        "Setting up detailed CheckWatt event for %s",
        checkwatt_data["display_name"],
    )

    event_description = EventEntityDescription(
        key="fcr_d_event",
        name="FCR-D State",
        icon="mdi:battery-alert",
        device_class="fcrd",
        translation_key="fcr_d_event",
    )

    entities.append(CheckWattFCRDEvent(coordinator, event_description))
    async_add_entities(entities, True)


class AbstractCheckwattEvent(CoordinatorEntity[CheckwattCoordinator], EventEntity):
    """Abstract class for an CheckWatt event."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CheckwattCoordinator,
        description: EventEntity,
    ) -> None:
        """Initialize the event."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._device_model = CHECKWATT_MODEL
        self._device_name = coordinator.data["display_name"]
        self._id = coordinator.data["id"]
        self.entity_description = description
        self._attr_unique_id = (
            f'checkwattUid_{description.key}_{coordinator.data["id"]}'
        )

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


class CheckWattFCRDEvent(AbstractCheckwattEvent):
    """Representation of a CheckWatt sleep event."""

    _attr_event_types = [
        EVENT_FCRD_ACTIVATED,
        EVENT_FCRD_DEACTIVATED,
        EVENT_FCRD_FAILED,
    ]

    def __init__(
        self,
        coordinator: CheckwattCoordinator,
        description: EventEntityDescription,
    ) -> None:
        """Initialize the CheckWatt event entity."""
        super().__init__(coordinator=coordinator, description=description)
        self._coordinator = coordinator

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"checkwatt_{self._id}_signal",
                self.handle_event,
            ),
        )

        # Send the status upon boot
        if "fcr_d_status" in self._coordinator.data:
            event = None
            if self._coordinator.data["fcr_d_status"] == "ACTIVATED":
                event = EVENT_FCRD_ACTIVATED
            elif self._coordinator.data["fcr_d_status"] == "DEACTIVATE":
                event = EVENT_FCRD_DEACTIVATED
            elif self._coordinator.data["fcr_d_status"] == "FAIL ACTIVATION":
                event = EVENT_FCRD_FAILED

            if event is not None:
                self._trigger_event(event)
                self.async_write_ha_state()

    @callback
    def handle_event(self, signal_payload) -> None:
        """Handle received event."""
        event = None
        if "signal" in signal_payload and signal_payload["signal"] == EVENT_SIGNAL_FCRD:
            if (
                "new_fcrd" in signal_payload["data"]
                and "state" in signal_payload["data"]["new_fcrd"]
            ):
                if signal_payload["data"]["new_fcrd"]["state"] == "ACTIVATED":
                    event = EVENT_FCRD_ACTIVATED
                elif signal_payload["data"]["new_fcrd"]["state"] == "DEACTIVATE":
                    event = EVENT_FCRD_DEACTIVATED
                elif signal_payload["data"]["new_fcrd"]["state"] == "FAIL ACTIVATION":
                    event = EVENT_FCRD_FAILED

            else:
                _LOGGER.error(
                    "Signal %s payload did not include correct data", EVENT_SIGNAL_FCRD
                )

        # Add additional signals and events here
        # Eg:
        # elif signal_payload["signal"] == EVENT_SIGNAL_NEW

        else:
            _LOGGER.error("Signal did not include a known signal")

        if event is not None:
            self._trigger_event(event)
            self.async_write_ha_state()
