"""Module for SIA Binary Sensors."""

import logging
import time
from typing import Callable

from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT as BINARY_SENSOR_FORMAT,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ZONE, STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util.dt import utcnow

from .const import (
    CONF_ACCOUNT,
    CONF_PING_INTERVAL,
    DATA_UPDATED,
    DOMAIN,
    PING_INTERVAL_MARGIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass, entry: ConfigEntry, async_add_devices: Callable[[], None]
) -> bool:
    """Set up sia_binary_sensor from a config entry."""
    async_add_devices(
        [
            device
            for device in hass.data[DOMAIN][entry.entry_id].states.values()
            if isinstance(device, SIABinarySensor)
        ]
    )

    return True


class SIABinarySensor(BinarySensorEntity, RestoreEntity):
    """Class for SIA Binary Sensors."""

    def __init__(
        self,
        entity_id: str,
        name: str,
        device_class: str,
        port: int,
        account: str,
        zone: int,
        ping_interval: int,
    ):
        """Create SIABinarySensor object."""
        self.entity_id = BINARY_SENSOR_FORMAT.format(entity_id)
        self._unique_id = entity_id
        self._name = name
        self._device_class = device_class
        self._port = port
        self._account = account
        self._zone = zone
        self._ping_interval = ping_interval

        self._should_poll = False
        self._is_on = None
        self._is_available = True
        self._remove_unavailability_tracker = None
        self._attr = {
            CONF_ACCOUNT: self._account,
            CONF_PING_INTERVAL: str(self._ping_interval),
            CONF_ZONE: self._zone,
        }

    async def async_added_to_hass(self):
        """Add sensor to HASS."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state is not None:
            if state.state == STATE_ON:
                self._is_on = True
            elif state.state == STATE_OFF:
                self._is_on = False
        await self._async_track_unavailable()
        async_dispatcher_connect(
            self.hass, DATA_UPDATED, self._schedule_immediate_update
        )

    @callback
    def _schedule_immediate_update(self):
        """Schedule update."""
        self.async_schedule_update_ha_state(True)

    @property
    def name(self) -> str:
        """Return name."""
        return self._name

    @property
    def ping_interval(self) -> int:
        """Get ping_interval."""
        return str(self._ping_interval)

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        return self._unique_id

    @property
    def account(self) -> str:
        """Return device account."""
        return self._account

    @property
    def available(self) -> bool:
        """Return avalability."""
        return self._is_available

    @property
    def device_state_attributes(self) -> dict:
        """Return attributes."""
        return self._attr

    @property
    def device_class(self) -> str:
        """Return device class."""
        return self._device_class

    @property
    def state(self) -> str:
        """Return the state of the binary sensor."""
        if self.is_on is None:
            return STATE_UNKNOWN
        return STATE_ON if self.is_on else STATE_OFF

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._is_on

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False

    @state.setter
    def state(self, new_on: bool):
        """Set state."""
        self._is_on = new_on
        if not self.registry_entry.disabled:
            self.async_schedule_update_ha_state()

    async def assume_available(self):
        """Reset unavalability tracker."""
        if not self.registry_entry.disabled:
            await self._async_track_unavailable()

    @callback
    async def _async_track_unavailable(self) -> bool:
        """Track availability."""
        if self._remove_unavailability_tracker:
            self._remove_unavailability_tracker()
        self._remove_unavailability_tracker = async_track_point_in_utc_time(
            self.hass,
            self._async_set_unavailable,
            utcnow() + self._ping_interval + PING_INTERVAL_MARGIN,
        )
        if not self._is_available:
            self._is_available = True
            return True
        return False

    @callback
    def _async_set_unavailable(self, now):
        """Set unavailable."""
        self._remove_unavailability_tracker = None
        self._is_available = False
        self.async_schedule_update_ha_state()

    @property
    def device_info(self) -> dict:
        """Return the device_info."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "via_device": (DOMAIN, self._port, self._account),
        }
